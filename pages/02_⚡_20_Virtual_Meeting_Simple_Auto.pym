import streamlit as st
import uuid
import time
import json
import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Generator
from openai import OpenAI

# 페이지 설정
st.set_page_config(
    page_title="Virtual Meeting Simple Auto",
    page_icon="🎭",
    layout="wide"
)

@dataclass
class Persona:
    id: str
    name: str
    role: str
    expertise: str
    is_moderator: bool = False

@dataclass
class ChatMessage:
    persona: Persona
    content: str
    timestamp: datetime
    is_human: bool = False

def initialize_session_state():
    """세션 상태 초기화"""
    if 'personas' not in st.session_state:
        st.session_state.personas = []
        
        # 기본 사회자 추가
        moderator = Persona(
            id="moderator",
            name="사회자 김진행",
            role="회의 사회자",
            expertise="회의 진행",
            is_moderator=True
        )
        st.session_state.personas.append(moderator)
    
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    if 'meeting_topic' not in st.session_state:
        st.session_state.meeting_topic = ""
    
    if 'meeting_active' not in st.session_state:
        st.session_state.meeting_active = False
    
    if 'auto_mode' not in st.session_state:
        st.session_state.auto_mode = False
    
    if 'current_speaker_index' not in st.session_state:
        st.session_state.current_speaker_index = 0
    
    if 'conversation_round' not in st.session_state:
        st.session_state.conversation_round = 0
    
    if 'max_rounds' not in st.session_state:
        st.session_state.max_rounds = 10
    
    if 'speaking_speed' not in st.session_state:
        st.session_state.speaking_speed = 3

def get_non_moderator_personas() -> List[Persona]:
    """사회자가 아닌 페르소나 목록"""
    return [p for p in st.session_state.personas if not p.is_moderator]

def get_next_speaker() -> Optional[Persona]:
    """다음 발언자 가져오기"""
    non_moderators = get_non_moderator_personas()
    if not non_moderators:
        return None
    return non_moderators[st.session_state.current_speaker_index % len(non_moderators)]

def advance_speaker():
    """다음 발언자로 이동"""
    non_moderators = get_non_moderator_personas()
    if non_moderators:
        st.session_state.current_speaker_index += 1
        if st.session_state.current_speaker_index % len(non_moderators) == 0:
            st.session_state.conversation_round += 1

def should_continue() -> bool:
    """회의 계속 여부"""
    return (st.session_state.meeting_active and 
            st.session_state.conversation_round < st.session_state.max_rounds)

