# ============================================================
# windows_agent/tools/file_tools.py
# ============================================================

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Any


class FileTools:
    """
    High-level filesystem tool.

    One public operation handles:

        list
        open
        copy
        move
        delete
        create_folder
        search

    Paths are resolved internally so the LLM can use human-friendly
    aliases such as:

        desktop
        documents
        downloads
        pictures

    The tool always converts the supplied path into an absolute,
    normalized Windows path before performing filesystem operations.
    """

    def __init__(
        self,
    ) -> None:
        """
        Initialize the filesystem tool.

        The current user's home directory is captured once and used
        for standard Windows folder aliases.
        """

        self._home = (
            Path.home().resolve()
        )

        self._aliases = {
            "home": self._home,
            "desktop": (
                self._home
                / "Desktop"
            ),
            "documents": (
                self._home
                / "Documents"
            ),
            "downloads": (
                self._home
                / "Downloads"
            ),
            "pictures": (
                self._home
                / "Pictures"
            ),
            "music": (
                self._home
                / "Music"
            ),
            "videos": (
                self._home
                / "Videos"
            ),
        }

    # ========================================================
    # PUBLIC TOOL
    # ========================================================

    def call(
        self,
        operation: str,
        path: str | None = None,
        dest: str | None = None,
        pattern: str | None = None,
        content: str | None = None,
        overwrite: bool = False,
        recursive: bool = False,
        include_hidden: bool = False,
        max_results: int = 100,
    ) -> dict[str, Any]:

        if not isinstance(
            operation,
            str,
        ):
            raise TypeError(
                "operation must be a string."
            )

        operation = (
            operation.strip()
            .lower()
        )

        if operation == "list":

            return self._list(
                path=path,
                recursive=recursive,
                include_hidden=include_hidden,
            )

        if operation == "open":

            return self._open(
                path=path,
            )

        if operation == "copy":

            return self._copy(
                path=path,
                dest=dest,
                overwrite=overwrite,
            )

        if operation == "move":

            return self._move(
                path=path,
                dest=dest,
                overwrite=overwrite,
            )

        if operation == "delete":

            return self._delete(
                path=path,
                recursive=recursive,
            )

        if operation == "create_folder":

            return self._create_folder(
                path=path,
            )

        if operation == "search":

            return self._search(
                path=path,
                pattern=pattern,
                recursive=recursive,
                include_hidden=include_hidden,
                max_results=max_results,
            )

        return {
            "success": False,
            "tool": "file_op",
            "operation": operation,
            "error": (
                "UnsupportedOperation"
            ),
            "message": (
                "Supported operations: "
                "list, open, copy, move, delete, "
                "create_folder, search."
            ),
        }

    # ========================================================
    # PATH RESOLUTION
    # ========================================================

    def _resolve_path(
        self,
        path: str,
    ) -> Path:
        """
        Resolve a human-facing path into an absolute Windows path.

        Resolution order:

            1. Validate string.
            2. Expand environment variables.
            3. Expand "~".
            4. Resolve known folder aliases.
            5. Resolve relative paths against the current user's home.
            6. Normalize to an absolute path.

        The returned path is always a pathlib.Path object.
        """

        if not isinstance(
            path,
            str,
        ):
            raise TypeError(
                "path must be a string."
            )

        path = path.strip()

        if not path:
            raise ValueError(
                "path cannot be empty."
            )

        expanded = os.path.expandvars(
            path
        )

        expanded = os.path.expanduser(
            expanded
        )

        normalized_alias = (
            expanded
            .strip()
            .replace(
                "\\",
                "/",
            )
            .strip("/")
            .casefold()
        )

        if normalized_alias in self._aliases:

            return (
                self._aliases[
                    normalized_alias
                ]
                .resolve()
            )

        # ----------------------------------------------------
        # Handle "pictures/file.txt", "desktop/report.pdf", etc.
        # ----------------------------------------------------

        alias_parts = (
            normalized_alias.split(
                "/",
                1,
            )
        )

        alias_name = (
            alias_parts[0]
        )

        if alias_name in self._aliases:

            base = (
                self._aliases[
                    alias_name
                ]
            )

            if len(
                alias_parts
            ) == 1:

                return base.resolve()

            remainder = (
                alias_parts[1]
            )

            return (
                base
                / remainder
            ).resolve()

        # ----------------------------------------------------
        # Absolute Windows path.
        # ----------------------------------------------------

        candidate = Path(
            expanded
        )

        if candidate.is_absolute():

            return candidate.resolve()

        # ----------------------------------------------------
        # Relative path.
        #
        # Relative filesystem references are interpreted relative
        # to the current user's home rather than the process working
        # directory. This prevents the LLM from accidentally depending
        # on wherever main.py happened to be launched.
        # ----------------------------------------------------

        return (
            self._home
            / candidate
        ).resolve()

    # ========================================================
    # LIST
    # ========================================================

    def _list(
        self,
        path: str | None,
        recursive: bool,
        include_hidden: bool,
    ) -> dict[str, Any]:
        """
        List the contents of a directory.

        Returns absolute normalized paths for every returned item.
        """

        if path is None:

            target = (
                self._home
            )

        else:

            target = (
                self._resolve_path(
                    path
                )
            )

        if not target.exists():

            return self._path_not_found(
                "list",
                target,
            )

        if not target.is_dir():

            return {
                "success": False,
                "tool": "file_op",
                "operation": "list",
                "path": str(target),
                "error": "NotADirectoryError",
                "message": (
                    f"Path is not a directory: "
                    f"{target}"
                ),
            }

        try:

            if recursive:

                iterator = (
                    target.rglob("*")
                )

            else:

                iterator = (
                    target.iterdir()
                )

            entries = []

            for item in iterator:

                if (
                    not include_hidden
                    and self._is_hidden(
                        item
                    )
                ):
                    continue

                entries.append(
                    self._serialize_path(
                        item
                    )
                )

            entries.sort(
                key=lambda entry: (
                    entry["name"].casefold()
                )
            )

            return {
                "success": True,
                "tool": "file_op",
                "operation": "list",
                "path": str(target),
                "count": len(
                    entries
                ),
                "items": entries,
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "list",
                "path": str(target),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # OPEN / READ
    # ========================================================

    def _open(
        self,
        path: str | None,
    ) -> dict[str, Any]:
        """
        Read a text file.

        Binary files are rejected rather than silently decoded
        incorrectly.
        """

        if path is None:

            raise ValueError(
                "path is required for open."
            )

        target = (
            self._resolve_path(
                path
            )
        )

        if not target.exists():

            return self._path_not_found(
                "open",
                target,
            )

        if target.is_dir():

            return {
                "success": False,
                "tool": "file_op",
                "operation": "open",
                "path": str(target),
                "error": (
                    "IsADirectoryError"
                ),
                "message": (
                    f"Path is a directory: "
                    f"{target}"
                ),
            }

        try:

            data = (
                target.read_bytes()
            )

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "open",
                "path": str(target),
                "error": type(exc).__name__,
                "message": str(exc),
            }

        # ----------------------------------------------------
        # Decode text safely.
        # ----------------------------------------------------

        encodings = (
            "utf-8-sig",
            "utf-8",
            "cp1252",
        )

        text = None
        selected_encoding = None

        for encoding in encodings:

            try:

                text = (
                    data.decode(
                        encoding
                    )
                )

                selected_encoding = (
                    encoding
                )

                break

            except UnicodeDecodeError:
                continue

        if text is None:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "open",
                "path": str(target),
                "error": (
                    "BinaryFileError"
                ),
                "message": (
                    "File could not be decoded "
                    "as supported text."
                ),
            }

        return {
            "success": True,
            "tool": "file_op",
            "operation": "open",
            "path": str(target),
            "encoding": selected_encoding,
            "size_bytes": len(
                data
            ),
            "content": text,
        }

    # ========================================================
    # COPY
    # ========================================================

    def _copy(
        self,
        path: str | None,
        dest: str | None,
        overwrite: bool,
    ) -> dict[str, Any]:
        """
        Copy a file or directory to the destination.
        """

        if path is None:
            raise ValueError(
                "path is required for copy."
            )

        if dest is None:
            raise ValueError(
                "dest is required for copy."
            )

        source = (
            self._resolve_path(
                path
            )
        )

        destination = (
            self._resolve_path(
                dest
            )
        )

        if not source.exists():

            return self._path_not_found(
                "copy",
                source,
            )

        try:

            final_destination = (
                self._prepare_destination(
                    source=source,
                    destination=destination,
                    overwrite=overwrite,
                )
            )

            if source.is_dir():

                if final_destination.exists():

                    if not overwrite:

                        raise FileExistsError(
                            f"Destination exists: "
                            f"{final_destination}"
                        )

                    shutil.rmtree(
                        final_destination
                    )

                shutil.copytree(
                    source,
                    final_destination,
                )

            else:

                final_destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    source,
                    final_destination,
                )

            return {
                "success": True,
                "tool": "file_op",
                "operation": "copy",
                "source": str(
                    source
                ),
                "destination": str(
                    final_destination
                ),
                "message": (
                    f"Copied {source} "
                    f"to {final_destination}."
                ),
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "copy",
                "source": str(
                    source
                ),
                "destination": str(
                    destination
                ),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # MOVE
    # ========================================================

    def _move(
        self,
        path: str | None,
        dest: str | None,
        overwrite: bool,
    ) -> dict[str, Any]:
        """
        Move a file or directory to the destination.
        """

        if path is None:
            raise ValueError(
                "path is required for move."
            )

        if dest is None:
            raise ValueError(
                "dest is required for move."
            )

        source = (
            self._resolve_path(
                path
            )
        )

        destination = (
            self._resolve_path(
                dest
            )
        )

        if not source.exists():

            return self._path_not_found(
                "move",
                source,
            )

        try:

            final_destination = (
                self._prepare_destination(
                    source=source,
                    destination=destination,
                    overwrite=overwrite,
                )
            )

            if final_destination.exists():

                if not overwrite:

                    raise FileExistsError(
                        f"Destination exists: "
                        f"{final_destination}"
                    )

                if final_destination.is_dir():

                    shutil.rmtree(
                        final_destination
                    )

                else:

                    final_destination.unlink()

            final_destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(source),
                str(final_destination),
            )

            return {
                "success": True,
                "tool": "file_op",
                "operation": "move",
                "source": str(
                    source
                ),
                "destination": str(
                    final_destination
                ),
                "message": (
                    f"Moved {source} "
                    f"to {final_destination}."
                ),
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "move",
                "source": str(
                    source
                ),
                "destination": str(
                    destination
                ),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # DELETE
    # ========================================================

    def _delete(
        self,
        path: str | None,
        recursive: bool,
    ) -> dict[str, Any]:
        """
        Delete a file or directory.

        Directory deletion requires recursive=True.
        """

        if path is None:

            raise ValueError(
                "path is required for delete."
            )

        target = (
            self._resolve_path(
                path
            )
        )

        if not target.exists():

            return self._path_not_found(
                "delete",
                target,
            )

        try:

            if target.is_dir():

                if not recursive:

                    return {
                        "success": False,
                        "tool": "file_op",
                        "operation": "delete",
                        "path": str(
                            target
                        ),
                        "error": (
                            "DirectoryDeletionRequiresRecursive"
                        ),
                        "message": (
                            "Set recursive=True to delete "
                            "a directory."
                        ),
                    }

                shutil.rmtree(
                    target
                )

            else:

                target.unlink()

            return {
                "success": True,
                "tool": "file_op",
                "operation": "delete",
                "path": str(
                    target
                ),
                "message": (
                    f"Deleted {target}."
                ),
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "delete",
                "path": str(
                    target
                ),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # CREATE FOLDER
    # ========================================================

    def _create_folder(
        self,
        path: str | None,
    ) -> dict[str, Any]:
        """
        Create a directory and all missing parent directories.
        """

        if path is None:

            raise ValueError(
                "path is required for create_folder."
            )

        target = (
            self._resolve_path(
                path
            )
        )

        if target.exists():

            if target.is_dir():

                return {
                    "success": True,
                    "tool": "file_op",
                    "operation": "create_folder",
                    "path": str(
                        target
                    ),
                    "created": False,
                    "message": (
                        f"Folder already exists: "
                        f"{target}"
                    ),
                }

            return {
                "success": False,
                "tool": "file_op",
                "operation": "create_folder",
                "path": str(
                    target
                ),
                "error": (
                    "PathAlreadyExists"
                ),
                "message": (
                    f"A file already exists at: "
                    f"{target}"
                ),
            }

        try:

            target.mkdir(
                parents=True,
                exist_ok=True,
            )

            return {
                "success": True,
                "tool": "file_op",
                "operation": "create_folder",
                "path": str(
                    target
                ),
                "created": True,
                "message": (
                    f"Created folder: "
                    f"{target}"
                ),
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "create_folder",
                "path": str(
                    target
                ),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # SEARCH
    # ========================================================

    def _search(
        self,
        path: str | None,
        pattern: str | None,
        recursive: bool,
        include_hidden: bool,
        max_results: int,
    ) -> dict[str, Any]:
        """
        Search a directory tree by filename pattern.

        Examples:

            *.pdf
            report*
            invoice?.xlsx
        """

        if path is None:

            root = (
                self._home
            )

        else:

            root = (
                self._resolve_path(
                    path
                )
            )

        if pattern is None:

            raise ValueError(
                "pattern is required for search."
            )

        pattern = pattern.strip()

        if not pattern:

            raise ValueError(
                "pattern cannot be empty."
            )

        if not isinstance(
            max_results,
            int,
        ):
            raise TypeError(
                "max_results must be an integer."
            )

        if max_results <= 0:

            raise ValueError(
                "max_results must be greater than zero."
            )

        if not root.exists():

            return self._path_not_found(
                "search",
                root,
            )

        if not root.is_dir():

            return {
                "success": False,
                "tool": "file_op",
                "operation": "search",
                "path": str(
                    root
                ),
                "error": (
                    "NotADirectoryError"
                ),
                "message": (
                    f"Search root is not a directory: "
                    f"{root}"
                ),
            }

        try:

            iterator = (
                root.rglob("*")
                if recursive
                else root.glob("*")
            )

            matches = []

            for item in iterator:

                if (
                    not include_hidden
                    and self._is_hidden(
                        item
                    )
                ):
                    continue

                if not fnmatch.fnmatch(
                    item.name,
                    pattern,
                ):
                    continue

                matches.append(
                    self._serialize_path(
                        item
                    )
                )

                if len(matches) >= max_results:
                    break

            return {
                "success": True,
                "tool": "file_op",
                "operation": "search",
                "path": str(
                    root
                ),
                "pattern": pattern,
                "count": len(
                    matches
                ),
                "results": matches,
            }

        except OSError as exc:

            return {
                "success": False,
                "tool": "file_op",
                "operation": "search",
                "path": str(
                    root
                ),
                "pattern": pattern,
                "error": type(exc).__name__,
                "message": str(exc),
            }

    # ========================================================
    # PATH HELPERS
    # ========================================================

    @staticmethod
    def _serialize_path(
        path: Path,
    ) -> dict[str, Any]:
        """
        Convert a filesystem path into a compact JSON-safe record.
        """

        try:

            is_directory = (
                path.is_dir()
            )

            is_file = (
                path.is_file()
            )

            size = (
                path.stat().st_size
                if is_file
                else None
            )

        except OSError:

            is_directory = False
            is_file = False
            size = None

        return {
            "name": path.name,
            "path": str(
                path.resolve()
            ),
            "type": (
                "directory"
                if is_directory
                else "file"
                if is_file
                else "other"
            ),
            "size_bytes": size,
        }

    @staticmethod
    def _is_hidden(
        path: Path,
    ) -> bool:
        """
        Determine whether a Windows path is hidden.

        Windows hidden attribute is checked through ctypes.
        Dot-prefixed names are also treated as hidden for consistency.
        """

        if path.name.startswith(
            "."
        ):
            return True

        try:

            import ctypes

            attributes = (
                ctypes.windll.kernel32.GetFileAttributesW(
                    str(path)
                )
            )

            if attributes == -1:
                return False

            # FILE_ATTRIBUTE_HIDDEN = 0x2
            return bool(
                attributes
                & 0x02
            )

        except Exception:

            return False

    @staticmethod
    def _prepare_destination(
        source: Path,
        destination: Path,
        overwrite: bool,
    ) -> Path:
        """
        Determine the final destination path.

        If the destination exists as a directory, the source basename
        is placed inside it, matching normal Windows copy/move behavior.
        """

        if (
            destination.exists()
            and destination.is_dir()
        ):

            destination = (
                destination
                / source.name
            )

        if (
            destination.exists()
            and not overwrite
        ):

            raise FileExistsError(
                f"Destination exists: "
                f"{destination}"
            )

        return (
            destination
            .resolve()
        )

    @staticmethod
    def _path_not_found(
        operation: str,
        path: Path,
    ) -> dict[str, Any]:
        """
        Return a consistent missing-path result.
        """

        return {
            "success": False,
            "tool": "file_op",
            "operation": operation,
            "path": str(path),
            "error": "FileNotFoundError",
            "message": (
                f"Path does not exist: "
                f"{path}"
            ),
        }