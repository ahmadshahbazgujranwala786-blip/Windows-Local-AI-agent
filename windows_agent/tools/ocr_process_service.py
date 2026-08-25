from __future__ import annotations

import multiprocessing
import traceback
from multiprocessing.connection import Connection
from typing import Any

import numpy as np


class OCRProcessService:

    def __init__(
        self,
        language: str = "en-US",
    ) -> None:
        self._language = language

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

        context = multiprocessing.get_context(# Create a fully isolated interpreter
            "spawn"
        )

        parent_connection, child_connection = (# Connection the parent(main process) and child(ocr_worker)
             context.Pipe()
        )

        process = context.Process(# Creating the Process
            target=self._worker_entry,
            args=(
                child_connection,
                self._language,
            ),
            name="WindowsAgent-OCR",
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
                "OCR worker exited before sending "
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
                "OCR worker returned an invalid "
                f"startup message: {message!r}"
            )

        if message.get("type") != "ready":

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
                "OCR worker failed to initialize:\n"
                f"{error_message}"
            )

        self._connection = parent_connection
        self._process = process

    @staticmethod
    def _worker_entry(
        connection: Connection,
        language: str,
    ) -> None:

        try:
            from windows_agent.tools.ocr_worker import (
                ocr_worker,
            )

            ocr_worker(
                connection,
                language,
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

    def recognize(
        self,
        frame: np.ndarray,
    ) -> Any:

        if not isinstance(
            frame,
            np.ndarray,
        ):
            raise TypeError(
                "frame must be a numpy.ndarray."
            )

        if frame.size == 0:
            raise ValueError(
                "frame cannot be empty."
            )

        self.start()

        if self._connection is None:
            raise RuntimeError(
                "OCR worker connection is unavailable."
            )

        try:
            self._connection.send(
                {
                    "command": "recognize",
                    "frame": frame,
                }
            )

        except (
            BrokenPipeError,
            EOFError,
            OSError,
        ) as exc:

            self._handle_worker_failure()

            raise RuntimeError(
                "Failed to send frame to OCR worker."
            ) from exc

        try:
            message = self._connection.recv()

        except (
            EOFError,
            OSError,
        ) as exc:

            self._handle_worker_failure()

            raise RuntimeError(
                "OCR worker terminated before returning "
                "a recognition result."
            ) from exc

        if not isinstance(
            message,
            dict,
        ):
            raise RuntimeError(
                "OCR worker returned an invalid response: "
                f"{message!r}"
            )

        response_type = message.get(
            "type"
        )

        if response_type == "error":

            traceback_text = message.get(
                "traceback"
            )

            error_text = message.get(
                "error",
                "Unknown OCR worker error.",
            )

            if traceback_text:
                raise RuntimeError(
                    "OCR worker failed:\n"
                    f"{traceback_text}"
                )

            raise RuntimeError(
                f"OCR worker failed: {error_text}"
            )

        if response_type != "result":
            raise RuntimeError(
                "Unexpected OCR worker response: "
                f"{message!r}"
            )

        return message.get(
            "result",
            [],
        )

    def _handle_worker_failure(
        self,
    ) -> None:

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