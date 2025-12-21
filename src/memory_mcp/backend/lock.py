"""跨平台文件锁实现（基于 filelock 库）"""

from pathlib import Path

from filelock import FileLock, Timeout

from ..file_manager import get_lock_file


class BackendLock:
    """后端单例文件锁"""

    def __init__(self, project_root: Path):
        # 文件锁
        self.lock_file = get_lock_file(project_root)

        # 创建 FileLock 实例（非阻塞模式）
        self._lock = FileLock(str(self.lock_file), timeout=0)

    def acquire(self) -> bool:
        """尝试获取独占锁，成功返回 True"""
        try:
            # 确保目录存在
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)

            # 尝试获取锁（非阻塞）
            self._lock.acquire(blocking=False)
            return True
        except Timeout:
            # 锁已被占用
            return False

    def write_info(self, pid: int, port: int):
        """写入后端信息到锁文件中"""
        self.lock_file.write_text(f"{pid}\n{port}\n")

    def release(self):
        """释放锁并删除锁文件"""
        try:
            if self._lock.is_locked:
                self._lock.release()
            self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass
