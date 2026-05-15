"""
Baseline comparison & severity classification.

Given a merged dataframe with multi-day data, compute for each campaign:
  - reference day CPA / ROAS (the latest day in the data, "D-1")
  - prior-day baseline (D-2) and same-weekday-prior-week (D-8)
  - % change vs each baseline
  - severity tag (critical / warning / normal)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import pandas as pd

Severity = Literal["critical", "warning", "normal", "improved", "new"]

# Defaults — overridable from sidebar
DEFAULT_THRESHOLDS = {
    "CPA": (15.0, 30.0),   # (warning %, critical %)  — increase is bad
    "ROAS": (15.0, 30.0),  # decrease is bad
}


@dataclass
class AnomalyConfig:
    cpa_warning: float = 15.0
    cpa_critical: float = 30.0
    roas_warning: float = 15.0
    roas_critical: float = 30.0


def _compute_kpi(df: pd.DataFrame) -> pd.DataFrame:
    """Add CPA, ROAS columns from raw 비용/회원가입/구매매출."""
    df = df.copy()
    # Use channel-side numbers as primary (consistent with current dashboard)
    sign = df.get("회원가입", pd.Series(0, index=df.index))
    rev = df.get("구매매출", pd.Series(0, index=df.index))
    cost = df.get("비용", pd.Series(0, index=df.index))
    df["CPA"] = (cost / sign.replace(0, pd.NA)).astype("float")
    df["ROAS"] = (rev / cost.replace(0, pd.NA) * 100).astype("float")
    return df


def _classify(cpa_delta_pct: float | None, roas_delta_pct: float | None,
              cfg: AnomalyConfig) -> Severity:
    """Map deltas to severity. CPA UP is bad, ROAS DOWN is bad."""
    cpa_up = cpa_delta_pct if cpa_delta_pct is not None else 0.0
    roas_down = -(roas_delta_pct or 0.0)  # negate so 'down' becomes positive

    worst = max(cpa_up, roas_down)
    if worst >= cfg.cpa_critical:
        return "critical"
    if worst >= cfg.cpa_warning:
        return "warning"
    if max(-cpa_up, -roas_down) >= cfg.cpa_warning:
        return "improved"
    return "normal"


def detect_campaign_anomalies(
    merged: pd.DataFrame,
    cfg: AnomalyConfig | None = None,
) -> pd.DataFrame:
    """
    Aggregate merged data by (캠페인, 날짜), compute CPA/ROAS, then for each
    campaign return reference-day metrics + deltas vs D-2 and D-8.

    Returns a DataFrame with columns:
      캠페인 · 채널 · CPA_ref · ROAS_ref · 비용_ref ·
      CPA_d1_vs_d2 · ROAS_d1_vs_d2 · CPA_d1_vs_d8 · ROAS_d1_vs_d8 ·
      severity · sort_key
    """
    cfg = cfg or AnomalyConfig()
    if merged.empty or "날짜" not in merged.columns:
        return pd.DataFrame()

    df = _compute_kpi(merged)
    dates = sorted(df["날짜"].dropna().unique())
    if len(dates) < 2:
        return pd.DataFrame()

    d_ref = dates[-1]
    d_prev = dates[-2]
    d_week = dates[-8] if len(dates) >= 8 else None

    def agg_by_day(day):
        sub = df[df["날짜"] == day]
        return (sub.groupby("캠페인", as_index=False)
                .agg(비용=("비용", "sum"),
                     노출=("노출", "sum"),
                     클릭=("클릭", "sum"),
                     회원가입=("회원가입", "sum"),
                     구매=("구매", "sum"),
                     구매매출=("구매매출", "sum"),
                     채널=("채널", "first")))

    ref = agg_by_day(d_ref).set_index("캠페인")
    ref["CPA"] = ref["비용"] / ref["회원가입"].replace(0, pd.NA)
    ref["ROAS"] = ref["구매매출"] / ref["비용"].replace(0, pd.NA) * 100

    prev = agg_by_day(d_prev).set_index("캠페인")
    prev["CPA"] = prev["비용"] / prev["회원가입"].replace(0, pd.NA)
    prev["ROAS"] = prev["구매매출"] / prev["비용"].replace(0, pd.NA) * 100

    week = None
    if d_week is not None:
        week = agg_by_day(d_week).set_index("캠페인")
        week["CPA"] = week["비용"] / week["회원가입"].replace(0, pd.NA)
        week["ROAS"] = week["구매매출"] / week["비용"].replace(0, pd.NA) * 100

    def pct_change(a, b):
        if pd.isna(a) or pd.isna(b) or b == 0:
            return None
        return float((a - b) / b * 100)

    rows = []
    for camp in ref.index:
        r = ref.loc[camp]
        p = prev.loc[camp] if camp in prev.index else None
        w = week.loc[camp] if (week is not None and camp in week.index) else None

        cpa_vs_d2 = pct_change(r["CPA"], p["CPA"]) if p is not None else None
        roas_vs_d2 = pct_change(r["ROAS"], p["ROAS"]) if p is not None else None
        cpa_vs_d8 = pct_change(r["CPA"], w["CPA"]) if w is not None else None
        roas_vs_d8 = pct_change(r["ROAS"], w["ROAS"]) if w is not None else None

        sev = _classify(cpa_vs_d2, roas_vs_d2, cfg) if p is not None else "new"

        rows.append({
            "캠페인": camp,
            "채널": r["채널"],
            "CPA_ref": r["CPA"],
            "ROAS_ref": r["ROAS"],
            "비용_ref": r["비용"],
            "회원가입_ref": r["회원가입"],
            "CPA_d1_vs_d2": cpa_vs_d2,
            "ROAS_d1_vs_d2": roas_vs_d2,
            "CPA_d1_vs_d8": cpa_vs_d8,
            "ROAS_d1_vs_d8": roas_vs_d8,
            "severity": sev,
        })

    out = pd.DataFrame(rows)
    # Sort key: severity rank (lower = worse) × cost impact desc
    sev_rank = {"critical": 0, "warning": 1, "new": 2, "improved": 3, "normal": 4}
    out["_sev_rank"] = out["severity"].map(sev_rank)
    out = out.sort_values(["_sev_rank", "비용_ref"], ascending=[True, False]).drop(columns=["_sev_rank"])
    return out.reset_index(drop=True)


def detect_subdrill(
    merged: pd.DataFrame,
    campaign: str,
    cfg: AnomalyConfig | None = None,
) -> pd.DataFrame:
    """Return group→creative breakdown for one campaign, with same delta cols."""
    cfg = cfg or AnomalyConfig()
    if merged.empty:
        return pd.DataFrame()
    sub = merged[merged["캠페인"] == campaign].copy()
    if sub.empty:
        return pd.DataFrame()

    dates = sorted(sub["날짜"].dropna().unique())
    if len(dates) < 2:
        return pd.DataFrame()

    d_ref = dates[-1]
    d_prev = dates[-2]
    d_week = dates[-8] if len(dates) >= 8 else None

    def agg_at_level(day, levels):
        s = sub[sub["날짜"] == day]
        g = s.groupby(levels, as_index=False).agg(
            비용=("비용", "sum"),
            회원가입=("회원가입", "sum"),
            구매매출=("구매매출", "sum"),
        )
        g["CPA"] = g["비용"] / g["회원가입"].replace(0, pd.NA)
        g["ROAS"] = g["구매매출"] / g["비용"].replace(0, pd.NA) * 100
        return g

    rows = []
    for level_name, level_cols in [("그룹", ["그룹"]), ("소재", ["그룹", "소재"])]:
        ref = agg_at_level(d_ref, level_cols)
        prev = agg_at_level(d_prev, level_cols)
        week = agg_at_level(d_week, level_cols) if d_week is not None else None

        key_cols = level_cols
        for _, r in ref.iterrows():
            mask_prev = (prev[key_cols] == r[key_cols].values).all(axis=1)
            p = prev[mask_prev].iloc[0] if mask_prev.any() else None
            mask_week = (week[key_cols] == r[key_cols].values).all(axis=1) if week is not None else None
            w = week[mask_week].iloc[0] if (week is not None and mask_week.any()) else None

            def pct(a, b):
                if pd.isna(a) or pd.isna(b) or b == 0: return None
                return float((a - b) / b * 100)

            rows.append({
                "level": level_name,
                "그룹": r.get("그룹", ""),
                "소재": r.get("소재", ""),
                "CPA_ref": r["CPA"],
                "비용_ref": r["비용"],
                "CPA_vs_d2": pct(r["CPA"], p["CPA"]) if p is not None else None,
                "CPA_vs_d8": pct(r["CPA"], w["CPA"]) if w is not None else None,
            })

    return pd.DataFrame(rows)


def summary_counts(anomaly_df: pd.DataFrame) -> dict:
    """Count by severity tag for the summary chips."""
    if anomaly_df.empty:
        return {"critical": 0, "warning": 0, "normal": 0, "improved": 0, "new": 0}
    return anomaly_df["severity"].value_counts().to_dict()
