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
    
    # OpenAI API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        st.stop()
    
    # AI 모델 선택
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
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

def generate_strategy_with_crewai(summary_content, application_content, keyword, model_name, active_agents, update_log=None):
    """CrewAI를 사용하여 여러 에이전트가 협업하여 전략 생성"""
    try:
        # 작업 시작 로그
        if update_log:
            update_log("## CrewAI 전략 생성 시작")
            update_log("여러 전문 에이전트가 협업하여 종합적인 전략을 생성합니다.")
        
        # LLM 설정
        llm = ChatOpenAI(model=model_name, temperature=0.7, api_key=os.getenv('OPENAI_API_KEY'))
        
        # 에이전트 생성
        agents = []
        agent_descriptions = {}  # 에이전트 설명 저장
        
        # 시장 분석 에이전트
        if "market" in active_agents:
            agent_name = "시장 분석가"
            agent_desc = "시장 동향과 경쟁 환경을 분석하여 사업 기회와 위협을 식별합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            market_analyst = Agent(
                role=agent_name,
                goal="시장 동향과 경쟁 환경을 분석하여 사업 기회와 위협을 식별한다",
                backstory="당신은 10년 이상의 경력을 가진 시장 분석 전문가입니다. 산업 동향을 파악하고 경쟁 환경을 분석하는 능력이 뛰어납니다.",
                verbose=True,
                llm=llm
            )
            agents.append(market_analyst)
            agent_descriptions[agent_name] = agent_desc
            
            if update_log:
                update_log(f"✅ {agent_name} 활성화 완료")
        
        # 고객 인사이트 에이전트
        if "customer" in active_agents:
            agent_name = "고객 인사이트 전문가"
            agent_desc = "고객의 니즈와 행동 패턴을 분석하여 고객 중심의 전략을 제시합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            customer_analyst = Agent(
                role=agent_name,
                goal="고객의 니즈와 행동 패턴을 분석하여 고객 중심의 전략을 제시한다",
                backstory="당신은 고객 행동 분석과 세분화에 전문성을 가진 마케팅 리서처입니다. 고객의 숨겨진 니즈를 발견하는 능력이 뛰어납니다.",
                verbose=True,
                llm=llm
            )
            agents.append(customer_analyst)
            agent_descriptions[agent_name] = agent_desc
            
            if update_log:
                update_log(f"✅ {agent_name} 활성화 완료")
        
        # 재무 분석 에이전트
        if "financial" in active_agents:
            agent_name = "재무 분석가"
            agent_desc = "사업의 재무적 측면을 분석하고 수익성과 투자 전략을 제시합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            financial_analyst = Agent(
                role=agent_name,
                goal="사업의 재무적 측면을 분석하고 수익성과 투자 전략을 제시한다",
                backstory="당신은 재무 모델링과 투자 분석에 전문성을 가진 재무 전문가입니다. 비용 구조 최적화와 수익성 향상 전략에 능숙합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(financial_analyst)
            agent_descriptions[agent_name] = agent_desc
            
            if update_log:
                update_log(f"✅ {agent_name} 활성화 완료")
        
        # 전략 기획 에이전트
        if "strategic" in active_agents:
            agent_name = "전략 기획가"
            agent_desc = "장기적 관점에서 조직의 비전과 목표를 설정하고 전략적 방향성을 제시합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            strategic_planner = Agent(
                role=agent_name,
                goal="조직의 장기 전략 방향을 수립하고 실행 가능한 전략적 이니셔티브를 도출한다",
                backstory="당신은 20년 이상의 전략 컨설팅 경험을 가진 전략가입니다. 복잡한 비즈니스 환경에서 명확한 전략적 방향을 제시하는 능력이 탁월합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(strategic_planner)
            agent_descriptions[agent_name] = agent_desc
            
            if update_log:
                update_log(f"✅ {agent_name} 활성화 완료")
        
        # 혁신 관리 에이전트
        if "innovation" in active_agents:
            agent_name = "혁신 관리자"
            agent_desc = "새로운 기회를 발굴하고 혁신적인 솔루션을 개발하여 조직의 경쟁력을 강화합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            innovation_manager = Agent(
                role=agent_name,
                goal="혁신적인 비즈니스 모델과 솔루션을 발굴하고 실행 전략을 수립한다",
                backstory="당신은 디지털 혁신과 비즈니스 모델 혁신 분야의 전문가입니다. 새로운 기회를 발굴하고 혁신적인 솔루션을 개발하는 능력이 탁월합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(innovation_manager)
            agent_descriptions[agent_name] = agent_desc
        
        # 인적 자원 관리 에이전트
        if "hr" in active_agents:
            agent_name = "인적 자원 관리자"
            agent_desc = "조직의 인재 전략을 수립하고 조직 문화와 역량을 강화합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            hr_manager = Agent(
                role=agent_name,
                goal="조직의 인재 확보, 육성, 유지 전략을 수립하고 조직 문화를 발전시킨다",
                backstory="당신은 인재 관리와 조직 개발 분야의 전문가입니다. 인재 전략 수립과 조직 문화 혁신에 깊은 경험이 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(hr_manager)
            agent_descriptions[agent_name] = agent_desc
        
        # 기술/IT 전략 에이전트
        if "tech" in active_agents:
            agent_name = "기술 전략가"
            agent_desc = "기술 트렌드를 분석하고 디지털 전환 전략을 수립합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            tech_strategist = Agent(
                role=agent_name,
                goal="기술 혁신 기회를 발굴하고 디지털 전환 전략을 수립한다",
                backstory="당신은 최신 기술 트렌드와 디지털 전환 전략 수립에 전문성을 가진 전문가입니다. 기술을 비즈니스 가치로 전환하는 능력이 탁월합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(tech_strategist)
            agent_descriptions[agent_name] = agent_desc
        
        # 법률/규제 준수 에이전트
        if "legal" in active_agents:
            agent_name = "법률 규제 전문가"
            agent_desc = "법적 리스크를 분석하고 규제 준수 전략을 수립합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            legal_expert = Agent(
                role=agent_name,
                goal="법적 리스크를 식별하고 규제 준수 전략을 수립한다",
                backstory="당신은 기업 법무와 규제 준수 분야의 전문가입니다. 법적 리스크 관리와 규제 대응 전략 수립에 풍부한 경험이 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(legal_expert)
            agent_descriptions[agent_name] = agent_desc
        
        # 지속가능성 전략 에이전트
        if "sustainability" in active_agents:
            agent_name = "지속가능성 전략가"
            agent_desc = "ESG 전략을 수립하고 지속가능한 비즈니스 모델을 개발합니다."
            
            if update_log:
                update_log(f"### {agent_name} 초기화 중...")
                update_log(f"**역할**: {agent_desc}")
            
            sustainability_strategist = Agent(
                role=agent_name,
                goal="ESG 관점의 비즈니스 기회를 발굴하고 지속가능성 전략을 수립한다",
                backstory="당신은 ESG 전략과 지속가능 경영 분야의 전문가입니다. 환경, 사회, 지배구조 측면에서의 가치 창출 전략 수립에 전문성이 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(sustainability_strategist)
            agent_descriptions[agent_name] = agent_desc
        
        # 추가: 품질 관리 에이전트
        if "quality" in active_agents:
            agent_name = "품질 관리 전문가"
            agent_desc = "제품/서비스 품질 전략을 수립하고 품질 관리 시스템을 설계합니다."
            
            quality_expert = Agent(
                role=agent_name,
                goal="품질 경쟁력 강화 전략을 수립하고 품질 관리 체계를 구축한다",
                backstory="당신은 품질 관리와 프로세스 혁신 분야의 전문가입니다. 품질 시스템 구축과 지속적 개선 활동에 풍부한 경험이 있습니다.",
                verbose=True,
                llm=llm
            )
            agents.append(quality_expert)
            agent_descriptions[agent_name] = agent_desc
        
        # 추가: 글로벌 전략 에이전트
        if "global" in active_agents:
            agent_name = "글로벌 전략가"
            agent_desc = "국제 시장 진출 전략을 수립하고 글로벌 운영 전략을 개발합니다."
            
            global_strategist = Agent(
                role=agent_name,
                goal="글로벌 시장 진출 전략을 수립하고 국제 경쟁력을 강화한다",
                backstory="당신은 글로벌 비즈니스 전략과 국제 시장 진출 분야의 전문가입니다. 다양한 국가와 문화에 대한 이해를 바탕으로 성공적인 글로벌화 전략을 수립합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(global_strategist)
            agent_descriptions[agent_name] = agent_desc
        
        # 추가: 데이터 분석 에이전트
        if "data" in active_agents:
            agent_name = "데이터 분석가"
            agent_desc = "데이터 기반의 인사이트를 도출하고 의사결정 전략을 제시합니다."
            
            data_analyst = Agent(
                role=agent_name,
                goal="데이터 분석을 통해 전략적 인사이트를 도출하고 의사결정을 지원한다",
                backstory="당신은 빅데이터 분석과 데이터 기반 의사결정 분야의 전문가입니다. 복잡한 데이터에서 실행 가능한 인사이트를 도출하는 능력이 탁월합니다.",
                verbose=True,
                llm=llm
            )
            agents.append(data_analyst)
            agent_descriptions[agent_name] = agent_desc
        
        # 태스크 설명 정의
        task_descriptions = {
            "context_analysis": "요약 내용과 기존 적용 내용을 분석하여 핵심 인사이트를 추출하고 강점과 약점을 파악합니다.",
            "expert_analysis": "각 전문 영역에서 기회와 도전 과제를 식별하고 구체적인 전략을 제안합니다.",
            "strategy_integration": "모든 전문가의 분석을 통합하여 종합적인 전략을 수립합니다."
        }
        
        # 태스크 생성
        if update_log:
            update_log("## 에이전트 태스크 생성")
            update_log("각 에이전트가 수행할 작업을 정의합니다.")
        
        tasks = []
        
        # 기본 정보 분석 태스크
        if update_log:
            update_log(f"### 태스크 1: 기본 분석")
            update_log(f"**담당**: {agents[0].role}")
            update_log(f"**내용**: {task_descriptions['context_analysis']}")
        
        context_analysis = Task(
            description=f"""
            다음 독서 토론 요약 내용과 기존 적용 내용을 분석하세요:
            
            [요약 내용]
            {summary_content[:500]}...
            
            [기존 적용 내용]
            {application_content[:500]}...
            
            '{keyword}' 관점에서 핵심 인사이트를 추출하고 기존 적용 내용의 강점과 약점을 분석하세요.
            """,
            expected_output="요약 내용과 기존 적용 내용에 대한 분석 결과, 핵심 인사이트, 강점과 약점 분석",
            agent=agents[0]  # 첫 번째 에이전트에게 할당
        )
        tasks.append(context_analysis)
        
        # 에이전트별 전문 분석 태스크 생성
        for i, agent in enumerate(agents[:-1]):  # 마지막 통합 에이전트 제외
            if i == 0:  # 첫 번째 에이전트는 이미 context_analysis 태스크가 있음
                continue
                
            agent_role = agent.role
            
            if update_log:
                update_log(f"### 태스크 {i+1}: {agent_role}의 전문 분석")
                update_log(f"**담당**: {agent_role}")
                update_log(f"**내용**: {task_descriptions['expert_analysis']}")
            
            agent_task = Task(
                description=f"""
                이전 분석 결과를 참고하여, '{keyword}' 관점에서 {agent_role}로서의 전문적인 분석을 수행하세요.
                
                [요약 내용]
                {summary_content[:300]}...
                
                [기존 적용 내용]
                {application_content[:300]}...
                
                다음을 포함하여 분석하세요:
                1. 주요 기회와 도전 과제
                2. 구체적인 전략 제안
                3. 실행 계획과 예상 결과
                
                전문적이고 실행 가능한 제안을 제시하세요.
                """,
                expected_output=f"{agent_role}의 전문적 분석 결과, 기회와 도전 과제, 전략 제안, 실행 계획",
                agent=agent,
                context=[context_analysis]
            )
            tasks.append(agent_task)
        
        # 최종 전략 통합 태스크
        if update_log:
            update_log(f"### 태스크 {len(agents)}: 전략 통합")
            update_log(f"**담당**: 전략 통합 전문가")
            update_log(f"**내용**: {task_descriptions['strategy_integration']}")
        
        final_strategy_task = Task(
            description=f"""
            모든 전문가의 분석 결과를 통합하여 '{keyword}' 관점에서 종합적인 전략을 수립하세요.
            
            다음 형식으로 최종 전략을 작성하세요:
            
            # {keyword} 관점의 전략
            
            ## 전략적 개요
            - 비전 및 미션
            - 핵심 가치 제안
            - 전략적 목표
            
            ## 시장 및 경쟁 분석
            - 시장 동향 및 기회
            - 경쟁 환경 분석
            - 차별화 전략
            
            ## 고객 가치 제안
            - 목표 고객 세그먼트
            - 고객 니즈 및 가치 제안
            - 고객 경험 전략
            
            ## 핵심 전략 이니셔티브
            1. 첫 번째 전략 (제목)
               - 전략적 근거
               - 상세 실행 방안
               - 필요 자원 및 역량
               
            2. 두 번째 전략 (제목)
               - 전략적 근거
               - 상세 실행 방안
               - 필요 자원 및 역량
               
            3. 세 번째 전략 (제목)
               - 전략적 근거
               - 상세 실행 방안
               - 필요 자원 및 역량
            
            ## 실행 로드맵
            - 단기 실행 항목 (1-3개월)
              * 구체적 실행 계획
              * 책임자/팀 지정
              * 성과 지표
            - 중기 실행 항목 (3-6개월)
              * 구체적 실행 계획
              * 책임자/팀 지정
              * 성과 지표
            - 장기 실행 항목 (6-12개월)
              * 구체적 실행 계획
              * 책임자/팀 지정
              * 성과 지표
            
            ## 조직 및 리소스 계획
            - 조직 구조 및 거버넌스
            - 필요 인력 및 역량
            - 예산 및 자원 할당
            
            ## 리스크 관리
            - 주요 리스크 식별
            - 리스크 평가 매트릭스
            - 리스크 대응 전략
            
            ## 혁신 및 지속가능성
            - 혁신 전략
            - 기술 로드맵
            - ESG 고려사항
            
            ## 성과 측정 및 모니터링
            - KPI 정의
            - 모니터링 체계
            - 피드백 및 조정 메커니즘
            
            ## 기대 효과
            - 정량적 효과
              * 재무적 성과
              * 운영 효율성
            - 정성적 효과
              * 조직 역량 강화
              * 시장 포지셔닝
            
            * 기존 적용 내용의 좋은 점은 유지하되, 요약 내용의 새로운 인사이트를 통합하여 더 발전된 전략을 제시해 주세요.
            * 구체적이고 실행 가능한 내용으로 작성해 주세요.
            * 전문적이고 논리적인 어조로 작성해 주세요.
            * 각 섹션은 상호 연계성을 가지고 일관된 전략적 방향을 제시해야 합니다.
            """,
            expected_output="마크다운 형식의 종합적인 전략 문서",
            agent=agents[-1],
            context=tasks
        )
        tasks.append(final_strategy_task)
        
        # Crew 생성 및 실행
        if update_log:
            update_log("## 에이전트 팀(Crew) 구성")
            update_log("모든 에이전트가 협업하여 작업을 수행합니다.")
        
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential  # 순차적 처리
        )
        
        if update_log:
            update_log("## 작업 시작")
            update_log("에이전트 팀이 작업을 시작합니다. 이 과정은 몇 분 정도 소요될 수 있습니다.")
        
        # 작업 진행 상황 시뮬레이션
        import threading
        import time
        
        # 작업 진행 상황을 시뮬레이션하는 함수
        def simulate_progress():
            if not update_log:
                return
                
            # 각 에이전트별 작업 단계
            work_stages = [
                "자료 검토 중...",
                "분석 수행 중...",
                "인사이트 도출 중...",
                "전략 수립 중...",
                "결과 정리 중..."
            ]
            
            # 각 태스크별 진행 상황 시뮬레이션
            for i, task in enumerate(tasks):
                agent_role = task.agent.role
                
                # 태스크 시작 알림
                update_log(f"🔄 **{agent_role}** 작업 시작: 태스크 {i+1}/{len(tasks)}", agent_role)
                
                # 작업 단계별 진행 상황 표시
                for stage in work_stages:
                    # 실제 작업이 완료되었는지 확인 (전역 변수로 설정)
                    if hasattr(simulate_progress, 'completed') and simulate_progress.completed:
                        return
                        
                    time.sleep(3)  # 3초 간격으로 업데이트
                    update_log(f"🔍 {stage}", agent_role)
                
                # 태스크 완료 알림
                update_log(f"✅ **{agent_role}** 작업 완료", agent_role)
        
        # 진행 상황 시뮬레이션 스레드 시작
        simulate_progress.completed = False
        progress_thread = threading.Thread(target=simulate_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        try:
            # 실제 작업 실행
            result = crew.kickoff()
            
            # 시뮬레이션 중지
            simulate_progress.completed = True
            
            if update_log:
                update_log("## 작업 완료")
                update_log("✅ 모든 에이전트 작업이 완료되었습니다!")
                update_log("✅ 최종 전략이 생성되었습니다.")
            
            # CrewOutput 객체에서 문자열 추출
            if hasattr(result, 'raw'):
                return result.raw  # 최신 버전의 CrewAI
            elif hasattr(result, 'output'):
                return result.output  # 일부 버전의 CrewAI
            else:
                # 객체를 문자열로 변환 시도
                return str(result)
                
        except Exception as e:
            # 시뮬레이션 중지
            simulate_progress.completed = True
            raise e
            
    except Exception as e:
        error_msg = f"CrewAI 전략 생성 중 오류 발생: {str(e)}"
        if update_log:
            update_log(f"❌ **오류 발생**: {error_msg}")
        st.error(error_msg)
        # 오류 발생 시 기존 방식으로 폴백
        return generate_strategy(summary_content, application_content, keyword, model_name)

if __name__ == "__main__":
    main() 