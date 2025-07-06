import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import base64
import io
from PIL import Image
import requests
import json
from datetime import datetime
import re
import traceback
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import time

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 페이지 설정
st.set_page_config(
    page_title="⚡ 전기/IoT 회로도 & 개념도 생성기", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 멀티 에이전트 시스템 클래스들
class ExpertAgent:
    """전문가 에이전트 기본 클래스"""
    
    def __init__(self, name, expertise, system_prompt):
        self.name = name
        self.expertise = expertise
        self.system_prompt = system_prompt
        self.conversation_history = []
    
    async def analyze_question(self, question, context=""):
        """질문을 분석하고 전문 분야에 대한 답변 생성"""
        try:
            full_prompt = f"""
            {self.system_prompt}
            
            사용자 질문: {question}
            컨텍스트: {context}
            
            당신의 전문 분야({self.expertise})에 관해 답변해주세요.
            답변은 다음 형식으로 제공해주세요:
            1. 핵심 답변
            2. 기술적 세부사항
            3. 권장사항
            4. 추가 고려사항
            """
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            self.conversation_history.append({
                "question": question,
                "answer": answer,
                "timestamp": datetime.now()
            })
            
            return answer
            
        except Exception as e:
            return f"오류 발생: {str(e)}"
    
    def needs_drawing(self, question, answer):
        """도면 생성이 필요한지 판단"""
        drawing_keywords = [
            "회로도", "배선도", "도면", "다이어그램", "시스템 구성도", 
            "배치도", "연결도", "토폴로지", "아키텍처", "설계도"
        ]
        
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        for keyword in drawing_keywords:
            if keyword in question_lower or keyword in answer_lower:
                return True
        
        return False

class IoTExpert(ExpertAgent):
    """IoT 전문가 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="IoT 전문가",
            expertise="IoT 시스템 설계 및 구현",
            system_prompt="""
            당신은 IoT(Internet of Things) 전문가입니다. 
            다음 분야에 대한 전문 지식을 가지고 있습니다:
            - IoT 디바이스 및 센서 기술
            - 무선 통신 프로토콜 (WiFi, Bluetooth, Zigbee, LoRa, NB-IoT)
            - IoT 플랫폼 및 클라우드 서비스
            - 데이터 수집 및 분석
            - IoT 보안 및 프라이버시
            - 엣지 컴퓨팅 및 펌웨어
            - IoT 시스템 아키텍처 설계
            
            항상 실용적이고 구현 가능한 솔루션을 제시하세요.
            """
        )

class AIExpert(ExpertAgent):
    """AI 전문가 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="AI 전문가",
            expertise="인공지능 및 머신러닝",
            system_prompt="""
            당신은 AI(인공지능) 전문가입니다.
            다음 분야에 대한 전문 지식을 가지고 있습니다:
            - 머신러닝 알고리즘 및 모델
            - 딥러닝 및 신경망
            - 컴퓨터 비전 및 이미지 처리
            - 자연어 처리 (NLP)
            - 강화학습 및 최적화
            - AI 하드웨어 및 엣지 AI
            - AI 윤리 및 책임있는 AI
            - AI 시스템 통합 및 배포
            
            최신 AI 트렌드와 실용적인 적용 방안을 제시하세요.
            """
        )

class ElectricalExpert(ExpertAgent):
    """전기 전문가 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="전기 전문가",
            expertise="전기 시스템 설계 및 안전",
            system_prompt="""
            당신은 전기 시스템 전문가입니다.
            다음 분야에 대한 전문 지식을 가지고 있습니다:
            - 전기회로 설계 및 분석
            - 전력 시스템 및 분배
            - 전기 안전 및 보호 장치
            - 전기 코드 및 규격 (NEC, IEC, KS)
            - 전기 측정 및 계측
            - 전기 기기 및 장비
            - 전기 시공 및 유지보수
            - 전기 에너지 효율성
            
            항상 안전을 최우선으로 하는 솔루션을 제시하세요.
            """
        )

class LightingExpert(ExpertAgent):
    """조명 전문가 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="조명 전문가",
            expertise="조명 시스템 설계 및 제어",
            system_prompt="""
            당신은 조명 시스템 전문가입니다.
            다음 분야에 대한 전문 지식을 가지고 있습니다:
            - LED 조명 기술 및 제어
            - 조명 설계 및 조도 계산
            - 스마트 조명 시스템
            - 조명 제어 프로토콜 (DALI, DMX, 0-10V)
            - 색온도 및 색 렌더링 지수
            - 에너지 효율 조명 솔루션
            - 인간 중심 조명 (HCL)
            - 조명 자동화 및 IoT 통합
            
            사용자 경험과 에너지 효율성을 고려한 솔루션을 제시하세요.
            """
        )

