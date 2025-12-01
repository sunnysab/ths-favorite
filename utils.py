from __future__ import annotations

import xml.etree.ElementTree as ET

from exceptions import THSAPIError


def parse_ths_xml_response(xml_text: str, action_name: str) -> ET.Element:
    """Parse THS XML payloads and guard against business failures.

    Args:
        xml_text: Raw XML string returned by THS.
        action_name: A short description of the ongoing action, used for error reporting.

    Returns:
        The parsed root :class:`xml.etree.ElementTree.Element`.

    Raises:
        THSAPIError: When the XML cannot be parsed, lacks the ``<ret>`` node,
            or indicates a non-zero ``code``.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise THSAPIError(action_name, f"响应解析失败: {exc}") from exc

    ret_node = root.find("ret")
    if ret_node is None:
        raise THSAPIError(action_name, "响应缺少 <ret> 节点")

    code = ret_node.attrib.get("code")
    if str(code) != "0":
        message = ret_node.attrib.get("msg") or "未知错误"
        raise THSAPIError(action_name, message, code=str(code) if code is not None else None)

    return root
