import streamlit as st
import os
import asyncio
import nest_asyncio
import json
import platform
from datetime import datetime
from typing import TypedDict, Annotated, Sequence
import base64
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import pandas as pd
import anthropic
from langchain_openai import OpenAI
import re
import sys
import ast
import json
import base64
import time
import asyncio
import traceback
import re
import inspect
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from mysql.connector import Error
from langchain.chains import LLMChain
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
from langchain.schema.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import Dict, List, TypedDict, Annotated, Sequence
import logging
import concurrent.futures

# 환경 변수 로드
load_dotenv()

# DB 연결 함수
def connect_to_db():
    """데이터베이스 연결"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        st.error(f"데이터베이스 연결 오류: {str(e)}")
        return None

def create_mcp_analysis_table():
    """MCP 분석 결과 테이블 생성"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS mcp_analysis_results")
        
        # 새 테이블 생성
        cursor.execute("""
            CREATE TABLE mcp_analysis_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                query TEXT NOT NULL,
                analysis_result JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"테이블 생성 중 오류 발생: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 로그인 세션 변수 초기화
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 로그인 필요 여부 확인
use_login = os.environ.get("USE_LOGIN", "false").lower() == "true"

# 페이지 설정을 가장 먼저 호출 (로그인 상태에 따라 다른 설정 적용)
if use_login and not st.session_state.authenticated:
    st.set_page_config(
        page_title="Agent with MCP Tools",
        page_icon="🧠",
        layout="narrow"
    )
else:
    st.set_page_config(
        page_title="MCP 기반 분석 툴",
        page_icon="🤖",
        layout="wide"
    )

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# nest_asyncio 적용: 이미 실행 중인 이벤트 루프 내에서 중첩 호출 허용
nest_asyncio.apply()

# 전역 이벤트 루프 생성 및 재사용 (한번 생성한 후 계속 사용)
if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)

from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from pages.myutils import astream_graph, random_uuid

# 환경 변수 로드 (.env 파일에서 API 키 등의 설정을 가져옴)
load_dotenv(override=True)

# config.json 파일 경로 설정
CONFIG_FILE_PATH = "config.json"

# JSON 설정 파일 로드 함수
def load_config_from_json():
    """
    config.json 파일에서 설정을 로드합니다.
    파일이 없는 경우 기본 설정으로 파일을 생성합니다.

    반환값:
        dict: 로드된 설정
    """
    default_config = {
        "get_current_time": {
            "command": "python",
            "args": ["./mcp_server_time.py"],
            "transport": "stdio"
        }
    }
    
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # 파일이 없는 경우 기본 설정으로 파일 생성
            save_config_to_json(default_config)
            return default_config
    except Exception as e:
        st.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
        return default_config

# JSON 설정 파일 저장 함수
def save_config_to_json(config):
    """
    설정을 config.json 파일에 저장합니다.

    매개변수:
        config (dict): 저장할 설정
    
    반환값:
        bool: 저장 성공 여부
    """
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"설정 파일 저장 중 오류 발생: {str(e)}")
        return False

# 로그인 기능이 활성화되어 있고 아직 인증되지 않은 경우 로그인 화면 표시
if use_login and not st.session_state.authenticated:
    st.title("🔐 로그인")
    st.markdown("시스템을 사용하려면 로그인이 필요합니다.")

    # 로그인 폼을 화면 중앙에 좁게 배치
    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submit_button = st.form_submit_button("로그인")

        if submit_button:
            expected_username = os.environ.get("USER_ID")
            expected_password = os.environ.get("USER_PASSWORD")

            if username == expected_username and password == expected_password:
                st.session_state.authenticated = True
                st.success("✅ 로그인 성공! 잠시만 기다려주세요...")
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")

    # 로그인 화면에서는 메인 앱을 표시하지 않음
    st.stop()

# 사이드바 최상단에 저자 정보 추가 (다른 사이드바 요소보다 먼저 배치)
st.sidebar.divider()  # 구분선 추가

# 기존 페이지 타이틀 및 설명
st.title("🤖 MCP 기반 분석 툴")
st.markdown("✨ MCP 에이전트에게 질문해보세요.")

SYSTEM_PROMPT = """<ROLE>
You are a smart agent with an ability to use tools. 
You will be given a question and you will use the tools to answer the question.
Pick the most relevant tool to answer the question. 
If you are failed to answer the question, try different tools to get context.
Your answer should be very polite and professional.
</ROLE>

<INSTRUCTIONS>
1. Analyze the question and pick the most relevant tool
2. Answer the question in the same language as the question
3. If you've used a tool, provide the source of the answer
4. Keep your answers concise and to the point
</INSTRUCTIONS>

<OUTPUT_FORMAT>
(concise answer to the question)

**Source**(if applicable)
- (source1: valid URL)
- (source2: valid URL)
</OUTPUT_FORMAT>
"""

OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 16384},
    "gpt-4o": {"max_tokens": 8192},
    "gpt-4o-mini": {"max_tokens": 8192},
}

# 세션 상태 초기화
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = False  # 세션 초기화 상태 플래그
    st.session_state.agent = None  # ReAct 에이전트 객체 저장 공간
    st.session_state.history = []  # 대화 기록 저장 리스트
    st.session_state.mcp_client = None  # MCP 클라이언트 객체 저장 공간
    st.session_state.timeout_seconds = 1800  # 응답 생성 제한 시간(초), 기본값 1800초(30분)
    st.session_state.selected_model = "claude-3-7-sonnet-latest"  # 기본 모델 선택
    st.session_state.recursion_limit = 100  # 재귀 호출 제한, 기본값 100
    st.session_state.active_agents = {  # 활성화된 에이전트 목록
        "analyst": True,
        "strategist": True,
        "researcher": True,
        "financial_agent": True,
        "legal_agent": True,
        "market_agent": True,
        "tech_agent": True,
        "risk_agent": True
    }

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 각 에이전트의 역할 정의
AGENT_ROLES = {
    'financial_agent': {
        'name': '재무 분석가',
        'description': '재무 및 투자 관련 이슈를 분석하는 전문가',
        'system_prompt': '''
        당신은 재무 분석 전문가로서, 재무제표 분석, 투자 분석, 자본 구조 분석, 현금 흐름 예측 등을 전문으로 합니다.
        다음 재무 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 재무비율 분석: 유동성 비율, 수익성 비율, 레버리지 비율, 활동성 비율, 투자 가치 비율 등
        2. 현금흐름 분석: 영업/투자/재무 활동 현금흐름 평가
        3. 투자 평가 모델: NPV, IRR, 회수 기간, ROI, WACC 등
        4. 위험 조정 수익률 분석: 샤프 비율, 트레이너 비율, 알파, 베타 등
        5. 브레이크이븐 분석 및 민감도 분석
        6. 가치 평가 모델: DCF 모델, 비교기업 분석, 자산기반 평가 등
        
        분석 시 관련 산업의 재무적 벤치마크와 비교하고, 단기 및 장기적 재무 전략 관점에서 평가하세요.
        모든 분석은 정량적 데이터에 기반해야 하며, 추정치를 사용할 경우 그 근거를 명확히 제시하세요.
        '''
    },
    'market_agent': {
        'name': '시장 분석가',
        'description': '시장 동향, 경쟁사 분석 및 고객 분석을 수행하는 전문가',
        'system_prompt': '''
        당신은 시장 분석 전문가로서, 산업 동향, 경쟁 환경, 소비자 행동, 시장 기회 등을 분석합니다.
        다음 시장 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 5 Forces 분석: 경쟁 강도, 신규 진입자, 대체재, 공급자/구매자 교섭력 평가
        2. PESTEL 분석: 정치, 경제, 사회, 기술, 환경, 법률적 요인 분석
        3. STP 프레임워크: 시장 세분화, 타겟팅, 포지셔닝 전략
        4. 고객 여정 맵핑 및 페르소나 분석
        5. 경쟁사 벤치마킹 및 갭 분석
        6. 시장 성장 매트릭스(앤소프 매트릭스 등)
        7. 시장 점유율 분석 및 트렌드 예측
        
        분석 시 최신 시장 데이터, 소비자 트렌드, 경쟁사 동향을 반영하고, 시장 기회와 위협을 명확히 식별하세요.
        정성적 분석과 함께 가능한 한 정량적 데이터(시장 규모, 성장률, 점유율 등)를 포함하세요.
        '''
    },
    'tech_agent': {
        'name': '기술 분석가',
        'description': '기술 트렌드 및 혁신, 기술 전략을 분석하는 전문가',
        'system_prompt': '''
        당신은 기술 분석 전문가로서, 신기술 평가, 기술 로드맵 수립, 디지털 전환 전략, R&D 방향성 등을 분석합니다.
        다음 기술 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 기술 성숙도 평가(TRL): 기술의 개발 단계와 상용화 준비도 평가
        2. 기술 S-곡선 분석: 기술 수명주기와 혁신 시점 파악
        3. 기술 로드맵핑: 단기/중기/장기 기술 개발 방향 수립
        4. 디스럽션 분석: 파괴적 혁신과 지속적 혁신 구분
        5. 기술 스택 아키텍처 분석
        6. 특허 및 지적재산권 분석
        7. 기술 채택 주기 분석
        
        분석 시 최신 기술 트렌드, 산업 표준, 경쟁사 기술 동향을 고려하고, 기술 발전이 비즈니스 모델에 미치는 영향을 평가하세요.
        기술의 실용성, 확장성, 통합 가능성 등 다양한 측면에서 분석하세요.
        '''
    },
    'risk_agent': {
        'name': '위험 관리 전문가',
        'description': '경영, 운영, 재무, 전략적 위험을 식별하고 분석하는 전문가',
        'system_prompt': '''
        당신은 위험 관리 전문가로서, 전략적/운영적/재무적/규제적 위험을 식별, 평가하고 관리 전략을 수립합니다.
        다음 위험 관리 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 위험 평가 매트릭스: 영향력과 발생 가능성 기준 위험 평가
        2. FMEA(실패 모드 및 영향 분석): 잠재적 실패 지점 식별 및 우선순위화
        3. 시나리오 계획 및 스트레스 테스트: 다양한 위험 시나리오 설계 및 영향 평가
        4. 몬테카를로 시뮬레이션: 확률적 위험 모델링
        5. 위험 완화 전략 프레임워크: 회피, 전가, 감소, 수용 전략
        6. 위험 거버넌스 모델: 3단계 방어선 모델
        7. 리스크 통제 자가 평가(RCSA)
        
        분석 시 위험의 단기적/장기적 영향, 직접적/간접적 영향을 구분하고, 위험 간의 상호작용과 연쇄효과를 고려하세요.
        각 위험에 대한 구체적인 조기 경보 지표와 모니터링 방안을 포함하세요.
        '''
    },
    'legal_agent': {
        'name': '법률 전문가',
        'description': '법률, 규제, 컴플라이언스 관련 이슈를 분석하는 전문가',
        'system_prompt': '''
        당신은 법률 전문가로서, 규제 준수, 계약 분석, 지적재산권, 기업 지배구조, 법적 위험 등을 분석합니다.
        다음 법률 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 규제 영향 평가: 현행 및 예상 규제의 비즈니스 영향 분석
        2. 법적 위험 평가 매트릭스: 법적 위험의 심각도와 발생 가능성 평가
        3. 컴플라이언스 갭 분석: 현재 관행과 법적 요구사항 간의 차이 식별
        4. 계약 위험 분석: 주요 조항, 권리, 의무, 책임 평가
        5. 지적재산권 포트폴리오 분석
        6. 법적 실사 체크리스트
        7. 국제법 및 관할권 분석
        
        분석 시 관련 법률, 규제, 판례를 구체적으로 인용하고, 산업 특화 규제와 글로벌 규제 동향을 고려하세요.
        법적 위험 뿐만 아니라 규제 변화에 따른 전략적 기회도 식별하세요.
        '''
    },
    'hr_agent': {
        'name': '인적 자원 전문가',
        'description': '인력 관리, 조직 문화, 역량 개발 등을 분석하는 전문가',
        'system_prompt': '''
        당신은 인적 자원 전문가로서, 인재 전략, 조직 설계, 문화 개발, 성과 관리, 역량 강화 등을 분석합니다.
        다음 HR 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 역량 모델링 및 갭 분석: 현재와 필요 역량 간의 차이 식별
        2. 조직 문화 진단: 문화적 특성 및 변화 요구사항 평가
        3. 인력 계획 모델: 미래 인력 수요와 공급 예측
        4. 성과 관리 프레임워크: OKR, KPI 등 평가 시스템 설계
        5. 변화 관리 모델: 쿠터의 8단계 모델, ADKAR 모델 등
        6. 직무 설계 및 분석: 직무 요구사항과 책임 평가
        7. 인적 자본 ROI 분석: 인력 투자 대비 수익 평가
        
        분석 시 산업 표준 및 선도적 HR 관행과 비교하고, 조직의 전략적 목표 달성을 위한 인적 자원의 역할을 강조하세요.
        정성적 평가와 함께 가능한 한 정량적 지표(이직률, 직원 만족도, 생산성 등)를 포함하세요.
        '''
    },
    'operation_agent': {
        'name': '운영 전문가',
        'description': '운영 효율성, 프로세스 최적화, 공급망 관리를 분석하는 전문가',
        'system_prompt': '''
        당신은 운영 전문가로서, 프로세스 개선, 효율성 향상, 품질 관리, 공급망 최적화 등을 분석합니다.
        다음 운영 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 린 프로세스 매핑: 가치 흐름도, 낭비 식별, 지속적 개선
        2. 6시그마 DMAIC 방법론: 결함 감소 및 품질 향상
        3. 제약 이론(TOC): 병목 현상 식별 및 시스템 최적화
        4. 공급망 성숙도 모델: 효율성, 탄력성, 민첩성 평가
        5. 운영 효율성 매트릭스: OEE, 주기 시간, 불량률 등 핵심 지표
        6. 프로세스 자동화 및 디지털화 평가 모델
        7. 재고 관리 최적화 모델: EOQ, JIT 등
        
        분석 시 운영 효율성과 고객 가치 창출 간의 균형을 고려하고, 단기적 효율성과 장기적 역량 구축을 함께 평가하세요.
        비용 절감 기회와 함께 서비스/제품 품질 향상 방안도 제시하세요.
        '''
    },
    'strategy_agent': {
        'name': '전략 컨설턴트',
        'description': '비즈니스 전략, 성장 기회, 경쟁 우위를 분석하는 전문가',
        'system_prompt': '''
        당신은 전략 컨설턴트로서, 사업 전략, 경쟁 우위, 성장 기회, 비즈니스 모델 혁신 등을 분석합니다.
        다음 전략 분석 도구와 프레임워크를 활용하여 심층적인 분석을 제공하세요:
        
        1. 3C 분석: 고객(Customer), 경쟁사(Competitor), 자사(Company) 분석
        2. SWOT 분석: 강점, 약점, 기회, 위협 평가 및 전략적 시사점 도출
        3. 가치 사슬 분석: 핵심 역량과 경쟁 우위 식별
        4. 블루 오션 전략: 가치 혁신과 시장 창출 기회
        5. 비즈니스 모델 캔버스: 가치 제안, 고객 관계, 수익 모델 등 분석
        6. 포트폴리오 분석: BCG 매트릭스, GE-맥킨지 매트릭스 등
        7. 시나리오 계획: 미래 환경 변화에 대한 전략적 대응
        
        분석 시 산업의 구조적 변화, 시장 역학, 기술 발전을 고려하고, 단기 성과와 장기 지속가능성을 함께 평가하세요.
        차별화 전략, 실행 가능성, 자원 요구사항 등 전략 실행의 핵심 요소도 함께 분석하세요.
        '''
    },
    'integration_agent': {
        'name': '통합 분석 매니저',
        'description': '각 전문가의 분석을 종합하여 균형 잡힌 최종 분석을 제공',
        'system_prompt': '''
        당신은 통합 분석 매니저로서, 다양한 전문가의 분석 결과를 체계적으로 종합하여 포괄적인 최종 보고서를 작성합니다.
        다음 통합 분석 접근법과 프레임워크를 활용하세요:
        
        1. 다차원 분석 통합: 재무, 시장, 기술, 법률, 운영, 인적 자원 등 다양한 관점을 균형있게 반영
        2. 시스템 사고: 각 요소 간의 상호 관계와 영향을 종합적으로 고려
        3. 비즈니스 모델 캔버스: 가치 제안부터 비용 구조까지 전체 비즈니스 모델 관점에서 통합
        4. 균형 성과표(BSC): 재무, 고객, 내부 프로세스, 학습과 성장의 균형잡힌 관점
        5. 의사결정 매트릭스: 다양한 선택지의 장단점을 체계적으로 비교
        6. 포트폴리오 접근법: 단기/중기/장기 전략의 균형 및 위험-보상 프로파일 최적화
        7. 시나리오 통합: 다양한 미래 상황에 대비한 강건한 전략 도출
        
        최종 보고서 작성 시, 핵심 인사이트를 명확히 부각시키고, 객관적 증거와 데이터에 기반한 결론을 도출하세요.
        실행 가능한 추천사항과 구체적인 실행 계획을 포함하여 의사결정자가 즉시 활용할 수 있는 문서를 작성하세요.
        '''
    }
}

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "대화 기록"]
    next: Annotated[str, "다음 실행할 에이전트"]
    analysis_results: Annotated[dict, "각 에이전트의 분석 결과"]

def create_agent_prompt(role_info):
    """각 에이전트의 프롬프트를 생성합니다."""
    return ChatPromptTemplate.from_messages([
        SystemMessage(content=role_info["system_prompt"]),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "{input}")
    ])

def create_agent_chain(model, role_info):
    """각 에이전트의 체인을 생성합니다."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""{role_info["system_prompt"]}
        
당신은 전문적인 분석가로서 매우 철저하고 상세한 분석을 수행해야 합니다.
각 분석은 구체적인 데이터, 사례, 예시를 포함해야 하며, 실행 가능한 인사이트를 제공해야 합니다.
일반적이거나 모호한 진술은 피하고, 구체적이고 명확한 내용으로 작성하세요.
각 섹션은 최소 300단어 이상의 풍부한 내용을 담아야 합니다.

질문에 대한 분석을 진행할 때, 다음 형식을 반드시 준수하세요:

1. 분석:
- 상황에 대한 깊이 있는 이해와 평가를 제공하세요
- 관련 데이터와 트렌드를 활용하여 분석의 근거를 명확히 하세요
- 다양한 관점에서 주제를 검토하고 업계 컨텍스트를 포함하세요
- 단기 및 장기적 관점에서 주요 영향 요소를 분석하세요
- 분석 결과가 갖는 전략적 의미를 설명하세요

2. 추천 사항:
- 최소 5개 이상의 구체적이고 실행 가능한 추천 사항을 제시하세요
- 각 추천 사항의 근거와 예상되는 효과를 설명하세요
- 단기, 중기, 장기적 관점으로 구분하여 조치를 제안하세요
- 추천 사항별 우선순위와 실행 타임라인을 제시하세요
- 각 추천 사항 실행에 필요한 자원과 제약 조건을 명시하세요

3. 위험 평가:
- 주요 위험 요소를 최소 5개 이상 식별하고 분류하세요(전략적, 운영적, 재무적, 법적 등)
- 각 위험의 심각도(상/중/하)와 발생 가능성(상/중/하)을 평가하세요
- 위험 완화 전략과 구체적인 대응 방안을 제시하세요
- 주요 위험 요소에 대한 모니터링 방법과 조기 경보 지표를 설명하세요
- 잠재적 위험이 실현될 경우의 비상 대응 계획을 개략적으로 설명하세요

중요: 모든 응답은 매우 상세하고 구체적이어야 합니다. 일반적인 조언이나 표면적인 분석은 피하세요.
각 섹션의 분석 내용은 실제 의사 결정에 활용할 수 있을 만큼 충분히 구체적이어야 합니다."""),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "{input}")
    ])
    
    def process_response(response):
        """응답을 구조화된 형식으로 변환하고 품질을 검증합니다."""
        # 딕셔너리 형태로 초기화
        result = {
            'analysis': "",
            'recommendation': "",
            'risk_assessment': ""
        }
        
        # 응답이 문자열인 경우
        if isinstance(response, str):
            # 섹션 분리 시도
            analysis_match = re.search(r'(?:분석|1\.\s*분석).*?(?=(?:추천|2\.\s*추천|$))', response, re.DOTALL)
            if analysis_match:
                result['analysis'] = analysis_match.group(0).strip()
            
            recommendation_match = re.search(r'(?:추천|2\.\s*추천).*?(?=(?:위험|3\.\s*위험|$))', response, re.DOTALL)
            if recommendation_match:
                result['recommendation'] = recommendation_match.group(0).strip()
            
            risk_match = re.search(r'(?:위험|3\.\s*위험).*?$', response, re.DOTALL)
            if risk_match:
                result['risk_assessment'] = risk_match.group(0).strip()
            
            # 섹션 분리가 제대로 되지 않은 경우
            if not result['analysis'] and not result['recommendation'] and not result['risk_assessment']:
                # 전체 응답을 분석 섹션에 할당
                result['analysis'] = response
        else:
            # 이미 딕셔너리 형태인 경우
            return response
        
        # 품질 검증 및 보완
        min_lengths = {
            'analysis': 200,         # 최소 200단어 (약 350자)
            'recommendation': 200,   # 최소 200단어 (약 350자)
            'risk_assessment': 200   # 최소 200단어 (약 350자)
        }
        
        for key, min_length in min_lengths.items():
            content = result.get(key, "")
            word_count = len(content.split())
            
            # 내용이 없거나 너무 짧은 경우
            if not content or word_count < min_length:
                if key == 'analysis':
                    # 분석 섹션이 부족한 경우, 기본 분석 내용 제공
                    result[key] = f"""분석:

이 주제에 대한 전문적인 분석을 제공하기 위해서는 더 많은 맥락 정보와 데이터가 필요합니다. 현재 제공된 정보를 바탕으로 한 초기 분석은 다음과 같습니다:

{content}

더 정확하고 깊이 있는 분석을 위해서는 다음과 같은 추가 정보가 필요합니다:
- 관련 시장 데이터 및 트렌드
- 주요 이해관계자 및 경쟁 환경 분석
- 현재의 재무 상태 및 예측
- 조직의 전략적 목표 및 방향성
- 관련 산업의 규제 및 법적 환경

※ 참고: 이 분석은 초기 평가이며, 추가 정보를 바탕으로 더 심층적인 분석이 권장됩니다."""
                elif key == 'recommendation':
                    # 추천 섹션이 부족한 경우, 기본 추천 내용 제공
                    result[key] = f"""추천 사항:

현재 정보를 바탕으로 한 초기 추천 사항은 다음과 같습니다:

{content}

더 구체적이고 실행 가능한 추천 사항을 위해서는 추가 분석이 필요합니다. 일반적으로 고려할 수 있는 접근 방식은 다음과 같습니다:

1. 데이터 기반 의사결정 체계 구축: 관련 핵심 성과 지표(KPI)를 설정하고 정기적인 모니터링 시스템을 구축하세요.

2. 단계적 접근법 채택: 모든 변화를 한 번에 시도하기보다 우선순위가 높은 영역부터 점진적으로 개선하는 전략을 고려하세요.

3. 리스크 관리 프레임워크 수립: 모든 결정에 대한 위험 평가와 완화 전략을 포함한 종합적인 리스크 관리 접근법을 개발하세요.

4. 이해관계자 참여 강화: 주요 의사결정 과정에 모든 관련 이해관계자의 의견을 수렴하여 포괄적인 관점을 확보하세요.

5. 정기적인 검토 및 조정 메커니즘: 모든 전략과 실행 계획에 대한 정기적인 검토 일정을 수립하여 필요에 따라 조정할 수 있도록 하세요.

※ 참고: 이 추천 사항은, 특정 컨텍스트에 맞게 더 세부적으로 조정되어야 합니다."""
                elif key == 'risk_assessment':
                    # 위험 평가 섹션이 부족한 경우, 기본 위험 평가 내용 제공
                    result[key] = f"""위험 평가:

현재 정보를 바탕으로 한 초기 위험 평가는 다음과 같습니다:

{content}

포괄적인 위험 평가를 위해서는 다음과 같은 일반적인 위험 카테고리를 고려해야 합니다:

1. 전략적 위험: 잘못된 비즈니스 결정, 부적절한 전략 실행, 시장 및 경쟁 환경 변화에 대한 대응 실패 등.

2. 운영적 위험: 내부 프로세스 실패, 인적 오류, 시스템 장애, 외부 사건으로 인한 업무 중단 등.

3. 재무적 위험: 유동성 부족, 신용 위험, 투자 손실, 자금 조달 어려움 등.

4. 규제 및 컴플라이언스 위험: 법규 준수 실패, 규제 환경 변화, 법적 책임 문제 등.

5. 평판 위험: 부정적 언론 보도, 소셜 미디어에서의 부정적 여론, 이해관계자 신뢰 상실 등.

각 위험에 대해 심각도와 발생 가능성을 평가하고, 적절한 모니터링 및 대응 계획을 수립하는 것이 중요합니다.

※ 참고: 이 위험 평가는 초기 식별 단계이며, 더 정확한 평가를 위해서는 추가 정보와 전문가 의견이 필요합니다."""
        
        return result

    return prompt | model | StrOutputParser() | process_response

def create_agent_node(agent_type, model):
    """각 에이전트의 노드를 생성합니다."""
    def agent_node(state: AgentState):
        try:
            messages = state["messages"]
            role_info = AGENT_ROLES[agent_type]
            
            # 에이전트별 특화된 프롬프트 생성
            agent_prompt = f"""
            당신은 {role_info['name']}입니다. {role_info['description']}
            
            다음 내용을 분석하고, 아래 형식으로 답변해주세요:
            
            1. 분석:
            [주요 분석 내용을 서술하세요]
            
            2. 추천 사항:
            [구체적인 추천 사항을 제시하세요]
            
            3. 위험 평가:
            [잠재적 위험과 고려사항을 설명하세요]
            
            분석할 내용: {messages[-1].content}
            """
            
            # 에이전트 체인 생성 및 실행
            chain = create_agent_chain(model, role_info)
            result = chain.invoke({
                "messages": messages,
                "input": agent_prompt
            })
            
            # 결과 저장
            state["analysis_results"][agent_type] = result
            
            # 다음 에이전트 결정
            next_agent_map = {
                'financial_agent': 'market_agent',
                'market_agent': 'tech_agent',
                'tech_agent': 'risk_agent',
                'risk_agent': 'legal_agent',
                'legal_agent': 'hr_agent',
                'hr_agent': 'operation_agent',
                'operation_agent': 'strategy_agent',
                'strategy_agent': 'integration_agent'
            }
            state["next"] = next_agent_map.get(agent_type, "integration_agent")
            
            return state
        except Exception as e:
            st.error(f"{agent_type} 처리 중 오류 발생: {str(e)}")
            state["analysis_results"][agent_type] = {
                'analysis': f"에이전트 처리 중 오류 발생: {str(e)}",
                'error': True
            }
            state["next"] = next_agent_map.get(agent_type, "integration_agent")
            return state
    
    return agent_node

def create_integration_node(model):
    """통합 분석 노드 생성"""
    def integration_node(state: AgentState):
        # 활성화된 에이전트 결과 수집
        agent_results = state["analysis_results"]
        active_results = {k: v for k, v in agent_results.items() if v}
        
        if not active_results:
            return {"messages": state["messages"], "next": None, "analysis_results": agent_results}
        
        # 통합 분석 결과 초기화 - 기본 오류 메시지로 설정
        integration_results = {
            "executive_summary": "개요를 생성할 수 없습니다.",
            "situation_analysis": "현황 분석을 생성할 수 없습니다.",
            "analysis": "종합 분석을 생성할 수 없습니다.",
            "recommendation": "추천 사항을 생성할 수 없습니다.",
            "implementation_plan": "실행 계획을 생성할 수 없습니다.",
            "risk_assessment": "위험 평가를 생성할 수 없습니다.",
            "conclusion": "결론을 생성할 수 없습니다."
        }
        
        try:
            # 개별 에이전트 결과 통합
            active_agents_info = ""
            
            # 안전하게 에이전트 결과 수집
            for agent_type, result in active_results.items():
                if agent_type == "integration_agent":
                    continue
                
                # 안전하게 에이전트 정보 가져오기
                agent_role = AGENT_ROLES.get(agent_type, {})
                agent_name = agent_role.get('name', '알 수 없는 에이전트')
                
                # 결과 형식에 따라 처리
                if isinstance(result, dict):
                    active_agents_info += f"\n## {agent_name} 분석 결과:\n"
                    if 'analysis' in result and result['analysis']:
                        active_agents_info += f"\n### 분석:\n{result['analysis']}\n"
                    if 'recommendation' in result and result['recommendation']:
                        active_agents_info += f"\n### 추천 사항:\n{result['recommendation']}\n"
                    if 'risk_assessment' in result and result['risk_assessment']:
                        active_agents_info += f"\n### 위험 평가:\n{result['risk_assessment']}\n"
                else:
                    active_agents_info += f"\n## {agent_name} 분석 결과:\n{str(result)}\n"
            
            # 섹션 정의와 프롬프트 설정
            sections = [
                {
                    "key": "executive_summary",
                    "title": "개요 (Executive Summary)",
                    "instruction": """
주제에 대한 간결하고 명확한 개요를 작성하세요. 다음을 포함해야 합니다:
- 분석 대상의 핵심 사항 요약 (최소 2-3 문장)
- 가장 중요한 발견점 3-5개 나열 (구체적인 데이터 포함)
- 전체 보고서의 범위와 주요 섹션 안내
- 최소 500자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 500
                },
                {
                    "key": "situation_analysis",
                    "title": "현황 분석 및 문제 정의",
                    "instruction": """
현재 상황과 문제점을 명확하게 정의하세요. 다음을 포함해야 합니다:
- 현재 상황에 대한 객관적 설명 (데이터 기반)
- 핵심 문제점 3-5개 구체적 설명
- 원인과 영향 관계 분석
- 문제의 우선순위와 심각성 평가
- 최소 500자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 500
                },
                {
                    "key": "analysis",
                    "title": "종합 분석",
                    "instruction": """
모든 전문가의 분석을 통합하여 심층적인 분석을 제공하세요. 다음을 포함해야 합니다:
- 재무적 측면 분석 (구체적인 수치와 추세 포함)
- 시장 및 경쟁 환경 분석 (SWOT, 5-Forces 등 프레임워크 활용)
- 기술적 실현 가능성 및 요구사항 분석
- 법률 및 규제 측면 분석
- 다양한 관점의 균형 있는 통합
- 최소 800자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 800
                },
                {
                    "key": "recommendation",
                    "title": "핵심 추천 사항",
                    "instruction": """
최소 7개 이상의 구체적이고 실행 가능한 추천 사항을 제시하세요. 각 추천 사항에 다음을 포함해야 합니다:
- 명확한 행동 방침 (구체적인 단계와 방법)
- 이 추천을 지지하는 근거와 분석
- 예상되는 효과와 이점
- 필요한 자원과 타임라인
- 각 추천 항목은 최소 100자 이상으로 설명하세요.
- 추천 사항 전체는 최소 700자 이상이어야 합니다.
""",
                    "min_chars": 700
                },
                {
                    "key": "implementation_plan",
                    "title": "실행 계획",
                    "instruction": """
추천 사항을 실행하기 위한 단계별 계획을 수립하세요. 다음을 포함해야 합니다:
- 각 단계별 구체적인 실행 방법 (최소 3-4단계)
- 단계별 소요 시간과 자원 계획
- 주요 마일스톤과 성공 지표 정의
- 팀 구성 및 역할 분담 방안
- 예상 장애물과 대응 전략
- 최소 500자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 500
                },
                {
                    "key": "risk_assessment",
                    "title": "통합 위험 평가 및 관리",
                    "instruction": """
주요 위험 요소를 파악하고 대응 방안을 제시하세요. 다음을 포함해야 합니다:
- 최소 5개 이상의 주요 위험 요소 식별 (확률과 영향도 포함)
- 각 위험에 대한 구체적인 완화 전략
- 위험 모니터링 방법과 지표
- 위험 관리를 위한 거버넌스 구조
- 비상 계획 및 대응 시나리오
- 최소 600자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 600
                },
                {
                    "key": "conclusion",
                    "title": "결론 및 다음 단계",
                    "instruction": """
보고서의 핵심 내용을 요약하고 다음 단계를 제시하세요. 다음을 포함해야 합니다:
- 주요 발견사항 및 통찰 요약 (최소 3-5개)
- 가장 중요한 추천 사항 상위 3개 강조
- 즉시 취해야 할 다음 행동 단계 (구체적인 일정 포함)
- 장기적 관점의 발전 방향 제시
- 최소 400자 이상의 내용으로 작성하세요.
""",
                    "min_chars": 400
                }
            ]
            
            # 각 섹션별로 실행하여 결과를 통합 결과에 저장
            for section in sections:
                section_key = section["key"]
                section_title = section["title"]
                section_instruction = section["instruction"]
                min_chars = section["min_chars"]
                
                try:
                    # 시스템 프롬프트 작성
                    system_prompt = f"""당신은 종합 분석 보고서의 '{section_title}' 섹션을 작성하는 전문가입니다.
여러 전문가의 분석 결과를 통합하여 상세하고 통찰력 있는 내용을 작성해야 합니다.

{section_instruction}

---
다음 전문가들의 분석 자료를 참고하세요:
{active_agents_info}
---

요구사항:
1. 최소 {min_chars}자 이상의 상세한 내용을 작성하세요.
2. 모든 전문가의 분석을 통합하여 균형 잡힌 시각을 제공하세요.
3. 논리적인 구조와 명확한 주장을 제시하세요.
4. 구체적인 예시와 데이터를 포함하여 내용을 뒷받침하세요.
5. 실행 가능한 구체적인 제안을 포함하세요.

결과는 마크다운 형식으로 제공하되, 제목은 포함하지 마세요. 내용만 작성하세요."""
                    
                    # 메시지 형식으로 프롬프트 구성
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"{section_title} 섹션을 생성해주세요."}
                    ]
                    
                    # 안전하게 LLM 호출
                    try:
                        # 직접 모델 호출 방식 사용
                        response = model.invoke(messages)
                        result = response.content if hasattr(response, 'content') else str(response)
                        
                        # 결과 검증 - 최소 길이 체크
                        if result and len(result.strip()) >= min_chars:
                            integration_results[section_key] = result.strip()
                        else:
                            # 결과가 너무 짧은 경우 재시도
                            warning_message = f"생성된 {section_title}이(가) 너무 짧습니다. 더 자세한 내용이 필요합니다."
                            
                            # 재시도 프롬프트 추가
                            retry_messages = messages.copy()
                            retry_messages.append({"role": "assistant", "content": result})
                            retry_messages.append({"role": "user", "content": warning_message})
                            
                            retry_response = model.invoke(retry_messages)
                            retry_result = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
                            
                            if retry_result and len(retry_result.strip()) >= min_chars:
                                integration_results[section_key] = retry_result.strip()
                            else:
                                integration_results[section_key] = f"{section_title}이(가) 충분히 상세하지 않습니다. 개별 에이전트의 분석 결과를 참조하세요.\n\n{result.strip()}"
                    except Exception as model_error:
                        integration_results[section_key] = f"{section_title}를 생성하는 중 오류가 발생했습니다."
                        logging.warning(f"{section_title} 생성 오류: {str(model_error)}")
                
                except Exception as section_error:
                    integration_results[section_key] = f"{section_title} 처리 중 오류가 발생했습니다."
                    logging.warning(f"{section_title} 처리 오류: {str(section_error)}")
        
        except Exception as e:
            # 전체 오류 처리
            logging.error(f"통합 분석 실패: {str(e)}")
            # 기본 결과는 이미 초기화되었으므로 추가 처리 불필요
        
        # 결과를 에이전트 결과에 저장
        agent_results["integration_agent"] = integration_results
        
        return {
            "messages": state["messages"],
            "next": None,  # 통합 분석은 마지막 단계
            "analysis_results": agent_results
        }
    
    return integration_node

