"""LLM 交互工具函数"""

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolUnionParam

from .config import DEFAULT_MODEL
from .logger import logger

client = AsyncAnthropic()


class Tool:
    """工具基类

    子类需要重载 execute() 方法来实现具体的工具逻辑。
    """

    def __init__(self, name: str, description: str, input_schema: dict):
        """初始化工具

        Args:
            name: 工具名称（唯一标识符）
            description: 工具描述（告诉 LLM 何时使用此工具）
            input_schema: 输入参数的 JSON Schema 定义
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema

    async def execute(self, tool_input: dict) -> str:
        """执行工具逻辑（子类必须重载）

        Args:
            tool_input: LLM 提供的工具输入参数

        Returns:
            工具执行结果（字符串形式，将返回给 LLM）

        Raises:
            NotImplementedError: 如果子类未重载此方法
        """
        raise NotImplementedError(f"Tool '{self.name}' 必须实现 execute() 方法")

    def to_anthropic_tool(self) -> ToolUnionParam:
        """转换为 Anthropic API 需要的工具格式

        Returns:
            符合 Anthropic API 格式的工具定义字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def extract_tool_calls(response: anthropic.types.Message) -> list[dict]:
    """从响应中提取所有工具调用

    Args:
        response: LLM 响应对象

    Returns:
        工具调用列表，每项包含 name, input, id
    """
    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append(
                {"name": block.name, "input": block.input, "id": block.id}
            )
    return tool_calls


def _log_conversation_history(messages: list[MessageParam], reason: str) -> None:
    """打印完整的对话历史（DEBUG 级别）

    Args:
        messages: 消息历史列表
        reason: 打印原因（如 'completed' 或 'timeout'）
    """
    logger.debug(f"[Agent] {reason.capitalize()} - Full conversation ({len(messages)} messages):")
    for i, msg in enumerate(messages):
        role = msg["role"]
        content = msg["content"]
        logger.debug(f"  Message [{i}] ({role}):")
        logger.debug(f"    {content}")


async def continue_conversation(
    system_prompt: str,
    messages: list[MessageParam],
    tools: list[ToolUnionParam],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> anthropic.types.Message:
    """继续多轮对话

    Args:
        system_prompt: 系统提示
        messages: 消息历史
        tools: 工具定义列表
        model: 模型名称
        max_tokens: 最大 token 数

    Returns:
        LLM 响应对象
    """
    try:
        return await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )
    except anthropic.RateLimitError as e:
        logger.warning(f"[LLM] Rate limited: {e}")
        raise
    except anthropic.APIConnectionError as e:
        logger.error(f"[LLM] Connection error: {e}")
        raise
    except anthropic.APIError as e:
        logger.error(f"[LLM] API error: {e}")
        raise


async def small_agent(
    initial_prompt: str,
    tools: list[Tool],
    final: list[ToolUnionParam],
    maxIter: int,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> tuple[str, dict] | None:
    """小型 Agent 循环：多轮工具调用直到达到 final 工具或超时

    Args:
        initial_prompt: 初始 prompt（用户消息）
        tools: Tool 对象列表（不包括 final 工具）
        final: final 工具列表（Anthropic 工具格式）
        maxIter: 最大迭代轮数
        model: 模型名称
        max_tokens: 最大 token 数

    Returns:
        成功时返回 (tool_name, tool_input) 元组，超时返回 None
    """
    tool_map = {tool.name: tool for tool in tools}

    anthropic_tools: list[ToolUnionParam] = [
        tool.to_anthropic_tool() for tool in tools
    ] + final

    final_names = {f["name"] for f in final}

    final_tools_desc = "\n".join(f"- {f['name']}: {f['description']}" for f in final)  # type: ignore
    tools_desc = chr(10).join(f"- {tool.name}: {tool.description}" for tool in tools) if tools else "无"

    system_prompt = f"""你是一个智能助手，可以使用提供的工具来完成任务。

你最多有 {maxIter} 轮机会来完成任务。每轮你可以调用工具，然后获得结果。

当你准备好给出最终答案时，调用以下工具之一：
{final_tools_desc}

可用工具：
{tools_desc}
"""

    messages: list[MessageParam] = [{"role": "user", "content": initial_prompt}]

    for iteration in range(maxIter):
        response = await continue_conversation(
            system_prompt=system_prompt,
            messages=messages,
            tools=anthropic_tools,
            model=model,
            max_tokens=max_tokens,
        )

        messages.append({"role": "assistant", "content": response.content})

        tool_calls = extract_tool_calls(response)

        if not tool_calls:
            continue

        for call in tool_calls:
            if call["name"] in final_names:
                _log_conversation_history(messages, f"completed (final tool: {call['name']})")
                return (call["name"], call["input"])

        tool_results = []
        for call in tool_calls:
            tool_name = call["name"]
            tool_input = call["input"]

            tool = tool_map.get(tool_name)
            if tool is None:
                result = f"错误：工具 '{tool_name}' 不存在"
            else:
                try:
                    result = await tool.execute(tool_input)
                except Exception as e:
                    result = f"工具执行失败: {str(e)}"

            tool_results.append(
                {"type": "tool_result", "tool_use_id": call["id"], "content": result}
            )

        messages.append({"role": "user", "content": tool_results})

    _log_conversation_history(messages, "timeout")
    return None
