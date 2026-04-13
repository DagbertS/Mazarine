from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import create_user, confirm_email, login, logout, get_current_user, resend_confirmation_code

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: str
    password: str

class ConfirmRequest(BaseModel):
    code: str

class LoginRequest(BaseModel):
    email_or_username: str
    password: str

class ResendCodeRequest(BaseModel):
    email: str

@router.post("/register")
async def register(body: RegisterRequest):
    # Email is also the username
    email = body.email.strip().lower()
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    try:
        result = await create_user(email, email, body.password)
        # In production, send the code via email. For now, log it and return it.
        print(f"[MAZARINE] Confirmation code for {email}: {result['confirmation_code']}")
        return {
            "status": "ok",
            "message": "A 6-digit confirmation code has been sent to your email address.",
            "email": email,
            # Include code in response for development/testing — remove in production
            "_dev_code": result["confirmation_code"],
        }
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/confirm")
async def confirm(body: ConfirmRequest):
    code = body.code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Please enter a valid 6-digit code")
    ok = await confirm_email(code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    return {"status": "ok", "message": "Account confirmed! You can now sign in."}

# Keep old GET endpoint for backwards compat
@router.get("/confirm/{token}")
async def confirm_get(token: str):
    ok = await confirm_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return {"status": "ok", "message": "Email confirmed. You can now log in."}

@router.post("/resend-code")
async def resend_code(body: ResendCodeRequest):
    result = await resend_confirmation_code(body.email)
    if not result:
        raise HTTPException(status_code=400, detail="No pending account found for this email")
    print(f"[MAZARINE] New confirmation code for {body.email}: {result['code']}")
    return {
        "status": "ok",
        "message": "A new confirmation code has been sent.",
        "_dev_code": result["code"],
    }

@router.post("/login")
async def do_login(body: LoginRequest, response: Response):
    result = await login(body.email_or_username, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if result.get("error") == "pending":
        raise HTTPException(status_code=403, detail=result["message"])
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
