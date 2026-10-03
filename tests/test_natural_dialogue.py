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

if __name__ == "__main__":
    test_natural_executive_dialogue()
