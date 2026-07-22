# Bagger Scanner — especificación

Módulo de research para identificar **candidatos** a multi-bagger / 100-bagger
alineados con la bibliografía clásica. **No predice** baggers; puntúa perfiles
compatibles con las características que esos autores enfatizan.

## Bibliografía (orden de peso conceptual)

1. **Christopher Mayer** — *100 Baggers*
2. **Thomas Phelps** — *100 to 1 in the Stock Market*
3. **William O’Neil** — CAN SLIM (*How to Make Money in Stocks*)
4. **Philip Fisher** — *Common Stocks and Uncommon Profits*
5. **Peter Lynch** — ten-baggers / PEG (*One Up on Wall Street*)
6. **Mark Minervini** — Trend Template / SEPA

## Pipeline

1. **Régimen de mercado (contexto)** — reutiliza el motor Alfayate (intermarket + tendencia SPX).  
   Si es Risk-Off: **advertencia** (O’Neil: no pelear el mercado), pero el ranking sigue visible.
2. **Universo** — ~200 tickers líquidos US (`universe.py`), ampliable.
3. **Datos** — precios batch (yfinance) + fundamentals best-effort por ticker.
4. **Scoring** — 5 pilares en [0,1], compuesto 0–100 con pesos fijos y **renormalización** si faltan datos.
5. **Razones** — cada candidato expone métricas y justificación literaria.

## Pesos del score

| Pilar | Peso | Métricas principales | Fuentes |
|-------|------|----------------------|---------|
| Quality / Capital efficiency | 30% | ROE/ROIC, márgenes, D/E | Mayer, Fisher, Phelps |
| Growth | 25% | Sales growth, EPS growth, quarterly EPS | Mayer, O’Neil, Lynch |
| Momentum / RS | 25% | RS vs SPX 3/6/12m, 52w high, SMA50/200 | O’Neil, Minervini |
| Valuation | 15% | PEG, trailing P/E | Lynch, Mayer |
| Bonus | 5% | Insider ownership, buybacks | Fisher, Mayer |

## API

```python
from astrotrading.bagger import run_bagger_scanner

result = run_bagger_scanner(top_n=25, min_score=40)
for c in result.candidates:
    print(c.rank, c.symbol, c.score, c.reasons[:2])
```

Scoring puro (sin red):

```python
from astrotrading.bagger.scoring import score_from_metrics

total, pillars, weights, reasons = score_from_metrics({...})
```

## Limitaciones

- Cobertura de fundamentals de yfinance es incompleta (ROIC, PEG, insiders).
- Multi-baggers reales son raros y requieren **años** (Phelps/Mayer).
- El score es un filtro de research, no una señal de trading.

## Archivos

- `src/astrotrading/bagger/literature.py` — mapeo bibliográfico
- `src/astrotrading/bagger/scoring.py` — funciones puras
- `src/astrotrading/bagger/universe.py` — universo configurable
- `src/astrotrading/bagger/engine.py` — orquestación
- `app/pages/3_Bagger_Scanner.py` — UI Streamlit
