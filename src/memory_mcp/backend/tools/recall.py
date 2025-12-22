"""Recall 工具 - 从记忆中召回信息"""

from anthropic.types import ToolUnionParam

from memory_mcp.backend.config import (
    DEFAULT_MAX_ITER,
    FAST_RECALL_MAX_ITER,
    FAST_RECALL_MAX_READ,
    FAST_RECALL_MAX_SEARCH,
    FAST_RECALL_REPORT_LIMIT,
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


async def deep_recall_memory(interest: str, registry: MemoryRegistry) -> str:
    """深度回忆流程（无限制，详尽搜索）"""
    logger.info(f"[Deep Recall] Query: {interest}")

    try:
        list_tool = ListMemoriesTool(registry)
        read_tool = ReadMemoryTool(registry)

        final_tools: list[ToolUnionParam] = [
            {
                "name": "submit",
                "description": "提交回忆报告",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "report": {
                            "type": "string",
                            "description": "综合回忆报告（Markdown 格式）",
                        }
                    },
                    "required": ["report"],
                },
            }
        ]

        initial_prompt = f"""尝试从记忆库回忆与这个有关的信息：{interest}

请按以下指导处理：
1. 使用 list_memories 工具搜索相关记忆
2. 使用 read_memory 工具读取相关记忆
3. 基于读取的内容，调用 submit 提交综合报告

提示：
- list_memories 返回的是按匹配度排序的结果
- read_memory 需要提供每个记忆唯一的关键词组
- 报告除了直接回应用户的兴趣点，还应该包含补充详细的背景信息
- 如果没有相关内容，请报告'没有相关记忆'"""

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
            return tool_input.get("report", "")

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
                "description": f"提交回忆报告",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "report": {
                            "type": "string",
                            "description": f"回忆报告（Markdown 格式，≤ {FAST_RECALL_REPORT_LIMIT} 字）",
                        }
                    },
                    "required": ["report"],
                },
            }
        ]

        initial_prompt = f"""尝试快速从记忆库回忆与这个有关的信息：{interest}

重要限制：
- 你只能调用 list_memories 最多 {FAST_RECALL_MAX_SEARCH} 次
- 你只能调用 read_memory 最多 {FAST_RECALL_MAX_READ} 次
- 最终报告必须简洁，不超过 {FAST_RECALL_REPORT_LIMIT} 字

处理流程：
1. 精心设计关键词，调用 list_memories 搜索。关键词越多，能够覆盖的记忆越多。
2. 阅读最相关的最多 {FAST_RECALL_MAX_READ} 篇记忆
3. 提交报告（≤ {FAST_RECALL_REPORT_LIMIT} 字）
4. 如果没有相关内容，直接报告'没有相关记忆'
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
            return tool_input.get("report", "")

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
