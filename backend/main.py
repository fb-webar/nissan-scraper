from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from backend.scraper import scrape_nissan_images

app = FastAPI(title="Nissan Image Scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Posluži statičke datoteke (CSS, itd.)
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


class ScrapeRequest(BaseModel):
    url: str


@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    try:
        result = await scrape_nissan_images(req.url)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/")
async def index():
    return FileResponse(os.path.join(frontend_path, "index.html"))
