import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load .env if it exists (override=True because host may set empty vars)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

from app.config import load_config, get_db_path, get_upload_dir
from app import database
from app.api import users, recipes, categories, cooking, planner, shopping, admin, menu

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    database.db_path = get_db_path()
    await database.init_db()

    upload_dir = get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    # Seed default admin if no users exist
    from app.database import get_conn
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT COUNT(*) FROM users")
        count = (await cur.fetchone())[0]
        if count == 0:
            from app.auth import create_user, confirm_email
            result = await create_user("admin@mazarine.app", "admin", "admin2026!", role="admin")
            await confirm_email(result["confirmation_token"])
            print("Default admin created: admin / admin2026!")
    finally:
        await conn.close()

    ai_status = "configured" if os.environ.get("ANTHROPIC_API_KEY") else "not configured"
    print(f"Mazarine started | DB: {database.db_path} | AI: {ai_status}")
    yield
    print("Mazarine shutting down")

app = FastAPI(title="Mazarine", version="1.0.0", lifespan=lifespan)

# API routes
app.include_router(users.router)
app.include_router(recipes.router)
app.include_router(categories.router)
app.include_router(cooking.router)
app.include_router(planner.router)
app.include_router(shopping.router)
app.include_router(admin.router)
app.include_router(menu.router)

# Static files
static_dir = Path(__file__).parent / "static"
upload_dir_path = Path(get_upload_dir())
os.makedirs(upload_dir_path, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(upload_dir_path)), name="uploads")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_ui():
    return FileResponse(str(static_dir / "index.html"))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mazarine", "version": "1.0.0"}
