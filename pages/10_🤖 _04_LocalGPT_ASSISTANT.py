import streamlit as st
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import os
import json
import time
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="🤖 CrewAI Multi-Agent System",
    page_icon="🤖",
    layout="wide"
)

# 환경 변수 설정 (CrewAI에서 필요)
os.environ["OPENAI_API_KEY"] = "NA"

# 사용 가능한 모델 목록 (크기 순)
AVAILABLE_MODELS = [
    {"name": "llama3.2:latest", "size": "2.0 GB"},
    {"name": "llama2:latest", "size": "3.8 GB"},
    {"name": "mistral:latest", "size": "4.1 GB"},
    {"name": "llama3.1:latest", "size": "4.9 GB"},
    {"name": "llama3.1:8b", "size": "4.9 GB"},
    {"name": "gemma:latest", "size": "5.0 GB"},
    {"name": "gemma2:latest", "size": "5.4 GB"},
    {"name": "deepseek-r1:14b", "size": "9.0 GB"},
    {"name": "phi4:latest", "size": "9.1 GB"},
    {"name": "deepseek-r1:32b", "size": "19 GB"},
    {"name": "llama3.3:latest", "size": "42 GB"}
]

# 워크플로우 타입 정의
WORKFLOW_TYPES = {
    "research_analysis": {
        "name": "🔬 연구 분석 워크플로우",
        "description": "복잡한 주제를 심도있게 연구하고 분석하는 워크플로우",
        "icon": "🔬",
        "agents": ["researcher", "analyst", "reviewer"]
    },
    "content_creation": {
        "name": "✍️ 콘텐츠 제작 워크플로우", 
        "description": "기획부터 작성, 편집까지 완성된 콘텐츠를 만드는 워크플로우",
        "icon": "✍️",
        "agents": ["planner", "writer", "editor"]
    },
    "problem_solving": {
        "name": "🧩 문제 해결 워크플로우",
        "description": "복잡한 문제를 분석하고 해결책을 도출하는 워크플로우", 
        "icon": "🧩",
        "agents": ["analyzer", "strategist", "validator"]
    },
    "translation_localization": {
        "name": "🌐 번역 현지화 워크플로우",
        "description": "다국어 번역과 문화적 현지화를 수행하는 워크플로우",
        "icon": "🌐", 
        "agents": ["translator", "cultural_advisor", "reviewer"]
    }
}

# Ollama 연결 테스트 함수
@st.cache_data(ttl=60)  # 1분 캐시
def test_ollama_connection():
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            return True, "연결됨"
        else:
            return False, f"상태 코드: {response.status_code}"
    except Exception as e:
        return False, f"연결 실패: {str(e)}"

# 사이드바 설정
st.sidebar.title("🤖 CrewAI 시스템 설정")

# Ollama 연결 상태 확인
st.sidebar.subheader("🔗 Ollama 연결 상태")
is_connected, connection_status = test_ollama_connection()
if is_connected:
    st.sidebar.success(f"✅ {connection_status}")
else:
    st.sidebar.error(f"❌ {connection_status}")
    st.sidebar.markdown("""
    **해결 방법:**
    1. 터미널에서 `ollama serve` 실행
    2. 모델 다운로드: `ollama pull mistral`
    3. 방화벽 설정 확인
    """)

# 모델 선택
st.sidebar.subheader("🧠 모델 설정")
selected_model = st.sidebar.selectbox(
    "사용할 모델을 선택하세요:",
    options=[model["name"] for model in AVAILABLE_MODELS],
    format_func=lambda x: f"{x} ({next(m['size'] for m in AVAILABLE_MODELS if m['name'] == x)})",
    index=2  # mistral:latest를 기본값으로 설정
)

# Temperature 설정
temperature = st.sidebar.slider(
    "Temperature:", 
    min_value=0.0, 
    max_value=2.0, 
    value=0.1, 
    step=0.1,
    help="값이 높을수록 더 창의적인 응답을 생성합니다."
)

