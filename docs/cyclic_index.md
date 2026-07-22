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
- Kernel por defecto: **JPL DE421** (`de421.bsp`)
- Cuerpos: barycenters de los planetas exteriores (estándar de calidad en DE)
- Fecha sin hora → **12:00 UTC** (convención diaria)

Los kernels se descargan una vez a `data/ephemeris/` y se reutilizan.

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

series = compute_cyclic_index_series("2000-01-01", "2024-12-31", step_days=7)
```

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
