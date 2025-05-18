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
    st.title("📚 독서 적용 파일 생성기 (CrewAI)")
    
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
    
    # 적용 파일 생성 UI (경영 프레임워크 선택 부분 제거)
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
        applications = get_application_list(debug_mode)
        if applications:
            application_options = ["선택하지 않음"] + [
                f"{app['file_name']} ({app['created_at'].strftime('%Y-%m-%d')})"
                for app in applications
            ]
            selected_application = st.selectbox(
                "기존 적용 사례",
                application_options,
                help="이전에 작성된 적용 사례를 선택하면 해당 내용을 참고하여 새로운 적용 파일을 생성합니다."
            )
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

        # 분석 키워드 선택 (프레임워크 대신 관점만 선택)
        keywords = ["가치 창조", "마케팅", "세일즈", "가치 전달", "재무", "기타"]
        selected_keyword = st.selectbox("분석 키워드", keywords)
        if selected_keyword == "기타":
            analysis_keyword = st.text_input("키워드 직접 입력")
        else:
            analysis_keyword = selected_keyword

    # 적용 파일 생성 버튼
    if st.button("🤖 적용 파일 생성", type="primary"):
        if not summary_file:
            st.error("요약 파일을 업로드해주세요.")
            return
        with st.spinner("AI가 적용 파일을 생성하고 있습니다..."):
            try:
                llm = ChatOpenAI(
                    api_key=OPENAI_API_KEY,
                    model=MODEL_NAME,
                    temperature=0.7
                )
                # 프롬프트 구성: 요약 내용과 기존 적용 파일을 통합/개선
                prompt = f'''
                아래의 "요약 내용"과 "기존 적용 파일"을 참고하여,
                기존 적용 파일을 개선/보완한 새로운 적용 파일을 작성해 주세요.
                - 요약 내용의 핵심 인사이트와 지침을 반드시 반영해 주세요.
                - 기존 적용 파일의 구조와 맥락을 최대한 유지하되, 중복은 피하고 자연스럽게 통합해 주세요.
                - 존댓말을 사용해 주세요.

                [요약 내용]
                {summary_content}

                [기존 적용 파일]
                {application_content}
                '''
                response = llm.invoke(prompt)
                final_result = response.content if hasattr(response, 'content') else str(response)

                report_content = f"""# {book_title} - 적용 파일 생성 보고서

## 📋 기본 정보
- 분석 키워드: {analysis_keyword}
- 작성일: {datetime.now().strftime('%Y-%m-%d')}

## 📊 적용 파일 요약
{final_result}

## 📑 전체 적용 파일
{final_result}
"""
                st.success("적용 파일 생성이 완료되었습니다!")
                st.markdown(report_content)
                st.download_button(
                    label="적용 파일 다운로드",
                    data=report_content,
                    file_name=f"{book_title}_적용파일.md",
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"적용 파일 생성 중 오류가 발생했습니다: {str(e)}")
                if debug_mode:
                    st.exception(e)

if __name__ == "__main__":
    main() 