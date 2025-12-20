"""文件管理器 - 负责文件系统 I/O 操作"""

from pathlib import Path


def ensure_dir(dir: Path) -> Path:
    """确保 .memories 目录存在

    Args:
        project_root: 项目根目录

    Returns:
        .memories 目录的路径
    """

    dir.mkdir(exist_ok=True)
    return dir


def list_markdown_names(project_root: Path) -> list[str]:
    """列出所有 memory 文件

    Args:
        project_root: 项目根目录

    Returns:
        字典，键为 keywords set（frozenset），值为文件路径
    """
    memories_dir = ensure_dir(project_root)

    return [file_path.stem for file_path in memories_dir.glob("*.md")]


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
