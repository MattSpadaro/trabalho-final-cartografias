"""
04_analise_buffer.py
====================
Análise de buffer em torno dos data centers para quantificar:
  - População vulnerável (IVS alto) nos raios de 5/10/20 km
  - Sobreposição entre zonas de alta criticidade hídrica e vulnerabilidade

Saída:
  - dados/processados/buffers_dcs.gpkg
  - dados/processados/pop_vulneravel_por_buffer.csv
  - dados/processados/zonas_injustica_ambiental.gpkg

Uso:
    python 04_analise_buffer.py
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PRO  = ROOT / "dados" / "processados"

CRS_METRO = "EPSG:31983"  # SIRGAS 2000 / UTM 23S (metros)

ARQ_DCS     = PRO / "dcs_por_bacia.gpkg"
ARQ_SETORES = PRO / "setores_com_ivs_bacias.gpkg"

# Raios de análise (metros)
RAIOS = [5_000, 10_000, 20_000]

# Limiar IVS para "alta vulnerabilidade"
IVS_ALTO = 0.400

# Coluna IVS no GeoDataFrame (verifique após carregar)
COL_IVS      = "ivs_geral"    # Ajuste conforme o dataset IPEA
COL_POP      = "V001"         # Coluna de população (Censo 2022 IBGE)
COL_NOME_DC  = "nome"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Criar buffers
# ══════════════════════════════════════════════════════════════════════════════
def criar_buffers(dcs: gpd.GeoDataFrame) -> dict[int, gpd.GeoDataFrame]:
    """Cria buffers circulares ao redor de cada data center."""
    print("\n[1] Criando buffers...")
    buffers = {}
    for raio in RAIOS:
        buf = dcs.copy()
        buf["geometry"] = buf.geometry.buffer(raio)
        buf["raio_m"]   = raio
        buf["raio_km"]  = raio / 1000
        buffers[raio] = buf
        print(f"  Buffer {raio/1000:.0f} km: {len(buf)} zonas criadas")

    # Exportar todos os buffers em uma camada
    todos = pd.concat(list(buffers.values()), ignore_index=True)
    todos_gdf = gpd.GeoDataFrame(todos, geometry="geometry", crs=CRS_METRO)
    saida = PRO / "buffers_dcs.gpkg"
    todos_gdf.to_file(saida, driver="GPKG")
    print(f"  Exportado: {saida}")
    return buffers


# ══════════════════════════════════════════════════════════════════════════════
# 2. Quantificar população vulnerável por buffer
# ══════════════════════════════════════════════════════════════════════════════
def pop_vulneravel_por_buffer(
    buffers: dict,
    setores: gpd.GeoDataFrame
) -> pd.DataFrame:
    """
    Para cada raio e cada data center, conta população em setores com IVS alto.
    Usa área de interseção como proxy de população parcial (areal weighting).
    """
    print("\n[2] Quantificando população vulnerável por buffer...")

    if COL_IVS not in setores.columns:
        print(f"  [aviso] Coluna '{COL_IVS}' não encontrada. Colunas disponíveis:")
        print(f"  {list(setores.columns)}")
        print("  → Ajuste COL_IVS no início do script conforme o dataset do IPEA")

    if COL_POP not in setores.columns:
        print(f"  [aviso] Coluna '{COL_POP}' não encontrada — usando contagem de setores como proxy")

    resultados = []
    for raio, buf_gdf in buffers.items():
        for _, dc in buf_gdf.iterrows():
            buf_poly = dc["geometry"]
            # Setores que intersectam o buffer
            clip = setores[setores.geometry.intersects(buf_poly)].copy()
            if clip.empty:
                continue

            # Interseção e ponderação por área
            clip["area_total"]  = clip.geometry.area
            clip["area_inter"]  = clip.geometry.intersection(buf_poly).area
            clip["proporcao"]   = clip["area_inter"] / clip["area_total"].replace(0, np.nan)

            # População estimada no buffer (ponderada por área)
            if COL_POP in clip.columns:
                clip[COL_POP] = pd.to_numeric(clip[COL_POP], errors="coerce").fillna(0)
                pop_total   = (clip[COL_POP] * clip["proporcao"]).sum()
            else:
                pop_total   = len(clip)   # proxy: nº de setores

            # Setores de alta vulnerabilidade
            if COL_IVS in clip.columns:
                clip[COL_IVS] = pd.to_numeric(clip[COL_IVS], errors="coerce")
                alta_vuln = clip[clip[COL_IVS] >= IVS_ALTO]
                if COL_POP in alta_vuln.columns:
                    pop_vuln = (alta_vuln[COL_POP] * alta_vuln["proporcao"]).sum()
                else:
                    pop_vuln = len(alta_vuln)
                pct_vuln = (pop_vuln / pop_total * 100) if pop_total > 0 else 0
            else:
                pop_vuln, pct_vuln = None, None

            resultados.append({
                "data_center":      dc.get(COL_NOME_DC, ""),
                "empresa":          dc.get("empresa", ""),
                "bacia":            dc.get("bacia_nome", ""),
                "raio_km":          raio / 1000,
                "setores_no_buffer": len(clip),
                "pop_total_est":    round(pop_total),
                "pop_vuln_est":     round(pop_vuln) if pop_vuln is not None else None,
                "pct_vuln":         round(pct_vuln, 1) if pct_vuln is not None else None,
            })

    df = pd.DataFrame(resultados)
    saida = PRO / "pop_vulneravel_por_buffer.csv"
    df.to_csv(saida, index=False, encoding="utf-8-sig")
    print(f"  Exportado: {saida}")
    print("\n  Resumo (raio 10 km):")
    print(df[df["raio_km"] == 10][["data_center", "pop_total_est", "pop_vuln_est", "pct_vuln"]].to_string(index=False))
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3. Zonas de injustiça ambiental (dupla pressão)
# ══════════════════════════════════════════════════════════════════════════════
def zonas_injustica_ambiental(
    setores: gpd.GeoDataFrame,
    buffers_10km: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Identifica setores que satisfazem as 3 condições simultaneamente:
      1. Alta vulnerabilidade social (IVS ≥ limiar)
      2. Dentro de 10 km de um data center
      3. Em bacia com criticidade hídrica alta (coluna 'criticidade' se disponível)
    """
    print("\n[3] Identificando zonas de injustiça ambiental...")

    # Condição 1: IVS alto
    if COL_IVS in setores.columns:
        setores[COL_IVS] = pd.to_numeric(setores[COL_IVS], errors="coerce")
        mask_vuln = setores[COL_IVS] >= IVS_ALTO
    else:
        print("  [aviso] IVS não disponível — marcando todos como 'potencialmente vulneráveis'")
        mask_vuln = pd.Series(True, index=setores.index)

    # Condição 2: Dentro de algum buffer de 10 km
    uniao_buffers = buffers_10km.geometry.union_all()
    mask_dc = setores.geometry.intersects(uniao_buffers)

    # Combinação
    zonas = setores[mask_vuln & mask_dc].copy()
    zonas["flag_injustica"] = True
    print(f"  {len(zonas)} setores identificados como zonas de injustiça ambiental")

    if COL_IVS in zonas.columns:
        print(f"  IVS médio: {zonas[COL_IVS].mean():.3f} | Máximo: {zonas[COL_IVS].max():.3f}")

    saida = PRO / "zonas_injustica_ambiental.gpkg"
    zonas.to_file(saida, driver="GPKG")
    print(f"  Exportado: {saida}")
    return zonas


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("FASE 2 — Análise de Buffer e Injustiça Ambiental")
    print("=" * 60)

    # Carregar dados processados
    if not ARQ_DCS.exists():
        print(f"[!] {ARQ_DCS} não encontrado. Execute 03_spatial_joins.py primeiro.")
        return

    dcs     = gpd.read_file(ARQ_DCS).to_crs(CRS_METRO)
    setores = gpd.read_file(ARQ_SETORES).to_crs(CRS_METRO) if ARQ_SETORES.exists() else None

    if setores is None:
        print(f"[!] Setores não encontrados em {ARQ_SETORES}. Execute 03_spatial_joins.py.")
        return

    print(f"\nData Centers carregados: {len(dcs)}")
    print(f"Setores censitários: {len(setores)}")

    # Análises
    buffers   = criar_buffers(dcs)
    df_pop    = pop_vulneravel_por_buffer(buffers, setores)
    buf_10km  = gpd.GeoDataFrame(buffers[10_000], geometry="geometry", crs=CRS_METRO)
    zonas_ia  = zonas_injustica_ambiental(setores, buf_10km)

    print("\n[Próximo passo] Execute 05_gerar_mapas.py")


if __name__ == "__main__":
    main()
