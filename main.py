import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 헤더
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 인구 변동률 지도",
    layout="wide"
)

st.title("📈 전국 시군구 인구 변동률 지도")
st.caption("2015년 대비 최신 연도의 시군구별 총인구 증감률(%) 시각화 지도입니다.")

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
def load_and_process_change_data():
    """2015년 대비 최신 연도의 시군구별 인구 변동률 계산하기"""
    df = pd.read_csv(POPULATION_URL, dtype={'코드': str})
    
    min_year = df['연도'].min()
    max_year = df['연도'].max()
    
    # -------------------------------------------------------------------------
    # [데이터 정제] 행정구역 명칭, 코드 최신화 및 결측치 방어
    # -------------------------------------------------------------------------
    # 1. 시도 명칭 변경
    df['시도'] = df['시도'].replace({
        '강원도': '강원특별자치도',
        '전라북도': '전북특별자치도'
    })
    
    # 2. 결측치(NaN) 방어: 세종시처럼 시군구가 없는 단일 지자체는 groupby에서 누락되지 않도록 시도 이름으로 채움
    df['시군구'] = df['시군구'].fillna(df['시도'])
    
    # 3. 앞 5자리 시군구 코드 추출
    df['sigungu_code'] = df['코드'].str[:5]
    
    # 4. 과거 시도 코드(강원도: 42, 전라북도: 45)를 최신 코드(강원: 51, 전북: 52)로 변환
    df['sigungu_code'] = df['sigungu_code'].apply(
        lambda x: '51' + x[2:] if x.startswith('42') else ('52' + x[2:] if x.startswith('45') else x)
    )
    # -------------------------------------------------------------------------
    
    # 전체 인구 계산
    total_cols = [c for c in df.columns if c.startswith('계_')]
    df['총인구'] = df[total_cols].sum(axis=1)
    
    # 시군구별, 연도별 인구 합산
    grouped = df[df['연도'].isin([min_year, max_year])].groupby(
        ['sigungu_code', '시도', '시군구', '연도'], as_index=False
    )['총인구'].sum()
    
    # 연도별 피벗 (2015년, 최신년도 열 생성)
    pivoted = grouped.pivot(
        index=['sigungu_code', '시도', '시군구'], 
        columns='연도', 
        values='총인구'
    ).reset_index()
    
    pivoted.columns.name = None
    pivoted = pivoted.rename(columns={min_year: '인구_2015', max_year: '인구_최신'})
    
    # 결측치를 0으로 채워 행 삭제 방지 (신설 및 통합 지역 대응)
    pivoted['인구_2015'] = pivoted['인구_2015'].fillna(0)
    pivoted['인구_최신'] = pivoted['인구_최신'].fillna(0)
    
    # 인구 변동률 및 증감수 계산
    pivoted['인구증감'] = pivoted['인구_최신'] - pivoted['인구_2015']
    pivoted['변동률'] = 0.0
    
    valid_mask = pivoted['인구_2015'] > 0
    pivoted.loc[valid_mask, '변동률'] = (
        (pivoted.loc[valid_mask, '인구_최신'] - pivoted.loc[valid_mask, '인구_2015']) 
        / pivoted.loc[valid_mask, '인구_2015']
    ) * 100
    pivoted['변동률'] = pivoted['변동률'].round(1)
    
    # 5단계 구획 설정
    bins = [-999, -15, -5, 5, 15, 999]
    labels = [
        '-15% 미만 (급감)', 
        '-15% 이상 ~ -5% 미만 (감소)', 
        '-5% 이상 ~ +5% 미만 (유지)', 
        '+5% 이상 ~ +15% 미만 (증가)', 
        '+15% 이상 (급증)'
    ]
    pivoted['변동단계'] = pd.cut(pivoted['변동률'], bins=bins, labels=labels)
    
    return pivoted, min_year, max_year

# 데이터 로딩 실행
with st.spinner("데이터를 분석 중입니다..."):
    geojson_data = load_geojson()
    
    # GeoJSON 내부의 구형 코드(42, 45)도 신형(51, 52)으로 업데이트하여 맵핑이 완벽히 되도록 처리
    for feature in geojson_data['features']:
        code = feature['properties']['코드']
        if code.startswith('42'):
            feature['properties']['코드'] = '51' + code[2:]
        elif code.startswith('45'):
            feature['properties']['코드'] = '52' + code[2:]
            
    df_sigungu, min_year, max_year = load_and_process_change_data()

# 사이드바 안내
st.sidebar.markdown(f"**비교 기간:** {min_year}년 ➡️ {max_year}년")
st.sidebar.info(
    "**인구 변동률 단계 구분 기준**\n\n"
    "- 🔴 **-15% 미만**: 인구 급감 지역\n"
    "- 🟠 **-15% ~ -5%**: 인구 감소 지역\n"
    "- ⚪ **-5% ~ +5%**: 인구 보합/유지 지역\n"
    "- 🔵 **+5% ~ +15%**: 인구 증가 지역\n"
    "- 🔷 **+15% 이상**: 인구 급증 지역"
)

# -----------------------------------------------------------------------------
# 3. 단계구분도(Choropleth Map) 생성 및 시각화
# -----------------------------------------------------------------------------
color_discrete_map = {
    '-15% 미만 (급감)': '#d73027',
    '-15% 이상 ~ -5% 미만 (감소)': '#fc8d59',
    '-5% 이상 ~ +5% 미만 (유지)': '#e0e0e0',
    '+5% 이상 ~ +15% 미만 (증가)': '#67a9cf',
    '+15% 이상 (급증)': '#02818a'
}

category_order = [
    '-15% 미만 (급감)', 
    '-15% 이상 ~ -5% 미만 (감소)', 
    '-5% 이상 ~ +5% 미만 (유지)', 
    '+5% 이상 ~ +15% 미만 (증가)', 
    '+15% 이상 (급증)'
]

fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 시군구 코드
    featureidkey='properties.코드',   # GeoJSON 속성의 5자리 코드
    color='변동단계',                 # 색상 구분 기준
    color_discrete_map=color_discrete_map,
    category_orders={'변동단계': category_order},
    center={"lat": 35.9, "lon": 127.8}, # 대한민국 중심 좌표
    zoom=6.2,
    mapbox_style="white-bg",          # 배경 지도 타일 없이 경계선만 표시
    hover_name='시군구',              # 툴팁 제목
    hover_data={
        '시도': True,
        'sigungu_code': False,
        '변동단계': False,
        '인구_2015': ':,명',
        '인구_최신': ':,명',
        '인구증감': ':,명',
        '변동률': ':.1f%'              # 소수점 1자리 + % 표기
    },
    labels={
        '변동단계': '인구 변동 구간',
        '시도': '시·도',
        '인구_2015': f'{min_year}년 인구',
        '인구_최신': f'{max_year}년 인구',
        '인구증감': '인구 증감수',
        '변동률': '변동률'
    }
)

# 레이아웃 디테일 설정
fig.update_traces(marker_line_width=0.5, marker_line_color="#666666")
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    height=650,
    legend=dict(
        title_text=f"인구 변동률 구간 ({min_year} 대비)",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255, 255, 255, 0.85)"
    )
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 4. 비율(%) 기준 상위/하위 10개 지역 표 표시
# -----------------------------------------------------------------------------
st.subheader("📊 인구 변동률(%) 극단 지역 비교")

col1, col2 = st.columns(2)

top10_rate = (
    df_sigungu.sort_values(by='변동률', ascending=False)
    .head(10)[['시도', '시군구', '인구_2015', '인구_최신', '인구증감', '변동률']]
    .reset_index(drop=True)
)

bottom10_rate = (
    df_sigungu.sort_values(by='변동률', ascending=True)
    .head(10)[['시도', '시군구', '인구_2015', '인구_최신', '인구증감', '변동률']]
    .reset_index(drop=True)
)

with col1:
    st.markdown("##### 🔵 인구 증가율(%) 가장 높은 지역 TOP 10")
    st.dataframe(
        top10_rate.style.format({
            '인구_2015': '{:,}명',
            '인구_최신': '{:,}명',
            '인구증감': '{:+,}명',
            '변동률': '{:+.1f}%'
        }),
        use_container_width=True
    )

with col2:
    st.markdown("##### 🔴 인구 감소율(%) 가장 높은 지역 TOP 10")
    st.dataframe(
        bottom10_rate.style.format({
            '인구_2015': '{:,}명',
            '인구_최신': '{:,}명',
            '인구증감': '{:+,}명',
            '변동률': '{:+.1f}%'
        }),
        use_container_width=True
    )
