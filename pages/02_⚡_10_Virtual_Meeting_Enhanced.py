import streamlit as st
from openai import OpenAI
import time
import threading
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Any
import uuid
from dotenv import load_dotenv
import pandas as pd
from io import StringIO
import PyPDF2
import docx
import tempfile
from dataclasses import dataclass
import asyncio
import queue
import random

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Virtual Meeting Enhanced - AI 가상 회의",
    page_icon="🎭",
    layout="wide"
)

@dataclass
class Persona:
    id: str
    name: str
    role: str
    prompt: str
    personality: str
    expertise: str
    speaking_style: str
    is_moderator: bool = False
    
    def __post_init__(self):
        if not self.prompt:
            self.prompt = self.generate_default_prompt()
    
    def generate_default_prompt(self) -> str:
        return f"""당신은 {self.name}입니다. 
        역할: {self.role}
        전문 분야: {self.expertise}
        성격: {self.personality}
        말하는 스타일: {self.speaking_style}
        
        회의에서 당신의 전문성을 바탕으로 건설적인 의견을 제시하세요.
        다른 참가자들의 의견을 경청하고 존중하며, 토론을 발전시키는 방향으로 참여하세요."""

@dataclass
class Message:
    timestamp: datetime
    persona_id: str
    persona_name: str
    content: str
    is_human_input: bool = False
    is_moderator: bool = False

class VirtualMeeting:
    def __init__(self):
        self.personas: List[Persona] = []
        self.messages: List[Message] = []
        self.meeting_topic = ""
        self.meeting_duration = 30  # 분
        self.start_time = None
        self.is_active = False
        self.uploaded_files_content = ""
        self.current_speaker_index = 0
        self.conversation_round = 0
        self.max_rounds = 10
        self.auto_mode = False
        self.speaking_speed = 3  # 초
        self.last_message_time = None
        
    def add_persona(self, persona: Persona) -> bool:
        if len(self.personas) < 10:
            self.personas.append(persona)
            return True
        return False
    
    def remove_persona(self, persona_id: str):
        self.personas = [p for p in self.personas if p.id != persona_id]
    
    def get_moderator(self) -> Persona:
        for persona in self.personas:
            if persona.is_moderator:
                return persona
        return None
    
    def get_non_moderator_personas(self) -> List[Persona]:
        return [p for p in self.personas if not p.is_moderator]
    
    def add_message(self, persona_id: str, content: str, is_human_input: bool = False) -> Message:
        persona = next((p for p in self.personas if p.id == persona_id), None)
        if persona:
            message = Message(
                timestamp=datetime.now(),
                persona_id=persona_id,
                persona_name=persona.name,
                content=content,
                is_human_input=is_human_input,
                is_moderator=persona.is_moderator
            )
            self.messages.append(message)
            self.last_message_time = datetime.now()
            return message
        return None
    
    def get_next_speaker(self) -> Persona:
        non_moderator_personas = self.get_non_moderator_personas()
        if not non_moderator_personas:
            return None
        
        current_persona = non_moderator_personas[self.current_speaker_index % len(non_moderator_personas)]
        return current_persona
    
    def advance_speaker(self):
        non_moderator_personas = self.get_non_moderator_personas()
        if non_moderator_personas:
            self.current_speaker_index += 1
            if self.current_speaker_index % len(non_moderator_personas) == 0:
                self.conversation_round += 1
    
    def is_time_to_speak(self) -> bool:
        if not self.last_message_time:
            return True
        # total_seconds()를 사용하여 정확한 시간 계산
        time_diff = (datetime.now() - self.last_message_time).total_seconds()
        return time_diff >= self.speaking_speed
    
    def should_continue(self) -> bool:
        if not self.is_active:
            return False
        if self.conversation_round >= self.max_rounds:
            return False
        if self.start_time:
            elapsed_time = (datetime.now() - self.start_time).total_seconds()
            if elapsed_time > (self.meeting_duration * 60):
                return False
        return True
    
    def get_time_until_next_speak(self) -> float:
        """다음 발언까지 남은 시간 (초) 계산"""
        if not self.last_message_time:
            return 0.0
        elapsed = (datetime.now() - self.last_message_time).total_seconds()
        remaining = max(0.0, self.speaking_speed - elapsed)
        return remaining

