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
import anthropic  # Anthropic 라이브러리 추가

# .env 파일 로드
load_dotenv()
st.title("🎙️ 회의록 작성 시스템")
# 인증 기능 (간단한 비밀번호 보호)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == os.getenv('ADMIN_PASSWORD', 'mds0118!'):  # 환경 변수에서 비밀번호 가져오기
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Gemini 클라이언트 초기화
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

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

def summarize_text(text, model_choice=None, reference_notes=None):
    """텍스트 요약 및 Action Items 추출"""
    try:
        model = model_choice or os.getenv('DEFAULT_AI_MODEL', 'claude-3-7-sonnet-latest')
        
        # 참고 사항이 있는 경우 프롬프트에 추가
        reference_prompt = ""
        if reference_notes and reference_notes.strip():
            reference_prompt = f"\n\n중요: 다음 참고 사항을 반드시 고려하여 요약해주세요: {reference_notes}"
        
        # Anthropic Claude 모델 사용
        if model.startswith('claude'):
            try:
                # 요약 생성
                summary_prompt = f"""다음 회의 내용을 요약해주세요.
                
{reference_prompt}

회의 내용:
{text}

요약 시 위의 참고 사항을 반드시 고려하여 작성해주세요. 다음 형식으로 정리해주세요:

1. 회의 요약 (핵심 내용 중심)
2. 주요 논의 사항 (bullet points)
3. 결정 사항"""

                summary_response = anthropic_client.messages.create(
                    model=model,
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": summary_prompt}
                    ]
                )
                
                summary = summary_response.content[0].text
                
                # Action Items 추출 - 더 명확한 지시 추가
                action_items_prompt = f"""다음 회의 내용에서 Action Items를 추출해주세요.
                
{reference_prompt}

회의 내용:
{text}

Action Items 추출 시 위의 참고 사항을 반드시 고려해주세요.

중요: 각 Action Item을 반드시 다음 형식으로 작성해주세요:
- Action Item 1
- Action Item 2
- Action Item 3

각 항목은 반드시 하이픈(-)으로 시작해야 합니다. 번호나 다른 기호를 사용하지 마세요.
최소 3개 이상의 Action Item을 추출해주세요."""

                action_items_response = anthropic_client.messages.create(
                    model=model,
                    max_tokens=500,
                    messages=[
                        {"role": "user", "content": action_items_prompt}
                    ]
                )
                
                action_items_text = action_items_response.content[0].text
                
                # 텍스트 파싱 개선
                action_items = []
                for line in action_items_text.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                        action_items.append(line.lstrip('-•* ').strip())
                
                # 파싱된 항목이 없으면 전체 텍스트를 분석하여 추출 시도
                if not action_items:
                    st.warning("Action Items 형식 파싱에 실패했습니다. 전체 텍스트에서 추출을 시도합니다.")
                    
                    # 전체 텍스트에서 "Action Item" 또는 유사한 키워드가 있는 줄 찾기
                    lines = action_items_text.split('\n')
                    for i, line in enumerate(lines):
                        if "action item" in line.lower() or "액션 아이템" in line.lower() or "조치 사항" in line.lower():
                            # 해당 줄 이후의 텍스트를 Action Items로 간주
                            for j in range(i+1, len(lines)):
                                item_line = lines[j].strip()
                                if item_line and not item_line.startswith('#') and not item_line.lower().startswith('action'):
                                    # 번호나 기호 제거
                                    clean_item = item_line
                                    for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '0.', '-', '*', '•', '○', '·']:
                                        if clean_item.startswith(prefix):
                                            clean_item = clean_item[len(prefix):].strip()
                                            break
                                    if clean_item:
                                        action_items.append(clean_item)
                
                # 여전히 Action Items가 없으면 GPT-4o-mini로 재시도
                if not action_items:
                    st.warning("Claude에서 Action Items 추출에 실패했습니다. GPT-4o-mini로 재시도합니다.")
                    
                    action_items_system_prompt = "회의 내용에서 Action Items만 추출하여 리스트로 작성해주세요."
                    
                    if reference_notes and reference_notes.strip():
                        action_items_system_prompt += f"\n\n중요: 다음 참고 사항을 반드시 고려하여 Action Items를 추출해주세요. 이 지침은 최우선으로 따라야 합니다:\n{reference_notes}"
                    
                    action_items_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": action_items_system_prompt},
                            {"role": "user", "content": text}
                        ],
                        max_tokens=500
                    )
                    action_items = action_items_response.choices[0].message.content.split('\n')
                    action_items = [item.strip('- ') for item in action_items if item.strip()]
                    
                    st.info("GPT-4o-mini를 사용하여 Action Items를 추출했습니다.")
                else:
                    st.success(f"Claude {model} 모델을 사용하여 요약 및 Action Items를 추출했습니다.")
                
                return summary, action_items
                
            except Exception as e:
                st.warning(f"Anthropic API 오류: {str(e)}. GPT-4o-mini로 대체합니다.")
                # Claude 실패 시 GPT-4o-mini로 폴백
                model = 'gpt-4o-mini'
        
        # Gemini 모델 사용
        elif model == 'gemini':
            try:
                # Gemini API 초기화 확인
                if not genai._configured:
                    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
                
                # 모델 생성 - 간단한 설정으로 시작
                gemini_model = genai.GenerativeModel('gemini-pro')
                
                # 요약 생성 - 참고 사항 포함 및 강조
                summary_prompt = f"""다음 회의 내용을 요약해주세요.
                
{reference_prompt}

회의 내용:
{text}

요약 시 위의 참고 사항을 반드시 고려하여 작성해주세요."""
                
                summary_response = gemini_model.generate_content(summary_prompt)
                
                if hasattr(summary_response, 'text'):
                    summary = summary_response.text
                else:
                    # 응답 형식이 다를 경우 대체 처리
                    summary = str(summary_response)
                
                # Action Items 추출 - 참고 사항 포함 및 강조
                action_items_prompt = f"""다음 회의 내용에서 Action Items를 추출해주세요.
                
{reference_prompt}

회의 내용:
{text}

Action Items 추출 시 위의 참고 사항을 반드시 고려해주세요."""
                
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
        
        # GPT-4o-mini 모델 사용 (다른 모델 실패 시 폴백 포함)
        if model == 'gpt-4o-mini':
            system_prompt = """
            회의 내용을 분석하여 다음 형식으로 정리해주세요:
            
            1. 회의 요약 (핵심 내용 중심)
            2. 주요 논의 사항 (bullet points)
            3. 결정 사항
            """
            
            # 참고 사항이 있는 경우 시스템 프롬프트에 추가 및 강조
            if reference_notes and reference_notes.strip():
                system_prompt += f"\n\n중요: 다음 참고 사항을 반드시 고려하여 요약해주세요. 이 지침은 최우선으로 따라야 합니다:\n{reference_notes}"
            
            summary_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000  # 비용 절감을 위한 토큰 제한
            )
            summary = summary_response.choices[0].message.content
            
            action_items_system_prompt = "회의 내용에서 Action Items만 추출하여 리스트로 작성해주세요."
            
            # 참고 사항이 있는 경우 Action Items 프롬프트에도 추가 및 강조
            if reference_notes and reference_notes.strip():
                action_items_system_prompt += f"\n\n중요: 다음 참고 사항을 반드시 고려하여 Action Items를 추출해주세요. 이 지침은 최우선으로 따라야 합니다:\n{reference_notes}"
            
            action_items_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": action_items_system_prompt},
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

