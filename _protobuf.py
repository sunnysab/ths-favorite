from __future__ import annotations

from typing import Tuple

_PB_WIRETYPE_VARINT = 0
_PB_WIRETYPE_LEN = 2


def encode_varint(value: int) -> bytes:
    buf = bytearray()
    while value > 127:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        value |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return value, offset


def field_varint(field_number: int, value: int) -> bytes:
    tag = (field_number << 3) | _PB_WIRETYPE_VARINT
    return encode_varint(tag) + encode_varint(value)


def field_bytes(field_number: int, payload: bytes) -> bytes:
    tag = (field_number << 3) | _PB_WIRETYPE_LEN
    return encode_varint(tag) + encode_varint(len(payload)) + payload
