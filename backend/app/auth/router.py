from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from app.auth.cookies import (
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
)
from app.auth.service import (
    get_user_profile,
    login_user,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
    update_display_name,
)
from app.core.config import REFRESH_COOKIE_NAME

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(
    user: RegisterRequest,
    response: Response,
):
    created_user = register_user(user.username, user.password)

    if created_user is None:
        raise HTTPException(status_code=400, detail="Unable to create account")

    set_refresh_cookie(
        response,
        created_user["refresh_token"],
    )

    return {
        "message": "Account created successfully",
        "access_token": created_user["access_token"],
        "token_type": "bearer",
        "user_id": created_user["id"],
        "username": created_user["username"],
        "display_name": created_user["display_name"],
    }


@router.post("/login")
def login(
    user: LoginRequest,
    response: Response,
):
    logged_user = login_user(user.username, user.password)

    if logged_user == "user_not_found":
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if logged_user == "wrong_password":
        raise HTTPException(status_code=401, detail="Invalid username or password")

    set_refresh_cookie(
        response,
        logged_user["refresh_token"],
    )

    return {
        "message": "Login successful",
        "access_token": logged_user["access_token"],
        "token_type": "bearer",
        "user_id": logged_user["id"],
        "username": logged_user["username"],
        "display_name": logged_user.get("display_name", ""),
    }


@router.put("/profile")
def update_profile(
    profile: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    updated_user = update_display_name(user_id, profile.display_name)

    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "Profile updated successfully",
        "user_id": updated_user["id"],
        "username": updated_user["username"],
        "display_name": updated_user["display_name"],
    }


@router.get("/profile")
def get_profile(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    user = get_user_profile(user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": user["id"], "username": user["username"], "display_name": user["display_name"]}


@router.post("/refresh")
def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
):
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Missing refresh token",
        )

    result = refresh_access_token(refresh_token)

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
        )

    set_refresh_cookie(
        response,
        result["refresh_token"],
    )

    return {
        "access_token": result["access_token"],
        "token_type": result["token_type"],
    }


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
):
    if refresh_token:
        revoke_refresh_token(refresh_token)

    clear_refresh_cookie(response)

    return {"message": "Logout successful"}
