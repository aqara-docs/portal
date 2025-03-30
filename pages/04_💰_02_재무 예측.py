import streamlit as st
import pandas as pd
import numpy as np
from sklearn import (
    linear_model, ensemble, preprocessing, metrics, model_selection
)
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import joblib

# 페이지 설정
st.set_page_config(
    page_title="비즈니스 예측 도구",
    page_icon="📈",
    layout="wide"
)

# 비즈니스 예측을 위한 알고리즘
ALGORITHMS = {
    "Linear Regression": linear_model.LinearRegression,
    "Ridge Regression": linear_model.Ridge,
    "Lasso Regression": linear_model.Lasso,
    "Random Forest Regressor": ensemble.RandomForestRegressor,
    "Gradient Boosting": ensemble.GradientBoostingRegressor
}

def load_data():
    """데이터 로드 함수"""
    st.subheader("1️⃣ 데이터 업로드")
    
    data_type = st.radio(
        "데이터 입력 방식 선택",
        ["파일 업로드", "수동 입력"]
    )
    
    if data_type == "파일 업로드":
        uploaded_file = st.file_uploader(
            "재무 데이터 파일 업로드 (CSV, Excel)", 
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
    else:
        st.write("수동으로 데이터 입력")
        periods = st.number_input("입력할 기간 수", min_value=1, value=12)
        
        data = {
            '기간': list(range(1, periods + 1)),
            '매출액': [],
            '비용': [],
            '영업이익': []
        }
        
        for i in range(periods):
            col1, col2, col3 = st.columns(3)
            with col1:
                revenue = st.number_input(f"{i+1}기 매출액", value=0.0, key=f"rev_{i}")
                data['매출액'].append(revenue)
            with col2:
                cost = st.number_input(f"{i+1}기 비용", value=0.0, key=f"cost_{i}")
                data['비용'].append(cost)
            with col3:
                profit = revenue - cost
                st.write(f"{i+1}기 영업이익: {profit:,.0f}")
                data['영업이익'].append(profit)
        
        df = pd.DataFrame(data)
        return df
    
    return None

def analyze_seasonality(df, target_col):
    """계절성 분석"""
    if len(df) >= 12:
        # 12개월 이상의 데이터가 있는 경우 계절성 분석
        seasonal_patterns = []
        for i in range(12):
            month_data = df[target_col][i::12]
            seasonal_patterns.append(month_data.mean())
        
        # 계절성 시각화
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(1, 13)),
            y=seasonal_patterns,
            mode='lines+markers',
            name='계절성 패턴'
        ))
        fig.update_layout(
            title="월별 계절성 패턴",
            xaxis_title="월",
            yaxis_title="평균 값"
        )
        st.plotly_chart(fig)
        
        return seasonal_patterns
    return None

def prepare_features(df):
    """특성 준비"""
    st.subheader("2️⃣ 예측 설정")
    
    # 시계열 특성 생성
    if 'date' in df.columns or '날짜' in df.columns:
        date_col = 'date' if 'date' in df.columns else '날짜'
        df[date_col] = pd.to_datetime(df[date_col])
        df['month'] = df[date_col].dt.month
        df['quarter'] = df[date_col].dt.quarter
        df['year'] = df[date_col].dt.year
        
    # 예측 대상 선택
    target = st.selectbox(
        "예측할 지표 선택",
        [col for col in df.columns if col not in ['date', '날짜', 'month', 'quarter', 'year']]
    )
    
    # 특성 선택
    features = st.multiselect(
        "예측에 사용할 특성 선택",
        [col for col in df.columns if col != target],
        default=[col for col in df.columns if col not in [target, 'date', '날짜']]
    )
    
    if not features:
        st.warning("특성을 선택해주세요.")
        return None, None
    
    X = df[features].copy()
    y = df[target].copy()
    
    # 데이터 전처리
    numeric_features = X.select_dtypes(include=[np.number]).columns
    if len(numeric_features) > 0:
        scaler = preprocessing.StandardScaler()
        X[numeric_features] = scaler.fit_transform(X[numeric_features])
    
    return X, y, target

