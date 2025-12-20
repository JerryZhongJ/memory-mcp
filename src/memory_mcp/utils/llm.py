"""LLM 交互工具函数"""

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolUnionParam

from ..config import ANTHROPIC_API_KEY, DEFAULT_MODEL

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class Tool:
    """工具基类

    子类需要重载 execute() 方法来实现具体的工具逻辑。

    Example:
        class SearchTool(Tool):
            def __init__(self, registry):
                super().__init__(
                    name="search_similar",
                    description="搜索相似的 memory 文件",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["keywords"]
                    }
                )
                self.registry = registry

            def execute(self, tool_input: dict) -> str:
                keywords = tool_input.get("keywords", [])
                results = self.registry.list(keywords)
                return f"找到 {len(results)} 个相似文件"
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
    return await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
        tools=tools,
    )


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
    # 1. 构建工具名称到对象的映射（仅包含可执行工具）
    tool_map = {tool.name: tool for tool in tools}

    # 2. 转换为 Anthropic API 格式（包含所有 final 工具）
    anthropic_tools: list[ToolUnionParam] = [
        tool.to_anthropic_tool() for tool in tools
    ] + final

    # 3. 提取所有 final 工具名称（用于快速检测）
    final_names = {f["name"] for f in final}

    # 4. 构建 system prompt
    final_tools_desc = "\n".join(f"- {f['name']}: {f['description']}" for f in final)  # type: ignore
    system_prompt = f"""你是一个智能助手，可以使用提供的工具来完成任务。

当你准备好给出最终答案时，调用以下工具之一：
{final_tools_desc}

可用工具：
{chr(10).join(f"- {tool.name}: {tool.description}" for tool in tools)}
"""

    # 5. 初始化消息历史（initial_prompt 作为第一个 user 消息）
    messages: list[MessageParam] = [{"role": "user", "content": initial_prompt}]

    # 6. 迭代循环
    for iteration in range(maxIter):
        # 6.1 调用 LLM（异步）
        response = await continue_conversation(
            system_prompt=system_prompt,
            messages=messages,
            tools=anthropic_tools,
            model=model,
            max_tokens=max_tokens,
        )

        # 6.2 更新消息历史
        messages.append({"role": "assistant", "content": response.content})

        # 6.3 提取工具调用
        tool_calls = extract_tool_calls(response)

        # 6.4 检查是否有工具调用
        if not tool_calls:
            # LLM 没有调用工具，继续下一轮
            continue

        # 6.5 检查是否调用了任何 final 工具
        for call in tool_calls:
            if call["name"] in final_names:
                # 找到 final 工具，立即返回工具名和参数
                return (call["name"], call["input"])

        # 6.6 执行非 final 工具（异步）
        tool_results = []
        for call in tool_calls:
            tool_name = call["name"]
            tool_input = call["input"]

            # 获取工具对象（final 工具不在 tool_map 中，但已经在上面处理过了）
            tool = tool_map.get(tool_name)
            if tool is None:
                # 工具不存在（理论上不应该发生，因为 LLM 只能调用我们提供的工具）
                result = f"错误：工具 '{tool_name}' 不存在"
            else:
                # 执行工具（异步）
                try:
                    result = await tool.execute(tool_input)
                except Exception as e:
                    result = f"工具执行失败: {str(e)}"

            # 构建 tool_result 消息
            tool_results.append(
                {"type": "tool_result", "tool_use_id": call["id"], "content": result}
            )

        # 6.7 添加 tool_result 到消息历史（作为 user 消息，满足 API 要求）
        messages.append({"role": "user", "content": tool_results})

    # 7. 达到最大迭代次数，返回 None
    return None