class ProjectManager(ExpertAgent):
    """프로젝트 매니저 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="프로젝트 매니저",
            expertise="프로젝트 관리 및 통합",
            system_prompt="""
            당신은 프로젝트 매니저입니다.
            다음 분야에 대한 전문 지식을 가지고 있습니다:
            - 프로젝트 계획 및 일정 관리
            - 예산 관리 및 비용 분석
            - 리스크 관리 및 품질 보증
            - 팀 관리 및 커뮤니케이션
            - 공급업체 관리 및 계약
            - 프로젝트 생명주기 관리
            - 변경 관리 및 통합
            - 프로젝트 성공 지표 및 평가
            
            실현 가능하고 효율적인 프로젝트 방안을 제시하세요.
            """
        )

class MultiAgentSystem:
    """멀티 에이전트 시스템 관리자"""
    
    def __init__(self):
        self.agents = {
            "iot": IoTExpert(),
            "ai": AIExpert(),
            "electrical": ElectricalExpert(),
            "lighting": LightingExpert(),
            "pm": ProjectManager()
        }
        self.conversation_history = []
    
    async def process_question(self, question, selected_experts=None):
        """질문을 처리하고 관련 전문가들의 답변을 수집"""
        if selected_experts is None:
            selected_experts = list(self.agents.keys())
        
        results = {}
        
        # 각 전문가의 답변 수집
        for expert_key in selected_experts:
            if expert_key in self.agents:
                agent = self.agents[expert_key]
                answer = await agent.analyze_question(question)
                results[expert_key] = {
                    "agent": agent,
                    "answer": answer,
                    "needs_drawing": agent.needs_drawing(question, answer)
                }
        
        # 대화 기록 저장
        self.conversation_history.append({
            "question": question,
            "answers": results,
            "timestamp": datetime.now()
        })
        
        return results
    
    def get_integrated_answer(self, results):
        """여러 전문가의 답변을 통합하여 종합적인 답변 생성"""
        try:
            integrated_prompt = """
            다음은 여러 전문가들의 답변입니다. 이들을 종합하여 
            사용자에게 일관되고 실용적인 종합 답변을 제공해주세요.
            
            """
            
            for expert_key, result in results.items():
                agent = result["agent"]
                answer = result["answer"]
                integrated_prompt += f"\n{agent.name}의 답변:\n{answer}\n"
            
            integrated_prompt += """
            
            위 답변들을 종합하여 다음 형식으로 정리해주세요:
            1. 핵심 요약
            2. 기술적 권장사항
            3. 구현 방안
            4. 주의사항
            5. 다음 단계
            """
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": integrated_prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"통합 답변 생성 중 오류 발생: {str(e)}"

# 멀티 에이전트 시스템 인스턴스
multi_agent_system = MultiAgentSystem()

def perform_perplexity_search(query, debug_mode=False):
    """Perplexity API를 사용한 검색 수행"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        st.error("Perplexity API 키가 설정되지 않았습니다.")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = "https://api.perplexity.ai/chat/completions"
    
    data = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in visual arts and image analysis. Provide detailed, accurate information about visual elements, styles, and artistic references. Always include sources when available."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    if debug_mode:
        st.write("=== Perplexity API 요청 디버그 정보 ===")
        st.write("URL:", url)
        st.write("Headers:", {k: v if k != 'Authorization' else f'Bearer {api_key[:8]}...' for k, v in headers.items()})
        st.write("Request Data:", json.dumps(data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if debug_mode:
            st.write("\n=== Perplexity API 응답 디버그 정보 ===")
            st.write(f"Status Code: {response.status_code}")
            st.write("Response Headers:", dict(response.headers))
            try:
                response_data = response.json()
                st.write("Response JSON:", json.dumps(response_data, indent=2, ensure_ascii=False))
            except:
                st.write("Raw Response:", response.text)
        
        if response.status_code != 200:
            error_msg = f"Perplexity API 오류 (상태 코드: {response.status_code})"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f"\n오류 내용: {error_data['error']}"
            except:
                error_msg += f"\n응답 내용: {response.text}"
            st.error(error_msg)
            return None
        
        result = response.json()
        
        # 응답에서 텍스트와 출처 추출
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            
            # 출처 정보가 있는 경우 별도로 표시
            sources = []
            if 'sources' in result['choices'][0]['message']:
                sources = result['choices'][0]['message']['sources']
            
            # 출처 정보가 본문에 포함된 경우 (URL이나 참조 형식으로)
            source_section = "\n\n**출처:**"
            if sources:
                source_section += "\n" + "\n".join([f"- {source}" for source in sources])
            elif "[" in content and "]" in content:  # 본문에 참조 형식으로 포함된 경우
                citations = re.findall(r'\[(.*?)\]', content)
                if citations:
                    source_section += "\n" + "\n".join([f"- {citation}" for citation in citations])
            
            # URL 형식의 출처 추출
            urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s)"\']', content)
            if urls:
                if source_section == "\n\n**출처:**":
                    source_section += "\n" + "\n".join([f"- {url}" for url in urls])
            
            # 출처 정보가 있는 경우에만 추가
            if source_section != "\n\n**출처:**":
                return content + source_section
            return content
            
        return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"Perplexity API 요청 실패: {str(e)}")
        if debug_mode:
            st.error(f"상세 오류: {traceback.format_exc()}")
        return None
    except Exception as e:
        st.error(f"예상치 못한 오류 발생: {str(e)}")
        if debug_mode:
            st.error(f"상세 오류: {traceback.format_exc()}")
        return None

