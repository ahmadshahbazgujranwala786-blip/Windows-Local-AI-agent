from dataclasses import dataclass
from typing import Optional
from io import BytesIO
import asyncio

import numpy as np
from PIL import Image

from winrt.windows.foundation import Uri
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import (
    BitmapDecoder,
    BitmapPixelFormat,
    BitmapAlphaMode,
)
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import (
    DataWriter,
    InMemoryRandomAccessStream,
)


@dataclass
class OCRWord:
    text: str
    bounding_rectangle: tuple[
        float,
        float,
        float,
        float,
    ]


@dataclass
class OCRLine:
    text: str
    words: list[OCRWord]


class WindowsOCR:

    def __init__(
        self,
        language: str = "en-US",
    ):
        self._language = Language(language)

        if not OcrEngine.is_language_supported(
            self._language
        ):
            raise RuntimeError(
                f"OCR language is not supported: {language}"
            )

        self._engine = (
            OcrEngine.try_create_from_language(
                self._language
            )
        )

        if self._engine is None:
            raise RuntimeError(
                f"Could not create OCR engine for: {language}"
            )

    def recognize(
        self,
        frame: np.ndarray,
    ) -> list[OCRLine]:

        if not isinstance(frame, np.ndarray):
            raise TypeError(
                "frame must be a numpy.ndarray."
            )

        if frame.size == 0:
            raise ValueError(
                "frame cannot be empty."
            )

        return asyncio.run(
            self._recognize_async(frame)
        )

    async def _recognize_async(
        self,
        frame: np.ndarray,
    ) -> list[OCRLine]:

        image = self._prepare_image(frame)

        bitmap = await self._numpy_to_software_bitmap(
            image
        )

        result = await self._engine.recognize_async(
            bitmap
        )

        lines: list[OCRLine] = []

        for line in result.lines:

            words: list[OCRWord] = []

            for word in line.words:

                rect = word.bounding_rect

                words.append(
                    OCRWord(
                        text=word.text,
                        bounding_rectangle=(
                            float(rect.x),
                            float(rect.y),
                            float(rect.width),
                            float(rect.height),
                        ),
                    )
                )

            lines.append(
                OCRLine(
                    text=line.text,
                    words=words,
                )
            )

        return lines

    def _prepare_image(
        self,
        frame: np.ndarray,
    ) -> Image.Image:

        if frame.ndim == 2:
            return Image.fromarray(
                frame,
                mode="L",
            ).convert("RGB")

        if frame.ndim != 3:
            raise ValueError(
                "frame must be a 2D or 3D numpy array."
            )

        channels = frame.shape[2]

        if channels == 3:
            # DXcam normally provides BGR frames.
            rgb = frame[:, :, ::-1]
            return Image.fromarray(
                rgb,
                mode="RGB",
            )

        if channels == 4:
            # BGRX/BGRA-style frame.
            rgba = frame[:, :, [2, 1, 0, 3]]
            return Image.fromarray(
                rgba,
                mode="RGBA",
            ).convert("RGB")

        raise ValueError(
            "Unsupported channel count. "
            "Expected 1, 3, or 4."
        )

    from io import BytesIO


    async def _numpy_to_software_bitmap(
    self,
    image: Image.Image,
    ):


       image = image.convert("RGBA")

       buffer = BytesIO()

       image.save(
        buffer,
        format="PNG",
    )

       encoded_bytes = buffer.getvalue()

       stream = InMemoryRandomAccessStream()

       writer = DataWriter(stream)

       writer.write_bytes(
        encoded_bytes,
    )

       await writer.store_async()
       await writer.flush_async()

       stream.seek(0)

       bitmap = await BitmapDecoder.create_async(
        stream,
       )

       software_bitmap = (
       await bitmap.get_software_bitmap_async()
)

       return software_bitmap  