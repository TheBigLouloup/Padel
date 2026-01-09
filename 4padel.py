import asyncio
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set
from playwright.async_api import async_playwright

URL = "https://www.4padel.fr/tournois"
OUT = Path("tournois_4padel.csv")

# Ex: "Le 09/01/2026 à 17h00"
DATETIME_RE = re.compile(
    r"\bLe\s+(?P<d>\d{2}/\d{2}/\d{4})\s+à\s+(?P<t>\d{1,2}h\d{2})\b",
    re.IGNORECASE,
)

def normalize_time(t: str) -> str:
    # "17h00" -> "17:00"
    return t.replace("h", ":")

async def click_cookies_best_effort(page) -> None:
    for label in ["Tout accepter", "Accepter", "J'accepte", "Accept", "Agree", "OK"]:
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                await btn.first.click(timeout=1500)
                return
        except:
            pass

async def extract_cards(page) -> List[Dict[str, str]]:
    """
    Extrait les cartes .lf-tournament-preview-container en s’appuyant sur les classes
    que tu as fournies.
    """
    cards = page.locator(".lf-tournament-preview-container")
    n = await cards.count()
    rows: List[Dict[str, str]] = []

    for i in range(n):
        c = cards.nth(i)

        # niveau (ex: P100) – dans <div class="fft"><p>...</p></div>
        level = ""
        lvl = c.locator(".fft p")
        if await lvl.count() > 0:
            level = (await lvl.first.inner_text()).strip()

        # club (ex: 4PADEL Marville) – <p class="lf-tournament-type">
        club = ""
        cl = c.locator("p.lf-tournament-type")
        if await cl.count() > 0:
            club = (await cl.first.inner_text()).strip()

        # bloc(s) date – <p class="lf-tournament-date"> ... </p>
        date_ps = c.locator("p.lf-tournament-date")
        date_texts: List[str] = []
        for j in range(await date_ps.count()):
            date_texts.append((await date_ps.nth(j).inner_text()).strip())

        # D’après ton exemple:
        #   [0] "P100 Soirée"      -> nom court (souvent)
        #   [1] "Le 09/01/2026..." -> date/heure
        #   [2] "Soirée - Ouvert..." -> format/ouverture (parfois)
        name = date_texts[0] if len(date_texts) >= 1 else ""
        datetime_str = ""
        format_ouverture = ""

        # Cherche la ligne "Le .. à .."
        for txt in date_texts:
            if "Le " in txt and " à " in txt:
                datetime_str = txt
                break

        # Prend la dernière ligne non "Le .. à .." comme format/ouverture
        for txt in reversed(date_texts):
            if not ("Le " in txt and " à " in txt):
                # évite de reprendre le nom si on a déjà name
                if txt != name:
                    format_ouverture = txt
                break

        date = ""
        heure = ""
        m = DATETIME_RE.search(datetime_str)
        if m:
            date = m.group("d")
            heure = normalize_time(m.group("t"))

        # Stocke la ligne brute “caractéristiques” pour garder l’info complète
        # (tu pourras raffiner ensuite en colonnes séparées si tu veux)
        caracteristiques = " | ".join([t for t in [name, format_ouverture] if t])

        rows.append({
            "niveau": level,
            "club": club,
            "nom": name,
            "date": date,
            "heure": heure,
            "format_ouverture": format_ouverture,
            "caracteristiques": caracteristiques,
        })

    return rows

def dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Set[Tuple[str, str, str, str]] = set()
    out: List[Dict[str, str]] = []
    for r in rows:
        key = (r["club"], r["date"], r["heure"], r["nom"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            geolocation={"latitude": 48.8566, "longitude": 2.3522},
            permissions=["geolocation"],
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        await click_cookies_best_effort(page)

        # Attendre que des cartes existent
        try:
            await page.wait_for_selector(".lf-tournament-preview-container", timeout=15000)
        except:
            await page.screenshot(path="debug_4padel_no_cards.png", full_page=True)
            await browser.close()
            print("❌ Aucune carte détectée. Screenshot: debug_4padel_no_cards.png")
            return

        # Scroll pour charger davantage (lazy load)
        prev = 0
        for _ in range(12):
            await page.wait_for_timeout(800)
            count = await page.locator(".lf-tournament-preview-container").count()
            if count == prev:
                # si ça n’augmente plus, on peut arrêter
                pass
            prev = count
            await page.mouse.wheel(0, 2000)

        rows = await extract_cards(page)
        await page.screenshot(path="debug_4padel_cards.png", full_page=True)

        await browser.close()

    rows = dedupe(rows)

    # Filtrer uniquement P100 et P250 puis trier par date/heure
    def _parse_sort_key(r: Dict[str, str]):
        d = r.get("date", "")
        t = r.get("heure", "")
        try:
            dd, mm, yyyy = d.split("/")
            y, m, d_ = int(yyyy), int(mm), int(dd)
        except:
            y, m, d_ = 0, 0, 0
        try:
            hh, mi = t.split(":")
            h, mn = int(hh), int(mi)
        except:
            h, mn = 0, 0
        return (y, m, d_, h, mn, r.get("club", ""), r.get("nom", ""))

    allowed = {"P100", "P250"}
    rows = [r for r in rows if r.get("niveau", "").upper() in allowed]
    rows.sort(key=_parse_sort_key)

    # N’écrit pas un CSV vide silencieusement
    if not rows:
        print("❌ 0 ligne après filtrage P100/P250.")
        print("➡️ Regarde debug_4padel_cards.png")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["niveau", "club", "nom", "date", "heure", "format_ouverture", "caracteristiques"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"✅ CSV créé: {OUT.resolve()} ({len(rows)} tournois)")
    print("📸 Debug: debug_4padel_cards.png")

if __name__ == "__main__":
    asyncio.run(main())
