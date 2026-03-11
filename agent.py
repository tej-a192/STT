import os
import asyncio
import logging
from dotenv import load_dotenv
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)
from tools.session_tools import SessionTools

load_dotenv()
logger = logging.getLogger(__name__)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

class STTAgent:
    def __init__(self, db_url: str):
        if not DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment.")
            
        self.dg_client = DeepgramClient(DEEPGRAM_API_KEY)
        self.session_tools = SessionTools(db_url)
        self.last_final_transcript = ""
        self.session_id = None
        self.confidence_drops = 0
        
        # Proper thread-safe mechanics
        self.language_switch_event = asyncio.Event()
        self.loop = None

    async def run(self, session_id: str, audio_generator, language_code: str):
        self.session_id = session_id
        self.confidence_drops = 0
        self.language_switch_event.clear()
        self.loop = asyncio.get_running_loop()
        dg_connection = None
        
        try:
            logger.info("STT Agent: Connecting to Deepgram...")
            dg_connection = self.dg_client.listen.live.v("1")
            
            dg_connection.on(LiveTranscriptionEvents.Transcript, self.handle_transcript)
            dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, self.handle_utterance_end)
            dg_connection.on(LiveTranscriptionEvents.Error, self.handle_error)
            
            options = LiveOptions(
                model="nova-3", 
                language=language_code,
                smart_format=True,
                endpointing=500,
                utterance_end_ms="1000",
                interim_results=True,
                encoding="linear16",
                sample_rate=16000,
                channels=1
            )
            
            if not dg_connection.start(options):
                logger.error("STT Agent: Failed to start connection")
                return
            
            logger.info("STT Agent: Connection established with speech detection features")
            logger.info(f"STT Agent: Listening for audio in language: {language_code}...")

            # Background task to break the generator safely on language switch
            async def monitor_switch():
                await self.language_switch_event.wait()
                logger.warning("Language Switch Triggered - Breaking audio stream.")

            switch_task = asyncio.create_task(monitor_switch())

            async for data in audio_generator:
                if self.language_switch_event.is_set():
                    break
                dg_connection.send(data)

            switch_task.cancel()

        except Exception as e:
            logger.error(f"STT Agent Error: {e}", exc_info=True)
        finally:
            # Guarantee graceful shutdown
            if dg_connection:
                dg_connection.finish()
                logger.info("STT Agent: Connection closed.")

    def handle_transcript(self, connection, result, **kwargs):
        if not result or not self.session_id:
            return
            
        sentence = ""
        detected_lang = "unknown"

        try:
            if hasattr(result, "channel") and result.channel.alternatives:
                alt = result.channel.alternatives[0]
                sentence = alt.transcript or ""

                if hasattr(alt, "words") and alt.words:
                    languages = [w.language for w in alt.words if hasattr(w, "language")]
                    if languages:
                        detected_lang = max(set(languages), key=languages.count)
                        
                    word_confidences = [w.confidence for w in alt.words if hasattr(w, "confidence")]
                    if word_confidences:
                        avg_confidence = sum(word_confidences) / len(word_confidences)
                        if avg_confidence < 0.45 and len(word_confidences) > 1:
                            self.confidence_drops += 1
                        elif avg_confidence > 0.6:
                            self.confidence_drops = 0
                            
                    if self.confidence_drops >= 3:
                        logger.warning(f"⚠️ STT Agent: Low confidence ({avg_confidence:.2f}) consecutively! Triggering Language Switch...")
                        # Thread-safe trigger to the main asyncio loop
                        if self.loop and not self.loop.is_closed():
                            self.loop.call_soon_threadsafe(self.language_switch_event.set)

                if detected_lang == "unknown" and hasattr(alt, "languages") and alt.languages:
                    detected_lang = alt.languages[0]

                is_final = getattr(result, 'is_final', False)
                speech_final = getattr(result, 'speech_final', False)
                
                if sentence.strip():
                    if is_final:
                        self.last_final_transcript = sentence
                        logger.info(f"STT Final: [{detected_lang}] {sentence}")
                    
                    if is_final or speech_final:
                        # Offload DB write back to Asyncio Loop so we don't block the WebSocket Thread
                        if self.loop and not self.loop.is_closed():
                            async def save_to_db(sid, txt, lang):
                                await asyncio.to_thread(self.session_tools.update_transcript, sid, txt, lang)
                            
                            asyncio.run_coroutine_threadsafe(
                                save_to_db(self.session_id, sentence, detected_lang), 
                                self.loop
                            )

        except Exception as e:
            logger.error(f"STT Transcript Processing Error: {e}", exc_info=True)

    def handle_utterance_end(self, connection, utterance_end, **kwargs):
        if not self.session_id:
            return
        last_word_time = getattr(utterance_end, 'last_word_end', 'N/A')
        logger.debug(f"STT UtteranceEnd: Speech paused, last word at {last_word_time}s")

        if self.last_final_transcript:
            logger.info(f"STT Complete Utterance: {self.last_final_transcript}")
            self.last_final_transcript = ""

    def handle_error(self, connection, error, **kwargs):
        logger.error(f"STT Connection Error: {error}")