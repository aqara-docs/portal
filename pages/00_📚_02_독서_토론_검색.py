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

def summarize_for_tts(text, max_length=3500):
    """TTS를 위해 텍스트를 요약"""
    if len(text) <= max_length:
        return text
    
    # 텍스트가 너무 길 경우 주요 섹션만 포함
    lines = text.split('\n')
    summary = []
    current_length = 0
    
    for line in lines:
        # 제목이나 중요 섹션 시작 부분 포함
        if line.startswith('#') or line.startswith('##'):
            if current_length + len(line) + 2 <= max_length:
                summary.append(line)
                current_length += len(line) + 2
        # 핵심 내용 포함
        elif '[핵심 요약]' in line or '[주요 분석]' in line or '[실행 제안]' in line:
            if current_length + len(line) + 2 <= max_length:
                summary.append(line)
                current_length += len(line) + 2
    
    return '\n'.join(summary)

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
            "적용 고급": "application_advanced",
            "적용 비교": "application_compare"
        }
        material_type = st.selectbox(
            "자료 유형",
            list(type_mapping.keys())
        )
    
    # 요약 모드에서 이전 토론 내용 입력 필드 추가
    previous_topic = None
    next_topic = None
    if material_type == "요약":
        previous_topic = st.text_input(
            "이전 토론 주제",
            placeholder="이전 독서 토론의 주제를 입력해주세요",
            key="previous_topic"
        )
    elif material_type == "적용":
        next_topic = st.text_input(
            "다음 토론 주제",
            placeholder="다음 독서 토론의 주제를 입력해주세요",
            key="next_topic"
        )
    
    # 적용 자료인 경우 분석 키워드 선택
    analysis_keyword = None
    if material_type in ["적용", "적용 고급", "적용 비교"]:
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords)
        
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력")
        else:
            analysis_keyword = selected_keyword
    
    # 적용 비교 모드
    if material_type == "적용 비교":
        show_application_comparison(selected_title, analysis_keyword, model_key, model_name)
    # 적용 고급 모드
    elif material_type == "적용 고급":
        show_advanced_application(selected_title, analysis_keyword, model_key, model_name)
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
                                        # 클로징 멘트 생성
                                        closing_ment = f"다음 시간에는 {next_topic if next_topic else '다음 주제'}에 대한 독서 토론을 진행할 예정입니다. 즐거운 하루 되세요. 감사합니다."
                                        
                                        # AI 분석 결과와 클로징 멘트만 포함
                                        combined_text = f"""
                                        AI 분석 결과입니다.
                                        {st.session_state.ai_analysis}
                                        
                                        {closing_ment}
                                        """
                                        audio_html = text_to_speech(combined_text)
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
                                        # 오프닝 멘트 생성
                                        opening_ment = f"안녕하세요. 좋은 아침입니다. 지난번 시간에는 {previous_topic if previous_topic else '이전 주제'}의 내용으로 독서토론을 진행했습니다. 그럼 오늘 독서 토론 내용을 요약해 드리겠습니다."
                                        
                                        # 전체 텍스트 구성 및 요약
                                        full_text = f"""
                                        {opening_ment}
                                        
                                        요약 내용입니다.
                                        {selected_file['content']}
                                        
                                        AI 의견입니다.
                                        {st.session_state.ai_opinion}
                                        """
                                        summarized_text = summarize_for_tts(full_text)
                                        audio_html = text_to_speech(summarized_text)
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
    """내용 분석"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    다음 내용을 '{keyword}' 관점에서 분석해주세요.
    
    분석 결과는 다음 형식으로 작성해주세요 (전체 글자 수 1750자 이내로 작성).
    반드시 존대말을 사용해 주세요.
    
    [핵심 요약] (150자 이내)
    - 핵심 내용을 1-2줄로 요약해 주세요
    
    [주요 분석] (900자 이내)
    1. '{keyword}' 관련 강점
    - 주요 강점 2개를 설명해 주세요
    
    2. '{keyword}' 측면의 개선점
    - 주요 개선점 2개를 제시해 주세요
    
    [실행 제안] (700자 이내)
    1. '{keyword}' 중심의 단기 과제 (1-3개월)
    - 구체적 실행 방안 2개를 제시해 주세요
    - 각 방안별 기대효과를 설명해 주세요
    
    2. '{keyword}' 중심의 중기 과제 (3-6개월)
    - 구체적 실행 방안 2개를 제시해 주세요
    - 각 방안별 기대효과를 설명해 주세요
    
    * 모든 내용은 반드시 존대말로 작성해 주세요.
    * 예시: "~해야 합니다", "~할 수 있습니다", "~하시기 바랍니다" 등의 형식으로 작성해 주세요.
    
    분석 내용:
    {content}
    """
    
    try:
        if model_key.startswith("Local"):
            # 로컬 LLM API 호출
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "max_tokens": 700  # 토큰 수 제한 (약 1750자)
                }
            )
            return response.json()['response']
        else:
            # OpenAI API 호출
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "당신은 비즈니스 분석 전문가입니다. 항상 존대말을 사용하여 분석 결과를 작성하되, 핵심적인 내용만 간단명료하게 작성합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700,  # 토큰 수 제한 (약 1750자)
                temperature=0.2
            )
            return response.choices[0].message.content
    except Exception as e:
        st.error(f"분석 중 오류 발생: {str(e)}")
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
    다음 문장에서 가장 중요한 비즈니스 관련 핵심 주제 하나만 3단어 이내로 추출해주세요:
    "{best_sentence}"
    
    예시 형식: "고객 가치", "효율적 리더십", "시장 전략" 등
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
            max_tokens=10
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
        간단명료하게 설명해주세요.
        
        150-250자 내외로 핵심적인 내용만 설명해주세요.
        """
        
        opinion_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 실무 경험이 풍부한 비즈니스 전문가입니다. 주어진 주제에 대해 간단명료하게 핵심적인 통찰과 실용적인 조언을 제공합니다."},
                {"role": "user", "content": opinion_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return opinion_response.choices[0].message.content
    except Exception as e:
        # 오류 발생 시 기본 응답
        return f"오늘 독서 토론에서 다룬 '{best_sentence}'에 관한 주제는 비즈니스에 중요한 시사점을 제공합니다."

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
            return analyze_content(prompt, keyword, model_key, model_name)
        else:
            return analyze_content(prompt, keyword, model_key, model_name)
    except Exception as e:
        st.error(f"비교 분석 중 오류 발생: {str(e)}")
        return "비교 분석 중 오류가 발생했습니다. 다시 시도해 주세요."

def show_advanced_application(book_title, keyword, model_key, model_name):
    """적용 고급 모드 - AI 분석 결과를 반영한 개선된 보고서 생성"""
    # 기존 get_files 함수 사용 - 키워드와 상관없이 모든 적용 파일 표시
    files = get_files(book_title, "application")
    
    if not files:
        st.info(f"{book_title}의 적용 자료가 없습니다.")
        return
    
    # 파일 선택
    selected_file = st.selectbox(
        "분석할 파일 선택",
        files,
        format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})"
    )
    
    if selected_file:
        # 파일 내용 표시
        st.write(f"### 📄 {selected_file['file_name']}")
        st.markdown(selected_file['content'])
        st.write("---")
        st.write(f"*등록일: {selected_file['created_at'].strftime('%Y-%m-%d')}*")
        
        # AI 분석 컨테이너
        analysis_container = st.container()
        
        # AI 분석 버튼
        if st.button("🤖 AI 분석"):
            with st.spinner("AI가 분석 중입니다..."):
                analysis_result = analyze_content(selected_file['content'], keyword, model_key, model_name)
                st.session_state.analysis_result = analysis_result
        
        # AI 분석 결과가 있으면 표시
        if 'analysis_result' in st.session_state:
            with analysis_container:
                st.write("### 🔍 AI 분석 결과")
                st.markdown(st.session_state.analysis_result)
                
                # 개선된 보고서 생성 버튼
                if st.button("✨ 개선된 보고서 생성"):
                    with st.spinner("AI가 개선된 보고서를 생성 중입니다..."):
                        improved_report = generate_improved_report(
                            selected_file['content'], 
                            st.session_state.analysis_result,
                            keyword
                        )
                        st.session_state.improved_report = improved_report
                
                # 개선된 보고서가 있으면 표시
                if 'improved_report' in st.session_state:
                    st.write("### 📝 개선된 보고서")
                    
                    # 긴 보고서를 섹션별로 분할하여 표시
                    improved_report = st.session_state.improved_report
                    sections = improved_report.split("\n## ")
                    
                    if len(sections) > 1:
                        # 첫 번째 섹션 (제목 포함)
                        st.markdown(sections[0])
                        
                        # 나머지 섹션들을 탭으로 표시
                        tabs = st.tabs([s.split("\n")[0] for s in sections[1:]])
                        for i, tab in enumerate(tabs):
                            with tab:
                                st.markdown("## " + sections[i+1])
                    else:
                        # 섹션이 없으면 전체 표시
                        st.markdown(improved_report)
                    
                    # 다운로드 버튼
                    download_filename = f"{selected_file['file_name'].split('.')[0]}_improved.md"
                    st.download_button(
                        label="📥 개선된 보고서 다운로드",
                        data=st.session_state.improved_report,
                        file_name=download_filename,
                        mime="text/markdown"
                    )
                    
                    # 저장 버튼
                    if st.button("💾 개선된 보고서 저장"):
                        with st.spinner("보고서를 저장 중입니다..."):
                            save_result = save_improved_report(
                                book_title,
                                keyword,
                                download_filename,
                                st.session_state.improved_report
                            )
                            if save_result:
                                st.success("개선된 보고서가 저장되었습니다!")
                            else:
                                st.error("보고서 저장 중 오류가 발생했습니다.")

def generate_improved_report(original_content, analysis_result, keyword):
    """AI 분석 결과를 반영하여 개선된 보고서 생성"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    try:
        # 긴 내용을 처리하기 위한 청크 기반 접근법
        if len(original_content) > 6000:
            st.info("보고서가 길어 섹션별로 처리합니다. 잠시만 기다려주세요...")
            
            # 1. 원본 보고서를 섹션으로 분할
            sections = split_into_sections(original_content)
            
            # 2. 분석 결과에서 개선사항 추출
            improvements = extract_improvements(analysis_result)
            
            # 3. 각 섹션별로 관련 개선사항 적용
            improved_sections = []
            progress_bar = st.progress(0)
            
            for i, section in enumerate(sections):
                # 이 섹션과 관련된 개선사항 찾기
                relevant_improvements = find_relevant_improvements(section, improvements)
                
                # 섹션 개선
                if relevant_improvements:
                    improved_section = improve_section(section, relevant_improvements, keyword)
                else:
                    improved_section = section
                
                improved_sections.append(improved_section)
                progress_bar.progress((i + 1) / len(sections))
            
            # 4. 개선된 섹션 결합
            return "\n\n".join(improved_sections)
        
        else:
            # 기존 방식: 한 번에 처리
            prompt = f"""
            다음은 '{keyword}' 관점에서 작성된 원본 사업 전략 보고서입니다:
            
            [원본 보고서]
            {original_content}
            
            다음은 이 보고서에 대한 AI 분석 결과입니다:
            
            [AI 분석 결과]
            {analysis_result}
            
            위 AI 분석 결과에서 제시된 개선사항과 실행 제안을 반영하여 원본 보고서를 개선해주세요.
            
            절대적 요구사항:
            1. 원본 보고서의 모든 내용을 100% 유지해야 합니다. 어떤 내용도 삭제하거나 축약하지 마세요.
            2. 원본 보고서의 모든 섹션, 소제목, 구조를 그대로 유지하세요.
            3. AI 분석에서 지적된 개선점과 실행 제안을 원본 보고서의 적절한 위치에 추가하세요.
            4. 추가된 내용은 원본 내용과 자연스럽게 통합되어야 합니다.
            5. 원본의 톤과 스타일을 유지하세요.
            6. 마크다운 형식을 유지하세요.
            
            최종 결과물은 원본 보고서의 모든 내용을 그대로 포함하면서, AI 분석의 개선사항과 제안사항이 자연스럽게 통합된 보고서여야 합니다.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 비즈니스 전략 보고서 개선 전문가입니다. 원본 보고서의 모든 내용과 구조를 100% 유지하면서 분석 결과를 반영하여 보고서를 자연스럽게 개선합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
    except Exception as e:
        st.error(f"개선된 보고서 생성 중 오류 발생: {str(e)}")
        return "개선된 보고서를 생성하는 중 오류가 발생했습니다."

def split_into_sections(content):
    """보고서를 섹션으로 분할"""
    # 제목 패턴으로 분할 (# 또는 ## 등으로 시작하는 라인)
    import re
    sections = re.split(r'\n(#+\s+)', content)
    
    # 분할된 결과 재구성
    if sections[0].strip() == '':
        sections = sections[1:]
    
    processed_sections = []
    for i in range(0, len(sections), 2):
        if i+1 < len(sections):
            processed_sections.append(sections[i] + sections[i+1])
        else:
            processed_sections.append(sections[i])
    
    return processed_sections if processed_sections else [content]

def extract_improvements(analysis_result):
    """분석 결과에서 개선사항 추출"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    다음 AI 분석 결과에서 주요 개선사항과 실행 제안을 추출해주세요:
    
    {analysis_result}
    
    각 개선사항을 다음 형식으로 정리해주세요:
    1. 개선 영역: (예: 마케팅 전략, 고객 관계 등)
    2. 개선 내용: (구체적인 개선 제안)
    3. 관련 키워드: (이 개선사항과 관련된 키워드 목록)
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 가벼운 모델 사용
        messages=[
            {"role": "system", "content": "당신은 비즈니스 분석 전문가입니다. 분석 결과에서 핵심 개선사항을 추출합니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return response.choices[0].message.content

def find_relevant_improvements(section, improvements):
    """섹션과 관련된 개선사항 찾기"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    다음 보고서 섹션과 관련된 개선사항을 찾아주세요:
    
    [보고서 섹션]
    {section}
    
    [개선사항 목록]
    {improvements}
    
    이 섹션과 관련된 개선사항만 선택하여 반환해주세요.
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 가벼운 모델 사용
        messages=[
            {"role": "system", "content": "당신은 비즈니스 분석 전문가입니다. 보고서 섹션과 관련된 개선사항을 찾습니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return response.choices[0].message.content

def improve_section(section, relevant_improvements, keyword):
    """섹션 개선"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    다음 보고서 섹션을 개선해주세요:
    
    [원본 섹션]
    {section}
    
    [관련 개선사항]
    {relevant_improvements}
    
    '{keyword}' 관점에서 위 개선사항을 반영하여 섹션을 개선해주세요.
    
    절대적 요구사항:
    1. 원본 섹션의 모든 내용을 100% 유지해야 합니다. 어떤 내용도 삭제하거나 축약하지 마세요.
    2. 원본 섹션의 구조를 그대로 유지하세요.
    3. 개선사항을 원본 내용과 자연스럽게 통합하세요.
    4. 원본의 톤과 스타일을 유지하세요.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 비즈니스 전략 보고서 개선 전문가입니다. 원본 내용을 100% 유지하면서 개선사항을 통합합니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return response.choices[0].message.content

def save_improved_report(book_title, keyword, file_name, content):
    """개선된 보고서를 저장"""
    try:
        # 저장 경로 설정
        save_dir = f"data/{book_title}/application"
        os.makedirs(save_dir, exist_ok=True)
        
        # 파일명에 키워드와 날짜 추가
        today = datetime.now().strftime("%Y%m%d")
        save_path = f"{save_dir}/{keyword}_{today}_improved.md"
        
        # 파일 저장
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return True
    except Exception as e:
        st.error(f"파일 저장 중 오류 발생: {str(e)}")
        return False

def get_application_files(book_title, keyword):
    """특정 책과 키워드에 해당하는 적용 파일 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        # 기존 get_files 함수와 동일한 테이블 이름 사용
        # 테이블 이름을 book_materials로 변경 (예시)
        if keyword:
            query = """
                SELECT id, file_name, content, created_at
                FROM book_materials
                WHERE book_title = %s AND file_type = 'application' AND content LIKE %s
                ORDER BY created_at DESC
            """
            cursor.execute(query, (book_title, f"%{keyword}%"))
        else:
            query = """
                SELECT id, file_name, content, created_at
                FROM book_materials
                WHERE book_title = %s AND file_type = 'application'
                ORDER BY created_at DESC
            """
            cursor.execute(query, (book_title,))
        
        files = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return files
    except Exception as e:
        st.error(f"파일 목록 조회 중 오류 발생: {str(e)}")
        return []

if __name__ == "__main__":
    main() 
    