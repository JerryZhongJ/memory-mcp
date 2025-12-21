"""配置常量和环境变量加载"""

import os

# API 配置
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
SMALL_FAST_MODEL = os.getenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-20251001")

# 文件配置
MAX_FILE_SIZE = 1000  # 字数限制
MEMORIES_DIR_NAME = ".memories"

FUZZY_MATCH_THRESHOLD = 0.8  # 关键字模糊匹配阈值

AUTO_SHUTDOWN_IDLE_SECONDS = 600  # 10 分钟无活动后自动退出
AUTO_SHUTDOWN_CHECK_INTERVAL_SECONDS = 30  # 每 30 秒检查一次
