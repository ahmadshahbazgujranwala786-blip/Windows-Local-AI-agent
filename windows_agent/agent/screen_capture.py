import time
from typing import Iterator, Optional

import dxcam
import numpy as np


class ScreenCapture:
    def __init__(
        self,
        target_fps: int = 30,
        output_idx: int = 0,
    ):
        self.target_fps = target_fps
        self.output_idx = output_idx

        self.camera = dxcam.create(
            output_idx=self.output_idx,
            backend="dxgi",
            output_color="BGR",
        )

        self._running = False

    def start(self) -> None:
        if self._running:
            return

        self.camera.start(
            target_fps=self.target_fps,
            video_mode=False,
        )

        self._running = True

    def stop(self) -> None:
        if not self._running:
            return

        self.camera.stop()
        self._running = False

    def get_frame(self) -> Optional[tuple[np.ndarray, float]]:
        if not self._running:
            raise RuntimeError("Screen capture is not running.")

        frame, timestamp = self.camera.get_latest_frame(
            with_timestamp=True,
        )

        if frame is None:
            return None

        return frame, timestamp

    def frames(self) -> Iterator[tuple[np.ndarray, float]]:
        if not self._running:
            raise RuntimeError("Screen capture is not running.")

        while self._running:
            result = self.get_frame()

            if result is None:
                time.sleep(0.001)
                continue

            yield result

    def is_running(self) -> bool:
        return self._running

    def release(self) -> None:
        if self._running:
            self.stop()

        self.camera.release()