"""
通用文本与格式化工具函数。
"""

import re

_SAFE_NAME_RE = re.compile(r"[^\w.\-]+")


def format_size(size: int) -> str:
    """把字节数格式化为 KB/MB，便于附件文本展示。"""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def sanitize_filename(name: str) -> str:
    """去除文件名中可能造成路径问题的字符。"""
    return _SAFE_NAME_RE.sub("_", name).strip("_")
