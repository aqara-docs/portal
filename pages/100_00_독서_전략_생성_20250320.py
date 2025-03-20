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
    
    # OpenAI API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        st.stop()
    
    # AI 모델 선택
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4')
    ai_models = {
        "GPT-4": MODEL_NAME,
        "GPT-3.5": "gpt-3.5-turbo"
    }
    
    # 고급 설정 섹션
    with st.expander("고급 설정"):
        selected_model = st.selectbox(
            "OpenAI 모델 선택",
            list(ai_models.keys()),
            index=0
        )
        model_name = ai_models[selected_model]
        
        # CrewAI 설정
        use_crewai = st.checkbox("CrewAI 사용", value=True)
        
        if use_crewai:
            st.subheader("활성화할 에이전트")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                market_agent = st.checkbox("시장 분석 에이전트", value=True)
                customer_agent = st.checkbox("고객 인사이트 에이전트", value=True)
                financial_agent = st.checkbox("재무 분석 에이전트", value=True)
                risk_agent = st.checkbox("리스크 관리 에이전트", value=True)
            
            with col2:
                operations_agent = st.checkbox("운영 최적화 에이전트", value=True)
                marketing_agent = st.checkbox("마케팅 전략 에이전트", value=True)
                strategic_agent = st.checkbox("전략 기획 에이전트", value=True)
                innovation_agent = st.checkbox("혁신 관리 에이전트", value=True)
            
            with col3:
                hr_agent = st.checkbox("인적 자원 관리 에이전트", value=True)
                tech_agent = st.checkbox("기술/IT 전략 에이전트", value=True)
                legal_agent = st.checkbox("법률/규제 준수 에이전트", value=True)
                sustainability_agent = st.checkbox("지속가능성 전략 에이전트", value=True)
            
            # 추가 에이전트 선택
            st.subheader("추가 전문 에이전트")
            col4, col5 = st.columns(2)
            
            with col4:
                quality_agent = st.checkbox("품질 관리 에이전트")
                global_agent = st.checkbox("글로벌 전략 에이전트")
            
            with col5:
                data_agent = st.checkbox("데이터 분석 에이전트")

            # 전략 프레임워크 선택 섹션
            st.subheader("전략 프레임워크 선택")
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
            # 새 전략 생성
            result = generate_strategy_with_crewai(
                    st.session_state.summary_content,
                    st.session_state.selected_application['content'],
                    st.session_state.analysis_keyword,
                    model_name,
                active_agents=True,
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

def create_strategic_agents(llm, selected_frameworks):
    """전략 수립을 위한 전문 에이전트 생성"""
    agents = []
    
    # 전략 기획 전문가
    strategic_planner = Agent(
        role="전략 기획 전문가",
        goal=f"""
        - 선택된 전략 프레임워크({', '.join(selected_frameworks)})를 활용하여 종합적인 비즈니스 전략 수립
        - 각 프레임워크의 핵심 요소를 전략에 직접 통합하여 실행 가능한 전략 도출
        - 시장 기회와 위험 요소를 고려한 전략적 방향성 제시
        """,
        backstory=f"""
        당신은 20년 경력의 전략 컨설턴트입니다. 글로벌 컨설팅 펌에서 다양한 산업의 
        전략 수립 프로젝트를 성공적으로 수행했으며, 특히 {', '.join(selected_frameworks)} 
        프레임워크를 활용한 비즈니스 전략 수립에 전문성을 보유하고 있습니다.
        """,
        verbose=True,
        llm=llm
    )
    agents.append(strategic_planner)
    
    # 프레임워크 전문가들 추가
    for framework in selected_frameworks:
        framework_expert = Agent(
            role=f"{framework} 전문가",
            goal=f"""
            - {framework} 프레임워크를 활용하여 비즈니스 전략 수립
            - {framework}의 핵심 요소를 적용한 실행 가능한 전략 제안
            - 다른 프레임워크 전문가들과 협력하여 통합된 전략 개발
            """,
            backstory=f"""
            당신은 {framework} 프레임워크 분야의 전문가로, 다양한 기업에 이 프레임워크를 
            적용하여 성공적인 전략을 수립한 경험이 있습니다. 이론적 지식뿐만 아니라 
            실제 비즈니스 상황에서의 적용 경험이 풍부합니다.
            """,
            verbose=True,
            llm=llm
        )
        agents.append(framework_expert)
    
    # 마케팅 전략가
    marketing_strategist = Agent(
        role="마케팅 전략가",
        goal=f"""
        - 선택된 프레임워크({', '.join(selected_frameworks)})를 활용한 마케팅 전략 수립
        - 시장 세분화 및 타겟 고객 정의
        - 차별화된 포지셔닝 전략 수립
        - 효과적인 마케팅 믹스(4P) 전략 개발
        """,
        backstory="""
        당신은 15년 경력의 마케팅 전문가입니다. 주요 글로벌 브랜드의 마케팅 디렉터로 
        근무했으며, 성공적인 브랜드 런칭과 마케팅 캠페인을 다수 수행했습니다.
        """,
        verbose=True,
        llm=llm
    )
    agents.append(marketing_strategist)

    # 영업 전략가
    sales_strategist = Agent(
        role="영업 전략가",
        goal=f"""
        - 선택된 프레임워크({', '.join(selected_frameworks)})를 활용한 영업 전략 수립
        - 효과적인 영업 채널 전략 수립
        - 고객 관계 관리 프로그램 개발
        - 매출 확대를 위한 영업 전략 수립
        """,
        backstory="""
        당신은 B2B/B2C 영업 분야에서 18년의 경력을 보유한 영업 전문가입니다. 
        다양한 산업에서 영업 조직을 성공적으로 이끌었으며, 특히 신규 시장 진출과 
        매출 성장 전략 수립에 탁월한 능력을 보유하고 있습니다.
        """,
        verbose=True,
        llm=llm
    )
    agents.append(sales_strategist)

    return agents

def create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks):
    """전략 수립을 위한 태스크 생성"""
    tasks = []
    
    # 요약 및 적용 내용 심층 분석 태스크
    content_analysis_task = Task(
        description=f"""
        다음 독서 토론 요약 내용과 기존 적용 내용을 철저히 분석하세요:
        
        ## 요약 내용
        {summary_content}
        
        ## 기존 적용 내용
        {application_content}
        
        분석 시 다음 사항에 중점을 두세요:
        1. 요약 내용의 핵심 개념, 원칙, 프레임워크 추출 (최소 5개)
        2. 기존 적용 내용의 주요 전략 및 실행 방안 식별 (최소 5개)
        3. '{keyword}' 관점에서 가장 중요한 인사이트 도출 (최소 3개)
        4. 요약 내용과 적용 내용 간의 연결점 및 통합 가능성 분석
        5. 요약 내용에서 기존 적용 내용을 보완할 수 있는 새로운 아이디어 도출
        
        분석 결과는 다음 형식으로 작성하세요:
        
        ### 요약 내용 핵심 개념
        1. [개념 1]: [상세 설명 및 페이지 참조]
        2. [개념 2]: [상세 설명 및 페이지 참조]
        ...
        
        ### 기존 적용 내용 주요 전략
        1. [전략 1]: [상세 설명]
        2. [전략 2]: [상세 설명]
        ...
        
        ### '{keyword}' 관점의 핵심 인사이트
        1. [인사이트 1]: [상세 설명 및 근거]
        2. [인사이트 2]: [상세 설명 및 근거]
        ...
        
        ### 통합 가능성 및 보완점
        1. [통합 포인트 1]: [상세 설명]
        2. [통합 포인트 2]: [상세 설명]
        ...
        
        ### 새로운 적용 아이디어
        1. [아이디어 1]: [상세 설명 및 근거]
        2. [아이디어 2]: [상세 설명 및 근거]
        ...
        
        * 모든 분석은 원문의 구체적인 내용과 페이지를 인용하여 근거를 제시하세요
        * 추상적인 개념보다 구체적인 사례와 적용 방안에 집중하세요
        * 분석 결과는 다음 전략 프레임워크 적용의 기초 자료로 활용됩니다
        """,
        agent=agents[0],
        expected_output="요약 및 적용 내용 심층 분석 결과 (markdown 형식)"
    )
    tasks.append(content_analysis_task)
    
    # 각 프레임워크별 전략 개발 태스크
    framework_tasks = []
    for i, framework in enumerate(selected_frameworks):
        framework_guide = get_framework_guide(framework)
        framework_expert_index = i + 1  # 프레임워크 전문가 인덱스
        
        if framework_expert_index < len(agents):
            task = Task(
                description=f"""
                '{framework}' 프레임워크를 활용하여 요약 내용과 적용 내용을 기반으로 구체적인 비즈니스 전략을 개발하세요.
                
                ## 요약 내용
                {summary_content}
                
                ## 기존 적용 내용
                {application_content}
                
                ## '{framework}' 활용 가이드
                {framework_guide}
                
                ## 전략 개발 요구사항
                1. 요약 내용에서 최소 3개 이상의 구체적인 개념/원칙을 인용하여 전략에 직접 적용하세요
                   - 예: "책의 X페이지에서 언급된 [개념]을 활용하여..."
                   - 예: "저자가 제시한 [원칙]에 따르면..."
                
                2. 기존 적용 내용의 전략을 최소 2개 이상 발전시키고 보완하세요
                   - 예: "기존 적용 내용의 [전략]을 [개념]을 통해 다음과 같이 발전시킬 수 있습니다..."
                
                3. '{framework}'의 핵심 요소를 활용하여 '{keyword}' 관점에서 전략을 체계적으로 수립하세요
                   - 각 프레임워크 요소별로 구체적인 전략 방안 제시
                   - 요약/적용 내용의 구체적인 인용과 연결
                
                4. 전략의 실행 방안을 구체적으로 제시하세요
                   - 단계별 실행 계획
                   - 필요한 자원 및 역량
                   - 예상되는 장애물 및 극복 방안
                
                * 단순히 프레임워크로 분석하는 것이 아니라, 프레임워크를 활용하여 실제 전략을 개발하세요
                * 모든 전략 요소는 요약 내용 또는 적용 내용의 구체적인 부분과 직접 연결되어야 합니다
                * 추상적인 제안이 아닌 실행 가능한 구체적인 전략을 제시하세요
                """,
                agent=agents[framework_expert_index],
                context=[content_analysis_task],
                async_execution=True,
                expected_output=f"{framework}를 활용한 전략 (markdown 형식)"
            )
            framework_tasks.append(task)
    
    tasks.extend(framework_tasks)

    # 마케팅 전략 수립 태스크
    marketing_strategy_task = Task(
        description=f"""
        요약 내용, 적용 내용 및 프레임워크 기반 전략을 통합하여 구체적인 마케팅 전략을 수립하세요:
        
        ## 요약 내용
        {summary_content}
        
        ## 적용 내용
        {application_content}
        
        ## 마케팅 전략 요구사항
        1. 시장 세분화 및 타겟팅
           - 요약 내용에서 언급된 고객 세분화 원칙 직접 인용 및 적용
           - 기존 적용 내용의 타겟팅 전략 발전 및 보완
           - 각 프레임워크의 요소를 활용한 세분화 전략 수립
        
        2. 포지셔닝 전략
           - 요약 내용의 차별화 원칙 직접 인용 및 적용
           - 기존 적용 내용의 포지셔닝 전략 발전 및 보완
           - '{keyword}' 관점에서의 독특한 가치 제안
        
        3. 마케팅 믹스(4P) 전략
           - 제품(Product): 요약 내용의 제품 개발 원칙 적용
           - 가격(Price): 요약 내용의 가격 책정 원칙 적용
           - 유통(Place): 요약 내용의 유통 채널 전략 적용
           - 프로모션(Promotion): 요약 내용의 커뮤니케이션 원칙 적용
        
        * 각 전략 요소에 특정 프레임워크의 요소가 어떻게 활용되었는지 명확히 설명하세요
        * 요약/적용 내용에서 추출한 구체적인 예시와 인사이트를 직접 인용하세요
        * 실행 가능한 액션 플랜을 제시하세요
        """,
        agent=agents[-2],  # 마케팅 전략가
        context=[content_analysis_task] + framework_tasks,
        expected_output="마케팅 전략 (markdown 형식)"
    )
    tasks.append(marketing_strategy_task)

    # 영업 전략 수립 태스크
    sales_strategy_task = Task(
        description=f"""
        요약 내용, 적용 내용 및 프레임워크 기반 전략을 통합하여 구체적인 영업 전략을 수립하세요:
        
        ## 요약 내용
        {summary_content}
        
        ## 적용 내용
        {application_content}
        
        ## 영업 전략 요구사항
        1. 영업 채널 전략
           - 요약 내용에서 언급된 채널 전략 원칙 직접 인용 및 적용
           - 기존 적용 내용의 채널 전략 발전 및 보완
           - 각 프레임워크의 요소를 활용한 채널 전략 수립
        
        2. 고객 관계 관리
           - 요약 내용의 고객 관계 구축 원칙 직접 인용 및 적용
           - 기존 적용 내용의 CRM 전략 발전 및 보완
           - '{keyword}' 관점에서의 고객 경험 설계
        
        3. 매출 확대 전략
           - 요약 내용의 매출 증대 원칙 직접 인용 및 적용
           - 기존 적용 내용의 매출 전략 발전 및 보완
           - 각 프레임워크의 요소를 활용한 매출 확대 방안
        
        * 각 전략 요소에 특정 프레임워크의 요소가 어떻게 활용되었는지 명확히 설명하세요
        * 요약/적용 내용에서 추출한 구체적인 예시와 인사이트를 직접 인용하세요
        * 실행 가능한 액션 플랜을 제시하세요
        """,
        agent=agents[-1],  # 영업 전략가
        context=[content_analysis_task] + framework_tasks,
        expected_output="영업 전략 (markdown 형식)"
    )
    tasks.append(sales_strategy_task)

    # 최종 전략 통합 태스크
    final_strategy_task = Task(
        description=f"""
        모든 분석 결과와 전략을 통합하여 요약 내용과 적용 내용에 깊이 기반한 '{keyword}' 관점의 종합적인 비즈니스 전략을 수립하세요:
        
        ## 요약 내용
        {summary_content}
        
        ## 적용 내용
        {application_content}
        
        ## 통합 비즈니스 전략 요구사항
        1. 전략적 개요
           - 비전 및 미션 (요약 내용의 핵심 원칙 직접 인용)
           - 핵심 가치 제안 (요약 내용과 각 프레임워크 요소 통합)
           - 전략적 목표 ('{keyword}' 관점 중심)
        
        2. 프레임워크 기반 전략
           {' '.join([f'- {framework}를 활용한 전략' for framework in selected_frameworks])}
           - 각 프레임워크의 핵심 요소가 어떻게 요약/적용 내용과 통합되었는지 명확히 설명
           - 요약 내용의 구체적인 개념/원칙 직접 인용
        
        3. 마케팅 전략 통합
           - 마케팅 전략가의 프레임워크 기반 전략 통합
           - 요약 내용의 마케팅 원칙 직접 인용 및 적용
           - 기존 적용 내용의 마케팅 전략 발전 및 보완
        
        4. 영업 전략 통합
           - 영업 전략가의 프레임워크 기반 전략 통합
           - 요약 내용의 영업 원칙 직접 인용 및 적용
           - 기존 적용 내용의 영업 전략 발전 및 보완
        
        5. 실행 계획
           - 단기 실행 항목 (1-3개월): 요약/적용 내용 기반 구체적 실행 방안
           - 중기 실행 항목 (3-6개월): 요약/적용 내용 기반 구체적 실행 방안
           - 장기 실행 항목 (6-12개월): 요약/적용 내용 기반 구체적 실행 방안
           - 각 항목별 책임자/팀 및 성과 지표
        
        * 모든 전략 요소는 요약 내용 또는 적용 내용의 구체적인 부분과 직접 연결되어야 합니다
        * 각 전략 요소가 어떤 프레임워크의 어떤 요소에서 도출되었는지 명시하세요
        * 요약 내용과 적용 내용의 핵심 인사이트를 전략에 명확히 반영하세요
        * '{keyword}' 관점이 전략 전반에 일관되게 적용되도록 하세요
        * 구체적이고 실행 가능한 전략을 제시하세요
        """,
        agent=agents[0],  # 전략 기획 전문가
        context=tasks,
        expected_output="최종 통합 전략 (markdown 형식)"
    )
    tasks.append(final_strategy_task)

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

