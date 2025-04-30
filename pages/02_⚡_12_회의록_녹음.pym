import streamlit as st
# 페이지 설정을 가장 먼저
st.set_page_config(page_title="회의록 작성 시스템", page_icon="🎙️", layout="wide")

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
import pydub
from pydub import AudioSegment
import math
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import numpy as np

# .env 파일 로드
load_dotenv()

# 세션 상태 초기화 - 최상단에 배치
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.recording = False
    st.session_state.start_time = None

# WebRTC 녹음을 위한 클래스
class AudioProcessor:
    def __init__(self):
        self.recording = False
        self.audio_file = None
        self.sample_rate = 16000
        self.frames = []
        self.frame_count = 0
        st.write("AudioProcessor initialized")

    def recv(self, frame):
        """WebRTC 프레임 수신 콜백"""
        try:
            # 프레임을 numpy 배열로 변환
            audio = frame.to_ndarray()
            
            # 프레임 수신 확인
            self.frame_count += 1
            if self.frame_count == 1:
                st.write(f"First frame received: shape={audio.shape}, dtype={audio.dtype}")
                st.write(f"Frame format: {frame.format.name}, Layout: {frame.layout.name}")

            # 녹음 중인 경우 프레임 저장
            if 'recording' in st.session_state and st.session_state.recording:
                # 프레임 데이터 저장 (모노로 변환)
                if len(audio.shape) > 1 and audio.shape[1] > 1:
                    audio = np.mean(audio, axis=1)
                self.frames.append(audio.copy())
                
                # 프레임 수 표시
                if len(self.frames) % 30 == 0:
                    st.write(f"Recording... Frames: {len(self.frames)}")

            return frame

        except Exception as e:
            st.error(f"Frame processing error: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return frame

    def start_recording(self):
        """녹음 시작"""
        try:
            self.recording = True
            self.frames = []
            self.frame_count = 0
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.audio_file = os.path.join(tempfile.gettempdir(), f"meeting_{timestamp}.wav")
            st.write("Recording started...")
        except Exception as e:
            st.error(f"Start recording error: {str(e)}")

    def stop_recording(self):
        """녹음 중지"""
        try:
            st.write(f"Stopping recording... Total frames: {len(self.frames)}")
            self.recording = False
            
            if len(self.frames) > 0:
                try:
                    # 모든 프레임을 하나의 배열로 결합
                    audio_data = np.concatenate(self.frames)
                    st.write(f"Audio data shape: {audio_data.shape}")
                    
                    # WAV 파일로 저장
                    with wave.open(self.audio_file, 'wb') as wave_file:
                        wave_file.setnchannels(1)
                        wave_file.setsampwidth(2)
                        wave_file.setframerate(self.sample_rate)
                        wave_file.writeframes(audio_data.tobytes())
                    
                    st.write(f"Audio saved successfully")
                    return self.audio_file
                except Exception as e:
                    st.error(f"Error saving audio: {str(e)}")
                    return None
            else:
                st.warning(f"No audio frames captured! (Total frames received: {self.frame_count})")
                return None
                
        except Exception as e:
            st.error(f"Stop recording error: {str(e)}")
            return None

# 전역 AudioProcessor 인스턴스 생성
processor = AudioProcessor()

def get_audio_processor():
    """AudioProcessor 인스턴스 반환"""
    global processor
    return processor

def main():
    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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
        
        # 녹음 상태 표시 컨테이너
        status_container = st.container()
        with status_container:
            status_placeholder = st.empty()
            time_placeholder = st.empty()
        
        try:
            # WebRTC 스트리머 설정
            webrtc_ctx = webrtc_streamer(
                key="audio-recorder",
                mode=WebRtcMode.SENDONLY,
                rtc_configuration=RTCConfiguration(
                    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
                ),
                media_stream_constraints={
                    "video": False,
                    "audio": {
                        "echoCancellation": True,
                        "noiseSuppression": True,
                        "autoGainControl": True
                    }
                },
                async_processing=True,
                audio_receiver_size=1024,
                video_processor_factory=None,
                audio_processor_factory=get_audio_processor
            )

            # 마이크 상태에 따른 안내 메시지
            if not webrtc_ctx.state.playing:
                status_placeholder.warning("⚠️ 'Start' 버튼을 눌러 마이크를 활성화해주세요.")
            else:
                # 녹음 제어 버튼
                if st.button("🎙️ 녹음 시작/중지", key="record_button"):
                    if not st.session_state.recording:
                        # 녹음 시작
                        processor.frames = []
                        processor.frame_count = 0
                        st.session_state.recording = True
                        st.session_state.start_time = datetime.now()
                        status_placeholder.info("🎙️ 녹음이 시작되었습니다...")
                    else:
                        # 녹음 중지
                        st.session_state.recording = False
                        st.session_state.start_time = None
                        
                        if len(processor.frames) > 0:
                            try:
                                # 오디오 저장 및 처리
                                audio_data = np.concatenate(processor.frames)
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                audio_file = os.path.join(tempfile.gettempdir(), f"meeting_{timestamp}.wav")
                                
                                with wave.open(audio_file, 'wb') as wave_file:
                                    wave_file.setnchannels(1)
                                    wave_file.setsampwidth(2)
                                    wave_file.setframerate(processor.sample_rate)
                                    wave_file.writeframes(audio_data.tobytes())
                                
                                # 오디오 재생 및 다운로드
                                with open(audio_file, 'rb') as f:
                                    audio_bytes = f.read()
                                    st.audio(audio_bytes, format="audio/wav")
                                    st.download_button(
                                        label="🎵 녹음 파일 다운로드",
                                        data=audio_bytes,
                                        file_name=f"meeting_{timestamp}.wav",
                                        mime="audio/wav"
                                    )
                            except Exception as e:
                                st.error(f"Error saving audio: {str(e)}")
                        else:
                            st.warning("No audio frames captured!")

            # 녹음 중인 경우 시간 표시
            if st.session_state.recording and st.session_state.start_time and webrtc_ctx.state.playing:
                current_time = datetime.now()
                duration = current_time - st.session_state.start_time
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                time_placeholder.info(f"⏱️ 녹음 시간: {minutes:02d}:{seconds:02d}")

        except Exception as e:
            st.error(f"녹음 중 오류가 발생했습니다: {str(e)}")
            st.session_state.recording = False
            st.session_state.start_time = None

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

def split_audio(audio_file, chunk_duration=300):  # 5분(300초) 단위로 분할
    """긴 오디오 파일을 작은 청크로 분할"""
    try:
        # 오디오 파일 로드
        audio = AudioSegment.from_wav(audio_file)
        
        # 청크 크기 계산 (5분 = 300,000ms)
        chunk_length_ms = chunk_duration * 1000
        chunks = []
        
        # 오디오를 청크로 분할
        for i in range(0, len(audio), chunk_length_ms):
            chunk = audio[i:i + chunk_length_ms]
            chunks.append(chunk)
            
        return chunks
    except Exception as e:
        st.error(f"오디오 분할 중 오류 발생: {str(e)}")
        return None

def transcribe_large_audio(audio_file):
    """큰 오디오 파일을 분할하여 텍스트로 변환"""
    try:
        # 파일 크기 확인
        file_size = os.path.getsize(audio_file) / (1024 * 1024)  # MB 단위
        
        if file_size <= 25:
            # 25MB 이하면 기존 방식으로 처리
            return transcribe_audio(audio_file)
        
        # 큰 파일은 청크로 분할
        chunks = split_audio(audio_file)
        if not chunks:
            return None
        
        # 진행 상태 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 각 청크를 임시 파일로 저장하고 변환
        transcripts = []
        for i, chunk in enumerate(chunks):
            status_text.text(f"음성 변환 중... ({i+1}/{len(chunks)})")
            
            # 임시 파일로 청크 저장
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                chunk.export(temp_file.name, format='wav')
                # 청크 변환
                chunk_transcript = transcribe_audio(temp_file.name)
                if chunk_transcript:
                    transcripts.append(chunk_transcript)
                
                # 임시 파일 삭제
                os.unlink(temp_file.name)
            
            # 진행률 업데이트
            progress_bar.progress((i + 1) / len(chunks))
        
        # 모든 텍스트 결합
        status_text.text("텍스트 결합 중...")
        full_transcript = ' '.join(transcripts)
        
        status_text.empty()
        progress_bar.empty()
        
        return full_transcript
    except Exception as e:
        st.error(f"음성 변환 중 오류 발생: {str(e)}")
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
        with st.spinner("녹음 파일을 저장하고 있습니다..."):
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
                file_size = os.path.getsize(filename)/1024/1024
                st.success(f"✅ 녹음 파일이 성공적으로 저장되었습니다. (크기: {file_size:.2f} MB)")
                
                # 다운로드 버튼 생성
                with open(filename, 'rb') as f:
                    audio_bytes = f.read()
                    st.download_button(
                        label="🎵 녹음 파일 다운로드",
                        data=audio_bytes,
                        file_name=f"meeting_{timestamp}.wav",
                        mime="audio/wav"
                    )
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

if __name__ == "__main__":
    main() 