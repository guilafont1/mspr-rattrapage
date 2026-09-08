# -*- coding: utf-8 -*-
"""
Electio-Analytics — tableau de bord décisionnel (Dash + Bootstrap + Plotly).
Toutes les données viennent de l'API FastAPI (aucune valeur inventée).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import ALL, Input, Output, State, dcc, html, no_update

# ---------------------------------------------------------------------------
# Config / thème
# ---------------------------------------------------------------------------
API = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
ASSETS = Path(__file__).resolve().parent / "assets"
GEOJSON_PATH = ASSETS / "departements.geojson"

INK = "#0B1F33"
SIGNAL = "#C8102E"
PAPER = "#F7F9FB"
MUTED = "#5A6B7D"
FONT_UI = "Figtree, Segoe UI, sans-serif"
FONT_BRAND = "Fraunces, Georgia, serif"

BLOCS = ["EXG", "GAU", "CEN", "DRO", "EXD"]
COLORS = {
    "EXG": "#6B0F1A",
    "GAU": "#C8102E",
    "CEN": "#C4922A",
    "DRO": "#2A5F9E",
    "EXD": "#0B1F33",
}
BLOCS_LABELS = {
    "EXG": "Extrême gauche",
    "GAU": "Gauche",
    "CEN": "Centre",
    "DRO": "Droite",
    "EXD": "Extrême droite",
}
INDIC_COLS = [
    ("taux_chomage_n1", "Chômage N−1 (%)"),
    ("delta_chomage_1a", "Δ chômage 1 an"),
    ("delta_chomage_5a", "Δ chômage 5 ans"),
    ("emploi_pour_1000hab", "Emploi / 1 000 hab."),
    ("croissance_emploi_5a_pct", "Croissance emploi 5 ans (%)"),
    ("croissance_pop_5a_pct", "Croissance pop. 5 ans (%)"),
    ("taux_pauvrete_n1", "Pauvreté N−1 (%)"),
    ("creations_entreprises_n1", "Créations / 10k hab."),
]

_GEO = None


def load_geojson():
    global _GEO
    if _GEO is None:
        with open(GEOJSON_PATH, encoding="utf-8") as f:
            _GEO = json.load(f)
    return _GEO


def dept_label_map():
    names = {}
    for feat in load_geojson().get("features", []):
        props = feat.get("properties") or {}
        code = str(props.get("code", "")).strip()
        nom = props.get("nom")
        if code:
            names[code] = str(nom) if nom else code
    return names


def dept_dropdown_options(depts):
    names = dept_label_map()
    return [{"label": f"{d} — {names.get(d, d)}", "value": d} for d in (depts or [])]


def api_get(path, **params):
    try:
        r = requests.get(f"{API}{path}", params={k: v for k, v in params.items() if v is not None}, timeout=20)
        if r.status_code >= 400:
            return None
        return r.json()
    except Exception:
        return None


def api_post(path, payload):
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=20)
        return r.status_code, r.json()
    except Exception as e:
        return 599, {"detail": str(e)}


def empty_fig(msg="Aucune donnée"):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=15, color=MUTED, family=FONT_UI))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=360, margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def legend_below(n_items: int = 5) -> dict:
    """Légende horizontale sous le graphique — jamais sur le titre."""
    return dict(
        orientation="h",
        yanchor="top",
        y=-0.28,
        x=0.5,
        xanchor="center",
        title_text="",
        bgcolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=12, color=MUTED, family=FONT_UI),
        itemsizing="constant",
        itemwidth=36,
        traceorder="normal",
    )


def blocs_key(present=None) -> html.Div:
    """Légende HTML partagée (évite le chevauchement Plotly en colonnes étroites)."""
    codes = [b for b in BLOCS if present is None or b in present]
    return html.Div(
        className="ea-blocs-key",
        children=[
            html.Span(
                [html.Span(className="ea-swatch", style={"background": COLORS[b]}), f"{b} · {BLOCS_LABELS[b]}"],
                className="ea-blocs-item",
            )
            for b in codes
        ],
    )


def base_layout(fig, title="", height=420, subtitle=None, bottom_legend=True):
    text = title
    if subtitle:
        text = (
            f"{title}<br><span style='font-size:12px;color:{MUTED};"
            f"font-family:{FONT_UI};font-weight:500'>{subtitle}</span>"
        )
    # Fraunces a des ascendantes hautes : ne pas coller le titre au bord du SVG.
    top = 108 if subtitle else 86
    bottom = 88 if bottom_legend else 48
    fig.update_layout(
        title=dict(
            text=text,
            font=dict(family=FONT_BRAND, size=18, color=INK),
            x=0,
            xanchor="left",
            y=0.94,
            yanchor="top",
            pad=dict(t=10, b=10),
        ),
        font=dict(family=FONT_UI, color=INK, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.35)",
        height=height,
        margin=dict(l=56, r=28, t=top, b=bottom),
        legend=legend_below() if bottom_legend else dict(title_text=""),
        hoverlabel=dict(bgcolor="#fff", bordercolor="rgba(11,31,51,0.12)",
                        font=dict(family=FONT_UI, color=INK, size=13)),
        transition=dict(duration=280, easing="cubic-in-out"),
        showlegend=bottom_legend,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(color=MUTED, size=11))
    fig.update_yaxes(gridcolor="rgba(11,31,51,0.06)", zeroline=False,
                     tickfont=dict(color=MUTED, size=11))
    return fig


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
external_stylesheets = [
    dbc.themes.FLATLY,
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    "https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap",
]
app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    title="Electio-Analytics",
)
server = app.server

app.index_string = """<!DOCTYPE html>
<html lang="fr">
<head>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""


def kpi_metric(label, value, sub=""):
    kids = [
        html.Div(label, className="ea-metric-label"),
        html.Div(str(value) if value is not None else "—", className="ea-metric-value"),
    ]
    if sub:
        kids.append(html.Div(sub, className="ea-metric-sub"))
    return html.Div(kids, className="ea-metric")


app.layout = html.Div(
    className="ea-shell",
    children=[
        html.Header(
            className="ea-mast",
            children=[
                html.Div(
                    className="ea-mast-top",
                    children=[
                        html.Div([
                            html.Div(["Electio", html.Span("-Analytics")], className="ea-brand"),
                            html.Span(className="ea-signal-rule"),
                            html.P(
                                "Forces territoriales, indicateurs socio-économiques et aide à la décision.",
                                className="ea-lead",
                            ),
                        ]),
                        html.Div(
                            className="ea-db-bar",
                            children=[
                                html.Span(id="db-status-pill", className="ea-db-pill ea-db-unknown", children=[
                                    html.I(className="bi bi-database me-1"),
                                    html.Span("BDD…", id="db-status-label"),
                                ]),
                                dbc.Button(
                                    [html.I(className="bi bi-plug-fill me-2"), "Tester la BDD"],
                                    id="db-test-btn",
                                    n_clicks=0,
                                    className="ea-db-btn",
                                    color="dark",
                                    size="sm",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        dcc.Store(id="store-annees"),
        dcc.Store(id="store-depts"),
        dcc.Store(id="store-db-ok", data=False),
        dcc.Interval(id="boot", interval=400, max_intervals=1),
        dcc.Interval(id="db-poll", interval=60_000, n_intervals=0),
        html.Div(id="api-banner"),
        dbc.Toast(
            id="db-toast",
            header="Connexion base de données",
            is_open=False,
            dismissable=True,
            duration=4500,
            icon="success",
            style={"position": "fixed", "top": 18, "right": 18, "width": 340, "zIndex": 2000},
        ),
        dbc.Tabs(
            id="tabs",
            active_tab="tab-overview",
            class_name="ea-nav",
            children=[
                dbc.Tab(label="Vue d'ensemble", tab_id="tab-overview"),
                dbc.Tab(label="Indicateurs", tab_id="tab-indics"),
                dbc.Tab(label="Analyse du modèle", tab_id="tab-model"),
                dbc.Tab(label="Prédiction", tab_id="tab-predict"),
            ],
        ),
        html.Div(id="tab-body", className="ea-section"),
        html.Footer(
            className="ea-footer",
            children="Sources INSEE · data.gouv.fr · Licence Ouverte v2.0 — médaillon bronze → silver → gold · anti-leakage N−1",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Boot / bannière API
# ---------------------------------------------------------------------------
@app.callback(
    Output("store-annees", "data"),
    Output("store-depts", "data"),
    Output("api-banner", "children"),
    Input("boot", "n_intervals"),
)
def boot(_):
    health = api_get("/health")
    annees = api_get("/annees") or []
    depts = api_get("/departements") or []
    if health is None:
        banner = dbc.Alert(
            "API inaccessible — vérifiez que le backend tourne sur :8000.",
            color="danger", className="py-2",
        )
    elif not health.get("modele_pret"):
        banner = dbc.Alert("API joignable, modèle non prêt.", color="warning", className="py-2")
    else:
        banner = None
    return annees, depts, banner


def _ping_db():
    """Retourne (ok: bool, payload: dict|None, error: str|None)."""
    try:
        r = requests.get(f"{API}/health/db", timeout=8)
        data = r.json() if r.content else {}
        if r.status_code == 200 and data.get("database") == "up":
            return True, data, None
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            return False, detail, detail.get("error", "BDD indisponible")
        return False, data, str(detail)
    except Exception as e:
        return False, None, str(e)


@app.callback(
    Output("db-status-pill", "className"),
    Output("db-status-label", "children"),
    Output("store-db-ok", "data"),
    Input("db-poll", "n_intervals"),
    Input("boot", "n_intervals"),
)
def poll_db(_, __):
    ok, data, err = _ping_db()
    if ok:
        ms = data.get("latency_ms", "?")
        rows = data.get("gold_rows", "?")
        return (
            "ea-db-pill ea-db-up",
            f"BDD OK · {ms} ms · {rows} lignes",
            True,
        )
    return "ea-db-pill ea-db-down", f"BDD KO · {err or 'hors ligne'}", False


@app.callback(
    Output("db-toast", "is_open"),
    Output("db-toast", "children"),
    Output("db-toast", "icon"),
    Output("db-toast", "header"),
    Input("db-test-btn", "n_clicks"),
    prevent_initial_call=True,
)
def notify_db_click(n):
    if not n:
        return no_update, no_update, no_update, no_update
    ok, data, err = _ping_db()
    if ok:
        ms = data.get("latency_ms", "?")
        rows = data.get("gold_rows", "?")
        msg = (
            f"La base de données est toujours joignable.\n"
            f"Latence {ms} ms · table GOLD : {rows} lignes."
        )
        return True, msg, "success", "BDD disponible"
    return True, f"Impossible de joindre la base : {err or 'erreur'}", "danger", "BDD indisponible"


@app.callback(
    Output("tab-body", "children"),
    Input("tabs", "active_tab"),
    Input("store-annees", "data"),
    Input("store-depts", "data"),
)
def render_tab(tab, annees, depts):
    # Re-rendu quand les stores se remplissent (évite dropdown vide au 1er chargement)
    annees = annees if annees else (api_get("/annees") or [])
    depts = depts if depts else (api_get("/departements") or [])
    if tab == "tab-overview":
        return layout_overview(annees)
    if tab == "tab-indics":
        return layout_indics(depts)
    if tab == "tab-model":
        return layout_model()
    if tab == "tab-predict":
        return layout_predict(depts)
    return html.Div()


# ========================= VUE D'ENSEMBLE ==================================
def _build_kpis():
    info = api_get("/model/info") or {}
    deps = api_get("/departements")
    ans = api_get("/annees")
    ov = api_get("/dashboard/overview") or {}
    acc = info.get("accuracy_test_2022")
    if acc is None:
        acc = info.get("accuracy_cv_groupee")
    acc_txt = f"{acc:.0%}" if isinstance(acc, (int, float)) else "—"
    modele = (info.get("modele_retenu") or "gradient_boosting").replace("_", " ")
    n_gold = info.get("n_observations")
    n_years = len(ans) if ans else len(ov.get("annees") or [])
    return [
        kpi_metric("Départements", len(deps) if deps else info.get("n_departements", "—")),
        kpi_metric("Scrutins T1", n_years, "2002 → 2022"),
        kpi_metric("Observations", n_gold or "—", "GOLD · lag n−1"),
        kpi_metric("Accuracy holdout", acc_txt, modele.title()),
    ]


def layout_overview(annees):
    if not annees:
        annees = api_get("/annees") or []
    default = annees[-1] if annees else None
    return html.Div([
        html.Div(_build_kpis(), className="ea-metrics"),
        html.Div(className="ea-split", children=[
            html.Div(className="ea-panel", children=[
                html.H2("Carte des forces", className="ea-section-title"),
                html.P(
                    "Bloc arrivé en tête au premier tour, par département (données GOLD).",
                    className="ea-section-lead",
                ),
                html.Div([
                    html.Label("Élection", className="ea-label"),
                    dcc.Dropdown(
                        id="ov-annee",
                        options=[{"label": str(a), "value": a} for a in annees],
                        value=default,
                        clearable=False,
                        placeholder="Choisir une année",
                        style={"maxWidth": 200},
                    ),
                ], className="mb-2"),
                dcc.Loading(dcc.Graph(id="ov-map", config={"displayModeBar": False}), type="dot"),
            ]),
            html.Div(className="ea-panel", children=[
                html.H2("Répartition", className="ea-section-title"),
                html.P("Combien de départements chaque bloc emporte.", className="ea-section-lead"),
                dcc.Loading(dcc.Graph(id="ov-bars", config={"displayModeBar": False}), type="dot"),
                dcc.Loading(dcc.Graph(id="ov-donut", config={"displayModeBar": False}), type="dot"),
            ]),
        ]),
        html.Div(className="ea-panel mt-3", children=[
            html.H2("Évolution nationale", className="ea-section-title"),
            html.P(
                "Scores moyens T1 par bloc (tous départements) et territoires gagnés à chaque scrutin.",
                className="ea-section-lead",
            ),
            blocs_key(),
            html.Div(className="ea-split", children=[
                dcc.Loading(dcc.Graph(id="ov-scores", config={"displayModeBar": False}), type="dot"),
                dcc.Loading(dcc.Graph(id="ov-stack", config={"displayModeBar": False}), type="dot"),
            ]),
        ]),
        html.Div(className="ea-panel mt-3", children=[
            html.H2("Profil socio-économique du gagnant", className="ea-section-title"),
            html.P(
                "Chômage et emploi moyens dans les départements selon le bloc arrivé en tête "
                "(indicateurs GOLD, année d'élection).",
                className="ea-section-lead",
            ),
            blocs_key(),
            html.Div(className="ea-split", children=[
                dcc.Loading(dcc.Graph(id="ov-chomage", config={"displayModeBar": False}), type="dot"),
                dcc.Loading(dcc.Graph(id="ov-emploi", config={"displayModeBar": False}), type="dot"),
            ]),
        ]),
        html.Div(className="ea-panel mt-3", children=[
            html.H2("Heatmap territoires", className="ea-section-title"),
            html.P(
                "Nombre de départements en tête par bloc et par année d'élection.",
                className="ea-section-lead",
            ),
            dcc.Loading(dcc.Graph(id="ov-heat", config={"displayModeBar": False}), type="dot"),
        ]),
    ])


def _fig_scores_nationaux(scores: list) -> go.Figure:
    if not scores:
        return empty_fig("Scores nationaux indisponibles")
    df = pd.DataFrame(scores)
    fig = go.Figure()
    for b in BLOCS:
        sub = df[df["bloc"] == b].sort_values("annee")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["annee"],
            y=sub["score_moyen"],
            mode="lines+markers",
            name=b,
            showlegend=False,
            line=dict(color=COLORS[b], width=2.5),
            marker=dict(size=8),
            hovertemplate=f"<b>{b} — {BLOCS_LABELS[b]}</b><br>%{{x}} · %{{y:.1f}} %<extra></extra>",
        ))
    base_layout(fig, "Score moyen T1 (%)", height=380, subtitle="Moyenne nationale", bottom_legend=False)
    years = sorted(df["annee"].unique().tolist())
    fig.update_layout(
        xaxis=dict(title="Année", tickmode="array", tickvals=years, title_standoff=8),
        yaxis=dict(title="%", showgrid=True, gridcolor="rgba(11,31,51,0.06)",
                   title_standoff=8, automargin=True),
        margin=dict(l=56, r=24, b=56),
        showlegend=False,
    )
    return fig


def _fig_stack_gagnants(rows: list) -> go.Figure:
    if not rows:
        return empty_fig("Historique indisponible")
    df = pd.DataFrame(rows)
    fig = go.Figure()
    for b in BLOCS:
        sub = df[df["bloc"] == b].sort_values("annee")
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            x=sub["annee"].astype(str),
            y=sub["n_departements"],
            name=b,
            showlegend=False,
            marker_color=COLORS[b],
            hovertemplate=f"<b>{b} — {BLOCS_LABELS[b]}</b><br>%{{x}} · %{{y}} depts<extra></extra>",
        ))
    base_layout(fig, "Territoires gagnés", height=380, subtitle="Départements en tête", bottom_legend=False)
    fig.update_layout(
        barmode="stack",
        xaxis=dict(title="Année", type="category", title_standoff=8),
        yaxis=dict(title="Départements", showgrid=True, gridcolor="rgba(11,31,51,0.06)",
                   title_standoff=8, automargin=True),
        margin=dict(l=56, r=24, b=56),
        showlegend=False,
    )
    return fig


def _fig_socio_bloc(rows: list, value_col: str, title: str, y_title: str, unit: str = "") -> go.Figure:
    if not rows:
        return empty_fig(f"{title} indisponible")
    df = pd.DataFrame(rows)
    df = df[df["bloc"].isin(BLOCS)].copy()
    if df.empty or value_col not in df.columns:
        return empty_fig(f"{title} indisponible")
    fig = go.Figure()
    unit_txt = f" {unit}" if unit else ""
    for b in BLOCS:
        sub = df[df["bloc"] == b].sort_values("annee")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["annee"],
            y=sub[value_col],
            mode="lines+markers",
            name=b,
            showlegend=False,
            line=dict(color=COLORS[b], width=2.2),
            marker=dict(size=7),
            hovertemplate=(
                f"<b>{b} — {BLOCS_LABELS[b]}</b><br>%{{x}} · %{{y:.1f}}{unit_txt}<extra></extra>"
            ),
        ))
    base_layout(fig, title, height=360, subtitle=None, bottom_legend=False)
    years = sorted(df["annee"].unique().tolist())
    fig.update_layout(
        xaxis=dict(title="Année", tickmode="array", tickvals=years, title_standoff=8),
        yaxis=dict(title=y_title, showgrid=True, gridcolor="rgba(11,31,51,0.06)",
                   title_standoff=10, automargin=True),
        margin=dict(l=64, r=24, b=56),
        showlegend=False,
    )
    return fig


def _fig_heatmap(rows: list) -> go.Figure:
    if not rows:
        return empty_fig("Heatmap indisponible")
    df = pd.DataFrame(rows)
    pivot = (
        df.pivot_table(index="bloc", columns="annee", values="n_departements", aggfunc="sum")
        .reindex(BLOCS)
        .fillna(0)
    )
    years = sorted(pivot.columns.tolist())
    z = pivot[years].values
    fig = go.Figure(go.Heatmap(
        z=z,
        x=[str(y) for y in years],
        y=[f"{b}  {BLOCS_LABELS[b]}" for b in BLOCS],
        colorscale=[
            [0, "#F4F1EC"],
            [0.35, "#C5D4E8"],
            [0.7, "#3D6B9A"],
            [1, "#0B1F33"],
        ],
        text=z.astype(int),
        texttemplate="%{text}",
        textfont=dict(size=13),
        hovertemplate="<b>%{y}</b><br>%{x} · %{z:.0f} depts<extra></extra>",
        colorbar=dict(title="Depts", thickness=12, len=0.75, y=0.5),
    ))
    base_layout(fig, "Départements en tête", height=340, subtitle="Année × bloc", bottom_legend=False)
    fig.update_layout(
        margin=dict(l=130, r=56, b=48),
        showlegend=False,
    )
    return fig


@app.callback(
    Output("ov-map", "figure"),
    Output("ov-bars", "figure"),
    Output("ov-donut", "figure"),
    Output("ov-scores", "figure"),
    Output("ov-stack", "figure"),
    Output("ov-chomage", "figure"),
    Output("ov-emploi", "figure"),
    Output("ov-heat", "figure"),
    Input("ov-annee", "value"),
)
def overview_figs(annee):
    empty = empty_fig()
    overview = api_get("/dashboard/overview") or {}
    scores = overview.get("scores_nationaux") or []
    gagnants = overview.get("gagnants_par_annee") or []
    chomage = overview.get("chomage_par_bloc") or []
    emploi = overview.get("emploi_par_bloc") or []

    fig_scores = _fig_scores_nationaux(scores)
    fig_stack = _fig_stack_gagnants(gagnants)
    fig_chom = _fig_socio_bloc(
        chomage, "chomage_moyen", "Chômage moyen", "Chômage (%)", unit="%",
    )
    fig_emp = _fig_socio_bloc(
        emploi, "emploi_moyen", "Emploi moyen", "Emploi / 1 000 hab.", unit="",
    )
    fig_heat = _fig_heatmap(gagnants)

    if not annee:
        return empty_fig("Sélectionnez une année"), empty, empty, fig_scores, fig_stack, fig_chom, fig_emp, fig_heat

    carte = api_get("/carte", annee=annee)
    if not carte:
        return (
            empty_fig(f"Pas de données carte pour {annee}"),
            empty, empty, fig_scores, fig_stack, fig_chom, fig_emp, fig_heat,
        )

    df = pd.DataFrame(carte)
    df["libelle"] = df["bloc_gagnant"].map(BLOCS_LABELS)
    df["bloc_legende"] = df["bloc_gagnant"].map(lambda b: f"{b} · {BLOCS_LABELS.get(b, b)}")
    present = [b for b in BLOCS if b in set(df["bloc_gagnant"])]
    legend_order = [f"{b} · {BLOCS_LABELS[b]}" for b in present]
    color_map = {f"{b} · {BLOCS_LABELS[b]}": COLORS[b] for b in present}

    geo = load_geojson()
    fig_map = px.choropleth(
        df,
        geojson=geo,
        locations="code_dept",
        featureidkey="properties.code",
        color="bloc_legende",
        color_discrete_map=color_map,
        category_orders={"bloc_legende": legend_order},
        hover_data={"code_dept": True, "libelle": True, "bloc_legende": False},
        labels={"bloc_legende": "Bloc", "libelle": "Libellé", "code_dept": "Département"},
    )
    fig_map.update_traces(marker_line_width=0.4, marker_line_color="rgba(255,255,255,0.85)")
    fig_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", resolution=50)
    base_layout(fig_map, f"Scrutin {annee}", height=520, bottom_legend=False)
    fig_map.update_layout(
        margin=dict(l=8, r=8, b=72),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.02,
            x=0.5,
            xanchor="center",
            title_text="",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=MUTED, family=FONT_UI),
            itemsizing="constant",
            itemwidth=40,
        ),
        showlegend=True,
    )

    counts = (
        df["bloc_gagnant"].value_counts().reindex(BLOCS).fillna(0).astype(int).reset_index()
    )
    counts.columns = ["bloc", "n"]
    counts = counts[counts["n"] > 0].sort_values("n")
    fig_bar = go.Figure(go.Bar(
        x=counts["n"],
        y=[f"{b}  {BLOCS_LABELS[b]}" for b in counts["bloc"]],
        orientation="h",
        marker=dict(color=[COLORS[b] for b in counts["bloc"]], line=dict(width=0)),
        text=[str(int(n)) for n in counts["n"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x} départements<extra></extra>",
        width=0.55,
        showlegend=False,
    ))
    base_layout(fig_bar, "Départements en tête", height=300, subtitle=str(annee), bottom_legend=False)
    xmax = max(int(counts["n"].max()) * 1.28, 8)
    fig_bar.update_layout(
        xaxis=dict(title="Nombre de départements", range=[0, xmax], showgrid=True,
                   gridcolor="rgba(11,31,51,0.06)"),
        yaxis=dict(title="", automargin=True),
        margin=dict(l=140, r=48, b=48),
        showlegend=False,
    )

    fig_donut = go.Figure(go.Pie(
        labels=[f"{b} · {BLOCS_LABELS[b]}" for b in counts["bloc"]],
        values=counts["n"],
        hole=0.58,
        marker=dict(colors=[COLORS[b] for b in counts["bloc"]], line=dict(color="#fff", width=2)),
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value} depts · %{percent}<extra></extra>",
        sort=False,
        showlegend=False,
    ))
    base_layout(fig_donut, "Part des territoires", height=300, subtitle=str(annee), bottom_legend=False)
    fig_donut.update_layout(
        showlegend=False,
        margin=dict(l=24, r=24, b=40),
        annotations=[dict(
            text=f"<b>{int(counts['n'].sum())}</b><br>depts",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=INK, family=FONT_UI),
        )],
    )

    return fig_map, fig_bar, fig_donut, fig_scores, fig_stack, fig_chom, fig_emp, fig_heat


# ========================= INDICATEURS =====================================
def layout_indics(depts):
    if not depts:
        depts = api_get("/departements") or []
    opts = [{"label": d, "value": d} for d in depts]
    return html.Div([
        html.Div(className="ea-panel mb-3", children=[
            html.H2("Indicateurs socio-économiques", className="ea-section-title"),
            html.P("Trajectoires départementales — features antérieures au scrutin (N−1).",
                   className="ea-section-lead"),
            dbc.Row([
                dbc.Col([
                    html.Label("Département A", className="ea-label"),
                    dcc.Dropdown(id="in-dept-a", options=opts, value=depts[0] if depts else None, clearable=False),
                ], md=4),
                dbc.Col([
                    html.Label("Comparer avec", className="ea-label"),
                    dcc.Dropdown(id="in-dept-b", options=opts, value=None, placeholder="Aucun"),
                ], md=4),
                dbc.Col([
                    html.Label("Indicateurs", className="ea-label"),
                    dcc.Dropdown(
                        id="in-metrics",
                        multi=True,
                        options=[{"label": lab, "value": col} for col, lab in INDIC_COLS],
                        value=["taux_chomage_n1", "emploi_pour_1000hab", "creations_entreprises_n1"],
                    ),
                ], md=4),
            ], className="g-3"),
        ]),
        dcc.Loading(dcc.Graph(id="in-graph", config={"displayModeBar": False}), type="dot"),
        html.Div(id="in-table", className="ea-panel mt-3"),
    ])


@app.callback(
    Output("in-graph", "figure"),
    Output("in-table", "children"),
    Input("in-dept-a", "value"),
    Input("in-dept-b", "value"),
    Input("in-metrics", "value"),
)
def indic_figs(dept_a, dept_b, metrics):
    if not dept_a or not metrics:
        return empty_fig("Choisissez un département et des indicateurs"), html.Div()

    label_map = dict(INDIC_COLS)
    fig = go.Figure()
    tables = []

    def add_dept(dept, dash_style="solid"):
        data = api_get("/indicateurs", dept=dept)
        if not data:
            return
        df = pd.DataFrame(data).sort_values("annee")
        for col in metrics:
            if col not in df.columns:
                continue
            fig.add_trace(go.Scatter(
                x=df["annee"], y=df[col],
                name=f"{label_map.get(col, col)} · {dept}",
                mode="lines+markers",
                line=dict(width=2.5, dash=dash_style),
                marker=dict(size=8),
                hovertemplate=f"<b>{dept}</b> · {label_map.get(col, col)}<br>%{{x}} : %{{y}}<extra></extra>",
            ))
        last = df.iloc[-1]
        rows = []
        for col, lab in INDIC_COLS:
            if col not in df.columns:
                continue
            val = last.get(col)
            rows.append(html.Tr([
                html.Td(lab),
                html.Td("—" if pd.isna(val) else f"{val:.2f}" if isinstance(val, float) else str(val)),
            ]))
        tables.append(html.Div([
            html.H5(f"Dernières valeurs — dept {dept} ({int(last['annee'])})", className="h6 ea-brand"),
            dbc.Table([html.Thead(html.Tr([html.Th("Indicateur"), html.Th("Valeur")])),
                       html.Tbody(rows)], bordered=True, hover=True, size="sm", className="mb-0"),
        ]))

    add_dept(dept_a, "solid")
    if dept_b and dept_b != dept_a:
        add_dept(dept_b, "dot")

    if not fig.data:
        return empty_fig("Pas de données pour ce département"), html.Div("Aucune donnée.")

    years = sorted({int(x) for tr in fig.data for x in tr.x})
    base_layout(fig, "Évolution des indicateurs", height=480)
    fig.update_layout(
        xaxis=dict(title="", tickmode="array", tickvals=years, ticktext=[str(y) for y in years]),
        yaxis=dict(title="Valeur", gridcolor="rgba(11,31,51,0.07)"),
        margin=dict(l=56, r=40, b=96),
    )
    return fig, html.Div(tables, className="d-flex flex-wrap gap-4")


# ========================= ANALYSE MODELE ==================================
def layout_model():
    return html.Div([
        html.Div(className="ea-panel mb-3", children=[
            html.H2("Analyse du modèle", className="ea-section-title"),
            html.P(
                "Sélection walk-forward temporel (métrique principale). "
                "La CV géo reste affichée en secondaire ; le holdout = dernier scrutin.",
                className="ea-section-lead",
            ),
        ]),
        html.Div(className="ea-split mb-3", children=[
            html.Div(className="ea-panel", children=[
                html.H3("Matrice de confusion", className="ea-section-title", style={"fontSize": "1.2rem"}),
                html.P("Holdout temporel (dernier scrutin)", className="ea-section-lead"),
                dcc.Loading(dcc.Graph(id="md-confusion", config={"displayModeBar": False}), type="dot"),
            ]),
            html.Div(className="ea-panel", children=[
                html.H3("Importance des variables", className="ea-section-title", style={"fontSize": "1.2rem"}),
                html.P("Modèle retenu (walk-forward)", className="ea-section-lead"),
                dcc.Loading(dcc.Graph(id="md-importance", config={"displayModeBar": False}), type="dot"),
            ]),
        ]),
        html.Div(className="ea-panel", children=[
            html.H3("Comparaison des modèles", className="ea-section-title", style={"fontSize": "1.2rem"}),
            html.Div(id="md-comparison", className="mt-2"),
        ]),
    ])


@app.callback(
    Output("md-confusion", "figure"),
    Output("md-importance", "figure"),
    Output("md-comparison", "children"),
    Input("tabs", "active_tab"),
)
def model_figs(tab):
    if tab != "tab-model":
        return no_update, no_update, no_update

    conf = api_get("/model/confusion")
    if conf and conf.get("matrix"):
        labels = conf["labels"]
        z = conf["matrix"]
        fig_cm = go.Figure(data=go.Heatmap(
            z=z, x=labels, y=labels, colorscale="Blues",
            text=z, texttemplate="%{text}", hovertemplate="Réel %{y} · Prédit %{x} : %{z}<extra></extra>",
        ))
        acc = conf.get("accuracy_test_2022")
        sub = f"Accuracy test 2022 : {acc:.0%}" if acc is not None else ""
        base_layout(fig_cm, f"Confusion — test 2022  {sub}", height=420)
        fig_cm.update_layout(xaxis_title="Prédit", yaxis_title="Réel",
                             margin=dict(l=64, r=40, b=56))
    else:
        fig_cm = empty_fig("Matrice indisponible")

    imp_data = api_get("/model/importance") or {}
    imp = imp_data.get("importances") or {}
    if imp:
        items = list(imp.items())[:12][::-1]
        fig_imp = go.Figure(go.Bar(
            x=[v for _, v in items], y=[k for k, _ in items], orientation="h",
            marker_color=INK,
            hovertemplate="<b>%{y}</b><br>%{x:.3f}<extra></extra>",
        ))
        base_layout(fig_imp, f"Importance — {imp_data.get('modele_retenu', 'modèle')}", height=420)
        fig_imp.update_layout(xaxis_title="Importance", yaxis_title="",
                              margin=dict(l=140, r=40, b=48))
    else:
        fig_imp = empty_fig("Importances indisponibles")

    comp = api_get("/model/comparison") or {}
    rows = comp.get("modeles") or []
    if not rows:
        table = html.P("Rapport ml_report.json indisponible côté API.", className="text-muted")
    else:
        header = html.Thead(html.Tr([
            html.Th("Modèle"), html.Th("Acc. walk-fwd"), html.Th("F1 walk-fwd"),
            html.Th("Acc. holdout"), html.Th("CV géo"), html.Th(""),
        ]))
        body_rows = []
        for r in rows:
            badge = dbc.Badge("Retenu", color="danger") if r.get("retenu") else ""
            body_rows.append(html.Tr([
                html.Td(r.get("modele", "")),
                html.Td(f"{r['accuracy_walkforward']:.3f}" if r.get("accuracy_walkforward") is not None else "—"),
                html.Td(f"{r['f1_macro_walkforward']:.3f}" if r.get("f1_macro_walkforward") is not None else "—"),
                html.Td(f"{r['accuracy_test_2022']:.3f}" if r.get("accuracy_test_2022") is not None else "—"),
                html.Td(f"{r['accuracy_cv_groupee']:.3f}" if r.get("accuracy_cv_groupee") is not None else "—"),
                html.Td(badge),
            ]))
        table = dbc.Table([header, html.Tbody(body_rows)], bordered=True, hover=True, responsive=True, size="sm")
        table = html.Div([
            html.P(
                f"Source : {comp.get('source')} · modèle retenu : {comp.get('modele_retenu')} · "
                f"n = {comp.get('n_observations')}",
                className="small text-muted",
            ),
            table,
        ])

    return fig_cm, fig_imp, table


# ========================= PREDICTION ======================================
PREDICT_FEATURES = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
    "taux_pauvrete_n1", "creations_entreprises_n1",
    "pct_gagnant_precedent", "marge_gagnante_precedente",
    "bloc_gagnant_precedent",
]

# Leviers what-if = features réellement utilisées par le modèle (hors lags politiques).
# Bornes = enveloppe d'entraînement observée dans data/gold/dataset_analytique.csv
# (lignes avec bloc_gagnant_precedent non nul). À recalculer après chaque
# run_pipeline.py — un arbre / RF n'extrapole pas hors de cette enveloppe.
WHATIF_METRICS = {
    "taux_chomage_n1": {
        "short": "Chômage",
        "label": "Chômage N−1",
        "question": "Et si le chômage était de…",
        "unit": " %",
        "step": 0.1,
        "digits": 1,
        "pad": 3.6,  # ≈ 2 σ
        "clamp": (3.79, 12.01),
        "shock": 1.8,
        "shock_txt": "pts",
        "fallback": 8.0,
        "link_deltas": True,
    },
    "delta_chomage_5a": {
        "short": "Δ chômage 5 ans",
        "label": "Variation du chômage sur 5 ans",
        "question": "Et si le chômage avait varié de…",
        "unit": " pts",
        "step": 0.05,
        "digits": 2,
        "pad": 0.9,  # ≈ 2 σ
        "clamp": (-0.92, 0.72),
        "shock": 0.45,
        "shock_txt": "pts",
        "fallback": 0.0,
    },
    "emploi_pour_1000hab": {
        "short": "Emploi / 1 000 hab.",
        "label": "Emploi pour 1 000 habitants",
        "question": "Et si l'emploi pour 1 000 habitants était de…",
        "unit": "",
        "step": 5,
        "digits": 0,
        "pad": 82,  # ≈ 2 σ
        "clamp": (301, 467),
        "shock": 40,
        "shock_txt": "",
        "fallback": 350,
    },
    "croissance_emploi_5a_pct": {
        "short": "Croissance emploi",
        "label": "Croissance de l'emploi (5 ans)",
        "question": "Et si la croissance de l'emploi sur 5 ans était de…",
        "unit": " %",
        "step": 0.2,
        "digits": 1,
        "pad": 2.0,  # ≈ 2 σ
        "clamp": (-1.2, 7.8),
        "shock": 1.0,
        "shock_txt": "pts",
        "fallback": 1.0,
    },
    "croissance_pop_5a_pct": {
        "short": "Croissance pop.",
        "label": "Croissance de la population (5 ans)",
        "question": "Et si la croissance de la population sur 5 ans était de…",
        "unit": " %",
        "step": 0.2,
        "digits": 1,
        "pad": 1.4,  # ≈ 2 σ
        "clamp": (-1.8, 7.9),
        "shock": 0.7,
        "shock_txt": "pts",
        "fallback": 0.0,
    },
    "creations_entreprises_n1": {
        "short": "Créations d'entreprises",
        "label": "Créations d'entreprises / 10 000 hab.",
        "question": "Et si les créations d'entreprises (pour 10 000 hab.) étaient de…",
        "unit": "",
        "step": 1,
        "digits": 0,
        "pad": 52,  # ≈ 2 σ
        "clamp": (62, 166),
        "shock": 26,
        "shock_txt": "",
        "fallback": 100,
    },
}

# Scénarios narratifs (France) — chocs ≈ 1 σ par levier (dans l'enveloppe)
SCENARIOS = {
    "crise": {
        "label": "Crise économique",
        "blurb": "Chômage en nette hausse, emploi et créations d’entreprises en repli.",
        "horizon": 2,
        "deltas": {
            "taux_chomage_n1": 1.8,
            "delta_chomage_5a": 0.45,
            "emploi_pour_1000hab": -40,
            "croissance_emploi_5a_pct": -1.0,
            "creations_entreprises_n1": -26,
        },
    },
    "reprise": {
        "label": "Reprise / croissance",
        "blurb": "Baisse du chômage, dynamisme de l’emploi et des créations.",
        "horizon": 2,
        "deltas": {
            "taux_chomage_n1": -1.4,
            "delta_chomage_5a": -0.45,
            "emploi_pour_1000hab": 35,
            "croissance_emploi_5a_pct": 1.0,
            "creations_entreprises_n1": 26,
            "croissance_pop_5a_pct": 0.7,
        },
    },
    "tension": {
        "label": "Tension sociale",
        "blurb": "Stagnation durable : chômage qui s’installe, tissu productif fragilisé.",
        "horizon": 3,
        "deltas": {
            "taux_chomage_n1": 0.9,
            "delta_chomage_5a": 0.3,
            "emploi_pour_1000hab": -20,
            "croissance_emploi_5a_pct": -0.6,
            "croissance_pop_5a_pct": -0.5,
            "creations_entreprises_n1": -14,
        },
    },
}


def _fmt_num(val, suffix="", digits=1):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        txt = f"{float(val):.{digits}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"
    return f"{txt}{suffix}"


def _round_step(val, step, digits):
    if step >= 1:
        return float(round(float(val) / step) * step)
    return round(float(val), digits)


def _metric_real(baseline, key):
    spec = WHATIF_METRICS[key]
    raw = (baseline or {}).get(key)
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return float(spec["fallback"])
    return _round_step(raw, spec["step"], spec["digits"])


def _slider_conf(key, baseline):
    spec = WHATIF_METRICS[key]
    real = _metric_real(baseline, key)
    lo = max(spec["clamp"][0], real - spec["pad"])
    hi = min(spec["clamp"][1], real + spec["pad"])
    if hi <= lo:
        hi = lo + spec["step"] * 10
    lo = _round_step(lo, spec["step"], spec["digits"])
    hi = _round_step(hi, spec["step"], spec["digits"])
    if hi <= lo:
        hi = lo + spec["step"]
    mid = _round_step((lo + hi) / 2, spec["step"], spec["digits"])
    marks = {
        lo: _fmt_num(lo, spec["unit"], spec["digits"]),
        mid: _fmt_num(mid, spec["unit"], spec["digits"]),
        hi: _fmt_num(hi, spec["unit"], spec["digits"]),
    }
    return lo, hi, spec["step"], marks, real


def _shock_labels(key):
    spec = WHATIF_METRICS[key]
    shock = spec["shock"]
    digits = 0 if abs(float(shock) - round(float(shock))) < 1e-9 else spec["digits"]
    disp = _fmt_num(shock, f" {spec['shock_txt']}" if spec["shock_txt"] else "", digits).strip()
    if key == "taux_chomage_n1":
        return f"Moins de chômage (−{disp})", f"Plus de chômage (+{disp})"
    return f"Baisse (−{disp})", f"Hausse (+{disp})"


def _apply_deltas(baseline, deltas):
    """Applique des chocs relatifs à la baseline, bornés par le clamp de chaque métrique."""
    out = {}
    for key, delta in (deltas or {}).items():
        if key not in WHATIF_METRICS:
            continue
        spec = WHATIF_METRICS[key]
        real = _metric_real(baseline, key)
        val = _round_step(real + float(delta), spec["step"], spec["digits"])
        lo, hi = spec["clamp"]
        out[key] = float(min(hi, max(lo, val)))
    return out


def _build_payload(baseline, overrides):
    payload = {k: baseline.get(k) for k in PREDICT_FEATURES}
    for key, sim_val in (overrides or {}).items():
        if key not in WHATIF_METRICS:
            continue
        spec = WHATIF_METRICS[key]
        real = baseline.get(key)
        payload[key] = float(sim_val)
        if spec.get("link_deltas") and real is not None:
            shock = float(sim_val) - float(real)
            for dkey in ("delta_chomage_1a", "delta_chomage_5a"):
                if payload.get(dkey) is not None:
                    payload[dkey] = float(payload[dkey]) + shock
    # Garde les leviers what-if dans l'enveloppe (y compris apres link_deltas)
    for key, spec in WHATIF_METRICS.items():
        if payload.get(key) is None:
            continue
        lo, hi = spec["clamp"]
        payload[key] = float(min(hi, max(lo, float(payload[key]))))
    return payload


def _metric_slider_block(key, baseline, value=None):
    spec = WHATIF_METRICS[key]
    lo, hi, step, marks, real = _slider_conf(key, baseline)
    if value is None:
        value = real
    else:
        value = _round_step(min(hi, max(lo, float(value))), step, spec["digits"])
    return html.Div(className="ea-whatif-metric", children=[
        html.Div(className="ea-whatif-head", children=[
            html.Label(spec["question"], className="ea-label mb-0"),
            html.Span(
                id={"type": "p-readout", "metric": key},
                children=_fmt_num(value, spec["unit"], spec["digits"]),
                className="ea-whatif-value",
            ),
        ]),
        dcc.Slider(
            id={"type": "p-slider", "metric": key},
            min=lo,
            max=hi,
            step=step,
            value=value,
            marks=marks,
            tooltip={"placement": "bottom", "always_visible": False},
            className="ea-slider",
        ),
    ])


def layout_predict(depts):
    depts = depts or []
    opts = [{"label": "France (national)", "value": "FR"}] + dept_dropdown_options(depts)
    default = "FR"
    metric_opts = [{"label": spec["short"], "value": key} for key, spec in WHATIF_METRICS.items()]
    return html.Div([
        html.Div(className="ea-panel mb-3", children=[
            html.H2("Prédiction what-if", className="ea-section-title"),
            html.P(
                "Prévision France (agrégat national) sur 1 / 2 / 3 ans (sujet préfecture). "
                "Choisissez les métriques à simuler : les autres restent à la moyenne nationale. "
                "Un département reste disponible en option pour un zoom territorial.",
                className="ea-section-lead",
            ),
            html.Div([
                html.Label("Périmètre", className="ea-label"),
                dcc.Dropdown(
                    id="p-dept",
                    options=opts,
                    value=default,
                    clearable=False,
                    placeholder="France (national)",
                    style={"maxWidth": 420},
                ),
            ], className="mb-3"),
            dcc.Store(id="p-baseline"),
            dcc.Store(id="p-scenario", data=None),
            html.Div(id="p-context"),
            html.Div([
                html.Label("Scénarios France", className="ea-label"),
                html.P(
                    "Trois trajectoires types, en plus de la baseline nationale. "
                    "Un clic charge les chocs socio-éco et aligne l’horizon.",
                    className="ea-metric-sub mb-2",
                ),
                html.Div(className="ea-scenario-grid", children=[
                    html.Button(
                        [
                            html.Span(SCENARIOS["crise"]["label"], className="ea-scenario-title"),
                            html.Span(SCENARIOS["crise"]["blurb"], className="ea-scenario-blurb"),
                        ],
                        id="p-sc-crise", n_clicks=0, type="button",
                        className="ea-scenario-card ea-scenario-crise",
                    ),
                    html.Button(
                        [
                            html.Span(SCENARIOS["reprise"]["label"], className="ea-scenario-title"),
                            html.Span(SCENARIOS["reprise"]["blurb"], className="ea-scenario-blurb"),
                        ],
                        id="p-sc-reprise", n_clicks=0, type="button",
                        className="ea-scenario-card ea-scenario-reprise",
                    ),
                    html.Button(
                        [
                            html.Span(SCENARIOS["tension"]["label"], className="ea-scenario-title"),
                            html.Span(SCENARIOS["tension"]["blurb"], className="ea-scenario-blurb"),
                        ],
                        id="p-sc-tension", n_clicks=0, type="button",
                        className="ea-scenario-card ea-scenario-tension",
                    ),
                ]),
                html.Div(id="p-scenario-badge", className="mt-2"),
            ], className="mb-4"),
            html.Div([
                html.Label("Horizon de prévision", className="ea-label"),
                dcc.RadioItems(
                    id="p-horizon",
                    options=[
                        {"label": "1 an", "value": 1},
                        {"label": "2 ans", "value": 2},
                        {"label": "3 ans", "value": 3},
                    ],
                    value=1,
                    inline=True,
                    className="ea-horizon-picks",
                    inputClassName="ea-metric-pick-input",
                    labelClassName="ea-metric-pick",
                ),
                html.P(
                    "Plus l’horizon est lointain, plus l’incertitude est élargie "
                    "(tendances socio-éco extrapolées).",
                    className="ea-metric-sub mb-0 mt-2",
                ),
            ], className="mb-4"),
            html.Div([
                html.Label("Métriques à simuler via le modèle", className="ea-label"),
                dcc.Checklist(
                    id="p-metrics",
                    options=metric_opts,
                    value=["taux_chomage_n1"],
                    inline=True,
                    className="ea-metric-picks",
                    inputClassName="ea-metric-pick-input",
                    labelClassName="ea-metric-pick",
                ),
                html.P(
                    "Cochez un ou plusieurs leviers. "
                    "Les métriques non cochées restent à leur valeur réelle (France ou département).",
                    className="ea-metric-sub mb-0 mt-2",
                ),
            ], className="mb-2"),
            html.Div(id="p-sliders", className="ea-whatif"),
            html.Div(className="ea-scenarios", children=[
                html.Button(
                    "Réinitialiser (situation réelle)",
                    id="p-sc-real",
                    n_clicks=0,
                    type="button",
                    className="ea-chip",
                ),
            ]),
        ]),
        html.Div(id="p-winner"),
        dcc.Loading(dcc.Graph(id="p-graph", config={"displayModeBar": False}), type="dot"),
        dcc.Loading(dcc.Graph(id="p-graph-horizons", config={"displayModeBar": False}), type="dot"),
        dcc.Loading(dcc.Graph(id="p-graph-scenarios", config={"displayModeBar": False}), type="dot"),
    ])


def _predict_context(row):
    annee = row.get("annee")
    annee_cible = row.get("annee_cible")
    dept = str(row.get("code_dept", "")).strip()
    is_fr = dept == "FR" or row.get("perimetre") == "france"
    lib = "France" if is_fr else (dept_label_map().get(dept) or row.get("libelle") or dept)
    if is_fr and row.get("n_departements"):
        ref = f"France · baseline {annee} ({row['n_departements']} depts)" if annee else "France"
    else:
        ref = f"{lib} · baseline {annee}" if annee else lib
    if annee_cible:
        ref = f"{ref} → cible {annee_cible}"
    prec = row.get("bloc_gagnant_precedent")
    obs = row.get("bloc_gagnant")
    chom_label = "Chômage moyen" if is_fr else "Chômage réel"
    obs_label = f"Majorité {annee}" if is_fr and annee else (f"Observé {annee}" if annee else "Observé")
    cible_label = f"Cible prévision" if annee_cible else "Cible"
    return html.Div(className="ea-snap", children=[
        html.Div([
            html.Div("Référence", className="ea-metric-label"),
            html.Div(ref, className="ea-snap-value"),
        ], className="ea-snap-item"),
        html.Div([
            html.Div(cible_label, className="ea-metric-label"),
            html.Div(str(annee_cible) if annee_cible else "—", className="ea-snap-value"),
        ], className="ea-snap-item"),
        html.Div([
            html.Div(chom_label, className="ea-metric-label"),
            html.Div(_fmt_num(row.get("taux_chomage_n1"), " %"), className="ea-snap-value"),
        ], className="ea-snap-item"),
        html.Div([
            html.Div("Emploi / 1 000 hab.", className="ea-metric-label"),
            html.Div(_fmt_num(row.get("emploi_pour_1000hab"), digits=0), className="ea-snap-value"),
        ], className="ea-snap-item"),
        html.Div([
            html.Div("Créations / 10k", className="ea-metric-label"),
            html.Div(_fmt_num(row.get("creations_entreprises_n1"), digits=0), className="ea-snap-value"),
        ], className="ea-snap-item"),
        html.Div([
            html.Div("Bloc précédent (lag)", className="ea-metric-label"),
            html.Div(
                f"{prec} — {BLOCS_LABELS.get(prec, prec)}" if prec else "—",
                className="ea-snap-value",
            ),
        ], className="ea-snap-item"),
        html.Div([
            html.Div(obs_label, className="ea-metric-label"),
            html.Div(
                f"{obs} — {BLOCS_LABELS.get(obs, obs)}" if obs else "—",
                className="ea-snap-value",
            ),
        ], className="ea-snap-item"),
    ])


@app.callback(
    Output("p-baseline", "data"),
    Output("p-context", "children"),
    Input("p-dept", "value"),
)
def load_predict_baseline(dept):
    if not dept:
        return None, html.P("Choisissez un périmètre (France ou département).", className="text-muted")
    row = api_get("/predict/baseline", dept=dept)
    if not row:
        label = "France" if str(dept).upper() in ("FR", "FRANCE") else f"le département {dept}"
        return None, dbc.Alert(
            f"Pas de données GOLD pour {label}.",
            color="warning", className="py-2",
        )
    return row, _predict_context(row)


@app.callback(
    Output("p-scenario", "data"),
    Output("p-metrics", "value"),
    Output("p-horizon", "value"),
    Output("p-scenario-badge", "children"),
    Input("p-sc-crise", "n_clicks"),
    Input("p-sc-reprise", "n_clicks"),
    Input("p-sc-tension", "n_clicks"),
    Input("p-sc-real", "n_clicks"),
    prevent_initial_call=True,
)
def apply_scenario(_crise, _reprise, _tension, _real):
    tid = dash.callback_context.triggered_id
    if tid == "p-sc-real" or tid is None:
        return None, ["taux_chomage_n1"], no_update, html.Div()
    key = {
        "p-sc-crise": "crise",
        "p-sc-reprise": "reprise",
        "p-sc-tension": "tension",
    }.get(tid)
    if not key or key not in SCENARIOS:
        return no_update, no_update, no_update, no_update
    sc = SCENARIOS[key]
    metrics = list(sc["deltas"].keys())
    badge = html.Div(className=f"ea-scenario-badge ea-scenario-{key}", children=[
        html.Strong(f"Scénario actif : {sc['label']}"),
        html.Span(f" — {sc['blurb']} (horizon {sc['horizon']} ans)"),
    ])
    return key, metrics, sc["horizon"], badge


@app.callback(
    Output("p-sliders", "children"),
    Input("p-baseline", "data"),
    Input("p-metrics", "value"),
    Input("p-scenario", "data"),
    Input("p-sc-real", "n_clicks"),
)
def render_predict_sliders(baseline, metrics, scenario, _reset):
    selected = [m for m in (metrics or []) if m in WHATIF_METRICS]
    if not selected:
        return html.P(
            "Cochez au moins une métrique pour activer la simulation.",
            className="text-muted mt-2",
        )
    if not baseline:
        return html.P("Choisissez un périmètre.", className="text-muted mt-2")
    overrides = {}
    if scenario and scenario in SCENARIOS:
        overrides = _apply_deltas(baseline, SCENARIOS[scenario]["deltas"])
    return [
        _metric_slider_block(key, baseline, overrides.get(key))
        for key in selected
    ]


@app.callback(
    Output({"type": "p-readout", "metric": ALL}, "children"),
    Input({"type": "p-slider", "metric": ALL}, "value"),
    State({"type": "p-slider", "metric": ALL}, "id"),
)
def update_slider_readouts(values, ids):
    if not ids:
        return []
    out = []
    for val, sid in zip(values or [], ids):
        key = sid["metric"]
        spec = WHATIF_METRICS[key]
        out.append(_fmt_num(val, spec["unit"], spec["digits"]))
    return out


@app.callback(
    Output("p-graph", "figure"),
    Output("p-graph-horizons", "figure"),
    Output("p-winner", "children"),
    Input("p-baseline", "data"),
    Input("p-horizon", "value"),
    Input("p-metrics", "value"),
    Input("p-scenario", "data"),
    Input({"type": "p-slider", "metric": ALL}, "value"),
    State({"type": "p-slider", "metric": ALL}, "id"),
)
def predict_fig(baseline, horizon, metrics, scenario, slider_vals, slider_ids):
    horizon = int(horizon or 1)
    if horizon not in (1, 2, 3):
        horizon = 1
    if not baseline:
        empty = empty_fig("Choisissez un périmètre")
        return empty, empty, html.Div()

    selected = set(m for m in (metrics or []) if m in WHATIF_METRICS)
    sim_notes = []
    overrides = {}
    for val, sid in zip(slider_vals or [], slider_ids or []):
        key = sid["metric"]
        if key in selected:
            overrides[key] = float(val)

    payload = _build_payload(baseline, overrides)
    for key, sim_val in overrides.items():
        spec = WHATIF_METRICS[key]
        real = baseline.get(key)
        sim_notes.append(
            f"{spec['short']} {_fmt_num(sim_val, spec['unit'], spec['digits'])}"
            + (
                f" (réel {_fmt_num(real, spec['unit'], spec['digits'])})"
                if real is not None else ""
            )
        )

    payload["horizon_ans"] = horizon
    code, body = api_post("/predict", payload)
    if code >= 400:
        err = empty_fig(f"Erreur API {code} : {body.get('detail', body)}")
        return err, err, html.Div()

    par_h = body.get("probabilites_par_horizon") or {}
    proba = body.get("probabilites") or par_h.get(str(horizon)) or {}
    if not proba:
        empty = empty_fig("Pas de probabilités")
        return empty, empty, html.Div()

    if max(proba.values()) > 1.5:
        proba = {k: v / 100.0 for k, v in proba.items()}

    ordered = sorted(proba.items(), key=lambda kv: kv[1])
    winner, win_p = max(proba.items(), key=lambda kv: kv[1])
    labels = [b for b, _ in ordered]
    values = [p for _, p in ordered]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(
            color=[COLORS.get(b, MUTED) for b in labels],
            opacity=[1.0 if b == winner else 0.7 for b in labels],
            line=dict(width=[2.5 if b == winner else 0 for b in labels], color=SIGNAL),
        ),
        text=[f"{p:.0%}" for p in values],
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(color=PAPER, size=13),
        hovertemplate="%{y} : %{x:.1%}<extra></extra>",
    ))
    base_layout(fig, f"Probabilités à {horizon} an{'s' if horizon > 1 else ''}", height=360)
    fig.update_layout(
        xaxis=dict(range=[0, 1], tickvals=[0, 0.25, 0.5, 0.75, 1],
                   ticktext=["0 %", "25 %", "50 %", "75 %", "100 %"], title=""),
        yaxis_title="",
        margin=dict(l=72, r=40, b=48),
    )
    fig.add_vline(x=0.5, line_dash="dash", line_color="rgba(11,31,51,0.25)")

    fig_h = go.Figure()
    blocs_order = [b for b in BLOCS if any(b in (par_h.get(str(h)) or {}) for h in (1, 2, 3))]
    if not blocs_order:
        blocs_order = list(proba.keys())
    for h in (1, 2, 3):
        ph = par_h.get(str(h)) or {}
        if ph and max(ph.values()) > 1.5:
            ph = {k: v / 100.0 for k, v in ph.items()}
        fig_h.add_trace(go.Bar(
            name=f"{h} an" if h == 1 else f"{h} ans",
            x=blocs_order,
            y=[ph.get(b, 0) for b in blocs_order],
            marker_color=[COLORS.get(b, MUTED) for b in blocs_order],
            opacity=0.55 if h != horizon else 1.0,
            hovertemplate="%{x} · " + (f"{h} an" if h == 1 else f"{h} ans")
            + " : %{y:.1%}<extra></extra>",
        ))
    base_layout(fig_h, "Comparaison des horizons 1 / 2 / 3 ans", height=340)
    fig_h.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 1], tickformat=".0%", title=""),
        xaxis_title="",
        legend=legend_below(3),
        margin=dict(l=48, r=24, b=72, t=56),
    )

    annee = baseline.get("annee")
    annee_cible = baseline.get("annee_cible")
    obs = baseline.get("bloc_gagnant")
    is_fr = str(baseline.get("code_dept", "")).upper() == "FR" or baseline.get("perimetre") == "france"
    scope = "France" if is_fr else f"référence {annee}"
    cible_txt = f" · cible {annee_cible}" if annee_cible else ""
    sc_label = SCENARIOS[scenario]["label"] if scenario in SCENARIOS else None
    if sc_label:
        note = (
            f"Scénario « {sc_label} » · horizon {horizon} an{'s' if horizon > 1 else ''} · "
            f"baseline {scope}"
            + (f" ({annee})" if is_fr and annee else "")
            + cible_txt
            + "."
        )
        if sim_notes:
            note += f" Leviers : {'; '.join(sim_notes)}."
    elif sim_notes:
        note = (
            f"Horizon {horizon} an{'s' if horizon > 1 else ''} · "
            f"leviers : {'; '.join(sim_notes)}. "
            f"Baseline {scope}"
            + (f" ({annee})" if is_fr and annee else "")
            + cible_txt
            + "."
        )
    else:
        note = (
            f"Horizon {horizon} an{'s' if horizon > 1 else ''} · "
            f"aucune métrique simulée (baseline {scope}"
            + (f" {annee}" if annee else "")
            + cible_txt
            + ")."
        )
        if obs:
            label_obs = "Majorité nationale" if is_fr else "Observé"
            note += f" {label_obs} : {obs} — {BLOCS_LABELS.get(obs, obs)}."

    hors = body.get("hors_enveloppe") or []
    if hors:
        details = ", ".join(
            f"{o.get('feature')}={o.get('valeur')} ∉ [{o.get('min')}; {o.get('max')}]"
            for o in hors
        )
        winner_box = html.Div(className="pred-winner", children=[
            dbc.Alert(
                [
                    html.Strong("Hors enveloppe d'entraînement — prédiction non conclusive. "),
                    html.Span(
                        "Au moins une feature dépasse le min/max observé à l'entraînement ; "
                        "le modèle (arbre / forêt) ne généralise pas au-delà. "
                        f"Dépassements : {details}."
                    ),
                ],
                color="warning",
                className="mb-2 py-2",
            ),
            html.Div(
                f"Distribution indicative à {horizon} an{'s' if horizon > 1 else ''} "
                f"(après clamp) — pas de vainqueur tranché",
                className="ea-metric-label",
            ),
            html.Div(
                f"Tête de liste technique : {winner} — {BLOCS_LABELS.get(winner, winner)} "
                f"({win_p:.0%})",
                className="ea-metric-sub",
                style={"fontSize": "1.05rem"},
            ),
            html.P(note, className="ea-metric-sub mb-0 mt-2"),
        ])
    else:
        winner_box = html.Div(className="pred-winner", children=[
            html.Div(
                f"Bloc prédit à {horizon} an{'s' if horizon > 1 else ''}"
                + (f" (cible {annee_cible})" if annee_cible else ""),
                className="ea-metric-label",
            ),
            html.Div(
                f"{winner} — {BLOCS_LABELS.get(winner, winner)} ({win_p:.0%})",
                className="ea-metric-value",
                style={"fontSize": "1.55rem"},
            ),
            html.P(note, className="ea-metric-sub mb-0 mt-2"),
            html.P(
                "Prédiction indicative — limites du modèle assumées "
                "(extrapolation des tendances + incertitude croissante).",
                className="ea-metric-sub mb-0 mt-1",
            ),
        ])
    return fig, fig_h, winner_box


@app.callback(
    Output("p-graph-scenarios", "figure"),
    Input("p-baseline", "data"),
    Input("p-horizon", "value"),
)
def predict_scenarios_compare(baseline, horizon):
    """Compare baseline France + 3 scénarios au même horizon."""
    horizon = int(horizon or 1)
    if horizon not in (1, 2, 3):
        horizon = 1
    if not baseline:
        return empty_fig("Choisissez un périmètre")

    series = [("Baseline France", {})]
    for key, sc in SCENARIOS.items():
        series.append((sc["label"], _apply_deltas(baseline, sc["deltas"])))

    results = []
    for name, overrides in series:
        payload = _build_payload(baseline, overrides)
        payload["horizon_ans"] = horizon
        code, body = api_post("/predict", payload)
        if code >= 400:
            return empty_fig(f"Erreur API {code}")
        proba = body.get("probabilites") or {}
        if proba and max(proba.values()) > 1.5:
            proba = {k: v / 100.0 for k, v in proba.items()}
        results.append((name, proba))

    blocs_order = [b for b in BLOCS if any(b in p for _, p in results)]
    if not blocs_order:
        blocs_order = sorted({b for _, p in results for b in p})

    palette = {
        "Baseline France": "#5A6B7D",
        SCENARIOS["crise"]["label"]: "#C8102E",
        SCENARIOS["reprise"]["label"]: "#2A5F9E",
        SCENARIOS["tension"]["label"]: "#C4922A",
    }
    fig = go.Figure()
    for name, proba in results:
        fig.add_trace(go.Bar(
            name=name,
            x=blocs_order,
            y=[proba.get(b, 0) for b in blocs_order],
            marker_color=palette.get(name, MUTED),
            hovertemplate="%{x} · " + name + " : %{y:.1%}<extra></extra>",
        ))
    base_layout(
        fig,
        f"Scénarios vs baseline — horizon {horizon} an{'s' if horizon > 1 else ''}",
        height=380,
    )
    fig.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 1], tickformat=".0%", title=""),
        xaxis_title="",
        legend=legend_below(4),
        margin=dict(l=48, r=24, b=80, t=56),
    )
    return fig


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
