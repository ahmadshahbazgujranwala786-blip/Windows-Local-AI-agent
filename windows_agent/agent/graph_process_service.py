# ============================================================
# windows_agent/agent/graph_process_service.py
# ============================================================

from __future__ import annotations

import multiprocessing
import traceback
from multiprocessing.connection import Connection
from typing import Any, Callable


class GraphProcessService:

    def __init__(
        self,
        tool_executor: Callable[..., Any],
    ) -> None:
   

        self._tool_executor = tool_executor

        self._process: (
            multiprocessing.Process | None
        ) = None

        self._connection: (
            Connection | None
        ) = None

    def start(self) -> None:

        if (
            self._process is not None
            and self._process.is_alive()
        ):
            return

        context = multiprocessing.get_context(
            "spawn"
        )

        parent_connection, child_connection = (
            context.Pipe()
        )

        process = context.Process(
            target=self._worker_entry,
            args=(
                child_connection,
            ),
            name="WindowsAgent-Graph",
            daemon=True,
        )

        try:
            process.start()

        except Exception:
            parent_connection.close()
            child_connection.close()
            raise

        child_connection.close()

        try:
            message = parent_connection.recv()

        except EOFError as exc:
            exit_code = process.exitcode

            parent_connection.close()

            process.join(
                timeout=2
            )

            raise RuntimeError(
                "Graph worker exited before sending "
                f"a ready message. Exit code: {exit_code}."
            ) from exc

        except Exception:
            parent_connection.close()

            if process.is_alive():
                process.terminate()

            process.join(
                timeout=2
            )

            raise

        if not isinstance(
            message,
            dict,
        ):
            parent_connection.close()

            if process.is_alive():
                process.terminate()

            process.join(
                timeout=2
            )

            raise RuntimeError(
                "Graph worker returned an invalid startup message: "
                f"{message!r}"
            )

        if message.get(
            "type"
        ) != "ready":

            error_message = (
                message.get(
                    "traceback"
                )
                or message.get(
                    "error"
                )
                or repr(message)
            )

            parent_connection.close()

            if process.is_alive():
                process.terminate()

            process.join(
                timeout=2
            )

            raise RuntimeError(
                "Graph worker failed to initialize:\n"
                f"{error_message}"
            )

        self._connection = parent_connection
        self._process = process

    @staticmethod
    def _worker_entry(
        connection: Connection,
    ) -> None:


        try:
            from windows_agent.tools.graph_worker import (
                graph_worker_main,
            )

            graph_worker_main(
                connection,
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

    def execute_complex_task(
        self,
        parsed_output: dict[str, Any],
    ) -> Any:


        if not isinstance(
            parsed_output,
            dict,
        ):
            raise TypeError(
                "parsed_output must be a dictionary."
            )

        if parsed_output.get(
            "task_type"
        ) != "complex":
            raise ValueError(
                "GraphProcessService requires a complex task."
            )

        plan = parsed_output.get(
            "plan"
        )

        if not isinstance(
            plan,
            list,
        ):
            raise ValueError(
                "Complex task plan must be a list."
            )

        if not plan:
            raise ValueError(
                "Complex task plan cannot be empty."
            )

        self.start()

        if self._connection is None:
            raise RuntimeError(
                "Graph worker connection is unavailable."
            )

        self._connection.send(
            {
                "command": "execute_complex_task",
                "parsed_output": parsed_output,
            }
        )

        while True:

            try:
                message = self._connection.recv()

            except (
                EOFError,
                OSError,
            ) as exc:

                self._handle_worker_failure()

                raise RuntimeError(
                    "Graph worker terminated before returning "
                    "a result."
                ) from exc

            if not isinstance(
                message,
                dict,
            ):
                raise RuntimeError(
                    "Graph worker returned an invalid message: "
                    f"{message!r}"
                )

            message_type = message.get(
                "type"
            )

            if message_type == "execute_tool":

                tool_name = message.get(
                    "tool"
                )

                parameters = message.get(
                    "parameters",
                    {},
                )

                try:
                    result = self._tool_executor(
                        tool_name,
                        **parameters,
                    )

                    self._connection.send(
                        {
                            "type": "tool_result",
                            "success": True,
                            "result": result,
                        }
                    )

                except Exception as exc:

                    self._connection.send(
                        {
                            "type": "tool_error",
                            "success": False,
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        }
                    )

                continue

            if message_type == "graph_result":

                return message.get(
                    "result"
                )

            if message_type == "error":

                raise RuntimeError(
                    "Graph worker failed:\n"
                    f"{message.get('traceback', message.get('error'))}"
                )

            raise RuntimeError(
                "Unexpected graph worker message: "
                f"{message!r}"
            )

    def _handle_worker_failure(self) -> None:

        process = self._process
        connection = self._connection

        self._process = None
        self._connection = None

        if connection is not None:

            try:
                connection.close()

            except Exception:
                pass

        if process is not None:

            if process.is_alive():
                process.terminate()

            process.join(
                timeout=2
            )

    def close(self) -> None:

        connection = self._connection
        process = self._process

        self._connection = None
        self._process = None

        if connection is not None:

            try:
                connection.send(
                    {
                        "command": "shutdown",
                    }
                )

                if connection.poll(
                    2
                ):
                    connection.recv()

            except Exception:
                pass

            finally:

                try:
                    connection.close()

                except Exception:
                    pass

        if process is not None:

            process.join(
                timeout=2
            )

            if process.is_alive():

                process.terminate()

                process.join(
                    timeout=2
                )