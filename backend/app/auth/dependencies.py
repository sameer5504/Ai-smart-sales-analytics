from fastapi import HTTPException, Request, status


def get_current_user(request: Request):
    auth_error = getattr(
        request.state,
        "auth_error",
        None,
    )

    if auth_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = getattr(
        request.state,
        "user_id",
        None,
    )

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": user_id,
    }
