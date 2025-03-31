import streamlit as st
import pandas as pd
import numpy as np
from sklearn import (
    linear_model, ensemble, preprocessing, metrics, model_selection, cluster
)
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import joblib
import tempfile
import os

# 페이지 설정
st.set_page_config(
    page_title="비즈니스 예측 도구",
    page_icon="📈",
    layout="wide"
)

# 비즈니스 예측을 위한 알고리즘
ALGORITHMS = {
    "회귀 분석": {
        "Linear Regression": linear_model.LinearRegression,
        "Ridge Regression": linear_model.Ridge,
        "Lasso Regression": linear_model.Lasso,
        "Random Forest Regressor": ensemble.RandomForestRegressor,
        "Gradient Boosting": ensemble.GradientBoostingRegressor
    },
    "분류 분석": {
        "Logistic Regression": linear_model.LogisticRegression,
        "Random Forest Classifier": ensemble.RandomForestClassifier,
        "Gradient Boosting Classifier": ensemble.GradientBoostingClassifier
    },
    "군집 분석": {
        "K-Means": cluster.KMeans,
        "DBSCAN": cluster.DBSCAN,
        "Hierarchical Clustering": cluster.AgglomerativeClustering
    }
}

def load_data():
    """데이터 로드 함수"""
    st.subheader("1️⃣ 데이터 업로드")
    
    data_type = st.radio(
        "데이터 입력 방식 선택",
        ["파일 업로드", "수동 입력"],
        key="data_input_type"
    )
    
    if data_type == "파일 업로드":
        uploaded_file = st.file_uploader(
            "재무 데이터 파일 업로드 (CSV, Excel)", 
            type=['csv', 'xlsx'],
            key="data_file_uploader"
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
        periods = st.number_input(
            "입력할 기간 수",
            min_value=1,
            value=12,
            key="input_periods"
        )
        
        data = {
            '기간': list(range(1, periods + 1)),
            '매출액': [],
            '비용': [],
            '영업이익': []
        }
        
        for i in range(periods):
            col1, col2, col3 = st.columns(3)
            with col1:
                revenue = st.number_input(
                    f"{i+1}기 매출액",
                    value=0.0,
                    key=f"manual_revenue_{i}"
                )
                data['매출액'].append(revenue)
            with col2:
                cost = st.number_input(
                    f"{i+1}기 비용",
                    value=0.0,
                    key=f"manual_cost_{i}"
                )
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

def prepare_features(df, model_type):
    """특성 준비"""
    st.subheader("2️⃣ 예측 설정")
    
    if df is None:
        return None, None, None
    
    # 데이터 타입 확인 및 전처리
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns
    
    # 예측 대상 선택
    if model_type == "회귀 분석":
        # 회귀 분석은 수치형 변수만 선택 가능
        if len(numeric_cols) == 0:
            st.warning("수치형 변수가 없습니다.")
            return None, None, None
        target_cols = numeric_cols
    elif model_type == "분류 분석":
        # 분류 분석은 모든 변수 선택 가능
        target_cols = df.columns
    else:  # 군집 분석
        return df, None, None  # 군집 분석은 타겟 변수가 필요 없음
    
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
        [col for col in target_cols if col not in ['month', 'quarter', 'year', 'date', '날짜']]
    )
    
    # 특성 선택 및 전처리
    available_features = []
    
    # 수치형 특성
    numeric_features = [col for col in numeric_cols if col != target]
    if numeric_features:
        selected_numeric = st.multiselect(
            "수치형 특성 선택",
            numeric_features,
            default=numeric_features
        )
        available_features.extend(selected_numeric)
    
    # 범주형 특성
    if len(categorical_cols) > 0:
        selected_categorical = st.multiselect(
            "범주형 특성 선택",
            [col for col in categorical_cols if col not in ['date', '날짜'] and col != target],
            default=[]
        )
        available_features.extend(selected_categorical)
    
    if not available_features:
        st.warning("특성을 선택해주세요.")
        return None, None, None
    
    try:
        # 데이터프레임 복사
        X = df[available_features].copy()
        y = df[target].copy()
        
        # 범주형 변수 전처리
        categorical_features = X.select_dtypes(exclude=[np.number]).columns
        if len(categorical_features) > 0:
            # Label Encoding 적용
            for col in categorical_features:
                le = preprocessing.LabelEncoder()
                X[col] = le.fit_transform(X[col])
        
        # 타겟 변수가 범주형인 경우 (분류 문제)
        if model_type == "분류 분석" and target in categorical_cols:
            le = preprocessing.LabelEncoder()
            y = le.fit_transform(y)
            # 레이블 매핑 정보 저장
            st.session_state[f'{target}_label_mapping'] = dict(zip(le.classes_, le.transform(le.classes_)))
            st.write("클래스 매핑:", st.session_state[f'{target}_label_mapping'])
        
        # 수치형 변수 전처리
        numeric_features = X.select_dtypes(include=[np.number]).columns
        if len(numeric_features) > 0:
            scaler = preprocessing.StandardScaler()
            X[numeric_features] = scaler.fit_transform(X[numeric_features])
        
        return X, y, target
        
    except Exception as e:
        st.error(f"특성 준비 중 오류 발생: {str(e)}")
        return None, None, None

