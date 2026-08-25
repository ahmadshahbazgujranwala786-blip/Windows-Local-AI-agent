# ============================================================
# windows_agent/tools/windows_inspect.py
# ============================================================

from __future__ import annotations

from collections import deque
import difflib
import re
from typing import Any

from pywinauto import Desktop


class WindowsInspect:
    """
    Read-only UI Automation inspection tool.

    Responsibilities:

        1. Resolve a real running top-level application window.
        2. Traverse its UIA tree.
        3. Return compact JSON-safe UI information.

    Supported inspection parameters:

        app
        depth
        filter_types
    """

    _MAX_ELEMENTS = 200

    def __init__(
        self,
        backend: str = "uia",
    ) -> None:
        """
        Initialize the UIA inspection tool.
        """

        if not isinstance(
            backend,
            str,
        ):
            raise TypeError(
                "backend must be a string."
            )

        backend = backend.strip().lower()

        if backend not in {
            "uia",
            "win32",
        }:
            raise ValueError(
                "backend must be 'uia' or 'win32'."
            )

        self.backend = backend

        self._desktop = Desktop(
            backend=self.backend
        )

    # ========================================================
    # PUBLIC TOOL
    # ========================================================

    def call(
        self,
        app: str,
        depth: int = 4,
        filter_types: str = "",
    ) -> list[dict[str, Any]]:
        """
        Inspect a running Windows application and return a compact
        representation of its UIA tree.
        """

        if not isinstance(
            app,
            str,
        ):
            raise TypeError(
                "app must be a string."
            )

        app = app.strip()

        if not app:
            return [
                {
                    "error": "app is required."
                }
            ]

        if not isinstance(
            depth,
            int,
        ):
            raise TypeError(
                "depth must be an integer."
            )

        if depth < 0:
            raise ValueError(
                "depth must be greater than or equal to zero."
            )

        allowed_types = (
            self._parse_filter_types(
                filter_types
            )
        )

        window = (
            self._resolve_window(
                app
            )
        )

        if window is None:

            return [
                {
                    "error": (
                        f"Running application not found: "
                        f"{app}"
                    )
                }
            ]

        return self._inspect_tree(
            window=window,
            depth=depth,
            allowed_types=allowed_types,
        )

    # ========================================================
    # RUNNING WINDOW RESOLUTION
    # ========================================================

    def _resolve_window(
        self,
        app: str,
    ):
        """
        Resolve a real top-level running application window.

        Matching order:

            1. Exact window title.
            2. Normalized exact title.
            3. Target contained in window title.
            4. Window title contained in target.
            5. Conservative fuzzy title match.

        Only top-level desktop windows are considered.
        """

        try:

            windows = list(
                self._desktop.windows(
                    visible_only=False
                )
            )

        except Exception:

            return None

        if not windows:
            return None

        # ----------------------------------------------------
        # 1. Exact title.
        # ----------------------------------------------------

        for window in windows:

            title = (
                self._safe_window_title(
                    window
                )
            )

            if (
                title.casefold()
                == app.casefold()
            ):

                return window

        target = (
            self._normalize_text(
                app
            )
        )

        if not target:
            return None

        # ----------------------------------------------------
        # 2-4. Normalized exact / containment.
        # ----------------------------------------------------

        for window in windows:

            title = (
                self._normalize_text(
                    self._safe_window_title(
                        window
                    )
                )
            )

            if not title:
                continue

            if title == target:
                return window

        for window in windows:

            title = (
                self._normalize_text(
                    self._safe_window_title(
                        window
                    )
                )
            )

            if not title:
                continue

            if target in title:
                return window

        for window in windows:

            title = (
                self._normalize_text(
                    self._safe_window_title(
                        window
                    )
                )
            )

            if not title:
                continue

            if title in target:
                return window

        # ----------------------------------------------------
        # 5. Conservative fuzzy matching.
        # ----------------------------------------------------

        best_ratio = 0.0
        best_window = None

        for window in windows:

            title = (
                self._safe_window_title(
                    window
                )
            )

            if not title:
                continue

            normalized_title = (
                self._normalize_text(
                    title
                )
            )

            if not normalized_title:
                continue

            ratio = (
                difflib.SequenceMatcher(
                    None,
                    target,
                    normalized_title,
                ).ratio()
            )

            if (
                ratio >= 0.75
                and ratio > best_ratio
            ):

                best_ratio = ratio
                best_window = window

        return best_window

    # ========================================================
    # UI TREE INSPECTION
    # ========================================================

    def _inspect_tree(
        self,
        window,
        depth: int,
        allowed_types: set[str],
    ) -> list[dict[str, Any]]:
        """
        Traverse the UIA tree breadth-first and serialize matching
        elements into plain dictionaries.
        """

        queue = deque(
            [
                (
                    window,
                    0,
                )
            ]
        )

        results: list[
            dict[str, Any]
        ] = []

        while queue:

            element, current_depth = (
                queue.popleft()
            )

            if current_depth > depth:
                continue

            control_type = (
                self._get_control_type(
                    element
                )
            )

            matches_filter = (
                not allowed_types
                or control_type.casefold()
                in allowed_types
            )

            if matches_filter:

                serialized = (
                    self._serialize_element(
                        element=element,
                        depth=current_depth,
                        control_type=control_type,
                    )
                )

                results.append(
                    serialized
                )

                if (
                    len(results)
                    >= self._MAX_ELEMENTS
                ):
                    break

            if current_depth >= depth:
                continue

            try:

                children = (
                    element.children()
                )

            except Exception:

                children = []

            for child in children:

                queue.append(
                    (
                        child,
                        current_depth + 1,
                    )
                )

        return results

    # ========================================================
    # SERIALIZATION
    # ========================================================

    def _serialize_element(
        self,
        element,
        depth: int,
        control_type: str,
    ) -> dict[str, Any]:
        """
        Convert one UIA element into JSON-safe information.
        """

        return {
            "name": self._safe_window_text(
                element
            ),
            "automation_id": (
                self._get_automation_id(
                    element
                )
            ),
            "control_type": control_type,
            "value": self._get_value(
                element
            ),
            "rect": self._get_rectangle(
                element
            ),
            "depth": depth,
        }

    # ========================================================
    # CONTROL TYPE
    # ========================================================

    @staticmethod
    def _get_control_type(
        element,
    ) -> str:
        """
        Return the UIA control type.
        """

        try:

            return str(
                element.element_info.control_type
                or ""
            )

        except Exception:

            return ""

    # ========================================================
    # AUTOMATION ID
    # ========================================================

    @staticmethod
    def _get_automation_id(
        element,
    ) -> str:
        """
        Return the UIA AutomationId.
        """

        try:

            return str(
                element.element_info.automation_id
                or ""
            )

        except Exception:

            return ""

    # ========================================================
    # VALUE
    # ========================================================

    @staticmethod
    def _get_value(
        element,
    ) -> str:
        """
        Read the best available value/text from a UIA element.
        """

        try:

            value = (
                element.get_value()
            )

            if value is not None:

                value = str(
                    value
                )

                if value.strip():

                    return value

        except Exception:
            pass

        try:

            value = (
                element.window_text()
            )

            if value is not None:

                value = str(
                    value
                )

                if value.strip():

                    return value

        except Exception:
            pass

        return ""

    # ========================================================
    # RECTANGLE
    # ========================================================

    @staticmethod
    def _get_rectangle(
        element,
    ) -> dict[str, int]:
        """
        Return a UIA element's bounding rectangle.
        """

        try:

            rectangle = (
                element.rectangle()
            )

            return {
                "x": int(
                    rectangle.left
                ),
                "y": int(
                    rectangle.top
                ),
                "w": int(
                    rectangle.width()
                ),
                "h": int(
                    rectangle.height()
                ),
            }

        except Exception:

            return {
                "x": 0,
                "y": 0,
                "w": 0,
                "h": 0,
            }

    # ========================================================
    # FILTER
    # ========================================================

    @staticmethod
    def _parse_filter_types(
        filter_types: str,
    ) -> set[str]:
        """
        Parse a comma-separated control-type filter.
        """

        if not isinstance(
            filter_types,
            str,
        ):
            raise TypeError(
                "filter_types must be a string."
            )

        return {
            value.strip().casefold()
            for value in filter_types.split(",")
            if value.strip()
        }

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _safe_window_title(
        window,
    ) -> str:
        """
        Safely return a top-level window title.
        """

        try:

            return str(
                window.window_text()
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _safe_window_text(
        element,
    ) -> str:
        """
        Safely return an element's visible/accessibility text.
        """

        try:

            return str(
                element.window_text()
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize text for case-insensitive UI matching.
        """

        text = text.casefold()

        text = re.sub(
            r"[^a-z0-9]+",
            " ",
            text,
        )

        return " ".join(
            text.split()
        )