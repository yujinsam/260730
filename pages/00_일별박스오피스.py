import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 & 주말 vs 평일 흥행 비교 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# ---------------------------------------------------------
# 1. 날짜 설정 (달력 선택 기능 추가)
# ---------------------------------------------------------
now = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday_dt = (now - timedelta(days=1)).date()

# 사이드바에서 날짜 선택 (최대 어제 날짜까지 선택 가능)
selected_date = st.sidebar.date_input(
    "📅 박스오피스 날짜 선택",
    value=yesterday_dt,
    max_value=yesterday_dt,
    help="오늘 날짜 이후는 집계 전이므로 어제 날짜까지만 선택 가능합니다."
)

target_dt_selected = selected_date.strftime("%Y%m%d")

# 선택한 날짜 기준 주말(일요일) 및 평일(목요일) 계산
selected_datetime = datetime.combine(selected_date, datetime.min.time())
days_since_sunday = (selected_datetime.weekday() + 1) % 7
last_sunday = selected_datetime - timedelta(days=days_since_sunday)
target_dt_weekend = last_sunday.strftime("%Y%m%d")

days_since_thursday = (selected_datetime.weekday() - 3) % 7
last_thursday = selected_datetime - timedelta(days=days_since_thursday)
target_dt_weekday = last_thursday.strftime("%Y%m%d")

# ---------------------------------------------------------
# 2. API 호출 공통 함수 (캐싱 적용)
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

# 영화 상세정보 API 연동 함수
@st.cache_data(ttl=86400)
def fetch_movie_detail(movie_code):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
    data, err = fetch_box_office(url, {"key": KOBIS_KEY, "movieCd": movie_code})
    if data and "movieInfoResult" in data:
        return data["movieInfoResult"]["movieInfo"]
    return None

# 영화 상세정보 대화상자(팝업)
@st.dialog("🎬 영화 상세 정보")
def show_movie_detail_dialog(movie_cd):
    with st.spinner("영화 정보를 가져오는 중..."):
        info = fetch_movie_detail(movie_cd)
    
    if not info:
        st.error("상세 정보를 불러올 수 없습니다.")
        return

    st.subheader(info.get("movieNm", "영화명 정보 없음"))
    if info.get("movieNmEn"):
        st.caption(f"영문명: {info.get('movieNmEn')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**상영 시간:** {info.get('showTm', '-')}분")
        st.markdown(f"**개봉일:** {info.get('openDt', '-')}")
        genres = ", ".join([g["genreNm"] for g in info.get("genres", [])])
        st.markdown(f"**장르:** {genres if genres else '-'}")
        
    with col2:
        nations = ", ".join([n["nationNm"] for n in info.get("nations", [])])
        st.markdown(f"**제작 국가:** {nations if nations else '-'}")
        audits = ", ".join([a["watchGradeNm"] for a in info.get("audits", [])])
        st.markdown(f"**관람 등급:** {audits if audits else '-'}")
        directors = ", ".join([d["peopleNm"] for d in info.get("directors", [])])
        st.markdown(f"**감독:** {directors if directors else '-'}")

    st.divider()
    st.markdown("##### 🎭 주요 출연진")
    actors = info.get("actors", [])
    if actors:
        actor_names = [f"{a['peopleNm']}" + (f" ({a['cast']} 역)" if a.get('cast') else "") for a in actors[:10]]
        st.write(", ".join(actor_names))
        if len(actors) > 10:
            st.caption(f"외 {len(actors) - 10}명")
    else:
        st.write("출연진 정보가 없습니다.")

    st.divider()
    companys = info.get("companys", [])
    if companys:
        comp_list = [f"{c['companyNm']} ({c['companyPartNm']})" for c in companys[:5]]
        st.caption("제작/배급사: " + ", ".join(comp_list))

# ---------------------------------------------------------
# 3. 데이터 로딩
# ---------------------------------------------------------
# A. 선택한 날짜 일별 박스오피스
daily_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
daily_data, err = fetch_box_office(daily_url, {"key": KOBIS_KEY, "targetDt": target_dt_selected})

if err:
    st.error(err)
    st.stop()

daily_list = daily_data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# B. 주말(금~일) & 평일(월~목) 박스오피스
weekly_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"
weekend_data, _ = fetch_box_office(weekly_url, {"key": KOBIS_KEY, "targetDt": target_dt_weekend, "weekGb": "0"})
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
tab1, tab2 = st.tabs(["📌 일별 박스오피스", "⚔️ 주말 vs 평일 흥행 비교"])

# ---------------------------------------------------------
# TAB 1: 선택한 날짜 박스오피스
# ---------------------------------------------------------
with tab1:
    st.caption(f"조회 기준일: {selected_date.strftime('%Y년 %m월 %d일')}")
    
    # 예외 처리: 데이터가 비어 있는 경우
    if not daily_list:
        st.warning("그날은 아직 집계 전입니다.")
    else:
        df_daily = pd.DataFrame(daily_list)
        for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
            df_daily[col] = pd.to_numeric(df_daily[col])

        # 1위 영화 지표 카드
        top = df_daily.sort_values("rank").iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("1위 영화", top["movieNm"])
        c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
        c3.metric("누적 관객", f"{top['audiAcc']:,}명")

        st.subheader("📋 박스오피스 TOP 10")
        st.info("💡 영화명을 선택하여 상세 정보를 볼 수 있습니다. (🏆: 누적관객 100만 이상)")

        # 가공 1: 순위 증감 표현 (rankInten / rankOldAndNew)
        def format_rank_inten(row):
            inten = row["rankInten"]
            if row.get("rankOldAndNew") == "NEW":
                return "🆕 NEW"
            if inten > 0:
                return f"🔺 +{inten}"
            elif inten < 0:
                return f"🔻 {inten}"
            else:
                return "➖ 0"

        df_daily["순위변동"] = df_daily.apply(format_rank_inten, axis=1)

        # 가공 2: 누적관객 100만 명 이상 🏆 이모지 표시
        def format_movie_title(row):
            title = row["movieNm"]
            if row["audiAcc"] >= 1_000_000:
                return f"{title} 🏆"
            return title

        df_daily["표시영화명"] = df_daily.apply(format_movie_title, axis=1)

        # 표 정리
        table_daily = df_daily[["rank", "순위변동", "표시영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt", "movieCd", "movieNm"]].copy()
        table_daily.columns = ["순위", "순위변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수", "movieCd", "originalMovieNm"]
        table_daily = table_daily.sort_values("순위").reset_index(drop=True)

        # 영화 상세 팝업 선택 드롭다운 (원본 영화명 표시)
        movie_options = dict(zip(table_daily["originalMovieNm"], table_daily["movieCd"]))
        selected_movie_nm = st.selectbox("🔍 상세정보를 조회할 영화를 선택하세요:", ["선택하세요..."] + list(movie_options.keys()))

        if selected_movie_nm != "선택하세요...":
            if st.button(f"'{selected_movie_nm}' 상세정보 보기"):
                show_movie_detail_dialog(movie_options[selected_movie_nm])

        # 박스오피스 테이블 출력 (내부 파라미터 컬럼 숨김)
        st.dataframe(
            table_daily.drop(columns=["movieCd", "originalMovieNm"]), 
            use_container_width=True
        )

        st.subheader("📈 관객수 상위 5편")
        top5_daily = table_daily.sort_values("관객수", ascending=False).head(5)
        st.bar_chart(top5_daily.set_index("영화명")["관객수"])

# ---------------------------------------------------------
# TAB 2: 주말 vs 평일 흥행 비교
# ---------------------------------------------------------
with tab2:
    st.subheader("⚔️ 최근 주말(금요일 - 일요일) vs 평일(월요일 - 목요일) 흥행 분석")
    st.caption(f"비교 대상 기준: 주말({last_sunday.strftime('%Y-%m-%d')} 주차) / 평일({last_thursday.strftime('%Y-%m-%d')} 주차)")

    if df_weekend.empty or df_weekday.empty:
        st.warning("주말 또는 평일 데이터를 불러오지 못했습니다.")
    else:
        weekend_top = df_weekend.sort_values("rank").iloc[0]
        weekday_top = df_weekday.sort_values("rank").iloc[0]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("주말 1위 영화", weekend_top["movieNm"])
        m2.metric("주말 1위 관객수", f"{weekend_top['audiCnt']:,}명")
        m3.metric("평일 1위 영화", weekday_top["movieNm"])
        m4.metric("평일 1위 관객수", f"{weekday_top['audiCnt']:,}명")

        st.divider()

        df_we = df_weekend[["movieNm", "rank", "audiCnt", "scrnCnt"]].rename(
            columns={"rank": "주말순위", "audiCnt": "주말관객수", "scrnCnt": "주말스크린수"}
        )
        df_wd = df_weekday[["movieNm", "rank", "audiCnt", "scrnCnt"]].rename(
            columns={"rank": "평일순위", "audiCnt": "평일관객수", "scrnCnt": "평일스크린수"}
        )

        df_merged = pd.merge(df_we, df_wd, on="movieNm", how="outer").fillna(0)
        df_merged["주말관객수"] = df_merged["주말관객수"].astype(int)
        df_merged["평일관객수"] = df_merged["평일관객수"].astype(int)

        st.write("##### 📊 주요 영화 주말/평일 관객수 비교 차트")
        df_merged["총관객수"] = df_merged["주말관객수"] + df_merged["평일관객수"]
        top_movies = df_merged.sort_values("총관객수", ascending=False).head(7)

        chart_data = top_movies.set_index("movieNm")[["평일관객수", "주말관객수"]]
        st.bar_chart(chart_data)

        st.write("##### 📋 주말 vs 평일 종합 비교표")
        display_df = df_merged[["movieNm", "주말순위", "주말관객수", "평일순위", "평일관객수"]].copy()
        display_df.columns = ["영화명", "주말 순위", "주말 관객수", "평일 순위", "평일 관객수"]
        
        display_df = display_df.sort_values("주말 관객수", ascending=False).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)
