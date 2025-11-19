import requests
from typing import List, Dict, Optional
from config import (
    FISH_AUDIO_API_KEY,
    FISH_AUDIO_BASE_URL,
    DEFAULT_MODELS,
    USE_CONFIG_MODELS_ONLY,
    FISH_AUDIO_BACKEND,
    FISH_AUDIO_MP3_BITRATE,
)
# Prefer direct HTTP for Opus; fallback to legacy SDK for mp3/wav/pcm
from fish_audio_sdk import Session, TTSRequest


class FishAudioClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or FISH_AUDIO_API_KEY
        self.base_url = (base_url or FISH_AUDIO_BASE_URL).rstrip("/")
        # Legacy session as fallback
        self.session = Session(self.api_key)

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def list_models(self) -> List[Dict]:
        if USE_CONFIG_MODELS_ONLY:
            return DEFAULT_MODELS
        try:
            url = f"{self.base_url}/voices"
            r = requests.get(url, headers=self._headers(), timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "voices" in data:
                    return data["voices"]
        except Exception:
            pass
        return DEFAULT_MODELS

    def synthesize_text(self, text: str, voice_id: str, language: str = "en", format_: str = "mp3", mp3_bitrate: int = None) -> bytes:
        """Generate speech audio.

        - When format_ == 'opus', use REST API directly to obtain OGG/Opus bytes.
        - Otherwise, use legacy Session + TTSRequest with supported formats ('mp3', 'wav', 'pcm').
        """
        # Direct HTTP path for Opus
        if format_ == "opus":
            try:
                url = f"{self.base_url}/v1/tts"
                payload = {
                    "text": text,
                    "reference_id": voice_id,
                    "format": "opus",
                    "model": FISH_AUDIO_BACKEND,
                    "normalize": True,
                    "latency": "normal",
                    "opus_bitrate": 32,
                }
                headers = self._headers()
                headers["Content-Type"] = "application/json"
                headers["Accept"] = "application/octet-stream"
                r = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
                if r.status_code != 200:
                    try:
                        err = r.json()
                    except Exception:
                        err = r.text
                    raise RuntimeError(f"HTTP {r.status_code}: {err}")
                audio_bytes = bytearray()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        audio_bytes.extend(chunk)
                if not audio_bytes:
                    raise RuntimeError("TTS failed: empty audio")
                return bytes(audio_bytes)
            except Exception as e:
                raise RuntimeError(f"TTS failed (HTTP/Opus): {e}")

        # Fallback: legacy SDK with supported formats
        try:
            kwargs = {
                "text": text,
                "reference_id": voice_id,
                "format": format_,
            }
            # Include mp3 bitrate if requested and format is mp3
            try:
                bitrate = mp3_bitrate if mp3_bitrate is not None else (FISH_AUDIO_MP3_BITRATE if format_ == "mp3" else None)
            except Exception:
                bitrate = None
            if format_ == "mp3" and isinstance(bitrate, int) and bitrate in (64, 128, 192):
                kwargs["mp3_bitrate"] = bitrate
            req = TTSRequest(**kwargs)
            audio_bytes = bytearray()
            for chunk in self.session.tts(req, backend=FISH_AUDIO_BACKEND):
                if isinstance(chunk, (bytes, bytearray)):
                    audio_bytes.extend(chunk)
                else:
                    try:
                        audio_bytes.extend(bytes(chunk))
                    except Exception:
                        pass
            if not audio_bytes:
                raise RuntimeError("TTS failed: empty audio")
            return bytes(audio_bytes)
        except Exception as e:
            raise RuntimeError(f"TTS failed: {e}")