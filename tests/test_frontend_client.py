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


@pytest.mark.asyncio
async def test_recovery_from_crashed_backend(test_project_dir):
    """测试场景：后端运行中突然崩溃，前端能否自动恢复

    测试步骤：
    1. 前端启动后端
    2. 验证后端正常工作
    3. 主动杀死后端进程（模拟崩溃）
    4. 前端再次操作，应该自动重启后端
    """
    test_dir = test_project_dir
    lock_file = get_lock_file(test_dir)

    # 启动前端客户端
    client = FrontendClient(test_dir)
    await client.start()

    # 验证后端正常工作
    health = await client.check_health()
    assert health["status"] == "healthy", "初始后端应该健康"
    print(f"✓ 后端已启动并运行正常")

    # 获取第一个后端的 PID
    lines = lock_file.read_text().strip().split("\n")
    first_backend_pid = int(lines[0])
    first_backend_port = int(lines[1])
    print(f"第一个后端: PID={first_backend_pid}, Port={first_backend_port}")

    # 模拟后端崩溃：主动杀死后端进程
    os.kill(first_backend_pid, 9)
    print(f"✓ 已杀死后端进程 {first_backend_pid}（模拟崩溃）")

    # 等待进程完全终止
    await asyncio.sleep(2)

    # 尝试回收僵尸进程（后端是前端的子进程）
    try:
        os.waitpid(first_backend_pid, 0)
        print(f"✓ 已回收后端进程 {first_backend_pid}")
    except OSError:
        print(f"✓ 后端进程 {first_backend_pid} 已由其他进程回收")

    # 验证后端进程已经真正死亡（非僵尸）
    ps_result = subprocess.run(
        ["ps", "-p", str(first_backend_pid), "-o", "stat"],
        capture_output=True,
        text=True,
    )
    if ps_result.returncode == 0 and "Z" in ps_result.stdout:
        pytest.fail(f"后端进程 {first_backend_pid} 变成了僵尸进程")
    print(f"✓ 确认后端进程 {first_backend_pid} 已完全终止")

    # 现在 _ensure_backend() 会主动检查后端健康，第一次操作就应该成功
    print("尝试操作（预期成功，自动检测并重启后端）...")
    await client.memorize("test content after crash")
    print(f"✓ 操作成功，后端已自动恢复（无需重试）")

    # 验证新的后端已启动
    assert lock_file.exists(), "Lock file应该存在"
    lines = lock_file.read_text().strip().split("\n")
    second_backend_pid = int(lines[0])
    second_backend_port = int(lines[1])

    assert second_backend_pid != first_backend_pid, "应该是新的后端进程"
    print(f"✓ 新后端: PID={second_backend_pid}, Port={second_backend_port}")

    # 验证新后端健康
    health = await client.check_health()
    assert health["status"] == "healthy", "新后端应该健康"
    print(f"✓ 新后端运行正常")

    print(f"✅ 测试通过：前端成功从后端崩溃中恢复")
    await client.close()


@pytest.mark.asyncio
async def test_recovery_from_unhealthy_process(test_project_dir):
    """测试场景2：后端进程存在但不健康（端口错误）

    预期行为：前端能够检测到不健康的后端并启动新后端
    注：当前实现可能不会主动清理不健康的旧进程
    """
    test_dir = test_project_dir
    lock_file = get_lock_file(test_dir)

    # 启动一个假进程（长期运行的sleep）
    fake_process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    fake_pid = fake_process.pid
    fake_port = 9999  # 一个不存在的端口

    print(f"启动了假进程: PID={fake_pid}")

    # 写入lock file
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(f"{fake_pid}\n{fake_port}\n")

    # 验证假进程确实存活
    try:
        os.kill(fake_pid, 0)
        print(f"假进程 {fake_pid} 正在运行")
    except OSError:
        fake_process.kill()
        pytest.fail(f"假进程 {fake_pid} 应该在运行")

    # 创建客户端并启动
    client = FrontendClient(test_dir)

    try:
        await client.start()

        # 等待清理操作完成
        await asyncio.sleep(1)

        # 验证新的lock file
        assert lock_file.exists(), "Lock file应该存在"
        lines = lock_file.read_text().strip().split("\n")
        new_pid = int(lines[0])
        new_port = int(lines[1])

        assert new_pid != fake_pid, "应该启动新的后端进程，而不是使用假进程"

        # 验证新进程确实存在
        try:
            os.kill(new_pid, 0)
            print(f"新进程 {new_pid} 存活")
        except OSError:
            pytest.fail(f"新进程 {new_pid} 应该存在但实际不存在")

        # 验证health check
        health = await client.check_health()
        assert health["status"] == "healthy", "新后端应该健康"

        # 检查假进程是否被清理（等待最多2秒让进程完全终止）
        fake_process_alive = True
        for _ in range(20):
            try:
                os.kill(fake_pid, 0)
                await asyncio.sleep(0.1)
            except OSError:
                fake_process_alive = False
                break

        if fake_process_alive:
            pytest.fail(f"假进程 {fake_pid} 应该被清理但仍然存活")
        else:
            print(f"✓ 假进程 {fake_pid} 已被清理")

        print(f"✓ 场景2测试通过：前端成功启动新后端")

    finally:
        # 清理
        await client.close()
        try:
            fake_process.kill()
            fake_process.wait(timeout=5)
        except:
            pass
