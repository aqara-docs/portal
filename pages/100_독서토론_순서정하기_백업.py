import streamlit as st
import random
import time
import pandas as pd
import numpy as np

st.set_page_config(page_title="📚 독서토론 순서정하기 V2", page_icon="📚", layout="wide")

# 스타일 설정
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .character-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        transition: transform 0.2s;
    }
    .character-card:hover {
        transform: translateY(-5px);
    }
    .ability-text {
        color: #000000;
        font-size: 0.9em;
        margin: 5px 0;
    }
    .character-name {
        color: #000000;
        font-weight: bold;
        font-size: 1.2em;
        margin: 10px 0;
    }
    .special-effect {
        color: #000000;
        font-weight: bold;
        font-size: 1.1em;
        margin: 8px 0;
    }
    .game-mode {
        background: white;
        color: #000000;
        padding: 20px;
        border-radius: 15px;
        margin: 15px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .result-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #2ecc71;
        color: #000000;
    }
    .stat-badge {
        background: #f8f9fa;
        color: #000000;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.9em;
        margin: 2px;
        display: inline-block;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
        font-weight: bold !important;
    }
    p {
        color: #000000;
    }
    small {
        color: #000000;
    }
    /* 버튼 스타일 수정 */
    .stButton > button {
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        color: white !important;
        font-weight: bold;
        font-size: 1.2em;
        padding: 0.5em 1em;
        border: none;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0,0,0,0.2);
        background: linear-gradient(135deg, #2a5298, #1e3c72);
    }
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# 참여자 정보
MEMBERS = {
    "현철님": {
        "title": "지혜의 현자",
        "icon": "🧙‍♂️",
        "stats": {"지혜": 95, "통찰력": 92, "경험": 94}
    },
    "창환님": {
        "title": "미래의 선구자",
        "icon": "🚀",
        "stats": {"혁신": 93, "창의력": 95, "선구안": 91}
    },
    "성범님": {
        "title": "통찰의 대가",
        "icon": "🎯",
        "stats": {"분석": 94, "전략": 93, "실행": 92}
    },
    "성현님": {
        "title": "창의의 연금술사",
        "icon": "🌟",
        "stats": {"창조": 95, "발상": 92, "기획": 93}
    },
    "상현님": {
        "title": "질문의 예술가",
        "icon": "🎭",
        "stats": {"탐구": 94, "호기심": 93, "통찰": 92}
    }
}

# 게임 모드 설정
GAME_MODES = {
    "월요일": {
        "title": "🎲 주사위 배틀",
        "description": "각자의 주사위 실력을 겨루어 순서를 정합니다",
        "effects": [
            "🎲 더블 주사위!",
            "🎯 크리티컬 히트!",
            "✨ 럭키 포인트!",
            "💫 파워 업!",
            "🌟 대성공!"
        ]
    },
    "화요일": {
        "title": "🃏 카드 대결",
        "description": "신비한 카드의 힘으로 순서를 결정합니다",
        "effects": [
            "🃏 로열 스트레이트!",
            "♠️ 스페이드 에이스!",
            "♥️ 하트의 여왕!",
            "♦️ 다이아 킹!",
            "♣️ 클로버의 기적!"
        ]
    },
    "수요일": {
        "title": "⚔️ RPG 배틀",
        "description": "각자의 능력치와 운을 합쳐 대결을 펼칩니다",
        "effects": [
            "⚔️ 궁극기 발동!",
            "🛡️ 영웅 모드!",
            "🏹 치명타 발생!",
            "🗡️ 콤보 공격!",
            "🎭 스킬 마스터!"
        ]
    },
    "목요일": {
        "title": "🎯 미션 수행",
        "description": "독서 관련 미션을 수행하여 순서를 정합니다",
        "effects": [
            "📚 독서 마스터!",
            "💡 지식의 빛!",
            "✍️ 필사의 달인!",
            "🎭 연기의 신!",
            "🗣️ 발표의 왕!"
        ]
    },
    "금요일": {
        "title": "🎪 랜덤 페스티벌",
        "description": "다양한 미니게임을 통해 순서를 정합니다",
        "effects": [
            "🎪 축제의 주인공!",
            "🎭 완벽한 공연!",
            "🎨 예술적 감각!",
            "🎯 정확한 판단!",
            "🎪 대미의 피날레!"
        ]
    }
}

def play_dice_battle():
    """주사위 배틀 진행"""
    results = {}
    for member in MEMBERS.keys():
        dice = random.randint(1, 6)
        bonus = random.randint(0, 2)
        total = dice + bonus
        results[member] = {
            "dice": dice,
            "bonus": bonus,
            "total": total,
            "effect": random.choice(GAME_MODES["월요일"]["effects"])
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['total'], random.random())))

