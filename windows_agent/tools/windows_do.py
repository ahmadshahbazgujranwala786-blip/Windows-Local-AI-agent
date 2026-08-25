# ============================================================
# windows_agent/tools/windows_do.py
# ============================================================

from __future__ import annotations

import ctypes
import tempfile
import time
from typing import Any

import pyautogui
from PIL import ImageGrab
from pywinauto import Desktop


class WindowsDo:
    """
    High-level Windows UI interaction tool.

    One public call() executes one or more UI actions against a
    running application.

    Supported actions:

        click
        double_click
        right_click
        type
        key
        scroll
        focus
        read
        read_screen
        wait
        screenshot
        close_app
    """

    def __init__(
        self,
        backend: str = "uia",
        inspector=None,
        window_resolver=None,
    ) -> None:
        """
        Initialize the Windows UI interaction tool.

        inspector:
            Optional WindowsInspect-compatible object.

        window_resolver:
            Optional WindowsLaunch-compatible object.
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

        self._inspector = inspector
        self._window_resolver = (
            window_resolver
        )

        pyautogui.PAUSE = 0.05
        pyautogui.FAILSAFE = True

    # ========================================================
    # PUBLIC TOOL
    # ========================================================

    def call(
        self,
        app: str,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Execute a sequential batch of UI actions on a running app.

        When an action or target fails, an inspection snapshot is
        attached when an inspector is available.
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
                    "action": "",
                    "target": None,
                    "status": "error",
                    "detail": "app is required.",
                    "value": None,
                }
            ]

        if not isinstance(
            actions,
            list,
        ):
            raise TypeError(
                "actions must be a list."
            )

        if not actions:
            return [
                {
                    "action": "",
                    "target": None,
                    "status": "error",
                    "detail": (
                        "actions must be a non-empty list."
                    ),
                    "value": None,
                }
            ]

        window = (
            self._resolve_window(
                app
            )
        )

        if window is None:

            return [
                {
                    "action": str(
                        action.get(
                            "action",
                            "",
                        )
                    )
                    if isinstance(
                        action,
                        dict,
                    )
                    else "",
                    "target": None,
                    "status": "error",
                    "detail": (
                        f"Running application not found: "
                        f"{app}"
                    ),
                    "value": None,
                }
                for action in actions
            ]

        self._bring_to_foreground(
            window
        )

        results: list[
            dict[str, Any]
        ] = []

        for index, action in enumerate(
            actions
        ):

            if not isinstance(
                action,
                dict,
            ):

                results.append(
                    {
                        "action": "",
                        "target": None,
                        "status": "error",
                        "detail": (
                            "Each action must be an object."
                        ),
                        "value": None,
                    }
                )

                continue

            action_type = str(
                action.get(
                    "action",
                    "",
                )
            ).strip().lower()

            target_descriptor = (
                action.get(
                    "target"
                )
            )

            element = None

            if target_descriptor is not None:

                element = (
                    self._find_element(
                        window=window,
                        target=target_descriptor,
                    )
                )

                if element is None:

                    result = (
                        self._make_result(
                            action=action,
                            target=None,
                            status="error",
                            detail=(
                                "Element not found: "
                                f"{target_descriptor}"
                            ),
                        )
                    )

                    result[
                        "inspect_fallback"
                    ] = (
                        self._inspect_fallback(
                            app
                        )
                    )

                    results.append(
                        result
                    )

                    continue

            try:

                result = (
                    self._execute_action(
                        action=action,
                        element=element,
                        window=window,
                    )
                )

            except Exception as exc:

                result = (
                    self._make_result(
                        action=action,
                        target=None,
                        status="error",
                        detail=str(
                            exc
                        ),
                    )
                )

            if (
                result.get(
                    "status"
                )
                == "error"
            ):

                result[
                    "inspect_fallback"
                ] = (
                    self._inspect_fallback(
                        app
                    )
                )

            results.append(
                result
            )

            if (
                action_type == "close_app"
                and result.get(
                    "status"
                ) == "ok"
            ):

                for skipped in (
                    actions[
                        index + 1:
                    ]
                ):

                    results.append(
                        {
                            "action": (
                                skipped.get(
                                    "action",
                                    "",
                                )
                            )
                            if isinstance(
                                skipped,
                                dict,
                            )
                            else "",
                            "target": None,
                            "status": "skipped",
                            "detail": (
                                "skipped because "
                                "the application "
                                "was closed."
                            ),
                            "value": None,
                        }
                    )

                break

        return results

    # ========================================================
    # ACTION EXECUTOR
    # ========================================================

    def _execute_action(
        self,
        action: dict[str, Any],
        element,
        window,
    ) -> dict[str, Any]:
        """
        Execute one UI action and return a normalized result.
        """

        action_type = str(
            action.get(
                "action",
                "",
            )
        ).strip().lower()

        target_name = (
            self._safe_element_name(
                element
            )
            if element is not None
            else None
        )

        # ----------------------------------------------------
        # CLICK
        # ----------------------------------------------------

        if action_type == "click":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "click requires a target.",
                )

            element.click_input()

            return self._make_result(
                action,
                target_name,
                "ok",
                "clicked",
            )

        # ----------------------------------------------------
        # DOUBLE CLICK
        # ----------------------------------------------------

        if action_type == "double_click":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "double_click requires a target.",
                )

            element.double_click_input()

            return self._make_result(
                action,
                target_name,
                "ok",
                "double-clicked",
            )

        # ----------------------------------------------------
        # RIGHT CLICK
        # ----------------------------------------------------

        if action_type == "right_click":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "right_click requires a target.",
                )

            element.right_click_input()

            return self._make_result(
                action,
                target_name,
                "ok",
                "right-clicked",
            )

        # ----------------------------------------------------
        # TYPE
        # ----------------------------------------------------

        if action_type == "type":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "type requires a target.",
                )

            text = action.get(
                "text",
                "",
            )

            append = bool(
                action.get(
                    "append",
                    False,
                )
            )

            if not isinstance(
                text,
                str,
            ):

                return self._make_result(
                    action,
                    target_name,
                    "error",
                    "text must be a string.",
                )

            # ------------------------------------------------
            # Focus the target.
            # ------------------------------------------------

            element.set_focus()

            # ------------------------------------------------
            # Clear when append=False.
            # ------------------------------------------------

            if not append:

                try:

                    element.set_edit_text(
                        ""
                    )

                except Exception:

                    pyautogui.hotkey(
                        "ctrl",
                        "a",
                    )

                    pyautogui.press(
                        "delete"
                    )

            # ------------------------------------------------
            # Prefer UIA typing.
            # ------------------------------------------------

            try:

                element.type_keys(
                    text,
                    with_spaces=True,
                )

            except Exception:

                pyautogui.write(
                    text,
                    interval=0.01,
                )

            return self._make_result(
                action,
                target_name,
                "ok",
                f"typed {len(text)} chars",
            )

        # ----------------------------------------------------
        # KEY
        # ----------------------------------------------------

        if action_type == "key":

            keys = action.get(
                "keys",
                "",
            )

            if not isinstance(
                keys,
                str,
            ):

                return self._make_result(
                    action,
                    target_name,
                    "error",
                    "keys must be a string.",
                )

            keys = keys.strip()

            if not keys:

                return self._make_result(
                    action,
                    target_name,
                    "error",
                    "keys cannot be empty.",
                )

            self._send_key_combo(
                keys
            )

            return self._make_result(
                action,
                target_name,
                "ok",
                f"sent key: {keys}",
            )

        # ----------------------------------------------------
        # SCROLL
        # ----------------------------------------------------

        if action_type == "scroll":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "scroll requires a target.",
                )

            direction = str(
                action.get(
                    "direction",
                    "down",
                )
            ).strip().lower()

            amount = int(
                action.get(
                    "amount",
                    3,
                )
            )

            if amount <= 0:

                return self._make_result(
                    action,
                    target_name,
                    "error",
                    "amount must be greater than zero.",
                )

            self._scroll_element(
                element,
                direction,
                amount,
            )

            return self._make_result(
                action,
                target_name,
                "ok",
                (
                    f"scrolled "
                    f"{direction} "
                    f"{amount}"
                ),
            )

        # ----------------------------------------------------
        # FOCUS
        # ----------------------------------------------------

        if action_type == "focus":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "focus requires a target.",
                )

            element.set_focus()

            return self._make_result(
                action,
                target_name,
                "ok",
                "focused",
            )

        # ----------------------------------------------------
        # READ
        # ----------------------------------------------------

        if action_type == "read":

            if element is None:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "read requires a target.",
                )

            value = (
                self._read_element_value(
                    element
                )
            )

            return self._make_result(
                action,
                target_name,
                "ok",
                "read value",
                value=value,
            )

        # ----------------------------------------------------
        # READ SCREEN
        # ----------------------------------------------------

        if action_type == "read_screen":

            value = (
                self._read_screen(
                    window
                )
            )

            return self._make_result(
                action,
                None,
                "ok",
                "read screen",
                value=value,
            )

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        if action_type == "wait":

            milliseconds = int(
                action.get(
                    "ms",
                    1000,
                )
            )

            if milliseconds < 0:

                return self._make_result(
                    action,
                    None,
                    "error",
                    "ms cannot be negative.",
                )

            time.sleep(
                milliseconds
                / 1000.0
            )

            return self._make_result(
                action,
                None,
                "ok",
                f"waited {milliseconds}ms",
            )

        # ----------------------------------------------------
        # SCREENSHOT
        # ----------------------------------------------------

        if action_type == "screenshot":

            path = (
                self._take_screenshot()
            )

            return self._make_result(
                action,
                None,
                "ok",
                "screenshot saved",
                value=path,
            )

        # ----------------------------------------------------
        # CLOSE APP
        # ----------------------------------------------------

        if action_type == "close_app":

            self._close_window(
                window
            )

            return self._make_result(
                action,
                None,
                "ok",
                "window closed",
            )

        # ----------------------------------------------------
        # UNKNOWN ACTION
        # ----------------------------------------------------

        return self._make_result(
            action,
            target_name,
            "error",
            (
                "Unknown action: "
                f"{action_type!r}"
            ),
        )

    # ========================================================
    # ELEMENT RESOLUTION
    # ========================================================

    def _find_element(
        self,
        window,
        target: Any,
    ):
        """
        Resolve a live UIA element from a target descriptor.

        Supported target forms:

            string
                Matches element name or AutomationId.

            dict
                Can contain:
                    name
                    automation_id
                    control_type
                    rect

        Resolution priority:

            1. AutomationId + control type
            2. Exact name + control type
            3. Exact rectangle + control type
            4. Exact rectangle
            5. Name
            6. AutomationId
            7. Control type + rectangle proximity

        This allows unnamed elements such as Notepad's Document
        control to be resolved using the rectangle returned by
        windows_inspect.
        """

        candidates = (
            self._get_descendants(
                window
            )
        )

        # ----------------------------------------------------
        # STRING TARGET
        # ----------------------------------------------------

        if isinstance(
            target,
            str,
        ):

            target_text = (
                target.strip()
            )

            if not target_text:
                return None

            normalized_target = (
                self._normalize_text(
                    target_text
                )
            )

            # Exact name.
            for element in candidates:

                name = (
                    self._normalize_text(
                        self._safe_element_name(
                            element
                        )
                    )
                )

                if (
                    name
                    == normalized_target
                ):

                    return element

            # Exact AutomationId.
            for element in candidates:

                automation_id = (
                    self._normalize_text(
                        self._safe_automation_id(
                            element
                        )
                    )
                )

                if (
                    automation_id
                    == normalized_target
                ):

                    return element

            # Substring name.
            for element in candidates:

                name = (
                    self._normalize_text(
                        self._safe_element_name(
                            element
                        )
                    )
                )

                if (
                    normalized_target
                    and normalized_target in name
                ):

                    return element

            return None

        # ----------------------------------------------------
        # DICTIONARY TARGET
        # ----------------------------------------------------

        if not isinstance(
            target,
            dict,
        ):
            return None

        requested_name = (
            self._optional_normalized(
                target.get(
                    "name"
                )
            )
        )

        requested_automation_id = (
            self._optional_normalized(
                target.get(
                    "automation_id"
                )
            )
        )

        requested_control_type = (
            self._optional_normalized(
                target.get(
                    "control_type"
                )
            )
        )

        requested_rect = (
            self._normalize_rect(
                target.get(
                    "rect"
                )
            )
        )

        # ----------------------------------------------------
        # Candidate scoring.
        #
        # We score every live UIA element against the inspection
        # descriptor and return only the strongest valid candidate.
        # ----------------------------------------------------

        best_element = None
        best_score = -1.0

        for element in candidates:

            score = 0.0

            actual_name = (
                self._optional_normalized(
                    self._safe_element_name(
                        element
                    )
                )
            )

            actual_automation_id = (
                self._optional_normalized(
                    self._safe_automation_id(
                        element
                    )
                )
            )

            actual_control_type = (
                self._optional_normalized(
                    self._safe_control_type(
                        element
                    )
                )
            )

            actual_rect = (
                self._get_element_rect(
                    element
                )
            )

            # ------------------------------------------------
            # AutomationId
            # ------------------------------------------------

            if requested_automation_id:

                if (
                    actual_automation_id
                    == requested_automation_id
                ):

                    score += 100.0

                elif (
                    requested_automation_id
                    in actual_automation_id
                ):

                    score += 50.0

                else:

                    # If an AutomationId was supplied and does
                    # not match, this is normally a different
                    # element. Penalize it strongly.
                    score -= 100.0

            # ------------------------------------------------
            # Name
            # ------------------------------------------------

            if requested_name:

                if (
                    actual_name
                    == requested_name
                ):

                    score += 80.0

                elif (
                    actual_name
                    and requested_name in actual_name
                ):

                    score += 40.0

                else:

                    score -= 20.0

            # ------------------------------------------------
            # Control type
            # ------------------------------------------------

            if requested_control_type:

                if (
                    actual_control_type
                    == requested_control_type
                ):

                    score += 60.0

                else:

                    score -= 60.0

            # ------------------------------------------------
            # Rectangle
            # ------------------------------------------------

            if requested_rect is not None:

                if actual_rect is None:

                    score -= 50.0

                else:

                    rect_score = (
                        self._rectangle_similarity(
                            requested_rect,
                            actual_rect,
                        )
                    )

                    score += (
                        rect_score
                        * 60.0
                    )

            # ------------------------------------------------
            # If no identifying information was supplied,
            # reject the candidate.
            # ------------------------------------------------

            if (
                not requested_name
                and not requested_automation_id
                and not requested_control_type
                and requested_rect is None
            ):

                continue

            # ------------------------------------------------
            # Unnamed Document / control-type + rectangle
            # descriptors can now resolve correctly.
            # ------------------------------------------------

            if (
                score > best_score
            ):

                best_score = score
                best_element = element

        # ----------------------------------------------------
        # Require a meaningful match.
        # ----------------------------------------------------

        if best_element is None:
            return None

        if best_score < 20.0:
            return None

        return best_element

    # ========================================================
    # TREE HELPERS
    # ========================================================

    @staticmethod
    def _get_descendants(
        window,
    ) -> list:
        """
        Return all UIA descendants of a target window.
        """

        try:

            return list(
                window.descendants()
            )

        except Exception:

            return []

    # ========================================================
    # WINDOW RESOLUTION
    # ========================================================

    def _resolve_window(
        self,
        app: str,
    ):
        """
        Resolve the running application window.

        Uses an optional WindowsLaunch resolver first and then falls
        back to top-level UIA window title matching.
        """

        if self._window_resolver is not None:

            try:

                resolver = getattr(
                    self._window_resolver,
                    "_resolve_running_app",
                    None,
                )

                if callable(
                    resolver
                ):

                    window = resolver(
                        app
                    )

                    if window is not None:

                        return window

            except Exception:

                pass

        try:

            windows = (
                self._desktop.windows(
                    visible_only=False
                )
            )

        except Exception:

            return None

        target = (
            self._normalize_text(
                app
            )
        )

        # Exact title.
        for window in windows:

            title = (
                self._normalize_text(
                    self._safe_window_title(
                        window
                    )
                )
            )

            if title == target:
                return window

        # Containment.
        for window in windows:

            title = (
                self._normalize_text(
                    self._safe_window_title(
                        window
                    )
                )
            )

            if (
                target
                and target in title
            ):

                return window

        return None

    # ========================================================
    # SCREEN READING
    # ========================================================

    def _read_screen(
        self,
        window,
    ) -> str:
        """
        Collect distinct UIA names and values from the application.
        """

        lines: list[str] = []
        seen: set[str] = set()

        for element in (
            self._get_descendants(
                window
            )
        ):

            name = (
                self._safe_element_name(
                    element
                ).strip()
            )

            if (
                name
                and name not in seen
            ):

                lines.append(
                    name
                )

                seen.add(
                    name
                )

            value = (
                self._read_element_value(
                    element
                ).strip()
            )

            if (
                value
                and value not in seen
            ):

                lines.append(
                    value
                )

                seen.add(
                    value
                )

        return "\n".join(
            lines
        )

    def _read_element_value(
        self,
        element,
    ) -> str:
        """
        Read the most useful value from a UIA element.
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
    # KEYBOARD
    # ========================================================

    def _send_key_combo(
        self,
        keys: str,
    ) -> None:
        """
        Send a keyboard key or key combination.
        """

        normalized = keys.strip()

        if not normalized:

            raise ValueError(
                "keys cannot be empty."
            )

        parts = [
            part.strip().lower()
            for part in normalized.split("+")
            if part.strip()
        ]

        if not parts:

            raise ValueError(
                "keys cannot be empty."
            )

        normalized_parts = [
            self._normalize_key_name(
                part
            )
            for part in parts
        ]

        if len(
            normalized_parts
        ) == 1:

            pyautogui.press(
                normalized_parts[0]
            )

            return

        pyautogui.hotkey(
            *normalized_parts
        )

    @staticmethod
    def _normalize_key_name(
        key: str,
    ) -> str:
        """
        Normalize common keyboard aliases.
        """

        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "escape": "esc",
            "return": "enter",
            "windows": "win",
            "lwin": "win",
            "page_up": "pageup",
            "page_down": "pagedown",
            "pgup": "pageup",
            "pgdn": "pagedown",
            "del": "delete",
            "ins": "insert",
            "spacebar": "space",
        }

        return aliases.get(
            key,
            key,
        )

    # ========================================================
    # SCROLL
    # ========================================================

    def _scroll_element(
        self,
        element,
        direction: str,
        amount: int,
    ) -> None:
        """
        Move to the target element and perform the requested scroll.
        """

        rectangle = (
            element.rectangle()
        )

        center_x = int(
            rectangle.left
            + rectangle.width() / 2
        )

        center_y = int(
            rectangle.top
            + rectangle.height() / 2
        )

        pyautogui.moveTo(
            center_x,
            center_y,
        )

        if direction == "left":

            pyautogui.hscroll(
                -amount
            )

        elif direction == "right":

            pyautogui.hscroll(
                amount
            )

        elif direction == "up":

            pyautogui.scroll(
                amount
            )

        else:

            pyautogui.scroll(
                -amount
            )

    # ========================================================
    # WINDOW CONTROL
    # ========================================================

    def _bring_to_foreground(
        self,
        window,
    ) -> None:
        """
        Restore and focus the application window before actions execute.
        """

        try:

            if window.is_minimized():

                window.restore()

        except Exception:

            pass

        try:

            handle = int(
                window.handle
            )

            ctypes.windll.user32.ShowWindow(
                handle,
                9,
            )

            ctypes.windll.user32.SetForegroundWindow(
                handle
            )

        except Exception:

            pass

        try:

            window.set_focus()

        except Exception:

            pass

        time.sleep(
            0.10
        )

    def _close_window(
        self,
        window,
    ) -> None:
        """
        Close the target application window.

        pywinauto close() is preferred; Alt+F4 is the fallback.
        """

        try:

            window.close()

            return

        except Exception:

            pass

        try:

            window.set_focus()

        except Exception:

            pass

        pyautogui.hotkey(
            "alt",
            "f4",
        )

    # ========================================================
    # INSPECTION FALLBACK
    # ========================================================

    def _inspect_fallback(
        self,
        app: str,
    ) -> list[dict[str, Any]]:
        """
        Request a fresh UI inspection after an action/target failure.
        """

        if self._inspector is None:
            return []

        try:

            return self._inspector.call(
                app=app,
                depth=4,
                filter_types="",
            )

        except Exception:

            return []

    # ========================================================
    # RECTANGLE MATCHING
    # ========================================================

    @staticmethod
    def _normalize_rect(
        rect: Any,
    ) -> dict[str, int] | None:
        """
        Normalize a rectangle descriptor from windows_inspect.

        Accepted form:

            {"x": 200, "y": 303, "w": 1422, "h": 559}

        Also accepts a four-value tuple/list:

            (200, 303, 1422, 559)
        """

        if isinstance(
            rect,
            dict,
        ):

            try:

                return {
                    "x": int(
                        rect["x"]
                    ),
                    "y": int(
                        rect["y"]
                    ),
                    "w": int(
                        rect["w"]
                    ),
                    "h": int(
                        rect["h"]
                    ),
                }

            except (
                KeyError,
                TypeError,
                ValueError,
            ):

                return None

        if isinstance(
            rect,
            (
                tuple,
                list,
            )
        ) and len(
            rect
        ) == 4:

            try:

                return {
                    "x": int(
                        rect[0]
                    ),
                    "y": int(
                        rect[1]
                    ),
                    "w": int(
                        rect[2]
                    ),
                    "h": int(
                        rect[3]
                    ),
                }

            except (
                TypeError,
                ValueError,
            ):

                return None

        return None

    @staticmethod
    def _get_element_rect(
        element,
    ) -> dict[str, int] | None:
        """
        Get a live UIA element rectangle in the same normalized format
        returned by windows_inspect.
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

            return None

    @staticmethod
    def _rectangle_similarity(
        expected: dict[str, int],
        actual: dict[str, int],
    ) -> float:
        """
        Calculate a 0..1 similarity between two rectangles.

        Small UI movement is tolerated because the element may have
        moved slightly between inspection and action.
        """

        expected_center_x = (
            expected["x"]
            + expected["w"] / 2
        )

        expected_center_y = (
            expected["y"]
            + expected["h"] / 2
        )

        actual_center_x = (
            actual["x"]
            + actual["w"] / 2
        )

        actual_center_y = (
            actual["y"]
            + actual["h"] / 2
        )

        center_distance = (
            (
                (
                    expected_center_x
                    - actual_center_x
                )
                ** 2
            )
            + (
                (
                    expected_center_y
                    - actual_center_y
                )
                ** 2
            )
        ) ** 0.5

        width_difference = abs(
            expected["w"]
            - actual["w"]
        )

        height_difference = abs(
            expected["h"]
            - actual["h"]
        )

        # ----------------------------------------------------
        # Normalize differences.
        # ----------------------------------------------------

        center_score = max(
            0.0,
            1.0
            - (
                center_distance
                / 500.0
            ),
        )

        width_score = max(
            0.0,
            1.0
            - (
                width_difference
                / max(
                    expected["w"],
                    1,
                )
            ),
        )

        height_score = max(
            0.0,
            1.0
            - (
                height_difference
                / max(
                    expected["h"],
                    1,
                )
            ),
        )

        return (
            center_score * 0.60
            + width_score * 0.20
            + height_score * 0.20
        )

    # ========================================================
    # SAFE VALUES
    # ========================================================

    @staticmethod
    def _safe_element_name(
        element,
    ) -> str:
        """
        Safely retrieve a UIA element name.
        """

        try:

            return str(
                element.window_text()
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _safe_automation_id(
        element,
    ) -> str:
        """
        Safely retrieve a UIA AutomationId.
        """

        try:

            return str(
                element.element_info.automation_id
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _safe_control_type(
        element,
    ) -> str:
        """
        Safely retrieve a UIA control type.
        """

        try:

            return str(
                element.element_info.control_type
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _safe_window_title(
        window,
    ) -> str:
        """
        Safely retrieve a window title.
        """

        try:

            return str(
                window.window_text()
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _optional_normalized(
        value: Any,
    ) -> str:
        """
        Normalize an optional target field.

        Empty strings and None become an empty string.
        """

        if value is None:
            return ""

        if not isinstance(
            value,
            str,
        ):

            value = str(
                value
            )

        return WindowsDo._normalize_text(
            value
        )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize text for case-insensitive UI matching.
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

    # ========================================================
    # RESULT
    # ========================================================

    @staticmethod
    def _make_result(
        action: dict[str, Any],
        target: Any,
        status: str,
        detail: str,
        value: Any = None,
    ) -> dict[str, Any]:
        """
        Create the standard JSON-safe action result.
        """

        if target is None:

            safe_target = None

        else:

            try:

                safe_target = str(
                    target
                )

            except Exception:

                safe_target = ""

        if value is None:

            safe_value = None

        else:

            try:

                safe_value = str(
                    value
                )

            except Exception:

                safe_value = ""

        return {
            "action": str(
                action.get(
                    "action",
                    "",
                )
            ),
            "target": safe_target,
            "status": str(
                status
            ),
            "detail": str(
                detail
            ),
            "value": safe_value,
        }

    # ========================================================
    # SCREENSHOT
    # ========================================================

    @staticmethod
    def _take_screenshot() -> str:
        """
        Capture the desktop into a temporary PNG file.
        """

        image = ImageGrab.grab()

        path = tempfile.mktemp(
            suffix=".png"
        )

        image.save(
            path
        )

        return path