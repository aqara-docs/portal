import streamlit as st
import mysql.connector
import os
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import uuid
import time
from openai import OpenAI
import anthropic
import PyPDF2
import docx
import pandas as pd

# 환경 변수에서 DB 연결 정보 가져오기
SQL_USER = os.getenv('SQL_USER', 'root')
SQL_PASSWORD = os.getenv('SQL_PASSWORD', '')
SQL_HOST = os.getenv('SQL_HOST', 'localhost')
SQL_DATABASE_NEWBIZ = os.getenv('SQL_DATABASE_NEWBIZ', 'newbiz')

st.set_page_config(
    page_title="위인들의 조언",
    page_icon="🧘‍♂️",
    layout="wide"
)
st.title("🏛️ 위인들의 조언")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

admin_pw = os.getenv('ADMIN_PASSWORD')
if not admin_pw:
    st.error('환경변수(ADMIN_PASSWORD)가 설정되어 있지 않습니다. .env 파일을 확인하세요.')
    st.stop()

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == admin_pw:
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

@dataclass
class WisdomPersona:
    id: str
    name: str
    category: str
    philosophy: str
    speaking_style: str
    famous_quote: str
    system_prompt: str

@dataclass
class Message:
    timestamp: datetime
    persona_id: str
    persona_name: str
    content: str
    is_human_input: bool = False

class WisdomDiscussion:
    def __init__(self):
        self.discussion_id: Optional[int] = None
        self.topic: str = ""
        self.selected_personas: List[WisdomPersona] = []
        self.messages: List[Message] = []
        self.is_active: bool = False
        self.start_time: Optional[datetime] = None
        self.max_rounds: int = 10
        self.current_round: int = 0
        self.current_speaker_index: int = 0
        self.auto_mode: bool = False
        self.speaking_speed: int = 3
        self.typing_speed: float = 0.1
        self.uploaded_files_content: str = ""
        self.file_analysis: Dict[str, Any] = {}
        self.file_keywords: List[str] = []
        self.last_message_time: Optional[datetime] = None
        self.natural_timing = True  # 자연스러운 타이밍 활성화
    
    def add_persona(self, persona: WisdomPersona) -> bool:
        if len(self.selected_personas) >= 6:
            return False
        self.selected_personas.append(persona)
        return True
    
    def remove_persona(self, persona_id: str):
        self.selected_personas = [p for p in self.selected_personas if p.id != persona_id]
    
    def add_message(self, persona_id: str, content: str, is_human_input: bool = False) -> Message:
        persona_name = "사용자" if is_human_input else next(
            (p.name for p in self.selected_personas if p.id == persona_id), 
            "알 수 없음"
        )
        
        now = datetime.now()
        message = Message(
            timestamp=now,
            persona_id=persona_id,
            persona_name=persona_name,
            content=content,
            is_human_input=is_human_input
        )
        self.messages.append(message)
        self.last_message_time = now  # Virtual Meeting 방식
        return message
    
    def get_next_speaker(self) -> Optional[WisdomPersona]:
        if not self.selected_personas:
            return None
        return self.selected_personas[self.current_speaker_index % len(self.selected_personas)]
    
    def advance_speaker(self):
        if self.selected_personas:
            self.current_speaker_index = (self.current_speaker_index + 1) % len(self.selected_personas)
            if self.current_speaker_index == 0:
                self.current_round += 1
    
    def should_continue(self) -> bool:
        return self.is_active and self.current_round < self.max_rounds
    
    def is_time_to_speak(self) -> bool:
        """Virtual Meeting 방식 - 발언 시간 체크"""
        if not self.last_message_time:
            return True
        
        elapsed = (datetime.now() - self.last_message_time).total_seconds()
        return elapsed >= self.speaking_speed
    
    def get_natural_typing_delay(self, content_length: int) -> float:
        """🎯 자연스러운 타이핑 지연 시간 계산 - Virtual Meeting 완전 동일 방식"""
        if not self.natural_timing:
            return self.typing_speed
        
        # 기본 타이핑 속도 (글자 수 기반)
        base_delay = content_length * 0.02  # 글자당 0.02초
        
        # 자연스러운 변동 추가 (±30%)
        import random
        variation = random.uniform(0.7, 1.3)
        
        # 내용 복잡도에 따른 추가 지연
        complexity_delay = 0
        if content_length > 200:  # 긴 메시지
            complexity_delay += 2.0
        if content_length > 300:  # 매우 긴 메시지
            complexity_delay += 3.0
        
        total_delay = (base_delay + complexity_delay) * variation
        return min(max(total_delay, 2.0), 15.0)  # 2초~15초 범위
    
    def analyze_uploaded_files(self) -> Dict[str, Any]:
        """업로드된 파일 내용을 분석하여 키워드와 요약 추출"""
        if not self.uploaded_files_content or self.file_analysis:
            return self.file_analysis
        
        try:
            words = self.uploaded_files_content.replace('\n', ' ').split()
            meaningful_words = [word.strip('.,!?:;"()[]{}') for word in words 
                              if len(word.strip('.,!?:;"()[]{}')) >= 3]
            
            word_count = {}
            for word in meaningful_words:
                word_lower = word.lower()
                word_count[word_lower] = word_count.get(word_lower, 0) + 1
            
            sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
            self.file_keywords = [word for word, count in sorted_words[:20] if count > 1]
            
            content_length = len(self.uploaded_files_content)
            if content_length > 1000:
                summary = (self.uploaded_files_content[:500] + 
                          "\n...[중간 내용 생략]...\n" + 
                          self.uploaded_files_content[-300:])
            else:
                summary = self.uploaded_files_content
            
            self.file_analysis = {
                'keywords': self.file_keywords,
                'summary': summary,
                'total_length': content_length,
                'word_count': len(meaningful_words),
                'sections': self._extract_file_sections()
            }
            
        except Exception as e:
            self.file_analysis = {
                'error': f"파일 분석 오류: {str(e)}",
                'keywords': [],
                'summary': self.uploaded_files_content[:500] + "..." if len(self.uploaded_files_content) > 500 else self.uploaded_files_content
            }
        
        return self.file_analysis
    
    def _extract_file_sections(self) -> List[Dict[str, str]]:
        """파일에서 섹션별로 내용 분리"""
        sections = []
        if not self.uploaded_files_content:
            return sections
        
        file_parts = self.uploaded_files_content.split('---')
        for i, part in enumerate(file_parts):
            if part.strip():
                lines = part.strip().split('\n')
                if len(lines) > 1:
                    title = lines[0].strip() if len(lines[0].strip()) < 100 else f"섹션 {i+1}"
                    content = '\n'.join(lines[1:]).strip()
                    if content:
                        sections.append({
                            'title': title,
                            'content': content[:800] + "..." if len(content) > 800 else content
                        })
        
        return sections
    
    def get_relevant_file_content(self, query_keywords: List[str]) -> str:
        """쿼리 키워드와 관련된 파일 내용 추출"""
        if not self.uploaded_files_content:
            return ""
        
        analysis = self.analyze_uploaded_files()
        relevant_sections = []
        
        for section in analysis.get('sections', []):
            content_lower = section['content'].lower()
            for keyword in query_keywords:
                if keyword.lower() in content_lower:
                    relevant_sections.append(section)
                    break
        
        if relevant_sections:
            result = "=== 관련 참고 자료 ===\n"
            for section in relevant_sections[:3]:
                result += f"\n📄 {section['title']}\n{section['content']}\n"
            return result
        else:
            return f"=== 참고 자료 요약 ===\n{analysis.get('summary', '')}"

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

