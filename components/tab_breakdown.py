"""🧩 분해 탭 — 임의 차원으로 슬라이싱 + Top N + CSV 다운로드."""
from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st


DIM_OPTIONS = ["채널", "캠페인", "캠페인목적", "그룹", "소재"]
SORT_OPTIONS = {
    "비용 (높은 순)": ("비용", False),
    "ROAS (높은 순)": ("ROAS", False),
    "CPA (낮은 순)": ("CPA", True),
    "회원가입 (높은 순)": ("회원가입", False),
}


def render(merged: pd.DataFrame):
    st.subheader("🧩 차원 분해 분석")

    if merged.empty:
        st.warning("데이터가 없습니다.")
        return

    # Controls
    c1, c2, c3 = st.columns([2, 1.2, 1])
    dims = c1.multiselect("분해 차원 (조합 가능)", DIM_OPTIONS, default=["채널"])
    sort_label = c2.selectbox("정렬", list(SORT_OPTIONS.keys()))
    top_n = c3.selectbox("Top N", [5, 10, 20, 50, "전체"], index=1)

    if not dims:
        st.info("최소 1개 차원을 선택하세요.")
        return

    # Optional date filter — limit to reference day or recent range
    dates = sorted(merged["날짜"].dropna().unique())
    if len(dates) > 1:
        use_recent = st.checkbox(
            f"최근 7일 누적으로 집계 ({dates[-7] if len(dates) >= 7 else dates[0]} ~ {dates[-1]})",
            value=False,
        )
        if use_recent:
            cutoff = dates[-7] if len(dates) >= 7 else dates[0]
            df = merged[merged["날짜"] >= cutoff].copy()
        else:
            df = merged[merged["날짜"] == dates[-1]].copy()
    else:
        df = merged.copy()

    # Aggregate
    agg = df.groupby(dims, as_index=False).agg(
        비용=("비용", "sum"),
        노출=("노출", "sum"),
        클릭=("클릭", "sum"),
        회원가입=("회원가입", "sum"),
        구매=("구매", "sum"),
        구매매출=("구매매출", "sum"),
    )
    agg["CTR (%)"] = (agg["클릭"] / agg["노출"].replace(0, pd.NA) * 100).round(2)
    agg["CPA (원)"] = (agg["비용"] / agg["회원가입"].replace(0, pd.NA)).round(0)
    agg["ROAS (%)"] = (agg["구매매출"] / agg["비용"].replace(0, pd.NA) * 100).round(0)

    sort_col, ascending = SORT_OPTIONS[sort_label]
    sort_key = "비용" if sort_col == "비용" else (
        "CPA (원)" if sort_col == "CPA" else (
            "ROAS (%)" if sort_col == "ROAS" else "회원가입"
        )
    )
    agg = agg.sort_values(sort_key, ascending=ascending, na_position="last")
    if top_n != "전체":
        agg = agg.head(int(top_n))

    # Table
    st.dataframe(
        agg[dims + ["비용", "노출", "클릭", "회원가입", "구매매출",
                    "CTR (%)", "CPA (원)", "ROAS (%)"]],
        hide_index=True, use_container_width=True,
    )

    # Bar chart for top entries (only 1 dim or join 2 dims into string)
    if len(agg) > 0:
        if len(dims) == 1:
            agg_chart = agg.head(15).copy()
            fig = px.bar(
                agg_chart.sort_values("비용"),
                x="비용", y=dims[0], orientation="h",
                title=f"비용 분포 (Top {min(15, len(agg))})",
                text_auto=".2s",
            )
            fig.update_layout(height=400, margin=dict(l=8, r=8, t=40, b=8))
            st.plotly_chart(fig, use_container_width=True)
        else:
            # combine dims into label
            agg_chart = agg.head(15).copy()
            agg_chart["_label"] = agg_chart[dims].astype(str).agg(" | ".join, axis=1)
            fig = px.bar(
                agg_chart.sort_values("비용"),
                x="비용", y="_label", orientation="h",
                title=f"비용 분포 (Top {min(15, len(agg))})",
                text_auto=".2s",
            )
            fig.update_layout(height=400, margin=dict(l=8, r=8, t=40, b=8),
                              yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    # CSV download
    csv_bytes = agg.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 현재 뷰 CSV 다운로드", csv_bytes,
                       f"breakdown_{'_'.join(dims)}.csv", "text/csv")
