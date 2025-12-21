"""Recall 工具 - 从记忆中召回信息"""

from anthropic.types import ToolUnionParam

from ..core.memory_registry import MemoryRegistry
from ..llm import small_agent
from ..logger import logger
from .memory_tools import ListMemoriesTool, ReadMemoryTool


async def recall_memory(interest: str, registry: MemoryRegistry) -> str:
    """使用 small_agent 实现的回忆流程"""
    logger.info(f"[Recall] Query: {interest}")

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
            maxIter=10,
        )

        if result is None:
            logger.warning(f"[Recall] Timeout for query: {interest}")
            return "查询超时，未能生成报告"

        tool_name, tool_input = result
        if tool_name == "submit":
            logger.info(f"[Recall] Completed for: {interest}")
            return tool_input.get("report", "")

        logger.warning(f"[Recall] Unknown result for query: {interest}")
        return "未知错误"

    except Exception as e:
        logger.error(f"[Recall] Failed: {e}", exc_info=True)
        raise
