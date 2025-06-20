import streamlit as st
import os
import base64
import pandas as pd
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain_anthropic import ChatAnthropic
import anthropic
import mysql.connector
import json
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import io
import re
from sqlalchemy import create_engine
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.tools import DuckDuckGoSearchResults, WikipediaQueryRun, Tool
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.utilities import WikipediaAPIWrapper

st.set_page_config(page_title="나만의 Jarvis", layout="wide")
st.title("[⚙️ J.A.R.V.I.S. ONLINE ⚙️]")

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
        
# --- MySQL 연결 통합 관리를 위한 클래스 추가 ---
class MySQLConnection:
    """MySQL 연결을 관리하는 클래스"""
    def __init__(self):
        self.config = {
            'host': os.getenv('SQL_HOST'),
            'user': os.getenv('SQL_USER'),
            'password': os.getenv('SQL_PASSWORD'),
            'database': os.getenv('SQL_DATABASE_NEWBIZ'),
            'charset': 'utf8mb4'
        }
        self.engine = None
        
    def get_connection(self):
        """MySQL 커넥션 반환"""
        return mysql.connector.connect(**self.config)
    
    def get_engine(self):
        """SQLAlchemy 엔진 반환"""
        if not self.engine:
            self.engine = create_engine(
                f"mysql+mysqlconnector://{self.config['user']}:{self.config['password']}@{self.config['host']}/{self.config['database']}?charset={self.config['charset']}"
            )
        return self.engine
    
    def execute_query(self, query, params=None):
        """쿼리 실행 및 결과 반환"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
            return result
        finally:
            cursor.close()
            conn.close()
    
    def execute_query_pandas(self, query, params=None):
        """pandas DataFrame으로 쿼리 결과 반환"""
        try:
            return pd.read_sql(query, self.get_engine(), params=params)
        except Exception as e:
            print(f"Error executing pandas query: {e}")
            return pd.DataFrame()

# --- 전역 MySQL 연결 객체 생성 ---
mysql_conn = MySQLConnection()

# --- Session state initialization (must be at the very top, before any UI or logic) ---
if 'selected_ai_api' not in st.session_state:
    st.session_state.selected_ai_api = 'Anthropic (Claude)'
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = 'claude-3-7-sonnet-latest'
# --- JARVIS 결과/로그 세션 상태도 항상 초기화 ---
if 'jarvis_last_results' not in st.session_state:
    st.session_state.jarvis_last_results = None
if 'jarvis_last_logs' not in st.session_state:
    st.session_state.jarvis_last_logs = None

# --- Chat history state ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

# --- 0. 화자(사용자) 선택 UI (항상 상단에 위치) ---
SPEAKERS = ["상현님","경호님","성범님","성일님","재원님","창환님", "현철님"]
if 'selected_speaker' not in st.session_state:
    st.session_state['selected_speaker'] = SPEAKERS[0]
selected_speaker = st.selectbox('화자(사용자) 선택', SPEAKERS, key='selected_speaker')

# --- 1. AI API/모델 선택 UI (DB생성.py 참고) ---
has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
has_openai_key = os.environ.get('OPENAI_API_KEY') is not None

model_options = [
    "claude-3-7-sonnet-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229", 
    "claude-3-haiku-20240307",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1-preview",
    "o1-mini"
]

available_models = []
if has_anthropic_key:
    available_models.extend([m for m in model_options if 'claude' in m.lower()])
if has_openai_key:
    available_models.extend([m for m in model_options if any(x in m.lower() for x in ['gpt', 'o1'])])
if not available_models:
    available_models = ['claude-3-7-sonnet-latest']

col_api, col_model = st.columns([1,2])
with col_api:
    selected_ai_api = st.selectbox(
        'AI API 선택',
        options=['Anthropic (Claude)', 'OpenAI (GPT)'],
        index=0 if st.session_state.selected_ai_api == 'Anthropic (Claude)' else 1,
        help="사용할 AI 제공자를 선택하세요. Claude는 Extended Thinking을 지원합니다."
    )
    st.session_state.selected_ai_api = selected_ai_api
with col_model:
    filtered_models = [m for m in available_models if (('claude' in m.lower() and selected_ai_api=='Anthropic (Claude)') or (any(x in m.lower() for x in ['gpt', 'o1']) and selected_ai_api=='OpenAI (GPT)'))]
    if not filtered_models:
        filtered_models = ['claude-3-7-sonnet-latest']
    selected_model = st.selectbox(
        'AI 모델 선택',
        options=filtered_models,
        index=filtered_models.index(st.session_state.selected_model) if st.session_state.selected_model in filtered_models else 0,
        help="Claude-3-7-sonnet-latest, Claude-3-5-sonnet-latest와 o1 모델들은 Extended Thinking(Reasoning)을 지원합니다."
    )
    st.session_state.selected_model = selected_model

# --- 2. JARVIS 페르소나(시스템 프롬프트) ---
JARVIS_SYSTEM_PROMPT = (
    "당신은 아이언맨(토니 스타크)의 인공지능 비서 JARVIS입니다. "
    "항상 논리적이고, 신속하며, 예의 바르고, 전문가 스타일로 답변하세요. "
    "모든 답변은 'JARVIS:'로 시작하며, 자신을 JARVIS(아이언맨의 AI)로만 인식합니다. "
    "절대 자신을 다른 AI, 챗봇, 어시스턴트, 인간 등으로 소개하지 마세요. "
    "불필요한 농담이나 아이언맨 관련 농담은 하지 마세요. "
    "질문이 모호하거나 불완전해도, 토니 스타크의 비서답게 핵심을 빠르게 파악해 명확하고 실용적인 답을 제시하세요. "
    "(모든 답변은 JARVIS의 페르소나로만!)"
)

def load_user_history(user_id):
    """사용자의 대화/지식/파일 히스토리를 로드하는 함수 (MySQL 연결 통합 버전)"""
    try:
        # 1. 최근 대화 히스토리
        chat_query = """
        SELECT 
            created_at,
            user_input,
            jarvis_response,
            files_json,
            logs_json
        FROM jarvis_interactions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 10
        """
        chat_history = mysql_conn.execute_query(chat_query, [user_id])
        
        # 2. 사용자 관련 지식/파일 정보
        knowledge_query = """
        SELECT 
            k.title,
            k.content,
            k.created_at,
            k.category
        FROM knowledge_base k
        JOIN user_knowledge uk ON k.id = uk.knowledge_id
        WHERE uk.user_id = %s
        ORDER BY k.created_at DESC
        LIMIT 5
        """
        knowledge = mysql_conn.execute_query(knowledge_query, [user_id])
        
        # 3. 최근 작업 기록
        work_query = """
        SELECT 
            action,
            details,
            created_at
        FROM work_journal
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 5
        """
        work_history = mysql_conn.execute_query(work_query, [user_id])
        
        return {
            'chat_history': chat_history,
            'knowledge': knowledge,
            'work_history': work_history
        }
    except Exception as e:
        print(f"Error loading user history: {e}")
        # 기본 응답 반환
        return {
            'chat_history': [],
            'knowledge': [],
            'work_history': [
                {
                    'action': 'newbiz DB 생성',
                    'details': 'Initial database setup',
                    'created_at': '2024-10-23'
                }
            ]
        }

def get_db_info_as_dataframes():
    """데이터베이스 정보를 pandas DataFrame으로 가져오는 함수"""
    try:
        # 1. 테이블 목록과 정보
        tables_query = """
        SELECT 
            TABLE_NAME,
            TABLE_COMMENT,
            TABLE_ROWS,
            CREATE_TIME,
            UPDATE_TIME
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = %s
        """
        tables_df = mysql_conn.execute_query_pandas(tables_query, [mysql_conn.config['database']])
        
        if tables_df.empty:
            print("No tables found in database")
            return None
        
        # 2. 컬럼 정보
        columns_query = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s
        """
        columns_df = mysql_conn.execute_query_pandas(columns_query, [mysql_conn.config['database']])
        
        # 3. 각 테이블의 샘플 데이터와 통계
        sample_data = {}
        table_stats = {}
        
        for table_name in tables_df['TABLE_NAME']:
            try:
                # 샘플 데이터 (최근 5개 행)
                sample_query = f"""
                SELECT * FROM {table_name} 
                ORDER BY CASE 
                    WHEN created_at IS NOT NULL THEN created_at 
                    ELSE '2099-12-31' 
                END DESC 
                LIMIT 5
                """
                sample_df = mysql_conn.execute_query_pandas(sample_query)
                if not sample_df.empty:
                    sample_data[table_name] = sample_df
                
                # 기본 통계 정보
                stats_query = f"SELECT COUNT(*) as total_rows FROM {table_name}"
                stats_df = mysql_conn.execute_query_pandas(stats_query)
                if not stats_df.empty:
                    table_stats[table_name] = {
                        'total_rows': stats_df['total_rows'].iloc[0],
                        'columns': len(columns_df[columns_df['TABLE_NAME'] == table_name])
                    }
            except Exception as e:
                print(f"Error getting data for table {table_name}: {e}")
                continue
        
        return {
            'tables': tables_df,
            'columns': columns_df,
            'samples': sample_data,
            'stats': table_stats
        }
    except Exception as e:
        print(f"Error in get_db_info_as_dataframes: {e}")
        return None