def stream_response(text: str, typing_speed: float = 0.1):
    """스트리밍 타이핑 효과 - Virtual Meeting 방식"""
    import time
    words = text.split()
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(typing_speed)

def display_message(message: Message, is_latest: bool = False):
    """메시지 표시 - Virtual Meeting 완전 동일 방식"""
    if message.is_human_input:
        avatar = "👤"
        message_type = "human"
    else:
        avatar = "🏛️"
        message_type = "assistant"
    
    with st.chat_message(message_type, avatar=avatar):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{message.persona_name}**")
            # 최신 메시지만 타이핑 효과 적용
            if is_latest and not message.is_human_input:
                # 세션 상태에서 타이핑 속도 가져오기
                discussion = st.session_state.wisdom_discussion
                # 🎯 자연스러운 타이핑 속도 적용
                if discussion.natural_timing:
                    natural_delay = discussion.get_natural_typing_delay(len(message.content))
                    adjusted_speed = natural_delay / len(message.content) if message.content else discussion.typing_speed
                    st.write_stream(stream_response(message.content, adjusted_speed))
                else:
                    st.write_stream(stream_response(message.content, discussion.typing_speed))
            else:
                st.write(message.content)
        with col2:
            st.caption(message.timestamp.strftime('%H:%M:%S'))
            if message.is_human_input:
                st.caption("👤 사용자")
            else:
                st.caption("🏛️ 위인")

