import base64
from typing import Any

import requests

from _protobuf import decode_varint, field_bytes, field_varint
from client import SHARED_SESSION
from config import (
    BLOCKSTOCK_APPNAME,
    DEFAULT_HEADERS,
    MULTI_STORAGE_DEFAULT_CLIENTTYPE,
    MULTI_STORAGE_URL,
    SELF_STOCK_HTTP_TIMEOUT,
)
from exceptions import THSNetworkError
from models import BlockstockDownload, BlockstockGroup, StockEntry


def extract_auth_params_from_cookies(cookies: dict[str, str]) -> dict[str, str]:
    import time
    import urllib.parse as _urlparse
    from datetime import datetime

    sessionid = ''
    user_raw = cookies.get('user', '')
    if user_raw:
        decoded = _urlparse.unquote(user_raw)
        text = base64.b64decode(decoded).decode('utf-8', errors='replace')
        parts = text.split(':')
        if len(parts) > 17:
            sessionid = parts[17]

    expires = datetime.fromtimestamp(time.time() + 86400).strftime('%Y-%m-%d %H:%M:%S')
    return {'userid': cookies.get('userid', ''), 'sessionid': sessionid, 'expires': expires}


def _encode_blockstock_payload(
    group_name: str, group_type: int, stock_list: list[StockEntry]
) -> bytes:
    gbk_bytes = group_name.encode('gbk')
    group_id_b64 = base64.b64encode(gbk_bytes).decode('ascii')

    codes = '|'.join(e.code for e in stock_list)
    types = '|'.join(e.market_type for e in stock_list)
    stock_str = f'{codes},{types}'

    group_data = field_bytes(1, group_id_b64.encode('ascii')) + field_bytes(
        3, stock_str.encode('ascii')
    )
    group_payload = field_bytes(1, field_varint(1, group_type)) + field_bytes(3, group_data)
    return field_bytes(1, group_payload)


def _parse_blockstock_download(data: bytes) -> BlockstockDownload:
    offset = 0
    count = 0
    version = 0
    groups: list[BlockstockGroup] = []

    while offset < len(data):
        tag, offset = decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:
            value, offset = decode_varint(data, offset)
            if field_number == 1:
                count = value
            elif field_number == 2:
                version = value
        elif wire_type == 2:
            length, offset = decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 3:
                groups.append(_parse_group_payload(chunk))

    return BlockstockDownload(count=count, version=version, groups=groups)


def _parse_group_payload(data: bytes) -> BlockstockGroup:
    offset = 0
    group_type = 0
    group_name = ''
    stock_list: list[StockEntry] = []

    while offset < len(data):
        tag, offset = decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:
            value, offset = decode_varint(data, offset)
            if field_number == 1:
                group_type = value
        elif wire_type == 2:
            length, offset = decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 1:
                inner_tag, _ = decode_varint(chunk, 0)
                if (inner_tag >> 3) == 1:
                    value, _ = decode_varint(chunk, 1)
                    group_type = value
            elif field_number == 3:
                inner = _parse_group_data(chunk)
                stock_list = inner.get('stock_list', [])
                gid = inner.get('group_id')
                if gid:
                    try:
                        gb = base64.b64decode(gid).decode('gbk')
                        group_name = gb
                    except Exception:
                        group_name = gid

    return BlockstockGroup(group_name=group_name, group_type=group_type, stock_list=stock_list)


def _parse_group_data(data: bytes) -> dict[str, Any]:
    offset = 0
    result: dict[str, Any] = {'group_id': None, 'stock_list': []}

    while offset < len(data):
        tag, offset = decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, offset = decode_varint(data, offset)
            chunk = data[offset : offset + length]
            offset += length
            if field_number == 1:
                result['group_id'] = chunk.decode('ascii')
            elif field_number == 3:
                raw = chunk.decode('ascii')
                comma_idx = raw.rfind(',')
                if comma_idx >= 0:
                    codes_segment = raw[:comma_idx]
                    types_segment = raw[comma_idx + 1 :]
                    codes = [c for c in codes_segment.split('|') if c]
                    type_codes = [t for t in types_segment.split('|') if t]
                    entries: list[StockEntry] = []
                    for i, code in enumerate(codes):
                        mtype = type_codes[i] if i < len(type_codes) else ''
                        entries.append(StockEntry(code, mtype))
                    result['stock_list'] = entries

    return result


def download_blockstock(
    auth_params: dict[str, str],
    cookies: dict[str, str],
    *,
    storepath: str = '/',
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> BlockstockDownload:
    data: dict[str, str] = {
        'reqtype': 'download',
        'userid': auth_params.get('userid', ''),
        'storepath': storepath,
        'sessionid': auth_params.get('sessionid', ''),
        'expires': auth_params.get('expires', ''),
        'appname': BLOCKSTOCK_APPNAME,
        'storetype': '2',
        'clienttype': auth_params.get('clienttype', MULTI_STORAGE_DEFAULT_CLIENTTYPE),
        'version': '0',
    }
    headers = {
        'User-Agent': DEFAULT_HEADERS.get('User-Agent', 'hevo'),
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    try:
        response = SHARED_SESSION.post(
            MULTI_STORAGE_URL,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError('blockstock download', str(exc)) from exc

    return _parse_blockstock_download(response.content)


def upload_blockstock(
    auth_params: dict[str, str],
    cookies: dict[str, str],
    group_name: str,
    group_type: int,
    stock_list: list[StockEntry],
    version: str,
    *,
    storepath: str = '/',
    timeout: float = SELF_STOCK_HTTP_TIMEOUT,
) -> dict[str, Any]:
    payload_bytes = _encode_blockstock_payload(group_name, group_type, stock_list)

    data: dict[str, str] = {
        'appname': BLOCKSTOCK_APPNAME,
        'reqtype': 'upload',
        'version': str(version),
        'storepath': storepath,
        'clienttype': auth_params.get('clienttype', MULTI_STORAGE_DEFAULT_CLIENTTYPE),
        'compresstype': 'none',
        'compresstype_upload': 'none',
        'compresstype_download': 'none',
        'userid': auth_params.get('userid', ''),
        'sessionid': auth_params.get('sessionid', ''),
        'expires': auth_params.get('expires', ''),
    }
    files = {'uploadFile': ('testFileList', payload_bytes, 'application/octet-stream')}
    headers = {'User-Agent': DEFAULT_HEADERS.get('User-Agent', 'hevo')}

    try:
        response = SHARED_SESSION.post(
            MULTI_STORAGE_URL,
            data=data,
            files=files,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise THSNetworkError('blockstock upload', str(exc)) from exc

    return _parse_blockstock_download(response.content)