def train_and_evaluate(X, y, target_name):
    """모델 학습 및 평가"""
    st.subheader("3️⃣ 모델 학습")
    
    # 알고리즘 선택
    algorithm = st.selectbox("예측 알고리즘 선택", list(ALGORITHMS.keys()))
    
    # 데이터 분할
    test_size = st.slider("테스트 데이터 비율", 0.1, 0.3, 0.2)
    
    try:
        X_train, X_test, y_train, y_test = model_selection.train_test_split(
            X, y, test_size=test_size, shuffle=False
        )
        
        # 모델 학습
        model = ALGORITHMS[algorithm]()
        model.fit(X_train, y_train)
        
        # 예측
        y_pred = model.predict(X_test)
        
        # 성능 평가
        mse = metrics.mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        r2 = metrics.r2_score(y_test, y_pred)
        
        st.write("#### 모델 성능")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("RMSE", f"{rmse:,.0f}")
        with col2:
            st.metric("MSE", f"{mse:,.0f}")
        with col3:
            st.metric("R² Score", f"{r2:.3f}")
        
        # 예측 vs 실제 시각화
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=y_test,
            name='실제값',
            mode='lines+markers'
        ))
        fig.add_trace(go.Scatter(
            y=y_pred,
            name='예측값',
            mode='lines+markers'
        ))
        fig.update_layout(
            title=f"{target_name} 예측 결과",
            xaxis_title="시점",
            yaxis_title=target_name
        )
        st.plotly_chart(fig)
        
        return model, X_test, y_test, y_pred
        
    except Exception as e:
        st.error(f"모델 학습 중 오류 발생: {e}")
        return None, None, None, None

def make_future_predictions(model, X, target_name):
    """미래 예측"""
    st.subheader("4️⃣ 미래 예측")
    
    forecast_periods = st.number_input(
        "예측할 기간 수",
        min_value=1,
        max_value=24,
        value=12
    )
    
    try:
        # 마지막 데이터 포인트 복사
        last_data = X.iloc[-1:].copy()
        future_predictions = []
        
        # 각 기간에 대해 예측
        for i in range(forecast_periods):
            pred = model.predict(last_data)
            future_predictions.append(pred[0])
            
            # 다음 예측을 위한 데이터 업데이트
            if 'month' in last_data.columns:
                last_data['month'] = (last_data['month'] % 12) + 1
            if 'quarter' in last_data.columns:
                last_data['quarter'] = (last_data['quarter'] % 4) + 1
            if 'year' in last_data.columns:
                if last_data['month'].iloc[0] == 1:
                    last_data['year'] += 1
        
        # 예측 결과 시각화
        fig = go.Figure()
        
        # 과거 데이터
        fig.add_trace(go.Scatter(
            x=list(range(len(X))),
            y=model.predict(X),
            name='과거 예측',
            line=dict(color='blue')
        ))
        
        # 미래 예측
        fig.add_trace(go.Scatter(
            x=list(range(len(X), len(X) + forecast_periods)),
            y=future_predictions,
            name='미래 예측',
            line=dict(color='red', dash='dash')
        ))
        
        fig.update_layout(
            title=f"{target_name} 미래 예측",
            xaxis_title="기간",
            yaxis_title=target_name,
            showlegend=True
        )
        st.plotly_chart(fig)
        
        # 예측값 표시
        st.write("#### 예측 결과")
        forecast_df = pd.DataFrame({
            '기간': [f'T+{i+1}' for i in range(forecast_periods)],
            '예측값': future_predictions
        })
        st.dataframe(forecast_df.style.format({'예측값': '{:,.0f}'}))
        
    except Exception as e:
        st.error(f"미래 예측 중 오류 발생: {e}")

def main():
    st.title("📈 비즈니스 예측 시스템")
    st.write("매출, 비용, 수익성 등 주요 비즈니스 지표 예측")
    
    # 데이터 로드
    df = load_data()
    
    if df is not None:
        st.write("#### 데이터 미리보기")
        st.dataframe(df.head())
        
        # 특성 준비
        X, y, target_name = prepare_features(df)
        
        if X is not None and y is not None:
            # 계절성 분석
            seasonal_patterns = analyze_seasonality(df, target_name)
            
            # 모델 학습 및 평가
            model, X_test, y_test, y_pred = train_and_evaluate(X, y, target_name)
            
            if model is not None:
                # 미래 예측
                make_future_predictions(model, X, target_name)
                
                # 모델 저장
                if st.button("모델 저장"):
                    try:
                        joblib.dump(model, f'{target_name}_prediction_model.joblib')
                        st.success("모델이 저장되었습니다.")
                    except Exception as e:
                        st.error(f"모델 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    main() 