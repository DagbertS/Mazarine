from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel
from app.auth import create_user, confirm_email, login, logout, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email_or_username: str
    password: str

@router.post("/register")
async def register(body: RegisterRequest):
    try:
        result = await create_user(body.email, body.username, body.password)
        return {"status": "ok", "message": "Account created. Please confirm your email.", "user_id": result["id"],
                "confirmation_token": result["confirmation_token"]}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="Email or username already exists")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/confirm/{token}")
async def confirm(token: str):
    ok = await confirm_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return {"status": "ok", "message": "Email confirmed. You can now log in."}

@router.post("/login")
async def do_login(body: LoginRequest, response: Response):
    result = await login(body.email_or_username, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie(
        key="session_token", value=result["token"],
        httponly=True, samesite="lax", max_age=72 * 3600,
    )
    return {"status": "ok", "user": result["user"], "token": result["token"]}

@router.post("/logout")
async def do_logout(request: Request, response: Response):
    await logout(request)
    response.delete_cookie("session_token")
    return {"status": "ok"}

@router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    return {"user": user}
