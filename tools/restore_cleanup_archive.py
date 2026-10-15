#!/usr/bin/env python3
"""Safely restore files from the 2026-10-15 cleanup ZIP archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile


MANIFEST_NAME = "__cleanup__/manifest.json"
DEFAULT_ARCHIVE = Path("archive/cleanup-2026-10-15.zip")
CHUNK_SIZE = 1024 * 1024


class ArchiveError(Exception):
    """An archive or restore destination failed validation."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def checked_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ArchiveError("manifest contains an empty or non-string path")
    if "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ArchiveError(f"unsafe archive path: {value!r}")
    pieces = value.split("/")
    if any(piece in ("", ".", "..") or ":" in piece for piece in pieces):
        raise ArchiveError(f"unsafe archive path: {value!r}")
    if pieces[0] == "__cleanup__":
        raise ArchiveError(f"reserved archive path: {value!r}")
    # PurePosixPath also documents the intended ZIP path convention.
    if PurePosixPath(value).as_posix() != value:
        raise ArchiveError(f"non-canonical archive path: {value!r}")
    return value


def parse_manifest(archive: zipfile.ZipFile) -> tuple[dict[str, dict], set[str]]:
    names: dict[str, zipfile.ZipInfo] = {}
    directories: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        if name in names or name in directories:
            raise ArchiveError(f"duplicate ZIP member: {name!r}")
        if info.is_dir():
            directories.add(name)
        else:
            names[name] = info

    if MANIFEST_NAME not in names:
        raise ArchiveError(f"archive is missing {MANIFEST_NAME}")
    try:
        raw = archive.read(names[MANIFEST_NAME])
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ArchiveError(f"cannot read manifest: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ArchiveError("manifest must contain a 'files' list")

    records: dict[str, dict] = {}
    for record in manifest["files"]:
        if not isinstance(record, dict):
            raise ArchiveError("manifest file records must be objects")
        path = checked_relative_path(record.get("path"))
        size = record.get("bytes")
        digest = record.get("sha256")
        if type(size) is not int or size < 0:
            raise ArchiveError(f"invalid byte count for {path!r}")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ArchiveError(f"invalid SHA-256 for {path!r}")
        if path in records:
            raise ArchiveError(f"duplicate manifest path: {path!r}")
        records[path] = {"path": path, "bytes": size, "sha256": digest}

    payload_names = {
        name for name in names
        if name != MANIFEST_NAME and not name.startswith("__cleanup__/")
    }
    if payload_names != set(records):
        missing = sorted(set(records) - payload_names)
        extra = sorted(payload_names - set(records))
        details = []
        if missing:
            details.append("missing ZIP payload: " + ", ".join(missing[:5]))
        if extra:
            details.append("unlisted ZIP payload: " + ", ".join(extra[:5]))
        raise ArchiveError("archive and manifest differ (" + "; ".join(details) + ")")
    return records, directories


def normalized_prefix(value: str) -> str:
    value = value.strip().replace("\\", "/").strip("/")
    if not value:
        raise ArchiveError("prefix cannot be empty")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ArchiveError(f"unsafe prefix: {value!r}")
    if any(part in ("", ".", "..") or ":" in part for part in value.split("/")):
        raise ArchiveError(f"unsafe prefix: {value!r}")
    return value


def selected_records(records: dict[str, dict], prefixes: list[str]) -> list[dict]:
    if not prefixes:
        return [records[key] for key in sorted(records)]
    normalized = [normalized_prefix(item) for item in prefixes]
    return [
        records[key]
        for key in sorted(records)
        if any(key == prefix or key.startswith(prefix + "/") for prefix in normalized)
    ]


def sha256_stream(stream) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            break
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def validate_payloads(archive: zipfile.ZipFile, records: list[dict]) -> None:
    for record in records:
        try:
            with archive.open(record["path"], "r") as stream:
                size, digest = sha256_stream(stream)
        except (KeyError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise ArchiveError(f"cannot verify {record['path']!r}: {exc}") from exc
        if size != record["bytes"] or digest != record["sha256"]:
            raise ArchiveError(f"archive payload hash/size mismatch: {record['path']}")


def is_link_or_junction(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def checked_target(root: Path, relative: str) -> Path:
    target = root.joinpath(*relative.split("/"))
    parts = relative.split("/")
    current = root
    for index, part in enumerate(parts):
        current = current / part
        if is_link_or_junction(current):
            raise ArchiveError(f"restore path crosses a symlink/junction: {current}")
        if current.exists() and index < len(parts) - 1 and not current.is_dir():
            raise ArchiveError(f"restore parent is not a directory: {current}")
    try:
        target.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ArchiveError(f"restore path escapes the repository: {relative}") from exc
    return target


def list_archive(records: list[dict], prefixes: list[str]) -> None:
    if prefixes:
        for record in records:
            print(f"{record['bytes']:>12}  {record['path']}")
        print(f"{len(records)} files, {sum(r['bytes'] for r in records):,} bytes")
        return

    groups: dict[str, list[int]] = {}
    for record in records:
        pieces = record["path"].split("/")
        group = "/".join(pieces[: min(2, len(pieces))])
        value = groups.setdefault(group, [0, 0])
        value[0] += 1
        value[1] += record["bytes"]
    for group in sorted(groups):
        count, size = groups[group]
        print(f"{count:>6} files  {size:>12,} bytes  {group}")
    print(f"{len(records)} files, {sum(r['bytes'] for r in records):,} bytes")


def restore(archive: zipfile.ZipFile, root: Path, records: list[dict]) -> None:
    # Validate every selected archive byte and every destination before writing.
    validate_payloads(archive, records)
    selected_paths = {record["path"] for record in records}
    for path in selected_paths:
        pieces = path.split("/")
        for index in range(1, len(pieces)):
            parent = "/".join(pieces[:index])
            if parent in selected_paths:
                raise ArchiveError(f"archive file is also a parent directory: {parent!r}")
    targets: list[tuple[dict, Path, bool]] = []
    for record in records:
        target = checked_target(root, record["path"])
        if target.exists():
            if not target.is_file():
                raise ArchiveError(f"restore destination is not a file: {target}")
            try:
                with target.open("rb") as stream:
                    size, digest = sha256_stream(stream)
            except OSError as exc:
                raise ArchiveError(f"cannot inspect existing file {target}: {exc}") from exc
            if size != record["bytes"] or digest != record["sha256"]:
                raise ArchiveError(f"refusing to overwrite different file: {target}")
            targets.append((record, target, True))
        else:
            targets.append((record, target, False))

    restored = 0
    skipped = 0
    for record, target, identical in targets:
        if identical:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".restore-", suffix=".tmp", dir=target.parent, delete=False
            ) as output:
                temporary_path = Path(output.name)
                with archive.open(record["path"], "r") as source:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        output.write(chunk)
            os.replace(temporary_path, target)
            temporary_path = None
            restored += 1
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
    print(f"Restored {restored} files; skipped {skipped} identical files.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="ZIP archive (default: archive/cleanup-2026-10-15.zip)")
    parser.add_argument("--list", action="store_true", help="list archive contents without restoring")
    parser.add_argument("--prefix", action="append", default=[], help="limit listing or restore to this path prefix; may be repeated")
    args = parser.parse_args(argv)

    root = repo_root()
    archive_path = args.archive if args.archive is not None else root / DEFAULT_ARCHIVE
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            all_records, _ = parse_manifest(archive)
            records = selected_records(all_records, args.prefix)
            if args.list:
                list_archive(records, args.prefix)
            else:
                restore(archive, root, records)
    except (OSError, zipfile.BadZipFile, ArchiveError) as exc:
        print(f"restore_cleanup_archive: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
