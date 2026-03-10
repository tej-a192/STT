import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from agent import STTAgent
from audio.mic_stream import get_mic_stream
from tools.session_tools import SessionTools

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️ WARNING: DATABASE_URL is not set in environment. App will crash.")

# Initial dummy state for local testing
DUMMY_SESSION_ID = "test_local_mic_001"
DUMMY_SESSION_STATE = {
  "session_id": DUMMY_SESSION_ID,
  "user_id": "debug_user",
  "created_at": datetime.utcnow().isoformat() + "Z",
  "updated_at": datetime.utcnow().isoformat() + "Z",
  "state": {
    "caller_number": "local_mic",
    "caller_name": "Dev User",
    "language": "unknown",
    "call_start_time": datetime.utcnow().isoformat() + "Z",
    "conversation": [],
    "entities": {},
    "intent_history": [],
    "lead_scoring": {},
    "sentiment": {},
    "call_summary": "",
    "next_actions": []
  },
  "metadata": {
    "workflow_version": "1.0",
    "language_detected_by": "deepgram",
    "stt_engine": "deepgram-nova-2-streaming"
  }
}

async def main():
    print("🚀 Starting Agent 2 (STT) testing flow...")
    
    # 1. Initialize logic and Database Session
    session_tools = SessionTools(DATABASE_URL)
    session_tools.create_dummy_session(DUMMY_SESSION_ID, DUMMY_SESSION_STATE)

    # 2. Get the async audio recording generator
    audio_stream = get_mic_stream()

    # 3. Start the Deepgram Agent
    stt_agent = STTAgent(db_url=DATABASE_URL)
    
    print("Press Ctrl+C to stop listening.")
    try:
        await stt_agent.run(DUMMY_SESSION_ID, audio_stream)
    except KeyboardInterrupt:
        print("\nStopping Agent...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
