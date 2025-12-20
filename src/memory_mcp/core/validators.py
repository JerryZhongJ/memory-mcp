"""记忆验证函数 - 数据验证层"""

import re
from dataclasses import dataclass
from typing import Iterable

from anthropic.types import ToolUnionParam
from rusty_results.prelude import Err, Ok, Result

from ..config import MAX_FILE_SIZE
from ..utils import llm


@dataclass(frozen=True)
class FailureHint:
    """带建议的错误类型"""

    message: str
    suggestion: str | None = None


def validate_keywords(keywords: Iterable[str]) -> Result[frozenset[str], FailureHint]:
    """验证 keywords 格式（非空，只能包含小写字母）"""
    keywords_list = list(keywords)

    if not keywords_list:
        return Err(FailureHint("Keywords 不能为空"))

    key = frozenset(keywords_list)
    errors = []

    for kw in key:
        if not kw:
            errors.append("包含空字符串")
        elif not kw.islower() or not kw.isalpha():
            errors.append(f"'{kw}' 包含非小写字母字符")

    if errors:
        error_msg = "Keywords 验证失败: " + "; ".join(errors)
        return Err(FailureHint(error_msg))

    return Ok(key)


def validate_content_size(content: str) -> Result[int, FailureHint]:
    """验证内容大小（≤ 1000 字，中文按字符计数，英文按单词计数）"""
    word_count = count_words_mixed(content)

    if word_count > MAX_FILE_SIZE:
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


async def validate_relevance(
    content: str, keywords: frozenset[str]
) -> Result[None, FailureHint]:
    """使用 LLM 验证内容与 keywords 的相关性"""
    final_tools: list[ToolUnionParam] = [
        {
            "name": "accept",
            "description": "判定记忆内容与关键词组高度相关",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "reject",
            "description": "判定记忆内容与关键词组不相关",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "不相关的原因",
                    }
                },
                "required": ["reason"],
            },
        },
    ]

    keywords_str = ", ".join(keywords)
    initial_prompt = f"""你判断给定的记忆内容是否与关键词组高度相关。

判断标准：
- 记忆内容应该主要讨论关键词组所描述的主题
- 关键词组应该能够准确概括记忆内容

关键词组：{keywords_str}
记忆内容：
{content}



请判断记忆内容是否与关键词组相关，并调用对应的工具：
- 如果相关，调用 accept 工具
- 如果不相关，调用 reject 工具并说明原因"""

    result = await llm.small_agent(
        initial_prompt=initial_prompt,
        tools=[],
        final=final_tools,
        maxIter=1,
        max_tokens=256,
    )

    if result is None:
        return Err(FailureHint("未知错误导致相关性验证失败"))

    tool_name, tool_input = result
    if tool_name == "accept":
        return Ok(None)
    elif tool_name == "reject":
        reason = tool_input.get("reason", "（未提供原因）")
        return Err(
            FailureHint(
                f"内容与关键词组不相关: {reason}",
                suggestion="重命名关键词组或者将不相关内容拆分出来",
            )
        )

    return Err(FailureHint("未知错误"))
