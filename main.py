import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from agent import STTAgent
from audio.mic_stream import get_mic_stream
from tools.session_tools import SessionTools
from audio.buffer import buffer_audio
from tools.lang_detect import detect_language

# Configure Global Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("⚠️ WARNING: DATABASE_URL is not set in environment. App will crash.")

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
    logger.info("🚀 Starting Agent 2 (STT) testing flow...")
    
    session_tools = SessionTools(DATABASE_URL)
    # Run sync DB table creation in thread to avoid event loop blocking on startup
    await asyncio.to_thread(session_tools.create_dummy_session, DUMMY_SESSION_ID, DUMMY_SESSION_STATE)

    audio_stream = get_mic_stream()
    stt_agent = STTAgent(db_url=DATABASE_URL)
    
    logger.info("Press Ctrl+C to stop listening.")
    try:
        while True:
            # Step A: Buffer 2 seconds of audio for LangID
            audio_bytes, _ = await buffer_audio(audio_stream, duration_seconds=2.0)
            
            # Step B: Detect language (Properly awaited)
            detected_lang, confidence, buffer_transcript = await detect_language(audio_bytes)
            logger.info(f"✅ Language Detected: {detected_lang}")
            
            # Prevent infinite failure loop if Deepgram cannot detect language
            if detected_lang == "unknown":
                logger.warning("Language undetected. Defaulting to 'en' to prevent websocket crash.")
                detected_lang = "en"
            
            # Step C: Immediately save the transcript asynchronously
            if buffer_transcript and buffer_transcript.strip():
                logger.info(f"⚡ [Low-Latency Buffer Transcript]: {buffer_transcript}")
                await asyncio.to_thread(
                    session_tools.update_transcript,
                    DUMMY_SESSION_ID,
                    buffer_transcript,
                    detected_lang
                )
            
            # Step D: Stream exclusively new audio using Deepgram
            logger.info(f"🎧 Starting WebSockets Stream in {detected_lang}...")
            await stt_agent.run(DUMMY_SESSION_ID, audio_stream, language_code=detected_lang)
            
            logger.info("🔄 Stream broken (likely due to confidence drop). Restarting to re-detect language...")
            await asyncio.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("\nStopping Agent...")
    except Exception as e:
        logger.error(f"Fatal error in main application loop: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass