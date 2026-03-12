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
                endpointing=300,   
                utterance_end_ms="1200",
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
                        # Append the chunk to our ongoing complete utterance buffer
                        if self.last_final_transcript:
                             self.last_final_transcript += f" {sentence}"
                        else:
                             self.last_final_transcript = sentence

                        print(f"Transcript : {sentence}")
                    
                # If speech_final is true, Deepgram detected a pause. 
                # This is our primary trigger to complete the utterance!
                if speech_final and self.last_final_transcript:
                    completed_utterance = self.last_final_transcript
                    print(f"Final Transcript : {completed_utterance}")

                    if self.loop and not self.loop.is_closed():
                        async def save_to_db(sid, txt):
                            await asyncio.to_thread(self.session_tools.update_transcript, sid, txt, "en")
                        
                        asyncio.run_coroutine_threadsafe(
                            save_to_db(self.session_id, completed_utterance), 
                            self.loop
                        )

                    self.last_final_transcript = ""

        except Exception as e:
            pass

    def handle_utterance_end(self, connection, utterance_end, **kwargs):
        if not self.session_id:
            return

        # UtteranceEnd acts as a fallback for noisy environments where
        # endpointing/speech_final might fail to detect a pause.
        if self.last_final_transcript:
            completed_utterance = self.last_final_transcript
            print(f"Final Transcript (Fallback) : {completed_utterance}")

            if self.loop and not self.loop.is_closed():
                async def save_to_db(sid, txt):
                    await asyncio.to_thread(self.session_tools.update_transcript, sid, txt, "en")
                
                asyncio.run_coroutine_threadsafe(
                    save_to_db(self.session_id, completed_utterance), 
                    self.loop
                )

            self.last_final_transcript = ""

    def handle_error(self, connection, error, **kwargs):
        pass