# ============================================================
# windows_agent/tools/list_installed_apps.py
# ============================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ListInstalledApps:
    """
    Return the pre-built Windows application index.

    This follows Airi's tool architecture:

        list_installed_apps
            ↓
        installed_apps.json
            ↓
        application records
            ↓
        Qwen can choose a valid application name
            ↓
        windows_launch(app)

    This tool does not launch applications, inspect UIA, or resolve
    executable paths. It only reads the application index.
    """

    def __init__(
        self,
        installed_apps_path: str | None = None,
    ) -> None:
        """
        Initialize the installed-application index reader.

        When no path is supplied, installed_apps.json is expected next
        to this Python file.
        """

        if installed_apps_path is None:

            installed_apps_path = str(
                Path(__file__).with_name(
                    "installed_apps.json"
                )
            )

        self._path = Path(
            installed_apps_path
        )

    # ========================================================
    # PUBLIC TOOL
    # ========================================================

    def call(
        self,
    ) -> list[dict[str, Any]] | dict[str, str]:
        """
        Load and return all installed applications.

        Returns either:

            list[dict[str, Any]]

        or:

            {"error": "..."}
        """

        try:

            with self._path.open(
                "r",
                encoding="utf-8-sig",
            ) as file:

                apps = json.load(
                    file
                )

        except FileNotFoundError:

            return {
                "error": (
                    "installed_apps.json not found: "
                    f"{self._path}"
                )
            }

        except json.JSONDecodeError as exc:

            return {
                "error": (
                    "installed_apps.json contains "
                    "invalid JSON: "
                    f"{exc}"
                )
            }

        except OSError as exc:

            return {
                "error": (
                    "Could not read installed_apps.json: "
                    f"{exc}"
                )
            }

        if not isinstance(
            apps,
            list,
        ):

            return {
                "error": (
                    "installed_apps.json must contain "
                    "a JSON array."
                )
            }

        return apps