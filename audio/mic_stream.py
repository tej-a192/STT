import pyaudio
import asyncio
import logging

logger = logging.getLogger(__name__)

# Audio recording parameters
RATE = 16000
CHUNK = 4096
CHANNELS = 1

def get_mic_stream():
    """
    Returns an async generator yielding audio chunks from the microphone.
    This can be swapped later with an AWS Connect audio stream generator.
    """
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    async def mic_generator():
        logger.info("🎙️ Microphone started. Start speaking...")
        try:
            while True:
                # Run blocking PyAudio read in a separate thread so it doesn't freeze the async event loop
                data = await asyncio.to_thread(stream.read, CHUNK, exception_on_overflow=False)
                yield data
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            logger.info("🎙️ Microphone stream cancelled.")
        except Exception as e:
            logger.error(f"🎙️ Microphone error: {e}", exc_info=True)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
            logger.info("🎙️ Microphone stopped.")

    return mic_generator()