def initialize_session_state():
    """세션 상태 초기화"""
    if 'virtual_meeting' not in st.session_state:
        st.session_state.virtual_meeting = VirtualMeeting()
        
        # 기본 사회자 페르소나 생성
        moderator = Persona(
            id="moderator_001",
            name="사회자 김진행",
            role="회의 사회자",
            prompt="""당신은 전문적인 회의 사회자입니다. 
            회의의 흐름을 원활하게 이끌고, 참가자들의 의견을 적절히 조율하며, 
            주제에서 벗어나지 않도록 안내하는 역할을 합니다.
            간결하고 명확하게 말하며, 모든 참가자가 발언할 기회를 갖도록 합니다.
            
            회의 진행 시 다음과 같은 역할을 수행합니다:
            - 회의 시작 시 참가자 소개 및 주제 안내
            - 발언 순서 조정 및 시간 관리
            - 토론이 격화되거나 주제에서 벗어날 때 중재
            - 중간 정리 및 결론 도출
            
            말하는 스타일: 정중하고 명확하며 간결하게, 때로는 유머를 섞어 분위기를 부드럽게 만듭니다.""",
            personality="차분하고 공정하며 전문적, 적절한 유머 감각",
            expertise="회의 진행, 토론 조율, 의견 정리, 갈등 중재",
            speaking_style="정중하고 명확하며 간결한 말투, 때로는 친근한 농담",
            is_moderator=True
        )
        st.session_state.virtual_meeting.add_persona(moderator)
    
    # 자동 모드 관련 세션 상태 추가
    if 'auto_mode_last_run' not in st.session_state:
        st.session_state.auto_mode_last_run = datetime.now()
    
    if 'auto_mode_running' not in st.session_state:
        st.session_state.auto_mode_running = False
    
    # 기본 페르소나들 추가 (예시)
    if len(st.session_state.virtual_meeting.personas) == 1:  # 사회자만 있는 경우
        sample_personas = [
            Persona(
                id="ceo_001",
                name="CEO 박성공",
                role="최고경영자",
                prompt="",
                personality="비전을 제시하고 리더십을 발휘하는 성격",
                expertise="전략 경영, 의사결정, 리더십",
                speaking_style="확신에 차고 카리스마 있는 말투"
            ),
            Persona(
                id="cto_001", 
                name="CTO 이기술",
                role="최고기술책임자",
                prompt="",
                personality="논리적이고 분석적인 성격",
                expertise="기술 전략, 개발, 혁신",
                speaking_style="데이터와 근거를 바탕으로 한 차분한 말투"
            ),
            Persona(
                id="cmo_001",
                name="CMO 김마케팅",
                role="최고마케팅책임자", 
                prompt="",
                personality="창의적이고 소통을 중시하는 성격",
                expertise="마케팅 전략, 브랜딩, 고객 분석",
                speaking_style="열정적이고 창의적인 아이디어를 제시하는 말투"
            )
        ]
        
        for persona in sample_personas:
            st.session_state.virtual_meeting.add_persona(persona)

def extract_text_from_file(uploaded_file) -> str:
    """업로드된 파일에서 텍스트 추출"""
    try:
        file_type = uploaded_file.type
        content = ""
        
        if file_type == "text/plain":
            content = str(uploaded_file.read(), "utf-8")
        elif file_type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                content += page.extract_text()
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(uploaded_file)
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
        elif file_type == "text/csv":
            df = pd.read_csv(uploaded_file)
            content = df.to_string()
        else:
            content = "지원하지 않는 파일 형식입니다."
            
        return content
    except Exception as e:
        return f"파일 읽기 오류: {str(e)}"

