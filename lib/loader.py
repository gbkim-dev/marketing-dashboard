"""
Load and merge channel + AppsFlyer CSVs from the data/ folder.
Auto-scans all CSVs matching the patterns each run, so dropping a new
daily file into data/ is enough to refresh.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

JOIN_KEYS = ["날짜", "캠페인", "그룹", "소재"]

# Campaign prefix → channel name mapping (heuristic, easily extensible)
CHANNEL_PREFIX_MAP = {
    "GGL": "구글",
    "GOOGLE": "구글",
    "MTA": "메타",
    "META": "메타",
    "FB": "메타",
    "KKO": "카카오",
    "KAKAO": "카카오",
    "NVR": "네이버",
    "NAVER": "네이버",
    "TIK": "틱톡",
    "TT": "틱톡",
}


def _infer_channel_from_campaign(campaign: str) -> str:
    if not isinstance(campaign, str):
        return "기타"
    prefix = campaign.split("_", 1)[0].upper()
    return CHANNEL_PREFIX_MAP.get(prefix, "기타")


def _read_concat(files: list[Path]) -> pd.DataFrame:
    """Read a list of CSVs and concat them. Handles UTF-8 BOM."""
    if not files:
        return pd.DataFrame()
    parts = []
    for f in files:
        df = pd.read_csv(f, encoding="utf-8-sig")
        df["_source_file"] = f.name
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def _scan(data_dir: Path, kind: str) -> list[Path]:
    """
    Find all CSVs matching `kind` ('channel' or 'appsflyer'), supporting BOTH:
      • date-folder layout: data/YYYY-MM-DD/channel.csv
      • flat layout       : data/YYYY-MM-DD_channel.csv (legacy)
    Skips files under any folder starting with '_' (archive, backup etc).
    """
    seen = set()
    files = []
    # Date-folder layout (preferred): data/**/channel.csv or data/**/appsflyer.csv
    for p in data_dir.glob(f"**/{kind}.csv"):
        if any(part.startswith("_") for part in p.relative_to(data_dir).parts):
            continue
        if p not in seen:
            seen.add(p); files.append(p)
    # Flat layout (legacy): data/*channel*.csv
    for p in data_dir.glob(f"*{kind}*.csv"):
        if p not in seen:
            seen.add(p); files.append(p)
    return sorted(files)


def load_channel(data_dir: Path) -> pd.DataFrame:
    files = _scan(data_dir, "channel")
    df = _read_concat(files)
    if df.empty:
        return df
    df = df.rename(columns={"일": "날짜"})
    df["날짜"] = pd.to_datetime(df["날짜"]).dt.date
    return df


def load_appsflyer(data_dir: Path) -> pd.DataFrame:
    files = _scan(data_dir, "appsflyer")
    df = _read_concat(files)
    if df.empty:
        return df
    df = df.rename(columns={"일": "날짜"})
    df["날짜"] = pd.to_datetime(df["날짜"]).dt.date
    # AF often has 미디어소스 — keep but also infer 채널 from 캠페인
    if "채널" not in df.columns:
        df["채널"] = df["캠페인"].apply(_infer_channel_from_campaign)
    return df


def merge_datasets(ch: pd.DataFrame, af: pd.DataFrame) -> pd.DataFrame:
    """Outer-join on date/campaign/group/creative.
    AF columns get _AF suffix; channel columns keep original names."""
    if ch.empty and af.empty:
        return pd.DataFrame()
    if ch.empty:
        return af
    if af.empty:
        return ch
    keys = JOIN_KEYS
    af_renamed = af.rename(
        columns={c: f"{c}_AF" for c in af.columns if c not in keys and c != "_source_file"}
    )
    merged = ch.merge(af_renamed, on=keys, how="outer", indicator=True)
    merged["조인_상태"] = merged["_merge"].map({
        "both": "양쪽 매치",
        "left_only": "채널만 (AF 누락)",
        "right_only": "AF만 (채널 누락)",
    })
    merged = merged.drop(columns=["_merge"])
    return merged


def list_data_files(data_dir: Path) -> dict:
    """Inventory of CSVs currently in the data folder.
    Returns paths relative to data_dir (e.g. '2025-01-01/channel.csv')."""
    ch = [str(f.relative_to(data_dir)).replace("\\", "/") for f in _scan(data_dir, "channel")]
    af = [str(f.relative_to(data_dir)).replace("\\", "/") for f in _scan(data_dir, "appsflyer")]
    return {"channel_files": ch, "appsflyer_files": af}