def play_card_battle():
    """카드 대결 진행"""
    results = {}
    cards = ["A", "K", "Q", "J", "10", "9", "8", "7"]
    card_values = {"A": 14, "K": 13, "Q": 12, "J": 11, "10": 10, "9": 9, "8": 8, "7": 7}
    
    for member in MEMBERS.keys():
        card = random.choice(cards)
        results[member] = {
            "card": card,
            "value": card_values[card],
            "effect": random.choice(GAME_MODES["화요일"]["effects"])
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['value'], random.random())))

def play_rpg_battle():
    """RPG 배틀 진행"""
    results = {}
    for member, info in MEMBERS.items():
        stat_name = random.choice(list(info["stats"].keys()))
        stat_value = info["stats"][stat_name]
        roll = random.randint(1, 20)
        total = stat_value + roll
        results[member] = {
            "stat_name": stat_name,
            "stat_value": stat_value,
            "roll": roll,
            "total": total,
            "effect": random.choice(GAME_MODES["수요일"]["effects"])
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['total'], random.random())))

def play_mission():
    """미션 수행"""
    results = {}
    missions = [
        "최근 읽은 책 소개하기",
        "인상 깊은 구절 암송하기",
        "책 속 장면 연기하기",
        "저자에게 질문 만들기",
        "책 추천하기"
    ]
    for member in MEMBERS.keys():
        score = random.randint(70, 100)
        mission = random.choice(missions)
        results[member] = {
            "mission": mission,
            "score": score,
            "grade": "S" if score >= 95 else "A" if score >= 90 else "B" if score >= 80 else "C",
            "effect": random.choice(GAME_MODES["목요일"]["effects"])
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['score'], random.random())))

def play_festival():
    """랜덤 페스티벌 진행"""
    results = {}
    festival_games = [
        "책 제목 빨리 말하기",
        "독서 퀴즈 맞히기",
        "북커버 맞추기",
        "줄거리 이어말하기",
        "책 속 인물 맞히기"
    ]
    for member in MEMBERS.keys():
        game = random.choice(festival_games)
        points = random.randint(60, 100)
        bonus = random.randint(0, 10)
        results[member] = {
            "game": game,
            "points": points,
            "bonus": bonus,
            "total": points + bonus,
            "effect": random.choice(GAME_MODES["금요일"]["effects"])
        }
    return dict(sorted(results.items(), key=lambda x: (-x[1]['total'], random.random())))

