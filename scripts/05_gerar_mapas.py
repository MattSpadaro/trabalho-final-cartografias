"""
05_gerar_mapas.py
=================
Gera os 5 mapas temáticos do trabalho final em alta resolução (300 DPI).
Qualidade Cartográfica Aprimorada (Aesthetic Cartography)

Mapas produzidos:
  1. Localização geral — Bacias PCJ e Alto Tietê no Estado de SP
  2. Data Centers sobre as bacias hidrográficas
  3. Vulnerabilidade social (IVS) por setor censitário
  4. Criticidade hídrica das sub-bacias
  5. Mapa síntese / integrado (data centers + IVS + criticidade)

Saída: mapas/ (PNG e PDF)
"""

import warnings
warnings.filterwarnings("ignore")

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as pe
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
PRO     = ROOT / "dados" / "processados"
BRUTO   = ROOT / "dados" / "brutos"
MAPAS   = ROOT / "mapas"
MAPAS.mkdir(exist_ok=True)

CRS = "EPSG:31983"   # UTM 23S — metros
DPI = 300

# Paletas de Cores Aprimoradas (Dark Theme)
COR_DCS       = "#FF3366"  # Rosa neon para os Data Centers
COR_PCJ       = "#00B4D8"  # Azul claro/ciano
COR_AT        = "#0077B6"  # Azul escuro
COR_VULN_ALTA = "#E63946"
COR_VULN_BAIXA= "#A8DADC"
COR_INJUSTICA = "#FF006E"
COR_BUFFER    = "#FFD166"

# ── Helpers Cartográficos ─────────────────────────────────────────────────────
def carregar(caminho: Path) -> gpd.GeoDataFrame | None:
    if not caminho.exists():
        print(f"  [skip] {caminho.name} não encontrado")
        return None
    return gpd.read_file(caminho).to_crs(CRS)

def salvar(fig, nome: str):
    for ext in ("png", "pdf"):
        p = MAPAS / f"{nome}.{ext}"
        fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"  Salvo: {p.name}")
    plt.close(fig)

def set_extent(ax, bacias):
    """Foca o mapa estritamente na área das bacias PCJ e Alto Tietê."""
    if bacias is not None and not bacias.empty:
        minx, miny, maxx, maxy = bacias.total_bounds
        dx = maxx - minx
        dy = maxy - miny
        ax.set_xlim(minx - 0.05 * dx, maxx + 0.05 * dx)
        ax.set_ylim(miny - 0.05 * dy, maxy + 0.05 * dy)

def adicionar_basemap(ax):
    """Adiciona mapa base CartoDB DarkMatter usando contextily."""
    try:
        import contextily as ctx
        ctx.add_basemap(ax, crs=CRS, source=ctx.providers.CartoDB.DarkMatter, zoom="auto")
    except Exception as e:
        print(f"  [aviso] Falha ao baixar basemap: {e}")
        ax.set_facecolor("#1A1A2E")

def elementos_cartograficos(ax):
    """Adiciona Seta de Norte e Barra de Escala (aprox. 20km)."""
    # Norte
    x, y, arrow_length = 0.95, 0.95, 0.06
    ax.annotate('N', xy=(x, y), xytext=(x, y - arrow_length),
                arrowprops=dict(facecolor='white', width=3, headwidth=10, edgecolor='black'),
                ha='center', va='center', fontsize=14, color='white', fontweight="bold",
                xycoords='axes fraction', textcoords='axes fraction',
                path_effects=[pe.withStroke(linewidth=2, foreground="black")])
    
    # Escala (20 km = 20_000 metros)
    xmin, xmax = ax.get_xlim()
    width_m = xmax - xmin
    if width_m > 0:
        frac_20km = 20000 / width_m
        ax.plot([0.05, 0.05 + frac_20km], [0.03, 0.03], 
                transform=ax.transAxes, color="white", linewidth=4, solid_capstyle="butt",
                path_effects=[pe.withStroke(linewidth=6, foreground="black")])
        ax.plot([0.05, 0.05], [0.02, 0.04], transform=ax.transAxes, color="white", linewidth=2)
        ax.plot([0.05 + frac_20km, 0.05 + frac_20km], [0.02, 0.04], transform=ax.transAxes, color="white", linewidth=2)
        ax.text(0.05 + frac_20km/2, 0.045, "20 km", transform=ax.transAxes, color="white", fontsize=10,
                ha='center', va='bottom', fontweight="bold",
                path_effects=[pe.withStroke(linewidth=2, foreground="black")])


