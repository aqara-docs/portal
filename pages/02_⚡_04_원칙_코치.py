import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
import random
from ollama import Client
import json
import re
from openai import OpenAI
import requests

load_dotenv()

# OLLAMA 클라이언트 설정
ollama_client = Client(host='http://localhost:11434')

# MySQL Database configuration
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# 페이지 설정
st.set_page_config(
    page_title="아카라라이프 원칙 코치",
    page_icon="��",
    layout="wide"
)

# 스타일 적용
st.markdown("""
<style>
    /* 기본 텍스트 스타일 */
    .stMarkdown, .stMarkdown p, .stText, .stText p {
        color: #E5E7EB !important;
        font-size: 1.1rem !important;
    }
    
    /* 헤더 스타일 */
    .main-header {
        font-size: 2.5rem;
        color: #E5E7EB;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    /* 서브헤더 스타일 */
    .stSubheader, h2, h3, h4 {
        color: #E5E7EB !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        margin: 1rem 0 !important;
    }
    
    /* 선택 박스 스타일 */
    .stSelectbox > div > div {
        background-color: #2D3748 !important;
        color: #E5E7EB !important;
        border: 1px solid #4A5568 !important;
    }
    
    .stSelectbox > label {
        color: #E5E7EB !important;
        font-size: 1.1rem !important;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        width: 100%;
        background-color: #3B82F6 !important;
        color: #FFFFFF !important;
        border: none !important;
        padding: 1rem !important;
        font-size: 1.1rem !important;
        margin: 0.5rem 0 !important;
        border-radius: 0.5rem !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        background-color: #2563EB !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* 모델 설명 카드 스타일 */
    .model-info-card {
        background-color: #2D3748;
        border-radius: 0.5rem;
        padding: 1.2rem;
        border-left: 4px solid #3B82F6;
        margin: 1rem 0;
    }
    
    .model-info-title {
        color: #E5E7EB;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .model-info-text {
        color: #E5E7EB;
        font-size: 1rem;
    }
    
    /* 캡션 스타일 */
    .stCaption {
        color: #E5E7EB !important;
        font-size: 0.9rem !important;
    }
    
    /* 구분선 스타일 */
    hr {
        border-color: #4A5568 !important;
        margin: 2rem 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'main'
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = None
if 'selected_subcategory' not in st.session_state:
    st.session_state.selected_subcategory = None

# 메인 헤더
st.markdown('<h1 class="main-header">아카라라이프 원칙 코치</h1>', unsafe_allow_html=True)

# LLM 모델 목록 업데이트
llm_models = {
    "DeepSeek 14B": "deepseek-r1:14b",   # 9.0GB - 중형 모델
    "DeepSeek 32B": "deepseek-r1:32b",   # 19GB - 중형 모델
    "DeepSeek 70B": "deepseek-r1:70b",   # 42GB - 대형 모델
    "Phi-4": "phi4:latest",              # 9.1GB - 중형 모델
    "Gemma 2": "gemma2:latest",          # 5.4GB - 소형 모델
    "LLaMA 3.1": "llama3.1:latest",      # 4.9GB - 소형 모델
    "Mistral": "mistral:latest",         # 4.1GB - 소형 모델
    "LLaMA 2": "llama2:latest",          # 3.8GB - 소형 모델
    "LLaMA 3.2": "llama3.2:latest",      # 2.0GB - 경량 모델
}

# 임베딩 모델은 별도로 지정
EMBEDDING_MODEL = "nomic-embed-text:latest"  # 274MB - 텍스트 임베딩 전용

def get_all_principles():
    """DB에서 모든 원칙과 세부원칙을 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                p.principle_id,
                p.principle_number,
                p.principle_title,
                sp.sub_principle_id,
                sp.sub_principle_number,
                sp.sub_principle_title,
                ai.action_item_text as description  # 실행 항목을 설명으로 사용
            FROM principles p
            JOIN sub_principles sp ON p.principle_id = sp.principle_id
            LEFT JOIN action_items ai ON sp.sub_principle_id = ai.sub_principle_id
            ORDER BY p.principle_number, sp.sub_principle_number
        """)
        principles = cursor.fetchall()
        cursor.close()
        conn.close()
        return principles
    except mysql.connector.Error as err:
        st.error(f"원칙 데이터 조회 중 오류 발생: {err}")
        return []

def clean_text(text):
    """HTML 태그를 제거하고 텍스트를 정제합니다."""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 앞뒤 공백 제거
    return text.strip()

def get_relevant_principles(category, subcategory, principles_data):
    """선택된 LLM을 사용하여 상황에 관련된 원칙들을 찾습니다."""
    
    # 세션 상태에서 선택된 모델 가져오기
    use_local_llm = st.session_state.get('use_local_llm', False)
    selected_model = st.session_state.get('selected_model')
    
    # 프롬프트 구성
    prompt = """
    당신은 아카라라이프의 원칙 코치입니다. 다음 상황에 가장 적합한 원칙들을 추천해주세요.

    상황: {} - {}

    아래 원칙들 중에서 이 상황에 가장 관련성이 높은 원칙 3-5개를 선택하고, 
    각 원칙이 이 상황에 어떻게 적용될 수 있는지 설명해주세요.
    
    원칙 목록:
    {}

    다음 JSON 형식으로만 응답해주세요:
    {{
        "selected_principles": [
            {{
                "principle_id": "<원칙ID>",
                "relevance_score": "<관련성 점수 1-10>",
                "application": "<이 원칙을 상황에 적용하는 방법 설명>"
            }}
        ],
        "coach_message": "<전반적인 조언 메시지>"
    }}
    """.format(
        category,
        subcategory,
        json.dumps(principles_data, ensure_ascii=False, indent=2)
    )

    try:
        if use_local_llm:
            # 로컬 LLM 사용
            response = analyze_with_local_llm(prompt, selected_model)
        else:
            # OpenAI 사용
            response = analyze_with_openai(prompt, selected_model)

        # JSON 응답 파싱
        if response:
            try:
                result = json.loads(response)
                # 응답 정제
                result['coach_message'] = clean_text(result['coach_message'])
                for principle in result['selected_principles']:
                    principle['application'] = clean_text(principle['application'])
                return result
            except json.JSONDecodeError:
                return create_default_response(category, subcategory, principles_data)
        else:
            raise ValueError("AI 모델로부터 응답을 받지 못했습니다")
            
    except Exception as e:
        st.error(f"AI 모델 실행 중 오류가 발생했습니다: {str(e)}")
        return create_default_response(category, subcategory, principles_data)

def analyze_with_openai(prompt, model):
    """OpenAI API를 사용한 분석"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 아카라라이프의 원칙 코치입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        if hasattr(response.choices[0].message, 'content'):
            return response.choices[0].message.content
        else:
            st.error("API 응답에 content가 없습니다.")
            return None
            
    except Exception as e:
        st.error(f"OpenAI API 호출 중 오류 발생: {str(e)}")
        return None

def analyze_with_local_llm(prompt, model):
    """로컬 LLM을 사용한 분석"""
    url = "http://localhost:11434/api/generate"
    
    data = {
        "model": model,
        "prompt": prompt,
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, json=data, stream=True)
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                json_response = json.loads(line)
                if 'response' in json_response:
                    full_response += json_response['response']
                if json_response.get('done', False):
                    break
        
        return full_response
        
    except Exception as e:
        st.error(f"로컬 LLM 호출 중 오류 발생: {str(e)}")
        return None

def create_default_response(category, subcategory, principles_data):
    """기본 응답을 생성합니다."""
    return {
        "selected_principles": [
            {
                "principle_id": p['principle_id'],
                "relevance_score": 7,
                "application": "이 원칙을 상황에 맞게 적용하세요."
            } for p in principles_data[:3]  # 처음 3개 원칙 선택
        ],
        "coach_message": f"{category}의 {subcategory} 상황에서는 위의 원칙들을 참고하여 문제를 해결해보세요."
    }

def show_main_view():
    st.subheader("AI 모델 선택")
    
    # OpenAI API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        st.stop()
    
    # AI 모델 선택 (기본값: gpt-4o-mini)
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
    
    with st.container():
        st.markdown("""
        <div style="margin-bottom: 2rem;">
            <p class="model-info-text">상황에 맞는 원칙을 추천받기 위한 AI 모델을 선택해주세요:</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            use_local_llm = st.checkbox("로컬 LLM 사용", value=False)
            st.session_state.use_local_llm = use_local_llm  # 세션 상태 저장
            
            if use_local_llm:
                llm_options = {
                    "DeepSeek 14B": "deepseek-r1:14b",
                    "DeepSeek 32B": "deepseek-r1:32b",
                    "DeepSeek 70B": "deepseek-r1:70b",
                    "Phi-4": "phi4:latest",
                    "LLaMA 3.1": "llama3.1:latest",
                    "Mistral": "mistral:latest"
                }
                selected_model = st.selectbox(
                    "로컬 LLM 모델 선택",
                    options=list(llm_options.keys()),
                    index=0
                )
                model_name = llm_options[selected_model]
            else:
                # OpenAI 모델명을 직접 사용
                model_name = MODEL_NAME
                st.info(f"OpenAI 모델 ({MODEL_NAME})을 사용합니다.")
            
            # 선택된 모델 세션 상태 저장
            st.session_state.selected_model = model_name
    
    # 구분선 추가
    st.markdown("<hr style='margin: 2rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
    
    # 기존의 카테고리 선택 부분
    st.subheader("어떤 상황에서 도움이 필요하신가요?")
    cols = st.columns(2)
    for i, (category, data) in enumerate(categories.items()):
        with cols[i % 2]:
            if st.button(f"{category}: {data['description']}", key=f"cat_{i}", 
                        help=data['description']):
                st.session_state.current_view = 'subcategory'
                st.session_state.selected_category = category
                # 선택된 모델명을 세션 상태에 저장 (수정된 부분)
                st.session_state.selected_model = model_name  # selected_model 대신 model_name 사용
                st.rerun()

# 세션 상태에 selected_model 추가
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "Mistral"

# 문제 카테고리 데이터
categories = {
    "의사결정": {
        "description": "중요한 결정을 내려야 할 때",
        "subcategories": [
            "복잡한 선택지 간 결정이 필요할 때",
            "불확실성이 높은 상황에서의 의사결정",
            "장기적 영향을 고려한 전략적 결정",
            "리스크와 보상의 균형이 필요한 결정",
            "시간 압박 하에서의 빠른 의사결정",
            "이해관계자 간 합의가 필요한 결정",
            "윤리적 고려사항이 포함된 의사결정",
            "자원 할당에 관한 의사결정",
            "데이터 기반 의사결정이 필요한 경우",
            "직관적 판단이 필요한 상황"
        ]
    },
    "팀 갈등": {
        "description": "팀 내 갈등이나 의견 충돌이 있을 때",
        "subcategories": [
            "역할과 책임에 대한 갈등",
            "의사소통 문제로 인한 갈등",
            "업무 스타일 차이로 인한 갈등",
            "성과 평가와 보상에 대한 갈등",
            "리더십 스타일에 대한 불만",
            "팀원 간 신뢰 부족",
            "업무 분배의 불균형",
            "변화에 대한 저항",
            "개인적 가치관 차이",
            "외부 압력으로 인한 팀 내 긴장"
        ]
    },
    "우선순위 설정": {
        "description": "여러 업무 중 우선순위를 정하기 어려울 때",
        "subcategories": [
            "긴급 vs 중요 업무의 우선순위",
            "다중 프로젝트 간 우선순위",
            "제한된 자원 상황에서의 선택",
            "단기 vs 장기 목표의 균형",
            "이해관계자별 요구사항 우선순위",
            "팀 내 업무 우선순위 조정",
            "위기 상황에서의 우선순위 재설정",
            "전략적 중요도에 따른 우선순위",
            "비용 대비 효과 기반 우선순위",
            "리스크 기반 우선순위 설정"
        ]
    },
    "혁신과 창의성": {
        "description": "새로운 아이디어나 접근법이 필요할 때",
        "subcategories": [
            "기존 방식의 혁신이 필요할 때",
            "새로운 시장/제품 개발이 필요할 때",
            "문제해결을 위한 창의적 접근이 필요할 때",
            "프로세스 개선이 필요할 때",
            "기술 혁신이 필요할 때",
            "조직 문화의 혁신이 필요할 때",
            "고객 경험 혁신이 필요할 때",
            "비즈니스 모델 혁신이 필요할 때",
            "서비스 혁신이 필요할 때",
            "협업 방식의 혁신이 필요할 때"
        ]
    },
    "실패와 회복": {
        "description": "실패 후 회복하고 교훈을 얻어야 할 때",
        "subcategories": [
            "프로젝트 실패 후 대응",
            "목표 미달성 상황 극복",
            "실수로 인한 신뢰 회복",
            "팀 사기 저하 극복",
            "재정적 손실 후 회복",
            "고객 불만 후 관계 회복",
            "기술적 실패 극복",
            "조직 변화 실패 후 대응",
            "시장 진입 실패 후 전략 수정",
            "인재 채용/육성 실패 극복"
        ]
    },
    "성과 향상": {
        "description": "개인 또는 팀의 성과를 향상시키고 싶을 때",
        "subcategories": [
            "개인 생산성 향상",
            "팀 성과 개선",
            "프로젝트 효율성 증대",
            "품질 향상",
            "비용 효율성 개선",
            "고객 만족도 향상",
            "매출/수익 증대",
            "업무 프로세스 최적화",
            "협업 효율성 향상",
            "학습 및 역량 개발"
        ]
    },
    "변화 관리": {
        "description": "조직이나 프로젝트의 변화를 관리해야 할 때",
        "subcategories": [
            "조직 구조 변경 관리",
            "새로운 시스템/기술 도입",
            "업무 프로세스 변경",
            "조직 문화 변화",
            "인수합병 후 통합",
            "사업 방향 전환",
            "급격한 성장 관리",
            "위기 상황에서의 변화",
            "세대 교체 관리",
            "시장 변화 대응"
        ]
    },
    "리더십": {
        "description": "리더로서 팀을 이끌거나 영향력을 발휘해야 할 때",
        "subcategories": [
            "비전과 방향 제시",
            "팀 동기부여",
            "성과 관리와 피드백",
            "권한 위임과 책임",
            "리더십 스타일 조정",
            "위기 상황 리더십",
            "변화 주도",
            "팀 역량 개발",
            "다양성 관리",
            "갈등 해결과 중재"
        ]
    }
}

def show_subcategory_view():
    # 뒤로가기 버튼
    if st.button("← 메인으로 돌아가기"):
        st.session_state.current_view = 'main'
        st.session_state.selected_category = None
        st.rerun()
    
    category = st.session_state.selected_category
    st.subheader(f"{category} - 구체적인 상황을 선택해주세요")
    
    for i, subcategory in enumerate(categories[category]['subcategories']):
        if st.button(subcategory, key=f"sub_{i}"):
            st.session_state.current_view = 'principles'
            st.session_state.selected_subcategory = subcategory
            st.rerun()

def show_principles_view():
    if st.button("← 이전으로 돌아가기"):
        st.session_state.current_view = 'subcategory'
        st.session_state.selected_subcategory = None
        st.rerun()
    
    category = st.session_state.selected_category
    subcategory = st.session_state.selected_subcategory
    
    st.subheader(f"'{subcategory}'에 도움이 되는 원칙들")
    
    # 모든 원칙 데이터 가져오기
    principles_data = get_all_principles()
    
    # 스피너 메시지를 컨테이너로 감싸서 스타일 적용
    with st.container():
        with st.spinner(f'🤖 {st.session_state.selected_model} AI가 상황에 맞는 원칙들을 분석하고 있습니다...'):
            result = get_relevant_principles(category, subcategory, principles_data)
    
    if result:
        # 코치 메시지 표시
        st.markdown(f"""
        <div class="coach-message">
            <div class="coach-title">🧠 원칙 코치의 조언</div>
            <div class="coach-text">{result['coach_message']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 선택된 원칙들 표시
        for principle in result['selected_principles']:
            principle_data = next(
                (p for p in principles_data if p['principle_id'] == principle['principle_id']), 
                None
            )
            
            if principle_data:
                st.markdown("---")
                
                # 원칙 제목 표시
                st.markdown(f"""
                <div class="principle-title">
                    <span class="principle-number">{principle_data['principle_number']}.{principle_data['sub_principle_number']}</span>
                    {principle_data['sub_principle_title']}
                </div>
                """, unsafe_allow_html=True)
                
                # 원칙 설명
                if principle_data.get('description'):
                    st.markdown(f"""
                    <div class="principle-description">
                        {principle_data['description']}
                    </div>
                    """, unsafe_allow_html=True)
                
                # 적용 방법
                st.markdown(f"""
                <div class="principle-application">
                    <strong>적용 방법:</strong><br>
                    {principle['application']}
                </div>
                """, unsafe_allow_html=True)
                
                # 관련성 점수
                relevance = int(principle['relevance_score'])
                st.progress(relevance / 10)
                st.caption(f"관련성 점수: {relevance}/10")
    else:
        st.error("원칙을 분석하는 중 문제가 발생했습니다.")

# 현재 뷰에 따라 화면 표시
if st.session_state.current_view == 'main':
    show_main_view()
elif st.session_state.current_view == 'subcategory':
    show_subcategory_view()
elif st.session_state.current_view == 'principles':
    show_principles_view() 