def generate_ai_response(persona: Persona) -> str:
    """AI 응답 생성"""
    try:
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
            return f"[{persona.name}] 안녕하세요! API 키가 설정되지 않아 데모 메시지입니다."
        
        client = OpenAI(api_key=openai_key)
        
        # 최근 대화 히스토리
        recent_messages = st.session_state.chat_messages[-5:] if st.session_state.chat_messages else []
        history = "\n".join([f"{msg.persona.name}: {msg.content}" for msg in recent_messages])
        
        system_prompt = f"""
        당신은 {persona.name}입니다.
        역할: {persona.role}
        전문 분야: {persona.expertise}
        
        회의 주제: {st.session_state.meeting_topic}
        현재 라운드: {st.session_state.conversation_round + 1}
        
        회의에서 당신의 전문성을 바탕으로 건설적인 의견을 제시하세요.
        응답은 2-3문장 정도로 간결하게 작성해주세요.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"대화 내용:\n{history}\n\n위 내용을 바탕으로 응답해주세요."}
            ],
            max_tokens=200,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[{persona.name}] 죄송합니다. 응답 생성 중 오류가 발생했습니다."

def stream_response(text: str) -> Generator[str, None, None]:
    """스트리밍 응답"""
    words = text.split()
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(0.05)

def execute_next_conversation() -> bool:
    """다음 대화 실행"""
    if not should_continue():
        return False
    
    current_persona = get_next_speaker()
    if not current_persona:
        return False
    
    # AI 응답 생성
    response = generate_ai_response(current_persona)
    
    # 메시지 추가
    message = ChatMessage(
        persona=current_persona,
        content=response,
        timestamp=datetime.now(),
        is_human=False
    )
    st.session_state.chat_messages.append(message)
    
    # 다음 발언자로 이동
    advance_speaker()
    
    return True

def main():
    st.title("🎭 Virtual Meeting Simple Auto - 간단한 자동 진행 회의")
    
    # 세션 상태 초기화
    initialize_session_state()
    
    # 자동 모드 체크 (페이지 최상단)
    if (st.session_state.auto_mode and 
        st.session_state.meeting_active and 
        should_continue()):
        
        # 자동 실행
        if execute_next_conversation():
            time.sleep(st.session_state.speaking_speed)
            st.rerun()
        else:
            st.session_state.auto_mode = False
            st.session_state.meeting_active = False
    
    # 사이드바
    with st.sidebar:
        st.header("🎯 회의 설정")
        
        # 회의 주제
        st.session_state.meeting_topic = st.text_area(
            "회의 주제",
            value=st.session_state.meeting_topic,
            placeholder="예: 신제품 출시 전략 수립"
        )
        
        # 설정
        st.session_state.max_rounds = st.slider("최대 라운드", 3, 20, st.session_state.max_rounds)
        st.session_state.speaking_speed = st.slider("발언 간격 (초)", 1, 10, st.session_state.speaking_speed)
        
        st.divider()
        
        # 페르소나 관리
        st.header("👥 참가자 관리")
        
        # 빠른 추가 버튼
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👨‍💼 CEO 추가"):
                ceo = Persona(
                    id=str(uuid.uuid4()),
                    name="CEO 박성공",
                    role="최고경영자",
                    expertise="전략 경영, 의사결정"
                )
                st.session_state.personas.append(ceo)
                st.rerun()
        
        with col2:
            if st.button("👩‍💻 CTO 추가"):
                cto = Persona(
                    id=str(uuid.uuid4()),
                    name="CTO 이기술",
                    role="최고기술책임자",
                    expertise="기술 전략, 개발"
                )
                st.session_state.personas.append(cto)
                st.rerun()
        
        # 현재 참가자 목록
        st.subheader("현재 참가자")
        for persona in st.session_state.personas:
            icon = "🎯" if persona.is_moderator else "🎭"
            st.write(f"{icon} {persona.name} ({persona.role})")
        
        st.divider()
        
        # 회의 제어
        st.header("🎮 회의 제어")
        
        if not st.session_state.meeting_active:
            if st.button("🚀 회의 시작", type="primary"):
                if st.session_state.meeting_topic and len(get_non_moderator_personas()) >= 1:
                    st.session_state.meeting_active = True
                    st.session_state.conversation_round = 0
                    st.session_state.current_speaker_index = 0
                    
                    # 사회자 인사말
                    moderator = next((p for p in st.session_state.personas if p.is_moderator), None)
                    if moderator:
                        greeting = f"안녕하세요, '{st.session_state.meeting_topic}'에 대해 논의하겠습니다."
                        message = ChatMessage(
                            persona=moderator,
                            content=greeting,
                            timestamp=datetime.now()
                        )
                        st.session_state.chat_messages.append(message)
                    
                    st.success("✅ 회의가 시작되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 주제와 참가자가 필요합니다.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔚 회의 종료"):
                    st.session_state.meeting_active = False
                    st.session_state.auto_mode = False
                    st.success("✅ 회의가 종료되었습니다.")
                    st.rerun()
            
            with col2:
                auto_label = "⏸️ 자동 중지" if st.session_state.auto_mode else "🤖 자동 시작"
                if st.button(auto_label):
                    st.session_state.auto_mode = not st.session_state.auto_mode
                    if st.session_state.auto_mode:
                        st.success("🔄 자동 모드 시작!")
                        st.rerun()  # 즉시 자동 실행 시작
                    else:
                        st.info("🎮 수동 모드로 전환")
                    st.rerun()
    
    # 메인 영역
    if not st.session_state.meeting_active:
        st.info("ℹ️ 회의를 시작하려면 사이드바에서 설정을 완료하고 '회의 시작' 버튼을 클릭하세요.")
        
        # 간단한 안내
        st.markdown("""
        ### 🎭 가상 회의 사용법
        1. **참가자 추가**: 사이드바에서 CEO, CTO 등 추가
        2. **주제 입력**: 회의에서 논의할 주제 작성
        3. **회의 시작**: 🚀 버튼으로 회의 시작
        4. **자동 진행**: 🤖 버튼으로 자동 모드 활성화
        """)
    
    else:
        # 회의 상태 표시
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔄 라운드", f"{st.session_state.conversation_round + 1}/{st.session_state.max_rounds}")
        with col2:
            st.metric("💬 메시지", len(st.session_state.chat_messages))
        with col3:
            next_speaker = get_next_speaker()
            st.metric("🎤 다음 발언자", next_speaker.name if next_speaker else "없음")
        with col4:
            mode_text = "🤖 자동" if st.session_state.auto_mode else "🎮 수동"
            st.metric("📊 모드", mode_text)
        
        # 자동 모드 상태
        if st.session_state.auto_mode:
            st.success("🤖 자동 모드 실행 중... 자동으로 대화가 진행됩니다.")
        
        # 수동 컨트롤
        if not st.session_state.auto_mode:
            st.header("🎮 수동 컨트롤")
            if st.button("➡️ 다음 발언", type="primary"):
                if execute_next_conversation():
                    st.rerun()
                else:
                    st.error("⚠️ 더 이상 진행할 수 없습니다.")
        
        # 대화 표시
        st.header("💬 회의 대화")
        
        for i, message in enumerate(st.session_state.chat_messages):
            persona = message.persona
            content = message.content
            
            # 아바타 설정
            if persona.is_moderator:
                avatar = "🎯"
            elif message.is_human:
                avatar = "👤"
            else:
                avatar = "🎭"
            
            # 메시지 표시
            with st.chat_message("assistant", avatar=avatar):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{persona.name}** ({persona.role})")
                    # 마지막 메시지만 스트리밍 효과
                    if i == len(st.session_state.chat_messages) - 1 and not message.is_human:
                        st.write_stream(stream_response(content))
                    else:
                        st.markdown(content)
                with col2:
                    st.caption(message.timestamp.strftime('%H:%M:%S'))
        
        # 회의록 다운로드
        if st.session_state.chat_messages:
            st.header("📄 회의록")
            
            # Markdown 형식
            md_content = f"# {st.session_state.meeting_topic}\n\n"
            md_content += f"**회의 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            md_content += "## 대화 내용\n\n"
            
            for message in st.session_state.chat_messages:
                md_content += f"### {message.persona.name} ({message.timestamp.strftime('%H:%M:%S')})\n"
                md_content += f"{message.content}\n\n"
            
            st.download_button(
                label="📄 회의록 다운로드",
                data=md_content,
                file_name=f"meeting_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                mime="text/markdown"
            )

if __name__ == "__main__":
    main() 