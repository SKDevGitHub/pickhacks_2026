"""
Auth0 JWT verification for FastAPI.
Validates access tokens issued by Auth0 for the Chartr AI API.
"""

import logging
import os
import time
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from dotenv import load_dotenv

logger = logging.getLogger("tech-signals-api.auth")

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ALGORITHMS = [os.getenv("AUTH0_ALGORITHMS", "RS256")]
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

security = HTTPBearer(auto_error=False)

_jwks_cache: Optional[dict] = None
_userinfo_cache: dict[str, tuple[dict, float]] = {}
_USERINFO_TTL = 300  # seconds – cache userinfo for 5 minutes


def _csv_set(value: str) -> set[str]:
    values: set[str] = set()
    for item in str(value or "").split(","):
        normalized = item.strip().strip('"').strip("'").lower()
        if normalized:
            values.add(normalized)
    return values


def _extract_claim(payload: dict, claim_name: str) -> str:
    direct = str(payload.get(claim_name, "")).strip().lower()
    if direct:
        return direct

    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if key.lower().endswith(f"/{claim_name}"):
            text = str(value or "").strip().lower()
            if text:
                return text
    return ""


def can_manage_articles(token_payload: dict) -> bool:
    """Determine whether token payload grants access to article generation/editing."""
    permissions = token_payload.get("permissions") or []
    if isinstance(permissions, list) and "manage:articles" in permissions:
        return True

    scope_value = str(token_payload.get("scope", "") or "")
    scopes = {part.strip() for part in scope_value.split(" ") if part.strip()}
    if "manage:articles" in scopes:
        return True

    allowed_emails = _csv_set(os.getenv("GENERATE_ALLOWED_EMAILS", ""))
    allowed_subs = _csv_set(os.getenv("GENERATE_ALLOWED_SUBS", ""))

    if not allowed_emails and not allowed_subs:
        return False

    email = _extract_claim(token_payload, "email")
    sub = _extract_claim(token_payload, "sub")

    if email and email in allowed_emails:
        return True
    if sub and sub in allowed_subs:
        return True

    return False


async def get_jwks() -> dict:
    """Fetch the JWKS (JSON Web Key Set) from Auth0."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache


async def get_userinfo(access_token: str) -> dict:
    """Fetch user profile claims from Auth0 (with in-memory TTL cache)."""
    now = time.monotonic()
    cached = _userinfo_cache.get(access_token)
    if cached:
        data, ts = cached
        if now - ts < _USERINFO_TTL:
            return data

    userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
        _userinfo_cache[access_token] = (data, now)
        # evict stale entries periodically
        if len(_userinfo_cache) > 200:
            cutoff = now - _USERINFO_TTL
            stale = [k for k, (_, ts) in _userinfo_cache.items() if ts < cutoff]
            for k in stale:
                _userinfo_cache.pop(k, None)
        return data


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Verify the Auth0 JWT access token and return its payload."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key",
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER,
        )
        payload["_access_token"] = token
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify credentials \u2014 Auth0 unreachable",
        )


def _is_edu_email(email: str) -> bool:
    """Return True when the email belongs to a .edu domain."""
    email = str(email or "").strip().lower()
    return email.endswith(".edu") or ".edu." in email.split("@")[-1]


async def require_edu_email(token_payload: dict = Depends(verify_token)) -> dict:
    """Authorization dependency — requires a verified .edu email address."""
    email = str(token_payload.get("email", "")).strip().lower()
    if not _is_edu_email(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A .edu email address is required to access this resource.",
        )
    return token_payload


async def require_article_admin(token_payload: dict = Depends(verify_token)) -> dict:
    """Authorization dependency for article generation/editing endpoints."""
    if can_manage_articles(token_payload):
        return token_payload

    # Token didn't have the right claims directly — try userinfo enrichment
    access_token = str(token_payload.get("_access_token", "")).strip()
    if access_token:
        try:
            userinfo = await get_userinfo(access_token)
            enriched_payload = dict(token_payload)
            for claim in ("email", "sub", "name"):
                if userinfo.get(claim):
                    enriched_payload[claim] = str(userinfo[claim]).strip().lower()

            if can_manage_articles(enriched_payload):
                logger.debug("Article admin granted via userinfo enrichment (email=%s)", enriched_payload.get("email"))
                return enriched_payload
            else:
                logger.info(
                    "Article admin denied after userinfo enrichment — email=%s sub=%s",
                    enriched_payload.get("email", "?"),
                    enriched_payload.get("sub", "?"),
                )
        except httpx.HTTPError as exc:
            logger.warning("Userinfo enrichment failed: %s", exc)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not allowed to access article generation features.",
    )
