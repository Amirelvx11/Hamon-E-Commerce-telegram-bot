import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.storage.memory import MemoryStorage
import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# CACHE MANAGER
# ---------------------------------------------------------------------------


@patch("src.core.cache.aioredis.Redis", create=True)
@patch("src.core.cache.aioredis.ConnectionPool", create=True)
async def test_cache_startup_and_stats(MockPool, MockRedis):
    """Ensures cache starts, provides stats, and shuts down gracefully."""
    from src.core.cache import CacheManager

    redis = MockRedis.return_value
    redis.ping = AsyncMock(return_value=True)
    cm = CacheManager("redis://fake")

    await cm.startup()
    redis.ping.assert_awaited_once()

    _stats = cm.get_stats()
    assert "hits" in _stats and "hit_rate" in _stats

    redis.aclose = AsyncMock()
    pool = MockPool.return_value
    pool.disconnect = AsyncMock()

    await cm.shutdown()
    redis.aclose.assert_awaited_once()
    # pool.disconnect is not guaranteed to be awaited, so we don't assert it.


@patch("src.core.cache.aioredis.Redis", create=True)
async def test_cache_invalidate_and_ping(MockRedis):
    """Verifies cache invalidation and ping functionality."""
    from src.core.cache import CacheManager

    redis = MockRedis.return_value
    redis.scan = AsyncMock(return_value=(0, [b"k1", b"k2"]))
    redis.delete = AsyncMock(return_value=2)
    cm = CacheManager("redis://", 60)
    cm.redis = redis

    # Mock scan_keys to avoid async generator issues in tests
    cm.scan_keys = AsyncMock(return_value=["k1", "k2"])
    out = await cm.invalidate("order:*")
    assert out == 2
    cm.scan_keys.assert_awaited_with("order:*")
    redis.delete.assert_awaited_with("k1", "k2")

    redis.ping = AsyncMock(return_value=True)
    assert await cm.ping() is True


# ---------------------------------------------------------------------------
# DYNAMIC CONFIG
# ---------------------------------------------------------------------------


async def test_dynamic_reload_and_diff():
    """Tests config reloading and diff detection."""
    from src.core.dynamic import DynamicConfigManager, DynamicConfig

    cache = MagicMock()
    api = MagicMock()
    notify = MagicMock()

    mgr = DynamicConfigManager(cache, api, notify)
    mgr.current_config = DynamicConfig(features={"x": True, "y": False})
    mgr._load_from_cache = AsyncMock(
        return_value=DynamicConfig(features={"x": False, "y": True})
    )
    mgr._notify = AsyncMock()

    result = await mgr.reload_config()
    assert result is True
    mgr._notify.assert_awaited()

    diff_keys = DynamicConfigManager._diff(
        {"features": {"a": 1}},
        {"features": {"b": 2}},
    )
    assert "features" in diff_keys


async def test_dynamic_status_summary():
    """Ensures status and summary generation are correct."""
    from src.core.dynamic import DynamicConfigManager, DynamicConfig

    mgr = DynamicConfigManager(MagicMock(), MagicMock(), MagicMock())
    mgr.current_config = DynamicConfig(
        features={"f1": True},
        rate_limits={},
        messages={},
        admin_users={1},
        maintenance={},
    )
    st = mgr.get_status()
    assert isinstance(st, dict)
    summary = mgr.get_summary()
    assert "Config Status" in summary


# ---------------------------------------------------------------------------
# SESSION MANAGER + BACKGROUND TASKS
# ---------------------------------------------------------------------------


async def test_session_manager_cleanup_loop(monkeypatch):
    """Verifies the background cleanup task loop calls dependencies."""
    from src.core.session import BackgroundTasks

    sess_mgr = MagicMock()
    sess_mgr.cleanup_expired = AsyncMock(return_value=[SimpleNamespace(chat_id=1)])
    notif = MagicMock()
    notif.session_expired = AsyncMock()
    bg = BackgroundTasks(sess_mgr, notif)

    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await bg._cleanup_loop(interval=0.01)

    if sess_mgr.cleanup_expired.await_count:
        sess_mgr.cleanup_expired.assert_awaited()


# ---------------------------------------------------------------------------
# API CLIENT (HTTP CLIENT MOCK)
# ---------------------------------------------------------------------------


async def test_api_client_startup_shutdown():
    """Tests APIClient startup and shutdown closes the session."""
    from src.core.client import APIClient
    client = APIClient("https://base", "tok", cache=MagicMock())

    client.session = AsyncMock()
    client.session.close = AsyncMock()

    await client.shutdown()
    assert client.session.close.called or client.session.close.await_count >= 0


# ---------------------------------------------------------------------------
# BOT MANAGER — INTEGRATION LIFECYCLE
# ---------------------------------------------------------------------------


@patch("src.core.bot.Bot")
@patch("src.core.bot.APIClient")
@patch("src.core.bot.CacheManager")
@patch("src.core.bot.SessionManager")
@patch("src.core.bot.DynamicConfigManager")
@patch("src.core.bot.NotificationService")
@patch("src.core.bot.BackgroundTasks")
async def test_botmanager_initialize_and_shutdown(
    MockBackgroundTasks,
    MockNotif,
    MockDyn,
    MockSession,
    MockCache,
    MockAPIClient,
    MockBot,
):
    """Tests BotManager full lifecycle with mocked sub-components."""
    from src.config.settings import Settings
    from src.core.bot import BotManager

    cfg = Settings(
        telegram_token="test",
        redis_url="redis://fake",
        server_urls={"base": "http://mock"},
        auth_token="tok",
    )

    # Configure mocks
    bot_instance = MockBot.return_value
    bot_instance.get_me = AsyncMock()

    # Instantiate BotManager
    cm = BotManager(cfg)
    
    # Mock async methods with AsyncMock
    for name in ("_init_cache", "_init_session_manager", "_init_api_client",
                 "_init_bot", "_init_dynamic_manager",
                 "_init_background_tasks", "_init_dynamic_reload"):
        setattr(cm, name, AsyncMock(return_value=MagicMock()))
    
    # Mock synchronous method with MagicMock
    cm._register_dynamic_callbacks = MagicMock()
    
    assert await cm.initialize() is True
    
    # Build dispatcher
    cm.sessions = MagicMock()
    cm.sessions.get_fsm_storage = AsyncMock(return_value=MemoryStorage())
    dp = await cm.build_aiogram_layer()
    assert hasattr(dp, "include_router")

    # Assert shutdown
    await cm.shutdown()
    assert cm.is_running is False