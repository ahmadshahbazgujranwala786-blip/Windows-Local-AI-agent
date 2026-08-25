from __future__ import annotations

from typing import Any


TOOL_DEFINITIONS: list[dict[str, Any]] = [

    # ========================================================
    # WINDOWS
    # ========================================================

    {
        "name": "windows_launch",
        "description": (
            "Launch a Windows application by name. "
            "Use this to open an application. "
            "Do not invent executable paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Human-readable application name."
                    ),
                },
                "args": {
                    "type": "string",
                    "description": (
                        "Optional command-line arguments."
                    ),
                },
            },
            "required": [
                "name",
            ],
        },
    },

    {
        "name": "windows_inspect",
        "description": (
            "Inspect the UI structure of a running Windows "
            "application and return relevant UI elements."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": (
                        "Running application name."
                    ),
                },
                "depth": {
                    "type": "integer",
                    "description": (
                        "Maximum UI tree depth. Default is 4."
                    ),
                },
                "filter_types": {
                    "type": "string",
                    "description": (
                        "Optional comma-separated control types."
                    ),
                },
            },
            "required": [
                "app",
            ],
        },
    },

    {
        "name": "windows_do",
        "description": (
            "Perform UI actions on a running Windows application. "
            "Supports clicking, typing, keyboard actions, scrolling, "
            "focus, reading, waiting, screenshots, and closing apps."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": (
                        "Running application name."
                    ),
                },
                "actions": {
                    "type": "array",
                    "description": (
                        "Sequential UI actions."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "click",
                                    "double_click",
                                    "right_click",
                                    "type",
                                    "key",
                                    "scroll",
                                    "focus",
                                    "read",
                                    "read_screen",
                                    "wait",
                                    "screenshot",
                                    "close_app",
                                ],
                            },
                            "target": {
                                "type": "string",
                            },
                            "text": {
                                "type": "string",
                            },
                            "append": {
                                "type": "boolean",
                            },
                            "keys": {
                                "type": "string",
                            },
                            "direction": {
                                "type": "string",
                                "enum": [
                                    "up",
                                    "down",
                                    "left",
                                    "right",
                                ],
                            },
                            "amount": {
                                "type": "integer",
                            },
                            "ms": {
                                "type": "integer",
                            },
                        },
                        "required": [
                            "action",
                        ],
                    },
                },
            },
            "required": [
                "app",
                "actions",
            ],
        },
    },

    {
        "name": "list_installed_apps",
        "description": (
            "List installed Windows applications from the "
            "application index."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ========================================================
    # FILESYSTEM
    # ========================================================

    {
        "name": "file_op",
        "description": (
            "Perform filesystem operations including listing, "
            "opening, copying, moving, deleting, creating folders, "
            "and searching files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "list",
                        "open",
                        "copy",
                        "move",
                        "delete",
                        "create_folder",
                        "search",
                    ],
                },
                "path": {
                    "type": "string",
                    "description": (
                        "File or folder path, or supported alias "
                        "such as desktop, documents, downloads, "
                        "or pictures."
                    ),
                },
                "dest": {
                    "type": "string",
                    "description": (
                        "Destination path for copy or move."
                    ),
                },
                "pattern": {
                    "type": "string",
                    "description": (
                        "Search pattern for search operations."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Optional content for supported operations."
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                },
                "recursive": {
                    "type": "boolean",
                },
                "include_hidden": {
                    "type": "boolean",
                },
                "max_results": {
                    "type": "integer",
                },
            },
            "required": [
                "operation",
            ],
        },
    },

    # ========================================================
    # SYSTEM
    # ========================================================

    {
        "name": "get_system_info",
        "description": (
            "Get basic Windows system information including the "
            "operating system, version, architecture, hostname, "
            "CPU information, Python version, and boot time."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    {
        "name": "get_running_applications",
        "description": (
            "List currently visible top-level Windows application "
            "windows, including titles, handles, and bounding rectangles."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    {
        "name": "get_processes",
        "description": (
            "List running Windows processes with process IDs, "
            "names, executable paths, and statuses."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    {
        "name": "get_system_resources",
        "description": (
            "Get current CPU, memory, swap, and disk resource usage."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ========================================================
    # PERCEPTION
    # ========================================================

    {
        "name": "screen_diagnose",
        "description": (
            "Inspect the current screen state using the current "
            "screen memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    {
        "name": "get_important_frames",
        "description": (
            "Retrieve previously captured important screen frames "
            "from perception memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ========================================================
    # MEMORY
    # ========================================================

    {
        "name": "user_memory",
        "description": (
            "Add, update, delete, or manage persistent user memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "add",
                        "update",
                        "delete",
                    ],
                },
                "memory_id": {
                    "type": "string",
                },
                "content": {
                    "type": "string",
                },
                "memory_type": {
                    "type": "string",
                },
            },
            "required": [
                "operation",
                "memory_id",
            ],
        },
    },
]


TOOL_DEFINITION_MAP: dict[
    str,
    dict[str, Any],
] = {
    definition["name"]: definition
    for definition in TOOL_DEFINITIONS
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """
    Return all LLM-facing JSON-serializable tool definitions.
    """

    return [
        definition.copy()
        for definition in TOOL_DEFINITIONS
    ]


def get_tool_definition(
    name: str,
) -> dict[str, Any]:
    """
    Return one tool definition by name.
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

        return dict(
            TOOL_DEFINITION_MAP[name]
        )

    except KeyError as exc:

        raise ValueError(
            f"Unknown tool definition: {name}"
        ) from exc