def load_conversation_history(user_id, search_keyword=None, limit=100):
    """대화 히스토리 로드 함수 (MySQL 연결 통합 버전)"""
    try:
        query = "SELECT * FROM jarvis_interactions WHERE user_id = %s"
        params = [user_id]
        
        if search_keyword:
            query += " AND (user_input LIKE %s OR jarvis_response LIKE %s)"
            kw = f"%{search_keyword}%"
            params.extend([kw, kw])
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        return mysql_conn.execute_query(query, params)
    except Exception as e:
        print(f"Error loading conversation history: {e}")
        return []

def save_interaction(user_id, speaker, msg, files=None, audio=None):
    """상호작용 저장 함수 (MySQL 연결 통합 버전)"""
    try:
        conn = mysql_conn.get_connection()
        cursor = conn.cursor()
        
        user_input = msg.get('input', None)
        jarvis_response = None
        if msg.get('results') and isinstance(msg['results'], dict):
            jarvis_response = msg['results'].get('대화에이전트', None)
        
        logs_json = json.dumps(msg.get('logs', None), ensure_ascii=False) if msg.get('logs') else None
        files_json = json.dumps(files, ensure_ascii=False) if files else None
        
        cursor.execute("""
            INSERT INTO jarvis_interactions
            (user_id, speaker, user_input, jarvis_response, files_json, audio_blob, logs_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            user_id,
            speaker,
            user_input,
            jarvis_response,
            files_json,
            audio,
            logs_json
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error saving interaction: {e}")

# --- 기존 함수들의 MySQL 연결 부분 업데이트 ---
def get_all_table_names():
    """테이블 목록 조회 함수 (MySQL 연결 통합 버전)"""
    try:
        result = mysql_conn.execute_query("SHOW TABLES")
        return [list(row.values())[0] for row in result]
    except Exception as e:
        print(f"Error getting table names: {e}")
        return []

def parse_uploaded_files(uploaded_files):
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'claude-3-7-sonnet-latest'
    if 'selected_ai_api' not in st.session_state:
        st.session_state.selected_ai_api = 'Anthropic (Claude)'
    # 파일 파싱/미리보기 (텍스트, PDF, docx, xlsx 일부 지원)
    previews = []
    for f in uploaded_files:
        ext = os.path.splitext(f.name)[-1].lower()
        try:
            if ext in [".txt", ".md"]:
                content = f.read().decode("utf-8")
            elif ext == ".pdf":
                import PyPDF2
                reader = PyPDF2.PdfReader(f)
                content = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            elif ext == ".docx":
                from docx import Document
                doc = Document(f)
                content = "\n".join([p.text for p in doc.paragraphs])
            elif ext == ".xlsx":
                df = pd.read_excel(f)
                content = df.to_csv(index=False)
            else:
                content = f"[{f.name}] 미리보기 지원 안됨"
        except Exception as e:
            content = f"[{f.name}] 파싱 오류: {e}"
        previews.append({"filename": f.name, "preview": content})
    return previews

def text_to_speech(text):
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'claude-3-7-sonnet-latest'
    if 'selected_ai_api' not in st.session_state:
        st.session_state.selected_ai_api = 'Anthropic (Claude)'
    # 실제 OpenAI TTS 연동 예시 (API 키 필요)
    try:
        from openai import OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            return None
        client = OpenAI(api_key=openai_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        audio_html = f'<audio controls><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
        return audio_html
    except Exception as e:
        return f"[TTS 오류] {e}"

# --- JARVIS 대화에이전트 프롬프트 생성 보조 함수 ---
def should_attach_history(user_input):
    keywords = [
        '이전 대화', '최근 기록', '지난 회의', '대화 히스토리', '최근 질문', '최근 답변',
        '대화 내역', '과거 대화', '마지막 대화', '최근 대화', '기록 보여줘', '기록 알려줘',
        '대화 보여줘', '대화 알려줘', '히스토리', 'history', 'log', 'meeting', '요약'
    ]
    return any(k in user_input for k in keywords)

def get_recent_history_for_prompt(user_id, n=5):
    rows = load_conversation_history(user_id, limit=n)
    if not rows:
        return "저장된 대화 기록이 없습니다."
    history_lines = []
    for r in rows:
        history_lines.append(f"[{r['created_at']}] 질문: {r['user_input']}\n답변: {r['jarvis_response']}")
    return '\n\n'.join(history_lines)

# --- 파일/음성 텍스트 추출 보조 함수 (간단 버전) ---
def extract_text_from_fileinfo(fileinfo):
    # fileinfo: dict with keys like 'name', 'content', 'type', 'text' (if extracted)
    if not fileinfo:
        return ''
    # 1. 텍스트 필드가 있으면 우선 사용
    if isinstance(fileinfo, dict) and 'text' in fileinfo and fileinfo['text']:
        return fileinfo['text']
    # 2. 파일명/타입 등 메타정보
    name = fileinfo.get('name', '')
    ftype = fileinfo.get('type', '')
    return f"[파일: {name} ({ftype})]"

def extract_text_from_audio(audio_blob):
    # 실제로는 STT 등으로 텍스트 변환 필요. 여기선 placeholder
    if audio_blob:
        return '[음성 파일: 텍스트 변환 결과(예시)]'
    return ''

def search_db_tables_for_relevance(user_input, max_rows=100, topn=2):
    tables = get_all_table_names()
    relevant_tables = []
    table_summaries = []
    # Prepare SQLAlchemy engine once
    engine = create_engine(
        f"mysql+mysqlconnector://{os.getenv('SQL_USER')}:{os.getenv('SQL_PASSWORD')}@{os.getenv('SQL_HOST')}/{os.getenv('SQL_DATABASE_NEWBIZ')}?charset=utf8mb4"
    )
    for table in tables:
        try:
            query = f"SELECT * FROM {table} LIMIT {max_rows}"
            df = pd.read_sql(query, engine)
            if df.empty:
                continue
            # 모든 컬럼을 하나의 텍스트로 합침
            docs = df.astype(str).apply(lambda row: ' '.join(row), axis=1).tolist()
            vectorizer = TfidfVectorizer().fit(docs + [user_input])
            doc_vecs = vectorizer.transform(docs)
            query_vec = vectorizer.transform([user_input])
            sims = cosine_similarity(query_vec, doc_vecs)[0]
            top_idx = np.argsort(sims)[::-1][:topn]
            # 유사도가 0.01 이상인 행만 추출
            relevant_rows = [(i, sims[i]) for i in top_idx if sims[i] > 0.01]
            if relevant_rows:
                relevant_tables.append(table)
                # 상위 N개 행 요약
                summary = '\n'.join([f"[{table}] {docs[i][:200]}... (유사도: {sims[i]:.2f})" for i, _ in relevant_rows])
                table_summaries.append(summary)
        except Exception as e:
            continue
    return relevant_tables, table_summaries

# --- 웹사이트 RAG: 크롤링 함수 (Virtual Company 참고) ---
def scrape_website_simple(url, max_pages=5):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    import time
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        visited_urls = set()
        texts = []
        urls_to_visit = [url]
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        successfully_scraped = 0
        while urls_to_visit and successfully_scraped < max_pages:
            current_url = urls_to_visit.pop(0)
            if current_url in visited_urls:
                continue
            try:
                response = session.get(current_url, timeout=10)
                response.raise_for_status()
                visited_urls.add(current_url)
                soup = BeautifulSoup(response.content, "html.parser")
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                cleaned_text = '\n'.join(lines)
                if len(cleaned_text) > 50:
                    page_title = soup.title.string.strip() if soup.title and soup.title.string else f'페이지 {successfully_scraped + 1}'
                    texts.append({
                        'content': cleaned_text,
                        'url': current_url,
                        'title': page_title
                    })
                    successfully_scraped += 1
                base_domain = urlparse(url).netloc
                for link in soup.find_all("a", href=True)[:20]:
                    absolute_link = urljoin(current_url, link['href'])
                    parsed_link = urlparse(absolute_link)
                    if (parsed_link.netloc == base_domain and 
                        absolute_link not in visited_urls and 
                        absolute_link not in urls_to_visit and
                        not any(x in absolute_link.lower() for x in ['#', 'javascript:', 'mailto:', 'tel:']) and
                        len(urls_to_visit) < 50):
                        urls_to_visit.append(absolute_link)
                time.sleep(0.5)
            except Exception:
                continue
        return texts
    except Exception:
        return []

# --- RAG 소스 추출 함수 ---
def extract_rag_sources(user_id, user_input, file_previews=None, website_texts=None):
    # DB 대화/지식/파일/음성 기록
    rows = load_conversation_history(user_id, limit=200)
    db_keyword_matches = []
    db_semantic_matches = []
    chat_keyword_matches = []
    chat_semantic_matches = []
    file_keyword_matches = []
    file_semantic_matches = []
    web_keyword_matches = []
    web_semantic_matches = []
    keyword = user_input.strip().lower()
    # DB: keyword match & semantic
    for r in rows:
        if r.get('user_input') and keyword in str(r['user_input']).lower():
            db_keyword_matches.append(f"[DB] 질문: {r['user_input']}\n답변: {r['jarvis_response']}")
        elif r.get('jarvis_response') and keyword in str(r['jarvis_response']).lower():
            db_keyword_matches.append(f"[DB] 질문: {r['user_input']}\n답변: {r['jarvis_response']}")
    # DB: semantic (유사도)
    db_docs = [f"질문: {r['user_input']}\n답변: {r['jarvis_response']}" for r in rows]
    if db_docs:
        vectorizer = TfidfVectorizer().fit(db_docs + [user_input])
        doc_vecs = vectorizer.transform(db_docs)
        query_vec = vectorizer.transform([user_input])
        sims = cosine_similarity(query_vec, doc_vecs)[0]
        top_idx = np.argsort(sims)[::-1][:5]
        db_semantic_matches = [db_docs[i] for i in top_idx if sims[i] > 0.1]
    # 대화/파일/웹: keyword & semantic
    if file_previews:
        for f in file_previews:
            if keyword in f.get('preview','').lower():
                file_keyword_matches.append(f"[파일] {f['filename']}: {f['preview'][:300]}")
        file_docs = [f.get('preview','') for f in file_previews if f.get('preview')]
        if file_docs:
            vectorizer = TfidfVectorizer().fit(file_docs + [user_input])
            doc_vecs = vectorizer.transform(file_docs)
            query_vec = vectorizer.transform([user_input])
            sims = cosine_similarity(query_vec, doc_vecs)[0]
            top_idx = np.argsort(sims)[::-1][:3]
            file_semantic_matches = [file_docs[i] for i in top_idx if sims[i] > 0.1]
    if website_texts:
        for i, w in enumerate(website_texts):
            if keyword in w.lower():
                web_keyword_matches.append(f"[웹사이트] {w[:300]}")
        if website_texts:
            vectorizer = TfidfVectorizer().fit(website_texts + [user_input])
            doc_vecs = vectorizer.transform(website_texts)
            query_vec = vectorizer.transform([user_input])
            sims = cosine_similarity(query_vec, doc_vecs)[0]
            top_idx = np.argsort(sims)[::-1][:3]
            web_semantic_matches = [website_texts[i] for i in top_idx if sims[i] > 0.1]
    # 대화 히스토리(세션)
    for msg in st.session_state.get('chat_history', []):
        if msg['role'] == 'user' and keyword in msg['content'].lower():
            chat_keyword_matches.append(f"[대화] {msg['content']}")
        elif msg['role'] == 'jarvis' and keyword in msg['content'].lower():
            chat_keyword_matches.append(f"[대화] {msg['content']}")
    # 대화 의미 기반(최근 10개)
    chat_docs = [m['content'] for m in st.session_state.get('chat_history', []) if m['role'] in ['user','jarvis']]
    if chat_docs:
        vectorizer = TfidfVectorizer().fit(chat_docs + [user_input])
        doc_vecs = vectorizer.transform(chat_docs)
        query_vec = vectorizer.transform([user_input])
        sims = cosine_similarity(query_vec, doc_vecs)[0]
        top_idx = np.argsort(sims)[::-1][:3]
        chat_semantic_matches = [chat_docs[i] for i in top_idx if sims[i] > 0.1]
    return {
        'db_keyword': db_keyword_matches,
        'db_semantic': db_semantic_matches,
        'chat_keyword': chat_keyword_matches,
        'chat_semantic': chat_semantic_matches,
        'file_keyword': file_keyword_matches,
        'file_semantic': file_semantic_matches,
        'web_keyword': web_keyword_matches,
        'web_semantic': web_semantic_matches,
    }

def search_all_db_tables_for_rag(user_input, max_rows=100, topn=2):
    from sqlalchemy import create_engine
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import os
    import json
    engine = create_engine(
        f"mysql+mysqlconnector://{os.getenv('SQL_USER')}:{os.getenv('SQL_PASSWORD')}@{os.getenv('SQL_HOST')}/{os.getenv('SQL_DATABASE_NEWBIZ')}?charset=utf8mb4"
    )
    tables = get_all_table_names()
    rag_results = []
    for table in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {table} LIMIT {max_rows}", engine)
            if df.empty:
                continue
            docs = df.astype(str).apply(lambda row: ' '.join(row), axis=1).tolist()
            vectorizer = TfidfVectorizer().fit(docs + [user_input])
            doc_vecs = vectorizer.transform(docs)
            query_vec = vectorizer.transform([user_input])
            sims = cosine_similarity(query_vec, doc_vecs)[0]
            top_idx = np.argsort(sims)[::-1][:topn]
            for i in top_idx:
                if sims[i] > 0.1:
                    # 구조적으로 컬럼명:값 딕셔너리로 첨부
                    row_dict = df.iloc[i].to_dict()
                    rag_results.append({
                        'table': table,
                        'row': row_dict,
                        'similarity': float(sims[i])
                    })
        except Exception:
            continue
    return rag_results

def get_meeting_titles(limit=10):
    import mysql.connector
    conn = mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM meeting_records ORDER BY created_at DESC LIMIT %s", (limit,))
    titles = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return titles

def get_meeting_record_by_title(title):
    import mysql.connector
    conn = mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM meeting_records WHERE title = %s LIMIT 1", (title,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def get_meeting_records_by_keyword(keyword, limit=10):
    import mysql.connector
    import re
    # 정규화: 소문자, 공백/특수문자(-,_) 제거
    keyword_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', keyword).lower()
    conn = mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )
    cursor = conn.cursor(dictionary=True)
    # IFNULL로 NULL 안전하게, 공백/하이픈/언더스코어 모두 제거
    try:
        query = """
            SELECT * FROM meeting_records
            WHERE REPLACE(REPLACE(REPLACE(LOWER(IFNULL(title, '')), ' ', ''), '-', ''), '_', '') LIKE %s
               OR REPLACE(REPLACE(REPLACE(LOWER(IFNULL(summary, '')), ' ', ''), '-', ''), '_', '') LIKE %s
               OR REPLACE(REPLACE(REPLACE(LOWER(IFNULL(full_text, '')), ' ', ''), '-', ''), '_', '') LIKE %s
            LIMIT %s
        """
        like_pattern = f'%{keyword_norm}%'
        cursor.execute(query, (like_pattern, like_pattern, like_pattern, limit))
        rows = cursor.fetchall()
    except Exception as e:
        rows = []
    cursor.close()
    conn.close()
    return rows

# --- 모든 테이블의 컬럼 정보와 샘플 row를 DataFrame 기반으로 반환 ---
def get_all_table_columns_and_samples(sample_n=2, keyword=None):
    import mysql.connector
    conn = mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    all_info = {}
    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = [row['Field'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        rows = []
        col_names = []
        # 1. keyword가 있으면, keyword가 포함되고 summary/full_text/action_items가 채워진 row 우선
        if keyword:
            try:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE "
                    f"(title LIKE %s OR summary LIKE %s OR full_text LIKE %s) AND "
                    f"((summary IS NOT NULL AND summary != '') OR (full_text IS NOT NULL AND full_text != '') OR (action_items IS NOT NULL AND action_items != '')) "
                    f"LIMIT {sample_n}",
                    (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
                )
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
            except Exception:
                rows = []
        # 2. keyword가 있으면, keyword가 포함된 row
        if not rows and keyword:
            try:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE "
                    f"(title LIKE %s OR summary LIKE %s OR full_text LIKE %s) "
                    f"LIMIT {sample_n}",
                    (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
                )
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
            except Exception:
                rows = []
        # 3. 그래도 없으면 그냥 LIMIT 2
        if not rows:
            try:
                cursor.execute(f"SELECT * FROM {table} LIMIT {sample_n}")
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
            except Exception:
                rows = []
                col_names = []
        sample_rows = [dict(zip(col_names, row)) for row in rows]
        all_info[table] = {
            "columns": columns,
            "sample_rows": sample_rows
        }
    cursor.close()
    conn.close()
    return all_info

# --- 진정한 DB RAG를 위한 새로운 함수들 ---
def get_table_schema_info(table_name):
    """테이블의 스키마 정보를 가져오는 함수"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4'
        )
        cursor = conn.cursor(dictionary=True)
        
        # 테이블 컬럼 정보 가져오기
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME, 
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        columns = cursor.fetchall()
        
        # 테이블 통계 정보 가져오기
        cursor.execute(f"SELECT COUNT(*) as row_count FROM {table_name}")
        row_count = cursor.fetchone()['row_count']
        
        # 샘플 데이터 가져오기 (최근 5개)
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY created_at DESC LIMIT 5")
        samples = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'columns': columns,
            'row_count': row_count,
            'samples': samples
        }
    except Exception as e:
        return {'error': str(e)}

