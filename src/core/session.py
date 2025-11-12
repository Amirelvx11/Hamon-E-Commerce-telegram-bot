""" Session management layer - uses cache for persistence """
import asyncio, logging
from contextlib import asynccontextmanager
from typing import Optional, List, AsyncGenerator
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.methods import DeleteMessages
from src.core.cache import CacheManager
from src.config.enums import UserState
from src.models.user import UserSession

logger = logging.getLogger(__name__)

class SessionManager:
    """Stateless, Redis-backed async session manager."""
    SESSION_PREFIX = "bot:session:"
    AUTH_PREFIX = "bot:auth:"
    DEFAULT_TTL = 1800  # 30 min
    AUTH_TTL = 3600     # 60 min
    
    def __init__(self, cache: CacheManager, notifications=None):
        self.cache = cache
        self.notifications = notifications
        self.metrics = { 'sessions_created': 0, 'auth_success': 0 }

    def update_defaults_from_config(self, cfg: dict):
        self.DEFAULT_TTL = cfg.get("session_ttl", self.DEFAULT_TTL)
        self.AUTH_TTL = cfg.get("auth_ttl", self.AUTH_TTL)

    async def get_fsm_storage(self) -> RedisStorage:
        """Return Aiogram-compatible FSM storage using the existing cache Redis client."""
        try:
            if not self.cache.redis:
                raise RuntimeError("Redis client not initialized in cache manager.")
            return RedisStorage(redis=self.cache.redis)
        except Exception as e:
            logger.error(f"Failed to initialize FSM storage: {e}", exc_info=True)
            raise

    @asynccontextmanager
    async def get_session(self, chat_id: int, user_id: Optional[int] = None) -> AsyncGenerator[UserSession, None]:
        """Context-managed safe session handling. Creates if non-existent, saves on exit."""
        session = await self._get(chat_id)

        if not session:
            session = UserSession(chat_id=chat_id, user_id=user_id or chat_id)
            self.metrics["sessions_created"] += 1
            logger.info(f"New session created for chat_id={chat_id}")
        
        if user_id:
            session.user_id = user_id
        try:
            yield session
        finally:
            if session:
                session.refresh() 
                await self._save(session)
    
    async def _get(self, chat_id: int) -> Optional[UserSession]:
        """Internal: fetch session directly from Redis."""
        key = f"{self.SESSION_PREFIX}{chat_id}"
        data = await self.cache.get(key)
        if data:
            try:
                return UserSession.model_validate(data)
            except Exception as e:
                logger.error(f"Session parsing failed for {chat_id}: {e}")
                await self.delete(chat_id)
        return None

    async def _save(self, session: UserSession) -> bool:
        """Internal: write session to Redis."""
        key = f"{self.SESSION_PREFIX}{session.chat_id}"
        ttl = self.AUTH_TTL if session.is_authenticated else self.DEFAULT_TTL
        try:
            return await self.cache.set(key, session.model_dump_json(exclude_none=True), ttl)
        except Exception as e:
            logger.error(f"Session save failed for {key}: {e}")
            return False

    async def delete(self, chat_id: int) -> None:
        """Completely delete session from Redis."""
        await self.cache.delete(f"{self.SESSION_PREFIX}{chat_id}")
        logger.info(f"Session deleted: {chat_id}")
    
    async def authenticate(self, chat_id: int, national_id: str, user_name: str,
                       phone: Optional[str] = None, city: Optional[str] = None,
                       user_id: Optional[int] = None) -> UserSession:
        async with self.get_session(chat_id, user_id) as session:
            session.is_authenticated = True
            session.national_id = national_id
            session.user_name = user_name
            session.phone_number = phone
            session.city = city
            session.state = UserState.AUTHENTICATED
            session.refresh(minutes=60)

            await self.cache.set(f"{self.AUTH_PREFIX}{national_id}", chat_id, self.AUTH_TTL)
            self.metrics["auth_success"] += 1
            logger.info(f"Authenticated user {national_id} at chat={chat_id}")
            return session
    
    async def logout(self, chat_id: int) -> None:
        """Clear authentication state within a session context."""
        async with self.get_session(chat_id) as session:
            if session.national_id:
                await self.cache.delete(f"{self.AUTH_PREFIX}{session.national_id}")
            
            session.is_authenticated = False
            session.national_id = None
            session.user_name = None
            session.phone_number = None
            session.state = UserState.IDLE
            session.temp_data.clear()
            logger.info(f"Logged out: chat_id={chat_id}")
    
    async def update_state(self,chat_id: int, new_state: UserState, **kwargs) -> UserSession:
        """Update user's FSM state and persist."""
        async with self.get_session(chat_id) as session:
            old_state = session.state
            session.state = new_state
            if kwargs:
                session.temp_data.update(kwargs)

            logger.debug(f"State: {old_state.name} → {new_state.name} (chat={chat_id})")
            return session

    async def track_message(self, chat_id: int, message_id: int):
        """Append bot message ID to tracked list."""
        async with self.get_session(chat_id) as session:
            session.last_bot_messages = (session.last_bot_messages + [message_id])[-5:]

    async def cleanup_messages(self, bot, chat_id: int,* , keep_message_id: int | None = None, limit: int | None = None) -> int:
        """Delete tracked bot messages safely with optional limit."""
        async with self.get_session(chat_id) as session:
            msg_ids = session.last_bot_messages[-limit:] if limit else session.last_bot_messages
            if not msg_ids: return 0

            if keep_message_id:
                msg_ids = [mid for mid in msg_ids if mid != keep_message_id]

            total_deleted = 0            
            try:
                # Split into chunks of ≤100 IDs — Telegram API limit
                for chunk in [msg_ids[i:i+100] for i in range(0, len(msg_ids), 100)]:
                    try:
                        result: bool = await bot(DeleteMessages(chat_id=chat_id, message_ids=chunk))
                    except Exception as e:
                        logger.debug(f"Bulk delete fallback due to {e}")
                        result: bool = await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
                    if result:
                        total_deleted += len(chunk)
                    else:
                        logger.warning(f"Partial cleanup failed for chat={chat_id}, chunk={chunk}")

                session.last_bot_messages = ([keep_message_id] if keep_message_id else [])
                await self._save(session)

                return total_deleted

            except Exception as e:
                logger.warning(f"Cleanup failed for chat={chat_id}: {e}", exc_info=True)
                return 0

    async def is_rate_limited(self, chat_id: int, max_requests: int = 100, window_seconds: int = 3600) -> bool:
        """rate limit check using cache atomic increment."""
        key = f"rate:{chat_id}"
        try:
            count = await self.cache.increment(key) or 0
            if count == 1:
                await self.cache.expire(key, window_seconds)
            elif count > max_requests:
                ttl = await self.cache.redis.ttl(key) if self.cache.redis else window_seconds
                if not self.notifications:
                    from src.services.notifications import NotificationService
                    bot_ref = getattr(self.cache, "bot", None)
                    if bot_ref:
                        self.notifications = NotificationService(bot_ref, self)
                if self.notifications:
                    await self.notifications.rate_limit_exceeded(chat_id, ttl or window_seconds)
                return True
            return False
        except Exception as e:
            logger.error(f"Rate-limit check failed for {chat_id}: {e}")
            return False

    async def cleanup_expired(self) -> list[UserSession]:
        """
        Scan Redis for sessions past their expiry window.
        Return list of UserSession objects that were removed.
        """
        expired_sessions = []
        try:
            keys = await self.cache.scan_keys(f"{self.SESSION_PREFIX}*")
            for key in keys:
                try:
                    raw = await self.cache.get(key)
                    if not raw:
                        continue
                    session = UserSession.model_validate(raw)
                    if session.is_expired():
                        await self.delete(session.chat_id)
                        expired_sessions.append(session)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Expired cleanup failure: {e}", exc_info=True)
        return expired_sessions

    async def get_by_national_id(self, national_id: str) -> Optional[int]:
        """Find chat_id by national ID"""
        return await self.cache.get(f"{self.AUTH_PREFIX}{national_id}")

    async def get_all_chat_ids(self) -> List[int]:
        """Scans Redis for all session keys and returns the chat IDs. Use for broadcasts."""
        chat_ids = []
        keys = await self.cache.scan_keys(f"{self.SESSION_PREFIX}*")
        for key in keys:
            try:
                chat_id_str = key.decode("utf-8").split(":")[1]
                chat_ids.append(int(chat_id_str))
            except (IndexError, ValueError):
                logger.warning(f"Could not parse chat_id from Redis key: {key}")
        return chat_ids

    async def get_stats(self) -> dict:
        """Aggregate runtime session stats, compatible with admin dashboard."""
        try:
            cache_stats = self.cache.get_stats()
            metrics = self.metrics

            keys = await self.cache.scan_keys(f"{self.SESSION_PREFIX}*")
            total_sessions = len(keys)
            auth_count = 0
            for key in keys:
                data = await self.cache.get(key)
                if data and isinstance(data, dict):
                    if data.get("is_authenticated", False):
                        auth_count += 1

            return {
                "total_sessions": total_sessions,
                "authenticated_sessions": auth_count,
                "cached_sessions": cache_stats.get("cached_items", 0),
                "total_requests": cache_stats.get("requests_total", 0),
                "cache_hit_rate": cache_stats.get("hit_rate", 0.0),
            }
        except Exception as e:
            logger.error(f"Session stats collection failed: {e}", exc_info=True)
            return {
                "total_sessions": 0,
                "authenticated_sessions": 0,
                "cached_sessions": 0,
                "cache_hit_rate": 0.0,
                "total_requests": 0,
            }

    def get_metrics(self) -> dict:
        """Get session metrics"""
        return {**self.metrics, **self.cache.get_stats()}

class BackgroundTasks:
    """Periodic background tasks for session cleanup."""
    from src.services.notifications import NotificationService
    
    def __init__(self, session_manager: SessionManager, notifications):
        self.manager = session_manager
        self.notifications = notifications
        self._task : Optional[asyncio.Task] = None
    
    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._cleanup_loop(interval=3600))
        logger.info("Session background cleanup task started.")

    async def _cleanup_loop(self, interval: int = 1800):
        """Periodically clean expired sessions and notify users."""
        while True:
            await asyncio.sleep(interval)
            try:
                expired_list = await self.manager.cleanup_expired()
                for s in expired_list:
                    await self.notifications.session_expired(s.chat_id)
                logger.info(f"Expired sessions cleaned: {len(expired_list)}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop runtime error: {e}", exc_info=True)

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    