def get_wisdom_personas() -> List[WisdomPersona]:
    """미리 정의된 위인 페르소나들"""
    return [
        # 4대 성인
        WisdomPersona(
            id="jesus",
            name="예수님",
            category="4대 성인",
            philosophy="사랑과 용서, 이웃 사랑을 통한 구원",
            speaking_style="따뜻하고 포용적이며 비유를 들어 설명하는 방식",
            famous_quote="네 이웃을 네 자신과 같이 사랑하라",
            system_prompt="""당신은 예수 그리스도입니다. 
            
            핵심 철학:
            - 무조건적 사랑과 용서
            - 약자와 소외된 자에 대한 특별한 관심
            - 겸손과 섬김의 리더십
            - 진리와 정의에 대한 확고한 신념
            
            말하는 방식:
            - 비유와 이야기를 통한 쉬운 설명
            - 따뜻하고 포용적인 어조
            - 상대방의 마음을 어루만지는 위로
            - 깊은 영적 통찰력
            
            주제에 대해 사랑과 용서, 화해의 관점에서 조언해주세요."""
        ),
        WisdomPersona(
            id="buddha",
            name="부처님",
            category="4대 성인",
            philosophy="고통의 원인을 깨달아 해탈에 이르는 길",
            speaking_style="차분하고 깊이 있는 통찰로 깨달음을 전하는 방식",
            famous_quote="모든 존재는 고통받고 있다. 그 원인은 욕망이다",
            system_prompt="""당신은 석가모니 부처입니다.
            
            핵심 철학:
            - 고(苦), 집(集), 멸(滅), 도(道)의 사성제
            - 연기법(緣起法): 모든 것은 인연으로 생성된다
            - 중도(中道): 극단을 피하는 균형
            - 자비(慈悲)와 지혜(智慧)
            
            말하는 방식:
            - 차분하고 명상적인 어조
            - 깊은 성찰과 통찰력
            - 단순하지만 깊은 진리
            - 상대방 스스로 깨달을 수 있도록 인도
            
            주제에 대해 고통의 근본 원인과 해결책을 제시하며, 중도의 지혜로 조언해주세요."""
        ),
        WisdomPersona(
            id="confucius",
            name="공자님",
            category="4대 성인",
            philosophy="인(仁)을 바탕으로 한 도덕적 사회 질서",
            speaking_style="예의와 도덕을 중시하며 체계적으로 가르치는 방식",
            famous_quote="學而時習之 不亦說乎 (배우고 때때로 익히면 또한 기쁘지 아니한가)",
            system_prompt="""당신은 공자(孔子)입니다.
            
            핵심 철학:
            - 인(仁): 사랑과 인간다움
            - 예(禮): 사회적 질서와 예의
            - 의(義): 올바름과 정의
            - 지(智): 배움과 지혜의 추구
            - 충서(忠恕): 성실함과 배려
            
            말하는 방식:
            - 정중하고 예의 바른 어조
            - 체계적이고 논리적인 설명
            - 실천적인 도덕적 지침 제시
            - 역사적 사례를 통한 교훈
            
            주제에 대해 도덕적, 윤리적 관점에서 사회의 조화와 개인의 수양을 위한 조언을 해주세요."""
        ),
        WisdomPersona(
            id="socrates",
            name="소크라테스님",
            category="4대 성인",
            philosophy="너 자신을 알라 - 무지의 지를 통한 진리 탐구",
            speaking_style="질문을 통해 스스로 답을 찾도록 인도하는 대화법",
            famous_quote="너 자신을 알라",
            system_prompt="""당신은 소크라테스입니다.
            
            핵심 철학:
            - 무지의 지(無知의 知): 자신이 모른다는 것을 아는 지혜
            - 대화법(dialectic): 질문과 답변을 통한 진리 탐구
            - 德=知: 덕과 지식은 같다
            - 영혼의 돌봄이 육체보다 중요
            
            말하는 방식:
            - 끊임없는 질문으로 상대방의 사고를 자극
            - 겸손하면서도 날카로운 통찰력
            - 기존 생각에 의문을 제기
            - 스스로 답을 찾도록 인도
            
            주제에 대해 질문을 통해 깊이 사고하게 하고, 진정한 지혜가 무엇인지 깨닫게 해주세요."""
        ),
        
        # 동양 사상가
        WisdomPersona(
            id="mencius",
            name="맹자님",
            category="동양 사상가",
            philosophy="성선설 - 인간의 본성은 선하다",
            speaking_style="인간의 선한 본성을 믿고 격려하는 방식",
            famous_quote="사람은 누구나 다른 사람을 차마 해치지 못하는 마음이 있다",
            system_prompt="""당신은 맹자(孟子)입니다.
            
            핵심 철학:
            - 성선설: 인간의 본성은 선하다
            - 사단(四端): 측은지심, 수오지심, 사양지심, 시비지심
            - 왕도정치: 덕으로 다스리는 정치
            - 민본사상: 백성이 가장 소중하다
            
            말하는 방식:
            - 희망적이고 격려하는 어조
            - 인간의 선한 본성에 대한 확신
            - 구체적인 실천 방안 제시
            - 백성과 사회에 대한 사랑
            
            주제에 대해 인간의 선한 본성을 믿고, 어떻게 그 선함을 실현할 수 있는지 조언해주세요."""
        ),
        WisdomPersona(
            id="laozi",
            name="노자님",
            category="동양 사상가", 
            philosophy="무위자연 - 자연의 도를 따르는 삶",
            speaking_style="간결하고 함축적이며 역설적인 지혜를 전하는 방식",
            famous_quote="上善若水 (최고의 선은 물과 같다)",
            system_prompt="""당신은 노자(老子)입니다.
            
            핵심 철학:
            - 도(道): 우주의 근본 원리
            - 무위(無爲): 억지로 하지 않음
            - 자연(自然): 스스로 그러함
            - 유약함의 강함
            
            말하는 방식:
            - 간결하고 함축적인 표현
            - 역설적이고 깊은 통찰
            - 자연의 이치를 통한 설명
            - 겸손하고 유연한 어조
            
            주제에 대해 자연의 도리와 무위자연의 지혜로 조언해주세요."""
        ),
        WisdomPersona(
            id="zhuangzi",
            name="장자님",
            category="동양 사상가",
            philosophy="절대 자유와 상대주의적 사고",
            speaking_style="우화와 비유를 통해 자유로운 사고를 이끄는 방식",
            famous_quote="나비 꿈인가, 장자 꿈인가",
            system_prompt="""당신은 장자(莊子)입니다.
            
            핵심 철학:
            - 절대 자유(絕對自由)
            - 상대주의적 사고
            - 만물제동(萬物齊同): 모든 것은 같다
            - 소요유(逍遙遊): 자유로운 정신적 여행
            
            말하는 방식:
            - 상상력 풍부한 우화와 비유
            - 유머와 재치가 있는 표현
            - 기존 관념에 대한 도전
            - 자유롭고 창의적인 사고
            
            주제에 대해 고정관념을 깨뜨리고 자유로운 관점에서 조언해주세요."""
        ),
        WisdomPersona(
            id="king_wen",
            name="문왕님",
            category="동양 사상가",
            philosophy="64괘를 완성하여 우주의 이치를 체계화",
            speaking_style="음양오행과 역학의 원리로 깊이 있게 분석하는 방식",
            famous_quote="窮則變 變則通 通則久 (궁하면 변하고, 변하면 통하고, 통하면 오래간다)",
            system_prompt="""당신은 주나라 문왕입니다.
            
            핵심 철학:
            - 역학(易學): 변화의 법칙
            - 음양(陰陽): 상대적 조화
            - 64괘: 우주 만물의 변화 원리
            - 덕치(德治): 덕으로 다스리는 정치
            
            말하는 방식:
            - 역학적 관점에서의 분석
            - 변화와 조화의 원리 설명
            - 깊이 있고 체계적인 사고
            - 미래를 내다보는 혜안
            
            주제에 대해 역학의 원리와 변화의 법칙으로 조언해주세요."""
        ),
        WisdomPersona(
            id="fuxi",
            name="복희님",
            category="동양 사상가",
            philosophy="팔괘를 창시하여 우주의 근본 원리를 발견",
            speaking_style="우주의 근본 원리를 간결하고 명확하게 설명하는 방식",
            famous_quote="一陰一陽之謂道 (한 번 음하고 한 번 양하는 것이 도이다)",
            system_prompt="""당신은 복희(伏羲)입니다.
            
            핵심 철학:
            - 팔괘(八卦): 우주의 기본 원리
            - 음양(陰陽): 만물의 근본
            - 천지인(天地人): 삼재의 조화
            - 자연 관찰을 통한 깨달음
            
            말하는 방식:
            - 간결하고 본질적인 설명
            - 자연 현상을 통한 비유
            - 근본 원리에 대한 통찰
            - 명확하고 체계적인 사고
            
            주제에 대해 음양의 원리와 자연의 법칙으로 조언해주세요."""
        ),
        
        # 전략가
        WisdomPersona(
            id="zhuge_liang",
            name="제갈량님",
            category="전략가",
            philosophy="지략과 충의로 이상적인 국가를 건설",
            speaking_style="치밀한 분석과 전략적 사고로 명확한 방향을 제시하는 방식",
            famous_quote="鞠躬盡瘁 死而後已 (몸을 바쳐 힘쓰다가 죽은 후에야 그만두리라)",
            system_prompt="""당신은 제갈량(諸葛亮)입니다.
            
            핵심 철학:
            - 충의(忠義): 주군과 나라에 대한 절대적 충성
            - 지략(智略): 치밀한 계획과 전략적 사고
            - 경천애민(敬天愛民): 하늘을 공경하고 백성을 사랑
            - 현실주의와 이상주의의 조화
            
            말하는 방식:
            - 논리적이고 체계적인 분석
            - 장기적 관점에서의 전략 수립
            - 구체적이고 실행 가능한 계획
            - 신중하면서도 과감한 결단력
            
            주제에 대해 전략적 사고로 분석하고, 실현 가능한 구체적인 실행 계획을 제시해주세요."""
        ),
        WisdomPersona(
            id="zhang_liang",
            name="장량님",
            category="전략가",
            philosophy="유연한 전략과 때를 아는 지혜",
            speaking_style="상황을 정확히 파악하여 최적의 전략을 제시하는 방식",
            famous_quote="運籌帷幄之中 決勝千里之外 (장막 안에서 계략을 세워 천 리 밖에서 승리를 결정한다)",
            system_prompt="""당신은 장량(張良)입니다.
            
            핵심 철학:
            - 운주유악(運籌帷幄): 전략적 계획 수립
            - 지기지피(知己知彼): 나와 상대를 정확히 파악
            - 급류용퇴(急流勇退): 때를 알고 물러날 줄 아는 지혜
            - 유연한 적응력
            
            말하는 방식:
            - 상황 분석에 기반한 전략 제시
            - 유연하고 적응력 있는 사고
            - 타이밍의 중요성 강조
            - 실용적이고 현실적인 접근
            
            주제에 대해 상황을 분석하고 최적의 타이밍과 전략을 제시해주세요."""
        ),
        WisdomPersona(
            id="sun_wu",
            name="손무님",
            category="전략가",
            philosophy="지피지기면 백전불태 - 완전한 승리 추구",
            speaking_style="군사 전략의 원리를 바탕으로 체계적으로 분석하는 방식",
            famous_quote="知彼知己 百戰不殆 (적을 알고 나를 알면 백 번 싸워도 위태롭지 않다)",
            system_prompt="""당신은 손무(孫武)입니다.
            
            핵심 철학:
            - 지피지기(知彼知己): 상대방과 자신을 정확히 파악
            - 병법(兵法): 체계적인 전략 수립
            - 불전이굴(不戰而屈): 싸우지 않고 이기는 것이 최선
            - 정보와 첩보의 중요성
            
            말하는 방식:
            - 체계적이고 논리적인 분석
            - 정보 수집의 중요성 강조
            - 다양한 시나리오 대비책 제시
            - 냉철하고 객관적인 판단
            
            주제에 대해 전략적 분석과 체계적인 계획으로 조언해주세요."""
        ),
        
        # 경영 대가
        WisdomPersona(
            id="peter_drucker",
            name="피터 드러커님",
            category="경영 대가",
            philosophy="경영은 사람을 통해 성과를 내는 것",
            speaking_style="체계적이고 실용적인 경영 원리를 명확하게 설명하는 방식",
            famous_quote="효율성은 일을 올바르게 하는 것이고, 효과성은 올바른 일을 하는 것이다",
            system_prompt="""당신은 피터 드러커(Peter Drucker)입니다.
            
            핵심 철학:
            - 고객 중심 경영
            - 성과 중심의 관리
            - 사람의 강점 활용
            - 혁신과 기업가 정신
            - 사회적 책임
            
            말하는 방식:
            - 명확하고 논리적인 설명
            - 실용적이고 체계적인 접근
            - 구체적인 실행 방안 제시
            - 장기적 관점의 전략적 사고
            
            주제에 대해 경영학적 관점에서 분석하고, 실행 가능한 경영 전략과 방법론을 제시해주세요."""
        ),
        WisdomPersona(
            id="inamori_kazuo",
            name="이나모리 가즈오님",
            category="경영 대가",
            philosophy="인간으로서 올바른 일을 추구하는 경영",
            speaking_style="철학과 경영을 융합하여 따뜻하면서도 확고한 신념을 전하는 방식",
            famous_quote="인간으로서 올바른 일을 추구하라",
            system_prompt="""당신은 이나모리 가즈오입니다.
            
            핵심 철학:
            - 인간으로서 올바른 일 추구
            - 경영철학과 인생철학의 통합
            - 이타적 경영과 사회 공헌
            - 끊임없는 자기계발과 성찰
            
            말하는 방식:
            - 따뜻하면서도 확고한 신념
            - 철학적 깊이가 있는 경영론
            - 실천적이고 구체적인 조언
            - 인간적 가치를 중시하는 접근
            
            주제에 대해 인간적 가치와 올바른 경영 철학으로 조언해주세요."""
        ),
        WisdomPersona(
            id="dale_carnegie",
            name="데일 카네기님",
            category="경영 대가",
            philosophy="인간 관계와 소통을 통한 성공",
            speaking_style="실용적이고 친근한 방식으로 인간관계의 원리를 설명하는 방식",
            famous_quote="다른 사람의 입장에서 사물을 보는 능력은 세상에서 가장 중요한 능력 중 하나이다",
            system_prompt="""당신은 데일 카네기(Dale Carnegie)입니다.
            
            핵심 철학:
            - 인간관계의 중요성
            - 효과적인 소통과 설득
            - 긍정적 사고와 자신감
            - 상대방을 이해하고 공감하기
            
            말하는 방식:
            - 친근하고 격려하는 어조
            - 실용적이고 구체적인 조언
            - 실제 사례와 경험 공유
            - 상대방의 자존감을 높이는 접근
            
            주제에 대해 인간관계와 소통의 관점에서 실용적인 조언을 해주세요."""
        ),
        
        # 게임이론가
        WisdomPersona(
            id="john_nash",
            name="존 내쉬님",
            category="게임이론가",
            philosophy="게임이론을 통한 최적의 전략적 균형점 찾기",
            speaking_style="수학적 논리와 게임이론으로 전략적 상황을 분석하는 방식",
            famous_quote="경쟁과 협력의 균형에서 최적해를 찾을 수 있다",
            system_prompt="""당신은 존 내쉬(John Nash)입니다.
            
            핵심 철학:
            - 내쉬 균형: 모든 참가자가 최적 전략을 선택하는 상태
            - 게임이론적 사고: 상호작용에서의 전략적 분석
            - 수학적 모델링을 통한 해결책 도출
            - 경쟁과 협력의 균형
            
            말하는 방식:
            - 논리적이고 수학적인 분석
            - 전략적 상황의 구조화
            - 다양한 시나리오와 결과 예측
            - 객관적이고 체계적인 접근
            
            주제에 대해 게임이론적 관점에서 전략적 균형점을 찾는 조언을 해주세요."""
        ),
        WisdomPersona(
            id="thomas_schelling",
            name="토마스 셸링님",
            category="게임이론가",
            philosophy="전략적 행동과 협상에서의 심리적 요소 분석",
            speaking_style="전략적 상황에서 인간의 행동 패턴을 분석하여 실용적 해법을 제시하는 방식",
            famous_quote="때로는 약속을 지킬 수 없게 만드는 것이 더 강한 협상력을 만든다",
            system_prompt="""당신은 토마스 셸링(Thomas Schelling)입니다.
            
            핵심 철학:
            - 전략적 행동과 협상 이론
            - 심리적 요소가 전략에 미치는 영향
            - 공약(commitment)의 전략적 활용
            - 갈등과 협력의 동역학
            
            말하는 방식:
            - 인간 행동의 심리적 분석
            - 실제 상황에 적용 가능한 전략
            - 협상과 갈등 해결의 실용적 접근
            - 창의적이고 역발상적 사고
            
            주제에 대해 전략적 행동과 협상의 관점에서 심리적 요소를 고려한 조언을 해주세요."""
        ),
    ]

