# ============================================================
# windows_agent/tools/windows_launch.py
# ============================================================

from __future__ import annotations

import ctypes
import difflib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import time
from typing import Any

import psutil
from pywinauto import Desktop


class WindowsLaunch:
    """
    Windows application launcher.

    Responsibilities:

        1. Resolve a human-readable application name.
        2. Detect whether the application is already running.
        3. Launch the application when necessary.
        4. Restore/focus an already-running application.
        5. Verify the resulting application window.

    Application discovery uses Windows' Applications shell through UIA.
    """

    _ACTIONABLE_CONTROL_TYPES = {
        "ListItem",
        "Button",
        "MenuItem",
        "TreeItem",
        "Hyperlink",
        "DataItem",
        "Custom",
    }

    _IGNORED_CONTROL_TYPES = {
        "Text",
        "Static",
        "Pane",
        "Group",
        "TitleBar",
        "Header",
        "HeaderItem",
    }

    # --------------------------------------------------------
    # Resolver behavior
    # --------------------------------------------------------

    _MAX_APPLICATION_CANDIDATES = 3
    _MIN_APPLICATION_CONFIDENCE = 0.50

    _BUILTIN_FALLBACKS = {
        "explorer": {
            "exe": "explorer.exe",
            "title_hint": "",
        },
        "file explorer": {
            "exe": "explorer.exe",
            "title_hint": "File Explorer",
        },
        "windows explorer": {
            "exe": "explorer.exe",
            "title_hint": "File Explorer",
        },
        "cmd": {
            "exe": "cmd.exe",
            "title_hint": "",
        },
        "command prompt": {
            "exe": "cmd.exe",
            "title_hint": "",
        },
        "notepad": {
            "exe": "notepad.exe",
            "title_hint": "Notepad",
        },
        "settings": {
            "exe": "SystemSettings.exe",
            "title_hint": "Settings",
        },
    }

    def __init__(
        self,
        backend: str = "uia",
        installed_apps_path: str | None = None,
    ) -> None:
        """
        Initialize the Windows application launcher.
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

        if installed_apps_path is None:

            installed_apps_path = str(
                pathlib.Path(__file__).with_name(
                    "installed_apps.json"
                )
            )

        self._installed_apps_path = pathlib.Path(
            installed_apps_path
        )

        self._installed_apps: dict[
            str,
            dict[str, str],
        ] = {}

        self._load_installed_apps()

    # ========================================================
    # PUBLIC TOOL
    # ========================================================

    def call(
        self,
        name: str,
        args: str = "",
    ) -> dict[str, Any]:
        """
        Launch a Windows application by human-readable name.

        If the application is already running, restore it, bring it
        to the foreground, and focus it.

        Otherwise resolve and launch the application, then verify
        the resulting top-level window.
        """

        if not isinstance(
            name,
            str,
        ):
            raise TypeError(
                "name must be a string."
            )

        name = name.strip()

        if not name:
            return {
                "status": "error",
                "window_title": "",
                "detail": "name is required.",
            }

        if not isinstance(
            args,
            str,
        ):
            raise TypeError(
                "args must be a string."
            )

        args = args.strip()

        try:

            # ==================================================
            # 1. CHECK REAL RUNNING APPLICATION
            # ==================================================

            running_window = (
                self._resolve_running_app(
                    name
                )
            )

            if running_window is not None:

                self._activate_window(
                    running_window
                )

                return {
                    "status": "already_running",
                    "window_title": (
                        self._safe_window_title(
                            running_window
                        )
                    ),
                    "detail": (
                        "Application was already "
                        "running and was brought "
                        "to the foreground."
                    ),
                }

            # ==================================================
            # 2. RESOLVE APPLICATION
            # ==================================================

            candidate = (
                self._resolve_application(
                    name
                )
            )

            # ==================================================
            # 3. LAUNCH UIA APPLICATION ENTRY
            # ==================================================

            if candidate is not None:

                launched = (
                    self._launch_uia_candidate(
                        candidate=candidate,
                        args=args,
                    )
                )

                if launched:

                    window = (
                        self._wait_for_window(
                            app=name,
                            title_hint=(
                                candidate.get(
                                    "name",
                                    "",
                                )
                            ),
                            timeout=5.0,
                        )
                    )

                    if window is not None:

                        self._activate_window(
                            window
                        )

                        return {
                            "status": "launched",
                            "window_title": (
                                self._safe_window_title(
                                    window
                                )
                            ),
                            "resolved_name": (
                                candidate["name"]
                            ),
                            "confidence": (
                                candidate["confidence"]
                            ),
                            "detail": "launched",
                        }

            # ==================================================
            # 4. CLASSIC EXECUTABLE FALLBACK
            # ==================================================

            record = (
                self._resolve_installed_record(
                    name
                )
            )

            if record is None:

                return {
                    "status": "error",
                    "window_title": "",
                    "detail": (
                        f"Application not found: "
                        f"{name}"
                    ),
                }

            executable = (
                self._resolve_executable(
                    record.get(
                        "exe",
                        "",
                    )
                )
            )

            if executable is None:

                return {
                    "status": "error",
                    "window_title": "",
                    "detail": (
                        "Application was found, but "
                        "its executable could not be resolved."
                    ),
                }

            process = (
                self._launch_executable(
                    executable=executable,
                    args=args,
                )
            )

            window = (
                self._wait_for_window(
                    app=name,
                    title_hint=record.get(
                        "title_hint",
                        "",
                    ),
                    timeout=5.0,
                )
            )

            if window is None:

                return {
                    "status": "error",
                    "window_title": "",
                    "detail": (
                        "Process started, but its "
                        "application window could not "
                        "be verified."
                    ),
                    "process_id": process.pid,
                }

            self._activate_window(
                window
            )

            return {
                "status": "launched",
                "window_title": (
                    self._safe_window_title(
                        window
                    )
                ),
                "detail": "launched",
                "process_id": process.pid,
                "executable": executable,
            }

        except Exception as exc:

            return {
                "status": "error",
                "window_title": "",
                "detail": str(exc),
            }

    # ========================================================
    # APPLICATION RESOLVER
    # ========================================================

    def _resolve_application(
        self,
        app: str,
    ) -> dict[str, Any] | None:
        """
        Resolve a human-readable application name through AppsFolder UIA.

        The resolver:

            1. Discovers candidate names.
            2. Ranks all candidates.
            3. Keeps only the top three.
            4. Checks them in descending confidence order.
            5. Returns the first candidate with confidence >= 0.50.

        Exact matches always receive confidence 1.0.
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
            return None

        target = (
            self._normalize_name(
                app
            )
        )

        if not target:
            return None

        target_tokens = set(
            target.split()
        )

        apps_folder = (
            self._open_apps_folder()
        )

        if apps_folder is None:
            return None

        try:

            elements = (
                apps_folder.descendants()
            )

        except Exception:

            return None

        candidates: list[
            dict[str, Any]
        ] = []

        seen: set[
            tuple[str, str]
        ] = set()

        # ----------------------------------------------------
        # Collect candidates.
        # ----------------------------------------------------

        for element in elements:

            try:

                element_name = str(
                    element.window_text()
                    or ""
                ).strip()

                control_type = str(
                    element.element_info.control_type
                    or ""
                )

            except Exception:

                continue

            if not element_name:
                continue

            normalized_name = (
                self._normalize_name(
                    element_name
                )
            )

            if not normalized_name:
                continue

            identity = (
                normalized_name,
                control_type,
            )

            if identity in seen:
                continue

            seen.add(
                identity
            )

            score = (
                self._score_application_name(
                    candidate=normalized_name,
                    target=target,
                    target_tokens=target_tokens,
                    control_type=control_type,
                )
            )

            candidates.append(
                {
                    "name": element_name,
                    "normalized_name": normalized_name,
                    "control_type": control_type,
                    "confidence": round(
                        score,
                        3,
                    ),
                    "element": element,
                }
            )

        if not candidates:
            return None

        # ----------------------------------------------------
        # Rank highest confidence first.
        #
        # Control type is only a secondary tie-breaker.
        # ----------------------------------------------------

        candidates.sort(
            key=lambda candidate: (
                candidate["confidence"],
                self._control_priority(
                    candidate[
                        "control_type"
                    ]
                ),
            ),
            reverse=True,
        )

        # ----------------------------------------------------
        # Keep ONLY top 3.
        # ----------------------------------------------------

        top_candidates = candidates[
            : self._MAX_APPLICATION_CANDIDATES
        ]

        # ----------------------------------------------------
        # Check candidates in ranked order.
        # ----------------------------------------------------

        for candidate in top_candidates:

            if (
                candidate["confidence"]
                >= self._MIN_APPLICATION_CONFIDENCE
            ):

                return candidate

        # ----------------------------------------------------
        # None of the top 3 candidates was strong enough.
        # ----------------------------------------------------

        return None

    def _score_application_name(
        self,
        candidate: str,
        target: str,
        target_tokens: set[str],
        control_type: str,
    ) -> float:
        """
        Score one Windows-exposed application name.

        Exact matches are independent of UIA control type.
        """

        # ----------------------------------------------------
        # Exact name.
        # ----------------------------------------------------

        if candidate == target:

            return 1.0

        # ----------------------------------------------------
        # Strong containment.
        # ----------------------------------------------------

        if (
            target
            and target in candidate
        ):

            score = 0.95

        elif (
            candidate
            and candidate in target
            and len(candidate) >= 3
        ):

            score = 0.92

        else:

            candidate_tokens = set(
                candidate.split()
            )

            overlap = (
                target_tokens
                & candidate_tokens
            )

            token_score = 0.0

            if overlap:

                token_score = (
                    len(overlap)
                    / len(target_tokens)
                ) * 0.85

            fuzzy_score = (
                difflib.SequenceMatcher(
                    None,
                    target,
                    candidate,
                ).ratio()
                * 0.80
            )

            score = max(
                token_score,
                fuzzy_score,
            )

        # ----------------------------------------------------
        # Control type is only a secondary signal.
        # Never penalize exact matches.
        # ----------------------------------------------------

        if (
            candidate != target
            and control_type in (
                self._IGNORED_CONTROL_TYPES
            )
        ):

            score *= 0.75

        elif (
            candidate != target
            and control_type in (
                self._ACTIONABLE_CONTROL_TYPES
            )
        ):

            score = min(
                score + 0.05,
                1.0,
            )

        return score

    # ========================================================
    # APPSFOLDER
    # ========================================================

    def _open_apps_folder(
        self,
    ):
        """
        Reuse an existing AppsFolder Explorer window when possible.

        Otherwise open shell:AppsFolder and identify the Explorer
        window representing the Applications virtual folder.
        """

        try:

            desktop = Desktop(
                backend=self.backend
            )

            existing = (
                self._find_apps_folder_window(
                    desktop
                )
            )

            if existing is not None:

                return existing

            before = (
                self._get_explorer_windows(
                    desktop
                )
            )

            before_handles = {
                handle
                for handle in (
                    self._safe_window_handle(
                        window
                    )
                    for window in before
                )
                if handle is not None
            }

            subprocess.Popen(
                [
                    "explorer.exe",
                    "shell:AppsFolder",
                ],
                shell=False,
            )

            deadline = (
                time.monotonic()
                + 5.0
            )

            while (
                time.monotonic()
                < deadline
            ):

                current = (
                    self._get_explorer_windows(
                        desktop
                    )
                )

                for window in current:

                    handle = (
                        self._safe_window_handle(
                            window
                        )
                    )

                    if (
                        handle is None
                        or handle in before_handles
                    ):
                        continue

                    if (
                        self._looks_like_apps_folder(
                            window
                        )
                    ):

                        return window

                existing = (
                    self._find_apps_folder_window(
                        desktop
                    )
                )

                if existing is not None:

                    return existing

                time.sleep(
                    0.10
                )

            return None

        except Exception:

            return None

    def _find_apps_folder_window(
        self,
        desktop,
    ):
        """
        Find an existing Explorer window representing AppsFolder.
        """

        for window in (
            self._get_explorer_windows(
                desktop
            )
        ):

            if (
                self._looks_like_apps_folder(
                    window
                )
            ):

                return window

        return None

    def _get_explorer_windows(
        self,
        desktop,
    ) -> list:
        """
        Return top-level explorer.exe windows.
        """

        windows: list = []

        try:

            all_windows = (
                desktop.windows(
                    visible_only=False
                )
            )

        except Exception:

            return windows

        for window in all_windows:

            try:

                process_id = (
                    window.process_id()
                )

                process = (
                    psutil.Process(
                        process_id
                    )
                )

                if (
                    process.name()
                    .casefold()
                    == "explorer.exe"
                ):

                    windows.append(
                        window
                    )

            except Exception:

                continue

        return windows

    def _looks_like_apps_folder(
        self,
        window,
    ) -> bool:
        """
        Determine whether an Explorer window represents AppsFolder.
        """

        try:

            title = (
                self._normalize_name(
                    window.window_text()
                    or ""
                )
            )

        except Exception:

            return False

        if title in {
            "applications",
            "apps",
            "appsfolder",
        }:

            return True

        try:

            descendants = (
                window.descendants()
            )

        except Exception:

            return False

        actionable_count = 0

        for element in descendants:

            try:

                name = str(
                    element.window_text()
                    or ""
                ).strip()

                control_type = str(
                    element.element_info.control_type
                    or ""
                )

            except Exception:

                continue

            if not name:
                continue

            if control_type not in (
                self._ACTIONABLE_CONTROL_TYPES
            ):

                continue

            actionable_count += 1

            if actionable_count >= 5:

                return True

        return False

    # ========================================================
    # UIA APPLICATION LAUNCH
    # ========================================================

    def _launch_uia_candidate(
        self,
        candidate: dict[str, Any],
        args: str,
    ) -> bool:
        """
        Activate exactly one resolved AppsFolder application entry.

        UIA InvokePattern is preferred. A single click is used only
        as a fallback.
        """

        element = candidate.get(
            "element"
        )

        if element is None:
            return False

        try:

            invoke = getattr(
                element,
                "invoke",
                None,
            )

            if callable(
                invoke
            ):

                invoke()

                return True

        except Exception:

            pass

        try:

            element.set_focus()

        except Exception:

            pass

        try:

            element.click_input()

            return True

        except Exception:

            return False

    # ========================================================
    # RUNNING APPLICATION RESOLUTION
    # ========================================================

    def _resolve_running_app(
        self,
        app: str,
    ):
        """
        Determine whether an application is genuinely running.

        AppsFolder is never queried here.
        """

        try:

            desktop = Desktop(
                backend=self.backend
            )

            windows = (
                desktop.windows(
                    visible_only=False
                )
            )

        except Exception:

            return None

        if not windows:
            return None

        # ----------------------------------------------------
        # Exact top-level title.
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

        # ----------------------------------------------------
        # Classic installed application record.
        # ----------------------------------------------------

        record = (
            self._resolve_installed_record(
                app
            )
        )

        if record is not None:

            title_hint = (
                record.get(
                    "title_hint",
                    "",
                ).strip()
            )

            executable = (
                record.get(
                    "exe",
                    "",
                ).strip()
            )

            if title_hint:

                normalized_hint = (
                    self._normalize_name(
                        title_hint
                    )
                )

                for window in windows:

                    title = (
                        self._normalize_name(
                            self._safe_window_title(
                                window
                            )
                        )
                    )

                    if (
                        title == normalized_hint
                        or normalized_hint in title
                    ):

                        return window

            if executable:

                executable_name = (
                    pathlib.Path(
                        executable
                    ).name.casefold()
                )

                matching_pids: set[
                    int
                ] = set()

                for process in (
                    psutil.process_iter(
                        [
                            "pid",
                            "name",
                        ]
                    )
                ):

                    try:

                        process_name = (
                            process.info.get(
                                "name"
                            )
                            or ""
                        ).casefold()

                        if (
                            process_name
                            == executable_name
                        ):

                            matching_pids.add(
                                int(
                                    process.info[
                                        "pid"
                                    ]
                                )
                            )

                    except Exception:

                        continue

                if matching_pids:

                    for window in windows:

                        try:

                            if (
                                window.process_id()
                                in matching_pids
                            ):

                                return window

                        except Exception:

                            continue

        # ----------------------------------------------------
        # Conservative fuzzy top-level title.
        # ----------------------------------------------------

        target = (
            self._normalize_name(
                app
            )
        )

        if not target:
            return None

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
                self._normalize_name(
                    title
                )
            )

            ratio = (
                difflib.SequenceMatcher(
                    None,
                    target,
                    normalized_title,
                ).ratio()
            )

            if (
                ratio >= 0.85
                and ratio > best_ratio
            ):

                best_ratio = ratio
                best_window = window

        return best_window

    # ========================================================
    # WINDOW ACTIVATION
    # ========================================================

    def _activate_window(
        self,
        window,
    ) -> None:
        """
        Restore, foreground, and focus a running application window.
        """

        try:

            if window.is_minimized():

                window.restore()

        except Exception:

            pass

        try:

            handle = (
                self._safe_window_handle(
                    window
                )
            )

            if handle:

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

    # ========================================================
    # WINDOW VERIFICATION
    # ========================================================

    def _wait_for_window(
        self,
        app: str,
        title_hint: str = "",
        timeout: float = 5.0,
    ):
        """
        Wait for a real top-level application window to appear.
        """

        deadline = (
            time.monotonic()
            + timeout
        )

        while (
            time.monotonic()
            < deadline
        ):

            window = (
                self._resolve_running_app(
                    app
                )
            )

            if window is not None:

                return window

            if title_hint:

                window = (
                    self._resolve_running_app(
                        title_hint
                    )
                )

                if window is not None:

                    return window

            time.sleep(
                0.10
            )

        return None

    # ========================================================
    # CLASSIC APPLICATION INDEX
    # ========================================================

    def _load_installed_apps(
        self,
    ) -> None:
        """
        Load the optional classic executable application index.
        """

        loaded: dict[
            str,
            dict[str, str],
        ] = {}

        if self._installed_apps_path.exists():

            try:

                raw = (
                    self._installed_apps_path.read_text(
                        encoding="utf-8-sig"
                    )
                )

                entries = json.loads(
                    raw
                )

                if isinstance(
                    entries,
                    list,
                ):

                    for entry in entries:

                        if not isinstance(
                            entry,
                            dict,
                        ):
                            continue

                        name = str(
                            entry.get(
                                "name",
                                "",
                            )
                        ).strip()

                        executable = str(
                            entry.get(
                                "exe",
                                "",
                            )
                        ).strip()

                        title_hint = str(
                            entry.get(
                                "title_hint",
                                "",
                            )
                        ).strip()

                        if (
                            not name
                            or not executable
                        ):
                            continue

                        record = {
                            "name": name,
                            "exe": executable,
                            "title_hint": title_hint,
                        }

                        name_key = (
                            self._normalize_name(
                                name
                            )
                        )

                        if name_key:

                            loaded[
                                name_key
                            ] = record

                        stem_key = (
                            self._normalize_name(
                                pathlib.Path(
                                    executable
                                ).stem
                            )
                        )

                        if (
                            stem_key
                            and stem_key not in loaded
                        ):

                            loaded[
                                stem_key
                            ] = record

            except Exception:

                pass

        # ----------------------------------------------------
        # Built-in classic executable fallbacks.
        # ----------------------------------------------------

        for name, fallback in (
            self._BUILTIN_FALLBACKS.items()
        ):

            key = (
                self._normalize_name(
                    name
                )
            )

            if key not in loaded:

                loaded[key] = {
                    "name": name,
                    "exe": fallback[
                        "exe"
                    ],
                    "title_hint": fallback[
                        "title_hint"
                    ],
                }

        self._installed_apps = loaded

    def _resolve_installed_record(
        self,
        app: str,
    ) -> dict[str, str] | None:
        """
        Resolve an application from the classic executable index.

        AppsFolder is not queried here.
        """

        normalized = (
            self._normalize_name(
                app
            )
        )

        if not normalized:
            return None

        exact = (
            self._installed_apps.get(
                normalized
            )
        )

        if exact is not None:

            return exact

        best_ratio = 0.0
        best_record = None

        for key, record in (
            self._installed_apps.items()
        ):

            ratio = (
                difflib.SequenceMatcher(
                    None,
                    normalized,
                    key,
                ).ratio()
            )

            if (
                ratio >= 0.80
                and ratio > best_ratio
            ):

                best_ratio = ratio
                best_record = record

        return best_record

    # ========================================================
    # EXECUTABLE
    # ========================================================

    @staticmethod
    def _resolve_executable(
        executable: str,
    ) -> str | None:
        """
        Resolve an executable name or path.
        """

        if not executable:
            return None

        executable = (
            os.path.expandvars(
                os.path.expanduser(
                    executable.strip(
                        '"'
                    )
                )
            )
        )

        path = pathlib.Path(
            executable
        )

        if path.is_absolute():

            if path.is_file():

                return str(
                    path.resolve()
                )

            return None

        return shutil.which(
            executable
        )

    @staticmethod
    def _launch_executable(
        executable: str,
        args: str,
    ) -> subprocess.Popen:
        """
        Launch a classic executable directly.
        """

        command_executable = (
            os.path.expandvars(
                os.path.expanduser(
                    executable.strip(
                        '"'
                    )
                )
            )
        )

        path = pathlib.Path(
            command_executable
        )

        if path.is_absolute():

            if not path.is_file():

                raise FileNotFoundError(
                    f"Executable does not exist: "
                    f"{path}"
                )

            command_executable = str(
                path.resolve()
            )

        else:

            resolved = shutil.which(
                command_executable
            )

            if resolved is None:

                raise FileNotFoundError(
                    f"Executable could not be found: "
                    f"{command_executable}"
                )

            command_executable = resolved

        command = [
            command_executable
        ]

        if args:

            try:

                command.extend(
                    shlex.split(
                        args,
                        posix=False,
                    )
                )

            except ValueError:

                command.extend(
                    args.split()
                )

        return subprocess.Popen(
            command,
            shell=False,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _control_priority(
        control_type: str,
    ) -> int:
        """
        Return the secondary ranking priority of a UIA control type.
        """

        priorities = {
            "ListItem": 6,
            "Button": 5,
            "MenuItem": 5,
            "TreeItem": 4,
            "Hyperlink": 4,
            "DataItem": 4,
            "Custom": 3,
            "Text": 2,
            "Static": 2,
            "Pane": 0,
            "Group": 0,
        }

        return priorities.get(
            control_type,
            1,
        )

    @staticmethod
    def _safe_window_handle(
        window,
    ) -> int | None:
        """
        Safely retrieve a native window handle.
        """

        try:

            return int(
                window.handle
            )

        except Exception:

            return None

    @staticmethod
    def _safe_window_title(
        window,
    ) -> str:
        """
        Safely retrieve a top-level window title.
        """

        try:

            return str(
                window.window_text()
                or ""
            )

        except Exception:

            return ""

    @staticmethod
    def _normalize_name(
        value: str,
    ) -> str:
        """
        Normalize text for case-insensitive application matching.
        """

        value = value.casefold()

        value = re.sub(
            r"[^a-z0-9]+",
            " ",
            value,
        )

        return " ".join(
            value.split()
        )