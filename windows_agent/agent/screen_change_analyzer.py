from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# NEW: CurrentScreenMemory import
from windows_agent.agent.current_screen_memory import (
    CurrentScreenMemory,
)


@dataclass
class ChangedRegion:
    x: int
    y: int
    width: int
    height: int
    area: int
    importance: float


@dataclass
class ScreenChangeResult:
    changed: bool
    importance: float
    regions: list[ChangedRegion]


class ScreenChangeAnalyzer:
    def __init__(
        self,
        change_threshold: float = 0.02,
        pixel_threshold: int = 25,
        min_region_area: int = 500,
        current_screen_memory: Optional[
            CurrentScreenMemory
        ] = None,
    ):
        self.change_threshold = change_threshold
        self.pixel_threshold = pixel_threshold
        self.min_region_area = min_region_area

        self._previous_frame: Optional[np.ndarray] = None

        self._current_screen_memory = current_screen_memory

    def analyze(
        self,
        frame: np.ndarray,
    ) -> ScreenChangeResult:
        self._validate_frame(frame)

        if self._previous_frame is None:
            self._previous_frame = frame.copy()

            return ScreenChangeResult(
                changed=False,
                importance=0.0,
                regions=[],
            )

        if frame.shape != self._previous_frame.shape:
            self._previous_frame = frame.copy()

            return ScreenChangeResult(
                changed=False,
                importance=0.0,
                regions=[],
            )

        previous_gray = cv2.cvtColor(
            self._previous_frame,
            cv2.COLOR_BGR2GRAY,
        )

        current_gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        difference = cv2.absdiff(
            previous_gray,
            current_gray,
        )

        _, difference_mask = cv2.threshold(
            difference,
            self.pixel_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        kernel = np.ones(
            (3, 3),
            np.uint8,
        )

        difference_mask = cv2.morphologyEx(
            difference_mask,
            cv2.MORPH_OPEN,# removes the noisy areas and maintain the main changing areas
            kernel,
        )

        contours, _ = cv2.findContours(# Finding the contours of shapes while neglecting the nestes contours
            difference_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        screen_area = frame.shape[0] * frame.shape[1]

        regions: list[ChangedRegion] = []
        changed_area = 0

        for contour in contours:
            area = int(cv2.contourArea(contour))

            if area < self.min_region_area:
                continue

            x, y, width, height = cv2.boundingRect(
                contour
            )

            region_importance = area / screen_area

            regions.append(
                ChangedRegion(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    area=area,
                    importance=region_importance,
                )
            )

            changed_area += area

        importance = changed_area / screen_area

        changed = importance >= self.change_threshold

        if self._previous_frame is None:
           self._previous_frame = frame.copy()

        if self._current_screen_memory is not None:
            self._current_screen_memory.update(frame)

        return ScreenChangeResult(
        changed=False,
        importance=0.0,
        regions=[],
    )

    def reset(self) -> None:
        self._previous_frame = None

    def _validate_frame(
        self,
        frame: np.ndarray,
    ) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError(
                "Frame must be a numpy.ndarray."
            )

        if frame.ndim != 3:
            raise ValueError(
                "Frame must have 3 dimensions."
            )

        if frame.shape[2] != 3:
            raise ValueError(
                "Frame must have 3 color channels."
            )
