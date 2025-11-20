import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

pytestmark = pytest.mark.asyncio


class FakeBot:
    """Minimal Aiogram Bot mock"""
    def __init__(self, token):
        self.token = token
        self.delete_webhook = AsyncMock()
        self.get_me = AsyncMock(return_value=SimpleNamespace(username="test_bot"))
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass


class FakeDispatcher:
    """Minimal Aiogram Dispatcher mock"""
    def __init__(self, *args, **kwargs):
        self.started = False
        self.handlers = []
        self.start_polling = AsyncMock()
    
    def include_router(self, router):
        self.handlers.append(router)


@patch("src.core.bot.Bot", new=FakeBot)
@patch("src.core.bot.Dispatcher", new=FakeDispatcher)
async def test_botmanager_full_lifecycle(app_settings, mock_redis_globally):
    """Test complete BotManager initialization and shutdown cycle"""
    from src.core.bot import BotManager
    
    manager = BotManager(app_settings)
    
    # Mock all initialization methods to prevent real connections
    manager._init_cache = AsyncMock(return_value=MagicMock(
        startup=AsyncMock(),
        get_stats=MagicMock(return_value={}),
        shutdown=AsyncMock()
    ))
    
    manager._init_session_manager = AsyncMock(return_value=MagicMock(
        stop=AsyncMock()
    ))
    
    manager._init_api_client = AsyncMock(return_value=MagicMock(
        startup=AsyncMock(),
        get_health=MagicMock(return_value={}),
        shutdown=AsyncMock()
    ))
    
    manager._init_dynamic_manager = AsyncMock(return_value=MagicMock(
        startup=AsyncMock(),
        shutdown=AsyncMock()
    ))
    
    manager._init_background_tasks = AsyncMock(return_value=MagicMock(
        start=AsyncMock(),
        stop=AsyncMock()
    ))
    
    manager._init_dynamic_reload = AsyncMock()
    manager._register_dynamic_callbacks = MagicMock()
    
    # Test initialization
    result = await manager.initialize()
    assert result is True
    assert manager.is_running is True
    
    # Test shutdown
    await manager.shutdown()
    assert manager.is_running is False


@patch("src.core.bot.Bot", new=FakeBot)
@patch("src.core.bot.Dispatcher", new=FakeDispatcher)
async def test_botmanager_build_dispatcher(app_settings, mock_redis_globally):
    """Test Aiogram dispatcher construction with routers"""
    from src.core.bot import BotManager
    
    manager = BotManager(app_settings)
    
    # Mock dependencies
    manager.bot = FakeBot("test_token")
    manager.sessions = MagicMock(get_fsm_storage=AsyncMock(return_value=MagicMock()))
    manager.cache = MagicMock()
    manager.dynamic = MagicMock()
    manager.api = MagicMock()
    
    dp = await manager.build_aiogram_layer()
    
    assert isinstance(dp, FakeDispatcher)
    assert len(dp.handlers) >= 4  # common, auth, order, support


@patch("main.BotManager")
async def test_main_entrypoint(MockBotManager):
    """Test main.py entry point with context manager"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import main
    
    mock_mgr = MockBotManager.return_value
    mock_mgr.__aenter__ = AsyncMock(return_value=mock_mgr)
    mock_mgr.__aexit__ = AsyncMock()
    mock_mgr.build_aiogram_layer = AsyncMock(return_value=FakeDispatcher())
    mock_mgr.bot = FakeBot("test")
    
    await main.main()
    
    mock_mgr.__aenter__.assert_awaited_once()
    mock_mgr.build_aiogram_layer.assert_awaited_once()
    mock_mgr.__aexit__.assert_awaited_once()


async def test_botmanager_context_manager(app_settings):
    """Test BotManager async context manager protocol"""
    from src.core.bot import BotManager
    
    manager = BotManager(app_settings)
    manager.initialize = AsyncMock(return_value=True)
    manager.shutdown = AsyncMock()
    
    async with manager as mgr:
        assert mgr is manager
        manager.initialize.assert_awaited_once()
    
    manager.shutdown.assert_awaited_once()


async def test_botmanager_initialization_failure(app_settings):
    """Test BotManager handles initialization failures gracefully"""
    from src.core.bot import BotManager
    
    manager = BotManager(app_settings)
    manager._init_cache = AsyncMock(side_effect=Exception("Redis connection failed"))
    manager.shutdown = AsyncMock()
    
    result = await manager.initialize()
    
    assert result is False
    manager.shutdown.assert_awaited_once()
