""" Session management layer - uses cache for persistence """
import logging
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, Optional, List, AsyncGenerator
from aiogram.fsm.storage.redis import RedisStorage

from src.core.dynamic import DynamicConfigManager
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
    
    def __init__(self, cache: CacheManager):
        self.cache = cache
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
        
        if user_id and session.user_id != user_id:
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
            return await self.cache.set(key, session.model_dump_json(), ttl)
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
            await self._save(session)
            logger.info(f"Authenticated user {national_id} at chat={chat_id}")
            return session
    
    async def logout(self, chat_id: int) -> None:
        """Clear authentication and persist logout state."""
        async with self.get_session(chat_id) as session:
            if session.national_id:
                await self.cache.delete(f"{self.AUTH_PREFIX}{session.national_id}")
            
            session.is_authenticated = False
            session.national_id = None
            session.user_name = None
            session.phone_number = None
            session.state = UserState.IDLE
            session.temp_data.clear()
            await self._save(session)
            logger.info(f"Logged out: chat_id={chat_id}")
    
    async def update_state(self,chat_id: int, new_state: UserState, **kwargs) -> UserSession:
        """Update user's FSM state and persist."""
        async with self.get_session(chat_id) as session:
            old_state = session.state
            session.state = new_state
            if kwargs:
                session.temp_data.update(kwargs)

            logger.debug(f"State: {old_state.name} → {new_state.name} (chat={chat_id})")
            await self._save(session)
            return session

    async def track_message(self, chat_id: int, message_id: int):
        """Append bot message ID to tracked list."""
        async with self.get_session(chat_id) as session:
            session.last_bot_messages = (session.last_bot_messages + [message_id])[-5:]
            await self._save(session)

    async def cleanup_messages(self, bot, chat_id: int):
        """Delete tracked bot messages safely."""
        async with self.get_session(chat_id) as session:
            deleted = 0
            for mid in session.last_bot_messages:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=mid)
                    deleted += 1
                except Exception as e:
                    logger.debug(f"Cleanup skip mid={mid}: {e}")
            session.last_bot_messages.clear()
            await self._save(session)
            logger.info(f"Cleaned up {deleted} messages for chat={chat_id}")

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
    
    def __init__(self, session_manager: SessionManager):
        self.manager = session_manager
        self._task : Optional[asyncio.Task] = None
    
    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._cleanup_loop(interval=3600))
        logger.info("Session background cleanup task started.")

    async def _cleanup_loop(self, interval: int):
        """Periodically scan for and delete expired sessions if Redis TTL fails."""
        while True:
            await asyncio.sleep(interval)
            try:
                logger.info("Running periodic expired session cleanup...")
                count = 0
                all_sessions_keys = await self.manager.cache.scan_keys(f"{self.manager.SESSION_PREFIX}*")
                for key in all_sessions_keys:
                    pass # We can add cleanup logic here if needed later.
                logger.info(f"Cleanup finished. Scanned {len(all_sessions_keys)} sessions.")
            except asyncio.CancelledError:
                logger.info("Background cleanup task stopped.")
                break
            except Exception as e:
                logger.error(f"Background cleanup loop error: {e}", exc_info=True)

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    