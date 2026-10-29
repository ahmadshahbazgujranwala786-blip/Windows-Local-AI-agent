# ============================================================
# windows_agent/agent/memory_db/chromadb.py
# ============================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import chromadb


COLLECTION_NAME = "user_memory"

TEMP_MEMORY_DAYS = 10

EMBEDDING_MODEL = (
    "https://tfhub.dev/google/"
    "universal-sentence-encoder/4"
)


class TensorFlowEmbeddingFunction:

    def __init__(self) -> None:

        self._model: Any | None = None

        self._lock = Lock()

    def name(self) -> str:

        return (
            "tensorflow_universal_sentence_encoder"
        )

    def __call__(
        self,
        input: list[str],
    ) -> list[list[float]]:

        if not isinstance(
            input,
            list,
        ):
            raise TypeError(
                "input must be a list of strings."
            )

        for text in input:

            if not isinstance(
                text,
                str,
            ):
                raise TypeError(
                    "Every embedding input must be a string."
                )

        model = self._get_model()

        embeddings = model(
            input
        )

        return embeddings.numpy().tolist()

    def _get_model(
        self,
    ) -> Any:

        if self._model is not None:

            return self._model

        with self._lock:

            if self._model is None:

                import tensorflow_hub as hub

                self._model = hub.load(
                    EMBEDDING_MODEL
                )

        return self._model


class UserMemory:

    def __init__(
        self,
        path: str | None = None,
    ) -> None:
        if path is None:
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[3]
            path = str(project_root / "memory_db" / "chroma_db")

        self._client = (
            chromadb.PersistentClient(
                path=path,
            )
        )

        self._embedding_function = (
            TensorFlowEmbeddingFunction()
        )

        self._collection = (
            self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=(
                    self._embedding_function
                ),
            )
        )

    def add_memory(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
    ) -> None:

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self._collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[
                {
                    "memory_type": memory_type,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

    def update_memory(
        self,
        memory_id: str,
        content: str,
    ) -> None:

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self._collection.update(
            ids=[memory_id],
            documents=[content],
            metadatas=[
                {
                    "updated_at": now,
                }
            ],
        )

    def delete_memory(
        self,
        memory_id: str,
    ) -> None:


        self._collection.delete(
            ids=[memory_id]
        )

    def cleanup_expired(
        self,
    ) -> None:
        
        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                days=TEMP_MEMORY_DAYS
            )
        )

        result = self._collection.get(
            include=[
                "metadatas"
            ]
        )

        ids_to_delete: list[str] = []

        for memory_id, metadata in zip(
            result["ids"],
            result["metadatas"],
        ):

            if metadata is None:
                continue

            if metadata.get(
                "memory_type"
            ) in {
                "name",
                "preference",
            }:
                continue

            created_at = metadata.get(
                "created_at"
            )

            if not created_at:
                continue

            created = (
                datetime.fromisoformat(
                    created_at
                )
            )

            if created < cutoff:

                ids_to_delete.append(
                    memory_id
                )

        if ids_to_delete:

            self._collection.delete(
                ids=ids_to_delete
            )

    def is_embedding_model_loaded(
        self,
    ) -> bool:

        return (
            self._embedding_function._model
            is not None
        )