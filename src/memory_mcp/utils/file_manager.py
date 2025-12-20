"""文件管理器 - 负责文件系统 I/O 操作"""

from pathlib import Path

from ..config import MEMORIES_DIR_NAME


def ensure_memories_dir(project_root: Path) -> Path:
    """确保 .memories 目录存在

    Args:
        project_root: 项目根目录

    Returns:
        .memories 目录的路径
    """
    memories_dir = project_root / MEMORIES_DIR_NAME
    memories_dir.mkdir(exist_ok=True)
    return memories_dir


def list_memory_files(project_root: Path) -> list[frozenset[str]]:
    """列出所有 memory 文件

    Args:
        project_root: 项目根目录

    Returns:
        字典，键为 keywords set（frozenset），值为文件路径
    """
    memories_dir = ensure_memories_dir(project_root)
    result = []

    for file_path in memories_dir.glob("*.md"):
        keywords = extract_keywords_from_filename(file_path.name)
        result.append(keywords)

    return result


def extract_keywords_from_filename(filename: str) -> frozenset:
    """从文件名提取 keywords set

    Args:
        filename: 文件名（例如 "api-design-patterns.md"）

    Returns:
        keywords 的 frozenset（无顺序）
    """
    # 去除 .md 后缀
    name = filename.removesuffix(".md")
    # 按连字符分割
    keywords = name.split("-")
    # 返回 frozenset（无顺序，可哈希）
    return frozenset(keywords)


def read_file(file_path: Path) -> str:
    """读取文件内容

    Args:
        file_path: 文件路径

    Returns:
        文件内容
    """
    return file_path.read_text(encoding="utf-8")


def write_file(file_path: Path, content: str) -> None:
    """写入文件

    Args:
        file_path: 文件路径
        content: 文件内容
    """
    file_path.write_text(content, encoding="utf-8")
