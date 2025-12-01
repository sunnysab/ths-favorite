from __future__ import annotations

from typing import Optional


class THSError(Exception):
    """Base exception for all custom THS-related errors."""


class THSAPIError(THSError):
    """Raised when the remote THS API reports a business failure."""

    def __init__(self, action_name: str, message: str, code: Optional[str] = None) -> None:
        self.action_name = action_name
        self.code = code
        detail = message
        if code is not None:
            detail = f"{message} (code={code})"
        super().__init__(f"{action_name} 失败: {detail}")


class THSNetworkError(THSError):
    """Raised when a network-level failure happens while calling THS services."""

    def __init__(self, action_name: str, message: str) -> None:
        self.action_name = action_name
        super().__init__(f"{action_name} 失败: {message}")
