import streamlit as st
from openai import OpenAI
import anthropic
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
import mysql.connector

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Virtual Meeting Enhanced - AI 가상 회의",
    page_icon="👥💻",
    layout="wide"
)
st.title("👥💻 Virtual Meeting Enhanced - AI 가상 회의")

# 인증 기능 (간단한 비밀번호 보호)
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
        if password:
            st.error("관리자 권한이 필요합니다")
        st.stop()
        
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
        self.round_summaries: Dict[int, str] = {}  # 라운드별 요약 저장
        self.key_insights: List[str] = []  # 주요 인사이트 저장
        self.file_analysis: Dict[str, Any] = {}  # 업로드된 파일 분석 결과
        self.file_keywords: List[str] = []  # 파일에서 추출된 키워드
        self.typing_speed: float = 0.1  # 타이핑 효과 속도 (초)
        self.last_moderator_intervention: datetime = None  # 마지막 사회자 개입 시간
        
        # 🎯 창의적 대화 체인 시스템
        self.conversation_chain = []  # 대화의 논리적 흐름 추적
        self.discussion_focus = ""  # 현재 논의 초점
        self.pending_questions = []  # 해결되지 않은 질문들
        self.agreements = []  # 합의된 사항들
        self.disagreements = []  # 이견이 있는 사항들
        self.manual_round_control = True  # 완전 수동 라운드 제어
        self.turn_counter = 0  # 발언 순서 카운터 (라운드와 분리)
        
        # 🔧 새로운 회의 제어 속성들
        self.original_max_rounds = 10  # 사용자가 설정한 원본 최대 라운드
        self.extension_granted = False  # 1라운드 연장 허가 여부
        self.consecutive_repetitions = 0  # 연속 반복 횟수
        self.last_meaningful_content = []  # 의미있는 최근 발언들
        
        # 🎯 ChatGPT 분석 기반 개선사항 추가
        self.content_tracker = {}  # 내용 반복 추적
        self.topic_progression = []  # 주제 진행 단계 추적
        self.decision_factors = {  # 의사결정 요소 추적
            'pros': [],
            'cons': [],
            'risks': [],
            'alternatives': []
        }
        self.persona_stance = {}  # 각 페르소나의 입장 추적
        self.natural_timing = True  # 자연스러운 타이밍 활성화
        self.conflict_introduced = False  # 갈등 요소 도입 여부
        self.decision_pressure_points = [0.3, 0.5, 0.7]  # 의사결정 압박 포인트
        
        # 🚨 사회자 중복 메시지 방지 플래그들
        self.final_message_sent = False  # 정상 종료 메시지 발송 여부
        self.extension_announced = False  # 연장 안내 메시지 발송 여부
        self.final_round_announced = False  # 최종 라운드 안내 메시지 발송 여부
        self.final_closure_sent = False  # 최종 마무리 메시지 발송 여부
        
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
        """🎯 발언자 순서 진행 및 라운드 자동 관리 (설정값은 고정)"""
        non_moderator_personas = self.get_non_moderator_personas()
        if non_moderator_personas:
            self.current_speaker_index += 1
            self.turn_counter += 1
            
            # ✅ 모든 참가자가 발언을 완료하면 라운드 자동 증가 (원래대로 복원)
            if self.current_speaker_index % len(non_moderator_personas) == 0:
                self.conversation_round += 1
                # 새 라운드 시작 시 대화 체인 상태 초기화
                self.discussion_focus = ""
                self.pending_questions = []
                self.consecutive_repetitions = 0
                
                # 🎯 라운드 진행 상황 디버깅 로그
                st.info(f"📊 라운드 {self.conversation_round} 시작 (참가자 {len(non_moderator_personas)}명 모두 발언 완료)")
    
    def get_current_round_accurately(self) -> int:
        """🎯 정확한 현재 라운드 계산 (사회자 메시지 제외)"""
        non_moderator_personas = self.get_non_moderator_personas()
        if not non_moderator_personas:
            return 1
        
        # 사회자가 아닌 메시지만 카운트
        non_moderator_messages = [msg for msg in self.messages 
                                 if not msg.is_moderator and not msg.is_human_input]
        
        # 정확한 라운드 계산
        accurate_round = (len(non_moderator_messages) - 1) // len(non_moderator_personas) + 1
        
        # 혹시 conversation_round와 다르면 동기화
        if accurate_round != self.conversation_round:
            st.warning(f"🔧 라운드 동기화: {self.conversation_round} → {accurate_round}")
            self.conversation_round = accurate_round
        
        return accurate_round
    
    def advance_round(self):
        """🎯 라운드 수동 증가 - 사용자만 호출 가능"""
        self.conversation_round += 1
        # 새 라운드 시작 시 대화 체인 상태 초기화
        self.discussion_focus = ""
        self.pending_questions = []
        self.consecutive_repetitions = 0
    
    def is_time_to_speak(self) -> bool:
        if not self.last_message_time:
            return True
        # total_seconds()를 사용하여 정확한 시간 계산
        time_diff = (datetime.now() - self.last_message_time).total_seconds()
        return time_diff >= self.speaking_speed
    
    def should_continue(self) -> bool:
        if not self.is_active:
            return False
        
        # 🎯 정확한 라운드 계산으로 확인
        current_round = self.get_current_round_accurately()
        
        # 🎯 설정된 라운드가 완료되기 전에는 절대 종료하지 않음
        if current_round < self.original_max_rounds:
            # 아직 설정된 라운드가 완료되지 않았으므로 계속 진행
            return True
        
        # 🎯 사용자 설정 최대 라운드 완료 후 처리 (2라운드 연장 시스템)
        if current_round >= self.original_max_rounds:
            if not self.extension_granted:
                # 🎯 10라운드에서 이미 마무리되었는지 확인
                if self._is_meeting_properly_concluded():
                    # 이미 충분히 마무리되었으면 연장하지 않고 정상 종료
                    self.is_active = False
                    st.success(f"🎉 {self.original_max_rounds}라운드에서 회의가 완전히 마무리되어 종료합니다.")
                    
                    # 🎯 정상 종료 시 사회자 마무리 메시지 (한 번만)
                    if not hasattr(self, 'final_message_sent'):
                        moderator = self.get_moderator()
                        if moderator:
                            final_message = f"""설정된 {self.original_max_rounds}라운드에서 회의가 성공적으로 마무리되었습니다.

모든 참가자분들이 충분히 의견을 나누고 결론을 도출해주셨습니다.
오늘 논의된 내용들을 바탕으로 좋은 결과가 있기를 기대합니다.

모든 분들의 적극적인 참여에 감사드립니다."""
                            
                            self.add_message(moderator.id, final_message)
                            self.final_message_sent = True
                    return False
                else:
                    # 마무리가 안 되었으면 2라운드 연장
                    self.extension_granted = True
                    self.max_rounds = self.original_max_rounds + 2  # 2라운드 연장
                    
                    # 🎯 사회자 시간 안내 메시지 추가 (한 번만)
                    if not hasattr(self, 'extension_announced'):
                        moderator = self.get_moderator()
                        if moderator:
                            time_notice = f"""정해진 {self.original_max_rounds}라운드가 완료되었습니다. 

회의 내용을 완전히 마무리하기 위해 추가로 2라운드를 연장하겠습니다.

📋 **연장 라운드 안내:**
- 라운드 {self.original_max_rounds + 1}: 핵심 논점 정리 및 최종 의견 제시
- 라운드 {self.original_max_rounds + 2}: 각자 최종 결론 및 마무리 인사

모든 분들께서는 지금까지의 논의 내용을 바탕으로 간결하고 명확하게 의견을 정리해 주시기 바랍니다. 특히 마지막 라운드에서는 반드시 회의를 마무리해 주세요."""
                            
                            self.add_message(moderator.id, time_notice)
                            self.extension_announced = True
                    
                    # 사용자에게 알림
                    st.info(f"🔔 설정된 {self.original_max_rounds}라운드가 완료되었으나 회의가 마무리되지 않아 2라운드 연장합니다.")
            
            elif current_round == self.original_max_rounds + 1:
                # 🎯 연장 1라운드 완료 - 마지막 라운드 공지 (한 번만)
                if not hasattr(self, 'final_round_announced'):
                    moderator = self.get_moderator()
                    if moderator:
                        final_round_announcement = f"""🏁 **연장 1라운드가 완료되었습니다**

이제 **마지막 라운드({self.original_max_rounds + 2}라운드)**에 들어갑니다.

모든 참가자께서는 다음 사항을 반드시 포함하여 발언해 주시기 바랍니다:
1. 📝 **개인 발언 요약**: 지금까지 본인이 제시한 주요 의견들
2. 🎯 **최종 결론**: 회의 주제에 대한 본인의 최종 입장
3. 🚀 **실행 방안**: 구체적인 다음 단계 제안
4. 🤝 **합의점**: 다른 참가자들과의 공통된 의견
5. 🙏 **감사 인사**: 회의 참여에 대한 마무리 인사

**이번이 마지막 기회입니다. 반드시 완전한 마무리를 해주시기 바랍니다.**"""
                        self.add_message(moderator.id, final_round_announcement)
                        self.final_round_announced = True
                return True
                
            elif current_round >= self.max_rounds:
                # 🎯 연장된 마지막 라운드에서는 모든 참가자가 발언을 완료했는지 확인
                if self._is_final_round_completed():
                    # 모든 참가자가 마지막 라운드에서 발언을 완료했으면 종료
                    self.is_active = False
                    
                    # 🎯 마무리 완료 검증 결과에 따른 메시지
                    current_round = self.get_current_round_accurately()
                    current_round_start = (current_round - 1) * len(self.get_non_moderator_personas())
                    final_messages = []
                    msg_count = 0
                    
                    for msg in self.messages:
                        if not msg.is_moderator and not msg.is_human_input:
                            if msg_count >= current_round_start:
                                final_messages.append(msg)
                            msg_count += 1
                    
                    # 마무리 품질 확인 및 사회자 최종 메시지 (한 번만)
                    if not hasattr(self, 'final_closure_sent'):
                        if hasattr(self, 'extension_granted') and self.extension_granted:
                            completion_verified = self._verify_final_round_completion(final_messages)
                            if completion_verified:
                                st.success(f"🎉 {self.max_rounds}라운드에서 모든 참가자가 히스토리 요약과 감사 인사를 완료하여 회의를 정상 종료합니다.")
                                final_message = f"""연장된 {self.max_rounds}라운드가 완료되어 회의를 마치겠습니다.

모든 참가자분들께서 자신의 발언 내용을 체계적으로 정리하고 의미 있는 마무리 인사를 해주셔서 완전한 회의 마무리가 되었습니다.

오늘 논의된 내용들이 실질적인 성과로 이어지기를 기대하며, 모든 분들의 적극적인 참여에 진심으로 감사드립니다."""
                            else:
                                st.warning(f"⚠️ {self.max_rounds}라운드 완료로 회의를 종료하지만, 일부 참가자의 마무리가 불완전할 수 있습니다.")
                                final_message = f"""연장된 {self.max_rounds}라운드가 완료되어 회의를 마치겠습니다.

시간 관계상 회의를 마무리하게 되었지만, 오늘 나온 다양한 의견들이 의미 있는 논의였습니다.

모든 분들의 참여에 감사드립니다."""
                        else:
                            st.warning(f"⏰ {self.max_rounds}라운드 완료로 회의를 종료합니다.")
                            final_message = f"예정된 {self.max_rounds}라운드가 모두 완료되어 회의를 마치겠습니다. 활발한 토론에 감사드립니다."
                        
                        # 🎯 사회자 최종 마무리 메시지 (한 번만)
                        moderator = self.get_moderator()
                        if moderator:
                            self.add_message(moderator.id, final_message)
                            self.final_closure_sent = True
                    return False
                else:
                    # 아직 모든 참가자가 발언하지 않았으면 계속 진행
                    return True
        
        # ⚠️ 설정된 라운드 완료 전에는 반복 감지나 시간 제한으로 종료하지 않음
        # 단, 연장 라운드에서는 반복 감지 적용
        if current_round >= self.original_max_rounds:
            # 🎯 반복 대화 감지로 조기 종료 (연장 라운드에서만)
            if self._detect_repetitive_conversation():
                self.is_active = False
                st.warning("🔄 반복적인 대화가 감지되어 회의를 조기 종료합니다.")
                return False
        
        # 시간 제한 체크 (연장 라운드에서만)
        if current_round >= self.original_max_rounds:
            if self.start_time:
                elapsed_time = (datetime.now() - self.start_time).total_seconds()
                if elapsed_time > (self.meeting_duration * 60):
                    self.is_active = False
                    return False
        
        return True
    
    def _detect_repetitive_conversation(self) -> bool:
        """🔄 반복적인 대화 감지 - 마무리 반복 패턴 강화 감지"""
        if len(self.messages) < 8:
            return False
        
        recent_messages = [msg for msg in self.messages[-12:] 
                          if not msg.is_moderator and not msg.is_human_input]
        
        if len(recent_messages) < 6:
            return False
        
        # 🚨 마무리 발언 반복 패턴 특별 감지 (8-10라운드 문제 해결)
        current_round = self.get_current_round_accurately()
        
        # 8라운드 이후에는 마무리 반복 패턴을 더 엄격하게 감지
        if current_round >= 8:
            # 마무리 관련 키워드 과도한 반복 감지
            finale_keywords = [
                '제가 이번 회의에서', '전체 논의를 종합', '구체적인 실행 방안',
                '함께 논의해 주신', '감사드립니다', '최종 의견', '마무리'
            ]
            
            finale_pattern_count = 0
            for msg in recent_messages[-6:]:  # 최근 6개 메시지
                content_lower = msg.content.lower()
                pattern_matches = sum(1 for keyword in finale_keywords if keyword in content_lower)
                if pattern_matches >= 3:  # 3개 이상의 마무리 패턴이 한 메시지에 있으면
                    finale_pattern_count += 1
            
            # 최근 6개 메시지 중 4개 이상이 마무리 패턴을 보이면 반복으로 판단
            if finale_pattern_count >= 4:
                self.consecutive_repetitions += 1
                return True
            
            # 동일한 문장 구조 반복 감지 (마무리 발언에서 자주 발생)
            structure_patterns = [
                '제가 이번 회의에서 제시한 핵심',
                '전체 논의를 종합해보면',
                '구체적인 실행 방안으로는',
                '특히 .*님의 의견에 동의하며',
                '오늘 함께 논의해 주신 모든 분들께 감사'
            ]
            
            structure_repetition = 0
            for pattern in structure_patterns:
                pattern_count = sum(1 for msg in recent_messages[-6:] 
                                  if pattern.replace('.*', '') in msg.content)
                if pattern_count >= 3:  # 같은 구조가 3번 이상 반복
                    structure_repetition += 1
            
            if structure_repetition >= 2:  # 2개 이상의 구조가 반복되면
                self.consecutive_repetitions += 1
                return True
        
        # 1. 🎯 내용 다양성 검사
        content_themes = self._extract_content_themes(recent_messages)
        if len(content_themes) <= 2:
            self.consecutive_repetitions += 1
            return True
        
        # 2. 🎯 키워드 반복 감지 (ChatGPT 지적 반복 키워드 포함)
        repetitive_keywords = [
            '결론', '마무리', '정리', '감사', '함께', '최상의 결과', '진행하기로',
            '지속 가능한', 'AI 기반', '브랜드 충성도', '아마존', '넷플릭스',
            '추천 알고리즘', '소비자 선호', '70% 이상', '예를 들어'
        ]
        
        keyword_frequency = {}
        for msg in recent_messages[-8:]:
            content_lower = msg.content.lower()
            for keyword in repetitive_keywords:
                if keyword in content_lower:
                    keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 1
        
        # 같은 키워드가 3번 이상 반복되면 반복으로 판단
        if any(count >= 3 for count in keyword_frequency.values()):
            self.consecutive_repetitions += 1
            return True
        
        # 3. 🎯 문장 구조 유사도 검사
        structural_similarity = self._check_structural_similarity(recent_messages)
        if structural_similarity > 0.7:
            self.consecutive_repetitions += 1
            return True
        
        # 4. 🎯 진전성 부족 감지
        if not self._has_content_progression(recent_messages):
            self.consecutive_repetitions += 1
            return True
        
        # 5. 기존 문장 유사도 검사 (더 엄격하게)
        def calculate_similarity(text1: str, text2: str) -> float:
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if len(words1) == 0 or len(words2) == 0:
                return 0.0
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            return intersection / union if union > 0 else 0.0
        
        # 최근 4개 메시지 간 유사도 검사
        similarities = []
        for i in range(len(recent_messages) - 1):
            for j in range(i + 1, len(recent_messages)):
                sim = calculate_similarity(recent_messages[i].content, recent_messages[j].content)
                similarities.append(sim)
        
        # 평균 유사도가 55% 이상이면 반복
        if similarities and sum(similarities) / len(similarities) > 0.55:
            self.consecutive_repetitions += 1
            return True
        
        return self.consecutive_repetitions >= 2
    
    def _extract_content_themes(self, messages) -> set:
        """메시지에서 주요 주제 추출"""
        themes = set()
        theme_keywords = {
            'technology': ['AI', '기술', '알고리즘', '디지털', '자동화', '인공지능'],
            'market': ['시장', '고객', '소비자', '경쟁', '점유율', '마케팅'],
            'finance': ['비용', '수익', 'ROI', '투자', '예산', '재무'],
            'strategy': ['전략', '계획', '방향', '목표', '비전', '전략적'],
            'risk': ['위험', '리스크', '우려', '문제', '제약', '부작용'],
            'execution': ['실행', '구현', '진행', '추진', '개발', '실무'],
            'product': ['제품', '서비스', '품질', '기능', '사용자', '경험'],
            'competition': ['경쟁사', '차별화', '우위', '비교', '대안', '선택']
        }
        
        for msg in messages:
            content_lower = msg.content.lower()
            for theme, keywords in theme_keywords.items():
                if any(keyword in content_lower for keyword in keywords):
                    themes.add(theme)
        
        return themes
    
    def _check_structural_similarity(self, messages) -> float:
        """문장 구조 유사도 검사"""
        if len(messages) < 3:
            return 0.0
        
        # 문장 시작 패턴 분석
        start_patterns = []
        for msg in messages[-6:]:
            sentences = msg.content.split('.')
            if sentences:
                first_sentence = sentences[0].strip()
                words = first_sentence.split()[:3]  # 첫 3단어
                if len(words) >= 2:
                    start_patterns.append(' '.join(words))
        
        # 패턴 중복도 계산
        if not start_patterns:
            return 0.0
        
        pattern_counts = {}
        for pattern in start_patterns:
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        max_count = max(pattern_counts.values())
        return max_count / len(start_patterns) if start_patterns else 0.0
    
    def _has_content_progression(self, messages) -> bool:
        """내용 진전성 확인"""
        if len(messages) < 4:
            return True
        
        # 새로운 정보나 관점 제시 확인
        progression_indicators = [
            '새로운', '추가로', '또한', '더 나아가', '구체적으로',
            '예를 들어', '반면에', '하지만', '그러나', '한편',
            '실제로', '데이터에 따르면', '경험상', '연구 결과',
            '다른 관점에서', '보완하자면', '대안으로', '개선하면'
        ]
        
        recent_progression_count = 0
        for msg in messages[-4:]:
            content_lower = msg.content.lower()
            if any(indicator in content_lower for indicator in progression_indicators):
                recent_progression_count += 1
        
        return recent_progression_count >= 2  # 최근 4개 메시지 중 2개 이상에서 진전성 확인
    
    def get_natural_typing_delay(self, content_length: int) -> float:
        """🎯 자연스러운 타이핑 지연 시간 계산"""
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
    
    def _is_conclusion_reached(self) -> bool:
        """결론이 충분히 도출되었는지 확인 - 더 정확한 판단"""
        if len(self.messages) < 6:  # 최소 메시지 수
            return False
        
        # 최근 메시지들에서 결론 패턴 확인
        recent_messages = self.messages[-8:]
        conclusion_keywords = ['결론', '마무리', '정리하면', '최종적으로', '따라서', '실행하기로', '합의']
        action_keywords = ['진행', '실행', '추진', '계획', '다음 단계', '액션']
        
        conclusion_count = 0
        action_count = 0
        
        for msg in recent_messages:
            if not msg.is_moderator and not msg.is_human_input:
                content_lower = msg.content.lower()
                
                conclusion_matches = sum(1 for keyword in conclusion_keywords if keyword in content_lower)
                action_matches = sum(1 for keyword in action_keywords if keyword in content_lower)
                
                if conclusion_matches >= 2:  # 결론 키워드 2개 이상
                    conclusion_count += 1
                if action_matches >= 1:  # 액션 키워드 1개 이상
                    action_count += 1
        
        # 최근 8개 메시지 중 4개 이상이 결론 내용이고, 2개 이상이 액션 내용이면 회의 종료
        return conclusion_count >= 4 and action_count >= 2
    
    def _is_meeting_properly_concluded(self) -> bool:
        """🚨 회의가 제대로 마무리되었는지 종합적으로 판단 - 10라운드 완료 시 사용 (강화된 감지)"""
        if len(self.messages) < 10:
            return False
        
        non_moderator_personas = self.get_non_moderator_personas()
        if not non_moderator_personas:
            return False
        
        # 🎯 8-10라운드 마무리 패턴 분석 (3개 라운드에서 반복적 마무리 감지)
        recent_round_messages = []
        start_round = max(1, self.original_max_rounds - 2)  # 8라운드부터
        
        msg_count = 0
        for msg in self.messages:
            if not msg.is_moderator and not msg.is_human_input:
                msg_round = (msg_count // len(non_moderator_personas)) + 1
                if msg_round >= start_round:
                    recent_round_messages.append(msg)
                msg_count += 1
        
        if len(recent_round_messages) < len(non_moderator_personas):
            return False
        
        # 🎯 마무리 발언 품질 검증 (validate_final_statement 활용)
        perfect_conclusions = 0
        gratitude_count = 0
        
        # 마지막 라운드(10라운드) 메시지들만 분석
        last_round_start = (self.original_max_rounds - 1) * len(non_moderator_personas)
        last_round_messages = []
        
        msg_count = 0
        for msg in self.messages:
            if not msg.is_moderator and not msg.is_human_input:
                if msg_count >= last_round_start:
                    last_round_messages.append(msg)
                msg_count += 1
        
        for msg in last_round_messages:
            # validate_final_statement로 마무리 품질 검증
            validation = validate_final_statement(msg.content, msg.persona_name)
            
            # 완벽한 마무리 발언 기준: 5가지 요소 중 4개 이상 + 감사 인사 필수
            required_elements = sum([
                validation['has_personal_summary'],
                validation['has_overall_conclusion'],
                validation['has_action_plan'],
                validation['has_participant_connection'],
                validation['has_gratitude']
            ])
            
            if validation['has_gratitude'] and required_elements >= 4:
                perfect_conclusions += 1
            
            if validation['has_gratitude']:
                gratitude_count += 1
        
        # 🎯 최근 3개 라운드에서 과도한 감사 표현 감지
        excessive_gratitude_count = 0
        for msg in recent_round_messages:
            if any(keyword in msg.content.lower() for keyword in ['감사', '고생', '수고']):
                excessive_gratitude_count += 1
        
        # 🎯 마무리 완료 판단 기준 (더 엄격하게)
        total_participants = len(non_moderator_personas)
        
        # 조건 1: 모든 참가자가 감사 인사를 했음
        all_expressed_gratitude = gratitude_count == total_participants
        
        # 조건 2: 80% 이상이 완벽한 마무리 발언을 했음
        perfect_conclusion_ratio = perfect_conclusions / total_participants
        mostly_perfect_conclusions = perfect_conclusion_ratio >= 0.8
        
        # 조건 3: 최근 3개 라운드에서 감사 표현이 참가자 수의 2배 이상 (반복적 마무리)
        excessive_gratitude = excessive_gratitude_count >= (total_participants * 2)
        
        # 🎯 최종 판단: 모든 조건이 충족되면 완전히 마무리된 것으로 판단
        is_fully_concluded = (
            all_expressed_gratitude and 
            mostly_perfect_conclusions and 
            excessive_gratitude
        )
        
        return is_fully_concluded
    
    def analyze_participant_statements_for_closure(self) -> Dict[str, Any]:
        """🎯 사회자가 참가자들의 발언 내용을 분석하여 마무리 타당성을 판단"""
        non_moderator_personas = self.get_non_moderator_personas()
        if not non_moderator_personas:
            return {"can_conclude": False, "reason": "참가자가 없습니다"}
        
        current_round = self.get_current_round_accurately()
        
        # 최근 3개 라운드 분석 (8-10라운드)
        analysis_start_round = max(1, current_round - 2)
        analysis_messages = []
        
        msg_count = 0
        for msg in self.messages:
            if not msg.is_moderator and not msg.is_human_input:
                msg_round = (msg_count // len(non_moderator_personas)) + 1
                if msg_round >= analysis_start_round:
                    analysis_messages.append({
                        'persona_name': msg.persona_name,
                        'persona_id': msg.persona_id,
                        'content': msg.content,
                        'round': msg_round,
                        'timestamp': msg.timestamp
                    })
                msg_count += 1
        
        # 1. 각 참가자별 발언 품질 분석
        participant_analysis = {}
        for persona in non_moderator_personas:
            persona_messages = [m for m in analysis_messages if m['persona_id'] == persona.id]
            
            if not persona_messages:
                participant_analysis[persona.name] = {
                    "has_spoken": False,
                    "conclusion_quality": 0,
                    "issues": ["최근 라운드에서 발언하지 않음"]
                }
                continue
            
            latest_message = persona_messages[-1]
            validation = validate_final_statement(latest_message['content'], persona.name)
            
            # 발언 품질 점수 계산
            quality_score = sum([
                validation['has_personal_summary'],
                validation['has_overall_conclusion'], 
                validation['has_action_plan'],
                validation['has_participant_connection'],
                validation['has_gratitude']
            ])
            
            # 문제점 식별
            issues = []
            if not validation['has_personal_summary']:
                issues.append("개인 발언 요약 부족")
            if not validation['has_overall_conclusion']:
                issues.append("전체 결론 정리 부족")
            if not validation['has_action_plan']:
                issues.append("구체적 실행 방안 부족")
            if not validation['has_participant_connection']:
                issues.append("다른 참가자와의 연결점 부족")
            if not validation['has_gratitude']:
                issues.append("감사 인사 누락")
            
            # 토론 계속 시도 감지
            discussion_continuation_patterns = [
                '아직 해결되지 않은', '추가로 논의', '하지만', '새로운 제안',
                '다음 라운드에서는', '논의하기를 기대', '다음 단계로는',
                '어떤 의견이 있으신가요', '세부 계획을', '조정할 수 있습니다'
            ]
            
            is_trying_to_continue = any(pattern in latest_message['content'] 
                                     for pattern in discussion_continuation_patterns)
            
            if is_trying_to_continue:
                issues.append("토론 계속 시도 - 마무리 의도 부족")
                quality_score -= 2  # 패널티
            
            participant_analysis[persona.name] = {
                "has_spoken": True,
                "conclusion_quality": quality_score,
                "message_length": len(latest_message['content']),
                "is_trying_to_continue": is_trying_to_continue,
                "issues": issues,
                "latest_content": latest_message['content'][:100] + "..." if len(latest_message['content']) > 100 else latest_message['content']
            }
        
        # 2. 전체 회의 마무리 적합성 판단
        total_participants = len(non_moderator_personas)
        spoken_participants = sum(1 for p in participant_analysis.values() if p["has_spoken"])
        high_quality_conclusions = sum(1 for p in participant_analysis.values() if p["conclusion_quality"] >= 4)
        continuation_attempts = sum(1 for p in participant_analysis.values() if p.get("is_trying_to_continue", False))
        
        # 3. 마무리 가능 여부 결정
        can_conclude = (
            spoken_participants == total_participants and  # 모든 참가자 발언
            high_quality_conclusions >= (total_participants * 0.8) and  # 80% 이상 고품질 마무리
            continuation_attempts == 0  # 토론 계속 시도 없음
        )
        
        # 4. 상세한 분석 결과 반환
        analysis_result = {
            "can_conclude": can_conclude,
            "total_participants": total_participants,
            "spoken_participants": spoken_participants,
            "high_quality_conclusions": high_quality_conclusions,
            "continuation_attempts": continuation_attempts,
            "participant_details": participant_analysis,
            "overall_quality_ratio": high_quality_conclusions / total_participants if total_participants > 0 else 0
        }
        
        # 5. 마무리 불가 사유 생성
        if not can_conclude:
            reasons = []
            if spoken_participants < total_participants:
                missing_count = total_participants - spoken_participants
                reasons.append(f"{missing_count}명이 아직 발언하지 않음")
            
            if high_quality_conclusions < (total_participants * 0.8):
                poor_quality_count = total_participants - high_quality_conclusions
                reasons.append(f"{poor_quality_count}명의 마무리 발언이 불완전")
            
            if continuation_attempts > 0:
                reasons.append(f"{continuation_attempts}명이 토론 계속을 시도")
            
            analysis_result["reasons_for_continuation"] = reasons
        
        return analysis_result
    
    def generate_informed_closure_message(self, analysis_result: Dict[str, Any], model_name: str = "gpt-4o-mini") -> str:
        """🎯 참가자 발언 분석 결과를 바탕으로 사회자의 타당한 마무리 메시지 생성"""
        try:
            # 모델에 따른 클라이언트 설정
            if model_name.startswith('claude'):
                client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            else:
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # 참가자별 발언 상태 요약
            participant_summary = ""
            for name, details in analysis_result["participant_details"].items():
                if details["has_spoken"]:
                    status = f"✅ {name}: 마무리 품질 {details['conclusion_quality']}/5점"
                    if details["issues"]:
                        status += f" (문제: {', '.join(details['issues'])})"
                    if details.get("is_trying_to_continue"):
                        status += " 🚨 토론 계속 시도"
                else:
                    status = f"❌ {name}: 발언 없음"
                participant_summary += f"- {status}\n"
            
            # 시스템 프롬프트
            system_prompt = f"""당신은 회의 사회자입니다. 참가자들의 발언 내용을 면밀히 분석한 결과를 바탕으로 회의 마무리 여부를 결정해야 합니다.

=== 📊 참가자 발언 분석 결과 ===
전체 참가자: {analysis_result['total_participants']}명
발언 완료: {analysis_result['spoken_participants']}명  
고품질 마무리: {analysis_result['high_quality_conclusions']}명
토론 계속 시도: {analysis_result['continuation_attempts']}명
전체 품질 비율: {analysis_result['overall_quality_ratio']:.1%}

=== 👥 참가자별 상세 분석 ===
{participant_summary}

=== 🎯 마무리 가능 여부 ===
{"✅ 마무리 가능" if analysis_result['can_conclude'] else "❌ 마무리 불가"}

{"" if analysis_result['can_conclude'] else f"불가 사유: {', '.join(analysis_result.get('reasons_for_continuation', []))}"} 

=== 📝 사회자 역할 ===
위 분석 결과를 바탕으로 다음 중 하나의 메시지를 작성하세요:

1) **마무리 가능한 경우**: 
   - 각 참가자의 주요 발언 내용을 구체적으로 언급
   - 회의에서 도달한 핵심 결론들을 정리
   - 합의된 실행 방안이나 다음 단계를 명시
   - 모든 참가자의 기여에 대한 구체적인 감사 표현

2) **마무리 불가능한 경우**:
   - 어떤 참가자의 어떤 부분이 부족한지 구체적으로 지적
   - 추가로 필요한 발언 내용을 명확히 안내
   - 연장 라운드의 목적과 기대사항을 상세히 설명

⚠️ **중요**: 단순히 "라운드가 끝났으니 마무리"가 아닌, 실제 발언 내용 분석에 기반한 타당한 근거를 제시하세요."""

            user_prompt = f"""회의 주제: {self.meeting_topic}

현재 상황에 맞는 사회자 메시지를 작성해주세요. 
반드시 위의 분석 결과를 구체적으로 언급하며, 각 참가자의 실제 발언 내용을 바탕으로 한 타당한 판단을 보여주세요."""

            # API 호출
            if model_name.startswith('claude'):
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text.strip()
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            # 오류 시 기본 메시지
            if analysis_result['can_conclude']:
                return f"""참가자 분석 결과, 모든 분들이 충분한 마무리 발언을 해주셨습니다.

📊 분석 결과:
- 전체 {analysis_result['total_participants']}명 중 {analysis_result['high_quality_conclusions']}명이 완전한 마무리 발언 완료
- 토론 계속 시도: {analysis_result['continuation_attempts']}건

회의를 마무리하겠습니다. 모든 분들의 적극적인 참여에 감사드립니다."""
            else:
                return f"""참가자 발언 분석 결과, 아직 완전한 마무리가 이루어지지 않았습니다.

📊 분석 결과:
- 발언 미완료: {analysis_result['total_participants'] - analysis_result['spoken_participants']}명
- 마무리 불완전: {analysis_result['total_participants'] - analysis_result['high_quality_conclusions']}명  
- 토론 계속 시도: {analysis_result['continuation_attempts']}건

추가 라운드를 진행하겠습니다."""
    
    def _is_final_round_completed(self) -> bool:
        """마지막 라운드에서 모든 참가자가 발언을 완료했는지 확인"""
        non_moderator_personas = self.get_non_moderator_personas()
        if not non_moderator_personas:
            return True
        
        # 현재 라운드에서 발언한 참가자 수 계산
        current_round = self.get_current_round_accurately()
        
        # 현재 라운드의 시작 메시지 인덱스 계산
        current_round_start = (current_round - 1) * len(non_moderator_personas)
        
        # 현재 라운드에서 발언한 참가자 수
        current_round_speakers = set()
        current_round_messages = []
        msg_count = 0
        
        for msg in self.messages:
            if not msg.is_moderator and not msg.is_human_input:
                if msg_count >= current_round_start:
                    current_round_speakers.add(msg.persona_id)
                    current_round_messages.append(msg)
                msg_count += 1
        
        # 모든 참가자가 현재 라운드에서 발언했는지 확인
        all_persona_ids = {persona.id for persona in non_moderator_personas}
        all_speakers_present = len(current_round_speakers) >= len(all_persona_ids)
        
        # 🎯 연장 최종 라운드인 경우 추가 검증
        if (current_round == self.max_rounds and 
            hasattr(self, 'extension_granted') and self.extension_granted):
            
            # 각 참가자가 히스토리 요약과 감사 인사를 했는지 확인
            if all_speakers_present:
                return self._verify_final_round_completion(current_round_messages)
        
        return all_speakers_present
    
    def _verify_final_round_completion(self, final_round_messages: List[Message]) -> bool:
        """마지막 라운드에서 각 참가자가 히스토리 요약과 감사 인사를 했는지 검증"""
        if not final_round_messages:
            return False
        
        # 필수 요소 키워드 정의
        history_keywords = ['이번 회의에서', '제가', '강조한', '핵심', '발언', '의견']
        summary_keywords = ['전체', '논의', '종합', '결론', '최종']
        action_keywords = ['실행', '방안', '다음', '단계', '액션', '계획', '추진']
        agreement_keywords = ['참가자', '동의', '합의', '함께', '공감']
        gratitude_keywords = ['감사', '고생', '수고', '참여', '협력', '논의할 수 있어']
        
        completed_participants = 0
        total_participants = len(self.get_non_moderator_personas())
        
        for msg in final_round_messages:
            content_lower = msg.content.lower()
            
            # 각 필수 요소가 포함되었는지 확인
            has_history = any(keyword in content_lower for keyword in history_keywords)
            has_summary = any(keyword in content_lower for keyword in summary_keywords)
            has_action = any(keyword in content_lower for keyword in action_keywords)
            has_agreement = any(keyword in content_lower for keyword in agreement_keywords)
            has_gratitude = any(keyword in content_lower for keyword in gratitude_keywords)
            
            # 5가지 요소 중 최소 4가지 이상 포함되어야 완료로 인정
            completion_score = sum([has_history, has_summary, has_action, has_agreement, has_gratitude])
            
            # 메시지 길이도 고려 (마무리 발언은 보통 길다)
            is_substantial = len(msg.content) >= 100  # 최소 100자 이상
            
            if completion_score >= 4 and is_substantial:
                completed_participants += 1
        
        # 전체 참가자의 80% 이상이 완전한 마무리를 했으면 완료로 인정
        completion_ratio = completed_participants / total_participants
        return completion_ratio >= 0.8
    
    def get_time_until_next_speak(self) -> float:
        """다음 발언까지 남은 시간 (초) 계산"""
        if not self.last_message_time:
            return 0.0
        elapsed = (datetime.now() - self.last_message_time).total_seconds()
        remaining = max(0.0, self.speaking_speed - elapsed)
        return remaining
        
    def generate_round_summary(self, round_number: int) -> str:
        """특정 라운드의 요약 생성"""
        if round_number in self.round_summaries:
            return self.round_summaries[round_number]
        
        # 해당 라운드의 메시지들 추출
        round_messages = []
        non_moderator_count = len(self.get_non_moderator_personas())
        
        if non_moderator_count == 0:
            return ""
        
        # 라운드별 메시지 범위 계산 (근사치)
        start_index = (round_number - 1) * non_moderator_count
        end_index = round_number * non_moderator_count
        
        for i, msg in enumerate(self.messages):
            if not msg.is_moderator and not msg.is_human_input:
                msg_round = (i // non_moderator_count) + 1
                if msg_round == round_number:
                    round_messages.append(msg)
        
        if not round_messages:
            return ""
        
        # 요약 생성
        summary_parts = []
        for msg in round_messages:
            persona = next((p for p in self.personas if p.id == msg.persona_id), None)
            if persona:
                summary_parts.append(f"{persona.role} {persona.name}: {msg.content[:80]}{'...' if len(msg.content) > 80 else ''}")
        
        summary = f"라운드 {round_number} 요약:\n" + "\n".join(summary_parts)
        self.round_summaries[round_number] = summary
        return summary
    
    def extract_key_insights(self) -> List[str]:
        """회의에서 핵심 인사이트 추출"""
        insights = []
        
        # 긴 메시지들에서 인사이트 추출 (100자 이상)
        for msg in self.messages:
            if len(msg.content) > 100 and not msg.is_moderator:
                persona = next((p for p in self.personas if p.id == msg.persona_id), None)
                if persona:
                    insight = f"[{persona.role}] {msg.content[:150]}{'...' if len(msg.content) > 150 else ''}"
                    insights.append(insight)
        
        self.key_insights = insights[-10:]  # 최근 10개만 유지
        return self.key_insights
    
    def analyze_conversation_flow(self) -> Dict[str, Any]:
        """🎯 대화 흐름 분석 - 창의적 대화 체인 시스템"""
        if len(self.messages) < 2:
            return {"status": "insufficient_data"}
        
        recent_messages = self.messages[-5:]  # 최근 5개 메시지
        
        # 1. 논의 초점 추출
        topics = []
        for msg in recent_messages:
            if not msg.is_moderator:
                # 핵심 키워드 추출 (간단한 방식)
                words = msg.content.split()
                important_words = [w for w in words if len(w) > 3 and w not in ['것입니다', '있습니다', '해야', '통해']]
                topics.extend(important_words[:3])  # 메시지당 최대 3개 키워드
        
        # 가장 자주 언급된 토픽을 현재 초점으로 설정
        if topics:
            from collections import Counter
            most_common = Counter(topics).most_common(1)
            self.discussion_focus = most_common[0][0] if most_common else ""
        
        # 2. 질문과 답변 매칭
        questions = []
        for msg in recent_messages:
            if '?' in msg.content or '어떻게' in msg.content or '왜' in msg.content:
                questions.append({
                    'speaker': msg.persona_name,
                    'question': msg.content,
                    'answered': False
                })
        
        # 3. 합의/이견 분석
        agreement_keywords = ['동의', '찬성', '맞습니다', '좋은', '적절', '정확']
        disagreement_keywords = ['하지만', '그러나', '반대', '문제', '우려', '다른']
        
        for msg in recent_messages:
            content_lower = msg.content.lower()
            if any(keyword in content_lower for keyword in agreement_keywords):
                self.agreements.append(f"{msg.persona_name}: {msg.content[:50]}...")
            elif any(keyword in content_lower for keyword in disagreement_keywords):
                self.disagreements.append(f"{msg.persona_name}: {msg.content[:50]}...")
        
        # 최근 3개만 유지
        self.agreements = self.agreements[-3:]
        self.disagreements = self.disagreements[-3:]
        
        return {
            "status": "analyzed",
            "focus": self.discussion_focus,
            "questions": questions,
            "agreements": len(self.agreements),
            "disagreements": len(self.disagreements)
        }
    
    def get_conversation_direction(self) -> str:
        """🎯 다음 대화 방향 제시"""
        analysis = self.analyze_conversation_flow()
        
        if analysis["status"] == "insufficient_data":
            return "회의 주제에 대한 첫 번째 의견을 제시해주세요."
        
        directions = []
        
        # 해결되지 않은 질문이 있으면 우선 처리
        if self.pending_questions:
            directions.append(f"미해결 질문: {self.pending_questions[-1]}")
        
        # 이견이 많으면 합의점 찾기
        if len(self.disagreements) > len(self.agreements):
            directions.append("서로 다른 의견들 사이의 공통점을 찾아보세요.")
        
        # 현재 초점이 있으면 심화 논의
        if self.discussion_focus:
            directions.append(f"'{self.discussion_focus}'에 대해 더 구체적으로 논의해주세요.")
        
        # 기본 방향
        if not directions:
            directions.append("이전 발언자의 의견에 대한 구체적인 반응이나 보완 의견을 제시해주세요.")
        
        return " | ".join(directions)

    def analyze_uploaded_files(self) -> Dict[str, Any]:
        """업로드된 파일 내용을 분석하여 키워드와 요약 추출"""
        if not self.uploaded_files_content or self.file_analysis:
            return self.file_analysis
        
        try:
            # 간단한 키워드 추출 (공백과 줄바꿈으로 단어 분리)
            words = self.uploaded_files_content.replace('\n', ' ').split()
            # 길이가 3자 이상인 단어들만 추출 (한국어/영어 혼합 고려)
            meaningful_words = [word.strip('.,!?:;"()[]{}') for word in words 
                              if len(word.strip('.,!?:;"()[]{}')) >= 3]
            
            # 빈도 계산 (간단한 방식)
            word_count = {}
            for word in meaningful_words:
                word_lower = word.lower()
                word_count[word_lower] = word_count.get(word_lower, 0) + 1
            
            # 상위 키워드 추출 (빈도 기준)
            sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
            self.file_keywords = [word for word, count in sorted_words[:20] if count > 1]
            
            # 파일 요약 (첫 부분과 마지막 부분)
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
        
        # 파일명으로 구분된 섹션들 추출
        file_parts = self.uploaded_files_content.split('---')
        for i, part in enumerate(file_parts):
            if part.strip():
                lines = part.strip().split('\n')
                if len(lines) > 1:
                    # 첫 줄이 파일명인 경우
                    title = lines[0].strip() if len(lines[0].strip()) < 100 else f"섹션 {i+1}"
                    content = '\n'.join(lines[1:]).strip()
                    if content:
                        sections.append({
                            'title': title,
                            'content': content[:800] + "..." if len(content) > 800 else content
                        })
        
        return sections
    
    def get_relevant_file_content(self, query_keywords: List[str]) -> str:
        """쿼리 키워드와 관련된 파일 내용 추출 (간단한 RAG)"""
        if not self.uploaded_files_content:
            return ""
        
        analysis = self.analyze_uploaded_files()
        
        # 키워드 매칭을 통한 관련 섹션 추출
        relevant_sections = []
        
        for section in analysis.get('sections', []):
            content_lower = section['content'].lower()
            # 쿼리 키워드 중 하나라도 포함된 섹션 추출
            for keyword in query_keywords:
                if keyword.lower() in content_lower:
                    relevant_sections.append(section)
                    break
        
        if relevant_sections:
            result = "=== 관련 참고 자료 ===\n"
            for section in relevant_sections[:3]:  # 최대 3개 섹션만
                result += f"\n📄 {section['title']}\n{section['content']}\n"
            return result
        else:
            # 관련 섹션이 없으면 전체 요약 반환
            return f"=== 참고 자료 요약 ===\n{analysis.get('summary', '')}"

def initialize_session_state():
    """세션 상태 초기화"""
    if 'virtual_meeting' not in st.session_state:
        st.session_state.virtual_meeting = VirtualMeeting()
    
    # 🎯 기존 meeting 객체를 대화 체인 시스템으로 업그레이드
    meeting = st.session_state.virtual_meeting
    
    # 새로운 대화 체인 시스템 속성이 없으면 추가
    if not hasattr(meeting, 'conversation_chain'):
        meeting.conversation_chain = []
        meeting.discussion_focus = ""
        meeting.pending_questions = []
        meeting.agreements = []
        meeting.disagreements = []
        meeting.manual_round_control = True
        meeting.turn_counter = len([msg for msg in meeting.messages if not msg.is_moderator and not msg.is_human_input])
    
    # 🔧 새로운 회의 제어 속성이 없으면 추가
    if not hasattr(meeting, 'original_max_rounds'):
        meeting.original_max_rounds = meeting.max_rounds
    if not hasattr(meeting, 'extension_granted'):
        meeting.extension_granted = False
    if not hasattr(meeting, 'consecutive_repetitions'):
        meeting.consecutive_repetitions = 0
    if not hasattr(meeting, 'last_meaningful_content'):
        meeting.last_meaningful_content = []
    
    # 기존 meeting 객체가 새로운 메소드를 가지고 있지 않으면 새로 생성
    if not hasattr(meeting, '_is_conclusion_reached'):
        # 기존 데이터 백업
        old_meeting = meeting
        new_meeting = VirtualMeeting()
        
        # 중요한 데이터 복사
        if hasattr(old_meeting, 'personas'):
            new_meeting.personas = old_meeting.personas
        if hasattr(old_meeting, 'messages'):
            new_meeting.messages = old_meeting.messages
        if hasattr(old_meeting, 'meeting_topic'):
            new_meeting.meeting_topic = old_meeting.meeting_topic
        if hasattr(old_meeting, 'conversation_round'):
            new_meeting.conversation_round = old_meeting.conversation_round
        if hasattr(old_meeting, 'max_rounds'):
            new_meeting.max_rounds = old_meeting.max_rounds
        if hasattr(old_meeting, 'is_active'):
            new_meeting.is_active = old_meeting.is_active
        if hasattr(old_meeting, 'start_time'):
            new_meeting.start_time = old_meeting.start_time
        if hasattr(old_meeting, 'uploaded_files_content'):
            new_meeting.uploaded_files_content = old_meeting.uploaded_files_content
        if hasattr(old_meeting, 'auto_mode'):
            new_meeting.auto_mode = old_meeting.auto_mode
        if hasattr(old_meeting, 'speaking_speed'):
            new_meeting.speaking_speed = old_meeting.speaking_speed
        if hasattr(old_meeting, 'typing_speed'):
            new_meeting.typing_speed = old_meeting.typing_speed
        
        # 🎯 대화 체인 시스템 속성도 복사
        if hasattr(old_meeting, 'conversation_chain'):
            new_meeting.conversation_chain = old_meeting.conversation_chain
            new_meeting.discussion_focus = old_meeting.discussion_focus
            new_meeting.pending_questions = old_meeting.pending_questions
            new_meeting.agreements = old_meeting.agreements
            new_meeting.disagreements = old_meeting.disagreements
            new_meeting.manual_round_control = old_meeting.manual_round_control
            new_meeting.turn_counter = old_meeting.turn_counter
        
        # 🔧 새로운 회의 제어 속성 복사
        if hasattr(old_meeting, 'original_max_rounds'):
            new_meeting.original_max_rounds = old_meeting.original_max_rounds
        else:
            new_meeting.original_max_rounds = new_meeting.max_rounds
            
        if hasattr(old_meeting, 'extension_granted'):
            new_meeting.extension_granted = old_meeting.extension_granted
        if hasattr(old_meeting, 'consecutive_repetitions'):
            new_meeting.consecutive_repetitions = old_meeting.consecutive_repetitions
        if hasattr(old_meeting, 'last_meaningful_content'):
            new_meeting.last_meaningful_content = old_meeting.last_meaningful_content
        
        st.session_state.virtual_meeting = new_meeting
    
    # AI 모델 선택 초기화
    if 'selected_ai_model' not in st.session_state:
        st.session_state.selected_ai_model = 'gpt-4o-mini'
        
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

def connect_to_db():
    """데이터베이스 연결"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

def save_meeting_record(meeting: 'VirtualMeeting', meeting_log: str, summary: str) -> bool:
    """회의록을 데이터베이스에 저장"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 참가자 목록 생성
        participants = ", ".join([p.name + "(" + p.role + ")" for p in meeting.personas])
        
        # 사용된 AI 모델 정보 추가
        ai_model_used = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
        
        # 회의록 저장 (action_items 필드에 AI 모델 정보 임시 저장)
        cursor.execute("""
            INSERT INTO meeting_records 
            (title, date, participants, full_text, summary, action_items, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            meeting.meeting_topic,
            meeting.start_time if meeting.start_time else datetime.now(),
            participants,
            meeting_log,
            summary,
            f"AI 모델: {ai_model_used}",  # action_items 필드에 AI 모델 정보 저장
            datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"회의록 저장 오류: {err}")
        return False

def get_saved_meeting_records() -> List[Dict]:
    """저장된 회의록 목록 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return []
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT meeting_id, title, date, participants, created_at
            FROM meeting_records
            ORDER BY date DESC, created_at DESC
        """)
        
        records = []
        for row in cursor.fetchall():
            records.append({
                'meeting_id': row[0],
                'title': row[1],
                'date': row[2],
                'participants': row[3],
                'created_at': row[4]
            })
        
        cursor.close()
        conn.close()
        return records
        
    except mysql.connector.Error as err:
        st.error(f"회의록 조회 오류: {err}")
        return []

def get_meeting_record_detail(meeting_id: int) -> Dict:
    """특정 회의록 상세 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT meeting_id, title, date, participants, full_text, summary, action_items, created_at
            FROM meeting_records
            WHERE meeting_id = %s
        """, (meeting_id,))
        
        row = cursor.fetchone()
        if row:
            record = {
                'meeting_id': row[0],
                'title': row[1],
                'date': row[2],
                'participants': row[3],
                'full_text': row[4],
                'summary': row[5],
                'action_items': row[6],
                'created_at': row[7]
            }
        else:
            record = {}
        
        cursor.close()
        conn.close()
        return record
        
    except mysql.connector.Error as err:
        st.error(f"회의록 상세 조회 오류: {err}")
        return {}

def delete_meeting_record(meeting_id: int) -> bool:
    """회의록 삭제"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM meeting_records WHERE meeting_id = %s", (meeting_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"회의록 삭제 오류: {err}")
        return False

def generate_meeting_summary(meeting_log: str, model_name: str = "gpt-4o-mini") -> str:
    """AI를 사용하여 회의록 요약 생성"""
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
        
        system_prompt = """당신은 회의록 요약 전문가입니다. 주어진 회의 내용을 바탕으로 다음 형식으로 요약해주세요:

## 📋 회의 요약

### 🎯 주요 논의 사항
- 핵심 논의 포인트들을 3-5개 정도로 정리

### 💡 주요 의견 및 제안
- 참가자별 주요 의견과 제안사항

### ✅ 결론 및 합의사항
- 회의를 통해 도출된 결론이나 합의된 내용

### 📝 향후 액션 아이템
- 후속 조치가 필요한 사항들

### 🔍 추가 검토 필요 사항
- 추후 논의가 필요한 이슈들

간결하고 명확하게 작성하되, 중요한 내용은 빠뜨리지 말고 포함해주세요."""

        user_message = f"다음 회의 내용을 요약해주세요:\n\n{meeting_log}"
        
        if model_name.startswith('claude'):
            # Claude API 호출
            response = client.messages.create(
                model=model_name,
                max_tokens=1000,
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
                max_tokens=1000,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"요약 생성 중 오류가 발생했습니다: {str(e)}"

def validate_final_statement(statement: str, persona_name: str) -> Dict[str, bool]:
    """마무리 발언의 완성도를 검증 - 강화된 검증 (토론 계속 시도 감지 포함)"""
    validation_result = {
        'has_personal_summary': False,
        'has_overall_conclusion': False, 
        'has_action_plan': False,
        'has_participant_connection': False,
        'has_gratitude': False,
        'is_continuing_discussion': False,  # 토론 계속 시도 감지
        'is_complete': False
    }
    
    statement_lower = statement.lower()
    
    # 0. 토론 계속 시도 감지 (마무리 발언이 아닌 경우)
    discussion_continuation_patterns = [
        '아직 해결되지 않은', '추가로 논의', '더 논의', '계속 논의',
        '다음 단계에서는', '향후 논의', '더 검토', '추가 검토',
        '하지만', '그러나', '반면에', '다른 관점에서',
        '새로운 제안', '추가 제안', '또 다른', '다른 방법',
        '문제점', '우려', '리스크', '쟁점', '이슈',
        '다음 발언자', '추가로', '더', '또한', '게다가',
        '논의해보', '검토해보', '생각해보', '고려해보',
        '필요합니다', '해야 합니다', '것이 좋을', '것 같습니다',
        '세부 계획을', '세부 계획', '세부적인', '구체화하는',
        '조정할 수 있습니다', '마련하는 것', '나아가야 할',
        '기대합니다', '기대하', '질문', '의견', '생각'
    ]
    
    # 강화된 토론 계속 시도 감지
    continuation_detected = any(pattern in statement_lower for pattern in discussion_continuation_patterns)
    
    # 특별히 강한 토론 계속 신호들 (이것들이 있으면 무조건 토론 계속으로 판단)
    strong_continuation_signals = [
        '다음 발언자는', '추가로 논의해보', '더 논의해보', '계속 논의해보',
        '검토해보는 것이', '생각해보는 것이', '고려해보는 것이',
        '것이 좋을 것 같습니다', '필요할 것 같습니다', '해야 할 것 같습니다',
        '다음 라운드에서는', '다음 라운드', '논의하기를 기대', '기대합니다',
        '다음 단계로는', '나아가야 할 것', '어떤 의견이 있으신가요', 
        '의견이 있으신가요', '어떻게 생각하시나요', '생각하시나요'
    ]
    
    strong_continuation_detected = any(signal in statement_lower for signal in strong_continuation_signals)
    
    validation_result['is_continuing_discussion'] = continuation_detected or strong_continuation_detected
    
    # 1. 개인 발언 히스토리 요약 체크 (더 구체적으로)
    personal_patterns = [
        '제가 이번 회의에서', '제가 강조한', '제가 제시한', '제가 말씀드린',
        '저의 핵심', '제 의견', '제가 생각한', '저는 이번에', '제 관점에서'
    ]
    validation_result['has_personal_summary'] = any(pattern in statement for pattern in personal_patterns)
    
    # 2. 전체 결론 도출 체크 (더 명확한 결론 표현)
    conclusion_patterns = [
        '전체 논의를 종합', '결론적으로', '종합해보면', '회의 결과',
        '전반적으로', '최종적으로', '논의를 통해', '결론은', '정리하면'
    ]
    validation_result['has_overall_conclusion'] = any(pattern in statement for pattern in conclusion_patterns)
    
    # 3. 실행 방안 체크 (구체적인 액션)
    action_patterns = [
        '실행 방안', '다음 단계', '액션 플랜', '구체적', '실행하',
        '진행하', '추진하', '계획', '후속', '조치'
    ]
    validation_result['has_action_plan'] = any(pattern in statement for pattern in action_patterns)
    
    # 4. 다른 참가자와의 연결점 체크 (더 구체적인 참조)
    connection_patterns = [
        '님의', '분의', '동의하', '공감하', '함께', '합의',
        '참가자', '의견에', '말씀에', '제안에', '생각에'
    ]
    validation_result['has_participant_connection'] = any(pattern in statement for pattern in connection_patterns)
    
    # 5. 감사 인사 체크 (더 명확한 감사 표현)
    gratitude_patterns = [
        '감사드립니다', '감사합니다', '고생 많으셨습니다', '수고하셨습니다',
        '함께 해주셔서', '참여해 주신', '논의해 주신', '고맙습니다'
    ]
    validation_result['has_gratitude'] = any(pattern in statement for pattern in gratitude_patterns)
    
    # 전체 완성도 체크 (5개 중 4개 이상 충족해야 완전한 마무리)
    completed_items = sum([
        validation_result['has_personal_summary'],
        validation_result['has_overall_conclusion'],
        validation_result['has_action_plan'],
        validation_result['has_participant_connection'],
        validation_result['has_gratitude']
    ])
    
    # 최소 길이 체크 (너무 짧으면 불완전)
    is_adequate_length = len(statement) >= 100
    
    # 토론 계속 시도가 감지되면 불완전한 마무리로 처리
    if validation_result['is_continuing_discussion']:
        validation_result['is_complete'] = False
    else:
        validation_result['is_complete'] = completed_items >= 4 and is_adequate_length
    
    return validation_result

def improve_final_statement(original_statement: str, persona: Persona, conversation_history: str, meeting_topic: str, model_name: str = "gpt-4o-mini") -> str:
    """불완전한 마무리 발언을 개선"""
    try:
        validation = validate_final_statement(original_statement, persona.name)
        
        if validation['is_complete']:
            return original_statement
        
        # 부족한 요소들 파악
        missing_elements = []
        if not validation['has_personal_summary']:
            missing_elements.append("개인 발언 히스토리 요약")
        if not validation['has_overall_conclusion']:
            missing_elements.append("회의 전체 결론")
        if not validation['has_action_plan']:
            missing_elements.append("구체적 실행 방안")
        if not validation['has_participant_connection']:
            missing_elements.append("다른 참가자와의 연결점")
        if not validation['has_gratitude']:
            missing_elements.append("감사 인사")
        
        # OpenAI API를 사용하여 개선된 발언 생성
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            return original_statement
        
        client = OpenAI(api_key=openai_key)
        
        system_prompt = f"""당신은 {persona.name}({persona.role})입니다.
        
        🎯 **마무리 발언 개선 임무**:
        
        원본 발언: "{original_statement}"
        
        부족한 요소들: {', '.join(missing_elements)}
        
        **개선 요구사항**:
        1. 원본 발언의 핵심 내용은 유지하면서
        2. 부족한 요소들을 자연스럽게 추가하여
        3. 완전한 마무리 발언으로 재구성하세요
        
        **반드시 포함해야 할 5가지 요소**:
        1️⃣ 자신의 발언 히스토리 요약 ("제가 이번 회의에서...")
        2️⃣ 회의 전체 결론 ("전체 논의를 종합해보면...")
        3️⃣ 구체적 실행 방안 ("구체적인 실행 방안으로는...")
        4️⃣ 다른 참가자와의 연결점 ("특히 ○○님의 의견에...")
        5️⃣ 감사 인사 ("함께 논의해 주신 모든 분들께 감사...")
        
        자연스럽고 완결성 있는 마무리 발언으로 개선해주세요."""
        
        user_message = f"회의 주제: {meeting_topic}\n\n회의 맥락:\n{conversation_history[-1000:]}\n\n위 내용을 바탕으로 완전한 마무리 발언을 생성해주세요."
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        improved_statement = response.choices[0].message.content.strip()
        
        # 개선된 발언도 검증
        improved_validation = validate_final_statement(improved_statement, persona.name)
        
        if improved_validation['is_complete']:
            return improved_statement
        else:
            # 여전히 불완전하면 원본 반환
            return original_statement
            
    except Exception as e:
        return original_statement

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

def generate_ai_response(persona: Persona, conversation_history: str, meeting_topic: str, file_content: str, round_number: int, enhanced_context: str = "", model_name: str = "gpt-4o-mini", total_rounds: int = 10, is_final_round: bool = False, final_round_context: str = "", conversation_direction: str = "", meeting: 'VirtualMeeting' = None) -> str:
    """AI 응답 생성 - 라운드별 맥락 유지 강화"""
    try:
        # 모델에 따른 클라이언트 설정
        if model_name.startswith('claude'):
            # Anthropic Claude 모델
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key or anthropic_key.strip() == '' or anthropic_key == 'NA':
                raise ValueError("Anthropic API 키가 올바르지 않습니다. .env 파일에서 ANTHROPIC_API_KEY를 확인해주세요.")
            
            client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            # OpenAI 모델
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                raise ValueError("OpenAI API 키가 올바르지 않습니다. .env 파일에서 OPENAI_API_KEY를 확인해주세요.")
            
            client = OpenAI(api_key=openai_key)
        
        # 라운드에 따른 맥락 조정 (연장 라운드 특별 처리)
        round_context = ""
        round_percentage = round_number / total_rounds
        
        # 🎯 연장 라운드 특별 처리
        original_max = getattr(meeting, 'original_max_rounds', total_rounds) if meeting else total_rounds
        is_extension_round = round_number > original_max
        is_final_extension_round = round_number == total_rounds and is_extension_round
        
        if is_final_extension_round:
            # 연장된 마지막 라운드 - 반드시 마무리
            round_context = f"""🏁 **연장된 최종 마무리 라운드** ({round_number}/{total_rounds}라운드)
            
            🚨 **절대 필수 - 완전한 마무리 발언 의무**:
            
            ⚠️ **중요**: 다른 참가자들이 이미 마무리 발언을 했더라도, 당신은 반드시 새로운 토론을 시작하지 말고 완전한 마무리 발언만 하세요.
            
            📝 **마무리 발언 5단계 (순서대로 반드시 포함):**
            
            1️⃣ **자신의 발언 히스토리 요약** 
               - "제가 이번 회의에서 제시한 핵심 의견은..."
               - 지금까지 자신이 말한 주요 내용 2-3개를 구체적으로 언급
            
            2️⃣ **회의 전체 결론 정리**
               - "전체 논의를 종합해보면..." 또는 "회의 결과..."
               - 회의에서 도달한 최종 결론이나 합의사항 명시
            
            3️⃣ **구체적 실행 방안 제시**
               - "구체적인 실행 방안으로는..." 또는 "다음 단계로..."
               - 실제 실행 가능한 액션 플랜이나 후속 조치 제안
            
            4️⃣ **다른 참가자와의 합의점**
               - "특히 [참가자명]님의 [구체적 의견]에 동의하며..."
               - 다른 참가자들과의 공통된 의견이나 협력점 언급
            
            5️⃣ **정중한 감사 인사 (필수)**
               - "오늘 함께 논의해 주신 모든 분들께 감사드립니다" 
               - "모든 분들 고생 많으셨습니다" 등의 진심 어린 마무리 인사
            
            🚫 **절대 금지사항**:
            - 새로운 논점이나 쟁점을 제기하지 마세요
            - "아직 해결되지 않은", "추가로 논의", "다음 단계에서는" 같은 표현으로 토론을 이어가지 마세요
            - 다른 참가자의 의견에 반박하거나 새로운 제안을 하지 마세요
            
            🎯 **이번이 당신의 마지막 발언입니다. 오직 마무리만 하세요.**
            
            {final_round_context}"""
            
        elif is_extension_round:
            # 연장 라운드 첫 번째 - 핵심 정리 (마무리 준비)
            round_context = f"""⏰ 연장 라운드입니다 ({round_number}/{total_rounds}라운드).
            
            📋 **핵심 논점 정리 단계 (마무리 준비)**:
            - 지금까지의 회의 내용 중 가장 중요한 논점들을 정리하세요
            - 당신의 전문 분야에서 본 핵심 의견을 명확히 제시하세요
            - 회의에서 도달한 주요 합의사항을 언급하세요
            - 다음 라운드에서는 완전한 마무리 발언을 준비하세요
            
            🚫 **주의사항**:
            - 새로운 쟁점이나 논점을 제기하지 마세요
            - 토론을 확장시키려 하지 말고 정리에 집중하세요
            
            ⚠️ 간결하고 핵심적으로 발언해 주세요."""
            
        elif round_number >= total_rounds:
            # 일반 마지막 라운드
            round_context = f"""🏁 마지막 라운드입니다 ({round_number}/{total_rounds}라운드). 
            
            이제 회의 전체를 종합하여 당신의 최종 결론을 제시할 차례입니다:
            - 전체 토론에서 나온 핵심 논점들을 정리하세요
            - 당신의 전문 분야 관점에서 최종 의견을 명확히 제시하세요  
            - 구체적인 실행 방안이나 다음 단계를 제안하세요
            - 다른 참가자들의 의견에 대한 동의/보완점을 언급하세요
            
            {final_round_context}"""
        elif round_number == 1:
            round_context = "이번이 첫 번째 발언입니다. 자신을 한 문장으로 간단히 소개한 후 주제에 대한 의견을 제시하세요."
        elif round_percentage <= 0.2:  # 초기 20%
            round_context = f"회의 초기 단계입니다 ({round_number}/{total_rounds}라운드). 문제 정의와 현황 파악에 집중하여 의견을 제시하세요."
        elif round_percentage <= 0.4:  # 20-40% - 갈등 도입 구간
            # 🎯 갈등 요소 도입 시점 결정
            should_introduce_conflict = False
            if meeting and not meeting.conflict_introduced and round_percentage >= 0.3:
                # 30% 지점에서 갈등 요소 도입 고려
                participant_count = len(meeting.get_non_moderator_personas())
                if participant_count >= 3 and round_number % participant_count == 1:  # 특정 순서의 참가자
                    should_introduce_conflict = True
                    meeting.conflict_introduced = True
            
            conflict_guidance = ""
            if should_introduce_conflict:
                conflict_guidance = f"""
                
                🎯 **중요**: 다음 중 하나의 우려사항을 건설적으로 제기하세요:
                - ROI나 비용 대비 효과에 대한 의문
                - 기술적 실현 가능성에 대한 회의
                - 시장 경쟁력이나 차별성 부족 우려  
                - 리스크나 부작용에 대한 경고
                - 대안적 접근 방식 제안
                
                ⚠️ 무조건 반대하지 말고, 건설적인 우려나 보완책을 제시하세요."""
            
            round_context = f"문제 탐색 단계입니다 ({round_number}/{total_rounds}라운드). 다양한 관점에서 문제를 분석하고 여러 해결책을 제시해보세요.{conflict_guidance}"
        elif round_percentage <= 0.6:  # 40-60% - 의사결정 압박
            # 🎯 의사결정 압박 포인트 확인
            decision_pressure = meeting and round_percentage in meeting.decision_pressure_points
            
            decision_guidance = ""
            if decision_pressure:
                decision_guidance = """
                
                🎯 **의사결정 압박**: 지금까지의 논의를 바탕으로 구체적인 방향성을 제시해야 합니다:
                - 제시된 옵션들 중 선호하는 방안과 그 이유
                - 실행 시 예상되는 구체적인 결과
                - 필요한 자원이나 조건들
                - 타임라인이나 우선순위 제안"""
            
            round_context = f"해결책 검토 단계입니다 ({round_number}/{total_rounds}라운드). 제시된 해결책들을 비교 분석하고 장단점을 논의하세요.{decision_guidance}"
        elif round_percentage <= 0.8:  # 60-80%
            round_context = f"합의 도출 단계입니다 ({round_number}/{total_rounds}라운드). 최적의 해결책을 선택하고 구체적인 실행 방안을 논의하세요."
        else:  # 80-100%
            round_context = f"결론 정리 단계입니다 ({round_number}/{total_rounds}라운드). 전체 논의를 종합하여 최종 결론과 향후 액션 플랜을 제시하세요."
        
        # 🎯 반복 방지 강화 (ChatGPT 지적 사항 반영)
        repetition_warning = ""
        if round_percentage > 0.6:
            recent_keywords = []
            if meeting and len(meeting.messages) >= 6:
                recent_messages = meeting.messages[-6:]
                for msg in recent_messages:
                    if not msg.is_moderator:
                        # ChatGPT가 지적한 반복 키워드들 추출
                        repetitive_terms = ['지속 가능한', 'AI 기반', '브랜드 충성도', '70% 이상', 
                                          '아마존', '넷플릭스', '추천 알고리즘', '예를 들어']
                        for term in repetitive_terms:
                            if term in msg.content:
                                recent_keywords.append(term)
            
            if recent_keywords:
                repetition_warning = f"""
                
                ⚠️ **반복 방지 필수**:
                - 다음 키워드들이 최근 자주 사용되었으니 피하세요: {', '.join(set(recent_keywords))}
                - 새로운 관점이나 구체적인 데이터를 제시하세요
                - 이전과 다른 전문 분야의 시각을 활용하세요
                - 실무적이고 구체적인 실행 방안에 집중하세요"""
            
            if round_percentage > 0.8:
                repetition_warning += """
                - 동일한 결론을 반복하지 말고, 차별화된 최종 의견을 제시하세요
                - '감사합니다', '함께 최상의 결과를' 같은 상투적 표현을 과도하게 사용하지 마세요"""
        
        if is_final_round:
            repetition_warning += """
            
            ⚠️ 마지막 라운드 중요 지침:
            - 이번이 당신의 마지막 발언 기회입니다
            - 회의 전체를 아우르는 종합적인 결론을 제시하세요
            - 당신의 전문성을 바탕으로 한 구체적인 제안을 포함하세요
            - 다른 참가자들과의 합의점을 찾아 언급하세요
            - 향후 실행해야 할 구체적인 액션 아이템을 제안하세요"""

        # 🎯 페르소나별 입장 추적 및 다양성 확보
        if meeting and persona.id not in meeting.persona_stance:
            # 첫 발언에서 입장 결정
            stances = ['supportive', 'cautious', 'analytical', 'creative']
            assigned_stances = list(meeting.persona_stance.values())
            available_stances = [s for s in stances if s not in assigned_stances]
            
            if available_stances:
                meeting.persona_stance[persona.id] = available_stances[0]
            else:
                meeting.persona_stance[persona.id] = 'supportive'
        
        current_stance = meeting.persona_stance.get(persona.id, 'supportive') if meeting else 'supportive'
        
        # 🎯 페르소나별 입장 반영
        stance_guidance = ""
        if current_stance == 'cautious':
            stance_guidance = "\n🎯 당신의 관점: 신중하고 리스크를 고려하는 입장에서 발언하세요."
        elif current_stance == 'analytical':
            stance_guidance = "\n🎯 당신의 관점: 데이터와 논리적 분석에 기반한 객관적 입장을 취하세요."
        elif current_stance == 'creative':
            stance_guidance = "\n🎯 당신의 관점: 창의적이고 혁신적인 아이디어를 제시하는 입장을 취하세요."
        else:  # supportive
            stance_guidance = "\n🎯 당신의 관점: 건설적이고 협력적인 입장에서 발언하세요."

        # 🎯 창의적 대화 체인 시스템 프롬프트
        conversation_guidance = ""
        if conversation_direction:
            conversation_guidance = f"\n🎯 대화 방향 가이드: {conversation_direction}\n"
        
        # 🎯 사회자 특별 처리
        if persona.is_moderator:
            # 연장 라운드 여부 확인
            original_max = getattr(meeting, 'original_max_rounds', total_rounds) if meeting else total_rounds
            is_extension_round = round_number > original_max
            
            moderator_warning = ""
            if is_extension_round:
                moderator_warning = f"""
            
            🚨 **연장 라운드 특별 주의사항**:
            - 현재 연장 라운드({round_number}/{total_rounds})입니다
            - 모든 참가자가 발언을 완료할 때까지 절대 회의를 종료하지 마세요
            - 특히 마지막 연장 라운드에서는 각 참가자가 자신의 기존 발언을 정리하고 감사 인사할 시간을 주세요
            - "회의를 마치겠습니다", "종료합니다", "완료되어" 같은 종료 표현을 절대 사용하지 마세요
            - 시스템이 자동으로 회의 종료를 처리하므로 중복 종료 발언을 하지 마세요
            """
            
            # 사회자가 이미 종료 관련 메시지를 보냈는지 확인 (더 강력한 검증)
            recent_moderator_messages = []
            for msg in meeting.messages[-10:]:  # 최근 10개 메시지 확인
                if msg.is_moderator:
                    recent_moderator_messages.append(msg.content.lower())
            
            # 종료 관련 키워드들을 더 포괄적으로 검사
            closure_keywords = [
                '마치겠습니다', '종료', '완료', '마무리', '끝', '감사드립니다',
                '회의를', '라운드가', '진심으로', '적극적인 참여'
            ]
            
            has_recent_closure = any(
                any(keyword in msg for keyword in closure_keywords)
                for msg in recent_moderator_messages
            )
            
            if has_recent_closure:
                # 이미 종료 메시지를 보낸 경우, 발언하지 않거나 매우 간단하게만
                system_prompt = f"""당신은 회의 사회자 {persona.name}입니다.
                
                🚨 **중요**: 이미 회의 종료/마무리 관련 발언을 하셨습니다.
                
                ⚠️ **절대 금지사항**: 
                - 회의 종료, 마무리, 완료, 감사 등의 표현을 다시 사용하지 마세요
                - 중복된 마무리 인사를 하지 마세요
                - 라운드 완료나 회의 진행 상황을 언급하지 마세요
                
                📋 **허용되는 발언만**:
                - 아무 말도 하지 않거나
                - "네, 감사합니다" 정도의 매우 간단한 응답만
                - 30자 이내로 극도로 간결하게
                
                🔇 **권장**: 가능하면 발언하지 마세요.
                """
            else:
                system_prompt = f"""당신은 회의 사회자 {persona.name}입니다.
                
                ⚠️ **중요한 사회자 규칙**:
                1. **절대로 회의를 임의로 종료하지 마세요**
                2. 라운드 {round_number}/{total_rounds}이므로 아직 회의가 진행 중입니다
                3. 설정된 {total_rounds}라운드가 완전히 끝나기 전까지는 종료 발언을 하지 마세요
                4. "회의를 마치겠습니다", "종료합니다" 같은 표현을 사용하지 마세요
                5. 시스템이 자동으로 회의 종료를 처리하므로 사회자는 진행만 담당하세요
                {moderator_warning}
                
                📋 **사회자 역할**:
                - 참가자들의 의견을 정리하고 요약하세요
                - 다음 논의 방향을 제시하세요
                - 구체적인 질문을 통해 토론을 심화시키세요
                - 다른 관점에서 문제를 바라보도록 유도하세요
                - 다음 발언자에게 자연스럽게 발언권을 넘기세요
                
                {round_context}
                
                현재 라운드 {round_number}/{total_rounds}에서 회의 진행을 도와주세요.
                150-200자 내외로 간결하게 발언하세요.
                """
        else:
            # 일반 참가자 - ChatGPT 분석 기반 개선
            system_prompt = f"""당신은 {persona.name}({persona.role})입니다.

            📋 **당신의 전문성**: {persona.expertise}
            {stance_guidance}
            
            ⚠️ **중요한 발언 지침**:
            1. 당신의 전문 분야 관점에서만 발언하세요
            2. 구체적이고 실무적인 의견을 제시하세요
            3. 다른 참가자의 의견을 듣고 반응하세요
            4. 150-250자 내외로 간결하게 발언하세요
            5. 단순한 동의보다는 새로운 관점을 제시하세요
            
            {round_context}
            {repetition_warning}
            {conversation_guidance}
            
            현재 라운드 {round_number}/{total_rounds}에서 당신의 전문적 의견을 제시하세요.
            
            🎯 **현실적인 회의 참여 방식**:
            - 완전한 동의보다는 건설적인 보완 의견을 제시하세요
            - 필요시 우려사항이나 리스크를 언급하세요
            - 실제 경험이나 데이터를 바탕으로 발언하세요
            - 다른 관점에서의 접근 방식을 제안하세요
            - 실행 가능성이나 제약 조건을 고려하세요
            """
        
        # 개선된 맥락 사용 (enhanced_context가 있으면 우선 사용)
        context_to_use = enhanced_context if enhanced_context else conversation_history
        
        user_message = f"맥락:\n{context_to_use}\n\n주제: {meeting_topic}\n라운드 {round_number}에서 발언하세요."
        
        if model_name.startswith('claude'):
            # Claude API 호출
            response = client.messages.create(
                model=model_name,
                max_tokens=300,
                temperature=0.8,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            ai_response = response.content[0].text.strip()
            
            # 🎯 마무리 라운드 발언 품질 검증 및 개선 (더 포괄적인 조건)
            is_any_final_round = (
                is_final_extension_round or 
                (is_final_round and round_number >= total_rounds) or
                round_number >= total_rounds or  # 총 라운드 수 이상
                (round_percentage >= 0.9)  # 90% 이상 진행된 경우
            )
            
            if is_any_final_round:
                validation = validate_final_statement(ai_response, persona.name)
                
                # 토론 계속 시도가 감지된 경우 강제로 마무리 발언으로 변경
                if validation['is_continuing_discussion']:
                    # 토론 계속 시도가 감지되면 완전히 새로운 마무리 발언 생성
                    forced_final_prompt = f"""🚨 **긴급 마무리 발언 생성**

당신은 {persona.name}({persona.role})입니다.

⚠️ **중요**: 방금 생성한 발언에서 토론 계속 시도가 감지되었습니다.
마무리 라운드에서는 오직 마무리만 해야 합니다.

📝 **반드시 포함해야 할 5가지 요소**:
1️⃣ "제가 이번 회의에서 제시한 핵심 의견은..." (자신의 발언 요약)
2️⃣ "전체 논의를 종합해보면..." (회의 전체 결론)
3️⃣ "구체적인 실행 방안으로는..." (실행 계획)
4️⃣ "특히 ○○님의 의견에 동의하며..." (다른 참가자와의 연결)
5️⃣ "오늘 함께 논의해 주신 모든 분들께 감사드립니다" (감사 인사)

🚫 **절대 금지**:
- 새로운 논점 제기
- "다음 발언자", "추가로 논의", "더 검토" 등의 표현
- 토론 확장 시도

주제: {meeting_topic}
최근 맥락: {context_to_use[-500:]}

완전한 마무리 발언만 생성하세요."""

                    try:
                        forced_response = client.messages.create(
                            model=model_name,
                            max_tokens=400,
                            temperature=0.5,  # 더 안정적인 응답을 위해 낮춤
                            system="당신은 회의 마무리 전문가입니다. 토론 확장 없이 오직 완전한 마무리 발언만 생성합니다.",
                            messages=[
                                {"role": "user", "content": forced_final_prompt}
                            ]
                        )
                        return forced_response.content[0].text.strip()
                    except:
                        # API 호출 실패 시 기본 마무리 발언
                        return f"제가 이번 회의에서 강조한 핵심은 {meeting_topic}에 대한 체계적 접근의 중요성입니다. 전체 논의를 종합해보면 모든 참가자분들의 전문성이 결합되어 의미 있는 결론에 도달했습니다. 구체적인 실행 방안으로는 오늘 논의된 내용들을 바탕으로 단계적 추진이 필요합니다. 특히 다른 참가자분들의 통찰력 있는 의견들에 깊이 공감하며, 오늘 함께 논의해 주신 모든 분들께 진심으로 감사드립니다."
                
                elif not validation['is_complete']:
                    # 일반적인 불완전한 마무리 발언인 경우 개선 시도
                    improved_response = improve_final_statement(
                        ai_response, 
                        persona, 
                        context_to_use, 
                        meeting_topic, 
                        model_name
                    )
                    
                    # 개선된 발언이 더 완전하다면 사용
                    improved_validation = validate_final_statement(improved_response, persona.name)
                    if improved_validation['is_complete'] and not improved_validation['is_continuing_discussion']:
                        return improved_response
                    else:
                        # 개선에 실패했다면 원본에 최소한의 마무리 요소 추가
                        return ai_response + f"\n\n오늘 모든 분들과 함께 {meeting_topic}에 대해 논의할 수 있어 정말 감사했습니다."
                
            return ai_response
        else:
            # OpenAI API 호출
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.8
            )
            ai_response = response.choices[0].message.content.strip()
            
            # 🎯 마무리 라운드 발언 품질 검증 및 개선 (더 포괄적인 조건)
            is_any_final_round = (
                is_final_extension_round or 
                (is_final_round and round_number >= total_rounds) or
                round_number >= total_rounds or  # 총 라운드 수 이상
                (round_percentage >= 0.9)  # 90% 이상 진행된 경우
            )
            
            if is_any_final_round:
                validation = validate_final_statement(ai_response, persona.name)
                
                # 토론 계속 시도가 감지된 경우 강제로 마무리 발언으로 변경
                if validation['is_continuing_discussion']:
                    # 토론 계속 시도가 감지되면 완전히 새로운 마무리 발언 생성
                    forced_final_prompt = f"""🚨 **긴급 마무리 발언 생성**

당신은 {persona.name}({persona.role})입니다.

⚠️ **중요**: 방금 생성한 발언에서 토론 계속 시도가 감지되었습니다.
마무리 라운드에서는 오직 마무리만 해야 합니다.

📝 **반드시 포함해야 할 5가지 요소**:
1️⃣ "제가 이번 회의에서 제시한 핵심 의견은..." (자신의 발언 요약)
2️⃣ "전체 논의를 종합해보면..." (회의 전체 결론)
3️⃣ "구체적인 실행 방안으로는..." (실행 계획)
4️⃣ "특히 ○○님의 의견에 동의하며..." (다른 참가자와의 연결)
5️⃣ "오늘 함께 논의해 주신 모든 분들께 감사드립니다" (감사 인사)

🚫 **절대 금지**:
- 새로운 논점 제기
- "다음 발언자", "추가로 논의", "더 검토" 등의 표현
- 토론 확장 시도

주제: {meeting_topic}
최근 맥락: {context_to_use[-500:]}

완전한 마무리 발언만 생성하세요."""

                    try:
                        forced_response = client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": "당신은 회의 마무리 전문가입니다. 토론 확장 없이 오직 완전한 마무리 발언만 생성합니다."},
                                {"role": "user", "content": forced_final_prompt}
                            ],
                            max_tokens=400,
                            temperature=0.5  # 더 안정적인 응답을 위해 낮춤
                        )
                        return forced_response.choices[0].message.content.strip()
                    except:
                        # API 호출 실패 시 기본 마무리 발언
                        return f"제가 이번 회의에서 강조한 핵심은 {meeting_topic}에 대한 체계적 접근의 중요성입니다. 전체 논의를 종합해보면 모든 참가자분들의 전문성이 결합되어 의미 있는 결론에 도달했습니다. 구체적인 실행 방안으로는 오늘 논의된 내용들을 바탕으로 단계적 추진이 필요합니다. 특히 다른 참가자분들의 통찰력 있는 의견들에 깊이 공감하며, 오늘 함께 논의해 주신 모든 분들께 진심으로 감사드립니다."
                
                elif not validation['is_complete']:
                    # 일반적인 불완전한 마무리 발언인 경우 개선 시도
                    improved_response = improve_final_statement(
                        ai_response, 
                        persona, 
                        context_to_use, 
                        meeting_topic, 
                        model_name
                    )
                    
                    # 개선된 발언이 더 완전하다면 사용
                    improved_validation = validate_final_statement(improved_response, persona.name)
                    if improved_validation['is_complete'] and not improved_validation['is_continuing_discussion']:
                        return improved_response
                    else:
                        # 개선에 실패했다면 원본에 최소한의 마무리 요소 추가
                        return ai_response + f"\n\n오늘 모든 분들과 함께 {meeting_topic}에 대해 논의할 수 있어 정말 감사했습니다."
                
            return ai_response
    except Exception as e:
        return f"[AI 응답 생성 오류: {str(e)}]"

def format_conversation_history(messages: List[Message], last_n: int = 15) -> str:
    """대화 히스토리 포맷팅 - 기본 버전 (하위 호환성 유지)"""
    recent_messages = messages[-last_n:] if len(messages) > last_n else messages
    history = ""
    for msg in recent_messages:
        history += f"{msg.persona_name}: {msg.content}\n"
    return history

def get_round_based_context(messages: List[Message], current_round: int, max_context_length: int = 2000) -> str:
    """라운드 기반 맥락 생성 - 전체 회의 맥락 유지"""
    if not messages:
        return ""
    
    # 라운드별 메시지 그룹화
    rounds_data = {}
    moderator_messages = []
    current_round_msgs = []
    
    for msg in messages:
        if msg.is_moderator:
            moderator_messages.append(msg)
        else:
            # 비사회자 메시지로 라운드 추정 (간단한 방식)
            estimated_round = len([m for m in messages[:messages.index(msg)+1] 
                                 if not m.is_moderator and not m.is_human_input]) // len([p for p in messages[0:1] if messages]) + 1
            
            if estimated_round not in rounds_data:
                rounds_data[estimated_round] = []
            rounds_data[estimated_round].append(msg)
    
    # 맥락 구성 전략
    context_parts = []
    
    # 1. 사회자 오프닝 (항상 포함)
    if moderator_messages:
        context_parts.append(f"[회의 시작] {moderator_messages[0].persona_name}: {moderator_messages[0].content}")
    
    # 2. 이전 라운드 요약 (라운드 2 이상일 때)
    if current_round > 1:
        previous_rounds_summary = []
        for round_num in sorted(rounds_data.keys()):
            if round_num < current_round:
                round_messages = rounds_data[round_num]
                if round_messages:
                    # 각 라운드의 핵심 포인트만 요약
                    key_points = []
                    for msg in round_messages:
                        # 메시지 길이가 긴 경우 요약
                        content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        key_points.append(f"{msg.persona_name}: {content}")
                    
                    previous_rounds_summary.append(f"\n[라운드 {round_num}]\n" + "\n".join(key_points))
        
        if previous_rounds_summary:
            context_parts.append("=== 이전 라운드 요약 ===")
            context_parts.extend(previous_rounds_summary)
    
    # 3. 최근 메시지들 (항상 포함 - 직접적 맥락)
    recent_messages = messages[-8:]  # 최근 8개 메시지
    if recent_messages:
        context_parts.append("\n=== 최근 대화 ===")
        for msg in recent_messages:
            context_parts.append(f"{msg.persona_name}: {msg.content}")
    
    # 4. 현재 라운드 진행 상황
    context_parts.append(f"\n=== 현재 상황 ===")
    context_parts.append(f"현재 라운드: {current_round}")
    
    # 전체 맥락 조합
    full_context = "\n".join(context_parts)
    
    # 토큰 길이 제한 (대략적으로 문자 수로 제한)
    if len(full_context) > max_context_length:
        # 길이가 초과되면 이전 라운드 요약 부분을 더 압축
        essential_parts = []
        
        # 필수 요소: 오프닝 + 최근 대화 + 현재 상황
        if moderator_messages:
            essential_parts.append(f"[회의 시작] {moderator_messages[0].persona_name}: {moderator_messages[0].content}")
        
        essential_parts.append("\n=== 최근 대화 ===")
        for msg in recent_messages:
            essential_parts.append(f"{msg.persona_name}: {msg.content}")
        
        essential_parts.append(f"\n=== 현재 상황 ===")
        essential_parts.append(f"현재 라운드: {current_round}")
        
        # 남은 공간에 이전 라운드 핵심만 추가
        essential_context = "\n".join(essential_parts)
        remaining_space = max_context_length - len(essential_context)
        
        if remaining_space > 200 and current_round > 1:
            # 가장 최근 1-2 라운드만 간략하게 추가
            recent_rounds = []
            for round_num in sorted(rounds_data.keys(), reverse=True):
                if round_num < current_round and len(recent_rounds) < 2:
                    round_messages = rounds_data[round_num][:3]  # 라운드당 최대 3개 메시지만
                    if round_messages:
                        round_summary = f"[라운드 {round_num}] " + "; ".join([f"{msg.persona_name}: {msg.content[:50]}..." for msg in round_messages])
                        if len(round_summary) < remaining_space:
                            recent_rounds.append(round_summary)
                            remaining_space -= len(round_summary)
            
            if recent_rounds:
                essential_parts.insert(-2, "\n=== 주요 라운드 요약 ===")
                essential_parts.insert(-2, "\n".join(reversed(recent_rounds)))
        
        full_context = "\n".join(essential_parts)
    
    return full_context

def get_comprehensive_meeting_context(meeting: 'VirtualMeeting') -> str:
    """회의 전체 맥락을 종합적으로 생성 - 과거 맥락 이해 개선"""
    context_parts = []
    
    # 1. 회의 기본 정보
    context_parts.append(f"=== 회의 정보 ===")
    context_parts.append(f"주제: {meeting.meeting_topic}")
    current_round = meeting.get_current_round_accurately()
    context_parts.append(f"현재 라운드: {current_round}/{meeting.max_rounds}")
    
    # 2. 현재 단계 정보
    round_percentage = current_round / meeting.max_rounds
    if round_percentage <= 0.2:
        stage = "문제 정의 및 현황 파악 단계"
    elif round_percentage <= 0.4:
        stage = "문제 탐색 및 해결책 제시 단계"
    elif round_percentage <= 0.6:
        stage = "해결책 비교 및 분석 단계"
    elif round_percentage <= 0.8:
        stage = "합의점 도출 및 구체화 단계"
    else:
        stage = "최종 결론 및 실행 방안 정리 단계"
    context_parts.append(f"토론 단계: {stage}")
    
    # 3. 라운드별 핵심 요약 (연장 라운드에서는 전체 히스토리 제공)
    if current_round > 0:
        context_parts.append(f"\n=== 회의 히스토리 요약 ===")
        
        # 🎯 연장 라운드이거나 마지막 단계에서는 전체 히스토리 제공
        is_extension_phase = hasattr(meeting, 'extension_granted') and meeting.extension_granted
        is_final_phase = round_percentage > 0.8
        is_final_extension_round = (current_round == meeting.max_rounds and is_extension_phase)
        
        if is_final_extension_round:
            # 연장 최종 라운드에서는 개인별 발언 히스토리 제공
            context_parts.append(f"\n=== 개인별 발언 히스토리 (기존 내용 정리용) ===")
            
            # 각 참가자별로 발언 내용 정리
            for persona in meeting.get_non_moderator_personas():
                persona_messages = [msg for msg in meeting.messages 
                                  if msg.persona_id == persona.id and not msg.is_moderator]
                
                if persona_messages:
                    context_parts.append(f"\n[{persona.role}] {persona.name}의 주요 발언:")
                    
                    # 각 라운드별 핵심 발언 (최대 3개 라운드)
                    round_count = len(persona_messages)
                    selected_rounds = [0, round_count//2, round_count-1] if round_count >= 3 else list(range(round_count))
                    
                    for i, msg_idx in enumerate(selected_rounds):
                        if msg_idx < len(persona_messages):
                            msg = persona_messages[msg_idx]
                            # 메시지 요약 (첫 문장 + 핵심 키워드)
                            sentences = msg.content.split('.')
                            summary = sentences[0] + ('.' + sentences[1][:50] + '...' if len(sentences) > 1 and len(sentences[1]) > 50 else ('.' + sentences[1] if len(sentences) > 1 else ''))
                            context_parts.append(f"  라운드 {msg_idx+1}: {summary}")
            
            # 전체 라운드 요약도 제공 (간략하게)
            start_round = 1
            max_rounds_to_show = current_round
        elif is_extension_phase or is_final_phase:
            # 전체 라운드 요약 제공
            start_round = 1
            max_rounds_to_show = current_round
        else:
            # 일반적으로는 최근 2-3라운드만
            start_round = max(1, current_round - 2)
            max_rounds_to_show = current_round
        
        for round_num in range(start_round, max_rounds_to_show + 1):
            round_messages = []
            # 해당 라운드의 메시지들 찾기
            non_moderator_count = len(meeting.get_non_moderator_personas())
            if non_moderator_count > 0:
                round_start_index = (round_num - 1) * non_moderator_count
                round_end_index = round_num * non_moderator_count
                
                msg_count = 0
                for i, msg in enumerate(meeting.messages):
                    if not msg.is_moderator and not msg.is_human_input:
                        if round_start_index <= msg_count < round_end_index:
                            # 메시지를 적당히 요약 (핵심 내용 추출)
                            sentences = msg.content.split('.')
                            if len(sentences) >= 2:
                                # 첫 두 문장 + 핵심 키워드
                                summary = sentences[0] + '.' + sentences[1].split(',')[0]
                                if len(summary) > 120:
                                    summary = summary[:120] + "..."
                            else:
                                summary = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            
                            # 페르소나 역할 정보 추가
                            persona = next((p for p in meeting.personas if p.id == msg.persona_id), None)
                            role_info = f"[{persona.role}]" if persona else ""
                            
                            round_messages.append(f"{role_info} {msg.persona_name}: {summary}")
                        msg_count += 1
            
            if round_messages:
                context_parts.append(f"[라운드 {round_num}]")
                # 연장 단계에서는 모든 발언, 일반 단계에서는 최대 4개
                max_messages = len(round_messages) if (is_extension_phase or is_final_phase) else 4
                context_parts.extend(round_messages[:max_messages])
    
    # 4. 최근 대화 (더 상세하게)
    context_parts.append(f"\n=== 최근 대화 ===")
    recent_messages = meeting.messages[-8:]  # 최근 8개로 확장
    for msg in recent_messages:
        # 메시지를 적절히 요약 (첫 문장 + α)
        sentences = msg.content.split('.')
        if len(sentences) > 1:
            content = sentences[0] + '.' + (sentences[1][:30] + "..." if len(sentences[1]) > 30 else sentences[1])
        else:
            content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        
        speaker_info = ""
        persona = next((p for p in meeting.personas if p.id == msg.persona_id), None)
        if persona and not msg.is_moderator:
            speaker_info = f"[{persona.role}]"
        
        context_parts.append(f"{speaker_info} {msg.persona_name}: {content}")
    
    # 5. 참고자료 (개선된 추출)
    if meeting.uploaded_files_content and meeting.meeting_topic:
        context_parts.append(f"\n=== 참고 자료 ===")
        topic_keywords = meeting.meeting_topic.lower().split()[:5]  # 키워드 확장
        
        # 관련 내용 추출
        relevant_content = meeting.get_relevant_file_content(topic_keywords)
        if relevant_content and len(relevant_content) > 50:
            # 참고자료를 적절한 길이로 요약
            if len(relevant_content) > 400:
                relevant_content = relevant_content[:400] + "..."
            context_parts.append(relevant_content)
    
    # 전체 맥락 조합 및 적절한 길이 제한
    full_context = "\n".join(context_parts)
    
    # 토큰 제한 (3000자 = 약 750토큰, max_tokens 300에 맞게 조정)
    max_length = 3000
    if len(full_context) > max_length:
        # 중요도 순으로 내용 유지
        essential = []
        essential.append(f"주제: {meeting.meeting_topic}")
        essential.append(f"라운드: {current_round}/{meeting.max_rounds}")
        essential.append(f"단계: {stage}")
        essential.append("\n최근대화:")
        
        # 최근 6개 메시지를 적절한 길이로
        for msg in meeting.messages[-6:]:
            content = msg.content.split('.')[0][:50] + "..." if len(msg.content) > 50 else msg.content
            essential.append(f"{msg.persona_name}: {content}")
        
        full_context = "\n".join(essential)
        
        # 여전히 길면 더 줄이기
        if len(full_context) > max_length:
            full_context = full_context[:max_length] + "..."
    
    return full_context

def stream_response(text: str, typing_speed: float = 0.1):
    """스트리밍 타이핑 효과 - 속도 조절 가능"""
    import time
    words = text.split()
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        time.sleep(typing_speed)  # 타이핑 속도 조절 (사용자 설정)

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
                # 세션 상태에서 타이핑 속도 가져오기
                meeting = st.session_state.virtual_meeting
                # 🎯 자연스러운 타이핑 속도 적용
                if meeting.natural_timing:
                    natural_delay = meeting.get_natural_typing_delay(len(message.content))
                    adjusted_speed = natural_delay / len(message.content) if message.content else meeting.typing_speed
                    st.write_stream(stream_response(message.content, adjusted_speed))
                else:
                    st.write_stream(stream_response(message.content, meeting.typing_speed))
            else:
                st.write(message.content)
        with col2:
            st.caption(message.timestamp.strftime('%H:%M:%S'))
            if message.is_human_input:
                st.caption("👤 인간 개입")

def should_moderator_intervene(meeting: VirtualMeeting) -> bool:
    """사회자가 개입해야 하는 상황인지 판단"""
    if not meeting.messages or meeting.conversation_round < 2:
        return False
    
    # 최근 사회자 개입 후 쿨다운 체크 (최소 5개 메시지 후에 다시 개입 가능)
    if meeting.last_moderator_intervention:
        messages_since_intervention = 0
        for msg in reversed(meeting.messages):
            if msg.timestamp <= meeting.last_moderator_intervention:
                break
            if not msg.is_moderator:  # 사회자가 아닌 메시지만 카운트
                messages_since_intervention += 1
        
        if messages_since_intervention < 5:  # 5개 메시지 미만이면 개입하지 않음
            return False
    
    # 특정 조건에서 사회자 개입 필요
    total_rounds = meeting.max_rounds
    current_round = meeting.conversation_round + 1
    round_percentage = current_round / total_rounds
    
    # 단계 전환 시점에서 사회자가 정리 (더 엄격한 조건)
    stage_transitions = [0.2, 0.4, 0.6, 0.8]
    for transition in stage_transitions:
        if abs(round_percentage - transition) < 0.02:  # 전환점을 더 좁게 설정 (5% -> 2%)
            # 해당 단계에서 이미 개입했는지 체크
            if meeting.last_moderator_intervention:
                last_intervention_round = meeting.conversation_round
                transition_round = int(total_rounds * transition)
                if abs(last_intervention_round - transition_round) <= 2:  # 이미 해당 단계에서 개입했으면 스킵
                    continue
            return True
    
    # 마지막 라운드 전에 사회자가 마무리 유도 (한 번만)
    if current_round >= total_rounds - 2:
        # 마지막 단계에서 아직 개입하지 않았다면 개입
        if not meeting.last_moderator_intervention:
            return True
        # 마지막 개입이 현재 라운드보다 5라운드 이상 전이면 다시 개입
        messages_since_last_intervention = 0
        for msg in reversed(meeting.messages):
            if msg.timestamp <= meeting.last_moderator_intervention:
                break
            if not msg.is_moderator:
                messages_since_last_intervention += 1
        if messages_since_last_intervention >= 10:  # 10개 메시지 후에 마무리 개입
            return True
    
    return False

def generate_final_meeting_summary(meeting: VirtualMeeting, model_name: str = "gpt-4o-mini") -> str:
    """사회자가 회의 최종 마무리 메시지 생성"""
    try:
        # 모델에 따른 클라이언트 설정
        if model_name.startswith('claude'):
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key or anthropic_key.strip() == '' or anthropic_key == 'NA':
                raise ValueError("Anthropic API 키가 올바르지 않습니다.")
            client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                raise ValueError("OpenAI API 키가 올바르지 않습니다.")
            client = OpenAI(api_key=openai_key)
        
        # 전체 회의 맥락 생성
        comprehensive_context = get_comprehensive_meeting_context(meeting)
        
        system_prompt = """당신은 회의 사회자입니다. 
        
        모든 참가자가 마지막 라운드에서 최종 결론을 발표했습니다.
        이제 회의를 공식적으로 마무리할 차례입니다.
        
        다음 요소들을 포함하여 회의를 마무리하세요:
        1. 오늘 회의에서 논의된 주요 내용 간략 정리
        2. 참가자들이 제시한 핵심 결론들 요약
        3. 합의된 사항이나 공통된 의견 강조
        4. 향후 실행해야 할 액션 아이템 정리
        5. 회의 참가에 대한 감사 인사
        6. 회의 공식 종료 선언
        
        따뜻하고 전문적인 톤으로 3-4문장 정도로 작성해주세요.
        """
        
        user_message = f"""회의 전체 맥락:
        {comprehensive_context}
        
        주제: {meeting.meeting_topic}
        총 라운드: {meeting.max_rounds}
        
        위 내용을 바탕으로 회의를 공식적으로 마무리해주세요."""
        
        if model_name.startswith('claude'):
            response = client.messages.create(
                model=model_name,
                max_tokens=300,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            return response.content[0].text.strip()
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"🏁 모든 참가자분들의 훌륭한 의견 발표로 '{meeting.meeting_topic}' 회의가 성공적으로 마무리되었습니다. 오늘 논의된 내용들을 바탕으로 좋은 결과가 있기를 기대합니다. 회의를 공식 종료하겠습니다. 감사합니다."

def generate_moderator_intervention(meeting: VirtualMeeting, model_name: str = "gpt-4o-mini") -> str:
    """사회자의 능동적 개입 메시지 생성"""
    try:
        # 모델에 따른 클라이언트 설정
        if model_name.startswith('claude'):
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if not anthropic_key or anthropic_key.strip() == '' or anthropic_key == 'NA':
                return "지금까지의 논의를 정리해보겠습니다."
            client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                return "지금까지의 논의를 정리해보겠습니다."
            client = OpenAI(api_key=openai_key)
        
        # 현재 상황 분석
        total_rounds = meeting.max_rounds
        current_round = meeting.conversation_round + 1
        round_percentage = current_round / total_rounds
        
        # 단계별 사회자 역할 정의
        if round_percentage <= 0.2:
            stage_role = "문제 정의 단계를 정리하고 다음 단계로 안내"
        elif round_percentage <= 0.4:
            stage_role = "다양한 관점들을 정리하고 해결책 모색 단계로 전환"
        elif round_percentage <= 0.6:
            stage_role = "제시된 해결책들을 정리하고 비교 분석 단계로 안내"
        elif round_percentage <= 0.8:
            stage_role = "논의된 내용을 바탕으로 합의점 도출 유도"
        else:
            stage_role = "전체 회의 내용을 종합하고 최종 결론 도출"
        
        # 최근 대화 요약
        recent_messages = meeting.messages[-6:] if len(meeting.messages) > 6 else meeting.messages
        recent_summary = "\n".join([f"{msg.persona_name}: {msg.content[:100]}..." for msg in recent_messages])
        
        # 개입 횟수에 따른 다양한 접근 방식
        moderator_messages = [msg for msg in meeting.messages if msg.is_moderator and not msg.is_human_input]
        intervention_count = len(moderator_messages)
        
        if intervention_count % 3 == 0:
            approach = "참가자들의 의견을 요약하고 다음 단계 방향을 제시하는"
        elif intervention_count % 3 == 1:
            approach = "구체적인 질문을 통해 논의를 심화시키는"
        else:
            approach = "다른 관점에서 문제를 바라보도록 유도하는"
        
        system_prompt = f"""당신은 전문적인 회의 사회자입니다. 
        현재 상황:
        - 회의 주제: {meeting.meeting_topic}
        - 현재 라운드: {current_round}/{total_rounds} ({round_percentage*100:.1f}% 진행)
        - 현재 단계: {stage_role}
        - 접근 방식: {approach}
        
        다음 역할을 수행하세요:
        1. {approach} 방식으로 개입
        2. 이전 발언과는 다른 관점이나 표현 사용
        3. 참가자들에게 구체적이고 실행 가능한 방향 제시
        
        중요: 이전 사회자 발언과 중복되지 않도록 새로운 관점이나 구체적인 질문을 포함하여 2-3문장으로 발언하세요.
        예시 접근:
        - "구체적으로 어떤 부분에서..." 
        - "다른 관점에서 보면..."
        - "실제 구현 시 고려해야 할..."
        - "우선순위를 정한다면..." 등"""
        
        user_message = f"최근 대화 내용:\n{recent_summary}\n\n위 내용을 바탕으로 사회자로서 적절한 개입 발언을 해주세요."
        
        if model_name.startswith('claude'):
            response = client.messages.create(
                model=model_name,
                max_tokens=300,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            return response.content[0].text.strip()
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
            
    except Exception as e:
        # 기본 메시지 반환
        total_rounds = meeting.max_rounds
        current_round = meeting.conversation_round + 1
        return f"지금까지 좋은 의견들이 많이 나왔습니다. 현재 {current_round}/{total_rounds} 라운드가 진행되고 있으니, 논의를 더욱 발전시켜 나가겠습니다."

def run_conversation_round(meeting: VirtualMeeting) -> bool:
    """🎯 대화 체인 시스템 - 한 번에 한 발언자만 처리"""
    if not meeting.should_continue():
        return False
    
    # 현재 발언자 가져오기
    current_persona = meeting.get_next_speaker()
    if not current_persona:
        return False
    
    # 🎯 대화 흐름 분석 및 방향 제시
    meeting.analyze_conversation_flow()
    conversation_direction = meeting.get_conversation_direction()
    
    # 모델 선택
    selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
    
    # 기본 대화 히스토리
    conversation_history = format_conversation_history(meeting.messages, last_n=10)
    
    # 종합 맥락 생성
    comprehensive_context = get_comprehensive_meeting_context(meeting)
    
    # 🎯 연장 라운드 및 마지막 라운드 여부 확인
    current_round = meeting.conversation_round + 1
    is_final_round = current_round >= meeting.max_rounds
    is_final_extension_round = (hasattr(meeting, 'extension_granted') and 
                               meeting.extension_granted and 
                               current_round == meeting.max_rounds)
    
    # 🎯 마지막 라운드에서는 참가자들에게 완전한 마무리 발언 유도
    if is_final_extension_round and not current_persona.is_moderator:
        # 마지막 라운드 특별 컨텍스트 추가
        final_round_context = f"""
        
        🏁 **최종 마무리 라운드 특별 안내**:
        
        이번이 {current_persona.name}님의 마지막 발언 기회입니다.
        반드시 다음 5가지를 모두 포함하여 완전한 마무리를 해주세요:
        
        1. 자신의 주요 발언 내용 요약
        2. 회의 전체 결론 정리  
        3. 구체적인 실행 방안 제시
        4. 다른 참가자들과의 합의점 언급
        5. 진심 어린 감사 인사
        
        불완전한 마무리는 회의 품질을 저하시킵니다.
        """
    else:
        final_round_context = ""
    
    # 🎯 AI 응답 생성 (대화 체인 시스템 적용)
    response = generate_ai_response(
        current_persona,
        conversation_history,
        meeting.meeting_topic,
        meeting.uploaded_files_content,
        current_round,
        enhanced_context=comprehensive_context,
        model_name=selected_model,
        total_rounds=meeting.max_rounds,
        is_final_round=is_final_extension_round,  # 연장된 마지막 라운드인지 전달
        final_round_context=final_round_context,  # 🎯 마지막 라운드 특별 컨텍스트 추가
        conversation_direction=conversation_direction,  # 🎯 대화 방향 가이드 추가
        meeting=meeting  # meeting 객체 전달
    )
    
    # 메시지 추가
    meeting.add_message(current_persona.id, response)
    
    # 🎯 발언자 순서만 진행 (라운드는 절대 자동 증가하지 않음)
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
    
    
    # 세션 상태 초기화
    initialize_session_state()
    meeting = st.session_state.virtual_meeting
    
    # 사이드바 - 회의 설정
    with st.sidebar:
        st.header("🎯 회의 설정")
        
        # AI 모델 선택 (독서토론과 동일한 방식)
        st.subheader("🤖 AI 모델 설정")
        
        # 사용 가능한 모델 목록 생성
        available_models = []
        has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
        if has_anthropic_key:
            available_models.extend([
                'claude-3-5-sonnet-latest',
                'claude-3-5-haiku-latest',
            ])
        has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
        if has_openai_key:
            available_models.extend(['gpt-4o', 'gpt-4o-mini'])
        
        # 모델이 하나도 없으면 기본값 추가
        if not available_models:
            available_models = ['gpt-4o-mini']
        
        # 현재 선택된 모델이 사용 가능한 목록에 있는지 확인
        current_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
        if current_model not in available_models and available_models:
            current_model = available_models[0]
            st.session_state.selected_ai_model = current_model
        
        # 모델 선택 UI
        selected_model = st.selectbox(
            '🧠 AI 모델 선택',
            options=available_models,
            index=available_models.index(current_model) if current_model in available_models else 0,
            help='Claude(Anthropic)는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
        )
        
        # 모델이 실제로 변경된 경우에만 세션 상태 업데이트
        if selected_model != st.session_state.get('selected_ai_model'):
            st.session_state.selected_ai_model = selected_model
        
        # 선택된 모델 정보 표시
        if selected_model.startswith('claude'):
            st.info("🧠 **Claude 모델 사용 중**\n- 고품질 대화 생성\n- 긴 맥락 이해 우수")
        else:
            st.info("🧠 **OpenAI 모델 사용 중**\n- 빠른 응답 속도\n- 안정적인 성능")
        
        st.divider()
        
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
        new_max_rounds = st.slider(
            "최대 대화 라운드",
            min_value=3,
            max_value=100,
            value=meeting.max_rounds,
            help="🔒 이 값은 절대 자동으로 변경되지 않습니다! 라운드는 자동으로 진행되며, 마무리가 안 된 경우에만 2라운드 자동 연장됩니다."
        )
        
        # 🔧 원본 최대 라운드 추적 (사용자가 직접 변경할 때만)
        if new_max_rounds != meeting.max_rounds:
            meeting.max_rounds = new_max_rounds
            meeting.original_max_rounds = new_max_rounds  # 사용자가 직접 설정한 원본 값 저장
            meeting.extension_granted = False  # 연장 여부 초기화
            st.success(f"✅ 최대 라운드가 {new_max_rounds}로 설정되었습니다!")
        
        # 발언 속도 설정
        meeting.speaking_speed = st.slider(
            "발언 간격 (초)",
            min_value=1,
            max_value=10,
            value=meeting.speaking_speed,
            help="자동 모드에서 발언 간격을 조절합니다"
        )
        
        # 타이핑 속도 설정 (새로 추가)
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
            if value == meeting.typing_speed:
                current_option = option
                break
        
        selected_option = st.selectbox(
            "💬 텍스트 타이핑 속도",
            options=list(typing_options.keys()),
            index=list(typing_options.keys()).index(current_option),
            help="AI 발언이 화면에 타이핑되어 나오는 속도를 조절합니다"
        )
        
        if typing_options[selected_option] == "custom":
            meeting.typing_speed = st.slider(
                "커스텀 타이핑 속도 (초/단어)",
                min_value=0.01,
                max_value=0.5,
                value=meeting.typing_speed,
                step=0.01,
                help="숫자가 낮을수록 빠르게 타이핑됩니다"
            )
        else:
            meeting.typing_speed = typing_options[selected_option]
        
        # 타이핑 속도 미리보기
        with st.expander("⚡ 타이핑 속도 미리보기", expanded=False):
            if st.button("🎬 테스트 해보기"):
                sample_text = "안녕하세요! 이것은 타이핑 속도 테스트입니다. 현재 설정된 속도로 텍스트가 표시됩니다."
                st.write("**샘플 텍스트:**")
                st.write_stream(stream_response(sample_text, meeting.typing_speed))
                st.caption(f"현재 설정: {meeting.typing_speed}초/단어")
        
        st.divider()
        
        # 🎯 회의 진행 상태 및 마무리 체크
        if meeting.is_active:
            st.header("📊 회의 진행 상태")
            
            current_round = meeting.get_current_round_accurately()
            
            # 기본 진행 상태 (progress bar는 항상 0.0~1.0 사이)
            progress = min(current_round / meeting.max_rounds, 1.0)
            
            # 연장 라운드인 경우 별도 표시
            if current_round > meeting.max_rounds:
                st.progress(1.0, text=f"연장 진행: {current_round}/{meeting.max_rounds} 라운드 (완료)")
            else:
                progress_percentage = int(progress * 100)
                st.progress(progress, text=f"진행률: {current_round}/{meeting.max_rounds} 라운드 ({progress_percentage}%)")
            
            # 연장 상태 표시
            if hasattr(meeting, 'extension_granted') and meeting.extension_granted:
                if current_round == meeting.max_rounds:
                    st.warning("🔄 **연장 최종 라운드**")
                    st.caption("각 참가자가 히스토리 요약과 감사 인사를 해야 합니다.")
                elif current_round > meeting.original_max_rounds:
                    st.info("⏰ **연장 라운드 진행 중**")
                    st.caption(f"원래 {meeting.original_max_rounds}라운드 → 2라운드 연장")
            
            # 🎯 마무리 상태 실시간 체크 (연장 최종 라운드에서만)
            if (hasattr(meeting, 'extension_granted') and meeting.extension_granted and 
                current_round == meeting.max_rounds):
                
                st.subheader("✅ 마무리 체크리스트")
                
                # 현재 라운드에서 발언한 참가자들의 메시지 추출
                current_round_start = (current_round - 1) * len(meeting.get_non_moderator_personas())
                final_messages = []
                msg_count = 0
                
                for msg in meeting.messages:
                    if not msg.is_moderator and not msg.is_human_input:
                        if msg_count >= current_round_start:
                            final_messages.append(msg)
                        msg_count += 1
                
                # 각 참가자별 마무리 상태 체크
                for persona in meeting.get_non_moderator_personas():
                    persona_final_msg = None
                    for msg in final_messages:
                        if msg.persona_id == persona.id:
                            persona_final_msg = msg
                            break
                    
                    if persona_final_msg:
                        # 마무리 요소 체크
                        content_lower = persona_final_msg.content.lower()
                        
                        has_history = any(keyword in content_lower for keyword in ['이번 회의에서', '제가', '강조한', '핵심'])
                        has_summary = any(keyword in content_lower for keyword in ['전체', '논의', '종합', '결론'])
                        has_gratitude = any(keyword in content_lower for keyword in ['감사', '고생', '수고', '참여'])
                        
                        completion_score = sum([has_history, has_summary, has_gratitude])
                        
                        if completion_score >= 2:
                            st.success(f"✅ {persona.name}: 마무리 완료")
                        else:
                            st.warning(f"⏳ {persona.name}: 마무리 대기 중")
                    else:
                        st.error(f"❌ {persona.name}: 아직 발언하지 않음")
                
                # 전체 마무리 상태
                if meeting._verify_final_round_completion(final_messages):
                    st.success("🎉 **모든 참가자 마무리 완료!**")
                    st.caption("곧 회의가 자동 종료됩니다.")
                else:
                    st.info("⏳ **마무리 진행 중...**")
                    st.caption("모든 참가자의 히스토리 요약과 감사 인사를 기다리고 있습니다.")
        
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
            
            # 파일이 처리된 경우 분석 결과 표시
            if meeting.uploaded_files_content:
                st.subheader("📖 파일 분석 결과")
                
                # 파일 분석 실행
                analysis = meeting.analyze_uploaded_files()
                
                # 분석 정보 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📄 총 길이", f"{analysis.get('total_length', 0):,}자")
                with col2:
                    st.metric("📝 단어 수", f"{analysis.get('word_count', 0):,}개")
                with col3:
                    st.metric("🔑 키워드", f"{len(analysis.get('keywords', [])):,}개")
                
                # 핵심 키워드 표시
                if analysis.get('keywords'):
                    st.write("**🔑 핵심 키워드:**")
                    keyword_display = ", ".join(analysis['keywords'][:15])
                    st.info(keyword_display)
                
                # 회의 주제와의 연관성 표시
                if meeting.meeting_topic:
                    topic_keywords = meeting.meeting_topic.replace(',', ' ').replace('.', ' ').split()
                    topic_keywords = [k.strip().lower() for k in topic_keywords if len(k.strip()) >= 2]
                    file_keywords = [k.lower() for k in analysis.get('keywords', [])]
                    
                    matching_keywords = [k for k in topic_keywords if k in file_keywords]
                    if matching_keywords:
                        st.success(f"✅ 회의 주제와 매칭되는 키워드: {', '.join(matching_keywords)}")
                    else:
                        st.warning("⚠️ 회의 주제와 직접적으로 매칭되는 키워드가 없습니다.")
                
                # 파일 내용 미리보기 (토글)
                with st.expander("📋 파일 내용 미리보기", expanded=False):
                    st.text_area(
                        "처리된 내용",
                        value=analysis.get('summary', meeting.uploaded_files_content[:500]),
                        height=150,
                        disabled=True,
                        key="file_preview"
                    )
                
                # RAG 활용 미리보기
                if meeting.meeting_topic:
                    with st.expander("🔍 AI가 활용할 관련 내용 미리보기", expanded=False):
                        relevant_content = meeting.get_relevant_file_content(topic_keywords)
                        if relevant_content:
                            st.text_area(
                                "회의 주제와 관련된 파일 내용",
                                value=relevant_content,
                                height=200,
                                disabled=True,
                                help="이 내용이 AI 응답 생성 시 우선적으로 참고됩니다"
                            )
                        else:
                            st.info("회의 주제와 관련된 특정 내용을 찾지 못했습니다. 전체 요약이 사용됩니다.")
        
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
                st.success("🚀 자동 모드 활성화! 정해진 라운드까지 완전 자동으로 진행됩니다.")
                st.info("💡 화면을 보고 있지 않아도 됩니다. 자동으로 완료되면 알림이 표시됩니다.")
        
        # 회의 종료 조건
        if meeting.is_active:
            st.divider()
            st.header("📊 진행 상황")
            progress = min(meeting.conversation_round / meeting.max_rounds, 1.0)
            
            # 연장 라운드인 경우 별도 표시
            if meeting.conversation_round > meeting.max_rounds:
                st.progress(1.0, text=f"연장 진행: {meeting.conversation_round}/{meeting.max_rounds} 라운드 (완료)")
            else:
                progress_percentage = int(progress * 100)
                st.progress(progress, text=f"라운드 진행: {meeting.conversation_round}/{meeting.max_rounds} ({progress_percentage}%)")
    
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
                        key=f"show_prompt_{persona.id}_{i}"  # 인덱스 추가로 고유성 보장
                    )
                    if show_prompt:
                        st.text_area(
                            "프롬프트",
                            value=persona.prompt,
                            height=100,
                            disabled=True,
                            key=f"prompt_view_{persona.id}_{i}"  # 인덱스 추가로 고유성 보장
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
        
        # 🎯 사회자 발언 분석 시스템 개선 안내
        with st.expander("🧠 **사회자 발언 분석 시스템 대폭 개선!**", expanded=False):
            st.success("🎯 **핵심 개선사항**")
            st.write("• **참가자 발언 내용 분석**: 8라운드부터 사회자가 모든 참가자의 발언 품질을 5단계로 분석")
            st.write("• **타당한 근거 기반 결정**: 단순 라운드 수가 아닌 실제 마무리 완성도로 회의 종료 판단")
            st.write("• **개별 참가자 피드백**: 누구의 어떤 부분이 부족한지 구체적으로 분석하여 안내")
            st.write("• **토론 계속 시도 감지**: '추가 논의', '다음 단계' 등 마무리 회피 패턴 실시간 감지")
            
            st.info("🎯 **8라운드 이후 새로운 기능**")
            st.write("• **수동 모드**: '참가자 분석 & 마무리 결정' 버튼으로 정밀 분석")
            st.write("• **자동 모드**: 사회자 차례에 자동으로 참가자 발언 분석 실행")
            st.write("• **품질 기준**: 80% 이상 참가자가 5단계 중 4단계 이상 완료 시에만 종료")
            st.write("• **연장 결정**: 분석 결과에 따른 근거 있는 2라운드 연장")
            
            st.error("🚨 **해결된 기존 문제들**")
            st.write("• 8-10라운드 동일한 마무리 발언 반복 → **완전 차단**")
            st.write("• 사회자가 아무런 생각 없이 특정 라운드에서 종료 → **분석 기반 결정**")
            st.write("• 참가자 발언 내용 무시하고 기계적 진행 → **내용 검토 후 타당한 판단**")
            
            st.success("💡 **이제 사회자가 참가자들의 실제 발언을 충분히 분석한 후 타당한 근거로 마무리를 결정합니다!**")
        
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
                # 라운드 표시에 연장 상태 정보 추가
                current_round_display = f"{meeting.conversation_round + 1}/{meeting.max_rounds}"
                
                # 🎯 연장 라운드 상태 표시
                if hasattr(meeting, 'extension_granted') and meeting.extension_granted:
                    if meeting.conversation_round + 1 == meeting.max_rounds:
                        current_round_display += " (🏁 연장 최종)"
                    elif meeting.conversation_round + 1 > meeting.original_max_rounds:
                        current_round_display += " (⏰ 연장중)"
                    else:
                        current_round_display += " (⏰ 연장예정)"
                elif meeting.conversation_round + 1 == meeting.max_rounds:
                    current_round_display += " (🏁 마지막)"
                elif meeting.conversation_round >= meeting.max_rounds:
                    current_round_display = f"{meeting.max_rounds}/{meeting.max_rounds} (✅ 완료)"
                
                st.metric("🔄 현재 라운드", current_round_display)
            with col3:
                st.metric("💬 총 메시지", len(meeting.messages))
            with col4:
                next_speaker = meeting.get_next_speaker()
                if meeting.conversation_round >= meeting.max_rounds:
                    # 회의가 종료된 경우
                    moderator = meeting.get_moderator()
                    last_message = meeting.messages[-1] if meeting.messages else None
                    
                    if last_message and last_message.is_moderator and moderator and last_message.persona_id == moderator.id:
                        st.metric("🎤 다음 발언자", "회의 완료")
                    else:
                        st.metric("🎤 다음 발언자", f"{moderator.name} (마무리)")
                elif meeting.conversation_round + 1 == meeting.max_rounds:
                    # 마지막 라운드인 경우
                    speaker_name = next_speaker.name if next_speaker else "없음"
                    st.metric("🎤 다음 발언자", f"{speaker_name} (최종결론)")
                else:
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
            
            # 라운드 진행 상황 표시 (조정 기능 제거)
            st.subheader("📊 라운드 진행 상황")
            col1, col2 = st.columns([2, 1])
            with col1:
                # 현재 진행률 계산
                current_progress = meeting.conversation_round / meeting.max_rounds * 100
                progress_color = "🟢" if current_progress < 70 else "🟡" if current_progress < 90 else "🔴"
                
                st.write(f"**현재 진행률**: {progress_color} {current_progress:.1f}% ({meeting.conversation_round}/{meeting.max_rounds})")
                
                # 토론 단계 표시
                round_percentage = (meeting.conversation_round + 1) / meeting.max_rounds
                if round_percentage <= 0.2:
                    stage = "🔍 문제 정의 및 현황 파악"
                elif round_percentage <= 0.4:
                    stage = "💡 문제 탐색 및 해결책 제시"
                elif round_percentage <= 0.6:
                    stage = "⚖️ 해결책 비교 및 분석"
                elif round_percentage <= 0.8:
                    stage = "🤝 합의점 도출 및 구체화"
                else:
                    stage = "📋 최종 결론 및 실행 방안"
                
                st.info(f"**현재 토론 단계**: {stage}")
            
            with col2:
                # 설정값 보호 상태 표시
                st.success(f"🔒 **최대 라운드 고정**\n{meeting.original_max_rounds}라운드로 설정됨")
                if meeting.extension_granted:
                    st.warning(f"⚠️ **1라운드 연장**\n{meeting.original_max_rounds} → {meeting.max_rounds}")
                st.info("💡 사이드바에서만 변경 가능")
                
                # 라운드 자동 진행 안내
                st.caption("🔄 라운드는 모든 참가자 발언 완료 시 자동 진행됩니다")
            
            # 대화 진행 컨트롤
            st.subheader("🗣️ 대화 진행")
            
            # 🎯 대화 체인 시스템 상태 표시
            non_moderator_personas = meeting.get_non_moderator_personas()
            if non_moderator_personas:
                next_speaker = meeting.get_next_speaker()
                if next_speaker:
                    st.info(f"🎯 **다음 발언자**: {next_speaker.name} ({next_speaker.role}) | 발언 순서: {meeting.turn_counter + 1}번째")
                
                # 대화 방향 가이드 표시
                if hasattr(meeting, 'get_conversation_direction'):
                    direction = meeting.get_conversation_direction()
                    if direction and direction != "회의 주제에 대한 첫 번째 의견을 제시해주세요.":
                        st.info(f"🧭 **대화 방향**: {direction}")
                
                # 현재 논의 초점 표시
                if hasattr(meeting, 'discussion_focus') and meeting.discussion_focus:
                    st.success(f"🎯 **현재 논의 초점**: {meeting.discussion_focus}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                # 🎯 회의 상태에 따른 버튼 표시
                if meeting.conversation_round >= meeting.max_rounds:
                    st.success("🏁 회의 완료")
                    st.info(f"✅ {meeting.max_rounds}라운드 모두 완료되었습니다.")
                elif st.button("💬 다음 발언", type="primary"):
                    with st.spinner("🤖 AI가 응답을 생성 중입니다..."):
                        success = run_conversation_round(meeting)
                        if success:
                            st.rerun()
                        else:
                            st.info("ℹ️ 회의가 종료되었습니다.")
            
            with col2:
                # 진행 상황 표시 (라운드는 자동으로 진행됨)
                current_round_display = meeting.conversation_round + 1
                progress = min(meeting.conversation_round / meeting.max_rounds, 1.0)
                
                # 연장 라운드인 경우 표시 조정
                if meeting.conversation_round >= meeting.max_rounds:
                    completion_text = "완료"
                    st.metric(
                        "📊 진행 상황", 
                        f"{current_round_display}/{meeting.max_rounds} 라운드",
                        f"100% {completion_text}"
                    )
                    st.progress(1.0)
                else:
                    st.metric(
                        "📊 진행 상황", 
                        f"{current_round_display}/{meeting.max_rounds} 라운드",
                        f"{progress*100:.1f}% 완료"
                    )
                    st.progress(progress)
                
                # 라운드 자동 진행 상태 표시
                non_moderator_count = len(meeting.get_non_moderator_personas())
                if non_moderator_count > 0:
                    current_turn_in_round = (meeting.current_speaker_index % non_moderator_count) + 1
                    st.caption(f"현재 라운드 내 진행: {current_turn_in_round}/{non_moderator_count}명 발언")
                else:
                    st.caption("참가자가 없습니다")
            
            with col3:
                current_round = meeting.get_current_round_accurately()
                
                # 🎯 8라운드 이후에는 분석 기반 사회자 발언으로 변경
                if current_round >= 8:
                    if st.button("🎯 참가자 분석 & 마무리 결정"):
                        moderator = meeting.get_moderator()
                        if moderator:
                            with st.spinner("🔍 참가자 발언을 분석하고 있습니다..."):
                                # 🎯 참가자 발언 상세 분석
                                analysis_result = meeting.analyze_participant_statements_for_closure()
                                selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                                
                                # 🎯 분석 결과 기반 사회자 메시지 생성
                                informed_message = meeting.generate_informed_closure_message(analysis_result, selected_model)
                                meeting.add_message(moderator.id, informed_message)
                                meeting.last_moderator_intervention = datetime.now()
                                
                                # 🎯 분석 결과 표시
                                if analysis_result['can_conclude']:
                                    st.success("🎉 **분석 완료**: 모든 참가자가 완전한 마무리 발언을 완료했습니다!")
                                    st.info(f"📊 품질 분석: {analysis_result['high_quality_conclusions']}/{analysis_result['total_participants']}명 완료 ({analysis_result['overall_quality_ratio']:.1%})")
                                    
                                    # 회의 종료 옵션 제공
                                    if st.button("🏁 지금 회의 종료", type="primary"):
                                        meeting.is_active = False
                                        st.balloons()
                                        st.rerun()
                                else:
                                    st.warning("⚠️ **분석 결과**: 일부 참가자의 마무리가 불완전합니다.")
                                    st.info(f"📋 문제점: {', '.join(analysis_result.get('reasons_for_continuation', []))}")
                                    
                                    # 연장 여부 선택
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        if st.button("⏰ 2라운드 연장"):
                                            if not getattr(meeting, 'extension_granted', False):
                                                meeting.extension_granted = True
                                                meeting.max_rounds += 2
                                                st.success("✅ 2라운드 연장되었습니다.")
                                            st.rerun()
                                    with col_b:
                                        if st.button("🔚 지금 종료"):
                                            meeting.is_active = False
                                            st.info("회의가 종료되었습니다.")
                                            st.rerun()
                                
                                st.rerun()
                        else:
                            st.error("❌ 사회자가 없습니다.")
                else:
                    # 8라운드 이전에는 기존 방식 유지
                    if st.button("🎯 사회자 정리"):
                        moderator = meeting.get_moderator()
                        if moderator:
                            with st.spinner("🎯 사회자가 정리 중입니다..."):
                                selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                                intervention_message = generate_moderator_intervention(meeting, selected_model)
                                meeting.add_message(moderator.id, intervention_message)
                                meeting.last_moderator_intervention = datetime.now()
                                st.success("✅ 사회자가 중간 정리를 했습니다.")
                                st.rerun()
                        else:
                            st.error("❌ 사회자가 없습니다.")
            
            with col4:
                if st.button("🔚 회의 종료"):
                    moderator = meeting.get_moderator()
                    current_round = meeting.get_current_round_accurately()
                    
                    # 🎯 8라운드 이후에는 분석 기반 마무리 메시지
                    if current_round >= 8 and moderator:
                        with st.spinner("🔍 최종 분석 중..."):
                            analysis_result = meeting.analyze_participant_statements_for_closure()
                            selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                            final_message = meeting.generate_informed_closure_message(analysis_result, selected_model)
                            meeting.add_message(moderator.id, final_message)
                            
                            # 분석 결과 표시
                            if analysis_result['can_conclude']:
                                st.success(f"🎉 **완전한 마무리**: {analysis_result['overall_quality_ratio']:.1%} 품질로 회의 완료!")
                            else:
                                st.warning(f"⚠️ **불완전한 마무리**: {analysis_result['overall_quality_ratio']:.1%} 품질이지만 회의 종료")
                    else:
                        # 기존 방식
                        if moderator:
                            closing_message = "오늘 회의를 마치겠습니다. 모든 분들의 활발한 참여에 감사드립니다."
                            meeting.add_message(moderator.id, closing_message)
                    
                    meeting.is_active = False
                    st.success("✅ 회의가 종료되었습니다.")
                    st.rerun()
            
            # 토론 완성도 체크 (새로 추가)
            if meeting.conversation_round > 0:
                st.subheader("📊 토론 완성도 체크")
                
                # 진행률 기반 완성도 분석
                round_percentage = meeting.conversation_round / meeting.max_rounds
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    # 토론 깊이 체크
                    avg_message_length = sum(len(msg.content) for msg in meeting.messages) / len(meeting.messages) if meeting.messages else 0
                    depth_score = min(100, avg_message_length / 2)  # 200자 기준 100점
                    st.metric("💭 토론 깊이", f"{depth_score:.0f}점", help="평균 발언 길이 기준")
                
                with col2:
                    # 참여도 체크
                    non_mod_personas = meeting.get_non_moderator_personas()
                    if non_mod_personas:
                        speaker_counts = {}
                        for msg in meeting.messages:
                            if not msg.is_moderator and not msg.is_human_input:
                                speaker_counts[msg.persona_id] = speaker_counts.get(msg.persona_id, 0) + 1
                        
                        participation_rate = len(speaker_counts) / len(non_mod_personas) * 100
                        st.metric("👥 참여도", f"{participation_rate:.0f}%", help="모든 참가자 발언 비율")
                
                with col3:
                    # 단계별 진행도
                    if round_percentage <= 0.2:
                        stage_completion = "문제정의 진행중"
                        stage_color = "🔵"
                    elif round_percentage <= 0.4:
                        stage_completion = "해결책 모색중"
                        stage_color = "🟡"
                    elif round_percentage <= 0.6:
                        stage_completion = "대안 비교중"
                        stage_color = "🟠"
                    elif round_percentage <= 0.8:
                        stage_completion = "합의 도출중"
                        stage_color = "🟣"
                    else:
                        stage_completion = "결론 정리중"
                        stage_color = "🔴"
                    
                    st.metric("🎯 진행 단계", f"{stage_color} {stage_completion}")
                
                # 완성도 종합 평가
                overall_completion = (round_percentage * 40) + (min(depth_score, 100) * 0.3) + (participation_rate * 0.3)
                
                if overall_completion >= 80:
                    completion_status = "🟢 우수한 토론 진행"
                elif overall_completion >= 60:
                    completion_status = "🟡 양호한 토론 진행"
                else:
                    completion_status = "🔴 더 깊이 있는 토론 필요"
                
                st.info(f"**종합 완성도**: {completion_status} ({overall_completion:.0f}점)")
                
                # 토론 개선 제안 및 종료 알림
                if round_percentage > 0.6 and overall_completion < 70:
                    st.warning("💡 **토론 개선 제안**: 더 구체적인 해결책과 실행 방안을 논의해보세요.")
                elif round_percentage > 0.8 and overall_completion < 80:
                    st.warning("💡 **마무리 제안**: 지금까지의 논의를 종합하여 명확한 결론을 도출해보세요.")
                
                # 회의 자동 종료 알림
                try:
                    if hasattr(meeting, '_is_conclusion_reached') and meeting._is_conclusion_reached():
                        st.success("🎉 **회의 완료**: 결론이 충분히 도출되어 회의가 자동으로 종료될 예정입니다.")
                    elif round_percentage > 0.9:
                        st.info("⏰ **회의 마무리**: 최대 라운드에 가까워지고 있습니다. 결론을 정리해주세요.")
                except AttributeError:
                    # 구버전 meeting 객체인 경우 간단한 대안 사용
                    if round_percentage > 0.9:
                        st.info("⏰ **회의 마무리**: 최대 라운드에 가까워지고 있습니다. 결론을 정리해주세요.")
            
            # 🎯 대화 체인 시스템 상태 (새로 추가)
            with st.expander("🎯 대화 체인 시스템 상태", expanded=False):
                if hasattr(meeting, 'conversation_chain'):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**📋 합의된 사항들:**")
                        if meeting.agreements:
                            for i, agreement in enumerate(meeting.agreements[-3:], 1):
                                st.write(f"{i}. {agreement}")
                        else:
                            st.write("아직 합의된 사항이 없습니다.")
                    
                    with col2:
                        st.write("**⚠️ 이견이 있는 사항들:**")
                        if meeting.disagreements:
                            for i, disagreement in enumerate(meeting.disagreements[-3:], 1):
                                st.write(f"{i}. {disagreement}")
                        else:
                            st.write("특별한 이견이 없습니다.")
                    
                    st.write(f"**🎯 현재 논의 초점:** {meeting.discussion_focus or '아직 설정되지 않음'}")
                    st.write(f"**📊 발언 순서:** {meeting.turn_counter}번째 발언")
                else:
                    st.info("대화 체인 시스템을 초기화하는 중입니다...")
            
            # 맥락 미리보기 (새로 추가)
            with st.expander("🔍 다음 발언 맥락 미리보기", expanded=False):
                next_speaker = meeting.get_next_speaker()
                if next_speaker:
                    st.write(f"**다음 발언자:** {next_speaker.name} ({next_speaker.role})")
                    
                    # 맥락 미리보기
                    comprehensive_context = get_comprehensive_meeting_context(meeting)
                    st.text_area(
                        "AI가 참고할 전체 맥락",
                        value=comprehensive_context,
                        height=200,
                        disabled=True,
                        help="이 맥락이 AI에게 전달되어 라운드별 연속성을 유지합니다"
                    )
                    
                    # 토큰 길이 정보
                    context_length = len(comprehensive_context)
                    st.caption(f"📊 맥락 길이: {context_length:,}자 (약 {context_length//4:,} 토큰)")
                else:
                    st.info("발언 가능한 참가자가 없습니다.")
            
            # 자동 진행 모드 상태 표시만 (실행은 메인 함수 끝에서)
            if meeting.auto_mode:
                st.success(f"🚀 자동 진행 모드 활성화 - {meeting.speaking_speed}초마다 자동 발언")
                st.info(f"🎯 목표: {meeting.max_rounds}라운드까지 자동 완료")
                
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
            
            # 추가 시스템 설정 정보
            col4, col5, col6, col7 = st.columns(4)
            with col4:
                st.metric("🕐 발언 간격", f"{meeting.speaking_speed}초")
            with col5:
                st.metric("⌨️ 타이핑 속도", f"{meeting.typing_speed}초/단어")
            with col6:
                saved_count = len(get_saved_meeting_records())
                st.metric("💾 저장된 회의록", f"{saved_count}개")
            with col7:
                current_ai_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                model_display = current_ai_model.split('-')[0].upper()  # claude 또는 GPT
                st.metric("🧠 AI 모델", model_display)
            
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
            
            # 🔧 새로운 회의 제어 상태 (반복 감지, 연장 정보)
            st.subheader("🛠️ 회의 제어 상태")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 원본 최대 라운드 vs 현재 최대 라운드 (2라운드 연장 정보)
                if hasattr(meeting, 'original_max_rounds') and hasattr(meeting, 'extension_granted'):
                    if meeting.extension_granted:
                        extension_count = meeting.max_rounds - meeting.original_max_rounds
                        st.warning(f"⚠️ **{extension_count}라운드 연장됨**\n원본: {meeting.original_max_rounds} → 현재: {meeting.max_rounds}")
                        
                        # 연장 라운드별 안내
                        if meeting.conversation_round + 1 == meeting.original_max_rounds + 1:
                            st.info("📋 **연장 1라운드**: 핵심 논점 정리")
                        elif meeting.conversation_round + 1 == meeting.original_max_rounds + 2:
                            st.error("🏁 **연장 2라운드**: 반드시 마무리!")
                    else:
                        st.success(f"✅ **원본 설정 유지**\n설정된 최대 라운드: {meeting.original_max_rounds}")
                else:
                    st.info(f"📊 최대 라운드: {meeting.max_rounds}")
            
            with col2:
                # 🎯 ChatGPT 분석 기반 개선사항 표시
                if hasattr(meeting, 'persona_stance') and meeting.persona_stance:
                    st.success("🎭 **페르소나 다양성 확보**")
                    stance_summary = {}
                    for persona_id, stance in meeting.persona_stance.items():
                        stance_summary[stance] = stance_summary.get(stance, 0) + 1
                    
                    stance_display = []
                    for stance, count in stance_summary.items():
                        stance_names = {'supportive': '협력적', 'cautious': '신중함', 
                                      'analytical': '분석적', 'creative': '창의적'}
                        stance_display.append(f"{stance_names.get(stance, stance)}: {count}명")
                    
                    st.caption(f"입장 분포: {', '.join(stance_display)}")
                else:
                    st.info("🎭 페르소나 입장 분배 중...")
                
                # 반복 대화 감지 상태 (기존 기능 유지)
                if hasattr(meeting, 'consecutive_repetitions'):
                    if meeting.consecutive_repetitions >= 2:
                        st.error(f"🔄 **반복 감지됨**\n연속 반복: {meeting.consecutive_repetitions}회")
                    elif meeting.consecutive_repetitions >= 1:
                        st.warning(f"⚠️ **반복 주의**\n연속 반복: {meeting.consecutive_repetitions}회")
                    else:
                        st.success("✅ **건전한 대화**\n반복 없음")
                else:
                    st.info("🔄 반복 감지 초기화 중...")
            
            with col3:
                # 자동 종료 조건 체크
                try:
                    if hasattr(meeting, '_is_conclusion_reached') and meeting._is_conclusion_reached():
                        st.success("🎯 **결론 도출 완료**\n회의 종료 가능")
                    elif hasattr(meeting, '_detect_repetitive_conversation') and meeting._detect_repetitive_conversation():
                        st.warning("🔄 **반복 대화 감지**\n조기 종료 예정")
                    else:
                        st.info("💬 **대화 진행 중**\n정상 상태")
                except:
                    st.info("🔍 **상태 분석 중**")
            
            # 라운드별 요약 현황 (새로 추가)
            st.subheader("🔄 라운드별 맥락 유지 현황")
            if meeting.conversation_round > 0:
                for round_num in range(1, meeting.conversation_round + 1):
                    with st.expander(f"📋 라운드 {round_num} 요약", expanded=False):
                        summary = meeting.generate_round_summary(round_num)
                        if summary:
                            st.text(summary)
                        else:
                            st.info("요약 생성 중...")
            else:
                st.info("아직 완료된 라운드가 없습니다.")
            
            # 핵심 인사이트 (새로 추가)
            key_insights = meeting.extract_key_insights()
            if key_insights:
                st.subheader("💡 핵심 인사이트")
                for insight in key_insights:
                    st.write(f"• {insight}")
            
            # 🏁 마무리 발언 품질 체크 (최종 라운드에서만)
            current_round = meeting.get_current_round_accurately()
            is_final_round = current_round >= meeting.max_rounds
            
            if is_final_round and meeting.messages:
                st.subheader("🏁 마무리 발언 품질 체크")
                
                # 최근 메시지들 중 마무리 발언 찾기
                final_statements = []
                for msg in reversed(meeting.messages[-10:]):  # 최근 10개 메시지에서
                    if not msg.is_moderator and not msg.is_human_input:
                        validation = validate_final_statement(msg.content, msg.persona_name)
                        if validation['has_gratitude'] or validation['has_personal_summary']:  # 마무리 시도한 발언
                            final_statements.append({
                                'persona': msg.persona_name,
                                'content': msg.content,
                                'validation': validation
                            })
                
                if final_statements:
                    for statement in final_statements:
                        with st.expander(f"{statement['persona']}의 마무리 발언 분석"):
                            validation = statement['validation']
                            
                            # 체크리스트 표시
                            st.write("**마무리 요소 체크리스트:**")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write("✅" if validation['has_personal_summary'] else "❌" + " 개인 발언 히스토리 요약")
                                st.write("✅" if validation['has_overall_conclusion'] else "❌" + " 회의 전체 결론")
                                st.write("✅" if validation['has_action_plan'] else "❌" + " 구체적 실행 방안")
                            
                            with col2:
                                st.write("✅" if validation['has_participant_connection'] else "❌" + " 다른 참가자와의 연결점")
                                st.write("✅" if validation['has_gratitude'] else "❌" + " 감사 인사")
                            
                            # 완성도 표시
                            completeness = sum([
                                validation['has_personal_summary'],
                                validation['has_overall_conclusion'],
                                validation['has_action_plan'],
                                validation['has_participant_connection'],
                                validation['has_gratitude']
                            ]) / 5 * 100
                            
                            if completeness == 100:
                                st.success(f"완벽한 마무리 발언! (완성도: {completeness:.0f}%)")
                            elif completeness >= 80:
                                st.warning(f"좋은 마무리 발언 (완성도: {completeness:.0f}%)")
                            elif completeness >= 60:
                                st.info(f"보통 수준의 마무리 발언 (완성도: {completeness:.0f}%)")
                            else:
                                st.error(f"불완전한 마무리 발언 (완성도: {completeness:.0f}%)")
                            
                            # 개선 제안
                            if not validation['is_complete']:
                                st.write("**개선 제안:**")
                                missing_elements = []
                                if not validation['has_personal_summary']:
                                    missing_elements.append("• '제가 이번 회의에서...'로 시작하는 개인 발언 요약")
                                if not validation['has_overall_conclusion']:
                                    missing_elements.append("• '전체 논의를 종합하면...'으로 시작하는 결론")
                                if not validation['has_action_plan']:
                                    missing_elements.append("• '구체적인 실행 방안으로는...'으로 시작하는 실행 계획")
                                if not validation['has_participant_connection']:
                                    missing_elements.append("• 다른 참가자의 의견에 대한 구체적 언급")
                                if not validation['has_gratitude']:
                                    missing_elements.append("• '감사합니다' 등의 마무리 인사")
                                
                                for element in missing_elements:
                                    st.write(element)
                else:
                    st.info("아직 완전한 마무리 발언이 나오지 않았습니다.")
            
            # 참고 자료 활용 현황 (새로 추가)
            if meeting.uploaded_files_content:
                st.subheader("📊 참고 자료 활용 현황")
                analysis = meeting.analyze_uploaded_files()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("📄 파일 크기", f"{analysis.get('total_length', 0):,}자")
                    st.metric("🔑 추출된 키워드", f"{len(analysis.get('keywords', []))}")
                
                with col2:
                    # 회의 주제와 키워드 매칭률 계산
                    if meeting.meeting_topic and analysis.get('keywords'):
                        topic_keywords = meeting.meeting_topic.replace(',', ' ').replace('.', ' ').split()
                        topic_keywords = [k.strip().lower() for k in topic_keywords if len(k.strip()) >= 2]
                        file_keywords = [k.lower() for k in analysis.get('keywords', [])]
                        
                        matching_keywords = [k for k in topic_keywords if k in file_keywords]
                        match_rate = len(matching_keywords) / len(topic_keywords) * 100 if topic_keywords else 0
                        
                        st.metric("🎯 주제 연관도", f"{match_rate:.1f}%")
                        st.metric("✅ 매칭 키워드", f"{len(matching_keywords)}개")
                
                # 파일 활용 품질 지표
                with st.expander("📈 파일 활용 분석", expanded=False):
                    if analysis.get('keywords'):
                        st.write("**🔑 상위 키워드:**")
                        st.write(", ".join(analysis['keywords'][:10]))
                    
                    if analysis.get('sections'):
                        st.write(f"**📁 섹션 구분:** {len(analysis['sections'])}개")
                        for i, section in enumerate(analysis['sections'][:3]):
                            st.write(f"  {i+1}. {section['title']}")
                    
                    # RAG 품질 평가
                    if meeting.meeting_topic:
                        relevant_content = meeting.get_relevant_file_content(topic_keywords)
                        if "관련 참고 자료" in relevant_content:
                            st.success("✅ RAG 시스템이 관련 내용을 성공적으로 추출했습니다")
                        else:
                            st.info("ℹ️ 전체 요약을 사용하여 참고 자료를 활용합니다")
            
            # 저장된 회의록 현황 (새로 추가)
            st.subheader("💾 저장된 회의록 현황")
            saved_records = get_saved_meeting_records()
            
            if saved_records:
                # 최근 5개 회의록만 표시
                recent_saved = saved_records[:5]
                
                for record in recent_saved:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.write(f"📋 **{record['title']}**")
                        with col2:
                            st.caption(f"📅 {record['date'].strftime('%Y-%m-%d %H:%M')}")
                        with col3:
                            if st.button("📖", key=f"quick_view_{record['meeting_id']}", help="빠른 보기"):
                                st.session_state.selected_meeting_id = record['meeting_id']
                
                if len(saved_records) > 5:
                    st.caption(f"... 외 {len(saved_records) - 5}개 더 (회의록 탭에서 전체 확인)")
            else:
                st.info("저장된 회의록이 없습니다.")
            
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
        
        # 서브탭 생성
        subtab1, subtab2, subtab3 = st.tabs(["📝 현재 회의록", "💾 회의록 저장", "📚 저장된 회의록"])
        
        with subtab1:
            st.subheader("📝 현재 회의 내용")
            
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
        
        with subtab2:
            st.subheader("💾 회의록 데이터베이스 저장")
            
            if meeting.messages:
                # 회의록 생성
                meeting_log = generate_meeting_log(meeting)
                
                # AI 요약 생성 버튼
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**📋 AI 회의록 요약 생성**")
                    st.caption("AI가 회의 내용을 분석하여 구조화된 요약을 생성합니다.")
                
                with col2:
                    if st.button("🤖 AI 요약 생성", type="secondary"):
                        with st.spinner("AI가 회의록을 요약하고 있습니다..."):
                            selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                            summary = generate_meeting_summary(meeting_log, selected_model)
                            st.session_state.meeting_summary = summary
                
                # 생성된 요약 표시
                if 'meeting_summary' in st.session_state:
                    st.subheader("📋 AI 생성 요약")
                    st.markdown(st.session_state.meeting_summary)
                    
                    # 저장 버튼
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("💾 회의록 저장", type="primary"):
                            if save_meeting_record(meeting, meeting_log, st.session_state.meeting_summary):
                                st.success("✅ 회의록이 성공적으로 저장되었습니다!")
                                # 요약 세션 상태 클리어
                                if 'meeting_summary' in st.session_state:
                                    del st.session_state.meeting_summary
                                st.rerun()
                            else:
                                st.error("❌ 회의록 저장에 실패했습니다.")
                    
                    with col2:
                        if st.button("🔄 요약 재생성"):
                            if 'meeting_summary' in st.session_state:
                                del st.session_state.meeting_summary
                            st.rerun()
                else:
                    st.info("💡 먼저 'AI 요약 생성' 버튼을 클릭하여 회의록 요약을 생성해주세요.")
                
                # 저장 정보 안내
                st.markdown("""
                ---
                ### 📊 저장될 정보
                - **회의 주제**: {topic}
                - **회의 일시**: {date}
                - **참가자**: {participants}
                - **전체 대화록**: 모든 발언 내용
                - **AI 요약**: 구조화된 회의 요약
                """.format(
                    topic=meeting.meeting_topic,
                    date=meeting.start_time.strftime('%Y-%m-%d %H:%M:%S') if meeting.start_time else "미정",
                    participants=", ".join([p.name for p in meeting.personas])
                ))
            else:
                st.info("ℹ️ 저장할 회의 내용이 없습니다.")
        
        with subtab3:
            st.subheader("📚 저장된 회의록 관리")
            
            # 저장된 회의록 목록 조회
            saved_records = get_saved_meeting_records()
            
            if saved_records:
                # 검색 기능
                search_term = st.text_input("🔍 회의록 검색", placeholder="회의 주제나 참가자명으로 검색...")
                
                # 검색 필터링
                if search_term:
                    filtered_records = [
                        record for record in saved_records 
                        if search_term.lower() in record['title'].lower() or 
                           search_term.lower() in record['participants'].lower()
                    ]
                else:
                    filtered_records = saved_records
                
                st.write(f"**📊 총 {len(filtered_records)}개의 회의록이 있습니다.**")
                
                # 회의록 목록 표시
                for record in filtered_records:
                    with st.expander(f"📅 {record['date'].strftime('%Y-%m-%d %H:%M')} - {record['title']}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**참가자**: {record['participants']}")
                            st.write(f"**저장일시**: {record['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        with col2:
                            if st.button("📖 상세보기", key=f"view_{record['meeting_id']}"):
                                st.session_state.selected_meeting_id = record['meeting_id']
                        
                        with col3:
                            if st.button("🗑️ 삭제", key=f"delete_{record['meeting_id']}", type="secondary"):
                                if delete_meeting_record(record['meeting_id']):
                                    st.success("✅ 회의록이 삭제되었습니다.")
                                    st.rerun()
                                else:
                                    st.error("❌ 삭제에 실패했습니다.")
                
                # 선택된 회의록 상세 보기
                if 'selected_meeting_id' in st.session_state:
                    st.markdown("---")
                    st.subheader("📖 회의록 상세 내용")
                    
                    detail = get_meeting_record_detail(st.session_state.selected_meeting_id)
                    if detail:
                        # 기본 정보
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**📋 회의 주제**: {detail['title']}")
                            st.write(f"**📅 회의 일시**: {detail['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                        with col2:
                            st.write(f"**👥 참가자**: {detail['participants']}")
                            st.write(f"**💾 저장일시**: {detail['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # 탭으로 구분된 내용
                        detail_tab1, detail_tab2 = st.tabs(["📋 AI 요약", "📝 전체 대화록"])
                        
                        with detail_tab1:
                            if detail['summary']:
                                st.markdown(detail['summary'])
                            else:
                                st.info("요약이 없습니다.")
                        
                        with detail_tab2:
                            if detail['full_text']:
                                st.markdown(detail['full_text'])
                            else:
                                st.info("대화록이 없습니다.")
                        
                        # 다운로드 버튼
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                label="📥 요약 다운로드",
                                data=detail['summary'] or "요약 없음",
                                file_name=f"meeting_summary_{detail['meeting_id']}.md",
                                mime="text/markdown"
                            )
                        with col2:
                            st.download_button(
                                label="📥 전체 대화록 다운로드",
                                data=detail['full_text'] or "대화록 없음",
                                file_name=f"meeting_full_{detail['meeting_id']}.md",
                                mime="text/markdown"
                            )
                        with col3:
                            if st.button("❌ 상세보기 닫기"):
                                if 'selected_meeting_id' in st.session_state:
                                    del st.session_state.selected_meeting_id
                                st.rerun()
                    else:
                        st.error("회의록을 찾을 수 없습니다.")
            else:
                st.info("📝 저장된 회의록이 없습니다. 회의를 진행한 후 '회의록 저장' 탭에서 저장해보세요.")

    # 🚀 강화된 자동 모드 실행 로직 (사회자 분석 기반 마무리)
    if meeting.auto_mode and meeting.is_active:
        if meeting.should_continue():
            if meeting.is_time_to_speak():
                # 🎯 사회자 차례일 때 참가자 발언 분석 후 마무리 결정
                next_speaker = meeting.get_next_speaker()
                current_round = meeting.get_current_round_accurately()
                
                # 사회자 차례이고 8라운드 이후인 경우 발언 분석 실행
                if (next_speaker and next_speaker.is_moderator and 
                    current_round >= 8 and 
                    not getattr(meeting, 'final_analysis_done', False)):
                    
                    # 🎯 참가자 발언 분석 실행
                    analysis_result = meeting.analyze_participant_statements_for_closure()
                    selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                    
                    # 🎯 분석 결과에 기반한 사회자 메시지 생성
                    informed_message = meeting.generate_informed_closure_message(analysis_result, selected_model)
                    meeting.add_message(next_speaker.id, informed_message)
                    
                    # 🎯 마무리 가능 여부에 따른 처리
                    if analysis_result['can_conclude']:
                        # 완전한 마무리 - 회의 종료
                        meeting.is_active = False
                        meeting.auto_mode = False
                        meeting.final_analysis_done = True
                        
                        st.success("🎉 **참가자 발언 분석 완료** - 모든 조건이 충족되어 회의를 마무리합니다!")
                        st.info(f"📊 분석 결과: {analysis_result['high_quality_conclusions']}/{analysis_result['total_participants']}명이 완전한 마무리 발언 완료")
                        st.balloons()
                    else:
                        # 마무리 불가 - 연장 진행
                        if not getattr(meeting, 'extension_granted', False):
                            meeting.extension_granted = True
                            meeting.max_rounds += 2  # 2라운드 연장
                            st.warning("⚠️ **발언 분석 결과** - 마무리가 불완전하여 2라운드 연장합니다.")
                            st.info(f"📋 연장 사유: {', '.join(analysis_result.get('reasons_for_continuation', []))}")
                        
                        meeting.advance_speaker()  # 사회자 발언 후 다음 발언자로
                    
                    st.rerun()
                    return
                
                # 일반적인 대화 실행
                success = run_conversation_round(meeting)
                if success:
                    # 새로운 메시지가 추가되었으므로 즉시 새로고침
                    st.rerun()
                else:
                    # 회의 자동 종료
                    meeting.is_active = False
                    meeting.auto_mode = False
                    moderator = meeting.get_moderator()
                    if moderator and not getattr(meeting, 'final_analysis_done', False):
                        closing_message = "자동 모드로 진행된 회의를 마치겠습니다. 모든 분들의 의견에 감사드립니다."
                        meeting.add_message(moderator.id, closing_message)
                    st.success("✅ 자동 모드 회의가 완료되었습니다.")
                    st.rerun()
            else:
                # 시간이 안 되었으면 0.5초 후 다시 체크 (더 빠른 반응)
                time.sleep(0.5)
                st.rerun()
        else:
            # 🎯 마지막 체크 - 참가자 발언 분석 기반 마무리
            if not getattr(meeting, 'final_analysis_done', False):
                analysis_result = meeting.analyze_participant_statements_for_closure()
                moderator = meeting.get_moderator()
                
                if moderator:
                    selected_model = st.session_state.get('selected_ai_model', 'gpt-4o-mini')
                    final_informed_message = meeting.generate_informed_closure_message(analysis_result, selected_model)
                    meeting.add_message(moderator.id, final_informed_message)
                    meeting.final_analysis_done = True
                    
                    if analysis_result['can_conclude']:
                        st.success("🎉 **최종 분석 완료** - 참가자들의 발언이 충분히 완료되어 회의를 마무리합니다!")
                    else:
                        st.warning("⚠️ **최종 분석 결과** - 일부 마무리가 불완전하지만 최대 라운드에 도달하여 회의를 종료합니다.")
                    
                    st.info(f"📊 최종 품질: {analysis_result['overall_quality_ratio']:.1%} ({analysis_result['high_quality_conclusions']}/{analysis_result['total_participants']}명 완료)")
            
            meeting.is_active = False
            meeting.auto_mode = False
            st.success(f"🏁 {meeting.max_rounds}라운드 회의가 완료되었습니다!")
            st.balloons()  # 축하 애니메이션
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