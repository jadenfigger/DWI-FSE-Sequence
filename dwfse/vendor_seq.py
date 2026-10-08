"""Strict reader/roundtrip writer for the supplied binary WavEd libraries.

This is a file-format inspection tool, not a vendor compiler or board emulator.
Only the two schemas exhaustively tested against scanner/utilities are accepted.
RF control words are retained, never reinterpreted as Pulseq events. A new file
still needs WavEd/compiler loading verification on the target software.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct

import numpy as np


@dataclass
class Frame:
    name: str
    wait_ticks: int
    words: np.ndarray
    expressions: tuple[bytes, ...]
    trailing_words: bytes = b""

    @property
    def records(self):
        return self.words.reshape(-1, 4 if len(self.expressions) == 4 else 2)

    @property
    def samples(self):
        if len(self.expressions) == 4:
            value = (self.records[:, 0] & 0x0FFF).astype(np.int32)
            return np.where(value & 0x0800, value - 4096, value)
        return self.records.view(np.int16).copy()


@dataclass
class Library:
    format_id: int
    header_value: int
    titles: tuple[bytes, ...]
    frames: list[Frame]
    comment_data: bytes = b""

    def frame(self, name):
        found = [frame for frame in self.frames if frame.name == name]
        if len(found) != 1:
            raise ValueError(f"Expected exactly one frame {name!r}, found {len(found)}")
        return found[0]

    def encode(self):
        if self.format_id not in (5, 6):
            raise ValueError("Unsupported WavEd format")
        channels = 4 if self.format_id == 6 else 2
        if not 1 <= len(self.frames) <= 65535:
            raise ValueError("Invalid frame count")
        out = bytearray(struct.pack("<BHH", self.format_id, len(self.frames), self.header_value))
        out.extend(bytes(4 * len(self.frames)))
        title_table = len(out)
        out.extend(bytes(5 * len(self.titles) + 4))
        for index, title in enumerate(self.titles):
            if not title.endswith(b"\0") or not 1 <= len(title) <= 255:
                raise ValueError("Title must be a short null-terminated byte string")
            struct.pack_into("<BI", out, title_table + index*5, len(title), len(out))
            out.extend(title)
        for index, frame in enumerate(self.frames):
            start = len(out)
            struct.pack_into("<I", out, 5+4*index, start)
            name = frame.name.encode("ascii") + b"\0"
            if not 1 <= len(name) <= 255 or len(frame.expressions) != channels:
                raise ValueError("Invalid frame name or expression count")
            words = np.asarray(frame.words, dtype="<u2").reshape(-1)
            if len(words) % (channels if self.format_id == 6 else 2):
                raise ValueError("Incomplete record")
            # On disk length counts 32-bit words, not samples or 16-bit words.
            if len(words) % 2 or not 1 <= len(words)//2 <= 65535:
                raise ValueError("Frame word count outside unsigned 16-bit range")
            if not 1 <= frame.wait_ticks <= 65535:
                raise ValueError("Frame dwell outside unsigned 16-bit range")
            out.extend(bytes(13+6*channels))
            data_pointer = len(out)
            out.extend(words.tobytes())
            if frame.trailing_words not in (b"", bytes(8)):
                raise ValueError("Unsupported stored gradient tail")
            out.extend(frame.trailing_words)
            for channel, expression in enumerate(frame.expressions):
                if not expression.endswith(b"\0") or not 1 <= len(expression) <= 65535:
                    raise ValueError("Invalid expression byte string")
                struct.pack_into("<HI", out, start+13+6*channel, len(expression), len(out))
                out.extend(expression)
            name_pointer = len(out)
            out.extend(name)
            struct.pack_into("<HHBII", out, start, frame.wait_ticks, len(words)//2,
                             len(name), name_pointer, data_pointer)
        if self.comment_data:
            struct.pack_into("<I", out, title_table+5*len(self.titles), len(out))
            out.extend(self.comment_data)
        return bytes(out)


def decode(source: bytes | str | Path) -> Library:
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    if len(data) < 20:
        raise ValueError("Truncated WavEd library")
    format_id, frame_count, header_value = struct.unpack_from("<BHH", data)
    if format_id not in (5, 6) or frame_count < 1:
        raise ValueError("Unsupported WavEd schema")
    channels = 4 if format_id == 6 else 2
    frame_pointers = struct.unpack_from("<"+"I"*frame_count, data, 5)
    cursor = 5+4*frame_count
    titles = []
    title_locations = []
    for _ in range(5 if format_id == 6 else 2):
        length, pointer = struct.unpack_from("<BI", data, cursor)
        titles.append(data[pointer:pointer+length])
        title_locations.append((pointer, length))
        cursor += 5
    comment_pointer = struct.unpack_from("<I", data, cursor)[0]
    cursor += 4
    for title, (pointer, length) in zip(titles, title_locations):
        if pointer != cursor or not title.endswith(b"\0") or len(title) != length:
            raise ValueError("Noncanonical title layout")
        cursor += length
    frames = []
    for pointer in frame_pointers:
        if pointer != cursor:
            raise ValueError("Noncanonical frame layout")
        dwell, word_count, name_length, name_pointer, raw_pointer = struct.unpack_from("<HHBII", data, pointer)
        descriptor = [struct.unpack_from("<HI", data, pointer+13+6*c) for c in range(channels)]
        cursor = pointer+13+6*channels
        if raw_pointer != cursor:
            raise ValueError("Unexpected raw sample offset")
        raw_bytes = data[raw_pointer:raw_pointer+4*word_count]
        if len(raw_bytes) != 4*word_count or word_count < 1 or dwell < 1:
            raise ValueError("Truncated/empty frame")
        words = np.frombuffer(raw_bytes, dtype="<u2").copy()
        if len(words) % channels:
            raise ValueError("Partial sample record")
        cursor += len(raw_bytes)
        trailing_words = data[cursor:descriptor[0][1]]
        if trailing_words not in (b"", bytes(8)) or (format_id == 6 and trailing_words):
            raise ValueError("Unsupported raw data suffix")
        cursor += len(trailing_words)
        expressions = []
        for length, expression_pointer in descriptor:
            expression = data[expression_pointer:expression_pointer+length]
            if expression_pointer != cursor or len(expression) != length or not expression.endswith(b"\0"):
                raise ValueError(f"Unexpected expression layout: frame@{pointer}, expected@{cursor}, got@{expression_pointer}, length={length}, bytes={expression!r}")
            expressions.append(expression)
            cursor += length
        name_raw = data[name_pointer:name_pointer+name_length]
        if name_pointer != cursor or len(name_raw) != name_length or not name_raw.endswith(b"\0"):
            raise ValueError("Invalid frame-name layout")
        name = name_raw[:-1].decode("ascii")
        cursor += name_length
        frames.append(Frame(name, dwell, words, tuple(expressions), trailing_words))
    if comment_pointer and comment_pointer != cursor:
        raise ValueError("Unexpected comment pointer")
    comment_data = data[cursor:] if comment_pointer else b""
    if not comment_pointer and cursor != len(data):
        raise ValueError("Unexpected trailing bytes")
    result = Library(format_id, header_value, tuple(titles), frames, comment_data)
    if result.encode() != data:
        raise ValueError("Lossy binary interpretation")
    return result


def real_rf_frame(name, amplitude_dac, wait_ticks, expressions=None):
    """Encode real signed RF using controls verified in RFstd44 sinc frames.

    Values are already calibrated integer DAC samples; no clipping/rescaling.
    This does not implement AP complex phase encoding. It preserves the real
    frame's F=0 and final control-marker pattern, whose board timing still needs
    vendor loading verification. Include any explicit zero guards deliberately.
    """
    samples = np.asarray(amplitude_dac)
    if samples.ndim != 1 or len(samples) < 2 or not np.isfinite(samples).all():
        raise ValueError("RF samples must be a finite one-dimensional vector")
    if not np.array_equal(samples, np.round(samples)) or np.any(abs(samples) > 2047):
        raise ValueError("RF DAC values must be integers in -2047..2047")
    if not isinstance(wait_ticks, (int, np.integer)) or not 1 <= wait_ticks <= 65535:
        raise ValueError("RF dwell must be integer ticks in 1..65535")
    records = np.tile(np.array([0x3000, 0xD000, 0x2000, 0x1000], dtype="<u2"), (len(samples), 1))
    records[:, 0] |= (samples.astype(np.int64) & 0x0FFF).astype(np.uint16)
    records[-1, 2] = 0x6000
    if expressions is None:
        # Blank editing expressions retain sampled records as the primary data;
        # WavEd regeneration is unverified. Never imply an external CSV is loaded.
        expressions = (b"\0",)*4
    return Frame(name, int(wait_ticks), records.reshape(-1), tuple(expressions))


def user_files(library):
    """Parse the embedded user() file table of a library (opt90_a/opt90_as).

    Layout seen in the vendor files, offsets absolute: u16 count, u16 name
    length, u32 name offset, u32 text length (0xFFFFFFFF = not embedded),
    u32 text offset, then the name and text. Only count 1 has a vendor example.
    """
    data = library.encode()
    block = library.comment_data
    if not block:
        return []
    base = len(data) - len(block)
    count, name_length = struct.unpack_from("<HH", block)
    name_at, text_length, text_at = struct.unpack_from("<III", block, 4)
    if count != 1 or name_at != base + 16 or text_at != name_at + name_length:
        raise ValueError("Unsupported user-file table")
    name = block[16:16 + name_length]
    if not name.endswith(b"\0"):
        raise ValueError("Invalid user-file name")
    text = b"" if text_length == 0xFFFFFFFF else block[16 + name_length:]
    if text_length != 0xFFFFFFFF and len(text) != text_length:
        raise ValueError("Embedded user-file length mismatch")
    return [(name[:-1].decode("ascii"), text)]


def user_rf_library(template, name, amplitude_dac, wait_ticks, text_name):
    """One real RF frame stored the way WavEd stores opt90_as.seq.

    The amplitude expression is ``N,user("text_name");`` and the referenced
    text (``N 1`` then one DAC value per line) is embedded, so WavEd can
    display and regenerate the frame. The stored records are those of
    real_rf_frame(); the text equals their samples exactly.
    """
    samples = np.asarray(amplitude_dac)
    n = len(samples)
    if not re.fullmatch(r"[a-z0-9_]{1,8}\.txt", text_name):
        raise ValueError("User-file name must be a short 8.3 .txt name")
    expressions = (f'{n},user("{text_name}");\0'.encode("ascii"),
                   f"{n}F,0;\0".encode("ascii"), b"\0", b"\0")
    frame = real_rf_frame(name, samples, wait_ticks, expressions)
    library = Library(template.format_id, template.header_value, template.titles, [frame])
    base = len(library.encode())
    file_name = text_name.encode("ascii") + b"\0"
    text = f"{n} 1\r\n".encode("ascii") + b"".join(b"%d\r\n" % int(v) for v in samples)
    library.comment_data = (struct.pack("<HHIII", 1, len(file_name), base + 16, len(text),
                                        base + 16 + len(file_name)) + file_name + text)
    restored = decode(library.encode())
    files = user_files(restored)
    if (len(restored.frames) != 1 or not np.array_equal(restored.frames[0].samples, samples)
            or files != [(text_name, text)]):
        raise ValueError("User-file RF library does not read back exactly")
    return restored


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root/"scanner/utilities").glob("*.seq")):
        lib = decode(path)
        print(path.name, "roundtrip OK", [(f.name, f.wait_ticks, len(f.records)) for f in lib.frames])
