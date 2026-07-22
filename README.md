# AstroTrading

Dashboard web **privado** que combina:

1. **Astro Quant** — Cyclic Index de André Barbault (determinístico, alta precisión) + comparativa multi-asset + señal de régimen.
2. **Alfayate Engine** — análisis top-down (intermarket / tendencia / amplitud) y ranking de acciones por relative strength.
3. **Bagger Scanner** — candidatos multi-bagger / 100-bagger con scoring explícito según Mayer, Phelps, O’Neil, Fisher, Lynch y Minervini.
4. **Capa de agentes** — narrativas LLM (xAI Grok u OpenAI) con fallback a plantillas.

> Uso personal / research. No constituye consejo de inversión.

---

## Decisión de stack (MVP)

| Opción | Pros | Contras |
|--------|------|---------|
| **Streamlit + Python** ✅ | Máxima velocidad en quant (skyfield, yfinance, pandas); un solo lenguaje; auth simple; deploy trivial | UI menos “productizada” que Next.js |
| Next.js + FastAPI | UI premium, App Router | Más superficie, dual runtime, Node requerido |

**Elegido: Streamlit + Python 3.11+** porque el valor del MVP está en el **rigor del Cyclic Index** y el motor quant, no en el framework frontend. El entorno de desarrollo actual no incluye Node.js; Python + skyfield es el camino más corto a un producto usable y correcto.

- **Efemérides:** skyfield + jplephem (JPL DE421 histórico; **DE440s** para forecast +50y)
- **Mercados:** yfinance (extensible a Polygon)
- **Charts:** Plotly
- **Auth:** single-user (usuario/contraseña, opcional bcrypt)
- **Deploy:** Streamlit Community Cloud, Railway, Fly.io o VPS

---

## Cyclic Index (fórmula exacta)

1. Longitudes eclípticas de **Jupiter, Saturn, Uranus, Neptune, Pluto**.
2. Las **10** distancias angulares **más cortas** (arco mínimo ≤ 180°) entre todos los pares.
3. **Suma** de esas 10 distancias → **Cyclic Index** (grados).

- Frame **heliocéntrico** (clásico Barbault) por defecto; geocéntrico opcional.
- Documentación detallada: [`docs/cyclic_index.md`](docs/cyclic_index.md).

```python
from datetime import date
from astrotrading.astrology import compute_cyclic_index

r = compute_cyclic_index(date.today(), frame="heliocentric")
print(r.index, r.longitudes, r.pairs)
```

---

## Estructura

```
AstroTrading/
├── app/
│   ├── Home.py                 # Entrypoint Streamlit + auth
│   └── pages/
│       ├── 1_Astro_Quant.py
│       └── 2_Alfayate_Engine.py
├── src/astrotrading/
│   ├── astrology/cyclic_index.py   # Motor Barbault (puro + skyfield)
│   ├── quant/                      # Régimen + regresión multi-asset
│   ├── market_data/                # yfinance + universo extensible
│   ├── alfayate/engine.py          # Top-down + RS ranking
│   ├── bagger/                     # Multi-bagger scanner (literatura)
│   ├── agents/narratives.py        # LLM + templates
│   ├── auth_gate.py
│   └── data_service.py
├── scripts/
│   ├── build_historical_index.py
│   └── hash_password.py
├── tests/
├── data/generated/                 # Series cacheadas
├── docs/
│   ├── cyclic_index.md
│   └── bagger_scanner.md
├── requirements.txt
└── .env.example
```

---

## Setup rápido

```bash
git clone https://github.com/datanalytics86/AstroTrading.git
cd AstroTrading

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -r requirements.txt
python -m pip install -e .

# Auth (obligatorio)
copy .env.example .env   # o cp .env.example .env
# Edita ASTROTRADING_USERNAME y ASTROTRADING_PASSWORD
```

Opcional — hash bcrypt:

```bash
python scripts/hash_password.py
# Pega ASTROTRADING_PASSWORD=bcrypt$... en .env
```

