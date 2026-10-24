from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.jwt import verify_access_token


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = None
        request.state.auth_error = None

        if request.method == "OPTIONS":
            return await call_next(request)

        authorization = request.headers.get("Authorization")

        # Authentication is enforced by Depends(get_current_user).
        # The middleware only processes a token when one is provided.
        if not authorization:
            return await call_next(request)

        scheme, _, token = authorization.partition(" ")

        if scheme.lower() != "bearer" or not token:
            request.state.auth_error = "Invalid authentication credentials"
            return await call_next(request)

        payload = verify_access_token(token)

        if payload == "expired":
            request.state.auth_error = "Access token has expired"
            return await call_next(request)

        if payload == "invalid" or not isinstance(payload, dict):
            request.state.auth_error = "Invalid access token"
            return await call_next(request)

        user_id = payload.get("sub")

        if user_id is None:
            request.state.auth_error = "Invalid access token"
            return await call_next(request)

        try:
            request.state.user_id = int(user_id)
        except (TypeError, ValueError):
            request.state.auth_error = "Invalid access token"

        return await call_next(request)
