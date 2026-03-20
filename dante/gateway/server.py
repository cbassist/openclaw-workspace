"""Donna voice gateway — FastAPI server for Phase 2 real-time voice."""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import sys
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import AuthError, validate_init_data, extract_user_id

# --- Load .env (same loader as bot.py) ---
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# --- Config ---
BOT_TOKEN = os.environ.get("DONNA_BOT_TOKEN", "")
AUTHORIZED_USERS = {8246962767}
ELEVENLABS_AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID", "")
GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8765"))
MINIAPP_URL = os.environ.get("MINIAPP_URL", "")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
WORKING_DIR = os.environ.get("DONNA_WORKDIR", os.path.expanduser("~/projects/openclaw-workspace"))
VOICE_SESSION_SECRET = os.environ.get("VOICE_SESSION_SECRET", "")

SYSTEM_PROMPT = (
    "You are Donna, a Claude Code instance in a real-time voice conversation via Telegram. "
    "Keep responses concise and conversational — the user is hearing your reply spoken aloud. "
    "You have full access to the openclaw-workspace and can run commands. "
    "Follow the Agent Coordination Protocol: canonical task flow is todo -> doing -> review -> done; "
    "as a Coding Agent you may move work only as far as review, never mark done unless you are explicitly acting as reviewer; "
    "user validation means only true human-only actions like permissions or subjective UX judgment, not reversible technical decisions; "
    "for reversible low-risk decisions, choose a reasonable path and proceed; "
    "for Python work use uv-managed workflows only and never install libraries into system Python. "
    "Archon source of truth: document 39786ee2-bb59-44db-8abe-008ce588bc48, mirrored locally at dante/AGENT_COORDINATION_PROTOCOL.md."
)

log = logging.getLogger("dante.gateway")

# --- Session store (in-memory for v1) ---
# Key: "telegram:{user_id}:voice" -> session dict
_sessions: dict[str, dict] = {}

# Session history: session_key -> list of {role, text, timestamp}
_session_history: dict[str, list[dict]] = defaultdict(list)
_MAX_SESSION_HISTORY = 40


# Session bearer tokens: token -> {user_id, session_id, created_at}
_session_tokens: dict[str, dict] = {}
_SESSION_TOKEN_TTL = 300  # 5 minutes


def _prune_session_tokens():
    """Remove expired session tokens."""
    cutoff = time.time() - _SESSION_TOKEN_TTL
    expired = [k for k, v in _session_tokens.items() if v["created_at"] < cutoff]
    for k in expired:
        del _session_tokens[k]


# --- Models ---
class SessionResponse(BaseModel):
    session_id: str
    user_id: int
    session_token: str  # Bearer token for subsequent calls (e.g. /api/token)


class TokenResponse(BaseModel):
    signed_url: str
    session_id: str


# --- Rate limiter (simple in-memory, per-IP) ---
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 20  # per window per IP

