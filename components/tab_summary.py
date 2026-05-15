"""📊 요약 탭 — 전일 종합 KPI 카드 + 채널 분포 + 어트리뷰션 갭."""
from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st


def _fmt_num(n, suffix=""):
    if pd.isna(n) or n is None:
        return "-"
    if abs(n) >= 1e8:
        return f"{n/1e8:.2f}억{suffix}"
    if abs(n) >= 1e4:
        return f"{n/1e4:.1f}만{suffix}"
    return f"{n:,.0f}{suffix}"


def _pct_delta(curr: float, prev: float) -> str:
    if prev == 0 or pd.isna(prev) or pd.isna(curr):
        return ""
    pct = (curr - prev) / prev * 100
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "")
    return f"{pct:+.1f}% {arrow}"


def render(merged: pd.DataFrame):
    st.subheader("📊 일일 종합 KPI")

    if merged.empty:
        st.warning("데이터가 없습니다.")
        return

    dates = sorted(merged["날짜"].dropna().unique())
    ref_day = dates[-1]
    prev_day = dates[-2] if len(dates) >= 2 else None

    ref = merged[merged["날짜"] == ref_day]
    prev = merged[merged["날짜"] == prev_day] if prev_day else None

    st.caption(
        f"기준일: **{ref_day}** "
        + (f"· 전일 비교: **{prev_day}**" if prev_day else "· (전일 데이터 없음)")
    )

    # ─── KPI cards (8) ───
    def metric(col, label, curr, prev_val, formatter, suffix=""):
        delta = _pct_delta(curr, prev_val) if prev_val is not None else ""
        col.metric(label, formatter(curr, suffix), delta if delta else None)

    cost = ref["비용"].sum()
    imp = ref["노출"].sum()
    clk = ref["클릭"].sum()
    sign = ref["회원가입"].sum() if "회원가입" in ref else 0
    rev = ref["구매매출"].sum() if "구매매출" in ref else 0

    ctr = (clk / imp * 100) if imp else 0
    cpc = (cost / clk) if clk else 0
    cpa = (cost / sign) if sign else 0
    roas = (rev / cost * 100) if cost else 0

    prev_cost = prev["비용"].sum() if prev is not None else None
    prev_imp = prev["노출"].sum() if prev is not None else None
    prev_clk = prev["클릭"].sum() if prev is not None else None
    prev_sign = prev["회원가입"].sum() if prev is not None and "회원가입" in prev else None
    prev_rev = prev["구매매출"].sum() if prev is not None and "구매매출" in prev else None
    prev_ctr = (prev_clk / prev_imp * 100) if prev_imp else None
    prev_cpc = (prev_cost / prev_clk) if prev_clk else None
    prev_cpa = (prev_cost / prev_sign) if prev_sign else None
    prev_roas = (prev_rev / prev_cost * 100) if prev_cost else None

    r1 = st.columns(4)
    metric(r1[0], "💸 총 비용", cost, prev_cost, _fmt_num, "원")
    metric(r1[1], "👀 총 노출", imp, prev_imp, _fmt_num)
    metric(r1[2], "🖱️ 총 클릭", clk, prev_clk, _fmt_num)
    metric(r1[3], "📈 CTR (%)", ctr, prev_ctr, lambda v, _: f"{v:.2f}%")

    r2 = st.columns(4)
    metric(r2[0], "💰 CPC", cpc, prev_cpc, lambda v, _: f"{v:,.0f}원")
    metric(r2[1], "🎯 CPA (회원가입)", cpa, prev_cpa, lambda v, _: f"{v:,.0f}원")
    metric(r2[2], "🛒 회원가입", sign, prev_sign, _fmt_num)
    metric(r2[3], "💎 ROAS", roas, prev_roas, lambda v, _: f"{v:,.0f}%")

    st.markdown("---")

    # ─── Channel cost distribution ───
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**채널별 비용 분포**")
        by_ch = ref.groupby("채널", as_index=False).agg(비용=("비용", "sum"))
        if not by_ch.empty:
            fig = px.pie(by_ch, names="채널", values="비용", hole=0.5)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, height=320, margin=dict(t=8, b=8, l=8, r=8))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**채널별 ROAS·CPA**")
        ch_kpi = ref.groupby("채널", as_index=False).agg(
            비용=("비용", "sum"),
            회원가입=("회원가입", "sum"),
            구매매출=("구매매출", "sum"),
        )
        ch_kpi["CPA"] = (ch_kpi["비용"] / ch_kpi["회원가입"].replace(0, pd.NA)).round(0)
        ch_kpi["ROAS"] = (ch_kpi["구매매출"] / ch_kpi["비용"].replace(0, pd.NA) * 100).round(0)
        st.dataframe(ch_kpi[["채널", "비용", "CPA", "ROAS"]],
                     hide_index=True, use_container_width=True)

    # ─── Attribution gap callout ───
    if "회원가입_AF" in ref.columns:
        sign_af = ref["회원가입_AF"].sum()
        if sign > 0:
            gap_pct = (sign - sign_af) / sign * 100
            if abs(gap_pct) > 5:
                st.markdown(
                    f"""<div style="background:#fef3c7;padding:14px 18px;border-radius:8px;
                                    border-left:4px solid #f59e0b;color:#78350f;margin-top:14px">
                        ⚠️ <b>어트리뷰션 갭</b> — 매체 보고 회원가입 {sign:,.0f} vs AF {sign_af:,.0f}
                        (갭 {gap_pct:+.1f}%)
                    </div>""",
                    unsafe_allow_html=True,
                )
