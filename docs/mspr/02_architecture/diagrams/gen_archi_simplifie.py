"""Génère le schéma d'architecture simplifié (slide PPT 16:9)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("archi_simplifiee_electio.png")

NAVY = (27, 42, 94)
BLUE = (0, 102, 204)
RED = (227, 27, 35)
GOLD = (201, 162, 39)
GREY = (242, 243, 247)
DARK = (34, 34, 34)
WHITE = (255, 255, 255)
MUTED = (90, 100, 130)
BRONZE_C = (184, 115, 51)
SILVER_C = (120, 125, 135)
TEAL = (0, 128, 128)

W, H = 1920, 1080


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"
    return ImageFont.truetype(path, size)


def round_rect(draw, xy, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def arrow_right(draw, x1, y, x2, color=NAVY, thickness=7):
    draw.line((x1, y, x2 - 20, y), fill=color, width=thickness)
    draw.polygon([(x2, y), (x2 - 24, y - 13), (x2 - 24, y + 13)], fill=color)


def arrow_down(draw, x, y1, y2, color=NAVY, thickness=5):
    draw.line((x, y1, x, y2 - 14), fill=color, width=thickness)
    draw.polygon([(x, y2), (x - 10, y2 - 16), (x + 10, y2 - 16)], fill=color)


def pills_row(draw, px, py, items):
    for label, color in items:
        f = font(16, True)
        bbox = draw.textbbox((0, 0), label, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        bw, bh = tw + 28, th + 14
        round_rect(draw, (px, py, px + bw, py + bh), 10, color)
        draw.text((px + 14, py + 6), label, fill=WHITE, font=f)
        px += bw + 10


def card(draw, x, y, w, h, title, accent, lines, pills):
    round_rect(draw, (x, y, x + w, y + h), 16, WHITE, outline=accent, width=3)
    draw.rounded_rectangle((x, y, x + w, y + 54), radius=16, fill=accent)
    draw.rectangle((x, y + 28, x + w, y + 54), fill=accent)
    draw.text((x + 20, y + 12), title, fill=WHITE, font=font(22, True))
    ty = y + 74
    for line in lines:
        draw.text((x + 20, ty), line, fill=DARK, font=font(20))
        ty += 34
    if pills:
        pills_row(draw, x + 18, y + h - 50, pills)


def row_card(draw, x, y, w, h, title, subtitle, accent):
    round_rect(draw, (x, y, x + w, y + h), 14, WHITE, outline=accent, width=3)
    draw.rectangle((x, y + 8, x + 10, y + h - 8), fill=accent)
    draw.text((x + 28, y + 14), title, fill=accent, font=font(22, True))
    draw.text((x + 28, y + 48), subtitle, fill=DARK, font=font(18))


def medal(draw, x, y, w, h, title, subtitle, color):
    round_rect(draw, (x, y, x + w, y + h), 14, WHITE, outline=color, width=3)
    draw.rounded_rectangle((x, y, x + w, y + 42), radius=14, fill=color)
    draw.rectangle((x, y + 22, x + w, y + 42), fill=color)
    draw.text((x + 16, y + 8), title, fill=WHITE, font=font(20, True))
    draw.text((x + 16, y + 54), subtitle, fill=DARK, font=font(18))


def main():
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, 100), fill=NAVY)
    draw.rectangle((0, 0, 16, 100), fill=RED)
    draw.text((40, 22), "Electio-Analytics — Architecture simplifiée", fill=WHITE, font=font(36, True))
    draw.text(
        (40, 64),
        "3 couches  ·  Sources ouvertes  →  Médailon  →  API / Dash / ML / BI",
        fill=(180, 190, 220),
        font=font(18),
    )

    y = 140
    col_h = 740
    gap = 78
    col_w = 536
    x1, x2, x3 = 36, 36 + col_w + gap, 36 + 2 * (col_w + gap)

    round_rect(draw, (x1, y, x1 + col_w, y + col_h), 22, GREY)
    round_rect(draw, (x2, y, x2 + col_w, y + col_h), 22, GREY)
    round_rect(draw, (x3, y, x3 + col_w, y + col_h), 22, GREY)

    pad = 22
    inner = col_w - 2 * pad

    # --- 1. Collecte ---
    draw.text((x1 + pad, y + 18), "1. Collecte", fill=BLUE, font=font(26, True))
    card(
        draw,
        x1 + pad,
        y + 70,
        inner,
        280,
        "Sources publiques",
        BLUE,
        ["data.gouv.fr  —  élections T1", "INSEE  —  chômage, emploi, pop", "Filosofi / SIDE  —  pauvreté"],
        [("Licence Ouverte v2", BLUE)],
    )
    card(
        draw,
        x1 + pad,
        y + 370,
        inner,
        340,
        "Ingestion",
        NAVY,
        ["Téléchargements parallèles", "Archive immuable  data/raw", "Sync objet  MinIO (S3)"],
        [("Python", NAVY), ("MinIO", MUTED), ("Docker", RED)],
    )

    # --- 2. Médailon ---
    draw.text((x2 + pad, y + 18), "2. Médailon", fill=NAVY, font=font(26, True))
    mx = x2 + pad
    medal(draw, mx, y + 70, inner, 120, "BRONZE", "Contrats CSV normalisés", BRONZE_C)
    arrow_down(draw, x2 + col_w // 2, y + 198, y + 228)
    medal(draw, mx, y + 232, inner, 120, "SILVER", "DQM · 16 contrôles · panel socio-éco", SILVER_C)
    arrow_down(draw, x2 + col_w // 2, y + 360, y + 390)
    medal(draw, mx, y + 394, inner, 120, "GOLD", "Grain : département × scrutin", GOLD)
    card(
        draw,
        mx,
        y + 534,
        inner,
        176,
        "Stockage analytique",
        NAVY,
        ["SQLite  ·  Postgres (Aiven)", "Modèle étoile  (faits + dimensions)"],
        [("SQL", NAVY), ("Metabase-ready", TEAL)],
    )

    # --- 3. Restitution ---
    draw.text((x3 + pad, y + 18), "3. Restitution", fill=RED, font=font(26, True))
    rows = [
        ("FastAPI", "API métier  ·  dashboard & predict", NAVY),
        ("Dash / Plotly", "Cartes, what-if, séries temporelles", BLUE),
        ("scikit-learn", "ML bloc gagnant  ·  walk-forward 2022", RED),
        ("Metabase", "BI self-service  ·  KPI Gold", TEAL),
    ]
    rh, rs = 145, 14
    for i, (title, subtitle, accent) in enumerate(rows):
        row_card(draw, x3 + pad, y + 70 + i * (rh + rs), inner, rh, title, subtitle, accent)

    mid_y = y + col_h // 2
    arrow_right(draw, x1 + col_w + 10, mid_y, x2 - 10)
    arrow_right(draw, x2 + col_w + 10, mid_y, x3 - 10)

    draw.rectangle((0, 1020, W, H), fill=GREY)
    draw.rectangle((0, 1020, W, 1024), fill=NAVY)
    draw.text(
        (40, 1038),
        "POC  ·  Python · Pandas · FastAPI · Dash · scikit-learn · SQLite / Postgres · MinIO · Metabase · Docker Compose",
        fill=DARK,
        font=font(18),
    )
    draw.text((1620, 1038), "Electio-Analytics", fill=NAVY, font=font(18, True))

    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT} ({OUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