def generate_strategy_with_crewai(summary_content, application_content, keyword, model_name, active_agents, update_log=None):
    try:
        selected_frameworks = st.session_state.get('selected_frameworks', [])
        
        # 디버그 메시지 출력
        if update_log:
            update_log(f"🔍 **디버그**: 선택된 키워드: '{keyword}'")
            update_log(f"🔍 **디버그**: 선택된 프레임워크: {', '.join(selected_frameworks) if selected_frameworks else '없음'}")
            update_log(f"🔍 **디버그**: 사용 모델: {model_name}")
        
        # 프레임워크가 선택되지 않았을 경우 기본 프레임워크 설정
        if not selected_frameworks:
            selected_frameworks = ["SWOT 분석", "비즈니스 모델 캔버스"]
            if update_log:
                update_log(f"⚠️ **알림**: 프레임워크가 선택되지 않아 기본 프레임워크를 사용합니다: {', '.join(selected_frameworks)}")
        
        # LLM 설정
        llm = ChatOpenAI(model=model_name, temperature=0.7)
        
        # 에이전트 생성 (도구 없이)
        agents = create_strategic_agents(llm, selected_frameworks)
        
        if update_log:
            update_log(f"✅ **에이전트 생성 완료**: {len(agents)}개의 에이전트가 준비되었습니다.")
            for i, agent in enumerate(agents):
                update_log(f"👤 **에이전트 {i+1}**: {agent.role}")
        
        # 태스크 생성
        tasks = create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks)
        
        if update_log:
            update_log(f"✅ **태스크 생성 완료**: {len(tasks)}개의 태스크가 준비되었습니다.")
            for i, task in enumerate(tasks):
                update_log(f"📋 **태스크 {i+1}**: {task.description.split('##')[0].strip()[:50]}...")
        
        # 프레임워크 분석 시작 알림
        if update_log:
            update_log("🚀 **분석 시작**: 선택된 프레임워크로 분석을 시작합니다...")
            for framework in selected_frameworks:
                update_log(f"📊 **프레임워크 분석**: '{framework}' 분석 중...")
        
        # Crew 생성 및 실행
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential
        )
        
        # 결과 생성
        if update_log:
            update_log("⏳ **처리 중**: CrewAI가 전략을 생성하고 있습니다. 잠시만 기다려주세요...")
        
        crew_output = crew.kickoff()
        
        # CrewOutput 객체에서 문자열 추출
        if hasattr(crew_output, 'raw'):
            result = crew_output.raw  # 최신 버전의 CrewAI
        elif hasattr(crew_output, 'output'):
            result = crew_output.output  # 일부 버전의 CrewAI
        else:
            # 객체를 문자열로 변환 시도
            result = str(crew_output)
        
        # 프레임워크 적용 확인
        framework_mentions = []
        for framework in selected_frameworks:
            if framework in result:
                framework_mentions.append(framework)
        
        if update_log:
            if framework_mentions:
                update_log(f"✅ **프레임워크 적용 확인**: 결과에 다음 프레임워크가 포함되어 있습니다: {', '.join(framework_mentions)}")
            else:
                update_log(f"⚠️ **주의**: 결과에 선택된 프레임워크가 명시적으로 언급되지 않았습니다.")
        
        # 프레임워크가 결과에 포함되지 않은 경우 보완
        if not all(framework in result for framework in selected_frameworks):
            if update_log:
                update_log("🔄 **보완 중**: 프레임워크 분석 결과를 보완합니다...")
            
            # 프레임워크 분석 보완
            supplement_prompt = f"""
            다음은 '{keyword}' 관점에서 생성된 전략입니다. 이 전략에 다음 프레임워크의 분석 결과를 명시적으로 통합해주세요:
            {', '.join(selected_frameworks)}
            
            각 프레임워크별로 분석 섹션을 추가하고, 전략 전반에 프레임워크의 인사이트가 반영되도록 해주세요.
            
            원본 전략:
            {result}
            """
            
            try:
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "당신은 비즈니스 전략 전문가입니다. 전략 프레임워크를 활용한 분석에 능숙합니다."},
                        {"role": "user", "content": supplement_prompt}
                    ],
                    temperature=0.7
                )
                
                result = response.choices[0].message.content
                
                if update_log:
                    update_log("✅ **보완 완료**: 프레임워크 분석이 전략에 통합되었습니다.")
            except Exception as e:
                if update_log:
                    update_log(f"⚠️ **보완 실패**: {str(e)}")
        
        # Markdown 파일로 저장
        output_filename = f"strategy_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(result)
        
        if update_log:
            update_log(f"✅ **완료**: 전략 생성이 완료되었습니다. 파일명: {output_filename}")
        
        return result
            
    except Exception as e:
        error_msg = f"CrewAI 전략 생성 중 오류 발생: {str(e)}"
        if update_log:
            update_log(f"❌ **오류 발생**: {error_msg}")
        st.error(error_msg)
        return None

if __name__ == "__main__":
    main() 