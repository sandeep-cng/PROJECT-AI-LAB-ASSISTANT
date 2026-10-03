import os
import json
import time
from typing import Dict
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, JSONResponse
import httpx

from backend.voice_agent import DiagnosticVoiceAgent, normalize_phone

telephony_router = APIRouter(prefix="/api/telephony", tags=["Telephony"])

# Active sessions store for in-flight telephone/simulated calls
active_sessions: Dict[str, DiagnosticVoiceAgent] = {}

def time_timestamp():
    return time.time()

# ==============================================================================
# 1. EXOTEL CLOUD TELEPHONY INTEGRATION (INDIA & GLOBAL)
# Full support for Inbound Webhooks, Barge-In interruption, and Status Callbacks
# ==============================================================================

@telephony_router.api_route("/exotel/incoming", methods=["GET", "POST"])
async def exotel_incoming_call(request: Request):
    """
    Exotel Inbound Voice Webhook.
    Triggered when a caller dials an Exotel Virtual Number (ExoPhone).
    Supports automatic caller ID recognition and Barge-In (bargin="true").
    """
    params = {}
    if request.method == "POST":
        try:
            form = await request.form()
            params = dict(form)
        except Exception:
            params = {}
    else:
        params = dict(request.query_params)

    caller_phone = params.get("From", params.get("CallFrom", "+919876543210"))
    call_sid = params.get("CallSid", f"EXOTEL-CALL-{int(time_timestamp())}")

    agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
    active_sessions[call_sid] = agent

    greeting_data = agent.get_initial_greeting()
    greeting_text = greeting_data["speech"]

    # Exotel Voice Markup with instant Barge-In enabled (bargin="true")
    exotel_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/api/telephony/exotel/turn?call_sid={call_sid}" method="POST" timeout="6" bargin="true">
        <Say voice="female" language="en-IN">{greeting_text}</Say>
    </Gather>
    <Say voice="female" language="en-IN">I am here whenever you are ready. Please feel free to ask about our tests, reports, or fasting.</Say>
    <Gather action="/api/telephony/exotel/turn?call_sid={call_sid}" method="POST" timeout="8" bargin="true"/>
    <Hangup/>
</Response>"""
    return Response(content=exotel_response, media_type="application/xml")


@telephony_router.api_route("/exotel/turn", methods=["GET", "POST"])
async def exotel_speech_turn(request: Request, call_sid: str = ""):
    """
    Processes subsequent spoken/DTMF turns from Exotel with Barge-In capability.
    """
    params = {}
    if request.method == "POST":
        try:
            form = await request.form()
            params = dict(form)
        except Exception:
            params = {}
    else:
        params = dict(request.query_params)

    call_sid = call_sid or params.get("CallSid", "")
    speech_result = params.get("SpeechResult", params.get("Digits", "")).strip()

    agent = active_sessions.get(call_sid)
    if not agent:
        caller_phone = params.get("From", "+919876543210")
        agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
        active_sessions[call_sid] = agent

    if not speech_result:
        # Prompt user if silent
        xml_prompt = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/api/telephony/exotel/turn?call_sid={call_sid}" method="POST" timeout="6" bargin="true">
        <Say voice="female" language="en-IN">Are you still there? You can book a doorstep sample draw, clinic visit, or check fasting rules.</Say>
    </Gather>
    <Say voice="female" language="en-IN">Thank you for contacting Apex Family Diagnostic Lab. Stay healthy!</Say>
    <Hangup/>
</Response>"""
        return Response(content=xml_prompt, media_type="application/xml")

    # Process spoken turn
    turn_result = agent.process_turn(speech_result)
    reply_speech = turn_result["speech"]
    human_phone = os.getenv("HUMAN_ASSISTANT_PHONE_NUMBER", os.getenv("DUTY_DOCTOR_PHONE_NUMBER", "+15624388802"))

    if turn_result.get("intent") in ["emergency_transfer", "human_handover", "human_handover_ambiguity"]:
        xml_reply = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="female" language="en-IN">{reply_speech}</Say>
    <!-- Direct Transfer to Senior Human Assistant / Duty Medical Officer Desk -->
    <Dial timeout="25">{human_phone}</Dial>
