"""文件管理器 - 负责文件系统 I/O 操作"""

import hashlib
from pathlib import Path


def get_cache_dir(project_root: Path) -> Path:
    # 使用 SHA256 确保跨进程一致性（不使用内置 hash()，因为有 hash randomization）
    path_str = str(project_root.absolute())
    path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:16]
    return Path.home() / ".memory-mcp" / path_hash


def get_lock_file(project_root: Path) -> Path:
    cache_dir = get_cache_dir(project_root)
    return cache_dir / "backend.lock"


def ensure_dir(dir: Path) -> Path:
    dir.mkdir(exist_ok=True)
    return dir


def list_markdown_names(project_root: Path) -> list[str]:
    memories_dir = ensure_dir(project_root)

    return [file_path.stem for file_path in memories_dir.glob("*.md")]


def read_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def write_file(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")
