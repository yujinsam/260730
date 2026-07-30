@st.cache_data
def load_and_process_change_data():
    """2015년 대비 최신 연도의 시군구별 인구 변동률 계산하기"""
    df = pd.read_csv(POPULATION_URL, dtype={'코드': str})
    
    min_year = df['연도'].min()
    max_year = df['연도'].max()
    
    df['sigungu_code'] = df['코드'].str[:5]
    
    total_cols = [c for c in df.columns if c.startswith('계_')]
    df['총인구'] = df[total_cols].sum(axis=1)
    
    # 시군구별, 연도별 인구 합산
    grouped = df[df['연도'].isin([min_year, max_year])].groupby(
        ['sigungu_code', '시도', '시군구', '연도'], as_index=False
    )['총인구'].sum()
    
    # 연도별 피벗
    pivoted = grouped.pivot(
        index=['sigungu_code', '시도', '시군구'], 
        columns='연도', 
        values='총인구'
    ).reset_index()
    
    pivoted.columns.name = None
    pivoted = pivoted.rename(columns={min_year: '인구_2015', max_year: '인구_최신'})
    
    # ❌ dropna() 삭제! 대신 0으로 채워 계산 에러 방지
    pivoted['인구_2015'] = pivoted['인구_2015'].fillna(0)
    pivoted['인구_최신'] = pivoted['인구_최신'].fillna(0)
    
    # 인구 변동률 계산 (2015년 인구가 0인 신설 지역은 0% 처리)
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
