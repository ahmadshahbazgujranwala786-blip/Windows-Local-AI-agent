from __future__ import annotations
from windows_agent.agent.screen_perception import ScreenPerception
from typing import Any


class GetImportantFramesTool:
 
    def __init__(
        self,
        screen_perception: ScreenPerception,
    ) -> None:

        self.screen_perception = (
            screen_perception
        )

    def __call__(self) -> dict[str, Any]:

        frames = (
            self.screen_perception
            .get_rolling_buffer()
        )

        return {
            "success": True,
            "frames": frames,
            "count": len(frames),
        }
