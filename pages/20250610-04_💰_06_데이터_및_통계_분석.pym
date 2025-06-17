import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.svm import SVC, SVR
from sklearn.metrics import (mean_squared_error, r2_score, accuracy_score, 
                           classification_report, confusion_matrix)
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import os
from openai import OpenAI
import google.generativeai as genai
import anthropic
from dotenv import load_dotenv
import json
import tempfile
from datetime import datetime
import matplotlib.font_manager as fm
import platform

# 한글 폰트 설정
if platform.system() == 'Darwin':  # macOS
    plt.rc('font', family='AppleGothic')
else:  # Windows
    plt.rc('font', family='Malgun Gothic')

# 그래프 스타일 설정
plt.style.use('default')  # seaborn 대신 default 스타일 사용
plt.rc('axes', unicode_minus=False)  # 마이너스 기호 깨짐 방지
plt.rc('figure', figsize=(12, 8))  # 기본 그래프 크기 설정
plt.rc('axes', grid=True)  # 그리드 표시
plt.rc('grid', linestyle='--', alpha=0.7)  # 그리드 스타일 설정

# seaborn 스타일 설정
sns.set_theme(style="whitegrid")  # set_style 대신 set_theme 사용
sns.set_palette("husl")
sns.set_context("notebook", font_scale=1.2)

# .env 파일 로드
load_dotenv()

# AI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def create_figure():
    """새로운 figure 생성 with 스타일 설정"""
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.grid(True, linestyle='--', alpha=0.7)
    return fig, ax

def analyze_with_ai(problem_description, data_description, analysis_type, model_choice="claude-3-5-sonnet-20240620"):
    """AI를 사용하여 데이터 분석 수행"""
    try:
        prompt = f"""다음 문제에 대한 {analysis_type} 분석을 수행해주세요.

분석 문제:
{problem_description}

데이터 설명:
{data_description}

다음 형식으로 응답해주세요:
1. 문제 분석
   - 문제의 핵심 포인트
   - 필요한 분석 방법
   - 예상되는 결과

2. 데이터 분석 계획
   - 데이터 전처리 방법
   - 필요한 변수 변환
   - 분석 단계

3. 권장되는 분석 방법과 그 이유
   - 통계적 방법 선택 이유
   - 머신러닝 모델 선택 이유
   - 장단점 분석

4. Python 코드
   - 데이터 전처리
   - 탐색적 데이터 분석(EDA)
   - 시각화
   - 모델링
   - 성능 평가

5. 결과 해석 방법
   - 주요 지표 해석
   - 시각화 해석
   - 모델 성능 평가

6. 주의사항 및 한계점
   - 데이터 품질 이슈
   - 모델 한계
   - 해석 시 주의점

분석 시 다음 사항을 고려해주세요:
- 데이터의 특성과 분포
- 결측치와 이상치 처리
- 적절한 통계적 방법
- 최적의 머신러닝 모델
- 교차 검증
- 하이퍼파라미터 튜닝
- 결과의 실무적 의미
"""

        if model_choice.startswith("claude"):
            response = anthropic_client.messages.create(
                model=model_choice,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            analysis = response.content[0].text
        elif model_choice == "gemini":
            gemini_model = genai.GenerativeModel('gemini-pro')
            response = gemini_model.generate_content(prompt)
            analysis = response.text
        else:  # GPT-4o-mini
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 데이터 사이언스와 통계 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000
            )
            analysis = response.choices[0].message.content

        return analysis
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def extract_code(analysis, language="python"):
    """AI 응답에서 코드 추출"""
    try:
        code_start = analysis.find(f"```{language}")
        if code_start == -1:
            code_start = analysis.find("```")
        
        if code_start != -1:
            code_start = analysis.find("\n", code_start) + 1
            code_end = analysis.find("```", code_start)
            if code_end != -1:
                return analysis[code_start:code_end].strip()
        return None
    except Exception as e:
        st.error(f"코드 추출 중 오류 발생: {str(e)}")
        return None

def execute_python_analysis(code, dfs):
    """Python 코드 실행"""
    try:
        # 로컬 네임스페이스 설정
        local_dict = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "sns": sns,
            "px": px,
            "go": go,
            "stats": stats,
            "StandardScaler": StandardScaler,
            "LabelEncoder": LabelEncoder,
            "train_test_split": train_test_split,
            "cross_val_score": cross_val_score,
            "LinearRegression": LinearRegression,
            "LogisticRegression": LogisticRegression,
            "DecisionTreeClassifier": DecisionTreeClassifier,
            "DecisionTreeRegressor": DecisionTreeRegressor,
            "RandomForestClassifier": RandomForestClassifier,
            "RandomForestRegressor": RandomForestRegressor,
            "SVC": SVC,
            "SVR": SVR,
            "mean_squared_error": mean_squared_error,
            "r2_score": r2_score,
            "accuracy_score": accuracy_score,
            "classification_report": classification_report,
            "confusion_matrix": confusion_matrix,
            "create_figure": create_figure  # 새로운 figure 생성 함수 추가
        }
        
        # 데이터프레임 추가
        for i, df in enumerate(dfs):
            local_dict[f"df_{i+1}"] = df.copy()
        
        # 코드 실행
        exec(code, globals(), local_dict)
        
        # 결과 반환
        return local_dict.get('result', None), local_dict.get('fig', None)
    except Exception as e:
        st.error(f"Python 코드 실행 중 오류 발생: {str(e)}")
        return None, None

