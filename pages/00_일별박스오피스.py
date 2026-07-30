import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 & 주말 vs 평일 흥행 비교 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# ---------------------------------------------------------
# 1. 날짜 계산 (어제, 지난 주말 일요일, 지난 평일 목요일)
# ---------------------------------------------------------
now = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = now - timedelta(days=1)
target_dt_yesterday = yesterday.strftime("%Y%m%d")

# 지난주 일요일 계산 (weekGb="0"은 금~일 주말 박스오피스 조회용)
# weekday(): 월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6
days_since_sunday = (yesterday.weekday() + 1) % 7
last_sunday = yesterday - timedelta(days=days_since_sunday)
target_dt_weekend = last_sunday.strftime("%Y%m%d")

# 지난주 목요일 계산 (weekGb="1"은 월~목 주중 박스오피스 조회용)
days_since_thursday = (yesterday.weekday() - 3) % 7
last_thursday = yesterday - timedelta(days=days_since_thursday)
target_dt_weekday = last_thursday.strftime("%Y%m%d")

# ---------------------------------------------------------
# 2. API 호출 공통 함수 (캐싱 적용으로 속도 개선)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_box_office(url, params):
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return None, f"요청 실패 (상태코드: {res.status_code})"
        data = res.json()
        if "faultInfo" in data:
            return None, "인증키가 올바르지 않습니다. Secrets를 확인해 주세요."
        return data, None
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 3. 데이터 로딩
# ---------------------------------------------------------
# A. 어제 일별 박스오피스
daily_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
daily_data, err = fetch_box_office(daily_url, {"key": KOBIS_KEY, "targetDt": target_dt_yesterday})

if err:
    st.error(err)
    st.stop()

daily_list = daily_data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not daily_list:
    st.warning("어제 박스오피스 데이터가 없습니다.")
    st.stop()

df_daily = pd.DataFrame(daily_list)
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df_daily[col] = pd.to_numeric(df_daily[col])

# B. 주말(금~일) & 평일(월~목) 박스오피스
weekly_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"

# 주말 (weekGb: 0 = 주말, 1 = 주중, 2 = 주간)
weekend_data, _ = fetch_box_office(weekly_url, {"key": KOBIS_KEY, "targetDt": target_dt_weekend, "weekGb": "0"})
# 평일(주중)
weekday_data, _ = fetch_box_office(weekly_url, {"key": KOBIS_KEY, "targetDt": target_dt_weekday, "weekGb": "1"})

weekend_list = weekend_data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", []) if weekend_data else []
weekday_list = weekday_data.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", []) if weekday_data else []

df_weekend = pd.DataFrame(weekend_list)
df_weekday = pd.DataFrame(weekday_list)

for df_temp in [df_weekend, df_weekday]:
    if not df_temp.empty:
        for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
            df_temp[col] = pd.to_numeric(df_temp[col])

# ---------------------------------------------------------
# 4. 화면 레이아웃 (탭 구성)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📌 어제의 박스오피스", "⚔️ 주말 vs 평일 흥행 비교"])

# ---------------------------------------------------------
# TAB 1: 어제 박스오피스 (기존 작성한 기능)
# ---------------------------------------------------------
with tab1:
    st.caption(f"조회 기준일: {yesterday.strftime('%Y-%m-%d')}")
    
    # 1위 영화 지표 카드
    top = df_daily.sort_values("rank").iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("어제 1위", top["movieNm"])
    c2.metric("어제 관객수", f"{top['audiCnt']:,}명")
    c3.metric("누적 관객", f"{top['audiAcc']:,}명")

    # 표 정리
    table_daily = df_daily[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    table_daily.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
    table_daily = table_daily.sort_values("순위").reset_index(drop=True)

    st.subheader("📋 일별 박스오피스 TOP 10")
    st.dataframe(table_daily, use_container_width=True)

    st.subheader("📈 관객수 상위 5편")
    top5_daily = table_daily.sort_values("관객수", ascending=False).head(5)
    st.bar_chart(top5_daily.set_index("영화명")["관객수"])

# ---------------------------------------------------------
# TAB 2: 주말 vs 평일 흥행 비교 (새로 추가된 기능)
# ---------------------------------------------------------
with tab2:
    st.subheader("⚔️ 최근 주말(금~일) vs 평일(월~목) 흥행 분석")
    st.caption(f"비교 대상 기준: 주말({last_sunday.strftime('%Y-%m-%d')} 주차) / 평일({last_thursday.strftime('%Y-%m-%d')} 주차)")

    if df_weekend.empty or df_weekday.empty:
        st.warning("주말 또는 평일 데이터를 불러오지 못했습니다.")
    else:
        # 요약 지표 비교
        weekend_top = df_weekend.sort_values("rank").iloc[0]
        weekday_top = df_weekday.sort_values("rank").iloc[0]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("주말 1위 영화", weekend_top["movieNm"])
        m2.metric("주말 1위 관객수", f"{weekend_top['audiCnt']:,}명")
        m3.metric("평일 1위 영화", weekday_top["movieNm"])
        m4.metric("평일 1위 관객수", f"{weekday_top['audiCnt']:,}명")

        st.divider()

        # 데이터 병합을 통한 주말 vs 평일 비교 표 생성
        df_we = df_weekend[["movieNm", "rank", "audiCnt", "scrnCnt"]].rename(
            columns={"rank": "주말순위", "audiCnt": "주말관객수", "scrnCnt": "주말스크린수"}
        )
        df_wd = df_weekday[["movieNm", "rank", "audiCnt", "scrnCnt"]].rename(
            columns={"rank": "평일순위", "audiCnt": "평일관객수", "scrnCnt": "평일스크린수"}
        )

        # 영화명 기준으로 주말/평일 성적 합치기
        df_merged = pd.merge(df_we, df_wd, on="movieNm", how="outer").fillna(0)
        
        # 순위 변동 계산 (평일 순위 - 주말 순위: 양수면 주말에 순위 상승)
        # 0점 처리된 영화는 순위 계산 시 직관적인 표시 처리
        df_merged["주말관객수"] = df_merged["주말관객수"].astype(int)
        df_merged["평일관객수"] = df_merged["평일관객수"].astype(int)

        st.write("##### 📊 주요 영화 주말/평일 관객수 비교 차트")
        # 관객수 합계 기준 상위 7개 영화 시각화
        df_merged["총관객수"] = df_merged["주말관객수"] + df_merged["평일관객수"]
        top_movies = df_merged.sort_values("총관객수", ascending=False).head(7)

        chart_data = top_movies.set_index("movieNm")[["평일관객수", "주말관객수"]]
        st.bar_chart(chart_data)

        st.write("##### 📋 주말 vs 평일 종합 비교표")
        display_df = df_merged[["movieNm", "주말순위", "주말관객수", "평일순위", "평일관객수"]].copy()
        display_df.columns = ["영화명", "주말 순위", "주말 관객수", "평일 순위", "평일 관객수"]
        
        # 보기 깔끔하게 관객수 기준 정렬
        display_df = display_df.sort_values("주말 관객수", ascending=False).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)