def run_wisdom_conversation_round(discussion: 'WisdomDiscussion') -> bool:
    """🎯 위인 대화 체인 시스템 - Virtual Meeting 방식"""
    if not discussion.should_continue():
        return False
    
    # 현재 발언자 가져오기
    current_persona = discussion.get_next_speaker()
    if not current_persona:
        return False
    
    # 모델 선택
    selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
    
    # 기본 대화 히스토리
    conversation_history = "\n".join([
        f"{msg.persona_name}: {msg.content}" 
        for msg in discussion.messages[-10:]  # 최근 10개 메시지
    ])
    
    # 파일 내용 준비
    file_content = ""
    if discussion.uploaded_files_content and discussion.topic:
        topic_keywords = discussion.topic.replace(',', ' ').replace('.', ' ').split()
        topic_keywords = [k.strip().lower() for k in topic_keywords if len(k.strip()) >= 2]
        file_content = discussion.get_relevant_file_content(topic_keywords)
    
    # AI 응답 생성
    response = generate_ai_response(
        current_persona,
        conversation_history,
        discussion.topic,
        file_content,
        selected_model
    )
    
    # 메시지 추가
    discussion.add_message(current_persona.id, response)
    
    # 발언자 순서 진행
    discussion.advance_speaker()
    
    return True

def generate_ai_response(persona: WisdomPersona, conversation_history: str, topic: str, file_content: str = "", model_name: str = "gpt-4o-mini") -> str:
    """위인 AI 응답 생성"""
    try:
        if model_name.startswith('claude'):
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key or anthropic_key.strip() == '':
                raise ValueError("Anthropic API 키가 필요합니다.")
            client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '':
                raise ValueError("OpenAI API 키가 필요합니다.")
            client = OpenAI(api_key=openai_key)
        
        content_with_files = f"""토론 주제: {topic}

{f"=== 참고 자료 ===\n{file_content}\n" if file_content else ""}

지금까지의 대화:
{conversation_history}

위 내용을 바탕으로 {persona.name}의 관점에서 지혜로운 조언을 해주세요.
"""
        
        if model_name.startswith('claude'):
            response = client.messages.create(
                model=model_name,
                max_tokens=800,
                temperature=0.7,
                system=persona.system_prompt,
                messages=[{"role": "user", "content": content_with_files}]
            )
            return response.content[0].text.strip()
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": persona.system_prompt},
                    {"role": "user", "content": content_with_files}
                ],
                max_tokens=800,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"죄송합니다. 현재 응답을 생성할 수 없습니다. ({str(e)})"

def connect_to_db():
    """데이터베이스 연결"""
    try:
        conn = mysql.connector.connect(
            user=SQL_USER,
            password=SQL_PASSWORD,
            host=SQL_HOST,
            database=SQL_DATABASE_NEWBIZ,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

def save_wisdom_discussion_record(discussion: 'WisdomDiscussion', discussion_log: str, summary: str) -> bool:
    """토론 기록을 데이터베이스에 저장"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 참가자 목록 생성
        participants = ", ".join([p.name for p in discussion.selected_personas])
        
        # 세션 ID 생성
        session_id = f"wisdom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # 통계 정보 계산
        total_messages = len(discussion.messages)
        user_messages = sum(1 for msg in discussion.messages if msg.is_human_input)
        ai_messages = total_messages - user_messages
        
        # 지속 시간 계산 (분)
        duration_minutes = 0
        if discussion.start_time:
            duration = datetime.now() - discussion.start_time
            duration_minutes = int(duration.total_seconds() / 60)
        
        # wisdom_discussions 테이블에 저장 (올바른 컬럼명 사용)
        cursor.execute("""
            INSERT INTO wisdom_discussions 
            (session_id, topic, participants, discussion_log, summary, 
             total_messages, user_messages, ai_messages, duration_minutes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session_id,
            discussion.topic,
            participants,
            discussion_log,
            summary,
            total_messages,
            user_messages,
            ai_messages,
            duration_minutes,
            'completed'
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"토론 기록 저장 오류: {err}")
        return False

def get_saved_wisdom_discussions() -> List[Dict]:
    """저장된 토론 기록 목록 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return []
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, topic, created_at, participants, status, total_messages
            FROM wisdom_discussions
            ORDER BY created_at DESC
        """)
        
        records = []
        for row in cursor.fetchall():
            records.append({
                'discussion_id': row[0],  # id를 discussion_id로 매핑
                'topic': row[1],
                'discussion_date': row[2],  # created_at을 discussion_date로 매핑
                'participants': row[3],
                'created_at': row[2],
                'status': row[4],
                'message_count': row[5]
            })
        
        cursor.close()
        conn.close()
        return records
        
    except mysql.connector.Error as err:
        st.error(f"토론 기록 조회 오류: {err}")
        return []

