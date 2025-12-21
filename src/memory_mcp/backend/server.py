"""Backend Worker 进程 - 处理 recall/memorize 业务逻辑"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from aiohttp import web

from .config import AUTO_SHUTDOWN_CHECK_INTERVAL_SECONDS, AUTO_SHUTDOWN_IDLE_SECONDS
from .core.memory_registry import MemoryRegistry
from .lock import BackendLock
from .logger import logger, setup_logger
from .tools.memorize import memorize_memory
from .tools.recall import recall_memory


class BackendServer:
    """后端服务器"""

    def __init__(
        self,
        project_root: Path,
        shutdown_idle: float = AUTO_SHUTDOWN_IDLE_SECONDS,
        shutdown_check_interval: float = AUTO_SHUTDOWN_CHECK_INTERVAL_SECONDS,
    ):
        self.project_root = project_root
        self.lock = BackendLock(project_root)

        self.active_tasks = 0
        self.last_activity = 0.0

        self._shutdown_idle = shutdown_idle
        self._shutdown_check_interval = shutdown_check_interval

        self._shutdown_event = asyncio.Event()
        self._shutdown_task: asyncio.Task | None = None

    async def handle_recall(self, request: web.Request) -> web.Response:
        """处理 recall 请求"""

        self.active_tasks += 1
        self.last_activity = asyncio.get_event_loop().time()

        try:
            data = await request.json()
            interest = data["interest"]

            result = await recall_memory(interest, self.registry)

            return web.json_response({"status": "success", "result": result})

        except Exception as e:
            logger.error(f"Recall failed: {e}", exc_info=True)
            return web.json_response({"status": "error", "error": str(e)}, status=500)
        finally:
            self.active_tasks -= 1

    async def handle_memorize(self, request: web.Request) -> web.Response:
        """处理 memorize 请求（异步）"""

        self.last_activity = asyncio.get_event_loop().time()

        try:
            data = await request.json()
            content = data["content"]

            # 启动后台任务
            asyncio.create_task(self._memorize_task(content))

            return web.json_response({"status": "accepted"})

        except Exception as e:
            logger.error(f"Memorize request failed: {e}", exc_info=True)
            return web.json_response({"status": "error", "error": str(e)}, status=500)

    async def _memorize_task(self, content: str):
        """后台 memorize 任务"""
        self.active_tasks += 1
        try:
            await memorize_memory(content, self.registry)
        finally:
            self.active_tasks -= 1

    async def handle_health(self, request: web.Request) -> web.Response:
        """健康检查"""
        return web.json_response(
            {
                "status": "healthy",
                "active_tasks": self.active_tasks,
            }
        )

    async def handle_heartbeat(self, request: web.Request) -> web.Response:
        """心跳接口（前端定期调用，保持后端存活）"""
        self.last_activity = asyncio.get_event_loop().time()
        return web.json_response({"status": "alive"})

    async def handle_set_log_level(self, request: web.Request) -> web.Response:
        """设置日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL, disable）"""
        try:
            data = await request.json()
            level = data.get("level", "").upper()

            if level == "DISABLE":
                # 禁用日志
                logger.setLevel(logging.CRITICAL + 1)  # 高于所有级别
                logger.info(
                    f"Log level set to DISABLE (actually {logging.CRITICAL + 1})"
                )
                return web.json_response(
                    {
                        "status": "success",
                        "level": "DISABLE",
                        "message": "Backend logging disabled",
                    }
                )

            # 验证日志级别
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if level not in valid_levels:
                return web.json_response(
                    {
                        "status": "error",
                        "error": f"Invalid level. Must be one of: {', '.join(valid_levels + ['DISABLE'])}",
                    },
                    status=400,
                )

            # 设置日志级别
            log_level = getattr(logging, level)
            logger.setLevel(log_level)
            logger.info(f"Log level changed to {level}")

            return web.json_response(
                {
                    "status": "success",
                    "level": level,
                    "message": f"Backend log level set to {level}",
                }
            )

        except Exception as e:
            return web.json_response({"status": "error", "error": str(e)}, status=500)

    async def auto_shutdown_monitor(self):
        """自动退出监控"""
        while True:
            await asyncio.sleep(self._shutdown_check_interval)

            idle_time = asyncio.get_event_loop().time() - self.last_activity

            logger.debug(
                f"Auto-shutdown check: tasks={self.active_tasks}, idle_time={idle_time:.1f}s"
            )

            if self.active_tasks == 0 and idle_time >= self._shutdown_idle:

                logger.info(
                    f"Auto-shutdown: no activity for {idle_time:.1f}s (>= {self._shutdown_idle}s), triggering shutdown"
                )
                self._shutdown_event.set()
                return

    def create_app(self) -> web.Application:
        """创建 aiohttp 应用"""
        app = web.Application()
        app.router.add_post("/recall", self.handle_recall)
        app.router.add_post("/memorize", self.handle_memorize)
        app.router.add_get("/health", self.handle_health)
        app.router.add_post("/heartbeat", self.handle_heartbeat)
        app.router.add_post("/log_level", self.handle_set_log_level)  # 日志级别控制
        return app

    async def run(self):
        """启动并运行服务器（阻塞直到退出）"""
        if not self.lock.acquire():
            logger.warning("Another backend instance is already running")
            sys.exit(0)

        try:
            logger.info(f"Starting backend for project: {self.project_root}")

            self.registry = MemoryRegistry(self.project_root)
            app = self.create_app()
            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()

            actual_port = site._server.sockets[0].getsockname()[1]  # type: ignore
            logger.info(f"Backend started on port {actual_port}")

            self.lock.write_info(os.getpid(), actual_port)

            self.last_activity = asyncio.get_event_loop().time()

            self._shutdown_task = asyncio.create_task(self.auto_shutdown_monitor())

            await self._shutdown_event.wait()
            logger.info("Shutting down gracefully...")

        except Exception as e:
            logger.error(f"Failed to start backend: {e}")
            raise
        finally:
            self.lock.release()


def main():
    """后端入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Memory MCP Backend Server")
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    setup_logger(args.project)
    server = BackendServer(args.project)

    asyncio.run(server.run())


if __name__ == "__main__":
    main()
