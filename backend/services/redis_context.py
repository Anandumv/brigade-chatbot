"""
Redis Context Manager for Multi-Turn Conversation Persistence
Replaces in-memory session storage with Redis for production durability.
"""

import redis
import json
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisContextManager:
    """
    Manages conversation context in Redis with sliding TTL.

    Context Structure (Spec-Compliant):
    {
        "call_id": "uuid",
        "active_project": None | str,
        "last_budget": None | int (INR),
        "last_location": None | str,
        "last_results": [],  # List of project dicts
        "last_filters": {},  # Quick filters dict
        "signals": {
            "price_sensitive": False,
            "upgrade_intent": False
        }
    }
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = 5400,  # 90 minutes (spec requirement)
        fallback_to_memory: bool = True
    ):
        """
        Initialize Redis context manager.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            ttl_seconds: TTL for context keys (default: 5400s = 90min)
            fallback_to_memory: If True, fallback to in-memory dict on Redis failure
        """
        self.ttl = ttl_seconds
        self.fallback_to_memory = fallback_to_memory
        self.memory_store: Dict[str, Dict[str, Any]] = {}  # Fallback storage
        self.redis_available = False

        try:
            self.client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            # Test connection
            self.client.ping()
            self.redis_available = True
            logger.info(f"✅ Redis connected successfully: {redis_url}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            if not fallback_to_memory:
                raise
            logger.info("Falling back to in-memory storage (context will not persist across restarts)")
            self.client = None

    def load_context(self, call_id: str) -> Dict[str, Any]:
        """
        Load conversation context for a given call_id.
        Implements sliding window TTL (resets expiry on every load).

        Args:
            call_id: Unique identifier for the conversation

        Returns:
            Context dict (default structure if not found)
        """
        key = f"call:{call_id}"

        # Try Redis first
        if self.redis_available and self.client:
            try:
                data = self.client.get(key)
                if data:
                    # Sliding window: reset TTL on access
                    self.client.expire(key, self.ttl)
                    context = json.loads(data)
                    logger.debug(f"📥 Loaded context from Redis for call_id={call_id}")
                    return context
            except Exception as e:
                logger.error(f"Redis load error for {call_id}: {e}")
                if not self.fallback_to_memory:
                    raise

        # Fallback to in-memory storage
        if call_id in self.memory_store:
            logger.debug(f"📥 Loaded context from memory for call_id={call_id}")
            return self.memory_store[call_id]

        # Return default context (spec-compliant structure)
        logger.debug(f"🆕 Creating new context for call_id={call_id}")
        return self._default_context(call_id)

    def save_context(self, call_id: str, context: Dict[str, Any]) -> bool:
        """
        Save conversation context to Redis with TTL.

        Args:
            call_id: Unique identifier for the conversation
            context: Context dict to save

        Returns:
            True if saved successfully, False otherwise
        """
        key = f"call:{call_id}"

        # Ensure call_id is set in context
        context["call_id"] = call_id

        # Try Redis first
        if self.redis_available and self.client:
            try:
                serialized = json.dumps(context)
                self.client.setex(key, self.ttl, serialized)
                logger.debug(f"💾 Saved context to Redis for call_id={call_id} (TTL={self.ttl}s)")
                return True
            except Exception as e:
                logger.error(f"Redis save error for {call_id}: {e}")
                if not self.fallback_to_memory:
                    raise

        # Fallback to in-memory storage
        self.memory_store[call_id] = context
        logger.debug(f"💾 Saved context to memory for call_id={call_id}")
        return True

    def delete_context(self, call_id: str) -> bool:
        """
        Delete conversation context (e.g., on explicit user logout).

        Args:
            call_id: Unique identifier for the conversation

        Returns:
            True if deleted successfully, False otherwise
        """
        key = f"call:{call_id}"

        # Delete from Redis
        if self.redis_available and self.client:
            try:
                self.client.delete(key)
                logger.debug(f"🗑️ Deleted context from Redis for call_id={call_id}")
            except Exception as e:
                logger.error(f"Redis delete error for {call_id}: {e}")

        # Delete from in-memory fallback
        if call_id in self.memory_store:
            del self.memory_store[call_id]
            logger.debug(f"🗑️ Deleted context from memory for call_id={call_id}")

        return True

    def _default_context(self, call_id: str) -> Dict[str, Any]:
        """
        Create default context structure (spec-compliant).

        Args:
            call_id: Unique identifier for the conversation

        Returns:
            Default context dict
        """
        return {
            "call_id": call_id,
            "active_project": None,
            "last_budget": None,
            "last_location": None,
            "last_results": [],
            "last_filters": {},
            "signals": {
                "price_sensitive": False,
                "upgrade_intent": False
            }
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check Redis connection health.

        Returns:
            Health status dict
        """
        if not self.redis_available or not self.client:
            return {
                "redis_available": False,
                "fallback_mode": "in-memory",
                "status": "degraded"
            }

        try:
            self.client.ping()
            return {
                "redis_available": True,
                "fallback_mode": None,
                "status": "healthy"
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "redis_available": False,
                "fallback_mode": "in-memory" if self.fallback_to_memory else "none",
                "status": "unhealthy",
                "error": str(e)
            }


# Global instance (initialized in main.py with config)
redis_context_manager: Optional[RedisContextManager] = None


def get_redis_context_manager() -> RedisContextManager:
    """
    Dependency injection helper for FastAPI endpoints.

    Returns:
        Global RedisContextManager instance

    Raises:
        RuntimeError if not initialized
    """
    if redis_context_manager is None:
        raise RuntimeError("RedisContextManager not initialized. Call init_redis_context_manager() first.")
    return redis_context_manager


def init_redis_context_manager(redis_url: str, ttl_seconds: int = 5400) -> RedisContextManager:
    """
    Initialize global RedisContextManager instance.
    Should be called once at application startup.

    Args:
        redis_url: Redis connection URL
        ttl_seconds: TTL for context keys (default: 5400s = 90min)

    Returns:
        Initialized RedisContextManager instance
    """
    global redis_context_manager
    redis_context_manager = RedisContextManager(redis_url, ttl_seconds)
    return redis_context_manager
