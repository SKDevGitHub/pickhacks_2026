"""
Auth0 JWT verification for FastAPI.
Validates access tokens issued by Auth0 for the Tech Signals API.
"""

import os
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ALGORITHMS = [os.getenv("AUTH0_ALGORITHMS", "RS256")]
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

security = HTTPBearer(auto_error=False)

_jwks_cache: Optional[dict] = None


def _csv_set(value: str) -> set[str]:
    return {item.strip().lower() for item in str(value or "").split(",") if item.strip()}


def can_manage_articles(token_payload: dict) -> bool:
    """Determine whether token payload grants access to article generation/editing."""
    permissions = token_payload.get("permissions") or []
    if isinstance(permissions, list) and "manage:articles" in permissions:
        return True

    allowed_emails = _csv_set(os.getenv("GENERATE_ALLOWED_EMAILS", ""))
    allowed_subs = _csv_set(os.getenv("GENERATE_ALLOWED_SUBS", ""))

    if not allowed_emails and not allowed_subs:
        return False

    email = str(token_payload.get("email", "")).strip().lower()
    sub = str(token_payload.get("sub", "")).strip().lower()

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
    if not can_manage_articles(token_payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access article generation features.",
        )
    return token_payload
