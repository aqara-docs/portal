import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI
import glob
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from langchain.tools import Tool, BaseTool
from typing import List
import asyncio
import markdown

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

def get_llm_models():
    """사용 가능한 LLM 모델 목록 반환"""
    models = {
        "OpenAI": {
            "GPT-4": "gpt-4",
            "GPT-3.5": "gpt-3.5-turbo"
        },
        "Ollama (로컬)": {
            "Llama2": "llama2:latest",  # 가장 최근에 업데이트된 모델
            "EEVE-Korean": "EEVE-Korean-10.8B:latest",  # 한국어 특화 모델
            "Gemma2": "gemma2:latest",  # Google의 새로운 모델
            "Mistral": "mistral:latest",
            "Llama3.1-8B": "llama3.1:8b",
            "Llama3.2": "llama3.2:latest"
        }
    }
    return models

def create_llm(provider, model_name):
    """선택된 제공자와 모델에 따라 LLM 인스턴스 생성"""
    if provider == "OpenAI":
        OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        if not OPENAI_API_KEY:
            st.error("OpenAI API 키가 설정되지 않았습니다.")
            st.stop()
        return ChatOpenAI(model=model_name, temperature=0.7)
    else:  # Ollama
        from langchain.chat_models import ChatOllama
        from langchain.schema import HumanMessage, SystemMessage
        
        class CrewAICompatibleOllama:
            def __init__(self, model_name, temperature=0.7):
                self.chat_model = ChatOllama(
                    model=model_name,
                    temperature=temperature,
                    num_ctx=4096,  # 컨텍스트 크기 지정
                    repeat_penalty=1.1,  # 반복 패널티 추가
                    num_predict=2048,  # 예측 토큰 수 제한
                    stop=["Human:", "Assistant:"]  # 응답 종료 토큰 지정
                )
                self.model_name = model_name
            
            def __str__(self):
                return f"Ollama ({self.model_name})"
            
            def complete(self, prompt):
                """CrewAI compatibility method"""
                try:
                    # 프롬프트 전처리
                    if isinstance(prompt, dict):
                        prompt = prompt.get('prompt', '')
                    elif not isinstance(prompt, str):
                        prompt = str(prompt)
                    
                    # 직접 프롬프트 전송
                    response = self.chat_model.predict(prompt)
                    
                    # 응답이 없는 경우 처리
                    if not response:
                        return "응답을 생성할 수 없습니다. 다시 시도해주세요."
                    
                    return response
                    
                except Exception as e:
                    st.error(f"Ollama 응답 처리 중 오류: {str(e)}")
                    return "오류가 발생했습니다. 다시 시도해주세요."
            
            def generate_text(self, prompt):
                """Additional compatibility method"""
                return self.complete(prompt)
            
            def get_model_name(self):
                return self.model_name
        
        return CrewAICompatibleOllama(
            model_name=model_name,
            temperature=0.7
        )