def search_for_reference_info(prompt, search_type="circuit"):
    """프롬프트에 대한 참조 정보 검색"""
    search_queries = {
        "circuit": f"""
        다음 전기회로도에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. 회로 구성 요소와 기호 (저항, 콘덴서, 인덕터, 다이오드, 트랜지스터 등)
        2. 표준 전기회로도 기호와 표기법 (IEC, IEEE, ANSI 표준)
        3. 회로 연결 방식과 배선 패턴
        4. 전압, 전류, 저항 값 표시 방법
        5. 유사한 회로도 예시나 참조 자료
        6. 회로도 작성 규칙과 표준
        7. 각 구성 요소의 정확한 기호와 표기법
        """,
        "wiring": f"""
        다음 전기 배선도에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. 전선 종류와 규격 (AWG, mm²)
        2. 스위치, 콘센트, 조명 기구의 표준 기호
        3. 배선 경로와 케이블 트레이 배치
        4. 단자함과 접속 박스 위치
        5. 전기 안전 규격과 코드 (NEC, IEC)
        6. 접지 시스템과 보호 장치
        7. 전압 레벨과 위상 표시
        """,
        "iot": f"""
        다음 IoT 시스템에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. IoT 디바이스와 센서 종류
        2. 무선 통신 프로토콜 (WiFi, Bluetooth, Zigbee, LoRa)
        3. 게이트웨이와 클라우드 연결 방식
        4. 데이터 플로우와 프로토콜 (MQTT, HTTP, CoAP)
        5. 전원 관리와 배터리 수명
        6. 보안 프로토콜과 암호화
        7. IoT 플랫폼과 서비스
        """,
        "automation": f"""
        다음 자동화 제어 시스템에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. PLC와 제어 시스템 종류
        2. 센서와 액추에이터 인터페이스
        3. 제어 로직과 래더 다이어그램
        4. HMI와 SCADA 시스템
        5. 안전 회로와 인터락 시스템
        6. 통신 프로토콜 (Modbus, Profinet, EtherCAT)
        7. 산업용 네트워크 토폴로지
        """,
        "power": f"""
        다음 전력 시스템에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. 전력 분전반과 차단기 종류
        2. 전력 계량기와 CT/PT
        3. 접지 시스템과 보호 접지
        4. 전압 레벨과 위상 구성
        5. 전력 품질과 보호 장치
        6. UPS와 백업 전원 시스템
        7. 전력 분배 토폴로지
        """,
        "control": f"""
        다음 제어 시스템에 대한 정확한 참조 정보를 찾아주세요:
        {prompt}
        
        다음 정보를 포함해주세요:
        1. 제어 시스템 아키텍처
        2. 피드백 루프와 제어 알고리즘
        3. 센서와 액추에이터 인터페이스
        4. 제어 신호와 통신 프로토콜
        5. 안전 시스템과 인터락
        6. 제어 패널과 HMI
        7. 시스템 통합과 인터페이스
        """
    }
    
    query = search_queries.get(search_type, search_queries["circuit"])
    return perform_perplexity_search(query)

