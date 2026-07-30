import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 헤더
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_layout="wide"
)

st.title("🗺️ 전국 시군구 고령화율 지도")
st.caption("행정안전부 주민등록 인구 데이터를 기반으로 한 시군구별 65세 이상 인구 비율 지도입니다.")

# 데이터 URL 정의
POPULATION_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 (캐싱 적용으로 속도 최적화)
# -----------------------------------------------------------------------------
@st.cache_data
def load_geojson():
    """GeoJSON 지도 경계 데이터 불러오기"""
    response = requests.get(GEOJSON_URL)
    return response.json()

@st.cache_data
def load_and_process_data():
    """인구 CSV 데이터를 읽어와 최신 연도 기준 시군구별 고령화율 계산하기"""
    # '코드' 열은 문자열(str)로 읽어야 앞자리 '0'이 유지되고 5자리 잘라내기가 가능합니다.
    df = pd.read_csv(POPULATION_URL, dtype={'코드': str})
    
    # 1) 가장 최신 연도 데이터만 필터링
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 2) 행정동 코드(10자리)의 앞 5자리를 추출하여 시군구 코드 생성
    df_latest['sigungu_code'] = df_latest['코드'].str[:5]
    
    # 3) 65세 이상 연령대 열('계_65세' ~ '계_100세 이상') 찾기
    age_cols = [c for c in df_latest.columns if c.startswith('계_')]
    
    # 연령 숫자를 추출하여 65세 이상인 열만 필터링
    senior_cols = []
    for col in age_cols:
        age_str = col.replace('계_', '').replace('세 이상', '').replace('세', '')
        try:
            if int(age_str) >= 65:
                senior_cols.append(col)
        except ValueError:
            continue
            
    # 전체 인구 계산에 필요한 모든 '계_' 열
    total_cols = senior_cols + [c for c in age_cols if c not in senior_cols]

    # 4) 시군구 단위로 총인구 및 65세 이상 인구 합산
    df_latest['총인구'] = df_latest[total_cols].sum(axis=1)
    df_latest['65세이상인구'] = df_latest[senior_cols].sum(axis=1)
    
    grouped = df_latest.groupby(['sigungu_code', '시도', '시군구'], as_index=False).agg({
        '총인구': 'sum',
        '65세이상인구': 'sum'
    })
    
    # 5) 고령화율(%) 계산
    grouped['고령화율'] = (grouped['65세이상인구'] / grouped['총인구']) * 100
    grouped['고령화율'] = grouped['고령화율'].round(1) # 소수점 첫째자리까지 정렬
    
    # 6) 지정된 경계값(19%, 23%, 28%, 38%) 기준으로 5단계 구획 채우기
    # 범례 및 정렬을 위해 범주형 라벨 부여
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']
    
    grouped['고령화단계'] = pd.cut(grouped['고령화율'], bins=bins, labels=labels)
    
    return grouped, latest_year

# 데이터 로딩 실행
with st.spinner("데이터를 불러오는 중입니다..."):
    geojson_data = load_geojson()
    df_sigungu, max_year = load_and_process_data()

st.sidebar.markdown(f"**기준 연도:** {max_year}년")
st.sidebar.info(
    "**고령화율 단계 구분 기준**\n\n"
    "- 1단계: 19% 미만\n"
    "- 2단계: 19% ~ 23%\n"
    "- 3단계: 23% ~ 28%\n"
    "- 4단계: 28% ~ 38%\n"
    "- 5단계: 38% 이상"
)

# -----------------------------------------------------------------------------
# 3. 단계구분도(Choropleth Map) 생성 및 시각화
# -----------------------------------------------------------------------------
# 단계별 색상 지정 (연한 빨간색/주황색 -> 진한 버건디 계열)
color_discrete_map = {
    '19% 미만': '#fef0d9',
    '19% 이상 ~ 23% 미만': '#fdcc8a',
    '23% 이상 ~ 28% 미만': '#fc8d59',
    '28% 이상 ~ 38% 미만': '#e34a33',
    '38% 이상': '#b30000'
}

fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 시군구 코드
    featureidkey='properties.코드',   # GeoJSON 속성의 5자리 코드
    color='고령화단계',               # 색상 구분 기준
    color_discrete_map=color_discrete_map,
    category_orders={'고령화단계': ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']},
    center={"lat": 35.9, "lon": 127.8}, # 대한민국 중심 좌표
    zoom=6.2,
    mapbox_style="white-bg",          # 배경 지도 타일 없이 경계선만 표시
    hover_name='시군구',              # 툴팁 제목
    hover_data={
        '시도': True,
        'sigungu_code': False,
        '고령화단계': False,
        '고령화율': ':.1f%'            # 소수점 1자리 + % 표기
    },
    labels={
        '고령화단계': '고령화율 구간',
        '시도': '시·도',
        '고령화율': '고령화율'
    }
)

# 레이아웃 디테일 설정 (경계선 및 가독성 조정)
fig.update_traces(marker_line_width=0.5, marker_line_color="#666666")
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    height=650,
    legend=dict(
        title_text="고령화율 구간",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 4. 지도 하단 상위/하위 10개 지역 표 표시
# -----------------------------------------------------------------------------
st.subheader("📊 고령화율 극단 지역 비교")

col1, col2 = st.columns(2)

# 고령화율 높은 순 상위 10개
top10 = (
    df_sigungu.sort_values(by='고령화율', ascending=False)
    .head(10)[['시도', '시군구', '총인구', '65세이상인구', '고령화율']]
    .reset_index(drop=True)
)

# 고령화율 낮은 순 하위 10개
bottom10 = (
    df_sigungu.sort_values(by='고령화율', ascending=True)
    .head(10)[['시도', '시군구', '총인구', '65세이상인구', '고령화율']]
    .reset_index(drop=True)
)

with col1:
    st.markdown("##### 🔴 고령화율 가장 높은 지역 TOP 10")
    st.dataframe(
        top10.style.format({
            '총인구': '{:,}명',
            '65세이상인구': '{:,}명',
            '고령화율': '{:.1f}%'
        }),
        use_container_width=True
    )

with col2:
    st.markdown("##### 🔵 고령화율 가장 낮은 지역 TOP 10")
    st.dataframe(
        bottom10.style.format({
            '총인구': '{:,}명',
            '65세이상인구': '{:,}명',
            '고령화율': '{:.1f}%'
        }),
        use_container_width=True
    )
