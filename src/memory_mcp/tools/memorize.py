"""Memorize 工具 - 将信息记忆到知识库"""

from anthropic.types import ToolUnionParam

from ..core.memory_registry import MemoryRegistry
from ..utils.llm import small_agent
from .memory_tools import (
    CreateMemoryTool,
    ListMemoriesTool,
    ReadMemoryTool,
    UpdateMemoryTool,
)


async def memorize_memory(content: str, registry: MemoryRegistry) -> str:
    """使用 small_agent 实现的保存流程"""
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

**重要约束**：
- 每个记忆 ≤ 1000 字
- Keywords：小写字母，准确反映主题


**更新时**：
- 融合新旧内容，避免重复
- 保持内容完整性和连贯性

**创建时**：
- 内容应独立、完整
- Keywords 应准确、简洁

**工具会返回成功或失败消息**，请根据反馈调整"""

    result = await small_agent(
        initial_prompt=initial_prompt,
        tools=[list_tool, read_tool, create_tool, update_tool],
        final=final_tools,
        maxIter=10,
    )

    if result is None:
        return "保存超时，未能完成操作"

    tool_name, tool_input = result

    if tool_name == "done":
        summary = tool_input.get("summary", "")
        return f"✓ 操作完成\n\n{summary}"

    return "未知错误"