</Response>"""
    else:
        xml_reply = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="/api/telephony/exotel/turn?call_sid={call_sid}" method="POST" timeout="6" bargin="true">
        <Say voice="female" language="en-IN">{reply_speech}</Say>
    </Gather>
    <Say voice="female" language="en-IN">Thank you for calling Apex Diagnostic Care. Have a wonderful day!</Say>
    <Hangup/>
</Response>"""

    return Response(content=xml_reply, media_type="application/xml")


@telephony_router.api_route("/exotel/status", methods=["GET", "POST"])
async def exotel_status_callback(request: Request):
    """
    Exotel Call Status & Disconnect Callback.
    Logs final duration, recording status, and cleans up active sessions.
    """
    params = {}
    if request.method == "POST":
        try:
            form = await request.form()
            params = dict(form)
        except Exception:
            params = {}
    else:
        params = dict(request.query_params)

    call_sid = params.get("CallSid", "")
    duration = params.get("DialCallDuration", params.get("Legs[0][Duration]", "0"))

    if call_sid in active_sessions:
        agent = active_sessions[call_sid]
        agent.actions_taken.append(f"Exotel Call Completed (Duration: {duration}s)")
        del active_sessions[call_sid]

    return JSONResponse({"status": "received", "call_sid": call_sid})


@telephony_router.post("/exotel/call")
async def exotel_outbound_call(request: Request):
    """
    Initiates outbound call to patient via Exotel REST API.
    """
    data = await request.json()
    to_phone = data.get("phone", "")
    if not to_phone:
        return JSONResponse({"error": "phone number required"}, status_code=400)

    account_sid = os.getenv("EXOTEL_ACCOUNT_SID", "")
    api_key = os.getenv("EXOTEL_API_KEY", "")
    api_token = os.getenv("EXOTEL_API_TOKEN", "")
    subdomain = os.getenv("EXOTEL_SUBDOMAIN", "api.exotel.com")
    virtual_number = os.getenv("EXOTEL_VIRTUAL_NUMBER", "")
    app_id = os.getenv("EXOTEL_APP_ID", "")

    if not (account_sid and api_key and api_token):
        return {
            "status": "simulated",
            "message": "Exotel credentials not configured in .env. Operating in Zero-Config simulation mode.",
            "call_sid": f"EXO-SIM-{int(time_timestamp())}",
            "to": to_phone
        }

    url = f"https://{api_key}:{api_token}@{subdomain}/v1/Accounts/{account_sid}/Calls/connect.json"
    payload = {
        "From": to_phone,
        "CallerId": virtual_number,
        "Url": f"http://{request.headers.get('host', 'localhost:8000')}/api/telephony/exotel/incoming"
    }
    if app_id:
        payload["AppId"] = app_id

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=payload, timeout=10.0)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ==============================================================================
# 2. TWILIO CLOUD TELEPHONY (WITH INSTANT BARGE-IN)
# ==============================================================================

@telephony_router.post("/twilio/incoming")
async def twilio_incoming_call(request: Request):
    """
    Production Twilio Inbound Voice Webhook with immediate Barge-In support.
    """
    form_data = await request.form()
    caller_phone = form_data.get("From", "+1 (555) 000-0000")
    call_sid = form_data.get("CallSid", f"TWILIO-{int(time_timestamp())}")

    agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
    active_sessions[call_sid] = agent

    greeting_data = agent.get_initial_greeting()
    greeting_text = greeting_data["speech"]

    # Wrap Say INSIDE Gather with bargeIn="true" so Polly cuts off immediately when user speaks!
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="6" bargeIn="true">
        <Say voice="Polly.Joanna-Neural" language="en-US">{greeting_text}</Say>
    </Gather>
    <Redirect>/api/telephony/twilio/turn?call_sid={call_sid}</Redirect>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")


