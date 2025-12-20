"""MCP 服务器入口"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .core.memory_registry import MemoryRegistry
from .tools.memorize import memorize_memory
from .tools.recall import recall_memory

load_dotenv()

mcp = FastMCP("memory-mcp")
_registry: MemoryRegistry = None  # type: ignore


@mcp.tool()
async def recall_memory_tool(interest: str) -> str:
    """从项目记忆中回忆相关信息

    Args:
        interest: 想要回忆的任何东西，可以是一句陈述、一个问题甚至是关键词
    """
    return await recall_memory(interest, _registry)


@mcp.tool()
async def memorize_memory_tool(content: str) -> str:
    """记住一些内容

    Args:
        content: 要记住的内容。可以是一句话、一段文字甚至更长的文本。
    """
    asyncio.create_task(memorize_memory(content, _registry))
    return "内容正在后台记忆中"


def main():
    """MCP 服务器入口函数"""
    parser = argparse.ArgumentParser(description="Memory MCP Server")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="项目根目录（默认：当前工作目录）",
    )
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        print(
            "错误: 未设置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 环境变量",
            file=sys.stderr,
        )
        print(
            "请在 .env 文件或 Claude Desktop 配置中设置 ANTHROPIC_API_KEY 和 ANTHROPIC_AUTH_TOKEN",
            file=sys.stderr,
        )
        sys.exit(1)

    global _registry
    _registry = MemoryRegistry(args.project)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
