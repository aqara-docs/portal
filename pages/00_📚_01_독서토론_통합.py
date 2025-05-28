import streamlit as st
import pandas as pd
import os
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
from langchain_openai import OpenAI as LangOpenAI
from langchain_anthropic import ChatAnthropic
import base64
import random
from datetime import timedelta
import time
import streamlit.components.v1 as components

st.set_page_config(page_title="📚 독서토론 통합", layout="wide")

# 환경 변수 로드
load_dotenv()
st.title("📚 독서토론 통합 관리")
# 모델 선택 및 API 키 확인
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = 'claude-3-7-sonnet-latest'

# 모델 선택 UI (Claude 최신 버전이 디폴트)
available_models = []
has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
if has_anthropic_key:
    available_models.extend([
        'claude-3-7-sonnet-latest',
        'claude-3-5-sonnet-latest',
        'claude-3-5-haiku-latest',
    ])
has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
if has_openai_key:
    available_models.extend(['gpt-4o', 'gpt-4o-mini'])
if not available_models:
    available_models = ['claude-3-7-sonnet-latest']

# 모델 선택 (다른 세션 상태에 영향을 주지 않도록 안전하게 처리)
selected_model = st.selectbox(
    'AI 모델 선택',
    options=available_models,
    index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
    help='Claude(Anthropic)는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
)
# 모델이 실제로 변경된 경우에만 세션 상태 업데이트
if selected_model != st.session_state.selected_model:
    st.session_state.selected_model = selected_model

# DB 연결 함수
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def save_material(book_title, file_name, content, type):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO reading_materials (book_title, file_name, content, type) VALUES (%s, %s, %s, %s)",
            (book_title, file_name, content, type)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"DB 저장 중 오류: {str(e)}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_materials(material_type):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, book_title, file_name, content, created_at FROM reading_materials WHERE type = %s ORDER BY created_at DESC",
            (material_type,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# 요약 함수 (Claude/OpenAI 모두 지원)
def ai_summarize(text, model_name, extra_prompt=None):
    summary_instruction = (
        "아래 텍스트를 600~900자 내외, bullet point 10~15개로, 주제별로 제목(굵게)을 붙여 핵심만 간결하게 요약해 주세요. "
        "각 항목은 '~함' 형태의 간결한 한글로 작성하고, 존댓말은 사용하지 마세요. "
        "불필요한 설명은 생략하고, 꼭 필요한 핵심만 요약해 주세요."
    )
    if model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=1200)
        prompt = f"""
{summary_instruction}
---
{text}
"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.invoke([
            {"role": "system", "content": "당신은 요약 전문가입니다. 항상 600~900자 내외, 10~15개 bullet point로, 주제별 제목과 함께 '~함' 형태의 간결체로 작성합니다. 존댓말은 사용하지 않습니다. 불필요한 설명 없이 꼭 필요한 핵심만 요약합니다."},
            {"role": "user", "content": prompt}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt = f"""
{summary_instruction}
---
{text}
"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 요약 전문가입니다. 항상 600~900자 내외, 10~15개 bullet point로, 주제별 제목과 함께 '~함' 형태의 간결체로 작성합니다. 존댓말은 사용하지 않습니다. 불필요한 설명 없이 꼭 필요한 핵심만 요약합니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.3
        )
        return response.choices[0].message.content

# 적용 파일 생성 함수 (Claude/OpenAI 모두 지원)
def ai_generate_application(summary_text, application_text, model_name, extra_prompt=None):
    if model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=8192)
        prompt = f"""
아래의 '요약 내용'과 '기존 적용 파일'을 참고하여, 기존 적용 파일을 개선/보완한 새로운 적용 파일을 작성해 주세요.\n\n[절대적 요구사항]\n- 기존 적용 파일의 대부분의 핵심 내용이 빠짐없이 포함되어야 합니다. 중요한 내용이 누락되지 않도록 하세요.\n- 기존 적용 파일의 모든 섹션, 소제목, 구조를 그대로 유지하세요.\n- 요약 내용의 핵심 인사이트와 지침을 반드시 반영해 주세요.\n- 기존 적용 파일의 구조와 맥락을 최대한 유지하되, 중복은 피하고 자연스럽게 통합해 주세요.\n- 반드시 존댓말을 사용해 주세요.\n\n[요약 내용]\n{summary_text}\n\n[기존 적용 파일]\n{application_text}\n"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.invoke([
            {"role": "system", "content": "당신은 적용 파일 통합 전문가입니다. 반드시 기존 적용 파일의 대부분의 핵심 내용이 빠짐없이 포함되고, 구조와 맥락을 유지하며, 존댓말로 작성합니다. 중요한 내용 누락 금지."},
            {"role": "user", "content": prompt}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt = f"""
