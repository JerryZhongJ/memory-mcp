"""记忆注册表 - 数据访问层（Repository Pattern）"""

import asyncio
import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from rusty_results.prelude import Err, Ok, Result

from ... import file_manager
from ..config import MEMORIES_DIR_NAME
from ..logger import logger
from . import matcher
from .validators import (
    FailureHint,
    validate_content_size,
    validate_keywords,
    validate_semantics,
)


class Memory:
    """Memory 状态封装：keywords(不可变主键), content(可变), version(自动维护), lock(异步锁)

    - 文件 I/O 由 Memory 自己管理
    - 延迟加载：首次访问 content/version 时才从文件读取
    """

    def __init__(self, keywords: frozenset[str], project_root: Path):
        """创建 Memory 对象（不做验证，只设置字段）

        验证应在工厂方法 Memory.create() 中完成。
        """
        self._keywords = keywords
        self._project_root = project_root
        self._loaded = False
        self._content: str | None = None
        self._version: str | None = None
        self.lock = asyncio.Lock()

    @property
    def keywords(self) -> frozenset[str]:
        return self._keywords

    @property
    def content(self) -> str:
        if not self._loaded:
            self._load_from_file()
        return self._content  # type: ignore

    async def set_content(self, new_content: str) -> Result[None, FailureHint]:
        """设置新内容，自动验证大小、相关性并写入文件"""
        match validate_content_size(new_content):
            case Err(e):
                return Err(e)

        match await validate_semantics(new_content, self._keywords):
            case Err(e):
                return Err(e)

        self._content = new_content
        self._version = self._generate_version()
        self._loaded = True
        self._save_to_file()

        return Ok(None)

    @property
    def version(self) -> str:
        if not self._loaded:
            self._load_from_file()
        return self._version  # type: ignore

    def snapshot(self) -> "MemorySnapShot":
        """获取 Memory 的快照对象"""
        return MemorySnapShot(
            keywords=self.keywords,
            content=self.content,
            version=self.version,
        )

    def check_version(self, version: str) -> Result[None, FailureHint]:
        if self.version == version:
            return Ok(None)
        else:
            return Err(
                FailureHint(
                    "version 不匹配或者已过期",
                    suggestion="检查 version 是否正确或者重新读取该记忆获取最新版本号",
                )
            )

    def _generate_version(self) -> str:
        """生成 version（keywords + content 的 SHA256 前 8 位）"""
        sorted_keywords = sorted(self._keywords)
        keywords_str = "-".join(sorted_keywords)
        combined = f"{keywords_str}|{self._content}"
        hash_obj = hashlib.sha256(combined.encode("utf-8"))
        return hash_obj.hexdigest()[:8]

    def _get_file_path(self) -> Path:
        sorted_keywords = sorted(self._keywords)
        filename = "-".join(sorted_keywords) + ".md"
        return self._project_root / MEMORIES_DIR_NAME / filename

    def _load_from_file(self) -> None:
        file_path = self._get_file_path()
        self._content = file_manager.read_file(file_path)
        self._version = self._generate_version()
        self._loaded = True

    def _save_to_file(self) -> None:
        if not self._loaded:
            return
        file_path = self._get_file_path()
        file_manager.write_file(file_path, self._content)  # type: ignore

    def delete_file(self) -> None:
        file_path = self._get_file_path()
        file_path.unlink(missing_ok=True)

    @classmethod
    async def create(
        cls, keywords: Iterable[str], content: str, project_root: Path
    ) -> Result["Memory", FailureHint]:
        """创建新 Memory 的工厂方法（包含完整验证：keywords, content 大小, LLM 相关性）"""

        match Memory.create_lazy(keywords, project_root):
            case Err(e):
                return Err(e)
            case Ok(memory):
                pass

        match validate_content_size(content):
            case Err(e):
                return Err(e)

        match await validate_semantics(content, memory.keywords):
            case Err(e):
                return Err(e)

        memory._content = content
        memory._version = memory._generate_version()
        memory._loaded = True
        memory._save_to_file()

        return Ok(memory)

    @classmethod
    def create_lazy(
        cls, keywords: Iterable[str], project_root: Path
    ) -> Result["Memory", FailureHint]:
        """创建新 Memory 的工厂方法（仅验证 keywords）"""

        match validate_keywords(keywords):
            case Err(e):
                return Err(e)
            case Ok(key):
                pass

        memory = cls(key, project_root)
        return Ok(memory)


