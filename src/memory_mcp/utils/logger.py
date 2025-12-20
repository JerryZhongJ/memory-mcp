"""日志配置模块"""

import logging
import os
import sys


def setup_logger():
    """配置日志系统（使用 root logger）

    - 输出到 stderr（MCP 标准）
    - 通过环境变量 LOG_LEVEL 控制级别（默认 INFO）
    - 格式：时间戳 | 级别 | 模块 | 消息
    - 捕获所有日志（包括第三方库）
    """
    root_logger = logging.getLogger()

    # 避免重复配置
    if root_logger.handlers:
        return root_logger

    # 从环境变量获取日志级别，默认 INFO
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # 输出到 stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(root_logger.level)

    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


setup_logger()
logger = logging.getLogger("memory-mcp")
