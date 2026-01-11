"""Recall 工具 - 从记忆中召回信息"""

from anthropic.types import ToolUnionParam

from memory_mcp.backend.config import (
    DEFAULT_MAX_ITER,
    FAST_RECALL_MAX_ITER,
    FAST_RECALL_MAX_READ,
    FAST_RECALL_MAX_SEARCH,
)

from ..core.memory_registry import MemoryRegistry
from ..llm import small_agent
from ..logger import logger
from .memory_tools import (
    LimitedListMemoriesTool,
    LimitedReadMemoryTool,
    ListMemoriesTool,
    ReadMemoryTool,
)


def _validate_extracts(extracts: list[dict], registry: MemoryRegistry) -> str:
    """将结构化的回忆数据格式化为 Markdown 文本

    Args:
        extracts: 包含 content 和 source 的字典列表
        registry: 记忆注册表，用于验证 source 是否真实存在

    Returns:
        格式化后的 Markdown 文本
    """
    if not extracts:
        return "没有相关记忆"

    lines = []
    for item in extracts:
        content = item.get("content", "").strip()
        source = item.get("source", [])

        if not content:
            continue

        # 验证 source 是否真实存在
        if not source or not isinstance(source, list):
            logger.warning(f"Skipping extract without valid source...")
            continue
        # 检查这个关键词组是否存在于记忆库中
        if not registry.has_memory(source):
            logger.warning(f"Skipping extract with non-existent source: {source}")
            continue
        # 来源验证通过，添加到输出（不显示来源）
        lines.append(content)

    return "\n".join(lines) if lines else "没有相关记忆"


async def deep_recall_memory(interest: str, registry: MemoryRegistry) -> str:
    """深度回忆流程（无限制，详尽搜索）"""
    logger.info(f"[Deep Recall] Query: {interest}")

    try:
        list_tool = ListMemoriesTool(registry)
        read_tool = ReadMemoryTool(registry)

        final_tools: list[ToolUnionParam] = [
            {
                "name": "submit",
                "description": "提交提取到的记忆信息",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "extracts": {
                            "type": "array",
                            "description": "提取到的记忆内容列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "string",
                                        "description": "从记忆中提取的具体内容（可以是一段话）",
                                    },
                                    "source": {
                                        "type": "array",
                                        "description": "信息来源的记忆关键词数组",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["content", "source"],
                            },
                        }
                    },
                    "required": ["extracts"],
                },
            }
        ]

        initial_prompt = f"""从记忆库中提取与以下查询相关的信息：{interest}

操作指南：
1. 使用 list_memories 工具搜索相关记忆
2. 使用 read_memory 工具读取相关记忆
3. 提取记忆中的相关信息并标注来源

任务要求：
- **仅提取记忆内容**：逐条提取你读取到的记忆中的相关信息，包括直接相关的信息和补充背景信息
- **每条信息必须标注来源**：source 字段必须是关键词数组，格式为 ["keyword1", "keyword2", ...]
- 不要对记忆内容进行扩展，只需逐条提取

提示：
- list_memories 返回的是按匹配度排序的结果
- read_memory 需要提供每个记忆唯一的关键词组
- 如果没有相关内容，返回空数组"""

        result = await small_agent(
            initial_prompt=initial_prompt,
            tools=[list_tool, read_tool],
            final=final_tools,
            maxIter=DEFAULT_MAX_ITER,
        )

        if result is None:
            logger.warning(f"[Deep Recall] Timeout for query: {interest}")
            return "查询超时，未能生成报告"

        tool_name, tool_input = result
        if tool_name == "submit":
            logger.info(f"[Deep Recall] Completed for: {interest}")
            extracts = tool_input.get("extracts", [])
            formatted_response = _validate_extracts(extracts, registry)
            return formatted_response

        logger.warning(f"[Deep Recall] Unknown result for query: {interest}")
        return "未知错误"

    except Exception as e:
        logger.error(f"[Deep Recall] Failed: {e}", exc_info=True)
        raise


async def fast_recall_memory(interest: str, registry: MemoryRegistry) -> str:
    """快速回忆流程（有限制，快速响应）"""
    logger.info(f"[Fast Recall] Query: {interest}")

    try:
        # 使用限制型工具
        list_tool = LimitedListMemoriesTool(registry, max_calls=2)
        read_tool = LimitedReadMemoryTool(registry, max_reads=5)

        final_tools: list[ToolUnionParam] = [
            {
                "name": "submit",
                "description": "提交提取到的记忆信息",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "extracts": {
                            "type": "array",
                            "description": "提取到的记忆内容列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "string",
                                        "description": "从记忆中提取的具体内容（可以是一段话）",
                                    },
                                    "source": {
                                        "type": "array",
                                        "description": "信息来源的记忆关键词数组",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["content", "source"],
                            },
                        }
                    },
                    "required": ["extracts"],
                },
            }
        ]

        initial_prompt = f"""从记忆库中提取与以下查询相关的信息：{interest}

操作限制：
- 你只能调用 list_memories 最多 {FAST_RECALL_MAX_SEARCH} 次
- 你只能调用 read_memory 最多 {FAST_RECALL_MAX_READ} 次

任务要求：
1. **仅提取记忆内容**：逐条提取你读取到的记忆中的相关信息，不要进行扩展
2. **每条信息必须标注来源**：source 字段必须是关键词数组，格式为 ["keyword1", "keyword2", ...]

处理流程：
1. 精心设计关键词，调用 list_memories 搜索
2. 阅读最相关的最多 {FAST_RECALL_MAX_READ} 篇记忆
3. 提取相关信息并标注来源
4. 如果没有相关内容，返回空数组
"""

        result = await small_agent(
            initial_prompt=initial_prompt,
            tools=[list_tool, read_tool],
            final=final_tools,
            maxIter=FAST_RECALL_MAX_ITER,  # 更小的迭代次数
        )

        if result is None:
            logger.warning(f"[Fast Recall] Timeout for query: {interest}")
            return "查询超时，未能生成报告"

        tool_name, tool_input = result
        if tool_name == "submit":
            logger.info(f"[Fast Recall] Completed for: {interest}")
            extracts = tool_input.get("extracts", [])
            formatted_response = _validate_extracts(extracts, registry)
            return formatted_response

        logger.warning(f"[Fast Recall] Unknown result for query: {interest}")
        return "未知错误"

    except Exception as e:
        logger.error(f"[Fast Recall] Failed: {e}", exc_info=True)
        raise


async def recall_memory(
    interest: str, registry: MemoryRegistry, deep: bool = False
) -> str:
    if deep:
        return await deep_recall_memory(interest, registry)
    else:
        return await fast_recall_memory(interest, registry)
