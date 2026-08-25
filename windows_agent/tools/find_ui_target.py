from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from windows_agent.agent.current_screen_memory import (
    CurrentScreenMemory,
)
from windows_agent.agent.uia_information import (
    UIAInformation,
)


UIA_CONFIDENCE_THRESHOLD = 0.75


@dataclass
class UITargetInfo:
    name: Optional[str]
    control_type: Optional[str]
    automation_id: Optional[str]
    bounding_rectangle: Optional[
        tuple[float, float, float, float]
    ]
    center: Optional[
        tuple[int, int]
    ]


class FindUITarget:
    """
    Find a UI target using UIA first and OCR as fallback.

    UIA candidates are already ranked by UIAInformation. The first
    candidate above the confidence threshold is accepted. Both UIA
    and OCR results include a verified center coordinate.
    """

    def __init__(
        self,
        screen_memory: CurrentScreenMemory,
        ocr,
        uia_information: UIAInformation,
    ) -> None:
        """
        Initialize screen, OCR, and UIA services.

        UIAInformation handles candidate discovery and confidence
        scoring. This class handles threshold filtering and OCR fallback.
        """

        self._screen_memory = screen_memory
        self._ocr = ocr
        self._uia_information = uia_information

    def find(
        self,
        target: str,
        area: Optional[
            tuple[int, int, int, int]
        ] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Find a target using UIA first and OCR second.

        The first UIA candidate above the confidence threshold is
        returned. Otherwise OCR is used as the fallback.
        """

        if not isinstance(
            target,
            str,
        ):
            raise TypeError(
                "target must be a string."
            )

        target = target.strip()

        if not target:
            raise ValueError(
                "target cannot be empty."
            )

        uia_result = self._find_with_uia(
            target,
            area,
        )

        if uia_result is not None:
            return {
                "found": True,
                "method": "uia",
                "target": uia_result,
            }

        frame = (
            self._screen_memory.get_frame()
        )

        if frame is None:
            return {
                "found": False,
                "method": "none",
                "reason": (
                    "current_screen_frame_unavailable"
                ),
            }

        ocr_result = self._find_with_ocr(
            frame,
            target,
            area,
        )

        if ocr_result is not None:
            return {
                "found": True,
                "method": "ocr",
                "target": ocr_result,
            }

        return {
            "found": False,
            "method": "uia_ocr",
            "reason": "target_not_found",
        }

    def _find_with_uia(
        self,
        target: str,
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> Optional[dict[str, Any]]:
        """
        Check the top UIA candidates and accept the first candidate
        whose confidence exceeds the configured threshold.
        """

        candidates = (
            self._uia_information.find_candidates(
                target=target,
                area=area,
                max_candidates=3,
            )
        )

        if not candidates:
            return None

        for candidate in candidates:

            if (
                candidate.confidence
                > UIA_CONFIDENCE_THRESHOLD
            ):
                result = asdict(
                    candidate.element
                )

                result["center"] = (
                    self._calculate_center(
                        candidate.element.bounding_rectangle
                    )
                )

                result["confidence"] = (
                    candidate.confidence
                )

                return result

        return None

    def _find_with_ocr(
        self,
        frame,
        target: str,
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> Optional[dict[str, Any]]:
        """
        Search OCR lines and words for the target.

        OCR results include the bounding rectangle and its verified
        center coordinate.
        """

        lines = self._ocr.recognize(
            frame
        )

        target_normalized = (
            self._normalize_text(
                target
            )
        )

        for line in lines:

            if (
                self._normalize_text(
                    line.text
                )
                == target_normalized
            ):
                rectangle = (
                    self._line_bounding_rectangle(
                        line
                    )
                )

                if rectangle is None:
                    continue

                if (
                    area is not None
                    and not self._rectangle_intersects_xywh(
                        rectangle,
                        area,
                    )
                ):
                    continue

                return {
                    "text": line.text,
                    "bounding_rectangle": rectangle,
                    "center": (
                        self._calculate_center(
                            rectangle
                        )
                    ),
                    "words": [
                        {
                            "text": word.text,
                            "bounding_rectangle": (
                                word.bounding_rectangle
                            ),
                            "center": (
                                self._calculate_center_xywh(
                                    word.bounding_rectangle
                                )
                            ),
                        }
                        for word in line.words
                    ],
                }

            for word in line.words:

                if (
                    self._normalize_text(
                        word.text
                    )
                    != target_normalized
                ):
                    continue

                rectangle = (
                    word.bounding_rectangle
                )

                if (
                    area is not None
                    and not self._rectangle_intersects_xywh(
                        rectangle,
                        area,
                    )
                ):
                    continue

                return {
                    "text": word.text,
                    "bounding_rectangle": rectangle,
                    "center": (
                        self._calculate_center_xywh(
                            rectangle
                        )
                    ),
                }

        return None

    @staticmethod
    def _calculate_center(
        rectangle: Optional[
            tuple[float, float, float, float]
        ],
    ) -> Optional[
        tuple[int, int]
    ]:
        """
        Calculate the screen center from an LTRB rectangle.
        """

        if rectangle is None:
            return None

        left, top, right, bottom = rectangle

        return (
            round((left + right) / 2),
            round((top + bottom) / 2),
        )

    @staticmethod
    def _calculate_center_xywh(
        rectangle: Optional[
            tuple[float, float, float, float]
        ],
    ) -> Optional[
        tuple[int, int]
    ]:
        """
        Calculate the screen center from an XYWH rectangle.
        """

        if rectangle is None:
            return None

        x, y, width, height = rectangle

        return (
            round(x + width / 2),
            round(y + height / 2),
        )

    @staticmethod
    def _line_bounding_rectangle(
        line,
    ) -> Optional[
        tuple[float, float, float, float]
    ]:
        """
        Combine OCR word rectangles into one LTRB line rectangle.
        """

        if not line.words:
            return None

        left = min(
            word.bounding_rectangle[0]
            for word in line.words
        )

        top = min(
            word.bounding_rectangle[1]
            for word in line.words
        )

        right = max(
            word.bounding_rectangle[0]
            + word.bounding_rectangle[2]
            for word in line.words
        )

        bottom = max(
            word.bounding_rectangle[1]
            + word.bounding_rectangle[3]
            for word in line.words
        )

        return (
            left,
            top,
            right,
            bottom,
        )

    @staticmethod
    def _rectangle_intersects_xywh(
        rectangle: tuple[
            float,
            float,
            float,
            float,
        ],
        area: tuple[int, int, int, int],
    ) -> bool:
        """
        Check whether an OCR rectangle intersects the requested area.
        """

        x, y, width, height = rectangle

        right = x + width
        bottom = y + height

        left_a, top_a, right_a, bottom_a = area

        return not (
            right <= left_a
            or x >= right_a
            or bottom <= top_a
            or y >= bottom_a
        )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize text for OCR comparison.
        """

        text = text.casefold()

        normalized = []

        for character in text:

            if character.isalnum():
                normalized.append(
                    character
                )
            else:
                normalized.append(
                    " "
                )

        return " ".join(
            "".join(
                normalized
            ).split()
        )

    def close(
        self,
    ) -> None:
        """
        Release target-finder resources.

        UIA COM cleanup belongs to UIAInformation.
        """

        return None