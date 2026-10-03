import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.voice_agent import DiagnosticVoiceAgent

def test_natural_executive_dialogue():
    print("--- Testing Natural Customer Care Executive Dialogue ---")
    agent = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-NATURAL-001")

    # Turn 1: User asks for CBC
    t1 = agent.process_turn("I need a CBC tomorrow")
    print(f"\nCaller: 'I need a CBC tomorrow'")
    print(f"Vinod:  '{t1['speech']}'")
    assert "Sure. CBC, right?" in t1["speech"], "Must confirm test naturally"
    assert "Are you looking for home collection or would you prefer visiting the lab?" in t1["speech"], "Must contextually ask preference"
    assert "10 to 12 AM for ₹450" in t1["speech"] and "12 to 2 PM for ₹500" in t1["speech"], "Must present slots and prices"

    # Turn 2: Caller chooses preference
    t2 = agent.process_turn("Home collection")
    print(f"\nCaller: 'Home collection'")
    print(f"Vinod:  '{t2['speech']}'")
    assert "Got it, home collection." in t2["speech"]
    assert "Which time works for you?" in t2["speech"]

    # Turn 3: Caller picks slot
    t3 = agent.process_turn("10 to 12 AM please")
    print(f"\nCaller: '10 to 12 AM please'")
    print(f"Vinod:  '{t3['speech']}'")
    assert "Done! Booked your CBC for tomorrow, 10:00 AM - 12:00 PM at ₹450." in t3["speech"]
    assert "WhatsApp" in t3["speech"] and "Gmail" in t3["speech"]

    # Test Turn 4: Test query without 'tomorrow'
    agent2 = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-NATURAL-002")
    t4 = agent2.process_turn("Can I book a CBC test?")
    print(f"\nCaller: 'Can I book a CBC test?'")
    print(f"Vinod:  '{t4['speech']}'")
    assert "Sure. CBC, right?" in t4["speech"]
    assert "Are you looking for home collection or would you prefer visiting the lab?" in t4["speech"]

    print("\n[SUCCESS] Natural Executive Dialogue matches all requirements with zero chatbot fluff!")


def test_example_real_conversation_funnel():
    print("\n--- Testing Exact Prompt Example: Real Conversation Funnel ---")
    agent = DiagnosticVoiceAgent(caller_phone="+91 91234 56789", call_sid="TEST-FUNNEL-001")

    # Opening
    greeting = agent.get_initial_greeting()
    print(f"Agent: '{greeting['speech']}'")
    assert "Hi, I'm your Lab Assistant Vinod. How can I help?" in greeting["speech"] or "Hi! I'm your Lab Assistant" in greeting["speech"]
    assert "How can I help?" in greeting["speech"]


    # Turn 1: User: "I want a blood test."
    print("\nUser:  'I want a blood test.'")
    t1 = agent.process_turn("I want a blood test.")
    print(f"Agent: '{t1['speech']}'")
    assert t1["speech"] == "Sure. Which test are you looking for?"
    assert t1["intent"] == "ask_test_name"

    # Turn 2: User: "CBC."
    print("\nUser:  'CBC.'")
    t2 = agent.process_turn("CBC.")
    print(f"Agent: '{t2['speech']}'")
    assert t2["speech"] == "Sure. Are you planning to visit the lab or would you like someone to collect the sample from home?"
    assert t2["intent"] == "ask_sampling_mode"

    # Turn 3: User: "Home."
    print("\nUser:  'Home.'")
    t3 = agent.process_turn("Home.")
    print(f"Agent: '{t3['speech']}'")
    assert t3["speech"] == "Okay. What day would you like?"
    assert t3["intent"] == "ask_appointment_date"

    # Turn 4: User: "Tomorrow."
    print("\nUser:  'Tomorrow.'")
    t4 = agent.process_turn("Tomorrow.")
    print(f"Agent: '{t4['speech']}'")
    assert t4["speech"] == "Morning or afternoon?"
    assert t4["intent"] == "ask_time_preference"

    # Turn 5: User: "Morning." -> Now the agent calls check_availability()
    print("\nUser:  'Morning.'")
    t5 = agent.process_turn("Morning.")
    print(f"Agent: '{t5['speech']}'")
    assert t5["tool_executed"] == "check_availability"
    assert "10 to 12 AM for ₹450" in t5["speech"]
    assert "Does that work for you?" in t5["speech"]

    # Turn 6: User: "Yes" (or "10 to 12 AM please") -> Agent calls book_appointment()
    print("\nUser:  'Yes'")
    t6 = agent.process_turn("Yes")
    print(f"Agent: '{t6['speech']}'")
    assert t6["tool_executed"] == "book_appointment"
    assert "Done! Booked your CBC for tomorrow, 10:00 AM - 12:00 PM at ₹450." in t6["speech"]
    assert "WhatsApp" in t6["speech"] and "Gmail" in t6["speech"]

    print("\n[SUCCESS] Exact Real Conversation Funnel passed with 100% precision!")


if __name__ == "__main__":
    test_natural_executive_dialogue()
    test_example_real_conversation_funnel()

