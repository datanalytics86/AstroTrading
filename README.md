# AstroTrading

Dashboard web **privado** que combina:

1. **Astro Quant** — Cyclic Index de André Barbault (determinístico, alta precisión) + comparativa multi-asset + señal de régimen.
2. **Alfayate Engine** — análisis top-down (intermarket / tendencia / amplitud) y ranking de acciones por relative strength.
3. **Capa de agentes** — narrativas LLM (xAI Grok u OpenAI) con fallback a plantillas.

> Uso personal / research. No constituye consejo de inversión.

---

## Decisión de stack (MVP)

| Opción | Pros | Contras |
|--------|------|---------|
| **Streamlit + Python** ✅ | Máxima velocidad en quant (skyfield, yfinance, pandas); un solo lenguaje; auth simple; deploy trivial | UI menos “productizada” que Next.js |
| Next.js + FastAPI | UI premium, App Router | Más superficie, dual runtime, Node requerido |

**Elegido: Streamlit + Python 3.11+** porque el valor del MVP está en el **rigor del Cyclic Index** y el motor quant, no en el framework frontend. El entorno de desarrollo actual no incluye Node.js; Python + skyfield es el camino más corto a un producto usable y correcto.

- **Efemérides:** skyfield + jplephem (JPL DE421)
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
│   ├── agents/narratives.py        # LLM + templates
│   ├── auth_gate.py
│   └── data_service.py
├── scripts/
│   ├── build_historical_index.py
│   └── hash_password.py
├── tests/
├── data/generated/                 # Series cacheadas
├── docs/
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
python scripts/build_historical_index.py --start 2000-01-01 --step 7
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
- Histórico desde 2000 (o 1990) con muestreo semanal.
- Comparativa rebased vs **SPX, Gold, BTC, WTI, Copper**.
- Regresión simple retorno forward ~63d ~ f(Cyclic Index).
- Señal **Favorable / Neutral / Desfavorable** con percentil, z-score, pendientes y justificación.
- Narrativa LLM opcional.

### Alfayate Engine (MVP)
1. Régimen: tendencia SPX (SMA50/200), SPX/Gold, HYG/TLT, BTC.
2. Amplitud: % del universo > SMA50 / SMA200.
3. Ranking RS 3m/6m/12m vs SPX + momentum + filtros de tendencia.
4. Razones legibles por ticker.

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
- [x] Código tipado, documentado, README
- [x] Deploy-friendly (Streamlit)

---

## Licencia

Proprietary — uso privado del propietario del repositorio.
