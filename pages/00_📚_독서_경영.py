import streamlit as st
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import base64
import hashlib
import re
import time
import openai
from openai import OpenAI
import io
import requests

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

st.set_page_config(page_title="🎵 이야기 재생 전용", layout="wide")

st.title("🎵 독서 경영-이야기 재생 전용")

# DB 연결 함수
def connect_to_db():
    try:
        connection = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

# 텍스트 포맷팅 함수
def format_bullet_points(text):
    """텍스트를 bullet point 형태로 포맷팅"""
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
    return '\n'.join(formatted)

# AI 컨텐츠 파싱 함수
def parse_ai_content(ai_content, content_type):
    """AI 컨텐츠를 파싱하여 구분된 섹션으로 반환"""
    if not ai_content:
        return None, None
    
    try:
        if content_type == 'summary':
            # Summary 타입: 원본 요약 파일과 AI 생성 핵심 요약으로 구분
            if "=== 📝 원본 요약 파일 ===" in ai_content and "=== 🤖 AI 생성 핵심 요약 ===" in ai_content:
                parts = ai_content.split("=== 🤖 AI 생성 핵심 요약 ===")
                original_part = parts[0].replace("=== 📝 원본 요약 파일 ===", "").strip()
                ai_part = parts[1].strip() if len(parts) > 1 else ""
                return original_part, ai_part
                
        elif content_type == 'application':
            # Application 타입: 원본 적용 파일과 AI 요약 및 총평으로 구분
            if "=== 📝 원본 적용 파일 ===" in ai_content and "=== 🤖 AI 요약 및 총평 ===" in ai_content:
                parts = ai_content.split("=== 🤖 AI 요약 및 총평 ===")
                original_part = parts[0].replace("=== 📝 원본 적용 파일 ===", "").strip()
                ai_part = parts[1].strip() if len(parts) > 1 else ""
                return original_part, ai_part
                
        elif content_type == 'fable':
            # Fable 타입: 전체가 AI 생성 우화
            return None, ai_content
            
        # 구분자가 없는 경우 전체를 AI 부분으로 간주
        return None, ai_content
        
    except Exception as e:
        st.warning(f"컨텐츠 파싱 중 오류: {e}")
        return None, ai_content

# 독서토론 레코드 조회 함수 (디버깅 강화)
def get_reading_discussion_records(content_type=None, book_title=None):
    connection = connect_to_db()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 쿼리 로깅을 위한 정보 수집
        query = """
            SELECT id, book_title, source_file_name, content_type, ai_content, 
                   audio_data, audio_filename, fable_type, model_used, extra_prompt,
                   opening_ment, next_topic, previous_topic, created_at
            FROM reading_discussion_records 
            WHERE 1=1
        """
        params = []
        
        if content_type:
            query += " AND content_type = %s"
            params.append(content_type)
        
        if book_title:
            query += " AND book_title = %s"
            params.append(book_title)
        
        # ID를 기준으로 정렬
        query += " ORDER BY id DESC"
        
        # 디버그 모드에서 쿼리 정보 표시
        if st.session_state.get("show_query_debug", False):
            st.sidebar.markdown("### 🔍 쿼리 디버그")
            st.sidebar.code(f"Query: {query}")
            st.sidebar.write(f"Params: {params}")
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        # 디버그 모드에서 조회 결과 표시
        if st.session_state.get("show_query_debug", False):
            st.sidebar.write(f"조회된 레코드 수: {len(records)}")
            for i, record in enumerate(records):
                st.sidebar.write(f"{i+1}. ID {record['id']}: {record['book_title']}")
                audio_size = len(record['audio_data']) if record['audio_data'] else 0
                st.sidebar.caption(f"   음성: {audio_size} bytes, 파일명: {record['audio_filename']}")
        
        return records
        
    except Error as e:
        st.error(f"데이터 조회 오류: {e}")
        return []
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# 음성 파일 지문 생성 함수
def generate_audio_fingerprint(audio_data):
    """음성 데이터의 고유 지문 생성"""
    if not audio_data:
        return "NO_AUDIO"
    
    # 음성 데이터의 크기와 시작/끝 부분의 해시를 조합
    size = len(audio_data)
    start_hash = hashlib.md5(audio_data[:min(1000, size)]).hexdigest()[:8]
    end_hash = hashlib.md5(audio_data[-min(1000, size):]).hexdigest()[:8]
    
    return f"{size}_{start_hash}_{end_hash}"

