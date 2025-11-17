""" Pure Redis caching layer - handles ONLY cache operations """
import asyncio, json , logging
import redis.asyncio as aioredis
from typing import Any, Dict, Optional,List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CacheManager:
    """Async Redis cache wrapper with JSON serialization and health stats."""
    
    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.redis: Optional[aioredis.Redis] = None
        self.pool: Optional[aioredis.ConnectionPool] = None
        self._stats = dict(hits=0, misses=0, errors=0)
        self._lock = asyncio.Lock()

    def update_defaults_from_config(self, cfg: dict):
        self.default_ttl = cfg.get("cache_ttl", self.default_ttl)

    async def reload_connection(self, new_url: str):
        await self.shutdown()
        self.redis_url = new_url
        await self.startup()

    async def invalidate(self, key_pattern: str) -> int:
        """Delete cached entries matching the pattern, e.g. 'order:*' or full key - Returns number of deleted keys."""
        if not self.redis:
            return 0
        try:
            keys = await self.scan_keys(key_pattern)
            if not keys:
                return 0
            deleted = await self.redis.delete(*keys)
            logger.debug(f"Invalidated {deleted} cache item(s) for pattern: {key_pattern}")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidate error for pattern {key_pattern}: {e}")
            return 0

    async def startup(self) -> None:
        """Connect to Redis with retry."""
        for attempt in range(3):
            try:
                self.pool = aioredis.ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=20,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                self.redis = aioredis.Redis(connection_pool=self.pool)
                await self.redis.ping()
                return
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Redis Cache module connection failed: {e}", exc_info=True)
                    raise
                await asyncio.sleep(2 ** attempt)

    async def ping(self) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            self._stats["errors"] += 1
            return None
        try:
            val = await self.redis.get(key)
            if val is None:
                self._stats["misses"] += 1
                return None
            self._stats["hits"] += 1
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.redis:
            return False
        ttl = ttl or self.default_ttl
        try:
            if isinstance(value, (dict, list, tuple)):
                value_to_write = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, BaseModel):
                value_to_write = value.model_dump_json()
            else:
                value_to_write = str(value)
                
            await self.redis.setex(key, ttl, value_to_write)
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        if not self.redis or not keys:
            return 0
        try:
            return await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return 0

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        if not self.redis:
            self._stats["errors"] += 1
            return None
        try:
            return await self.redis.incr(key, amount)
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Cache increment error on {key}: {e}")
            return None

    async def expire(self, key: str, ttl: int) -> bool:
        if not self.redis:
            return False
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error: {e}")
            return False

    async def scan_keys(self, pattern: str) -> List[str]:
        if not self.redis:
            return []
        try:
            cursor, keys = 0, []
            while True:
                cursor, chunk = await self.redis.scan(cursor=cursor, match=pattern, count=200)
                keys.extend(chunk)
                if cursor == 0:
                    break
            return keys
        except Exception as e:
            logger.error(f"Scan error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total else 0
        return {
            "connected": self.redis is not None,
            **self._stats,
            "hit_rate": round(hit_rate, 3),
            "total_requests": total,
        }

    async def shutdown(self) -> None:
        """Graceful disconnect."""
        async with self._lock:
            try:
                if self.redis:
                    await self.redis.aclose()
                    self.redis = None
                if self.pool:
                    await self.pool.disconnect()
                    self.pool = None
                logger.info("Redis Cache module disconnected")
            except Exception as e:
                logger.debug(f"Redis Cache module shutdown error: {e}")
