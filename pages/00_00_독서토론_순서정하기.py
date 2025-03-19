import streamlit as st
import random
import time
import pandas as pd
import numpy as np

st.set_page_config(page_title="🎯 독서토론 순서정하기", page_icon="🎯", layout="wide")

# 전체 페이지 스타일 설정
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .character-card {
        background-color: white;
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
    /* 제목 스타일 추가 */
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }
    .st-emotion-cache-1629p8f h1 {
        color: #000000 !important;
    }
    .st-emotion-cache-1629p8f h2 {
        color: #000000 !important;
    }
    .st-emotion-cache-1629p8f h3 {
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# 참여자별 캐릭터 설정
CHARACTERS = {
    "현철님": "🧙‍♂️ 지혜의 현자",
    "창환님": "🚀 미래의 선구자",
    "성범님": "🎯 통찰의 대가",
    "성현님": "🌟 창의의 연금술사",
    "상현님": "🎭 질문의 예술가"
}

# 특별한 능력치
ABILITIES = {
    "현철님": ["통찰력 MAX", "지혜 +100", "경험치 +500"],
    "창환님": ["창의력 MAX", "혁신 +100", "선구안 +500"],
    "성범님": ["분석력 MAX", "전략 +100", "실행력 +500"],
    "성현님": ["창조력 MAX", "발상 +100", "기획력 +500"],
    "상현님": ["질문력 MAX", "탐구 +100", "호기심 +500"]
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
    "상현님": {"질문력": 94, "탐구": 92, "호기심": 91}
}

# 랜덤 미션 목록
MISSIONS = [
    "📚 가장 최근에 읽은 책 제목 말하기",
    "💡 이번 주 최고의 아이디어 공유하기",
    "🎯 한 문장으로 이번 주 목표 설명하기",
    "🌟 가장 인상 깊었던 책 구절 암기하기",
    "🎭 책 속 한 장면 연기하기"
]

def generate_roulette_animation():
    """룰렛 애니메이션 생성"""
    placeholder = st.empty()
    participants = list(CHARACTERS.keys())
    for _ in range(20):  # 20프레임의 애니메이션
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

def main():
    st.markdown('<h1 style="color: black;">🎯 독서토론 순서 정하기</h1>', unsafe_allow_html=True)
    st.markdown('<h3 style="color: black;">🎲 오늘의 토론 멤버를 확인하세요!</h3>', unsafe_allow_html=True)

    # 캐릭터 소개
    cols = st.columns(5)
    for i, (person, character) in enumerate(CHARACTERS.items()):
        with cols[i]:
            st.markdown(f"""
            <div class="character-card">
                <h3>{character}</h3>
                <p class="character-name">{person}</p>
                <div class="ability-text">
                    {'<br>'.join(f'• {ability}' for ability in ABILITIES[person])}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    if 'order_generated' not in st.session_state:
        st.session_state.order_generated = False
        st.session_state.final_order = []
        st.session_state.effects = {}

    if not st.session_state.order_generated:
        if st.button("🎯 발표 순서 정하기!", use_container_width=True):
            with st.spinner("순서를 정하는 중..."):
                placeholder = generate_roulette_animation()
                
                # 최종 순서 생성
                participants = list(CHARACTERS.keys())
                random.shuffle(participants)
                st.session_state.final_order = participants
                
                # 각 참가자별 특별 효과 부여
                st.session_state.effects = {
                    person: get_special_effect() 
                    for person in participants
                }
                
                st.session_state.order_generated = True
                st.balloons()
                st.snow()
                st.rerun()

    if st.session_state.order_generated:
        st.markdown('<h2 style="color: black;">🎉 최종 발표 순서</h2>', unsafe_allow_html=True)
        
        # 결과 테이블 생성
        results = []
        for i, person in enumerate(st.session_state.final_order, 1):
            results.append({
                "순서": f"{i}번째",
                "캐릭터": CHARACTERS[person],
                "이름": person,
                "특별효과": st.session_state.effects[person],
                "능력치": " | ".join(ABILITIES[person])
            })
        
        df = pd.DataFrame(results)
        
        # 데이터프레임 표시 (테이블 대신)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "순서": st.column_config.Column(width=100),
                "캐릭터": st.column_config.Column(width=200),
                "이름": st.column_config.Column(width=100),
                "특별효과": st.column_config.Column(width=200),
                "능력치": st.column_config.Column(width=400)
            }
        )

        # 결과를 카드 형태로도 표시
        st.markdown('<h3 style="color: black;">📊 상세 정보</h3>', unsafe_allow_html=True)
        for i, person in enumerate(st.session_state.final_order, 1):
            with st.container():
                st.markdown(f"""
                <div style="background-color: white; padding: 20px; border-radius: 10px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h3 style="color: #0066cc;">{i}번째 발표자: {person}</h3>
                    <p style="color: #1f1f1f;"><strong>캐릭터:</strong> {CHARACTERS[person]}</p>
                    <p style="color: #ff4b4b;"><strong>특별효과:</strong> {st.session_state.effects[person]}</p>
                    <p style="color: #1f1f1f;"><strong>능력치:</strong> {' | '.join(ABILITIES[person])}</p>
                </div>
                """, unsafe_allow_html=True)

        if st.button("🔄 다시 정하기", use_container_width=True):
            st.session_state.order_generated = False
            st.rerun()

if __name__ == "__main__":
    main() 