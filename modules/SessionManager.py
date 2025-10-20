"""
Redis Session Manager - Handling Sessions (Data, Create, Rate Limit and etc) and Background Tasks
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from .CoreConfig import BotConfig, BotMetrics, UserState

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Minimal session data structure"""

    user_id: int
    chat_id: int
    state: UserState = UserState.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(minutes=30)
    )

    is_authenticated: bool = False
    nationalId: Optional[str] = None
    user_name: Optional[str] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None

    temp_data: Dict[str, Any] = field(default_factory=dict)

    last_activity: datetime = field(default_factory=datetime.now)
    request_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for Redis storage"""
        data = asdict(self)
        for key in ["created_at", "expires_at", "last_activity"]:
            if data[key]:
                data[key] = data[key].isoformat()
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionData":
        """Create instance from dictionary"""
        session_data = data.copy()

        for key in ["created_at", "expires_at", "last_activity"]:
            if session_data.get(key):
                session_data[key] = datetime.fromisoformat(session_data[key])

        if "state" in session_data:
            try:
                session_data["state"] = UserState(session_data["state"])
            except ValueError:
                session_data["state"] = UserState.IDLE

        session_data.setdefault("temp_data", {})
        session_data.setdefault("request_count", 0)

        return cls(**session_data)

    def is_expired(self) -> bool:
        """Check if session expired"""
        return datetime.now() > self.expires_at

    def extend(self, minutes: int = 30):
        """Extend session expiry"""
        self.expires_at = datetime.now() + timedelta(minutes=minutes)
        self.last_activity = datetime.now()


class RedisSessionManager:
    """Minimal async Redis session manager"""

    def __init__(self, config: BotConfig, metrics: BotMetrics):
        self.config = config
        self.metrics = metrics
        self.redis: Optional[aioredis.Redis] = None
        self.pool: Optional[aioredis.ConnectionPool] = None
        self._local_cache: Dict[int, SessionData] = {}
        self._lock = asyncio.Lock()
        # Redis key prefixes
        self.KEY_PREFIX = "bot:session:"
        self.AUTH_PREFIX = "bot:auth:"
        # TTL configuration
        self.DEFAULT_TTL = 1800  # 30 minutes
        self.AUTH_TTL = 3600  # 60 minutes
        self.MAX_CACHE_SIZE = 500

    async def connect(self):
        """Connect to Redis with proper connection pooling"""
        for attempt in range(3):
            try:
                self.pool = aioredis.ConnectionPool.from_url(
                    self.config.redis_url,
                    decode_responses=True,
                    max_connections=20,
                    socket_keepalive=True,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                self.redis = aioredis.Redis(connection_pool=self.pool)

                await self.redis.ping()
                logger.info("✅ Redis connected")
                return
            except Exception as e:
                if attempt == 2:  # Last attempt
                    logger.error(f"❌ Redis connection failed: {e}")
                    raise
                await asyncio.sleep(2**attempt)  # Exponential backoff inline

    async def disconnect(self):
        """Safely disconnect from Redis"""
        try:
            if self.redis:
                # Use aclose() instead of close() for redis-py 5.0+
                if hasattr(self.redis, "aclose"):
                    await self.redis.aclose()
                else:
                    await self.redis.close()  # Fallback for older versions
                self.redis = None

            if self.pool:
                await self.pool.disconnect()
                self.pool = None

            logger.info("Redis disconnected")
        except Exception as e:
            logger.debug(f"Disconnect error (expected during shutdown): {e}")

    @asynccontextmanager
    async def session(self, chat_id: int, user_id: Optional[int] = None):
        """Session context manager"""
        if not self.redis:
            logger.error("Redis not connected")
            yield None
            return

        session = await self.get_or_create(chat_id, user_id)
        try:
            yield session
        finally:
            if session:
                await self.save(session)

    async def get_or_create(
        self, chat_id: int, user_id: Optional[int] = None
    ) -> SessionData:
        """Get existing or create new session"""
        if not self.redis:
            logger.error("Redis not connected")
            return None

        # Check local cache
        if chat_id in self._local_cache:
            session = self._local_cache[chat_id]
            if not session.is_expired():
                if user_id and session.user_id != user_id:
                    session.user_id = user_id
                self.metrics.cache_hits += 1
                return session
            else:
                del self._local_cache[chat_id]

        # Check Redis
        key = f"{self.KEY_PREFIX}{chat_id}"
        data = await self.redis.get(key)

        if data:
            try:
                session = SessionData.from_dict(json.loads(data))
                if not session.is_expired():
                    if user_id and session.user_id != user_id:
                        session.user_id = user_id
                    self._local_cache[chat_id] = session
                    return session
            except Exception as e:
                logger.error(f"Session decode error: {e}")

        # Create new session - chat_id is primary, user_id must be provided or use chat_id
        actual_user_id = user_id or chat_id  # Fallback but log warning
        if user_id is None:
            logger.warning(f"Creating session for chat_id {chat_id} without user_id")

        session = SessionData(user_id=actual_user_id, chat_id=chat_id)
        await self.save(session)

        self.metrics.total_sessions += 1
        self.metrics.active_sessions = len(self._local_cache)
        logger.info(f"New session created: chat_id={chat_id}, user_id={actual_user_id}")
        return session

    async def save(self, session: SessionData):
        """Save session to Redis"""
        try:
            session.last_activity = datetime.now()
            session.request_count += 1

            ttl = self.AUTH_TTL if session.is_authenticated else self.DEFAULT_TTL

            # Save to Redis
            key = f"{self.KEY_PREFIX}{session.chat_id}"
            await self.redis.setex(key, ttl, json.dumps(session.to_dict()))
            self._local_cache[session.chat_id] = session

            # Cleanup cache if too large
            if len(self._local_cache) > self.MAX_CACHE_SIZE:
                await self._cleanup_cache()

        except Exception as e:
            logger.error(f"Save error: {e}")

    async def clear(self, chat_id: int):
        """Clear session completely"""
        try:
            if self.redis:
                key = f"{self.KEY_PREFIX}{chat_id}"
                try:
                    await self.redis.delete(key)
                except (ConnectionError, RuntimeError) as e:
                    logger.warning(f"Could not delete from Redis: {e}")

            if chat_id in self._local_cache:
                del self._local_cache[chat_id]

            self.metrics.active_sessions = len(self._local_cache)
            logger.info(f"Session cleared: {chat_id}")
        except Exception as e:
            logger.error(f"Error clearing session {chat_id}: {e}")

    async def _cleanup_cache(self):
        """Clean up local cache - remove expired and limit size"""
        async with self._lock:
            expired_keys = []

            for chat_id, session in list(self._local_cache.items()):
                if session.is_expired():
                    expired_keys.append(chat_id)

            for chat_id in expired_keys[
                : len(expired_keys) // 2
            ]:  # Remove half to avoid blocking
                try:
                    del self._local_cache[chat_id]
                    # Also clean from Redis if still there
                    redis_key = f"{self.KEY_PREFIX}{chat_id}"
                    await self.redis.delete(redis_key)
                except Exception:
                    pass

            # Limit cache size if still too large
            if len(self._local_cache) > self.MAX_CACHE_SIZE:
                # Remove oldest sessions (by created_at)
                sorted_sessions = sorted(
                    self._local_cache.items(), key=lambda x: x[1].created_at
                )
                to_remove = (
                    len(sorted_sessions) - self.MAX_CACHE_SIZE // 2
                )  # Keep half capacity

                for chat_id, _ in sorted_sessions[:to_remove]:
                    try:
                        del self._local_cache[chat_id]
                    except KeyError:
                        pass

            self.metrics.active_sessions = len(self._local_cache)
            logger.debug(f"Cache cleaned: {len(self._local_cache)} active sessions")

    async def update_state(self, chat_id: int, new_state: UserState, **kwargs):
        """Update session state"""
        async with self.session(chat_id) as session:
            old_state = session.state
            session.state = new_state
            session.extend()

            if kwargs:
                session.temp_data.update(kwargs)

            logger.info(
                f"State changed: chat_id={chat_id} {old_state.name} -> {new_state.name}"
            )
            return session

    async def authenticate(
        self, chat_id: int, nationalId: str, name: str, user_id: Optional[int] = None
    ):
        """Authenticate user - chat_id is primary"""
        session = await self.get_or_create(chat_id, user_id)
        if not session:
            return None
        session.is_authenticated = True
        session.nationalId = nationalId
        session.user_name = name
        session.state = UserState.AUTHENTICATED
        session.extend(60)

        auth_key = f"{self.AUTH_PREFIX}{nationalId}"
        await self.redis.setex(auth_key, self.AUTH_TTL, chat_id)

        self.metrics.authenticated_users += 1
        logger.info(
            f"User authenticated: chat_id={chat_id}, user_id={session.user_id}, name={name}"
        )
        return session

    async def logout(self, chat_id: int):
        """Logout user"""
        async with self.session(chat_id) as session:
            if session.nationalId:
                auth_key = f"{self.AUTH_PREFIX}{session.nationalId}"
                await self.redis.delete(auth_key)

            session.is_authenticated = False
            session.nationalId = None
            session.user_name = None
            session.state = UserState.IDLE
            session.temp_data.clear()

            if self.metrics.authenticated_users > 0:
                self.metrics.authenticated_users -= 1

            logger.info(f"User logged out: chat_id={chat_id}")

    async def get_user_by_nationalId(self, nationalId: str) -> Optional[int]:
        """Get chat_id by national ID"""
        if not self.redis:
            return None
        auth_key = f"{self.AUTH_PREFIX}{nationalId}"
        chat_id = await self.redis.get(auth_key)
        return int(chat_id) if chat_id else None

    async def is_rate_limited(self, chat_id: int) -> bool:
        """Check if user is rate limited"""
        session = await self.get_or_create(chat_id)
        if not session:
            return False

        max_requests = getattr(self.config, "max_requests_per_hour", 100)

        if session.request_count > max_requests:
            session.state = UserState.RATE_LIMITED
            session.temp_data["rate_limit_expires"] = (
                datetime.now() + timedelta(hours=1)
            ).timestamp()
            await self.save(session)
            return True

        return False

    async def get_active_sessions(self) -> List[SessionData]:
        """Get all active sessions from cache and Redis"""
        active_sessions = []

        for chat_id, session in self._local_cache.items():
            if not session.is_expired():
                active_sessions.append(session)

        if self.redis:
            cursor = "0"
            while cursor != 0:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=f"{self.KEY_PREFIX}*",
                    count=50,  # Smaller batch for performance
                )

                for key in keys:
                    chat_id = int(key.replace(f"{self.KEY_PREFIX}", ""))
                    if chat_id not in self._local_cache:  # Skip cached
                        try:
                            data = await self.redis.get(key)
                            if data:
                                session = SessionData.from_dict(json.loads(data))
                                if not session.is_expired():
                                    active_sessions.append(session)
                        except Exception:
                            continue

        return active_sessions

    async def get_stats(self) -> Dict:
        """Get session statistics"""
        if not self.redis:
            return {
                "total_sessions": 0,
                "authenticated_sessions": 0,
                "cached_sessions": len(self._local_cache),
                "cache_hit_rate": 0.0,
                "total_requests": self.metrics.total_requests,
            }

        cursor = "0"
        total = 0
        authenticated = 0

        while cursor != 0:
            cursor, keys = await self.redis.scan(
                cursor=cursor, match=f"{self.KEY_PREFIX}*", count=100
            )
            total += len(keys)

            for key in keys:
                try:
                    data = await self.redis.get(key)
                    if data:
                        session_dict = json.loads(data)
                        if session_dict.get("is_authenticated", False):
                            authenticated += 1
                except Exception:
                    continue

        cache_ratio = self.metrics.cache_hits / max(
            self.metrics.cache_hits + self.metrics.cache_misses, 1
        )

        return {
            "total_sessions": total,
            "authenticated_sessions": authenticated,
            "cached_sessions": len(self._local_cache),
            "cache_hit_rate": cache_ratio,
            "total_requests": self.metrics.total_requests,
        }

    async def cleanup_expired(self):
        """Clean up expired sessions from Redis"""
        if not self.redis:
            return 0

        cursor = "0"
        deleted = 0

        while cursor != 0:
            cursor, keys = await self.redis.scan(
                cursor=cursor, match=f"{self.KEY_PREFIX}*", count=100
            )

            for key in keys:
                try:
                    data = await self.redis.get(key)
                    if data:
                        session_dict = json.loads(data)
                        expires_at_str = session_dict.get("expires_at")
                        if expires_at_str:
                            expires_at = datetime.fromisoformat(expires_at_str)
                            if datetime.now() > expires_at:
                                await self.redis.delete(key)
                                deleted += 1
                except Exception:
                    continue

        logger.info(f"Cleaned up {deleted} expired sessions")
        return deleted


class SessionBackgroundTasks:
    """Background tasks for session management"""

    def __init__(self, manager: RedisSessionManager):
        self.manager = manager
        self.cleanup_task = None
        self.running = False

    async def start(self):
        """Start background tasks"""
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Background tasks started")

    async def stop(self):
        """Stop background tasks"""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Background tasks stopped")

    async def _cleanup_loop(self):
        """Periodic cleanup task"""
        while self.running:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                if self.manager.redis:
                    deleted = await self.manager.cleanup_expired()
                    await self.manager._cleanup_cache()
                    logger.debug(
                        f"Background cleanup: deleted {deleted} expired sessions"
                    )
            except asyncio.CancelledError:
                logger.debug("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry on error


async def create_session_manager(
    config: BotConfig, metrics: BotMetrics
) -> RedisSessionManager:
    """Factory to create and initialize session manager"""
    manager = RedisSessionManager(config, metrics)
    await manager.connect()

    tasks = SessionBackgroundTasks(manager)
    await tasks.start()
    manager.background_tasks = tasks

    # Test connection
    test_session = await manager.get_or_create(999999)  # Dummy chat_id
    if test_session:
        await manager.save(test_session)
        logger.info("✅ Session manager initialized successfully")
    else:
        logger.error("❌ Session manager initialization failed")

    return manager


def format_session_info(session: SessionData) -> str:
    """Format session info for display"""
    info = f"""
📊 Session Info:
• User ID: {session.user_id}
• Chat ID: {session.chat_id or 'N/A'}
• State: {session.state.name}
• Authenticated: {'✅' if session.is_authenticated else '❌'}
• User: {session.user_name or 'N/A'}
• National ID: {session.nationalId or 'N/A'}
• Requests: {session.request_count}
• Expires: {session.expires_at.strftime('%Y-%m-%d %H:%M')}
    """
    return info.strip()
