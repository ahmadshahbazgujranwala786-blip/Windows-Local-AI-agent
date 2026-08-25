from __future__ import annotations

from typing import Any

from windows_agent.agent.memory_db.chromadb import UserMemory


class UserMemoryTool:

    def __init__(
        self,
        memory: UserMemory,
    ) -> None:
        self._memory = memory

    def __call__(
        self,
        operation: str,
        memory_id: str,
        content: str | None = None,
        memory_type: str | None = None,
    ) -> dict[str, Any]:

        if operation == "add":

            if content is None:
                raise ValueError(
                    "content is required for add."
                )

            if memory_type is None:
                raise ValueError(
                    "memory_type is required for add."
                )

            self._memory.add_memory(
                memory_id=memory_id,
                content=content,
                memory_type=memory_type,
            )

        elif operation == "update":

            if content is None:
                raise ValueError(
                    "content is required for update."
                )

            self._memory.update_memory(
                memory_id=memory_id,
                content=content,
            )

        elif operation == "delete":

            self._memory.delete_memory(
                memory_id=memory_id,
            )

        else:
            raise ValueError(
                f"Unknown operation: {operation}"
            )

        return {
            "success": True,
            "operation": operation,
            "memory_id": memory_id,
        }