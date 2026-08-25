from __future__ import annotations

import traceback
from multiprocessing.connection import Connection

import numpy as np

from windows_agent.tools.windows_ocr import WindowsOCR


def ocr_worker(
    connection: Connection,
    language: str = "en-US",
) -> None:

    try:
        ocr = WindowsOCR(
            language=language,
        )

        connection.send(
            {
                "type": "ready",
                "success": True,
            }
        )

        while True:

            message = connection.recv()

            command = message.get(
                "command"
            )

            if command == "recognize":

                frame = message.get(
                    "frame"
                )

                if not isinstance(
                    frame,
                    np.ndarray,
                ):
                    raise TypeError(
                        "OCR worker received an invalid frame."
                    )

                result = ocr.recognize(
                    frame,
                )

                connection.send(
                    {
                        "type": "result",
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
                    f"Unknown OCR worker command: {command}"
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

