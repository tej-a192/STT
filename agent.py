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
        self.loop = None

    async def run(self, session_id: str, audio_generator, language_code: str):
        self.session_id = session_id
        self.loop = asyncio.get_running_loop()
        dg_connection = None
        
        try:
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
                return
            
            print("Start Speaking")

            async for data in audio_generator:
                dg_connection.send(data)

        except Exception as e:
            pass
        finally:
            if dg_connection:
                dg_connection.finish()

    def handle_transcript(self, connection, result, **kwargs):
        if not result or not self.session_id:
            return
            
        sentence = ""

        try:
            if hasattr(result, "channel") and result.channel.alternatives:
                alt = result.channel.alternatives[0]
                sentence = alt.transcript or ""

                is_final = getattr(result, 'is_final', False)
                speech_final = getattr(result, 'speech_final', False)
                
                if sentence.strip():
                    if not is_final and not speech_final:
                        pass
                        
                    if is_final:
                        self.last_final_transcript = sentence
                        print(f"Transcript : {sentence}")
                    
                    if is_final or speech_final:
                        if self.loop and not self.loop.is_closed():
                            async def save_to_db(sid, txt):
                                await asyncio.to_thread(self.session_tools.update_transcript, sid, txt, "en")
                            
                            asyncio.run_coroutine_threadsafe(
                                save_to_db(self.session_id, sentence), 
                                self.loop
                            )

        except Exception as e:
            pass

    def handle_utterance_end(self, connection, utterance_end, **kwargs):
        if not self.session_id:
            return

        if self.last_final_transcript:
            print(f"Final Transcript : {self.last_final_transcript}")
            self.last_final_transcript = ""

    def handle_error(self, connection, error, **kwargs):
        pass