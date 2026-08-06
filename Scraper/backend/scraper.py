import asyncio
import re
from playwright.async_api import async_playwright


async def scrape_nissan_images(url: str) -> dict:
    """
    Otvara Nissan konfigurator, presreće mrežne pozive
    i hvata linkove slika + Pannellum panorame.
    """
    captured_images = set()
    pannellum_sources = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # Presretanje svih mrežnih zahtjeva za slike
        image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".avif")

        def handle_response(response):
            resp_url = response.url.lower()
            if any(ext in resp_url for ext in image_extensions):
                captured_images.add(response.url)
            # Pannellum panorame često sadrže ove ključne riječi
            if any(k in resp_url for k in ["panorama", "pannellum", "equirect", "360", "interior"]):
                pannellum_sources.add(response.url)

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception:
            # Ako networkidle zapne, nastavi svejedno
            pass

        # Pričekaj da se dinamički sadržaj učita
        await page.wait_for_timeout(5000)

        # Pokušaj scrollati da se lazy-load slike učitaju
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)

        # Pretraži i sam HTML za Pannellum config u <script> tagovima
        html = await page.content()
        pannellum_in_html = re.findall(
            r'["\'](https?://[^"\']+(?:panorama|pannellum|equirect|360)[^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        for src in pannellum_in_html:
            pannellum_sources.add(src)

        await browser.close()

    # Klasificiraj rezultate
    exterior = sorted([u for u in captured_images if "exterior" in u.lower() or "ext" in u.lower()])
    interior = sorted(pannellum_sources)
    others = sorted([u for u in captured_images if u not in exterior and u not in interior])

    return {
        "exterior_360": exterior,
        "interior_pannellum": interior,
        "other_images": others,
        "total": len(captured_images) + len(pannellum_sources),
    }