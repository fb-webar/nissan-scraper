from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from scraper import scrape_nissan_images

app = FastAPI(title="Nissan Image Scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeRequest(BaseModel):
    url: str


@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    try:
        result = await scrape_nissan_images(req.url)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Posluži frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def index():
    return FileResponse(os.path.join(frontend_path, "index.html"))