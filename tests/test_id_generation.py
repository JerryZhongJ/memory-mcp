"""测试确定性 ID 生成功能"""

import pytest

from memory_mcp.backend.core.memory_registry import MemoryRegistry


class TestDeterministicID:
    """测试确定性 ID 生成"""

    def test_same_input_same_id(self, tmp_path):
        """相同 keywords + content 生成相同 ID"""
        registry = MemoryRegistry(tmp_path)

        keywords = frozenset(["test", "demo"])
        content = "This is test content"

        id1 = registry._generate_id(keywords, content)
        id2 = registry._generate_id(keywords, content)

        assert id1 == id2

    def test_keyword_order_irrelevant(self, tmp_path):
        """keywords 顺序不影响 ID"""
        registry = MemoryRegistry(tmp_path)

        keywords1 = frozenset(["api", "design"])
        keywords2 = frozenset(["design", "api"])
        content = "Same content"

        id1 = registry._generate_id(keywords1, content)
        id2 = registry._generate_id(keywords2, content)

        assert id1 == id2

    def test_different_content_different_id(self, tmp_path):
        """content 变化 → ID 变化"""
        registry = MemoryRegistry(tmp_path)

        keywords = frozenset(["test"])
        content1 = "Content A"
        content2 = "Content B"

        id1 = registry._generate_id(keywords, content1)
        id2 = registry._generate_id(keywords, content2)

        assert id1 != id2

    def test_different_keywords_different_id(self, tmp_path):
        """keywords 变化 → ID 变化"""
        registry = MemoryRegistry(tmp_path)

        keywords1 = frozenset(["test"])
        keywords2 = frozenset(["demo"])
        content = "Same content"

        id1 = registry._generate_id(keywords1, content)
        id2 = registry._generate_id(keywords2, content)

        assert id1 != id2

    def test_id_format(self, tmp_path):
        """ID 格式为 8 字符哈希"""
        registry = MemoryRegistry(tmp_path)

        keywords = frozenset(["test"])
        content = "Test"

        id = registry._generate_id(keywords, content)

        assert len(id) == 8
        assert all(c in "0123456789abcdef" for c in id)

    def test_empty_content(self, tmp_path):
        """空 content 可以生成 ID"""
        registry = MemoryRegistry(tmp_path)

        keywords = frozenset(["test"])
        content = ""

        id = registry._generate_id(keywords, content)

        assert len(id) == 8


class TestIDPersistence:
    """测试 ID 持久性（跨 Registry 重启）"""

    def test_id_consistent_across_restart(self, tmp_path):
        """重启后 ID 保持一致"""
        # 第一次创建
        registry1 = MemoryRegistry(tmp_path)
        result = registry1.create(["test"], "Content")
        id1 = result.unwrap()

        # 模拟重启
        registry2 = MemoryRegistry(tmp_path)
        result = registry2.read(["test"])
        content, id2 = result.unwrap()

        assert id1 == id2  # 确定性 ID

    def test_update_changes_id(self, tmp_path):
        """update 后 ID 变化"""
        registry = MemoryRegistry(tmp_path)

        # 创建
        result = registry.create(["test"], "Original")
        original_id = result.unwrap()

        # 更新
        result = registry.update(original_id, "Original", "Updated")
        new_id = result.unwrap()

        assert original_id != new_id  # ID 应该变化

    def test_reassign_changes_id(self, tmp_path):
        """reassign 后 ID 变化，旧 memory 被删除"""
        registry = MemoryRegistry(tmp_path)

        # 创建
        result = registry.create(["test"], "Content")
        original_id = result.unwrap()

        # 重命名
        result = registry.reassign(original_id, ["renamed"])
        new_id = result.unwrap()

        # ID 应该变化（因为 keywords 变了）
        assert original_id != new_id

        # 旧 keywords 应该不存在
        old_result = registry.read(["test"])
        assert not old_result.success

        # 新 keywords 应该存在
        new_result = registry.read(["renamed"])
        assert new_result.success
        content, id = new_result.unwrap()
        assert content == "Content"
        assert id == new_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