# 교차 참조 분석 함수
def analyze_audio_text_matching():
    """전체 데이터베이스에서 음성-텍스트 매칭 분석"""
    connection = connect_to_db()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, book_title, content_type, ai_content, audio_data, created_at
            FROM reading_discussion_records 
            ORDER BY id ASC
        """)
        all_records = cursor.fetchall()
        
        analysis_results = []
        for record in all_records:
            # 텍스트 지문 생성 (첫 100자)
            text_snippet = record['ai_content'][:100] if record['ai_content'] else "NO_TEXT"
            text_fingerprint = hashlib.md5(text_snippet.encode()).hexdigest()[:8]
            
            # 음성 지문 생성
            audio_fingerprint = generate_audio_fingerprint(record['audio_data'])
            
            analysis_results.append({
                'id': record['id'],
                'book_title': record['book_title'],
                'content_type': record['content_type'],
                'text_fingerprint': text_fingerprint,
                'audio_fingerprint': audio_fingerprint,
                'text_snippet': text_snippet,
                'created_at': record['created_at']
            })
        
        return analysis_results
        
    except Error as e:
        st.error(f"분석 중 오류: {e}")
        return []
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# 책 제목 목록 조회 함수
def get_book_titles():
    connection = connect_to_db()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT book_title FROM reading_discussion_records ORDER BY book_title")
        titles = [row[0] for row in cursor.fetchall()]
        return titles
        
    except Error as e:
        st.error(f"책 제목 조회 오류: {e}")
        return []
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# 명언 생성 함수
def generate_quote_from_content(content, book_title, user_prompt=None):
    """저장된 컨텐츠를 기반으로 명언을 생성"""
    try:
        # 컨텐츠 검증 및 처리
        if not content or content.strip() == "":
            st.error("저장된 컨텐츠가 없어 명언을 생성할 수 없습니다.")
            return None
        
        # 컨텐츠에서 핵심 내용 추출 (최대 4000자로 증가)
        content_summary = content[:4000] if content else ""
        
        # 기본 프롬프트 구성 - 저장된 컨텐츠 활용을 더 강조
        base_prompt = f"""
다음은 '{book_title}' 책에서 추출된 실제 독서 내용입니다. 이 내용을 반드시 기반으로 하여 깊이 있고 영감을 주는 명언을 만들어주세요.

**📖 책 제목:** {book_title}

**📝 저장된 독서 내용:**
{content_summary}

**🎯 요청사항:** 위의 구체적인 독서 내용에서 나온 핵심 메시지와 인사이트를 바탕으로 명언을 작성해주세요. 일반적인 명언이 아닌, 이 책의 내용과 직접적으로 연관된 명언이어야 합니다.
"""
        
        # 사용자 추가 프롬프트가 있다면 포함
        if user_prompt and user_prompt.strip():
            base_prompt += f"""

**💡 사용자 추가 요청:**
{user_prompt.strip()}
(단, 위의 독서 내용을 기반으로 하되 이 추가 요청을 반영해주세요)
"""
        
        final_prompt = base_prompt + """

**📋 명언 작성 요구사항:**
1. **반드시 위에 제공된 독서 내용의 핵심 메시지를 기반으로** 명언을 만들어주세요
2. 한글 명언과 영문 명언을 각각 1개씩 만들어주세요
3. 명언은 간결하면서도 깊이가 있어야 합니다
4. 실제 삶에 적용할 수 있는 실용적인 지혜를 담아주세요
5. 독서 내용에서 나온 구체적인 개념이나 아이디어를 반영해주세요
6. 사용자의 추가 요청이 있다면 그것을 반영하되, 반드시 독서 내용 기반을 유지해주세요