# 워크플로우 선택
st.sidebar.subheader("🔄 워크플로우 선택")
selected_workflow_key = st.sidebar.selectbox(
    "워크플로우를 선택하세요:",
    options=list(WORKFLOW_TYPES.keys()),
    format_func=lambda x: WORKFLOW_TYPES[x]["name"],
    index=0
)

selected_workflow = WORKFLOW_TYPES[selected_workflow_key]

# 워크플로우 정보 표시
with st.sidebar.expander("ℹ️ 선택된 워크플로우 정보"):
    st.write(f"**{selected_workflow['icon']} {selected_workflow['name']}**")
    st.write(selected_workflow["description"])
    st.write(f"**참여 에이전트:** {', '.join(selected_workflow['agents'])}")

# 실행 모드 설정
execution_mode = st.sidebar.radio(
    "실행 모드:",
    ["순차적 실행", "계층적 실행"],
    help="순차적: 에이전트들이 순서대로 작업 / 계층적: 관리자가 작업을 분배"
)

# Ollama LLM 설정 (타임아웃 개선)
@st.cache_resource
def get_crew_llm(model_name, temp):
    return ChatOpenAI(
        model=f"ollama/{model_name}",
        base_url="http://localhost:11434/v1",
        temperature=temp,
        timeout=1800,  # 30분 타임아웃
        max_retries=3,
        request_timeout=600  # 10분 요청 타임아웃
    )

