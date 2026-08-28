"""Deliberately malformed image bytes, shared across test suites."""

from __future__ import annotations

import struct


def break_png_chunk_crc(png: bytes) -> bytes:
    """A PNG whose header still parses but whose IDAT chunk fails its checksum.

    The interesting corruption, because Pillow reports it as a SyntaxError
    rather than an OSError -- the case a decode-failure clause is most likely
    to miss. Plain ASCII or a truncated body both raise OSError subclasses and
    so prove nothing about that gap.
    """
    corrupt = bytearray(png)
    # Four bytes into the IDAT payload, past the chunk's own four-byte type.
    corrupt[png.index(b"IDAT") + 8] ^= 0xFF
    return bytes(corrupt)


def shorten_png_ihdr(png: bytes) -> bytes:
    """A PNG whose header chunk declares fewer bytes than a header needs.

    The other non-OSError way a malformed PNG surfaces: Pillow raises
    ValueError once IHDR promises less than the thirteen bytes it must carry.
    """
    short = bytearray(png)
    # The first chunk's length field, immediately after the 8-byte signature.
    # A PNG's first chunk is always IHDR.
    short[8:12] = struct.pack(">I", 12)
    return bytes(short)
