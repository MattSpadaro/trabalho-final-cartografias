"""
02_georreferenciar_dcs.py
=========================
Geocodifica os data centers listados manualmente, valida via PeeringDB
e exporta o shapefile de pontos para uso no QGIS e nos scripts seguintes.

Fluxo:
  1. Lê data_centers_bruto.csv (preenchido manualmente)
  2. Complementa com dados da API PeeringDB (endereços, capacidade)
  3. Geocodifica via Nominatim (OSM) — sem precisar de API key
  4. Valida coordenadas no Google Earth (abre URL KML)
  5. Exporta data_centers.gpkg e data_centers.csv finais

Uso:
    pip install geopandas pandas requests geopy tqdm
    python 02_georreferenciar_dcs.py
"""

import sys
import io
# Forcar UTF-8 no stdout/stderr do Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import time
import requests
import pandas as pd
import geopandas as gpd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm import tqdm

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
DIR_DC  = ROOT / "dados" / "brutos" / "data_centers"
DIR_PRO = ROOT / "dados" / "processados"
DIR_PRO.mkdir(parents=True, exist_ok=True)

ARQUIVO_BRUTO  = DIR_DC / "data_centers_bruto.csv"
ARQUIVO_FINAL  = DIR_PRO / "data_centers.gpkg"
CSV_FINAL      = DIR_PRO / "data_centers.csv"

# CRS de saída — SIRGAS 2000 geográfico
CRS_SAIDA = "EPSG:4674"

# ── PeeringDB ────────────────────────────────────────────────────────────────
PEERINGDB_BASE = "https://www.peeringdb.com/api"

# Facilidades registradas em SP (busca por cidade/país)
PEERINGDB_PARAMS = {
    "country": "BR",
    "state": "SP",
    "depth": 1,
}


def buscar_peeringdb() -> pd.DataFrame:
    """Busca instalações de data centers no PeeringDB (SP, BR)."""
    print("\n[PeeringDB] Buscando facilidades em SP...")
    url = f"{PEERINGDB_BASE}/fac"
    try:
        resp = requests.get(url, params=PEERINGDB_PARAMS, timeout=30)
        resp.raise_for_status()
        dados = resp.json().get("data", [])
        registros = []
        for d in dados:
            registros.append({
                "nome":         d.get("name", ""),
                "empresa":      d.get("org", {}).get("name", "") if isinstance(d.get("org"), dict) else "",
                "endereco":     d.get("address1", ""),
                "cidade":       d.get("city", ""),
                "estado":       d.get("state", ""),
                "cep":          d.get("zipcode", ""),
                "pais":         d.get("country", ""),
                "website":      d.get("website", ""),
                "peeringdb_id": d.get("id", ""),
                "lat":          d.get("latitude", None),
                "lon":          d.get("longitude", None),
                "fonte":        "PeeringDB",
            })
        df = pd.DataFrame(registros)
        print(f"  Encontrados: {len(df)} registros")
        arq_pdb = DIR_DC / "peeringdb_sp.csv"
        df.to_csv(arq_pdb, index=False, encoding="utf-8-sig")
        print(f"  Salvo: {arq_pdb}")
        return df
    except Exception as e:
        print(f"  [aviso] PeeringDB indisponível: {e}")
        return pd.DataFrame()


# ── Geocodificação via Nominatim (OSM) ────────────────────────────────────────
def geocodificar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Geocodifica linhas sem lat/lon usando Nominatim (OSM).
    Respeita rate limit de 1 req/s.
    """
    print("\n[Geocodificação] Nominatim (OSM)...")
    geolocator = Nominatim(user_agent="trabalho_final_dc_bacias_sp")
    geocode    = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

    sem_coords = df["lat"].isna() | (df["lat"] == "")

    for idx in tqdm(df[sem_coords].index, desc="Geocodificando"):
        row = df.loc[idx]
        # Monta query progressiva: endereço → cidade → CEP
        queries = [
            f"{row.get('endereco', '')}, {row.get('cidade', '')}, SP, Brasil",
            f"{row.get('cidade', '')}, SP, Brasil",
        ]
        for q in queries:
            if not q.strip(", "):
                continue
            try:
                loc = geocode(q)
                if loc:
                    df.at[idx, "lat"] = loc.latitude
                    df.at[idx, "lon"] = loc.longitude
                    df.at[idx, "geocod_query"] = q
                    df.at[idx, "geocod_fonte"] = "Nominatim"
                    break
            except Exception:
                time.sleep(1)

    total_coords = df["lat"].notna().sum()
    print(f"  Geocodificados: {total_coords}/{len(df)} registros")
    return df


# ── Conversão para GeoDataFrame ───────────────────────────────────────────────
def para_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Converte DataFrame com lat/lon para GeoDataFrame de pontos."""
    df_geo = df.dropna(subset=["lat", "lon"]).copy()
    gdf = gpd.GeoDataFrame(
        df_geo,
        geometry=gpd.points_from_xy(df_geo["lon"], df_geo["lat"]),
        crs="EPSG:4326",
    ).to_crs(CRS_SAIDA)
    return gdf