def generate_enhanced_prompt(original_prompt, reference_info, search_type="general"):
    """참조 정보를 바탕으로 향상된 프롬프트 생성"""
    enhancement_prompt = f"""
    다음 원본 프롬프트와 웹 검색을 통해 얻은 참조 정보를 바탕으로, 
    더 구체적이고 현실적인 이미지 생성 프롬프트를 만들어주세요.

    원본 프롬프트: {original_prompt}
    
    참조 정보:
    {reference_info}
    
    다음 형식으로 응답해주세요:
    1. 향상된 프롬프트 (구체적이고 상세한 설명)
    2. 주요 시각적 요소 (색상, 조명, 구도, 스타일)
    3. 기술적 세부사항 (해상도, 품질, 효과)
    4. 참조 출처 요약
    
    프롬프트는 영어로 작성하고, 구체적이고 시각적으로 명확해야 합니다.
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": enhancement_prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"프롬프트 향상 중 오류 발생: {str(e)}")
        return original_prompt

def generate_image_with_dalle(prompt, model="dall-e-3", size="1024x1024", quality="standard", style="vivid"):
    """OpenAI DALL-E를 사용하여 이미지 생성"""
    try:
        response = openai.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1
        )
        
        # 이미지 URL에서 이미지 다운로드
        image_url = response.data[0].url
        image_response = requests.get(image_url)
        image = Image.open(io.BytesIO(image_response.content))
        
        return {
            'image': image,
            'url': image_url,
            'model': model,
            'prompt': prompt,
            'created_at': datetime.now()
        }
    except Exception as e:
        st.error(f"DALL-E 이미지 생성 중 오류 발생: {str(e)}")
        return None

def generate_image_with_claude(prompt, model="claude-3-5-sonnet-20241022"):
    """Anthropic Claude Artifacts를 사용하여 이미지 생성"""
    try:
        # Claude Artifacts를 사용한 이미지 생성
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"다음 프롬프트로 이미지를 생성해주세요: {prompt}"
                        }
                    ]
                }
            ]
        )
        
        # Claude Artifacts에서 이미지 추출
        if response.content and len(response.content) > 0:
            for content in response.content:
                if hasattr(content, 'type') and content.type == 'image':
                    # 이미지 데이터 처리
                    image_data = content.source.data
                    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
                    
                    return {
                        'image': image,
                        'url': None,  # Claude는 URL을 제공하지 않음
                        'model': model,
                        'prompt': prompt,
                        'created_at': datetime.now()
                    }
        
        st.warning("Claude에서 이미지를 생성할 수 없습니다. 텍스트 응답만 받았습니다.")
        return None
        
    except Exception as e:
        st.error(f"Claude 이미지 생성 중 오류 발생: {str(e)}")
        return None

def save_image_to_session(image_data):
    """생성된 이미지를 세션에 저장"""
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = []
    
    st.session_state.generated_images.append(image_data)

def download_image(image, filename):
    """이미지를 다운로드 가능한 형태로 변환"""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    return img_byte_arr

def main():
    st.title("⚡ 전기/IoT 전문 기술 컨설팅 & 도면 생성기")
    st.markdown("IoT, AI, 전기, 조명 전문가들과 프로젝트 매니저가 협력하여 기술적 문제를 해결하고 필요한 도면을 생성합니다!")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["🤖 전문가 컨설팅", "⚡ 도면 생성"])
    
    with tab1:
        st.header("🤖 전문가 컨설팅 시스템")
        
        # 전문가 선택
        st.subheader("👥 전문가 선택")
        col_experts = st.columns(5)
        
        with col_experts[0]:
            iot_selected = st.checkbox("🌐 IoT 전문가", value=True, key="iot_expert")
        with col_experts[1]:
            ai_selected = st.checkbox("🧠 AI 전문가", value=True, key="ai_expert")
        with col_experts[2]:
            electrical_selected = st.checkbox("⚡ 전기 전문가", value=True, key="electrical_expert")
        with col_experts[3]:
            lighting_selected = st.checkbox("💡 조명 전문가", value=True, key="lighting_expert")
        with col_experts[4]:
            pm_selected = st.checkbox("📊 프로젝트 매니저", value=True, key="pm_expert")
        
        # 선택된 전문가들
        selected_experts = []
        if iot_selected:
            selected_experts.append("iot")
        if ai_selected:
            selected_experts.append("ai")
        if electrical_selected:
            selected_experts.append("electrical")
        if lighting_selected:
            selected_experts.append("lighting")
        if pm_selected:
            selected_experts.append("pm")
        
        if not selected_experts:
            st.warning("최소 한 명의 전문가를 선택해주세요!")
            return
        
        # 질문 입력
        st.subheader("❓ 질문하기")
        question = st.text_area(
            "기술적 질문이나 프로젝트 요구사항을 입력하세요",
            placeholder="예: 스마트 홈 IoT 시스템을 구축하려고 하는데, 어떤 센서와 통신 방식을 사용해야 할까요?",
            height=120,
            key="expert_question"
        )
        
        # 컨텍스트 입력 (선택사항)
        context = st.text_area(
            "추가 컨텍스트 (선택사항)",
            placeholder="예: 100평 아파트, 예산 500만원, 6개월 내 완료",
            height=80,
            key="expert_context"
        )
        
        # 질문 제출
        col_submit1, col_submit2 = st.columns([1, 1])
        
        with col_submit1:
            if st.button("🤖 전문가들에게 질문하기", type="primary", use_container_width=True, key="ask_experts"):
                if not question.strip():
                    st.error("질문을 입력해주세요!")
                    return
                
                # 진행 상황 표시
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 비동기 처리를 위한 래퍼 함수
                    def run_async_question():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(
                                multi_agent_system.process_question(question, selected_experts)
                            )
                        finally:
                            loop.close()
                    
                    # 스레드에서 실행
                    with ThreadPoolExecutor() as executor:
                        future = executor.submit(run_async_question)
                        
                        # 진행 상황 업데이트
                        for i in range(5):
                            progress_bar.progress((i + 1) * 20)
                            status_text.text(f"전문가들이 답변을 준비하고 있습니다... ({i + 1}/5)")
                            time.sleep(0.5)
                        
                        results = future.result()
                    
                    # 결과 표시
                    st.success("✅ 전문가들의 답변이 준비되었습니다!")
                    
                    # 각 전문가별 답변 표시
                    st.subheader("👥 전문가별 답변")
                    
                    for expert_key, result in results.items():
                        agent = result["agent"]
                        answer = result["answer"]
                        needs_drawing = result["needs_drawing"]
                        
                        with st.expander(f"💬 {agent.name}의 답변", expanded=True):
                            st.markdown(answer)
                            
                            if needs_drawing:
                                st.info("🎨 이 답변과 관련된 도면이 필요할 수 있습니다. '도면 생성' 탭에서 관련 도면을 생성해보세요!")
                    
                    # 통합 답변 생성
                    st.subheader("📋 종합 답변")
                    with st.spinner("전문가들의 답변을 종합하고 있습니다..."):
                        integrated_answer = multi_agent_system.get_integrated_answer(results)
                        st.markdown(integrated_answer)
                    
                    # 도면 생성 제안
                    drawing_needed = any(result["needs_drawing"] for result in results.values())
                    if drawing_needed:
                        st.info("🎨 도면 생성이 필요합니다! '도면 생성' 탭으로 이동하여 관련 도면을 생성해보세요.")
                
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")
                    st.error(traceback.format_exc())
        
        with col_submit2:
            if st.button("🗑️ 대화 기록 초기화", use_container_width=True, key="reset_conversation"):
                multi_agent_system.conversation_history = []
                for agent in multi_agent_system.agents.values():
                    agent.conversation_history = []
                st.success("✅ 대화 기록이 초기화되었습니다!")
                st.rerun()
        
        # 대화 기록 표시
        if multi_agent_system.conversation_history:
            st.subheader("📚 대화 기록")
            for i, conversation in enumerate(reversed(multi_agent_system.conversation_history)):
                with st.expander(f"대화 {len(multi_agent_system.conversation_history) - i} - {conversation['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.write(f"**질문:** {conversation['question']}")
                    
                    for expert_key, result in conversation['answers'].items():
                        agent = result["agent"]
                        answer = result["answer"]
                        st.write(f"**{agent.name}:** {answer[:200]}...")
    
    with tab2:
        # 기존 도면 생성 기능
        #st.header("⚡ 도면 생성")
        
        # 사이드바 설정
        with st.sidebar:
            st.header("⚙️ 도면 생성 설정")
            
            # 웹 검색 기능 활성화
            enable_web_search = st.checkbox(
                "🌐 웹 검색 기반 생성",
                value=True,
                help="Perplexity API를 사용하여 웹에서 최신 기술 정보와 표준을 검색하고 정확한 도면을 생성합니다"
            )
            
            if enable_web_search:
                st.subheader("🔍 검색 설정")
                search_type = st.selectbox(
                    "검색 유형",
                    ["circuit", "wiring", "iot", "automation", "power", "control"],
                    format_func=lambda x: {
                        "circuit": "전기회로도",
                        "wiring": "배선도",
                        "iot": "IoT 시스템",
                        "automation": "자동화 시스템",
                        "power": "전력 시스템",
                        "control": "제어 시스템"
                    }[x],
                    help="검색할 기술 정보의 유형을 선택하세요"
                )
                
                debug_mode = st.checkbox(
                    "디버그 모드",
                    help="API 요청/응답 정보를 자세히 표시합니다"
                )
            
            # 모델 선택
            model_choice = st.selectbox(
                "사용할 AI 모델",
                ["OpenAI DALL-E 3", "OpenAI DALL-E 2", "Anthropic Claude"],
                help="도면 생성을 위한 AI 모델을 선택하세요"
            )
            
            # DALL-E 설정
            if "DALL-E" in model_choice:
                st.subheader("DALL-E 설정")
                
                # 모델 버전
                dalle_model = st.selectbox(
                    "DALL-E 버전",
                    ["dall-e-3", "dall-e-2"] if model_choice == "OpenAI DALL-E 3" else ["dall-e-2"],
                    help="DALL-E 모델 버전을 선택하세요"
                )
                
                # 이미지 크기
                image_size = st.selectbox(
                    "도면 크기",
                    ["1024x1024", "1792x1024", "1024x1792"] if dalle_model == "dall-e-3" else ["256x256", "512x512", "1024x1024"],
                    help="생성할 도면의 크기를 선택하세요"
                )
                
                # 품질 설정 (DALL-E 3만)
                if dalle_model == "dall-e-3":
                    image_quality = st.selectbox(
                        "도면 품질",
                        ["standard", "hd"],
                        help="도면 품질을 선택하세요 (HD는 더 높은 품질이지만 더 많은 크레딧을 사용합니다)"
                    )
                else:
                    image_quality = "standard"
                
                # 스타일 설정 (DALL-E 3만)
                if dalle_model == "dall-e-3":
                    image_style = st.selectbox(
                        "도면 스타일",
                        ["vivid", "natural"],
                        help="도면 스타일을 선택하세요"
                    )
                else:
                    image_style = "vivid"
            
            # Claude 설정
            elif model_choice == "Anthropic Claude":
                st.subheader("Claude 설정")
                claude_model = st.selectbox(
                    "Claude 모델",
                    ["claude-3-5-sonnet-20241022", "claude-3-sonnet-20240229"],
                    help="Claude 모델을 선택하세요"
                )
            
            st.markdown("---")
            
            # 도면 템플릿
            st.subheader("📋 도면 템플릿")
            template_choice = st.selectbox(
                "템플릿 선택",
                ["직접 입력", "전기회로도", "배선도", "IoT 시스템", "자동화 제어", "전력 분배", "센서 네트워크", "통신 시스템"]
            )
            
            if template_choice != "직접 입력":
                templates = {
                    "전기회로도": "전문적인 전기회로도, 표준 기호 사용, 깔끔한 선과 연결, 정확한 구성 요소 기호, 고해상도, 공학 도면 스타일",
                    "배선도": "전기 배선도, 전선 경로, 스위치, 콘센트, 조명 배치, 단자함 위치, 안전 규격 준수",
                    "IoT 시스템": "IoT 디바이스 네트워크, 센서 연결, 게이트웨이, 클라우드 연결, 데이터 플로우, 무선 통신",
                    "자동화 제어": "PLC 제어 시스템, 센서 입력, 액추에이터 출력, 제어 로직, 안전 회로, HMI 인터페이스",
                    "전력 분배": "전력 분전반, 차단기, 퓨즈, 전력 계량기, 접지 시스템, 전압 레벨 표시",
                    "센서 네트워크": "다양한 센서 배치, 데이터 수집 노드, 무선 통신 링크, 배터리 전원, 환경 모니터링",
                    "통신 시스템": "이더넷, RS485, Modbus, CAN 버스, 무선 통신, 프로토콜 변환기, 네트워크 토폴로지"
                }
                st.text_area("템플릿 프롬프트", templates[template_choice], height=100, key="sidebar_template_prompt_1")
        
        # 메인 컨텐츠
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("⚡ 도면 생성")
            
            # 프롬프트 입력
            if template_choice == "직접 입력":
                prompt = st.text_area(
                    "도면 설명을 입력하세요",
                    placeholder="예: 3상 전력 분전반 배선도, 220V 콘센트 10개, 조명 스위치 5개",
                    height=120,
                    help="생성하고 싶은 도면에 대해 자세히 설명해주세요",
                    key="main_prompt_input"
                )
            else:
                base_prompt = st.text_area(
                    "기본 프롬프트",
                    placeholder="예: 공장 자동화 시스템, 스마트 홈 IoT 네트워크 등",
                    height=80,
                    key="base_prompt_input"
                )
                template_prompt = st.sidebar.text_area("템플릿 프롬프트", templates[template_choice], height=100, key="sidebar_template_prompt_2")
                prompt = f"{base_prompt}, {template_prompt}" if base_prompt else template_prompt
            
            # 추가 옵션
            with st.expander("🔧 추가 옵션"):
                col_a, col_b = st.columns(2)
                
                with col_a:
                    negative_prompt = st.text_area(
                        "제외할 요소",
                        placeholder="예: 색상, 장식 요소, 불필요한 텍스트",
                        height=80,
                        help="도면에서 제외하고 싶은 요소를 입력하세요",
                        key="negative_prompt_input"
                    )
                
                with col_b:
                    style_guide = st.text_area(
                        "스타일 가이드",
                        placeholder="예: 단순화된 도면, 상세한 도면, 3D 렌더링",
                        height=80,
                        help="원하는 도면 스타일을 추가로 지정하세요",
                        key="style_guide_input"
                    )
            
            # 웹 검색 결과 표시
            if enable_web_search and prompt.strip():
                with st.expander("🔍 웹 검색 결과", expanded=True):
                    with st.spinner("웹에서 참조 정보를 검색하고 있습니다..."):
                        reference_info = search_for_reference_info(prompt, search_type)
                        
                        if reference_info:
                            st.markdown("### 📚 참조 정보")
                            st.markdown(reference_info)
                            
                            # 향상된 프롬프트 생성
                            with st.spinner("참조 정보를 바탕으로 프롬프트를 향상하고 있습니다..."):
                                enhanced_prompt = generate_enhanced_prompt(prompt, reference_info, search_type)
                                
                                st.markdown("### ✨ 향상된 프롬프트")
                                st.text_area(
                                    "향상된 프롬프트",
                                    enhanced_prompt,
                                    height=150,
                                    help="웹 검색 결과를 바탕으로 향상된 프롬프트입니다",
                                    key="enhanced_prompt_display"
                                )
                                
                                # 향상된 프롬프트 사용 여부
                                use_enhanced = st.checkbox(
                                    "향상된 프롬프트 사용",
                                    value=True,
                                    help="체크하면 웹 검색 결과를 바탕으로 향상된 프롬프트를 사용합니다",
                                    key="use_enhanced_prompt"
                                )
                                
                                if use_enhanced:
                                    prompt = enhanced_prompt
                        else:
                            st.warning("웹 검색 결과를 가져올 수 없습니다. 원본 프롬프트를 사용합니다.")
            
            # 최종 프롬프트 구성
            final_prompt = prompt
            if negative_prompt:
                final_prompt += f" (제외: {negative_prompt})"
            if style_guide:
                final_prompt += f" (스타일: {style_guide})"
            
            # 생성 버튼
            col_gen1, col_gen2, col_gen3 = st.columns([1, 1, 1])
            
            with col_gen1:
                if st.button("⚡ 도면 생성", type="primary", use_container_width=True, key="generate_button"):
                    if not final_prompt.strip():
                        st.error("프롬프트를 입력해주세요!")
                        return
                    
                    with st.spinner("AI가 도면을 생성하고 있습니다..."):
                        if "DALL-E" in model_choice:
                            result = generate_image_with_dalle(
                                final_prompt,
                                dalle_model,
                                image_size,
                                image_quality,
                                image_style
                            )
                        else:  # Claude
                            result = generate_image_with_claude(final_prompt, claude_model)
                        
                        if result:
                            save_image_to_session(result)
                            st.success("✅ 도면이 생성되었습니다!")
                            st.rerun()
            
            with col_gen2:
                if st.button("🔄 다시 생성", use_container_width=True, key="regenerate_button"):
                    if not final_prompt.strip():
                        st.error("프롬프트를 입력해주세요!")
                        return
                    
                    with st.spinner("AI가 새로운 도면을 생성하고 있습니다..."):
                        if "DALL-E" in model_choice:
                            result = generate_image_with_dalle(
                                final_prompt,
                                dalle_model,
                                image_size,
                                image_quality,
                                image_style
                            )
                        else:  # Claude
                            result = generate_image_with_claude(final_prompt, claude_model)
                        
                        if result:
                            save_image_to_session(result)
                            st.success("✅ 새로운 도면이 생성되었습니다!")
                            st.rerun()
            
            with col_gen3:
                if st.button("🗑️ 초기화", use_container_width=True, key="reset_button"):
                    if 'generated_images' in st.session_state:
                        del st.session_state.generated_images
                    st.success("✅ 초기화되었습니다!")
                    st.rerun()
        
        with col2:
            st.header("📊 생성 정보")
            
            if 'generated_images' in st.session_state and st.session_state.generated_images:
                latest_image = st.session_state.generated_images[-1]
                
                st.info(f"""
                **모델:** {latest_image['model']}
                **생성 시간:** {latest_image['created_at'].strftime('%Y-%m-%d %H:%M:%S')}
                **프롬프트:** {latest_image['prompt'][:100]}...
                """)
                
                if latest_image['url']:
                    st.markdown(f"[원본 도면]({latest_image['url']})")
        
        # 생성된 이미지 표시
        if 'generated_images' in st.session_state and st.session_state.generated_images:
            st.header("📋 생성된 도면들")
            
            # 이미지 갤러리
            num_images = len(st.session_state.generated_images)
            cols = st.columns(min(3, num_images))
            
            for idx, image_data in enumerate(st.session_state.generated_images):
                col_idx = idx % 3
                with cols[col_idx]:
                    st.subheader(f"도면 {idx + 1}")
                    st.image(image_data['image'], use_container_width=True)
                    
                    # 이미지 정보
                    with st.expander(f"📋 도면 {idx + 1} 정보"):
                        st.write(f"**모델:** {image_data['model']}")
                        st.write(f"**생성 시간:** {image_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write(f"**프롬프트:** {image_data['prompt']}")
                        
                        if image_data['url']:
                            st.markdown(f"[원본 도면]({image_data['url']})")
                        
                        # 다운로드 버튼
                        img_bytes = download_image(image_data['image'], f"technical_drawing_{idx + 1}.png")
                        st.download_button(
                            label=f"📥 도면 {idx + 1} 다운로드",
                            data=img_bytes,
                            file_name=f"technical_drawing_{idx + 1}.png",
                            mime="image/png",
                            use_container_width=True,
                            key=f"download_button_{idx}"
                        )
                    
                    # 개별 삭제 버튼
                    if st.button(f"🗑️ 도면 {idx + 1} 삭제", key=f"delete_{idx}", use_container_width=True):
                        st.session_state.generated_images.pop(idx)
                        st.success(f"도면 {idx + 1}이 삭제되었습니다!")
                        st.rerun()
        
        # 사용 팁
        with st.expander("💡 사용 팁"):
            st.markdown("""
            ### 웹 검색 기반 도면 생성의 장점:
            
            **1. 정확성 향상**
            - 최신 기술 표준과 규격 정보 반영
            - 정확한 기호와 표기법 사용
            
            **2. 전문성 증가**
            - 웹 검색을 통한 전문 기술 정보 제공
            - 산업 표준과 안전 규격 준수
            
            **3. 참조 출처 제공**
            - 생성된 도면의 기술적 근거 확인 가능
            - 신뢰할 수 있는 기술 자료 기반 생성
            
            ### 더 좋은 결과를 위한 팁:
            
            **1. 구체적인 검색 유형 선택**
            - 전기회로도: 표준 전기 기호와 회로 구성 요소
            - 배선도: 전선 규격, 안전 규격, 배치 정보
            - IoT 시스템: 통신 프로토콜, 센서, 플랫폼
            - 자동화 시스템: PLC, 제어 로직, 안전 회로
            - 전력 시스템: 분전반, 보호 장치, 접지
            - 제어 시스템: 피드백 루프, 인터페이스
            
            **2. 검색 결과 활용**
            - 제공된 기술 정보 검토
            - 향상된 프롬프트 사용 권장
            
            **3. 반복 개선**
            - 검색 결과를 바탕으로 프롬프트 수정
            - 여러 번의 시도로 최적 결과 도출
            
            ### ⚡ 전기회로도 생성 팁:
            
            **표준 기호와 규칙:**
            - **저항**: 지그재그 선 또는 직사각형 기호
            - **콘덴서**: 두 개의 평행선
            - **인덕터**: 나선형 기호
            - **다이오드**: 화살표 기호
            - **트랜지스터**: 삼각형과 선 조합
            - **전원**: +, - 기호 또는 배터리 기호
            
            **회로도 작성 규칙:**
            - **깔끔한 선**: 직선과 직각 연결
            - **표준 기호**: IEC, IEEE, ANSI 표준 준수
            - **값 표시**: 저항값, 전압값 명확히 표시
            - **노드 표시**: 연결점 명확히 표시
            - **레이블**: 각 구성 요소에 식별자 부여
            
            **추천 프롬프트 예시:**
            - "LED와 저항을 사용한 간단한 직렬 회로, 5V 전원, 220옴 저항"
            - "555 타이머 IC를 사용한 발진 회로, LED 깜빡임 회로"
            - "오피앰프를 사용한 반전 증폭기 회로, 741 IC"
            
            ### 🔌 배선도 생성 팁:
            
            **배선 구성 요소:**
            - **전선**: AWG 규격, 색상 코드
            - **스위치**: 단극, 3방향, 4방향
            - **콘센트**: 120V, 240V, GFCI, AFCI
            - **조명**: LED, 형광등, 할로겐
            - **차단기**: 단극, 2극, 3극
            
            **안전 규격:**
            - **NEC 코드**: 미국 전기 안전 규격
            - **IEC 표준**: 국제 전기 표준
            - **접지**: 보호 접지, 기능 접지
            - **보호 장치**: 퓨즈, 차단기, 서지 보호
            
            **추천 프롬프트 예시:**
            - "3상 전력 분전반 배선도, 220V 콘센트 10개, 조명 스위치 5개"
            - "스마트 홈 배선도, WiFi 스위치, 자동화 콘센트"
            - "공장 전력 분배 시스템, 모터 제어 패널"
            
            ### 🌐 IoT 시스템 생성 팁:
            
            **IoT 구성 요소:**
            - **센서**: 온도, 습도, 압력, 모션, 가스
            - **액추에이터**: 릴레이, 모터, LED, 디스플레이
            - **게이트웨이**: WiFi, Bluetooth, Zigbee, LoRa
            - **클라우드**: AWS IoT, Azure IoT, Google Cloud IoT
            - **플랫폼**: Home Assistant, Node-RED, ThingsBoard
            
            **통신 프로토콜:**
            - **MQTT**: 경량 메시징 프로토콜
            - **HTTP/HTTPS**: REST API 통신
            - **CoAP**: 제한된 환경용 프로토콜
            - **Modbus**: 산업용 통신 프로토콜
            
            **추천 프롬프트 예시:**
            - "스마트 홈 IoT 네트워크, 온도/습도 센서, 스마트 조명"
            - "공장 IoT 모니터링 시스템, 센서 네트워크, 데이터 수집"
            - "스마트 시티 IoT 인프라, 환경 모니터링, 교통 제어"
            
            ### 🤖 자동화 제어 시스템 팁:
            
            **제어 시스템 구성:**
            - **PLC**: 프로그래머블 로직 컨트롤러
            - **HMI**: 휴먼 머신 인터페이스
            - **SCADA**: 감시 제어 및 데이터 수집
            - **센서**: 온도, 압력, 레벨, 위치
            - **액추에이터**: 밸브, 모터, 히터, 펌프
            
            **제어 로직:**
            - **래더 다이어그램**: PLC 프로그래밍
            - **펑션 블록**: 고급 제어 기능
            - **순차 제어**: 단계별 프로세스 제어
            - **피드백 제어**: PID 제어 알고리즘
            
            **추천 프롬프트 예시:**
            - "PLC 기반 자동화 제어 시스템, 센서 입력, 모터 제어"
            - "스마트 팩토리 자동화, 로봇 제어, 품질 검사"
            - "빌딩 자동화 시스템, HVAC 제어, 보안 시스템"
            """)
        
        # 모델별 특징
        with st.expander("🤖 모델별 특징"):
            st.markdown("""
            ### OpenAI DALL-E 3
            - **장점:** 매우 높은 품질, 정확한 기호 표시, 세밀한 디테일
            - **특징:** 1024x1024, 1792x1024, 1024x1792 크기 지원
            - **적합한 용도:** 고품질 전기회로도, 상세한 배선도, 정밀한 시스템 도면
            
            ### OpenAI DALL-E 2
            - **장점:** 빠른 생성, 다양한 스타일 지원
            - **특징:** 256x256, 512x512, 1024x1024 크기 지원
            - **적합한 용도:** 빠른 프로토타이핑, 기본 회로도, 개념도
            
            ### Anthropic Claude
            - **장점:** 창의적인 해석, 복잡한 시스템 이해
            - **특징:** 텍스트와 도면 생성 통합
            - **적합한 용도:** 복잡한 IoT 시스템, 통합 제어 시스템, 개념적 아키텍처
            
            ### Perplexity API (웹 검색)
            - **장점:** 실시간 기술 정보 수집, 최신 표준 자료 제공
            - **특징:** 다양한 기술 출처의 신뢰할 수 있는 정보
            - **적합한 용도:** 표준 준수 도면, 최신 기술 반영, 정확한 기호 사용
            """)

if __name__ == "__main__":
    main() 