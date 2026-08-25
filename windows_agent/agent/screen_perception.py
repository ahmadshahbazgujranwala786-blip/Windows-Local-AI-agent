from __future__ import annotations

from collections import deque
from dataclasses import asdict
from typing import Any

from windows_agent.agent.screen_change_analyzer import (
    ChangedRegion,
    ScreenChangeResult,
)
from windows_agent.agent.uia_information import (
    UIAInformation,
)


class ScreenPerception:

    def __init__(
        self,
        uia_information: UIAInformation,
        buffer_size: int = 10,
    ) -> None:

        self._uia = uia_information

        self._rolling_buffer: deque[
            dict[str, Any]
        ] = deque(
            maxlen=buffer_size
        )

    def analyze(
        self,
        change_result: ScreenChangeResult,
    ) -> dict[str, Any]:

        if not isinstance(
            change_result,
            ScreenChangeResult,
        ):
            raise TypeError(
                "change_result must be a ScreenChangeResult."
            )

        regions: list[dict[str, Any]] = []

        for region in change_result.regions:

            region_data = self._process_region(
                region
            )

            regions.append(region_data)

        result: dict[str, Any] = {
            "changed": change_result.changed,
            "importance": change_result.importance,
            "regions": regions,
        }

        self._rolling_buffer.append(
            result
        )

        return result

    def _process_region(
        self,
        region: ChangedRegion,
    ) -> dict[str, Any]:

        point = self._region_center(
            region
        )

        uia_info = self._uia.element_from_point(
            point[0],
            point[1],
        )

        region_data: dict[str, Any] = {
            "region": asdict(region),
            "query_point": {
                "x": point[0],
                "y": point[1],
            },
            "uia": None,
        }

        if uia_info is not None:

            region_data["uia"] = asdict(
                uia_info
            )

        return region_data

    def _region_center(
        self,
        region: ChangedRegion,
    ) -> tuple[int, int]:

        center_x = (
            region.x
            + region.width // 2
        )

        center_y = (
            region.y
            + region.height // 2
        )

        return (
            center_x,
            center_y,
        )

    def get_rolling_buffer(
        self,
    ) -> list[dict[str, Any]]:

        return list(
            self._rolling_buffer
        )

    def clear_rolling_buffer(
        self,
    ) -> None:

        self._rolling_buffer.clear()