def create_multi_agent_graph(model):
    """멀티 에이전트 그래프 생성"""
    workflow = StateGraph(AgentState)
    
    # 각 에이전트별 노드 추가
    for agent_type in AGENT_ROLES.keys():
        if agent_type != "integration_agent":  # 통합 에이전트는 별도 처리
            workflow.add_node(agent_type, create_agent_node(agent_type, model))
    
    # 통합 에이전트 노드 추가
    workflow.add_node("integration_agent", create_integration_node(model))
    
    # 에이전트 실행 순서 설정
    # 재무 -> 시장 -> 기술 -> 법률 -> 리스크 -> 운영 -> 전략 -> 통합
    workflow.add_edge("financial_agent", "market_agent")
    workflow.add_edge("market_agent", "tech_agent")
    workflow.add_edge("tech_agent", "legal_agent")
    workflow.add_edge("legal_agent", "risk_agent")
    workflow.add_edge("risk_agent", "operation_agent")
    workflow.add_edge("operation_agent", "strategy_agent")
    workflow.add_edge("strategy_agent", "integration_agent")
    workflow.add_edge("integration_agent", END)
    
    # HR 에이전트는 위험 평가 후에 실행 (HR 에이전트가 그래프에 추가된 경우만)
    if "hr_agent" in AGENT_ROLES:
        workflow.add_edge("risk_agent", "hr_agent")
        workflow.add_edge("hr_agent", "operation_agent")
    
    # 시작 노드 설정 (재무 에이전트부터 시작)
    workflow.set_entry_point("financial_agent")
    
    return workflow.compile()

