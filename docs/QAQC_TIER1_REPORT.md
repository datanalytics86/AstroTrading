# QAQC Tier 1 Report — AstroTrading

**Fecha:** 2026-07-22  
**Repositorio:** https://github.com/datanalytics86/AstroTrading  
**Alcance:** Cyclic Index + Forecast 50y · Alfayate · Bagger Scanner · Auth · Streamlit · Tests · Docs  
**Auditor:** Senior Quant / Code Audit / QA Lead (Tier 1)

---

## 1. Resumen Ejecutivo

| Dimensión | Estado post-fix |
|-----------|-------------------|
| Correctness científica (Cyclic Index) | **Sólida** — fórmula exacta, determinista, testeada |
| Forecast orbital 50y | **Sólida** — DE440s, misma fórmula, disclaimers claros |
| Bagger / Alfayate | **Aceptable MVP** — scoring transparente; fundamentals yfinance limitados |
| Auth | **Sólida post-fix** — fail-closed + compare seguro |
| Tests | **59 passed** (antes 45); coverage ~44% global, >85% en core math |
| Producción privada | **Lista** con salvedades documentadas (Medium/Low) |

### Hallazgos por severidad

| Severidad | Encontrados | Fixed | Accepted / Deferred |
|-----------|-------------|-------|---------------------|
| **Critical** | 1 | 1 | 0 |
| **High** | 6 | 6 | 0 |
| **Medium** | 7 | 1 (docs) | 6 deferred |
| **Low** | 5 | 1 | 4 deferred |

### Conclusión

**Listo para uso privado de research** tras los fixes Critical/High de esta auditoría.  
No es un producto financiero regulado ni un motor de señales de trading; el Cyclic Index y el forecast son **mecánica celeste**, y los módulos de acciones son **scanners heurísticos**.

---

## 2. Resultados de Tests

### Suite completa (post-fix)

```
59 passed in ~1.4–1.8s
```

Módulos de test:
- `tests/test_cyclic_index.py` — fórmula, pares, helio/geo, DE421↔DE440s
- `tests/test_forecast.py` — horizonte, extremos, summary, smoke live
- `tests/test_bagger_scoring.py` — pesos y pilares
- `tests/test_bagger_fundamentals.py` — **nuevo** (no double-count, no ROA→ROIC)
- `tests/test_auth.py` — **nuevo** (fail-closed, lengths, bcrypt)
- `tests/test_regime.py` — régimen heurístico

### Coverage aproximado (`pytest --cov=astrotrading`)

| Área | Cover (aprox.) |
|------|----------------|
| `astrology/cyclic_index.py` | **90%** |
| `astrology/forecast.py` | **79%** |
| `bagger/scoring.py` | **86%** |
| `quant/regime.py` | **88%** |
| `auth_gate.py` (helpers) | 36% (UI Streamlit no ejercida) |
| `alfayate/engine.py` | 0% (I/O yfinance — sin mocks) |
| **TOTAL** | **~44%** |

### Probes científicas manuales (auditoría)

| Check | Resultado |
|-------|-----------|
| 10 pares exactos C(5,2) | OK |
| Arco mínimo (350°–10°=20°) | OK |
| Índice = suma de pares | OK |
| Determinismo misma fecha | OK |
| DE421 vs DE440s (2020-06-15) | Δ ≈ **6.6e-5°** |
| Forecast punto = `compute_cyclic_index(..., kernel=de440s)` | **match exacto** |
| Helio ≠ geo (2020-06-15) | 539.84° vs 529.77° |

---

## 3. Hallazgos Detallados

| ID | Severidad | Módulo | Descripción | Estado |
|----|-----------|--------|-------------|--------|
| **C-01** | Critical | `auth_gate.py` | `hmac.compare_digest` **lanza ValueError** si usuario/password tienen distinta longitud → login puede crashear (500) en vez de “credenciales incorrectas”. | **Fixed** |
| **H-01** | High | `tests/test_cyclic_index.py` | Assert heliocéntrico vs geocéntrico era `... or True` → **siempre pasaba** (test inútil). | **Fixed** |
| **H-02** | High | `bagger/engine.py` | `earningsGrowth` hacía fallback a `earningsQuarterlyGrowth` → **double-count** del mismo dato en pilares Growth. | **Fixed** |
| **H-03** | High | `bagger/engine.py` | `trailing_pe` aceptaba `forwardPE` → valoración mal etiquetada. | **Fixed** |
| **H-04** | High | `bagger/engine.py` | Código muerto/confuso con ROA; riesgo de confundir ROA con ROIC (Mayer). | **Fixed** (ROIC solo `returnOnCapital`) |
| **H-05** | High | `cyclic_index.py` | `mkdir` de efemérides sin try/except → fallo posible en FS restringido (Cloud). | **Fixed** |
| **H-06** | High | Docs / régimen | Etiquetas Favorable/Desfavorable podían leerse como “ortodoxia Barbault” o predicción; hacía falta explicitar heurística. | **Fixed** (docs + docstrings + UI caption) |
| M-01 | Medium | Tests | `alfayate/engine.py` y `market_data` sin tests unitarios (dependen de red). | Deferred |
| M-02 | Medium | Histórico vs forecast | Histórico default DE421; forecast DE440s. Δ despreciable en overlap; no unificado en un solo kernel. | Accepted (documentado) |
| M-03 | Medium | Auth | Password plaintext permitido en MVP; sin rate-limit / session TTL. | Deferred (privado single-user) |
| M-04 | Medium | Bagger | ROIC casi nunca disponible en yfinance → quality cae a ROE (honesto pero limitado). | Accepted |
| M-05 | Medium | Bagger/Alfayate | Universo fijo ~300 tickers; no S&P 500 completo ni survivorship control. | Deferred |
| M-06 | Medium | Coverage | Agents, data_service, fetchers ~0% en unit tests. | Deferred |
| M-07 | Medium | UI | `set_page_config` / import error path en Astro Quant es correcto pero frágil si se reordena código. | Accepted |
| L-01 | Low | `cyclic_index.py` | Import `math` no usado (eliminado en fix colateral). | Fixed |
| L-02 | Low | Performance | Series histórica 1920 weekly y bagger full universe son lentos en cold start. | Deferred |
| L-03 | Low | Cache mercado | Depende de pyarrow o CSV fallback (ya implementado). | Accepted |
| L-04 | Low | README | Podía mencionar informe QAQC. | Fixed (enlace) |
| L-05 | Low | Forecast extrema | Detector local sensible a `order`; puede omitir ondas suaves. | Accepted |

