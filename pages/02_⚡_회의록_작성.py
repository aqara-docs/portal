import streamlit as st
from audio_recorder_streamlit import audio_recorder
import os
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import json
from openai import OpenAI
import tempfile
import time
import queue
import threading
import wave
import base64
from fpdf import FPDF
import io

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 페이지 설정
st.set_page_config(page_title="회의록 작성 시스템", page_icon="🎙️", layout="wide")

# 녹음 관련 전역 변수
SAMPLE_RATE = 48000
CHANNELS = 1
audio_frames = []

# 녹음 상태 관리를 위한 session_state 초기화
if 'recording_started' not in st.session_state:
    st.session_state.recording_started = False
if 'recording_start_time' not in st.session_state:
    st.session_state.recording_start_time = None

class AudioRecorder:
    def __init__(self):
        self.audio_frames = []
        self.recording = False
        self.audio_queue = queue.Queue()

    def recorder_factory(self):
        def callback(frame: av.AudioFrame) -> av.AudioFrame:
            if self.recording:
                audio_data = frame.to_ndarray()
                self.audio_queue.put(audio_data)
            return frame
        return callback

    def save_audio(self, filename):
        with wave.open(filename, 'wb') as wave_file:
            wave_file.setnchannels(CHANNELS)
            wave_file.setsampwidth(2)  # 16-bit audio
            wave_file.setframerate(SAMPLE_RATE)
            
            while not self.audio_queue.empty():
                audio_chunk = self.audio_queue.get()
                wave_file.writeframes(audio_chunk.tobytes())

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def create_tables():
    """필요한 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_records (
            meeting_id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            date DATETIME NOT NULL,
            participants TEXT,
            audio_path VARCHAR(255),
            full_text TEXT,
            summary TEXT,
            action_items TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def save_meeting_record(title, participants, audio_path, full_text, summary, action_items):
    """회의 기록 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        query = """
        INSERT INTO meeting_records 
        (title, date, participants, audio_path, full_text, summary, action_items)
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            title,
            json.dumps(participants, ensure_ascii=False),
            audio_path,
            full_text,
            summary,
            json.dumps(action_items, ensure_ascii=False)
        ))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
        return False
    finally:
        conn.close()

def get_meeting_records(search_query=""):
    """회의 기록 검색"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        if search_query:
            query = """
            SELECT * FROM meeting_records 
            WHERE title LIKE %s OR full_text LIKE %s OR summary LIKE %s
            ORDER BY date DESC
            """
            cursor.execute(query, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
        else:
            query = "SELECT * FROM meeting_records ORDER BY date DESC"
            cursor.execute(query)
        
        return cursor.fetchall()
    except Exception as e:
        st.error(f"검색 중 오류가 발생했습니다: {str(e)}")
        return []
    finally:
        conn.close()

def transcribe_audio(audio_file):
    """음성을 텍스트로 변환"""
    try:
        with open(audio_file, "rb") as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                language="ko"
            )
        return transcript.text
    except Exception as e:
        st.error(f"음성 변환 중 오류가 발생했습니다: {str(e)}")
        return None

