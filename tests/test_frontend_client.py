"""测试 BackendClient 的 discover 功能"""

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import mkdtemp

import pytest
import pytest_asyncio

from memory_mcp.file_manager import get_lock_file
from memory_mcp.frontend.client import FrontendClient


@pytest_asyncio.fixture
async def test_project_dir():
    """提供临时测试目录，测试结束后自动清理"""
    test_dir = Path(mkdtemp(prefix="test_memory_mcp_"))
    yield test_dir

    # 清理：先清理后端进程，再删除目录
    lock_file = get_lock_file(test_dir)
    if lock_file.exists():
        try:
            lock_content = lock_file.read_text().strip().split("\n")
            if lock_content:
                backend_pid = int(lock_content[0])
                os.kill(backend_pid, 15)  # SIGTERM
                await asyncio.sleep(0.5)
        except:
            pass

    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_discover_backend(test_project_dir):
    """测试能否发现正在运行的后端"""
    test_dir = test_project_dir

    # 启动后端进程
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "memory_mcp.backend.server",
            "--project",
            str(test_dir),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待后端启动
    await asyncio.sleep(2.0)

    # 检查后端进程是否存活
    poll_result = backend_proc.poll()
    assert poll_result is None, f"后端进程应该在运行，但退出码为 {poll_result}"

    # 检查 lock 文件是否创建
    lock_file = get_lock_file(test_dir)
    assert lock_file.exists(), f"Lock 文件应该存在: {lock_file}"

    # 检查 lock 文件内容
    lock_content = lock_file.read_text()
    print(f"Lock 文件内容: {lock_content}")

    # 创建 client，测试 discover
    client = FrontendClient(test_dir)
    discovered = await client._discover_backend()

    assert (
        discovered is True
    ), f"应该能发现正在运行的后端，但 discover 返回 {discovered}"
    assert client.backend_url is not None, "backend_url 应该被设置"
    assert "127.0.0.1" in client.backend_url, "应该是本地地址"

    # 验证能访问 health endpoint
    session = await client._get_session()
    async with session.get(f"{client.backend_url}/health") as resp:
        assert resp.status == 200, "health check 应该成功"
        data = await resp.json()
        assert data["status"] == "healthy"

    # 关闭后端
    backend_proc.terminate()
    backend_proc.wait(timeout=5)

    # 等待进程完全退出
    await asyncio.sleep(0.5)

    # 创建新的 client，测试 discover 应该失败
    client2 = FrontendClient(test_dir)
    discovered2 = await client2._discover_backend()

    assert discovered2 is False, "后端已关闭，discover 应该返回 False"
    assert client2.backend_url is None, "backend_url 应该是 None"

    # 清理
    await client.close()
    await client2.close()


@pytest.mark.asyncio
async def test_discover_no_backend(test_project_dir):
    """测试当没有后端运行时，discover 应该返回 False"""
    test_dir = test_project_dir

    client = FrontendClient(test_dir)
    discovered = await client._discover_backend()

    assert discovered is False, "没有后端运行，discover 应该返回 False"
    assert client.backend_url is None, "backend_url 应该是 None"

    await client.close()


@pytest.mark.asyncio
async def test_frontend_start_backend(test_project_dir):
    """测试前端能否自动启动后端"""
    test_dir = test_project_dir

    # 创建 client，此时没有后端运行
    client = FrontendClient(test_dir)

    # 调用 ensure_backend，应该自动启动后端
    await client.start()

    # 验证后端已启动
    assert client.backend_url is not None, "backend_url 应该被设置"
    assert "127.0.0.1" in client.backend_url, "应该是本地地址"

    # 验证 lock 文件存在
    lock_file = get_lock_file(test_dir)
    assert lock_file.exists(), f"Lock 文件应该存在: {lock_file}"

    # 验证能访问 health endpoint
    session = await client._get_session()
    async with session.get(f"{client.backend_url}/health") as resp:
        assert resp.status == 200, "health check 应该成功"
        data = await resp.json()
        assert data["status"] == "healthy"

    # 清理
    await client.close()


@pytest.mark.asyncio
async def test_client_check_health(test_project_dir):
    """测试FrontendClient的check_health方法"""
    from memory_mcp.file_manager import get_cache_dir

    test_dir = test_project_dir

    client = FrontendClient(test_dir)
    await client.start()

    health_info = await client.check_health()

    assert health_info["status"] == "healthy"
    assert "active_tasks" in health_info
    assert "log_path" in health_info
    expected_log_path = str(get_cache_dir(test_dir) / "backend.log")
    assert health_info["log_path"] == expected_log_path

    await client.close()