**📄 응답 형식:**
한글 명언: "명언 내용"
영문 명언: "Quote content"
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 독서 내용을 분석하여 그 책의 핵심 메시지를 바탕으로 깊이 있는 명언을 만드는 전문가입니다. 반드시 제공된 독서 내용의 구체적인 인사이트와 개념을 기반으로 명언을 만들어야 하며, 일반적이거나 추상적인 명언이 아닌 해당 책의 내용과 직접 연관된 명언을 만들어주세요."},
                {"role": "user", "content": final_prompt}
            ],
            max_tokens=800,  # 토큰 수 증가
            temperature=0.7
        )
        
        quote_text = response.choices[0].message.content
        return quote_text
        
    except Exception as e:
        st.error(f"명언 생성 중 오류: {e}")
        return None

# 명언 음성 생성 함수
def generate_quote_audio(quote_text):
    """명언을 음성으로 변환"""
    try:
        # 한글과 영문 명언을 분리
        lines = quote_text.split('\n')
        korean_quote = ""
        english_quote = ""
        
        for line in lines:
            if line.startswith('한글 명언:'):
                korean_quote = line.replace('한글 명언:', '').strip().strip('"')
            elif line.startswith('영문 명언:'):
                english_quote = line.replace('영문 명언:', '').strip().strip('"')
        
        # 음성 생성을 위한 전체 텍스트 구성
        full_text = f"오늘의 명언입니다. {korean_quote}. In English, {english_quote}"
        
        # OpenAI TTS API를 사용하여 음성 생성
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",  # 여성 목소리
            input=full_text,
            response_format="mp3"
        )
        
        # 음성 데이터를 바이트로 변환
        audio_data = response.content
        return audio_data, korean_quote, english_quote
        
    except Exception as e:
        st.error(f"음성 생성 중 오류: {e}")
        return None, None, None

