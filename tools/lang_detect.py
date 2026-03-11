from typing import Tuple
import os
import logging
import asyncio
import io
import wave
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

logger = logging.getLogger(__name__)

# Cache the client globally so we don't recreate connection pools on every call
_dg_client = None

def get_dg_client():
    global _dg_client
    if _dg_client is None:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if api_key:
            _dg_client = DeepgramClient(api_key)
    return _dg_client

def wrap_pcm_as_wav(pcm_bytes: bytes, sample_rate=16000, channels=1, sampwidth=2) -> bytes:
    """
    Wraps raw PCM audio bytes in a standard WAV container.
    This gives Deepgram the metadata it needs to process the audio.
    When switching to AWS Connect, change sample_rate to 8000.
    """
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

async def detect_language(audio_bytes: bytes) -> Tuple[str, float, str]:
    """
    Returns (language_code, confidence_score, transcript_text)
    - language_code: detected language or "unknown"
    - confidence_score: 0.0 to 1.0 (0.0 if detection failed)
    - transcript_text: The transcribed text of the buffer.
    """
    client = get_dg_client()
    if not client:
        logger.warning("⚠️ Warning: DEEPGRAM_API_KEY not found.")
        return "unknown", 0.0, ""

    try:
        # Wrap the raw PCM mic audio into a WAV format
        wav_bytes = wrap_pcm_as_wav(audio_bytes, sample_rate=16000)

        payload: FileSource = {
            "buffer": wav_bytes,
        }

        options = PrerecordedOptions(
            model="nova-3",
            detect_language=True,
        )

        # Use asyncio.to_thread to run the synchronous network request without blocking the async event loop!
        response = await asyncio.to_thread(
            client.listen.prerecorded.v("1").transcribe_file,
            payload,
            options,
            timeout=300
        )

        response_dict = response.to_dict()

        if "results" in response_dict:
            channels = response_dict["results"].get("channels", [])
            if channels:
                detected_lang = channels[0].get("detected_language")
                language_confidence = channels[0].get("language_confidence", 0.0)
                
                transcript = ""
                alternatives = channels[0].get("alternatives", [])
                if alternatives:
                     transcript = alternatives[0].get("transcript", "")

                if detected_lang:
                    logger.info(f"🔍 LangID: {detected_lang} (confidence: {language_confidence:.2f}) | Transcript: '{transcript}'")
                    return detected_lang, language_confidence, transcript

        logger.info("🔍 Language detection failed - no confident match.")
        return "unknown", 0.0, ""

    except Exception as e:
        logger.error(f"❌ Language Detection API Failed: {e}", exc_info=True)
        return "unknown", 0.0, ""

# Usage example:
if __name__ == "__main__":
    async def test():
        with open("your_audio_file.wav", "rb") as f:
            audio_buffer = f.read()

        detected_lang, confidence, transcript = await detect_language(audio_buffer)
        if confidence > 0.5:
            logger.info(f"✅ Using detected language: {detected_lang} - T: {transcript}")
        else:
            logger.warning(f"⚠️ Low confidence ({confidence:.2f}), using multilingual mode")
            detected_lang = "multi"
            
    asyncio.run(test())