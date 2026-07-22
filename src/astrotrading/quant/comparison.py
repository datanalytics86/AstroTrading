"""
Compare Cyclic Index vs multi-asset performance.

Provides:
  - aligned panel (index + rebased assets)
  - simple OLS regression of forward asset returns on index level / changes
  - correlation table
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class AssetRegression:
    asset: str
    n_obs: int
    beta: float
    alpha: float
    r_squared: float
    corr: float
    correlation_with_delta_ci: float


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[float, float, float]:
    """Simple OLS y = a + b x. Returns (alpha, beta, r2)."""
    mask = np.isfinite(y) & np.isfinite(x)
    y, x = y[mask], x[mask]
    n = len(y)
    if n < 10:
        return 0.0, 0.0, 0.0
    x_mean = x.mean()
    y_mean = y.mean()
    var_x = ((x - x_mean) ** 2).sum()
    if var_x <= 0:
        return float(y_mean), 0.0, 0.0
    beta = float(((x - x_mean) * (y - y_mean)).sum() / var_x)
    alpha = float(y_mean - beta * x_mean)
    y_hat = alpha + beta * x
    ss_res = float(((y - y_hat) ** 2).sum())
    ss_tot = float(((y - y_mean) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return alpha, beta, r2


def align_index_and_assets(
    cyclic: pd.Series,
    assets: pd.DataFrame,
) -> pd.DataFrame:
    """
    Outer-join on calendar dates, forward-fill cyclic (weekly) onto daily assets,
    then drop rows without asset prices.
    """
    ci = cyclic.copy()
    ci.index = pd.to_datetime(ci.index)
    ci = ci.sort_index().rename("cyclic_index")

    a = assets.copy()
    a.index = pd.to_datetime(a.index)
    a = a.sort_index()

    panel = a.join(ci, how="left")
    panel["cyclic_index"] = panel["cyclic_index"].ffill()
    panel = panel.dropna(subset=["cyclic_index"], how="any")
    return panel


def compare_index_vs_assets(
    cyclic: pd.Series,
    assets: pd.DataFrame,
    *,
    forward_days: int = 63,
    rebalance_base: float = 100.0,
) -> dict:
    """
    Full comparison package for the dashboard.

    Returns dict with:
      panel_rebased, correlations, regressions, summary
    """
    panel = align_index_and_assets(cyclic, assets)
    asset_cols = [c for c in panel.columns if c != "cyclic_index"]

    # Rebased prices for charting
    rebased = panel[asset_cols].copy()
    for col in asset_cols:
        s = rebased[col].dropna()
        if not s.empty and s.iloc[0] != 0:
            rebased[col] = rebased[col] / s.iloc[0] * rebalance_base
    rebased["cyclic_index"] = panel["cyclic_index"]

    # Correlations: level CI vs asset returns; ΔCI vs returns
    rets = panel[asset_cols].pct_change(fill_method=None)
    d_ci = panel["cyclic_index"].diff()
    corr_level = {}
    corr_delta = {}
    for col in asset_cols:
        asset_ret = panel[col].pct_change(fill_method=None).fillna(0)
        corr_level[col] = float(panel["cyclic_index"].corr(asset_ret))
        corr_delta[col] = float(d_ci.corr(rets[col]))

    # Forward return regression: r_{t→t+h} ~ a + b * CI_t
    regressions: list[AssetRegression] = []
    for col in asset_cols:
        fwd = panel[col].shift(-forward_days) / panel[col] - 1.0
        y = fwd.to_numpy(dtype=float)
        x = panel["cyclic_index"].to_numpy(dtype=float)
        alpha, beta, r2 = _ols(y, x)
        mask = np.isfinite(y) & np.isfinite(x)
        corr = float(np.corrcoef(x[mask], y[mask])[0, 1]) if mask.sum() > 5 else 0.0
        regressions.append(
            AssetRegression(
                asset=col,
                n_obs=int(mask.sum()),
                beta=round(beta, 6),
                alpha=round(alpha, 6),
                r_squared=round(r2, 4),
                corr=round(corr, 4),
                correlation_with_delta_ci=round(corr_delta.get(col) or 0.0, 4),
            )
        )

    summary = {
        "start": panel.index.min().date().isoformat() if len(panel) else None,
        "end": panel.index.max().date().isoformat() if len(panel) else None,
        "n_rows": int(len(panel)),
        "assets": asset_cols,
        "forward_days": forward_days,
    }

    return {
        "panel": panel,
        "panel_rebased": rebased,
        "correlations_level": corr_level,
        "correlations_delta": corr_delta,
        "regressions": regressions,
        "summary": summary,
    }