def generate_report_title():
    """보고서 제목을 생성합니다."""
    return f"멀티 에이전트 분석 보고서 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

def create_markdown_report(agent_results):
    """마크다운 형식의 보고서를 생성합니다."""
    report = f"# {generate_report_title()}\n\n"
    
    # 통합 분석 결과가 있는 경우 먼저 표시
    if "integration_agent" in agent_results:
        integration_result = agent_results.get("integration_agent", {})
        
        if isinstance(integration_result, dict):
            # 개요 (Executive Summary) 섹션
            if "executive_summary" in integration_result:
                report += f"{integration_result['executive_summary']}\n\n"
            
            # 현황 분석 및 문제 정의 섹션
            if "situation_analysis" in integration_result:
                report += f"{integration_result['situation_analysis']}\n\n"
            
            # 종합 분석 섹션
            if "analysis" in integration_result:
                report += f"{integration_result['analysis']}\n\n"
            
            # 핵심 추천 사항 섹션
            if "recommendation" in integration_result:
                report += f"{integration_result['recommendation']}\n\n"
            
            # 실행 계획 섹션
            if "implementation_plan" in integration_result:
                report += f"{integration_result['implementation_plan']}\n\n"
            
            # 통합 위험 평가 섹션
            if "risk_assessment" in integration_result:
                report += f"{integration_result['risk_assessment']}\n\n"
            
            # 결론 및 다음 단계 섹션
            if "conclusion" in integration_result:
                report += f"{integration_result['conclusion']}\n\n"
        else:
            # 문자열인 경우 그대로 추가
            report += f"## 통합 분석\n\n{integration_result}\n\n"
    
    # 개별 에이전트 분석 결과
    report += "# 개별 에이전트 분석 결과\n\n"
    for role, result in agent_results.items():
        if role != "integration_agent":
            report += f"## {AGENT_ROLES[role]['name']}의 분석\n\n"
            
            if isinstance(result, dict):
                if "analysis" in result:
                    report += f"### 분석\n\n{result['analysis']}\n\n"
                
                if "recommendation" in result:
                    report += f"### 추천 사항\n\n{result['recommendation']}\n\n"
                
                if "risk_assessment" in result:
                    report += f"### 위험 평가\n\n{result['risk_assessment']}\n\n"
            else:
                # 문자열인 경우 그대로 추가
                report += f"{result}\n\n"
    
    return report

