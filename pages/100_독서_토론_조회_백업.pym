import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import json

load_dotenv()

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def main():
    st.title("독서토론 조회")
    
    # OpenAI API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        st.stop()
    
    # AI 모델 선택 (기본값: GPT-4)
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
    ai_models = {
        "GPT-4": MODEL_NAME,
        "GPT-3.5": "gpt-3.5-turbo"
    }
    
    # 고급 설정 섹션
    with st.expander("고급 설정"):
        use_local_llm = st.checkbox("로컬 LLM 사용", value=False)
        
        if use_local_llm:
            local_models = {
                "Deepseek 14B": "deepseek-r1:14b",
                "Deepseek 32B": "deepseek-r1:32b",
                "Llama 3.1": "llama3.1:latest",
                "Phi-4": "phi4:latest",
                "Mistral": "mistral:latest"
            }
            selected_model = st.selectbox(
                "로컬 LLM 모델 선택",
                list(local_models.keys())
            )
            model_key = f"Local - {selected_model}"
            model_name = local_models[selected_model]
        else:
            selected_model = st.selectbox(
                "OpenAI 모델 선택",
                list(ai_models.keys()),
                index=0
            )
            model_key = selected_model
            model_name = ai_models[selected_model]
    
    # 필터 옵션
    col1, col2 = st.columns(2)
    
    with col1:
        titles = get_book_titles()
        if "퍼스널 MBA" not in titles:
            titles = ["퍼스널 MBA"] + titles
        
        selected_title = st.selectbox(
            "책 선택",
            titles,
            index=titles.index("퍼스널 MBA") if "퍼스널 MBA" in titles else 0
        )
    
    with col2:
        type_mapping = {
            "요약": "summary",
            "적용": "application"
        }
        material_type = st.selectbox(
            "자료 유형",
            list(type_mapping.keys())
        )
    
    # 적용 자료인 경우 분석 키워드 선택
    analysis_keyword = None
    if material_type == "적용":
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords)
        
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력")
        else:
            analysis_keyword = selected_keyword
    
    # 파일 목록 조회
    files = get_files(selected_title, type_mapping[material_type])
    
    if files:
        selected_file = st.selectbox(
            "파일 선택",
            files,
            format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})"
        )
        
        if selected_file:
            st.write(f"### {selected_file['file_name']}")
            st.markdown(selected_file['content'])
            st.write("---")
            st.write(f"*등록일: {selected_file['created_at'].strftime('%Y-%m-%d')}*")
            
            # AI 분석 (적용 자료이고 키워드가 선택된 경우)
            if material_type == "적용" and analysis_keyword:
                if st.button("AI 분석"):
                    with st.spinner("AI가 분석 중입니다..."):
                        analysis = analyze_content(
                            selected_file['content'],
                            analysis_keyword,
                            model_key,
                            model_name
                        )
                        
                        st.write("### AI 분석 결과")
                        st.write(analysis)
    else:
        st.info(f"{selected_title}의 {material_type} 자료가 없습니다.")

