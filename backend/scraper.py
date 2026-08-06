import re
from playwright.async_api import async_playwright


async def scrape_nissan_images(url: str) -> dict:
    iris_links = set()
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--no-sandbox",
                    "--single-process",
                    "--no-zygote",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--mute-audio",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            # Blokiraj teške resurse koji troše memoriju (fontovi, video, css)
            # ali PUSTI slike jer nam trebaju IRIS pozivi
            async def block_heavy(route):
                rtype = route.request.resource_type
                if rtype in ("font", "media", "stylesheet"):
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_heavy)

            def handle_response(response):
                u = response.url
                if "heliosnissan.net/iris" in u or "mediaserver" in u:
                    iris_links.add(u)

            page.on("response", handle_response)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass

            await page.wait_for_timeout(4000)

            # Pokušaj kliknuti interijer (razni jezici/tržišta)
            interior_selectors = [
                "text=Innenraum",
                "text=Interior",
                "text=Intérieur",
                "text=Interieur",
                "text=360",
                "[data-view='interior']",
                "[class*='interior']",
                "[class*='pano']",
            ]
            for sel in interior_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        await el.click(timeout=2000)
                        await page.wait_for_timeout(2500)
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(2000)

    except Exception as e:
        # Ako sve pukne, vrati barem što smo uhvatili + poruku
        pass
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    # Klasifikacija - fleksibilna za sve modele
    exterior = []
    interior = []
    other_iris = []

    for link in iris_links:
        low = link.lower()
        if "pi_on" in low or "centerpano" in low or "width=4096" in low:
            interior.append(link)
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
