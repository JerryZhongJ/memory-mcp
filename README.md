# Memory MCP

为 Claude Desktop 提供项目记忆管理的 MCP 服务器。

## 快速开始（推荐）

### 方式一：直接从 GitHub 使用（无需下载）

编辑 Claude Desktop 配置文件：
- Linux/Mac: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

添加配置：

```json
{
  "mcpServers": {
    "memory": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/your-username/memory-mcp.git",
        "memory-mcp",
        "--project",
        "/path/to/your/project"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-xxx"
      }
    }
  }
}
```

**优势**：
- ✅ 无需手动下载和安装
- ✅ 自动使用最新版本
- ✅ 自动管理依赖

### 方式二：本地安装

#### 前置要求

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器
- Anthropic API Key

#### 安装步骤

```bash
git clone https://github.com/your-username/memory-mcp.git
cd memory-mcp
uv sync
```

#### 配置 Claude Desktop

```json
{
  "mcpServers": {
    "memory": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/memory-mcp",
        "run",
        "memory-mcp",
        "--project",
        "/path/to/your/project"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-xxx"
      }
    }
  }
}
```

### 获取 API Key

在 [Anthropic Console](https://console.anthropic.com/) 获取 API Key。

### 重启 Claude Desktop

配置完成后重启 Claude Desktop 加载服务器。

## 工作原理

- 记忆以 Markdown 文件形式存储在项目的 `.memories` 目录
- 使用关键词进行智能匹配和检索
- LLM 自动决定创建新记忆或更新现有记忆
- 自动验证内容大小和相关性
- 前后端分离架构，后端自动管理生命周期

## 许可证

MIT
