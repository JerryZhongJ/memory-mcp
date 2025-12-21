"""记忆验证函数 - 数据验证层"""

import re
from dataclasses import dataclass
from typing import Iterable

from anthropic.types import ToolUnionParam
from rusty_results.prelude import Err, Ok, Result

from .. import llm
from ..config import MAX_FILE_SIZE
from ..logger import logger


@dataclass(frozen=True)
class FailureHint:
    """带建议的错误类型"""

    message: str
    suggestion: str | None = None


def validate_keywords(keywords: Iterable[str]) -> Result[frozenset[str], FailureHint]:
    """验证 keywords 格式（非空，由小写字母和数字组成，且至少包含一个字母）"""
    keywords_list = list(keywords)

    if not keywords_list:
        return Err(FailureHint("Keywords 不能为空"))

    key = frozenset(keywords_list)
    errors = []

    for kw in key:
        if not kw:
            errors.append("包含空字符串")
        elif not (kw.isalnum() and kw.islower() and any(c.isalpha() for c in kw)):
            errors.append(f"'{kw}' 必须由小写字母和数字组成，且至少包含一个字母")

    if errors:
        error_msg = "Keywords 验证失败: " + "; ".join(errors)
        logger.warning(f"[Validate:Keywords] Failed: {'; '.join(errors)}")
        return Err(FailureHint(error_msg))

    return Ok(key)


def validate_content_size(content: str) -> Result[int, FailureHint]:
    """验证内容大小（≤ 1000 字，中文按字符计数，英文按单词计数）"""
    word_count = count_words_mixed(content)

    if word_count > MAX_FILE_SIZE:
        logger.warning(f"[Validate:Size] Exceeded: {word_count} > {MAX_FILE_SIZE}")
        return Err(
            FailureHint(
                f"内容过长：{word_count} 字，超过限制 {MAX_FILE_SIZE} 字",
                suggestion="将内容拆分为多个较短的记忆",
            )
        )

    return Ok(word_count)


def count_words_mixed(content: str) -> int:
    """计算中英文混合内容的字数（中文按字符，英文/数字按单词）"""
    chinese_count = sum(1 for char in content if "\u4e00" <= char <= "\u9fff")

    text_without_chinese = re.sub(r"[\u4e00-\u9fff]", " ", content)
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text_without_chinese)
    english_count = len(words)

    return chinese_count + english_count


async def validate_semantics(
    content: str, keywords: frozenset[str]
) -> Result[None, FailureHint]:
    """使用 LLM 验证内容的语义质量（相关性 + 避免冗余的代码片段）"""
    final_tools: list[ToolUnionParam] = [
        {
            "name": "accept",
            "description": "判定记忆内容合格",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "reject",
            "description": "判定记忆内容不合格",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "拒绝的具体原因",
                    }
                },
                "required": ["reason"],
            },
        },
    ]

    keywords_str = ", ".join(keywords)
    initial_prompt = f"""你需要判断给定的记忆内容是否符合质量要求。

检查两个方面：

1. **相关性**：内容是否与关键词组高度相关，关键词组能否完整且准确概括记忆内容。

2. **避免冗余**：检查是否存在可以省略的冗余代码片段或引用段落。
   - 如果某个代码片段或引用段落**已经提供了获取方式**（如源代码位置、URL、文献引用等），那么该代码/段落本身就是冗余的。
   - 简短的代码示例（1-3行）或关键引用可以保留，但大段代码/长篇引用配上对应的获取方式时，就应该只留获取方式


关键词组：{keywords_str}

记忆内容：
{content}

请判断内容是否合格，并调用对应的工具：
- 如果合格（相关且无冗余），调用 accept
- 如果不合格，调用 reject 并给出具体原因"""

    result = await llm.small_agent(
        initial_prompt=initial_prompt,
        tools=[],
        final=final_tools,
        maxIter=1,
    )

    if result is None:
        logger.error(f"[Validate:Semantics] LLM timeout for: {sorted(keywords)}")
        return Err(FailureHint("未知错误导致语义验证失败"))

    tool_name, tool_input = result
    if tool_name == "accept":
        return Ok(None)
    elif tool_name == "reject":
        reason = tool_input.get("reason", "（未提供原因）")
        logger.warning(
            f"[Validate:Semantics] Rejected for {sorted(keywords)}: {reason}"
        )

        return Err(
            FailureHint(
                f"内容不符合要求: {reason}",
                suggestion="如果是相关性问题，可以重命名关键词组或者将不相关内容拆分出来；如果是冗余代码和引用段落，可以将其替换为源代码位置、URL或其他获取方式。",
            )
        )

    return Err(FailureHint("未知错误"))
