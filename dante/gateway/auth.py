"""Telegram Mini App initData HMAC validation and replay protection."""

import hashlib
import hmac
import json
import time
from collections import OrderedDict
from urllib.parse import parse_qs, unquote

# Replay protection: recent initData hashes with timestamp
_recent_hashes: OrderedDict[str, float] = OrderedDict()
_REPLAY_WINDOW = 300  # 5 minutes
_MAX_REPLAY_ENTRIES = 1000


class AuthError(Exception):
    """Raised when Telegram initData validation fails."""


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age: int = 300,
    check_replay: bool = True,
) -> dict:
    """Validate Telegram Mini App initData and return the parsed user data.

    Args:
        init_data: Raw initData query string from Telegram WebApp.
        bot_token: The bot token used to compute the HMAC.
        max_age: Maximum age of auth_date in seconds (default 5 min).
        check_replay: Whether to check for replay attacks.

    Returns:
        Dict with 'user' (parsed JSON), 'auth_date', 'query_id', etc.

    Raises:
        AuthError: If validation fails.
    """
    # Parse the query string
    parsed = parse_qs(init_data, keep_blank_values=True)

    # Extract hash
    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        raise AuthError("Missing hash in initData")

    # Build data_check_string: sorted key=value pairs joined by newline
    data_check_string = "\n".join(
        f"{k}={unquote(v[0])}" for k, v in sorted(parsed.items())
    )

    # Compute HMAC: secret_key = HMAC-SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise AuthError("Invalid initData signature")

    # Check auth_date freshness
    auth_date_str = parsed.get("auth_date", [None])[0]
    if not auth_date_str:
        raise AuthError("Missing auth_date")

    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise AuthError("Invalid auth_date format")

    age = time.time() - auth_date
    if age > max_age:
        raise AuthError(f"initData expired ({age:.0f}s > {max_age}s)")
    if age < -60:  # Allow small clock skew
        raise AuthError(f"initData from the future ({age:.0f}s)")

    # Replay protection
    if check_replay:
        _prune_replay_cache()
        if received_hash in _recent_hashes:
            raise AuthError("Replay detected: initData already used")
        _recent_hashes[received_hash] = time.time()

    # Parse user JSON
    result = {}
    for k, v in parsed.items():
        val = unquote(v[0])
        if k == "user":
            try:
                result["user"] = json.loads(val)
            except json.JSONDecodeError:
                raise AuthError("Invalid user JSON in initData")
        else:
            result[k] = val

    result["auth_date"] = auth_date
    return result


def _prune_replay_cache():
    """Remove expired entries from the replay cache."""
    cutoff = time.time() - _REPLAY_WINDOW
    while _recent_hashes:
        oldest_hash, oldest_time = next(iter(_recent_hashes.items()))
        if oldest_time < cutoff:
            _recent_hashes.pop(oldest_hash)
        else:
            break
    # Hard cap
    while len(_recent_hashes) > _MAX_REPLAY_ENTRIES:
        _recent_hashes.popitem(last=False)


def extract_user_id(validated_data: dict) -> int | None:
    """Extract the Telegram user ID from validated initData."""
    user = validated_data.get("user", {})
    return user.get("id")
