"""后端日志配置（输出到文件，不输出到 stderr）"""

import logging
import os
from logging.handlers import RotatingFileHandler
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

    # 添加文件 handler（带日志轮转）
    # 单个文件最大 10MB，保留 5 个备份文件，总计最多 50MB
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # 禁用 aiohttp 访问日志，避免心跳等 HTTP 请求日志刷屏
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


logger = logging.getLogger("memory-mcp")