def get_semantic_table_matches(query, tables=None):
    """쿼리와 의미적으로 관련된 테이블을 찾는 함수"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4'
        )
        cursor = conn.cursor(dictionary=True)
        
        # 전체 테이블 목록 가져오기
        cursor.execute("""
            SELECT 
                TABLE_NAME,
                TABLE_COMMENT,
                TABLE_ROWS,
                CREATE_TIME,
                UPDATE_TIME
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        tables = cursor.fetchall()
        
        table_info = []
        for table in tables:
            table_name = table['TABLE_NAME']
            
            # 컬럼 정보 가져오기
            cursor.execute("""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
            columns = cursor.fetchall()
            
            # 샘플 데이터 가져오기 (에러 방지를 위해 try-except 사용)
            sample_data = None
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
                sample_data = cursor.fetchone()
            except:
                pass
            
            # 테이블 설명 텍스트 생성
            description = f"""
            테이블명: {table_name}
            설명: {table['TABLE_COMMENT'] or '설명 없음'}
            예상 행 수: {table['TABLE_ROWS'] or '알 수 없음'}
            생성일: {table['CREATE_TIME'] or '알 수 없음'}
            마지막 수정: {table['UPDATE_TIME'] or '알 수 없음'}
            
            컬럼 정보:
            {chr(10).join(f"- {col['COLUMN_NAME']} ({col['DATA_TYPE']}) {'NULL 허용' if col['IS_NULLABLE']=='YES' else 'NULL 불가'} {': '+col['COLUMN_COMMENT'] if col['COLUMN_COMMENT'] else ''}" for col in columns)}
            
            {'샘플 데이터: ' + str(sample_data) if sample_data else '샘플 데이터 없음'}
            """
            
            table_info.append({
                'table': table_name,
                'description': description,
                'columns': columns,
                'sample': sample_data
            })
        
        cursor.close()
        conn.close()
        
        if not query or query.lower() in ['all', '전체', '목록']:
            # 전체 테이블 목록 요청시 모든 정보 반환
            return table_info
        
        # 의미적 유사도 계산
        vectorizer = TfidfVectorizer()
        descriptions = [info['description'] for info in table_info]
        vectors = vectorizer.fit_transform(descriptions + [query])
        similarities = cosine_similarity(vectors[-1:], vectors[:-1])[0]
        
        # 유사도 순으로 정렬
        matches = []
        for i, sim in enumerate(similarities):
            if sim > 0.1:  # 유사도 임계값
                matches.append({
                    'table': table_info[i]['table'],
                    'similarity': float(sim),
                    'description': table_info[i]['description'],
                    'columns': table_info[i]['columns'],
                    'sample': table_info[i]['sample']
                })
        
        return sorted(matches, key=lambda x: x['similarity'], reverse=True)
    except Exception as e:
        print(f"Error in get_semantic_table_matches: {e}")
        return {'error': str(e)}

def get_semantic_row_matches(query, table_name, limit=10):
    """테이블 내에서 쿼리와 의미적으로 관련된 행을 찾는 함수"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4'
        )
        cursor = conn.cursor(dictionary=True)
        
        # 테이블의 텍스트 타입 컬럼 찾기
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = %s 
            AND DATA_TYPE IN ('varchar', 'text', 'longtext')
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        text_columns = [row['COLUMN_NAME'] for row in cursor.fetchall()]
        
        if not text_columns:
            return {'error': '텍스트 컬럼이 없는 테이블입니다.'}
        
        # 텍스트 컬럼들의 데이터를 하나의 문자열로 합쳐서 가져오기
        concat_columns = "CONCAT_WS(' ', " + ", ".join(text_columns) + ")"
        cursor.execute(f"SELECT *, {concat_columns} as combined_text FROM {table_name}")
        rows = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not rows:
            return {'error': '테이블에 데이터가 없습니다.'}
        
        # 의미적 유사도 계산
        vectorizer = TfidfVectorizer()
        texts = [row['combined_text'] for row in rows]
        vectors = vectorizer.fit_transform(texts + [query])
        similarities = cosine_similarity(vectors[-1:], vectors[:-1])[0]
        
        # 유사도 순으로 정렬
        matches = []
        for i, sim in enumerate(similarities):
            if sim > 0.1:  # 유사도 임계값
                row_data = {k: v for k, v in rows[i].items() if k != 'combined_text'}
                matches.append({
                    'row': row_data,
                    'similarity': float(sim)
                })
        
        return sorted(matches, key=lambda x: x['similarity'], reverse=True)[:limit]
    except Exception as e:
        return {'error': str(e)}