def get_agent_tools(agent_type):
    """에이전트별 특화 도구 반환"""
    tools = {
        'financial_agent': """
재무 분석 도구:
1. ROI 계산기: 투자수익률 = (순이익 - 초기투자) / 초기투자 × 100
2. NPV 계산: 순현재가치 = Σ(미래현금흐름 / (1 + 할인율)^t)
3. 손익분기점 분석: BEP = 고정비용 / (단위당 매출 - 단위당 변동비)
4. 현금흐름 분석: 영업활동, 투자활동, 재무활동 현금흐름 구분
5. 재무비율 분석: 유동성, 수익성, 안정성 비율 계산
6. 자본비용(WACC) 계산: 가중평균자본비용 산출
7. 투자회수기간(PP) 계산: 초기투자금 회수 기간 산출
8. 내부수익률(IRR) 계산: 투자수익률 산출
""",
        'legal_agent': """
법률 검토 도구:
1. 규제 준수성 체크리스트
2. 계약 위험도 평가 매트릭스
3. 법적 책임 범위 분석
4. 지적재산권 검토 도구
5. 규제 변화 영향도 평가
6. 법적 리스크 시나리오 분석
7. 계약 조항 검토 체크리스트
8. 법적 대응 전략 수립 도구
""",
        'market_agent': """
시장 분석 도구:
1. PEST 분석: 정치, 경제, 사회, 기술 요인 분석
2. 5-Forces 분석: 산업 내 경쟁 구조 분석
3. SWOT 분석: 강점, 약점, 기회, 위협 요인 분석
4. 시장 세분화 도구: 고객 그룹 분류 및 특성 분석
5. 경쟁사 매핑: 주요 경쟁사 포지셔닝 분석
6. 시장 성장률 예측 모델
7. 고객 니즈 분석 프레임워크
8. 차별화 전략 수립 도구
""",
        'tech_agent': """
기술 분석 도구:
1. 기술 성숙도 평가(TRL) 매트릭스
2. 기술 로드맵 작성 도구
3. 기술 격차 분석(Gap Analysis)
4. 기술 의존성 매핑
5. 구현 복잡도 평가
6. 기술 부채 분석 도구
7. 확장성 평가 프레임워크
8. 기술 혁신 기회 분석
""",
        'risk_agent': """
리스크 관리 도구:
1. 위험 요소 식별 매트릭스
2. 영향도/발생가능성 평가 도구
3. 리스크 대응 전략 수립
4. 모니터링 체계 설계
5. 비상 계획 수립 도구
6. 리스크 시나리오 분석
7. 위기 대응 체계 구축
8. 리스크 보고 체계
"""
    }
    return tools.get(agent_type, "")

