"""📈 추세 탭 — CPA/ROAS/CTR/CVR 시계열, 채널별 라인."""
from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st


METRIC_OPTIONS = {
    "CPA": ("비용", "회원가입", "원", lambda c, s: c / s.replace(0, pd.NA)),
    "ROAS": ("구매매출", "비용", "%",
             lambda r, c: r / c.replace(0, pd.NA) * 100),
    "CTR": ("클릭", "노출", "%",
            lambda c, i: c / i.replace(0, pd.NA) * 100),
    "CVR": ("회원가입", "클릭", "%",
            lambda s, c: s / c.replace(0, pd.NA) * 100),
}


def render(merged: pd.DataFrame):
    st.subheader("📈 추세 분석")

    if merged.empty:
        st.warning("데이터가 없습니다.")
        return

    dates = sorted(merged["날짜"].dropna().unique())
    if len(dates) < 2:
        st.info("최소 2일치 데이터가 필요합니다.")
        return

    # Controls
    c1, c2, c3 = st.columns([1, 1, 2])
    metric_name = c1.radio("지표", list(METRIC_OPTIONS.keys()), horizontal=True)
    range_days = c2.radio("기간", [7, 14, 30], horizontal=True, format_func=lambda d: f"{d}일")
    breakdown = c3.radio("분해 기준", ["채널", "캠페인목적", "(없음)"], horizontal=True)

    # Filter to last N days
    cutoff = dates[-1] - pd.Timedelta(days=range_days - 1)
    cutoff_date = cutoff if hasattr(cutoff, "date") else cutoff
    try:
        cutoff_date = cutoff_date.date()  # type: ignore
    except Exception:
        pass
    df = merged[merged["날짜"] >= cutoff_date].copy()

    if df.empty:
        st.info(f"최근 {range_days}일 데이터 없음")
        return

    num_col, den_col, unit, formula = METRIC_OPTIONS[metric_name]
    group_cols = ["날짜"] if breakdown == "(없음)" else ["날짜", breakdown]
    agg = df.groupby(group_cols, as_index=False).agg(
        {num_col: "sum", den_col: "sum"}
    )
    agg[metric_name] = formula(agg[num_col], agg[den_col])

    color_arg = breakdown if breakdown != "(없음)" else None
    fig = px.line(agg, x="날짜", y=metric_name, color=color_arg,
                  markers=True,
                  title=f"{metric_name} ({unit}) — 최근 {range_days}일")
    fig.update_layout(height=420, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # Quick stats below
    st.markdown("**기간 요약**")
    quick = df.groupby("날짜", as_index=False).agg(
        비용=("비용", "sum"),
        클릭=("클릭", "sum"),
        노출=("노출", "sum"),
        회원가입=("회원가입", "sum"),
        구매매출=("구매매출", "sum"),
    )
    quick["CPA"] = (quick["비용"] / quick["회원가입"].replace(0, pd.NA)).round(0)
    quick["ROAS"] = (quick["구매매출"] / quick["비용"].replace(0, pd.NA) * 100).round(1)
    quick["CTR"] = (quick["클릭"] / quick["노출"].replace(0, pd.NA) * 100).round(2)
    st.dataframe(
        quick[["날짜", "비용", "클릭", "회원가입", "CPA", "ROAS", "CTR"]],
        hide_index=True, use_container_width=True,
    )