def format_db_info_for_llm(db_info):
    """DataFrame 정보를 LLM을 위한 문자열로 포맷팅"""
    if not db_info:
        return "데이터베이스 정보를 가져올 수 없습니다."
    
    formatted_text = "[newbiz 데이터베이스 정보]\n\n"
    
    # 1. 전체 테이블 목록 및 요약
    tables_df = db_info['tables']
    formatted_text += f"총 테이블 수: {len(tables_df)}개\n\n"
    
    # 2. 각 테이블별 상세 정보
    for idx, table in tables_df.iterrows():
        table_name = table['TABLE_NAME']
        
        # 테이블 기본 정보
        formatted_text += f"{idx+1}. {table_name}\n"
        formatted_text += f"   설명: {table['TABLE_COMMENT'] if pd.notna(table['TABLE_COMMENT']) else '설명 없음'}\n"
        formatted_text += f"   생성일: {table['CREATE_TIME']}\n"
        formatted_text += f"   마지막 수정: {table['UPDATE_TIME']}\n"
        
        # 테이블 통계
        if table_name in db_info['stats']:
            stats = db_info['stats'][table_name]
            formatted_text += f"   총 행 수: {stats['total_rows']:,}개\n"
            formatted_text += f"   컬럼 수: {stats['columns']}개\n"
        
        # 컬럼 정보
        columns = db_info['columns'][db_info['columns']['TABLE_NAME'] == table_name]
        formatted_text += "   컬럼 목록:\n"
        for _, col in columns.iterrows():
            col_desc = f"   - {col['COLUMN_NAME']} ({col['DATA_TYPE']})"
            if pd.notna(col['COLUMN_COMMENT']):
                col_desc += f": {col['COLUMN_COMMENT']}"
            formatted_text += col_desc + "\n"
        
        # 샘플 데이터
        if table_name in db_info['samples']:
            sample_df = db_info['samples'][table_name]
            if not sample_df.empty:
                formatted_text += "   샘플 데이터 (최근 5개 중 일부 컬럼):\n"
                # 너무 길어지지 않도록 처음 3개 컬럼만 표시
                sample_str = sample_df.head().iloc[:, :3].to_string()
                formatted_text += "   " + sample_str.replace("\n", "\n   ") + "\n"
        
        formatted_text += "-" * 80 + "\n"
    
    return formatted_text

