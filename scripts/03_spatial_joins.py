"""
03_spatial_joins.py
===================
Cruzamentos geoespaciais entre:
  - Data centers geocodificados
  - Bacias hidrográficas (PCJ / Alto Tietê)
  - Setores censitários com IVS

Saída:
  - dados/processados/dcs_por_bacia.gpkg
  - dados/processados/setores_por_bacia.gpkg
  - dados/processados/setores_com_ivs_bacias.gpkg

Uso:
    python 03_spatial_joins.py
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
BRUTO      = ROOT / "dados" / "brutos"
PRO        = ROOT / "dados" / "processados"
PRO.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:31983"   # SIRGAS 2000 / UTM zona 23S — metros, ideal para SP

# Arquivos de entrada
ARQ_DCS     = PRO / "data_centers.gpkg"
ARQ_BACIAS  = BRUTO / "bacias" / "ugrhi_sp" / "LimiteUGRHIPolygon.shp"
ARQ_SETORES = BRUTO / "censo_2022" / "setores_sp_geobr.gpkg"     # geobr 68k setores SP
ARQ_IVS     = BRUTO / "ivs" / "UDHs_RM_Todas.shp"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Carregar camadas
# ══════════════════════════════════════════════════════════════════════════════
def carregar(caminho: Path, nome: str) -> gpd.GeoDataFrame | None:
    if not caminho.exists():
        print(f"  [aviso] Arquivo não encontrado: {caminho}")
        print(f"  → Execute 01_download_dados.py primeiro")
        return None
    print(f"  Carregando {nome}...")
    gdf = gpd.read_file(caminho)
    return gdf.to_crs(CRS)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Filtrar bacias PCJ e Alto Tietê
# ══════════════════════════════════════════════════════════════════════════════
def filtrar_bacias(bacias: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Filtra as UGRHIs PCJ (05) e Alto Tietê (06) do shapefile geral.
    Adapte os nomes das colunas conforme o shapefile que você baixou.
    """
    print("  Filtrando bacias PCJ e Alto Tietê...")
    # Tenta colunas comuns dos shapefiles DAEE/DataGEO
    for col in ["UGRHI", "ugrhi", "NOME_UGRHI", "nome", "Nome"]:
        if col in bacias.columns:
            pcj  = bacias[bacias[col].astype(str).str.contains("PIRACICABA|PCJ|05", case=False, na=False)]
            at   = bacias[bacias[col].astype(str).str.contains("Tiet|06", case=False, na=False)]
            if len(pcj) + len(at) > 0:
                resultado = pd.concat([pcj, at])
                resultado["bacia_nome"] = resultado[col]
                print(f"  PCJ: {len(pcj)} polígono(s) | Alto Tietê: {len(at)} polígono(s)")
                return resultado
    # Se não encontrar, retorna tudo (para inspeção)
    print("  [aviso] Não foi possível filtrar por nome de bacia. Usando todas as bacias.")
    return bacias


# ══════════════════════════════════════════════════════════════════════════════
# 3. Spatial Join — Data Centers × Bacias
# ══════════════════════════════════════════════════════════════════════════════
def join_dcs_bacias(dcs: gpd.GeoDataFrame, bacias: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Vincula cada data center à bacia hidrográfica em que se encontra."""
    print("\n[3] Spatial Join: Data Centers × Bacias...")
    resultado = gpd.sjoin(dcs, bacias[["bacia_nome", "geometry"]], how="left", predicate="within")
    n_sem_bacia = resultado["bacia_nome"].isna().sum()
    if n_sem_bacia:
        print(f"  [aviso] {n_sem_bacia} DC(s) fora das bacias filtradas (podem estar em outras UGRHIs)")
    saida = PRO / "dcs_por_bacia.gpkg"
    resultado.to_file(saida, driver="GPKG")
    print(f"  Salvo: {saida}")
    # Resumo
    print("\n  Distribuição por bacia:")
    print(resultado.groupby("bacia_nome", dropna=False)["nome"].count().to_string())
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# 4. Spatial Join — Setores Censitários × Bacias
# ══════════════════════════════════════════════════════════════════════════════
def join_setores_bacias(setores: gpd.GeoDataFrame, bacias: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filtra os setores censitários que intersectam as bacias PCJ/AT."""
    print("\n[4] Spatial Join: Setores × Bacias...")
    resultado = gpd.sjoin(setores, bacias[["bacia_nome", "geometry"]], how="inner", predicate="intersects")
    resultado = resultado[~resultado.index.duplicated(keep="first")]
    saida = PRO / "setores_por_bacia.gpkg"
    resultado.to_file(saida, driver="GPKG")
    print(f"  {len(resultado)} setores censitários nas bacias | Salvo: {saida}")
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# 5. Vincular IVS aos setores (se disponível)
# ══════════════════════════════════════════════════════════════════════════════
def vincular_ivs(setores: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Vincula dados de IVS (IPEA) aos setores censitários via spatial join."""
    if not ARQ_IVS.exists():
        print("\n[5] IVS não disponível ainda — execute após baixar os dados do IPEA")
        print("    Acesse: https://ivs.ipea.gov.br → Download → Shapefile")
        return setores

    print("\n[5] Vinculando IVS aos setores...")
    ivs = gpd.read_file(ARQ_IVS).to_crs(CRS)
    # O IVS usa Unidades de Desenvolvimento Humano (UDH), não setores censitários
    # Fazemos spatial join por centroide do setor
    setores_c = setores.copy()
    setores_c["geometry"] = setores_c.geometry.centroid
    for col in ["index_right", "index_left"]:
        if col in ivs.columns:
            ivs = ivs.drop(columns=[col])
        if col in setores_c.columns:
            setores_c = setores_c.drop(columns=[col])
    joined = gpd.sjoin(setores_c, ivs, how="left", predicate="within")
    # Coloca a geometria original de volta
    joined["geometry"] = setores.geometry
    joined = gpd.GeoDataFrame(joined, geometry="geometry", crs=CRS)
    saida = PRO / "setores_com_ivs_bacias.gpkg"
    joined.to_file(saida, driver="GPKG")
    print(f"  Salvo: {saida}")
    return joined


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("FASE 2 — Spatial Joins")
    print("=" * 60)

    dcs     = carregar(ARQ_DCS,     "Data Centers")
    bacias  = carregar(ARQ_BACIAS,  "Bacias Hidrográficas")
    setores = carregar(ARQ_SETORES, "Setores Censitários SP")

    if bacias is not None:
        bacias = filtrar_bacias(bacias)

    if dcs is not None and bacias is not None:
        dcs_bacias = join_dcs_bacias(dcs, bacias)

    if setores is not None and bacias is not None:
        setores_bacias = join_setores_bacias(setores, bacias)
        vincular_ivs(setores_bacias)

    print("\n[Próximo passo] Execute 04_analise_buffer.py")


if __name__ == "__main__":
    main()