def delete_meeting_record(meeting_id):
    """회의 기록 삭제"""
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
        
        query = "DELETE FROM meeting_records WHERE meeting_id = %s"
        cursor.execute(query, (meeting_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"데이터베이스 삭제 중 오류 발생: {str(e)}")
        return False

def process_text_file(file_content):
    """텍스트 파일 내용을 처리"""
    try:
        # 파일 내용을 문자열로 디코딩
        text = file_content.decode('utf-8')
        return text
    except UnicodeDecodeError:
        try:
            # UTF-8 디코딩 실패 시 다른 인코딩 시도
            text = file_content.decode('cp949')
            return text
        except Exception as e:
            st.error(f"텍스트 파일 디코딩 중 오류 발생: {str(e)}")
            return None

def main():
    
    
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
            # 미팅 형태와 제목 조합
            formatted_title = f"{meeting_type}-{title}" if meeting_type else title
            
            # DB에 저장
            if save_meeting_record(
                formatted_title,
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
        ["claude-3-7-sonnet-latest", "gpt-4o-mini", "gemini"],
        index=0  # Claude를 기본 모델로 설정
    )
    
    # 테이블 생성
    create_tables()
    
    # 탭 생성
    tab1, tab2 = st.tabs(["회의록 작성", "회의록 검색"])
    
    with tab1:
        st.header("회의록 작성")
        
        # 회의 정보 입력
        title = st.text_input("회의 제목")
        
        # 참석자 입력
        participants = st.text_area("참석자 (쉼표로 구분)")
        
        # 미팅 형태 선택 추가
        meeting_type = st.selectbox(
            "미팅 형태",
            ["사내 미팅", "외부 미팅", "독서 토론"],
            index=0,
            key="meeting_type_select"
        )
        
        # 독서 토론 기본 참고 사항
        reading_discussion_default = """핵심 논점 및 주요 의견: 각 참가자가 제시한 주요 관점과 핵심 논점을 중심으로 요약해 주세요.
의견 대립점: 토론 중 발생한 의견 차이나 대립되는 시각을 명확히 정리해 주세요.
새로운 인사이트: 토론을 통해 도출된 새로운 통찰이나 참신한 관점을 중심으로 요약해 주세요.
질문과 응답: 토론 중 제기된 중요한 질문과 그에 대한 응답을 요약해 주세요.
책과 현실의 연결점: 책의 내용이 현실 세계나 참가자들의 경험과 어떻게 연결되었는지 중심으로 요약해 주세요.
결론 및 합의점: 토론 결과 도출된 결론이나 참가자들이 동의한 핵심 포인트를 요약해 주세요.
후속 논의 주제: 이번 토론에서 완전히 다루지 못했거나 다음 토론에서 더 깊이 다룰 만한 주제를 정리해 주세요."""
        
        # 미팅 형태에 따른 참고 사항 기본값 설정
        if 'previous_meeting_type' not in st.session_state:
            st.session_state.previous_meeting_type = meeting_type
            st.session_state.reference_notes_value = reading_discussion_default if meeting_type == "독서 토론" else ""
        
        # 미팅 형태가 변경되었을 때 참고 사항 기본값 업데이트
        if st.session_state.previous_meeting_type != meeting_type:
            st.session_state.reference_notes_value = reading_discussion_default if meeting_type == "독서 토론" else ""
            st.session_state.previous_meeting_type = meeting_type
        
        # 참고 사항 입력 필드
        reference_notes = st.text_area(
            "회의록 요약 시 참고할 사항 (AI가 이 내용을 고려하여 요약합니다)",
            value=st.session_state.reference_notes_value,
            placeholder="예: 마케팅 전략에 중점을 두고 요약해주세요. / 신제품 출시 일정에 관한 내용을 중요하게 다뤄주세요.",
            height=250 if meeting_type == "독서 토론" else 100
        )
        
        # 참고 사항 값 저장
        st.session_state.reference_notes_value = reference_notes
        
        # 파일 업로드 - 음성 및 텍스트 파일 지원
        uploaded_file = st.file_uploader("회의 녹음 파일 또는 텍스트 파일 선택 (M4A, WAV, TXT, MD)", type=['m4a', 'wav', 'txt', 'md'])
        
        if uploaded_file is not None:
            # 파일 크기 표시
            file_size = uploaded_file.size / (1024 * 1024)  # MB로 변환
            st.write(f"📊 파일 크기: {file_size:.2f} MB")
            
            # 파일 확장자 확인
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
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
                        # 파일 형식에 따른 처리
                        if file_extension in ['m4a', 'wav']:
                            # 음성 파일 처리
                            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
                                tmp_file.write(uploaded_file.getvalue())
                                temp_path = tmp_file.name
                            
                            with st.spinner(f"{file_extension.upper()} 파일을 텍스트로 변환 중..."):
                                text = transcribe_large_audio(temp_path)
                                
                            # 임시 파일 삭제
                            if os.path.exists(temp_path):
                                os.unlink(temp_path)
                        else:
                            # 텍스트 파일 처리
                            with st.spinner("텍스트 파일 처리 중..."):
                                text = process_text_file(uploaded_file.getvalue())
                        
                        if text:
                            with st.spinner("텍스트 분석 중..."):
                                # 참고 사항을 summarize_text 함수에 전달
                                summary, action_items = summarize_text(text, model_choice, reference_notes)
                                
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
                        st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
                        st.session_state.analysis_started = False
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
        
        # 삭제 후 새로고침을 위한 상태 변수
        if 'refresh_records' not in st.session_state:
            st.session_state.refresh_records = False
            
        # 삭제 콜백 함수
        def delete_record(meeting_id):
            if delete_meeting_record(meeting_id):
                st.session_state.refresh_records = True
                st.success("회의록이 성공적으로 삭제되었습니다.")
            else:
                st.error("회의록 삭제에 실패했습니다.")
        
        # 삭제 후 새로고침
        if st.session_state.refresh_records:
            st.session_state.refresh_records = False
            st.rerun()
        
        # 검색 결과 표시
        records = get_meeting_records(search_query)
        
        if records:
            for record in records:
                with st.expander(f"📅 {record['created_at'].strftime('%Y-%m-%d %H:%M')} | {record['title']}", expanded=False):
                    # 회의록 내용 표시
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
                    
                    # 삭제 버튼 추가
                    st.markdown("### ⚠️ 회의록 관리")
                    delete_button_key = f"delete_button_{record['meeting_id']}"
                    
                    # 삭제 확인을 위한 체크박스
                    confirm_delete = st.checkbox(f"삭제 확인", key=f"confirm_{record['meeting_id']}")
                    
                    if confirm_delete:
                        if st.button("🗑️ 회의록 삭제", key=delete_button_key, type="primary", use_container_width=True):
                            delete_record(record['meeting_id'])
                    else:
                        st.button("🗑️ 회의록 삭제", key=delete_button_key, disabled=True, use_container_width=True)
                        st.caption("삭제하려면 먼저 '삭제 확인' 체크박스를 선택하세요.")
        else:
            st.info("검색 결과가 없습니다.")

if __name__ == "__main__":
    main() 