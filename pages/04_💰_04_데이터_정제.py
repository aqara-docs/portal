import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import tempfile
import base64
from datetime import datetime

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def clean_data_with_ai(df, cleaning_instructions):
    """AI를 사용하여 데이터 클리닝"""
    try:
        # 데이터프레임을 문자열로 변환
        df_str = df.to_string()
        
        # 프롬프트 생성
        prompt = f"""다음 데이터를 분석하고 클리닝해주세요.

데이터:
{df_str}

클리닝 지침:
{cleaning_instructions}

다음 형식으로 응답해주세요:
1. 데이터 분석 결과
2. 발견된 문제점
3. 클리닝 제안
4. Python 코드 (pandas를 사용한 데이터 클리닝 코드)

주의사항:
- 데이터는 이미 'df' 변수에 로드되어 있습니다. 파일을 다시 읽지 마세요.
- 'df'를 직접 수정하여 클리닝을 수행하세요.
- pd.read_csv나 pd.read_excel 같은 파일 읽기 함수를 사용하지 마세요.

코드 예시:
```python
# 잘못된 예:
df = pd.read_csv('파일경로')  # 파일을 다시 읽지 마세요

# 올바른 예:
df = df.dropna()  # 기존 df를 직접 수정
```

코드는 실행 가능한 형태로 제공해주세요."""

        # OpenAI GPT 사용
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "당신은 데이터 분석과 클리닝 전문가입니다. 데이터는 이미 'df' 변수에 로드되어 있으므로, 파일을 다시 읽지 말고 기존 df를 직접 수정하세요."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000
        )
        analysis = response.choices[0].message.content

        return analysis
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def extract_python_code(analysis):
    """AI 응답에서 Python 코드 추출"""
    try:
        # 코드 블록 찾기
        code_start = analysis.find("```python")
        code_end = analysis.find("```", code_start + 8)
        
        if code_start != -1 and code_end != -1:
            code = analysis[code_start + 8:code_end].strip()
            return code
        return None
    except Exception as e:
        st.error(f"코드 추출 중 오류 발생: {str(e)}")
        return None

def apply_cleaning_code(df, code):
    """추출된 Python 코드 적용"""
    try:
        # 자주 사용되는 데이터 클리닝 함수들
        def remove_unnamed_columns(df):
            # 컬럼 이름을 문자열로 변환하여 처리
            columns_to_keep = []
            for col in df.columns:
                col_str = str(col)
                if not col_str.startswith('Unnamed:') and not 'Unnamed' in col_str:
                    columns_to_keep.append(col)
            return df[columns_to_keep]
            
        def remove_empty_columns(df):
            return df.dropna(axis=1, how='all')
            
        def remove_empty_rows(df):
            return df.dropna(how='all')
            
        def convert_numeric(df, columns):
            for col in columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
            
        def clean_column_names(df):
            # 컬럼 이름을 문자열로 변환하고 공백 제거
            df.columns = [str(col).strip() for col in df.columns]
            return df

        # 로컬 네임스페이스 생성 및 자주 사용되는 변수들 초기화
        local_dict = {
            "df": df.copy(),
            "pd": pd,
            "np": np,
            "n": None,
            "i": 0,
            "x": 0,
            "y": 0,
            "value": 0,
            "count": 0,
            "remove_unnamed_columns": remove_unnamed_columns,
            "remove_empty_columns": remove_empty_columns,
            "remove_empty_rows": remove_empty_rows,
            "convert_numeric": convert_numeric,
            "clean_column_names": clean_column_names
        }
        
        # 허용된 import 구문 목록
        allowed_imports = {
            "import pandas as pd",
            "import numpy as np",
            "from pandas import",
            "from numpy import"
        }
        
        # 코드를 여러 줄로 분리
        code_lines = code.strip().split('\n')
        cleaned_code_lines = []
        
        # 각 줄 검사 및 실행
        for i, line in enumerate(code_lines, 1):
            line = line.strip()
            
            # 빈 줄 무시
            if not line:
                continue
                
            # 주석 줄은 그대로 포함
            if line.startswith('#'):
                cleaned_code_lines.append(line)
                continue
                
            # import 구문 검사
            if line.startswith(("import", "from")):
                if not any(line.startswith(allowed) for allowed in allowed_imports):
                    raise SecurityError(f"허용되지 않은 import 구문: {line}")
                continue  # 허용된 import는 건너뛰기 (이미 로컬 네임스페이스에 있음)
            
            # 기타 보안 검사
            if "exec" in line or "eval" in line:
                raise SecurityError(f"보안상의 이유로 exec, eval 구문은 실행할 수 없습니다: {line}")
            
            cleaned_code_lines.append(line)
        
        # 정제된 코드 실행
        for i, line in enumerate(cleaned_code_lines, 1):
            try:
                exec(line, globals(), local_dict)
            except Exception as e:
                st.error(f"코드 {i}번째 줄에서 오류 발생: {line}\n오류 내용: {str(e)}")
                return None
        
        # 클리닝된 데이터프레임 반환
        return local_dict["df"]
    except SecurityError as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"코드 적용 중 오류 발생: {str(e)}")
        return None

