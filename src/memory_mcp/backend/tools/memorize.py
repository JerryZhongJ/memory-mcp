"""Memorize 工具 - 将信息记忆到知识库"""

from anthropic.types import ToolUnionParam

from ..core.memory_registry import MemoryRegistry
from ..llm import small_agent
from ..logger import logger
from .memory_tools import (
    CreateMemoryTool,
    ListMemoriesTool,
    ReadMemoryTool,
    UpdateMemoryTool,
)


async def memorize_memory(content: str, registry: MemoryRegistry):
    """使用 small_agent 实现的保存流程"""
    logger.info(f"[Memorize] Content length: {len(content)} chars")

    try:
        list_tool = ListMemoriesTool(registry)
        read_tool = ReadMemoryTool(registry)
        create_tool = CreateMemoryTool(registry)
        update_tool = UpdateMemoryTool(registry)

        final_tools: list[ToolUnionParam] = [
            {
                "name": "done",
                "description": "完成所有保存操作",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "操作摘要（已创建/更新了哪些记忆）",
                        }
                    },
                    "required": ["summary"],
                },
            }
        ]

        initial_prompt = f"""把以下内容保存到记忆库中：

{content}

---------
请按以下指导处理：
1. 使用 list_memories 搜索相似的现有记忆
2. 使用 read_memory 读取相关记忆
3. 决定并执行操作（可以多次）：
   - 调用 update_memory 把新内容合并到现有记忆中
   - 调用 create_memory 创建新的记忆
4. 完成所有操作后，调用 done

**重要原则**：
- 每个记忆 ≤ 1000 字
- 关键词组：每个关键词由小写字母和数字组成，且至少包含一个字母。关键词组准确描述内容。
- 细节很重要：请不要丢失任何细节，除了下面提到的冗余代码和引用段落。
- 避免冗余代码和引用段落：如果已知代码和引用段落的获取方式（如源代码位置、URL等），请只保留获取方式即可。

**工具会返回成功或失败消息**，请根据反馈调整"""

        result = await small_agent(
            initial_prompt=initial_prompt,
            tools=[list_tool, read_tool, create_tool, update_tool],
            final=final_tools,
            maxIter=20,
        )

        if result is None:
            logger.warning(f"[Memorize] Timeout, content length: {len(content)}")
            return

        tool_name, tool_input = result

        if tool_name == "done":
            summary = tool_input.get("summary", "")
            logger.info(f"[Memorize] Completed")
            return

        logger.warning(f"[Memorize] Unknown result, content length: {len(content)}")
        return

    except Exception as e:
        logger.error(f"[Memorize] Failed: {e}", exc_info=True)
        raise