def build_jarvis_prompt(rag, user_input):
    prompt = ''
    
    # 테이블 관련 키워드가 있는지 확인
    table_keywords = ['테이블', 'table', 'db', 'database', '데이터베이스']
    is_table_query = any(kw in user_input.lower() for kw in table_keywords)
    
    if is_table_query:
        # pandas DataFrame으로 DB 정보 가져오기
        db_info = get_db_info_as_dataframes()
        if db_info:
            # LLM을 위한 포맷으로 변환
            formatted_info = format_db_info_for_llm(db_info)
            prompt += formatted_info + "\n"
        else:
            prompt += "[데이터베이스 조회 오류] 데이터베이스 정보를 가져올 수 없습니다.\n"
    
    # 기존 RAG 정보 추가
    if rag['db_keyword']:
        prompt += '[DB에서 직접 키워드 매칭된 정보]\n' + '\n'.join(rag['db_keyword']) + '\n\n'
    if rag['chat_keyword']:
        prompt += '[대화에서 직접 키워드 매칭]\n' + '\n'.join(rag['chat_keyword']) + '\n\n'
    if rag['db_semantic']:
        prompt += '[DB 의미 기반 유사 정보]\n' + '\n'.join(rag['db_semantic']) + '\n\n'
    if rag['chat_semantic']:
        prompt += '[대화 의미 기반 유사 정보]\n' + '\n'.join(rag['chat_semantic']) + '\n\n'
    # 2. 파일/웹 기반 정보
    if rag['file_keyword']:
        prompt += '[파일에서 직접 키워드 매칭]\n' + '\n'.join(rag['file_keyword']) + '\n\n'
    if rag['web_keyword']:
        prompt += '[웹사이트에서 직접 키워드 매칭]\n' + '\n'.join(rag['web_keyword']) + '\n\n'
    if rag['file_semantic']:
        prompt += '[파일 의미 기반 유사 정보]\n' + '\n'.join(rag['file_semantic']) + '\n\n'
    if rag['web_semantic']:
        prompt += '[웹사이트 의미 기반 유사 정보]\n' + '\n'.join(rag['web_semantic']) + '\n\n'
    # 3. DB 전체 테이블 의미 기반 유사 정보 (맨 마지막에만 첨부)
    all_db_rag = search_all_db_tables_for_rag(user_input)
    # --- 실제 meeting_records.title 추출 ---
    meeting_titles = []
    meeting_detail = None
    meeting_multi_detail = []
    # title 후보 추출(질문에 포함된 title이 있으면)
    if 'meeting_records' in user_input.lower():
        try:
            meeting_titles = get_meeting_titles(10)
        except Exception as e:
            meeting_titles = [f'오류: {e}']
        # 질문에 title 후보가 포함되어 있으면 상세 정보도 추출
        for t in meeting_titles:
            if t in user_input:
                try:
                    meeting_detail = get_meeting_record_by_title(t)
                except Exception as e:
                    meeting_detail = {'오류': str(e)}
                break
        # --- 다중 row: 키워드가 포함된 모든 row 추출 ---
        # (예: '독서토론' 등)
        m = re.search(r'meeting_records.*?(\w+)', user_input.lower())
        keyword = None
        if m:
            # meeting_records 다음에 나오는 단어를 키워드로 사용
            keyword = m.group(1)
        # 또는, "~라는 단어가 포함된" 패턴에서 키워드 추출
        m2 = re.search(r'([\w가-힣]+)[\s,]*[이라는|라는|가 포함된|포함된]', user_input)
        if m2:
            keyword = m2.group(1)
        if keyword:
            # 정규화: 소문자, 공백/특수문자 제거
            keyword_norm = re.sub(r'[^가-힣a-zA-Z0-9]', '', keyword).lower()
            try:
                meeting_multi_detail = get_meeting_records_by_keyword(keyword_norm, limit=10)
            except Exception as e:
                meeting_multi_detail = [{'오류': str(e)}]
    # 프롬프트에 실제 meeting_records.title 첨부
    if meeting_titles:
        prompt += '[실제 meeting_records.title]\n' + '\n'.join(meeting_titles) + '\n\n'
    # 프롬프트에 meeting_records 상세 정보 첨부
    if meeting_detail:
        prompt += '[meeting_records 상세 정보]\n'
        for k, v in meeting_detail.items():
            prompt += f'{k}: {v}\n'
        prompt += '\n'
    # 프롬프트에 meeting_records 다중 row 상세 정보 첨부
    if meeting_multi_detail:
        prompt += '[meeting_records 다중 row 상세 정보]\n'
        for idx, row in enumerate(meeting_multi_detail, 1):
            prompt += f'- row {idx}:\n'
            for k, v in row.items():
                if k in ['summary', 'full_text'] and (not v or str(v).strip() == ''):
                    v = '내용 없음'
                prompt += f'    {k}: {v}\n'
            prompt += '\n'
        prompt += (
            '위의 각 row에 대해 title, summary, full_text, action_items 등 모든 컬럼을 반드시 참고하여 각각의 내용을 요약해 주세요. '
            '특히 summary, full_text, action_items에 실제 내용이 있으면 반드시 포함하세요. '
            'title만 나열하지 말고, 각 row의 실제 내용을 요약해 주세요. '
            '아래의 표/JSON 구조를 그대로 참고하세요. title만 요약하지 말고 반드시 모든 컬럼을 반영하세요.\n'
        )
    # 프롬프트에 DB 전체 테이블 유사 정보(구조적) 첨부
    if all_db_rag:
        already = set(prompt)
        filtered = [x for x in all_db_rag if str(x) not in already]
        if filtered:
            prompt += '[DB 전체 테이블 유사 정보]\n'
            for item in filtered:
                prompt += f'- [테이블: {item["table"]}] (유사도: {item["similarity"]:.2f})\n'
                for k, v in item['row'].items():
                    prompt += f'    {k}: {v}\n'
                prompt += '\n'
            prompt += '(참고: 위 정보는 대화 이력에 직접적으로 관련된 정보가 부족할 때만 보조적으로 활용하세요.)\n\n'
    # --- 모든 테이블의 칼럼 정보와 샘플 row를 DataFrame 기반으로 프롬프트에 추가 ---
    try:
        # 질문에서 keyword 추출 (예: '독서토론')
        m = re.search(r'([\w가-힣]+)[\s,]*(?:이라는|라는|가 포함된|포함된|관련된|관련|리스트|요약|회의|미팅)', user_input)
        if m:
            keyword = m.group(1)
        # 추가: meeting_records에서 ~, ~와 관련된, ~ 포함된 등 다양한 패턴 지원
        m2 = re.search(r'meeting_records.*?(\w+)', user_input.lower())
        if m2:
            keyword = m2.group(1)
        all_info = get_all_table_columns_and_samples(sample_n=2, keyword=keyword)
        prompt += '\n[DB 전체 테이블 구조 및 샘플]\n'
        for table, info in all_info.items():
            prompt += f'[{table}]\n- 컬럼: {', '.join(info["columns"])}\n- 샘플 데이터:\n'
            for row in info["sample_rows"]:
                import json
                prompt += f'    {json.dumps(row, ensure_ascii=False)}\n'
        prompt += (
            '\n반드시 위의 컬럼명과 샘플 row만 사용해서 답변하세요. 임의의 컬럼명을 상상하지 말고, 실제 존재하는 컬럼만 사용하세요.\n'
            'title만 요약하지 말고 summary, full_text, action_items 등 모든 컬럼을 반드시 반영하세요.\n'
            '아래의 표/JSON 구조를 그대로 참고하세요. title만 요약하지 말고 반드시 모든 컬럼을 반영하세요.\n'
            '샘플 row 외에도 실제 DB에 값이 있는 row가 더 있을 수 있으니, 반드시 모든 row를 요약하라. summary/full_text/action_items가 비어있지 않은 row가 있으면 반드시 그 내용을 반영하라.\n'
        )
    except Exception as e:
        prompt += f"[DB 전체 테이블 구조/샘플 정보 오류: {e}]\n"
    # 4. 실제 질문 및 안내
    prompt += (
        '위 정보를 바탕으로, 다음 사항을 준수하여 답변해주세요:\n'
        '1. 테이블 목록과 각 테이블의 주요 정보를 명확하게 설명\n'
        '2. 각 테이블의 용도와 주요 컬럼 설명\n'
        '3. 데이터 현황(행 수 등) 포함\n'
        '4. 가능한 경우 샘플 데이터로 예시 설명\n\n'
        f'{user_input}'
    )
    return prompt