아래의 '요약 내용'과 '기존 적용 파일'을 참고하여, 기존 적용 파일을 개선/보완한 새로운 적용 파일을 작성해 주세요.\n\n[절대적 요구사항]\n- 기존 적용 파일의 대부분의 핵심 내용이 빠짐없이 포함되어야 합니다. 중요한 내용이 누락되지 않도록 하세요.\n- 기존 적용 파일의 모든 섹션, 소제목, 구조를 그대로 유지하세요.\n- 요약 내용의 핵심 인사이트와 지침을 반드시 반영해 주세요.\n- 기존 적용 파일의 구조와 맥락을 최대한 유지하되, 중복은 피하고 자연스럽게 통합해 주세요.\n- 반드시 존댓말을 사용해 주세요.\n\n[요약 내용]\n{summary_text}\n\n[기존 적용 파일]\n{application_text}\n"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 적용 파일 통합 전문가입니다. 반드시 기존 적용 파일의 대부분의 핵심 내용이 빠짐없이 포함되고, 구조와 맥락을 유지하며, 존댓말로 작성합니다. 중요한 내용 누락 금지."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=8192,
            temperature=0.3
        )
        return response.choices[0].message.content

def summarize_for_tts(text, max_length=3500):
    if len(text) <= max_length:
        return text
    lines = text.split('\n')
    summary = []
    current_length = 0
    for line in lines:
        if line.startswith('#') or line.startswith('##'):
            if current_length + len(line) + 2 <= max_length:
                summary.append(line)
                current_length += len(line) + 2
        elif '[핵심 요약]' in line or '[주요 분석]' in line or '[실행 제안]' in line:
            if current_length + len(line) + 2 <= max_length:
                summary.append(line)
                current_length += len(line) + 2
    return '\n'.join(summary)

def text_to_speech(text):
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        audio_html = f'''
            <audio controls>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
        '''
        return audio_html
    except Exception as e:
        st.error(f"음성 변환 중 오류 발생: {str(e)}")
        return None

# --- JS 동적 효과 함수 추가 (스코프 적용) ---
def get_alarm_js_scoped():
    return """
    <script>
    let audioContext = null;
    let isAudioInitialized = false;
    async function initAudioContext() {
        if (!isAudioInitialized) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                await audioContext.resume();
                isAudioInitialized = true;
            } catch (e) { console.error('오디오 컨텍스트 초기화 실패:', e); }
        }
    }
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
        } catch (e) { console.error('비프음 재생 실패:', e); }
    }
    window.playBeep = playBeep;
    </script>
    """
def get_toast_notification_js_scoped():
    return """
    <style>
    .order-tab-root .toast { visibility: hidden; min-width: 250px; margin-left: -125px; background-color: #ff4b4b; color: white; text-align: center; border-radius: 10px; padding: 16px; position: fixed; z-index: 1000; left: 50%; bottom: 30px; font-size: 18px; font-weight: bold; box-shadow: 0px 0px 10px rgba(0,0,0,0.5); transition: visibility 0.5s, opacity 0.5s; opacity: 0; }
    .order-tab-root .toast.show { visibility: visible; opacity: 1; }
    </style>
    <div class="toast"></div>
    <script>
    function showToast(message) {
        const toast = document.querySelector('.order-tab-root .toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = "toast show";
        setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 3000);
    }
    window.showToast = showToast;
    </script>
    """

def get_obsidian_notification_js_scoped():
    return '''
    <div class="obsidian-alert" style="display: none;">
        <div class="alert-content">
            <div class="large-emoji">🎙️</div>
            <div class="alert-text">옵시디언 녹음기능을 활성화해 주세요!</div>
        </div>
    </div>
    <script>
    function showObsidianNotification() {
        const alert = document.querySelector('.order-tab-root .obsidian-alert');
        if (!alert) return;
        alert.style.display = 'flex';
        setTimeout(() => { alert.style.display = 'none'; }, 3000);
    }
    window.showObsidianNotification = showObsidianNotification;
    </script>
    <style>
    .order-tab-root .obsidian-alert {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 102, 204, 0.95);
        display: none; justify-content: center; align-items: center;
        z-index: 9999; animation: pulse 2s;
    }
    .order-tab-root .obsidian-alert .alert-content {
        background: white; padding: 2rem; border-radius: 20px; text-align: center;
        box-shadow: 0 0 30px rgba(0,0,0,0.3); animation: bounce 1s;
    }
    .order-tab-root .obsidian-alert .large-emoji { font-size: 5rem; margin-bottom: 1rem; }
    .order-tab-root .obsidian-alert .alert-text { font-size: 2rem; font-weight: bold; color: #0066cc; margin: 1rem 0; }
    @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
    </style>
    '''

