import os
import httpx
from typing import Optional


async def send_confirmation_email(to_email: str, code: str) -> bool:
    """
    Send a confirmation code email.

    Supports two providers:
    1. Resend (set RESEND_API_KEY) — recommended, free 100 emails/day
    2. Fallback: log to console (development mode)

    To set up Resend:
    1. Sign up at https://resend.com
    2. Get your API key from the dashboard
    3. Set RESEND_API_KEY environment variable
    4. Verify your sending domain (or use onboarding@resend.dev for testing)
    """
    resend_key = os.environ.get("RESEND_API_KEY")

    if resend_key:
        return await _send_via_resend(resend_key, to_email, code)

    # Fallback: console log
    print(f"[MAZARINE EMAIL] To: {to_email} | Code: {code}")
    print(f"[MAZARINE EMAIL] (Set RESEND_API_KEY to send real emails)")
    return True


async def _send_via_resend(api_key: str, to_email: str, code: str) -> bool:
    """Send email via Resend API."""
    from_email = os.environ.get("MAZARINE_FROM_EMAIL", "Mazarine <onboarding@resend.dev>")

    html = f"""
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
                    "subject": f"Your Mazarine confirmation code: {code}",
                    "html": html,
                },
            )
            if resp.status_code in (200, 201):
                print(f"[MAZARINE EMAIL] Sent confirmation to {to_email} via Resend")
                return True
            else:
                print(f"[MAZARINE EMAIL] Resend error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[MAZARINE EMAIL] Failed to send: {e}")
        return False
