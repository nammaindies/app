from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import RedirectResponse

from app.auth.deps import set_session_cookie
from app.auth.magiclink import consume
from app.deps import get_conn

router = APIRouter()


@router.get("/auth/magic-link/consume")
async def consume_link(token: str, conn=Depends(get_conn)):
    oid = await consume(conn, token)
    if oid is None:
        raise HTTPException(status_code=401, detail="invalid or expired link")
    resp = RedirectResponse(url="/", status_code=303)
    set_session_cookie(resp, oid)
    return resp
