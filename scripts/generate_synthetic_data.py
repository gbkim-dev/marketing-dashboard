"""
Generate 8 days of synthetic marketing data based on the 2025-01-01 sample.
Creates data/2024-12-25 through data/2025-01-01 with realistic variance.
Injects 1-2 deliberate anomalies so the dashboard can demonstrate features.

Run: python scripts/generate_synthetic_data.py
Idempotent: overwrites existing synthetic days (will NOT touch 2025-01-01 source).
"""
from __future__ import annotations
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
SOURCE_DATE = date(2025, 1, 1)
DAYS_BEFORE = 7   # 2024-12-25 ~ 2024-12-31 (clean baselines before source)
DAYS_AFTER = 1    # 2025-01-02 (the "reference day" with anomaly injected)


def jitter(value: int, *, frac: float = 0.15) -> int:
    """Return value perturbed by ±frac. Floor at 1 to avoid zeros."""
    noise = random.uniform(-frac, frac)
    return max(1, int(round(value * (1 + noise))))


def shift_row(row: pd.Series, new_date: str, *, factor: float = 1.0) -> pd.Series:
    """Clone a row with new date and metric jitter. `factor` lets us simulate
    week-over-week drift (e.g. 0.85 = 15% cheaper performance)."""
    out = row.copy()
    out["일"] = new_date
    for col in ["노출", "클릭", "비용", "회원가입", "구매", "구매매출"]:
        if col in out.index:
            out[col] = jitter(int(out[col] * factor), frac=0.18)
    return out


def main() -> None:
    random.seed(20250101)  # deterministic

    src_dir = DATA_DIR / SOURCE_DATE.isoformat()
    if not src_dir.exists():
        print(f"[!] Source folder not found: {src_dir}")
        return

    ch_src = pd.read_csv(src_dir / "channel.csv", encoding="utf-8-sig")
    af_src = pd.read_csv(src_dir / "appsflyer.csv", encoding="utf-8-sig")

    # The "reference day" = latest generated day = SOURCE_DATE + DAYS_AFTER.
    # Anomaly is injected on that day so the dashboard's anomaly tab shows
    # critical alerts (CPA UP / ROAS DOWN compared to clean baselines).
    reference_day = (SOURCE_DATE + timedelta(days=DAYS_AFTER)).isoformat()

    # Generate clean baseline days BEFORE source (2024-12-25 ~ 2024-12-31)
    for offset in range(DAYS_BEFORE, 0, -1):
        target = (SOURCE_DATE - timedelta(days=offset)).isoformat()
        # Slight weekly drift — older days slightly worse performance
        drift_factor = 1.0 + (offset - 4) * 0.02

        out_dir = DATA_DIR / target
        out_dir.mkdir(parents=True, exist_ok=True)

        ch_rows = [shift_row(r, target, factor=drift_factor) for _, r in ch_src.iterrows()]
        ch_df = pd.DataFrame(ch_rows)
        ch_df.to_csv(out_dir / "channel.csv", index=False, encoding="utf-8-sig")

        af_rows = [shift_row(r, target, factor=drift_factor) for _, r in af_src.iterrows()]
        af_df = pd.DataFrame(af_rows)
        # AF attribution gap (~15-20% lower than channel report)
        for col in ["클릭", "회원가입", "구매", "구매매출"]:
            if col in af_df.columns:
                af_df[col] = (af_df[col] * random.uniform(0.78, 0.88)).astype(int).clip(lower=1)
        af_df.to_csv(out_dir / "appsflyer.csv", index=False, encoding="utf-8-sig")

        print(f"  ✓ {target}/  (baseline)")

    # Generate FUTURE day(s) WITH anomaly — this becomes the reference day
    for offset in range(1, DAYS_AFTER + 1):
        target = (SOURCE_DATE + timedelta(days=offset)).isoformat()
        out_dir = DATA_DIR / target
        out_dir.mkdir(parents=True, exist_ok=True)

        ch_rows = [shift_row(r, target, factor=1.02) for _, r in ch_src.iterrows()]
        ch_df = pd.DataFrame(ch_rows)

        if target == reference_day:
            # Anomaly 1: GGL_CMP_03_첫구매 — CPA exploded (cost up, conversions down)
            mask1 = ch_df["캠페인"] == "GGL_CMP_03_첫구매"
            ch_df.loc[mask1, "비용"] = (ch_df.loc[mask1, "비용"] * 1.55).astype(int)
            ch_df.loc[mask1, "회원가입"] = (ch_df.loc[mask1, "회원가입"] * 0.45).astype(int).clip(lower=1)
            ch_df.loc[mask1, "구매"] = (ch_df.loc[mask1, "구매"] * 0.55).astype(int).clip(lower=1)
            ch_df.loc[mask1, "구매매출"] = (ch_df.loc[mask1, "구매매출"] * 0.50).astype(int)

            # Anomaly 2 (warning level): META_CMP_03_재구매 — modest worsening
            mask2 = ch_df["캠페인"] == "META_CMP_03_재구매"
            ch_df.loc[mask2, "비용"] = (ch_df.loc[mask2, "비용"] * 1.20).astype(int)
            ch_df.loc[mask2, "회원가입"] = (ch_df.loc[mask2, "회원가입"] * 0.78).astype(int).clip(lower=1)

        ch_df.to_csv(out_dir / "channel.csv", index=False, encoding="utf-8-sig")

        af_rows = [shift_row(r, target, factor=1.02) for _, r in af_src.iterrows()]
        af_df = pd.DataFrame(af_rows)
        for col in ["클릭", "회원가입", "구매", "구매매출"]:
            if col in af_df.columns:
                af_df[col] = (af_df[col] * random.uniform(0.78, 0.88)).astype(int).clip(lower=1)

        if target == reference_day:
            mask1 = af_df["캠페인"] == "GGL_CMP_03_첫구매"
            af_df.loc[mask1, "회원가입"] = (af_df.loc[mask1, "회원가입"] * 0.50).astype(int).clip(lower=1)
            af_df.loc[mask1, "구매"] = (af_df.loc[mask1, "구매"] * 0.60).astype(int).clip(lower=1)

        af_df.to_csv(out_dir / "appsflyer.csv", index=False, encoding="utf-8-sig")
        print(f"  ✓ {target}/  (reference day with anomalies)")

    print(f"\n[DONE] Generated {DAYS_BEFORE} baseline days + {DAYS_AFTER} reference day.")
    print(f"       Reference day: {reference_day}")
    print(f"       Critical anomaly: GGL_CMP_03_첫구매 (CPA +205% expected)")
    print(f"       Warning anomaly: META_CMP_03_재구매 (CPA +54% expected)")
    print(f"\n  Total daily folders now:")
    for d in sorted(DATA_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            print(f"    {d.name}/")


if __name__ == "__main__":
    main()
