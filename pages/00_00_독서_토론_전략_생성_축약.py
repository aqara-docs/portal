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
    
    # 비용 최적화 옵션
    st.sidebar.header("⚙️ 실행 설정")
    cost_effective = st.sidebar.checkbox(
        "비용 최적화 모드",
        help="활성화하면 더 경제적인 모델을 사용하고 에이전트 수를 최적화합니다. 비활성화하면 더 정교한 분석이 가능하지만 비용이 증가합니다.",
        value=True
    )
    
    debug_mode = st.sidebar.checkbox(
        "디버그 모드",
        help="에이전트와 태스크의 실행 과정을 자세히 표시합니다.",
        value=False
    )
    st.session_state.debug_mode = debug_mode  # 세션 상태에 저장

    # 비용 최적화에 따른 모델 선택
    if cost_effective:
        ai_models = {
            "GPT-3.5": "gpt-3.5-turbo",
            "Ollama-Llama2": "llama2:latest",
            "Ollama-Mistral": "mistral:latest"
        }
        default_model = "GPT-3.5" if debug_mode else "GPT-3.5"
    else:
        ai_models = {
            "GPT-4": "gpt-4-turbo-preview",
            "GPT-3.5-16K": "gpt-3.5-turbo-16k",
            "Ollama-Mixtral": "mixtral:latest"
        }
        default_model = "GPT-4"
    
    # OpenAI API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        st.stop()
    
    # AI 모델 선택
    MODEL_NAME = os.getenv('MODEL_NAME', default_model)
    
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
                coopetition = st.checkbox("협력적 경쟁관계 (Coopetition)", 
                    help="경쟁사와의 협력을 통한 가치 창출 전략")
                toc = st.checkbox("제약이론 (Theory of Constraints)", 
                    help="시스템의 제약요소 식별 및 개선을 통한 성과 향상")
                porter_competitive = st.checkbox("마이클 포터의 경쟁전략", 
                    help="원가우위, 차별화, 집중화 전략을 통한 경쟁우위 확보")
                swot = st.checkbox("SWOT 분석", 
                    help="강점, 약점, 기회, 위협 요인 분석")
            
            with col2:
                bmc = st.checkbox("비즈니스 모델 캔버스", 
                    help="9개 블록으로 구성된 비즈니스 모델 분석")
                vrio = st.checkbox("VRIO 프레임워크", 
                    help="자원 기반 관점의 경쟁 우위 분석")
                game_theory = st.checkbox("게임이론 (Game Theory)", 
                    help="전략적 의사결정과 경쟁자 반응 예측을 위한 분석")
                lean = st.checkbox("린 스타트업 & 고객 개발 모델", 
                    help="MVP와 고객 피드백 기반의 반복 개선 전략")
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
            if coopetition: selected_frameworks.append("협력적 경쟁관계")
            if toc: selected_frameworks.append("제약이론")
            if porter_competitive: selected_frameworks.append("마이클 포터의 경쟁전략")
            if swot: selected_frameworks.append("SWOT 분석")
            if bmc: selected_frameworks.append("비즈니스 모델 캔버스")
            if vrio: selected_frameworks.append("VRIO 프레임워크")
            if game_theory: selected_frameworks.append("게임이론")
            if lean: selected_frameworks.append("린 스타트업 & 고객 개발 모델")
            if disruptive: selected_frameworks.append("디스럽티브 이노베이션")
            if custom_framework: selected_frameworks.append(custom_framework)

            # 선택된 프레임워크가 있을 경우 표시
            if selected_frameworks:
                st.markdown("#### 선택된 전략 프레임워크")
                for framework in selected_frameworks:
                    st.markdown(f"- {framework}")
            else:
                st.info("전략 프레임워크를 선택하지 않았습니다. AI가 자동으로 적합한 프레임워크를 선정합니다.")

            # 선택된 프레임워크를 세션 상태에 저장
            st.session_state.selected_frameworks = selected_frameworks
    
    # 세션 상태 초기화
    if 'new_strategy' not in st.session_state:
        st.session_state.new_strategy = None
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
            summary_content = summary_file.read().decode('utf-8')
            st.write("### 요약 내용 미리보기")
            st.text_area("요약 내용", summary_content[:500] + "..." if len(summary_content) > 500 else summary_content, height=300, disabled=True)
            
            # 세션 상태에 저장
            if 'summary_content' not in st.session_state:
                st.session_state.summary_content = summary_content
                st.session_state.summary_filename = summary_file.name
    
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
            # 새 전략 생성 (CrewAI 또는 일반 방식)
            if use_crewai:
                # 활성화된 에이전트 목록 생성
                active_agents = []
                if market_agent: active_agents.append("market")
                if customer_agent: active_agents.append("customer")
                if financial_agent: active_agents.append("financial")
                if risk_agent: active_agents.append("risk")
                if operations_agent: active_agents.append("operations")
                if marketing_agent: active_agents.append("marketing")
                if strategic_agent: active_agents.append("strategic")
                if innovation_agent: active_agents.append("innovation")
                if hr_agent: active_agents.append("hr")
                if tech_agent: active_agents.append("tech")
                if legal_agent: active_agents.append("legal")
                if sustainability_agent: active_agents.append("sustainability")
                if quality_agent: active_agents.append("quality")
                if global_agent: active_agents.append("global")
                if data_agent: active_agents.append("data")
                
                new_strategy = generate_strategy_with_crewai(
                    st.session_state.summary_content,
                    st.session_state.selected_application['content'],
                    st.session_state.analysis_keyword,
                    model_name,
                    active_agents,
                    update_log  # 로그 업데이트 함수 전달
                )
            else:
                new_strategy = generate_strategy(
                    st.session_state.summary_content,
                    st.session_state.selected_application['content'],
                    st.session_state.analysis_keyword,
                    model_name
                )
            
            # 세션 상태에 저장
            st.session_state.new_strategy = new_strategy
            st.session_state.saved_to_db = False
            
            # 페이지 새로고침
            st.rerun()
    
    # 생성된 전략이 있으면 표시
    if st.session_state.new_strategy:
        st.success("새로운 전략이 생성되었습니다!")
        
        # 생성된 전략 표시
        st.write("### 생성된 전략")
        st.markdown(st.session_state.new_strategy)
        
        # 파일명 생성 (날짜 포함)
        today = datetime.now().strftime('%Y%m%d')
        new_file_name = f"{st.session_state.book_title}_적용_{st.session_state.analysis_keyword}_{today}.md"
        
        # 저장 확인 (이미 저장되지 않은 경우에만 버튼 표시)
        if not st.session_state.saved_to_db:
            save_button = st.button("💾 DB에 저장", key="save_button")
            
            if save_button:
                try:
                    # 전략 내용이 문자열인지 확인
                    strategy_content = st.session_state.new_strategy
                    if not isinstance(strategy_content, str):
                        strategy_content = str(strategy_content)
                    
                    # 요약 파일 저장
                    summary_saved = save_material(
                        st.session_state.book_title, 
                        st.session_state.summary_filename, 
                        st.session_state.summary_content, 
                        "summary"
                    )
                    
                    # 새 전략 저장
                    strategy_saved = save_material(
                        st.session_state.book_title, 
                        new_file_name, 
                        strategy_content,  # 문자열로 변환된 내용 사용
                        "application"
                    )
                    
                    if summary_saved and strategy_saved:
                        st.session_state.saved_to_db = True
                        st.success("요약 파일과 새로운 전략이 성공적으로 저장되었습니다!")
                        st.balloons()
                    else:
                        st.error("저장 중 오류가 발생했습니다.")
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {str(e)}")
        else:
            st.info("이미 DB에 저장되었습니다.")
            
            # 새로운 전략 생성 버튼
            if st.button("🔄 새로운 전략 생성하기", key="new_strategy_button"):
                # 세션 상태 초기화
                st.session_state.new_strategy = None
                st.session_state.saved_to_db = False
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
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO reading_materials (
                book_title, file_name, content, type
            ) VALUES (%s, %s, %s, %s)
        """, (book_title, file_name, content, type))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"DB 저장 실패: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def generate_strategy(summary_content, application_content, keyword, model_name):
    """AI를 사용하여 새로운 전략 생성 (기존 방식)"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    다음은 독서 토론에서 나온 요약 내용과 기존 적용 내용입니다.
    요약 내용을 기존 적용 내용에 통합하여 '{keyword}' 관점에서 더 발전된 새로운 전략을 생성해 주세요.
    
    [요약 내용]
    {summary_content}
    
    [기존 적용 내용]
    {application_content}
    
    다음 형식으로 새로운 전략을 작성해 주세요:
    
    # {keyword} 관점의 전략
    
    ## 핵심 인사이트
    - 요약 내용에서 얻은 핵심 인사이트 3가지
    - 각 인사이트가 '{keyword}' 관점에서 가지는 의미
    
    ## 전략적 접근
    1. 첫 번째 전략 (제목)
       - 상세 설명
       - 실행 방안
       
    2. 두 번째 전략 (제목)
       - 상세 설명
       - 실행 방안
       
    3. 세 번째 전략 (제목)
       - 상세 설명
       - 실행 방안
    
    ## 실행 계획
    - 단기 실행 항목 (1-3개월)
    - 중기 실행 항목 (3-6개월)
    - 장기 실행 항목 (6-12개월)
    
    ## 기대 효과
    - '{keyword}' 관점에서 예상되는 주요 효과 3가지
    - 각 효과의 측정 방법
    
    * 기존 적용 내용의 좋은 점은 유지하되, 요약 내용의 새로운 인사이트를 통합하여 더 발전된 전략을 제시해 주세요.
    * 구체적이고 실행 가능한 내용으로 작성해 주세요.
    * 전문적이고 논리적인 어조로 작성해 주세요.
    """
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 비즈니스 전략 전문가입니다. 독서에서 얻은 인사이트를 실제 비즈니스에 적용하는 구체적인 전략을 제시합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"AI 전략 생성 중 오류 발생: {str(e)}")
        return None

def generate_strategy_with_crewai(summary_content, application_content, keyword, llm, active_agents, update_log=None):
    try:
        selected_frameworks = st.session_state.get('selected_frameworks', [])
        debug_mode = st.session_state.get('debug_mode', False)
        
        if update_log:
            update_log("## 전략 생성 프로세스 시작")
            update_log(f"- 선택된 키워드: {keyword}")
            update_log(f"- 활성화된 에이전트: {len(active_agents)}개")
            update_log(f"- 선택된 프레임워크: {len(selected_frameworks)}개")
        
        # 에이전트와 태스크 생성
        agents = create_strategic_agents(llm, selected_frameworks, active_agents, debug_mode)
        tasks = create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks, debug_mode)
        
        # 매니저 에이전트 생성
        manager_agent = Agent(
            role="전략 프로젝트 매니저",
            goal="전체 전략 수립 프로세스 조정 및 관리",
            backstory="수석 프로젝트 매니저로서 복잡한 전략 프로젝트를 성공적으로 이끈 풍부한 경험이 있습니다.",
        verbose=True,
        llm=llm
    )
        
        if debug_mode:
            st.write("### 🚀 태스크 실행 시작")
            st.write("✅ 매니저 에이전트 활성화")
        
        # 각 태스크 순차적 실행
        results = []
        for i, task in enumerate(tasks):
            if debug_mode:
                st.write(f"⚙️ 실행 중: Task {i+1}/{len(tasks)} - {task.description.split()[0]}")
            
            try:
                # 단일 태스크 실행을 위한 임시 크루 생성
                temp_crew = Crew(
                    agents=[task.agent, manager_agent],
                    tasks=[task],
                    verbose=True,
                    process=Process.sequential
                )
                
                # 태스크 실행
                task_result = temp_crew.kickoff()
                if hasattr(task_result, 'raw_output'):
                    results.append(task_result.raw_output)
                else:
                    results.append(str(task_result))
                
                if debug_mode:
                    st.write(f"✅ 완료: {task.description.split()[0]}")
                    preview = results[-1][:200] + "..." if len(results[-1]) > 200 else results[-1]
                    st.write(f"결과 미리보기:\n{preview}")
                
                if update_log:
                    update_log(f"✅ {task.description.split()[0]} 완료")
                
            except Exception as task_error:
                error_msg = f"태스크 실행 실패: {str(task_error)}"
                if debug_mode:
                    st.write(f"❌ {error_msg}")
                if update_log:
                    update_log(f"❌ {error_msg}")
                results.append(None)
        
        # 최종 보고서를 섹션별로 생성
        final_sections = []
        section_tasks = [
            {
                "title": "Executive Summary",
                "description": """
                경영진을 위한 핵심 요약을 작성하세요:
                - 핵심 전략 방향과 실행 계획
                - 단계별 매출 목표(2025년 35억, 2026년 100억, 2027년 250억, 2029년 600억)와 달성 전략
                - 주요 성공 요인과 리스크 관리 방안
                - 투자 대비 수익 예상 및 재무 계획
                """,
                "pages": 1
            },
            {
                "title": "시장 및 경쟁 분석",
                "description": """
                시장과 경쟁 환경을 분석하세요:
                - 시장 규모와 성장성 분석 (구체적 수치 포함)
                - 경쟁사 포지셔닝과 주요 경쟁사 분석
                - 고객 세그먼트별 니즈와 기회 분석
                - SWOT 분석 결과 및 시사점
                """,
                "pages": 2
            },
            {
                "title": "매출 목표 달성 전략",
                "description": """
                연도별 매출 목표(2025년 35억, 2026년 100억, 2027년 250억, 2029년 600억) 달성을 위한 
                구체적인 전략과 액션 플랜을 수립하세요:
                
                - 연도별 매출 목표 달성을 위한 핵심 전략
                - 제품/서비스 포트폴리오 전략과 가격 정책
                - 채널별 매출 계획과 성장 전략
                - 고객 확보 및 유지 전략
                - 각 전략별 구체적인 액션 플랜(담당자, 일정, 예산 포함)
                """,
                "pages": 4
            },
            {
                "title": "마케팅 및 영업 전략",
                "description": """
                매출 목표 달성을 지원할 마케팅 및 영업 전략을 수립하세요:
                - 브랜드 포지셔닝과 차별화 전략
                - 채널별 마케팅 전략과 예산 배분
                - 영업 조직 및 프로세스 설계
                - 구체적인 마케팅 캠페인 계획
                - 실행 일정과 담당 조직
                """,
                "pages": 3
            },
            {
                "title": "운영 및 재무 계획",
                "description": """
                사업 운영과 재무 계획을 수립하세요:
                - 조직 구조와 인력 계획
                - 프로세스 최적화 방안
                - 연도별 손익 계획과 투자 계획
                - 원가 구조 최적화 전략
                - 현금흐름 관리 방안
                """,
                "pages": 3
            },
            {
                "title": "리스크 관리 및 실행 계획",
                "description": """
                리스크 관리와 전략 실행 계획을 수립하세요:
                - 주요 리스크 요인과 대응 전략
                - 단계별 실행 로드맵
                - 조직별 역할과 책임
                - KPI 설정 및 성과 측정 방법
                - 전략 조정 메커니즘
                """,
                "pages": 2
            }
        ]

        for section in section_tasks:
            section_task = Task(
                description=f"""
                {section['description']}
                
                작성 시 필수 준수사항:
                1. 반드시 한글로 작성할 것
                2. 모든 수치와 목표는 구체적으로 제시할 것
                3. 실행 계획은 상세하게 기술할 것 (담당자, 일정, 예산 포함)
                4. 각 전문가의 분석 내용을 빠짐없이 통합적으로 반영할 것
                5. 해당 섹션은 약 {section['pages']}페이지 분량으로 작성할 것
                6. 특히 매출 목표 달성을 위한 구체적인 액션 플랜을 강조할 것
                
                보고서는 전문적이고 논리적인 어조로, 명확한 헤딩과 서브헤딩, 표, 
                리스트 등을 활용하여 가독성 높게 작성하십시오.
                """,
                expected_output=f"{section['title']} 섹션 (약 {section['pages']}페이지 분량의 상세 분석)",
                agent=agents[0],
                context=tasks
            )
            tasks.append(section_task)
        
        if debug_mode:
            st.write("✅ 모든 태스크 생성 완료")
        
        return tasks

    except Exception as e:
        error_msg = f"전략 생성 중 오류 발생: {str(e)}"
        if update_log:
            update_log(f"❌ 오류: {error_msg}")
        if debug_mode:
            st.write(f"### ❌ 오류 발생\n{error_msg}")
            st.write("### 🔍 디버그 정보")
            st.write(f"에이전트 수: {len(agents)}")
            st.write(f"태스크 수: {len(tasks)}")
        return error_msg

def create_strategic_agents(llm, selected_frameworks, active_agents, debug_mode=False):
    """전략 수립을 위한 에이전트 생성"""
    agents = []
    
    # 프레임워크 전문가 정의를 먼저 수행
    framework_experts = {
        "블루오션 전략": "가치 혁신과 시장 창출 전략 전문가",
        "SWOT 분석": "내부 역량과 외부 환경 분석 전문가",
        "비즈니스 모델 캔버스": "비즈니스 모델 혁신 전문가",
        "마이클 포터의 경쟁전략": "경쟁우위 확보 전략 전문가",
        "협력적 경쟁관계": "경쟁사와의 협력 전략 전문가",
        "제약이론": "시스템 제약 식별 및 개선 전문가",
        "VRIO 프레임워크": "지속가능한 경쟁 우위 분석 전문가",
        "게임이론": "전략적 의사결정 및 경쟁자 행동 예측 전문가",
        "린 스타트업": "빠른 시장 검증과 피봇 전문가",
        "디스럽티브 이노베이션": "시장 판도 변화 전문가"
    }
    
    if debug_mode:
        st.write("### 🤖 에이전트 생성 시작")
    
    # 선택된 프레임워크가 없을 경우 AI가 자동 선택
    if not selected_frameworks:
        framework_selector = Agent(
            role="전략 프레임워크 선정 전문가",
            goal="비즈니스 상황에 가장 적합한 전략 프레임워크 선정",
            backstory="""
            다양한 산업과 비즈니스 상황에서 최적의 전략 프레임워크를 선정한 경험이 풍부한 전략 컨설턴트입니다.
            특히 신규 사업 개발과 성장 전략 수립에 전문성을 보유하고 있습니다.
            """,
            verbose=True,
            llm=llm
        )
        
        framework_selection_task = Task(
            description="""
            아카라라이프 신사업실의 상황을 분석하여 가장 적합한 전략 프레임워크 3개를 선정하세요.
            
            고려사항:
            1. 신규 사업 개발 및 성장 단계
                - 시장 진입 전략
                - 성장 가속화 방안
                - 수익성 확보 전략
            
            2. 산업 특성
                - 시장 성숙도
                - 경쟁 강도
                - 기술 혁신 속도
            
            3. 조직 역량
                - 현재 보유 자원
                - 핵심 역량
                - 조직 문화
            
            4. 매출 목표 달성
                - 단계별 성장 전략
                - 리소스 확보 방안
                - 실행 가능성
            
            선택 가능한 프레임워크 목록:
            1. 블루오션 전략
            2. SWOT 분석
            3. 비즈니스 모델 캔버스
            4. 마이클 포터의 경쟁전략
            5. 협력적 경쟁관계
            6. 제약이론
            7. VRIO 프레임워크
            8. 게임이론
            9. 린 스타트업
            10. 디스럽티브 이노베이션
            
            위 목록에서 정확히 3개의 프레임워크를 선택하여 다음 형식으로만 응답하세요:
            1. [프레임워크명]
            2. [프레임워크명]
            3. [프레임워크명]
            
            다른 설명이나 이유는 포함하지 마세요.
            """,
            expected_output="1. [프레임워크명]\n2. [프레임워크명]\n3. [프레임워크명]",
            agent=framework_selector
        )
        
        # 임시 크루 생성 및 태스크 실행
        temp_crew = Crew(
            agents=[framework_selector],
            tasks=[framework_selection_task],
            verbose=True,
            process=Process.sequential
        )
        
        # 프레임워크 선정 결과 처리
        try:
            result = temp_crew.kickoff()
            result_text = str(result)  # CrewOutput을 문자열로 변환
            
            # 결과에서 프레임워크 이름만 추출
            selected_frameworks = []
            for line in result_text.split('\n'):
                if line.strip().startswith(('1.', '2.', '3.')):
                    framework = line.split('.')[1].strip()
                    if framework in framework_experts:
                        selected_frameworks.append(framework)
            
            if len(selected_frameworks) != 3:
                if debug_mode:
                    st.write(f"선택된 프레임워크: {selected_frameworks}")
                raise ValueError("프레임워크 3개를 선정하지 못했습니다.")
            
            if debug_mode:
                st.write("🎯 AI가 선택한 프레임워크:")
                for i, framework in enumerate(selected_frameworks, 1):
                    st.write(f"{i}. {framework}")
        except Exception as e:
            if debug_mode:
                st.write(f"프레임워크 선택 오류: {str(e)}")
                st.write(f"AI 응답: {result_text if 'result_text' in locals() else '응답 없음'}")
            st.warning("프레임워크 자동 선택 중 오류가 발생하여 기본 프레임워크를 사용합니다.")
            selected_frameworks = ["비즈니스 모델 캔버스", "블루오션 전략", "린 스타트업"]

    # 1. 코디네이터 에이전트 (항상 포함)
    coordinator = Agent(
        role="전략 기획 코디네이터",
        goal="모든 분석과 전략을 통합하여 실행 가능한 전략 보고서 작성",
        backstory="수석 전략 컨설턴트로서 다양한 산업의 전략 수립 경험이 풍부하며, 여러 전문가의 의견을 조율하고 통합하는 역할을 수행합니다.",
        verbose=True,
        llm=llm
    )
    agents.append(coordinator)
    
    # 2. 프레임워크 전문가 에이전트
    for framework in selected_frameworks:
        if framework in framework_experts:
            agent = Agent(
                role=f"{framework} 전문가",
                goal=f"{framework}를 활용한 심층 분석 및 전략 제안",
                backstory=f"당신은 {framework_experts[framework]}입니다. 해당 프레임워크를 활용한 수많은 프로젝트 경험이 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(agent)
            if debug_mode:
                st.write(f"✅ {framework} 전문가 에이전트 생성 완료")

    # 3. 기능별 전문가 에이전트
    functional_experts = {
        "market": ("시장 분석가", "시장 동향과 경쟁 환경 분석"),
        "customer": ("고객 인사이트 전문가", "고객 니즈와 행동 분석"),
        "financial": ("재무 전략가", "재무적 실행 가능성과 수익성 분석"),
        "marketing": ("마케팅 전략가", "마케팅 및 브랜드 전략 수립"),
        "operations": ("운영 최적화 전문가", "프로세스와 운영 효율성 분석"),
        "risk": ("리스크 관리 전문가", "리스크 식별 및 대응 전략 수립")
    }

    for agent_key in active_agents:
        if agent_key in functional_experts:
            role, goal = functional_experts[agent_key]
            agent = Agent(
                role=role,
                goal=goal,
                backstory=f"당신은 {role}로서 해당 분야의 전문성과 실무 경험을 보유하고 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(agent)
            if debug_mode:
                st.write(f"✅ {role} 에이전트 생성 완료")

    return agents

def create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks, debug_mode=False):
    """전략 수립을 위한 태스크 생성"""
    tasks = []
    
    if debug_mode:
        st.write("### 📋 태스크 생성 시작")

    # 1. 초기 통합 분석 태스크 수정
    initial_analysis = Task(
        description=f"""
        '{keyword}' 관점에서 요약 내용과 기존 적용 내용을 심층 분석하세요.
        특히 아카라라이프 신사업실의 매출 목표를 고려하여 분석을 진행하세요.
        
        분석 요구사항:
        1. 핵심 개념과 시사점 도출
        2. 기존 전략의 강점과 개선점
        3. '{keyword}' 관련 주요 기회 요인
        4. 매출 목표 달성을 위한 실행 가능한 전략 방향 제시
        5. 매출 목표와의 연계성 분석
        
        [요약 내용]
        {summary_content}
        
        [기존 적용 내용]
        {application_content}
        
        주요 고려사항:
        - 기존 적용 내용에서 언급된 매출 목표를 반드시 참고할 것
        - 매출 목표 달성을 위한 구체적인 전략 제시
        - 목표 달성의 현실성 검토 및 필요한 조정사항 제안
        """,
        expected_output="""
        다음 형식으로 상세한 분석 보고서를 작성하세요:
        
        # 초기 분석 보고서
        
        ## 1. 매출 목표 분석
        - 현재 매출 목표
        - 목표의 실현 가능성 평가
        - 목표 달성을 위한 핵심 요구사항
        
        ## 2. 핵심 개념과 시사점
        - (5개 이상의 핵심 발견사항)
        
        ## 3. 기존 전략 분석
        ### 강점
        - (3개 이상)
        ### 개선점
        - (3개 이상)
        
        ## 4. 주요 기회 요인
        - (4개 이상의 구체적 기회)
        
        ## 5. 전략 방향 제안
        ### 매출 목표 연계 전략
        - (매출 목표 달성을 위한 3-5개의 핵심 전략)
        ### 실행 계획
        - (구체적인 실행 방안과 일정)
        """,
        agent=agents[0]
    )
    tasks.append(initial_analysis)

    # 2. 프레임워크별 분석 태스크
    for i, framework in enumerate(selected_frameworks):
        framework_task = Task(
                description=f"""
            {framework}를 사용하여 '{keyword}' 관련 전략을 분석하세요.
            
            요구사항:
            1. {framework}의 각 요소별 상세 분석 수행
            2. 분석 결과를 바탕으로 한 전략적 시사점 도출
            3. 구체적인 실행 방안 제시
            
            참고 자료:
            {initial_analysis.description}
            """,
            expected_output=f"""
            # {framework} 분석 보고서
            
            ## 1. 프레임워크 분석
            (프레임워크의 각 요소별 상세 분석)
            
            ## 2. 전략적 시사점
            - (최소 3개의 핵심 시사점)
            
            ## 3. 실행 방안
            ### 단기 전략 (0-6개월)
            - (2-3개의 구체적 실행 계획)
            
            ### 중기 전략 (6-18개월)
            - (2-3개의 구체적 실행 계획)
            
            ### 장기 전략 (18개월 이상)
            - (2-3개의 구체적 실행 계획)
            """,
            agent=agents[i+1],
            context=[initial_analysis]
        )
        tasks.append(framework_task)

    # 3. 전문가별 분석 태스크
    expert_tasks = []
    for i, agent in enumerate(agents[len(selected_frameworks)+1:]):
        if debug_mode:
            st.write(f"✅ {agent.role} 전문가 태스크 생성 중")
        
        expert_task = Task(
        description=f"""
            {agent.role}의 관점에서 '{keyword}' 관련 전략을 분석하고 제안하세요.
            
            요구사항:
            1. 현재 상황 분석
                - 시장/산업 동향
                - 경쟁사 분석
                - 고객 니즈
            2. 핵심 과제 도출
                - 주요 기회 요인
                - 해결해야 할 문제점
            3. 전략적 제안
                - 구체적인 실행 방안
                - 기대 효과
                - 필요 자원
            4. 리스크 분석
                - 잠재적 위험 요소
                - 대응 방안
            
            참고 자료:
            - 초기 분석 결과
            - 프레임워크 분석 결과
            """,
            expected_output=f"""
            # {agent.role} 전문 분석 보고서
            
            ## 1. 현황 분석
            ### 시장/산업 동향
            - (주요 트렌드 3-5개)
            
            ### 경쟁 현황
            - (주요 경쟁사 분석)
            
            ### 고객 니즈
            - (핵심 니즈 3-5개)
            
            ## 2. 핵심 과제
            - (우선순위가 높은 과제 3-5개)
            
            ## 3. 전략적 제안
            ### 단기 실행 방안 (0-6개월)
            - (구체적인 실행 계획 2-3개)
            
            ### 중장기 전략 방향 (6개월 이상)
            - (전략적 방향성 2-3개)
            
            ## 4. 리스크 관리
            ### 주요 리스크
            - (잠재적 위험 요소 2-3개)
            
            ### 대응 방안
            - (각 리스크별 구체적 대응 방안)
            """,
            agent=agent,
            context=[initial_analysis] + tasks[1:i+1]
        )
        expert_tasks.append(expert_task)
        tasks.append(expert_task)

    # 최종 통합 전략을 섹션별로 생성
    final_sections = []
    section_tasks = [
        {
            "title": "Executive Summary",
            "description": """
            경영진을 위한 핵심 요약을 작성하세요:
            - 핵심 전략 방향과 실행 계획
            - 단계별 매출 목표(2025년 35억, 2026년 100억, 2027년 250억, 2029년 600억)와 달성 전략
            - 주요 성공 요인과 리스크 관리 방안
            - 투자 대비 수익 예상 및 재무 계획
            """,
            "pages": 1
        },
        {
            "title": "시장 및 경쟁 분석",
            "description": """
            시장과 경쟁 환경을 분석하세요:
            - 시장 규모와 성장성 분석 (구체적 수치 포함)
            - 경쟁사 포지셔닝과 주요 경쟁사 분석
            - 고객 세그먼트별 니즈와 기회 분석
            - SWOT 분석 결과 및 시사점
            """,
            "pages": 2
        },
        {
            "title": "매출 목표 달성 전략",
            "description": """
            연도별 매출 목표(2025년 35억, 2026년 100억, 2027년 250억, 2029년 600억) 달성을 위한 
            구체적인 전략과 액션 플랜을 수립하세요:
            
            - 연도별 매출 목표 달성을 위한 핵심 전략
            - 제품/서비스 포트폴리오 전략과 가격 정책
            - 채널별 매출 계획과 성장 전략
            - 고객 확보 및 유지 전략
            - 각 전략별 구체적인 액션 플랜(담당자, 일정, 예산 포함)
            """,
            "pages": 4
        },
        {
            "title": "마케팅 및 영업 전략",
            "description": """
            매출 목표 달성을 지원할 마케팅 및 영업 전략을 수립하세요:
            - 브랜드 포지셔닝과 차별화 전략
            - 채널별 마케팅 전략과 예산 배분
            - 영업 조직 및 프로세스 설계
            - 구체적인 마케팅 캠페인 계획
            - 실행 일정과 담당 조직
            """,
            "pages": 3
        },
        {
            "title": "운영 및 재무 계획",
            "description": """
            사업 운영과 재무 계획을 수립하세요:
            - 조직 구조와 인력 계획
            - 프로세스 최적화 방안
            - 연도별 손익 계획과 투자 계획
            - 원가 구조 최적화 전략
            - 현금흐름 관리 방안
            """,
            "pages": 3
        },
        {
            "title": "리스크 관리 및 실행 계획",
            "description": """
            리스크 관리와 전략 실행 계획을 수립하세요:
            - 주요 리스크 요인과 대응 전략
            - 단계별 실행 로드맵
            - 조직별 역할과 책임
            - KPI 설정 및 성과 측정 방법
            - 전략 조정 메커니즘
            """,
            "pages": 2
        }
    ]

    for section in section_tasks:
        section_task = Task(
            description=f"""
            {section['description']}
            
            작성 시 필수 준수사항:
            1. 반드시 한글로 작성할 것
            2. 모든 수치와 목표는 구체적으로 제시할 것
            3. 실행 계획은 상세하게 기술할 것 (담당자, 일정, 예산 포함)
            4. 각 전문가의 분석 내용을 빠짐없이 통합적으로 반영할 것
            5. 해당 섹션은 약 {section['pages']}페이지 분량으로 작성할 것
            6. 특히 매출 목표 달성을 위한 구체적인 액션 플랜을 강조할 것
            
            보고서는 전문적이고 논리적인 어조로, 명확한 헤딩과 서브헤딩, 표, 
            리스트 등을 활용하여 가독성 높게 작성하십시오.
            """,
            expected_output=f"{section['title']} 섹션 (약 {section['pages']}페이지 분량의 상세 분석)",
            agent=agents[0],
            context=tasks
        )
        tasks.append(section_task)
    
    if debug_mode:
        st.write("✅ 모든 태스크 생성 완료")
    
    return tasks

if __name__ == "__main__":
    main() 