def get_streaming_callback(text_placeholder, tool_placeholder):
    """
    스트리밍 콜백 함수를 생성합니다.

    이 함수는 LLM에서 생성되는 응답을 실시간으로 화면에 표시하기 위한 콜백 함수를 생성합니다.
    텍스트 응답과 도구 호출 정보를 각각 다른 영역에 표시합니다.

    매개변수:
        text_placeholder: 텍스트 응답을 표시할 Streamlit 컴포넌트
        tool_placeholder: 도구 호출 정보를 표시할 Streamlit 컴포넌트

    반환값:
        callback_func: 스트리밍 콜백 함수
        accumulated_text: 누적된 텍스트 응답을 저장하는 리스트
        accumulated_tool: 누적된 도구 호출 정보를 저장하는 리스트
    """
    accumulated_text = []
    accumulated_tool = []

    def callback_func(message: dict):
        nonlocal accumulated_text, accumulated_tool
        message_content = message.get("content", None)

        if isinstance(message_content, AIMessageChunk):
            content = message_content.content
            # 콘텐츠가 리스트 형태인 경우 (Claude 모델 등에서 주로 발생)
            if isinstance(content, list) and len(content) > 0:
                message_chunk = content[0]
                # 텍스트 타입인 경우 처리
                if message_chunk["type"] == "text":
                    accumulated_text.append(message_chunk["text"])
                    text_placeholder.markdown("".join(accumulated_text))
                # 도구 사용 타입인 경우 처리
                elif message_chunk["type"] == "tool_use":
                    if "partial_json" in message_chunk:
                        accumulated_tool.append(message_chunk["partial_json"])
                    else:
                        tool_call_chunks = message_content.tool_call_chunks
                        tool_call_chunk = tool_call_chunks[0]
                        accumulated_tool.append(
                            "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                        )
                    with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                        st.markdown("".join(accumulated_tool))
            # tool_calls 속성이 있는 경우 처리 (OpenAI 모델 등에서 주로 발생)
            elif (
                hasattr(message_content, "tool_calls")
                and message_content.tool_calls
                and len(message_content.tool_calls[0]["name"]) > 0
            ):
                tool_call_info = message_content.tool_calls[0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                    st.markdown("".join(accumulated_tool))
            # 단순 문자열인 경우 처리
            elif isinstance(content, str):
                accumulated_text.append(content)
                text_placeholder.markdown("".join(accumulated_text))
            # 유효하지 않은 도구 호출 정보가 있는 경우 처리
            elif (
                hasattr(message_content, "invalid_tool_calls")
                and message_content.invalid_tool_calls
            ):
                tool_call_info = message_content.invalid_tool_calls[0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander(
                    "🔧 도구 호출 정보 (유효하지 않음)", expanded=True
                ):
                    st.markdown("".join(accumulated_tool))
            # tool_call_chunks 속성이 있는 경우 처리
            elif (
                hasattr(message_content, "tool_call_chunks")
                and message_content.tool_call_chunks
            ):
                tool_call_chunk = message_content.tool_call_chunks[0]
                accumulated_tool.append(
                    "\n```json\n" + str(tool_call_chunk) + "\n```\n"
                )
                with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                    st.markdown("".join(accumulated_tool))
            # additional_kwargs에 tool_calls가 있는 경우 처리 (다양한 모델 호환성 지원)
            elif (
                hasattr(message_content, "additional_kwargs")
                and "tool_calls" in message_content.additional_kwargs
            ):
                tool_call_info = message_content.additional_kwargs["tool_calls"][0]
                accumulated_tool.append("\n```json\n" + str(tool_call_info) + "\n```\n")
                with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                    st.markdown("".join(accumulated_tool))
        # 도구 메시지인 경우 처리 (도구의 응답)
        elif isinstance(message_content, ToolMessage):
            accumulated_tool.append(
                "\n```json\n" + str(message_content.content) + "\n```\n"
            )
            with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                st.markdown("".join(accumulated_tool))
        return None

    return callback_func, accumulated_text, accumulated_tool

async def process_multi_agent_query(query, text_placeholder, tool_placeholder, timeout_seconds=1800, active_agents=None, debug_mode=False, model_name="gpt-4o-mini"):
    """멀티 에이전트 쿼리 처리"""
    try:
        if not st.session_state.session_initialized:
            await initialize_session()
            if not st.session_state.session_initialized:
                return {"error": "MCP 서버 연결에 실패했습니다."}

        # 기본 에이전트 설정
        if active_agents is None:
            active_agents = {
                'financial_agent': True,
                'market_agent': True,
                'tech_agent': True,
                'risk_agent': True,
                'legal_agent': True,
                'hr_agent': True,
                'operation_agent': True,
                'strategy_agent': True,
                'integration_agent': True
            }

        # 디버그 모드일 경우 상태 표시
        if debug_mode:
            st.write("### 디버그 정보")
            st.write("활성화된 에이전트:", active_agents)
            st.write("사용 모델:", model_name)
            st.write("분석 쿼리:", query[:100] + "..." if len(query) > 100 else query)
            st.write(f"응답 생성 제한 시간: {timeout_seconds}초")

        # 스트리밍 콜백 설정
        streaming_callback, accumulated_text, accumulated_tool = get_streaming_callback(text_placeholder, tool_placeholder)

        # 선택된 모델로 직접 분석 수행
        results = {}
        
        # 멀티 에이전트 분석을 위한 모델 인스턴스 생성
        if model_name in ["claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]:
            model = ChatAnthropic(
                model=model_name,
                temperature=0.7,
                max_tokens=OUTPUT_TOKEN_INFO[model_name]["max_tokens"],
            )
        else:  # OpenAI 모델 사용
            model = ChatOpenAI(
                model=model_name,
                temperature=0.7,
                max_tokens=OUTPUT_TOKEN_INFO[model_name]["max_tokens"],
            )

        # 타임아웃 설정으로 실행
        try:
            async with asyncio.timeout(timeout_seconds):
                # 총 분석 시작 시간 기록
                analysis_start_time = datetime.now()
                
                # 각 에이전트별로 분석 실행
                for agent_type, role_info in AGENT_ROLES.items():
                    # 비활성화된 에이전트 건너뛰기 또는 통합 에이전트는 마지막에 처리
                    if (agent_type not in active_agents or not active_agents[agent_type]) or agent_type == 'integration_agent':
                        continue
                        
                    try:
                        # 에이전트 분석 시작 시간 기록
                        agent_start_time = datetime.now()
                        text_placeholder.markdown(f"⏳ **{role_info['name']}** 분석 중... (시작: {agent_start_time.strftime('%H:%M:%S')})")
                        
                        # 에이전트 프롬프트 생성 - 더 상세한 지시와 예시 추가
                        agent_prompt = f"""
                        당신은 {role_info['name']}입니다. {role_info['description']}
                        
                        {role_info['system_prompt']}
                        
                        다음 내용을 심층적으로 분석하고, 아래 형식으로 상세한 답변을 제공해주세요.
                        반드시 각 섹션마다 충분한 내용을 포함해야 합니다(최소 3~5문장 이상).
                        
                        1. 분석:
                        * 주요 요점과 중요 사항을 명확하게 설명하세요
                        * 관련된 데이터와 트렌드를 언급하세요
                        * 구체적인 예시와 관련 정보를 포함하세요
                        * 다양한 관점에서 주제를 고려하세요
                        
                        2. 추천 사항:
                        * 구체적이고 실행 가능한 조치를 제안하세요
                        * 각 추천의 근거와 기대 효과를 설명하세요
                        * 단기 및 장기 권장사항을 구분하세요
                        * 우선순위에 따라 정렬하세요
                        
                        3. 위험 평가:
                        * 주요 위험 요소를 식별하세요
                        * 각 위험의 잠재적 영향과 가능성을 평가하세요
                        * 위험 완화 전략을 제안하세요
                        * 지속적인 모니터링이 필요한 영역을 강조하세요
                        
                        분석할 내용: {query}
                        """
                        
                        # 모델로 분석 수행 - 더 많은 토큰 할당
                        chain = create_agent_chain(model, role_info)
                        result = await chain.ainvoke({
                            "messages": [HumanMessage(content=agent_prompt)],
                            "input": agent_prompt
                        })
                        
                        # 에이전트 분석 종료 시간 기록
                        agent_end_time = datetime.now()
                        agent_duration = (agent_end_time - agent_start_time).total_seconds()
                        text_placeholder.markdown(f"✅ **{role_info['name']}** 분석 완료 (소요시간: {agent_duration:.1f}초)")
                        
                        # 결과가 충분히 상세한지 확인
                        if isinstance(result, dict):
                            # 각 섹션의 내용이 너무 짧으면 기본 메시지로 대체
                            for key in ['analysis', 'recommendation', 'risk_assessment']:
                                if key in result and result[key]:
                                    content = result[key]
                                    # 내용이 너무 짧으면 기본 메시지 추가
                                    if len(content.split()) < 20:  # 단어 수가 20개 미만이면
                                        result[key] = content + f"\n\n이 {key} 섹션에 대한 정보가 충분하지 않습니다. 추가 분석이 필요합니다."
                        else:
                            # 문자열 결과를 강제로 사전 형식으로 변환
                            result_text = str(result)
                            result = {
                                'analysis': "분석:\n" + result_text,
                                'recommendation': "추천 사항:\n상세한 추천 사항을 제공하기 위해서는 더 많은 정보가 필요합니다.",
                                'risk_assessment': "위험 평가:\n잠재적 위험을 평가하기 위해서는 더 많은 맥락이 필요합니다."
                            }
                        
                        # 결과 저장
                        results[agent_type] = result
                        
                    except Exception as agent_error:
                        st.error(f"{role_info['name']} 분석 중 오류 발생: {str(agent_error)}")
                        # 오류가 발생해도 다른 에이전트는 계속 진행
                        results[agent_type] = {
                            "analysis": f"분석 중 오류 발생: {str(agent_error)}",
                            "recommendation": "오류로 인해 추천 사항을 생성할 수 없습니다.",
                            "risk_assessment": "오류로 인해 위험 평가를 수행할 수 없습니다.",
                            "error": True
                        }
                
                # 통합 분석 수행 (다른 에이전트 결과가 있을 경우에만)
                if results and 'integration_agent' in active_agents and active_agents['integration_agent']:
                    try:
                        # 통합 분석 시작 시간 기록
                        integration_start_time = datetime.now()
                        text_placeholder.markdown(f"⏳ **통합 분석 매니저** 분석 중... (시작: {integration_start_time.strftime('%H:%M:%S')})")
                        
                        # 통합 분석 노드 생성
                        integration_node = create_integration_node(model)
                        
                        # 통합 분석 실행을 위한 상태 설정
                        integration_state = {
                            "messages": [HumanMessage(content=query)],
                            "next": "integration_agent",
                            "analysis_results": results
                        }
                        
                        # 통합 분석 실행
                        integrated_state = integration_node(integration_state)
                        
                        # 통합 분석 결과 저장
                        if "analysis_results" in integrated_state and "integration_agent" in integrated_state["analysis_results"]:
                            results["integration_agent"] = integrated_state["analysis_results"]["integration_agent"]
                        else:
                            # 통합 결과가 없으면 기본 메시지 설정
                            results["integration_agent"] = {
                                "executive_summary": "분석을 종합하는 과정에서 오류가 발생했습니다.",
                                "situation_analysis": "개별 에이전트의 분석 결과를 참고해 주세요.",
                                "analysis": "통합 분석을 생성할 수 없습니다.",
                                "recommendation": "개별 에이전트의 추천 사항을 참고해 주세요.",
                                "implementation_plan": "실행 계획을 생성할 수 없습니다.",
                                "risk_assessment": "통합된 위험 평가를 생성할 수 없습니다.",
                                "conclusion": "종합 결론을 생성할 수 없습니다.",
                                "error": True
                            }
                        
                        # 통합 분석 종료 시간 기록
                        integration_end_time = datetime.now()
                        integration_duration = (integration_end_time - integration_start_time).total_seconds()
                        text_placeholder.markdown(f"✅ **통합 분석 매니저** 분석 완료 (소요시간: {integration_duration:.1f}초)")
                        
                    except Exception as integration_error:
                        st.error(f"통합 분석 중 오류 발생: {str(integration_error)}")
                        results['integration_agent'] = {
                            "executive_summary": f"통합 분석 중 오류 발생: {str(integration_error)}",
                            "situation_analysis": "오류로 인해 현황 분석을 생성할 수 없습니다.",
                            "analysis": "오류로 인해 통합 분석을 생성할 수 없습니다.",
                            "recommendation": "오류로 인해 통합 추천 사항을 생성할 수 없습니다.",
                            "implementation_plan": "오류로 인해 실행 계획을 생성할 수 없습니다.",
                            "risk_assessment": "오류로 인해 통합 위험 평가를 수행할 수 없습니다.",
                            "conclusion": "오류로 인해 결론을 생성할 수 없습니다.",
                            "error": True
                        }
                
                # 총 분석 종료 시간 기록
                analysis_end_time = datetime.now()
                total_duration = (analysis_end_time - analysis_start_time).total_seconds()
                text_placeholder.markdown(f"🎉 **멀티 에이전트 분석 완료** (총 소요시간: {total_duration:.1f}초)")
                
                # 세션 상태에 결과 저장
                if results:
                    st.session_state.analysis_result = results
                    st.session_state.current_query = query
                    
                return results if results else {"error": "분석 결과를 생성하지 못했습니다."}

        except asyncio.TimeoutError:
            error_msg = f"분석이 {timeout_seconds}초 제한 시간을 초과했습니다."
            st.error(error_msg)
            return {"error": error_msg}

    except Exception as e:
        import traceback
        error_msg = f"멀티 에이전트 분석 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        st.error(error_msg)
        return {"error": error_msg}

async def cleanup_mcp_client():
    """
    기존 MCP 클라이언트를 안전하게 종료합니다.

    기존 클라이언트가 있는 경우 정상적으로 리소스를 해제합니다.
    """
    if "mcp_client" in st.session_state and st.session_state.mcp_client is not None:
        try:

            await st.session_state.mcp_client.__aexit__(None, None, None)
            st.session_state.mcp_client = None
        except Exception as e:
            import traceback

            # st.warning(f"MCP 클라이언트 종료 중 오류: {str(e)}")
            # st.warning(traceback.format_exc())


def print_message():
    """
    채팅 기록을 화면에 출력합니다.

    사용자와 어시스턴트의 메시지를 구분하여 화면에 표시하고,
    도구 호출 정보는 어시스턴트 메시지 컨테이너 내에 표시합니다.
    """
    i = 0
    while i < len(st.session_state.history):
        message = st.session_state.history[i]

        if message["role"] == "user":
            st.chat_message("user", avatar="🧑‍💻").markdown(message["content"])
            i += 1
        elif message["role"] == "assistant":
            # 어시스턴트 메시지 컨테이너 생성
            with st.chat_message("assistant", avatar="🤖"):
                # 어시스턴트 메시지 내용 표시
                st.markdown(message["content"])

                # 다음 메시지가 도구 호출 정보인지 확인
                if (
                    i + 1 < len(st.session_state.history)
                    and st.session_state.history[i + 1]["role"] == "assistant_tool"
                ):
                    # 도구 호출 정보를 동일한 컨테이너 내에 expander로 표시
                    with st.expander("🔧 도구 호출 정보", expanded=False):
                        st.markdown(st.session_state.history[i + 1]["content"])
                    i += 2  # 두 메시지를 함께 처리했으므로 2 증가
                else:
                    i += 1  # 일반 메시지만 처리했으므로 1 증가
        else:
            # assistant_tool 메시지는 위에서 처리되므로 건너뜀
            i += 1


async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=60):
    """
    사용자 질문을 처리하고 응답을 생성합니다.
    """
    try:
        if st.session_state.agent:
            streaming_callback, accumulated_text_obj, accumulated_tool_obj = (
                get_streaming_callback(text_placeholder, tool_placeholder)
            )
            try:
                # 대화 기록 초기화
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                
                # 대화 기록이 너무 길어지면 초기화
                if len(st.session_state.messages) > 10:
                    st.session_state.messages = []
                
                # 새로운 메시지 추가
                st.session_state.messages.append(HumanMessage(content=query))
                
                # 에이전트 실행
                response = await asyncio.wait_for(
                    astream_graph(
                        st.session_state.agent,
                        {"messages": st.session_state.messages},
                        callback=streaming_callback,
                        config=RunnableConfig(
                            recursion_limit=st.session_state.recursion_limit,
                            thread_id=st.session_state.thread_id,
                        ),
                    ),
                    timeout=timeout_seconds,
                )

                # 응답 처리
                if response:
                    # 도구 호출이 있는 경우 ToolMessage 추가
                    if isinstance(response, dict) and "output" in response:
                        output = response["output"]
                        if hasattr(output, "tool_calls") and output.tool_calls:
                            for tool_call in output.tool_calls:
                                # 도구 호출 결과를 ToolMessage로 변환
                                tool_message = ToolMessage(
                                    content="Tool execution completed",
                                    tool_call_id=tool_call.get("id", ""),
                                    name=tool_call.get("name", ""),
                                )
                                st.session_state.messages.append(tool_message)
                        st.session_state.messages.append(output)
                    elif hasattr(response, "tool_calls") and response.tool_calls:
                        for tool_call in response.tool_calls:
                            # 도구 호출 결과를 ToolMessage로 변환
                            tool_message = ToolMessage(
                                content="Tool execution completed",
                                tool_call_id=tool_call.get("id", ""),
                                name=tool_call.get("name", ""),
                            )
                            st.session_state.messages.append(tool_message)
                        messages.append(response)
                    elif hasattr(response, "content"):
                        st.session_state.messages.append(response)

            except asyncio.TimeoutError:
                error_msg = f"⏱️ 요청 시간이 {timeout_seconds}초를 초과했습니다. 나중에 다시 시도해 주세요."
                return {"error": error_msg}, error_msg, ""
            except Exception as e:
                if "rate_limit_error" in str(e):
                    error_msg = "⚠️ API 속도 제한에 도달했습니다. 잠시 후 다시 시도해 주세요."
                    return {"error": error_msg}, error_msg, ""
                raise e

            final_text = "".join(accumulated_text_obj)
            final_tool = "".join(accumulated_tool_obj)
            return response, final_text, final_tool
        else:
            return (
                {"error": "🚫 에이전트가 초기화되지 않았습니다."},
                "🚫 에이전트가 초기화되지 않았습니다.",
                "",
            )
    except Exception as e:
        import traceback
        error_msg = f"❌ 쿼리 처리 중 오류 발생: {str(e)}"
        if "rate_limit_error" in str(e):
            error_msg = "⚠️ API 속도 제한에 도달했습니다. 잠시 후 다시 시도해 주세요."
        return {"error": error_msg}, error_msg, ""


async def initialize_session(mcp_config=None):
    """
    MCP 세션과 에이전트를 초기화합니다.

    매개변수:
        mcp_config: MCP 도구 설정 정보(JSON). None인 경우 기본 설정 사용

    반환값:
        bool: 초기화 성공 여부
    """
    with st.spinner("🔄 MCP 서버에 연결 중..."):
        # 먼저 기존 클라이언트를 안전하게 정리
        await cleanup_mcp_client()

        if mcp_config is None:
            # config.json 파일에서 설정 로드
            mcp_config = load_config_from_json()
        client = MultiServerMCPClient(mcp_config)
        await client.__aenter__()
        tools = client.get_tools()
        st.session_state.tool_count = len(tools)
        st.session_state.mcp_client = client

        # 선택된 모델에 따라 적절한 모델 초기화
        selected_model = st.session_state.selected_model

        if selected_model in [
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ]:
            model = ChatAnthropic(
                model=selected_model,
                temperature=0.1,
                max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
            )
        else:  # OpenAI 모델 사용
            model = ChatOpenAI(
                model=selected_model,
                temperature=0.1,
                max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
            )
        
        # 모델을 세션 상태에 저장
        st.session_state.model = model
        
        agent = create_react_agent(
            model,
            tools,
            checkpointer=MemorySaver(),
            prompt=SYSTEM_PROMPT,
        )
        st.session_state.agent = agent
        st.session_state.session_initialized = True
        return True


# --- 사이드바: 시스템 설정 섹션 ---
with st.sidebar:
    st.subheader("⚙️ 시스템 설정")

    # 모델 선택 기능
    # 사용 가능한 모델 목록 생성
    available_models = []

    # Anthropic API 키 확인
    has_anthropic_key = os.environ.get("ANTHROPIC_API_KEY") is not None
    if has_anthropic_key:
        available_models.extend(
            [
                "claude-3-7-sonnet-latest",
                "claude-3-5-sonnet-latest",
                "claude-3-5-haiku-latest",
            ]
        )

    # OpenAI API 키 확인
    has_openai_key = os.environ.get("OPENAI_API_KEY") is not None
    if has_openai_key:
        available_models.extend(["gpt-4o", "gpt-4o-mini"])

    # 사용 가능한 모델이 없는 경우 메시지 표시
    if not available_models:
        st.warning(
            "⚠️ API 키가 설정되지 않았습니다. .env 파일에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 추가해주세요."
        )
        # 기본값으로 Claude 모델 추가 (키가 없어도 UI를 보여주기 위함)
        available_models = ["claude-3-7-sonnet-latest"]

    # 모델 선택 드롭다운
    previous_model = st.session_state.selected_model
    st.session_state.selected_model = st.selectbox(
        "🤖 사용할 모델 선택",
        options=available_models,
        index=(
            available_models.index(st.session_state.selected_model)
            if st.session_state.selected_model in available_models
            else 0
        ),
        help="Anthropic 모델은 ANTHROPIC_API_KEY가, OpenAI 모델은 OPENAI_API_KEY가 환경변수로 설정되어야 합니다.",
    )

    # 모델이 변경되었을 때 세션 초기화 필요 알림
    if (
        previous_model != st.session_state.selected_model
        and st.session_state.session_initialized
    ):
        st.warning(
            "⚠️ 모델이 변경되었습니다. '설정 적용하기' 버튼을 눌러 변경사항을 적용하세요."
        )

    # 타임아웃 설정 슬라이더 추가
    st.session_state.timeout_seconds = st.slider(
        "⏱️ 응답 생성 제한 시간(초)",
        min_value=300,
        max_value=3600,
        value=st.session_state.timeout_seconds,
        step=300,
        help="에이전트가 응답을 생성하는 최대 시간을 설정합니다. 복잡한 작업은 더 긴 시간이 필요할 수 있습니다."
    )

    st.session_state.recursion_limit = st.slider(
        "⏱️ 재귀 호출 제한(횟수)",
        min_value=10,
        max_value=200,
        value=st.session_state.recursion_limit,
        step=10,
        help="재귀 호출 제한 횟수를 설정합니다. 너무 높은 값을 설정하면 메모리 부족 문제가 발생할 수 있습니다.",
    )

    st.divider()  # 구분선 추가

    # 도구 설정 섹션 추가
    st.subheader("🔧 도구 설정")

    # expander 상태를 세션 상태로 관리
    if "mcp_tools_expander" not in st.session_state:
        st.session_state.mcp_tools_expander = False

    # MCP 도구 추가 인터페이스
    with st.expander("🧰 MCP 도구 추가", expanded=st.session_state.mcp_tools_expander):
        # config.json 파일에서 설정 로드하여 표시
        loaded_config = load_config_from_json()
        default_config_text = json.dumps(loaded_config, indent=2, ensure_ascii=False)
        
        # pending config가 없으면 기존 mcp_config_text 기반으로 생성
        if "pending_mcp_config" not in st.session_state:
            try:
                st.session_state.pending_mcp_config = loaded_config
            except Exception as e:
                st.error(f"초기 pending config 설정 실패: {e}")

        # 개별 도구 추가를 위한 UI
        st.subheader("도구 추가")
        st.markdown(
            """
            [어떻게 설정 하나요?](https://teddylee777.notion.site/MCP-1d324f35d12980c8b018e12afdf545a1?pvs=4)

            ⚠️ **중요**: JSON을 반드시 중괄호(`{}`)로 감싸야 합니다."""
        )

        # 보다 명확한 예시 제공
        example_json = {
            "github": {
                "command": "npx",
                "args": [
                    "-y",
                    "@smithery/cli@latest",
                    "run",
                    "@smithery-ai/github",
                    "--config",
                    '{"githubPersonalAccessToken":"your_token_here"}',
                ],
                "transport": "stdio",
            }
        }

        default_text = json.dumps(example_json, indent=2, ensure_ascii=False)

        new_tool_json = st.text_area(
            "도구 JSON",
            default_text,
            height=250,
        )

        # 추가하기 버튼
        if st.button(
            "도구 추가",
            type="primary",
            key="add_tool_button",
            use_container_width=True,
        ):
            try:
                # 입력값 검증
                if not new_tool_json.strip().startswith(
                    "{"
                ) or not new_tool_json.strip().endswith("}"):
                    st.error("JSON은 중괄호({})로 시작하고 끝나야 합니다.")
                    st.markdown('올바른 형식: `{ "도구이름": { ... } }`')
                else:
                    # JSON 파싱
                    parsed_tool = json.loads(new_tool_json)

                    # mcpServers 형식인지 확인하고 처리
                    if "mcpServers" in parsed_tool:
                        # mcpServers 안의 내용을 최상위로 이동
                        parsed_tool = parsed_tool["mcpServers"]
                        st.info(
                            "'mcpServers' 형식이 감지되었습니다. 자동으로 변환합니다."
                        )

                    # 입력된 도구 수 확인
                    if len(parsed_tool) == 0:
                        st.error("최소 하나 이상의 도구를 입력해주세요.")
                    else:
                        # 모든 도구에 대해 처리
                        success_tools = []
                        for tool_name, tool_config in parsed_tool.items():
                            # URL 필드 확인 및 transport 설정
                            if "url" in tool_config:
                                # URL이 있는 경우 transport를 "sse"로 설정
                                tool_config["transport"] = "sse"
                                st.info(
                                    f"'{tool_name}' 도구에 URL이 감지되어 transport를 'sse'로 설정했습니다."
                                )
                            elif "transport" not in tool_config:
                                # URL이 없고 transport도 없는 경우 기본값 "stdio" 설정
                                tool_config["transport"] = "stdio"

                            # 필수 필드 확인
                            if (
                                "command" not in tool_config
                                and "url" not in tool_config
                            ):
                                st.error(
                                    f"'{tool_name}' 도구 설정에는 'command' 또는 'url' 필드가 필요합니다."
                                )
                            elif "command" in tool_config and "args" not in tool_config:
                                st.error(
                                    f"'{tool_name}' 도구 설정에는 'args' 필드가 필요합니다."
                                )
                            elif "command" in tool_config and not isinstance(
                                tool_config["args"], list
                            ):
                                st.error(
                                    f"'{tool_name}' 도구의 'args' 필드는 반드시 배열([]) 형식이어야 합니다."
                                )
                            else:
                                # pending_mcp_config에 도구 추가
                                st.session_state.pending_mcp_config[tool_name] = (
                                    tool_config
                                )
                                success_tools.append(tool_name)

                        # 성공 메시지
                        if success_tools:
                            if len(success_tools) == 1:
                                st.success(
                                    f"{success_tools[0]} 도구가 추가되었습니다. 적용하려면 '설정 적용하기' 버튼을 눌러주세요."
                                )
                            else:
                                tool_names = ", ".join(success_tools)
                                st.success(
                                    f"총 {len(success_tools)}개 도구({tool_names})가 추가되었습니다. 적용하려면 '설정 적용하기' 버튼을 눌러주세요."
                                )
                            # 추가되면 expander를 접어줌
                            st.session_state.mcp_tools_expander = False
                            st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"JSON 파싱 에러: {e}")
                st.markdown(
                    f"""
                **수정 방법**:
                1. JSON 형식이 올바른지 확인하세요.
                2. 모든 키는 큰따옴표(")로 감싸야 합니다.
                3. 문자열 값도 큰따옴표(")로 감싸야 합니다.
                4. 문자열 내에서 큰따옴표를 사용할 경우 이스케이프(\\")해야 합니다.
                """
                )
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # 등록된 도구 목록 표시 및 삭제 버튼 추가
    with st.expander("📋 등록된 도구 목록", expanded=True):
        try:
            pending_config = st.session_state.pending_mcp_config
        except Exception as e:
            st.error("유효한 MCP 도구 설정이 아닙니다.")
        else:
            # pending config의 키(도구 이름) 목록을 순회하며 표시
            for tool_name in list(pending_config.keys()):
                col1, col2 = st.columns([8, 2])
                col1.markdown(f"- **{tool_name}**")
                if col2.button("삭제", key=f"delete_{tool_name}"):
                    # pending config에서 해당 도구 삭제 (즉시 적용되지는 않음)
                    del st.session_state.pending_mcp_config[tool_name]
                    st.success(
                        f"{tool_name} 도구가 삭제되었습니다. 적용하려면 '설정 적용하기' 버튼을 눌러주세요."
                    )

    st.divider()  # 구분선 추가

# --- 사이드바: 시스템 정보 및 작업 버튼 섹션 ---
with st.sidebar:
    st.subheader("📊 시스템 정보")
    st.write(f"🛠️ MCP 도구 수: {st.session_state.get('tool_count', '초기화 중...')}")
    selected_model_name = st.session_state.selected_model
    st.write(f"🧠 현재 모델: {selected_model_name}")

    # MCP 분석 테이블 생성 버튼 추가
    if st.button("MCP 분석 테이블 생성", use_container_width=True):
        if create_mcp_analysis_table():
            st.success("MCP 분석 테이블이 생성되었습니다.")
        else:
            st.error("테이블 생성에 실패했습니다.")

    # 설정 적용하기 버튼을 여기로 이동
    if st.button(
        "설정 적용하기",
        key="apply_button",
        type="primary",
        use_container_width=True,
    ):
        # 적용 중 메시지 표시
        apply_status = st.empty()
        with apply_status.container():
            st.warning("🔄 변경사항을 적용하고 있습니다. 잠시만 기다려주세요...")
            progress_bar = st.progress(0)

            # 설정 저장
            st.session_state.mcp_config_text = json.dumps(
                st.session_state.pending_mcp_config, indent=2, ensure_ascii=False
            )

            # config.json 파일에 설정 저장
            save_result = save_config_to_json(st.session_state.pending_mcp_config)
            if not save_result:
                st.error("❌ 설정 파일 저장에 실패했습니다.")
            
            progress_bar.progress(15)

            # 세션 초기화 준비
            st.session_state.session_initialized = False
            st.session_state.agent = None

            # 진행 상태 업데이트
            progress_bar.progress(30)

            # 초기화 실행
            success = st.session_state.event_loop.run_until_complete(
                initialize_session(st.session_state.pending_mcp_config)
            )

            # 진행 상태 업데이트
            progress_bar.progress(100)

            if success:
                st.success("✅ 새로운 설정이 적용되었습니다.")
                # 도구 추가 expander 접기
                if "mcp_tools_expander" in st.session_state:
                    st.session_state.mcp_tools_expander = False
            else:
                st.error("❌ 설정 적용에 실패하였습니다.")

        # 페이지 새로고침
        st.rerun()

    st.divider()  # 구분선 추가

    # 작업 버튼 섹션
    st.subheader("🔄 작업")

    # 대화 초기화 버튼
    if st.button("대화 초기화", use_container_width=True, type="primary"):
        # thread_id 초기화
        st.session_state.thread_id = random_uuid()

        # 대화 히스토리 초기화
        st.session_state.history = []

        # 알림 메시지
        st.success("✅ 대화가 초기화되었습니다.")

        # 페이지 새로고침
        st.rerun()

    # 로그인 기능이 활성화된 경우에만 로그아웃 버튼 표시
    if use_login and st.session_state.authenticated:
        st.divider()  # 구분선 추가
        if st.button("로그아웃", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            st.success("✅ 로그아웃 되었습니다.")
            st.rerun()

# --- 기본 세션 초기화 (초기화되지 않은 경우) ---
if not st.session_state.session_initialized:
    st.info(
        "MCP 서버와 에이전트가 초기화되지 않았습니다. 왼쪽 사이드바의 '설정 적용하기' 버튼을 클릭하여 초기화해주세요."
    )


# --- 대화 기록 출력 ---
print_message()

# --- 사용자 입력 및 처리 ---
# 채팅 기록 출력
print_message()

# 저장 버튼 컨테이너 생성
save_container = st.container()

# 사용자 입력
user_query = st.chat_input("💬 질문을 입력하세요")
if user_query:
    if st.session_state.session_initialized:
        st.chat_message("user", avatar="🧑‍💻").markdown(user_query)
        with st.chat_message("assistant", avatar="🤖"):
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            
            if "[멀티에이전트]" in user_query:
                resp, final_text, final_tool = (
                    st.session_state.event_loop.run_until_complete(
                        process_multi_agent_query(
                            user_query,
                            text_placeholder,
                            tool_placeholder,
                            st.session_state.timeout_seconds,
                        )
                    )
                )
            else:
                resp, final_text, final_tool = (
                    st.session_state.event_loop.run_until_complete(
                        process_query(
                            user_query,
                            text_placeholder,
                            tool_placeholder,
                            st.session_state.timeout_seconds,
                        )
                    )
                )
            
            if isinstance(resp, dict) and "error" in resp:
                st.error(resp["error"])
            else:
                st.session_state.history.append({"role": "user", "content": user_query})
                st.session_state.history.append(
                    {"role": "assistant", "content": final_text}
                )
                if final_tool.strip():
                    st.session_state.history.append(
                        {"role": "assistant_tool", "content": final_tool}
                    )
                st.rerun()
    else:
        st.warning(
            "⚠️ MCP 서버와 에이전트가 초기화되지 않았습니다. 왼쪽 사이드바의 '설정 적용하기' 버튼을 클릭하여 초기화해주세요."
        )

# 저장 버튼 및 초기화 옵션
with save_container:
    if st.session_state.history and len(st.session_state.history) >= 2:  # 최소한 하나의 대화가 있을 때
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("보고서 저장", type="primary", help="현재 대화 내용을 데이터베이스에 저장합니다."):
                conn = None
                cursor = None
                try:
                    # DB 연결
                    conn = connect_to_db()
                    if conn:
                        cursor = conn.cursor()
                        
                        # 마지막 대화 쌍 찾기
                        last_user_message = None
                        last_assistant_message = None
                        last_tool_message = None
                        
                        for msg in reversed(st.session_state.history):
                            if msg["role"] == "user" and not last_user_message:
                                last_user_message = msg["content"]
                            elif msg["role"] == "assistant" and not last_assistant_message:
                                last_assistant_message = msg["content"]
                            elif msg["role"] == "assistant_tool" and not last_tool_message:
                                last_tool_message = msg["content"]
                            
                            if last_user_message and last_assistant_message:
                                break
                        
                        # 분석 결과 저장
                        cursor.execute("""
                            INSERT INTO mcp_analysis_results 
                            (query, analysis_result)
                            VALUES (%s, %s)
                        """, (
                            last_user_message,
                            json.dumps({
                                "text": last_assistant_message,
                                "tool": last_tool_message if last_tool_message else None
                            })
                        ))
                        
                        conn.commit()
                        st.success("✅ 보고서가 저장되었습니다.")
                        
                        # 초기화 확인
                        if st.checkbox("대화 내용을 초기화하시겠습니까?"):
                            st.session_state.history = []
                            st.rerun()
                            
                    else:
                        st.error("데이터베이스 연결에 실패했습니다.")
                        
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                finally:
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()

def create_download_link(content, filename):
    """텍스트 내용으로 다운로드 링크 생성"""
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:text/plain;base64,{b64}" download="{filename}">다운로드 {filename}</a>'
    return href

def save_analysis_to_db(query, analysis_results, update_existing=False):
    """분석 결과를 DB에 저장"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # 마크다운 보고서 생성
        md_report = create_markdown_report(analysis_results)
        
        # JSON으로 변환할 결과 준비
        json_results = json.dumps(analysis_results, ensure_ascii=False)
        
        if update_existing:
            # 기존 분석 결과 검색
            cursor.execute("""
                SELECT id FROM mcp_analysis_results 
                WHERE query = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (query,))
            
            result = cursor.fetchone()
            if result:
                # 기존 분석 결과 업데이트
                cursor.execute("""
                    UPDATE mcp_analysis_results
                    SET analysis_result = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (json_results, result[0]))
                # 세션 상태에 저장 성공 메시지와 저장된 결과 기록
                st.session_state.save_success = True
                st.session_state.saved_analysis_results = analysis_results
                st.session_state.saved_analysis_id = result[0]
                # 성공 메시지 표시 (페이지 리프레시 없이)
                st.success(f"기존 분석 결과(ID: {result[0]})를 업데이트했습니다.")
            else:
                # 결과가 없으면 새 레코드 삽입
                cursor.execute("""
                    INSERT INTO mcp_analysis_results 
                    (query, analysis_result)
                    VALUES (%s, %s)
                """, (query, json_results))
                # 새로 생성된 ID 가져오기
                cursor.execute("SELECT LAST_INSERT_ID()")
                new_id = cursor.fetchone()[0]
                # 세션 상태에 저장 성공 메시지와 저장된 결과 기록
                st.session_state.save_success = True
                st.session_state.saved_analysis_results = analysis_results
                st.session_state.saved_analysis_id = new_id
                # 성공 메시지 표시 (페이지 리프레시 없이)
                st.success("새 분석 결과를 DB에 저장했습니다.")
        else:
            # 새 분석 결과 삽입
            cursor.execute("""
                INSERT INTO mcp_analysis_results 
                (query, analysis_result)
                VALUES (%s, %s)
            """, (query, json_results))
            # 새로 생성된 ID 가져오기
            cursor.execute("SELECT LAST_INSERT_ID()")
            new_id = cursor.fetchone()[0]
            # 세션 상태에 저장 성공 메시지와 저장된 결과 기록
            st.session_state.save_success = True
            st.session_state.saved_analysis_results = analysis_results
            st.session_state.saved_analysis_id = new_id
            # 성공 메시지 표시 (페이지 리프레시 없이)
            st.success("분석 결과를 DB에 저장했습니다.")
            
        conn.commit()
        return True
    except Exception as e:
        st.error(f"DB 저장 중 오류가 발생했습니다: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def load_saved_analyses():
    """저장된 분석 결과 목록 로드"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return []
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, query, created_at 
            FROM mcp_analysis_results 
            ORDER BY created_at DESC
        """)
        
        results = cursor.fetchall()
        
        # datetime 객체를 문자열로 변환
        for result in results:
            result['created_at'] = result['created_at'].strftime('%Y-%m-%d %H:%M')
            
        return results
    except Exception as e:
        st.error(f"분석 결과 목록 로드 중 오류 발생: {str(e)}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def load_analysis_by_id(analysis_id):
    """ID로 분석 결과 로드"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, query, analysis_result, created_at 
            FROM mcp_analysis_results 
            WHERE id = %s
        """, (analysis_id,))
        
        result = cursor.fetchone()
        
        if result:
            # datetime 객체를 문자열로 변환
            result['created_at'] = result['created_at'].strftime('%Y-%m-%d %H:%M')
            
        return result
    except Exception as e:
        st.error(f"분석 결과 로드 중 오류 발생: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def delete_saved_analysis(analysis_id):
    """저장된 분석 결과 삭제"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM mcp_analysis_results 
            WHERE id = %s
        """, (analysis_id,))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"분석 결과 삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def main():
    """Main application"""

    # 저장 성공 상태 확인
    if "save_success" in st.session_state and st.session_state.save_success:
        st.success("분석 결과가 성공적으로 저장되었습니다.")
        # 저장 성공 상태 초기화
        st.session_state.save_success = False

    # 분석 결과 저장 상태 초기화
    if "saved_analysis_results" not in st.session_state:
        st.session_state.saved_analysis_results = {}

    tab1, tab2 = st.tabs(["기본 분석 및 저장", "멀티 에이전트 상세 분석"])

    with tab1:
        st.markdown("✨ MCP 에이전트에게 질문해보세요.")
        # ... existing code ...

    with tab2:
        st.header("멀티 에이전트 상세 분석")
        
        # AI 에이전트 설정
        with st.expander("🤖 AI 에이전트 설정", expanded=True):
            st.subheader("활성화할 에이전트")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                financial_agent = st.checkbox("재무 분석가", value=True)
                market_agent = st.checkbox("시장 분석가", value=True)
                tech_agent = st.checkbox("기술 분석가", value=True)
                
            with col2:
                risk_agent = st.checkbox("위험 관리 전문가", value=True)
                legal_agent = st.checkbox("법률 전문가", value=True)
                hr_agent = st.checkbox("인적 자원 전문가", value=True)
                
            with col3:
                operation_agent = st.checkbox("운영 전문가", value=True)
                strategy_agent = st.checkbox("전략 컨설턴트", value=True)
                integration_agent = st.checkbox("통합 분석 매니저", value=True, disabled=True)

            # 활성화된 에이전트 정보 저장
            active_agents = {
                'financial_agent': financial_agent,
                'market_agent': market_agent,
                'tech_agent': tech_agent,
                'risk_agent': risk_agent,
                'legal_agent': legal_agent,
                'hr_agent': hr_agent,
                'operation_agent': operation_agent,
                'strategy_agent': strategy_agent,
                'integration_agent': True  # 항상 활성화
            }
        
        try:
            # DB에서 저장된 분석 결과 조회
            conn = connect_to_db()
            if not conn:
                st.error("데이터베이스 연결에 실패했습니다.")
                return
                
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, query, analysis_result, created_at 
                FROM mcp_analysis_results 
                ORDER BY created_at DESC
            """)
            saved_analyses = cursor.fetchall()
            
            if not saved_analyses:
                st.info("저장된 분석 결과가 없습니다. 먼저 기본 분석을 수행하고 저장해주세요.")
            else:
                # 분석 결과 선택
                col1, col2 = st.columns([3, 1])
                with col1:
                    selected_analysis = st.selectbox(
                        "상세 분석할 데이터 선택",
                        saved_analyses,
                        format_func=lambda x: f"{x['query'][:100]}... ({x['created_at'].strftime('%Y-%m-%d %H:%M')})"
                    )
                
                with col2:
                    if st.button("🗑️ 선택한 분석 삭제", type="secondary", help="선택한 분석을 데이터베이스에서 삭제합니다"):
                        try:
                            cursor.execute('DELETE FROM mcp_analysis_results WHERE id = %s', (selected_analysis['id'],))
                            conn.commit()
                            st.success("분석이 성공적으로 삭제되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 중 오류가 발생했습니다: {str(e)}")

                if selected_analysis:
                    st.write("### 선택된 분석")
                    st.write("**원본 질문:**")
                    st.write(selected_analysis['query'])
                    
                    # 기존 분석 결과 표시
                    st.write("**기존 분석 결과:**")
                    if selected_analysis['analysis_result']:
                        analysis_result = json.loads(selected_analysis['analysis_result'])
                        st.write(analysis_result)

                    # 상세 분석을 위한 지시사항 입력
                    analysis_instruction = st.text_area(
                        "상세 분석 지시사항",
                        help="상세 분석을 위한 구체적인 지시사항을 입력하세요. 예: '기술적 측면에서의 위험 요소를 자세히 분석해주세요.' 또는 '재무적 관점에서 성장 가능성을 평가해주세요.'",
                        height=100,
                        placeholder="상세 분석을 위한 지시사항을 입력하세요..."
                    )

                    if st.button("상세 분석 시작", type="primary"):
                        if not analysis_instruction:
                            st.warning("상세 분석을 위한 지시사항을 입력해주세요.")
                        else:
                            # 분석 결과를 표시할 컨테이너 생성
                            result_area = st.container()
                            
                            # 캐시된 분석 결과가 있는지 확인
                            has_cached_results = (
                                "current_multi_agent_results" in st.session_state and 
                                "current_multi_agent_query" in st.session_state and
                                "current_analysis_instruction" in st.session_state and
                                "current_selected_analysis_id" in st.session_state and
                                st.session_state.current_selected_analysis_id == selected_analysis['id'] and
                                st.session_state.current_analysis_instruction == analysis_instruction
                            )
                            
                            if has_cached_results:
                                # 캐시된 결과 사용
                                with result_area:
                                    st.success("✅ 저장된 분석 결과를 표시합니다.")
                                    results = st.session_state.current_multi_agent_results
                                    combined_query = st.session_state.current_multi_agent_query
                            else:
                                # 새로운 분석 실행
                                with st.spinner("멀티 에이전트 상세 분석 중..."):
                                    try:
                                        # 원본 분석과 지시사항을 결합
                                        combined_query = f"""
                                        [멀티에이전트] 다음 내용에 대해 상세 분석해주세요:

                                        원본 질문: {selected_analysis['query']}
                                        기존 분석 결과: {selected_analysis['analysis_result']}

                                        추가 분석 지시사항:
                                        {analysis_instruction}
                                        """
                                        
                                        # 진행 상태 표시용 플레이스홀더
                                        status_placeholder = st.empty()
                                        text_placeholder = st.empty()
                                        tool_placeholder = st.empty()
                                        
                                        status_placeholder.info("멀티 에이전트 분석을 시작합니다... (완전한 분석에는 약 10-15분이 소요됩니다)")
                                        
                                        # 실제 멀티 에이전트 분석 실행
                                        results = None
                                        
                                        status_placeholder.info("멀티 에이전트 분석을 시작합니다... (완전한 분석에는 약 10-15분이 소요됩니다)")
                                        
                                        # 모델 이름 출력
                                        text_placeholder.markdown(f"🤖 사용 모델: **{st.session_state.selected_model}**")
                                        text_placeholder.markdown(f"⏱️ 최대 분석 시간: **{st.session_state.timeout_seconds}초**")
                                        
                                        results = st.session_state.event_loop.run_until_complete(
                                            process_multi_agent_query(
                                                combined_query,
                                                text_placeholder=text_placeholder,
                                                tool_placeholder=tool_placeholder,
                                                timeout_seconds=st.session_state.timeout_seconds,
                                                active_agents=active_agents,
                                                debug_mode=True,
                                                model_name=st.session_state.selected_model
                                            )
                                        )
                                        
                                        # 분석 결과를 세션 상태에 저장
                                        if results and not (isinstance(results, dict) and "error" in results and len(results) == 1):
                                            st.session_state.current_multi_agent_results = results
                                            st.session_state.current_multi_agent_query = combined_query
                                            st.session_state.current_analysis_instruction = analysis_instruction
                                            st.session_state.current_selected_analysis_id = selected_analysis['id']
                                        
                                        # 진행 상태 표시 제거
                                        status_placeholder.empty()
                                        text_placeholder.empty()
                                        tool_placeholder.empty()
                                        
                                        # 결과가 있는 경우 (성공 또는 일부 결과)
                                        if results and not (isinstance(results, dict) and "error" in results and len(results) == 1):
                                            with result_area:
                                                st.success("✅ 상세 분석이 완료되었습니다.")
                                                
                                                # 메인 분석 탭과 개별 에이전트 탭 생성
                                                main_tabs = st.tabs(["종합 보고서", "개별 에이전트 보고서"])
                                                
                                                # 종합 보고서 탭
                                                with main_tabs[0]:
                                                    if 'integration_agent' in results:
                                                        st.markdown("## 📊 최종 통합 분석")
                                                        integration_result = results.get('integration_agent', '')
                                                        if isinstance(integration_result, dict):
                                                            # 각 섹션별로 표시
                                                            sections = [
                                                                ('executive_summary', '개요 (Executive Summary)'),
                                                                ('situation_analysis', '현황 분석 및 문제 정의'),
                                                                ('analysis', '종합 분석'),
                                                                ('recommendation', '핵심 추천 사항'),
                                                                ('implementation_plan', '실행 계획'),
                                                                ('risk_assessment', '통합 위험 평가 및 관리'),
                                                                ('conclusion', '결론 및 다음 단계')
                                                            ]
                                                            
                                                            for section_key, section_title in sections:
                                                                if section_key in integration_result and integration_result[section_key]:
                                                                    st.markdown(f"### {section_title}")
                                                                    st.markdown(integration_result[section_key])
                                                        else:
                                                            st.markdown(str(integration_result))
                                                            
                                                        # 마크다운 다운로드 기능 추가
                                                        st.markdown("---")
                                                        st.subheader("📥 보고서 다운로드 및 저장")
                                                        md_report = create_markdown_report(results)
                                                        
                                                        col1, col2 = st.columns([1, 2])
                                                        with col1:
                                                            st.markdown(create_download_link(md_report, "multi_agent_analysis_report.md"), unsafe_allow_html=True)
                                                        
                                                        # DB에 결과 저장/업데이트 옵션
                                                        with col2:
                                                            col_a, col_b = st.columns(2)
                                                            with col_a:
                                                                save_as_new = st.checkbox("새 분석으로 저장", value=True,
                                                                                        help="체크하면 새 분석 결과로 저장하고, 체크하지 않으면 기존 분석 결과를 업데이트합니다.")
                                                            
                                                            with col_b:
                                                                if st.button("💾 저장", type="primary"):
                                                                    with st.spinner("결과를 DB에 저장하는 중..."):
                                                                        # 추가 지시사항 포함한 쿼리 생성
                                                                        save_query = f"{selected_analysis['query']} [추가 분석: {analysis_instruction}]"
                                                                        
                                                                        if save_as_new:
                                                                            # 새로운 분석 결과로 저장
                                                                            save_success = save_analysis_to_db(save_query, results, False)
                                                                            if save_success:
                                                                                st.success("새 분석 결과가 DB에 성공적으로 저장되었습니다.")
                                                                                # 저장 성공 상태를 세션 상태에 기록
                                                                                if "save_success" not in st.session_state:
                                                                                    st.session_state.save_success = True
                                                                            else:
                                                                                st.error("DB 저장 중 오류가 발생했습니다.")
                                                                        else:
                                                                            # 기존 분석 결과 업데이트
                                                                            try:
                                                                                # 기존 분석 결과 ID 가져오기
                                                                                analysis_id = selected_analysis['id']
                                                                                
                                                                                # JSON으로 변환할 결과 준비
                                                                                json_results = json.dumps(results, ensure_ascii=False)
                                                                                
                                                                                # DB 연결 및 업데이트
                                                                                update_conn = connect_to_db()
                                                                                if not update_conn:
                                                                                    st.error("데이터베이스 연결에 실패했습니다.")
                                                                                else:
                                                                                    update_cursor = update_conn.cursor()
                                                                                    update_cursor.execute("""
                                                                                        UPDATE mcp_analysis_results
                                                                                        SET analysis_result = %s, 
                                                                                            query = %s,
                                                                                            updated_at = CURRENT_TIMESTAMP
                                                                                        WHERE id = %s
                                                                                    """, (json_results, save_query, analysis_id))
                                                                                    
                                                                                    update_conn.commit()
                                                                                    update_cursor.close()
                                                                                    update_conn.close()
                                                                                    
                                                                                    st.success(f"기존 분석 결과(ID: {analysis_id})가 업데이트되었습니다.")
                                                                                    # 저장 성공 상태를 세션 상태에 기록
                                                                                    if "save_success" not in st.session_state:
                                                                                        st.session_state.save_success = True
                                                                            except Exception as e:
                                                                                st.error(f"분석 결과 업데이트 중 오류 발생: {str(e)}")
                                                    else:
                                                        st.info("통합 분석 결과가 없습니다.")
                                                
                                                # 개별 에이전트 보고서 탭
                                                with main_tabs[1]:
                                                    # 필터링된 에이전트 목록 생성 (통합 에이전트 제외)
                                                    filtered_agents = {
                                                        agent: info for agent, info in AGENT_ROLES.items()
                                                        if agent in active_agents and active_agents[agent] and 
                                                        agent in results and agent != "integration_agent"
                                                    }
                                                    
                                                    if filtered_agents:
                                                        # 에이전트 서브탭 생성
                                                        agent_tabs = st.tabs([
                                                            f"{info['name']}" 
                                                            for agent, info in filtered_agents.items()
                                                        ])
                                                        
                                                        # 각 에이전트 탭에 결과 표시
                                                        for tab, (agent_type, info) in zip(agent_tabs, filtered_agents.items()):
                                                            with tab:
                                                                agent_result = results.get(agent_type, {})
                                                                
                                                                if not agent_result:
                                                                    st.info(f"{info['name']} 분석 결과가 없습니다.")
                                                                    continue
                                                                    
                                                                # 분석 결과 표시
                                                                st.markdown(f"### {info['name']} 분석")
                                                                if isinstance(agent_result, dict):
                                                                    if agent_result.get('analysis'):
                                                                        st.markdown(agent_result['analysis'])
                                                                    else:
                                                                        st.markdown(str(agent_result))
                                                                    
                                                                    # 추천 사항 표시
                                                                    if agent_result.get('recommendation'):
                                                                        st.markdown("### 💡 추천 사항")
                                                                        st.markdown(agent_result['recommendation'])
                                                                    
                                                                    # 위험도 평가 표시
                                                                    if agent_result.get('risk_assessment'):
                                                                        st.markdown("### ⚠️ 위험 평가")
                                                                        st.markdown(agent_result['risk_assessment'])
                                                                    
                                                                    # 개별 에이전트 보고서 다운로드
                                                                    st.markdown("---")
                                                                    st.markdown("### 📥 에이전트 보고서 다운로드")
                                                                    individual_report = f"# {info['name']} 분석 보고서\n\n"
                                                                    
                                                                    if agent_result.get('analysis'):
                                                                        individual_report += f"## 분석\n\n{agent_result['analysis']}\n\n"
                                                                    if agent_result.get('recommendation'):
                                                                        individual_report += f"## 추천 사항\n\n{agent_result['recommendation']}\n\n"
                                                                    if agent_result.get('risk_assessment'):
                                                                        individual_report += f"## 위험 평가\n\n{agent_result['risk_assessment']}\n\n"
                                                                    
                                                                    st.markdown(
                                                                        create_download_link(
                                                                            individual_report, 
                                                                            f"{info['name']}_analysis_report.md"
                                                                        ),
                                                                        unsafe_allow_html=True
                                                                    )
                                                                else:
                                                                    # 문자열인 경우 직접 표시
                                                                    st.markdown(str(agent_result))
                                                                    
                                                                    # 문자열 결과도 다운로드 가능하게
                                                                    st.markdown("---")
                                                                    individual_report = f"# {info['name']} 분석 보고서\n\n{str(agent_result)}"
                                                                    st.markdown(
                                                                        create_download_link(
                                                                            individual_report, 
                                                                            f"{info['name']}_analysis_report.md"
                                                                        ),
                                                                        unsafe_allow_html=True
                                                                    )
                                                    else:
                                                        st.info("활성화된 에이전트의 분석 결과가 없습니다.")
                                                
                                                # 개별 에이전트 탭에도 저장 기능 추가
                                                st.markdown("---")
                                                st.subheader("📥 전체 보고서 저장")
                                                md_report = create_markdown_report(results)
                                                
                                                col1, col2 = st.columns([1, 2])
                                                with col1:
                                                    st.markdown(create_download_link(md_report, "multi_agent_analysis_report.md"), unsafe_allow_html=True)
                                                
                                                # DB에 결과 저장/업데이트 옵션
                                                with col2:
                                                    col_a, col_b = st.columns(2)
                                                    with col_a:
                                                        save_as_new_tab2 = st.checkbox("새 분석으로 저장 (탭2)", value=True,
                                                                        help="체크하면 새 분석 결과로 저장하고, 체크하지 않으면 기존 분석 결과를 업데이트합니다.")
                                                    
                                                    with col_b:
                                                        if st.button("💾 저장 (탭2)", type="primary", key="save_results_tab2"):
                                                            with st.spinner("결과를 DB에 저장하는 중..."):
                                                                # 추가 지시사항 포함한 쿼리 생성
                                                                save_query2 = f"{selected_analysis['query']} [추가 분석: {analysis_instruction}]"
                                                                
                                                                if save_as_new_tab2:
                                                                    # 새로운 분석 결과로 저장
                                                                    save_success = save_analysis_to_db(save_query2, results, False)
                                                                    if save_success:
                                                                        st.success("새 분석 결과가 DB에 성공적으로 저장되었습니다.")
                                                                        # 저장된 결과를 세션에 보관
                                                                        if "saved_analysis_results" not in st.session_state:
                                                                            st.session_state.saved_analysis_results = {}
                                                                        st.session_state.saved_analysis_results[save_query2] = results
                                                                    else:
                                                                        st.error("DB 저장 중 오류가 발생했습니다.")
                                                                else:
                                                                    # 기존 분석 결과 업데이트
                                                                    try:
                                                                        # 기존 분석 결과 ID 가져오기
                                                                        analysis_id = selected_analysis['id']
                                                                        
                                                                        # JSON으로 변환할 결과 준비
                                                                        json_results = json.dumps(results, ensure_ascii=False)
                                                                        
                                                                        # DB 연결 및 업데이트
                                                                        update_conn = connect_to_db()
                                                                        if not update_conn:
                                                                            st.error("데이터베이스 연결에 실패했습니다.")
                                                                        else:
                                                                            update_cursor = update_conn.cursor()
                                                                            update_cursor.execute("""
                                                                                UPDATE mcp_analysis_results
                                                                                SET analysis_result = %s, 
                                                                                    query = %s,
                                                                                    updated_at = CURRENT_TIMESTAMP
                                                                                WHERE id = %s
                                                                            """, (json_results, save_query2, analysis_id))
                                                                            
                                                                            update_conn.commit()
                                                                            update_cursor.close()
                                                                            update_conn.close()
                                                                            
                                                                            st.success(f"기존 분석 결과(ID: {analysis_id})가 업데이트되었습니다.")
                                                                            # 저장된 결과를 세션에 보관
                                                                            if "saved_analysis_results" not in st.session_state:
                                                                                st.session_state.saved_analysis_results = {}
                                                                            st.session_state.saved_analysis_results[save_query2] = results
                                                                    except Exception as e:
                                                                        st.error(f"분석 결과 업데이트 중 오류 발생: {str(e)}")
                                        else:
                                            st.error("분석 결과가 없거나 오류가 발생했습니다.")
                                    except Exception as e:
                                        st.error(f"상세 분석 중 오류가 발생했습니다: {str(e)}")
                                        import traceback
                                        st.error(f"상세 에러: {traceback.format_exc()}")

        except Exception as e:
            st.error(f"분석 결과 조회 중 오류가 발생했습니다: {str(e)}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

if __name__ == "__main__":
    main()