def main():
    st.set_page_config(page_title="데이터 및 통계 분석 도구", page_icon="💰", layout="wide")
    st.title("💰 데이터 및 통계 분석 도구")
    
    # 세션 상태 초기화
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'python_code' not in st.session_state:
        st.session_state.python_code = None
    if 'analysis_completed' not in st.session_state:
        st.session_state.analysis_completed = False
    
    # AI 모델 선택
    model_choice = st.sidebar.selectbox(
        "AI 모델 선택",
        ["claude-3-5-sonnet-20240620", "gpt-4o-mini", "gemini-1.5-flash"],
        index=0
    )
    
    # 분석 유형 선택
    analysis_type = st.sidebar.selectbox(
        "분석 유형 선택",
        ["탐색적 데이터 분석 (EDA)",
         "회귀 분석",
         "분류 분석",
         "시계열 분석",
         "군집 분석",
         "가설 검정",
         "상관 분석",
         "요인 분석"]
    )

    # 분석 문제 입력
    st.header("📝 분석 문제 정의")
    problem_description = st.text_area(
        "분석하고자 하는 문제를 자세히 설명해주세요",
        placeholder="""예시:
1. 분석 목적: 고객 이탈 예측 모델 개발
2. 핵심 질문: 
   - 어떤 요인이 고객 이탈에 가장 큰 영향을 미치는가?
   - 고객 이탈 가능성이 높은 고객을 얼마나 정확하게 예측할 수 있는가?
3. 기대 결과:
   - 고객 이탈 예측 모델
   - 주요 이탈 요인 분석
   - 고객 유지를 위한 실행 가능한 인사이트""",
        height=200
    )
    
    # 파일 업로드
    st.header("📊 데이터 업로드")
    uploaded_files = st.file_uploader(
        "데이터 파일 선택 (CSV, Excel)", 
        type=['csv', 'xlsx'], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        dfs = []  # 데이터프레임 저장 리스트
        
        # 각 파일 처리
        for file in uploaded_files:
            try:
                file_extension = file.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
                dfs.append(df)
                
                st.subheader(f"📊 {file.name} 미리보기")
                st.dataframe(df.head())
                
                # 데이터 정보 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"행 수: {df.shape[0]}")
                with col2:
                    st.write(f"열 수: {df.shape[1]}")
                with col3:
                    st.write(f"결측치 수: {df.isnull().sum().sum()}")
                
                # 데이터 타입 정보
                st.write("데이터 타입 정보:")
                st.write(df.dtypes)
                
                # 기본 통계량
                st.write("기본 통계량:")
                st.write(df.describe())
                
                # 결측치 시각화
                fig, ax = create_figure()
                sns.heatmap(df.isnull(), yticklabels=False, cbar=False, cmap='viridis')
                plt.title('결측치 분포', pad=20)
                st.pyplot(fig)
                plt.close()
                
                # 수치형 변수 분포 시각화
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    st.subheader("수치형 변수 분포")
                    for i in range(0, len(numeric_cols), 2):
                        cols = numeric_cols[i:min(i+2, len(numeric_cols))]
                        fig, ax = create_figure()
                        for col in cols:
                            sns.histplot(data=df, x=col, kde=True, ax=ax)
                            plt.title(f'{col} 분포', pad=20)
                        st.pyplot(fig)
                        plt.close()
                
            except Exception as e:
                st.error(f"{file.name} 처리 중 오류 발생: {str(e)}")
        
        # 분석 지침 입력
        st.header("🎯 분석 지침")
        analysis_instructions = st.text_area(
            "추가적인 분석 지침을 입력해주세요",
            placeholder="특별히 고려해야 할 사항이나 제약 조건이 있다면 입력해주세요.",
            height=100
        )
        
        if st.button("AI 분석 시작", use_container_width=True):
            if problem_description:
                with st.spinner("AI가 데이터를 분석중입니다..."):
                    # 데이터 설명 생성
                    data_description = "\n\n".join([
                        f"데이터셋 {i+1}:\n"
                        f"- 파일명: {file.name}\n"
                        f"- 크기: {df.shape}\n"
                        f"- 컬럼: {', '.join(df.columns)}\n"
                        f"- 데이터 타입:\n{df.dtypes.to_string()}\n"
                        f"- 기본 통계량:\n{df.describe().to_string()}"
                        for i, (file, df) in enumerate(zip(uploaded_files, dfs))
                    ])
                    
                    # AI 분석 수행
                    analysis = analyze_with_ai(
                        problem_description,
                        f"{data_description}\n\n추가 지침:\n{analysis_instructions}",
                        analysis_type,
                        model_choice
                    )
                    
                    if analysis:
                        st.session_state.analysis_result = analysis
                        st.session_state.analysis_completed = True
                        python_code = extract_code(analysis, "python")
                        if python_code:
                            st.session_state.python_code = python_code
            else:
                st.warning("분석 문제를 입력해주세요.")

        # 분석 결과 표시 (세션 상태 사용)
        if st.session_state.analysis_completed:
            st.subheader("🤖 AI 분석 결과")
            st.markdown(st.session_state.analysis_result)
            
            if st.session_state.python_code:
                st.subheader("🐍 Python 분석")
                st.code(st.session_state.python_code, language="python")
                
                if st.button("Python 코드 실행", key="execute_python", use_container_width=True):
                    with st.spinner("Python 분석 실행 중..."):
                        result, fig = execute_python_analysis(st.session_state.python_code, dfs)
                        
                        if result is not None:
                            st.subheader("Python 분석 결과")
                            st.write(result)
                        
                        if fig is not None:
                            st.pyplot(fig)

if __name__ == "__main__":
    main()
