from __future__ import annotations

import json

from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

MODEL_DIRECTORY = Path(
    r"C:\Windows Agent\models\stt"
)

MODEL_PATHS = {
    "en": MODEL_DIRECTORY / "vosk-model-small-en-us-0.15",
    "hi": MODEL_DIRECTORY / "vosk-model-small-hi-0.22",
    "ar": MODEL_DIRECTORY / "vosk-model-ar-mgb2-0.4",
}

class VoskSTTEngine:

    def __init__(self, sample_rate: int = 16000) -> None:


        self.sample_rate = sample_rate

        self._model: Model | None = None
        self._language: str | None = None

        SetLogLevel(-1)

    def _load_model(self, language: str) -> None:

        if language not in MODEL_PATHS:
            raise ValueError(
                f"Unsupported language: {language}"
            )

        if (
            self._language == language
            and self._model is not None
        ):
            return

        self.unload()

        model_path = MODEL_PATHS[language]

        if not model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {model_path}"
            )

        self._model = Model(
            str(model_path)
        )

        self._language = language

    def _create_recognizer(self) -> KaldiRecognizer:

        if self._model is None:
            raise RuntimeError(
                "No Vosk model is loaded."
            )

        return KaldiRecognizer(
            self._model,
            self.sample_rate,
        )

    def transcribe(
        self,
        audio_data: bytes,
        language: str,
    ) -> str | None:

        if not audio_data:
            return None

        if len(audio_data) % 2 != 0:
            raise ValueError(
                "PCM audio data must contain 16-bit samples."
            )

        self._load_model(language)

        recognizer = self._create_recognizer()

        recognizer.AcceptWaveform(
            audio_data
        )

        result = json.loads(
            recognizer.FinalResult()
        )

        text = result.get(
            "text",
            "",
        ).strip()

        return text or None

    def unload(self) -> None:
        self._model = None
        self._language = None

    @property
    def language(self) -> str | None:

        return self._language