class MemorySnapShot(NamedTuple):
    keywords: frozenset[str]
    content: str
    version: str


def extract_keywords_from_filename(name: str) -> frozenset:
    """从文件名提取 keywords set

    Args:
        filename: 文件名（例如 "api-design-patterns"）

    Returns:
        keywords 的 frozenset（无顺序）
    """

    # 按连字符分割
    keywords = name.split("-")
    # 返回 frozenset（无顺序，可哈希）
    return frozenset(keywords)


class MemoryRegistry:
    """记忆注册表 - 数据访问层

    - Memory 对象封装 keywords, content, version, lock
    - 每个 memory 有自己的锁（细粒度并发）
    - _registry_lock 保护 _memories 字典的增删改
    - 写入立即持久化
    - keywords 用于定位 memory（主键），version 用于乐观锁检查
    """

    def __init__(self, project_root: Path):
        self._project_root = project_root
        self._memories: dict[frozenset[str], Memory] = {}
        self._registry_lock = asyncio.Lock()
        self._load_metadata()

    def _load_metadata(self) -> None:
        """从文件系统加载元数据并创建 Memory 对象（延迟加载）"""
        names = file_manager.list_markdown_names(self._project_root / MEMORIES_DIR_NAME)
        for name in names:
            keywords = extract_keywords_from_filename(name)
            match Memory.create_lazy(keywords, self._project_root):
                case Ok(memory):
                    self._memories[keywords] = memory
                case Err(_):
                    continue

    def _find_memory(
        self, keywords: Iterable[str]
    ) -> Result[tuple[frozenset[str], Memory], FailureHint]:
        """查找 memory（不验证 keywords 格式，用于 read/update/reassign/delete）"""
        key = frozenset(keywords)
        if key not in self._memories:
            return Err(
                FailureHint(
                    "Memory 不存在",
                    suggestion="确认提供的关键词组是否正确且完整。可以先列出记忆来查看它们的关键词组。",
                )
            )
        return Ok((key, self._memories[key]))

    def read(self, keywords: Iterable[str]) -> Result[MemorySnapShot, FailureHint]:
        """读取 memory 的 content 和 version"""
        match self._find_memory(keywords):
            case Err(e):
                logger.warning(f"[Read] Not found: {sorted(keywords)}")
                return Err(e)
            case Ok((key, memory)):
                pass

        logger.info(f"[Read] Success: {sorted(keywords)}")
        return Ok(memory.snapshot())

    def list(self, keywords: Iterable[str] | None = None) -> list[frozenset[str]]:
        """列出所有或匹配指定关键词的 memory（按匹配度排序）"""
        if keywords is None:
            result = list(self._memories.keys())
            logger.info(f"[List] All memories: {len(result)} found")
            return result

        query_keywords = list(keywords)
        scored_keywords = []

        for file_keywords in self._memories.keys():
            score = matcher.score_match(query_keywords, file_keywords)
            if score > 0:
                scored_keywords.append((file_keywords, score))

        scored_keywords.sort(key=lambda x: x[1], reverse=True)
        result = [kw for kw, _ in scored_keywords]
        logger.info(f"[List] Query: {sorted(query_keywords)}, matched: {len(result)}")
        return result

    async def create(
        self,
        keywords: Iterable[str],
        content: str,
    ) -> Result[MemorySnapShot, FailureHint]:
        """创建新 memory（返回 version）"""

        match await Memory.create(keywords, content, self._project_root):
            case Err(e):
                logger.warning(f"[Create] Validation failed: {e.message}")
                return Err(e)
            case Ok(memory):
                pass

        keywords = memory.keywords
        async with self._registry_lock:
            if keywords in self._memories:
                logger.warning(f"[Create] Keywords already exist: {sorted(keywords)}")
                return Err(
                    FailureHint(
                        "Memory 已存在",
                        suggestion="使用不同的关键词组或者直接更新现有记忆（更新记忆之前需要先读取它）",
                    )
                )
            self._memories[keywords] = memory
            logger.info(
                f"[Create] Success: {sorted(keywords)}, version={memory.version}"
            )

            return Ok(memory.snapshot())

    async def update(
        self,
        keywords: Iterable[str],
        old_content: str,
        new_content: str,
        version: str,
    ) -> Result[MemorySnapShot, FailureHint]:
        """部分更新 memory（old_content 必须在文件中唯一匹配，返回新 version）"""
        match self._find_memory(keywords):
            case Err(e):
                logger.warning(f"[Update] Not found: {sorted(keywords)}")
                return Err(e)
            case Ok((key, memory)):
                pass

        async with memory.lock:
            match memory.check_version(version):
                case Err(e):
                    logger.warning(
                        f"[Update] Version mismatch: {sorted(keywords)}, "
                        f"expected={version}, actual={memory.version}"
                    )
                    return Err(e)

            current_content = memory.content
            count = current_content.count(old_content)
            if count == 0:
                logger.warning(f"[Update] Content not found: {sorted(keywords)}")
                return Err(
                    FailureHint(
                        "找不到要替换的内容",
                        suggestion="检查要被替换的内容与记忆中的内容完全一致",
                    )
                )
            elif count > 1:
                logger.warning(
                    f"[Update] Content not unique: {sorted(keywords)}, occurrences={count}"
                )
                return Err(
                    FailureHint(
                        f"要替换的内容不唯一，在文件中出现 {count} 次",
                        suggestion="使用更具体、更长的内容片段以确保唯一性",
                    )
                )

            updated_content = current_content.replace(old_content, new_content, 1)

            match await memory.set_content(updated_content):
                case Err(e):
                    logger.warning(f"[Update] Content validation failed: {e.message}")
                    return Err(e)

            logger.info(
                f"[Update] Success: {sorted(keywords)}, version {version} -> {memory.version}"
            )
            return Ok(memory.snapshot())

    async def reassign(
        self, keywords: Iterable[str], new_keywords: Iterable[str], version: str
    ) -> Result[MemorySnapShot, FailureHint]:
        """重命名 memory 的 keywords（返回新 version）"""
        match self._find_memory(keywords):
            case Err(e):
                logger.warning(f"[Reassign] Not found: {sorted(keywords)}")
                return Err(e)
            case Ok((old_key, old_memory)):
                pass

        async with old_memory.lock:
            match old_memory.check_version(version):
                case Err(e):
                    logger.warning(
                        f"[Reassign] Version mismatch: {sorted(keywords)}, "
                        f"expected={version}, actual={old_memory.version}"
                    )
                    return Err(e)

            match await Memory.create(
                new_keywords, old_memory.content, self._project_root
            ):
                case Err(e):
                    logger.warning(
                        f"[Reassign] New keywords validation failed: {e.message}"
                    )
                    return Err(e)
                case Ok(new_memory):
                    pass

            async with self._registry_lock:
                if new_memory.keywords in self._memories:
                    logger.warning(
                        f"[Reassign] New keywords conflict: {sorted(new_memory.keywords)}"
                    )
                    return Err(
                        FailureHint(
                            "新 Keywords 对应的 Memory 已存在",
                            suggestion="选择其他关键词组或先删除已存在的记忆",
                        )
                    )

                del self._memories[old_key]
                self._memories[new_memory.keywords] = new_memory

            old_memory.delete_file()

            logger.info(
                f"[Reassign] Success: {sorted(keywords)} -> {sorted(new_memory.keywords)}, "
                f"version {version} -> {new_memory.version}"
            )
            return Ok(new_memory.snapshot())

    def delete(
        self, keywords: Iterable[str], version: str
    ) -> Result[None, FailureHint]:
        """删除 memory"""
        match self._find_memory(keywords):
            case Err(e):
                logger.warning(f"[Delete] Not found: {sorted(keywords)}")
                return Err(e)
            case Ok((key, memory)):
                pass

        match memory.check_version(version):
            case Err(e):
                logger.warning(f"[Delete] Version mismatch: {sorted(keywords)}")
                return Err(e)

        memory.delete_file()
        del self._memories[key]

        logger.info(f"[Delete] Success: {sorted(keywords)}")
        return Ok(None)
