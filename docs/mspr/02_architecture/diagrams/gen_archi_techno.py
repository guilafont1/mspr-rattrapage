"""Génère le schéma Architecture + stack techno (slide PPT 16:9)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("archi_techno_electio.png")

# Palette alignée sur make_deck.js
NAVY = (27, 42, 94)
BLUE = (0, 102, 204)
RED = (227, 27, 35)
GOLD = (201, 162, 39)
GREY = (242, 243, 247)
DARK = (34, 34, 34)
WHITE = (255, 255, 255)
MUTED = (100, 110, 140)
BRONZE_C = (184, 115, 51)
SILVER_C = (120, 125, 135)
LINE = (200, 205, 220)

W, H = 1920, 1080


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"
    return ImageFont.truetype(path, size)


def round_rect(draw, xy, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw, x, y, text, fill, text_color=WHITE, pad_x=14, pad_y=6, f=None):
    f = f or font(18, True)
    bbox = draw.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + 2 * pad_x, th + 2 * pad_y
    round_rect(draw, (x, y, x + w, y + h), 10, fill)
    draw.text((x + pad_x, y + pad_y - 1), text, fill=text_color, font=f)
    return w, h


def arrow_right(draw, x1, y, x2, color=NAVY, thickness=3):
    draw.line((x1, y, x2 - 12, y), fill=color, width=thickness)
    draw.polygon([(x2, y), (x2 - 14, y - 7), (x2 - 14, y + 7)], fill=color)


def arrow_down(draw, x, y1, y2, color=NAVY, thickness=3):
    draw.line((x, y1, x, y2 - 12), fill=color, width=thickness)
    draw.polygon([(x, y2), (x - 7, y2 - 14), (x + 7, y2 - 14)], fill=color)


def layer_card(draw, x, y, w, h, title, accent, lines, tech_pills):
    round_rect(draw, (x, y, x + w, y + h), 16, GREY, outline=accent, width=3)
    # bandeau titre
    draw.rounded_rectangle((x, y, x + w, y + 48), radius=16, fill=accent)
    draw.rectangle((x, y + 24, x + w, y + 48), fill=accent)
    draw.text((x + 18, y + 10), title, fill=WHITE, font=font(22, True))

    ty = y + 64
    for line in lines:
        draw.text((x + 18, ty), "•  " + line, fill=DARK, font=font(18))
        ty += 30

    px, py = x + 16, y + h - 52
    for label, color in tech_pills:
        pw, ph = pill(draw, px, py, label, color)
        px += pw + 8


def main():
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # En-tête
    draw.rectangle((0, 0, W, 110), fill=NAVY)
    draw.rectangle((0, 0, 18, 110), fill=RED)
    draw.text((40, 28), "Electio-Analytics — Architecture & stack technique", fill=WHITE, font=font(36, True))
    draw.text(
        (40, 72),
        "POC MSPR · médailon Big Data · ML · BI  ·  96 départements · 5 scrutins",
        fill=(180, 190, 220),
        font=font(18),
    )

    # --- Ligne 1 : Sources → Ingestion → Stockage objet ---
    y0 = 140
    cards_top = [
        (
            40,
            "1. Sources",
            BLUE,
            ["data.gouv.fr — élections T1", "INSEE — chômage, emploi, pop", "Filosofi / SIDE — pauvreté"],
            [("Licence Ouverte v2", BLUE), ("API / CSV / XLS", MUTED)],
        ),
        (
            520,
            "2. Ingestion",
            NAVY,
            ["Téléchargements parallèles", "ThreadPoolExecutor", "Archive immuable data/raw"],
            [("Python", NAVY), ("urllib", MUTED), ("etl/01_download", MUTED)],
        ),
        (
            1000,
            "3. Datalake objet",
            (70, 90, 130),
            ["Sync médailon vers S3", "Profil Docker datalake", "Voie scale-out object storage"],
            [("MinIO", (70, 90, 130)), ("S3 API", MUTED)],
        ),
        (
            1480,
            "4. Orchestration",
            RED,
            ["run_pipeline.py (POC)", "tests pytest + DQM", "DAG Airflow (cible prod)"],
            [("Docker Compose", RED), ("pytest", MUTED)],
        ),
    ]

    cw, ch = 400, 220
    for x, title, accent, lines, pills in cards_top:
        layer_card(draw, x, y0, cw, ch, title, accent, lines, pills)

    # flèches horizontales ligne 1
    for x in (440, 920, 1400):
        arrow_right(draw, x, y0 + ch // 2, x + 80)

    # --- Ligne 2 : Médailon ---
    y1 = 400
    draw.text((40, y1 - 28), "Couches médailon", fill=NAVY, font=font(20, True))
    draw.rectangle((220, y1 - 18, 280, y1 - 12), fill=RED)

    med = [
        (
            40,
            "BRONZE",
            BRONZE_C,
            ["Contrats normalisés", "6 CSV + manifeste JSON", "Codes dept / 5 blocs"],
            [("Pandas", BRONZE_C), ("référentiels.py", MUTED)],
        ),
        (
            520,
            "SILVER",
            SILVER_C,
            ["DQM (16 contrôles)", "Dédup + bornes métier", "Panel socioeco_annuel"],
            [("DQM interne", SILVER_C), ("Pandas", MUTED)],
        ),
        (
            1000,
            "GOLD",
            GOLD,
            ["Grain : dept × scrutin", "Features ≤ N−1 (anti-fuite)", "480 lignes analytiques"],
            [("SQLite", GOLD), ("Postgres / Aiven", MUTED)],
        ),
        (
            1480,
            "Modèle étoile",
            NAVY,
            ["fait_resultat_election", "dim_dept · dim_annee · dim_bloc", "KPI + table service GOLD"],
            [("SQL", NAVY), ("Metabase-ready", MUTED)],
        ),
    ]
    for x, title, accent, lines, pills in med:
        layer_card(draw, x, y1, cw, ch, title, accent, lines, pills)
    for x in (440, 920, 1400):
        arrow_right(draw, x, y1 + ch // 2, x + 80)

    # flèches verticales sources → bronze / gold → restitution
    arrow_down(draw, 240, y0 + ch, y1 - 4)
    arrow_down(draw, 1200, y1 + ch, 660)

    # --- Ligne 3 : Restitution ---
    y2 = 670
    draw.text((40, y2 - 28), "Restitution & consommation", fill=NAVY, font=font(20, True))
    draw.rectangle((320, y2 - 18, 380, y2 - 12), fill=RED)

    rest = [
        (
            40,
            "API métier",
            NAVY,
            ["Endpoints dashboard / predict", "Reload modèle ML", "Health DB (Gold)"],
            [("FastAPI", NAVY), ("Uvicorn", MUTED), (":8000", MUTED)],
        ),
        (
            520,
            "Dashboard interactif",
            BLUE,
            ["Scénarios what-if", "Cartes & séries temporelles", "Appels API backend"],
            [("Dash", BLUE), ("Plotly", MUTED), (":8050", MUTED)],
        ),
        (
            1000,
            "Machine Learning",
            RED,
            ["Classification bloc gagnant", "Walk-forward temporel", "Holdout 2022 = 0,53"],
            [("scikit-learn", RED), ("Gradient Boosting", MUTED)],
        ),
        (
            1480,
            "BI self-service",
            (0, 128, 128),
            ["Exploration Gold / Postgres", "Dashboards KPI jury", "Profil Docker bi"],
            [("Metabase", (0, 128, 128)), (":3000", MUTED)],
        ),
    ]
    for x, title, accent, lines, pills in rest:
        layer_card(draw, x, y2, cw, ch, title, accent, lines, pills)
    for x in (440, 920, 1400):
        arrow_right(draw, x, y2 + ch // 2, x + 80, color=BLUE)

    # Pied de page
    draw.rectangle((0, 1020, W, H), fill=GREY)
    draw.rectangle((0, 1020, W, 1024), fill=NAVY)
    footer = (
        "Stack POC : Python · Pandas · FastAPI · Dash/Plotly · scikit-learn · SQLite/Postgres · MinIO · Metabase · Docker Compose"
    )
    draw.text((40, 1038), footer, fill=DARK, font=font(18))
    draw.text((1680, 1038), "Electio-Analytics", fill=NAVY, font=font(18, True))

    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT} ({OUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
