# Trabalho Final — Diagnóstico Socioambiental Integrado

**Expansão de Data Centers, Pressão Hídrica e Vulnerabilidade Social em Barueri e Campinas (SP)**

> Matheus Spadaro (RA 822389) | Felipe Camargo (RA 823676) | Gustavo Gomes (RA 823176)

---

## Estrutura do Projeto

```
trabalho_final/
├── dados/
│   ├── brutos/
│   │   ├── data_centers/       ← CSV com coordenadas dos DCs
│   │   ├── bacias/             ← SHP das bacias PCJ e Alto Tietê
│   │   ├── censo_2022/         ← SHP setores censitários + CSV demográfico
│   │   ├── ivs/                ← Dados IVS IPEA
│   │   └── snis/               ← Indicadores de saneamento
│   └── processados/            ← GeoPackages e CSVs intermediários
├── scripts/                    ← Pipeline Python (rodar em ordem)
├── mapas/                      ← Exports finais (PNG 300 DPI + PDF)
├── texto/                      ← Relatório final
├── apresentacao/               ← Slides
└── README.md
```

---

## Pipeline de Execução

Execute os scripts **na ordem abaixo**:

```bash
# 1. Instalar dependências
pip install geopandas geobr requests geopy tqdm mapclassify contextily matplotlib

# 2. Baixar bases de dados
python scripts/01_download_dados.py

# 3. Geocodificar e validar data centers
python scripts/02_georreferenciar_dcs.py

# 4. Spatial joins (DCs × Bacias × Setores)
python scripts/03_spatial_joins.py

# 5. Análise de buffer e injustiça ambiental
python scripts/04_analise_buffer.py

# 6. Gerar mapas finais
python scripts/05_gerar_mapas.py
```

---

## Downloads Necessários

| Dado | Fonte | URL | Salvar em |
|------|-------|-----|-----------|
| UGRHIs SP (shapefile) | DataGEO/DAEE | https://datageo.ambiente.sp.gov.br | dados/brutos/bacias/ |
| Sub-bacias PCJ | Agência PCJ | https://agencia.baciaspcj.org.br | dados/brutos/bacias/pcj/ |
| Balanço hídrico ANA | ANA Dados Abertos | https://dadosabertos.ana.gov.br | dados/brutos/bacias/ |
| IVS IPEA (shapefile) | Atlas IVS | https://ivs.ipea.gov.br | dados/brutos/ivs/ |
| SNIS indicadores | SINISA | https://www.gov.br/cidades/snis | dados/brutos/snis/ |

---

## Ajustes Necessários nos Scripts

Após baixar os dados, **verifique e ajuste** as seguintes variáveis:

### `03_spatial_joins.py`
- `ARQ_SETORES` → caminho exato do SHP do IBGE após extração
- Nome das colunas de UGRHI no shapefile do DAEE (linha `filtrar_bacias()`)

### `04_analise_buffer.py`
- `COL_IVS` → nome da coluna IVS no GeoDataFrame do IPEA
- `COL_POP` → nome da coluna de população do Censo 2022

### `05_gerar_mapas.py`
- `COL_CRIT` → nome da coluna de criticidade hídrica no shapefile da ANA

---

## Validação dos Data Centers no Google Earth

Após rodar `02_georreferenciar_dcs.py`:

1. Abra `dados/brutos/data_centers/data_centers_validacao.kml` no **Google Earth Pro**
2. Para cada ponto, verifique no satélite se há:
   - Baterias de **chillers** (unidades azuis/cinzas no telhado)
   - **Torres de resfriamento** (cilindros brancos)
   - **Geradores** de emergência (grandes unidades metálicas)
3. Se o ponto estiver errado, corrija `lat`/`lon` em `data_centers_bruto.csv`
4. Rode novamente `02_georreferenciar_dcs.py`

---

## CRS / Projeção

| Etapa | CRS | EPSG | Motivo |
|-------|-----|------|--------|
| Entrada (geobr, IBGE) | SIRGAS 2000 geográfico | 4674 | Padrão brasileiro |
| Análise/buffers | SIRGAS 2000 / UTM 23S | 31983 | Metros (SP) |
| Exportação final | SIRGAS 2000 geográfico | 4674 | Compatibilidade QGIS |

---

## Referências Rápidas

- **CGI.br/Cetic.br:** https://cgi.br/publicacoes/
- **PeeringDB:** https://www.peeringdb.com/
- **ANA Dados Abertos:** https://dadosabertos.ana.gov.br/
- **DataGEO/DAEE:** https://datageo.ambiente.sp.gov.br/
- **Atlas IVS IPEA:** https://ivs.ipea.gov.br/
- **geobr (Python):** https://github.com/ipeaGIT/geobr
