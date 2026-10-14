#!/usr/bin/env python3
"""Recolector conservador de ligazóns de torneos desde calendarios públicos."""
from __future__ import annotations
import hashlib, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "sources.json"
OUTPUT = ROOT / "data" / "tournaments.json"
HEADERS = {"User-Agent": "XadrezGaliciaAlertas/1.0 (open-source calendar; respectful periodic requests)"}
MONTHS = {
    "xaneiro":"01","enero":"01","janeiro":"01","febreiro":"02","febrero":"02",
    "marzo":"03","març":"03","abril":"04","maio":"05","mayo":"05","xuño":"06",
    "junio":"06","xullo":"07","julio":"07","agosto":"08","setembro":"09",
    "septiembre":"09","outubro":"10","octubre":"10","novembro":"11",
    "noviembre":"11","decembro":"12","diciembre":"12"
}
PROVINCES = {
    "a coruña":"A Coruña","coruña":"A Coruña","lugo":"Lugo",
    "ourense":"Ourense","orense":"Ourense","pontevedra":"Pontevedra"
}
FORMATS = [
    (("blitz","relámpago","relampago","bullet"),"Blitz"),
    (("rápido","rapido","rapid","semirrápidas","semirrapidas"),"Rápido"),
    (("promoción","promocion","escolar","sub-8","sub-10","sub-12","sub-14","sub-16"),"Promoción/escolar"),
    (("clásico","clasico","standard","estándar","estandar"),"Clásico"),
]
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def parse_date(text: str):
    """Retorna primeira data ISO atopada; non inventa ano se non está presente."""
    s = text.lower().replace(" de ", " ")
    # 2026-10-31 ou 31/10/2026
    m = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m:
        try: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        except ValueError: pass
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", s)
    if m:
        try: return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        except ValueError: pass
    month_pattern = "|".join(sorted(MONTHS, key=len, reverse=True))
    m = re.search(rf"\b(\d{{1,2}})\s+(?:de\s+)?({month_pattern})\s+(?:de\s+)?(20\d{{2}})\b", s)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(2)]}-{int(m.group(1)):02d}"
    # Só aceptar datas sen ano se o contexto menciona explicitamente 2026.
    if "2026" in s:
        m = re.search(rf"\b(\d{{1,2}})\s+(?:de\s+)?({month_pattern})\b", s)
        if m:
            return f"2026-{MONTHS[m.group(2)]}-{int(m.group(1)):02d}"
    return None

def infer_province(text: str):
    low = text.lower()
    for needle, province in PROVINCES.items():
        if re.search(rf"\b{re.escape(needle)}\b", low):
            return province
    # Concellos frecuentes, só como indicios e non como cobertura exhaustiva.
    known = {
        "vigo":"Pontevedra","mos":"Pontevedra","ponteareas":"Pontevedra","tui":"Pontevedra",
        "vilagarcía":"Pontevedra","vilagarcia":"Pontevedra","mondariz":"Pontevedra",
        "santiago":"A Coruña","ferrol":"A Coruña","arteixo":"A Coruña","carballo":"A Coruña",
        "lugo":"Lugo","monforte":"Lugo","ourense":"Ourense","verín":"Ourense","verin":"Ourense"
    }
    for town, province in known.items():
        if re.search(rf"\b{re.escape(town)}\b", low):
            return province
    return "Sen determinar"

def infer_format(text: str):
    low = text.lower()
    for terms, label in FORMATS:
        if any(term in low for term in terms):
            return label
    return "Sen determinar"

def stable_id(url, title, start):
    return hashlib.sha256(f"{url}|{title.lower()}|{start or ''}".encode()).hexdigest()[:16]

