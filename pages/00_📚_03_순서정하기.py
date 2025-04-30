import streamlit as st
import random
import time
import pandas as pd
import numpy as np
from datetime import timedelta, datetime
import base64
from openai import OpenAI
import os
from dotenv import load_dotenv
import mysql.connector

# .env 파일 로드
load_dotenv()

# 페이지 설정을 가장 먼저 실행
st.set_page_config(
    page_title="🎯 독서토론 순서정하기",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 초기 알림을 위한 상태 관리
if 'initial_notice_shown' not in st.session_state:
    st.session_state.initial_notice_shown = False

# 앱 시작 시 알림 표시 (한 번만)
if not st.session_state.initial_notice_shown:
    st.markdown("""
    <style>
    @keyframes slideIn {
        0% { transform: translateY(-20px); opacity: 0; }
        100% { transform: translateY(0); opacity: 1; }
    }
    
    .notice-container {
        background: linear-gradient(145deg, #0066cc, #0052a3);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 20px auto;
        max-width: 600px;
        animation: slideIn 0.5s ease-out;
    }
    
    .notice-icon {
        font-size: 48px;
        margin-bottom: 10px;
        display: inline-block;
    }
    
    .notice-text {
        font-size: 24px;
        font-weight: bold;
        margin: 10px 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .notice-subtext {
        font-size: 16px;
        opacity: 0.9;
        margin-top: 10px;
    }
    
    .highlight {
        background: rgba(255,255,255,0.2);
        padding: 5px 10px;
        border-radius: 5px;
        display: inline-block;
        margin: 5px 0;
    }
    </style>
    
    <div class="notice-container">
        <div class="notice-icon">🎙️</div>
        <div class="notice-text">옵시디언 녹음기능을 활성화해 주세요!</div>
        <div class="notice-subtext">
            <div class="highlight">토론 내용 기록을 위해 꼭 필요합니다</div>
            <div class="highlight">시작 전 반드시 확인해 주세요</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.session_state.initial_notice_shown = True

# 전체 페이지 스타일 설정
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .character-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .ability-text {
        color: #1f1f1f;
        font-size: 0.9em;
    }
    .character-name {
        color: #0066cc;
        font-weight: bold;
    }
    .special-effect {
        color: #ff4b4b;
        font-weight: bold;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #1f1f1f !important;
    }
    .timer-display {
        color: #1f1f1f;
        font-size: 4rem;
        font-weight: bold;
        text-align: center;
    }
    .timer-status {
        font-size: 1.2rem;
        text-align: center;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    @keyframes glow {
        0% { box-shadow: 0 0 5px rgba(0,102,204,0.5); }
        50% { box-shadow: 0 0 20px rgba(0,102,204,0.8); }
        100% { box-shadow: 0 0 5px rgba(0,102,204,0.5); }
    }
    @keyframes slideIn {
        0% { transform: translateY(-20px); opacity: 0; }
        100% { transform: translateY(0); opacity: 1; }
    }
    .notice-container {
        background: linear-gradient(145deg, #0066cc, #0052a3);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 20px auto;
        max-width: 600px;
        animation: slideIn 0.5s ease-out, pulse 2s infinite, glow 2s infinite;
    }
    .notice-icon {
        font-size: 48px;
        margin-bottom: 10px;
        display: inline-block;
        animation: pulse 1s infinite;
    }
    .notice-text {
        font-size: 24px;
        font-weight: bold;
        margin: 10px 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .notice-subtext {
        font-size: 16px;
        opacity: 0.9;
        margin-top: 10px;
    }
    .highlight {
        background: rgba(255,255,255,0.2);
        padding: 5px 10px;
        border-radius: 5px;
        display: inline-block;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# 알람 소리 재생을 위한 JavaScript 함수 수정
def get_alarm_js():
    return """
    <script>
    // 오디오 컨텍스트 초기화 함수
    let audioContext = null;
    let isAudioInitialized = false;

    async function initAudioContext() {
        if (!isAudioInitialized) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                await audioContext.resume();
                isAudioInitialized = true;
                console.log('오디오 컨텍스트 초기화 성공');
            } catch (e) {
                console.error('오디오 컨텍스트 초기화 실패:', e);
            }
        }
    }

    // 비프음 재생 함수
    async function playBeep() {
        await initAudioContext();
        if (!audioContext) return;

        try {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.5);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (e) {
            console.error('비프음 재생 실패:', e);
        }
    }

    // 전역 스코프에 함수 등록
    window.playBeep = playBeep;
    </script>
    """

# 토스트 알림 표시를 위한 JavaScript 함수
def get_toast_notification_js():
    return """
    <style>
    .toast {
        visibility: hidden;
        min-width: 250px;
        margin-left: -125px;
        background-color: #ff4b4b;
        color: white;
        text-align: center;
        border-radius: 10px;
        padding: 16px;
        position: fixed;
        z-index: 1000;
        left: 50%;
        bottom: 30px;
        font-size: 18px;
        font-weight: bold;
        box-shadow: 0px 0px 10px rgba(0,0,0,0.5);
        transition: visibility 0.5s, opacity 0.5s;
        opacity: 0;
    }
    .toast.show {
        visibility: visible;
        opacity: 1;
    }
    </style>
    <div id="toast" class="toast"></div>
    <script>
    function showToast(message) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.className = "toast show";
        setTimeout(() => {
            toast.className = toast.className.replace("show", "");
        }, 3000);
    }
    window.showToast = showToast;
    </script>
    """

# TTS 기능을 위한 JavaScript 함수 추가
def get_tts_js():
    return """
    <script>
    function speakText(text) {
        // TTS 기능 초기화
        const speech = new SpeechSynthesisUtterance();
        speech.lang = 'ko-KR';  // 한국어 설정
        speech.text = text;
        speech.volume = 1;  // 볼륨 설정 (0.0 ~ 1.0)
        speech.rate = 1;    // 속도 설정 (0.1 ~ 10)
        speech.pitch = 1;   // 음높이 설정 (0 ~ 2)
        
        // TTS 실행
        window.speechSynthesis.speak(speech);
    }
    
    // 전역 스코프에 함수 등록
    window.speakText = speakText;
    </script>
    """

# 참여자별 캐릭터 설정
CHARACTERS = {
    "현철님": "🧙‍♂️ 지혜의 현자",
    "창환님": "🚀 미래의 선구자",
    "성범님": "🎯 통찰의 대가",
    "성현님": "🌟 창의의 연금술사",
    "상현님": "🎭 질문의 예술가",
    "성일님": "💡 혁신의 아이콘"
}

# 특별한 능력치
ABILITIES = {
    "현철님": ["통찰력 MAX", "지혜 +100", "경험치 +500"],
    "창환님": ["창의력 MAX", "혁신 +100", "선구안 +500"],
    "성범님": ["분석력 MAX", "전략 +100", "실행력 +500"],
    "성현님": ["창조력 MAX", "발상 +100", "기획력 +500"],
    "상현님": ["질문력 MAX", "탐구 +100", "호기심 +500"],
    "성일님": ["혁신력 MAX", "창의 +100", "도전정신 +500"]
}

# 요일별 테마 설정
THEMES = {
    "월요일": {
        "name": "🎯 캐릭터 룰렛",
        "description": "각자의 캐릭터로 진행하는 클래식한 룰렛 방식",
        "style": "classic"
    },
    "화요일": {
        "name": "🎲 주사위 배틀",
        "description": "각자 주사위를 굴려 높은 숫자가 나온 순서대로 진행",
        "style": "dice"
    },
    "수요일": {
        "name": "🃏 카드 드로우",
        "description": "각자 카드를 뽑아 카드 숫자 순서대로 진행",
        "style": "cards"
    },
    "목요일": {
        "name": "🎮 RPG 퀘스트",
        "description": "RPG 스타일의 미니게임으로 순서 결정",
        "style": "rpg"
    },
    "금요일": {
        "name": "🎪 랜덤 미션",
        "description": "재미있는 미션을 수행하여 순서 결정",
        "style": "mission"
    }
}

# 주사위 배틀용 효과
DICE_EFFECTS = {
    6: "🌟 크리티컬 히트! 2배 데미지",
    5: "✨ 강화 주사위! +2 보너스",
    4: "💫 럭키 포인트! +1 보너스",
    3: "🎯 안정적인 굴림!",
    2: "😅 아쉬운 굴림...",
    1: "💔 크리티컬 미스..."
}

# 카드 드로우용 카드 설정
CARDS = {
    "A": "👑 에이스의 기품",
    "K": "👑 왕의 카리스마",
    "Q": "👑 여왕의 우아함",
    "J": "👑 기사의 용맹",
    "10": "🌟 완벽한 균형",
    "9": "✨ 높은 에너지",
    "8": "💫 안정적인 힘",
    "7": "🎯 행운의 숫자",
    "6": "💪 도전적인 정신",
    "5": "🎭 변화의 기운",
    "4": "🎪 신비한 힘",
    "3": "🎲 기회의 숫자",
    "2": "🃏 반전의 기회"
}

# RPG 퀘스트용 스탯
RPG_STATS = {
    "현철님": {"지혜": 90, "통찰력": 95, "경험": 88},
    "창환님": {"창의력": 92, "혁신": 94, "선구안": 89},
    "성범님": {"분석력": 93, "전략": 91, "실행력": 90},
    "성현님": {"창조력": 91, "발상": 93, "기획력": 92},
    "상현님": {"질문력": 94, "탐구": 92, "호기심": 91},
    "성일님": {"혁신력": 95, "창의": 93, "도전정신": 94}
}

# 랜덤 미션 목록
MISSIONS = [
    "📚 가장 최근에 읽은 책 제목 말하기",
    "💡 이번 주 최고의 아이디어 공유하기",
    "🎯 한 문장으로 이번 주 목표 설명하기",
    "🌟 가장 인상 깊었던 책 구절 암기하기",
    "🎭 책 속 한 장면 연기하기"
]

# 타이머 관련 session_state 초기화 함수 추가
def init_timer_state():
    """타이머 관련 상태 초기화"""
    if 'timer_started' not in st.session_state:
        st.session_state.timer_started = False
        st.session_state.start_time = None
        st.session_state.duration = timedelta(minutes=20)
        st.session_state.timer_finished = False
        st.session_state.alarm_enabled = True
        st.session_state.toast_enabled = True

def format_time(td):
    """타임델타를 MM:SS 형식으로 변환"""
    total_seconds = int(td.total_seconds())
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"

def get_timer_status(remaining):
    """남은 시간에 따른 상태 메시지와 색상 반환"""
    seconds = remaining.total_seconds()
    if seconds <= 60:
        return "⚠️ 1분 남았습니다!", "#ff4b4b"
    elif seconds <= 300:
        return "🕒 5분 미만 남았습니다", "#ff9900"
    return "토론이 진행 중입니다", "#666666"

def generate_roulette_animation():
    """룰렛 애니메이션 생성"""
    placeholder = st.empty()
    participants = list(CHARACTERS.keys())
    for _ in range(20):
        random.shuffle(participants)
        display_text = "\n".join([f"### {CHARACTERS[p]}" for p in participants[:5]])
        placeholder.markdown(display_text)
        time.sleep(0.1)
    return placeholder

def get_special_effect():
    """특별 효과 생성"""
    effects = [
        "🌈 독서력 2배 증가!",
        "💫 통찰력 레벨 UP!",
        "🎭 토론 스킬 강화!",
        "🎯 집중력 MAX!",
        "🚀 아이디어 폭발!",
        "🧠 브레인스토밍 파워!"
    ]
    return random.choice(effects)

def generate_dice_battle():
    """주사위 배틀 진행"""
    results = {}
    for person in CHARACTERS.keys():
        dice = random.randint(1, 6)
        bonus = random.randint(0, 2)
        total = dice + bonus
        results[person] = {
            "dice": dice,
            "bonus": bonus,
            "total": total,
            "effect": DICE_EFFECTS[dice]
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['total'], random.random())))

def draw_cards():
    """카드 드로우 진행"""
    card_values = list(CARDS.keys())
    results = {}
    drawn_cards = random.sample(card_values, len(CHARACTERS))
    for person, card in zip(CHARACTERS.keys(), drawn_cards):
        results[person] = {
            "card": card,
            "effect": CARDS[card]
        }
    return dict(sorted(results.items(), key=lambda x: card_values.index(x[1]['card'])))

def rpg_quest():
    """RPG 퀘스트 진행"""
    results = {}
    quest_type = random.choice(list(next(iter(RPG_STATS.values())).keys()))
    for person, stats in RPG_STATS.items():
        base_score = stats[quest_type]
        roll = random.randint(1, 20)
        total = base_score + roll
        results[person] = {
            "stat": quest_type,
            "base": base_score,
            "roll": roll,
            "total": total
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['total'], random.random())))

def random_mission():
    """랜덤 미션 수행"""
    results = {}
    for person in CHARACTERS.keys():
        mission = random.choice(MISSIONS)
        score = random.randint(70, 100)
        results[person] = {
            "mission": mission,
            "score": score,
            "feedback": get_mission_feedback(score)
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['score'], random.random())))

def get_mission_feedback(score):
    """미션 점수에 따른 피드백 생성"""
    if score >= 90:
        return "🌟 완벽한 수행!"
    elif score >= 80:
        return "✨ 훌륭한 수행!"
    elif score >= 70:
        return "💫 좋은 시도!"
    else:
        return "🎯 다음을 기대해요!"

# 더 강력한 시각적 알림 효과 추가
st.markdown("""
<style>
@keyframes blink-intense {
    0% { transform: scale(1); background: linear-gradient(145deg, #ff4b4b, #ff6b6b); }
    50% { transform: scale(1.05); background: linear-gradient(145deg, #ff6b6b, #ff8b8b); }
    100% { transform: scale(1); background: linear-gradient(145deg, #ff4b4b, #ff6b6b); }
}

.intense-warning {
    background: linear-gradient(145deg, #ff4b4b, #ff6b6b);
    color: white;
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    font-size: 28px;
    font-weight: bold;
    margin: 20px 0;
    animation: blink-intense 0.7s infinite;
    box-shadow: 0 4px 15px rgba(255, 75, 75, 0.5);
}

/* 전체 화면 오버레이 */
.fullscreen-alert {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(255, 75, 75, 0.95);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { background: rgba(255, 75, 75, 0.95); }
    50% { background: rgba(255, 75, 75, 0.7); }
    100% { background: rgba(255, 75, 75, 0.95); }
}

/* 알림 메시지 컨테이너 */
.alert-content {
    background: white;
    padding: 2rem;
    border-radius: 20px;
    text-align: center;
    box-shadow: 0 0 30px rgba(0,0,0,0.3);
    animation: bounce 1s infinite;
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-20px); }
}

/* 큰 시계 이모지 */
.large-emoji {
    font-size: 5rem;
    margin-bottom: 1rem;
}

/* 알림 텍스트 */
.alert-text {
    font-size: 2rem;
    font-weight: bold;
    color: #ff4b4b;
    margin: 1rem 0;
}

/* 서브 텍스트 */
.alert-subtext {
    font-size: 1.2rem;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

def get_audio_js():
    return """
    <script>
    let audioContext = null;
    let isAudioInitialized = false;

    // 오디오 컨텍스트 초기화 함수
    async function initAudioContext() {
        if (!isAudioInitialized) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                await audioContext.resume();
                isAudioInitialized = true;
                console.log('오디오 컨텍스트 초기화 성공');
            } catch (e) {
                console.error('오디오 컨텍스트 초기화 실패:', e);
            }
        }
    }

    // 비프음 재생 함수
    async function playBeep() {
        await initAudioContext();
        if (!audioContext) return;

        try {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.5);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (e) {
            console.error('비프음 재생 실패:', e);
        }
    }

    // 전역 스코프에 함수 등록
    window.playBeep = playBeep;
    </script>
    """

# 알람 음성 생성 함수
def generate_alarm_audio():
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if not os.getenv('OPENAI_API_KEY'):
            st.error("OpenAI API 키가 설정되지 않았습니다.")
            return None
            
        # 알람 메시지 생성 (더 자연스러운 문장으로)
        alarm_text = """
        토론 시간이 종료되었습니다.
        토론을 마무리해 주세요.
        토론을 마무리해 주세요.
        토론을 마무리해 주세요.
        """
        
        # 음성 생성 (한국어 음성으로 설정)
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",  # 더 자연스러운 목소리 선택
            input=alarm_text,
            speed=0.9  # 약간 천천히 말하도록 설정
        )
        
        # 음성 데이터를 base64로 인코딩
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        return audio_base64
        
    except Exception as e:
        st.error(f"알람 음성 생성 중 오류 발생: {str(e)}")
        return None

# DB 설정
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

def get_mission_vision_values():
    """미션/비전/가치/원칙 데이터를 모두 가져옴"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        all_items = []
        
        # 미션 & 비전
        cursor.execute("SELECT mission_text, vision_text FROM mission_vision LIMIT 1")
        mission_vision = cursor.fetchone()
        if mission_vision:
            all_items.extend([
                f"🎯 미션: {mission_vision['mission_text']}",
                f"🌟 비전: {mission_vision['vision_text']}"
            ])
        
        # 핵심 가치
        cursor.execute("SELECT value_title, value_description FROM core_values ORDER BY sort_order")
        values = cursor.fetchall()
        all_items.extend([f"💎 핵심가치 - {value['value_title']}: {value['value_description']}" for value in values])
        
        # 핵심 목표
        cursor.execute("SELECT category, objective_text FROM key_objectives ORDER BY category, sort_order")
        objectives = cursor.fetchall()
        all_items.extend([f"🎯 {obj['category']}: {obj['objective_text']}" for obj in objectives])
        
        # 원칙 데이터
        # 서문
        cursor.execute("SELECT intro_text FROM introduction LIMIT 1")
        intro = cursor.fetchone()
        if intro:
            all_items.append(f"📜 서문: {intro['intro_text']}")
        
        # 요약
        cursor.execute("SELECT summary_title, summary_text FROM summary")
        summaries = cursor.fetchall()
        all_items.extend([f"📋 {summary['summary_title']}: {summary['summary_text']}" for summary in summaries])
        
        # 원칙
        cursor.execute("""
            SELECT 
                p.principle_number,
                p.principle_title,
                sp.sub_principle_number,
                sp.sub_principle_title,
                ai.action_item_text
            FROM principles p
            LEFT JOIN sub_principles sp ON p.principle_id = sp.principle_id
            LEFT JOIN action_items ai ON sp.sub_principle_id = ai.sub_principle_id
            ORDER BY p.principle_number, sp.sub_principle_number
        """)
        principles = cursor.fetchall()
        
        current_principle = None
        for p in principles:
            if current_principle != p['principle_number']:
                current_principle = p['principle_number']
                all_items.append(f"📌 원칙 {p['principle_number']}: {p['principle_title']}")
            if p['sub_principle_title']:
                all_items.append(f"   └ {p['sub_principle_number']} {p['sub_principle_title']}")
            if p['action_item_text']:
                all_items.append(f"      ▪ {p['action_item_text']}")
        
        cursor.close()
        conn.close()
        
        return all_items
    except Exception as e:
        st.error(f"데이터 조회 중 오류 발생: {str(e)}")
        return []

def init_values_state():
    """명언 표시를 위한 세션 상태 초기화"""
    if 'values_state' not in st.session_state:
        st.session_state.values_state = {
            'all_items': [
                "Success is not the key to happiness. Happiness is the key to success.\n성공이 행복의 열쇠가 아니라, 행복이 성공의 열쇠다.",
                "Opportunities don't happen. You create them. – Chris Grosser\n기회는 저절로 생기는 것이 아니다. 당신이 만들어내는 것이다. – 크리스 그로서",
                "Don't be afraid to give up the good to go for the great. – John D. Rockefeller\n더 좋은 것을 얻기 위해 좋은 것을 포기하는 것을 두려워하지 마라. – 존 D. 록펠러",
                "Success usually comes to those who are too busy to be looking for it. – Henry David Thoreau\n성공은 대개 그것을 찾느라 바쁜 사람들에게 찾아온다. – 헨리 데이비드 소로우",
                "If you really look closely, most overnight successes took a long time. – Steve Jobs\n자세히 보면, 대부분의 갑작스러운 성공은 오랜 시간이 걸렸다. – 스티브 잡스",
                "The way to get started is to quit talking and begin doing. – Walt Disney\n시작하는 방법은 말하는 것을 멈추고 행동하는 것이다. – 월트 디즈니",
                "Don't let the fear of losing be greater than the excitement of winning. – Robert Kiyosaki\n패배에 대한 두려움이 승리의 기쁨보다 커지게 하지 마라. – 로버트 기요사키",
                "If you are not willing to risk the usual, you will have to settle for the ordinary. – Jim Rohn\n일반적인 위험을 감수하지 않으면 평범한 것에 만족해야 한다. – 짐 론",
                "The only place where success comes before work is in the dictionary. – Vidal Sassoon\n성공이 노력보다 먼저 오는 곳은 사전뿐이다. – 비달 사순",
                "The function of leadership is to produce more leaders, not more followers. – Ralph Nader\n리더십의 기능은 더 많은 추종자가 아닌 더 많은 리더를 만드는 것이다. – 랄프 네이더",
                "Innovation distinguishes between a leader and a follower. – Steve Jobs\n혁신은 리더와 추종자를 구별한다. – 스티브 잡스",
                "Your time is limited, so don't waste it living someone else's life. – Steve Jobs\n당신의 시간은 한정되어 있으니, 다른 사람의 삶을 사느라 낭비하지 마라. – 스티브 잡스",
                "The best way to predict the future is to create it. – Peter Drucker\n미래를 예측하는 가장 좋은 방법은 그것을 창조하는 것이다. – 피터 드러커",
                "Do not be embarrassed by your failures, learn from them and start again. – Richard Branson\n실패를 부끄러워하지 말고, 그로부터 배우고 다시 시작하라. – 리처드 브랜슨",
                "Success is not in what you have, but who you are. – Bo Bennett\n성공은 당신이 가진 것에 있지 않고, 당신이 누구인가에 있다. – 보 베넷",
                "The only limit to our realization of tomorrow is our doubts of today. – Franklin D. Roosevelt\n내일의 실현에 대한 유일한 한계는 오늘의 의심이다. – 프랭클린 D. 루스벨트",
                "The road to success and the road to failure are almost exactly the same. – Colin R. Davis\n성공으로 가는 길과 실패로 가는 길은 거의 똑같다. – 콜린 R. 데이비스",
                "Success is not just about making money. It's about making a difference. – Unknown\n성공은 돈을 버는 것만이 아니라 변화를 만드는 것이다. – 작자 미상",
                "Fall seven times and stand up eight. – Japanese Proverb\n일곱 번 넘어져도 여덟 번째 일어나라. – 일본 속담",
                "The secret of success is to do the common thing uncommonly well. – John D. Rockefeller Jr.\n성공의 비밀은 평범한 일을 비범하게 잘하는 것이다. – 존 D. 록펠러 주니어",
                "I find that the harder I work, the more luck I seem to have. – Thomas Jefferson\n열심히 일할숝록 운이 더 좋아지는 것 같다. – 토머스 제퍼슨",
                "Success is not how high you have climbed, but how you make a positive difference to the world. – Roy T. Bennett\n성공은 얼마나 높이 올라갔느냐가 아니라, 세상에 얼마나 긍정적인 변화를 가져왔느냐에 달려 있다. – 로이 T. 베넷",
                "The only way to do great work is to love what you do. – Steve Jobs\n훌륭한 일을 하는 유일한 방법은 당신이 하는 일을 사랑하는 것이다. – 스티브 잡스"
            ],
            'current_index': 0,
            'repeat_count': 0  # 현재 명언의 반복 횟수를 추적
        }

def display_current_value():
    """현재 명언 표시"""
    if not st.session_state.values_state['all_items']:
        return
    
    current_item = st.session_state.values_state['all_items'][st.session_state.values_state['current_index']]
    total_items = len(st.session_state.values_state['all_items'])
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(145deg, #ffffff, #f0f0f0);
        padding: 20px;
        border-radius: 10px;
        box-shadow: 3px 3px 6px #d9d9d9, -3px -3px 6px #ffffff;
        margin: 10px 0;
        font-size: 24px;
        line-height: 1.5;
        color: #0066cc;  /* 진한 파란색으로 변경 */
        font-weight: 500;  /* 글자 두께 약간 증가 */
        text-align: center;
        white-space: pre-line;
    ">
        {current_item}
        <div style="font-size: 14px; color: #666; margin-top: 15px;">
            명언 {st.session_state.values_state['current_index'] + 1} / {total_items}
            (반복 {st.session_state.values_state['repeat_count'] + 1} / 10)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 반복 횟수 증가
    st.session_state.values_state['repeat_count'] += 1
    
    # 10번 반복 후 다음 명언으로
    if st.session_state.values_state['repeat_count'] >= 10:
        st.session_state.values_state['current_index'] = (st.session_state.values_state['current_index'] + 1) % total_items
        st.session_state.values_state['repeat_count'] = 0  # 반복 횟수 리셋

def generate_obsidian_notification_js():
    return """
    <div class="obsidian-alert" style="display: none;">
        <div class="alert-content">
            <div class="large-emoji">🎙️</div>
            <div class="alert-text">옵시디언 녹음기능을 활성화해 주세요!</div>
        </div>
    </div>
    <script>
    function showObsidianNotification() {
        const alert = document.querySelector('.obsidian-alert');
        alert.style.display = 'flex';
        setTimeout(() => {
            alert.style.display = 'none';
        }, 3000);
    }
    </script>
    <style>
    .obsidian-alert {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 102, 204, 0.95);
        display: none;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        animation: pulse 2s;
    }
    
    .obsidian-alert .alert-content {
        background: white;
        padding: 2rem;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 0 30px rgba(0,0,0,0.3);
        animation: bounce 1s;
    }
    
    .obsidian-alert .large-emoji {
        font-size: 5rem;
        margin-bottom: 1rem;
    }
    
    .obsidian-alert .alert-text {
        font-size: 2rem;
        font-weight: bold;
        color: #0066cc;
        margin: 1rem 0;
    }

    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-20px); }
    }
    </style>
    """

def main():
    st.markdown('<h1 style="color: black;">🎯 독서토론 순서 정하기</h1>', unsafe_allow_html=True)
    st.markdown('<h3 style="color: black;">🎲 오늘의 토론 멤버를 확인하세요!</h3>', unsafe_allow_html=True)

    # JavaScript 코드 삽입 (필요한 경우에만)
    if 'js_loaded' not in st.session_state:
        st.markdown(get_alarm_js(), unsafe_allow_html=True)
        st.markdown(get_toast_notification_js(), unsafe_allow_html=True)
        st.session_state.js_loaded = True

    # 캐릭터 소개
    cols = st.columns(len(CHARACTERS))
    for i, (person, character) in enumerate(CHARACTERS.items()):
        with cols[i]:
            st.markdown(f"""
            <div class="character-card">
                <h3>{character}</h3>
                <p class="character-name">{person}</p>
            </div>
            """, unsafe_allow_html=True)

    # 명언 표시 초기화 및 표시
    init_values_state()
    st.markdown('<h3 style="color: black;">✨ 오늘의 명언</h3>', unsafe_allow_html=True)
    display_current_value()

    st.markdown("---")

    # 순서 생성 및 타이머 관련 상태 초기화
    if 'order_generated' not in st.session_state:
        st.session_state.order_generated = False
        st.session_state.final_order = []
        st.session_state.effects = {}

    if not st.session_state.order_generated:
        if st.button("🎯 발표 순서 정하기!", use_container_width=True):
            with st.spinner("순서를 정하는 중..."):
                placeholder = generate_roulette_animation()
                participants = list(CHARACTERS.keys())
                random.shuffle(participants)
                st.session_state.final_order = participants
                st.session_state.effects = {person: get_special_effect() for person in participants}
                st.session_state.order_generated = True
                st.balloons()
                st.rerun()

    if st.session_state.order_generated:
        # 2단 레이아웃 생성 - 간격 조정
        col1, col2 = st.columns([1, 1], gap="large")
        
        with col1:
            st.markdown('<h2 style="color: black; font-size: 24px; margin-bottom: 20px;">🎉 발표 순서</h2>', unsafe_allow_html=True)
            # 순서 카드를 더 작고 조밀하게 표시
            for i, person in enumerate(st.session_state.final_order, 1):
                st.markdown(f"""
                <div style="background: linear-gradient(145deg, #ffffff, #f0f0f0);
                           padding: 10px;
                           border-radius: 8px;
                           margin: 5px 0;
                           box-shadow: 3px 3px 6px #d9d9d9, -3px -3px 6px #ffffff;">
                    <div style="color: #0066cc; margin: 0; font-size: 16px; display: flex; align-items: center;">
                        <span style="font-weight: bold; min-width: 24px;">{i}.</span>
                        <span style="margin-left: 8px;">{person}</span>
                        <span style="margin-left: 8px; opacity: 0.8;">{CHARACTERS[person]}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown('<h2 style="color: black; font-size: 24px; margin-bottom: 20px;">⏱️ 토론 타이머</h2>', unsafe_allow_html=True)
            init_timer_state()
            
            # 알람 설정 추가
            with st.expander("⚙️ 알람 설정"):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.alarm_enabled = st.checkbox(
                        "🔔 소리 알림",
                        value=st.session_state.alarm_enabled,
                        key="alarm_sound",
                        help="타이머 종료 시 알람 소리를 재생합니다"
                    )
                
                with col2:
                    st.session_state.toast_enabled = st.checkbox(
                        "📱 화면 알림",
                        value=st.session_state.toast_enabled,
                        key="toast_notification",
                        help="타이머 종료 시 화면에 알림을 표시합니다"
                    )
                
                # 타이머 설정
                timer_duration = st.slider(
                    "⏰ 시간 (분)",
                    min_value=1,
                    max_value=30,
                    value=int(st.session_state.duration.total_seconds() // 60),
                    key="timer_duration",
                    help="토론 시간을 설정합니다"
                )
                st.session_state.duration = timedelta(minutes=timer_duration)
            
            if not st.session_state.timer_started:
                if st.button("⏱️ 토론 시작하기", use_container_width=True):
                    st.session_state.timer_started = True
                    st.session_state.start_time = datetime.now()
                    st.session_state.timer_finished = False
                    st.rerun()
            else:
                current_time = datetime.now()
                elapsed = current_time - st.session_state.start_time
                remaining = st.session_state.duration - elapsed
                
                if remaining.total_seconds() <= 0:
                    if not st.session_state.timer_finished:
                        st.session_state.timer_finished = True
                        
                        # 알람 소리 재생 (설정이 활성화된 경우)
                        if st.session_state.alarm_enabled:
                            st.markdown("""
                            <script>
                            playBeep();
                            // 1초 간격으로 3번 반복
                            let count = 0;
                            const beepInterval = setInterval(() => {
                                count++;
                                if (count < 3) {
                                    playBeep();
                                } else {
                                    clearInterval(beepInterval);
                                }
                            }, 1000);
                            </script>
                            """, unsafe_allow_html=True)

                        # 화면 알림 표시 (설정이 활성화된 경우)
                        if st.session_state.toast_enabled:
                            st.markdown("""
                            <script>
                            showToast("⏰ 시간이 종료되었습니다!");
                            </script>
                            """, unsafe_allow_html=True)

                        # 시각적 경고 메시지 표시
                        st.markdown("""
                        <div class="intense-warning">
                            ⏰ 시간이 종료되었습니다!
                        </div>
                        """, unsafe_allow_html=True)

                        # 전체 화면 알림 효과와 AI 음성 재생
                        audio_base64 = st.session_state.alarm_audio if 'alarm_audio' in st.session_state else ''
                        st.markdown(f"""
                        <div class="fullscreen-alert">
                            <div class="alert-content">
                                <div class="large-emoji">⏰</div>
                                <div class="alert-text">시간이 종료되었습니다!</div>
                                <div class="alert-subtext">토론을 마무리해 주세요</div>
                            </div>
                        </div>
                        <audio id="alarmAudio" autoplay style="display: none;">
                            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                        </audio>
                        <script>
                        // 알람 음성 자동 재생 및 반복
                        const audio = document.getElementById('alarmAudio');
                        
                        function playAlarm() {{{{
                            audio.currentTime = 0;
                            audio.play()
                                .then(() => console.log('알람 재생 성공'))
                                .catch(e => console.error('알람 재생 실패:', e));
                        }}}}
                        
                        // 초기 재생
                        playAlarm();
                        
                        // 2초 간격으로 3번 반복 재생
                        let playCount = 0;
                        const interval = setInterval(() => {{{{
                            playCount++;
                            if (playCount < 3) {{{{
                                playAlarm();
                            }}}} else {{{{
                                clearInterval(interval);
                            }}}}
                        }}}}, 2000);
                        </script>
                        """, unsafe_allow_html=True)

                    if st.button("🔄 타이머 리셋", use_container_width=True):
                        st.session_state.timer_started = False
                        st.session_state.start_time = None
                        st.session_state.timer_finished = False
                        st.rerun()
                else:
                    status_msg, status_color = get_timer_status(remaining)
                    progress = 1 - (remaining / st.session_state.duration)
                    
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(145deg, #f8f9fa, #e9ecef);
                        border-radius: 15px;
                        padding: 20px;
                        text-align: center;
                        box-shadow: 5px 5px 10px #d9d9d9, -5px -5px 10px #ffffff;
                    ">
                        <div class="timer-display">{format_time(remaining)}</div>
                        <div class="timer-status" style="color: {status_color};">{status_msg}</div>
                        <div style="
                            width: 100%;
                            height: 10px;
                            background-color: #e9ecef;
                            border-radius: 5px;
                            overflow: hidden;
                            margin: 10px 0;
                        ">
                            <div style="
                                width: {progress * 100}%;
                                height: 100%;
                                background: linear-gradient(90deg, #0066cc, #00cc99);
                            "></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if remaining.total_seconds() <= 60 and remaining.total_seconds() > 59 and st.session_state.alarm_enabled:
                        st.markdown("<script>playBeep();</script>", unsafe_allow_html=True)
                    
                    time.sleep(1)
                    st.rerun()

        # 하단에 다시 정하기 버튼
        st.markdown("---")
        if st.button("🔄 다시 정하기", use_container_width=True):
            st.session_state.order_generated = False
            st.session_state.timer_started = False
            st.session_state.start_time = None
            st.session_state.timer_finished = False
            st.rerun()

if __name__ == "__main__":
    # 타이머 종료 알람용 음성 생성 (한 번만)
    if 'alarm_audio' not in st.session_state:
        st.session_state.alarm_audio = generate_alarm_audio()
    main() 