# 메인 앱
def main():
    #st.markdown("### 🎵 이야기 재생")
    st.write("저장된 AI 요약과 우화 콘텐츠를 조회하고 음성을 재생할 수 있습니다.")
    
    # 데이터 개수 선택
    col1, col2 = st.columns([3, 1])
    with col1:
        record_count = st.selectbox(
            "표시할 최근 레코드 수",
            [3, 5, 10, 15, 20, 30, 50],
            index=2,  # 디폴트 10개
            key="record_count"
        )
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    # 최근 N개 데이터 가져오기
    all_records = get_reading_discussion_records()
    filtered_records = all_records[:record_count]
    
    if filtered_records:
        # 헤더
        st.write(f"### 📋 총 {len(filtered_records)}개의 기록이 있습니다.")
        
        for i, record in enumerate(filtered_records):
            with st.expander(f"{'📝' if record['content_type'] == 'summary' else '📋' if record['content_type'] == 'application' else '📚'} {record['book_title']} - {record['content_type'].upper()} ({record['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                # 메타데이터 정보
                meta_col1, meta_col2 = st.columns(2)
                with meta_col1:
                    st.write(f"**📖 책 제목:** {record['book_title']}")
                    st.write(f"**📄 원본 파일:** {record['source_file_name'] or 'N/A'}")
                    st.write(f"**🤖 사용 모델:** {record['model_used'] or 'N/A'}")
                with meta_col2:
                    if record['content_type'] == 'fable':
                        st.write(f"**🎭 우화 스타일:** {record['fable_type'] or 'N/A'}")
                    if record['next_topic']:
                        st.write(f"**➡️ 다음 주제:** {record['next_topic']}")
                    if record['previous_topic']:
                        st.write(f"**⬅️ 이전 주제:** {record['previous_topic']}")
                
                # 추가 프롬프트가 있다면 표시
                if record['extra_prompt']:
                    st.write(f"**💡 추가 프롬프트:** {record['extra_prompt']}")
                
                # AI 생성 콘텐츠 표시
                if record['ai_content']:
                    st.markdown("#### 📝 저장된 콘텐츠")
                    if record['content_type'] == 'summary':
                        # 요약의 경우 원본과 AI 요약을 구분하여 표시
                        content = record['ai_content']
                        if "=== 📝 원본 요약 파일 ===" in content and "=== 🤖 AI 생성 핵심 요약 ===" in content:
                            parts = content.split("=== 🤖 AI 생성 핵심 요약 ===")
                            if len(parts) == 2:
                                original_content = parts[0].replace("=== 📝 원본 요약 파일 ===", "").strip()
                                ai_content = parts[1].strip()
                                
                                # 탭으로 구분하여 표시
                                sub_tab1, sub_tab2 = st.tabs(["📝 원본 요약", "🤖 AI 핵심 요약"])
                                with sub_tab1:
                                    st.markdown(format_bullet_points(original_content))
                                with sub_tab2:
                                    st.markdown(format_bullet_points(ai_content))
                            else:
                                st.markdown(format_bullet_points(content))
                        else:
                            st.markdown(format_bullet_points(content))
                    elif record['content_type'] == 'application':
                        # 적용 파일의 경우 원본과 AI 요약을 구분하여 표시
                        content = record['ai_content']
                        if "=== 📝 원본 적용 파일 ===" in content and "=== 🤖 AI 요약 및 총평 ===" in content:
                            parts = content.split("=== 🤖 AI 요약 및 총평 ===")
                            if len(parts) == 2:
                                original_content = parts[0].replace("=== 📝 원본 적용 파일 ===", "").strip()
                                ai_content = parts[1].strip()
                                
                                # 탭으로 구분하여 표시
                                sub_tab1, sub_tab2 = st.tabs(["📝 원본 적용 파일", "🤖 AI 요약 및 총평"])
                                with sub_tab1:
                                    st.markdown(format_bullet_points(original_content))
                                with sub_tab2:
                                    st.markdown(ai_content)
                            else:
                                st.markdown(format_bullet_points(content))
                        else:
                            st.markdown(format_bullet_points(content))
                    else:
                        # 우화의 경우 그대로 표시
                        st.markdown(record['ai_content'])
                
                # 음성 재생 기능
                if record['audio_data']:
                    st.markdown("#### 🎵 음성 재생")
                    try:
                        # BLOB 데이터를 base64로 변환하여 재생
                        audio_base64 = base64.b64encode(record['audio_data']).decode('utf-8')
                        audio_html = f'''
                            <audio controls style="width: 100%;">
                                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                                Your browser does not support the audio element.
                            </audio>
                        '''
                        st.markdown(audio_html, unsafe_allow_html=True)
                        
                        # 다운로드 버튼 표시
                        st.download_button(
                            label="🎵 음성 파일 다운로드",
                            data=record['audio_data'],
                            file_name=record['audio_filename'] or f"{record['content_type']}_{record['book_title']}_{record['id']}.mp3",
                            mime="audio/mp3",
                            key=f"download_audio_{record['id']}"
                        )
                        
                        # 명언 생성 섹션
                        st.markdown("#### ✨ 오늘의 명언 생성")
                        
                        # 프롬프트 입력과 버튼을 나란히 배치
                        col_prompt, col_button = st.columns([3, 1])
                        
                        with col_prompt:
                            user_prompt = st.text_area(
                                "추가 프롬프트 (선택사항)",
                                placeholder="예: 동기부여가 되는 명언으로 만들어주세요, 리더십에 관한 명언으로 만들어주세요 등",
                                height=68,
                                key=f"quote_prompt_{record['id']}"
                            )
                        
                        with col_button:
                            st.markdown("<br>", unsafe_allow_html=True)  # 버튼 높이 맞추기
                            if st.button("✨ 명언 생성", key=f"quote_btn_{record['id']}"):
                                with st.spinner("명언을 생성하고 있습니다..."):
                                    # 명언 생성 (프롬프트 포함)
                                    quote_text = generate_quote_from_content(
                                        record['ai_content'], 
                                        record['book_title'], 
                                        user_prompt
                                    )
                                    
                                    if quote_text:
                                        # 음성 생성
                                        audio_data, korean_quote, english_quote = generate_quote_audio(quote_text)
                                        
                                        # 세션 상태에 저장하여 다시 렌더링될 때도 유지
                                        st.session_state[f"quote_data_{record['id']}"] = {
                                            'korean': korean_quote,
                                            'english': english_quote,
                                            'audio': audio_data,
                                            'user_prompt': user_prompt  # 사용된 프롬프트도 저장
                                        }
                        
                        # 명언이 생성되었다면 표시
                        if f"quote_data_{record['id']}" in st.session_state:
                            quote_data = st.session_state[f"quote_data_{record['id']}"]
                            st.markdown("#### 🎯 생성된 명언")
                            
                            # 사용된 프롬프트 표시 (있다면)
                            if quote_data.get('user_prompt') and quote_data['user_prompt'].strip():
                                st.caption(f"**💡 사용된 추가 프롬프트:** {quote_data['user_prompt']}")
                            
                            # 명언 표시
                            st.success(f"**🇰🇷 한글 명언:** {quote_data['korean']}")
                            st.info(f"**🇺🇸 English Quote:** {quote_data['english']}")
                            
                            # 명언 음성 재생과 새로운 명언 생성 버튼을 나란히 배치
                            if quote_data['audio']:
                                st.markdown("**🎵 명언 음성:**")
                                try:
                                    audio_base64 = base64.b64encode(quote_data['audio']).decode('utf-8')
                                    audio_html = f'''
                                        <audio controls style="width: 100%;">
                                            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                                            Your browser does not support the audio element.
                                        </audio>
                                    '''
                                    st.markdown(audio_html, unsafe_allow_html=True)
                                    
                                    # 다운로드와 새로운 명언 생성 버튼을 나란히 배치
                                    col_download_quote, col_new_quote = st.columns([1, 1])
                                    
                                    with col_download_quote:
                                        st.download_button(
                                            label="💾 명언 음성 다운로드",
                                            data=quote_data['audio'],
                                            file_name=f"quote_{record['book_title']}_{record['id']}.mp3",
                                            mime="audio/mp3",
                                            key=f"download_quote_{record['id']}"
                                        )
                                    
                                    with col_new_quote:
                                        if st.button("🔄 새로운 명언 생성", key=f"new_quote_{record['id']}"):
                                            del st.session_state[f"quote_data_{record['id']}"]
                                            st.rerun()
                                            
                                except Exception as e:
                                    st.error(f"명언 음성 재생 중 오류: {str(e)}")
                            else:
                                # 음성이 없는 경우에도 새로운 명언 생성 버튼 표시
                                if st.button("🔄 새로운 명언 생성", key=f"new_quote_{record['id']}"):
                                    del st.session_state[f"quote_data_{record['id']}"]
                                    st.rerun()
                    except Exception as e:
                        st.error(f"음성 재생 중 오류: {str(e)}")
                else:
                    st.info("저장된 음성 파일이 없습니다.")
                
                # 구분선
                st.markdown("---")
    else:
        st.info("저장된 기록이 없습니다. AI 요약이나 우화를 생성하고 음성을 생성해보세요!")
    
    # 푸터
    st.markdown("---")
    st.markdown("""
    **💡 사용 팁:**
    - **탭 구분**: "AI 핵심 요약" 및 "AI 요약 및 총평" 탭의 내용이 실제 음성으로 변환된 텍스트입니다
    - **다운로드**: 각 음성 파일을 다운로드할 수 있습니다
    - **✨ 오늘의 명언**: 저장된 컨텐츠를 기반으로 한글/영문 명언을 생성하고 음성으로 들을 수 있습니다
    - **📝 추가 프롬프트**: 명언 생성 시 원하는 스타일이나 주제를 지정할 수 있습니다 (예: "동기부여", "리더십", "성공" 등)
    - **명언 재생성**: "새로운 명언 생성" 버튼을 클릭하여 다른 명언을 만들 수 있습니다
    - **프롬프트 활용**: 빈 프롬프트로 생성하면 기본 명언, 프롬프트를 입력하면 맞춤형 명언이 생성됩니다
    - **최신순 정렬**: 가장 최근에 생성된 콘텐츠부터 표시됩니다
    """)

if __name__ == "__main__":
    main() 