# --- JARVIS 답변 생성 ---
def get_jarvis_answer(prompt, use_langchain, selected_model, selected_ai_api, files=None, speaker=None):
    answer = ''
    # 1. LLM 호출 (Claude/OpenAI)
    try:
        if selected_ai_api == 'OpenAI (GPT)':
            llm = ChatOpenAI(model=selected_model or "gpt-4o", openai_api_key=os.getenv('OPENAI_API_KEY'), max_tokens=4096)
        elif selected_ai_api == 'Anthropic (Claude)':
            llm = ChatAnthropic(model=selected_model or "claude-3-7-sonnet-latest", api_key=os.getenv('ANTHROPIC_API_KEY'), max_tokens=4096)
        else:
            llm = ChatOpenAI(model="gpt-4o", openai_api_key=os.getenv('OPENAI_API_KEY'), max_tokens=4096)
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        answer = ''
    # 2. LangChain 멀티툴 Agent fallback (웹검색, 계산 등)
    if (not answer or not str(answer).strip()) and use_langchain:
        # Firecrawl 웹검색 툴 등 기존과 동일하게
        import requests
        def firecrawl_search(query: str) -> str:
            api_key = os.getenv('FIRECRAWL_API_KEY')
            url = "https://api.firecrawl.dev/v1/search"
            headers = {"Authorization": f"Bearer {api_key}"}
            params = {"q": query, "num_results": 5}
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if not results:
                        return "검색 결과가 없습니다."
                    return "\n\n".join([f"{r['title']}\n{r['url']}\n{r.get('snippet','')}" for r in results])
                else:
                    return f"Firecrawl 검색 오류: {response.status_code} {response.text}"
            except Exception as e:
                return f"Firecrawl 검색 예외: {e}"
        firecrawl_tool = Tool(
            name="Firecrawl Web Search",
            func=firecrawl_search,
            description="실시간 웹 검색이 필요할 때 사용 (Firecrawl API 기반)"
        )
        wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        calc_tool = PythonREPLTool()
        tools = [
            firecrawl_tool,
            Tool(name="Wikipedia", func=wiki_tool.run, description="백과사전 정보가 필요할 때 사용"),
            Tool(name="Calculator", func=calc_tool.run, description="수식 계산, 데이터 분석, 파이썬 코드 실행"),
        ]
        if files:
            for f in files:
                if 'preview' in f and f['preview']:
                    tools.append(Tool(name=f"Summary of {f['filename']}", func=lambda x, t=f['preview']: t[:500], description=f"업로드 파일 {f['filename']} 요약"))
        if selected_ai_api == 'OpenAI (GPT)':
            llm_agent = ChatOpenAI(model=selected_model or "gpt-4o", openai_api_key=os.getenv('OPENAI_API_KEY'), max_tokens=4096)
        elif selected_ai_api == 'Anthropic (Claude)':
            llm_agent = ChatAnthropic(model=selected_model or "claude-3-7-sonnet-latest", api_key=os.getenv('ANTHROPIC_API_KEY'), max_tokens=4096)
        else:
            llm_agent = ChatOpenAI(model="gpt-4o", openai_api_key=os.getenv('OPENAI_API_KEY'), max_tokens=4096)
        agent = initialize_agent(tools, llm_agent, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False)
        try:
            answer = agent.run(prompt)
        except Exception as e:
            answer = ''
    # 3. 기본 안내 메시지
    if not answer or not str(answer).strip():
        answer = "죄송합니다. 관련된 답변을 찾지 못했습니다."
    # --- 화자 첫 대화 시 인사 ---
    if speaker:
        import mysql.connector
        try:
            conn = mysql.connector.connect(
                host=os.getenv('SQL_HOST'),
                user=os.getenv('SQL_USER'),
                password=os.getenv('SQL_PASSWORD'),
                database=os.getenv('SQL_DATABASE_NEWBIZ'),
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jarvis_interactions WHERE speaker = %s", (speaker,))
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            if count == 0:
                answer = f"JARVIS: 처음 뵙겠습니다, {speaker}. 앞으로 잘 부탁드립니다.\n" + answer
        except Exception as e:
            pass
    # 항상 JARVIS: prefix, 중복 방지 (대소문자, 공백 무시)
    answer = answer.strip()
    # Remove double prefix if present
    answer = re.sub(r'^(\s*jarvis:)(\s*jarvis:)+', r'JARVIS:', answer, flags=re.IGNORECASE)
    # Remove any accidental 'JARVIS: JARVIS:'
    answer = re.sub(r'^(\s*jarvis:)\s*jarvis:', r'JARVIS:', answer, flags=re.IGNORECASE)
    # Add prefix if missing
    if not re.match(r'^\s*jarvis:', answer, re.IGNORECASE):
        answer = "JARVIS: " + answer
    return answer

# --- 마지막 요청 질의 감지 함수 ---
def is_last_request_query(user_input):
    keywords = [
        '이전 대화', '최근 기록', '지난 회의', '대화 히스토리', '최근 질문', '최근 답변',
        '대화 내역', '과거 대화', '마지막 대화', '최근 대화', '기록 보여줘', '기록 알려줘',
        '대화 보여줘', '대화 알려줘', '히스토리', 'history', 'log', 'meeting', '요약'
    ]
    return any(k in user_input for k in keywords)

def get_last_meaningful_request(user_id, n=5):
    rows = load_conversation_history(user_id, limit=n)
    if not rows:
        return "저장된 대화 기록이 없습니다."
    history_lines = []
    for r in rows:
        history_lines.append(f"[{r['created_at']}] 질문: {r['user_input']}\n답변: {r['jarvis_response']}")
    return '\n\n'.join(history_lines)

# --- LangChain 멀티툴/기존 분석 에이전트 함수 ---
def analyze_with_agents(user_input, files, audio, user_history, agent_tools, use_langchain=False, selected_model=None, selected_ai_api=None):
    results = {}
    logs = []
    # ... (함수 본문은 기존대로 유지, 모든 return에서 results, logs 반환)
    # ...
    return results, logs

# --- 4. 사용자/세션 정보 ---
user_id = "user1"  # 실제 구현시 로그인/세션 기반
user_history = load_user_history(user_id)

# --- 메인 대화/분석 컨테이너 (입력+결과 한 화면) ---
main_area = st.container()
with main_area:
    # --- 웹사이트 RAG: Streamlit UI 및 세션 상태 ---
    if 'website_texts' not in st.session_state:
        st.session_state['website_texts'] = []
    with st.expander('🌐 웹사이트 RAG 데이터 추가', expanded=False):
        website_url = st.text_input('웹사이트 URL 입력', key='website_url')
        max_pages = st.slider('최대 크롤링 페이지 수', 1, 10, 3, key='website_max_pages')
        if st.button('웹사이트 크롤링', key='website_crawl_btn') and website_url:
            with st.spinner('웹사이트 크롤링 중...'):
                website_texts = scrape_website_simple(website_url, max_pages)
                if website_texts:
                    st.session_state['website_texts'] = [w['content'] for w in website_texts]
                    st.success(f"{len(website_texts)}개 페이지 크롤링 완료!")
                else:
                    st.warning('크롤링 결과가 없습니다.')
        if st.session_state['website_texts']:
            st.info(f"현재 {len(st.session_state['website_texts'])}개 웹페이지 텍스트가 RAG에 포함됩니다.")

    with st.form(key="jarvis_input_form"):
        st.markdown("#### 메시지 입력 (JARVIS)")
        col1, col2 = st.columns([3,1])
        with col1:
            user_input = st.text_area("텍스트/명령/질문 입력", key="user_input")
        with col2:
            audio_file = st.file_uploader("음성 업로드(mp3/wav)", type=["mp3","wav"], key="audio_input")
        file_uploads = st.file_uploader("문서/이미지/파일 업로드", type=["pdf","docx","xlsx","pptx","png","jpg","jpeg","txt","md"], accept_multiple_files=True, key="file_input")
        agent_tools = {"대화에이전트": ["기본대화"], "문서분석에이전트": ["문서분석"], "음성에이전트": ["음성분석"], "보고에이전트": ["보고서"]}
        use_langchain = st.checkbox("LangChain 사용", value=False)
        submit_btn = st.form_submit_button("JARVIS에게 요청")

    if submit_btn:
        try:
            file_previews = parse_uploaded_files(file_uploads) if file_uploads else []
            audio_data = audio_file.read() if audio_file else None
            website_texts = st.session_state.get('website_texts', [])
            rag = extract_rag_sources(user_id, user_input, file_previews, website_texts)
            prompt = build_jarvis_prompt(rag, user_input)
            answer = get_jarvis_answer(prompt, use_langchain, st.session_state.selected_model, st.session_state.selected_ai_api, files=file_previews, speaker=selected_speaker)
            st.session_state['chat_history'].append({'role': 'user', 'content': user_input, 'speaker': selected_speaker})
            st.session_state['chat_history'].append({'role': 'jarvis', 'content': answer, 'speaker': selected_speaker})
            st.session_state.jarvis_last_results = {'대화에이전트': answer}
            st.session_state.jarvis_last_logs = [prompt]
            st.session_state.jarvis_last_input = user_input
            st.session_state.jarvis_last_files = file_previews
            st.session_state.jarvis_last_audio = audio_data
        except Exception as e:
            st.error(f"[JARVIS 오류] {e}")
            import traceback
            st.error(traceback.format_exc())

    # 누적 대화 히스토리 출력 (ChatGPT/Claude 스타일)
    if st.session_state.get('chat_history'):
        st.markdown('---')
        for msg in st.session_state['chat_history']:
            if msg['role'] == 'user':
                st.markdown(f"**🙋‍♂️ {msg.get('speaker', selected_speaker)}:** {msg['content']}")
            else:
                answer_html = msg['content'].replace('\n', '<br>') if isinstance(msg['content'], str) else msg['content']
                st.markdown(f"**🤖 JARVIS:** {answer_html}", unsafe_allow_html=True)
    # 참고 데이터(References) 표기 (마지막 JARVIS 답변 기준)
    if st.session_state.get('jarvis_last_results'):
        references = []
        if st.session_state.get('jarvis_last_logs'):
            if any('DB 테이블' in log or 'newbiz DB' in log for log in st.session_state['jarvis_last_logs']):
                references.append('DB(대화/테이블)')
        if st.session_state.get('website_texts'):
            if len(st.session_state['website_texts']) > 0:
                references.append('웹사이트 크롤링')
        if references:
            st.markdown('---')
            st.markdown('**참고 데이터(References):** ' + ', '.join(references))
        save_interaction(user_id, selected_speaker, {"input": st.session_state.jarvis_last_input, "results": st.session_state.jarvis_last_results, "logs": st.session_state.jarvis_last_logs}, files=st.session_state.jarvis_last_files, audio=st.session_state.jarvis_last_audio)

# --- 9. 파일 미리보기 (업로드시) ---
if 'jarvis_last_files' in st.session_state and st.session_state.jarvis_last_files:
    st.markdown("#### 업로드 파일 미리보기 (최신 요청 기준)")
    for f in st.session_state.jarvis_last_files:
        st.write(f["filename"])
        st.write(f["preview"][:500])

def download_history_as_csv(history_rows):
    import pandas as pd
    df = pd.DataFrame(history_rows)
    if not df.empty:
        df = df.rename(columns={
            'created_at': '시간',
            'user_input': '질문',
            'jarvis_response': '답변',
            'files_json': '파일',
            'logs_json': '로그',
        })
        return df.to_csv(index=False).encode('utf-8-sig')
    return b''

# --- 하단: 대화 히스토리/검색/다운로드 UI ---
with st.expander('💬 JARVIS 대화 히스토리/검색/다운로드', expanded=False):
    selected_speaker = st.session_state['selected_speaker']
    search_kw = st.text_input('키워드로 대화 검색', key='history_search_kw')
    if 'user_id' in locals():
        hist_rows = load_conversation_history(user_id, search_kw)
        # speaker 컬럼이 있는 경우만 필터링
        hist_rows = [r for r in hist_rows if r.get('speaker') == selected_speaker]
        if hist_rows:
            st.write(f"총 {len(hist_rows)}건의 대화 기록 (화자: {selected_speaker})")
            st.dataframe([
                {
                    '시간': r['created_at'],
                    '질문': r['user_input'],
                    '답변': r['jarvis_response'],
                    '파일': r['files_json'],
                    '로그': r['logs_json'],
                } for r in hist_rows
            ], hide_index=True)
            csv_bytes = download_history_as_csv(hist_rows)
            st.download_button('CSV로 다운로드', data=csv_bytes, file_name=f'jarvis_history_{selected_speaker}.csv', mime='text/csv')
            # --- 화자별 대화 기록 전체 삭제 버튼 ---
            if st.button(f'⚠️ {selected_speaker}의 대화 기록 전체 삭제', key='delete_speaker_history'):
                try:
                    conn = mysql.connector.connect(
                        host=os.getenv('SQL_HOST'),
                        user=os.getenv('SQL_USER'),
                        password=os.getenv('SQL_PASSWORD'),
                        database=os.getenv('SQL_DATABASE_NEWBIZ'),
                        charset='utf8mb4'
                    )
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM jarvis_interactions WHERE speaker = %s", (selected_speaker,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f'{selected_speaker}의 대화 기록이 모두 삭제되었습니다.')
                    st.rerun()
                except Exception as e:
                    st.error(f'삭제 중 오류: {e}')
        else:
            st.info(f'{selected_speaker}의 대화 기록이 없습니다.')
    else:
        st.info('로그인/세션 정보가 필요합니다.') 

def connect_to_db():
    """Virtual Company 스타일의 데이터베이스 연결 함수"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ')
        )
        return connection
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

def get_table_schema(table_name):
    """테이블 스키마 정보를 가져오는 함수"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        columns = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return columns
    except Exception as e:
        st.error(f"스키마 조회 오류: {e}")
        return None

def get_mysql_tables():
    """데이터베이스의 모든 테이블 목록을 가져오는 함수"""
    try:
        conn = connect_to_db()
        if not conn:
            return []
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                TABLE_NAME,
                TABLE_COMMENT,
                TABLE_ROWS,
                CREATE_TIME,
                UPDATE_TIME
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        
        tables = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return tables
    except Exception as e:
        st.error(f"테이블 목록 조회 오류: {e}")
        return []

def load_mysql_data(table_name, limit=1000):
    """특정 테이블의 데이터를 pandas DataFrame으로 로드하는 함수"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return None

def get_db_info_as_dataframes():
    """데이터베이스 정보를 pandas DataFrame으로 가져오는 함수 (개선된 버전)"""
    try:
        # 1. 테이블 목록과 정보
        tables = get_mysql_tables()
        if not tables:
            return None
        
        tables_df = pd.DataFrame(tables, columns=['TABLE_NAME', 'TABLE_COMMENT', 'TABLE_ROWS', 'CREATE_TIME', 'UPDATE_TIME'])
        
        # 2. 각 테이블의 스키마와 샘플 데이터
        schema_info = {}
        sample_data = {}
        
        for table_name in tables_df['TABLE_NAME']:
            # 스키마 정보
            schema = get_table_schema(table_name)
            if schema:
                schema_info[table_name] = pd.DataFrame(schema)
            
            # 샘플 데이터
            df = load_mysql_data(table_name, limit=5)
            if df is not None and not df.empty:
                sample_data[table_name] = df
        
        return {
            'tables': tables_df,
            'schemas': schema_info,
            'samples': sample_data
        }
    except Exception as e:
        st.error(f"데이터베이스 정보 수집 오류: {e}")
        return None

def format_db_info_for_llm(db_info):
    """DataFrame 정보를 LLM을 위한 문자열로 포맷팅 (개선된 버전)"""
    if not db_info:
        return "데이터베이스 정보를 가져올 수 없습니다."
    
    formatted_text = "[newbiz 데이터베이스 정보]\n\n"
    
    # 1. 전체 테이블 목록 및 요약
    tables_df = db_info['tables']
    formatted_text += f"총 테이블 수: {len(tables_df)}개\n\n"
    
    # 2. 각 테이블별 상세 정보
    for idx, table in tables_df.iterrows():
        table_name = table['TABLE_NAME']
        
        # 테이블 기본 정보
        formatted_text += f"{idx+1}. {table_name}\n"
        formatted_text += f"   설명: {table['TABLE_COMMENT'] if pd.notna(table['TABLE_COMMENT']) else '설명 없음'}\n"
        formatted_text += f"   예상 행 수: {table['TABLE_ROWS'] if pd.notna(table['TABLE_ROWS']) else '알 수 없음'}\n"
        formatted_text += f"   생성일: {table['CREATE_TIME']}\n"
        formatted_text += f"   마지막 수정: {table['UPDATE_TIME']}\n"
        
        # 스키마 정보
        if table_name in db_info['schemas']:
            schema_df = db_info['schemas'][table_name]
            formatted_text += "   컬럼 정보:\n"
            for _, col in schema_df.iterrows():
                col_desc = f"   - {col['COLUMN_NAME']} ({col['DATA_TYPE']})"
                if col['IS_NULLABLE'] == 'NO':
                    col_desc += " [필수]"
                if col['COLUMN_KEY'] == 'PRI':
                    col_desc += " [기본키]"
                if pd.notna(col['COLUMN_COMMENT']):
                    col_desc += f": {col['COLUMN_COMMENT']}"
                formatted_text += col_desc + "\n"
        
        # 샘플 데이터
        if table_name in db_info['samples']:
            sample_df = db_info['samples'][table_name]
            formatted_text += "   샘플 데이터 (최근 5개 중 일부):\n"
            sample_str = sample_df.head().to_string()
            formatted_text += "   " + sample_str.replace("\n", "\n   ") + "\n"
        
        formatted_text += "-" * 80 + "\n"
    
    return formatted_text

# --- MySQL 연결 클래스 업데이트 ---
class MySQLConnection:
    """MySQL 연결을 관리하는 클래스 (개선된 버전)"""
    def __init__(self):
        self.config = {
            'host': os.getenv('SQL_HOST'),
            'user': os.getenv('SQL_USER'),
            'password': os.getenv('SQL_PASSWORD'),
            'database': os.getenv('SQL_DATABASE_NEWBIZ'),
            'charset': 'utf8mb4'
        }
        self._connection = None
        self._engine = None
    
    def get_connection(self):
        """MySQL 커넥션 반환 (연결 실패시 None)"""
        try:
            if not self._connection or not self._connection.is_connected():
                self._connection = mysql.connector.connect(**self.config)
            return self._connection
        except Exception as e:
            st.error(f"MySQL 연결 오류: {e}")
            return None
    
    def get_engine(self):
        """SQLAlchemy 엔진 반환"""
        if not self._engine:
            try:
                self._engine = create_engine(
                    f"mysql+mysqlconnector://{self.config['user']}:{self.config['password']}@{self.config['host']}/{self.config['database']}?charset={self.config['charset']}"
                )
            except Exception as e:
                st.error(f"SQLAlchemy 엔진 생성 오류: {e}")
                return None
        return self._engine
    
    def execute_query(self, query, params=None):
        """쿼리 실행 및 결과 반환 (실패시 None)"""
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
            return result
        except Exception as e:
            st.error(f"쿼리 실행 오류: {e}")
            return None
        finally:
            cursor.close()
    
    def execute_query_pandas(self, query, params=None):
        """pandas DataFrame으로 쿼리 결과 반환 (실패시 빈 DataFrame)"""
        engine = self.get_engine()
        if not engine:
            return pd.DataFrame()
        
        try:
            return pd.read_sql(query, engine, params=params)
        except Exception as e:
            st.error(f"pandas 쿼리 실행 오류: {e}")
            return pd.DataFrame()

# 전역 MySQL 연결 객체 재생성
mysql_conn = MySQLConnection()