def train_and_evaluate(X, y, target_name, model_type):
    """모델 학습 및 평가"""
    st.subheader("3️⃣ 모델 학습")
    
    # 세션 상태 초기화
    if 'trained_model' not in st.session_state:
        st.session_state.trained_model = None
    
    # 데이터 분할 설정
    test_size = st.slider("테스트 데이터 비율", 0.1, 0.3, 0.2)
    
    # 분류 문제인 경우 클래스 분포 확인
    if model_type == "분류 분석":
        class_counts = pd.Series(y).value_counts()
        st.write("클래스별 데이터 수:")
        st.write(class_counts)
        
        if min(class_counts) < 2:
            st.error("각 클래스당 최소 2개 이상의 데이터가 필요합니다.")
            return None
    
    # 알고리즘 선택
    algorithm = st.selectbox("예측 알고리즘 선택", list(ALGORITHMS[model_type].keys()))
    
    # 학습 버튼
    if st.button("모델 학습 시작", use_container_width=True):
        try:
            # 데이터 분할
            X_train, X_test, y_train, y_test = model_selection.train_test_split(
                X, y, test_size=test_size, 
                shuffle=True, 
                stratify=y if model_type == "분류 분석" else None
            )
            
            # 모델 초기화 및 학습
            with st.spinner('모델 학습 중...'):
                model = ALGORITHMS[model_type][algorithm]()
                model.fit(X_train, y_train)
                
                # 학습된 모델을 세션 상태에 저장
                st.session_state.trained_model = model
                st.session_state.model_data = {
                    'X': X,
                    'y': y,
                    'target_name': target_name,
                    'model_type': model_type,
                    'algorithm': algorithm
                }
            
            # 예측
            y_pred = model.predict(X_test)
            
            # 성능 평가 결과를 세션 상태에 저장
            if model_type == "회귀 분석":
                mse = metrics.mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                r2 = metrics.r2_score(y_test, y_pred)
                
                st.session_state.model_metrics = {
                    'RMSE': rmse,
                    'MSE': mse,
                    'R2': r2
                }
                
                st.write("#### 모델 성능")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("RMSE", f"{rmse:.2f}")
                with col2:
                    st.metric("MSE", f"{mse:.2f}")
                with col3:
                    st.metric("R² Score", f"{r2:.3f}")
                
                # 예측 vs 실제 시각화
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=y_test, name='실제값', mode='markers'))
                fig.add_trace(go.Scatter(y=y_pred, name='예측값', mode='markers'))
                fig.update_layout(title="예측 결과 비교", showlegend=True)
                st.plotly_chart(fig, key="train_evaluation_chart")
                
            else:  # 분류 분석
                accuracy = metrics.accuracy_score(y_test, y_pred)
                precision = metrics.precision_score(y_test, y_pred, average='weighted')
                recall = metrics.recall_score(y_test, y_pred, average='weighted')
                f1 = metrics.f1_score(y_test, y_pred, average='weighted')
                
                st.session_state.model_metrics = {
                    'Accuracy': accuracy,
                    'Precision': precision,
                    'Recall': recall,
                    'F1': f1
                }
                
                st.write("#### 모델 성능")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Accuracy", f"{accuracy:.3f}")
                with col2:
                    st.metric("Precision", f"{precision:.3f}")
                with col3:
                    st.metric("Recall", f"{recall:.3f}")
                with col4:
                    st.metric("F1 Score", f"{f1:.3f}")
                
                # 혼동 행렬 시각화
                cm = metrics.confusion_matrix(y_test, y_pred)
                fig = px.imshow(cm, 
                              labels=dict(x="예측", y="실제"),
                              title="혼동 행렬")
                st.plotly_chart(fig, key="confusion_matrix_chart")
            
            return model
            
        except Exception as e:
            st.error(f"모델 학습 중 오류 발생: {str(e)}")
            return None
    
    # 이전에 학습된 모델이 있으면 반환
    return st.session_state.trained_model if 'trained_model' in st.session_state else None

