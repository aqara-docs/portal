import streamlit as st
import os
import tempfile
import base64
from datetime import datetime
from openai import OpenAI
from pydub import AudioSegment
import json
from dotenv import load_dotenv
import mysql.connector
import google.generativeai as genai

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Gemini 클라이언트 초기화
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def create_tables():
    """데이터베이스 테이블 생성"""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
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
    except Exception as e:
        st.error(f"데이터베이스 테이블 생성 중 오류 발생: {str(e)}")

def save_meeting_record(title, participants, audio_path, full_text, summary, action_items):
    """회의 기록 저장"""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
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
        conn.close()
        return True
    except Exception as e:
        st.error(f"데이터베이스 저장 중 오류 발생: {str(e)}")
        return False

def get_meeting_records(search_query=None):
    """회의 기록 조회"""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        cursor = conn.cursor(dictionary=True)
        
        if search_query:
            query = """
                SELECT * FROM meeting_records 
                WHERE title LIKE %s OR full_text LIKE %s OR summary LIKE %s
                ORDER BY created_at DESC
            """
            search_term = f"%{search_query}%"
            cursor.execute(query, (search_term, search_term, search_term))
        else:
            cursor.execute("SELECT * FROM meeting_records ORDER BY created_at DESC")
        
        records = cursor.fetchall()
        conn.close()
        return records
    except Exception as e:
        st.error(f"데이터베이스 조회 중 오류 발생: {str(e)}")
        return []

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

