# app/auth/redis.py

import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


async def add_to_blacklist(jti: str, exp: int):
    """Add a token's JTI to the blacklist"""
    await redis_client.set(f"blacklist:{jti}", "1", ex=exp)


async def is_blacklisted(jti: str) -> bool:
    """Check if a token's JTI is blacklisted"""
    return await redis_client.exists(f"blacklist:{jti}")
