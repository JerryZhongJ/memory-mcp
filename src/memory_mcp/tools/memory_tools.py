"""Memory 工具类 - 所有工具的集中定义"""

from rusty_results.prelude import Err, Ok

from ..core.memory_registry import MemoryRegistry
from ..utils.llm import Tool


class ListMemoriesTool(Tool):
    """列出匹配的 memory"""

    def __init__(self, registry: MemoryRegistry):
        super().__init__(
            name="list_memories",
            description="列出与关键词匹配的记忆，每个记忆用一组关键词唯一标识",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键词列表（可选，为空则列出所有）",
                    }
                },
                "required": [],
            },
        )
        self.registry = registry

    async def execute(self, tool_input: dict) -> str:
        keywords: list[str] = tool_input.get("keywords", None)  # type: ignore
        if keywords:
            keywords_str = ", ".join(sorted(keywords))
        else:
            keywords_str = ""
        results = self.registry.list(keywords) if keywords else self.registry.list()

        if not results:
            return f"未找到匹配({keywords_str})的记忆"

        output = f"找到匹配({keywords_str}) {len(results)} 个记忆:\n"
        for idx, kw_set in enumerate(results[:10], start=1):
            keywords_str = ", ".join(sorted(kw_set))
            output += f"{idx}. {keywords_str}\n"

        if len(results) > 10:
            output += f"... 还有 {len(results) - 10} 个"

        return output


class ReadMemoryTool(Tool):
    """读取 memory 内容"""

    def __init__(self, registry: MemoryRegistry):
        super().__init__(
            name="read_memory",
            description="读取指定记忆的内容（用一组关键词唯一标识）",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "用来标识记忆的一组关键词",
                    }
                },
                "required": ["keywords"],
            },
        )
        self.registry = registry

    async def execute(self, tool_input: dict) -> str:
        keywords = tool_input.get("keywords", [])
        keywords_str = ", ".join(sorted(keywords))
        match self.registry.read(keywords):
            case Ok((keywords, content, version)):
                keywords_str = ", ".join(sorted(keywords))
                return f"""关键词组：{keywords_str}
版本号: {version}

{content}
"""
            case Err(e):
                error_msg = f"读取({keywords_str})的记忆失败: {e.message}"
                if e.suggestion:
                    error_msg += f"\n建议: {e.suggestion}"
                return error_msg


class CreateMemoryTool(Tool):
    """创建新的 memory"""

    def __init__(self, registry: MemoryRegistry):
        super().__init__(
            name="create_memory",
            description="创建新的记忆",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "用来标识记忆的一组关键词，每个关键词由小写字母和数字组成，且至少包含一个字母。",
                    },
                    "content": {
                        "type": "string",
                        "description": "记忆内容（Markdown 格式，≤ 1000 字）",
                    },
                },
                "required": ["keywords", "content"],
            },
        )
        self.registry = registry

    async def execute(self, tool_input: dict) -> str:
        keywords = tool_input.get("keywords", [])
        keywords_str = ", ".join(keywords)
        content = tool_input.get("content", "")

        match await self.registry.create(keywords, content):
            case Ok((keywords, content, version)):
                keywords_str = ", ".join(keywords)
                return f"✓ 成功创建记忆: ({keywords_str}), 版本号: {version}"
            case Err(e):
                error_msg = f"✗ 创建({keywords_str})的记忆失败: {e.message}"
                if e.suggestion:
                    error_msg += f"\n建议: {e.suggestion}"
                return error_msg


class UpdateMemoryTool(Tool):
    """更新现有 memory"""

    def __init__(self, registry: MemoryRegistry):
        super().__init__(
            name="update_memory",
            description="更新现有记忆",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "用来标识被更新记忆的关键词组",
                    },
                    "old_content": {
                        "type": "string",
                        "description": "被替换的内容（在该记忆中唯一出现）",
                    },
                    "new_content": {"type": "string", "description": "新的内容"},
                    "version": {
                        "type": "string",
                        "description": "记忆的版本号",
                    },
                },
                "required": ["keywords", "old_content", "new_content", "version"],
            },
        )
        self.registry = registry

    async def execute(self, tool_input: dict) -> str:
        keywords = tool_input.get("keywords", [])
        keywords_str = ", ".join(keywords)
        old_content = tool_input.get("old_content", "")
        new_content = tool_input.get("new_content", "")
        version = tool_input.get("version", "")

        result = await self.registry.update(keywords, old_content, new_content, version)

        match result:
            case Ok((keywords, content, new_version)):
                keywords_str = ", ".join(keywords)
                return f"✓ 成功更新记忆: ({keywords_str}), 新版本号: {new_version}"
            case Err(e):
                error_msg = f"✗ 更新({keywords_str})的记忆失败: {e.message}"
                if e.suggestion:
                    error_msg += f"\n建议: {e.suggestion}"
                return error_msg


class ReassignMemoryTool(Tool):
    """重命名 memory 的 keywords"""

    def __init__(self, registry: MemoryRegistry):
        super().__init__(
            name="reassign_memory",
            description="重命名记忆的关键词组（保持内容不变）",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要重命名的记忆的关键词组",
                    },
                    "new_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新的关键词组，每个关键词由小写字母和数字组成，且至少包含一个字母。",
                    },
                    "version": {
                        "type": "string",
                        "description": "记忆的版本号",
                    },
                },
                "required": ["keywords", "new_keywords", "version"],
            },
        )
        self.registry = registry

    async def execute(self, tool_input: dict) -> str:
        keywords = tool_input.get("keywords", [])
        keywords_str = ", ".join(sorted(keywords))
        new_keywords = tool_input.get("new_keywords", [])
        version = tool_input.get("version", "")

        result = await self.registry.reassign(keywords, new_keywords, version)

        match result:
            case Ok((new_keywords, content, new_version)):
                new_keywords_str = ", ".join(new_keywords)
                return f"✓ 成功重命名原 ({keywords_str}) 记忆为: ({new_keywords_str}), 新版本号: {new_version}"
            case Err(e):
                error_msg = f"✗ 重命名({keywords_str})失败: {e.message}"
                if e.suggestion:
                    error_msg += f"\n建议: {e.suggestion}"
                return error_msg
