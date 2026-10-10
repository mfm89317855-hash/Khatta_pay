"""Speech-to-text transcription module using faster-whisper.

Configured with Urdu language hint ('ur') and automatic fallback.
Lazy loads the model to conserve memory and startup time.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union

from khatatalk.config import DEFAULT_WHISPER_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)

# PyAV 14+ compatibility patch for faster-whisper
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except ImportError:
    pass

# Global model cache to avoid reloading weights repeatedly
_CACHED_WHISPER_MODEL = None
_CACHED_MODEL_SIZE = None
_OPENAI_EXHAUSTED = False


def transcribe_with_whisper_api(audio_file_path: Union[str, Path], api_key: str) -> Optional[str]:
    """Transcribes audio using OpenAI Whisper API ('whisper-1')."""
    global _OPENAI_EXHAUSTED
    if _OPENAI_EXHAUSTED:
        return None

    path_str = str(audio_file_path)
    try:
        import openai
        client = openai.OpenAI(api_key=api_key, max_retries=0)
        with open(path_str, "rb") as audio_file:
            transcript_obj = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                prompt="Pakistani shopkeeper transaction in Urdu, Roman Urdu, or English (e.g. 'Ahmed ko 2 kilo cheeni udhaar di 400 rupay')."
            )
            text = getattr(transcript_obj, "text", "") or ""
            if text.strip():
                logger.info("Successfully transcribed audio via Whisper API ('whisper-1').")
                return text.strip()
    except Exception as e:
        err_str = str(e)
        if "insufficient_quota" in err_str or "429" in err_str or "credit_balance_exhausted" in err_str:
            _OPENAI_EXHAUSTED = True
            logger.warning("OpenAI API quota exhausted. Switched instantly to offline local faster-whisper for all subsequent voice requests.")
        else:
            logger.warning("Whisper API transcription failed (%s). Falling back to local faster-whisper.", e)
    return None


def get_whisper_model(model_size: Optional[str] = None):
    """Lazily loads and caches the faster-whisper model."""
    global _CACHED_WHISPER_MODEL, _CACHED_MODEL_SIZE
    size = model_size or DEFAULT_WHISPER_MODEL

    if _CACHED_WHISPER_MODEL is not None and _CACHED_MODEL_SIZE == size:
        return _CACHED_WHISPER_MODEL

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper is not installed. Audio transcription will not be available.")
        return None

    try:
        # Shop environments typically run on CPU with int8 quantization
        device = os.getenv("KHATATALK_WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("KHATATALK_WHISPER_COMPUTE", "int8")
        logger.info("Loading faster-whisper model '%s' on %s (%s)...", size, device, compute_type)
        _CACHED_WHISPER_MODEL = WhisperModel(size, device=device, compute_type=compute_type)
        _CACHED_MODEL_SIZE = size
        return _CACHED_WHISPER_MODEL
    except Exception as e:
        logger.error("Failed to load faster-whisper model '%s': %s", size, e)
        return None


def transcribe_audio(
    audio_file_path: Union[str, Path],
    model_size: Optional[str] = None,
    language_hint: str = "ur",
    beam_size: int = 5,
    api_key: Optional[str] = None,
) -> str:
    """Transcribes an audio file using Whisper API (if API key available) or local faster-whisper.

    Strategy:
    1. If Whisper API key is set, transcribes via OpenAI Whisper API ('whisper-1').
    2. If API key is absent or fails, falls back to local faster-whisper with Urdu hint & auto-detect.
    """
    path_str = str(audio_file_path)
    if not os.path.exists(path_str):
        raise FileNotFoundError(f"Audio file not found: {path_str}")

    key = api_key or OPENAI_API_KEY
    if key:
        api_text = transcribe_with_whisper_api(path_str, key)
        if api_text:
            return api_text

    model = get_whisper_model(model_size)
    if model is None:
        raise RuntimeError(
            "faster-whisper is not loaded. Please verify faster-whisper installation or use text input fallback."
        )

    try:
        # Step 1: Attempt with Urdu hint
        segments, info = model.transcribe(
            path_str,
            language=language_hint,
            beam_size=beam_size,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()

        # Step 2: Fallback to auto language if transcription is empty
        if not text:
            logger.info("Transcription with 'ur' hint was empty; attempting auto-detection...")
            segments, info = model.transcribe(
                path_str,
                language=None,
                beam_size=beam_size,
                vad_filter=True,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()

        return text
    except Exception as err:
        logger.error("Error during whisper transcription: %s", err)
        raise RuntimeError(f"Transcription failed: {err}") from err
