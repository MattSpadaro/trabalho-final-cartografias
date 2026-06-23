# -*- coding: utf-8 -*-
"""
01_download_dados.py
====================
Download em lote de todas as bases de dados geoespaciais do projeto.

Fontes:
  - geobr: municipios SP (IBGE 2022)
  - IBGE FTP direto: setores censitarios SP 2022
  - ANA / DataGEO: UGRHIs e balanco hidrico

Uso:
    pip install geobr geopandas requests tqdm
    python 01_download_dados.py
"""

import sys
import io
import zipfile
import requests
from pathlib import Path
from tqdm import tqdm

# Forcar UTF-8 no stdout para evitar UnicodeEncodeError no Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Diretorios ────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
BRUTO      = ROOT / "dados" / "brutos"
DIR_BACIAS = BRUTO / "bacias"
DIR_CENSO  = BRUTO / "censo_2022"
DIR_IVS    = BRUTO / "ivs"

# ── Helpers ───────────────────────────────────────────────────────────────────
def baixar_arquivo(url: str, destino: Path, desc: str = "") -> Path:
    """Baixa um arquivo com barra de progresso."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        print(f"  [skip] {destino.name} ja existe.")
        return destino
    print(f"  [download] {desc or url[:80]}")
    resp = requests.get(url, stream=True, timeout=180)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    with open(destino, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=destino.name) as bar:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            bar.update(len(chunk))
    return destino


def extrair_zip(zip_path: Path, pasta_destino: Path) -> None:
    """Extrai zip se existir."""
    if not zip_path.exists():
        print(f"  [erro] ZIP nao encontrado: {zip_path}")
        return
    pasta_destino.mkdir(parents=True, exist_ok=True)
    print(f"  [unzip] {zip_path.name} -> {pasta_destino.name}/")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(pasta_destino)


# ══════════════════════════════════════════════════════════════════════════════
# 1. GEOBR — Municipios SP
# ══════════════════════════════════════════════════════════════════════════════
def baixar_municipios_geobr():
    """Baixa shapefile de municipios do estado de SP via geobr."""
    try:
        import geobr
    except ImportError:
        print("[!] geobr nao instalado.")
        return

    arq = DIR_CENSO / "municipios_sp.gpkg"
    if arq.exists():
        print(f"  [skip] {arq.name}")
        return

    print("  Baixando municipios SP (IBGE 2022) via geobr...")
    muni = geobr.read_municipality(code_muni="SP", year=2022)
    muni.to_file(arq, driver="GPKG")
    print(f"  Salvo: {arq.name}")


# ══════════════════════════════════════════════════════════════════════════════
# 2. IBGE FTP — Setores Censitarios SP (2022) — download direto
# ══════════════════════════════════════════════════════════════════════════════
def baixar_setores_ibge():
    """
    Baixa os setores censitarios do estado de SP diretamente do FTP do IBGE.
    Arquivo: SP_20231030.zip (~150-200 MB).
    """
    print("\n=== [2/4] Setores Censitarios SP — IBGE FTP ===")

    # URL correta do IBGE (Censo Demografico 2022 — setores definitivos)
    url = (
        "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
        "malhas_territoriais/censo_2022/setores_censitarios/shp/sp/"
        "SP_setores_CD2022.zip"
    )

    zip_dest = DIR_CENSO / "setores_sp_censo2022.zip"
    pasta    = DIR_CENSO / "setores_sp"

    if pasta.exists() and any(pasta.glob("*.shp")):
        print(f"  [skip] Setores ja extraidos em {pasta.name}/")
        return

    try:
        baixar_arquivo(url, zip_dest, "Setores Censitarios SP — Censo 2022 (~180 MB)")
        extrair_zip(zip_dest, pasta)
        shps = list(pasta.glob("**/*.shp"))
        if shps:
            print(f"  OK! {len(shps)} shapefile(s) encontrado(s):")
            for s in shps[:5]:
                print(f"    {s.name}")
        else:
            print("  [aviso] Nenhum .shp encontrado apos extracao. Verifique o ZIP.")
    except Exception as e:
        print(f"  [aviso] Falha no download IBGE: {e}")
        print("  -> Baixe manualmente em:")
        print("     https://www.ibge.gov.br/geociencias/downloads-geociencias.html")
        print("     Caminho: Organizacao do territorio > Malhas territoriais > Setores")
        print(f"     Salve em: {DIR_CENSO}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. DataGEO/DAEE — UGRHIs SP
# ══════════════════════════════════════════════════════════════════════════════
def baixar_ugrhi():
    """Tenta baixar UGRHIs via WFS do DataGEO. Fallback com instrucao manual."""
    print("\n=== [3/4] UGRHIs SP (PCJ e Alto Tiete) ===")

    url_wfs = (
        "https://datageo.ambiente.sp.gov.br/geoserver/datageo/UGRHI_SP/ows"
        "?service=WFS&version=1.0.0&request=GetFeature"
        "&typeName=datageo:UGRHI_SP&outputFormat=SHAPE-ZIP"
    )

    zip_dest = DIR_BACIAS / "ugrhi_sp.zip"
    pasta    = DIR_BACIAS / "ugrhi_sp"

    if pasta.exists() and any(pasta.glob("*.shp")):
        print(f"  [skip] UGRHIs ja extraidas em {pasta.name}/")
        return

    try:
        print("  Tentando WFS DataGEO...")
        baixar_arquivo(url_wfs, zip_dest, "UGRHI SP via WFS DataGEO")
        extrair_zip(zip_dest, pasta)
        print(f"  OK! Salvo em: {pasta.name}/")
    except Exception as e:
        print(f"  [aviso] WFS DataGEO indisponivel: {e}")
        print()
        print("  DOWNLOAD MANUAL NECESSARIO:")
        print("  1. Acesse: https://datageo.ambiente.sp.gov.br/")
        print("  2. Pesquise 'UGRHI' na barra de busca")
        print("  3. Baixe o shapefile de Unidades de Gerenciamento de Recursos Hidricos")
        print(f"  4. Extraia em: {pasta}")
        print()
        print("  Alternativa — ANA Dados Abertos:")
        print("  https://dadosabertos.ana.gov.br/datasets/ANA::otto-bacias/about")
        print(f"  Salve em: {DIR_BACIAS}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Instrucoes para downloads manuais restantes
# ══════════════════════════════════════════════════════════════════════════════
def instrucoes_manuais():
    print("\n=== [4/4] Instrucoes para dados que exigem download manual ===")

    manuais = [
        ("Sub-bacias PCJ (shapefile)",
         "https://agencia.baciaspcj.org.br/",
         str(DIR_BACIAS / "pcj")),
        ("Balanco Hidrico ANA (por UGRHI)",
         "https://dadosabertos.ana.gov.br/ -> pesquise 'balanco hidrico'",
         str(DIR_BACIAS / "balanco_hidrico_ana.csv")),
        ("IVS IPEA (shapefile por UDH)",
         "https://ivs.ipea.gov.br/ -> Download -> Shapefile",
         str(DIR_IVS)),
        ("SNIS / SINISA (indicadores municipais)",
         "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/snis",
         str(BRUTO / "snis")),
    ]

    for nome, url, destino in manuais:
        print(f"\n  [{nome}]")
        print(f"   URL: {url}")
        print(f"   Salvar em: {destino}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Verificar dependencias criticas
    deps_faltando = []
    for dep in ["geopandas", "requests", "tqdm"]:
        try:
            __import__(dep)
        except ImportError:
            deps_faltando.append(dep)
    if deps_faltando:
        print(f"[!] Instale: pip install {' '.join(deps_faltando)}")
        sys.exit(1)

    print("=" * 60)
    print("TRABALHO FINAL - Download de Bases de Dados Geoespaciais")
    print("=" * 60)

    baixar_municipios_geobr()
    baixar_setores_ibge()
    baixar_ugrhi()
    instrucoes_manuais()

    print()
    print("=" * 60)
    print("Download concluido!")
    print(f"Pasta do projeto: {ROOT}")
    print("Itens [manual] precisam de download pelo navegador.")
    print("=" * 60)
