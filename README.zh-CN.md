[English](README.md) | 简体中文

# Memory MCP

为 Claude Code 提供项目记忆管理的 MCP 服务器。

## 快速开始

### 前置要求

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器
- Anthropic API Key（从 [Anthropic Console](https://console.anthropic.com/) 获取）

### 方式一：使用 CLI 命令添加（推荐）

**从 GitHub 直接安装（无需下载）：**

```bash
# 添加到当前项目（本地作用域）
claude mcp add memory \
  --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uvx --from git+https://github.com/JerryZhongJ/memory-mcp.git memory-mcp --project $(pwd)
```

### 方式二：本地开发安装

如果你需要修改源码或参与开发：

```bash
# 1. 克隆仓库
git clone https://github.com/JerryZhongJ/memory-mcp.git
cd memory-mcp

# 2. 安装依赖
uv sync

# 3. 添加到 Claude Code
claude mcp add memory \
  --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv --directory /path/to/memory-mcp run memory-mcp --project $(pwd)
```

### 验证安装

配置完成后，Claude Code 会自动加载服务器。你可以使用以下命令验证：

```bash
# 查看所有已配置的 MCP 服务器
claude mcp list

# 在 Claude Code 中使用 /mcp 命令查看服务器状态
```

### 管理服务器

```bash
# 移除服务器
claude mcp remove memory

# 查看服务器详情
claude mcp get memory
```

## 工作原理

- 记忆以 Markdown 文件形式存储在项目的 `.memories` 目录
- 使用关键词进行智能匹配和检索
- LLM 自动决定创建新记忆或更新现有记忆
- 自动验证内容大小和相关性
- 前后端分离架构，后端自动管理生命周期

## 配置 CLAUDE.md

为了让 Claude 更好地使用这个 MCP 服务，建议在你的项目中创建 `.claude/CLAUDE.md` 文件，添加以下使用规则：

````markdown
# 项目记忆管理规则

## ⚠️ 强制规则（必须严格遵守）

### 1. 任务开始前必须查询记忆

**每次收到用户问题时，第一步必须使用 `recall_memory_tool` 查询相关信息。**

不要依赖判断来决定是否需要查询。任何问题都可能与已有记忆相关。

### 2. 发现新信息后必须立即保存

**每当你通过调查获得有价值的新信息，必须立即使用 `memorize_memory_tool` 保存。**

在发现信息的当时就保存，不要等到回答完用户问题。

**标准工作流程**：
```
用户提问 → 查询记忆 → 调查代码/文档 → 发现新信息 → 立即保存 → 回答用户
```

**重要**：跳过这些步骤会导致重复劳动、答案不一致、知识丢失。
````
## 许可证

MIT
