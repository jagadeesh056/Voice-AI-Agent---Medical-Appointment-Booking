import os
import json
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class RedisCache:
    def __init__(self):
        try:
            self.client = redis.from_url(REDIS_URL, decode_responses=True)
            self.client.ping()
            print("[v0] Redis connection established")
        except Exception as e:
            print(f"[v0] Redis connection failed: {e}")
            self.client = None

    def is_connected(self):
        return self.client is not None

    def set_session(self, session_id: str, session_data: dict, ttl_minutes: int = 30):
        """Store session data in Redis"""
        try:
            key = f"session:{session_id}"
            self.client.setex(
                key,
                timedelta(minutes=ttl_minutes),
                json.dumps(session_data)
            )
            return True
        except Exception as e:
            print(f"[v0] Error setting session: {e}")
            return False

    def get_session(self, session_id: str):
        """Retrieve session data from Redis"""
        try:
            key = f"session:{session_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"[v0] Error getting session: {e}")
            return None

    def delete_session(self, session_id: str):
        """Delete session from Redis"""
        try:
            key = f"session:{session_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"[v0] Error deleting session: {e}")
            return False

    def store_conversation_context(self, session_id: str, context: dict, ttl_minutes: int = 30):
        """Store conversation context (last N turns) for the session"""
        try:
            key = f"context:{session_id}"
            self.client.setex(
                key,
                timedelta(minutes=ttl_minutes),
                json.dumps(context)
            )
            return True
        except Exception as e:
            print(f"[v0] Error storing context: {e}")
            return False

    def get_conversation_context(self, session_id: str):
        """Retrieve conversation context"""
        try:
            key = f"context:{session_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"[v0] Error getting context: {e}")
            return None

    def cache_user_data(self, user_id: int, user_data: dict, ttl_minutes: int = 60):
        """Cache user data for quick lookup"""
        try:
            key = f"user:{user_id}"
            self.client.setex(
                key,
                timedelta(minutes=ttl_minutes),
                json.dumps(user_data)
            )
            return True
        except Exception as e:
            print(f"[v0] Error caching user: {e}")
            return False

    def get_cached_user(self, user_id: int):
        """Get cached user data"""
        try:
            key = f"user:{user_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"[v0] Error retrieving cached user: {e}")
            return None


# Global cache instance
cache = RedisCache()
