"""前端日志配置（MCP 标准：输出到 stderr）"""

import logging
import os
import sys


def setup_logger():
    """配置前端日志系统

    - 输出到 stderr（MCP 标准）
    - 通过环境变量 LOG_LEVEL 控制级别（默认 INFO）
    """
    root_logger = logging.getLogger()

    # 避免重复配置
    if root_logger.handlers:
        return root_logger

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(root_logger.level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    return root_logger


setup_logger()
logger = logging.getLogger("memory-mcp-frontend")
