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
from langchain.tools import Tool, DuckDuckGoSearchRun, BaseTool
from langchain.utilities import GoogleSerperAPIWrapper
from langchain.tools import WikipediaQueryRun
from langchain.utilities import WikipediaAPIWrapper
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from typing import Any, Optional

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

def create_strategic_tasks(agents, summary_content, application_content, keyword, selected_frameworks, llm, debug_mode=False):
    """전략 수립을 위한 태스크 생성"""
    tasks = []
    
    if debug_mode:
        st.write("### 태스크 생성 시작")

    # 1. 초기 통합 분석 태스크
    initial_analysis = Task(
        description=f"""
        '{keyword}' 관점에서 요약 내용을 분석하여 전략적 시사점을 도출하세요.
        
        분석 요구사항:
        1. 핵심 개념과 원칙 정리
        2. 현재 상황 분석
           - 시장 환경
           - 경쟁 상황
           - 내부 역량
        3. 주요 기회와 위험 요인
        4. 전략적 시사점
        
        [요약 내용]
        {summary_content}
        
        [기존 적용 내용]
        {application_content}
        
        결과물 포함 사항:
        1. 상세한 현황 분석
        2. 구체적인 데이터와 근거
        3. 실행 가능한 전략 방향
        """,
        expected_output="초기 분석 보고서",
        agent=agents[0]
    )
    tasks.append(initial_analysis)

    # 2. 프레임워크별 분석 태스크
    for i, framework in enumerate(selected_frameworks):
        framework_task = Task(
            description=f"""
            {framework}를 사용하여 '{keyword}' 관련 전략을 수립하세요.
            
            요구사항:
            1. {framework} 각 요소별 상세 분석
            2. 구체적인 실행 계획 수립
               - 단기(0-6개월)
               - 중기(6-18개월)
               - 장기(18개월 이상)
            3. 필요 자원과 예산 추정
            4. 성과 측정 지표(KPI) 설정
            5. 리스크 관리 방안
            
            이전 분석 결과:
            {initial_analysis.description}
            """,
            expected_output=f"{framework} 기반 전략 보고서",
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
            {agent.role}의 관점에서 전략을 분석하고 구체적인 실행 계획을 수립하세요.
            
            포함해야 할 내용:
            1. 전문 분야별 상세 분석
            2. 구체적인 실행 방안
               - 세부 액션 아이템
               - 일정 계획
               - 필요 자원
               - 예상 비용
            3. 성과 지표와 목표
            4. 위험 요소와 대응 방안
            5. 조직 및 프로세스 설계
            
            기존 분석 내용을 참고하여 통합적인 관점에서 검토하세요.
            """,
            expected_output=f"{agent.role} 전문 분석 보고서",
            agent=agent,
            context=[initial_analysis] + tasks[1:i+1]
        )
        expert_tasks.append(expert_task)
        tasks.append(expert_task)

    # 코디네이터 에이전트 수정
    coordinator = Agent(
        role="전략 코디네이터",
        goal="다양한 전문가의 분석을 통합하여 포괄적인 전략 보고서 작성",
        backstory="""
        당신은 수석 전략 컨설턴트로서 다양한 전문가들의 분석을 종합하여 
        실행 가능한 통합 전략을 수립하는 전문가입니다.
        각 분야 전문가들의 의견을 조율하고 일관된 전략으로 통합하는 것이 주요 역할입니다.
        """,
        verbose=debug_mode,
        llm=llm
    )

    # 최종 통합 태스크 추가
    final_integration_task = Task(
        description=f"""
        모든 전문가의 분석 결과를 검토하고 통합하여 최종 전략 보고서를 작성하세요.
        
        통합 보고서에 반드시 포함해야 할 내용:
        
        1. 전략 개요
           - 핵심 목표와 방향성
           - 주요 전략적 시사점
        
        2. 세부 영역별 전략
           - 마케팅 및 세일즈 전략
           - 운영 및 프로세스 전략
           - 조직 및 인적 자원 전략
           - 재무 및 투자 전략
        
        3. 실행 계획
           - 단기/중기/장기 목표와 마일스톤
           - 세부 액션 플랜
           - 필요 자원 및 예산
        
        4. 리스크 관리
           - 주요 리스크 요인
           - 대응 전략
           - 모니터링 계획
        
        각 전문가의 분석을 상호 연계하여 일관성 있는 전략을 도출하세요.
        모든 제안은 구체적이고 실행 가능해야 합니다.
        """,
        expected_output="통합 전략 보고서",
        agent=coordinator,
        context=tasks  # 모든 이전 태스크의 결과를 컨텍스트로 제공
    )

    # tasks 리스트에 최종 통합 태스크 추가
    tasks.append(final_integration_task)

    return tasks

# 공통 도구
search = DuckDuckGoSearchRun()
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
finance_news = YahooFinanceNewsTool()

# 에이전트별 특화 도구 정의
def create_agent_tools():
    """에이전트별 도구 생성"""
    def market_research(query: str) -> str:
        return f"시장 조사 결과: {query}에 대한 분석"
        
    def industry_analysis(query: str) -> str:
        return f"산업 분석 결과: {query}에 대한 분석"
        
    def financial_analysis(query: str) -> str:
        return f"재무 분석 결과: {query}에 대한 분석"
        
    def competitor_analysis(query: str) -> str:
        return f"경쟁사 분석 결과: {query}에 대한 분석"

    tools = {
        "시장 분석가": [
            {
                "name": "market_research",
                "description": "시장 동향, 경쟁사, 산업 트렌드 등을 조사합니다.",
                "function": market_research
            },
            {
                "name": "industry_analysis",
                "description": "산업 구조와 동향을 분석합니다.",
                "function": industry_analysis
            }
        ],
        "재무 전략가": [
            {
                "name": "financial_analysis",
                "description": "재무 지표와 성과를 분석합니다.",
                "function": financial_analysis
            }
        ],
        "마케팅 전략가": [
            {
                "name": "market_research",
                "description": "시장 규모와 성장성을 분석합니다.",
                "function": market_research
            },
            {
                "name": "competitor_analysis",
                "description": "주요 경쟁사의 전략을 분석합니다.",
                "function": competitor_analysis
            }
        ]
    }
    
    return tools

# 에이전트 생성 시 도구 추가
agent_tools = create_agent_tools()

def get_application_list(debug_mode=False):
    """DB에서 적용 사례 목록 가져오기"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            id,
            file_name,
            content,
            created_at
        FROM 
            reading_materials
        WHERE 
            type = 'application'
        ORDER BY 
            created_at DESC
        """
        
        cursor.execute(query)
        applications = cursor.fetchall()
        
        if debug_mode:
            st.write(f"가져온 적용 사례 수: {len(applications)}")
        
        return applications
        
    except Exception as e:
        st.error(f"적용 사례를 불러오는 중 오류가 발생했습니다: {str(e)}")
        if debug_mode:
            st.exception(e)
        return []
        
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    st.title("📚 독서 전략 생성기 (CrewAI)")
    
    # 비용 최적화 옵션
    st.sidebar.header("⚙️ 실행 설정")
    cost_effective = st.sidebar.checkbox(
        "비용 최적화 모드",
        help="활성화하면 더 경제적인 모델을 사용하고 에이전트 수를 최적화합니다.",
        value=True
    )
    
    # 디버그 모드 설정
    debug_mode = st.sidebar.checkbox(
        "디버그 모드",
        help="에이전트와 태스크의 실행 과정을 자세히 표시합니다.",
        value=False
    )
    st.session_state.debug_mode = debug_mode

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
            # 에이전트 선택 UI
            st.subheader("활성화할 에이전트")
            col1, col2, col3 = st.columns(3)
            
            selected_agents = {}
            with col1:
                selected_agents["market"] = st.checkbox("시장 분석 에이전트", value=True)
                selected_agents["customer"] = st.checkbox("고객 인사이트 에이전트", value=True)
                selected_agents["financial"] = st.checkbox("재무 분석 에이전트", value=True)
            
            with col2:
                selected_agents["operations"] = st.checkbox("운영 최적화 에이전트", value=True)
                selected_agents["marketing"] = st.checkbox("마케팅 전략 에이전트", value=True)
                selected_agents["risk"] = st.checkbox("리스크 관리 에이전트", value=True)
            
            with col3:
                selected_agents["tech"] = st.checkbox("기술/IT 전략 에이전트", value=True)
                selected_agents["legal"] = st.checkbox("법률/규제 준수 에이전트", value=True)
                selected_agents["sustainability"] = st.checkbox("지속가능성 전략 에이전트", value=True)

            # 전략 프레임워크 선택
            st.subheader("전략 프레임워크 선택")
            col1, col2 = st.columns(2)
            
            selected_frameworks = []
            with col1:
                if st.checkbox("블루오션 전략"): selected_frameworks.append("블루오션 전략")
                if st.checkbox("SWOT 분석"): selected_frameworks.append("SWOT 분석")
                if st.checkbox("비즈니스 모델 캔버스"): selected_frameworks.append("비즈니스 모델 캔버스")
                if st.checkbox("제약이론"): selected_frameworks.append("제약이론")
            
            with col2:
                if st.checkbox("마이클 포터의 경쟁전략"): selected_frameworks.append("마이클 포터의 경쟁전략")
                if st.checkbox("VRIO 프레임워크"): selected_frameworks.append("VRIO 프레임워크")
                if st.checkbox("린 스타트업"): selected_frameworks.append("린 스타트업")
                if st.checkbox("디스럽티브 이노베이션"): selected_frameworks.append("디스럽티브 이노베이션")

            if not selected_frameworks:
                st.info("AI가 자동으로 적합한 프레임워크를 선정합니다.")

    # 메인 인터페이스
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("요약 파일 업로드")
        book_title = st.text_input("책 제목", value="퍼스널 MBA")
        summary_file = st.file_uploader("독서토론 요약 파일", type=['md', 'txt'])
        
        if summary_file:
            summary_content = summary_file.read().decode('utf-8')
            st.text_area("요약 내용 미리보기", summary_content[:500] + "...", height=200)
    
    with col2:
        st.header("적용 파일 선택")
        
        # DB에서 적용 사례 목록 가져오기
        applications = get_application_list(debug_mode)
        
        if applications:
            # 선택 옵션 생성 (file_name 사용)
            application_options = ["선택하지 않음"] + [
                f"{app['file_name']} ({app['created_at'].strftime('%Y-%m-%d')})"
                for app in applications
            ]
            
            # 적용 파일 선택
            selected_application = st.selectbox(
                "기존 적용 사례",
                application_options,
                help="이전에 작성된 적용 사례를 선택하면 해당 내용을 참고하여 전략을 생성합니다."
            )
            
            # 선택된 적용 사례의 내용 표시
            if selected_application != "선택하지 않음":
                selected_idx = application_options.index(selected_application) - 1
                application_content = applications[selected_idx]['content']
                st.text_area(
                    "적용 내용 미리보기", 
                    application_content[:500] + "..." if len(application_content) > 500 else application_content,
                    height=200
                )
        else:
            st.info("등록된 적용 사례가 없습니다.")
            application_content = ""

        # 분석 키워드 선택
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords)
        
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력")
        else:
            analysis_keyword = selected_keyword

    # 전략 생성 버튼
    if st.button("🤖 AI 전략 생성", type="primary"):
        if not summary_file:
            st.error("요약 파일을 업로드해주세요.")
            return
            
        with st.spinner("AI 에이전트들이 전략을 생성하고 있습니다..."):
            try:
                # LLM 설정
                llm = ChatOpenAI(
                    api_key=OPENAI_API_KEY,
                    model=model_name,
                    temperature=0.7
                )
                
                # 활성화된 에이전트만 필터링
                active_agents = [key for key, value in selected_agents.items() if value]
                
                if debug_mode:
                    st.write("### 🤖 에이전트 생성 시작")
                    st.write(f"활성화된 에이전트: {active_agents}")
                    st.write(f"선택된 프레임워크: {selected_frameworks}")
                
                # 에이전트 생성
                agents = []
                
                # 프레임워크 전문가 에이전트 생성
                framework_experts = {
                    "SWOT 분석": "SWOT 분석을 통한 전략 수립 전문가",
                    "블루오션 전략": "블루오션 전략 수립 전문가",
                    "포터의 5가지 힘": "산업 구조 분석 전문가",
                    "비즈니스 모델 캔버스": "비즈니스 모델 혁신 전문가",
                    "마케팅 믹스(4P)": "마케팅 전략 전문가",
                    "STP 전략": "시장 세분화 전문가"
                }

                # 선택된 프레임워크별 전문가 에이전트 생성
                for framework in selected_frameworks:
                    if framework in framework_experts:
                        agent = Agent(
                            role=f"{framework} 전문가",
                            goal=f"{framework}를 활용한 심층 분석 및 전략 제안",
                            backstory=f"당신은 {framework_experts[framework]}입니다. 해당 프레임워크를 활용한 수많은 프로젝트 경험이 있습니다.",
                            verbose=debug_mode,
                            llm=llm
                        )
                        agents.append(agent)
                        if debug_mode:
                            st.write(f"✅ {framework} 전문가 에이전트 생성 완료")

                # 기능별 전문가 에이전트 생성
                functional_experts = {
                    "market": ("시장 분석가", "시장 동향과 경쟁 환경 분석"),
                    "customer": ("고객 인사이트 전문가", "고객 니즈와 행동 분석"),
                    "financial": ("재무 전략가", "재무적 실행 가능성과 수익성 분석"),
                    "marketing": ("마케팅 전략가", "마케팅 및 브랜드 전략 수립"),
                    "operations": ("운영 최적화 전문가", "프로세스와 운영 효율성 분석"),
                    "risk": ("리스크 관리 전문가", "리스크 식별 및 대응 전략 수립")
                }

                # 선택된 기능별 전문가 에이전트 생성
                for agent_key in active_agents:
                    if agent_key in functional_experts:
                        role, goal = functional_experts[agent_key]
                        
                        agent = Agent(
                            role=role,
                            goal=goal,
                            backstory=f"당신은 {role}로서 해당 분야의 전문성과 실무 경험을 보유하고 있습니다.",
                            verbose=debug_mode,
                            llm=llm
                        )
                        agents.append(agent)
                        if debug_mode:
                            st.write(f"✅ {role} 에이전트 생성 완료")

                # 코디네이터 에이전트 (항상 포함)
                coordinator = Agent(
                    role="전략 코디네이터",
                    goal="다양한 전문가의 분석을 통합하여 포괄적인 전략 보고서 작성",
                    backstory="""
                    당신은 수석 전략 컨설턴트로서 다양한 전문가들의 분석을 종합하여 
                    실행 가능한 통합 전략을 수립하는 전문가입니다.
                    각 분야 전문가들의 의견을 조율하고 일관된 전략으로 통합하는 것이 주요 역할입니다.
                    """,
                    verbose=debug_mode,
                    llm=llm
                )
                agents.insert(0, coordinator)  # 코디네이터를 첫 번째 위치에 추가

                # 태스크 생성 및 실행
                tasks = create_strategic_tasks(
                    agents=agents,
                    summary_content=summary_content,
                    application_content=application_content,
                    keyword=analysis_keyword,
                    selected_frameworks=selected_frameworks,
                    llm=llm,
                    debug_mode=debug_mode
                )
                
                # Crew 생성 및 실행
                crew = Crew(
                    agents=agents,
                    tasks=tasks,
                    verbose=debug_mode,
                    process=Process.sequential
                )
                
                # 결과 생성 및 처리
                result = crew.kickoff()
                
                # 각 태스크의 결과를 저장할 딕셔너리
                task_results = {}
                
                # 모든 태스크의 결과 수집
                for task in tasks:
                    if hasattr(task, 'output'):
                        task_results[task.agent.role] = task.output
                
                # 최종 통합 결과
                final_result = result.raw_output if hasattr(result, 'raw_output') else str(result)
                
                # 보고서 구조화
                report_content = f"""# {book_title} - 전략 분석 보고서

## 📋 기본 정보
- 분석 키워드: {analysis_keyword}
- 적용 프레임워크: {', '.join(selected_frameworks)}
- 작성일: {datetime.now().strftime('%Y-%m-%d')}

## 📊 통합 전략 요약
{final_result}

## 📊 프레임워크별 분석 결과
"""

                # 프레임워크 전문가 결과 추가
                for framework in selected_frameworks:
                    expert_role = f"{framework} 전문가"
                    if expert_role in task_results:
                        report_content += f"""
### {framework} 분석
{task_results[expert_role]}
"""

                # 기능별 전문가 분석 결과 추가
                report_content += "\n## 🎯 전문가별 세부 분석\n"
                
                expert_categories = {
                    "시장 분석가": "시장 분석",
                    "고객 인사이트 전문가": "고객 분석",
                    "재무 전략가": "재무 전략",
                    "마케팅 전략가": "마케팅 전략",
                    "운영 최적화 전문가": "운영 전략",
                    "리스크 관리 전문가": "리스크 관리"
                }
                
                for role, category in expert_categories.items():
                    if role in task_results:
                        report_content += f"""
### {category}
{task_results[role]}
"""

                # 실행 계획 및 기타 섹션 추가
                report_content += """
## 📈 통합 실행 계획
### 단기 전략 (0-6개월)
- 즉시 실행 가능한 액션 아이템
- 필요 자원 및 예산
- 기대 효과

### 중기 전략 (6-18개월)
- 주요 전략 과제
- 조직 및 프로세스 개선
- 성과 지표

### 장기 전략 (18개월 이상)
- 비전 및 장기 목표
- 핵심 성공 요인
- 투자 계획
"""
                
                # 결과 표시
                st.success("전략 생성이 완료되었습니다!")
                
                # 탭으로 결과 구분하여 표시
                tab1, tab2, tab3 = st.tabs(["핵심 요약", "📊 프레임워크별 분석", "📑 전체 보고서"])
                
                with tab1:
                    st.markdown("### 핵심 전략 요약")
                    st.markdown(final_result[:1500] + "...")
                
                with tab2:
                    # 프레임워크별 분석 결과
                    st.markdown("### 프레임워크 분석 결과")
                    for framework in selected_frameworks:
                        expert_role = f"{framework} 전문가"
                        if expert_role in task_results:
                            with st.expander(f"{framework} 분석"):
                                st.markdown(task_results[expert_role])
                    
                    # 전문가별 분석 결과
                    st.markdown("### 전문가별 분석 결과")
                    for role, category in expert_categories.items():
                        if role in task_results:
                            with st.expander(category):
                                st.markdown(task_results[role])
                
                with tab3:
                    st.markdown(report_content)
                
                # 결과 다운로드
                st.download_button(
                    label="전략 보고서 다운로드",
                    data=report_content,
                    file_name=f"{book_title}_전략분석.md",
                    mime="text/markdown"
                )

            except Exception as e:
                st.error(f"전략 생성 중 오류가 발생했습니다: {str(e)}")
                if debug_mode:
                    st.exception(e)

if __name__ == "__main__":
    main() 