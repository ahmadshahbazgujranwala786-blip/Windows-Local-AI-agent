from __future__ import annotations

import platform
import socket
from datetime import datetime
from typing import Any

import psutil


class SystemTools:

    def get_system_info(
        self,
    ) -> dict[str, Any]:

        try:

            boot_timestamp = psutil.boot_time()

            return {
                "success": True,
                "tool": "get_system_info",
                "os": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "hostname": socket.gethostname(),
                "processor": platform.processor(),
                "logical_cpu_count": psutil.cpu_count(
                    logical=True
                ),
                "physical_cpu_count": psutil.cpu_count(
                    logical=False
                ),
                "python_version": platform.python_version(),
                "boot_time": datetime.fromtimestamp(
                    boot_timestamp
                ).isoformat(),
            }

        except Exception as exc:

            return {
                "success": False,
                "tool": "get_system_info",
                "error": type(exc).__name__,
                "message": str(exc),
            }

    def get_running_applications(
        self,
    ) -> dict[str, Any]:
        
        try:

            from pywinauto import Desktop

            desktop = Desktop(
                backend="uia"
            )

            windows: list[dict[str, Any]] = []

            for window in desktop.windows():

                try:

                    if not window.is_visible():
                        continue

                    title = (
                        window.window_text()
                        .strip()
                    )

                    if not title:
                        continue

                    rectangle = (
                        window.rectangle()
                    )

                    windows.append(
                        {
                            "title": title,
                            "handle": window.handle,
                            "bounding_rectangle": (
                                rectangle.left,
                                rectangle.top,
                                rectangle.right,
                                rectangle.bottom,
                            ),
                        }
                    )

                except Exception:
                    continue

            return {
                "success": True,
                "tool": "get_running_applications",
                "applications": windows,
                "count": len(windows),
            }

        except Exception as exc:

            return {
                "success": False,
                "tool": "get_running_applications",
                "error": type(exc).__name__,
                "message": str(exc),
            }

    def get_processes(
        self,
    ) -> dict[str, Any]:
        
        try:

            processes: list[
                dict[str, Any]
            ] = []

            for process in psutil.process_iter(
                [
                    "pid",
                    "name",
                    "exe",
                    "status",
                ]
            ):

                try:

                    info = process.info

                    processes.append(
                        {
                            "pid": info.get(
                                "pid"
                            ),
                            "name": info.get(
                                "name"
                            ),
                            "exe": info.get(
                                "exe"
                            ),
                            "status": info.get(
                                "status"
                            ),
                        }
                    )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):

                    continue

            processes.sort(
                key=lambda item: (
                    (
                        item.get("name")
                        or ""
                    ).casefold()
                )
            )

            return {
                "success": True,
                "tool": "get_processes",
                "processes": processes,
                "count": len(processes),
            }

        except Exception as exc:

            return {
                "success": False,
                "tool": "get_processes",
                "error": type(exc).__name__,
                "message": str(exc),
            }

    def get_system_resources(
        self,
    ) -> dict[str, Any]:

        try:

            memory = (
                psutil.virtual_memory()
            )

            swap = (
                psutil.swap_memory()
            )

            cpu_percent = (
                psutil.cpu_percent(
                    interval=0.2
                )
            )

            cpu_frequency = (
                psutil.cpu_freq()
            )

            disks: list[
                dict[str, Any]
            ] = []

            for partition in psutil.disk_partitions(
                all=False
            ):

                try:

                    usage = (
                        psutil.disk_usage(
                            partition.mountpoint
                        )
                    )

                    disks.append(
                        {
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "filesystem": partition.fstype,
                            "total_bytes": usage.total,
                            "used_bytes": usage.used,
                            "free_bytes": usage.free,
                            "percent": usage.percent,
                        }
                    )

                except (
                    OSError,
                    PermissionError,
                ):

                    continue

            result: dict[str, Any] = {
                "success": True,
                "tool": "get_system_resources",
                "cpu": {
                    "usage_percent": cpu_percent,
                    "logical_cores": psutil.cpu_count(
                        logical=True
                    ),
                    "physical_cores": psutil.cpu_count(
                        logical=False
                    ),
                },
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "free_bytes": memory.free,
                    "percent": memory.percent,
                },
                "swap": {
                    "total_bytes": swap.total,
                    "used_bytes": swap.used,
                    "free_bytes": swap.free,
                    "percent": swap.percent,
                },
                "disks": disks,
            }

            if cpu_frequency is not None:

                result["cpu"][
                    "current_mhz"
                ] = cpu_frequency.current

                result["cpu"][
                    "min_mhz"
                ] = cpu_frequency.min

                result["cpu"][
                    "max_mhz"
                ] = cpu_frequency.max

            return result

        except Exception as exc:

            return {
                "success": False,
                "tool": "get_system_resources",
                "error": type(exc).__name__,
                "message": str(exc),
            }