### Tests del Cyclic Index

```bash
python -m pytest tests/ -v
```

### Precalcular serie histórica

```bash
python scripts/build_historical_index.py --start 1920-01-01 --step 7
```

### Arrancar el dashboard

```bash
streamlit run app/Home.py
```

Abre `http://localhost:8501`, inicia sesión con las credenciales de `.env`.

---

## Módulos

### Astro Quant
- Valor actual del índice + desglose de longitudes y 10 arcos.
- Histórico **desde 1920** (semanal; DE421). Ventanas 1950/1970/1990/2000 en el UI.
- **Forecast orbital a 50 años** (DE440s; DE421 solo llega a ~2053) con chart histórico+futuro, min/max y zonas de compresión/expansión.
- Correlación multi-asset con cobertura realista por activo (SPX ~1927, BTC ~2014, etc.).
- Comparativa rebased vs **SPX, Gold, BTC, WTI, Copper**.
- Regresión simple retorno forward ~63d ~ f(Cyclic Index).
- Señal **Favorable / Neutral / Desfavorable** con percentil, z-score, pendientes y justificación.
- Narrativa LLM opcional.

```bash
# Regenerar proyección 50y
python scripts/build_forecast_50y.py --force
```

### Alfayate Engine (MVP)
1. Régimen: tendencia SPX (SMA50/200), SPX/Gold, HYG/TLT, BTC.
2. Amplitud: % del universo > SMA50 / SMA200.
3. Ranking RS 3m/6m/12m vs SPX + momentum + filtros de tendencia.
4. Razones legibles por ticker.

### Bagger Scanner
Scanner de **potenciales multi-baggers** con score 0–100 transparente:

| Pilar | Peso | Literatura |
|-------|------|------------|
| Quality (ROE/ROIC, márgenes, D/E) | 30% | Mayer, Fisher, Phelps |
| Growth (sales/EPS) | 25% | Mayer, O’Neil, Lynch |
| Momentum / RS + SMA / 52w | 25% | O’Neil, Minervini |
| Valuation (PEG, P/E) | 15% | Lynch, Mayer |
| Bonus (insiders, buybacks) | 5% | Fisher, Mayer |

- Contexto de régimen vía Alfayate (aviso en Risk-Off, no bloqueo).
- Universo ~200 tickers líquidos (configurable en `bagger/universe.py`).
- Detalle: [`docs/bagger_scanner.md`](docs/bagger_scanner.md).

```python
from astrotrading.bagger import run_bagger_scanner
print(run_bagger_scanner(top_n=15).candidates[0])
```

### Extender commodities / activos
En `src/astrotrading/market_data/fetchers.py`:

```python
AssetSpec("silver", "Silver", "SI=F", "metal"),
```

---

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `ASTROTRADING_USERNAME` | Usuario único |
| `ASTROTRADING_PASSWORD` | Password o `bcrypt$...` |
| `XAI_API_KEY` | Narrativas Grok (opcional) |
| `OPENAI_API_KEY` | Fallback OpenAI-compatible |
| `POLYGON_API_KEY` | Reservado / futuro |

---

## Deploy

**Streamlit Community Cloud:** conecta el repo, entrypoint `app/Home.py`, secrets con las vars de auth.

**Docker (simple):**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=src
EXPOSE 8501
CMD ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## Criterios MVP

- [x] Auth single-user (fail-closed sin password)
- [x] Cyclic Index correcto y testeado (26+ tests)
- [x] Valor actual + histórico
- [x] Charts vs SPX, Gold, BTC, WTI, Copper
- [x] Señal de régimen con justificación
- [x] Ranking top-down estilo Alfayate
- [x] Bagger Scanner con criterios literarios + razones
- [x] Código tipado, documentado, README
- [x] Deploy-friendly (Streamlit)

---

## Licencia

Proprietary — uso privado del propietario del repositorio.