def scrape_source(source):
    result = {"name": source["name"], "url": source["url"], "ok": False, "found": 0, "message": ""}
    events = []
    try:
        response = requests.get(source["url"], headers=HEADERS, timeout=25)
        response.raise_for_status()
        if "text/html" not in response.headers.get("content-type", "").lower():
            result["message"] = "A resposta non parece HTML; non se extraeron fichas."
            return events, result
        soup = BeautifulSoup(response.text, "html.parser")
        # Só examinar ligazóns cuxo texto, URL ou contexto parece relacionado co xadrez/torneos.
        for a in soup.find_all("a", href=True):
            title = norm(a.get_text(" ", strip=True))
            href = urljoin(response.url, a["href"])
            if not title or len(title) < 4 or href.startswith(("mailto:", "javascript:")):
                continue
            parsed = urlparse(href)
            if parsed.scheme not in ("http", "https"):
                continue
            if any(x in href.lower() for x in ("facebook.com", "instagram.com", "youtube.com", "twitter.com", "x.com")):
                continue
            parent = a
            context = title
            for _ in range(3):
                if parent.parent:
                    parent = parent.parent
                    context += " " + norm(parent.get_text(" ", strip=True))[:1600]
            combined = norm(title + " " + href + " " + context)
            low = combined.lower()
            chess_words = ("xadrez","ajedrez","chess","torneo","torneo","torneio","open","memorial","campionato","campionato","fegaxa","info64","blitz")
            if not any(w in low for w in chess_words):
                continue
            # Evitar que ligazóns de navegación xenéricas se convertan en eventos.
            if title.lower() in {"inicio","home","calendario","torneos","competicións","competitions","ver máis","leer más"}:
                continue
            start = parse_date(combined)
            # Para reducir falsos positivos: requírese data, ou unha URL claramente de evento/torneo.
            eventish = any(w in low for w in ("torneo","torneio","open","memorial","festival","campionato","campeonato","blitz"))
            if not start and not (eventish and re.search(r"/(evento|torneo|torne|open|memorial|festival|competition|competicion)", parsed.path.lower())):
                continue
            # O texto contextual pode ser un calendario completo; mantemos descrición curta.
            location = ""
            province = infer_province(combined)
            if province != "Sen determinar":
                for town in ("Vigo","Mos","Ponteareas","Tui","Vilagarcía de Arousa","Mondariz-Balneario","Santiago de Compostela","Ferrol","A Coruña","Lugo","Ourense"):
                    if town.lower() in low:
                        location = town
                        break
            event = {
                "id": stable_id(href, title, start), "title": title[:180],
                "start_date": start, "end_date": None, "location": location,
                "province": province, "format": infer_format(combined),
                "category": "", "description": "Información extraída automaticamente; comproba datas e bases na fonte.",
                "url": href, "source_name": source["name"],
                "last_seen": datetime.now(timezone.utc).date().isoformat()
            }
            events.append(event)
        # Deduplicación interna.
        unique = {e["id"]: e for e in events}
        events = list(unique.values())
        result.update(ok=True, found=len(events), message="Consulta correcta.")
    except Exception as exc:
        result["message"] = f"{type(exc).__name__}: {str(exc)[:220]}"
    return events, result

def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    all_events, statuses = [], []
    for source in config.get("sources", []):
        events, status = scrape_source(source)
        all_events.extend(events)
        statuses.append(status)
        time.sleep(1.5)  # peticións espazadas e respectuosas
    # Deduplicar por URL + título normalizado, priorizando fichas con data/provincia coñecida.
    merged = {}
    for event in all_events:
        key = (event["url"].rstrip("/"), event["title"].lower())
        old = merged.get(key)
        score = lambda e: int(bool(e["start_date"])) + int(e["province"] != "Sen determinar") + int(e["format"] != "Sen determinar")
        if old is None or score(event) > score(old):
            merged[key] = event
    events = list(merged.values())
    events.sort(key=lambda e: (e["start_date"] or "9999-99-99", e["title"].lower()))
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tournaments": events,
        "source_status": statuses
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Actualización rematada: {len(events)} fichas; fontes correctas: {sum(s['ok'] for s in statuses)}/{len(statuses)}.")
    for s in statuses:
        print(f"- {s['name']}: {'OK' if s['ok'] else 'ERRO'}; {s['found']} fichas; {s['message']}")
    # Non fallar por unha fonte caída: o JSON e os logs permiten detectar a incidencia.
if __name__ == "__main__":
    main()