def get_wisdom_discussion_detail(discussion_id: int) -> Dict:
    """특정 토론 기록 상세 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, topic, created_at, participants, discussion_log, summary, 
                   total_messages, user_messages, ai_messages, duration_minutes, status
            FROM wisdom_discussions
            WHERE id = %s
        """, (discussion_id,))
        
        row = cursor.fetchone()
        if row:
            record = {
                'discussion_id': row[0],  # id를 discussion_id로 매핑
                'topic': row[1],
                'discussion_date': row[2],  # created_at을 discussion_date로 매핑
                'participants': row[3],
                'full_content': row[4],  # discussion_log를 full_content로 매핑
                'ai_summary': row[5],  # summary를 ai_summary로 매핑
                'ai_model': 'N/A',  # ai_model 컬럼이 없으므로 기본값
                'created_at': row[2],
                'total_messages': row[6],
                'user_messages': row[7],
                'ai_messages': row[8],
                'duration_minutes': row[9],
                'status': row[10]
            }
        else:
            record = {}
        
        cursor.close()
        conn.close()
        return record
        
    except mysql.connector.Error as err:
        st.error(f"토론 기록 상세 조회 오류: {err}")
        return {}

def delete_wisdom_discussion_record(discussion_id: int) -> bool:
    """토론 기록 삭제"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wisdom_discussions WHERE id = %s", (discussion_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"토론 기록 삭제 오류: {err}")
        return False

def generate_wisdom_discussion_summary(discussion_log: str, model_name: str = "gpt-4o-mini") -> str:
    """AI를 사용하여 토론 요약 생성"""
    try:
        # 모델에 따른 클라이언트 설정
        if model_name.startswith('claude'):
            # Anthropic Claude 모델
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key or anthropic_key.strip() == '' or anthropic_key == 'NA':
                return "AI 요약을 생성할 수 없습니다. Anthropic API 키를 확인해주세요."
            
            client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            # OpenAI 모델
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                return "AI 요약을 생성할 수 없습니다. OpenAI API 키를 확인해주세요."
            
            client = OpenAI(api_key=openai_key)
        
        system_prompt = """당신은 위인들의 토론 요약 전문가입니다. 주어진 토론 내용을 바탕으로 다음 형식으로 요약해주세요:

## 🏛️ 위인들의 지혜 토론 요약

### 🎯 토론 주제와 핵심 쟁점
- 논의된 주제의 핵심과 주요 관점들

### 🧙‍♂️ 위인별 주요 관점
- 각 위인의 철학과 사상에 기반한 핵심 의견들

### 💎 도출된 지혜와 통찰
- 토론을 통해 얻은 깊이 있는 통찰과 지혜

### 🤝 공통된 가치와 차이점
- 위인들 간의 공통된 견해와 흥미로운 차이점

### 📚 실생활 적용 방안
- 논의된 내용을 현실에 적용할 수 있는 구체적 방법

### 🔮 추가 탐구 주제
- 더 깊이 논의해볼 만한 관련 주제들

각 위인의 고유한 철학과 사상을 반영하여 요약하되, 현대적 관점에서의 실용적 가치도 포함해주세요."""

        user_message = f"다음 위인들의 토론 내용을 요약해주세요:\n\n{discussion_log}"
        
        if model_name.startswith('claude'):
            # Claude API 호출
            response = client.messages.create(
                model=model_name,
                max_tokens=1200,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text.strip()
        else:
            # OpenAI API 호출
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1200,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"요약 생성 중 오류가 발생했습니다: {str(e)}"

def generate_wisdom_discussion_log(discussion: 'WisdomDiscussion') -> str:
    """토론 기록 생성"""
    log = f"""# 🏛️ 위인들의 지혜 토론 기록

## 🎯 토론 정보
- **주제**: {discussion.topic}
- **시작 시간**: {discussion.start_time.strftime('%Y-%m-%d %H:%M:%S') if discussion.start_time else 'N/A'}
- **총 라운드**: {discussion.current_round}
- **참여 위인 수**: {len(discussion.selected_personas)}명

