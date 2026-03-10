import pyaudio
import asyncio

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
        print("🎙️  Microphone started. Start speaking...")
        try:
            while True:
                # Read audio data block
                data = stream.read(CHUNK, exception_on_overflow=False)
                yield data
                # Yield control to the event loop
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            print("🎙️  Microphone stream cancelled.")
        except Exception as e:
            print(f"🎙️  Microphone error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
            print("🎙️  Microphone stopped.")

    return mic_generator()
