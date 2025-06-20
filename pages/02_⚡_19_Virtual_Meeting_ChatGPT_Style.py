import streamlit as st
import uuid
import time
import json
import os
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Generator
from openai import OpenAI
import docx
import PyPDF2

# 페이지 설정
st.set_page_config(
    page_title="Virtual Meeting ChatGPT Style",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
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
        self.meeting_topic: str = ""
        self.meeting_duration: int = 30
        self.max_rounds: int = 10
        self.speaking_speed: int = 3
        self.is_active: bool = False
        self.auto_mode: bool = False
        self.start_time: Optional[datetime] = None
        self.conversation_round: int = 0
        self.current_speaker_index: int = 0
        self.uploaded_files_content: str = ""
        
    def add_persona(self, persona: Persona) -> bool:
        if len(self.personas) >= 10:
            return False
        self.personas.append(persona)
        return True
    
    def remove_persona(self, persona_id: str):
        self.personas = [p for p in self.personas if p.id != persona_id]
    
    def get_moderator(self) -> Optional[Persona]:
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
            return message
        return None
    
    def get_next_speaker(self) -> Optional[Persona]:
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

def initialize_session_state():
    """세션 상태 초기화"""
    if 'virtual_meeting_chatgpt' not in st.session_state:
        st.session_state.virtual_meeting_chatgpt = VirtualMeeting()
        
        # 기본 사회자 페르소나 생성
        moderator = Persona(
            id="moderator_001",
            name="사회자 김진행",
            role="회의 사회자",
            prompt="""당신은 전문적인 회의 사회자입니다. 
            회의의 흐름을 원활하게 이끌고, 참가자들의 의견을 적절히 조율하며, 
            주제에서 벗어나지 않도록 안내하는 역할을 합니다.
            간결하고 명확하게 말하며, 모든 참가자가 발언할 기회를 갖도록 합니다.""",
            personality="차분하고 공정하며 전문적",
            expertise="회의 진행, 토론 조율, 의견 정리",
            speaking_style="정중하고 명확하며 간결한 말투",
            is_moderator=True
        )
        st.session_state.virtual_meeting_chatgpt.add_persona(moderator)
    
    # 채팅 기록 초기화 (검색시스템 패턴)
    if 'meeting_chat_history' not in st.session_state:
        st.session_state.meeting_chat_history = []
    
    # 자동 진행 상태
    if 'auto_conversation_active' not in st.session_state:
        st.session_state.auto_conversation_active = False

def extract_text_from_file(uploaded_file) -> str:
    """업로드된 파일에서 텍스트 추출"""
    try:
        file_type = uploaded_file.type
        content = ""
        
        if file_type == "text/plain":
            content = str(uploaded_file.read(), "utf-8")
        elif file_type == "text/markdown":
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
            return f"[{persona.name}] 안녕하세요! OpenAI API 키가 설정되지 않아 데모 메시지를 보내드립니다."
        
        client = OpenAI(api_key=openai_key)
        
        # 라운드에 따른 맥락 조정
        round_context = ""
        if round_number == 1:
            round_context = "이번이 첫 번째 발언입니다. 자신을 간단히 소개하고 주제에 대한 첫 번째 의견을 제시하세요."
        elif round_number <= 3:
            round_context = "초기 토론 단계입니다. 다른 참가자들의 의견을 듣고 자신의 관점을 추가하세요."
        elif round_number <= 6:
            round_context = "토론이 깊어지고 있습니다. 구체적인 해결책이나 대안을 제시해보세요."
        else:
            round_context = "토론이 마무리 단계입니다. 지금까지의 논의를 정리하거나 결론을 향해 나아가세요."
        
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
        
        지금까지의 대화 흐름을 파악하고, 당신의 역할과 전문성에 맞는 의견을 제시하세요.
        응답은 자연스럽고 사람다운 말투로 2-3문장 정도로 작성해주세요.
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
        return f"[{persona.name}] 죄송합니다. 기술적인 문제로 응답을 생성할 수 없습니다. (오류: {str(e)})"

def stream_response(text: str, delay: float = 0.05) -> Generator[str, None, None]:
    """텍스트를 단어별로 스트리밍"""
    words = text.split()
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(delay)

def format_conversation_history(messages: List[Message], last_n: int = 15) -> str:
    """대화 히스토리 포맷팅"""
    recent_messages = messages[-last_n:] if len(messages) > last_n else messages
    history = ""
    for msg in recent_messages:
        history += f"{msg.persona_name}: {msg.content}\n"
    return history

def execute_next_conversation(meeting: VirtualMeeting) -> bool:
    """다음 대화 실행 (검색시스템 패턴 적용)"""
    if not meeting.should_continue():
        return False
    
    current_persona = meeting.get_next_speaker()
    if not current_persona:
        return False
    
    # 대화 히스토리 준비
    conversation_history = format_conversation_history(meeting.messages)
    
    # AI 응답 생성
    response = generate_ai_response(
        persona=current_persona,
        conversation_history=conversation_history,
        meeting_topic=meeting.meeting_topic,
        file_content=meeting.uploaded_files_content,
        round_number=meeting.conversation_round + 1
    )
    
    # 메시지를 채팅 기록에 추가 (검색시스템 패턴)
    st.session_state.meeting_chat_history.append({
        'persona': current_persona,
        'content': response,
        'timestamp': datetime.now(),
        'round': meeting.conversation_round + 1
    })
    
    # 회의 객체에도 메시지 추가
    meeting.add_message(current_persona.id, response)
    meeting.advance_speaker()
    
    return True

def main():
    st.title("🎭 Virtual Meeting ChatGPT Style - ChatGPT 스타일 가상 회의")
    
    # 세션 상태 초기화
    initialize_session_state()
    meeting = st.session_state.virtual_meeting_chatgpt
    
    # 페이지 로드 시 자동 실행 체크 (최우선)
    if (meeting.auto_mode and 
        st.session_state.auto_conversation_active and 
        meeting.is_active and 
        meeting.should_continue()):
        
        next_speaker = meeting.get_next_speaker()
        if next_speaker:
            # 즉시 다음 발언 실행
            if execute_next_conversation(meeting):
                time.sleep(1)  # 1초 대기 후 새로고침
                st.rerun()
            else:
                meeting.auto_mode = False
                st.session_state.auto_conversation_active = False
    
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
            min_value=2,
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
            all_content = ""
            for uploaded_file in uploaded_files:
                content = extract_text_from_file(uploaded_file)
                all_content += f"\n\n=== {uploaded_file.name} ===\n{content}"
            meeting.uploaded_files_content = all_content
            st.success(f"✅ {len(uploaded_files)}개 파일이 업로드되었습니다!")
        
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
                    
                    # 사회자 인사말을 채팅 기록에 추가
                    moderator = meeting.get_moderator()
                    if moderator:
                        greeting = f"안녕하세요, '{meeting.meeting_topic}'에 대해 논의하겠습니다. 활발한 참여 부탁드립니다."
                        st.session_state.meeting_chat_history.append({
                            'persona': moderator,
                            'content': greeting,
                            'timestamp': datetime.now(),
                            'round': 0
                        })
                        meeting.add_message(moderator.id, greeting)
                    
                    st.success("✅ 회의가 시작되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 주제 입력과 최소 2명의 참가자가 필요합니다.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⏸️ 회의 일시정지"):
                    meeting.is_active = False
                    meeting.auto_mode = False
                    st.session_state.auto_conversation_active = False
                    st.info("⏸️ 회의가 일시정지되었습니다.")
                    st.rerun()
            with col2:
                if st.button("🔚 회의 종료"):
                    meeting.is_active = False
                    meeting.auto_mode = False
                    st.session_state.auto_conversation_active = False
                    moderator = meeting.get_moderator()
                    if moderator:
                        closing_message = "오늘 회의를 마치겠습니다. 모든 분들의 활발한 참여에 감사드립니다."
                        st.session_state.meeting_chat_history.append({
                            'persona': moderator,
                            'content': closing_message,
                            'timestamp': datetime.now(),
                            'round': meeting.conversation_round
                        })
                        meeting.add_message(moderator.id, closing_message)
                    st.success("✅ 회의가 종료되었습니다.")
                    st.rerun()
            
            # 자동 모드 토글
            new_auto_mode = st.toggle("🤖 자동 진행 모드", value=meeting.auto_mode)
            if new_auto_mode != meeting.auto_mode:
                meeting.auto_mode = new_auto_mode
                st.session_state.auto_conversation_active = new_auto_mode
                if meeting.auto_mode:
                    st.success("🔄 자동 모드가 활성화되었습니다. 잠시 후 자동 진행됩니다.")
                    # 즉시 자동 실행 트리거
                    st.rerun()
                else:
                    st.info("🎮 수동 모드로 전환되었습니다.")
                    st.rerun()
    
    # 메인 영역
    if not meeting.is_active:
        st.info("ℹ️ 회의를 시작하려면 사이드바에서 '회의 시작' 버튼을 클릭하세요.")
        
        # 페르소나 간단 추가
        st.header("👥 빠른 페르소나 추가")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("👨‍💼 CEO 추가"):
                ceo = Persona(
                    id=str(uuid.uuid4()),
                    name="CEO 박성공",
                    role="최고경영자",
                    prompt="",
                    personality="비전 제시와 리더십을 중시하는 성격",
                    expertise="전략 경영, 의사결정, 리더십",
                    speaking_style="확신에 차고 카리스마 있는 말투"
                )
                if meeting.add_persona(ceo):
                    st.success("✅ CEO가 추가되었습니다!")
                    st.rerun()
        
        with col2:
            if st.button("👩‍💻 CTO 추가"):
                cto = Persona(
                    id=str(uuid.uuid4()),
                    name="CTO 이기술",
                    role="최고기술책임자",
                    prompt="",
                    personality="논리적이고 분석적인 성격",
                    expertise="기술 전략, 개발, 혁신",
                    speaking_style="데이터와 근거를 바탕으로 한 차분한 말투"
                )
                if meeting.add_persona(cto):
                    st.success("✅ CTO가 추가되었습니다!")
                    st.rerun()
        
        with col3:
            if st.button("👨‍🎨 CMO 추가"):
                cmo = Persona(
                    id=str(uuid.uuid4()),
                    name="CMO 김마케팅",
                    role="최고마케팅책임자",
                    prompt="",
                    personality="창의적이고 고객 중심적 사고",
                    expertise="마케팅 전략, 브랜딩, 고객 분석",
                    speaking_style="열정적이고 창의적인 말투"
                )
                if meeting.add_persona(cmo):
                    st.success("✅ CMO가 추가되었습니다!")
                    st.rerun()
        
        # 현재 페르소나 목록
        st.header("👥 현재 참가자")
        for persona in meeting.personas:
            icon = "🎯" if persona.is_moderator else "🎭"
            st.write(f"{icon} **{persona.name}** ({persona.role}) - {persona.expertise}")
    
    else:
        # 회의 진행 상황
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            elapsed_time = datetime.now() - meeting.start_time
            st.metric("⏰ 경과 시간", f"{elapsed_time.seconds // 60}분")
        with col2:
            st.metric("🔄 현재 라운드", f"{meeting.conversation_round + 1}/{meeting.max_rounds}")
        with col3:
            st.metric("💬 총 메시지", len(st.session_state.meeting_chat_history))
        with col4:
            next_speaker = meeting.get_next_speaker()
            st.metric("🎤 다음 발언자", next_speaker.name if next_speaker else "없음")
        
        # 자동 모드 상태 표시 및 실행
        if meeting.auto_mode and st.session_state.auto_conversation_active:
            if meeting.should_continue():
                # 다음 발언자 정보 표시
                next_speaker = meeting.get_next_speaker()
                if next_speaker:
                    st.info(f"🤖 자동 모드 실행 중... 다음 발언자: {next_speaker.name}")
                    
                    # 자동으로 다음 발언 실행
                    if execute_next_conversation(meeting):
                        # 발언 간격 후 자동 새로고침
                        time.sleep(meeting.speaking_speed)
                        st.rerun()
                    else:
                        meeting.auto_mode = False
                        st.session_state.auto_conversation_active = False
                        st.info("🏁 회의가 자동으로 종료되었습니다.")
                        st.rerun()
                else:
                    meeting.auto_mode = False
                    st.session_state.auto_conversation_active = False
                    st.error("⚠️ 발언할 페르소나가 없습니다.")
                    st.rerun()
            else:
                meeting.auto_mode = False
                st.session_state.auto_conversation_active = False
                st.info("🏁 회의가 자동으로 종료되었습니다.")
                st.rerun()
        elif meeting.auto_mode:
            # 자동 모드는 활성화되었지만 대화가 비활성 상태
            st.warning("🤖 자동 모드가 활성화되었지만 대화가 시작되지 않았습니다.")
            if st.button("🚀 자동 대화 시작"):
                st.session_state.auto_conversation_active = True
                st.rerun()
        
        # 수동 컨트롤
        if not meeting.auto_mode:
            st.header("🎮 수동 컨트롤")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("➡️ 다음 발언", type="primary"):
                    if execute_next_conversation(meeting):
                        st.rerun()
                    else:
                        st.error("⚠️ 더 이상 진행할 수 없습니다.")
            
            with col2:
                next_speaker = meeting.get_next_speaker()
                if next_speaker:
                    human_input = st.text_area(
                        f"💬 {next_speaker.name}으로 직접 발언",
                        height=100,
                        key=f"human_input_{next_speaker.id}"
                    )
                    if st.button(f"🎤 {next_speaker.name} 발언"):
                        if human_input.strip():
                            st.session_state.meeting_chat_history.append({
                                'persona': next_speaker,
                                'content': human_input.strip(),
                                'timestamp': datetime.now(),
                                'round': meeting.conversation_round + 1,
                                'is_human': True
                            })
                            meeting.add_message(next_speaker.id, human_input.strip(), is_human_input=True)
                            meeting.advance_speaker()
                            st.rerun()
                        else:
                            st.error("⚠️ 발언 내용을 입력해주세요.")
        
        # ChatGPT 스타일 대화 표시 (검색시스템 패턴 적용)
        st.header("💬 회의 대화")
        
        # 대화 기록 표시 (최신 대화가 아래쪽에 오도록)
        for chat in st.session_state.meeting_chat_history:
            persona = chat['persona']
            content = chat['content']
            timestamp = chat['timestamp']
            is_human = chat.get('is_human', False)
            
            # 아바타 설정
            if persona.is_moderator:
                avatar = "🎯"
            elif is_human:
                avatar = "👤"
            else:
                avatar = "🎭"
            
            # ChatGPT 스타일 메시지 표시
            with st.chat_message("assistant", avatar=avatar):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{persona.name}** ({persona.role})")
                    # 스트리밍 효과 (마지막 메시지에만 적용)
                    if chat == st.session_state.meeting_chat_history[-1] and not is_human:
                        st.write_stream(stream_response(content))
                    else:
                        st.markdown(content)
                with col2:
                    st.caption(timestamp.strftime('%H:%M:%S'))
                    if is_human:
                        st.caption("👤 인간 개입")
                    st.caption(f"라운드 {chat['round']}")
        
        # 회의록 다운로드
        st.header("📄 회의록")
        if st.session_state.meeting_chat_history:
            col1, col2 = st.columns(2)
            
            with col1:
                # Markdown 형식 다운로드
                md_content = f"# {meeting.meeting_topic}\n\n"
                md_content += f"**회의 시간**: {meeting.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                md_content += f"**참가자**: {', '.join([p.name for p in meeting.personas])}\n\n"
                md_content += "## 대화 내용\n\n"
                
                for chat in st.session_state.meeting_chat_history:
                    persona = chat['persona']
                    content = chat['content']
                    timestamp = chat['timestamp']
                    is_human = chat.get('is_human', False)
                    human_marker = " (인간 개입)" if is_human else ""
                    
                    md_content += f"### {persona.name}{human_marker} ({timestamp.strftime('%H:%M:%S')})\n"
                    md_content += f"{content}\n\n"
                
                st.download_button(
                    label="📄 Markdown 다운로드",
                    data=md_content,
                    file_name=f"meeting_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                    mime="text/markdown"
                )
            
            with col2:
                # JSON 형식 다운로드
                meeting_data = {
                    "topic": meeting.meeting_topic,
                    "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                    "participants": [
                        {
                            "name": p.name,
                            "role": p.role,
                            "expertise": p.expertise,
                            "is_moderator": p.is_moderator
                        } for p in meeting.personas
                    ],
                    "messages": [
                        {
                            "timestamp": chat['timestamp'].isoformat(),
                            "speaker": chat['persona'].name,
                            "content": chat['content'],
                            "round": chat['round'],
                            "is_human_input": chat.get('is_human', False),
                            "is_moderator": chat['persona'].is_moderator
                        } for chat in st.session_state.meeting_chat_history
                    ]
                }
                
                st.download_button(
                    label="📊 JSON 다운로드",
                    data=json.dumps(meeting_data, ensure_ascii=False, indent=2),
                    file_name=f"meeting_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main() 