def split_audio(audio_file, chunk_duration=300):
    """긴 오디오 파일을 작은 청크로 분할"""
    try:
        # FFmpeg 의존성 확인
        try:
            # m4a 파일을 wav로 변환
            audio = AudioSegment.from_file(audio_file, format="m4a")
        except Exception as e:
            st.error(f"FFmpeg 오류: {str(e)}")
            st.info("FFmpeg이 설치되어 있지 않습니다. 전체 파일을 한 번에 처리합니다.")
            # FFmpeg 없이 파일 전체를 반환
            return [audio_file]  # 파일 경로 자체를 반환
        
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
        
        if file_size <= 24:  # 25MB 미만으로 안전하게 설정
            # 작은 파일은 기존 방식으로 처리
            return transcribe_audio(audio_file)
        
        # 파일 확장자 확인
        file_extension = os.path.splitext(audio_file)[1].lower()
        
        # 큰 파일은 분할 처리
        st.warning(f"파일 크기가 {file_size:.2f}MB로 OpenAI 제한(25MB)을 초과합니다. 파일을 분할하여 처리합니다.")
        
        # 진행 상태 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            from pydub import AudioSegment
            
            # 오디오 파일 로드 시도
            try:
                if file_extension == '.m4a':
                    audio = AudioSegment.from_file(audio_file, format="m4a")
                elif file_extension == '.wav':
                    audio = AudioSegment.from_file(audio_file, format="wav")
                else:
                    audio = AudioSegment.from_file(audio_file)
            except Exception as load_error:
                # FFmpeg 오류 발생 시 명확한 메시지 표시 후 종료
                if "ffprobe" in str(load_error).lower() or "ffmpeg" in str(load_error).lower():
                    st.error("FFmpeg가 설치되어 있지 않아 오디오 파일을 처리할 수 없습니다.")
                    st.info("FFmpeg를 설치하거나 25MB 이하의 WAV 파일로 변환한 후 다시 시도해주세요.")
                    progress_bar.empty()
                    status_text.empty()
                    return None
                else:
                    # 기타 오류 재발생
                    raise load_error
            
            # 오디오 압축 (모노로 변환, 샘플레이트 낮춤)
            compressed_audio = audio.set_channels(1).set_frame_rate(16000)
            
            # 오디오 길이 확인
            duration_ms = len(compressed_audio)
            
            # 필요한 청크 수 계산 (파일 크기 기반)
            # 원본 파일 크기를 기준으로 청크 수 결정 (안전하게 10MB 단위로 분할)
            chunk_size_target = 10  # MB (안전하게 10MB로 설정)
            num_chunks = max(5, int(file_size / chunk_size_target) + 1)
            
            st.info(f"파일 크기: {file_size:.1f}MB, 분할할 청크 수: {num_chunks}개")
            status_text.text(f"파일을 {num_chunks}개 청크로 분할합니다.")
            
            # 청크 지속 시간 계산
            chunk_duration = duration_ms // num_chunks
            
            # 청크 분할 및 처리
            transcripts = []
            for i in range(num_chunks):
                start_ms = i * chunk_duration
                end_ms = min((i + 1) * chunk_duration, duration_ms)
                
                chunk = compressed_audio[start_ms:end_ms]
                
                status_text.text(f"청크 변환 중... ({i+1}/{num_chunks})")
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as chunk_file:
                    # 추가 압축 설정 (비트레이트 낮춤)
                    chunk.export(chunk_file.name, format='wav', 
                                parameters=["-ac", "1", "-ar", "16000", "-b:a", "32k"])
                    
                    # 청크 크기 확인
                    chunk_size = os.path.getsize(chunk_file.name) / (1024 * 1024)
                    
                    # 청크가 여전히 너무 크면 더 작게 분할
                    if chunk_size > 24:
                        st.warning(f"청크 {i+1} 크기가 {chunk_size:.1f}MB로 여전히 큽니다. 추가 분할합니다.")
                        
                        # 임시 파일 삭제
                        os.unlink(chunk_file.name)
                        
                        # 청크를 2개로 추가 분할
                        sub_duration = len(chunk)
                        half_duration = sub_duration // 2
                        
                        # 첫 번째 하위 청크
                        sub_chunk1 = chunk[:half_duration]
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as sub_file1:
                            sub_chunk1.export(sub_file1.name, format='wav', 
                                            parameters=["-ac", "1", "-ar", "16000", "-b:a", "24k"])
                            
                            sub_size1 = os.path.getsize(sub_file1.name) / (1024 * 1024)
                            st.info(f"하위 청크 {i+1}.1 크기: {sub_size1:.1f}MB")
                            
                            if sub_size1 <= 24:
                                # 하위 청크 변환
                                sub_transcript1 = transcribe_audio(sub_file1.name)
                                if sub_transcript1:
                                    transcripts.append(sub_transcript1)
                            else:
                                st.error(f"하위 청크 {i+1}.1도 너무 큽니다({sub_size1:.1f}MB). 이 부분은 건너뜁니다.")
                            
                            os.unlink(sub_file1.name)
                        
                        # 두 번째 하위 청크
                        sub_chunk2 = chunk[half_duration:]
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as sub_file2:
                            sub_chunk2.export(sub_file2.name, format='wav', 
                                            parameters=["-ac", "1", "-ar", "16000", "-b:a", "24k"])
                            
                            sub_size2 = os.path.getsize(sub_file2.name) / (1024 * 1024)
                            st.info(f"하위 청크 {i+1}.2 크기: {sub_size2:.1f}MB")
                            
                            if sub_size2 <= 24:
                                # 하위 청크 변환
                                sub_transcript2 = transcribe_audio(sub_file2.name)
                                if sub_transcript2:
                                    transcripts.append(sub_transcript2)
                            else:
                                st.error(f"하위 청크 {i+1}.2도 너무 큽니다({sub_size2:.1f}MB). 이 부분은 건너뜁니다.")
                            
                            os.unlink(sub_file2.name)
                    else:
                        # 청크 크기 표시
                        st.info(f"청크 {i+1} 크기: {chunk_size:.1f}MB")
                        
                        # 청크 변환
                        chunk_transcript = transcribe_audio(chunk_file.name)
                        if chunk_transcript:
                            transcripts.append(chunk_transcript)
                        
                        # 임시 파일 삭제
                        os.unlink(chunk_file.name)
                
                # 진행률 업데이트
                progress_bar.progress((i + 1) / num_chunks)
            
            # 모든 텍스트 결합
            status_text.text("텍스트 결합 중...")
            full_transcript = ' '.join(transcripts)
            
            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()
            
            return full_transcript
            
        except Exception as e:
            st.error(f"오디오 처리 중 오류 발생: {str(e)}")
            
            # FFmpeg 관련 오류인 경우
            if "ffprobe" in str(e).lower() or "ffmpeg" in str(e).lower():
                st.warning("FFmpeg가 설치되어 있지 않아 오디오 파일을 처리할 수 없습니다.")
                st.info("FFmpeg를 설치하거나 25MB 이하의 WAV 파일로 변환한 후 다시 시도해주세요.")
            
            # 진행 표시 제거
            progress_bar.empty()
            status_text.empty()
            return None
            
    except Exception as e:
        st.error(f"음성 변환 중 오류 발생: {str(e)}")
        return None