def main():
    st.title("📚 독서 전략 생성기 (CrewAI)")
    
    if 'saved_to_db' not in st.session_state:
        st.session_state.saved_to_db = False
    
    # 메인 인터페이스
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("요약 파일 업로드")
        
        # 책 제목 입력 (기본값: 퍼스널 MBA)
        book_title = st.text_input("책 제목", value="퍼스널 MBA", key="book_title")
        
        # 요약 파일 업로드
        summary_file = st.file_uploader(
            "독서토론 요약 파일 (md)",
            type=['md', 'txt'],
            key='summary'
        )
        
        if summary_file:
            try:
                summary_content = summary_file.read().decode('utf-8')
                st.write("### 요약 내용 미리보기")
                st.text_area("요약 내용", summary_content[:500] + "..." if len(summary_content) > 500 else summary_content, height=300, disabled=True)
                
                # 세션 상태에 저장
                st.session_state.summary_content = summary_content
                st.session_state.summary_filename = summary_file.name
                
                # 요약 파일을 DB에 저장 (파일이 변경될 때마다)
                if 'last_summary_file' not in st.session_state or st.session_state.last_summary_file != summary_file.name:
                    summary_saved = save_material(
                        book_title,
                        summary_file.name,
                        summary_content,
                        "summary"
                    )
                    
                    if summary_saved:
                        st.success(f"요약 파일이 저장되었습니다: {summary_file.name}")
                        st.session_state.last_summary_file = summary_file.name
                    else:
                        st.error("요약 파일 저장에 실패했습니다.")
                
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {str(e)}")
    
    with col2:
        st.header("적용 파일 선택")
        
        # 분석 키워드 선택
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords, key="keyword")
        
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력", key="custom_keyword")
        else:
            analysis_keyword = selected_keyword
        
        # 세션 상태에 키워드 저장
        st.session_state.analysis_keyword = analysis_keyword
        
        # 적용 파일 목록 조회
        application_files = get_application_files(book_title)
        
        if application_files:
            selected_application = st.selectbox(
                "기존 적용 파일",
                application_files,
                format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})",
                key="application"
            )
            
            if selected_application:
                st.write("### 적용 내용 미리보기")
                st.text_area("적용 내용", selected_application['content'][:500] + "..." if len(selected_application['content']) > 500 else selected_application['content'], height=300, disabled=True)
                
                # 세션 상태에 저장
                st.session_state.selected_application = selected_application
        else:
            st.warning(f"{book_title}에 대한 적용 파일이 없습니다.")
            selected_application = None
    
    # LLM 설정 섹션
    st.subheader("🤖 LLM 모델 설정")
    
    # LLM 제공자 및 모델 선택
    llm_models = get_llm_models()
    llm_provider = st.selectbox(
        "LLM 제공자 선택",
        options=list(llm_models.keys()),
        help="OpenAI는 더 높은 품질의 결과를 제공하지만 비용이 발생합니다. Ollama는 무료이며 로컬에서 실행됩니다."
    )
    
    selected_model = st.selectbox(
        "모델 선택",
        options=list(llm_models[llm_provider].keys()),
        help="선택한 제공자의 사용 가능한 모델 목록"
    )
    
    model_name = llm_models[llm_provider][selected_model]
    
    # 에이전트 선택 섹션
    st.subheader("🤖 추가 전문 에이전트 선택")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        market_selected = st.checkbox("시장 분석", value=True)
        customer_selected = st.checkbox("고객 인사이트", value=True)
        financial_selected = st.checkbox("재무 전략", value=True)
        risk_selected = st.checkbox("리스크 관리", value=True)
        operations_selected = st.checkbox("운영 전략", value=True)
    
    with col2:
        marketing_selected = st.checkbox("마케팅 전략", value=True)
        strategic_selected = st.checkbox("전략 기획", value=True)
        innovation_selected = st.checkbox("혁신 전략", value=True)
        hr_selected = st.checkbox("인적자원", value=True)
    
    with col3:
        tech_selected = st.checkbox("기술 전략", value=True)
        legal_selected = st.checkbox("법무", value=True)
        sustainability_selected = st.checkbox("지속가능성", value=True)
        quality_selected = st.checkbox("품질 관리", value=True)
        data_selected = st.checkbox("데이터 분석", value=True)
    
    # 전략 프레임워크 선택 섹션
    st.subheader("📊 전략 프레임워크 선택")
    st.markdown("분석에 활용할 전략 프레임워크를 선택하세요.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        blue_ocean = st.checkbox("블루오션 전략 (Blue Ocean Strategy)", 
            help="ERRC 그리드와 전략 캔버스를 통한 가치 혁신 분석")
        ansoff = st.checkbox("안소프 매트릭스 (Ansoff Matrix)", 
            help="시장과 제품 관점의 4가지 성장 전략 도출")
        pestel = st.checkbox("PESTEL 분석", 
            help="정치, 경제, 사회, 기술, 환경, 법률 관점의 거시환경 분석")
        porter = st.checkbox("포터의 5가지 힘 (Porter's Five Forces)", 
            help="산업 구조와 경쟁 강도 분석")
        swot = st.checkbox("SWOT 분석", 
            help="강점, 약점, 기회, 위협 요인 분석")
    
    with col2:
        bmc = st.checkbox("비즈니스 모델 캔버스", 
            help="9개 블록으로 구성된 비즈니스 모델 분석")
        vrio = st.checkbox("VRIO 프레임워크", 
            help="자원 기반 관점의 경쟁 우위 분석")
        lean = st.checkbox("린 스타트업 & 고객 개발 모델", 
            help="MVP와 고객 피드백 기반의 반복 개선 전략")
        bsc = st.checkbox("밸런스드 스코어카드", 
            help="재무, 고객, 프로세스, 학습/성장 관점의 성과 지표")
        disruptive = st.checkbox("디스럽티브 이노베이션", 
            help="파괴적 혁신을 통한 시장 재편 전략")
    
    # 사용자 정의 프레임워크 입력
    st.markdown("### 추가 전략 프레임워크")
    custom_framework = st.text_input(
        "사용자 정의 전략 프레임워크를 입력하세요",
        help="분석에 추가로 활용하고 싶은 전략 프레임워크를 입력하세요"
    )

    # 선택된 프레임워크 목록 생성
    selected_frameworks = []
    if blue_ocean: selected_frameworks.append("블루오션 전략")
    if ansoff: selected_frameworks.append("안소프 매트릭스")
    if pestel: selected_frameworks.append("PESTEL 분석")
    if porter: selected_frameworks.append("포터의 5가지 힘")
    if swot: selected_frameworks.append("SWOT 분석")
    if bmc: selected_frameworks.append("비즈니스 모델 캔버스")
    if vrio: selected_frameworks.append("VRIO 프레임워크")
    if lean: selected_frameworks.append("린 스타트업 & 고객 개발 모델")
    if bsc: selected_frameworks.append("밸런스드 스코어카드")
    if disruptive: selected_frameworks.append("디스럽티브 이노베이션")
    if custom_framework: selected_frameworks.append(custom_framework)

    # 선택된 프레임워크 저장
    st.session_state['selected_frameworks'] = selected_frameworks
    
    # AI 전략 생성 버튼
    generate_button = st.button("🤖 AI 전략 생성", type="primary", key="generate_button")
    
    # 에이전트 대화 로그를 표시할 컨테이너 생성
    agent_conversation = st.empty()
    
    if generate_button and summary_file and 'selected_application' in st.session_state:
        # 에이전트 대화 로그 컨테이너 초기화
        with agent_conversation.container():
            st.write("### 🤖 에이전트 작업 로그")
            conversation_log = st.empty()
            
            # 대화 로그를 저장할 변수
            st.session_state.conversation_history = []
            
            # 대화 로그 업데이트 함수
            def update_log(message, agent_name=None):
                if agent_name:
                    formatted_message = f"**{agent_name}**: {message}"
                else:
                    formatted_message = message
                
                st.session_state.conversation_history.append(formatted_message)
                conversation_log.markdown("\n\n".join(st.session_state.conversation_history))
            
            update_log("AI 에이전트들이 새로운 전략을 생성하고 있습니다...")
        
        with st.spinner("AI 에이전트들이 새로운 전략을 생성하고 있습니다..."):
            try:
                # LLM 인스턴스 생성
                llm = create_llm(llm_provider, model_name)
                
                # 선택된 에이전트 목록 생성
                active_agents = []
                if market_selected: active_agents.append('market_agent')
                if customer_selected: active_agents.append('customer_agent')
                if financial_selected: active_agents.append('financial_agent')
                if risk_selected: active_agents.append('risk_agent')
                if operations_selected: active_agents.append('operations_agent')
                if marketing_selected: active_agents.append('marketing_agent')
                if strategic_selected: active_agents.append('strategic_agent')
                if innovation_selected: active_agents.append('innovation_agent')
                if hr_selected: active_agents.append('hr_agent')
                if tech_selected: active_agents.append('tech_agent')
                if legal_selected: active_agents.append('legal_agent')
                if sustainability_selected: active_agents.append('sustainability_agent')
                if quality_selected: active_agents.append('quality_agent')
                if data_selected: active_agents.append('data_agent')
                
                # 새 전략 생성
                result = generate_strategy_with_crewai(
                    st.session_state.summary_content,
                    st.session_state.selected_application['content'],
                    st.session_state.analysis_keyword,
                    llm,  # LLM 인스턴스 전달
                    active_agents=active_agents,
                    update_log=update_log
                )
                
                if result:
                    st.session_state.new_strategy = result
                    st.success("전략 생성이 완료되었습니다!")
                    st.markdown("## 생성된 전략")
                    st.markdown(result)
                
                # 파일명 생성 (날짜 포함)
                today = datetime.now().strftime('%Y%m%d')
                new_file_name = f"{st.session_state.book_title}_적용_{st.session_state.analysis_keyword}_{today}.md"
                st.session_state.new_file_name = new_file_name
                
            except Exception as e:
                st.error(f"전략 생성 중 오류 발생: {str(e)}")
    
    # 저장 버튼 섹션 수정
    if 'new_strategy' in st.session_state and not st.session_state.saved_to_db:
        st.write("---")
        st.subheader("전략 저장")
        save_button = st.button("💾 DB에 저장", key="save_button")
        
        if save_button:
            try:
                saved_files = []
                
                # 1. 요약 파일 저장
                if 'summary_content' in st.session_state and 'summary_filename' in st.session_state:
                    summary_saved = save_material(
                        st.session_state.book_title,
                        st.session_state.summary_filename,
                        st.session_state.summary_content,
                        "summary"
                    )
                    if summary_saved:
                        saved_files.append("요약 파일")
                
                # 2. 새로운 전략 저장
                strategy_content = st.session_state.new_strategy
                if not isinstance(strategy_content, str):
                    strategy_content = str(strategy_content)
                
                # 파일명 생성 (날짜 포함)
                today = datetime.now().strftime('%Y%m%d')
                new_file_name = f"{st.session_state.book_title}_적용_{st.session_state.analysis_keyword}_{today}.md"
                
                strategy_saved = save_material(
                    st.session_state.book_title,
                    new_file_name,
                    strategy_content,
                    "application"
                )
                
                if strategy_saved:
                    saved_files.append("새로운 전략")
                    st.session_state.new_file_name = new_file_name
                
                # 저장 결과 표시
                if saved_files:
                    st.session_state.saved_to_db = True
                    st.success(f"{', '.join(saved_files)}이(가) 성공적으로 저장되었습니다.")
                    
                    # 다운로드 버튼 제공
                    st.download_button(
                        label="📥 전략 파일 다운로드",
                        data=strategy_content,
                        file_name=new_file_name,
                        mime="text/markdown"
                    )
                else:
                    st.error("파일 저장에 실패했습니다.")
                    
            except Exception as e:
                st.error(f"저장 중 오류 발생: {str(e)}")
    
    # 이미 저장된 경우 다운로드 버튼만 표시
    elif 'new_strategy' in st.session_state and st.session_state.saved_to_db:
        st.write("---")
        st.success(f"전략이 성공적으로 저장되었습니다!")
        
        # 다운로드 버튼 제공
        st.download_button(
            label="📥 전략 파일 다운로드",
            data=st.session_state.new_strategy,
            file_name=st.session_state.new_file_name,
            mime="text/markdown"
        )
        
        # 새로운 전략 생성 버튼
        if st.button("🔄 새로운 전략 생성하기"):
            # 세션 상태 초기화
            for key in ['new_strategy', 'saved_to_db', 'new_file_name']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def get_application_files(book_title):
    """적용 파일 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT *
            FROM reading_materials
            WHERE book_title = %s
            AND type = 'application'
            ORDER BY created_at DESC
        """, (book_title,))
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_material(book_title, file_name, content, type):
    """자료를 DB에 저장"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 기존 파일 확인
        cursor.execute(
            "SELECT id FROM reading_materials WHERE book_title = %s AND file_name = %s AND type = %s",
            (book_title, file_name, type)
        )
        existing = cursor.fetchone()
        cursor.fetchall()  # 남은 결과 정리
        
        if existing:
            # 기존 파일 업데이트
            cursor.execute(
                "UPDATE reading_materials SET content = %s, updated_at = NOW() WHERE id = %s",
                (content, existing[0])
            )
        else:
            # 새 파일 저장
            cursor.execute(
                "INSERT INTO reading_materials (book_title, file_name, content, type) VALUES (%s, %s, %s, %s)",
                (book_title, file_name, content, type)
            )
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"DB 저장 중 오류: {str(e)}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_strategic_agents(llm, selected_frameworks, active_agents):
    """전략 수립을 위한 에이전트 생성"""
    agents = []
    
    # 1. 전략기획 전문가 (항상 첫 번째로 생성)
    strategy_expert = Agent(
        role="전략기획 전문가",
        goal="독서 토론 내용을 바탕으로 실행 가능한 전략 수립",
        backstory="20년 경력의 전략 컨설턴트로서 다양한 산업의 전략 수립 경험 보유",
        llm=llm,
        verbose=True
    )
    agents.append(strategy_expert)
    
    # 2. 프레임워크 전문가 생성 (필수)
    for framework in selected_frameworks:
        framework_expert = Agent(
            role=f"{framework} 전문가",
            goal=f"{framework}를 활용한 심층 전략 분석 및 전략 도출",
            backstory=f"{framework} 분야의 전문가로서 다수의 성공적인 전략 수립 경험 보유",
            llm=llm,
            verbose=True
        )
        agents.append(framework_expert)
    
    # 3. 필수 전문가 생성
    essential_agents = {
        'marketing_agent': ("마케팅 전략가", "효과적인 마케팅 전략 수립", "디지털 마케팅 전문가"),
        'sales_agent': ("영업 전략가", "실행 가능한 영업 전략 수립", "B2B/B2C 영업 전문가")
    }
    
    for agent_key, (role, goal, backstory) in essential_agents.items():
        agent = Agent(
            role=role,
            goal=goal,
            backstory=f"{backstory}로서 다양한 전략 수립 및 실행 경험 보유",
            llm=llm,
            verbose=True
        )
        agents.append(agent)
    
    # 4. 추가 전문가 생성 (선택적)
    additional_agents = {
        'market_agent': ("시장 분석 전문가", "시장 동향과 경쟁 환경 분석", "시장 조사 및 분석 전문가"),
        'customer_agent': ("고객 인사이트 전문가", "고객 니즈 및 행동 패턴 분석", "소비자 행동 연구 전문가"),
        'financial_agent': ("재무 전략가", "재무 계획 및 투자 전략 수립", "재무 및 투자 전문가"),
        'risk_agent': ("리스크 관리 전문가", "리스크 식별 및 대응 전략 수립", "기업 리스크 관리 전문가"),
        'operations_agent': ("운영 전략가", "효율적인 운영 체계 설계", "운영 최적화 전문가"),
        'innovation_agent': ("혁신 전략가", "혁신적 비즈니스 모델 개발", "기업 혁신 전문가"),
        'hr_agent': ("인적자원 전략가", "조직 및 인재 전략 수립", "HR 전략 전문가"),
        'tech_agent': ("기술 전략가", "기술 로드맵 수립", "기술 전략 전문가"),
        'legal_agent': ("법무 전략가", "법적 리스크 관리", "기업 법무 전문가"),
        'sustainability_agent': ("지속가능성 전략가", "ESG 전략 수립", "지속가능경영 전문가"),
        'quality_agent': ("품질 전략가", "품질 관리 체계 수립", "품질 경영 전문가"),
        'data_agent': ("데이터 전략가", "데이터 기반 의사결정 체계 수립", "데이터 분석 전문가")
    }
    
    for agent_key in active_agents:
        if agent_key in additional_agents and agent_key not in essential_agents:
            role, goal, backstory = additional_agents[agent_key]
            agent = Agent(
                role=role,
                goal=goal,
                backstory=f"{backstory}로서 다양한 프로젝트 경험 보유",
                llm=llm,
                verbose=True
            )
            agents.append(agent)
    
    return agents

def create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks):
    """전략 수립을 위한 태스크 생성"""
    tasks = []
    
    # 1. 초기 분석 태스크 (전략기획 전문가)
    content_analysis_task = Task(
        description=f"""
        독서 토론 요약과 기존 적용 내용을 '{keyword}' 관점에서 철저히 분석하세요.
        
        분석 요구사항:
        1. 핵심 개념과 원칙 추출 (최소 5개)
        2. 현재 전략의 강점과 약점
        3. 개선 및 혁신 기회
        4. 실행 가능한 제안사항
        
        * 모든 분석은 구체적 근거와 페이지 참조 포함
        * 실행 가능한 제안 중심으로 작성
        """,
        agent=agents[0],
        expected_output="초기 분석 결과 (markdown 형식)"
    )
    tasks.append(content_analysis_task)
    
    # 2. 프레임워크별 분석 태스크
    for framework in selected_frameworks:
        framework_expert = next((agent for agent in agents if framework in agent.role), None)
        if framework_expert:
            framework_task = Task(
                description=f"""
                '{framework}'를 활용하여 '{keyword}' 관점의 전략을 개발하세요.
                
                요구사항:
                1. 프레임워크의 각 요소별 상세 분석
                2. 독서 토론 내용과의 연계성 제시
                3. 구체적인 전략 방안 도출
                4. 실행 계획 수립
                
                결과물 포함사항:
                1. 프레임워크 기반 분석 결과
                2. 도출된 전략 방향
                3. 실행 방안
                4. 기대효과
                
                * 모든 내용은 한글로 작성
                * 구체적 수치와 일정 포함
                """,
                agent=framework_expert,
                context=[content_analysis_task],
                expected_output=f"{framework} 분석 결과 (markdown 형식)"
            )
            tasks.append(framework_task)
    
    # 3. 전문가별 분석 태스크
    for agent in agents:
        if "프레임워크" not in agent.role and agent.role != "전략기획 전문가":
            expert_task = Task(
                description=f"""
                {agent.role}의 전문성을 바탕으로 '{keyword}' 관련 전략을 수립하세요.
                
                분석 범위:
                1. 현재 상황 진단
                2. 개선 기회 도출
                3. 구체적 실행 방안
                4. 성과 측정 방안
                
                결과물 구성:
                1. 전문 영역 현황 분석
                2. 핵심 전략 제안
                3. 실행 계획
                4. 기대효과
                
                * 독서 토론 내용 적극 활용
                * 구체적 수치 목표 설정
                * 실행 가능성 중심
                """,
                agent=agent,
                context=[content_analysis_task],
                expected_output=f"{agent.role} 전략 제안 (markdown 형식)"
            )
            tasks.append(expert_task)
    
    # 4. 통합 보고서 작성 태스크
    final_report_task = create_final_report_task(agents, tasks, keyword)
    tasks.append(final_report_task)
    
    return tasks

def get_framework_guide(framework):
    """각 프레임워크별 분석 가이드 제공"""
    guides = {
        "블루오션 전략": """
        1. 전략 캔버스 작성
           - 현재 산업의 경쟁 요소 식별
           - 각 요소별 투자 수준 평가
        
        2. ERRC 그리드 분석
           - 제거(Eliminate): 제거할 요소
           - 감소(Reduce): 감소시킬 요소
           - 증가(Raise): 증가시킬 요소
           - 창조(Create): 새롭게 창조할 요소
        
        3. 비경쟁 공간 도출
           - 새로운 가치 곡선 설계
           - 차별화 포인트 식별
        """,
        
        "안소프 매트릭스": """
        1. 시장 침투 전략
           - 기존 제품/서비스로 기존 시장 점유율 확대 방안
        
        2. 시장 개발 전략
           - 기존 제품/서비스로 새로운 시장 진출 방안
        
        3. 제품 개발 전략
           - 기존 시장을 위한 새로운 제품/서비스 개발 방안
        
        4. 다각화 전략
           - 새로운 제품/서비스로 새로운 시장 진출 방안
        """,
        
        "PESTEL 분석": """
        1. 정치적(Political) 요인
           - 정부 정책, 규제, 정치적 안정성 분석
        
        2. 경제적(Economic) 요인
           - 경제 성장률, 인플레이션, 환율, 소득 수준 분석
        
        3. 사회적(Social) 요인
           - 인구 통계, 문화적 트렌드, 라이프스타일 변화 분석
        
        4. 기술적(Technological) 요인
           - 기술 혁신, R&D 활동, 자동화, 기술 변화 속도 분석
        
        5. 환경적(Environmental) 요인
           - 환경 규제, 지속가능성, 기후 변화 영향 분석
        
        6. 법적(Legal) 요인
           - 법률 변화, 고용법, 소비자 보호법, 안전 규제 분석
        """,
        
        # 다른 프레임워크 가이드 추가...
    }
    
    # 기본 가이드 제공
    default_guide = """
    1. 프레임워크의 주요 구성 요소 식별
    2. 각 요소별 상세 분석 수행
    3. 전략적 시사점 도출
    4. 실행 가능한 전략 방향 제안
    """
    
    return guides.get(framework, default_guide)

def create_final_report_task(agents, all_tasks, keyword):
    """최종 사업 전략 보고서 작성 태스크"""
    return Task(
        description=f"""
        모든 분석과 전략을 통합하여 CEO를 위한 최종 사업 전략 보고서를 한글로 작성하세요.
        
        ## 보고서 구성
        1. 개요
           - 보고서 목적 및 범위
           - 핵심 요약(Executive Summary)
           - 주요 발견사항 및 권고사항
           - '{keyword}' 관점의 핵심 전략 방향
        
        2. 시장 분석
           - 산업 동향 및 전망
           - 목표 시장 세분화
           - 경쟁 환경 분석
           - 선택된 프레임워크 기반 분석 결과
           - SWOT 분석(강점, 약점, 기회, 위협)
        
        3. 고객 분석
           - 목표 고객 프로필
           - 고객 니즈 및 구매 행동
           - 고객 피드백 및 인사이트
           - 가치 제안(Value Proposition)
        
        4. 제품/서비스 전략
           - 제품/서비스 포트폴리오
           - 차별화 요소
           - 가격 전략
           - 제품 개발 로드맵
        
        5. 마케팅 전략
           - 브랜드 포지셔닝
           - 판촉 및 홍보 계획
           - 디지털 마케팅 전략
           - 고객 획득 및 유지 전략
        
        6. 운영 전략
           - 생산/서비스 제공 프로세스
           - 공급망 관리
           - 품질 관리 시스템
           - 운영 효율성 개선 방안
        
        7. 조직 및 인적 자원 전략
           - 조직 구조
           - 핵심 역량 및 필요 인재
           - 인력 확보 및 개발 계획
        
        8. 재무 계획
           - 투자 요구사항
           - 수익 모델 및 예상 재무제표
           - 손익분기점 분석
           - 투자 수익률(ROI) 분석
        
        9. 리스크 관리
           - 주요 리스크 식별
           - 리스크 완화 전략
           - 비상 계획
        
        10. 실행 계획
            - 주요 이정표 및 타임라인
            - 책임 배분
            - 성과 측정 지표(KPI)
            - 모니터링 및 평가 메커니즘
        
        11. 결론 및 다음 단계
            - 종합 평가
            - 권고 사항
            - 향후 과제 및 발전 방향
        
        작성 요구사항:
        * 모든 내용은 한글로 작성할 것
        * 독서 토론 내용과 기존 적용 내용을 적극 활용할 것
        * 선택된 프레임워크의 분석 결과를 명확히 표시할 것
        * '{keyword}' 관점에서 전략의 일관성을 유지할 것
        * 구체적인 수치와 일정을 포함할 것
        * 실행 가능한 제안을 중심으로 작성할 것
        * 각 섹션은 명확한 근거와 논리를 바탕으로 작성할 것
        """,
        agent=agents[0],
        context=all_tasks,
        expected_output="최종 사업 전략 보고서 (한글, markdown 형식)"
    )

def generate_strategy_with_crewai(summary_content, application_content, keyword, llm, active_agents, update_log=None):
    try:
        selected_frameworks = st.session_state.get('selected_frameworks', [])
        
        if update_log:
            update_log("🔄 **초기화 정보**:")
            update_log(f"- 선택된 키워드: '{keyword}'")
            update_log(f"- 선택된 프레임워크: {', '.join(selected_frameworks)}")
            update_log(f"- 활성화된 에이전트: {', '.join(active_agents)}")
            update_log(f"- 사용 모델: {str(llm)}")
            update_log("---")
        
        # 에이전트 생성 과정 상세 로깅
        if update_log:
            update_log("🤖 **에이전트 생성 시작**")
            update_log("1. 전략기획 전문가 생성 중...")
        
        # 에이전트 생성 (llm 직접 전달)
        agents = create_strategic_agents(llm, selected_frameworks, active_agents)
        
        # 생성된 에이전트 상세 정보 로깅
        if update_log:
            update_log("\n✅ **생성된 에이전트 목록**:")
            for i, agent in enumerate(agents):
                update_log(f"👤 **에이전트 {i+1}**: {agent.role}")
                update_log(f"   - 목표: {agent.goal}")
                update_log(f"   - 배경: {agent.backstory}")
            update_log("---")
        
        # 태스크 생성 과정 로깅
        if update_log:
            update_log("📋 **태스크 생성 시작**")
        
        tasks = create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks)
        
        # 생성된 태스크 상세 정보 로깅
        if update_log:
            update_log("\n✅ **생성된 태스크 목록**:")
            for i, task in enumerate(tasks):
                task_desc = task.description.split('##')[0].strip()[:100] + "..."
                update_log(f"📌 **태스크 {i+1}**: {task_desc}")
                update_log(f"   - 담당 에이전트: {task.agent.role}")
        
        # Crew 실행 시작 로깅
        if update_log:
            update_log("\n🚀 **전략 수립 프로세스 시작**")
            update_log("- 에이전트들이 협력하여 전략을 수립합니다...")
        
        # Crew 생성 및 실행
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential
        )
        
        result = crew.kickoff()
        
        # 작업 완료 로깅
        if update_log:
            update_log("\n✅ **전략 수립 완료**")
            update_log("- 최종 결과물 생성 중...")
        
        # 결과 처리 및 반환
        if hasattr(result, 'raw'):
            return result.raw
        elif hasattr(result, 'output'):
            return result.output
        else:
            return str(result)
            
    except Exception as e:
        error_msg = f"CrewAI 전략 생성 중 오류 발생: {str(e)}"
        if update_log:
            update_log(f"\n❌ **오류 발생**: {error_msg}")
            update_log("- 에이전트 생성 및 실행 과정에서 문제가 발생했습니다.")
        st.error(error_msg)
        return None

if __name__ == "__main__":
    main() 