class SecurityError(Exception):
    pass

def create_download_link(df, filename):
    """데이터프레임 다운로드 링크 생성"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">다운로드</a>'
    return href

def main():
    st.set_page_config(page_title="데이터 정제 도구", page_icon="💰", layout="wide")
    st.title("💰 데이터 정제 도구")

    # 세션 상태 초기화
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cleaning_code' not in st.session_state:
        st.session_state.cleaning_code = None
    if 'cleaned_df' not in st.session_state:
        st.session_state.cleaned_df = None
    if 'original_df' not in st.session_state:
        st.session_state.original_df = None

    # 파일 업로드
    uploaded_file = st.file_uploader("데이터 파일 선택 (CSV, Excel)", type=['csv', 'xlsx'])

    if uploaded_file is not None:
        try:
            # 파일 확장자 확인
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            # 파일 읽기
            if file_extension == 'csv':
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            # 원본 데이터프레임 저장
            st.session_state.original_df = df

            # 데이터 미리보기
            st.subheader("📊 원본 데이터 미리보기")
            st.dataframe(df.head())

            # 데이터 정보 표시
            st.subheader("📋 데이터 정보")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"행 수: {df.shape[0]}")
            with col2:
                st.write(f"열 수: {df.shape[1]}")
            with col3:
                st.write(f"결측치 수: {df.isnull().sum().sum()}")

            # 클리닝 지침 입력
            cleaning_instructions = st.text_area(
                "클리닝 지침 입력",
                placeholder="예: 결측치 처리, 이상치 제거, 데이터 타입 변환 등",
                height=100
            )

            if st.button("AI 분석 시작", use_container_width=True):
                if cleaning_instructions:
                    with st.spinner("AI가 데이터를 분석중입니다..."):
                        # AI 분석 수행
                        analysis = clean_data_with_ai(df, cleaning_instructions)
                        st.session_state.analysis_result = analysis
                        
                        if analysis:
                            st.subheader("🤖 AI 분석 결과")
                            st.markdown(analysis)

                            # Python 코드 추출 및 적용
                            code = extract_python_code(analysis)
                            if code:
                                st.session_state.cleaning_code = code
                                st.subheader("🔍 추출된 Python 코드")
                                st.code(code, language="python")

            # 저장된 분석 결과와 코드 표시
            if st.session_state.analysis_result:
                st.subheader("🤖 AI 분석 결과")
                st.markdown(st.session_state.analysis_result)

                if st.session_state.cleaning_code:
                    st.subheader("🔍 추출된 Python 코드")
                    st.code(st.session_state.cleaning_code, language="python")

                    # 코드 적용 여부 확인
                    if st.button("클리닝 코드 적용", use_container_width=True):
                        cleaned_df = apply_cleaning_code(st.session_state.original_df, st.session_state.cleaning_code)
                        st.session_state.cleaned_df = cleaned_df
                        
                        if cleaned_df is not None:
                            st.subheader("✨ 클리닝된 데이터")
                            st.dataframe(cleaned_df.head())

                            # 변경된 내용 표시
                            st.subheader("📊 데이터 변경 사항")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write("**원본 데이터 정보**")
                                st.write(f"- 행 수: {st.session_state.original_df.shape[0]}")
                                st.write(f"- 열 수: {st.session_state.original_df.shape[1]}")
                                st.write(f"- 결측치 수: {st.session_state.original_df.isnull().sum().sum()}")
                            with col2:
                                st.write("**클리닝된 데이터 정보**")
                                st.write(f"- 행 수: {cleaned_df.shape[0]}")
                                st.write(f"- 열 수: {cleaned_df.shape[1]}")
                                st.write(f"- 결측치 수: {cleaned_df.isnull().sum().sum()}")

                            # 다운로드 링크 생성
                            st.markdown("### 📥 클리닝된 데이터 다운로드")
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"cleaned_data_{timestamp}.csv"
                            st.markdown(create_download_link(cleaned_df, filename), unsafe_allow_html=True)

            if not cleaning_instructions and st.session_state.analysis_result is None:
                st.warning("클리닝 지침을 입력해주세요.")

        except Exception as e:
            st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main() 