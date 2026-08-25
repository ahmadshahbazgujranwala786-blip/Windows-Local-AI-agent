from __future__ import annotations

from typing import Callable

import numpy as np
import torch
from silero_vad import VADIterator, load_silero_vad

from windows_agent.agent.voice.audio.microphone import AudioChunk

class VoiceActivityDetector:

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_silence_duration_ms: int = 100,
        speech_pad_ms: int = 30,
    ) -> None:
        

        if sample_rate not in (8000, 16000):
            raise ValueError(
                "Silero VAD supports 8000 Hz and 16000 Hz audio."
            )

        self.sample_rate = sample_rate

        self.model = load_silero_vad()

        self.iterator = VADIterator(
            self.model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=speech_pad_ms,
        )

        self._speech_callback: Callable[[str, AudioChunk], None] | None = None

    def set_callback(
        self,
        callback: Callable[[str, AudioChunk], None],
    ) -> None:

        self._speech_callback = callback

    def process(self, chunk: AudioChunk) -> None:


        if chunk.sample_rate != self.sample_rate:
            raise ValueError(
                f"Expected {self.sample_rate} Hz audio, "
                f"received {chunk.sample_rate} Hz."
            )

        audio = np.asarray(chunk.samples, dtype=np.float32)# Extracting the audio samples

        if audio.ndim == 2:
            audio = audio[:, 0]

        audio_tensor = torch.from_numpy(audio)# To send it to VAD, we should convert it to torch array

        event = self.iterator(audio_tensor)# giving the audio to VAD iterator

        if event is None:
            return

        if self._speech_callback is not None:
            if "start" in event:
                self._speech_callback("start", chunk)

            elif "end" in event:
                self._speech_callback("end", chunk)

    def reset(self) -> None:

        self.iterator.reset_states()


if __name__ == "__main__":
    from windows_agent.agent.voice.audio.microphone import Microphone

    microphone = Microphone(
        sample_rate=16000,
        channels=1,
        block_size=512,
    )

    detector = VoiceActivityDetector(
        sample_rate=16000,
    )

    def on_speech_event(
        event: str,
        chunk: AudioChunk,
    ) -> None:
        print(
            f"Speech {event} "
            f"({len(chunk.samples)} samples)"
        )

    detector.set_callback(on_speech_event)

    microphone.set_callback(detector.process)

    try:
        print("Listening...")
        print("Speak into the microphone. Press Ctrl+C to stop.")

        microphone.start()

        while True:
            pass

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        microphone.stop()
        detector.reset()