# ============================================================
# windows_agent/tools/tool_manager.py
# ============================================================

from __future__ import annotations

from typing import Any, Callable


ToolCallable = Callable[..., Any]


class ToolManager:
    """
    Central registry and executor for all LLM-facing tools.

    High-level tools:

        windows_launch
        windows_inspect
        windows_do
        list_installed_apps
        file_op

        get_system_info
        get_running_applications
        get_processes
        get_system_resources

        screen_diagnose
        get_important_frames
        user_memory
    """

    def __init__(
        self,
        windows_launch=None,
        windows_inspect=None,
        windows_do=None,
        list_installed_apps=None,
        file_op=None,
        system_tools=None,
        screen_diagnose=None,
        get_important_frames=None,
        user_memory=None,
    ) -> None:
        """
        Register the supplied tool implementations.

        Tool objects may expose:
            call()
            __call__()

        Existing specialized classes such as ScreenDiagnoseTool and
        UserMemory are registered through their actual public methods.
        """

        self._tools: dict[
            str,
            ToolCallable,
        ] = {}

        # ====================================================
        # WINDOWS
        # ====================================================

        self._register_object(
            "windows_launch",
            windows_launch,
        )

        self._register_object(
            "windows_inspect",
            windows_inspect,
        )

        self._register_object(
            "windows_do",
            windows_do,
        )

        self._register_object(
            "list_installed_apps",
            list_installed_apps,
        )

        # ====================================================
        # FILESYSTEM
        # ====================================================

        self._register_object(
            "file_op",
            file_op,
        )

        # ====================================================
        # SYSTEM
        # ====================================================

        if system_tools is not None:

            self._register_method(
                "get_system_info",
                system_tools,
                "get_system_info",
            )

            self._register_method(
                "get_running_applications",
                system_tools,
                "get_running_applications",
            )

            self._register_method(
                "get_processes",
                system_tools,
                "get_processes",
            )

            self._register_method(
                "get_system_resources",
                system_tools,
                "get_system_resources",
            )

        # ====================================================
        # SCREEN DIAGNOSIS
        # ====================================================

        if screen_diagnose is not None:

            self._register_method(
                "screen_diagnose",
                screen_diagnose,
                "diagnose",
            )

        # ====================================================
        # IMPORTANT FRAMES
        # ====================================================

        self._register_object(
            "get_important_frames",
            get_important_frames,
        )

        # ====================================================
        # MEMORY
        # ====================================================

        if user_memory is not None:

            self._register_object(
            "user_memory",
             user_memory,
               )

    # ========================================================
    # REGISTRATION
    # ========================================================

    def _register_object(
        self,
        name: str,
        tool: Any,
    ) -> None:
        """
        Register an object exposing either call() or __call__().
        """

        if tool is None:
            return

        call_method = getattr(
            tool,
            "call",
            None,
        )

        if callable(
            call_method
        ):

            self._register(
                name,
                call_method,
            )

            return

        if callable(
            tool
        ):

            self._register(
                name,
                tool,
            )

            return

        raise TypeError(
            f"Tool '{name}' must expose "
            "call() or be directly callable."
        )

    def _register_method(
        self,
        name: str,
        owner: Any,
        method_name: str,
    ) -> None:
        """
        Register a specific public method from a tool object.
        """

        method = getattr(
            owner,
            method_name,
            None,
        )

        if not callable(
            method
        ):

            raise AttributeError(
                f"Tool '{name}' requires callable "
                f"method '{method_name}'."
            )

        self._register(
            name,
            method,
        )

    def _register(
        self,
        name: str,
        function: ToolCallable,
    ) -> None:
        """
        Add one executable callable to the registry.
        """

        if name in self._tools:

            raise ValueError(
                f"Tool already registered: {name}"
            )

        self._tools[
            name
        ] = function

    # ========================================================
    # PUBLIC REGISTRY
    # ========================================================

    def list_tools(
        self,
    ) -> list[str]:
        """
        Return all registered tool names.
        """

        return list(
            self._tools.keys()
        )

    def has_tool(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a tool is registered.
        """

        if not isinstance(
            name,
            str,
        ):
            return False

        return (
            name.strip()
            in self._tools
        )

    def get_tool(
        self,
        name: str,
    ) -> ToolCallable:
        """
        Retrieve one registered tool callable.
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
            raise ValueError(
                "name cannot be empty."
            )

        try:

            return self._tools[
                name
            ]

        except KeyError as exc:

            raise KeyError(
                f"Unknown tool: {name}"
            ) from exc

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        tool_name: str,
        **parameters: Any,
    ) -> Any:
        """
        Execute one registered tool and normalize unexpected failures.
        """

        if not isinstance(
            tool_name,
            str,
        ):
            raise TypeError(
                "tool_name must be a string."
            )

        tool_name = tool_name.strip()

        if not tool_name:
            raise ValueError(
                "tool_name cannot be empty."
            )

        function = self.get_tool(
            tool_name
        )

        try:

            return function(
                **parameters
            )

        except Exception as exc:

            return {
                "success": False,
                "tool": tool_name,
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # DIAGNOSTICS
    # ========================================================

    def registration_report(
        self,
    ) -> dict[str, Any]:
        """
        Return the currently registered tool names and count.
        """

        tools = self.list_tools()

        return {
            "success": True,
            "registered_tools": tools,
            "count": len(
                tools
            ),
        }

    def clear(
        self,
    ) -> None:
        """
        Remove all currently registered tools.
        """

        self._tools.clear()