# 📊 마케팅 성과 대시보드

> ⚠️ **본 레포는 Claude Code 교육용 TEST 프로젝트입니다.**
> 실제 운영 환경이 아니며, 데이터는 모두 워크샵용 합성 샘플(구글·메타·네이버 가상 캠페인)입니다.
> 실제 광고주 데이터를 절대 포함하지 않습니다.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gbkim-dev-marketing-dashboard-app-dcajy3.streamlit.app/)
![Status](https://img.shields.io/badge/status-EDUCATIONAL_TEST-orange)
![Built with](https://img.shields.io/badge/built_with-Claude_Code-blueviolet)

🌐 **라이브 데모**: https://gbkim-dev-marketing-dashboard-app-dcajy3.streamlit.app/

채널 데이터 + AppsFlyer 어트리뷰션을 자동 조인해서 **"매일 아침 따져봐야 할 캠페인"**을 30초 안에 잡아내는 Streamlit 대시보드.

> **만든 배경**: 매드업 X Claude Code 워크샵 교육 산출물.
> 워크샵 토픽 1번(데이터 분석 & 대시보드)을 자연어 지시만으로 Claude Code가 실제 코드로 구현한 버전.

## 🎓 교육용 프로젝트 안내

| 항목 | 내용 |
|------|------|
| **목적** | Claude Code로 마케팅 자동화 가능성 시연 |
| **상태** | TEST · 실제 운영용 X |
| **데이터** | 모두 합성·가상 캠페인 (개인정보·실제 매체 데이터 없음) |
| **제작 방식** | 자연어 브레인스토밍 → 디자인 스펙 → 코드 자동 생성 |
| **소요 시간** | 약 2시간 (브레인스토밍 30분 + 구현·검증 1.5시간) |

본 프로젝트는 **"자연어로 부탁만 하면 마케팅 자동화 도구를 만들 수 있다"** 는 워크샵 주제를 증명하기 위한 데모입니다. 실제 광고주 데이터로 운영하려면 별도 fork + 데이터 검증 + 보안 점검이 필요합니다.

---

## 🎯 핵심 기능

| 탭 | 역할 |
|----|------|
| 🚨 **이상 신호** | 캠페인 단위 급변 자동 감지 + 그룹·소재 드릴다운 |
| 📊 **요약** | 전일 종합 KPI 8개 + 채널 분포 + 어트리뷰션 갭 |
| 📈 **추세** | CPA/ROAS/CTR/CVR 시계열 (7/14/30일) |
| 🧩 **분해** | 임의 차원 슬라이싱 + CSV 다운로드 |

### 이상 신호 감지 로직

- **베이스라인**: 전일(D-2) + 전주 동요일(D-8) 듀얼 비교
- **심각도**:
  - 🚨 **심각** — CPA +30%↑ 또는 ROAS -30%↓
  - ⚠️ **주의** — CPA +15~30% 또는 ROAS -15~-30%
  - 📈 **개선** — 반대 방향 큰 변화
  - ✅ **정상** — 변화 ±15% 이내
- **정렬**: 심각도 → 비용 영향 큰 순 (예산 손실 우선)
- **임계치**: 사이드바에서 조정 가능

---

## 🚀 로컬 실행

```bash
git clone https://github.com/<your-username>/marketing-dashboard.git
cd marketing-dashboard
pip install -r requirements.txt
streamlit run app.py
```

→ http://localhost:8501

---

## 📁 데이터 구조

```
data/
├── 2024-12-25/
│   ├── channel.csv         # 매체 보고 데이터
│   └── appsflyer.csv       # AppsFlyer 어트리뷰션
├── 2024-12-26/
│   └── ...
└── 2025-01-02/
    └── ...
```

**매일 작업 흐름:**
1. 채널·AF CSV 받기
2. `data/YYYY-MM-DD/` 폴더 만들고 `channel.csv`·`appsflyer.csv` 떨어뜨림
3. 브라우저 새로고침 (60초 캐시)

### 컬럼 표준

| 파일 | 컬럼 |
|------|------|
| channel.csv | 일·채널·채널분류·캠페인·캠페인목적·그룹·소재·노출·클릭·비용·회원가입·구매·구매매출 |
| appsflyer.csv | 일·미디어소스·캠페인·그룹·소재·클릭·회원가입·구매·구매매출 |

**조인 키**: 일 + 캠페인 + 그룹 + 소재 (4-key)

---

## 🎨 네이밍 컨벤션

### 캠페인 prefix → 채널 자동 매핑
- `GGL_*` → 구글
- `META_*` / `FB_*` → 메타
- `NVR_*` → 네이버
- `KKO_*` → 카카오
- `TT_*` → 틱톡

새 매체 추가: `lib/loader.py`의 `CHANNEL_PREFIX_MAP` 에 등록.

### 소재 타입 prefix
- `VID_*` 비디오 / `IMG_*` 이미지 / `CRS_*` 캐러셀 / `TXT_*` 텍스트

---

## 🏗 프로젝트 구조

```
marketing-dashboard/
├── app.py                       # Streamlit 라우터 (4탭)
├── lib/
│   ├── loader.py                # CSV 스캔·조인·캐싱
│   └── anomaly.py               # 베이스라인 비교·심각도
├── components/
│   ├── tab_anomaly.py           # 🚨 이상 신호
│   ├── tab_summary.py           # 📊 요약
│   ├── tab_trend.py             # 📈 추세
│   └── tab_breakdown.py         # 🧩 분해
├── scripts/
│   └── generate_synthetic_data.py  # 합성 데이터 생성기
├── docs/
│   └── superpowers/specs/       # 디자인 스펙
├── data/                        # 일별 CSV
└── requirements.txt
```

---

## 🌐 Streamlit Cloud 배포

1. https://share.streamlit.io 접속 (GitHub 로그인)
2. **New app** → 본 레포 선택
3. Main file: `app.py`
4. Deploy 클릭 → 약 2분 후 공개 URL 발급

### 첫 배포 시 주의
- `requirements.txt` 의존성 자동 설치
- `data/` 폴더 그대로 포함되어 샘플 대시보드 즉시 작동
- 실제 광고주 데이터로 바꾸려면 → 본인 워크스페이스에 별도 fork 후 데이터 교체

---

## 📜 라이선스 / 출처

- 매드업 X Claude Code 워크샵 산출물
- 데이터는 워크샵용 합성 샘플 (실제 광고주 데이터 아님)
- MIT 라이선스 적용 가능 (필요 시 추가)