def display_results(day, results):
    """결과 표시"""
    st.markdown(f"### 🎉 {GAME_MODES[day]['title']} 결과")
    
    for i, (member, result) in enumerate(results.items(), 1):
        with st.container():
            st.markdown(
                f"""
                <div class="result-card" style="color: #000000; padding: 20px; background: white; border-radius: 15px; margin: 10px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #2ecc71;">
                    <h3>{i}번째 발표자: {MEMBERS[member]['icon']} {member}</h3>
                    <p><strong>{MEMBERS[member]['title']}</strong></p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # 결과 내용 별도 표시
            if day == "월요일":
                st.write(f"🎲 주사위: {result['dice']} + {result['bonus']} = {result['total']}")
            elif day == "화요일":
                st.write(f"🃏 카드: {result['card']} (파워: {result['value']})")
            elif day == "수요일":
                st.write(f"⚔️ {result['stat_name']}: {result['stat_value']} + 주사위: {result['roll']} = {result['total']}")
            elif day == "목요일":
                st.write(f"📝 미션: {result['mission']}")
                st.write(f"점수: {result['score']} ({result['grade']}등급)")
            else:  # 금요일
                st.write(f"🎪 게임: {result['game']}")
                st.write(f"점수: {result['points']} + {result['bonus']} = {result['total']}")
            
            # 특별 효과 표시
            st.markdown(
                f"""
                <p style="color: #ff4b4b; font-weight: bold; font-size: 1.1em; margin-top: 10px;">
                    ✨ {result['effect']}
                </p>
                """,
                unsafe_allow_html=True
            )

def generate_roulette_animation(mode):
    """룰렛 애니메이션 생성"""
    placeholder = st.empty()
    participants = list(MEMBERS.keys())
    for _ in range(20):  # 20프레임의 애니메이션
        random.shuffle(participants)
        display_text = "\n".join([
            f"### {MEMBERS[p]['icon']} {p} - {random.choice(GAME_MODES[mode]['effects'])}" 
            for p in participants[:5]
        ])
        placeholder.markdown(display_text)
        time.sleep(0.1)
    return placeholder

def get_daily_effect(day):
    """요일별 특별 효과 생성"""
    return random.choice(GAME_MODES[day]['effects'])

def play_animation(day, members):
    """요일별 특별 애니메이션 효과"""
    placeholder = st.empty()
    
    if day == "월요일":
        # 주사위 굴리기 애니메이션
        for _ in range(15):
            dice_display = ""
            for member in members:
                dice = random.randint(1, 6)
                dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
                dice_display += f"### {MEMBERS[member]['icon']} {member}: {dice_faces[dice-1]}\n"
            placeholder.markdown(dice_display)
            time.sleep(0.2)
    
    elif day == "화요일":
        # 카드 뽑기 애니메이션
        cards = ["🂡", "🂮", "🂭", "🂫", "🂪", "🂩", "🂨", "🂧"]
        for _ in range(15):
            card_display = ""
            for member in members:
                card = random.choice(cards)
                card_display += f"### {MEMBERS[member]['icon']} {member}: {card}\n"
            placeholder.markdown(card_display)
            time.sleep(0.2)
    
    elif day == "수요일":
        # RPG 스킬 발동 애니메이션
        skills = ["⚔️", "🛡️", "🏹", "✨", "🔮"]
        for _ in range(15):
            skill_display = ""
            for member in members:
                skill = random.choice(skills)
                power = random.randint(50, 100)
                skill_display += f"### {MEMBERS[member]['icon']} {member}: {skill} {power}!\n"
            placeholder.markdown(skill_display)
            time.sleep(0.2)
    
    elif day == "목요일":
        # 미션 수행 애니메이션
        progress = ["📚", "📖", "📗", "📘", "📙"]
        for _ in range(15):
            mission_display = ""
            for member in members:
                stage = random.choice(progress)
                mission_display += f"### {MEMBERS[member]['icon']} {member}: {stage}\n"
            placeholder.markdown(mission_display)
            time.sleep(0.2)
    
    else:  # 금요일
        # 페스티벌 애니메이션
        festival = ["🎪", "🎭", "🎨", "🎯", "🎪"]
        for _ in range(15):
            fest_display = ""
            for member in members:
                effect = "".join(random.choices(festival, k=3))
                fest_display += f"### {MEMBERS[member]['icon']} {member}: {effect}\n"
            placeholder.markdown(fest_display)
            time.sleep(0.2)
    
    return placeholder

def main():
    st.title("🎯 독서토론 순서정하기 V2")
    
    # 요일 선택
    day_options = {
        "월요일": "🎲 주사위 배틀",
        "화요일": "🃏 카드 대결",
        "수요일": "⚔️ RPG 배틀",
        "목요일": "🎯 미션 수행",
        "금요일": "🎪 랜덤 페스티벌"
    }
    
    # 이전 선택한 요일 저장
    if 'previous_day' not in st.session_state:
        st.session_state.previous_day = None
    
    day = st.selectbox(
        "요일을 선택하세요",
        list(day_options.keys()),
        format_func=lambda x: f"{x}: {day_options[x]}"
    )
    
    # 요일이 변경되면 결과 초기화
    if st.session_state.previous_day != day:
        st.session_state.order_generated = False
        if hasattr(st.session_state, 'results'):
            del st.session_state.results
        st.session_state.previous_day = day
    
    st.markdown(f"""
    <div class="game-mode">
        <h2>{GAME_MODES[day]['title']}</h2>
        <p>{GAME_MODES[day]['description']}</p>
    </div>
    """, unsafe_allow_html=True)

    # 참여자 목록 표시
    st.markdown("### 👥 참여자 목록")
    cols = st.columns(5)
    for i, (member, info) in enumerate(MEMBERS.items()):
        with cols[i]:
            st.markdown(f"""
            <div class="character-card">
                <h4>{info['icon']} {member}</h4>
                <p>{info['title']}</p>
                <small>{'<br>'.join(f'{k}: {v}' for k, v in info['stats'].items())}</small>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")

    if 'order_generated' not in st.session_state:
        st.session_state.order_generated = False

    if not st.session_state.order_generated:
        if st.button(f"🎮 {GAME_MODES[day]['title']} 시작하기!", use_container_width=True):
            with st.spinner("게임 준비 중..."):
                # 참가자 목록 준비
                participants = list(MEMBERS.keys())
                random.shuffle(participants)
                
                # 애니메이션 실행
                play_animation(day, participants)
                
                # 요일별 게임 진행
                if day == "월요일":
                    st.session_state.results = play_dice_battle()
                elif day == "화요일":
                    st.session_state.results = play_card_battle()
                elif day == "수요일":
                    st.session_state.results = play_rpg_battle()
                elif day == "목요일":
                    st.session_state.results = play_mission()
                else:  # 금요일
                    st.session_state.results = play_festival()
                
                st.session_state.order_generated = True
                
                # 효과음 & 시각효과
                st.balloons()
                st.snow()
                st.rerun()

    if st.session_state.order_generated and hasattr(st.session_state, 'results'):
        # 결과 표시
        display_results(day, st.session_state.results)
        
        # 효과음 & 시각효과
        st.balloons()
        st.snow()

        if st.button("🔄 다시 선택하기!", use_container_width=True):
            st.session_state.order_generated = False
            if hasattr(st.session_state, 'results'):
                del st.session_state.results
            st.rerun()

if __name__ == "__main__":
    main() 