def generate_ai_response(persona: Persona, conversation_history: str, meeting_topic: str, file_content: str, round_number: int) -> str:
    """AI 응답 생성"""
    try:
        # OpenAI API 키 검증
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
            raise ValueError("OpenAI API 키가 올바르지 않습니다. .env 파일에서 OPENAI_API_KEY를 확인해주세요.")
        
        client = OpenAI(api_key=openai_key)
        
        # 라운드에 따른 맥락 조정
        round_context = ""
        if round_number == 1:
            round_context = "이번이 첫 번째 발언입니다. 자신을 한 문장으로 간단히 소개한 후 주제에 대한 의견을 제시하세요."
        elif round_number <= 3:
            round_context = "회의가 진행 중입니다. 다른 참가자들의 의견을 참고하여 자신의 관점을 추가하세요. 자기소개는 하지 마세요."
        elif round_number <= 6:
            round_context = "토론이 깊어지고 있습니다. 구체적인 해결책이나 대안을 제시해보세요. 자기소개는 하지 마세요."
        else:
            round_context = "토론이 마무리 단계입니다. 지금까지의 논의를 정리하거나 결론을 향해 나아가세요. 자기소개는 하지 마세요."
        
        system_prompt = f"""
        {persona.prompt}
        
        당신의 정보:
        - 이름: {persona.name}
        - 역할: {persona.role}
        - 성격: {persona.personality}
        - 전문 분야: {persona.expertise}
        - 말하는 스타일: {persona.speaking_style}
        
        회의 주제: {meeting_topic}
        현재 라운드: {round_number}
        
        {round_context}
        
        참고 자료: {file_content[:1500] if file_content else "없음"}
        
        중요한 지침:
        - 첫 번째 라운드가 아니라면 자기소개를 하지 마세요
        - "안녕하세요, 저는 ○○입니다" 같은 인사말은 첫 번째 라운드에서만 사용하세요
        - 바로 주제에 대한 의견이나 분석을 시작하세요
        - 자연스럽고 사람다운 말투로 2-3문장 정도로 작성해주세요
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"대화 내용:\n{conversation_history}\n\n위 내용을 바탕으로 응답해주세요."}
            ],
            max_tokens=300,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[AI 응답 생성 오류: {str(e)}]"

def format_conversation_history(messages: List[Message], last_n: int = 15) -> str:
    """대화 히스토리 포맷팅"""
    recent_messages = messages[-last_n:] if len(messages) > last_n else messages
    history = ""
    for msg in recent_messages:
        history += f"{msg.persona_name}: {msg.content}\n"
    return history

def stream_response(text: str):
    """스트리밍 타이핑 효과"""
    import time
    words = text.split()
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(0.1)  # 타이핑 속도 조절 (더 느리게)

def display_message(message: Message, is_latest: bool = False):
    """메시지 표시"""
    avatar = "🎯" if message.is_moderator else "🎭"
    if message.is_human_input:
        avatar = "👤"
    
    with st.chat_message(
        "assistant" if not message.is_human_input else "human",
        avatar=avatar
    ):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{message.persona_name}**")
            # 최신 메시지만 타이핑 효과 적용
            if is_latest and not message.is_human_input:
                st.write_stream(stream_response(message.content))
            else:
                st.write(message.content)
        with col2:
            st.caption(message.timestamp.strftime('%H:%M:%S'))
            if message.is_human_input:
                st.caption("👤 인간 개입")

def run_conversation_round(meeting: VirtualMeeting) -> bool:
    """한 라운드의 대화 실행"""
    if not meeting.should_continue():
        return False
    
    current_persona = meeting.get_next_speaker()
    if not current_persona:
        return False
    
    # 대화 히스토리 생성
    conversation_history = format_conversation_history(meeting.messages)
    
    # AI 응답 생성
    response = generate_ai_response(
        current_persona,
        conversation_history,
        meeting.meeting_topic,
        meeting.uploaded_files_content,
        meeting.conversation_round + 1
    )
    
    # 메시지 추가
    meeting.add_message(current_persona.id, response)
    
    # 다음 발언자로 이동
    meeting.advance_speaker()
    
    return True

def preset_personas() -> List[Dict]:
    """미리 설정된 페르소나 목록"""
    return [
        {
            "name": "전략기획자 이전략",
            "role": "전략기획팀장",
            "personality": "분석적이고 체계적인 사고를 하는 성격",
            "expertise": "전략 수립, 사업 분석, 시장 조사",
            "speaking_style": "논리적이고 체계적인 설명을 하는 말투"
        },
        {
            "name": "디자이너 박창의",
            "role": "UX/UI 디자이너",
            "personality": "창의적이고 사용자 중심적 사고를 하는 성격",
            "expertise": "사용자 경험, 인터페이스 디자인, 디자인 시스템",
            "speaking_style": "감성적이고 직관적인 표현을 사용하는 말투"
        },
        {
            "name": "개발자 김코딩",
            "role": "시니어 개발자",
            "personality": "논리적이고 문제 해결 지향적인 성격",
            "expertise": "소프트웨어 개발, 시스템 아키텍처, 기술 최적화",
            "speaking_style": "간결하고 기술적인 용어를 사용하는 말투"
        },
        {
            "name": "영업팀장 최세일즈",
            "role": "영업팀장",
            "personality": "적극적이고 목표 지향적인 성격",
            "expertise": "고객 관리, 영업 전략, 협상",
            "speaking_style": "열정적이고 설득력 있는 말투"
        },
        {
            "name": "재무담당자 정캐시",
            "role": "재무팀장",
            "personality": "신중하고 정확성을 중시하는 성격",
            "expertise": "재무 분석, 예산 관리, 투자 평가",
            "speaking_style": "정확한 수치와 데이터를 기반으로 한 신중한 말투"
        }
    ]

def main():
    st.title("🎭 Virtual Meeting Enhanced - AI 가상 회의")
    
    # 세션 상태 초기화
    initialize_session_state()
    meeting = st.session_state.virtual_meeting
    
    # 사이드바 - 회의 설정
    with st.sidebar:
        st.header("🎯 회의 설정")
        
        # 회의 주제
        meeting.meeting_topic = st.text_area(
            "회의 주제",
            value=meeting.meeting_topic,
            help="토론할 주제를 입력하세요",
            placeholder="예: 신제품 출시 전략 수립"
        )
        
        # 회의 시간 설정
        meeting.meeting_duration = st.slider(
            "회의 시간 (분)",
            min_value=5,
            max_value=120,
            value=meeting.meeting_duration
        )
        
        # 최대 라운드 설정
        meeting.max_rounds = st.slider(
            "최대 대화 라운드",
            min_value=3,
            max_value=20,
            value=meeting.max_rounds
        )
        
        # 발언 속도 설정
        meeting.speaking_speed = st.slider(
            "발언 간격 (초)",
            min_value=1,
            max_value=10,
            value=meeting.speaking_speed,
            help="자동 모드에서 발언 간격을 조절합니다"
        )
        
        st.divider()
        
        # 파일 업로드
        st.header("📁 참고 자료 업로드")
        uploaded_files = st.file_uploader(
            "파일을 업로드하세요",
            type=['txt','md','pdf', 'docx', 'csv'],
            accept_multiple_files=True,
            help="페르소나들이 참고할 자료를 업로드하세요"
        )
        
        if uploaded_files:
            if st.button("📄 파일 처리"):
                with st.spinner("파일을 처리 중입니다..."):
                    combined_content = ""
                    for file in uploaded_files:
                        content = extract_text_from_file(file)
                        combined_content += f"\n--- {file.name} ---\n{content}\n"
                    
                    meeting.uploaded_files_content = combined_content
                    st.success(f"✅ {len(uploaded_files)}개 파일이 처리되었습니다!")
            
            # 파일이 처리된 경우 미리보기 표시
            if meeting.uploaded_files_content:
                st.subheader("📖 파일 내용")
                st.text_area(
                    "처리된 내용 미리보기",
                    value=meeting.uploaded_files_content[:300] + "..." if len(meeting.uploaded_files_content) > 300 else meeting.uploaded_files_content,
                    height=80,
                    disabled=True,
                    key="file_preview"
                )
        
        st.divider()
        
        # 회의 제어
        st.header("🎮 회의 제어")
        
        if not meeting.is_active:
            if st.button("🚀 회의 시작", type="primary"):
                if meeting.meeting_topic and len(meeting.personas) > 1:
                    meeting.is_active = True
                    meeting.start_time = datetime.now()
                    meeting.conversation_round = 0
                    meeting.current_speaker_index = 0
                    
                    # 사회자 인사말 추가
                    moderator = meeting.get_moderator()
                    if moderator:
                        opening_message = f"안녕하세요, 오늘 '{meeting.meeting_topic}'에 대해 논의하겠습니다. 모든 참가자들의 활발한 참여를 부탁드립니다."
                        meeting.add_message(moderator.id, opening_message)
                    
                    st.success("✅ 회의가 시작되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 회의 주제와 최소 2명의 페르소나가 필요합니다.")
        else:
            # 회의 진행 상태 표시
            if meeting.start_time:
                elapsed = datetime.now() - meeting.start_time
                remaining = meeting.meeting_duration * 60 - elapsed.seconds
                st.info(f"⏰ 경과: {elapsed.seconds//60}분 | 남은시간: {max(0, remaining//60)}분")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏸️ 회의 중단"):
                    meeting.is_active = False
                    st.success("⏸️ 회의가 중단되었습니다.")
                    st.rerun()
            with col2:
                if st.button("🔄 회의 재시작"):
                    meeting.is_active = True
                    st.success("▶️ 회의가 재시작되었습니다.")
                    st.rerun()
            
            # 자동 모드 토글
            meeting.auto_mode = st.toggle("🤖 자동 진행 모드", value=meeting.auto_mode)
            if meeting.auto_mode:
                st.info("🔄 자동 모드가 활성화되었습니다.")
        
        # 회의 종료 조건
        if meeting.is_active:
            st.divider()
            st.header("📊 진행 상황")
            progress = min(meeting.conversation_round / meeting.max_rounds, 1.0)
            st.progress(progress, text=f"라운드 진행: {meeting.conversation_round}/{meeting.max_rounds}")
    
    # 메인 영역
    tab1, tab2, tab3, tab4 = st.tabs(["👥 페르소나 관리", "💬 실시간 회의", "📊 회의 현황", "📝 회의록"])
    
    with tab1:
        st.header("👥 페르소나 관리")
        
        # 프리셋 페르소나 추가
        st.subheader("🎯 프리셋 페르소나")
        preset_options = preset_personas()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_preset = st.selectbox(
                "프리셋 선택",
                options=range(len(preset_options)),
                format_func=lambda x: f"{preset_options[x]['name']} ({preset_options[x]['role']})",
                index=None,
                placeholder="프리셋을 선택하세요"
            )
        with col2:
            if selected_preset is not None and st.button("➕ 프리셋 추가"):
                preset = preset_options[selected_preset]
                new_persona = Persona(
                    id=str(uuid.uuid4()),
                    name=preset['name'],
                    role=preset['role'],
                    prompt="",  # 자동 생성됨
                    personality=preset['personality'],
                    expertise=preset['expertise'],
                    speaking_style=preset['speaking_style']
                )
                
                if meeting.add_persona(new_persona):
                    st.success(f"✅ {preset['name']} 페르소나가 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("❌ 최대 10개의 페르소나만 추가할 수 있습니다.")
        
        st.divider()
        
        # 커스텀 페르소나 추가
        with st.expander("➕ 커스텀 페르소나 추가", expanded=False):
            with st.form("add_persona"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("이름", placeholder="예: 김전문")
                    role = st.text_input("역할", placeholder="예: 마케팅 담당자")
                    expertise = st.text_input("전문 분야", placeholder="예: 디지털 마케팅, SNS 전략")
                with col2:
                    personality = st.text_area("성격/특성", placeholder="예: 창의적이고 도전적인 성격")
                    speaking_style = st.text_input("말하는 스타일", placeholder="예: 열정적이고 구체적인 말투")
                
                prompt = st.text_area(
                    "커스텀 프롬프트 (선택사항)",
                    help="비워두면 자동으로 생성됩니다",
                    placeholder="이 페르소나의 특별한 행동 패턴이나 전문성을 정의하는 프롬프트를 입력하세요"
                )
                
                if st.form_submit_button("페르소나 추가", type="primary"):
                    if name and role:
                        new_persona = Persona(
                            id=str(uuid.uuid4()),
                            name=name,
                            role=role,
                            prompt=prompt,
                            personality=personality,
                            expertise=expertise,
                            speaking_style=speaking_style
                        )
                        
                        if meeting.add_persona(new_persona):
                            st.success(f"✅ {name} 페르소나가 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("❌ 최대 10개의 페르소나만 추가할 수 있습니다.")
                    else:
                        st.error("⚠️ 이름과 역할은 필수 항목입니다.")
        
        # 기존 페르소나 목록
        st.subheader("현재 페르소나 목록")
        for i, persona in enumerate(meeting.personas):
            icon = "🎯" if persona.is_moderator else "🎭"
            
            with st.expander(f"{icon} {persona.name} ({persona.role})"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**전문 분야:** {persona.expertise}")
                    st.write(f"**성격:** {persona.personality}")
                    st.write(f"**말하는 스타일:** {persona.speaking_style}")
                    
                    # 프롬프트 표시 (expander 대신 toggle 사용)
                    show_prompt = st.toggle(
                        "🤖 AI 프롬프트 보기", 
                        key=f"show_prompt_{persona.id}"
                    )
                    if show_prompt:
                        st.text_area(
                            "프롬프트",
                            value=persona.prompt,
                            height=100,
                            disabled=True,
                            key=f"prompt_view_{persona.id}"
                        )
                
                with col2:
                    if not persona.is_moderator:
                        if st.button("🗑️ 삭제", key=f"delete_{persona.id}"):
                            meeting.remove_persona(persona.id)
                            st.success(f"✅ {persona.name} 페르소나가 삭제되었습니다.")
                            st.rerun()
                    else:
                        st.info("🔒 사회자")
    
    with tab2:
        st.header("💬 실시간 회의")
        
        if not meeting.is_active:
            st.info("ℹ️ 회의를 시작하려면 사이드바에서 '회의 시작' 버튼을 클릭하세요.")
            
            # 회의 시작 전 미리보기
            if meeting.meeting_topic:
                st.subheader("📋 회의 정보")
                st.write(f"**주제:** {meeting.meeting_topic}")
                st.write(f"**예상 시간:** {meeting.meeting_duration}분")
                st.write(f"**참여자:** {len(meeting.personas)}명")
                st.write(f"**참여자 목록:** {', '.join([p.name for p in meeting.personas])}")
        else:
            # 회의 진행 상황
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                elapsed_time = datetime.now() - meeting.start_time
                st.metric("⏰ 경과 시간", f"{elapsed_time.seconds // 60}분")
            with col2:
                st.metric("🔄 현재 라운드", f"{meeting.conversation_round + 1}/{meeting.max_rounds}")
            with col3:
                st.metric("💬 총 메시지", len(meeting.messages))
            with col4:
                next_speaker = meeting.get_next_speaker()
                st.metric("🎤 다음 발언자", next_speaker.name if next_speaker else "없음")
            
            # 사회자 개입
            st.subheader("🎯 사회자 개입")
            moderator = meeting.get_moderator()
            if moderator:
                with st.form("moderator_form"):
                    human_input = st.text_area(
                        f"{moderator.name}로서 발언",
                        help="사회자 역할로 회의 방향을 제시하거나 의견을 추가하세요",
                        placeholder="예: 지금까지의 의견을 정리해보겠습니다..."
                    )
                    
                    if st.form_submit_button("💬 발언하기", type="primary"):
                        if human_input:
                            meeting.add_message(moderator.id, human_input, is_human_input=True)
                            st.success("✅ 발언이 추가되었습니다!")
                            st.rerun()
            
            # 대화 진행 컨트롤
            st.subheader("🗣️ 대화 진행")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("➡️ 다음 발언", type="primary"):
                    with st.spinner("🤖 AI가 응답을 생성 중입니다..."):
                        success = run_conversation_round(meeting)
                        if success:
                            st.rerun()
                        else:
                            st.info("ℹ️ 회의가 종료되었거나 더 이상 진행할 수 없습니다.")
            
            with col2:
                if st.button("⏭️ 라운드 스킵"):
                    meeting.conversation_round += 1
                    st.info("⏭️ 라운드가 스킵되었습니다.")
                    st.rerun()
            
            with col3:
                if st.button("🔚 회의 종료"):
                    meeting.is_active = False
                    # 사회자 마무리 발언
                    if moderator:
                        closing_message = "오늘 회의를 마치겠습니다. 모든 분들의 활발한 참여에 감사드립니다."
                        meeting.add_message(moderator.id, closing_message)
                    st.success("✅ 회의가 종료되었습니다.")
                    st.rerun()
            
            # 자동 진행 모드 상태 표시만 (실행은 메인 함수 끝에서)
            if meeting.auto_mode:
                st.success(f"🤖 자동 진행 모드 활성화 - {meeting.speaking_speed}초마다 자동 발언")
                
                # 자동 진행 상태 표시 - 정확한 시간 계산
                col1, col2 = st.columns([3, 1])
                with col1:
                    if meeting.last_message_time:
                        time_since_last = (datetime.now() - meeting.last_message_time).total_seconds()
                        remaining_time = max(0, meeting.speaking_speed - time_since_last)
                        progress_value = min(1.0, (meeting.speaking_speed - remaining_time) / meeting.speaking_speed)
                        
                        if remaining_time <= 0:
                            st.success("⚡ 다음 발언 실행 중...")
                        else:
                            st.progress(
                                progress_value,
                                text=f"다음 발언까지 {remaining_time:.1f}초 남음"
                            )
                    else:
                        st.info("🚀 첫 발언 준비 중...")
                
                with col2:
                    if st.button("⏸️ 자동모드 중단"):
                        meeting.auto_mode = False
                        st.info("자동 모드가 중단되었습니다.")
                        st.rerun()
            
            # 대화 내용 표시 (항상 최신 상태로)
            st.subheader("💭 대화 내용")
            
            # 대화 컨테이너 (스크롤 가능)
            chat_container = st.container()
            with chat_container:
                if meeting.messages:
                    # 모든 메시지 표시 (최신 메시지만 타이핑 효과)
                    for i, message in enumerate(meeting.messages):
                        is_latest = (i == len(meeting.messages) - 1)  # 마지막 메시지인지 확인
                        display_message(message, is_latest=is_latest)
                    
                    # 최신 메시지 강조
                    st.info(f"💬 총 메시지: {len(meeting.messages)}개 | 마지막 발언: {meeting.messages[-1].timestamp.strftime('%H:%M:%S')}")
                else:
                    st.info("💭 아직 대화가 시작되지 않았습니다.")
                
                # 자동 스크롤을 위한 앵커
                st.write("")
    
    with tab3:
        st.header("📊 회의 현황")
        
        if meeting.messages:
            # 회의 개요
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💬 총 발언 수", len(meeting.messages))
            with col2:
                human_messages = sum(1 for msg in meeting.messages if msg.is_human_input)
                st.metric("👤 인간 개입", human_messages)
            with col3:
                if meeting.start_time:
                    duration = datetime.now() - meeting.start_time
                    st.metric("⏱️ 회의 시간", f"{duration.seconds//60}분 {duration.seconds%60}초")
            
            # 발언 통계
            speaker_stats = {}
            for message in meeting.messages:
                if message.persona_name in speaker_stats:
                    speaker_stats[message.persona_name] += 1
                else:
                    speaker_stats[message.persona_name] = 1
            
            # 발언 횟수 차트
            if speaker_stats:
                st.subheader("👤 발언자별 통계")
                df_stats = pd.DataFrame(list(speaker_stats.items()), columns=['발언자', '발언 횟수'])
                df_stats = df_stats.sort_values('발언 횟수', ascending=True)
                st.bar_chart(df_stats.set_index('발언자'))
                
                # 발언 분포 파이 차트
                try:
                    import plotly.express as px
                    fig = px.pie(df_stats, values='발언 횟수', names='발언자', title='발언 분포')
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.info("📊 Plotly가 설치되지 않아 파이 차트를 표시할 수 없습니다.")
            
            # 시간대별 활동
            st.subheader("📈 시간대별 활동")
            if len(meeting.messages) > 1:
                time_data = []
                for i, message in enumerate(meeting.messages):
                    time_data.append({
                        '순서': i + 1,
                        '시간': message.timestamp.strftime('%H:%M:%S'),
                        '발언자': message.persona_name,
                        '내용 길이': len(message.content)
                    })
                
                df_time = pd.DataFrame(time_data)
                st.line_chart(df_time.set_index('순서')['내용 길이'])
            
            # 최근 활동
            st.subheader("🕐 최근 활동")
            recent_messages = meeting.messages[-10:] if len(meeting.messages) > 10 else meeting.messages
            for message in reversed(recent_messages):
                icon = "🎯" if message.is_moderator else "🎭"
                if message.is_human_input:
                    icon = "👤"
                
                st.write(
                    f"{icon} **{message.timestamp.strftime('%H:%M:%S')}** - "
                    f"{message.persona_name}: {message.content[:100]}..."
                )
        else:
            st.info("ℹ️ 아직 회의 메시지가 없습니다.")
    
    with tab4:
        st.header("📝 회의록")
        
        if meeting.messages:
            # 회의록 생성
            meeting_log = generate_meeting_log(meeting)
            
            # 다운로드 버튼
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.download_button(
                    label="📥 Markdown 다운로드",
                    data=meeting_log,
                    file_name=f"meeting_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
            with col2:
                # JSON 형태로도 다운로드 가능
                json_data = {
                    "meeting_info": {
                        "topic": meeting.meeting_topic,
                        "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                        "duration": meeting.meeting_duration,
                        "participants": [{"name": p.name, "role": p.role} for p in meeting.personas]
                    },
                    "messages": [
                        {
                            "timestamp": msg.timestamp.isoformat(),
                            "speaker": msg.persona_name,
                            "content": msg.content,
                            "is_human_input": msg.is_human_input
                        } for msg in meeting.messages
                    ]
                }
                
                st.download_button(
                    label="📊 JSON 다운로드",
                    data=json.dumps(json_data, ensure_ascii=False, indent=2),
                    file_name=f"meeting_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            # 회의록 미리보기
            st.subheader("👀 회의록 미리보기")
            st.markdown(meeting_log)
        else:
            st.info("ℹ️ 회의록이 비어있습니다.")

    # 🚀 자동 모드 실행 로직 (메인 함수 끝에서 실제 대화 실행)
    if meeting.auto_mode and meeting.is_active and meeting.should_continue():
        if meeting.is_time_to_speak():
            # 실제로 대화 실행
            success = run_conversation_round(meeting)
            if success:
                # 새로운 메시지가 추가되었으므로 즉시 새로고침
                st.rerun()
            else:
                # 회의 자동 종료
                meeting.is_active = False
                meeting.auto_mode = False
                moderator = meeting.get_moderator()
                if moderator:
                    closing_message = "자동 모드로 진행된 회의를 마치겠습니다. 모든 분들의 의견에 감사드립니다."
                    meeting.add_message(moderator.id, closing_message)
                st.success("✅ 자동 모드 회의가 완료되었습니다.")
                st.rerun()
        else:
            # 시간이 안 되었으면 1초 후 다시 체크
            time.sleep(1)
            st.rerun()

def generate_meeting_log(meeting: VirtualMeeting) -> str:
    """회의록 생성"""
    log = f"""# 📋 회의록