def make_future_predictions(model, X, target_name, key_suffix=""):
    """미래 예측"""
    st.subheader("4️⃣ 미래 예측")
    
    forecast_periods = st.number_input(
        "예측할 기간 수",
        min_value=1,
        max_value=24,
        value=12,
        key=f"forecast_periods{key_suffix}"
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
        st.plotly_chart(fig, key=f"future_prediction_chart{key_suffix}")
        
        # 예측값 표시
        st.write("#### 예측 결과")
        forecast_df = pd.DataFrame({
            '기간': [f'T+{i+1}' for i in range(forecast_periods)],
            '예측값': future_predictions
        })
        st.dataframe(forecast_df.style.format({'예측값': '{:,.0f}'}), key=f"forecast_df{key_suffix}")
        
    except Exception as e:
        st.error(f"미래 예측 중 오류 발생: {e}")

def load_saved_model():
    """저장된 모델 로드"""
    st.subheader("저장된 모델 불러오기")
    
    uploaded_model = st.file_uploader("모델 파일 업로드 (.joblib)", type=['joblib'], key="model_uploader")
    if uploaded_model is not None:
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(uploaded_model.getvalue())
                model_path = tmp_file.name
            
            # 모델 로드
            model = joblib.load(model_path)
            st.success("모델을 성공적으로 불러왔습니다!")
            
            # 임시 파일 삭제
            os.unlink(model_path)
            return model
        except Exception as e:
            st.error(f"모델 로드 중 오류 발생: {str(e)}")
            return None
    return None

def main():
    st.title("📈 비즈니스 예측 시스템")
    st.write("매출, 비용, 수익성 등 주요 비즈니스 지표 예측")
    
    # 분석 유형 선택
    analysis_type = st.radio(
        "분석 유형 선택",
        ["새로운 분석 시작", "저장된 모델 사용"]
    )
    
    if analysis_type == "새로운 분석 시작":
        # 데이터 로드
        df = load_data()
        
        if df is not None:
            st.write("#### 데이터 미리보기")
            st.dataframe(df.head())
            
            # 분석 유형 선택
            model_type = st.selectbox(
                "모델 유형 선택",
                ["회귀 분석", "분류 분석", "군집 분석"]
            )
            
            # 특성 준비
            X, y, target_name = prepare_features(df, model_type)
            
            if X is not None and y is not None and target_name is not None:
                if model_type == "군집 분석":
                    perform_clustering(X, df)
                else:
                    # 계절성 분석 (시계열 데이터인 경우)
                    if 'date' in df.columns or '날짜' in df.columns:
                        seasonal_patterns = analyze_seasonality(df, target_name)
                    
                    # 모델 학습 및 평가
                    model = train_and_evaluate(X, y, target_name, model_type)
                    
                    if model is not None:
                        # 미래 예측 (한 번만 호출)
                        make_future_predictions(model, X, target_name)
                        
                        # 모델 저장
                        if st.button("모델 저장"):
                            try:
                                save_path = f'{target_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_model.joblib'
                                joblib.dump(st.session_state.trained_model, save_path)
                                
                                # 다운로드 버튼 생성
                                with open(save_path, 'rb') as f:
                                    model_bytes = f.read()
                                st.download_button(
                                    label="모델 다운로드",
                                    data=model_bytes,
                                    file_name=save_path,
                                    mime="application/octet-stream"
                                )
                                st.success(f"모델이 저장되었습니다: {save_path}")
                                
                                # 저장 후 예측 다시 호출하지 않음
                            except Exception as e:
                                st.error(f"모델 저장 중 오류 발생: {str(e)}")
    
    else:  # 저장된 모델 사용
        model = load_saved_model()
        if model is not None:
            # 새로운 데이터 입력
            st.subheader("새로운 데이터 입력")
            
            # 모델의 특성 정보 표시
            if hasattr(model, 'feature_names_in_'):
                st.write("필요한 특성:", ", ".join(model.feature_names_in_))
            
            # 데이터 입력 방식 선택
            input_method = st.radio("데이터 입력 방식", ["수동 입력", "파일 업로드"], key="input_method")
            
            if input_method == "수동 입력":
                # 수동으로 특성값 입력
                input_data = {}
                for i, feature in enumerate(model.feature_names_in_):
                    input_data[feature] = st.number_input(
                        f"{feature} 값 입력",
                        value=0.0,
                        key=f"input_{i}"
                    )
                
                if st.button("예측하기", key="predict_button"):
                    try:
                        # 입력 데이터를 데이터프레임으로 변환
                        input_df = pd.DataFrame([input_data])
                        prediction = model.predict(input_df)
                        st.success(f"예측 결과: {prediction[0]:,.2f}")
                    except Exception as e:
                        st.error(f"예측 중 오류 발생: {str(e)}")
            
            else:  # 파일 업로드
                uploaded_file = st.file_uploader(
                    "예측할 데이터 파일",
                    type=['csv', 'xlsx'],
                    key="prediction_data_uploader"
                )
                if uploaded_file is not None:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            pred_df = pd.read_csv(uploaded_file)
                        else:
                            pred_df = pd.read_excel(uploaded_file)
                        
                        # 필요한 특성이 모두 있는지 확인
                        missing_features = set(model.feature_names_in_) - set(pred_df.columns)
                        if missing_features:
                            st.error(f"다음 특성이 없습니다: {missing_features}")
                        else:
                            predictions = model.predict(pred_df[model.feature_names_in_])
                            pred_df['예측값'] = predictions
                            st.write("예측 결과:")
                            st.dataframe(pred_df)
                    except Exception as e:
                        st.error(f"예측 중 오류 발생: {str(e)}")

def perform_clustering(X, df):
    """군집 분석 수행"""
    st.subheader("군집 분석")
    
    # 알고리즘 선택
    algorithm = st.selectbox("군집화 알고리즘 선택", list(ALGORITHMS["군집 분석"].keys()))
    
    if algorithm == "K-Means":
        n_clusters = st.slider("군집 수 선택", 2, 10, 3)
        model = ALGORITHMS["군집 분석"][algorithm](n_clusters=n_clusters)
    elif algorithm == "DBSCAN":
        eps = st.slider("eps 값 선택", 0.1, 2.0, 0.5)
        min_samples = st.slider("min_samples 값 선택", 2, 10, 5)
        model = ALGORITHMS["군집 분석"][algorithm](eps=eps, min_samples=min_samples)
    else:
        n_clusters = st.slider("군집 수 선택", 2, 10, 3)
        model = ALGORITHMS["군집 분석"][algorithm](n_clusters=n_clusters)
    
    # 군집화 수행
    clusters = model.fit_predict(X)
    
    # 결과 시각화
    if X.shape[1] >= 2:
        fig = px.scatter(
            x=X.iloc[:, 0],
            y=X.iloc[:, 1],
            color=clusters,
            title="군집 분석 결과"
        )
        st.plotly_chart(fig)
    
    # 군집별 통계
    df['Cluster'] = clusters
    st.write("군집별 통계:")
    st.write(df.groupby('Cluster').mean())

if __name__ == "__main__":
    main() 