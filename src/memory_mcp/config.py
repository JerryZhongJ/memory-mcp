"""配置常量和环境变量加载"""
import os
from pathlib import Path

# API 配置
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

# 文件配置
MAX_FILE_SIZE = 1000           # 字数限制
MEMORIES_DIR_NAME = ".memories"

# 查询配置
# 注意：不限制 LLM 选择的文件数量

# 模糊匹配配置
FUZZY_MATCH_THRESHOLD = 0.6    # 关键字模糊匹配阈值
