"""配置常量和环境变量加载"""

# API 配置
import os

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
SMALL_FAST_MODEL = os.getenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-20251001")
# 文件配置
MAX_FILE_SIZE = 1000  # 字数限制
MEMORIES_DIR_NAME = ".memories"

# 模糊匹配配置
FUZZY_MATCH_THRESHOLD = 0.8  # 关键字模糊匹配阈值
