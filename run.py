import os
import sys
import subprocess

def main():
    print("=" * 70)
    print("APEX MEDILAB - MULTIMODAL AI DIAGNOSTIC LAB & VOICE AGENT")
    print("=" * 70)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Check and run database initialization & seed
    print("[1/3] Initializing Relational Database Schema & Policy RAG...")
    try:
        from backend.seed_data import init_and_seed_db
        from backend.rag_engine import rag_engine
        init_and_seed_db()
        print(f"       Policy RAG Index active: {len(rag_engine.chunks)} policy clauses indexed.")
    except Exception as e:
        print(f"       Initialization notice: {e}")

    # Start FastAPI Application Server
    print("[2/3] Starting Telephony & Multimodal AI FastAPI Server...")
    print("       Server URL: http://localhost:8000")
    print("       Phone Call Studio: http://localhost:8000/#voice-studio")
    print("       Multimodal Prescription Scanner: http://localhost:8000/#prescription-scanner")
    print("       Policy RAG Explorer: http://localhost:8000/#policy-rag")
    print("=" * 70)

    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
