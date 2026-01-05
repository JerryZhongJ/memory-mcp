English | [简体中文](README.zh-CN.md)

# Memory MCP

An MCP server that provides project memory management for Claude Code.

## Quick Start

### Prerequisites

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) package manager
- Anthropic API Key (get it from [Anthropic Console](https://console.anthropic.com/))

### Option 1: Install via CLI (Recommended)

**Install directly from GitHub (no download required):**

```bash
# Add to current project (local scope)
claude mcp add memory \
  --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uvx --from git+https://github.com/JerryZhongJ/memory-mcp.git memory-mcp --project $(pwd)
```

### Option 2: Local Development Installation

If you need to modify the source code or contribute to development:

```bash
# 1. Clone the repository
git clone https://github.com/JerryZhongJ/memory-mcp.git
cd memory-mcp

# 2. Install dependencies
uv sync

# 3. Add to Claude Code
claude mcp add memory \
  --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv --directory /path/to/memory-mcp run memory-mcp --project $(pwd)
```

### Verify Installation

After configuration, Claude Code will automatically load the server. You can verify with:

```bash
# List all configured MCP servers
claude mcp list

# Use /mcp command in Claude Code to check server status
```

### Manage Server

```bash
# Remove server
claude mcp remove memory

# View server details
claude mcp get memory
```

## How It Works

- Memories are stored as Markdown files in the project's `.memories` directory
- Uses intelligent keyword matching and retrieval
- LLM automatically decides whether to create new memories or update existing ones
- Automatically validates content size and relevance
- Frontend-backend separation architecture with automatic backend lifecycle management

## Configuring CLAUDE.md

To help Claude better use this MCP service, it's recommended to create a `.claude/CLAUDE.md` file in your project with the following usage rules:

```markdown
# Project Memory Management Rules

## ⚠️ Mandatory Rules (Must Be Strictly Followed)

### 1. Query Memory Before Starting Tasks

**Every time you receive a user question, the first step must be to use `recall_memory_tool` to query relevant information.**

Do not rely on judgment to decide whether to query. Any question may be related to existing memories.

### 2. Save New Information Immediately Upon Discovery

**Whenever you obtain valuable new information through investigation, you must immediately use `memorize_memory_tool` to save it.**

Save the information as soon as you discover it, don't wait until after answering the user's question.

**Standard Workflow**:
```
User Question → Query Memory → Investigate Code/Docs → Discover New Info → Save Immediately → Answer User
```

**Important**: Skipping these steps leads to duplicate work, inconsistent answers, and knowledge loss.
```
## License

MIT
