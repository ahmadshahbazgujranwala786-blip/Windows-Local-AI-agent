from __future__ import annotations

import traceback
from multiprocessing.connection import Connection
from typing import Any


class RemoteToolManager:

    def __init__(
        self,
        connection: Connection,
    ) -> None:


        self._connection = connection

    def execute(
        self,
        tool_name: str,
        **parameters: Any,
    ) -> Any:

        self._connection.send(
            {
                "type": "execute_tool",
                "tool": tool_name,
                "parameters": parameters,
            }
        )

        response = self._connection.recv()

        if not isinstance(
            response,
            dict,
        ):
            raise RuntimeError(
                "Main process returned an invalid tool response."
            )

        response_type = response.get(
            "type"
        )

        if response_type == "tool_result":
            return response.get(
                "result"
            )

        if response_type == "tool_error":
            raise RuntimeError(
                response.get(
                    "error",
                    "Unknown tool execution error.",
                )
            )

        raise RuntimeError(
            "Unexpected main-process response: "
            f"{response!r}"
        )


def graph_worker_main(
    connection: Connection,
) -> None:

    try:
        from windows_agent.agent.graph import (
            execute_complex_task,
        )

        tool_manager = RemoteToolManager(
            connection,
        )

        connection.send(
            {
                "type": "ready",
                "success": True,
            }
        )

        while True:
            message = connection.recv()

            if not isinstance(
                message,
                dict,
            ):
                raise RuntimeError(
                    "Graph worker received an invalid message."
                )

            command = message.get(
                "command"
            )

            if command == "execute_complex_task":

                parsed_output = message.get(
                    "parsed_output"
                )

                if not isinstance(
                    parsed_output,
                    dict,
                ):
                    raise ValueError(
                        "parsed_output must be a dictionary."
                    )

                if parsed_output.get(
                    "task_type"
                ) != "complex":
                    raise ValueError(
                        "Graph worker requires a complex task."
                    )

                result = execute_complex_task(
                    parsed_output,
                    tool_manager,
                )

                connection.send(
                    {
                        "type": "graph_result",
                        "success": True,
                        "result": result,
                    }
                )

            elif command == "shutdown":

                connection.send(
                    {
                        "type": "shutdown",
                        "success": True,
                    }
                )

                break

            else:
                raise ValueError(
                    f"Unknown graph-worker command: {command!r}"
                )

    except Exception as exc:

        try:
            connection.send(
                {
                    "type": "error",
                    "success": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )

        except Exception:
            pass

    finally:

        try:
            connection.close()

        except Exception:
            pass