"""Backend 客户端 - Frontend 用于与 Backend 通信"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import aiohttp

from ..file_manager import get_lock_file
from .config import HEARTBEAT_INTERVAL
from .logger import logger


class FrontendClient:
    """客户端（Frontend 侧）"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backend_url: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._heartbeat_task: asyncio.Task | None = None  # 心跳任务
        self._ensure_backend_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话（懒加载）"""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=120)  # recall 超时 2 分钟
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _ensure_backend(self):
        async with self._ensure_backend_lock:
            if await self._discover_backend():
                logger.info(f"Found existing backend at {self.backend_url}")
                return

            await self._start_backend()
            logger.info(f"Started new backend at {self.backend_url}")

    async def start(self):
        """确保后端运行（发现或启动）"""
        await self._ensure_backend()
        self._start_heartbeat()  # 启动心跳

    def _start_heartbeat(self):
        """启动心跳任务"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Heartbeat started")

    async def _heartbeat_loop(self):
        """心跳循环（每 4 分钟发送一次）"""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)  # 每1秒
                session = await self._get_session()
                async with session.post(
                    f"{self.backend_url}/heartbeat",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as resp:
                    if resp.status == 200:
                        logger.debug("Heartbeat sent")
                    else:
                        logger.warning(f"Heartbeat failed: {resp.status}")
            except asyncio.CancelledError:
                logger.info("Heartbeat stopped")
                break
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                await self._ensure_backend()

    async def _discover_backend(self) -> bool:
        """发现现有后端"""
        lock_file = get_lock_file(self.project_root)

        if not lock_file.exists():
            return False

        try:
            lines = lock_file.read_text().strip().split("\n")
            if len(lines) < 2:
                return False

            pid = int(lines[0])
            port = int(lines[1])

            # 检查进程是否存活
            if not self._is_process_alive(pid):
                lock_file.unlink(missing_ok=True)  # 清理过期 lock
                self._cleanup_backend(pid)
                return False

            # 发送 health check
            url = f"http://127.0.0.1:{port}"
            session = await self._get_session()

            try:
                async with session.get(
                    f"{url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        self.backend_url = url
                        return True
                    else:
                        self._cleanup_backend(pid)
                        return False
            except Exception as e:
                logger.warning(f"Health check failed: {e}")
                self._cleanup_backend(pid)
                return False

        except Exception as e:
            logger.warning(f"Backend discovery failed: {e}")
            return False

    def _is_process_alive(self, pid: int) -> bool:
        """检查进程是否存活"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _cleanup_backend(self, pid: int):
        """清理不健康的后端进程和 lock 文件"""
        try:
            os.kill(pid, 9)  # SIGKILL
            logger.info(f"Killed process {pid}")
            # 回收僵尸进程
            try:
                os.waitpid(pid, 0)
                logger.debug(f"Reaped zombie process {pid}")
            except OSError as e:
                logger.debug(f"Failed to reap process {pid}: {e}")
        except OSError as e:
            logger.warning(f"Failed to kill process {pid}: {e}")
        lock_file = get_lock_file(self.project_root)
        lock_file.unlink(missing_ok=True)
        logger.info(f"Cleaned up backend process {pid} and lock file")

    async def _start_backend(self):
        """启动新后端进程（完全独立）"""
        # 构建启动命令
        cmd = [
            sys.executable,
            "-m",
            "memory_mcp.backend.server",
            "--project",
            str(self.project_root),
        ]

        # 跨平台进程独立性配置
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }

        # Unix/Linux/macOS: 创建新会话
        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        # Windows: 创建新进程组
        else:
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )

        # 启动后端进程（不保存引用，让它完全独立）
        subprocess.Popen(cmd, **kwargs)  # type: ignore

        # 等待后端启动（重试发现）
        for _ in range(10):  # 最多等待 5 秒
            await asyncio.sleep(0.5)
            if await self._discover_backend():
                return

        raise RuntimeError("Failed to start backend: timeout waiting for health check")

    async def recall(self, interest: str, deep: bool = False) -> str:
        """调用 recall（阻塞等待结果）
        Returns:
            回忆报告
        """

        session = await self._get_session()

        try:
            async with session.post(
                f"{self.backend_url}/recall",
                json={"interest": interest, "deep": deep},
            ) as resp:
                data = await resp.json()

                if data["status"] == "success":
                    return data["result"]
                else:
                    raise RuntimeError(data.get("error", "Unknown error"))

        except Exception as e:
            logger.error(f"Recall failed: {e}")
            raise

    async def memorize(self, content: str):
        """调用 memorize（立即返回）"""

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.backend_url}/memorize",
                json={"content": content},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()

                if data["status"] != "accepted":
                    raise RuntimeError(data.get("error", "Unknown error"))

                return

        except Exception as e:
            logger.error(f"Memorize request failed: {e}")
            raise

    async def set_log_level(self, level: str):
        """设置后端日志级别

        Args:
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL, DISABLE）
        """

        session = await self._get_session()

        try:
            async with session.post(
                f"{self.backend_url}/log_level",
                json={"level": level},
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                data = await resp.json()

                if data["status"] == "success":
                    logger.info(f"Backend log level set to {level}")
                    return data["message"]
                else:
                    raise RuntimeError(data.get("error", "Failed to set log level"))

        except Exception as e:
            logger.error(f"Set log level failed: {e}")
            raise

    async def check_health(self) -> dict:
        """检查后端健康状态并返回信息

        Returns:
            包含状态、活跃任务数和日志路径的字典
        """

        session = await self._get_session()
        try:
            async with session.get(
                f"{self.backend_url}/health",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                data = await resp.json()

                if resp.status == 200:
                    return data
                else:
                    raise RuntimeError(data.get("error", "Health check failed"))
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    async def close(self):
        """关闭客户端"""
        # 停止心跳
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 关闭 HTTP 会话
        if self._session:
            await self._session.close()
