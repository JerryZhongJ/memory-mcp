"""测试 validators 模块的验证函数"""
import pytest
from src.memory_mcp.core.validators import (
    validate_keywords,
    validate_content_size,
    count_words_mixed,
    OperationResult
)


class TestCountWordsMixed:
    """测试中英文混合字数统计"""

    @pytest.mark.parametrize("content,expected", [
        # 正常计数
        ("Hello world this is a test", 6),  # 纯英文
        ("这是一个测试", 6),  # 纯中文：这、是、一、个、测、试
        ("这是 a test 测试", 6),  # 中英混合：4中文 + 2英文
        ("这有 123 个数字", 6),  # 含数字：5中文 + 1数字
        ("你好，世界！Hello, world!", 6),  # 含标点：4中文 + 2英文
        # 边界情况
        ("", 0),  # 空字符串
        ("   ", 0),  # 只有空格
        ("!@#$%^&*()", 0),  # 只有标点
    ])
    def test_count_words(self, content, expected):
        """测试各种内容的字数统计"""
        assert count_words_mixed(content) == expected


class TestValidateKeywords:
    """测试 keywords 验证函数"""

    def test_valid_keywords(self):
        """测试有效的 keywords"""
        result = validate_keywords(["test", "demo", "valid"])
        assert result.success
        assert result.value == frozenset(["test", "demo", "valid"])
        assert result.error is None

    @pytest.mark.parametrize("keywords,expected_error", [
        ([], "Keywords 不能为空"),
        (["Invalid"], "'Invalid'"),
        (["test123"], "'test123'"),
        (["valid", ""], "包含空字符串"),
        (["test-name"], "'test-name'"),
    ])
    def test_invalid_keywords_single_error(self, keywords, expected_error):
        """测试各种单一错误的 keywords"""
        result = validate_keywords(keywords)
        assert not result.success
        assert expected_error in result.error

    def test_multiple_errors_collected(self):
        """测试收集所有错误（不 fail fast）"""
        result = validate_keywords(["valid", "Invalid", "test123", ""])
        assert not result.success
        # 应该包含所有三种错误
        assert "包含空字符串" in result.error
        assert "'Invalid'" in result.error
        assert "'test123'" in result.error
        assert ";" in result.error  # 用分号分隔
        # 有效的关键词不应该出现在错误中
        assert "'valid'" not in result.error


class TestValidateContentSize:
    """测试内容大小验证函数"""

    @pytest.mark.parametrize("word_count,should_pass", [
        (0, True),      # 空内容
        (1, True),      # 单个单词
        (100, True),    # 正常内容
        (1000, True),   # 恰好等于限制
        (1001, False),  # 超过限制
    ])
    def test_content_size(self, word_count, should_pass):
        """测试各种大小的内容验证"""
        content = " ".join(["word"] * word_count)
        result = validate_content_size(content)

        if should_pass:
            assert result.success
            assert result.value == word_count
        else:
            assert not result.success
            assert "内容过长" in result.error
            assert f"{word_count} 字" in result.error


class TestOperationResult:
    """测试 OperationResult 类型"""

    def test_ok_variants(self):
        """测试成功结果的各种形式"""
        # 带值
        result_with_value = OperationResult.ok("test_value")
        assert result_with_value.success
        assert result_with_value.value == "test_value"
        assert result_with_value.error is None
        assert bool(result_with_value) is True

    def test_fail(self):
        """测试失败结果"""
        result = OperationResult.fail("error message")
        assert not result.success
        assert result.value is None
        assert result.error == "error message"
        assert bool(result) is False

    def test_unwrap_success(self):
        """测试成功结果的 unwrap"""
        result = OperationResult.ok("test_value")
        assert result.unwrap() == "test_value"

    def test_unwrap_on_failure_raises(self):
        """测试对失败结果调用 unwrap 会抛出异常"""
        result = OperationResult.fail("error message")
        with pytest.raises(ValueError, match="尝试对失败结果调用 unwrap.*error message"):
            result.unwrap()

    def test_unwrap_err_on_failure(self):
        """测试失败结果的 unwrap_err"""
        result = OperationResult.fail("error message")
        assert result.unwrap_err() == "error message"

    def test_unwrap_err_on_success_raises(self):
        """测试对成功结果调用 unwrap_err 会抛出异常"""
        result = OperationResult.ok("value")
        with pytest.raises(ValueError, match="尝试对成功结果调用 unwrap_err"):
            result.unwrap_err()


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
