import os
import asyncio
from dotenv import load_dotenv
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)
from tools.session_tools import SessionTools

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

class STTAgent:
    def __init__(self, db_url: str):
        if not DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment.")
            
        self.dg_client = DeepgramClient(DEEPGRAM_API_KEY)
        self.session_tools = SessionTools(db_url)
        self.last_final_transcript = ""
        self.session_id = None

    async def run(self, session_id: str, audio_generator):
        self.session_id = session_id
        
        try:
            print("STT Agent: Connecting to Deepgram...")
            
            dg_connection = self.dg_client.listen.live.v("1")
            
            dg_connection.on(LiveTranscriptionEvents.Transcript, self.handle_transcript)
            dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, self.handle_utterance_end)
            dg_connection.on(LiveTranscriptionEvents.Error, self.handle_error)
            
            options = LiveOptions(
                model="nova-3",
                language="multi",
                smart_format=True,
                endpointing=500,
                utterance_end_ms="1000",
                interim_results=True,
                encoding="linear16",
                sample_rate=16000,
                channels=1
            )
            
            if dg_connection.start(options) is False:
                print("STT Agent: Failed to start connection")
                return
            
            print("STT Agent: Connection established with speech detection features")
            print("STT Agent: Listening for audio...")

            async for data in audio_generator:
                dg_connection.send(data)

            dg_connection.finish()

        except Exception as e:
            print(f"STT Agent Error: {e}")
            import traceback
            traceback.print_exc()

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
                
                if detected_lang == "unknown" and hasattr(alt, "languages") and alt.languages:
                    detected_lang = alt.languages[0]

                is_final = getattr(result, 'is_final', False)
                speech_final = getattr(result, 'speech_final', False)
                
                # Minimal logging - only final results to database
                if sentence.strip():
                    if is_final:
                        self.last_final_transcript = sentence
                        print(f"STT Final: [{detected_lang}] {sentence}")
                    
                    if is_final or speech_final:
                        self.session_tools.update_transcript(
                            session_id=self.session_id,
                            transcript=sentence,
                            language=detected_lang,
                        )
                        # Database save confirmation is handled by session_tools

        except Exception as e:
            print(f"STT Transcript Processing Error: {e}")

    def handle_utterance_end(self, connection, utterance_end, **kwargs):
        if not self.session_id:
            return
            
        last_word_time = getattr(utterance_end, 'last_word_end', 'N/A')
        print(f"STT UtteranceEnd: Speech paused, last word at {last_word_time}s")

        if self.last_final_transcript:
            print(f"STT Complete Utterance: {self.last_final_transcript}")
            self.last_final_transcript = ""

    def handle_error(self, connection, error, **kwargs):
        print(f"STT Connection Error: {error}")
