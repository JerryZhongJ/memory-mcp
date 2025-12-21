"""后端日志配置（输出到文件，不输出到 stderr）"""

import logging
import os
from pathlib import Path

from ..file_manager import get_cache_dir


def setup_logger(project_root: Path):
    """配置后端日志系统（输出到文件）

    Args:
        project_root: 项目根目录

    重新配置 root logger，确保所有模块（core, utils, tools）的日志都输出到文件
    """
    cache_dir = get_cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_file = cache_dir / "backend.log"

    # 配置 root logger（所有模块都会继承）
    root_logger = logging.getLogger()

    # 清除现有的 handlers（避免重复配置）
    root_logger.handlers.clear()

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # 添加文件 handler
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


logger = logging.getLogger("memory-mcp")