# 에이전트 정의 함수들 (도구 없이)
def create_researcher_agent(llm):
    return Agent(
        role="Senior Research Analyst",
        goal="주어진 주제에 대해 포괄적이고 정확한 연구를 수행합니다",
        backstory="""당신은 15년 경력의 시니어 연구 분석가입니다. 
        복잡한 주제를 체계적으로 분석하고, 신뢰할 수 있는 정보를 수집하며,
        데이터 기반의 인사이트를 도출하는 전문가입니다.
        항상 출처를 명확히 하고 객관적인 관점을 유지합니다.
        내장된 지식을 활용하여 깊이 있는 분석을 제공합니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=True
    )

def create_analyst_agent(llm):
    return Agent(
        role="Data Analyst & Strategist", 
        goal="연구 결과를 분석하고 실행 가능한 인사이트를 도출합니다",
        backstory="""당신은 데이터 분석과 전략 수립 전문가입니다.
        복잡한 정보를 체계적으로 분석하고, 패턴을 찾아내며,
        실용적인 결론과 추천사항을 제시합니다.
        비즈니스 관점에서 분석 결과를 해석하는 능력이 뛰어납니다.
        논리적 사고와 전략적 분석에 집중합니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_reviewer_agent(llm):
    return Agent(
        role="Quality Assurance Reviewer",
        goal="모든 결과물의 품질을 검증하고 개선점을 제안합니다",
        backstory="""당신은 품질 보증 전문가입니다.
        연구 결과와 분석 내용의 정확성, 논리성, 완성도를 평가하고,
        개선이 필요한 부분을 명확히 지적하며 구체적인 개선 방안을 제시합니다.
        높은 기준을 유지하며 세심한 검토를 수행합니다.
        비판적 사고와 품질 관리에 전문성을 가지고 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=True
    )

def create_planner_agent(llm):
    return Agent(
        role="Content Strategy Planner",
        goal="효과적인 콘텐츠 전략과 구조를 기획합니다",
        backstory="""당신은 콘텐츠 전략 기획 전문가입니다.
        타겟 오디언스를 분석하고, 효과적인 메시지 전달 방법을 설계하며,
        체계적인 콘텐츠 구조를 만드는 능력이 뛰어납니다.
        SEO와 사용자 경험을 모두 고려한 전략을 수립합니다.
        마케팅과 콘텐츠 기획에 특화된 전문가입니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_writer_agent(llm):
    return Agent(
        role="Professional Content Writer",
        goal="기획에 따라 매력적이고 정확한 콘텐츠를 작성합니다",
        backstory="""당신은 10년 경력의 전문 콘텐츠 작가입니다.
        복잡한 내용을 이해하기 쉽게 설명하고, 독자의 관심을 끄는
        매력적인 글을 작성합니다. 다양한 형식과 톤에 능숙하며,
        항상 독자 중심의 관점으로 글을 씁니다.
        창의적 글쓰기와 기술 문서 작성에 모두 뛰어납니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_editor_agent(llm):
    return Agent(
        role="Senior Content Editor",
        goal="콘텐츠를 검토하고 최종 품질을 보장합니다",
        backstory="""당신은 시니어 콘텐츠 에디터입니다.
        문법, 스타일, 논리성, 가독성을 종합적으로 검토하고,
        브랜드 톤앤매너에 맞게 콘텐츠를 최적화합니다.
        세심한 검토를 통해 완벽한 품질의 콘텐츠를 만들어냅니다.
        편집과 교정, 스타일 가이드 적용에 전문성을 가지고 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=True
    )

def create_translator_agent(llm):
    return Agent(
        role="Professional Translator",
        goal="정확하고 자연스러운 번역을 제공합니다",
        backstory="""당신은 다국어 번역 전문가입니다.
        언어의 미묘한 뉘앙스와 문화적 맥락을 이해하며,
        원문의 의도를 정확히 전달하는 자연스러운 번역을 제공합니다.
        다양한 분야의 전문 용어에 정통합니다.
        한국어, 영어, 일본어, 중국어 등 다국어에 능통합니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_cultural_advisor_agent(llm):
    return Agent(
        role="Cultural Localization Advisor",
        goal="문화적 맥락을 고려한 현지화를 제안합니다",
        backstory="""당신은 문화 현지화 전문가입니다.
        다양한 문화권의 관습, 가치관, 소통 방식을 깊이 이해하며,
        타겟 문화에 적합한 표현과 접근 방식을 제안합니다.
        문화적 민감성을 고려한 조언을 제공합니다.
        국제 비즈니스와 문화 연구에 전문성을 가지고 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_analyzer_agent(llm):
    return Agent(
        role="Problem Analysis Specialist",
        goal="복잡한 문제를 체계적으로 분석하고 분해합니다",
        backstory="""당신은 문제 분석 전문가입니다.
        복잡한 문제를 구성 요소로 분해하고, 원인과 결과를 파악하며,
        다각도에서 문제를 조명합니다. 체계적이고 논리적인 접근을
        통해 문제의 본질을 정확히 파악합니다.
        시스템 사고와 근본 원인 분석에 특화되어 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_strategist_agent(llm):
    return Agent(
        role="Solution Strategy Developer",
        goal="실현 가능한 해결책과 전략을 개발합니다",
        backstory="""당신은 솔루션 전략 개발자입니다.
        분석된 문제를 바탕으로 창의적이고 실현 가능한 해결책을 제시하며,
        단계적 실행 계획을 수립합니다. 리스크를 고려하고
        대안을 준비하는 전략적 사고가 뛰어납니다.
        경영 전략과 프로젝트 관리에 전문성을 가지고 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=False
    )

def create_validator_agent(llm):
    return Agent(
        role="Solution Validation Expert",
        goal="제안된 해결책의 타당성을 검증하고 개선합니다",
        backstory="""당신은 솔루션 검증 전문가입니다.
        제안된 해결책의 실현 가능성, 효과성, 위험도를 평가하고,
        개선점을 제안합니다. 실무 경험을 바탕으로 현실적인
        관점에서 솔루션을 검토합니다.
        위험 관리와 실행 가능성 평가에 전문성을 가지고 있습니다.""",
        llm=llm,
        verbose=True,
        memory=True,
        allow_delegation=True
    )

# 태스크 생성 함수들
def create_research_tasks(agents, topic):
    research_task = Task(
        description=f"""
        주제 '{topic}'에 대해 포괄적인 연구를 수행하세요.
        
        다음 사항들을 포함해야 합니다:
        1. 주제의 핵심 개념과 정의
        2. 최신 동향과 발전 사항 (당신의 지식 기반으로)
        3. 주요 플레이어와 이해관계자
        4. 도전과제와 기회요인
        5. 관련 데이터와 통계 (일반적인 지식 기반)
        
        당신의 전문 지식을 활용하여 객관적인 관점을 유지하세요.
        """,
        expected_output="체계적으로 정리된 연구 보고서 (한국어, 2000자 이상)",
        agent=agents["researcher"]
    )
    
    analysis_task = Task(
        description=f"""
        연구 결과를 바탕으로 '{topic}'에 대한 심화 분석을 수행하세요.
        
        분석 내용:
        1. 주요 패턴과 트렌드 식별
        2. 영향도 및 중요도 평가
        3. 향후 전망과 예측
        4. 실행 가능한 인사이트 도출
        5. 권장사항 제시
        
        논리적이고 체계적인 분석을 제공하세요.
        """,
        expected_output="상세한 분석 리포트 (한국어, 1500자 이상)",
        agent=agents["analyst"],
        context=[research_task]
    )
    
    review_task = Task(
        description="""
        연구 보고서와 분석 리포트를 종합 검토하세요.
        
        검토 기준:
        1. 정보의 정확성과 논리성
        2. 분석의 일관성
        3. 결론의 깊이와 완성도
        4. 개선이 필요한 부분 식별
        5. 최종 결론의 타당성
        
        건설적인 피드백과 개선방안을 제시하여 최종 통합 리포트를 작성하세요.
        """,
        expected_output="품질 검토 보고서와 최종 통합 리포트 (한국어, 1000자 이상)",
        agent=agents["reviewer"],
        context=[research_task, analysis_task]
    )
    
    return [research_task, analysis_task, review_task]

def create_content_tasks(agents, topic):
    planning_task = Task(
        description=f"""
        주제 '{topic}'에 대한 콘텐츠 제작 전략을 수립하세요.
        
        기획 요소:
        1. 타겟 오디언스 분석
        2. 핵심 메시지 정의
        3. 콘텐츠 구조 설계
        4. 톤앤매너 설정
        5. 효과적인 표현 방식 선정
        
        매력적이고 효과적인 콘텐츠 전략을 제시하세요.
        """,
        expected_output="상세한 콘텐츠 기획서 (한국어, 1000자 이상)",
        agent=agents["planner"]
    )
    
    writing_task = Task(
        description=f"""
        기획서를 바탕으로 '{topic}'에 대한 고품질 콘텐츠를 작성하세요.
        
        작성 요구사항:
        1. 기획서의 구조와 방향성 준수
        2. 독자 친화적인 문체 사용
        3. 논리적이고 체계적인 구성
        4. 적절한 예시와 사례 포함
        5. 명확한 결론과 액션 포인트
        
        매력적이고 유익한 콘텐츠를 제작하세요.
        """,
        expected_output="완성된 콘텐츠 (한국어, 2500자 이상, 마크다운 형식)",
        agent=agents["writer"],
        context=[planning_task]
    )
    
    editing_task = Task(
        description="""
        작성된 콘텐츠를 전면 검토하고 편집하세요.
        
        편집 기준:
        1. 문법과 맞춤법 검토
        2. 문체와 톤 일관성 확인
        3. 논리적 흐름 개선
        4. 가독성 향상
        5. 전체적인 품질 향상
        
        최고 품질의 완성된 콘텐츠를 제공하세요.
        """,
        expected_output="최종 편집된 고품질 콘텐츠 (한국어, 마크다운 형식)",
        agent=agents["editor"],
        context=[planning_task, writing_task]
    )
    
    return [planning_task, writing_task, editing_task]

def create_problem_solving_tasks(agents, topic):
    analyze_task = Task(
        description=f"""
        문제 '{topic}'을 체계적으로 분석하세요.
        
        분석 영역:
        1. 문제의 정확한 정의
        2. 근본 원인 분석
        3. 영향 범위 파악
        4. 제약 조건 식별
        5. 우선순위 설정
        
        객관적이고 포괄적인 문제 분석을 수행하세요.
        """,
        expected_output="상세한 문제 분석 보고서 (한국어, 1500자 이상)",
        agent=agents["analyzer"]
    )
    
    strategy_task = Task(
        description=f"""
        분석된 문제 '{topic}'에 대한 해결 전략을 개발하세요.
        
        전략 요소:
        1. 다양한 해결 방안 제시
        2. 각 방안의 장단점 평가
        3. 실행 계획 수립
        4. 필요 자원 산정
        5. 위험 요소 및 대응책
        
        실현 가능하고 효과적인 해결 전략을 제안하세요.
        """,
        expected_output="종합적인 해결 전략 보고서 (한국어, 2000자 이상)",
        agent=agents["strategist"],
        context=[analyze_task]
    )
    
    validate_task = Task(
        description="""
        제안된 해결 전략을 검증하고 최적화하세요.
        
        검증 기준:
        1. 실현 가능성 평가
        2. 예상 효과 분석
        3. 리스크 평가
        4. 비용 대비 효과
        5. 대안 시나리오 검토
        
        검증된 최종 솔루션을 제시하세요.
        """,
        expected_output="검증된 최종 솔루션 보고서 (한국어, 1500자 이상)",
        agent=agents["validator"],
        context=[analyze_task, strategy_task]
    )
    
    return [analyze_task, strategy_task, validate_task]

def create_translation_tasks(agents, content):
    translate_task = Task(
        description=f"""
        다음 내용을 영어로 정확하게 번역하세요:
        
        원문: {content}
        
        번역 요구사항:
        1. 원문의 의미와 뉘앙스 보존
        2. 자연스러운 영어 표현 사용
        3. 전문 용어의 정확한 번역
        4. 문화적 맥락 고려
        5. 가독성 있는 문체
        
        고품질의 전문 번역을 제공하세요.
        """,
        expected_output="정확하고 자연스러운 영어 번역문",
        agent=agents["translator"]
    )
    
    localize_task = Task(
        description="""
        번역된 내용을 영어권 문화에 맞게 현지화하세요.
        
        현지화 요소:
        1. 문화적 적절성 검토
        2. 표현 방식 조정
        3. 예시와 사례 현지화
        4. 커뮤니케이션 스타일 조정
        5. 타겟 오디언스 고려
        
        문화적으로 적절하고 효과적인 현지화를 제안하세요.
        """,
        expected_output="현지화 제안사항과 개선된 번역문",
        agent=agents["cultural_advisor"],
        context=[translate_task]
    )
    
    final_review_task = Task(
        description="""
        번역과 현지화 작업을 최종 검토하세요.
        
        검토 사항:
        1. 번역의 정확성
        2. 현지화의 적절성
        3. 전체적인 일관성
        4. 품질 및 완성도
        5. 개선이 필요한 부분
        
        최종 완성된 번역물을 제공하세요.
        """,
        expected_output="최종 검토된 완성 번역문",
        agent=agents["reviewer"],
        context=[translate_task, localize_task]
    )
    
    return [translate_task, localize_task, final_review_task]

# 에이전트 매핑
AGENT_CREATORS = {
    "researcher": create_researcher_agent,
    "analyst": create_analyst_agent,
    "reviewer": create_reviewer_agent,
    "planner": create_planner_agent,
    "writer": create_writer_agent,
    "editor": create_editor_agent,
    "translator": create_translator_agent,
    "cultural_advisor": create_cultural_advisor_agent,
    "analyzer": create_analyzer_agent,
    "strategist": create_strategist_agent,
    "validator": create_validator_agent
}

# 태스크 매핑
TASK_CREATORS = {
    "research_analysis": create_research_tasks,
    "content_creation": create_content_tasks,
    "problem_solving": create_problem_solving_tasks,
    "translation_localization": create_translation_tasks
}

# 메시지 저장 함수 (독립적)
def save_crew_message(message, role, workflow=None):
    if "crew_messages" not in st.session_state:
        st.session_state["crew_messages"] = []
    
    message_data = {
        "message": message,
        "role": role,
        "timestamp": datetime.now().isoformat(),
        "workflow": workflow,
        "model": selected_model
    }
    
    st.session_state["crew_messages"].append(message_data)

# 메시지 기록 표시
def paint_crew_history():
    if "crew_messages" in st.session_state:
        for message_data in st.session_state["crew_messages"]:
            workflow = message_data.get("workflow", "일반")
            workflow_info = WORKFLOW_TYPES.get(workflow, {"icon": "🤖", "name": "일반"})
            
            if message_data["role"] == "human":
                with st.chat_message("user"):
                    st.markdown(message_data["message"])
            else:
                with st.chat_message("assistant", avatar=workflow_info["icon"]):
                    st.markdown(message_data["message"])

# 메인 UI
st.title("🤖 CrewAI Multi-Agent System")
st.markdown("**진정한 다중 에이전트 협업 시스템**")

# 현재 설정 정보 표시
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    st.markdown(f"**워크플로우:** {selected_workflow['icon']} {selected_workflow['name']}")
with col2:
    st.markdown(f"**모델:** {selected_model}")
with col3:
    st.markdown(f"**실행 모드:** {execution_mode}")

# 워크플로우 설명
with st.expander("🔄 현재 워크플로우 정보"):
    st.markdown(f"### {selected_workflow['icon']} {selected_workflow['name']}")
    st.write(selected_workflow["description"])
    
    st.markdown("#### 🤖 참여 에이전트들:")
    for agent_key in selected_workflow["agents"]:
        if agent_key == "researcher":
            st.write("**🔍 Senior Research Analyst**: 포괄적이고 정확한 연구 수행")
        elif agent_key == "analyst":
            st.write("**📊 Data Analyst & Strategist**: 데이터 분석과 인사이트 도출")
        elif agent_key == "reviewer":
            st.write("**✅ Quality Assurance Reviewer**: 품질 검증과 개선점 제안")
        elif agent_key == "planner":
            st.write("**📋 Content Strategy Planner**: 효과적인 콘텐츠 전략 기획")
        elif agent_key == "writer":
            st.write("**✍️ Professional Content Writer**: 매력적인 콘텐츠 작성")
        elif agent_key == "editor":
            st.write("**📝 Senior Content Editor**: 최종 품질 보장과 편집")
        elif agent_key == "translator":
            st.write("**🌐 Professional Translator**: 정확하고 자연스러운 번역")
        elif agent_key == "cultural_advisor":
            st.write("**🌍 Cultural Localization Advisor**: 문화적 현지화 조언")
        elif agent_key == "analyzer":
            st.write("**🔬 Problem Analysis Specialist**: 체계적인 문제 분석")
        elif agent_key == "strategist":
            st.write("**🎯 Solution Strategy Developer**: 실현 가능한 해결책 개발")
        elif agent_key == "validator":
            st.write("**🔍 Solution Validation Expert**: 솔루션 타당성 검증")

# 사용법 안내
st.markdown("""
💡 **CrewAI 멀티에이전트 시스템 사용법:**
1. 원하는 워크플로우를 선택하세요
2. 실행 모드를 설정하세요 (순차적/계층적)
3. 주제나 요청사항을 입력하세요
4. 에이전트들이 협력하여 작업을 수행합니다!

**워크플로우별 특징:**
- **🔬 연구 분석**: 연구원 → 분석가 → 검토자 순으로 협력
- **✍️ 콘텐츠 제작**: 기획자 → 작가 → 편집자 순으로 협력  
- **🧩 문제 해결**: 분석가 → 전략가 → 검증자 순으로 협력
- **🌐 번역 현지화**: 번역가 → 문화자문가 → 검토자 순으로 협력

📝 **참고**: 현재는 에이전트들의 내장 지식을 활용하여 작업합니다.
""")

# 기존 메시지 기록 그리기
paint_crew_history()

# 입력 인터페이스
if selected_workflow_key == "translation_localization":
    user_input = st.text_area(
        "번역할 내용을 입력하세요:",
        placeholder="번역하고 싶은 한국어 텍스트를 입력해주세요...",
        height=100
    )
else:
    user_input = st.chat_input("원하는 주제나 요청사항을 입력하세요...")

if user_input:
    # Ollama 연결 상태 재확인
    if not is_connected:
        st.error("❌ Ollama 서버에 연결할 수 없습니다. 사이드바의 해결 방법을 확인해주세요.")
        st.stop()
    
    save_crew_message(user_input, "human", selected_workflow_key)
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    with st.chat_message("assistant", avatar=selected_workflow["icon"]):
        # 진행 상황 표시
        progress_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("🔄 시스템 초기화 중...")
                progress_bar.progress(10)
                
                # LLM 초기화
                status_text.text("🧠 LLM 모델 로딩 중...")
                llm = get_crew_llm(selected_model, temperature)
                progress_bar.progress(20)
                
                # 워크플로우별 에이전트 생성 (도구 없이)
                status_text.text("🤖 에이전트들 생성 중...")
                agents = {}
                agent_count = len(selected_workflow["agents"])
                
                for i, agent_key in enumerate(selected_workflow["agents"]):
                    if agent_key in AGENT_CREATORS:
                        agents[agent_key] = AGENT_CREATORS[agent_key](llm)
                        progress = 20 + (30 * (i + 1) / agent_count)
                        progress_bar.progress(int(progress))
                        status_text.text(f"🤖 에이전트 '{agent_key}' 생성 완료...")
                
                # 워크플로우별 태스크 생성
                status_text.text("📋 작업 태스크 생성 중...")
                if selected_workflow_key in TASK_CREATORS:
                    tasks = TASK_CREATORS[selected_workflow_key](agents, user_input)
                    progress_bar.progress(60)
                else:
                    st.error("지원되지 않는 워크플로우입니다.")
                    st.stop()
                
                # 실행 모드 설정
                process_mode = Process.sequential if execution_mode == "순차적 실행" else Process.hierarchical
                
                # Crew 생성
                status_text.text("👥 팀(Crew) 구성 중...")
                crew = Crew(
                    agents=list(agents.values()),
                    tasks=tasks,
                    process=process_mode,
                    verbose=True,
                    memory=True
                )
                progress_bar.progress(70)
                
                # 작업 실행
                status_text.text("🚀 에이전트들이 협력 작업을 시작합니다...")
                progress_bar.progress(80)
                
                # 실제 작업 실행 (시간이 오래 걸릴 수 있음)
                with st.spinner("💼 에이전트들이 열심히 작업 중입니다... (최대 30분 소요 가능)"):
                    result = crew.kickoff()
                
                progress_bar.progress(100)
                status_text.text("✅ 작업 완료!")
                
                # 진행 표시 제거
                progress_container.empty()
                
                # 결과 표시
                st.markdown("### 🎉 협업 작업 완료!")
                st.markdown(result)
                
                # 메시지 저장
                save_crew_message(result, "assistant", selected_workflow_key)
                
            except Exception as e:
                progress_container.empty()
                error_msg = str(e)
                
                if "timeout" in error_msg.lower():
                    st.error("""
                    ⏰ **작업 시간 초과**
                    
                    멀티에이전트 작업이 예상보다 오래 걸렸습니다.
                    
                    **해결 방법:**
                    1. 더 간단한 주제로 시도해보세요
                    2. 더 작은 모델 사용 (llama3.2:latest 추천)
                    3. Temperature를 낮춰보세요 (0.1)
                    4. 워크플로우를 '순차적 실행'으로 설정
                    """)
                elif "connection" in error_msg.lower():
                    st.error("""
                    🔌 **연결 오류**
                    
                    Ollama 서버와의 연결에 문제가 있습니다.
                    
                    **해결 방법:**
                    1. 터미널에서 `ollama serve` 실행
                    2. `ollama ps`로 모델 상태 확인
                    3. 모델을 미리 로드: `ollama run mistral`
                    """)
                else:
                    st.error(f"❌ 에이전트 협업 중 오류가 발생했습니다: {error_msg}")
                
                logger.error(f"CrewAI 오류: {e}")
                
                # 상세한 디버그 정보 (개발용)
                with st.expander("🔧 상세 오류 정보 (개발자용)"):
                    st.code(f"""
                    오류 유형: {type(e).__name__}
                    오류 메시지: {str(e)}
                    모델: {selected_model}
                    워크플로우: {selected_workflow_key}
                    실행 모드: {execution_mode}
                    """)

# 사이드바 하단 정보
with st.sidebar:
    st.markdown("---")
    
    # 현재 세션 통계
    if "crew_messages" in st.session_state:
        st.markdown("### 📊 협업 세션 통계")
        total_messages = len(st.session_state["crew_messages"])
        user_messages = sum(1 for msg in st.session_state["crew_messages"] if msg["role"] == "human")
        crew_responses = total_messages - user_messages
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("총 메시지", total_messages)
            st.metric("사용자 요청", user_messages)
        with col2:
            st.metric("Crew 응답", crew_responses)
            
            # 가장 많이 사용된 워크플로우
            workflow_usage = {}
            for msg in st.session_state["crew_messages"]:
                if msg["role"] == "assistant" and msg.get("workflow"):
                    workflow_key = msg["workflow"]
                    workflow_usage[workflow_key] = workflow_usage.get(workflow_key, 0) + 1
            
            if workflow_usage:
                most_used_workflow = max(workflow_usage, key=workflow_usage.get)
                workflow_info = WORKFLOW_TYPES.get(most_used_workflow, {"icon": "🤖"})
                st.metric("주요 워크플로우", f"{workflow_info['icon']}")

    # CrewAI 가이드
    st.markdown("### 💡 CrewAI 활용 팁")
    with st.expander("효과적인 협업 방법"):
        st.markdown("""
        **워크플로우 선택 가이드:**
        - **복잡한 연구**: 🔬 연구 분석 워크플로우
        - **글 작성**: ✍️ 콘텐츠 제작 워크플로우  
        - **문제 해결**: 🧩 문제 해결 워크플로우
        - **다국어 작업**: 🌐 번역 현지화 워크플로우
        
        **더 나은 결과를 위한 팁:**
        - 구체적이고 명확한 요청하기
        - 충분한 맥락 정보 제공하기
        - 원하는 결과물 형식 명시하기
        """)
    
    with st.expander("실행 모드 가이드"):
        st.markdown("""
        **순차적 실행:**
        - 에이전트들이 순서대로 작업
        - 이전 결과를 다음 에이전트가 활용
        - 안정적이고 예측 가능한 결과
        
        **계층적 실행:**
        - 관리자가 작업을 분배하고 조율
        - 더 복잡한 협업 가능
        - 창의적이고 다양한 접근
        """)

# 관리 버튼들
st.sidebar.markdown("---")
col1, col2 = st.sidebar.columns(2)

with col1:
    if st.button("💬 대화 초기화", use_container_width=True):
        st.session_state["crew_messages"] = []
        st.rerun()

with col2:
    if st.button("📊 상세 통계", use_container_width=True):
        if "crew_messages" in st.session_state:
            st.session_state["show_crew_stats"] = True
        else:
            st.sidebar.info("협업 기록이 없습니다.")

# 상세 통계 표시
if st.session_state.get("show_crew_stats", False):
    st.session_state["show_crew_stats"] = False
    
    with st.expander("📈 CrewAI 협업 통계", expanded=True):
        if "crew_messages" in st.session_state:
            messages = st.session_state["crew_messages"]
            
            # 워크플로우별 사용 통계
            workflow_stats = {}
            for msg in messages:
                if msg["role"] == "assistant" and msg.get("workflow"):
                    workflow_key = msg["workflow"]
                    if workflow_key not in workflow_stats:
                        workflow_stats[workflow_key] = 0
                    workflow_stats[workflow_key] += 1
            
            if workflow_stats:
                st.markdown("#### 🔄 워크플로우별 사용 빈도")
                for workflow_key, count in sorted(workflow_stats.items(), key=lambda x: x[1], reverse=True):
                    workflow_info = WORKFLOW_TYPES.get(workflow_key, {"icon": "🤖", "name": "알 수 없음"})
                    percentage = (count / len([m for m in messages if m["role"] == "assistant"])) * 100
                    st.write(f"{workflow_info['icon']} {workflow_info['name']}: {count}회 ({percentage:.1f}%)")

# 세션 상태 초기화
if "crew_messages" not in st.session_state:
    st.session_state["crew_messages"] = []