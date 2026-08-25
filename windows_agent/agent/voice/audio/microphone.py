# Install dependency first:
# python -m pip install sounddevice numpy
#REMEMBER!!! Call back function technique is used whenever we want a function not to immediately call
# We are using the callback function so that its calling will be decided by arriving chunks(audio signlas)
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import sounddevice as sd


@dataclass(frozen=True)
class AudioChunk:

    samples: np.ndarray
    sample_rate: int


class Microphone:

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        block_size: int = 512,
        device: int | str | None = None,
    ) -> None:

        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.device = device

        self._stream: sd.InputStream | None = None
        self._audio_callback: Callable[[AudioChunk], None] | None = None

    def set_callback(# Used to callback the show_audio function
        self,
        callback: Callable[[AudioChunk], None],
    ) -> None:
   
        self._audio_callback = callback# actually we are making that line a callable function

    def _handle_audio(# gets the audio data and creas the chunks
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:


        if status:
            print(f"Microphone status: {status}")

        if self._audio_callback is None:
            return

        chunk = AudioChunk(
            samples=indata.copy(),
            sample_rate=self.sample_rate,
        )

        self._audio_callback(chunk)

    def start(self) -> None:
 
        if self._stream is not None:
            return

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            channels=self.channels,
            dtype="float32",
            callback=self._handle_audio,
        )

        self._stream.start()

    def stop(self) -> None:


        if self._stream is None:
            return

        self._stream.stop()
        self._stream.close()
        self._stream = None

    @staticmethod
    def list_devices() -> None:

        print(sd.query_devices())


if __name__ == "__main__":
    microphone = Microphone()

    def show_audio(chunk: AudioChunk) -> None:
        print(
            f"Received {len(chunk.samples)} samples "
            f"at {chunk.sample_rate} Hz"
        )

    microphone.set_callback(show_audio)# the main function will be given only the callback function(roughly)

    try:
        print("Starting microphone...")
        print("Speak into the microphone. Press Ctrl+C to stop.")

        microphone.start()

        while True:
            pass

    except KeyboardInterrupt:
        print("\nStopping microphone...")

    finally:
        microphone.stop()