import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import json
import base64

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
    st.title("📚 독서 토론 조회")
    
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
            "적용": "application",
            "적용 비교": "application_compare"  # 새로운 유형 추가
        }
        material_type = st.selectbox(
            "자료 유형",
            list(type_mapping.keys())
        )
    
    # 적용 자료인 경우 분석 키워드 선택
    analysis_keyword = None
    if material_type in ["적용", "적용 비교"]:
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords)
        
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력")
        else:
            analysis_keyword = selected_keyword
    
    # 적용 비교 모드
    if material_type == "적용 비교":
        show_application_comparison(selected_title, analysis_keyword, model_key, model_name)
    else:
        # 기존 파일 목록 조회 및 표시 로직
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
                
                # AI 분석/의견 버튼
                if material_type == "적용" and analysis_keyword:
                    # AI 분석 결과 표시 컨테이너 생성
                    analysis_container = st.container()
                    
                    if st.button("AI 분석"):
                        with st.spinner("AI가 분석 중입니다..."):
                            analysis = analyze_content(
                                selected_file['content'],
                                analysis_keyword,
                                model_key,
                                model_name
                            )
                            st.session_state.ai_analysis = analysis
                    
                    # AI 분석 결과가 있으면 표시
                    if 'ai_analysis' in st.session_state:
                        with analysis_container:
                            st.write("### AI 분석 결과")
                            st.write(st.session_state.ai_analysis)
                            
                            # 음성 재생 버튼
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                if st.button("🔊 음성으로 듣기"):
                                    with st.spinner("음성을 생성하고 있습니다..."):
                                        # AI 분석 결과만 음성으로 변환
                                        audio_html = text_to_speech(st.session_state.ai_analysis)
                                        if audio_html:
                                            st.markdown(audio_html, unsafe_allow_html=True)
                
                elif material_type == "요약":
                    # AI 의견 표시 컨테이너 생성
                    opinion_container = st.container()
                    
                    # AI 의견 생성 버튼
                    if st.button("🤖 AI 의견 생성"):
                        with st.spinner("AI가 의견을 생성하고 있습니다..."):
                            st.session_state.ai_opinion = generate_business_opinion(selected_file['content'])
                    
                    # AI 의견이 있으면 표시
                    if 'ai_opinion' in st.session_state:
                        with opinion_container:
                            st.write("### 💡 AI 의견")
                            st.write(st.session_state.ai_opinion)
                            
                            # 음성 재생 버튼
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                if st.button("🔊 음성으로 듣기"):
                                    with st.spinner("음성을 생성하고 있습니다..."):
                                        combined_text = f"""
                                        요약 내용입니다.
                                        {selected_file['content']}
                                        
                                        AI 의견입니다.
                                        {st.session_state.ai_opinion}
                                        """
                                        audio_html = text_to_speech(combined_text)
                                        if audio_html:
                                            st.markdown(audio_html, unsafe_allow_html=True)
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
    base_prompt = f"""
    다음 사업계획서를 '{keyword}' 관점에서만 집중적으로 분석해 주세요.
    다른 관점은 제외하고 오직 '{keyword}' 측면에서만 검토해 주시기 바랍니다.

    분석할 텍스트:
    {content}
    
    다음 형식으로 답변해 주세요:

    [핵심 요약]
    - '{keyword}' 관점에서만 본 핵심 내용을 2-3줄로 요약해 주세요
    - '{keyword}' 측면의 가장 중요한 시사점 1-2가지를 제시해 주세요

    [주요 분석]
    1. '{keyword}' 관련 강점 (2가지)
        - 각 강점이 '{keyword}' 측면에서 가지는 구체적 근거와 효과
    
    2. '{keyword}' 측면의 개선점 (2가지)
        - 각 개선점이 '{keyword}' 관점에서 가지는 문제와 해결 방안

    [실행 제안]
    1. '{keyword}' 중심의 단기 과제 (1-3개월)
        - '{keyword}' 강화를 위한 즉시 실행 가능한 2가지 방안
        - 각각이 '{keyword}' 측면에서 가져올 기대효과
    
    2. '{keyword}' 중심의 중기 과제 (3-6개월)
        - '{keyword}' 역량 강화를 위한 2가지 전략 방안
        - '{keyword}' 관점의 실행 단계와 성과 지표

    * 모든 내용을 '{keyword}' 관점에서만 구체적이고 실용적으로 작성해 주시되, 존댓말을 사용해 주세요.
    * 다른 관점이나 주제는 제외하고, 오직 '{keyword}'에만 집중해 주세요.
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
        - 실행 가능성
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

def generate_business_opinion(summary_text):
    """비즈니스 관점에서의 AI 의견 생성"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # 비즈니스 관련 키워드
    business_keywords = [
        "전략", "성과", "효율", "생산성", "혁신", "성장", "매출", "비용",
        "고객", "시장", "경쟁", "가치", "리더십", "관리", "운영", "프로세스"
    ]
    
    # 가장 관련성 높은 문장 선택
    sentences = [s.strip() for s in summary_text.split('.') if len(s.strip()) > 10]
    best_sentence = max(sentences, 
                       key=lambda x: sum(1 for keyword in business_keywords if keyword in x),
                       default=None)
    
    if not best_sentence:
        return "요약 내용에서 비즈니스 관련 주제를 찾을 수 없습니다."
    
    # 문장에서 핵심 주제 추출
    prompt_for_topic = f"""
    다음 문장에서 가장 중요한 비즈니스 관련 핵심 주제 하나만 5단어 이내로 추출해주세요:
    "{best_sentence}"
    
    예시 형식: "고객 가치 창출", "효율적 리더십", "시장 확장 전략" 등
    """
    
    try:
        # 핵심 주제 추출
        topic_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 텍스트에서 핵심 주제를 정확하게 추출하는 전문가입니다."},
                {"role": "user", "content": prompt_for_topic}
            ],
            temperature=0.3,
            max_tokens=20
        )
        
        core_topic = topic_response.choices[0].message.content.strip().strip('"\'')
        
        # 추출된 주제에 대한 의견 생성
        opinion_prompt = f"""
        다음은 독서 토론에서 나온 중요한 비즈니스 주제입니다:
        
        주제: "{core_topic}"
        
        관련 문장: "{best_sentence}"
        
        이 주제에 대해 비즈니스 전문가의 입장에서 의견을 제시해주세요:
        - "오늘 독서 토론에서 다룬 '{core_topic}'에 대해 말씀드리겠습니다."로 시작하여
        - 이 주제가 비즈니스에 어떤 의미가 있는지
        - 어떻게 실제로 적용해볼 수 있는지
        - 구체적인 실행 방안까지 자연스럽게 설명해주세요
        
        300-500자 내외로 구체적으로 설명해주세요.
        """
        
        opinion_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 실무 경험이 풍부한 비즈니스 전문가입니다. 주어진 한 가지 주제에 대해서만 깊이 있는 통찰과 실용적인 조언을 제공합니다."},
                {"role": "user", "content": opinion_prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        return opinion_response.choices[0].message.content
    except Exception as e:
        # 오류 발생 시 기본 응답
        return f"오늘 독서 토론에서 다룬 '{best_sentence}'에 관한 주제는 비즈니스에 중요한 시사점을 제공합니다. 이를 실제 업무에 적용하려면 구체적인 실행 계획과 단계별 접근이 필요합니다."

def text_to_speech(text):
    """OpenAI TTS API를 사용한 텍스트를 음성으로 변환"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # 음성 생성 요청
        response = client.audio.speech.create(
            model="tts-1",  # 또는 "tts-1-hd"
            voice="alloy",  # 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer' 중 선택
            input=text
        )
        
        # 음성 데이터를 바이트로 가져오기
        audio_data = response.content
        
        # 오디오 데이터를 base64로 인코딩
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # HTML audio 태그로 표시
        audio_html = f"""
            <audio controls>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
        """
        
        return audio_html
    except Exception as e:
        st.error(f"음성 변환 중 오류 발생: {str(e)}")
        return None

def show_application_comparison(book_title, keyword, model_key, model_name):
    """적용 자료 비교 화면 표시"""
    st.write("### 적용 자료 비교")
    st.write("두 개의 적용 자료를 선택하여 비교할 수 있습니다.")
    
    # 적용 자료 목록 조회
    files = get_files(book_title, "application")
    
    if not files or len(files) < 2:
        st.warning("비교할 적용 자료가 충분하지 않습니다. 최소 2개 이상의 적용 자료가 필요합니다.")
        return
    
    # 파일 선택 컬럼
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("#### 기준 자료 (이전)")
        left_file = st.selectbox(
            "비교할 첫 번째 자료",
            files,
            format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})",
            key="left_file"
        )
        
        if left_file:
            st.write(f"**{left_file['file_name']}**")
            st.write(f"*등록일: {left_file['created_at'].strftime('%Y-%m-%d')}*")
            st.text_area("내용", left_file['content'], height=300, key="left_content", disabled=True)
    
    with col2:
        st.write("#### 비교 자료 (이후)")
        # 왼쪽에서 선택한 파일 제외
        right_files = [f for f in files if f['id'] != left_file['id']] if left_file else files
        
        right_file = st.selectbox(
            "비교할 두 번째 자료",
            right_files,
            format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})",
            key="right_file"
        )
        
        if right_file:
            st.write(f"**{right_file['file_name']}**")
            st.write(f"*등록일: {right_file['created_at'].strftime('%Y-%m-%d')}*")
            st.text_area("내용", right_file['content'], height=300, key="right_content", disabled=True)
    
    # 비교 분석 버튼
    if left_file and right_file:
        # 분석 결과 표시 컨테이너
        comparison_container = st.container()
        
        if st.button("🔍 AI 비교 분석"):
            with st.spinner("두 자료를 비교 분석 중입니다..."):
                comparison_result = compare_applications(
                    left_file['content'],
                    right_file['content'],
                    keyword,
                    model_key,
                    model_name
                )
                st.session_state.comparison_result = comparison_result
        
        # 비교 결과가 있으면 표시
        if 'comparison_result' in st.session_state:
            with comparison_container:
                st.write("### 📊 비교 분석 결과")
                st.markdown(st.session_state.comparison_result)
                
                # 음성 재생 버튼
                if st.button("🔊 음성으로 듣기", key="compare_audio"):
                    with st.spinner("음성을 생성하고 있습니다..."):
                        audio_html = text_to_speech(st.session_state.comparison_result)
                        if audio_html:
                            st.markdown(audio_html, unsafe_allow_html=True)

def compare_applications(content1, content2, keyword, model_key, model_name):
    """두 적용 자료 비교 분석"""
    prompt = f"""
    다음은 '{keyword}' 관점에서 작성된 두 개의 적용 자료입니다. 
    첫 번째 자료(이전)와 비교하여 두 번째 자료(이후)에서 어떤 내용이 보강되었는지 분석해 주세요.
    
    [첫 번째 자료 - 이전]
    {content1}
    
    [두 번째 자료 - 이후]
    {content2}
    
    다음 형식으로 분석 결과를 제공해 주세요:
    
    ## 비교 분석 요약
    - 두 자료의 전반적인 차이점을 2-3줄로 요약
    - 두 번째 자료에서 가장 중요하게 보강된 부분 2가지
    
    ## 세부 비교 분석
    1. 보강된 내용
       - 두 번째 자료에서 새롭게 추가되거나 크게 발전된 내용 3가지
       - 각 내용이 '{keyword}' 관점에서 어떤 가치를 더했는지 설명
    
    2. 개선된 논리성
       - 두 번째 자료에서 논리적 구조나 설득력이 향상된 부분
       - 구체적인 예시나 데이터 보강 사항
    
    3. 실행 가능성 향상
       - 두 번째 자료에서 실행 계획이나 구체성이 개선된 부분
       - '{keyword}' 측면에서 실행 가능성이 높아진 요소
    
    ## 종합 평가
    - 두 번째 자료가 첫 번째 자료에 비해 '{keyword}' 관점에서 얼마나 발전했는지 평가
    - 여전히 보완이 필요한 부분 1-2가지 제안
    
    * 모든 분석은 '{keyword}' 관점에 집중하여 작성해 주세요.
    * 구체적인 예시와 근거를 들어 설명해 주세요.
    * 존댓말을 사용해 주세요.
    """
    
    try:
        if "Local" in model_key:
            return analyze_with_local_llm(prompt, model_name)
        else:
            return analyze_with_openai(prompt, model_name)
    except Exception as e:
        st.error(f"비교 분석 중 오류 발생: {str(e)}")
        return "비교 분석 중 오류가 발생했습니다. 다시 시도해 주세요."

if __name__ == "__main__":
    main() 
    