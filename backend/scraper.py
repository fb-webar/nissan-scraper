import re
from playwright.async_api import async_playwright


async def scrape_nissan_images(url: str) -> dict:
    """
    Otvara Nissan konfigurator, presreće IRIS mrežne pozive
    i izdvaja čiste linkove za eksterijer i interijer (Pannellum 360).
    """
    iris_links = set()

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

        # Presreći SAMO IRIS pozive (prava slika vozila)
        def handle_response(response):
            if "heliosnissan.net/iris" in response.url or "mediaserver" in response.url:
                iris_links.add(response.url)

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception:
            pass

        await page.wait_for_timeout(4000)

        # Pokušaj kliknuti na interijer 360 da se Pannellum učita
        # (probaj razne selektore - Nissan ih može mijenjati)
        interior_selectors = [
            "text=Innenraum",          # DE
            "text=Interior",
            "text=360",
            "[data-view='interior']",
            ".interior-view",
            "[class*='interior']",
            "[class*='pano']",
        ]
        for sel in interior_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    await el.click(timeout=2000)
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                continue

        # Dodatno čekanje da panorama sigurno stigne
        await page.wait_for_timeout(3000)

        # Scroll da potakne lazy load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        await browser.close()

    # Klasificiraj IRIS linkove
    exterior = []
    interior = []
    other_iris = []

    for link in iris_links:
        low = link.lower()
        # Interijer: PI_ON ili pov=centerpano
        if "pi_on" in low or "centerpano" in low or "width=4096" in low:
            interior.append(link)
        # Eksterijer: PE_ON ili pov=E
        elif "pe_on" in low or re.search(r"pov=e\d", low):
            exterior.append(link)
        else:
            other_iris.append(link)

    return {
        "exterior_360": sorted(set(exterior)),
        "interior_pannellum": sorted(set(interior)),
        "other_images": sorted(set(other_iris)),
        "total": len(iris_links),
    }
    }
