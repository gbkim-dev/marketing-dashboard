"""🚨 이상 신호 탭 — 캠페인 단위 급변 리스트 + 그룹·소재 드릴다운."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from lib.anomaly import (
    AnomalyConfig, detect_campaign_anomalies, detect_subdrill, summary_counts,
)

SEV_STYLE = {
    "critical":  ("🚨", "심각",  "#7f1d1d", "#fef2f2", "#dc2626"),
    "warning":   ("⚠️", "주의",  "#78350f", "#fef3c7", "#f59e0b"),
    "normal":    ("✅", "정상",  "#064e3b", "#d1fae5", "#10b981"),
    "improved":  ("📈", "개선",  "#1e3a8a", "#dbeafe", "#3b82f6"),
    "new":       ("🆕", "신규",  "#4c1d95", "#ede9fe", "#8b5cf6"),
}


def _fmt_delta(pct: float | None) -> str:
    if pct is None or pd.isna(pct):
        return "—"
    sign = "▲" if pct > 0 else ("▼" if pct < 0 else "")
    return f"{pct:+.1f}% {sign}"


def _delta_color(pct: float | None, *, bad_direction: str = "up") -> str:
    """For CPA: up is bad (red). For ROAS: down is bad."""
    if pct is None or pd.isna(pct):
        return "#9ca3af"
    if bad_direction == "up":
        return "#fca5a5" if pct > 15 else ("#22c55e" if pct < -15 else "#d1d5db")
    return "#fca5a5" if pct < -15 else ("#22c55e" if pct > 15 else "#d1d5db")


def render(merged: pd.DataFrame, cfg: AnomalyConfig):
    st.subheader("🚨 이상 신호 — 캠페인 단위")

    if merged.empty:
        st.warning("데이터가 없습니다.")
        return

    dates = sorted(merged["날짜"].dropna().unique())
    if len(dates) < 2:
        st.info(
            f"베이스라인 비교를 위해 최소 2일치 데이터가 필요합니다. "
            f"현재: {len(dates)}일치 ({dates[0] if dates else '-'}). "
            f"`data/YYYY-MM-DD/` 폴더 추가하시면 이 탭이 활성화됩니다."
        )
        return

    ref_day = dates[-1]
    d2 = dates[-2]
    d8 = dates[-8] if len(dates) >= 8 else None

    st.caption(
        f"기준일 **{ref_day}** · 전일 비교 **{d2}** · "
        f"전주 동요일 비교 **{d8 if d8 else '(데이터 부족)'}**"
    )

    anomaly_df = detect_campaign_anomalies(merged, cfg)
    if anomaly_df.empty:
        st.warning("이상 신호 데이터를 계산할 수 없습니다.")
        return

    # ─── Severity summary chips ───
    counts = summary_counts(anomaly_df)
    chip_cols = st.columns(5)
    sev_order = ["critical", "warning", "new", "improved", "normal"]
    for col, sev in zip(chip_cols, sev_order):
        icon, label, _, bg, border = SEV_STYLE[sev]
        n = counts.get(sev, 0)
        col.markdown(
            f"""<div style="background:{bg};padding:10px 14px;border-radius:8px;
                            border-left:4px solid {border};text-align:center">
                <div style="font-size:11px;color:#374151;letter-spacing:1px">{icon} {label}</div>
                <div style="font-size:22px;font-weight:700;color:#111827">{n}<span style="font-size:13px;font-weight:400">건</span></div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ─── Severity filter ───
    selected_sevs = st.multiselect(
        "표시할 심각도",
        options=sev_order,
        default=["critical", "warning", "new"],
        format_func=lambda s: f"{SEV_STYLE[s][0]} {SEV_STYLE[s][1]}",
    )
    filtered = anomaly_df[anomaly_df["severity"].isin(selected_sevs)]
    if filtered.empty:
        st.info("선택한 심각도에 해당하는 캠페인이 없습니다.")
        return

    # ─── Campaign rows with inline drilldown via st.expander ───
    st.markdown("")
    if "expanded_camps" not in st.session_state:
        st.session_state["expanded_camps"] = set()

    for _, row in filtered.iterrows():
        camp = row["캠페인"]
        sev = row["severity"]
        icon, _, _, bg, border = SEV_STYLE[sev]

        # Build label: severity icon + name + key metrics
        cpa_ref = row["CPA_ref"]
        d2_pct = row["CPA_d1_vs_d2"]
        d8_pct = row["CPA_d1_vs_d8"]
        cost = row["비용_ref"]

        label_cols = st.columns([0.5, 3, 1.2, 1.2, 1.2, 1.4])
        with label_cols[0]:
            st.markdown(f"<div style='font-size:22px;text-align:center'>{icon}</div>",
                        unsafe_allow_html=True)
        with label_cols[1]:
            st.markdown(
                f"<div style='font-size:15px;font-weight:600;color:#e5e7eb;padding-top:4px'>"
                f"{camp}</div>"
                f"<div style='font-size:11px;color:#9ca3af'>채널: {row['채널']}</div>",
                unsafe_allow_html=True,
            )
        with label_cols[2]:
            st.markdown(
                f"<div style='font-size:11px;color:#9ca3af'>CPA (D-1)</div>"
                f"<div style='font-size:15px;font-weight:600;color:#e5e7eb'>"
                f"{cpa_ref:,.0f}원</div>",
                unsafe_allow_html=True,
            )
        with label_cols[3]:
            st.markdown(
                f"<div style='font-size:11px;color:#9ca3af'>vs 전일</div>"
                f"<div style='font-size:15px;font-weight:600;color:{_delta_color(d2_pct)}'>"
                f"{_fmt_delta(d2_pct)}</div>",
                unsafe_allow_html=True,
            )
        with label_cols[4]:
            st.markdown(
                f"<div style='font-size:11px;color:#9ca3af'>vs 전주</div>"
                f"<div style='font-size:15px;font-weight:600;color:{_delta_color(d8_pct)}'>"
                f"{_fmt_delta(d8_pct)}</div>",
                unsafe_allow_html=True,
            )
        with label_cols[5]:
            st.markdown(
                f"<div style='font-size:11px;color:#9ca3af'>비용 영향</div>"
                f"<div style='font-size:15px;font-weight:600;color:#e5e7eb'>"
                f"{cost:,.0f}원</div>",
                unsafe_allow_html=True,
            )

        # Drilldown via expander — show ▼ group / 소재 breakdown
        with st.expander("📂 그룹·소재 드릴다운", expanded=(sev == "critical")):
            sub = detect_subdrill(merged, camp, cfg)
            if sub.empty:
                st.caption("드릴다운 데이터 없음")
            else:
                group_rows = sub[sub["level"] == "그룹"].copy()
                creative_rows = sub[sub["level"] == "소재"].copy()

                if not group_rows.empty:
                    st.markdown("**▸ 그룹별**")
                    g_show = group_rows[["그룹", "CPA_ref", "CPA_vs_d2", "CPA_vs_d8", "비용_ref"]].copy()
                    g_show.columns = ["그룹", "CPA (원)", "vs 전일 (%)", "vs 전주 (%)", "비용 (원)"]
                    g_show["CPA (원)"] = g_show["CPA (원)"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                    g_show["vs 전일 (%)"] = g_show["vs 전일 (%)"].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
                    g_show["vs 전주 (%)"] = g_show["vs 전주 (%)"].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
                    g_show["비용 (원)"] = g_show["비용 (원)"].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(g_show, hide_index=True, use_container_width=True)

                if not creative_rows.empty:
                    st.markdown("**▸ 소재별 (Top 5 by 비용)**")
                    c_show = creative_rows.nlargest(5, "비용_ref")[
                        ["그룹", "소재", "CPA_ref", "CPA_vs_d2", "CPA_vs_d8", "비용_ref"]
                    ].copy()
                    c_show.columns = ["그룹", "소재", "CPA (원)", "vs 전일 (%)", "vs 전주 (%)", "비용 (원)"]
                    c_show["CPA (원)"] = c_show["CPA (원)"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                    c_show["vs 전일 (%)"] = c_show["vs 전일 (%)"].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
                    c_show["vs 전주 (%)"] = c_show["vs 전주 (%)"].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
                    c_show["비용 (원)"] = c_show["비용 (원)"].apply(lambda x: f"{x:,.0f}")
                    st.dataframe(c_show, hide_index=True, use_container_width=True)

        st.markdown("<hr style='margin:8px 0;border:0;border-top:1px solid #2a3142'>",
                    unsafe_allow_html=True)
