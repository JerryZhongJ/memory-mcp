"""测试 BackendServer 的自动退出功能"""

import asyncio
from pathlib import Path
from tempfile import mkdtemp

import pytest
import pytest_asyncio

from memory_mcp.backend.server import BackendServer
from memory_mcp.file_manager import get_lock_file


@pytest_asyncio.fixture
async def test_project_dir():
    """提供临时测试目录，测试结束后自动清理"""
    test_dir = Path(mkdtemp(prefix="test_backend_"))
    yield test_dir

    import shutil

    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_auto_shutdown_when_idle(test_project_dir):
    """测试后端在空闲时自动退出"""
    test_dir = test_project_dir

    server = BackendServer(
        test_dir,
        shutdown_idle=2.0,
        shutdown_check_interval=0.5,
    )

    run_task = asyncio.create_task(server.run())

    await asyncio.sleep(0.5)

    lock_file = get_lock_file(test_dir)
    assert lock_file.exists(), "后端应该已启动并创建 lock 文件"

    await asyncio.sleep(3.0)

    assert run_task.done(), "后端应该已自动退出"

    assert not lock_file.exists(), "Lock 文件应该被清理"


@pytest.mark.asyncio
async def test_no_shutdown_when_active(test_project_dir):
    """测试后端在有活动时不会自动退出"""
    import aiohttp

    test_dir = test_project_dir

    server = BackendServer(
        test_dir,
        shutdown_idle=2.0,
        shutdown_check_interval=0.5,
    )

    run_task = asyncio.create_task(server.run())

    await asyncio.sleep(0.5)

    lock_file = get_lock_file(test_dir)
    assert lock_file.exists(), "后端应该已启动"

    lock_content = lock_file.read_text().strip().split("\n")
    port = int(lock_content[1])
    backend_url = f"http://127.0.0.1:{port}"

    async with aiohttp.ClientSession() as session:
        for _ in range(5):
            async with session.post(f"{backend_url}/heartbeat") as resp:
                assert resp.status == 200

            await asyncio.sleep(0.8)

    assert not run_task.done(), "后端应该仍在运行（因为有心跳活动）"

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_health_returns_log_path(test_project_dir):
    """测试health API返回log文件路径"""
    import aiohttp

    from memory_mcp.file_manager import get_cache_dir

    test_dir = test_project_dir

    server = BackendServer(
        test_dir,
        shutdown_idle=10.0,
        shutdown_check_interval=1.0,
    )

    run_task = asyncio.create_task(server.run())

    await asyncio.sleep(0.5)

    lock_file = get_lock_file(test_dir)
    assert lock_file.exists(), "后端应该已启动"

    lock_content = lock_file.read_text().strip().split("\n")
    port = int(lock_content[1])
    backend_url = f"http://127.0.0.1:{port}"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{backend_url}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "healthy"
            assert "log_path" in data
            expected_log_path = str(get_cache_dir(test_dir) / "backend.log")
            assert data["log_path"] == expected_log_path

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass
