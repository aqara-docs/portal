import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.proportion import proportions_ztest
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
import seaborn as sns
import matplotlib.pyplot as plt

# 페이지 설정
st.set_page_config(
    page_title="Stats Explorer",
    page_icon="📈",
    layout="wide"
)

# 사용 가능한 통계 분석 방법
STAT_METHODS = {
    "기술 통계": [
        "기본 통계량",
        "분포 분석",
        "이상치 분석"
    ],
    "가설 검정": [
        "일표본 t검정",
        "독립표본 t검정",
        "대응표본 t검정",
        "일원배치 분산분석(ANOVA)",
        "카이제곱 검정",
        "상관 분석"
    ],
    "회귀 분석": [
        "단순 선형 회귀",
        "다중 선형 회귀",
        "로지스틱 회귀"
    ],
    "비모수 검정": [
        "Mann-Whitney U 검정",
        "Wilcoxon 부호 순위 검정",
        "Kruskal-Wallis H 검정"
    ]
}

# 비즈니스 통계 분석 방법
BUSINESS_STAT_METHODS = {
    "재무 지표 분석": [
        "수익성 지표",
        "성장성 지표",
        "안정성 지표",
        "활동성 지표",
        "주가 관련 지표"
    ],
    "비즈니스 성과 분석": [
        "매출 추세 분석",
        "비용 구조 분석",
        "수익성 분석",
        "고객 지표 분석"
    ],
    "시장 분석": [
        "시장점유율 분석",
        "경쟁사 비교 분석",
        "산업 평균 비교"
    ],
    "리스크 분석": [
        "변동성 분석",
        "민감도 분석",
        "시나리오 분석"
    ]
}

def load_data():
    """데이터 로드 함수"""
    uploaded_file = st.file_uploader(
        "데이터 파일 업로드 (CSV, Excel)", 
        type=['csv', 'xlsx']
    )
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            return df
        except Exception as e:
            st.error(f"파일 로드 중 오류 발생: {e}")
            return None
    return None

def descriptive_statistics(df):
    """기술 통계 분석"""
    if df is None or df.empty:
        st.warning("데이터를 먼저 업로드해주세요.")
        return
        
    st.subheader("기술 통계 분석")
    
    # 변수 선택
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        st.warning("수치형 변수가 없습니다.")
        return
        
    selected_cols = st.multiselect(
        "분석할 변수 선택",
        numeric_cols,
        default=numeric_cols[0] if len(numeric_cols) > 0 else None
    )
    
    if selected_cols:
        # 기본 통계량
        st.write("### 기본 통계량")
        stats_df = df[selected_cols].describe()
        stats_df.loc['왜도'] = df[selected_cols].skew()
        stats_df.loc['첨도'] = df[selected_cols].kurtosis()
        st.dataframe(stats_df)
        
        # 분포 시각화
        st.write("### 분포 시각화")
        for col in selected_cols:
            fig = px.histogram(
                df, x=col,
                title=f"{col} 분포",
                marginal="box"
            )
            st.plotly_chart(fig)
            
            # Q-Q plot
            fig = px.scatter(
                x=np.sort(df[col]),
                y=stats.norm.ppf(np.linspace(0.01, 0.99, len(df))),
                title=f"{col} Q-Q Plot"
            )
            fig.add_trace(
                go.Scatter(
                    x=[df[col].min(), df[col].max()],
                    y=[df[col].min(), df[col].max()],
                    mode='lines',
                    name='정규분포선'
                )
            )
            st.plotly_chart(fig)

def hypothesis_testing(df):
    """가설 검정"""
    if df is None or df.empty:
        st.warning("데이터를 먼저 업로드해주세요.")
        return
        
    st.subheader("가설 검정")
    
    # 수치형/범주형 변수 확인
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns
    
    if len(numeric_cols) == 0:
        st.warning("수치형 변수가 없어 검정을 수행할 수 없습니다.")
        return
    
    test_type = st.selectbox(
        "검정 방법 선택",
        STAT_METHODS["가설 검정"]
    )
    
    if test_type == "일표본 t검정":
        col = st.selectbox("변수 선택", df.select_dtypes(include=[np.number]).columns)
        mu = st.number_input("귀무가설의 평균값", value=0.0)
        
        result = stats.ttest_1samp(df[col].dropna(), mu)
        st.write(f"### 일표본 t검정 결과")
        st.write(f"t-통계량: {result.statistic:.4f}")
        st.write(f"p-value: {result.pvalue:.4f}")
        
    elif test_type == "독립표본 t검정":
        num_col = st.selectbox("수치형 변수", df.select_dtypes(include=[np.number]).columns)
        cat_col = st.selectbox("그룹 변수", df.select_dtypes(exclude=[np.number]).columns)
        
        groups = df[cat_col].unique()
        if len(groups) == 2:
            group1 = df[df[cat_col] == groups[0]][num_col].dropna()
            group2 = df[df[cat_col] == groups[1]][num_col].dropna()
            
            result = stats.ttest_ind(group1, group2)
            st.write(f"### 독립표본 t검정 결과")
            st.write(f"t-통계량: {result.statistic:.4f}")
            st.write(f"p-value: {result.pvalue:.4f}")
            
            # 박스플롯
            fig = px.box(df, x=cat_col, y=num_col)
            st.plotly_chart(fig)
            
    elif test_type == "카이제곱 검정":
        # 범주형 변수 선택
        cat_cols = df.select_dtypes(exclude=[np.number]).columns
        if len(cat_cols) < 2:
            st.warning("카이제곱 검정을 위해서는 최소 2개의 범주형 변수가 필요합니다.")
            return
            
        col1 = st.selectbox("첫 번째 변수", cat_cols)
        col2 = st.selectbox("두 번째 변수", [col for col in cat_cols if col != col1])
        
        # 교차표 생성
        contingency_table = pd.crosstab(df[col1], df[col2])
        st.write("### 교차표")
        st.dataframe(contingency_table)
        
        # 카이제곱 검정 수행
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        st.write("### 카이제곱 검정 결과")
        st.write(f"카이제곱 통계량: {chi2:.4f}")
        st.write(f"자유도: {dof}")
        st.write(f"p-value: {p_value:.4f}")
        
        # 시각화
        fig = px.imshow(
            contingency_table,
            title="교차표 히트맵",
            labels=dict(color="빈도")
        )
        st.plotly_chart(fig)

    # ... (나머지 검정 코드는 동일)

def correlation_analysis(df):
    """상관 분석"""
    if df is None or df.empty:
        st.warning("데이터를 먼저 업로드해주세요.")
        return
        
    st.subheader("상관 분석")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) < 2:
        st.warning("상관 분석을 위해서는 최소 2개의 수치형 변수가 필요합니다.")
        return
        
    selected_cols = st.multiselect(
        "분석할 변수 선택",
        numeric_cols,
        default=list(numeric_cols)[:min(5, len(numeric_cols))]
    )
    
    if len(selected_cols) > 1:
        # 상관 행렬
        corr = df[selected_cols].corr()
        
        # 히트맵
        fig = px.imshow(
            corr,
            title="상관관계 히트맵",
            labels=dict(color="상관계수")
        )
        st.plotly_chart(fig)
        
        # 산점도 행렬
        fig = px.scatter_matrix(df[selected_cols])
        st.plotly_chart(fig)
        
        # 상관계수 검정
        st.write("### 상관계수 검정 결과")
        for i in range(len(selected_cols)):
            for j in range(i+1, len(selected_cols)):
                col1, col2 = selected_cols[i], selected_cols[j]
                r, p = stats.pearsonr(df[col1].dropna(), df[col2].dropna())
                st.write(f"{col1} vs {col2}:")
                st.write(f"상관계수: {r:.4f}")
                st.write(f"p-value: {p:.4f}")

def regression_analysis(df):
    """회귀 분석"""
    if df is None or df.empty:
        st.warning("데이터를 먼저 업로드해주세요.")
        return
        
    st.subheader("회귀 분석")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) < 2:
        st.warning("회귀 분석을 위해서는 최소 2개의 수치형 변수가 필요합니다.")
        return
        
    reg_type = st.selectbox(
        "회귀 분석 유형",
        STAT_METHODS["회귀 분석"]
    )
    
    if reg_type in ["단순 선형 회귀", "다중 선형 회귀"]:
        # 변수 선택
        y_col = st.selectbox("종속변수 선택", numeric_cols)
        
        if reg_type == "단순 선형 회귀":
            x_cols = [st.selectbox("독립변수 선택", [col for col in numeric_cols if col != y_col])]
        else:
            x_cols = st.multiselect(
                "독립변수 선택",
                [col for col in numeric_cols if col != y_col]
            )
        
        if x_cols:
            # 회귀 분석 실행
            X = sm.add_constant(df[x_cols])
            y = df[y_col]
            
            model = sm.OLS(y, X).fit()
            
            # 결과 출력
            st.write("### 회귀분석 결과")
            st.write(model.summary())
            
            # 잔차 분석
            residuals = model.resid
            fitted = model.fittedvalues
            
            # 잔차 플롯
            fig = px.scatter(
                x=fitted,
                y=residuals,
                labels={"x": "예측값", "y": "잔차"},
                title="잔차 플롯"
            )
            st.plotly_chart(fig)
            
            # Q-Q 플롯
            fig = px.scatter(
                x=np.sort(residuals),
                y=stats.norm.ppf(np.linspace(0.01, 0.99, len(residuals))),
                title="잔차의 Q-Q Plot"
            )
            st.plotly_chart(fig)

def analyze_financial_ratios(df):
    """재무 비율 분석"""
    st.subheader("재무 비율 분석")
    
    # 필요한 컬럼 확인
    required_cols = {
        '매출액': ['revenue', 'sales', '매출액'],
        '영업이익': ['operating_income', 'operating_profit', '영업이익'],
        '당기순이익': ['net_income', 'net_profit', '당기순이익'],
        '총자산': ['total_assets', '총자산'],
        '자기자본': ['equity', '자기자본'],
        '유동자산': ['current_assets', '유동자산'],
        '유동부채': ['current_liabilities', '유동부채']
    }
    
    # 컬럼 매핑
    col_mapping = {}
    for key, possible_names in required_cols.items():
        found_cols = [col for col in df.columns if col.lower() in possible_names]
        if found_cols:
            col_mapping[key] = found_cols[0]
    
    if len(col_mapping) > 0:
        st.write("### 주요 재무 비율")
        
        ratios = {}
        
        # 수익성 지표
        if all(k in col_mapping for k in ['매출액', '영업이익', '당기순이익']):
            ratios['영업이익률'] = (df[col_mapping['영업이익']] / df[col_mapping['매출액']]) * 100
            ratios['순이익률'] = (df[col_mapping['당기순이익']] / df[col_mapping['매출액']]) * 100
        
        # 안정성 지표
        if all(k in col_mapping for k in ['유동자산', '유동부채']):
            ratios['유동비율'] = (df[col_mapping['유동자산']] / df[col_mapping['유동부채']]) * 100
        
        # 결과 표시
        if ratios:
            ratio_df = pd.DataFrame(ratios)
            st.dataframe(ratio_df.describe().round(2))
            
            # 시각화
            for ratio_name, ratio_values in ratios.items():
                fig = px.line(
                    x=df.index,
                    y=ratio_values,
                    title=f"{ratio_name} 추세",
                    labels={'x': '기간', 'y': f'{ratio_name} (%)'}
                )
                st.plotly_chart(fig)

def analyze_business_performance(df):
    """비즈니스 성과 분석"""
    st.subheader("비즈니스 성과 분석")
    
    # 매출 분석
    if '매출액' in df.columns:
        st.write("### 매출 분석")
        
        # 매출 추세
        fig = px.line(
            df,
            x=df.index,
            y='매출액',
            title="매출 추세"
        )
        st.plotly_chart(fig)
        
        # 매출 성장률
        df['매출성장률'] = df['매출액'].pct_change() * 100
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "평균 매출 성장률",
                f"{df['매출성장률'].mean():.1f}%"
            )
        with col2:
            st.metric(
                "최근 매출 성장률",
                f"{df['매출성장률'].iloc[-1]:.1f}%"
            )
        
        # 계절성 분석
        if len(df) >= 12:
            st.write("### 계절성 분석")
            seasonal_decompose = sm.tsa.seasonal_decompose(
                df['매출액'],
                period=12,
                extrapolate_trend='freq'
            )
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=seasonal_decompose.seasonal,
                name='계절성 패턴'
            ))
            fig.update_layout(title="매출의 계절성 패턴")
            st.plotly_chart(fig)

def analyze_market_share(df):
    """시장 점유율 분석"""
    st.subheader("시장 분석")
    
    if '시장점유율' in df.columns:
        st.write("### 시장점유율 추이")
        
        fig = px.line(
            df,
            x=df.index,
            y='시장점유율',
            title="시장점유율 변화"
        )
        st.plotly_chart(fig)
        
        # 기초 통계량
        st.write("### 시장점유율 통계")
        st.dataframe(df['시장점유율'].describe().round(2))
        
        # 변화 추세 분석
        df['점유율_변화'] = df['시장점유율'].diff()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "평균 시장점유율",
                f"{df['시장점유율'].mean():.1f}%"
            )
        with col2:
            st.metric(
                "점유율 변화 추세",
                f"{df['점유율_변화'].mean():.2f}%",
                delta=f"{df['점유율_변화'].iloc[-1]:.2f}%"
            )

def analyze_risk(df):
    """리스크 분석"""
    st.subheader("리스크 분석")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    selected_col = st.selectbox("분석할 지표 선택", numeric_cols)
    
    if selected_col:
        # 변동성 분석
        st.write("### 변동성 분석")
        
        # 변동계수 (CV)
        cv = df[selected_col].std() / df[selected_col].mean()
        
        # 최대 낙폭
        max_drawdown = (
            (df[selected_col] - df[selected_col].cummax()) / df[selected_col].cummax()
        ).min() * 100
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("변동계수 (CV)", f"{cv:.3f}")
        with col2:
            st.metric("최대 낙폭", f"{max_drawdown:.1f}%")
        
        # 변동성 시각화
        rolling_std = df[selected_col].rolling(window=12).std()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=df[selected_col],
            name='실제값'
        ))
        fig.add_trace(go.Scatter(
            y=rolling_std,
            name='12개월 변동성',
            line=dict(dash='dash')
        ))
        fig.update_layout(title="변동성 추이")
        st.plotly_chart(fig)
        
        # 민감도 분석
        st.write("### 민감도 분석")
        
        change_range = st.slider(
            "변화율 범위 (%)",
            min_value=-50,
            max_value=50,
            value=(-20, 20)
        )
        
        changes = np.linspace(change_range[0], change_range[1], 100)
        base_value = df[selected_col].mean()
        
        sensitivity = pd.DataFrame({
            '변화율': changes,
            '값': base_value * (1 + changes/100)
        })
        
        fig = px.line(
            sensitivity,
            x='변화율',
            y='값',
            title="민감도 분석"
        )
        st.plotly_chart(fig)

def main():
    st.title("📊 비즈니스 통계 분석")
    st.write("재무 및 비즈니스 성과의 통계적 분석")
    
    # 데이터 로드
    df = load_data()
    
    if df is not None:
        st.write("### 데이터 미리보기")
        st.dataframe(df.head())
        
        st.write("### 데이터 정보")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("행 수", df.shape[0])
        with col2:
            st.metric("열 수", df.shape[1])
        with col3:
            st.metric("수치형 변수 수", len(df.select_dtypes(include=[np.number]).columns))
        
        # 탭 생성
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "기본 통계",
            "재무 지표",
            "비즈니스 성과",
            "시장 분석",
            "리스크 분석"
        ])
        
        with tab1:
            descriptive_statistics(df)
        
        with tab2:
            analyze_financial_ratios(df)
        
        with tab3:
            analyze_business_performance(df)
        
        with tab4:
            analyze_market_share(df)
        
        with tab5:
            analyze_risk(df)

if __name__ == "__main__":
    main() 