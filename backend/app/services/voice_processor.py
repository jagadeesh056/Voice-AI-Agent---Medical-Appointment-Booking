import base64
import io
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

_USE_OPENAI_VOICE = os.getenv("USE_OPENAI_VOICE", "false").lower() == "true"
_OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")


class VoiceProcessor:
    """
    Handles voice processing: STT, TTS, audio encoding/decoding.

    STT / TTS strategy:
      • If USE_OPENAI_VOICE=true AND OPENAI_API_KEY is set  → real Whisper + TTS
      • Otherwise                                            → mock STT passes through
        whatever text is available; TTS is skipped.
    """

    def __init__(self):
        self.sample_rate = int(os.getenv("SAMPLE_RATE", 16000))
        self._voice_enabled = _USE_OPENAI_VOICE and bool(_OPENAI_API_KEY)

        if self._voice_enabled:
            from openai import OpenAI as _OpenAI
            self._oai = _OpenAI(api_key=_OPENAI_API_KEY)
            print("[v0] VoiceProcessor: using OpenAI Whisper + TTS for audio")
        else:
            self._oai = None
            print("[v0] VoiceProcessor: audio disabled (Ollama mode — text only)")

        print(f"[v0] VoiceProcessor initialized with sample rate: {self.sample_rate}")

    # ------------------------------------------------------------------
    # Speech-to-Text
    # ------------------------------------------------------------------

    async def transcribe_audio(
        self,
        audio_data: str,
        language: str = "en",
        # FIX: Accept optional hint text from the WebSocket message so that
        # in mock mode the frontend sees the real typed text, not a placeholder.
        hint_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe base64-encoded audio.

        In Ollama/text-only mode:
          - If hint_text is supplied (forwarded from the WS message), return it verbatim.
          - Otherwise fall back to a generic placeholder.
        """
        audio_bytes = self.decode_audio_chunk(audio_data)
        duration = len(audio_bytes) / (self.sample_rate * 2) if audio_bytes else 0

        if not self._voice_enabled:
            # ── FIXED: use the actual text from the WS message if available ──
            text = hint_text if hint_text else "I need to book an appointment"
            if not hint_text:
                print("[v0] STT skipped (Ollama mode) — no hint_text, using placeholder")
            else:
                print(f"[v0] STT skipped (Ollama mode) — forwarding hint_text: {text!r}")
            return {
                "text":       text,
                "confidence": 0.90,
                "language":   language,
                "duration":   duration,
                "mock":       True,
            }

        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = f"audio_{language}.wav"

            transcript = self._oai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language if language != "ta" else None,
            )

            return {
                "text":       transcript.text,
                "confidence": 0.95,
                "language":   language,
                "duration":   duration,
            }

        except Exception as e:
            print(f"[v0] STT error: {e}")
            return {"text": "", "confidence": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Text-to-Speech
    # ------------------------------------------------------------------

    async def synthesize_speech(
        self,
        text: str,
        language: str = "en",
        voice: str = "alloy",
    ) -> Optional[str]:
        """Convert text to speech. Returns None in Ollama/text-only mode."""
        if not self._voice_enabled:
            print("[v0] TTS skipped (Ollama mode)")
            return None

        try:
            print(f"[v0] TTS generating speech for: {text[:60]}...")
            voice_map = {"en": "alloy", "hi": "nova", "ta": "shimmer"}
            selected_voice = voice_map.get(language, voice)

            response = self._oai.audio.speech.create(
                model="tts-1",
                voice=selected_voice,
                input=text,
                response_format="mp3",
            )

            audio_base64 = base64.b64encode(response.content).decode()
            print(f"[v0] TTS audio generated: {len(response.content)} bytes")
            return audio_base64

        except Exception as e:
            print(f"[v0] TTS error: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def decode_audio_chunk(self, audio_data: str) -> bytes:
        try:
            return base64.b64decode(audio_data)
        except Exception as e:
            print(f"[v0] Audio decode error: {e}")
            return b""

    def encode_audio_chunk(self, audio_bytes: bytes) -> str:
        try:
            return base64.b64encode(audio_bytes).decode()
        except Exception as e:
            print(f"[v0] Audio encode error: {e}")
            return ""

    async def extract_audio_features(self, audio_bytes: bytes) -> Dict[str, Any]:
        return {
            "duration":      len(audio_bytes) / (self.sample_rate * 2),
            "energy":        0.5,
            "silence_ratio": 0.1,
        }