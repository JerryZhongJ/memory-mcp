"""MCP 服务器入口"""

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import FrontendClient

load_dotenv()

_client: FrontendClient = None  # type: ignore


@asynccontextmanager
async def lifespan(app):
    """服务器生命周期管理：启动时初始化后端"""
    # 启动时：积极启动后端
    await _client.start()
    yield
    # 关闭时：清理资源
    await _client.close()


mcp = FastMCP("memory-mcp", lifespan=lifespan)


@mcp.tool()
async def recall_memory_tool(interest: str, deep: bool = False) -> str:
    """从项目记忆中回忆相关信息

    Args:
        interest: 想要回忆的任何东西，可以是一句陈述、一个问题。
        deep: 是否使用深度模式（默认 False）
              - False: 反应快速，报告简洁
              - True: 耗时较长，但报告更全面
    """
    return await _client.recall(interest, deep=deep)


@mcp.tool()
async def memorize_memory_tool(content: str) -> str:
    """记住一些内容

    Args:
        content: 要记住的内容。可以是一句话、一段文字甚至更长的文本。
    """
    await _client.memorize(content)
    return "内容正在后台记忆中"


@mcp.tool()
async def set_backend_log_level_tool(level: str) -> str:
    """设置后端日志级别（用于调试）

    Args:
        level: 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL, DISABLE
    """
    try:
        message = await _client.set_log_level(level)
        return message
    except Exception as e:
        return f"设置日志级别失败: {str(e)}"


def main():
    """MCP 服务器入口函数"""
    parser = argparse.ArgumentParser(description="Memory MCP Server (Frontend)")
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

    global _client
    project_root = args.project.resolve()
    _client = FrontendClient(project_root)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