MAX_REQUEST_BODY = 64 * 1024  # 64 KB


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only rate-limit sensitive endpoints
        path = request.url.path
        if path in ("/api/session", "/api/token"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            key = f"{client_ip}:{path}"
            # Prune old entries
            _rate_limits[key] = [t for t in _rate_limits[key] if t > now - RATE_LIMIT_WINDOW]
            if len(_rate_limits[key]) >= RATE_LIMIT_MAX_REQUESTS:
                log.warning("Rate limit exceeded: %s %s", client_ip, path)
                return Response(
                    content='{"detail":"Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                )
            _rate_limits[key].append(now)

        # Body size limit for POST requests
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_REQUEST_BODY:
                return Response(
                    content='{"detail":"Request body too large"}',
                    status_code=413,
                    media_type="application/json",
                )

        return await call_next(request)


# --- App ---
app = FastAPI(title="Donna Voice Gateway", version="0.1.0")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production via MINIAPP_URL
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def _parse_tma_header(authorization: str | None) -> str:
    """Extract initData from 'tma {initData}' authorization header."""
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[4:]


def _session_key(user_id: int) -> str:
    return f"telegram:{user_id}:voice"


def _session_id_from_key(key: str) -> str:
    """Derive a stable, opaque session ID from the session key."""
    return hashlib.sha256(key.encode()).hexdigest()[:24]


@app.post("/api/session", response_model=SessionResponse)
async def create_session(authorization: str | None = Header(None)):
    """Create or resume a Donna voice session."""
    init_data = _parse_tma_header(authorization)

    try:
        validated = validate_init_data(init_data, BOT_TOKEN)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id = extract_user_id(validated)
    if user_id is None:
        raise HTTPException(status_code=401, detail="No user ID in initData")

    if user_id not in AUTHORIZED_USERS:
        raise HTTPException(status_code=403, detail="User not authorized")

    key = _session_key(user_id)
    session_id = _session_id_from_key(key)

    # Create or resume session
    if key not in _sessions:
        _sessions[key] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": time.time(),
            "last_active": time.time(),
        }
        log.info("New voice session: user_id=%s session_id=%s", user_id, session_id)
    else:
        _sessions[key]["last_active"] = time.time()
        log.info("Resumed voice session: user_id=%s session_id=%s", user_id, session_id)

    # Issue a short-lived session token for subsequent calls (avoids replay on /api/token)
    session_token = secrets.token_urlsafe(32)
    _prune_session_tokens()
    _session_tokens[session_token] = {
        "user_id": user_id,
        "session_id": session_id,
        "created_at": time.time(),
    }

    return SessionResponse(session_id=session_id, user_id=user_id, session_token=session_token)


@app.post("/api/token", response_model=TokenResponse)
async def mint_token(authorization: str | None = Header(None)):
    """Mint a signed WebRTC URL for ElevenLabs real-time voice.

    Accepts 'Bearer {session_token}' from /api/session (preferred, avoids replay)
    or 'tma {initData}' (fallback).
    """
    import httpx

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if authorization.startswith("Bearer "):
        # Validate session token issued by /api/session
        token = authorization[7:]
        token_data = _session_tokens.pop(token, None)  # One-time use
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired session token")
        if time.time() - token_data["created_at"] > _SESSION_TOKEN_TTL:
            raise HTTPException(status_code=401, detail="Session token expired")
        user_id = token_data["user_id"]
        session_id = token_data["session_id"]
    elif authorization.startswith("tma "):
        # Fallback: validate initData directly (skip replay for token endpoint)
        init_data = authorization[4:]
        try:
            validated = validate_init_data(init_data, BOT_TOKEN, check_replay=False)
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        user_id = extract_user_id(validated)
        if user_id is None or user_id not in AUTHORIZED_USERS:
            raise HTTPException(status_code=403, detail="User not authorized")
        key = _session_key(user_id)
        session_id = _session_id_from_key(key)
    else:
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")

    if not ELEVENLABS_AGENT_ID:
        raise HTTPException(status_code=503, detail="ElevenLabs agent not configured")

    elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not elevenlabs_api_key:
        raise HTTPException(status_code=503, detail="ElevenLabs API key not configured")

    # Call ElevenLabs to get a signed WebRTC URL
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url",
                params={"agent_id": ELEVENLABS_AGENT_ID},
                headers={"xi-api-key": elevenlabs_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            signed_url = data.get("signed_url", "")
    except httpx.HTTPStatusError as e:
        log.error("ElevenLabs token mint failed: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=502, detail="Failed to get ElevenLabs signed URL")
    except Exception as e:
        log.error("ElevenLabs token mint error: %s", e)
        raise HTTPException(status_code=502, detail="ElevenLabs service unavailable")

    if not signed_url:
        raise HTTPException(status_code=502, detail="Empty signed URL from ElevenLabs")

    log.info("AUDIT token_mint: user_id=%s session_id=%s", user_id, session_id)
    return TokenResponse(signed_url=signed_url, session_id=session_id)


@app.get("/health")
async def health():
    """Health check with diagnostics."""
    import shutil

    # Check Claude CLI reachability
    claude_available = shutil.which(CLAUDE_BIN) is not None

    # Check ElevenLabs reachability (lightweight)
    elevenlabs_reachable = False
    elevenlabs_key_set = bool(os.environ.get("ELEVENLABS_API_KEY", ""))
    if elevenlabs_key_set:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.elevenlabs.io/v1/user",
                    headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                )
                elevenlabs_reachable = resp.status_code == 200
        except Exception:
            pass

    checks = {
        "bot_token_set": bool(BOT_TOKEN),
        "agent_id_set": bool(ELEVENLABS_AGENT_ID),
        "elevenlabs_key_set": elevenlabs_key_set,
        "elevenlabs_reachable": elevenlabs_reachable,
        "claude_available": claude_available,
        "session_secret_set": bool(VOICE_SESSION_SECRET),
    }

    all_ok = all([checks["bot_token_set"], checks["claude_available"], checks["elevenlabs_key_set"]])

    return {
        "status": "ok" if all_ok else "degraded",
        "active_sessions": len(_sessions),
        "checks": checks,
    }


# --- Session history helpers (used by webhook handler in later tasks) ---

def get_session_history(session_id: str) -> list[dict]:
    """Get conversation history for a session."""
    return list(_session_history.get(session_id, []))


def record_session_message(session_id: str, role: str, text: str):
    """Append a message to session history."""
    _session_history[session_id].append({
        "role": role,
        "text": text,
        "timestamp": time.time(),
    })
    # Trim
    if len(_session_history[session_id]) > _MAX_SESSION_HISTORY:
        _session_history[session_id] = _session_history[session_id][-_MAX_SESSION_HISTORY:]


# --- Claude bridge (same as bot.py but using gateway system prompt) ---

async def _ask_claude(prompt: str) -> str:
    """Run claude --print and return the response."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--append-system-prompt", SYSTEM_PROMPT,
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=WORKING_DIR,
    )
    stdout, stderr = await proc.communicate()
    response = stdout.decode().strip()
    if not response and stderr:
        response = f"[stderr] {stderr.decode().strip()}"
    return response or "(empty response)"


def _format_session_history(session_id: str, new_text: str) -> str:
    """Build a prompt with session conversation history."""
    history = get_session_history(session_id)
    parts = []
    if history:
        parts.append("=== Voice conversation so far ===")
        for entry in history:
            label = "User" if entry["role"] == "user" else "Donna"
            parts.append(f"{label}: {entry['text']}")
        parts.append("=== New utterance ===")
    parts.append(f"User: {new_text}")
    return "\n".join(parts)


# --- Webhook: ElevenLabs server tool callback ---
#
# ElevenLabs Conversational AI uses a specific format for server tool callbacks:
#   Header: ElevenLabs-Signature: t=<timestamp>,v1=<hmac_sha256_hex>
#   Signed content: "{timestamp}.{raw_body}"
#   Payload: { "type": "tool_call", "tool_call": {...}, "conversation_id": "...", "agent_id": "..." }
#   Response: { "type": "tool_response", "tool_response": {"tool_call_id": "...", "output": "..."} }
# Ref: https://elevenlabs.io/docs/conversational-ai/customization/tools/server-tools


def _verify_elevenlabs_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    """Verify ElevenLabs-Signature header (HMAC-SHA256).

    Header format: ElevenLabs-Signature: t=<timestamp>,v1=<hex_signature>
    Signed content: "{t}.{raw_body}"
    """
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(","))
    except ValueError:
        return False

    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False

    # Construct signed content: timestamp.body
    signed_content = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_content.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False

    # Replay protection: reject if timestamp is more than 5 minutes old
    try:
        if abs(int(time.time()) - int(timestamp)) > 300:
            log.warning("ElevenLabs signature timestamp too old: %s", timestamp)
            return False
    except ValueError:
        return False

    return True


class ToolCall(BaseModel):
    tool_call_id: str
    tool_name: str
    parameters: dict = {}


class ElevenLabsToolRequest(BaseModel):
    type: str  # "tool_call"
    tool_call: ToolCall
    conversation_id: str | None = None
    agent_id: str | None = None


class ToolResponse(BaseModel):
    tool_call_id: str
    output: str


class ElevenLabsToolResponse(BaseModel):
    type: str = "tool_response"
    tool_response: ToolResponse


@app.post("/api/webhook/respond")
async def webhook_respond(request: Request):
    """ElevenLabs server tool callback: receive tool call, return Claude response.

    The ElevenLabs Agent is configured with a server tool that calls this endpoint
    when the user finishes speaking. The tool parameters should include:
    - session_id: Donna voice session ID
    - transcript: Finalized user transcript text
    """
    body = await request.body()

    # Verify ElevenLabs-Signature header
    if VOICE_SESSION_SECRET:
        sig_header = request.headers.get("elevenlabs-signature", "")
        if not sig_header or not _verify_elevenlabs_signature(VOICE_SESSION_SECRET, body, sig_header):
            log.warning("Webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid ElevenLabs signature")
    else:
        log.warning("No VOICE_SESSION_SECRET set; webhook endpoint is unauthenticated")

    # Parse the ElevenLabs tool_call payload
    try:
        payload = ElevenLabsToolRequest.model_validate_json(body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")

    if payload.type != "tool_call":
        raise HTTPException(status_code=422, detail=f"Expected type 'tool_call', got '{payload.type}'")

    # Extract parameters from the tool call
    params = payload.tool_call.parameters
    session_id = params.get("session_id", "")
    transcript = params.get("transcript", "").strip()
    caller_id = payload.conversation_id or payload.agent_id or ""

    if not transcript:
        return ElevenLabsToolResponse(
            tool_response=ToolResponse(
                tool_call_id=payload.tool_call.tool_call_id,
                output="(no transcript received)",
            )
        )

    # Validate session exists
    session_exists = any(s["session_id"] == session_id for s in _sessions.values())
    if not session_exists:
        log.warning("Webhook for unknown session: %s caller=%s", session_id, caller_id)
        # Still respond rather than failing — the agent needs a tool response
        return ElevenLabsToolResponse(
            tool_response=ToolResponse(
                tool_call_id=payload.tool_call.tool_call_id,
                output="(unknown session — please restart the voice chat)",
            )
        )

    log.info(
        "Webhook: session_id=%s tool_call_id=%s conversation_id=%s transcript=%s",
        session_id, payload.tool_call.tool_call_id, payload.conversation_id, transcript[:100],
    )

    # Build prompt with session history
    full_prompt = _format_session_history(session_id, transcript)

    # Record user utterance
    record_session_message(session_id, "user", transcript)

    # Call Claude
    response = await _ask_claude(full_prompt)

    # Record Donna's response
    record_session_message(session_id, "assistant", response)

    log.info(
        "AUDIT webhook_respond: session_id=%s tool_call_id=%s transcript_len=%d response_len=%d",
        session_id, payload.tool_call.tool_call_id, len(transcript), len(response),
    )

    return ElevenLabsToolResponse(
        tool_response=ToolResponse(
            tool_call_id=payload.tool_call.tool_call_id,
            output=response,
        )
    )