---

## 4. Fixes Aplicados

1. **Auth (`auth_gate.py`)**  
   - Igualdad de strings vía SHA-256 + `hmac.compare_digest` (sin crash por longitud).  
   - Fail-closed sin password se mantiene.  
   - Tests de regresión en `tests/test_auth.py`.

2. **Cyclic Index tests**  
   - Assert helio≠geo real.  
   - Nuevo test DE421 vs DE440s en era de overlap.

3. **Bagger fundamentals**  
   - Sin fallback annual←quarterly.  
   - Sin forwardPE como trailing.  
   - ROIC solo si existe `returnOnCapital`.  
   - Tests en `tests/test_bagger_fundamentals.py`.

4. **Robustez ephemeris dir**  
   - `mkdir` protegido con `OSError` handler.

5. **Claridad interpretativa**  
   - `regime.py`, `docs/cyclic_index.md`, caption forecast en Astro Quant:  
     proyección orbital ≠ predicción de mercados; régimen = heurística del dashboard.

6. **Informe**  
   - Este documento en `docs/QAQC_TIER1_REPORT.md`.

---

## 5. Recomendaciones (Medium / Low y futuro)

1. **Mocks de yfinance** para tests de Alfayate / Bagger engine (régimen + ranking sin red).  
2. **Session TTL** y bcrypt obligatorio en producción Cloud.  
3. **Unificar kernel DE440s** también para histórico reciente (opcional; coste de descarga).  
4. **Ampliar universo** Bagger a S&P 500 completo con job batch nocturno.  
5. **Logging estructurado** y métricas de latencia en scanners.  
6. **CI GitHub Actions**: `pytest` en cada push a `main`.  
7. **Rate limit** de login (N intentos / IP) si se expone URL pública.  
8. No presentar scores Bagger/Alfayate como “predicción de multi-baggers” en materiales externos.

---

## 6. Checklist de auditoría (estado)

### A. Cyclic Index Engine
- [x] Fórmula = suma de 10 arcos mínimos ≤180° (J–S–U–N–P)  
- [x] Determinística y reproducible  
- [x] Helio / geo revisados  
- [x] skyfield + DE421 / DE440s y límites documentados  
- [x] Tests cyclic + forecast ejecutados  
- [x] Forecast etiquetado como proyección orbital  

### B. Bagger Scanner
- [x] Pilares alineados con Mayer / O’Neil / Fisher / Lynch / Minervini (heurística transparente)  
- [x] Razones por ticker  
- [x] Missing data → renormalización de pesos  
- [x] Tests scoring + fundamentals  

### C. Alfayate Engine
- [x] Top-down régimen → ranking revisado  
- [x] Manejo de fallos de datos (returns vacíos / notes) — sin tests de red  

### D. Auth & Security
- [x] Fail-closed  
- [x] Sin secrets en git (`.env` ignored)  
- [x] `.env.example` presente  
- [x] Compare seguro post-fix  

### E. UI / Streamlit
- [x] Home + 3 páginas; bootstrap path Cloud  
- [x] `@st.cache_data` en cargas pesados  
- [x] Errores de import visibles en Astro Quant  

### F–H. Ingeniería / Docs / Tests
- [x] Estructura limpia; requirements con `-e .`  
- [x] Docs cyclic + bagger + este informe  
- [x] 59 tests green  

---

## 7. Conclusión Final

El núcleo **Cyclic Index + Forecast** es de **calidad Tier 1** para un research desk privado: fórmula correcta, kernels documentados, tests de regresión fuertes tras la auditoría.

Los módulos **Alfayate** y **Bagger** son MVPs **útiles y transparentes**, limitados por la calidad de fundamentals de yfinance y por la ausencia de tests de integración con red — aceptable si se comunican como scanners, no como alpha garantizado.

La auditoría corrigió un **bug Critical de auth** y varios **High** de scoring/tests/robustez. El repositorio queda en estado **apto para producción privada**, con recomendaciones Medium/Low priorizables en el siguiente ciclo.

---

*Fin del informe QAQC Tier 1.*