## 🎯 회의 정보
- **주제**: {meeting.meeting_topic}
- **시작 시간**: {meeting.start_time.strftime('%Y-%m-%d %H:%M:%S') if meeting.start_time else 'N/A'}
- **예정 시간**: {meeting.meeting_duration}분
- **총 라운드**: {meeting.conversation_round}
- **참여자 수**: {len(meeting.personas)}명

## 👥 참여자 목록
"""
    for persona in meeting.personas:
        icon = "🎯" if persona.is_moderator else "🎭"
        log += f"- {icon} **{persona.name}** ({persona.role})\n"
    
    log += f"\n## 💬 대화 내용 ({len(meeting.messages)}개 메시지)\n\n"
    
    current_round = 0
    for i, message in enumerate(meeting.messages):
        # 라운드 구분
        if i > 0 and not message.is_human_input and not message.is_moderator:
            speaker_index = [j for j, p in enumerate(meeting.get_non_moderator_personas()) 
                           if p.id == message.persona_id]
            if speaker_index and speaker_index[0] == 0:
                current_round += 1
                log += f"\n### 🔄 라운드 {current_round}\n\n"
        
        # 메시지 추가
        icon = "🎯" if message.is_moderator else "🎭"
        if message.is_human_input:
            icon = "👤"
        
        log += f"**{message.timestamp.strftime('%H:%M:%S')}** {icon} **{message.persona_name}**\n"
        log += f"> {message.content}\n\n"
    
    log += f"\n---\n*회의록 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    return log

if __name__ == "__main__":
    main() 