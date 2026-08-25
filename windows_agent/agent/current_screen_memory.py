import numpy as np

class CurrentScreenMemory:

    def __init__(self):
        self._frame: np.ndarray | None = None

    def update(
        self,
        frame: np.ndarray,
    ) -> None:

        if not isinstance(frame, np.ndarray):
            raise TypeError(
                "frame must be a numpy.ndarray."
            )

        if frame.size == 0:
            raise ValueError(
                "frame cannot be empty."
            )

        self._frame = frame.copy()

    def get_frame(
        self,
    ) -> np.ndarray | None:

        if self._frame is None:
            return None

        return self._frame.copy()
