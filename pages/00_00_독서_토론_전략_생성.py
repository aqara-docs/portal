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
        if debug_mode:
            default_model = "GPT-3.5"
        else:
            ai_models = {
                "GPT-4": "gpt-4o-mini",
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
        
        # 최종 보고서 생성
        final_report = f"""
        # {keyword} 중심 사업 전략 보고서

        ## 1. 개요
        - 분석 기반: {st.session_state.book_title}
        - 핵심 키워드: {keyword}
        - 적용 프레임워크: {', '.join(selected_frameworks)}

        ## 2. 초기 분석 결과
        {results[0] if results and results[0] else '초기 분석 결과를 가져올 수 없습니다.'}

        ## 3. 프레임워크 기반 전략 분석
        """
        
        # 프레임워크 분석 결과 추가
        framework_results = []
        for i, framework in enumerate(selected_frameworks):
            task_output = results[i + 1]
            if task_output:
                framework_results.append(f"### {framework}\n{task_output}")
        
        final_report += "\n\n".join(framework_results) if framework_results else "프레임워크 분석 결과를 가져올 수 없습니다."
        
        # 전문가 분석 결과 추가
        expert_start_idx = len(selected_frameworks) + 1
        expert_results = []
        for i, agent in enumerate(agents[len(selected_frameworks)+1:]):
            task_idx = expert_start_idx + i
            if task_idx < len(tasks):
                task_output = results[task_idx]
                if task_output:
                    expert_results.append(f"### {agent.role}의 분석\n{task_output}")
        
        final_report += "\n\n## 4. 전문가 분석 결과\n"
        final_report += "\n\n".join(expert_results) if expert_results else "전문가 분석 결과를 가져올 수 없습니다."
        
        # 최종 통합 전략 추가
        if tasks[-1] and results[-1]:
            final_report += f"\n\n## 5. 통합 전략 제안\n{results[-1]}"
        else:
            final_report += "\n\n## 5. 통합 전략 제안\n최종 전략을 가져올 수 없습니다."
        
        if debug_mode:
            st.write("### 📑 최종 보고서 생성 완료")
            st.write(final_report)
        
        return final_report
        
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
    
    if debug_mode:
        st.write("### 🤖 에이전트 생성 시작")
    
    # 1. 코디네이터 에이전트 (항상 포함)
    coordinator = Agent(
        role="전략 기획 코디네이터",
        goal="모든 분석과 전략을 통합하여 실행 가능한 전략 보고서 작성",
        backstory="수석 전략 컨설턴트로서 다양한 산업의 전략 수립 경험이 풍부하며, 여러 전문가의 의견을 조율하고 통합하는 역할을 수행합니다.",
                verbose=True,
                llm=llm
            )
    agents.append(coordinator)
    if debug_mode:
        st.write("✅ 코디네이터 에이전트 생성 완료")

    # 2. 프레임워크 전문가 에이전트
    framework_experts = {
        "블루오션 전략": "가치 혁신과 시장 창출 전략 전문가",
        "SWOT 분석": "내부 역량과 외부 환경 분석 전문가",
        "비즈니스 모델 캔버스": "비즈니스 모델 혁신 전문가",
        "포터의 5가지 힘": "산업 구조와 경쟁 분석 전문가",
        "협력적 경쟁관계": "경쟁사와의 협력 전략 전문가",
        "제약이론": "시스템 제약 식별 및 개선 전문가",
        "마이클 포터의 경쟁전략": "경쟁우위 확보 전략 전문가",
        "게임이론": "전략적 의사결정 및 경쟁자 행동 예측 전문가",
        "디스럽티브 이노베이션": "혁신 전략 전문가"
    }

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

    # 1. 초기 통합 분석 태스크
    initial_analysis = Task(
        description=f"""
        '{keyword}' 관점에서 요약 내용과 기존 적용 내용을 심층 분석하세요.
        
        분석 요구사항:
        1. 핵심 개념과 시사점 도출
        2. 기존 전략의 강점과 개선점
        3. '{keyword}' 관련 주요 기회 요인
        4. 실행 가능한 전략 방향 제시
        
        [요약 내용]
        {summary_content}
        
        [기존 적용 내용]
        {application_content}
        """,
        expected_output="""
        다음 형식으로 상세한 분석 보고서를 작성하세요:
        
        # 초기 분석 보고서
        
        ## 1. 핵심 개념과 시사점
        - (5개 이상의 핵심 발견사항)
        
        ## 2. 기존 전략 분석
        ### 강점
        - (3개 이상)
        ### 개선점
        - (3개 이상)
        
        ## 3. 주요 기회 요인
        - (4개 이상의 구체적 기회)
        
        ## 4. 전략 방향 제안
        - (3-5개의 실행 가능한 전략)
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

    # 4. 최종 통합 전략 태스크 수정
    final_task = Task(
            description=f"""
        모든 분석 결과를 통합하여 포괄적인 전략 보고서를 작성하세요.
        
        요구사항:
        1. Executive Summary (경영진 요약)
            - 핵심 전략 방향 (3-5개)
            - 주요 실행 계획 (단기/중기/장기)
            - 기대 효과 (정량적/정성적)
            - 투자 대비 수익 예상
        
        2. 시장 및 환경 분석
            - 산업 동향 및 시장 기회
            - 경쟁 환경 분석 (주요 경쟁사 3-5개)
            - 고객 세그먼트 및 니즈 분석
            - PESTEL 요약 (정치/경제/사회/기술/환경/법률)
        
        3. 3C 심층 분석
            - Customer (고객): 세그먼트별 상세 분석, 구매 여정, 페인 포인트
            - Competitor (경쟁사): 강점/약점, 시장 점유율, 차별화 전략
            - Company (자사): 핵심 역량, 개선 필요 영역, 경쟁 우위 요소
        
        4. 전략 프레임워크 통합 분석
            - 선택된 각 프레임워크의 핵심 시사점
            - 프레임워크 간 연계성 및 통합적 인사이트
            - 전략적 우선순위 도출
        
        5. 사업 전략 (Business Strategy)
            - 비전 및 미션 재정립
            - 사업 모델 혁신 방안
            - 가치 제안 (Value Proposition) 강화
            - 수익 모델 다변화
            - 파트너십 및 협업 전략
        
        6. 마케팅 전략 (Marketing Strategy)
            - 브랜드 포지셔닝 및 메시지
            - 채널 전략 (온/오프라인)
            - 콘텐츠 및 커뮤니케이션 전략
            - 고객 경험 설계
            - 마케팅 KPI 및 측정 방안
        
        7. 영업 전략 (Sales Strategy)
            - 영업 채널 최적화
            - 가격 전략 및 정책
            - 영업 프로세스 개선
            - 고객 관계 관리 (CRM) 전략
            - 영업 인력 역량 강화
        
        8. 운영 전략 (Operations Strategy)
            - 공급망 최적화
            - 품질 관리 체계
            - 프로세스 효율화
            - 기술 인프라 구축
            - 지속가능성 통합
        
        9. 상세 실행 계획 (Action Plan)
            - 단기 전략 (0-6개월): 구체적 실행 항목, 담당자, 예산, 일정
            - 중기 전략 (6-18개월): 주요 이니셔티브, 필요 자원, 기대 성과
            - 장기 전략 (18개월 이상): 전략적 방향성, 투자 계획, 성장 로드맵
        
        10. 재무 계획 및 투자 전략
            - 예상 손익 계산서 (3-5년)
            - 투자 계획 및 자금 조달
            - 손익분기점 분석
            - 재무적 리스크 관리
        
        11. 리스크 관리 및 대응 계획
            - 주요 리스크 요인 식별 (내부/외부)
            - 리스크별 영향도 및 발생 가능성 평가
            - 구체적 대응 전략 및 비상 계획
            - 모니터링 체계 및 조기 경보 시스템
        
        12. 성과 측정 및 평가 체계
            - 핵심 성과 지표 (KPI) 설정
            - 모니터링 및 보고 체계
            - 피드백 루프 및 개선 프로세스
            - 성과 인센티브 연계 방안
        
        13. 결론 및 제언
            - 핵심 성공 요인 (CSF)
            - 우선적 실행 과제
            - 경영진을 위한 권고사항
            - 기대 효과 종합
        """,
        expected_output="""
        # 사업 전략 보고서 최종본
        
        ## Executive Summary
        (핵심 내용 1-2페이지 요약 - 경영진이 빠르게 이해할 수 있도록 작성)
        
        ## 1. 시장 및 환경 분석
        ### 산업 동향 및 시장 기회
        - (주요 트렌드 및 기회 요인 5개 이상)
        
        ### 경쟁 환경 분석
        - (주요 경쟁사별 상세 분석)
        
        ### 고객 세그먼트 및 니즈
        - (세그먼트별 특성 및 니즈 분석)
        
        ### PESTEL 요약
        - (각 요소별 핵심 영향 요인)
        
        ## 2. 3C 심층 분석
        ### Customer (고객)
        - (세그먼트별 상세 분석)
        - (구매 여정 및 의사결정 요인)
        - (페인 포인트 및 기회 영역)
        
        ### Competitor (경쟁사)
        - (주요 경쟁사별 강점/약점)
        - (시장 점유율 및 포지셔닝)
        - (경쟁사 전략 및 대응 방안)
        
        ### Company (자사)
        - (핵심 역량 및 자원)
        - (개선 필요 영역)
        - (차별화 요소 및 경쟁 우위)
        
        ## 3. 전략 프레임워크 통합 분석
        (각 프레임워크별 핵심 시사점 및 통합적 인사이트)
        
        ## 4. 사업 전략 (Business Strategy)
        ### 비전 및 미션
        - (재정립된 비전/미션 제안)
        
        ### 사업 모델 혁신
        - (혁신 방안 3-5개)
        
        ### 가치 제안 강화
        - (강화된 가치 제안 내용)
        
        ### 수익 모델 다변화
        - (신규/개선된 수익 모델 제안)
        
        ### 파트너십 및 협업 전략
        - (주요 파트너십 대상 및 협업 방안)
        
        ## 5. 마케팅 전략 (Marketing Strategy)
        ### 브랜드 포지셔닝 및 메시지
        - (명확한 포지셔닝 제안)
        - (핵심 메시지 및 가치)
        
        ### 채널 전략
        - (온/오프라인 채널별 접근 방안)
        
        ### 콘텐츠 및 커뮤니케이션 전략
        - (주요 콘텐츠 유형 및 테마)
        - (커뮤니케이션 채널별 전략)
        
        ### 고객 경험 설계
        - (고객 여정별 경험 개선 방안)
        
        ### 마케팅 KPI 및 측정
        - (주요 KPI 및 목표치)
        
        ## 6. 영업 전략 (Sales Strategy)
        ### 영업 채널 최적화
        - (채널별 전략 및 리소스 배분)
        
        ### 가격 전략 및 정책
        - (가격 구조 및 정책 제안)
        
        ### 영업 프로세스 개선
        - (프로세스 개선 방안)
        
        ### 고객 관계 관리
        - (CRM 전략 및 실행 방안)
        
        ### 영업 인력 역량 강화
        - (교육 및 개발 프로그램)
        
        ## 7. 운영 전략 (Operations Strategy)
        ### 공급망 최적화
        - (공급망 개선 방안)
        
        ### 품질 관리 체계
        - (품질 관리 프로세스 및 기준)
        
        ### 프로세스 효율화
        - (주요 프로세스 개선 방안)
        
        ### 기술 인프라 구축
        - (필요 기술 및 시스템)
        
        ### 지속가능성 통합
        - (지속가능성 실행 방안)
        
        ## 8. 상세 실행 계획
        ### 단기 전략 (0-6개월)
        - (구체적 실행 항목, 담당자, 예산, 일정)
        
        ### 중기 전략 (6-18개월)
        - (주요 이니셔티브, 필요 자원, 기대 성과)
        
        ### 장기 전략 (18개월 이상)
        - (전략적 방향성, 투자 계획, 성장 로드맵)
        
        ## 9. 재무 계획 및 투자 전략
        ### 예상 손익 계산서
        - (3-5년 재무 예측)
        
        ### 투자 계획 및 자금 조달
        - (필요 투자금 및 조달 방안)
        
        ### 손익분기점 분석
        - (손익분기점 및 달성 시점)
        
        ### 재무적 리스크 관리
        - (재무 리스크 및 대응 방안)
        
        ## 10. 리스크 관리 및 대응 계획
        ### 주요 리스크 요인
        - (내부/외부 리스크 식별)
        
        ### 리스크 평가
        - (영향도 및 발생 가능성 평가)
        
        ### 대응 전략
        - (리스크별 구체적 대응 방안)
        
        ### 모니터링 체계
        - (조기 경보 시스템 및 대응 프로세스)
        
        ## 11. 성과 측정 및 평가 체계
        ### 핵심 성과 지표 (KPI)
        - (영역별 KPI 및 목표치)
        
        ### 모니터링 및 보고 체계
        - (성과 측정 및 보고 프로세스)
        
        ### 피드백 및 개선 프로세스
        - (지속적 개선을 위한 체계)
        
        ## 12. 결론 및 제언
        ### 핵심 성공 요인 (CSF)
        - (5-7개의 핵심 성공 요인)
        
        ### 우선적 실행 과제
        - (즉시 착수해야 할 3-5개 과제)
        
        ### 경영진을 위한 권고사항
        - (주요 의사결정 및 지원 사항)
        
        ### 기대 효과 종합
        - (정량적/정성적 기대 효과)
        """,
        agent=agents[0],
        context=tasks
    )
    tasks.append(final_task)
    
    if debug_mode:
        st.write("✅ 모든 태스크 생성 완료")
    
    return tasks

if __name__ == "__main__":
    main() 