# ══════════════════════════════════════════════════════════════════════════════
# MAPA 1 — Localização Geral
# ══════════════════════════════════════════════════════════════════════════════
def mapa_localizacao(muni_sp, bacias, dcs):
    print("\n[Mapa 1] Localização geral...")
    fig, ax = plt.subplots(1, 1, figsize=(14, 12), facecolor="#14141C")
    ax.set_facecolor("#14141C")

    # Para a localização geral, deixamos um pouco mais amplo para ver o Estado
    if muni_sp is not None:
        muni_sp.plot(ax=ax, color="#1E1E2E", edgecolor="#2D2D44", linewidth=0.3, zorder=1)

    if bacias is not None:
        bacias[bacias["bacia_nome"].str.contains("PCJ", case=False, na=False)].plot(
            ax=ax, color=COR_PCJ, alpha=0.6, edgecolor="cyan", linewidth=1.2, zorder=2
        )
        bacias[bacias["bacia_nome"].str.contains("Tiet", case=False, na=False)].plot(
            ax=ax, color=COR_AT, alpha=0.6, edgecolor="#48CAE4", linewidth=1.2, zorder=2
        )
        # Foca nas bacias, mas com margem maior
        minx, miny, maxx, maxy = bacias.total_bounds
        dx, dy = maxx - minx, maxy - miny
        ax.set_xlim(minx - 0.2 * dx, maxx + 0.2 * dx)
        ax.set_ylim(miny - 0.2 * dy, maxy + 0.2 * dy)
        adicionar_basemap(ax)

    if dcs is not None:
        dcs.plot(ax=ax, color=COR_DCS, markersize=80, marker="o",
                 zorder=5, edgecolor="white", linewidth=1.5,
                 path_effects=[pe.withStroke(linewidth=4, foreground="black")])

    elementos_cartograficos(ax)

    # Legenda
    patches = [
        mpatches.Patch(color=COR_PCJ,  alpha=0.8, label="Bacia Hidrográfica PCJ"),
        mpatches.Patch(color=COR_AT,   alpha=0.8, label="Bacia Hidrográfica Alto Tietê"),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COR_DCS, markersize=10, 
                   markeredgecolor='white', markeredgewidth=1.5, label='Data Centers')
    ]
    ax.legend(handles=patches, loc="lower right", facecolor="#1E1E2E", edgecolor="#4A4A6A",
              labelcolor="white", fontsize=11, framealpha=0.9, shadow=True)

    ax.set_title("Localização dos Data Centers nas Bacias PCJ e Alto Tietê — SP",
                 color="white", fontsize=16, fontweight="bold", pad=20)
    ax.set_axis_off()
    _creditos(ax)
    salvar(fig, "01_localizacao_geral")


# ══════════════════════════════════════════════════════════════════════════════
# MAPA 2 — Data Centers sobre as Bacias
# ══════════════════════════════════════════════════════════════════════════════
def mapa_data_centers(bacias, dcs, setores):
    print("[Mapa 2] Data Centers × Bacias...")
    fig, ax = plt.subplots(1, 1, figsize=(14, 12), facecolor="#14141C")
    ax.set_facecolor("#14141C")

    set_extent(ax, bacias)
    adicionar_basemap(ax)

    if setores is not None:
        setores.plot(ax=ax, color="#2B2D42", edgecolor="#8D99AE", linewidth=0.1, alpha=0.3, zorder=2)

    if bacias is not None:
        bacias.plot(ax=ax, color="none", edgecolor="#00B4D8", linewidth=2.5, linestyle="-", zorder=3,
                    path_effects=[pe.withStroke(linewidth=4, foreground="#03045E")])

    if dcs is not None:
        dcs.plot(ax=ax, color=COR_DCS, markersize=100, marker="o",
                 zorder=10, edgecolor="white", linewidth=1.5,
                 path_effects=[pe.withStroke(linewidth=3, foreground="#4A0404")])
        # Rótulos para Data Centers maiores ou amostra (evitar poluição)
        for _, row in dcs.iterrows():
            nome = str(row.get("nome", row.get("name", "")))
            if "Equinix" in nome or "Ascenty" in nome or "ODATA" in nome:
                ax.annotate(
                    nome[:15], xy=(row.geometry.x, row.geometry.y),
                    xytext=(6, 6), textcoords="offset points",
                    color="white", fontsize=8, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=2.5, foreground="black")]
                )

    elementos_cartograficos(ax)

    # Legenda
    patches = [
        plt.Line2D([0], [0], color="#00B4D8", lw=2.5, label="Limite das Bacias"),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COR_DCS, markersize=10, label='Data Centers')
    ]
    ax.legend(handles=patches, loc="lower right", facecolor="#1E1E2E", edgecolor="none", labelcolor="white", fontsize=11)

    ax.set_title("Distribuição Espacial de Data Centers — PCJ e Alto Tietê",
                 color="white", fontsize=16, fontweight="bold", pad=20)
    ax.set_axis_off()
    _creditos(ax)
    salvar(fig, "02_data_centers_bacias")


