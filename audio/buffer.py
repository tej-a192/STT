import asyncio
import audioop
import logging

logger = logging.getLogger(__name__)

async def buffer_audio(stream_generator, duration_seconds=2.0, rate=16000, chunk_size=4096):
    """
    Waits for the user to start speaking, then pulls a specific duration 
    of audio from the async stream generator.
    """
    # Volume threshold (0 to 32768). Adjust this if it's too sensitive or not sensitive enough!
    SILENCE_THRESHOLD = 300 
    
    required_chunks = max(1, int((rate / chunk_size) * duration_seconds))
    buffered_chunks =[]
    
    logger.info("⏳ Waiting for you to start speaking before detecting language...")
    
    # 1. Wait for actual speech (Skip silent audio chunks)
    while True:
        try:
            chunk = await stream_generator.__anext__()
            # Measure the volume (RMS) of the 16-bit audio chunk
            rms = audioop.rms(chunk, 2)
            
            if rms > SILENCE_THRESHOLD:
                buffered_chunks.append(chunk)
                logger.info(f"🗣️ Speech detected! (Volume: {rms}). Buffering 2 seconds for Language ID...")
                break
        except StopAsyncIteration:
            return b"",[]

    # 2. Record the required duration now that the user is talking
    for _ in range(required_chunks - 1):
        try:
            chunk = await stream_generator.__anext__()
            buffered_chunks.append(chunk)
        except StopAsyncIteration:
            break
            
    return b"".join(buffered_chunks), buffered_chunks