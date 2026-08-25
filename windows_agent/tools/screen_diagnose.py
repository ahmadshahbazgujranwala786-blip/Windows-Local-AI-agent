from __future__ import annotations

from typing import Any

import numpy as np

from windows_agent.agent.current_screen_memory import (
    CurrentScreenMemory,
)


class ScreenDiagnoseTool:

    def __init__(
        self,
        screen_memory: CurrentScreenMemory,
    ) -> None:


        if not isinstance(
            screen_memory,
            CurrentScreenMemory,
        ):
            raise TypeError(
                "screen_memory must be a CurrentScreenMemory."
            )

        self._screen_memory = (
            screen_memory
        )

    def diagnose(
        self,
    ) -> dict[str, Any]:

        frame = (
            self._screen_memory.get_frame()
        )

        if frame is None:
            return {
                "type": "vision",
                "available": False,
                "reason": (
                    "No current screen frame is available."
                ),
            }

        if not isinstance(
            frame,
            np.ndarray,
        ):
            raise TypeError(
                "CurrentScreenMemory returned "
                "an invalid frame."
            )

        if frame.size == 0:
            return {
                "type": "vision",
                "available": False,
                "reason": (
                    "The current screen frame is empty."
                ),
            }

        return {
            "type": "vision",
            "available": True,
            "frame": frame,
        }