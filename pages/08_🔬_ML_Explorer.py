import streamlit as st
import pandas as pd
import numpy as np
from sklearn import (
    linear_model, tree, ensemble, svm, neural_network, 
    preprocessing, metrics, model_selection
)
from sklearn.impute import SimpleImputer
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import json
import base64

# 페이지 설정
st.set_page_config(
    page_title="ML Explorer",
    page_icon="🔬",
    layout="wide"
)

# 사용 가능한 ML 알고리즘
ALGORITHMS = {
    "회귀": {
        "Linear Regression": linear_model.LinearRegression,
        "Ridge Regression": linear_model.Ridge,
        "Lasso Regression": linear_model.Lasso,
        "Decision Tree Regressor": tree.DecisionTreeRegressor,
        "Random Forest Regressor": ensemble.RandomForestRegressor,
        "SVR": svm.SVR,
        "Neural Network Regressor": neural_network.MLPRegressor
    },
    "분류": {
        "Logistic Regression": linear_model.LogisticRegression,
        "Decision Tree Classifier": tree.DecisionTreeClassifier,
        "Random Forest Classifier": ensemble.RandomForestClassifier,
        "SVC": svm.SVC,
        "Neural Network Classifier": neural_network.MLPClassifier
    }
}

def load_data():
    """데이터 로드 함수"""
    uploaded_file = st.file_uploader(
        "데이터 파일 업로드 (CSV, Excel, Google Sheets)", 
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

def explore_data(df):
    """데이터 탐색 함수"""
    st.subheader("1. 데이터 기본 정보")
    
    # 기본 정보 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("행 수", df.shape[0])
    with col2:
        st.metric("열 수", df.shape[1])
    with col3:
        st.metric("결측치가 있는 열 수", df.isna().any().sum())
    
    # 데이터 미리보기
    st.subheader("2. 데이터 미리보기")
    st.dataframe(df.head())
    
    # 기술 통계량
    st.subheader("3. 기술 통계량")
    st.dataframe(df.describe())
    
    # 결측치 시각화
    st.subheader("4. 결측치 분포")
    missing_data = df.isnull().sum()
    if missing_data.any():
        fig = px.bar(
            x=missing_data.index,
            y=missing_data.values,
            title="컬럼별 결측치 수"
        )
        st.plotly_chart(fig)
    
    # 상관관계 분석
    st.subheader("5. 상관관계 분석")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 1:
        corr = df[numeric_cols].corr()
        fig = px.imshow(
            corr,
            title="상관관계 히트맵",
            labels=dict(color="상관계수")
        )
        st.plotly_chart(fig)

def prepare_data(df):
    """데이터 전처리 함수"""
    st.subheader("데이터 전처리")
    
    # 데이터 타입 정보 표시
    st.write("컬럼별 데이터 타입:")
    dtype_df = pd.DataFrame({
        '데이터 타입': df.dtypes,
        '고유값 수': df.nunique(),
        '샘플 값': [df[col].iloc[0] if len(df) > 0 else None for col in df.columns]
    })
    st.dataframe(dtype_df)
    
    # 타겟 변수 선택
    target = st.selectbox("타겟 변수 선택", df.columns)
    features = st.multiselect("특성 변수 선택", [col for col in df.columns if col != target])
    
    if not features:
        st.warning("특성 변수를 선택해주세요.")
        return None, None
    
    # 전처리 옵션
    st.write("전처리 옵션:")
    handle_missing = st.checkbox("결측치 처리", value=True)
    scale_features = st.checkbox("특성 스케일링")
    encode_categorical = st.checkbox("범주형 변수 인코딩", value=True)
    
    try:
        X = df[features].copy()
        y = df[target].copy()
        
        # 데이터 타입 자동 감지 및 변환
        for col in X.columns:
            try:
                X[col] = pd.to_numeric(X[col], errors='raise')
            except (ValueError, TypeError):
                X[col] = X[col].astype(str)
        
        # 결측치 처리
        if handle_missing:
            # 숫자형 컬럼
            num_cols = X.select_dtypes(include=[np.number]).columns
            if len(num_cols) > 0:
                num_imputer = SimpleImputer(strategy='mean')
                X[num_cols] = num_imputer.fit_transform(X[num_cols])
            
            # 범주형 컬럼
            cat_cols = X.select_dtypes(exclude=[np.number]).columns
            if len(cat_cols) > 0:
                cat_imputer = SimpleImputer(strategy='most_frequent')
                X[cat_cols] = cat_imputer.fit_transform(X[cat_cols])
        
        # 범주형 변수 인코딩
        if encode_categorical:
            cat_cols = X.select_dtypes(exclude=[np.number]).columns
            if len(cat_cols) > 0:
                # Label Encoding for target if it's categorical
                if not pd.api.types.is_numeric_dtype(y):
                    label_encoder = preprocessing.LabelEncoder()
                    y = label_encoder.fit_transform(y)
                    st.info(f"타겟 변수의 클래스: {list(label_encoder.classes_)}")
                
                # One-Hot Encoding for features
                encoder = preprocessing.OneHotEncoder(
                    sparse_output=False,
                    handle_unknown='ignore'
                )
                encoded_cats = encoder.fit_transform(X[cat_cols])
                encoded_df = pd.DataFrame(
                    encoded_cats,
                    columns=encoder.get_feature_names_out(cat_cols)
                )
                
                # 원본 데이터에서 범주형 컬럼 제거하고 인코딩된 결과 추가
                X = pd.concat([X.select_dtypes(include=[np.number]), encoded_df], axis=1)
                
                # 인코딩 결과 표시
                st.write("인코딩된 특성:", X.columns.tolist())
        
        # 특성 스케일링
        if scale_features and len(X.select_dtypes(include=[np.number]).columns) > 0:
            scaler = preprocessing.StandardScaler()
            X = pd.DataFrame(
                scaler.fit_transform(X),
                columns=X.columns
            )
        
        # 최종 데이터셋 미리보기
        st.write("전처리 완료된 데이터 미리보기:")
        st.write("X shape:", X.shape)
        st.write("y shape:", y.shape)
        st.dataframe(X.head())
        
        return X, y
        
    except Exception as e:
        st.error(f"데이터 전처리 중 오류 발생: {str(e)}")
        return None, None

def train_model(X, y, task_type="회귀"):
    """모델 학습 함수"""
    st.subheader("모델 학습")
    
    # 알고리즘 선택
    algorithm = st.selectbox(
        "알고리즘 선택",
        options=list(ALGORITHMS[task_type].keys())
    )
    
    # 학습/테스트 분할
    test_size = st.slider("테스트 세트 비율", 0.1, 0.5, 0.2)
    
    try:
        # 데이터 분할
        X_train, X_test, y_train, y_test = model_selection.train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # 모델 학습
        model = ALGORITHMS[task_type][algorithm]()
        model.fit(X_train, y_train)
        
        # 예측
        y_pred = model.predict(X_test)
        
        # 성능 평가
        if task_type == "회귀":
            mse = metrics.mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = metrics.r2_score(y_test, y_pred)
            
            st.write("모델 성능:")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("MSE", f"{mse:.4f}")
            with col2:
                st.metric("RMSE", f"{rmse:.4f}")
            with col3:
                st.metric("R2 Score", f"{r2:.4f}")
            
            # 실제값 vs 예측값 산점도
            fig = px.scatter(
                x=y_test, y=y_pred,
                labels={"x": "실제값", "y": "예측값"},
                title="실제값 vs 예측값"
            )
            fig.add_trace(
                go.Scatter(x=[y_test.min(), y_test.max()], 
                          y=[y_test.min(), y_test.max()],
                          mode='lines', name='Perfect Prediction')
            )
            st.plotly_chart(fig)
            
        else:  # 분류
            accuracy = metrics.accuracy_score(y_test, y_pred)
            precision = metrics.precision_score(y_test, y_pred, average='weighted')
            recall = metrics.recall_score(y_test, y_pred, average='weighted')
            
            st.write("모델 성능:")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Accuracy", f"{accuracy:.4f}")
            with col2:
                st.metric("Precision", f"{precision:.4f}")
            with col3:
                st.metric("Recall", f"{recall:.4f}")
            
            # 혼동 행렬
            cm = metrics.confusion_matrix(y_test, y_pred)
            fig = px.imshow(
                cm,
                labels=dict(x="예측값", y="실제값"),
                title="혼동 행렬"
            )
            st.plotly_chart(fig)
        
        return model
        
    except Exception as e:
        st.error(f"모델 학습 중 오류 발생: {e}")
        return None

def export_results(model, X, y):
    """결과 내보내기 함수"""
    st.subheader("결과 내보내기")
    
    # 모델 저장
    if st.button("모델 저장"):
        try:
            joblib.dump(model, 'trained_model.joblib')
            st.success("모델이 'trained_model.joblib'로 저장되었습니다.")
        except Exception as e:
            st.error(f"모델 저장 중 오류 발생: {e}")
    
    # 마크다운 리포트 생성
    if st.button("마크다운 리포트 생성"):
        try:
            report = generate_markdown_report(model, X, y)
            download_link = create_download_link(report, "report.md")
            st.markdown(download_link, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"리포트 생성 중 오류 발생: {e}")

def generate_markdown_report(model, X, y):
    """마크다운 리포트 생성 함수"""
    report = f"""# 머신러닝 분석 리포트

## 1. 데이터셋 정보
- 샘플 수: {X.shape[0]}
- 특성 수: {X.shape[1]}
- 특성 이름: {', '.join(X.columns)}

## 2. 모델 정보
- 알고리즘: {type(model).__name__}
- 모델 파라미터: {model.get_params()}

## 3. 성능 지표
"""
    # 여기에 성능 지표 추가
    
    return report

def create_download_link(content, filename):
    """다운로드 링크 생성 함수"""
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:text/markdown;base64,{b64}" download="{filename}">리포트 다운로드</a>'

def main():
    st.title("🔬 ML Explorer")
    st.write("데이터 분석과 머신러닝을 위한 올인원 도구")
    
    # 데이터 로드
    df = load_data()
    
    if df is not None:
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["데이터 탐색", "모델 학습", "결과 내보내기"])
        
        with tab1:
            explore_data(df)
        
        with tab2:
            X, y = prepare_data(df)
            if X is not None and y is not None:
                task_type = st.radio("작업 유형", ["회귀", "분류"])
                model = train_model(X, y, task_type)
        
        with tab3:
            if 'model' in locals() and model is not None:
                export_results(model, X, y)

if __name__ == "__main__":
    main() 