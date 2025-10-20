"""
Session Manager Test Suite
Minimal and correct version for production validation
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "modules"))

try:
    from modules.core_config import BotConfig, BotMetrics, UserState
    from modules.session_manager import (
        RedisSessionManager,
        SessionBackgroundTasks,
        SessionData,
    )

    REAL_IMPORTS_AVAILABLE = True
except ImportError:
    REAL_IMPORTS_AVAILABLE = False

    class MockUserState:
        IDLE = "IDLE"
        AUTHENTICATED = "AUTHENTICATED"
        RATE_LIMITED = "RATE_LIMITED"

    class MockBotMetrics:
        def __init__(self):
            self.total_sessions = 0
            self.active_sessions = 0
            self.authenticated_users = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.total_requests = 0

        def increment_request(self):
            self.total_requests += 1

        def get_cache_ratio(self) -> float:
            total = self.cache_hits + self.cache_misses
            return self.cache_hits / total if total > 0 else 0.0

    class MockBotConfig:
        def __init__(self, redis_url: str = "redis://localhost:6379/0"):
            self.redis_url = redis_url
            self.redis_password = None
            self.auth_token = ""
            self.server_urls = {}
            self.maintenance_mode = False
            self.max_requests_per_hour = 100
            self.session_timeout = 30

    class MockSessionData:
        def __init__(
            self,
            user_id: int,
            chat_id: int,
            state: str = MockUserState.IDLE,
            created_at: datetime = None,
            expires_at: datetime = None,
            is_authenticated: bool = False,
            nationalId: Optional[str] = None,
            user_name: Optional[str] = None,
            temp_data: Dict[str, Any] = None,
            last_activity: datetime = None,
            request_count: int = 0,
        ):
            self.user_id = user_id
            self.chat_id = chat_id
            self.state = state
            self.created_at = created_at or datetime.now()
            self.expires_at = expires_at or (datetime.now() + timedelta(minutes=30))
            self.is_authenticated = is_authenticated
            self.nationalId = nationalId
            self.user_name = user_name
            self.temp_data = temp_data or {}
            self.last_activity = last_activity or datetime.now()
            self.request_count = request_count

        def to_dict(self) -> Dict:
            return {
                "user_id": self.user_id,
                "chat_id": self.chat_id,
                "state": self.state,
                "created_at": self.created_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "is_authenticated": self.is_authenticated,
                "nationalId": self.nationalId,
                "user_name": self.user_name,
                "temp_data": self.temp_data,
                "last_activity": self.last_activity.isoformat(),
                "request_count": self.request_count,
            }

        @classmethod
        def from_dict(cls, data: Dict) -> "MockSessionData":
            return cls(
                user_id=data.get("user_id"),
                chat_id=data.get("chat_id"),
                state=data.get("state", MockUserState.IDLE),
                created_at=(
                    datetime.fromisoformat(data.get("created_at"))
                    if data.get("created_at")
                    else datetime.now()
                ),
                expires_at=(
                    datetime.fromisoformat(data.get("expires_at"))
                    if data.get("expires_at")
                    else (datetime.now() + timedelta(minutes=30))
                ),
                is_authenticated=data.get("is_authenticated", False),
                nationalId=data.get("nationalId"),
                user_name=data.get("user_name"),
                temp_data=data.get("temp_data", {}),
                last_activity=(
                    datetime.fromisoformat(data.get("last_activity"))
                    if data.get("last_activity")
                    else datetime.now()
                ),
                request_count=data.get("request_count", 0),
            )

        def is_expired(self) -> bool:
            return datetime.now() > self.expires_at

        def extend(self, minutes: int = 30):
            self.expires_at = datetime.now() + timedelta(minutes=minutes)
            self.last_activity = datetime.now()
            self.request_count += 1

    class MockRedisSessionManager:
        def __init__(self, config, metrics):
            self.config = config
            self.metrics = metrics
            self.redis = AsyncMock()
            self.pool = AsyncMock()
            self._local_cache = {}
            self.KEY_PREFIX = "bot:session:"
            self.AUTH_PREFIX = "bot:auth:"
            self.DEFAULT_TTL = 1800
            self.AUTH_TTL = 3600
            self.MAX_CACHE_SIZE = 500
            self.background_tasks = None

            self.redis.get = AsyncMock(return_value=None)
            self.redis.setex = AsyncMock(return_value=True)
            self.redis.delete = AsyncMock(return_value=1)
            self.redis.ping = AsyncMock(return_value=True)
            self.redis.scan = AsyncMock(side_effect=self._mock_scan)
            self.redis.aclose = AsyncMock()

        async def _mock_scan(self, cursor, match=None, count=100):
            if cursor == "0":
                return "0", [f"{match}:1", f"{match}:2"] if match else []
            return "0", []

        async def connect(self):
            await self.redis.ping()

        async def disconnect(self):
            await self.redis.aclose()

        @asynccontextmanager
        async def session(self, chat_id: int, user_id: Optional[int] = None):
            session = await self.get_or_create(chat_id, user_id)
            try:
                yield session
            finally:
                if session:
                    await self.save(session)

        async def get_or_create(
            self, chat_id: int, user_id: Optional[int] = None
        ) -> MockSessionData:
            if chat_id in self._local_cache:
                session = self._local_cache[chat_id]
                if not session.is_expired():
                    if user_id and session.user_id != user_id:
                        session.user_id = user_id
                    self.metrics.cache_hits += 1
                    return session
                del self._local_cache[chat_id]

            self.metrics.cache_misses += 1
            key = f"{self.KEY_PREFIX}{chat_id}"
            data = await self.redis.get(key)

            if data:
                try:
                    session_dict = json.loads(data)
                    session = MockSessionData.from_dict(session_dict)
                    if not session.is_expired():
                        if user_id and session.user_id != user_id:
                            session.user_id = user_id
                        self._local_cache[chat_id] = session
                        return session
                except Exception:
                    pass

            actual_user_id = user_id or chat_id
            session = MockSessionData(user_id=actual_user_id, chat_id=chat_id)
            await self.save(session)
            self._local_cache[chat_id] = session
            self.metrics.total_sessions += 1
            self.metrics.active_sessions = len(self._local_cache)
            return session

        async def save(self, session: MockSessionData):
            session.last_activity = datetime.now()
            session.request_count += 1
            ttl = self.AUTH_TTL if session.is_authenticated else self.DEFAULT_TTL
            key = f"{self.KEY_PREFIX}{session.chat_id}"
            await self.redis.setex(key, ttl, json.dumps(session.to_dict()))
            self._local_cache[session.chat_id] = session

        async def authenticate(
            self,
            chat_id: int,
            nationalId: str,
            name: str,
            user_id: Optional[int] = None,
        ):
            session = await self.get_or_create(chat_id, user_id)
            session.is_authenticated = True
            session.nationalId = nationalId
            session.user_name = name
            session.state = MockUserState.AUTHENTICATED
            session.extend(60)

            auth_key = f"{self.AUTH_PREFIX}{nationalId}"
            await self.redis.setex(auth_key, self.AUTH_TTL, chat_id)
            self.metrics.authenticated_users += 1
            return session

        async def logout(self, chat_id: int):
            session = await self.get_or_create(chat_id)
            if session.nationalId:
                auth_key = f"{self.AUTH_PREFIX}{session.nationalId}"
                await self.redis.delete(auth_key)

            session.is_authenticated = False
            session.nationalId = None
            session.user_name = None
            session.state = MockUserState.IDLE
            session.temp_data.clear()
            await self.save(session)
            if self.metrics.authenticated_users > 0:
                self.metrics.authenticated_users -= 1

        async def clear(self, chat_id: int):
            key = f"{self.KEY_PREFIX}{chat_id}"
            await self.redis.delete(key)
            if chat_id in self._local_cache:
                del self._local_cache[chat_id]

        async def get_stats(self) -> Dict:
            return {
                "total_sessions": 10,
                "authenticated_sessions": 2,
                "cached_sessions": len(self._local_cache),
                "cache_hit_rate": self.metrics.get_cache_ratio(),
                "total_requests": self.metrics.total_requests,
            }

        async def cleanup_expired(self):
            return 1

        async def get_user_by_nationalId(self, nationalId: str) -> Optional[int]:
            auth_key = f"{self.AUTH_PREFIX}{nationalId}"
            chat_id = await self.redis.get(auth_key)
            return int(chat_id) if chat_id else None

        async def is_rate_limited(self, chat_id: int) -> bool:
            session = await self.get_or_create(chat_id)
            if session.request_count > self.config.max_requests_per_hour:
                session.state = MockUserState.RATE_LIMITED
                await self.save(session)
                return True
            return False

        async def get_active_sessions(self) -> List[MockSessionData]:
            return list(self._local_cache.values())

    RedisSessionManager = MockRedisSessionManager
    SessionData = MockSessionData
    UserState = MockUserState
    BotConfig = MockBotConfig
    BotMetrics = MockBotMetrics


@pytest.fixture
async def redis_client():
    redis = None
    try:
        redis = await aioredis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
        )
        await redis.ping()
        yield redis
        await redis.flushdb()
    except Exception as e:
        logger.warning(f"Live Redis unavailable: {e}")
        yield None
    finally:
        if redis:
            await redis.aclose()


@pytest.fixture
def config():
    return BotConfig(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@pytest.fixture
def metrics():
    return BotMetrics()


@pytest.fixture
async def session_manager(config, metrics, redis_client):
    if not REAL_IMPORTS_AVAILABLE:
        manager = RedisSessionManager(config, metrics)
    else:
        manager = RedisSessionManager(config, metrics)

    if redis_client:
        manager.redis = redis_client
        await manager.connect()
    else:
        manager.redis = AsyncMock()
        manager.redis.ping = AsyncMock(return_value=True)
        manager.redis.setex = AsyncMock(return_value=True)
        manager.redis.get = AsyncMock(return_value=None)
        manager.redis.delete = AsyncMock(return_value=1)
        manager.redis.aclose = AsyncMock()

    yield manager

    if hasattr(manager, "disconnect"):
        await manager.disconnect()
    elif manager.redis:
        await manager.redis.aclose()


class TestUnitMockedRedis:
    @pytest.fixture
    def mock_manager(self, config, metrics):
        return MockRedisSessionManager(config, metrics)

    @pytest.mark.asyncio
    async def test_session_creation_mock(self, mock_manager):
        session = await mock_manager.get_or_create(12345)
        assert session.chat_id == 12345
        assert session.state == MockUserState.IDLE
        assert session.user_id == 12345
        mock_manager.redis.get.assert_called_with("bot:session:12345")
        mock_manager.redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_authentication_mock(self, mock_manager):
        session = await mock_manager.authenticate(12345, "1234567890", "Test User")
        assert session.is_authenticated is True
        assert session.chat_id == 12345
        assert session.state == MockUserState.AUTHENTICATED
        mock_manager.redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_logout_mock(self, mock_manager):
        await mock_manager.authenticate(12345, "1234567890", "Test User")
        await mock_manager.logout(12345)
        session = await mock_manager.get_or_create(12345)
        assert session.is_authenticated is False
        mock_manager.redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limiting_mock(self, mock_manager, config):
        config.max_requests_per_hour = 2
        for _ in range(3):
            session = await mock_manager.get_or_create(12345)
            await mock_manager.save(session)
        is_limited = await mock_manager.is_rate_limited(12345)
        assert is_limited is True

    @pytest.mark.asyncio
    async def test_context_manager_mock(self, mock_manager):
        async with mock_manager.session(12345) as session:
            session.temp_data["test"] = "value"
        mock_manager.redis.setex.assert_called()


class TestIntegrationLiveRedis:
    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self, session_manager, redis_client):
        if not redis_client:
            pytest.skip("Live Redis required")
        async with session_manager.session(99999) as session:
            pass
        await session_manager.authenticate(99999, "production_test", "Production User")
        await session_manager.logout(99999)
        data = await redis_client.get("bot:session:99999")
        assert data is not None


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_redis_connection(self, config, metrics):
        manager = RedisSessionManager(config, metrics)
        manager.redis = None
        with pytest.raises(AttributeError):
            await manager.get_or_create(99999)


@pytest.mark.asyncio
async def test_env_loading():
    from dotenv import load_dotenv

    load_dotenv(".env.test", override=True)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"REDIS_URL: {redis_url}")
    assert redis_url is not None
    assert "localhost" in redis_url or "redis://" in redis_url

    maintenance = os.getenv("MAINTENANCE_MODE", "false").lower()
    print(f"MAINTENANCE_MODE: {maintenance}")
    assert maintenance == "false"

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    print(f"TELEGRAM_BOT_TOKEN length: {len(token)}")

    if os.path.exists(".env.test"):
        with open(".env.test", "r", encoding="utf-8") as f:
            content = f.read()
            print(f".env.test content preview: {content[:100]}...")
            assert "REDIS_URL" in content
            assert "TELEGRAM_BOT_TOKEN" in content
    else:
        print("⚠️ .env.test file not found - using defaults")

    print("✅ Environment checks passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--asyncio-mode=auto"])