def summarize_text(text):
    """텍스트 요약 및 액션 아이템 추출"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """
                회의 내용을 분석하여 다음 형식으로 정리해주세요:
                
                1. 회의 요약 (핵심 내용 중심)
                2. 주요 논의 사항 (bullet points)
                3. 결정 사항
                4. Action Items (담당자/기한 포함)
                """},
                {"role": "user", "content": text}
            ],
            temperature=0.7
        )
        
        summary = response.choices[0].message.content
        
        # Action Items 추출
        action_items = []
        for line in summary.split('\n'):
            if "Action Items" in line or "담당자" in line or "기한" in line:
                action_items.append(line.strip())
        
        return summary, action_items
    except Exception as e:
        st.error(f"텍스트 요약 중 오류가 발생했습니다: {str(e)}")
        return None, []

def save_audio_bytes(audio_bytes):
    """오디오 바이트를 파일로 저장"""
    if not audio_bytes:
        return None
        
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        filename = os.path.join(temp_dir, f"meeting_{timestamp}.wav")
        
        # 파일 크기 검증
        if len(audio_bytes) < 100:  # 최소 크기 검증
            st.error("녹음 파일이 너무 작습니다.")
            return None
            
        with open(filename, 'wb') as f:
            f.write(audio_bytes)
            
        # 저장된 파일 검증
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            st.info(f"녹음 파일이 저장되었습니다. (크기: {os.path.getsize(filename)/1024/1024:.2f} MB)")
            return filename
        else:
            st.error("파일 저장에 실패했습니다.")
            return None
            
    except Exception as e:
        st.error(f"오디오 파일 저장 중 오류가 발생했습니다: {str(e)}")
        return None

def create_download_link(content, filename, text):
    """다운로드 링크 생성"""
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'

def generate_markdown(title, date, participants, summary, action_items, full_text):
    """마크다운 파일 생성"""
    # 각 섹션을 리스트로 만들어 join
    sections = [
        f"# 회의록: {title}",
        "",
        "## 기본 정보",
        f"- 날짜: {date}",
        f"- 참석자: {', '.join(participants)}",
        "",
        "## 회의 요약",
        summary,
        "",
        "## Action Items"
    ]
    
    # Action Items 추가
    if action_items:
        sections.extend([f"- {item}" for item in action_items])
    else:
        sections.append("없음")
    
    # 전체 내용 추가
    sections.extend([
        "",
        "## 전체 내용",
        full_text
    ])
    
    # 모든 섹션을 줄바꿈으로 연결
    return "\n".join(sections)

def main():
    st.title("🎙️ 회의록 작성 시스템")
    
    # 테이블 생성
    create_tables()
    
    # 탭 생성
    tab1, tab2 = st.tabs(["회의 녹음/기록", "회의록 검색"])
    
    with tab1:
        st.header("회의 녹음 및 기록")
        
        # 회의 정보 입력
        title = st.text_input("회의 제목")
        participants = st.text_area("참석자 (쉼표로 구분)")
        
        # 녹음 컴포넌트
        st.write("🎙️ 녹음 시작/중지")
        
        # 녹음 시간 표시 컨테이너
        time_placeholder = st.empty()
        
        # 녹음 컴포넌트
        audio_bytes = audio_recorder(
            pause_threshold=1800.0,  # 30분으로 증가 (초 단위)
            energy_threshold=0.01,
            recording_color="#e74c3c",
            neutral_color="#95a5a6",
            sample_rate=16000  # 샘플레이트를 낮춰서 파일 크기 감소
        )

        # 녹음 상태 및 시간 관리
        if audio_bytes:
            if not st.session_state.recording_started:
                st.session_state.recording_started = True
                st.session_state.recording_start_time = datetime.now()
            
            try:
                # 녹음 시간 계산
                current_time = datetime.now()
                recording_duration = current_time - st.session_state.recording_start_time
                minutes = int(recording_duration.total_seconds() // 60)
                seconds = int(recording_duration.total_seconds() % 60)
                
                # 파일 크기 확인
                file_size = len(audio_bytes)
                
                # 상태 표시
                time_placeholder.info(f"⏱️ 녹음 시간: {minutes:02d}:{seconds:02d}")
                st.write(f"📊 파일 크기: {file_size/1024/1024:.2f} MB")
                
                if minutes >= 28:  # 28분 이상 녹음시 경고
                    st.warning("⚠️ 녹음 시간이 28분을 초과했습니다. 곧 새로운 녹음을 시작하는 것을 추천합니다.")
                
                # 최소 파일 크기 검증 (1KB)
                if file_size > 1024:
                    st.audio(audio_bytes, format="audio/wav")
                    st.session_state.audio_file = save_audio_bytes(audio_bytes)
                    if st.session_state.audio_file:
                        st.success("✅ 녹음이 완료되었습니다.")
                        # 녹음 상태 초기화
                        st.session_state.recording_started = False
                        st.session_state.recording_start_time = None
                else:
                    st.warning("⚠️ 녹음 시간이 너무 짧습니다. 더 길게 녹음해주세요.")
                    
            except Exception as e:
                st.error(f"녹음 처리 중 오류가 발생했습니다: {str(e)}")
                # 오류 발생시 상태 초기화
                st.session_state.recording_started = False
                st.session_state.recording_start_time = None
        
        # 분석 버튼
        if st.button("AI 분석 시작", use_container_width=True):
            if 'audio_file' in st.session_state and title and participants:
                with st.spinner("음성을 텍스트로 변환 중..."):
                    text = transcribe_audio(st.session_state.audio_file)
                    
                if text:
                    with st.spinner("텍스트 분석 중..."):
                        summary, action_items = summarize_text(text)
                        
                        if summary:
                            # DB에 저장
                            if save_meeting_record(
                                title,
                                participants.split(','),
                                st.session_state.audio_file,
                                text,
                                summary,
                                action_items
                            ):
                                st.success("회의록이 저장되었습니다.")
                                
                                # 결과 표시
                                st.subheader("📝 회의록")
                                st.write(summary)
                                
                                if action_items:
                                    st.subheader("✅ Action Items")
                                    for item in action_items:
                                        st.write(item)
                                
                                # 다운로드 옵션
                                st.markdown("### 📥 다운로드")
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    # 텍스트 파일 다운로드
                                    text_content = "\n".join([
                                        f"회의록: {title}",
                                        f"날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                                        f"참석자: {', '.join(participants.split(','))}",
                                        "",
                                        "=== 회의 요약 ===",
                                        summary,
                                        "",
                                        "=== Action Items ===",
                                        "\n".join([f"• {item}" for item in action_items]),
                                        "",
                                        "=== 전체 내용 ===",
                                        text
                                    ])
                                    st.markdown(
                                        create_download_link(
                                            text_content, 
                                            f"회의록_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                            "📄 텍스트 파일 다운로드"
                                        ),
                                        unsafe_allow_html=True
                                    )
                                
                                with col2:
                                    # 마크다운 파일 다운로드
                                    try:
                                        markdown_content = generate_markdown(
                                            title,
                                            datetime.now().strftime('%Y-%m-%d %H:%M'),
                                            participants.split(','),
                                            summary,
                                            action_items,
                                            text
                                        )
                                        
                                        st.markdown(
                                            create_download_link(
                                                markdown_content, 
                                                f"회의록_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                                                "📝 마크다운 파일 다운로드"
                                            ),
                                            unsafe_allow_html=True
                                        )
                                    except Exception as e:
                                        st.error(f"마크다운 생성 중 오류가 발생했습니다: {str(e)}")
            else:
                st.error("회의 제목, 참석자 정보, 녹음 파일이 모두 필요합니다.")
    
    with tab2:
        st.header("회의록 검색")
        
        # 검색 필터
        search_query = st.text_input("검색어 입력 (제목, 내용, 요약)")
        
        # 검색 결과 표시
        records = get_meeting_records(search_query)
        
        if records:
            for record in records:
                with st.expander(f"📅 {record['date'].strftime('%Y-%m-%d %H:%M')} | {record['title']}", expanded=False):
                    st.write("**참석자:**", ", ".join(json.loads(record['participants'])))
                    st.write("**회의 요약:**")
                    st.write(record['summary'])
                    
                    if record['action_items']:
                        st.write("**Action Items:**")
                        for item in json.loads(record['action_items']):
                            st.write(f"- {item}")
                    
                    st.write("**전체 내용:**")
                    st.write(record['full_text'])
                    
                    # 다운로드 옵션
                    st.markdown("### 📥 다운로드")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 텍스트 파일 다운로드
                        text_content = "\n".join([
                            f"회의록: {record['title']}",
                            f"날짜: {record['date'].strftime('%Y-%m-%d %H:%M')}",
                            f"참석자: {', '.join(json.loads(record['participants']))}",
                            "",
                            "=== 회의 요약 ===",
                            record['summary'],
                            "",
                            "=== Action Items ===",
                            "\n".join([f"• {item}" for item in json.loads(record['action_items'])]),
                            "",
                            "=== 전체 내용 ===",
                            record['full_text']
                        ])
                        st.markdown(
                            create_download_link(
                                text_content, 
                                f"회의록_{record['date'].strftime('%Y%m%d_%H%M')}.txt",
                                "📄 텍스트 파일 다운로드"
                            ),
                            unsafe_allow_html=True
                        )
                    
                    with col2:
                        # 마크다운 파일 다운로드
                        try:
                            markdown_content = generate_markdown(
                                record['title'],
                                record['date'].strftime('%Y-%m-%d %H:%M'),
                                json.loads(record['participants']),
                                record['summary'],
                                json.loads(record['action_items']),
                                record['full_text']
                            )
                            
                            st.markdown(
                                create_download_link(
                                    markdown_content, 
                                    f"회의록_{record['date'].strftime('%Y%m%d_%H%M')}.md",
                                    "📝 마크다운 파일 다운로드"
                                ),
                                unsafe_allow_html=True
                            )
                        except Exception as e:
                            st.error(f"마크다운 생성 중 오류가 발생했습니다: {str(e)}")
        else:
            st.info("검색 결과가 없습니다.")

if __name__ == "__main__":
    main() 