# ══════════════════════════════════════════════════════════════════════════════
# MAPA 3 — Vulnerabilidade Social (IVS)
# ══════════════════════════════════════════════════════════════════════════════
def mapa_ivs(bacias, setores, dcs):
    print("[Mapa 3] IVS por setor censitário...")
    COL_IVS = "ivs_geral"

    fig, ax = plt.subplots(1, 1, figsize=(14, 12), facecolor="#14141C")
    ax.set_facecolor("#14141C")

    set_extent(ax, bacias)
    adicionar_basemap(ax)

    if setores is not None and COL_IVS in setores.columns:
        setores.plot(
            ax=ax, column=COL_IVS, cmap="magma",
            edgecolor="none", linewidth=0, alpha=0.75, zorder=2,
            legend=True,
            legend_kwds={"label": "Índice de Vulnerabilidade Social (IVS)",
                         "shrink": 0.5, "orientation": "horizontal", "pad": 0.02}
        )
    elif setores is not None:
        print(f"  [aviso] Coluna IVS '{COL_IVS}' não encontrada. Aplicando estilo de densidade neutro.")
        setores.plot(ax=ax, color="#E07A5F", edgecolor="#F4F1DE", linewidth=0.15, alpha=0.5, zorder=2)

    if dcs is not None:
        dcs.plot(ax=ax, color="#00FFCC", markersize=120, marker="*",
                 zorder=10, edgecolor="black", linewidth=1, label="Data Centers")

    elementos_cartograficos(ax)
    
    if COL_IVS not in setores.columns:
        patches = [
            mpatches.Patch(color="#E07A5F", alpha=0.5, label="Setores Censitários (IVS Indisponível)"),
            plt.Line2D([0], [0], marker='*', color='w', markerfacecolor="#00FFCC", markeredgecolor='k', markersize=12, label='Data Centers')
        ]
        ax.legend(handles=patches, loc="lower right", facecolor="#1E1E2E", edgecolor="none", labelcolor="white", fontsize=11)

    ax.set_title("Vulnerabilidade Social e Localização dos Data Centers",
                 color="white", fontsize=16, fontweight="bold", pad=20)
    ax.set_axis_off()
    _creditos(ax)
    salvar(fig, "03_ivs_vulnerabilidade")


# ══════════════════════════════════════════════════════════════════════════════
# MAPA 4 — Criticidade Hídrica
# ══════════════════════════════════════════════════════════════════════════════
def mapa_hidrico(bacias, dcs):
    print("[Mapa 4] Criticidade hídrica...")
    fig, ax = plt.subplots(1, 1, figsize=(14, 12), facecolor="#14141C")
    ax.set_facecolor("#14141C")

    set_extent(ax, bacias)
    adicionar_basemap(ax)

    COL_CRIT = "criticidade"

    if bacias is not None:
        if COL_CRIT in bacias.columns:
            bacias.plot(ax=ax, column=COL_CRIT, cmap="RdYlBu_r",
                        edgecolor="white", linewidth=1.5, alpha=0.6, zorder=2,
                        legend=True,
                        legend_kwds={"label": "Criticidade Hídrica", "shrink": 0.5})
        else:
            print(f"  [aviso] Coluna '{COL_CRIT}' não encontrada. Exibindo paleta padrão.")
            bacias.plot(ax=ax, color="#0077B6", edgecolor="#90E0EF", linewidth=2, alpha=0.4, zorder=2)

    if dcs is not None:
        dcs.plot(ax=ax, color="#FF9F1C", markersize=90, marker="o",
                 zorder=10, edgecolor="white", linewidth=1.5,
                 path_effects=[pe.withStroke(linewidth=3, foreground="black")])

    elementos_cartograficos(ax)
    
    if COL_CRIT not in bacias.columns:
        patches = [
            mpatches.Patch(color="#0077B6", alpha=0.4, label="Área da Bacia Hidrográfica"),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor="#FF9F1C", markeredgecolor='w', markersize=10, label='Data Centers')
        ]
        ax.legend(handles=patches, loc="lower right", facecolor="#1E1E2E", edgecolor="none", labelcolor="white", fontsize=11)

    ax.set_title("Criticidade Hídrica e Pressão Estrutural nas Bacias PCJ e Alto Tietê",
                 color="white", fontsize=16, fontweight="bold", pad=20)
    ax.set_axis_off()
    _creditos(ax)
    salvar(fig, "04_criticidade_hidrica")


