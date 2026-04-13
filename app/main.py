import os
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone
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


async def seed_recipes(conn, admin_id: str):
    """Load seed recipes from seed_data.json on first deployment."""
    seed_path = Path(__file__).parent / "seed_data.json"
    if not seed_path.exists():
        print("No seed_data.json found, skipping recipe seed")
        return

    with open(seed_path) as f:
        seed = json.load(f)

    recipe_count = len(seed.get("recipes", []))
    print(f"Seeding {recipe_count} recipes from seed_data.json...")

    now = datetime.now(timezone.utc).isoformat()

    # Create tags first
    tag_id_map = {}  # name -> id
    for tag_entry in seed.get("tags", []):
        tname = tag_entry["name"]
        ttype = tag_entry.get("type", "auto")
        tid = f"tag-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            "INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
            (tid, admin_id, tname, ttype),
        )
        cur = await conn.execute(
            "SELECT id FROM tags WHERE user_id = ? AND name = ?", (admin_id, tname)
        )
        row = await cur.fetchone()
        if row:
            tag_id_map[tname] = row[0]

    # Create recipes
    for r in seed["recipes"]:
        rid = f"rcp-{uuid.uuid4().hex[:12]}"
        await conn.execute(
            """INSERT INTO recipes (id, user_id, title, description, ingredients, directions,
               servings, prep_time_minutes, cook_time_minutes, total_time_minutes,
               source_url, source_name, notes, nutrition, photo_urls,
               rating, is_favourite, is_pinned, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid, admin_id, r["title"], r.get("description", ""),
                json.dumps(r.get("ingredients", [])),
                json.dumps(r.get("directions", [])),
                r.get("servings"), r.get("prep_time_minutes"),
                r.get("cook_time_minutes"), r.get("total_time_minutes"),
                r.get("source_url", ""), r.get("source_name", ""),
                r.get("notes", ""),
                json.dumps(r.get("nutrition", {})),
                json.dumps(r.get("photo_urls", [])),
                0, 0, 0, now, now,
            ),
        )

        for tname in r.get("tags", []):
            if tname in tag_id_map:
                await conn.execute(
                    "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)",
                    (rid, tag_id_map[tname]),
                )

    await conn.commit()
    print(f"Seeded {recipe_count} recipes with {len(tag_id_map)} tags")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    db_path = get_db_path()
    database.db_path = db_path

    # Check if this is a brand new database (file doesn't exist yet)
    is_fresh = not Path(db_path).exists()

    # Create tables (idempotent — IF NOT EXISTS)
    await database.init_db()

    upload_dir = get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    # Only seed on truly fresh database (file just created)
    if is_fresh:
        from app.database import get_conn
        conn = await get_conn()
        try:
            from app.auth import create_user, confirm_email
            result = await create_user("admin@mazarine.app", "admin", "admin2026!", role="admin")
            await confirm_email(result["confirmation_token"])
            print("Default admin created: admin / admin2026!")

            await seed_recipes(conn, result["id"])
        finally:
            await conn.close()
    else:
        print(f"Existing database found at {db_path} — skipping seed")

    ai_status = "configured" if os.environ.get("ANTHROPIC_API_KEY") else "not configured"
    print(f"Mazarine started | DB: {db_path} | AI: {ai_status} | Fresh: {is_fresh}")
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

# Generate a cache-busting version from the current deployment time
import hashlib, time as _time
_build_version = hashlib.md5(str(_time.time()).encode()).hexdigest()[:10]

app.mount("/uploads", StaticFiles(directory=str(upload_dir_path)), name="uploads")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_ui():
    from fastapi.responses import HTMLResponse
    html_path = static_dir / "index.html"
    html = html_path.read_text()
    # Inject cache-busting version into all static asset URLs
    html = html.replace('.css"', f'.css?v={_build_version}"')
    html = html.replace('.js"', f'.js?v={_build_version}"')
    return HTMLResponse(content=html, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(str(static_dir / "manifest.json"), media_type="application/manifest+json")

@app.get("/favicon.png")
async def serve_favicon():
    return FileResponse(str(static_dir / "img" / "favicon.png"), media_type="image/png")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mazarine", "version": "1.0.0"}
