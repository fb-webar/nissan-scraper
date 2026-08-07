import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.async_api import async_playwright


def build_interior_panorama(base_link: str) -> str:
    parsed = urlparse(base_link)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["width"] = ["4096"]
    params["pov"] = ["centerpano,cgd"]
    params["quality"] = ["85"]
    params.pop("y", None)
    params.pop("bkgnd", None)
    if "sa" in params:
        sa_val = params["sa"][0]
        sa_val = sa_val.replace(",PE_ON", "").replace("PE_ON", "")
        if "PI_ON" not in sa_val:
            sa_val = sa_val.rstrip(",") + ",PI_ON"
        params["sa"] = [sa_val]
    new_query = urlencode(params, doseq=True, safe=",")
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment,
    ))


async def extract_vehicle_info(page):
    """Izvuci čitljive informacije o vozilu sa stranice."""
    info = {
        "model": "",
        "color": "",
        "is_dual_tone": False,
        "interior": "",
        "grade": "",
        "price": "",
    }

    try:
        body_text = await page.inner_text("body")
    except Exception:
        body_text = ""

    # MODEL
    try:
        m = re.search(r"NISSAN\s+([\w\-]+)", body_text, re.IGNORECASE)
        if m:
            info["model"] = m.group(1)
    except Exception:
        pass

    # BOJA - dual tone prioritet
    dual_patterns = [
        r"(Two-Tone[^\n]+?Roof)",
        r"(Two-Tone[^\n]{3,60})",
        r"(Zwei-Farben[^\n]{3,60})",
        r"(Bi-Ton[^\n]{3,60})",
        r"(Dual[- ]?Tone[^\n]{3,60})",
    ]
    for pat in dual_patterns:
        m = re.search(pat, body_text, re.IGNORECASE)
        if m:
            info["color"] = m.group(1).strip()
            info["is_dual_tone"] = True
            break

    # Single boja
    if not info["color"]:
        single_patterns = [
            r"\b((?:Diamond|Fuji|Ceramic|Pearl|Magnetic|Gun|Storm|Champagne)\s+\w+)\b",
            r"\b([A-Z][a-z]+\s+(?:Red|Black|White|Silver|Grey|Gray|Blue|Bronze|Green|Pearl))\b",
        ]
        for pat in single_patterns:
            m = re.search(pat, body_text)
            if m:
                info["color"] = m.group(1).strip()
                break

    # INTERIJER
    interior_patterns = [
        r"([A-Z][a-z]+\s*[-–]\s*(?:Synthetic\s+)?(?:Leather|Cloth|Stoff|Alcantara|Tissu)[^\n]{0,50})",
        r"([A-Z][a-z]+\s+(?:Leather|Cloth|Stoff|Alcantara)[^\n]{0,40})",
    ]
    for pat in interior_patterns:
        m = re.search(pat, body_text, re.IGNORECASE)
        if m:
            info["interior"] = m.group(1).strip()
            break

    # GRADE
    grade_keywords = ["N-Connecta", "N-Design", "Tekna+", "Tekna", "Acenta Premium",
                      "Acenta", "Visia", "Premiere Edition"]
    for kw in grade_keywords:
        if kw in body_text:
            info["grade"] = kw
            break

    # CIJENA
    try:
        m = re.search(r"(?:Total Price|Gesamtpreis|Prix total)[^\d]*([\d.,]+\s*[€£])",
                      body_text, re.IGNORECASE)
        if m:
            info["price"] = m.group(1).strip()
    except Exception:
        pass

    return info


async def scrape_nissan_images(url: str) -> dict:
    iris_links = set()
    vehicle_info = {}
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu", "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox", "--no-sandbox",
                    "--single-process", "--no-zygote",
                    "--disable-extensions", "--disable-background-networking",
                    "--disable-default-apps", "--disable-sync", "--mute-audio",
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

            await page.wait_for_timeout(5000)

            try:
                vehicle_info = await extract_vehicle_info(page)
            except Exception:
                vehicle_info = {}

            await page.wait_for_timeout(2000)

    except Exception:
        pass
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    # Klasifikacija
    exterior = []
    interior_captured = []
    other_iris = []

    for link in iris_links:
        low = link.lower()
        if ("centerpano" in low or "pi_on" in low or "width=4096" in low
                or re.search(r"pov=i\d", low)):
            interior_captured.append(link)
        elif "pe_on" in low or re.search(r"pov=e\d", low):
            exterior.append(link)
        else:
            other_iris.append(link)

    # Generiraj interijer panoramu
    generated_interior = ""
    all_links = list(iris_links)
    if all_links:
        base = exterior[0] if exterior else all_links[0]
        try:
            generated_interior = build_interior_panorama(base)
        except Exception:
            generated_interior = ""

    interior_final = sorted(set(interior_captured))
    if generated_interior and generated_interior not in interior_final:
        interior_final.insert(0, generated_interior)

    # Dekodiraj šifre iz linka
    codes = {}
    if all_links:
        parsed = urlparse(all_links[0])
        qs = parse_qs(parsed.query)
        codes = {
            "vehicle_code": qs.get("vehicle", [""])[0],
            "paint_code": qs.get("paint", [""])[0],
            "fabric_code": qs.get("fabric", [""])[0],
        }

    return {
        "exterior_360": sorted(set(exterior)),
        "interior_pannellum": interior_final,
        "generated_panorama": generated_interior,
        "other_images": sorted(set(other_iris)),
        "vehicle_info": vehicle_info,
        "codes": codes,
        "total": len(iris_links),
    }