# ══════════════════════════════════════════════════════════════════════════════
# MAPA 5 — Síntese / Injustiça Ambiental
# ══════════════════════════════════════════════════════════════════════════════
def mapa_sintese(bacias, setores, dcs, zonas_ia, buffers):
    print("[Mapa 5] Mapa síntese — injustiça ambiental...")
    fig, ax = plt.subplots(1, 1, figsize=(16, 14), facecolor="#14141C")
    ax.set_facecolor("#14141C")

    set_extent(ax, bacias)
    adicionar_basemap(ax)

    # Bacias
    if bacias is not None:
        bacias.plot(ax=ax, color="none", edgecolor="#00B4D8", linewidth=2.5, linestyle="-", zorder=3, alpha=0.8)

    # Setores de Injustiça Ambiental
    if zonas_ia is not None:
        zonas_ia.plot(ax=ax, color=COR_INJUSTICA, edgecolor="none", alpha=0.75, zorder=4)

    # Buffers de 10 km
    if buffers is not None:
        buffers.plot(ax=ax, color="none", edgecolor=COR_BUFFER, linewidth=2, linestyle="--", alpha=0.9, zorder=5,
                     path_effects=[pe.withStroke(linewidth=3, foreground="black")])

    # Data Centers
    if dcs is not None:
        dcs.plot(ax=ax, color="white", markersize=120, marker="o",
                 zorder=15, edgecolor="black", linewidth=2,
                 path_effects=[pe.withStroke(linewidth=4, foreground=COR_DCS)])

    elementos_cartograficos(ax)

    # Legenda Complexa
    patches = [
        mpatches.Patch(color=COR_INJUSTICA, alpha=0.8, label="Área de Injustiça Ambiental (Alta Vulnerabilidade)"),
        plt.Line2D([0], [0], color=COR_BUFFER, lw=2, linestyle="--", label="Zona de Influência Direta (Raio 10 km)"),
        plt.Line2D([0], [0], color="#00B4D8", lw=2.5, label="Limite das Bacias Hídricas"),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor="white", markeredgecolor='black', markersize=11, label='Data Center')
    ]
    ax.legend(handles=patches, loc="lower right", facecolor="#1A1A2E", edgecolor="#4A5568",
              labelcolor="white", fontsize=12, framealpha=0.95, shadow=True)

    ax.set_title(
        "DIAGNÓSTICO SOCIOAMBIENTAL INTEGRADO\n"
        "Data Centers, Recursos Hídricos e Potencial Injustiça Ambiental — SP",
        color="white", fontsize=18, fontweight="bold", pad=20
    )
    ax.set_axis_off()
    _creditos(ax)
    salvar(fig, "05_sintese_injustica_ambiental")


# ── Créditos ──────────────────────────────────────────────────────────────────
def _creditos(ax):
    ax.annotate(
        "Fontes de Dados: Censo IBGE 2022 | Base SNIRH ANA / DAEE-SP | Base IVS IPEA | CGI.br / Cetic.br | PeeringDB\n"
        "Projeção Cartográfica: SIRGAS 2000 / UTM Zona 23S (EPSG:31983) | Elaboração Própria (2026)",
        xy=(0.01, 0.01), xycoords="axes fraction",
        fontsize=8, color="#8D99AE", fontweight="bold",
        ha="left", va="bottom",
        path_effects=[pe.withStroke(linewidth=2, foreground="black")]
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("FASE 3 — Geração de Mapas Temáticos (High-Res Cartography)")
    print("=" * 60)

    muni_sp  = carregar(BRUTO / "censo_2022" / "municipios_sp.gpkg")
    bacias   = carregar(PRO / "dcs_por_bacia.gpkg")
    dcs      = carregar(PRO / "data_centers.gpkg")
    setores  = carregar(PRO / "setores_com_ivs_bacias.gpkg")
    zonas_ia = carregar(PRO / "zonas_injustica_ambiental.gpkg")
    buffers  = carregar(PRO / "buffers_dcs.gpkg")

    buf_10 = None
    if buffers is not None and "raio_m" in buffers.columns:
        buf_10 = buffers[buffers["raio_m"] == 10_000]

    mapa_localizacao(muni_sp, bacias, dcs)
    mapa_data_centers(bacias, dcs, setores)
    mapa_ivs(bacias, setores, dcs)
    mapa_hidrico(bacias, dcs)
    mapa_sintese(bacias, setores, dcs, zonas_ia, buf_10)

    print(f"\n{'='*60}")
    print(f"Mapas de alta resolução salvos em: {MAPAS}")
    print("Abra os PNGs para revisão visual antes da entrega final.")

if __name__ == "__main__":
    main()
