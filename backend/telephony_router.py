import json
from typing import Dict
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from backend.voice_agent import DiagnosticVoiceAgent

telephony_router = APIRouter(prefix="/api/telephony", tags=["Telephony"])

# Active sessions store for in-flight telephone/simulated calls
active_sessions: Dict[str, DiagnosticVoiceAgent] = {}

@telephony_router.post("/twilio/incoming")
async def twilio_incoming_call(request: Request):
    """
    Production Twilio Inbound Voice Webhook.
    Triggered when any user dials the Diagnostic Lab from their personal telephone.
    """
    form_data = await request.form()
    caller_phone = form_data.get("From", "+1 (555) 000-0000")
    call_sid = form_data.get("CallSid", "TWILIO-CALL-UNKNOWN")

    agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
    active_sessions[call_sid] = agent

    greeting_data = agent.get_initial_greeting()
    greeting_text = greeting_data["speech"]

    # Generate standard TwiML XML response with speech recognition gather
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural" language="en-US">{greeting_text}</Say>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="5">
        <Say voice="Polly.Joanna-Neural">I am listening. Please let me know how I can assist you.</Say>
    </Gather>
    <Redirect>/api/telephony/twilio/turn?call_sid={call_sid}</Redirect>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")

@telephony_router.post("/twilio/turn")
async def twilio_speech_turn(request: Request, call_sid: str = ""):
    """
    Handles subsequent spoken turns from Twilio Speech-to-Text.
    """
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "").strip()
    agent = active_sessions.get(call_sid)

    if not agent:
        agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 000-0000", call_sid=call_sid)
        active_sessions[call_sid] = agent

    if not speech_result:
        # Prompt user if silent
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="5">
        <Say voice="Polly.Joanna-Neural">Are you still there? You can ask me to book a blood test, check your report, or ask about fasting.</Say>
    </Gather>
    <Say voice="Polly.Joanna-Neural">Thank you for calling Apex MediLab. Goodbye!</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Process turn with AI voice agent
    turn_result = agent.process_turn(speech_result)
    reply_speech = turn_result["speech"]

    if turn_result.get("intent") == "emergency":
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{reply_speech}</Say>
    <Hangup/>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{reply_speech}</Say>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="6">
    </Gather>
    <Say voice="Polly.Joanna-Neural">Thank you for contacting Apex MediLab. We wish you good health!</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")

@telephony_router.post("/livekit/token")
async def livekit_token_generator(request: Request):
    """
    Generates LiveKit WebRTC token for browser or SIP inbound voice participant.
    """
    data = await request.json()
    caller_phone = data.get("phone", "+1 (555) 234-5678")
    room_name = f"medilab-call-{caller_phone.replace('+', '').replace(' ', '')}"

    # In blank environment mode, return simulated room configuration
    return {
        "room": room_name,
        "identity": caller_phone,
        "token": "simulated_livekit_token_ready",
        "ws_url": "wss://livekit.example.com",
        "status": "ready"
    }

async def handle_phone_call_websocket(websocket: WebSocket):
    """
    Interactive Browser Phone Call Simulator WebSocket.
    Allows testing the complete personal phone call experience directly in the browser!
    """
    await websocket.accept()
    agent: DiagnosticVoiceAgent = None
    call_sid: str = None

    try:
        while True:
            raw_data = await websocket.receive_text()
            message = json.loads(raw_data)
            msg_type = message.get("type")

            if msg_type == "initiate_call":
                caller_phone = message.get("caller_phone", "+1 (555) 234-5678")
                call_sid = f"SIM-CALL-{int(time_timestamp())}"
                agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
                active_sessions[call_sid] = agent

                greeting = agent.get_initial_greeting()
                await websocket.send_text(json.dumps({
                    "type": "call_connected",
                    "call_sid": call_sid,
                    "caller_name": greeting["caller_name"],
                    "caller_phone": caller_phone,
                    "is_returning": greeting["is_returning_patient"],
                    "speech": greeting["speech"]
                }))

            elif msg_type == "user_speech":
                user_text = message.get("text", "")
                if agent:
                    result = agent.process_turn(user_text)
                    await websocket.send_text(json.dumps({
                        "type": "agent_response",
                        "speech": result["speech"],
                        "intent": result["intent"],
                        "tool_executed": result.get("tool_executed"),
                        "actions_taken": result.get("actions_taken", []),
                        "citations": result.get("citations", []),
                        "extra": result
                    }))

            elif msg_type == "hangup":
                if agent:
                    agent.actions_taken.append("Call Completed & Hung Up by Caller")
                await websocket.send_text(json.dumps({
                    "type": "call_ended",
                    "message": "Call successfully ended. Call logs and actions updated."
                }))
                break

    except WebSocketDisconnect:
        pass
    finally:
        if call_sid and call_sid in active_sessions:
            del active_sessions[call_sid]

def time_timestamp():
    import time
    return time.time()