def get_files(book_title, material_type):
    """파일 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT *
            FROM reading_materials
            WHERE book_title = %s
            AND type = %s
            ORDER BY created_at DESC
        """, (book_title, material_type))
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_book_titles():
    """저장된 책 제목 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT book_title
            FROM reading_materials
            ORDER BY book_title
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def analyze_content(content, keyword, model_key, model_name):
    """AI를 사용하여 내용 분석"""
    keyword_guide = {
        "가치 창출": """
            - 고객에게 제공하는 핵심 가치
            - 가치 창출 방식과 프로세스
            - 차별화된 가치 제안
            - 수익 창출 구조
        """,
        "마케팅": """
            - 목표 시장 정의
            - 마케팅 전략과 채널
            - 고객 획득 방안
            - 브랜드 포지셔닝
        """,
        "세일즈": """
            - 판매 전략과 프로세스
            - 영업 조직과 운영
            - 매출 목표와 계획
            - 고객 관리 방안
        """,
        "가치 전달": """
            - 서비스 제공 프로세스
            - 고객 경험 관리
            - 품질 관리 체계
            - 고객 지원 체계
        """,
        "재무": """
            - 수익성 분석
            - 비용 구조
            - 투자 계획
            - 재무적 지속가능성
        """
    }

    base_prompt = f"""
    당신은 경영 컨설턴트입니다. 다음 사업계획서를 '{keyword}' 관점에서만 집중적으로 분석해주세요.
    
    특히 다음 항목들을 중점적으로 검토하세요:
    {keyword_guide.get(keyword, "키워드와 관련된 모든 측면을 검토")}

    분석할 텍스트:
    {content}

    다음 형식으로 정확하게 답변해주세요:

    [키워드 반영도] (상/중/하 중 하나만 선택)
    [평가 근거]
    - {keyword}와 관련된 구체적인 근거 2-3줄

    [전체 논평]
    - {keyword} 관점에서의 강점과 차별화 요소
    - {keyword} 실행 가능성
    - {keyword} 관련 시장 경쟁력

    [보완 필요사항]
    - {keyword} 실행 방안 보완점
    - {keyword} 관련 위험 요소 대응
    - {keyword} 시장 대응 전략
    """

    if "Local" in model_key:
        prompt = f"""You are a business consultant analyzing a business plan specifically focusing on '{keyword}'.
        Please provide your analysis in Korean, strictly following this format:

        [키워드 반영도] 
        '{keyword}'에 대해 '상', '중', '하' 중 하나만 선택

        [평가 근거]
        '{keyword}'와 직접 관련된 구체적 근거만 2-3줄로 작성

        [전체 논평]
        '{keyword}' 관점에서만 다음 내용을 3-4줄로 작성:
        - 강점과 차별화 요소
        - 실현 가능성
        - 시장 경쟁력

        [보완 필요사항]
        '{keyword}'에 관련된 다음 세 가지를 각각 한 줄로 작성:
        - 구체적인 실행 방안
        - 위험 요소 대응 방안
        - 시장 대응 전략

        Review guidelines for '{keyword}':
        {keyword_guide.get(keyword, "키워드와 관련된 모든 측면을 검토")}

        {base_prompt}

        Important:
        1. Focus ONLY on aspects related to '{keyword}'
        2. Provide ALL responses in Korean
        3. Follow the exact format specified
        4. Make practical and specific suggestions
        """
    else:
        prompt = base_prompt

    try:
        if "Local" in model_key:
            return analyze_with_local_llm(prompt, model_name)
        else:
            return analyze_with_openai(prompt, model_name)
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def analyze_with_openai(prompt, model):
    """OpenAI API를 사용한 분석"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 경영 컨설턴트로서 사업계획서를 분석하고 실용적인 조언을 제공합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        if hasattr(response.choices[0].message, 'content'):
            return response.choices[0].message.content
        else:
            st.error("API 응답에 content가 없습니다.")
            return None
            
    except Exception as e:
        st.error(f"OpenAI API 호출 중 오류 발생: {str(e)}")
        return None

def analyze_with_local_llm(prompt, model):
    """로컬 LLM을 사용한 분석"""
    url = "http://localhost:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, json=data, stream=True)
        
        # 전체 응답 텍스트를 저장할 변수
        full_response = ""
        
        # 스트리밍 응답 처리
        for line in response.iter_lines():
            if line:
                # 각 라인을 JSON으로 파싱
                json_response = json.loads(line)
                if 'response' in json_response:
                    # 응답 텍스트 누적
                    full_response += json_response['response']
                    
                # 완료 여부 확인
                if json_response.get('done', False):
                    break
        
        return full_response
        
    except Exception as e:
        st.error(f"로컬 LLM 호출 중 오류 발생: {str(e)}")
        return None

if __name__ == "__main__":
    main() 