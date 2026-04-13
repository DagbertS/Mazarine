import os
import httpx
from typing import Optional


ADMIN_EMAIL = os.environ.get("MAZARINE_ADMIN_EMAIL", "dagbert@outlook.com")


async def send_confirmation_email(to_email: str, code: str) -> bool:
    """
    Send a confirmation code email to a new user.

    With RESEND_API_KEY: sends a branded HTML email via Resend.
    Without: logs code to console (dev mode).
    """
    resend_key = os.environ.get("RESEND_API_KEY")

    if resend_key:
        return await _send_via_resend(
            api_key=resend_key,
            to_email=to_email,
            subject=f"Your Mazarine confirmation code: {code}",
            html=_confirmation_html(code),
        )

    # Fallback: console log
    print(f"[MAZARINE EMAIL] To: {to_email} | Code: {code}")
    print(f"[MAZARINE EMAIL] (Set RESEND_API_KEY to send real emails)")
    return True


async def notify_admin_new_user(user_email: str) -> bool:
    """
    Notify the admin when a new user registers.
    Sends to MAZARINE_ADMIN_EMAIL (default: dagbert@outlook.com).
    """
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print(f"[MAZARINE ADMIN] New user registered: {user_email}")
        return True

    html = f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="font-size: 28px; font-weight: 400; letter-spacing: 8px; margin: 0;">MAZARINE</h1>
            <p style="color: #999; font-size: 12px; letter-spacing: 3px; margin-top: 4px;">ADMIN NOTIFICATION</p>
        </div>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 20px 0;">
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            A new user has registered on Mazarine:
        </p>
        <div style="background: #F5F4F0; padding: 16px 20px; border-radius: 4px; margin: 20px 0;">
            <p style="margin: 0; font-size: 15px; color: #1A1A1A;">
                <strong>{user_email}</strong>
            </p>
        </div>
        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            Their account is pending email verification. Once they confirm their code,
            they will be able to log in.
        </p>
        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            You can manage users in the Admin section of the website.
        </p>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 30px 0 20px;">
        <p style="font-size: 11px; color: #999; text-align: center;">
            Mazarine — Your recipe collection, beautifully organised
        </p>
    </div>
    """

    return await _send_via_resend(
        api_key=resend_key,
        to_email=ADMIN_EMAIL,
        subject=f"Mazarine: New user registered — {user_email}",
        html=html,
    )


async def notify_admin_user_verified(user_email: str) -> bool:
    """Notify admin when a user successfully verifies their account."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print(f"[MAZARINE ADMIN] User verified: {user_email}")
        return True

    html = f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="font-size: 28px; font-weight: 400; letter-spacing: 8px; margin: 0;">MAZARINE</h1>
            <p style="color: #999; font-size: 12px; letter-spacing: 3px; margin-top: 4px;">ADMIN NOTIFICATION</p>
        </div>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 20px 0;">
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            A new user has verified their account and is now active:
        </p>
        <div style="background: #E8F5E9; padding: 16px 20px; border-radius: 4px; margin: 20px 0;">
            <p style="margin: 0; font-size: 15px; color: #2E7D32;">
                &#x2713; <strong>{user_email}</strong> is now active
            </p>
        </div>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 30px 0 20px;">
        <p style="font-size: 11px; color: #999; text-align: center;">
            Mazarine — Your recipe collection, beautifully organised
        </p>
    </div>
    """

    return await _send_via_resend(
        api_key=resend_key,
        to_email=ADMIN_EMAIL,
        subject=f"Mazarine: User verified — {user_email}",
        html=html,
    )


def _confirmation_html(code: str) -> str:
    return f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="font-size: 28px; font-weight: 400; letter-spacing: 8px; margin: 0;">MAZARINE</h1>
            <p style="color: #999; font-size: 12px; letter-spacing: 3px; margin-top: 4px;">A PERSONAL COOKBOOK</p>
        </div>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 20px 0;">
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            Welcome to Mazarine. Here is your confirmation code:
        </p>
        <div style="text-align: center; margin: 30px 0;">
            <div style="font-family: monospace; font-size: 36px; letter-spacing: 12px; font-weight: bold; color: #1A1A1A;
                        background: #F5F4F0; padding: 20px; border-radius: 4px; display: inline-block;">
                {code}
            </div>
        </div>
        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            Enter this code on the website to activate your account.
        </p>
        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            If you didn't create an account, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #E8E6E1; margin: 30px 0 20px;">
        <p style="font-size: 11px; color: #999; text-align: center;">
            Mazarine — Your recipe collection, beautifully organised
        </p>
    </div>
    """


async def _send_via_resend(api_key: str, to_email: str, subject: str, html: str) -> bool:
    """Send an email via the Resend API."""
    from_email = os.environ.get("MAZARINE_FROM_EMAIL", "Mazarine <onboarding@resend.dev>")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.status_code in (200, 201):
                print(f"[MAZARINE EMAIL] Sent to {to_email}: {subject}")
                return True
            else:
                print(f"[MAZARINE EMAIL] Resend error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[MAZARINE EMAIL] Failed to send: {e}")
        return False