@telephony_router.post("/twilio/turn")
async def twilio_speech_turn(request: Request, call_sid: str = ""):
    """
    Handles subsequent spoken turns from Twilio Speech-to-Text with Barge-In.
    """
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "").strip()
    agent = active_sessions.get(call_sid)

    if not agent:
        agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 000-0000", call_sid=call_sid)
        active_sessions[call_sid] = agent

    if not speech_result:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="5" bargeIn="true">
        <Say voice="Polly.Joanna-Neural">Are you still there? You can ask me to book a blood test, check your report, or ask about fasting.</Say>
    </Gather>
    <Say voice="Polly.Joanna-Neural">Thank you for calling Apex MediLab. Goodbye!</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    turn_result = agent.process_turn(speech_result)
    reply_speech = turn_result["speech"]
    human_phone = os.getenv("HUMAN_ASSISTANT_PHONE_NUMBER", os.getenv("DUTY_DOCTOR_PHONE_NUMBER", "+15624388802"))

    if turn_result.get("intent") in ["emergency_transfer", "human_handover", "human_handover_ambiguity"]:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{reply_speech}</Say>
    <!-- Direct Transfer to Senior Human Assistant / Duty Medical Officer Desk -->
    <Dial timeout="25">{human_phone}</Dial>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/api/telephony/twilio/turn?call_sid={call_sid}" method="POST" speechTimeout="auto" timeout="6" bargeIn="true">
        <Say voice="Polly.Joanna-Neural">{reply_speech}</Say>
    </Gather>
    <Say voice="Polly.Joanna-Neural">Thank you for contacting Apex MediLab. We wish you good health!</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# ==============================================================================
# 3. WEBRTC & REST CHAT SESSIONS
# ==============================================================================

@telephony_router.post("/livekit/token")
async def livekit_token_generator(request: Request):
    data = await request.json()
    caller_phone = data.get("phone", "+1 (555) 234-5678")
    room_name = f"medilab-call-{caller_phone.replace('+', '').replace(' ', '')}"

    return {
        "room": room_name,
        "identity": caller_phone,
        "token": "simulated_livekit_token_ready",
        "ws_url": "wss://livekit.example.com",
        "status": "ready"
    }


@telephony_router.post("/chat-initiate")
async def rest_chat_initiate(request: Request):
    data = await request.json()
    caller_phone = data.get("caller_phone", "+1 (555) 234-5678")
    call_sid = f"REST-CALL-{int(time_timestamp())}"
    agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
    active_sessions[call_sid] = agent

    greeting = agent.get_initial_greeting()
    return {
        "type": "call_connected",
        "call_sid": call_sid,
        "caller_name": greeting["caller_name"],
        "caller_phone": caller_phone,
        "is_returning": greeting["is_returning_patient"],
        "speech": greeting["speech"]
    }


@telephony_router.post("/chat-turn")
async def rest_chat_turn(request: Request):
    data = await request.json()
    call_sid = data.get("call_sid", "")
    caller_phone = data.get("caller_phone", "+1 (555) 234-5678")
    user_text = data.get("text", "").strip()

    agent = active_sessions.get(call_sid)
    if not agent:
        agent = DiagnosticVoiceAgent(caller_phone=caller_phone, call_sid=call_sid)
        active_sessions[call_sid] = agent

    result = agent.process_turn(user_text)
    return {
        "type": "agent_response",
        "speech": result["speech"],
        "intent": result["intent"],
        "tool_executed": result.get("tool_executed"),
        "actions_taken": result.get("actions_taken", []),
        "citations": result.get("citations", []),
        "extra": result
    }


# ==============================================================================
# 4. INTERACTIVE WEBSOCKET SIMULATOR (WITH REAL-TIME BARGE-IN INTERRUPTION)
# ==============================================================================

async def handle_phone_call_websocket(websocket: WebSocket):
    """
    Interactive Browser Phone Call Simulator WebSocket.
    Features instant Barge-In detection: user speech immediately cancels agent speech!
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
                    "speech": greeting["speech"],
                    "barge_in_active": True
                }))

            elif msg_type == "user_interrupt":
                # Real-time Barge-In notification: user started speaking/typing while agent was talking
                reason = message.get("reason", "user_speech_detected")
                if agent:
                    agent.actions_taken.append(f"Agent Interrupted by Caller (Barge-In: {reason})")
                await websocket.send_text(json.dumps({
                    "type": "agent_interrupted",
                    "call_sid": call_sid,
                    "status": "stopped_speaking",
                    "reason": reason
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
                        "extra": result,
                        "barge_in_active": True
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