def summarize_text(text, model_choice=None):
    """텍스트 요약 및 Action Items 추출"""
    try:
        model = model_choice or os.getenv('DEFAULT_AI_MODEL', 'gpt-4o-mini')
        
        if model == 'gemini':
            try:
                # Gemini API 초기화 확인
                if not genai._configured:
                    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
                
                # 모델 생성 - 간단한 설정으로 시작
                gemini_model = genai.GenerativeModel('gemini-pro')
                
                # 요약 생성 - 간단한 프롬프트로 시작
                summary_prompt = "다음 회의 내용을 요약해주세요:\n\n" + text
                summary_response = gemini_model.generate_content(summary_prompt)
                
                if hasattr(summary_response, 'text'):
                    summary = summary_response.text
                else:
                    # 응답 형식이 다를 경우 대체 처리
                    summary = str(summary_response)
                
                # Action Items 추출 - 간단한 프롬프트로 시작
                action_items_prompt = "다음 회의 내용에서 Action Items를 추출해주세요:\n\n" + text
                action_items_response = gemini_model.generate_content(action_items_prompt)
                
                if hasattr(action_items_response, 'text'):
                    action_items_text = action_items_response.text
                else:
                    action_items_text = str(action_items_response)
                
                # 텍스트 파싱
                action_items = []
                for line in action_items_text.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•')):
                        action_items.append(line.lstrip('-•').strip())
                
                st.success("Gemini 모델을 사용하여 요약했습니다.")
                return summary, action_items
                
            except Exception as e:
                st.warning(f"Gemini API 오류: {str(e)}. GPT-4o-mini로 대체합니다.")
                # Gemini 실패 시 GPT-4o-mini로 폴백
                model = 'gpt-4o-mini'
        
        # GPT-4o-mini 모델 사용 (Gemini 실패 시 폴백 포함)
        if model == 'gpt-4o-mini':
            summary_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                    회의 내용을 분석하여 다음 형식으로 정리해주세요:
                    
                    1. 회의 요약 (핵심 내용 중심)
                    2. 주요 논의 사항 (bullet points)
                    3. 결정 사항
                    """},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000  # 비용 절감을 위한 토큰 제한
            )
            summary = summary_response.choices[0].message.content
            
            action_items_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "회의 내용에서 Action Items만 추출하여 리스트로 작성해주세요."},
                    {"role": "user", "content": text}
                ],
                max_tokens=500  # 비용 절감을 위한 토큰 제한
            )
            action_items = action_items_response.choices[0].message.content.split('\n')
            action_items = [item.strip('- ') for item in action_items if item.strip()]
            
            st.success("GPT-4o-mini 모델을 사용하여 요약했습니다.")
        
        return summary, action_items
    except Exception as e:
        st.error(f"텍스트 요약 중 오류 발생: {str(e)}")
        return None, None

def create_download_link(content, filename, text):
    """다운로드 링크 생성"""
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'

def generate_markdown(title, date, participants, summary, action_items, full_text):
    """마크다운 파일 생성"""
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
    
    if action_items:
        sections.extend([f"- {item}" for item in action_items])
    else:
        sections.append("없음")
    
    sections.extend([
        "",
        "## 전체 내용",
        full_text
    ])
    
    return "\n".join(sections)

def main():
    st.title("🎙️ 회의록 작성 시스템")
    
    # 세션 상태 초기화 (앱 시작 시 한 번만)
    if 'action_items_list' not in st.session_state:
        st.session_state.action_items_list = []
    
    if 'summary_text' not in st.session_state:
        st.session_state.summary_text = ""
    
    if 'full_transcript' not in st.session_state:
        st.session_state.full_transcript = ""
    
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    
    if 'save_clicked' not in st.session_state:
        st.session_state.save_clicked = False
    
    # 저장 함수 정의 - 실제 저장 로직을 여기서 처리
    def save_meeting_record_callback():
        if title and participants:
            # DB에 저장
            if save_meeting_record(
                title,
                participants.split(','),
                temp_path if 'temp_path' in locals() else "",
                st.session_state.full_transcript,
                st.session_state.summary_text,
                st.session_state.action_items_list
            ):
                st.session_state.save_success = True
            else:
                st.session_state.save_success = False
    
    # AI 모델 선택
    model_choice = st.sidebar.selectbox(
        "AI 모델 선택",
        ["gpt-4o-mini", "gemini"],
        index=0 if os.getenv('DEFAULT_AI_MODEL') == 'gpt-4o-mini' else 1
    )
    
    # 테이블 생성
    create_tables()
    
    # 탭 생성
    tab1, tab2 = st.tabs(["회의록 작성", "회의록 검색"])
    
    with tab1:
        st.header("회의록 작성")
        
        # 회의 정보 입력
        title = st.text_input("회의 제목")
        participants = st.text_area("참석자 (쉼표로 구분)")
        
        # 오디오 파일 업로드 - WAV 파일 추가
        uploaded_file = st.file_uploader("회의 녹음 파일 선택 (M4A, WAV)", type=['m4a', 'wav'])
        
        if uploaded_file is not None:
            # 파일 크기 표시
            file_size = uploaded_file.size / (1024 * 1024)  # MB로 변환
            st.write(f"📊 파일 크기: {file_size:.2f} MB")
            
            # 파일 확장자 확인
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                temp_path = tmp_file.name
            
            # AI 분석 상태를 위한 placeholder
            analysis_status = st.empty()
            
            # 분석 함수 정의
            def start_analysis():
                st.session_state.analysis_started = True
            
            # 분석 버튼
            if not st.session_state.analysis_complete:
                st.button("AI 분석 시작", on_click=start_analysis, use_container_width=True)
            
            # 분석 시작 상태 확인
            if 'analysis_started' not in st.session_state:
                st.session_state.analysis_started = False
            
            if st.session_state.analysis_started and not st.session_state.analysis_complete:
                if title and participants:
                    # 즉시 분석 시작 메시지 표시
                    analysis_status.info("🤖 AI 분석이 시작되었습니다...")
                    
                    try:
                        with st.spinner(f"{file_extension.upper()} 파일을 텍스트로 변환 중..."):
                            text = transcribe_large_audio(temp_path)
                            
                        if text:
                            with st.spinner("텍스트 분석 중..."):
                                summary, action_items = summarize_text(text, model_choice)
                                
                                if summary:
                                    # 분석 결과를 세션 상태에 저장
                                    st.session_state.summary_text = summary
                                    st.session_state.full_transcript = text
                                    st.session_state.action_items_list = action_items.copy() if action_items else []
                                    st.session_state.analysis_complete = True
                                    st.session_state.analysis_started = False  # 분석 완료 후 초기화
                                    
                                    # 페이지 새로고침
                                    st.rerun()
                    except Exception as e:
                        st.error(f"음성 변환 중 오류가 발생했습니다: {str(e)}")
                        st.session_state.analysis_started = False
                    finally:
                        # 임시 파일 삭제
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                else:
                    analysis_status.error("❗ 회의 제목과 참석자 정보가 필요합니다.")
                    st.session_state.analysis_started = False
            
            # 분석 완료 후 결과 표시
            if st.session_state.analysis_complete:
                st.success("✅ 분석이 완료되었습니다. 결과를 검토해주세요.")
                
                # 결과 표시
                st.subheader("📝 회의록")
                st.write(st.session_state.summary_text)
                
                # Action Items 편집 및 표시
                st.subheader("✅ Action Items")
                
                # 현재 Action Items 표시
                action_items_text = st.text_area(
                    "Action Items (각 항목을 새 줄에 입력하세요)",
                    value="\n".join(st.session_state.action_items_list),
                    height=200,
                    key="action_items_editor"
                )
                
                # 텍스트 영역에서 Action Items 파싱 및 세션 상태에 저장
                st.session_state.action_items_list = [item.strip() for item in action_items_text.split('\n') if item.strip()]
                
                # 저장 버튼
                st.button("회의록 저장", on_click=save_meeting_record_callback, use_container_width=True, type="primary")
                
                # 저장 성공 메시지 표시
                if 'save_success' in st.session_state and st.session_state.save_success:
                    st.success("✅ 회의록이 성공적으로 저장되었습니다.")
                    
                    # 다운로드 옵션
                    st.markdown("### 📥 다운로드")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 텍스트 파일 다운로드
                        text_content = "\n".join([
                            f"회의록: {title}",
                            f"날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                            f"참석자: {participants}",
                            "",
                            "=== 회의 요약 ===",
                            st.session_state.summary_text,
                            "",
                            "=== Action Items ===",
                            "\n".join([f"• {item}" for item in st.session_state.action_items_list]),
                            "",
                            "=== 전체 내용 ===",
                            st.session_state.full_transcript
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
                                st.session_state.summary_text,
                                st.session_state.action_items_list,
                                st.session_state.full_transcript
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
                
                # 저장 실패 메시지 표시
                elif 'save_success' in st.session_state and not st.session_state.save_success:
                    st.error("❌ 회의록 저장에 실패했습니다.")
    
    with tab2:
        st.header("회의록 검색")
        
        # 검색 필터
        search_query = st.text_input("검색어 입력 (제목, 내용, 요약)")
        
        # 검색 결과 표시
        records = get_meeting_records(search_query)
        
        if records:
            for record in records:
                with st.expander(f"📅 {record['created_at'].strftime('%Y-%m-%d %H:%M')} | {record['title']}", expanded=False):
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
                            f"날짜: {record['created_at'].strftime('%Y-%m-%d %H:%M')}",
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
                                f"회의록_{record['created_at'].strftime('%Y%m%d_%H%M')}.txt",
                                "📄 텍스트 파일 다운로드"
                            ),
                            unsafe_allow_html=True
                        )
                    
                    with col2:
                        # 마크다운 파일 다운로드
                        try:
                            markdown_content = generate_markdown(
                                record['title'],
                                record['created_at'].strftime('%Y-%m-%d %H:%M'),
                                json.loads(record['participants']),
                                record['summary'],
                                json.loads(record['action_items']),
                                record['full_text']
                            )
                            
                            st.markdown(
                                create_download_link(
                                    markdown_content,
                                    f"회의록_{record['created_at'].strftime('%Y%m%d_%H%M')}.md",
                                    "📝 마크다운 파일 다운로드"
                                ),
                                unsafe_allow_html=True
                            )
                        except Exception as e:
                            st.error(f"마크다운 생성 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main() 