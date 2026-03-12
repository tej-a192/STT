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
    "language": "en",
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
    "workflow_version": "2.0",
    "language_detected_by": "default_english",
    "stt_engine": "deepgram-nova-3-streaming"
  }
}

async def main():
    print("STT Service is started")
    
    session_tools = SessionTools(DATABASE_URL)
    await asyncio.to_thread(session_tools.create_dummy_session, DUMMY_SESSION_ID, DUMMY_SESSION_STATE)

    audio_stream = get_mic_stream()
    stt_agent = STTAgent(db_url=DATABASE_URL)
    
    try:
        # Step: Stream English audio directly
        await stt_agent.run(DUMMY_SESSION_ID, audio_stream, language_code="en")
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass