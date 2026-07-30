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
from dash import Input, Output, State, dcc, html, no_update

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
    top = 78 if subtitle else 58
    bottom = 88 if bottom_legend else 48
    fig.update_layout(
        title=dict(
            text=text,
            font=dict(family=FONT_BRAND, size=18, color=INK),
            x=0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(t=2, b=12),
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
        return layout_predict()
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
        margin=dict(l=56, r=24, t=72, b=56),
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
        margin=dict(l=56, r=24, t=72, b=56),
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
        margin=dict(l=64, r=24, t=58, b=56),
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
        margin=dict(l=130, r=56, t=70, b=48),
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
        margin=dict(l=8, r=8, t=58, b=72),
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
        margin=dict(l=140, r=48, t=70, b=48),
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
        margin=dict(l=24, r=24, t=70, b=40),
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
        margin=dict(l=56, r=40, t=64, b=96),
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
                             margin=dict(l=64, r=40, t=72, b=56))
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
                              margin=dict(l=140, r=40, t=64, b=48))
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
def layout_predict():
    return html.Div([
        html.Div(className="ea-panel mb-3", children=[
            html.H2("Prédiction what-if", className="ea-section-title"),
            html.P(
                "Indicateurs N−1 et bloc précédent. Prédiction indicative — limites du modèle assumées.",
                className="ea-section-lead",
            ),
            dbc.Row([
                dbc.Col(_num_input("p-chom", "Chômage N−1 (%)", 8.5), md=4, lg=2),
                dbc.Col(_num_input("p-delta", "Δ chômage 5 ans", -0.5), md=4, lg=2),
                dbc.Col(_num_input("p-emploi", "Emploi / 1 000 hab.", 350), md=4, lg=2),
                dbc.Col(_num_input("p-crois", "Croissance emploi (%)", 1.0), md=4, lg=2),
                dbc.Col(_num_input("p-ent", "Créations / 10k", 25.0), md=4, lg=2),
                dbc.Col([
                    html.Label("Bloc précédent", className="ea-label"),
                    dcc.Dropdown(
                        id="p-prec",
                        options=[{"label": f"{b} — {BLOCS_LABELS[b]}", "value": b} for b in BLOCS],
                        value="CEN", clearable=False,
                    ),
                ], md=4, lg=2),
            ], className="g-3 mb-3"),
            html.Button("Lancer la prédiction", id="p-btn", n_clicks=0, className="ea-btn btn btn-dark"),
        ]),
        html.Div(id="p-winner"),
        dcc.Loading(dcc.Graph(id="p-graph", config={"displayModeBar": False}), type="dot"),
    ])


def _num_input(id_, label, val):
    return html.Div([
        html.Label(label, className="ea-label"),
        dbc.Input(id=id_, type="number", value=val, step="any"),
    ])


@app.callback(
    Output("p-graph", "figure"),
    Output("p-winner", "children"),
    Input("p-btn", "n_clicks"),
    State("p-chom", "value"),
    State("p-delta", "value"),
    State("p-emploi", "value"),
    State("p-crois", "value"),
    State("p-ent", "value"),
    State("p-prec", "value"),
    prevent_initial_call=False,
)
def predict_fig(n, chom, delta, emploi, crois, ent, prec):
    if not n:
        return empty_fig("Saisissez des valeurs puis lancez la prédiction"), html.Div()
    payload = {
        "taux_chomage_n1": chom,
        "delta_chomage_5a": delta,
        "emploi_pour_1000hab": emploi,
        "croissance_emploi_5a_pct": crois,
        "creations_entreprises_n1": ent,
        "bloc_gagnant_precedent": prec,
    }
    code, body = api_post("/predict", payload)
    if code >= 400:
        return empty_fig(f"Erreur API {code} : {body.get('detail', body)}"), html.Div()
    proba = body.get("probabilites") or {}
    if not proba:
        return empty_fig("Pas de probabilités"), html.Div()

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
    base_layout(fig, "Probabilités de bloc en tête", height=420)
    fig.update_layout(
        xaxis=dict(range=[0, 1], tickvals=[0, 0.25, 0.5, 0.75, 1],
                   ticktext=["0 %", "25 %", "50 %", "75 %", "100 %"], title=""),
        yaxis_title="",
        margin=dict(l=72, r=40, t=64, b=48),
    )
    fig.add_vline(x=0.5, line_dash="dash", line_color="rgba(11,31,51,0.25)")

    winner_box = html.Div(className="pred-winner", children=[
        html.Div("Bloc prédit", className="ea-metric-label"),
        html.Div(
            f"{winner} — {BLOCS_LABELS.get(winner, winner)} ({win_p:.0%})",
            className="ea-metric-value",
            style={"fontSize": "1.55rem"},
        ),
        html.P(
            "Prédiction indicative. Limites : scrutin 2022 atypique — "
            "la référence reste l'accuracy en validation croisée groupée.",
            className="ea-metric-sub mb-0 mt-2",
        ),
    ])
    return fig, winner_box


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
