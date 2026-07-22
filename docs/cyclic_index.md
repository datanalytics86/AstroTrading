# Cyclic Index de André Barbault — especificación de implementación

## Fórmula (exacta)

1. Obtener longitudes eclípticas de: **Jupiter, Saturn, Uranus, Neptune, Pluto**.
2. Calcular las **10** distancias angulares **más cortas** (arco mínimo ≤ 180°) entre todos los pares \(C(5,2)=10\).
3. **Sumar** esas 10 distancias → **Cyclic Index** (en grados).

\[
CI(t) = \sum_{1 \le i < j \le 5} \min\bigl(|\lambda_i - \lambda_j| \bmod 360,\ 360 - |\lambda_i - \lambda_j| \bmod 360\bigr)
\]

Rango teórico: \([0,\ 1800]\) grados.

## Marco de referencia

| Frame          | Origen | Uso en AstroTrading                          |
|----------------|--------|----------------------------------------------|
| **heliocentric** | Sol  | **Primario** — convención clásica de Barbault |
| geocentric     | Tierra | Secundario / contraste                        |

## Efemérides

- Motor: **skyfield** + **jplephem**
- Kernel histórico por defecto: **JPL DE421** (`de421.bsp`) — cobertura ~1899-07-29 → **2053-10-09**
- Kernel de **forecast +50 años**: **JPL DE440s** (`de440s.bsp`) — cubre holgadamente hasta 2076+
- Cuerpos: barycenters de los planetas exteriores (estándar de calidad en DE)
- Fecha sin hora → **12:00 UTC** (convención diaria)

Los kernels se descargan una vez a `data/ephemeris/` y se reutilizan.

### Limitación DE421 y forecast

Un horizonte de **+50 años** desde ~2026 termina en **~2076**, **fuera** del rango de DE421.
Por eso el forecast **no** usa DE421: usa **DE440s**. La fórmula del índice es idéntica;
solo cambia el kernel de efemérides.

## API Python

```python
from datetime import date
from astrotrading.astrology import compute_cyclic_index

r = compute_cyclic_index(date(2000, 1, 1), frame="heliocentric")
print(r.index)          # float, grados
print(r.longitudes)     # dict por planeta
print(r.pairs)          # 10 pares → distancia
```

Serie histórica:

```python
from astrotrading.astrology import compute_cyclic_index_series

series = compute_cyclic_index_series("1920-01-01", "2026-07-22", step_days=7)
```

### Forecast orbital a 50 años

```python
from astrotrading.astrology import load_or_build_forecast

df, summary = load_or_build_forecast(years=50, step_days=14, frame="heliocentric")
print(summary.forecast_min, summary.forecast_min_date)
print(summary.trend_label, summary.slope_per_year)
```

- Script: `python scripts/build_forecast_50y.py --force`
- Cache: `data/generated/cyclic_index_forecast_50y_heliocentric.csv`
- **No es predicción de mercados**: proyección determinística de posiciones planetarias.

## Interpretación de régimen (MVP)

Heurística cuantitativa sobre el nivel y la pendiente del índice (no es señal de trading automática):

- **Favorable**: índice en zona baja relativa (dispersión planetaria baja / fases de concentración) + pendiente no alcista fuerte.
- **Neutral**: zona media o señales mixtas.
- **Desfavorable**: índice en zona alta relativa (máxima dispersión angular) + pendiente alcista.

El dashboard muestra percentil histórico, z-score y pendiente de 1–2 años para justificar la señal.

## Reproducibilidad

Dado el mismo kernel JPL y la misma fecha UTC, el valor es **bit-reproducible** (función pura sobre efemérides deterministas). Los tests en `tests/test_cyclic_index.py` cubren la matemática angular y la integración con skyfield.

## Referencias

- André Barbault — trabajos sobre el índice cíclico de planetas lentos.
- JPL Planetary and Lunar Ephemerides (DE421 / DE440).
- Skyfield documentation: https://rhodesmill.org/skyfield/