# ── Exportar KML para validação no Google Earth ───────────────────────────────
def exportar_kml(gdf: gpd.GeoDataFrame, destino: Path) -> None:
    """Exporta KML para validação visual no Google Earth."""
    try:
        gdf_wgs = gdf.to_crs("EPSG:4326")
        gdf_wgs.to_file(destino, driver="KML")
        print(f"  KML exportado: {destino}")
        print("  → Abra no Google Earth para auditar cada ponto (torres de resfriamento no telhado)")
    except Exception as e:
        print(f"  [aviso] Exportação KML falhou: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("FASE 1 — Geocodificação dos Data Centers")
    print("=" * 60)

    # 1. PeeringDB
    df_pdb = buscar_peeringdb()

    # 2. CSV preenchido manualmente (dados já conhecidos das âncoras)
    if ARQUIVO_BRUTO.exists():
        print(f"\n[CSV Manual] Carregando {ARQUIVO_BRUTO.name}...")
        df_manual = pd.read_csv(ARQUIVO_BRUTO, encoding="utf-8-sig", dtype=str)
        # Normaliza colunas mínimas
        for col in ["lat", "lon", "geocod_query", "geocod_fonte"]:
            if col not in df_manual.columns:
                df_manual[col] = None
        print(f"  {len(df_manual)} registros carregados.")
    else:
        print(f"\n[aviso] {ARQUIVO_BRUTO} não encontrado.")
        print("  → Crie o arquivo CSV manualmente. Um template foi gerado em:")
        template = DIR_DC / "data_centers_bruto_TEMPLATE.csv"
        pd.DataFrame(columns=[
            "nome", "empresa", "endereco", "cidade", "estado",
            "cep", "lat", "lon", "capacidade_mw", "tipo_resfriamento",
            "ano_inauguracao", "fonte", "notas"
        ]).to_csv(template, index=False, encoding="utf-8-sig")
        print(f"  {template}")
        df_manual = pd.DataFrame()

    # 3. Concatenar PeeringDB + manual (removendo duplicatas por nome)
    frames = [f for f in [df_pdb, df_manual] if not f.empty]
    if not frames:
        print("\n[!] Nenhum dado disponível. Preencha o CSV manualmente e rode novamente.")
        return

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["nome"], keep="last").reset_index(drop=True)
    print(f"\n[Combinado] Total: {len(df)} data centers")

    # 4. Geocodificar os que não têm coordenadas
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = geocodificar(df)

    # 5. Converter para GeoDataFrame e exportar
    gdf = para_geodataframe(df)
    print(f"\n[Export] GeoDataFrame com {len(gdf)} pontos geocodificados")

    gdf.to_file(ARQUIVO_FINAL, driver="GPKG")
    print(f"  GeoPackage: {ARQUIVO_FINAL}")

    # Salva CSV sem geometria para inspeção fácil
    df_out = df.drop(columns=["geometry"], errors="ignore")
    df_out.to_csv(CSV_FINAL, index=False, encoding="utf-8-sig")
    print(f"  CSV: {CSV_FINAL}")

    # KML para validação no Google Earth
    exportar_kml(gdf, DIR_DC / "data_centers_validacao.kml")

    print("\n[Próximo passo]")
    print("  1. Abra data_centers_validacao.kml no Google Earth Pro")
    print("  2. Verifique se cada ponto corresponde a um edifício com chillers/torres de resfriamento")
    print("  3. Corrija coordenadas no CSV e rode este script novamente")
    print("  4. Rode 03_spatial_joins.py")


if __name__ == "__main__":
    main()
