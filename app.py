"""
Streamlit Marketing Performance Dashboard — 4-tab redesign.

Tabs:
  1. 🚨 이상 신호 (메인)  — 캠페인 단위 급변 + 그룹·소재 드릴다운
  2. 📊 요약            — 전일 종합 KPI, 어트리뷰션 갭
  3. 📈 추세            — 메트릭 × 기간 × 차원
  4. 🧩 분해            — 임의 차원 슬라이싱 + CSV
"""
from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

# Make local 'lib' / 'components' importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from lib.loader import (
    load_channel, load_appsflyer, merge_datasets, list_data_files,
)
from lib.anomaly import AnomalyConfig
from components import tab_anomaly, tab_summary, tab_trend, tab_breakdown

DATA_DIR = ROOT / "data"

st.set_page_config(
    page_title="마케팅 성과 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Light CSS polish
st.markdown("""
<style>
  .block-container {padding-top: 1.5rem; padding-bottom: 4rem; max-width: 1400px;}
  [data-testid="stMetricValue"] {font-size: 26px; font-weight: 700;}
  [data-testid="stMetricLabel"] {color: #6B7280;}
  div[data-testid="stExpander"] {background: rgba(255,255,255,0.02); border-radius: 6px; margin-top: 4px;}
</style>
""", unsafe_allow_html=True)


# ─── Data loading (cached) ───
@st.cache_data(ttl=60, show_spinner="📂 data/ 폴더 스캔 중...")
def load_all(_marker: str):  # marker so cache busts on demand
    ch = load_channel(DATA_DIR)
    af = load_appsflyer(DATA_DIR)
    merged = merge_datasets(ch, af)
    return ch, af, merged


# Mtime marker so cache invalidates when files change
def folder_signature(data_dir: Path) -> str:
    sig = []
    for p in data_dir.rglob("*.csv"):
        if any(x.startswith("_") for x in p.relative_to(data_dir).parts):
            continue
        sig.append(f"{p.name}:{p.stat().st_mtime:.0f}")
    return "|".join(sorted(sig))


ch, af, merged = load_all(folder_signature(DATA_DIR))
inv = list_data_files(DATA_DIR)

# ─── Sidebar ───
with st.sidebar:
    st.markdown("### 🔍 필터")

    if not merged.empty:
        dates_available = sorted(merged["날짜"].dropna().unique())
        if len(dates_available) > 1:
            date_range = st.date_input(
                "기간",
                value=(dates_available[0], dates_available[-1]),
                min_value=dates_available[0],
                max_value=dates_available[-1],
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                d0, d1 = date_range
                merged = merged[(merged["날짜"] >= d0) & (merged["날짜"] <= d1)].copy()

        channels_avail = sorted(merged["채널"].dropna().unique())
        selected_channels = st.multiselect(
            "채널", channels_avail, default=channels_avail,
        )
        if selected_channels:
            merged = merged[merged["채널"].isin(selected_channels)]

        campaigns_avail = sorted(merged["캠페인"].dropna().unique())
        selected_campaigns = st.multiselect(
            "캠페인 (비어두면 전체)", campaigns_avail, default=[],
        )
        if selected_campaigns:
            merged = merged[merged["캠페인"].isin(selected_campaigns)]

    st.markdown("---")
    st.markdown("### ⚙️ 이상 신호 임계치")
    cpa_w = st.slider("CPA 주의 (%)", 5, 50, 15, 1)
    cpa_c = st.slider("CPA 심각 (%)", cpa_w + 1, 100, max(30, cpa_w + 1), 1)
    roas_w = st.slider("ROAS 주의 (%)", 5, 50, 15, 1)
    roas_c = st.slider("ROAS 심각 (%)", roas_w + 1, 100, max(30, roas_w + 1), 1)
    cfg = AnomalyConfig(
        cpa_warning=cpa_w, cpa_critical=cpa_c,
        roas_warning=roas_w, roas_critical=roas_c,
    )

    st.markdown("---")
    st.markdown("### 📁 인식된 파일")
    if inv["channel_files"]:
        for f in inv["channel_files"][:6]:
            st.caption(f"📊 {f}")
        if len(inv["channel_files"]) > 6:
            st.caption(f"_… 외 {len(inv['channel_files']) - 6}개_")
    if inv["appsflyer_files"]:
        for f in inv["appsflyer_files"][:6]:
            st.caption(f"📱 {f}")
        if len(inv["appsflyer_files"]) > 6:
            st.caption(f"_… 외 {len(inv['appsflyer_files']) - 6}개_")
    st.caption(f"_총 채널 {len(inv['channel_files'])} · AF {len(inv['appsflyer_files'])} · 60초 캐시_")


# ─── Main: tabs ───
st.title("📊 마케팅 성과 대시보드")
if merged.empty:
    st.error(
        "data/ 폴더에 CSV가 없습니다.\n\n"
        "**사용법**: `data/YYYY-MM-DD/` 폴더 만들고 `channel.csv`·`appsflyer.csv` 파일 추가 → 자동 인식."
    )
    st.stop()

st.caption(
    f"📍 데이터: `{DATA_DIR.relative_to(ROOT.parent)}` · "
    f"날짜 {sorted(merged['날짜'].unique())[0]} ~ {sorted(merged['날짜'].unique())[-1]} · "
    f"행 {len(merged):,}"
)

tab1, tab2, tab3, tab4 = st.tabs([
    "🚨 이상 신호",
    "📊 요약",
    "📈 추세",
    "🧩 분해",
])

with tab1:
    tab_anomaly.render(merged, cfg)

with tab2:
    tab_summary.render(merged)

with tab3:
    tab_trend.render(merged)

with tab4:
    tab_breakdown.render(merged)
