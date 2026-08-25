from __future__ import annotations

import threading
from typing import Callable

from windows_agent.agent.voice.stt.engine import VoskSTTEngine


SILENCE_TIMEOUT = 3.0


class STTService:

    def __init__(
        self,
        engine: VoskSTTEngine,
        language: str = "en",
        silence_timeout: float = SILENCE_TIMEOUT,
        result_callback: Callable[[str], None] | None = None,
    ) -> None:


        self.engine = engine
        self.language = language
        self.silence_timeout = silence_timeout
        self.result_callback = result_callback

        self._audio_buffer = bytearray()

        self._active = False
        self._silence_timer: threading.Timer | None = None

        self._lock = threading.Lock()

    def process_audio(
        self,
        audio_data: bytes,
    ) -> None:


        if not audio_data:
            return

        self.start()

        self.add_audio(
            audio_data,
        )

        self.speech_stopped()

    def start(self) -> None:


        with self._lock:
            self._cancel_timer()

            self._audio_buffer.clear()
            self._active = True

    def add_audio(
        self,
        audio_data: bytes,
    ) -> None:

        if not audio_data:
            return

        with self._lock:
            if not self._active:
                return

            self._audio_buffer.extend(
                audio_data
            )

    def speech_started(self) -> None:


        with self._lock:
            if not self._active:
                self._active = True

            self._cancel_timer()

    def speech_stopped(self) -> None:

        with self._lock:
            if not self._active:
                return

            self._cancel_timer()

            self._silence_timer = threading.Timer(
                self.silence_timeout,
                self._finalize_session,
            )

            self._silence_timer.daemon = True
            self._silence_timer.start()

    def _finalize_session(self) -> None:

        print(
            "STT: 3-second timer fired"
        )

        with self._lock:
            if not self._active:
                print(
                    "STT: session is inactive"
                )
                return

            audio_data = bytes(
                self._audio_buffer
            )

            print(
                f"STT: finalizing "
                f"{len(audio_data)} audio bytes"
            )

            self._audio_buffer.clear()
            self._active = False
            self._silence_timer = None

            if not audio_data:
                print(
                    "STT: audio buffer is empty"
                )
                return

        print(
            "STT: sending audio to Vosk..."
        )

        text = self.engine.transcribe(
            audio_data,
            self.language,
        )

        print(
            f"STT: Vosk returned: {text!r}"
        )

        if text and self.result_callback:
            self.result_callback(text)

    def _cancel_timer(self) -> None:

        if self._silence_timer is not None:
            self._silence_timer.cancel()
            self._silence_timer = None

    def stop(self) -> None:


        with self._lock:
            self._cancel_timer()

            self._audio_buffer.clear()
            self._active = False