## 🏛️ 참여 위인 목록
"""
    for persona in discussion.selected_personas:
        log += f"- 🧙‍♂️ **{persona.name}** ({persona.category})\n"
        log += f"  - **철학**: {persona.philosophy}\n"
        log += f"  - **명언**: \"{persona.famous_quote}\"\n\n"
    
    log += f"\n## 💬 토론 내용 ({len(discussion.messages)}개 메시지)\n\n"
    
    current_round = 0
    for i, message in enumerate(discussion.messages):
        # 라운드 구분
        if i > 0 and not message.is_human_input:
            speaker_index = [j for j, p in enumerate(discussion.selected_personas) 
                           if p.id == message.persona_id]
            if speaker_index and speaker_index[0] == 0:
                current_round += 1
                log += f"\n### 🔄 라운드 {current_round}\n\n"
        
        # 메시지 추가
        icon = "🏛️" if not message.is_human_input else "👤"
        
        log += f"**{message.timestamp.strftime('%H:%M:%S')}** {icon} **{message.persona_name}**\n"
        log += f"> {message.content}\n\n"
    
    log += f"\n---\n*토론 기록 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    return log

def initialize_session_state():
    """세션 상태 초기화"""
    # 강제 초기화 옵션 (문제 해결용)
    if st.sidebar.button("🔄 세션 초기화 (문제 해결용)", help="display_message 오류가 발생하면 클릭하세요"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    if 'wisdom_discussion' not in st.session_state:
        st.session_state.wisdom_discussion = WisdomDiscussion()
    else:
        # 기존 객체에 새로운 속성들이 없으면 추가 (호환성 유지)
        discussion = st.session_state.wisdom_discussion
        if not hasattr(discussion, 'last_message_time'):
            discussion.last_message_time = None
        if not hasattr(discussion, 'start_time'):
            discussion.start_time = None
        if not hasattr(discussion, 'natural_timing'):
            discussion.natural_timing = True
    
    if 'selected_ai_model' not in st.session_state:
        st.session_state.selected_ai_model = 'gpt-4o-mini'

def main():
    
    st.markdown("### 역사상 위대한 인물들과 함께하는 지혜로운 토론의 장")
    
    # 세션 상태 초기화
    initialize_session_state()
    discussion = st.session_state.wisdom_discussion
    
    # 사이드바 - 토론 설정
    with st.sidebar:
        st.header("⚙️ 토론 설정")
        
        # AI 모델 선택
        st.subheader("🤖 AI 모델 설정")
        
        available_models = []
        if os.environ.get('ANTHROPIC_API_KEY'):
            available_models.extend(['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'])
        if os.environ.get('OPENAI_API_KEY'):
            available_models.extend(['gpt-4o', 'gpt-4o-mini'])
        
        if not available_models:
            available_models = ['gpt-4o-mini']
        
        current_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
        if current_model not in available_models and available_models:
            current_model = available_models[0]
            st.session_state.selected_ai_model = current_model
        
        selected_model = st.selectbox(
            '🧠 AI 모델 선택',
            options=available_models,
            index=available_models.index(current_model) if current_model in available_models else 0,
            help='Claude는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
        )
        
        if selected_model != st.session_state.get('selected_ai_model'):
            st.session_state.selected_ai_model = selected_model
        
        st.divider()
        
        # 토론 주제
        discussion.topic = st.text_area(
            "📝 토론 주제",
            value=discussion.topic,
            help="위인들과 함께 토론하고 싶은 주제를 입력하세요",
            placeholder="예: 리더십의 진정한 의미는 무엇인가?"
        )
        
        # 설정들
        discussion.max_rounds = st.slider("🔄 최대 토론 라운드", 3, 20, discussion.max_rounds)
        discussion.speaking_speed = st.slider("⏱️ 발언 간격 (초)", 1, 10, discussion.speaking_speed)
        
        # 타이핑 속도 설정 (Virtual Meeting 완전 동일 방식)
        st.subheader("⌨️ 화면 표시 설정")
        
        # 타이핑 속도 옵션
        typing_options = {
            "매우 빠름 (0.02초)": 0.02,
            "빠름 (0.05초)": 0.05,
            "보통 (0.1초)": 0.1,
            "느림 (0.15초)": 0.15,
            "매우 느림 (0.25초)": 0.25,
            "커스텀": "custom"
        }
        
        # 현재 설정된 값에 맞는 옵션 찾기
        current_option = "보통 (0.1초)"  # 기본값
        for option, value in typing_options.items():
            if value == discussion.typing_speed:
                current_option = option
                break
        
        selected_option = st.selectbox(
            "💬 텍스트 타이핑 속도",
            options=list(typing_options.keys()),
            index=list(typing_options.keys()).index(current_option),
            help="위인들의 발언이 화면에 타이핑되어 나오는 속도를 조절합니다"
        )
        
        if typing_options[selected_option] == "custom":
            discussion.typing_speed = st.slider(
                "커스텀 타이핑 속도 (초/단어)",
                min_value=0.01,
                max_value=0.5,
                value=discussion.typing_speed,
                step=0.01,
                help="숫자가 낮을수록 빠르게 타이핑됩니다"
            )
        else:
            discussion.typing_speed = typing_options[selected_option]
        
        # 타이핑 속도 미리보기
        with st.expander("⚡ 타이핑 속도 미리보기", expanded=False):
            if st.button("🎬 테스트 해보기"):
                sample_text = "안녕하세요! 이것은 타이핑 속도 테스트입니다. 현재 설정된 속도로 텍스트가 표시됩니다."
                st.write("**샘플 텍스트:**")
                st.write_stream(stream_response(sample_text, discussion.typing_speed))
                st.caption(f"현재 설정: {discussion.typing_speed}초/단어")
        
        # 자동 모드
        discussion.auto_mode = st.toggle("🤖 자동 토론 모드", value=discussion.auto_mode)
        
        st.divider()
        
        # 파일 업로드
        st.header("📁 참고 자료 업로드")
        uploaded_files = st.file_uploader(
            "파일을 업로드하세요",
            type=['txt','md','pdf', 'docx', 'csv'],
            accept_multiple_files=True,
            help="위인들이 참고할 자료를 업로드하세요"
        )
        
        if uploaded_files:
            if st.button("📄 파일 처리"):
                with st.spinner("파일을 처리 중입니다..."):
                    combined_content = ""
                    for file in uploaded_files:
                        content = extract_text_from_file(file)
                        combined_content += f"\n--- {file.name} ---\n{content}\n"
                    
                    discussion.uploaded_files_content = combined_content
                    st.success(f"✅ {len(uploaded_files)}개 파일이 처리되었습니다!")
            
            if discussion.uploaded_files_content:
                analysis = discussion.analyze_uploaded_files()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📄 총 길이", f"{analysis.get('total_length', 0):,}자")
                with col2:
                    st.metric("📝 단어 수", f"{analysis.get('word_count', 0):,}개")
                with col3:
                    st.metric("🔑 키워드", f"{len(analysis.get('keywords', [])):,}개")
                
                if analysis.get('keywords'):
                    st.write("**🔑 핵심 키워드:**")
                    keyword_display = ", ".join(analysis['keywords'][:10])
                    st.info(keyword_display)
    
    # 메인 영역
    tab1, tab2, tab3, tab4 = st.tabs(["🏛️ 위인 선택", "💬 토론 진행", "📊 토론 현황", "📝 토론 기록"])
    
    with tab1:
        st.header("🏛️ 위인 선택")
        
        if discussion.selected_personas:
            st.write("**현재 선택된 위인들:**")
            cols = st.columns(min(len(discussion.selected_personas), 3))
            for i, persona in enumerate(discussion.selected_personas):
                with cols[i % 3]:
                    with st.container():
                        st.write(f"**{persona.name}** ({persona.category})")
                        st.caption(f"💭 {persona.famous_quote}")
                        if st.button(f"❌ 제외", key=f"remove_{persona.id}"):
                            discussion.remove_persona(persona.id)
                            st.rerun()
        else:
            st.info("👇 아래에서 토론에 참여할 위인들을 선택해주세요 (최대 6명)")
        
        st.divider()
        
        all_personas = get_wisdom_personas()
        categories = ["4대 성인", "동양 사상가", "전략가", "경영 대가", "게임이론가"]
        
        for category in categories:
            with st.expander(f"📚 {category}", expanded=False):
                category_personas = [p for p in all_personas if p.category == category]
                
                for persona in category_personas:
                    is_selected = any(p.id == persona.id for p in discussion.selected_personas)
                    
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{persona.name}**")
                        st.caption(f"📖 **철학:** {persona.philosophy}")
                        st.caption(f"💬 **명언:** \"{persona.famous_quote}\"")
                        st.caption(f"🗣️ **말하는 방식:** {persona.speaking_style}")
                    
                    with col2:
                        if is_selected:
                            st.success("✅ 선택됨")
                        else:
                            if len(discussion.selected_personas) >= 6:
                                st.warning("최대 6명")
                            else:
                                if st.button("➕ 선택", key=f"add_{persona.id}"):
                                    if discussion.add_persona(persona):
                                        st.success(f"{persona.name}이 추가되었습니다!")
                                        st.rerun()
                    st.divider()
    
    with tab2:
        st.subheader("💬 토론 진행")
        
        if not discussion.topic:
            st.warning("⚠️ 토론 주제를 입력해주세요.")
        elif not discussion.selected_personas:
            st.warning("⚠️ 최소 1명의 위인을 선택해주세요.")
        else:
            # 토론 제어 버튼
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if not discussion.is_active:
                    if st.button("🚀 토론 시작", type="primary", use_container_width=True):
                        discussion.is_active = True
                        discussion.start_time = datetime.now()
                        st.success("✅ 토론이 시작되었습니다!")
                        st.rerun()
                else:
                    if st.button("⏸️ 토론 중단", use_container_width=True):
                        discussion.is_active = False
                        st.success("⏸️ 토론이 중단되었습니다.")
                        st.rerun()
            
            with col2:
                if discussion.is_active and not discussion.auto_mode:
                    if st.button("➡️ 다음 발언", type="secondary", use_container_width=True):
                        current_speaker = discussion.get_next_speaker()
                        if current_speaker:
                            with st.spinner(f"🤔 {current_speaker.name}이 생각 중입니다..."):
                                if run_wisdom_conversation_round(discussion):
                                    st.success(f"✅ {current_speaker.name}의 발언이 추가되었습니다!")
                                    st.rerun()
                                else:
                                    st.error("토론을 계속할 수 없습니다.")
                        else:
                            st.error("발언할 위인을 찾을 수 없습니다.")
            
            with col3:
                if discussion.is_active:
                    if st.button("🏁 토론 종료", use_container_width=True):
                        discussion.is_active = False
                        st.success("🏁 토론이 종료되었습니다.")
                        st.rerun()
            
            # 사용자 참여
            if discussion.is_active:
                st.divider()
                st.write("**💬 대화에 참여하기**")
                user_input = st.text_area(
                    "당신의 의견을 입력하세요:",
                    height=100,
                    placeholder="위인들과의 토론에 참여해보세요..."
                )
                
                if st.button("📝 의견 제출", type="primary"):
                    if user_input.strip():
                        discussion.add_message("user", user_input, is_human_input=True)
                        st.success("✅ 의견이 제출되었습니다!")
                        st.rerun()
            
            st.divider()
            
            # 🎯 자동 토론 상태 표시 (Virtual Meeting 완전 동일 방식)
            if discussion.auto_mode:
                st.success(f"🚀 자동 진행 모드 활성화 - {discussion.speaking_speed}초마다 자동 발언")
                st.info(f"🎯 목표: {discussion.max_rounds}라운드까지 자동 완료")
                
                # 자동 진행 상태 표시 - 정확한 시간 계산
                col1, col2 = st.columns([3, 1])
                with col1:
                    if discussion.last_message_time:
                        time_since_last = (datetime.now() - discussion.last_message_time).total_seconds()
                        remaining_time = max(0, discussion.speaking_speed - time_since_last)
                        progress_value = min(1.0, (discussion.speaking_speed - remaining_time) / discussion.speaking_speed)
                        
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
                        discussion.auto_mode = False
                        st.info("자동 모드가 중단되었습니다.")
                        st.rerun()
            
            # 메시지 표시
            st.write("**📜 토론 내용**")
            
            # 디버깅 정보
            if st.checkbox("🔍 디버그 정보 표시"):
                st.write(f"**디버그 정보:**")
                st.write(f"- 총 메시지 수: {len(discussion.messages)}")
                st.write(f"- 토론 활성 상태: {discussion.is_active}")
                st.write(f"- 자동 모드: {discussion.auto_mode}")
                st.write(f"- 현재 라운드: {discussion.current_round}")
                st.write(f"- 선택된 위인 수: {len(discussion.selected_personas)}")
                if discussion.selected_personas:
                    st.write(f"- 선택된 위인들: {[p.name for p in discussion.selected_personas]}")
            
            if discussion.messages:
                st.success(f"✅ {len(discussion.messages)}개의 메시지가 있습니다.")
                for i, message in enumerate(discussion.messages):
                    is_latest = (i == len(discussion.messages) - 1)
                    display_message(message, is_latest)
            else:
                st.info("💡 토론이 시작되면 대화 내용이 여기에 표시됩니다.")
    
    with tab3:
        st.subheader("📊 토론 현황")
        
        if discussion.is_active or discussion.messages:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🗣️ 총 발언 수", len(discussion.messages))
            
            with col2:
                st.metric("🔄 현재 라운드", discussion.current_round)
            
            with col3:
                progress = min(discussion.current_round / discussion.max_rounds, 1.0)
                st.metric("📈 진행률", f"{progress:.1%}")
            
            with col4:
                if discussion.is_active:
                    next_speaker = discussion.get_next_speaker()
                    if next_speaker:
                        st.metric("🎯 다음 발언자", next_speaker.name)
                    else:
                        st.metric("🎯 상태", "완료")
                else:
                    st.metric("🎯 상태", "중단됨")
            
            st.progress(progress, text=f"토론 진행률: {discussion.current_round}/{discussion.max_rounds} 라운드")
            
            # 자동 모드 상태 표시
            if discussion.auto_mode:
                auto_status = "🟢 실행 중" if st.session_state.get('auto_running', False) else "🟡 대기 중"
                st.info(f"🤖 자동 모드: {auto_status}")
            
            if discussion.messages:
                st.write("**📈 참가자별 발언 통계**")
                
                speaker_stats = {}
                for msg in discussion.messages:
                    if msg.persona_name not in speaker_stats:
                        speaker_stats[msg.persona_name] = 0
                    speaker_stats[msg.persona_name] += 1
                
                df_stats = pd.DataFrame(list(speaker_stats.items()), columns=['참가자', '발언 수'])
                st.bar_chart(df_stats.set_index('참가자'))
                
                # 최근 발언자 순서 표시
                if len(discussion.messages) > 0:
                    st.write("**🕒 최근 발언 순서**")
                    recent_messages = discussion.messages[-5:] if len(discussion.messages) > 5 else discussion.messages
                    for i, msg in enumerate(recent_messages):
                        time_str = msg.timestamp.strftime('%H:%M:%S')
                        st.caption(f"{len(discussion.messages) - len(recent_messages) + i + 1}. {time_str} - {msg.persona_name}")
        else:
            st.info("토론이 시작되면 현황이 표시됩니다.")

    with tab4:
        st.header("📝 토론 기록")
        
        # 서브탭 생성
        subtab1, subtab2, subtab3 = st.tabs(["📝 현재 토론 기록", "💾 토론 기록 저장", "📚 저장된 토론 기록"])
        
        with subtab1:
            st.subheader("📝 현재 토론 내용")
            
            if discussion.messages:
                # 토론 기록 생성
                discussion_log = generate_wisdom_discussion_log(discussion)
                
                # 다운로드 버튼
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    st.download_button(
                        label="📥 Markdown 다운로드",
                        data=discussion_log,
                        file_name=f"wisdom_discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
                with col2:
                    # JSON 형태로도 다운로드 가능
                    json_data = {
                        "discussion_info": {
                            "topic": discussion.topic,
                            "start_time": discussion.start_time.isoformat() if discussion.start_time else None,
                            "max_rounds": discussion.max_rounds,
                            "participants": [{"name": p.name, "category": p.category, "philosophy": p.philosophy} for p in discussion.selected_personas]
                        },
                        "messages": [
                            {
                                "timestamp": msg.timestamp.isoformat(),
                                "speaker": msg.persona_name,
                                "content": msg.content,
                                "is_human_input": msg.is_human_input
                            } for msg in discussion.messages
                        ]
                    }
                    
                    st.download_button(
                        label="📊 JSON 다운로드",
                        data=json.dumps(json_data, ensure_ascii=False, indent=2),
                        file_name=f"wisdom_discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
                # 토론 기록 미리보기
                st.subheader("👀 토론 기록 미리보기")
                st.markdown(discussion_log)
            else:
                st.info("ℹ️ 토론 기록이 비어있습니다.")
        
        with subtab2:
            st.subheader("💾 토론 기록 데이터베이스 저장")
            
            if discussion.messages:
                # 토론 기록 생성
                discussion_log = generate_wisdom_discussion_log(discussion)
                
                # AI 요약 생성 버튼
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**📋 AI 토론 요약 생성**")
                    st.caption("AI가 위인들의 토론 내용을 분석하여 구조화된 요약을 생성합니다.")
                
                with col2:
                    if st.button("🤖 AI 요약 생성", type="secondary"):
                        with st.spinner("AI가 토론 내용을 요약하고 있습니다..."):
                            selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                            summary = generate_wisdom_discussion_summary(discussion_log, selected_model)
                            st.session_state.discussion_summary = summary
                
                # 생성된 요약 표시
                if 'discussion_summary' in st.session_state:
                    st.subheader("📋 AI 생성 요약")
                    st.markdown(st.session_state.discussion_summary)
                    
                    # 저장 버튼
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("💾 토론 기록 저장", type="primary"):
                            if save_wisdom_discussion_record(discussion, discussion_log, st.session_state.discussion_summary):
                                st.success("✅ 토론 기록이 성공적으로 저장되었습니다!")
                                # 요약 세션 상태 클리어
                                if 'discussion_summary' in st.session_state:
                                    del st.session_state.discussion_summary
                                st.rerun()
                            else:
                                st.error("❌ 토론 기록 저장에 실패했습니다.")
                    
                    with col2:
                        if st.button("🔄 요약 재생성"):
                            if 'discussion_summary' in st.session_state:
                                del st.session_state.discussion_summary
                            st.rerun()
                else:
                    st.info("💡 먼저 'AI 요약 생성' 버튼을 클릭하여 토론 요약을 생성해주세요.")
                
                # 저장 정보 안내
                st.markdown("""
                ---
                ### 📊 저장될 정보
                - **토론 주제**: {topic}
                - **토론 일시**: {date}
                - **참여 위인**: {participants}
                - **전체 토론 내용**: 모든 발언 내용
                - **AI 요약**: 구조화된 토론 요약
                """.format(
                    topic=discussion.topic,
                    date=discussion.start_time.strftime('%Y-%m-%d %H:%M:%S') if discussion.start_time else "미정",
                    participants=", ".join([p.name for p in discussion.selected_personas])
                ))
            else:
                st.info("ℹ️ 저장할 토론 내용이 없습니다.")
        
        with subtab3:
            st.subheader("📚 저장된 토론 기록 관리")
            
            # 저장된 토론 기록 목록 조회
            saved_records = get_saved_wisdom_discussions()
            
            if saved_records:
                # 검색 기능
                search_term = st.text_input("🔍 토론 기록 검색", placeholder="토론 주제나 위인명으로 검색...")
                
                # 검색 필터링
                if search_term:
                    filtered_records = [
                        record for record in saved_records 
                        if search_term.lower() in record['topic'].lower() or 
                           search_term.lower() in record['participants'].lower()
                    ]
                else:
                    filtered_records = saved_records
                
                st.write(f"**📊 총 {len(filtered_records)}개의 토론 기록이 있습니다.**")
                
                # 토론 기록 목록 표시
                for record in filtered_records:
                    # 상태에 따른 아이콘 설정
                    status_icon = "✅" if record.get('status') == 'completed' else "⏸️"
                    message_count = record.get('message_count', 0)
                    
                    with st.expander(f"{status_icon} {record['discussion_date'].strftime('%Y-%m-%d %H:%M')} - {record['topic']} ({message_count}개 메시지)", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**참여 위인**: {record['participants']}")
                            st.write(f"**저장일시**: {record['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                            if record.get('status'):
                                status_text = "완료됨" if record['status'] == 'completed' else record['status']
                                st.write(f"**상태**: {status_text}")
                        
                        with col2:
                            if st.button("📖 상세보기", key=f"view_{record['discussion_id']}"):
                                st.session_state.selected_discussion_id = record['discussion_id']
                        
                        with col3:
                            if st.button("🗑️ 삭제", key=f"delete_{record['discussion_id']}", type="secondary"):
                                if delete_wisdom_discussion_record(record['discussion_id']):
                                    st.success("✅ 토론 기록이 삭제되었습니다.")
                                    st.rerun()
                                else:
                                    st.error("❌ 삭제에 실패했습니다.")
                
                # 선택된 토론 기록 상세 보기
                if 'selected_discussion_id' in st.session_state:
                    st.markdown("---")
                    st.subheader("📖 토론 기록 상세 내용")
                    
                    detail = get_wisdom_discussion_detail(st.session_state.selected_discussion_id)
                    if detail:
                        # 기본 정보
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**📋 토론 주제**: {detail['topic']}")
                            st.write(f"**📅 토론 일시**: {detail['discussion_date'].strftime('%Y-%m-%d %H:%M:%S')}")
                            if detail.get('duration_minutes'):
                                st.write(f"**⏱️ 토론 시간**: {detail['duration_minutes']}분")
                        with col2:
                            st.write(f"**🏛️ 참여 위인**: {detail['participants']}")
                            st.write(f"**💾 저장일시**: {detail['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                            if detail.get('status'):
                                status_text = "완료됨" if detail['status'] == 'completed' else detail['status']
                                st.write(f"**📊 상태**: {status_text}")
                        
                        # 메시지 통계
                        if detail.get('total_messages'):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("💬 총 메시지", detail.get('total_messages', 0))
                            with col2:
                                st.metric("👤 사용자 메시지", detail.get('user_messages', 0))
                            with col3:
                                st.metric("🏛️ 위인 메시지", detail.get('ai_messages', 0))
                        
                        # 탭으로 구분된 내용
                        detail_tab1, detail_tab2 = st.tabs(["📋 AI 요약", "📝 전체 토론 기록"])
                        
                        with detail_tab1:
                            if detail['ai_summary']:
                                st.markdown(detail['ai_summary'])
                            else:
                                st.info("요약이 없습니다.")
                        
                        with detail_tab2:
                            if detail['full_content']:
                                st.markdown(detail['full_content'])
                            else:
                                st.info("토론 기록이 없습니다.")
                        
                        # 다운로드 버튼
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                label="📥 요약 다운로드",
                                data=detail['ai_summary'] or "요약 없음",
                                file_name=f"wisdom_summary_{detail['discussion_id']}.md",
                                mime="text/markdown"
                            )
                        with col2:
                            st.download_button(
                                label="📥 전체 토론 기록 다운로드",
                                data=detail['full_content'] or "토론 기록 없음",
                                file_name=f"wisdom_full_{detail['discussion_id']}.md",
                                mime="text/markdown"
                            )
                        with col3:
                            if st.button("❌ 상세보기 닫기"):
                                if 'selected_discussion_id' in st.session_state:
                                    del st.session_state.selected_discussion_id
                                st.rerun()
                    else:
                        st.error("토론 기록을 찾을 수 없습니다.")
            else:
                st.info("📝 저장된 토론 기록이 없습니다. 토론을 진행한 후 '토론 기록 저장' 탭에서 저장해보세요.")

    # 🚀 자동 모드 실행 로직 (Virtual Meeting 완전 동일 방식)
    if discussion.auto_mode and discussion.is_active:
        if discussion.should_continue():
            if discussion.is_time_to_speak():
                # 자동 대화 진행
                success = run_wisdom_conversation_round(discussion)
                if success:
                    # 새로운 메시지가 추가되었으므로 즉시 새로고침
                    st.rerun()
                else:
                    # 토론 자동 종료
                    discussion.is_active = False
                    discussion.auto_mode = False
                    st.success("✅ 자동 토론이 완료되었습니다.")
                    st.rerun()
            else:
                # 시간이 안 되었으면 0.5초 후 다시 체크 (더 빠른 반응)
                time.sleep(0.5)
                st.rerun()
        else:
            # 토론 종료
            discussion.is_active = False
            discussion.auto_mode = False
            st.success(f"🏁 {discussion.max_rounds}라운드 토론이 완료되었습니다!")
            st.balloons()
            st.rerun()

if __name__ == "__main__":
    main() 