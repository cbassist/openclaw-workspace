"""Donna voice adapter — async ElevenLabs STT (Scribe v2) and TTS utilities."""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path

from elevenlabs import AsyncElevenLabs

# --- Config (reads from env; .env is loaded by bot.py before this module is imported) ---
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "/opt/homebrew/bin/ffmpeg")
VOICE_STT_TIMEOUT = int(os.environ.get("VOICE_STT_TIMEOUT", "45"))
VOICE_TTS_TIMEOUT = int(os.environ.get("VOICE_TTS_TIMEOUT", "45"))
VOICE_FFMPEG_TIMEOUT = int(os.environ.get("VOICE_FFMPEG_TIMEOUT", "20"))
VOICE_CONCURRENCY = int(os.environ.get("VOICE_CONCURRENCY", "3"))
VOICE_TTS_CHAR_LIMIT = int(os.environ.get("VOICE_TTS_CHAR_LIMIT", "1000"))

log = logging.getLogger("dante.voice")

# --- Module-level client and concurrency guard ---
_client = AsyncElevenLabs(api_key=ELEVENLABS_API_KEY) if ELEVENLABS_API_KEY else None
_semaphore = asyncio.Semaphore(VOICE_CONCURRENCY)


class VoiceError(Exception):
    """Raised when a voice operation fails gracefully."""


async def transcribe_voice(audio_bytes: bytes) -> str:
    """Transcribe audio bytes (OGG/Opus from Telegram) via ElevenLabs Scribe v2.

    Returns the transcription text.
    Raises VoiceError on failure or timeout.
    """
    if not _client:
        raise VoiceError("ElevenLabs API key not configured")

    start = time.monotonic()
    async with _semaphore:
        try:
            result = await asyncio.wait_for(
                _client.speech_to_text.convert(
                    file=audio_bytes,
                    model_id="scribe_v2",
                ),
                timeout=VOICE_STT_TIMEOUT,
            )
            elapsed = time.monotonic() - start
            text = result.text.strip() if result.text else ""
            log.info("STT done in %.1fs, %d bytes -> %d chars", elapsed, len(audio_bytes), len(text))
            return text
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            log.error("STT timeout after %.1fs (%d bytes)", elapsed, len(audio_bytes))
            raise VoiceError(f"Transcription timed out after {VOICE_STT_TIMEOUT}s")
        except Exception as e:
            elapsed = time.monotonic() - start
            log.error("STT failed after %.1fs: %s", elapsed, e)
            raise VoiceError(f"Transcription failed: {e}")


async def text_to_voice(text: str, voice_id: str | None = None) -> bytes:
    """Convert text to OGG/Opus audio via ElevenLabs TTS + ffmpeg.

    Truncates text to VOICE_TTS_CHAR_LIMIT before sending to TTS.
    Returns OGG bytes suitable for Telegram voice notes.
    Raises VoiceError on failure or timeout.
    """
    if not _client:
        raise VoiceError("ElevenLabs API key not configured")

    voice_id = voice_id or ELEVENLABS_VOICE_ID
    # Truncate to limit TTS costs
    tts_text = text[:VOICE_TTS_CHAR_LIMIT]

    start = time.monotonic()
    async with _semaphore:
        mp3_tmp = None
        ogg_tmp = None
        try:
            # Step 1: ElevenLabs TTS -> MP3 (async generator, collect with timeout)
            response = _client.text_to_speech.convert(
                text=tts_text,
                voice_id=voice_id,
                model_id=os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2"),
                output_format="mp3_44100_128",
            )

            mp3_data = b""
            try:
                async with asyncio.timeout(VOICE_TTS_TIMEOUT):
                    async for chunk in response:
                        mp3_data += chunk
            except TimeoutError:
                raise VoiceError(f"TTS timed out after {VOICE_TTS_TIMEOUT}s")

            if not mp3_data:
                raise VoiceError("TTS returned empty audio")

            tts_elapsed = time.monotonic() - start
            log.info("TTS done in %.1fs, %d chars -> %d bytes MP3", tts_elapsed, len(tts_text), len(mp3_data))

            # Step 2: ffmpeg MP3 -> OGG/Opus
            mp3_tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            mp3_tmp.write(mp3_data)
            mp3_tmp.close()

            ogg_tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
            ogg_tmp.close()

            ffmpeg_start = time.monotonic()
            proc = await asyncio.create_subprocess_exec(
                FFMPEG_BIN, "-y", "-i", mp3_tmp.name,
                "-c:a", "libopus", "-b:a", "64k",
                ogg_tmp.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=VOICE_FFMPEG_TIMEOUT)
            except asyncio.TimeoutError:
                proc.kill()
                raise VoiceError(f"ffmpeg timed out after {VOICE_FFMPEG_TIMEOUT}s")

            if proc.returncode != 0:
                raise VoiceError(f"ffmpeg exited with code {proc.returncode}")

            ogg_bytes = Path(ogg_tmp.name).read_bytes()
            ffmpeg_elapsed = time.monotonic() - ffmpeg_start
            total_elapsed = time.monotonic() - start
            log.info(
                "ffmpeg done in %.1fs, %d bytes MP3 -> %d bytes OGG (total %.1fs)",
                ffmpeg_elapsed, len(mp3_data), len(ogg_bytes), total_elapsed,
            )
            return ogg_bytes

        except VoiceError:
            raise
        except Exception as e:
            elapsed = time.monotonic() - start
            log.error("TTS pipeline failed after %.1fs: %s", elapsed, e)
            raise VoiceError(f"Voice synthesis failed: {e}")
        finally:
            # Clean up temp files
            for tmp in (mp3_tmp, ogg_tmp):
                if tmp:
                    try:
                        Path(tmp.name).unlink(missing_ok=True)
                    except OSError:
                        pass