def discussion_order_tab():
    # 캐릭터/상수 (함수 최상단에 위치)
    CHARACTERS = {"현철님": "🧙‍♂️ 지혜의 현자", "창환님": "🚀 미래의 선구자", "성범님": "🎯 통찰의 대가", "상현님": "🎭 질문의 예술가", "성일님": "💡 혁신의 아이콘", "경호님": "🦾 전략의 마에스트로", "재원님": "⚡️ 기술영업의 달인"}
    VALUES = [
        "Success is not the key to happiness. Happiness is the key to success.\n성공이 행복의 열쇠가 아니라, 행복이 성공의 열쇠다.",
        "I find that the harder I work, the more luck I seem to have. – Thomas Jefferson\n열심히 일 할수록 운이 더 좋아지는 것 같다. – 토머스 제퍼슨",
        # ... (필요시 추가)
    ]
    # 순서/타이머 관련 상태 초기화 (최상단에서 보장)
    if 'order_generated' not in st.session_state:
        st.session_state.order_generated = False
        st.session_state.final_order = []
    if 'order_timer_started' not in st.session_state:
        st.session_state.order_timer_started = False
        st.session_state.order_start_time = None
        st.session_state.order_duration = timedelta(minutes=15)
        st.session_state.order_timer_finished = False
        st.session_state.order_alarm_enabled = True
        st.session_state.order_toast_enabled = True
    # 스타일 및 JS (최초 1회만)
    if 'order_js_loaded' not in st.session_state:
        st.markdown("""
        <style>
        .order-tab-root .character-card { background-color: #f8f9fa; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 1rem; }
        .order-tab-root .character-name { color: #0066cc; font-weight: bold; }
        .order-tab-root .timer-display { color: #1f1f1f; font-size: 4rem; font-weight: bold; text-align: center; }
        .order-tab-root .timer-status { font-size: 1.2rem; text-align: center; }
        .order-tab-root .intense-warning { background: linear-gradient(145deg, #ff4b4b, #ff6b6b); color: white; padding: 20px; border-radius: 15px; text-align: center; font-size: 28px; font-weight: bold; margin: 20px 0; animation: blink-intense 0.7s infinite; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.5); }
        .order-tab-root .fullscreen-alert { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(255, 75, 75, 0.95); display: flex; justify-content: center; align-items: center; z-index: 9999; animation: pulse 2s infinite; }
        .order-tab-root .alert-content { background: white; padding: 2rem; border-radius: 20px; text-align: center; box-shadow: 0 0 30px rgba(0,0,0,0.3); animation: bounce 1s infinite; }
        .order-tab-root .large-emoji { font-size: 5rem; margin-bottom: 1rem; }
        .order-tab-root .alert-text { font-size: 2rem; font-weight: bold; color: #ff4b4b; margin: 1rem 0; }
        .order-tab-root .alert-subtext { font-size: 1.2rem; color: #666; }
        @keyframes blink-intense { 0% { transform: scale(1); background: linear-gradient(145deg, #ff4b4b, #ff6b6b); } 50% { transform: scale(1.05); background: linear-gradient(145deg, #ff6b6b, #ff8b8b); } 100% { transform: scale(1); background: linear-gradient(145deg, #ff4b4b, #ff6b6b); } }
        @keyframes pulse { 0% { background: rgba(255, 75, 75, 0.95); } 50% { background: rgba(255, 75, 75, 0.7); } 100% { background: rgba(255, 75, 75, 0.95); } }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        </style>
        """, unsafe_allow_html=True)
        st.markdown(get_alarm_js_scoped(), unsafe_allow_html=True)
        st.markdown(get_toast_notification_js_scoped(), unsafe_allow_html=True)
        st.session_state.order_js_loaded = True
    st.markdown("<div class='order-tab-root'>", unsafe_allow_html=True)
    # 옵시디언 녹음기능 알림 (한 번만, 정적)
    if 'order_initial_notice_shown' not in st.session_state:
        st.markdown('''
        <div class="notice-container" style="background: linear-gradient(145deg, #0066cc, #0052a3); color: white; padding: 20px; border-radius: 15px; text-align: center; margin: 20px auto; max-width: 600px; animation: slideIn 0.5s ease-out;">
            <div class="notice-icon" style="font-size: 48px; margin-bottom: 10px; display: inline-block;">🎙️</div>
            <div class="notice-text" style="font-size: 24px; font-weight: bold; margin: 10px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">옵시디언 녹음기능을 활성화해 주세요!</div>
            <div class="notice-subtext">
                <div class="highlight" style="background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 5px; display: inline-block; margin: 5px 0;">토론 내용 기록을 위해 꼭 필요합니다</div>
                <div class="highlight" style="background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 5px; display: inline-block; margin: 5px 0;">시작 전 반드시 확인해 주세요</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.session_state.order_initial_notice_shown = True
    # 헤딩 색상 흰색으로 변경
    st.markdown('<h1 style="color: #fff;">🎯 독서토론 순서 정하기</h1>', unsafe_allow_html=True)
    st.markdown('<h3 style="color: #fff;">🎲 오늘의 토론 멤버를 확인하세요!</h3>', unsafe_allow_html=True)
    cols = st.columns(len(CHARACTERS))
    for i, (person, character) in enumerate(CHARACTERS.items()):
        with cols[i]:
            st.markdown(f"<div class='character-card'><h3>{character}</h3><p class='character-name'>{person}</p></div>", unsafe_allow_html=True)
    st.markdown("---")
    if not st.session_state.order_generated:
        if st.button("🎯 발표 순서 정하기!", key="order_btn", use_container_width=True):
            with st.spinner("순서를 정하는 중..."):
                # 룰렛 애니메이션 (동적)
                placeholder = st.empty()
                participants = list(CHARACTERS.keys())
                for _ in range(30):
                    random.shuffle(participants)
                    display_text = "\n".join([f"<div style='font-size:28px; font-weight:bold; color:#0066cc;'>{CHARACTERS[p]} <span style='color:#222;'>{p}</span></div>" for p in participants])
                    placeholder.markdown(f"<div class='order-tab-root'>{display_text}</div>", unsafe_allow_html=True)
                    time.sleep(0.08)
                other_participants = [p for p in participants if p != "현철님"]
                random.shuffle(other_participants)
                st.session_state.final_order = other_participants + ["현철님"]
                st.session_state.order_generated = True
                st.balloons()
    if st.session_state.order_generated:
        col1, col2 = st.columns([1, 1], gap="large")
        with col1:
            st.markdown('<h2 style="color: #fff; font-size: 24px; margin-bottom: 20px;">🎉 발표 순서</h2>', unsafe_allow_html=True)
            for i, person in enumerate(st.session_state.final_order, 1):
                st.markdown(f"<div style='background: linear-gradient(145deg, #ffffff, #f0f0f0); padding: 10px; border-radius: 8px; margin: 5px 0; box-shadow: 3px 3px 6px #d9d9d9, -3px -3px 6px #ffffff;'><div style='color: #0066cc; margin: 0; font-size: 16px; display: flex; align-items: center;'><span style='font-weight: bold; min-width: 24px;'>{i}.</span><span style='margin-left: 8px;'>{person}</span><span style='margin-left: 8px; opacity: 0.8;'>{CHARACTERS[person]}</span></div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<h2 style="color: #fff; font-size: 24px; margin-bottom: 20px;">⏱️ 토론 타이머</h2>', unsafe_allow_html=True)
            # 타이머 관련 상태 초기화 (최상단에서 보장)
            if 'order_timer_started' not in st.session_state:
                st.session_state.order_timer_started = False
                st.session_state.order_start_time = None
                st.session_state.order_duration = timedelta(minutes=15)
                st.session_state.order_timer_finished = False
            # 타이머 시간 설정 슬라이더 (1~30분, 기본 15분)
            timer_duration = st.slider("⏰ 시간 (분)", min_value=1, max_value=30, value=int(st.session_state.order_duration.total_seconds() // 60), key="order_timer_duration")
            st.session_state.order_duration = timedelta(minutes=timer_duration)

            if not st.session_state.order_timer_started:
                if st.button("⏱️ 토론 시작하기", use_container_width=True):
                    st.session_state.order_timer_started = True
                    st.session_state.order_start_time = datetime.now().timestamp()
                    st.session_state.order_timer_finished = False
            else:
                if st.button("🔄 타이머 리셋", use_container_width=True):
                    # 타이머 관련 세션 상태만 리셋 (다른 탭의 세션 상태는 보호)
                    st.session_state.order_timer_started = False
                    st.session_state.order_start_time = None
                    st.session_state.order_timer_finished = False
                # JS 기반 실시간 타이머 표시
                start_time = st.session_state.order_start_time
                duration = int(st.session_state.order_duration.total_seconds())  # 초 단위
                audio_base64 = st.session_state.get('order_end_audio', '')
                # 타이머+음성 HTML 삽입 (종료 시 src를 동적으로 할당하고 play)
                components.html(f'''
                <div id='timer' style='font-size:2rem; text-align:center; color:#fff; background:#222; border-radius:10px; padding:10px 0; margin:10px 0;'></div>
                <audio id='endAudio' style='display:none;'></audio>
                <script>
                const start = {start_time} * 1000;
                const duration = {duration} * 1000;
                const audioBase64 = "{audio_base64}";
                function updateTimer() {{
                    const now = Date.now();
                    const elapsed = now - start;
                    const remaining = Math.max(0, duration - elapsed);
                    const sec = Math.floor(remaining / 1000);
                    const min = Math.floor(sec / 60);
                    const secDisplay = String(sec % 60).padStart(2, '0');
                    const minDisplay = String(min).padStart(2, '0');
                    document.getElementById('timer').innerText = '남은 시간: ' + minDisplay + ':' + secDisplay;
                    if (remaining > 0) {{
                        setTimeout(updateTimer, 1000);
                    }} else {{
                        document.getElementById('timer').innerText = '타이머 종료!';
                        // 종료 음성 자동 재생 (src를 동적으로 할당)
                        const audio = document.getElementById('endAudio');
                        if (audio && audioBase64) {{
                            audio.src = 'data:audio/mp3;base64,' + audioBase64;
                            audio.currentTime = 0;
                            audio.play();
                        }}
                    }}
                }}
                updateTimer();
                </script>
                ''', height=80)
    st.markdown("---")
    if st.button("🔄 다시 정하기", key="order_reset", use_container_width=True):
        # 타이머 관련 세션 상태만 초기화 (다른 탭의 세션 상태는 보호)
        st.session_state.order_generated = False
        st.session_state.order_timer_started = False
        st.session_state.order_start_time = None
        st.session_state.order_timer_finished = False
    st.markdown("</div>", unsafe_allow_html=True)

def main():
    # 독서토론 검색/조회 탭의 세션 상태를 영구적으로 보호
    if 'ai_summary_result' not in st.session_state:
        st.session_state['ai_summary_result'] = None
    if 'tts_audio' not in st.session_state:
        st.session_state['tts_audio'] = None
    if 'ai_app_summary_result' not in st.session_state:
        st.session_state['ai_app_summary_result'] = None
    if 'tts_app_audio' not in st.session_state:
        st.session_state['tts_app_audio'] = None
   
    tab1, tab2, tab3, tab_order = st.tabs(["요약/적용 파일 등록", "적용 파일 생성", "독서토론 검색/조회", "발표 순서/타이머"])
    with tab1:
        st.header("요약/적용 파일 등록")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("파일 업로드")
            uploaded_file = st.file_uploader("요약/적용 파일 업로드 (txt, md)", type=["txt", "md"])
        with col2:
            st.subheader("텍스트 직접 입력")
            text_input = st.text_area("텍스트를 복사해 넣으세요", height=200)
        # 책 제목 선택 (selectbox, 기본값: Good to Great)
        book_title = st.selectbox(
            "책 제목",
            ["퍼스널 MBA", "레이달리오의 원칙", "Good to Great"],
            index=2
        )
        material_type = st.selectbox("자료 유형", ["요약", "적용"])
        openai_api_key = os.getenv('OPENAI_API_KEY')
        file_name = None
        raw_text = None
        # --- 추가: AI 프롬프트용 텍스트 박스 ---
        extra_prompt_reg = st.text_area("AI 프롬프트에 추가로 참고할 내용(선택)", key="reg_extra_prompt", placeholder="특정 관점, 강조점, 추가 지시사항 등 자유롭게 입력하세요.", height=80)
        # ---
        if uploaded_file:
            file_name = uploaded_file.name
            raw_text = uploaded_file.read().decode('utf-8')
        elif text_input.strip():
            file_name = f"manual_input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            raw_text = text_input
        if st.button("등록 (AI 요약 및 저장)"):
            if not raw_text:
                st.warning("파일 업로드 또는 텍스트 입력이 필요합니다.")
            elif not openai_api_key and not uploaded_file:
                st.error("OpenAI API 키가 설정되지 않았습니다.")
            else:
                with st.spinner("저장 중입니다..."):
                    try:
                        if uploaded_file:
                            # 파일 업로드 시 AI 요약 없이 원문 저장
                            saved = save_material(book_title, file_name, raw_text, "summary" if material_type=="요약" else "application")
                            preview_content = raw_text
                        else:
                            # 직접 입력 시 AI 요약 후 저장 (요약/적용 모두)
                            summary = ai_summarize(raw_text, st.session_state.selected_model, extra_prompt_reg)
                            saved = save_material(book_title, file_name, summary, "summary" if material_type=="요약" else "application")
                            preview_content = summary
                        if saved:
                            st.success("저장 완료!")
                            st.markdown("### 저장된 내용 미리보기")
                            st.markdown(format_bullet_points(preview_content))
                    except Exception as e:
                        st.error(f"AI 요약/저장 중 오류: {str(e)}")

    with tab2:
        st.header("적용 파일 생성")
        openai_api_key = os.getenv('OPENAI_API_KEY')
        # 요약 파일, 기존 적용 파일 선택
        summaries = get_materials("summary")
        applications = get_materials("application")
        summary_options = [f"{s['book_title']} - {s['file_name']}" for s in summaries]
        application_options = [f"{a['book_title']} - {a['file_name']}" for a in applications]
        selected_summary = st.selectbox("요약 파일 선택", options=summary_options)
        selected_application = st.selectbox("기존 적용 파일 선택", options=application_options)
        extra_prompt = st.text_area("AI 프롬프트에 추가로 참고할 내용(선택)", placeholder="특정 관점, 강조점, 추가 지시사항 등 자유롭게 입력하세요.", height=80)
        if st.button("AI 적용 파일 생성 및 저장"):
            if not openai_api_key:
                st.error("OpenAI API 키가 설정되지 않았습니다.")
            else:
                with st.spinner("AI가 적용 파일을 생성 중입니다..."):
                    try:
                        summary_text = summaries[summary_options.index(selected_summary)]['content']
                        application_text = applications[application_options.index(selected_application)]['content']
                        result = ai_generate_application(summary_text, application_text, st.session_state.selected_model, extra_prompt)
                        # 저장
                        book_title = summaries[summary_options.index(selected_summary)]['book_title']
                        file_name = f"AI_적용파일_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                        saved = save_material(book_title, file_name, result, "application")
                        if saved:
                            st.success("적용 파일 생성 및 저장 완료!")
                            st.markdown("### 생성된 적용 파일 미리보기")
                            st.markdown(result)
                    except Exception as e:
                        st.error(f"AI 적용 파일 생성/저장 중 오류: {str(e)}")

    with tab3:
        st.header("독서토론 검색/조회")
        subtab1, subtab2 = st.tabs(["요약 파일", "적용 파일"])
        with subtab1:
            st.subheader("요약 파일 검색/AI 요약/음성 생성")
            summaries = get_materials("summary")
            previous_topic = st.text_input("이전 토론 주제", placeholder="이전 독서 토론의 주제를 입력해주세요", key="prev_topic_tts")
            if summaries:
                summary_options = [f"{s['book_title']} - {s['file_name']} ({s['created_at'].strftime('%Y-%m-%d')})" for s in summaries]
                selected_idx = st.selectbox("요약 파일 선택 (최신순)", range(len(summary_options)), format_func=lambda i: summary_options[i], key="summary_selectbox")
                selected_summary = summaries[selected_idx]
                st.write(f"### {selected_summary['file_name']}")
                st.markdown(format_bullet_points(selected_summary['content']))
                st.write(f"*등록일: {selected_summary['created_at'].strftime('%Y-%m-%d')}*")
                extra_prompt_summary = st.text_area("AI 프롬프트에 추가로 참고할 내용(선택)", key="summary_extra_prompt", placeholder="특정 관점, 강조점, 추가 지시사항 등 자유롭게 입력하세요.", height=80)
                if st.button("AI 요약"):
                    with st.spinner("AI가 핵심 요약을 생성 중입니다..."):
                        try:
                            ai_summary = ai_summarize_keypoints(selected_summary['content'], st.session_state.selected_model, extra_prompt_summary)
                            st.session_state['ai_summary_result'] = ai_summary
                        except Exception as e:
                            st.error(f"AI 요약 중 오류: {str(e)}")
                if st.session_state['ai_summary_result']:
                    st.markdown("### 비즈니스 실전 적용 핵심")
                    st.markdown(format_bullet_points(st.session_state['ai_summary_result']))
                if st.button("음성 생성", key="summary_tts_btn"):
                    with st.spinner("음성을 생성하고 있습니다..."):
                        try:
                            opening_ment = f"안녕하세요. 좋은 아침입니다. 지난번 시간에는 {previous_topic if previous_topic else '이전 주제'}의 내용으로 독서토론을 진행했습니다. 그럼 오늘 독서 토론 내용을 요약해 드리겠습니다."
                            full_text = f"""
{opening_ment}
\n요약 내용입니다.\n{selected_summary['content']}"""
                            if st.session_state.get('ai_summary_result'):
                                full_text += f"\n\n비즈니스 실전 적용 핵심 내용입니다.\n{st.session_state['ai_summary_result']}"
                            full_text += "\n\n즐거운 독서 토론 되세요."
                            summarized_text = summarize_for_tts(full_text)
                            tts_audio = text_to_speech(summarized_text)
                            if tts_audio:
                                st.session_state['tts_audio'] = tts_audio
                        except Exception as e:
                            st.error(f"음성 생성 중 오류: {str(e)}")
                if st.session_state['tts_audio']:
                    st.markdown(st.session_state['tts_audio'], unsafe_allow_html=True)
            else:
                st.info("등록된 요약 파일이 없습니다.")
        with subtab2:
            st.subheader("적용 파일 검색/AI 요약/음성 생성")
            applications = get_materials("application")
            next_topic = st.text_input("다음 토론 주제", placeholder="다음 독서 토론의 주제를 입력해주세요", key="next_topic_tts")
            if applications:
                application_options = [f"{a['book_title']} - {a['file_name']} ({a['created_at'].strftime('%Y-%m-%d')})" for a in applications]
                selected_idx = st.selectbox("적용 파일 선택 (최신순)", range(len(application_options)), format_func=lambda i: application_options[i], key="app_selectbox")
                selected_application = applications[selected_idx]
                st.write(f"### {selected_application['file_name']}")
                st.markdown(format_bullet_points(selected_application['content']))
                st.write(f"*등록일: {selected_application['created_at'].strftime('%Y-%m-%d')}*")
                extra_prompt_app = st.text_area("AI 프롬프트에 추가로 참고할 내용(선택)", key="app_extra_prompt", placeholder="특정 관점, 강조점, 추가 지시사항 등 자유롭게 입력하세요.", height=80)
                if st.button("AI 요약", key="app_ai_summary"):
                    with st.spinner("AI가 적용 파일을 요약 중입니다..."):
                        try:
                            ai_app_summary = ai_summarize_application_summary(selected_application['content'], st.session_state.selected_model, extra_prompt_app)
                            st.session_state['ai_app_summary_result'] = ai_app_summary
                        except Exception as e:
                            st.error(f"AI 요약 중 오류: {str(e)}")
                if st.session_state['ai_app_summary_result']:
                    st.markdown("### 적용 파일 요약 및 총평 (AI)")
                    st.markdown(st.session_state['ai_app_summary_result'])
                if st.button("음성 생성", key="app_tts"):
                    with st.spinner("음성을 생성하고 있습니다..."):
                        try:
                            opening_ment = "즐거운 독서토론 되셨는지요. 이번 독서토론의 적용 파일에 대한 AI 요약과 총평을 해 드리겠습니다."
                            closing_ment = f"다음 시간에는 {next_topic if next_topic else '다음 주제'}에 대한 독서 토론을 진행할 예정입니다."
                            tts_text = f"{opening_ment}\n" + (st.session_state.get('ai_app_summary_result') or '') + f"\n{closing_ment}"
                            summarized_text = summarize_for_tts(tts_text)
                            tts_app_audio = text_to_speech(summarized_text)
                            if tts_app_audio:
                                st.session_state['tts_app_audio'] = tts_app_audio
                        except Exception as e:
                            st.error(f"음성 생성 중 오류: {str(e)}")
                if st.session_state['tts_app_audio']:
                    st.markdown(st.session_state['tts_app_audio'], unsafe_allow_html=True)
            else:
                st.info("등록된 적용 파일이 없습니다.")

    with tab_order:
        discussion_order_tab()

def format_bullet_points(text):
    lines = text.split('\n')
    formatted = []
    for line in lines:
        # 제목(섹션) 강조: 굵게 처리
        if line.strip().startswith('#') or line.strip().startswith('**') or (line.strip() and not line.strip().startswith('•') and not line.strip().startswith('-')):
            formatted.append(f"**{line.strip().replace('#','').strip()}**")
        # bullet point
        elif '•' in line:
            parts = line.split('•')
            new_line = parts[0]
            for part in parts[1:]:
                if part.strip():
                    new_line += '\n• ' + part.strip()
            formatted.append(new_line)
        else:
            formatted.append(line)
    # 빈 줄 추가로 가독성 향상
    return '\n\n'.join([l for l in formatted if l.strip()])

def ai_summarize_keypoints(text, model_name, extra_prompt=None):
    summary_instruction = (
        "아래 텍스트에서 실제 비즈니스 업무 환경에 바로 적용할 수 있는 실전 핵심 내용 1~2가지만, 각 항목당 100자 이내의 bullet point(•)로 요약해 주세요. "
        "각 항목은 '~함' 형태의 한글로 작성하고, 존댓말은 사용하지 마세요. "
        "불필요한 설명 없이, 실무에서 바로 쓸 수 있는 구체적이고 실질적인 실천/적용 방안만 1~2개 bullet point로 제시해 주세요."
    )
    if model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=400)
        prompt = f"""
{summary_instruction}
---
{text}
"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.invoke([
            {"role": "system", "content": "당신은 비즈니스 실전 적용 요약 전문가입니다. 항상 실제 업무에 바로 적용할 수 있는 실천/적용 방안만 1~2개, 각 항목당 100자 이내로 bullet point로 '~함' 형태의 간결체로 작성합니다. 존댓말은 사용하지 않습니다. 불필요한 설명은 제외합니다."},
            {"role": "user", "content": prompt}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt = f"""
{summary_instruction}
---
{text}
"""
        if extra_prompt and extra_prompt.strip():
            prompt += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 비즈니스 실전 적용 요약 전문가입니다. 항상 실제 업무에 바로 적용할 수 있는 실천/적용 방안만 1~2개, 각 항목당 100자 이내로 bullet point로 '~함' 형태의 간결체로 작성합니다. 존댓말은 사용하지 않습니다. 불필요한 설명은 제외합니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.3
        )
        return response.choices[0].message.content

def ai_summarize_application_summary(text, model_name, extra_prompt=None):
    prompt = (
        "아래 적용 파일의 핵심 내용을 더 상세하게 요약해 주세요. 이어서, 총평의 제목은 반드시 '투명하고 진실한 조직 문화'로 하고, 그 아래에는 협업하는 조직 문화 만들기 관점에서 적용 파일에 대한 총평을 5줄 이내로 간결하게 작성해 주세요. 전체 분량은 약 2분 분량(요약은 상세하게, 총평은 간결하게)으로 해 주세요. 필요시 bullet point를 활용해도 좋습니다."
    )
    if model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=4096)
        prompt_full = f"{prompt}\n---\n{text}"
        if extra_prompt and extra_prompt.strip():
            prompt_full += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.invoke([
            {"role": "system", "content": "당신은 비즈니스 요약 및 평가 전문가입니다. 적용 파일의 핵심을 더 상세하게 요약하고, 총평의 제목은 반드시 '투명하고 진실한 조직 문화'로 하며, 그 아래에는 협업하는 조직 문화 만들기 관점에서 5줄 이내로 간결한 총평을 작성해 주세요."},
            {"role": "user", "content": prompt_full}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt_full = f"{prompt}\n---\n{text}"
        if extra_prompt and extra_prompt.strip():
            prompt_full += f"\n[참고 내용]\n{extra_prompt.strip()}\n"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 비즈니스 요약 및 평가 전문가입니다. 적용 파일의 핵심을 더 상세하게 요약하고, 총평의 제목은 반드시 '투명하고 진실한 조직 문화'로 하며, 그 아래에는 협업하는 조직 문화 만들기 관점에서 5줄 이내로 간결한 총평을 작성해 주세요."},
                {"role": "user", "content": prompt_full}
            ],
            max_tokens=4096,
            temperature=0.3
        )
        return response.choices[0].message.content

def is_pi_number_exists(pi_number):
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM proforma_invoices WHERE pi_number = %s", (pi_number,))
    exists = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    return exists

if __name__ == "__main__":
    # 타이머 종료 음성 메시지 준비 (앱 시작 시 한 번만)
    if 'order_end_audio' not in st.session_state:
        try:
            from openai import OpenAI
            import base64, os
            tts_text = "토론 시간이 종료되었습니다. 토론을 마무리해 주세요. 토론을 마무리해 주세요. 토론을 마무리해 주세요."
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=tts_text,
                speed=0.9
            )
            audio_data = response.content
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            st.session_state['order_end_audio'] = audio_base64
        except Exception as e:
            st.session_state['order_end_audio'] = ''
    main() 