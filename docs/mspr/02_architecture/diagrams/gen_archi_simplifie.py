"""Schéma d'architecture simplifié — slide PPT 16:9 (grille 4 colonnes)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("archi_simplifiee_electio.png")

NAVY = (27, 42, 94)
BLUE = (0, 102, 204)
RED = (227, 27, 35)
GOLD = (201, 162, 39)
DARK = (34, 34, 34)
WHITE = (255, 255, 255)
MUTED = (90, 100, 130)
BRONZE_C = (176, 112, 48)
SILVER_C = (108, 114, 124)
TEAL = (0, 128, 128)
FOOTER_BG = (242, 243, 247)

BAND_1 = (232, 240, 252)
BAND_2 = (244, 245, 249)
BAND_3 = (252, 238, 238)

W, H = 1920, 1080
HEADER_H = 72
FOOTER_H = 48
MARGIN = 40
BAND_GAP = 40
BAND_H = 286
LABEL_H = 44
BOX_W = 408
BOX_H = 156
COL_GAP = 52  # gouttière = flèches horizontales
COL_XS = (66, 526, 986, 1446)  # 4 colonnes identiques sur les 3 rangées


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"
    return ImageFont.truetype(path, size)


def round_rect(draw, xy, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def node(draw, col, y, title, subtitle, accent):
    x = COL_XS[col]
    round_rect(draw, (x, y, x + BOX_W, y + BOX_H), 12, WHITE, outline=accent, width=2)
    draw.rounded_rectangle((x, y, x + BOX_W, y + 14), radius=12, fill=accent)
    draw.rectangle((x, y + 8, x + BOX_W, y + 14), fill=accent)
    cx = x + BOX_W / 2
    body_mid = y + 14 + (BOX_H - 14) / 2
    draw.text((cx, body_mid - 16), title, font=font(22, True), fill=NAVY, anchor="mm")
    draw.text((cx, body_mid + 18), subtitle, font=font(16), fill=MUTED, anchor="mm")
    return (x, y, x + BOX_W, y + BOX_H)


def arrow_right(draw, x1, x2, y):
    head = 12
    draw.line((x1, y, x2 - head, y), fill=NAVY, width=3)
    draw.polygon([(x2, y), (x2 - head, y - 6), (x2 - head, y + 6)], fill=NAVY)


def arrow_down(draw, x, y1, y2):
    head = 12
    draw.line((x, y1, x, y2 - head), fill=NAVY, width=3)
    draw.polygon([(x, y2), (x - 6, y2 - head), (x + 6, y2 - head)], fill=NAVY)


def gutter_x(left_col):
    """Milieu de la gouttière entre left_col et left_col+1."""
    return COL_XS[left_col] + BOX_W + COL_GAP / 2


def band(draw, y, fill, number, title, accent):
    x0, x1 = MARGIN, W - MARGIN
    round_rect(draw, (x0, y, x1, y + BAND_H), 14, fill)
    cx, cy = x0 + 28, y + LABEL_H / 2
    draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), fill=accent)
    draw.text((cx, cy), str(number), font=font(15, True), fill=WHITE, anchor="mm")
    draw.text((x0 + 50, cy), title, font=font(20, True), fill=NAVY, anchor="lm")
    return y + LABEL_H + (BAND_H - LABEL_H - BOX_H) // 2


def main():
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, HEADER_H), fill=NAVY)
    draw.rectangle((0, 0, 10, HEADER_H), fill=RED)
    draw.text((28, 36), "Electio-Analytics — Architecture", font=font(28, True), fill=WHITE, anchor="lm")
    draw.text(
        (1888, 36),
        "Collecte  →  Médailon  →  Restitution",
        font=font(16),
        fill=(180, 190, 220),
        anchor="rm",
    )

    y1 = HEADER_H + 14
    y2 = y1 + BAND_H + BAND_GAP
    y3 = y2 + BAND_H + BAND_GAP

    by1 = band(draw, y1, BAND_1, 1, "Collecte", BLUE)
    by2 = band(draw, y2, BAND_2, 2, "Médailon", GOLD)
    by3 = band(draw, y3, BAND_3, 3, "Restitution", RED)

    # Rangée 1 — 3 sources (parallèles) puis ingestion
    node(draw, 0, by1, "data.gouv.fr", "Élections T1  ·  5 scrutins", BLUE)
    node(draw, 1, by1, "INSEE", "Chômage · emploi · population", BLUE)
    node(draw, 2, by1, "Filosofi / SIDE", "Pauvreté  ·  Licence Ouverte v2", BLUE)
    node(draw, 3, by1, "Ingestion", "Python  ·  MinIO  ·  data/raw", NAVY)
    my1 = by1 + 14 + (BOX_H - 14) / 2
    arrow_right(draw, COL_XS[2] + BOX_W + 10, COL_XS[3] - 10, my1)

    # Rangée 2 — pipeline médailon
    node(draw, 0, by2, "Bronze", "Contrats CSV normalisés", BRONZE_C)
    node(draw, 1, by2, "Silver", "DQM · 16 contrôles · panel", SILVER_C)
    node(draw, 2, by2, "Gold", "Grain : département × scrutin", GOLD)
    node(draw, 3, by2, "Stockage", "SQLite / Postgres  ·  modèle étoile", NAVY)
    my2 = by2 + 14 + (BOX_H - 14) / 2
    arrow_right(draw, COL_XS[0] + BOX_W + 10, COL_XS[1] - 10, my2)
    arrow_right(draw, COL_XS[1] + BOX_W + 10, COL_XS[2] - 10, my2)
    arrow_right(draw, COL_XS[2] + BOX_W + 10, COL_XS[3] - 10, my2)

    # Rangée 3 — 4 sorties parallèles
    node(draw, 0, by3, "FastAPI", "API métier  ·  dashboard & predict", NAVY)
    node(draw, 1, by3, "Dash / Plotly", "Cartes · scénarios what-if", BLUE)
    node(draw, 2, by3, "scikit-learn", "ML bloc gagnant  ·  holdout 2022", RED)
    node(draw, 3, by3, "Metabase", "BI self-service  ·  KPI Gold", TEAL)

    # Connecteurs verticaux : gouttière centrale (entre col 1 et 2, x = 960)
    spine = int(gutter_x(1))
    arrow_down(draw, spine, y1 + BAND_H + 6, y2 - 6)
    arrow_down(draw, spine, y2 + BAND_H + 6, y3 - 6)

    fy = H - FOOTER_H
    draw.rectangle((0, fy, W, H), fill=FOOTER_BG)
    draw.rectangle((0, fy, W, fy + 3), fill=NAVY)
    draw.text(
        (28, fy + FOOTER_H / 2),
        "POC  ·  Python · Pandas · FastAPI · Dash · scikit-learn · SQLite / Postgres · MinIO · Metabase · Docker Compose",
        font=font(15),
        fill=DARK,
        anchor="lm",
    )
    draw.text((1892, fy + FOOTER_H / 2), "Electio-Analytics", font=font(15, True), fill=NAVY, anchor="rm")

    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT}")
    print(f"bands y={y1},{y2},{y3}  box_y={by1},{by2},{by3}  spine={spine}")
    print(f"cols={COL_XS}  right={COL_XS[-1] + BOX_W}")


if __name__ == "__main__":
    main()
