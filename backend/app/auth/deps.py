from uuid import UUID

from fastapi import HTTPException
from starlette.requests import Request

from app.security import issue_session, read_session

SESSION_COOKIE = "session"


async def require_observer(request: Request) -> UUID:
    cookie_value = request.cookies.get(SESSION_COOKIE)
    if cookie_value is None:
        raise HTTPException(status_code=401)
    observer_id = read_session(cookie_value)
    if observer_id is None:
        raise HTTPException(status_code=401)
    return observer_id


def set_session_cookie(response, observer_id: UUID) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(observer_id),
        httponly=True,
        samesite="lax",
        path="/",
        secure=True,
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
