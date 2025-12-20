# Memory MCP

为 Claude Desktop 提供项目记忆管理的 MCP 服务器。

## 安装

### 前置要求

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器
- Anthropic API Key

### 安装步骤

```bash
git clone <repository-url>
cd memory-mcp
uv sync
```

## 配置

### 1. 获取 API Key

在 [Anthropic Console](https://console.anthropic.com/) 获取 API Key。

### 2. 配置 Claude Desktop

编辑配置文件：
- Linux/Mac: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

单项目配置：

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

多项目配置：

```json
{
  "mcpServers": {
    "memory-project-a": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/memory-mcp",
        "run", "memory-mcp",
        "--project", "/path/to/project-a"
      ],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-xxx" }
    },
    "memory-project-b": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/memory-mcp",
        "run", "memory-mcp",
        "--project", "/path/to/project-b"
      ],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-xxx" }
    }
  }
}
```

### 3. 重启 Claude Desktop

配置完成后重启 Claude Desktop 加载服务器。

## 工作原理

- 记忆以 Markdown 文件形式存储在项目目录
- 使用关键词进行智能匹配和检索
- LLM 自动决定创建新记忆或更新现有记忆
- 自动验证内容大小和相关性

## 许可证

MIT
