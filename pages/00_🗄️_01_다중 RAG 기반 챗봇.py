import streamlit as st
import os
from datetime import datetime
import time
import random
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
from langchain_anthropic import ChatAnthropic
import json
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# RAG 관련 import 추가
import mysql.connector
import pandas as pd
from sqlalchemy import create_engine
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import nltk
import logging
from pathlib import Path
import hashlib

# 벡터 데이터베이스 관련 import
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.faiss import FAISS
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import UnstructuredFileLoader
from langchain.schema import Document

# 청크 처리 함수 import
from chunk_processor import process_chunked_rag

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="🤖 다중 RAG 기반 챗봇 🗄️",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 다중 RAG 기반 챗봇 🗄️")

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

st.markdown("RAG 기반 AI 어시스턴트 - MySQL DB, 웹사이트, 문서 분석 지원")

# 표준화된 데이터베이스 연결 함수
def connect_to_db():
    """데이터베이스 연결"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

def create_rag_agent_tables():
    """RAG 에이전트용 테이블 생성"""
    try:
        connection = connect_to_db()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # 1. 메인 대화 세션 테이블
        rag_conversations_table = """
        CREATE TABLE IF NOT EXISTS rag_conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_title VARCHAR(255) NOT NULL COMMENT '대화 세션 제목',
            user_query TEXT NOT NULL COMMENT '사용자 질문',
            assistant_response LONGTEXT COMMENT 'AI 응답',
            model_name VARCHAR(100) NOT NULL COMMENT '사용된 AI 모델',
            has_reasoning BOOLEAN DEFAULT FALSE COMMENT 'reasoning 포함 여부',
            reasoning_content LONGTEXT COMMENT 'reasoning 과정',
            rag_sources_used INT DEFAULT 0 COMMENT '사용된 RAG 소스 수',
            execution_time_seconds INT COMMENT '응답 생성 시간(초)',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            tags VARCHAR(500) COMMENT '검색용 태그',
            notes TEXT COMMENT '추가 메모',
            INDEX idx_created_at (created_at),
            INDEX idx_model_name (model_name),
            INDEX idx_has_reasoning (has_reasoning),
            FULLTEXT idx_search (session_title, user_query, tags, notes)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG 에이전트 대화 세션';
        """
        cursor.execute(rag_conversations_table)
        
        # 2. RAG 소스 정보 테이블
        rag_sources_table = """
        CREATE TABLE IF NOT EXISTS rag_conversation_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            conversation_id INT NOT NULL COMMENT '대화 세션 ID',
            source_type ENUM('mysql', 'website', 'files') NOT NULL COMMENT 'RAG 소스 타입',
            source_name VARCHAR(255) NOT NULL COMMENT '소스 이름',
            source_description TEXT COMMENT '소스 설명',
            source_details JSON COMMENT '소스 상세 정보',
            data_size INT COMMENT '데이터 크기',
            content_preview TEXT COMMENT '데이터 미리보기',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES rag_conversations(id) ON DELETE CASCADE,
            INDEX idx_conversation_id (conversation_id),
            INDEX idx_source_type (source_type),
            INDEX idx_source_name (source_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG 소스 정보';
        """
        cursor.execute(rag_sources_table)
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        st.error(f"테이블 생성 오류: {str(e)}")
        return False

def get_mysql_tables():
    """MySQL 테이블 목록 조회"""
    try:
        connection = connect_to_db()
        if not connection:
            return []
        
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        return tables
    except Exception as e:
        st.error(f"테이블 조회 오류: {str(e)}")
        return []

def load_mysql_data(selected_tables):
    """선택된 MySQL 테이블 데이터 로드"""
    mysql_data = {}
    
    try:
        connection = connect_to_db()
        if not connection:
            return mysql_data
        
        for table in selected_tables:
            try:
                query = f"SELECT * FROM {table} LIMIT 1000"
                df = pd.read_sql(query, connection)
                mysql_data[table] = df
                st.success(f"✅ {table} 테이블 로드 완료 ({len(df)}행)")
            except Exception as e:
                st.error(f"❌ {table} 테이블 로드 실패: {str(e)}")
        
        connection.close()
        return mysql_data
        
    except Exception as e:
        st.error(f"MySQL 데이터 로드 오류: {str(e)}")
        return mysql_data

def scrape_website_simple(url, max_pages=5):
    """간단한 웹사이트 스크래핑 - 개선된 버전"""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        visited_urls = set()
        scraped_data = []
        urls_to_visit = [url]
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        successfully_scraped = 0  # 실제로 스크래핑된 페이지 수
        
        while urls_to_visit and successfully_scraped < max_pages:
            current_url = urls_to_visit.pop(0)
            
            if current_url in visited_urls:
                continue
                
            try:
                response = session.get(current_url, timeout=10)
                response.raise_for_status()
                
                visited_urls.add(current_url)
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 페이지 제목 추출
                title = soup.find('title')
                title_text = title.get_text().strip() if title else f"페이지 {successfully_scraped + 1}"
                
                # 불필요한 태그 제거
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                
                # 본문 텍스트 추출
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = ' '.join(chunk for chunk in chunks if chunk)
                
                # 콘텐츠가 있으면 추가 (길이 제한 완화)
                if len(content) > 50:  # 50자로 기준 낮춤
                    scraped_data.append({
                        'url': current_url,
                        'title': title_text,
                        'content': content[:2000]  # 처음 2000자만
                    })
                    
                    successfully_scraped += 1
                    st.success(f"✅ 페이지 {successfully_scraped}/{max_pages} 스크래핑 완료: {title_text}")
                
                # 더 많은 링크 찾기 (제한 완화)
                base_domain = urlparse(url).netloc
                
                # 링크 탐색을 더 적극적으로
                for link in soup.find_all("a", href=True)[:20]:  # 20개로 증가
                    absolute_link = urljoin(current_url, link['href'])
                    parsed_link = urlparse(absolute_link)
                    
                    # 조건 완화: 같은 도메인 + 기본적인 필터링
                    if (parsed_link.netloc == base_domain and 
                        absolute_link not in visited_urls and 
                        absolute_link not in urls_to_visit and
                        not any(x in absolute_link.lower() for x in ['#', 'javascript:', 'mailto:', 'tel:']) and
                        len(urls_to_visit) < 50):  # 대기 큐 크기 제한
                        urls_to_visit.append(absolute_link)
                
                time.sleep(0.5)  # 지연시간 단축 (1초 → 0.5초)
                
            except Exception as e:
                st.warning(f"⚠️ 페이지 크롤링 실패 ({current_url}): {str(e)}")
                continue
        
        # 결과 메시지 개선
        if scraped_data:
            if successfully_scraped == max_pages:
                st.success(f"🎉 목표 달성! {successfully_scraped}개 페이지 크롤링 완료!")
            else:
                st.info(f"📄 {successfully_scraped}개 페이지 크롤링 완료 (목표: {max_pages}개)")
                if successfully_scraped < max_pages:
                    st.warning(f"💡 {max_pages - successfully_scraped}개 페이지 부족 - 사이트에 추가 링크가 부족할 수 있습니다.")
        else:
            st.error("❌ 크롤링된 페이지가 없습니다.")
        
        return scraped_data
        
    except Exception as e:
        st.error(f"❌ 웹사이트 스크래핑 실패: {str(e)}")
        return []

def process_files(files):
    """업로드된 파일 처리"""
    files_data = []
    
    for file in files:
        try:
            if file.type == "text/plain":
                content = str(file.read(), "utf-8")
            elif file.type == "application/pdf":
                # PDF 처리 (간단한 예시)
                content = "PDF 파일 - 전문 처리 필요"
            else:
                content = str(file.read(), "utf-8", errors='ignore')
            
            files_data.append({
                'name': file.name,
                'size': len(content),
                'content': content
            })
            
            st.success(f"✅ 파일 처리 완료: {file.name}")
            
        except Exception as e:
            st.error(f"❌ 파일 처리 실패 ({file.name}): {str(e)}")
    
    return files_data 

def create_rag_context(mysql_data=None, website_data=None, files_data=None, model_name=None):
    """RAG 컨텍스트 생성 - 모델별 크기 제한 적용"""
    context_parts = []
    rag_sources_used = []
    
    # 모델별 크기 제한 설정
    if model_name and model_name.startswith('claude'):
        MAX_CONTEXT_SIZE = 7000000  # 7MB
        MYSQL_SAMPLE_ROWS = 1
        CONTENT_PREVIEW_SIZE = 200
        apply_size_limit = True
        limit_type = "Claude 7MB"
    elif model_name and model_name.startswith('o1'):
        MAX_CONTEXT_SIZE = 800000   # 800KB
        MYSQL_SAMPLE_ROWS = 2
        CONTENT_PREVIEW_SIZE = 300
        apply_size_limit = True
        limit_type = "o1 800KB"
    elif model_name and (model_name.startswith('gpt-4') or model_name.startswith('gpt-3')):
        MAX_CONTEXT_SIZE = 3000000  # 3MB
        MYSQL_SAMPLE_ROWS = 3
        CONTENT_PREVIEW_SIZE = 500
        apply_size_limit = True
        limit_type = "GPT 3MB"
    else:
        MAX_CONTEXT_SIZE = 1000000  # 1MB
        MYSQL_SAMPLE_ROWS = 2
        CONTENT_PREVIEW_SIZE = 300
        apply_size_limit = True
        limit_type = "기본 1MB"
    
    current_size = 0
    
    # MySQL 데이터 컨텍스트
    if mysql_data and current_size < MAX_CONTEXT_SIZE:
        mysql_context = "=== MySQL 데이터베이스 정보 ===\n"
        mysql_tables = []
        total_mysql_rows = 0
        
        for table_name, df in mysql_data.items():
            table_info = f"\n[{table_name}] 테이블:\n"
            table_info += f"- 행 수: {len(df):,}개\n"
            table_info += f"- 컬럼: {', '.join(df.columns.tolist())}\n"
            
            mysql_tables.append(table_name)
            total_mysql_rows += len(df)
            
            if len(df) > 0:
                table_info += "- 샘플 데이터:\n"
                sample_data = df.head(MYSQL_SAMPLE_ROWS).to_string(index=False, max_cols=5 if apply_size_limit else None)
                if apply_size_limit and len(sample_data) > 500:
                    sample_data = sample_data[:500] + "..."
                table_info += sample_data + "\n"
            
            if current_size + len(table_info) > MAX_CONTEXT_SIZE:
                mysql_context += f"\n[테이블 {table_name} 생략 - {limit_type} 크기 제한 초과]\n"
                break
            
            mysql_context += table_info
            current_size += len(table_info)
        
        context_parts.append(mysql_context)
        rag_sources_used.append({
            'type': 'mysql',
            'name': 'MySQL 데이터베이스',
            'details': f"{len(mysql_tables)}개 테이블 ({total_mysql_rows:,}행)",
            'tables': mysql_tables
        })
    
    # 웹사이트 데이터 컨텍스트
    if website_data and current_size < MAX_CONTEXT_SIZE:
        website_context = "=== 웹사이트 크롤링 정보 ===\n"
        website_urls = []
        
        for i, page_data in enumerate(website_data[:3]):
            page_info = f"\n[페이지 {i+1}] {page_data['title']}\n"
            page_info += f"URL: {page_data['url']}\n"
            
            content_preview = page_data['content'][:CONTENT_PREVIEW_SIZE] + "..."
            page_info += f"내용 미리보기: {content_preview}\n"
            
            if apply_size_limit and current_size + len(page_info) > MAX_CONTEXT_SIZE:
                website_context += f"\n[페이지 {i+1} 생략 - 크기 제한 초과]\n"
                break
            
            website_context += page_info
            current_size += len(page_info)
            
            website_urls.append({
                'title': page_data['title'],
                'url': page_data['url']
            })
        
        context_parts.append(website_context)
        rag_sources_used.append({
            'type': 'website',
            'name': '웹사이트 크롤링',
            'details': f"{len(website_data)}개 페이지",
            'urls': website_urls
        })
    
    # 파일 데이터 컨텍스트
    if files_data and current_size < MAX_CONTEXT_SIZE:
        files_context = "=== 업로드된 문서 정보 ===\n"
        file_list = []
        total_file_size = 0
        
        for file_data in files_data:
            file_info = f"\n[문서] {file_data['name']}\n"
            file_info += f"크기: {file_data['size']:,}자\n"
            
            content_preview = file_data['content'][:CONTENT_PREVIEW_SIZE] + "..."
            file_info += f"내용 미리보기: {content_preview}\n"
            
            if apply_size_limit and current_size + len(file_info) > MAX_CONTEXT_SIZE:
                files_context += f"\n[파일 {file_data['name']} 생략 - 크기 제한 초과]\n"
                break
            
            files_context += file_info
            current_size += len(file_info)
            
            file_list.append(file_data['name'])
            total_file_size += file_data['size']
        
        context_parts.append(files_context)
        rag_sources_used.append({
            'type': 'files',
            'name': '업로드 문서',
            'details': f"{len(file_list)}개 파일 ({total_file_size:,}자)",
            'files': file_list
        })
    
    context_text = "\n\n".join(context_parts)
    
    final_size = len(context_text)
    if apply_size_limit:
        if final_size > MAX_CONTEXT_SIZE:
            st.warning(f"⚠️ RAG 컨텍스트가 너무 큽니다 ({final_size:,}자 > {MAX_CONTEXT_SIZE:,}자). 일부 데이터가 제외될 수 있습니다.")
            context_text = context_text[:MAX_CONTEXT_SIZE] + "\n\n[콘텐츠가 크기 제한으로 인해 잘렸습니다]"
        elif final_size > MAX_CONTEXT_SIZE * 0.8:
            st.info(f"💡 RAG 컨텍스트 크기: {final_size:,}자 (제한: {MAX_CONTEXT_SIZE:,}자)")
    else:
        if final_size > 1000000:
            st.info(f"💡 RAG 컨텍스트 크기: {final_size:,}자 (OpenAI 모델 - 크기 제한 없음)")
    
    return context_text, rag_sources_used

def get_ai_response(prompt, model_name, system_prompt="", enable_thinking=False, thinking_budget=4000):
    """AI 모델로부터 응답을 받는 함수 (reasoning 과정 표시 지원)"""
    try:
        if model_name.startswith('claude'):
            # Reasoning 모델인지 확인 (참조 파일 기준)
            is_reasoning_model = (
                model_name == 'claude-3-7-sonnet-latest' or
                model_name == 'claude-3-5-sonnet-latest'
            )
            
            if is_reasoning_model and enable_thinking:
                # Extended Thinking 사용 (직접 Anthropic 클라이언트 사용)
                import anthropic
                direct_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
                
                messages = [{"role": "user", "content": prompt}]
                
                response = direct_client.messages.create(
                    model=model_name,
                    max_tokens=8192,
                    system=system_prompt if system_prompt else None,
                    thinking={
                        "type": "enabled",
                        "budget_tokens": thinking_budget
                    },
                    messages=messages
                )
                
                thinking_content = ""
                final_content = ""
                
                for block in response.content:
                    if hasattr(block, 'type'):
                        if block.type == "thinking":
                            thinking_content = block.thinking
                        elif block.type == "text":
                            final_content = block.text
                        elif block.type == "redacted_thinking":
                            thinking_content += "\n[일부 사고 과정이 보안상 암호화되었습니다]"
                
                return {
                    "content": final_content,
                    "thinking": thinking_content,
                    "has_thinking": True
                }
            else:
                # 일반 모드 (LangChain 사용)
                from langchain_anthropic import ChatAnthropic
                client = ChatAnthropic(
                    model=model_name, 
                    api_key=os.getenv('ANTHROPIC_API_KEY'), 
                    temperature=0.7, 
                    max_tokens=8192
                )
                
                if system_prompt:
                    full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
                    response = client.invoke(full_prompt)
                else:
                    response = client.invoke(prompt)
                
                content = response.content if hasattr(response, 'content') else str(response)
                return {
                    "content": content,
                    "thinking": "",
                    "has_thinking": False
                }
                
        else:
            # OpenAI 모델들
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key:
                st.error("❌ OpenAI API 키가 설정되지 않았습니다!")
                return {
                    "content": "OpenAI API 키가 필요합니다.",
                    "thinking": "",
                    "has_thinking": False
                }
            
            from openai import OpenAI
            openai_client = OpenAI(api_key=openai_key)
            
            is_o1_model = model_name.startswith('o1')
            
            if is_o1_model:
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt}
                    ],
                    max_completion_tokens=8192
                )
                
                content = response.choices[0].message.content
                
                return {
                    "content": content,
                    "thinking": "🧠 이 모델은 내부적으로 복잡한 reasoning 과정을 거쳐 답변을 생성했습니다.",
                    "has_thinking": True
                }
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=8192
                )
                
                content = response.choices[0].message.content
                return {
                    "content": content,
                    "thinking": "",
                    "has_thinking": False
                }
            
    except Exception as e:
        st.error(f"❌ AI 응답 생성 중 오류가 발생했습니다: {str(e)}")
        return {
            "content": f"오류가 발생했습니다: {str(e)}",
            "thinking": "",
            "has_thinking": False
        } 

def save_conversation(session_title, user_query, assistant_response, model_name, has_reasoning=False, reasoning_content="", rag_sources_used=None, execution_time_seconds=None):
    """대화 내용을 데이터베이스에 저장"""
    try:
        connection = connect_to_db()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        rag_source_count = len(rag_sources_used) if rag_sources_used else 0
        
        # 메인 대화 저장
        insert_conversation = """
        INSERT INTO rag_conversations 
        (session_title, user_query, assistant_response, model_name, has_reasoning, reasoning_content, rag_sources_used, execution_time_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_conversation, (
            session_title,
            user_query,
            assistant_response,
            model_name,
            has_reasoning,
            reasoning_content,
            rag_source_count,
            execution_time_seconds
        ))
        
        conversation_id = cursor.lastrowid
        
        # RAG 소스 정보 저장
        if rag_sources_used:
            insert_source = """
            INSERT INTO rag_conversation_sources
            (conversation_id, source_type, source_name, source_description, source_details)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            for source in rag_sources_used:
                cursor.execute(insert_source, (
                    conversation_id,
                    source['type'],
                    source['name'],
                    source['details'],
                    json.dumps(source, ensure_ascii=False)
                ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        st.error(f"대화 저장 오류: {str(e)}")
        return False

def get_conversation_history(limit=20, search_term=None, model_filter=None):
    """저장된 대화 이력 조회"""
    try:
        connection = connect_to_db()
        if not connection:
            return []
            
        cursor = connection.cursor(dictionary=True)
        
        base_query = """
        SELECT id, session_title, user_query, assistant_response, model_name, 
               has_reasoning, reasoning_content, rag_sources_used, 
               execution_time_seconds, created_at
        FROM rag_conversations
        """
        
        conditions = []
        params = []
        
        if search_term:
            conditions.append("(session_title LIKE %s OR user_query LIKE %s)")
            params.extend([f'%{search_term}%', f'%{search_term}%'])
        
        if model_filter and model_filter != "전체":
            conditions.append("model_name LIKE %s")
            params.append(f'%{model_filter}%')
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        base_query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(base_query, params)
        conversations = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return conversations
        
    except Exception as e:
        st.error(f"대화 이력 조회 오류: {str(e)}")
        return []

# 세션 상태 초기화
if 'mysql_data' not in st.session_state:
    st.session_state.mysql_data = {}
if 'website_data' not in st.session_state:
    st.session_state.website_data = []
if 'files_data' not in st.session_state:
    st.session_state.files_data = []
if 'enable_sidebar_reasoning' not in st.session_state:
    st.session_state.enable_sidebar_reasoning = False
if 'rag_sources_used' not in st.session_state:
    st.session_state.rag_sources_used = []
if 'current_conversation' not in st.session_state:
    st.session_state.current_conversation = None

# 테이블 생성 버튼
if st.button("🛠️ RAG 에이전트 테이블 생성/검증"):
    if create_rag_agent_tables():
        st.success("✅ RAG 에이전트 테이블이 성공적으로 생성/검증되었습니다!")
    else:
        st.error("❌ 테이블 생성에 실패했습니다.")

# 메인 탭 인터페이스
tab1, tab2, tab3 = st.tabs([
    "🤖 AI 챗봇",
    "📊 RAG 데이터 관리",
    "📝 대화 이력 조회"
])

# Tab 1: AI 챗봇
with tab1:
    st.header("🤖 RAG 기반 AI 챗봇")
    
    # 모델 선택
    col1, col2 = st.columns([3, 2])
    
    with col1:
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
        
        selected_model = st.selectbox(
            "🎯 AI 모델 선택",
            model_options,
            index=0,
            help="Claude-3-7-sonnet-latest, Claude-3-5-sonnet-latest와 o1 모델들은 Extended Thinking(Reasoning)을 지원합니다."
        )
    
    with col2:
        session_title = st.text_input(
            "📝 세션 제목 (선택사항)",
            placeholder="예: 매출 분석 질문",
            help="대화를 구분하기 위한 제목입니다."
        )
    
    # 사용자 질문 입력
    user_query = st.text_area(
        "❓ 질문을 입력하세요",
        height=100,
        placeholder="예: 최근 3개월 매출 동향을 분석해주세요."
    )
    
    # 질문 버튼과 RAG 데이터 요약
    col1, col2 = st.columns([2, 3])
    
    with col1:
        submit_button = st.button("🚀 질문하기", type="primary", use_container_width=True)
    
    with col2:
        # 현재 로드된 RAG 데이터 요약 표시
        rag_summary = []
        if st.session_state.mysql_data:
            total_rows = sum(len(df) for df in st.session_state.mysql_data.values())
            rag_summary.append(f"🗄️ MySQL: {len(st.session_state.mysql_data)}개 테이블 ({total_rows:,}행)")
        
        if st.session_state.website_data:
            rag_summary.append(f"🌐 웹사이트: {len(st.session_state.website_data)}개 페이지")
        
        if st.session_state.files_data:
            total_size = sum(f['size'] for f in st.session_state.files_data)
            rag_summary.append(f"📄 문서: {len(st.session_state.files_data)}개 ({total_size:,}자)")
        
        if rag_summary:
            st.info("📋 **현재 RAG 데이터**: " + " | ".join(rag_summary))
        else:
            st.warning("⚠️ RAG 데이터가 없습니다. '📊 RAG 데이터 관리' 탭에서 데이터를 로드하세요.")
    
    # AI 응답 처리
    if submit_button and user_query.strip():
        if not any([st.session_state.mysql_data, st.session_state.website_data, st.session_state.files_data]):
            st.error("❌ RAG 데이터가 없습니다! 먼저 '📊 RAG 데이터 관리' 탭에서 데이터를 로드해주세요.")
        else:
            start_time = time.time()
            
            with st.spinner(f"🤖 {selected_model}이 RAG 데이터를 분석하고 있습니다..."):
                
                # 청크 처리가 필요한지 확인 (청크 처리 함수에서 판단)
                chunked_result = process_chunked_rag(
                    user_query=user_query,
                    mysql_data=st.session_state.mysql_data if st.session_state.mysql_data else None,
                    website_data=st.session_state.website_data if st.session_state.website_data else None,
                    files_data=st.session_state.files_data if st.session_state.files_data else None,
                    model_name=selected_model,
                    get_ai_response_func=get_ai_response
                )
                
                if chunked_result:
                    # 청크 처리 결과
                    response = chunked_result
                    rag_context = "청크 기반 처리"
                    rag_sources_used = response['rag_sources_used']
                else:
                    # 일반 RAG 처리
                    rag_context, rag_sources_used = create_rag_context(
                        mysql_data=st.session_state.mysql_data if st.session_state.mysql_data else None,
                        website_data=st.session_state.website_data if st.session_state.website_data else None,
                        files_data=st.session_state.files_data if st.session_state.files_data else None,
                        model_name=selected_model
                    )
                    
                    # RAG 프롬프트 구성
                    system_prompt = "당신은 RAG(Retrieval-Augmented Generation) 기반 AI 어시스턴트입니다. 제공된 컨텍스트를 바탕으로 정확하고 유용한 답변을 제공해주세요."
                    
                    if rag_context.strip():
                        prompt = f"""
다음은 질문에 답하기 위해 수집된 컨텍스트 정보입니다:

{rag_context}

질문: {user_query}

위의 컨텍스트 정보를 바탕으로 질문에 대해 상세하고 정확한 답변을 제공해주세요. 
- 컨텍스트에 없는 정보는 추측하지 마세요
- 관련 데이터가 있다면 구체적인 수치나 예시를 포함해주세요
- 답변의 근거가 되는 소스를 명시해주세요
"""
                    else:
                        prompt = f"질문: {user_query}\n\n컨텍스트 정보가 없습니다. 일반적인 지식을 바탕으로 답변해주세요."
                    
                    # AI 응답 생성
                    response = get_ai_response(
                        prompt=prompt,
                        model_name=selected_model,
                        system_prompt=system_prompt,
                        enable_thinking=st.session_state.get('enable_sidebar_reasoning', False)
                    )
            
            end_time = time.time()
            execution_time = int(end_time - start_time)
            
            # 응답 표시
            st.success(f"✅ **응답 완료** (소요시간: {execution_time}초)")
            
            # 청크 처리인지 확인하여 다른 형태로 표시
            if chunked_result:
                # 청크 처리 결과 표시
                st.markdown("### 🤖 AI 응답")
                st.markdown(response['content'])
                
                # 청크별 상세 결과 표시
                if 'chunk_responses' in response:
                    with st.expander(f"📊 청크별 처리 결과 ({response['chunk_count']}개 청크)", expanded=False):
                        for chunk_resp in response['chunk_responses']:
                            st.markdown(f"**청크 {chunk_resp['chunk_id']} 결과:**")
                            st.markdown(chunk_resp['content'])
                            st.markdown("---")
            else:
                # 일반 처리 결과 표시
                st.markdown("### 🤖 AI 응답")
                st.markdown(response['content'])
            
            # RAG 소스 정보 표시
            if rag_sources_used:
                with st.expander(f"📚 사용된 RAG 소스 ({len(rag_sources_used)}개)", expanded=False):
                    for i, source in enumerate(rag_sources_used):
                        st.markdown(f"**{i+1}. {source['name']}**")
                        st.markdown(f"- 타입: {source['type']}")
                        st.markdown(f"- 상세: {source['details']}")
                        if i < len(rag_sources_used) - 1:
                            st.markdown("---")
            
            # Reasoning 과정 표시 (사이드바 설정에 따라)
            if response.get('has_thinking', False) and response.get('thinking', '').strip():
                if st.session_state.get('enable_sidebar_reasoning', False):
                    # 사이드바에 표시는 나중에 처리
                    pass
                else:
                    # 메인 영역에 표시
                    st.markdown("### 🧠 AI 사고 과정 (Reasoning)")
                    reasoning_content = response['thinking']
                    reasoning_html = f"""
                    <details open>
                        <summary style="cursor: pointer; font-weight: bold; color: #1f77b4; font-size: 16px;">
                            🧠 Reasoning 과정 보기/숨기기
                        </summary>
                        <div style="margin-top: 15px; padding: 15px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #1f77b4; color: #000000; font-family: 'Courier New', monospace; white-space: pre-wrap; max-height: 500px; overflow-y: auto;">
{reasoning_content}
                        </div>
                    </details>
                    """
                    st.markdown(reasoning_html, unsafe_allow_html=True)
            
            # 대화 저장
            final_session_title = session_title.strip() if session_title.strip() else f"질문_{datetime.now().strftime('%m%d_%H%M')}"
            
            save_success = save_conversation(
                session_title=final_session_title,
                user_query=user_query,
                assistant_response=response['content'],
                model_name=selected_model,
                has_reasoning=response.get('has_thinking', False),
                reasoning_content=response.get('thinking', ''),
                rag_sources_used=rag_sources_used,
                execution_time_seconds=execution_time
            )
            
            if save_success:
                st.success("💾 대화가 데이터베이스에 저장되었습니다!")
                
                # 현재 대화 세션에 저장
                st.session_state.current_conversation = {
                    'title': final_session_title,
                    'query': user_query,
                    'response': response['content'],
                    'model': selected_model,
                    'has_thinking': response.get('has_thinking', False),
                    'thinking': response.get('thinking', ''),
                    'rag_sources': rag_sources_used,
                    'execution_time': execution_time,
                    'chunked': bool(chunked_result)
                }
                
                # 사이드바 reasoning 정보 업데이트
                st.session_state.rag_sources_used = rag_sources_used
            else:
                st.warning("⚠️ 대화 저장에 실패했지만 응답은 정상적으로 완료되었습니다.")
    
    elif submit_button:
        st.warning("❓ 질문을 입력해주세요!") 

# Tab 2: RAG 데이터 관리
with tab2:
    st.header("📊 RAG 데이터 관리")
    
    # MySQL 데이터 섹션
    st.subheader("🗄️ MySQL 데이터베이스")
    
    if st.button("🔄 테이블 목록 새로고침"):
        st.rerun()
    
    # 테이블 목록 조회
    available_tables = get_mysql_tables()
    
    if available_tables:
        selected_tables = st.multiselect(
            "📋 분석할 테이블 선택",
            available_tables,
            default=list(st.session_state.mysql_data.keys()) if st.session_state.mysql_data else None,
            help="Ctrl/Cmd를 누르고 클릭하여 여러 테이블을 선택할 수 있습니다."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 선택된 테이블 로드", type="primary"):
                if selected_tables:
                    with st.spinner("MySQL 데이터를 로드하는 중..."):
                        loaded_data = load_mysql_data(selected_tables)
                        st.session_state.mysql_data = loaded_data
                        
                        if loaded_data:
                            total_rows = sum(len(df) for df in loaded_data.values())
                            st.success(f"✅ {len(loaded_data)}개 테이블 로드 완료! (총 {total_rows:,}행)")
                        else:
                            st.error("❌ 테이블 로드에 실패했습니다.")
                else:
                    st.warning("테이블을 선택해주세요.")
        
        with col2:
            if st.button("🗑️ MySQL 데이터 초기화"):
                st.session_state.mysql_data = {}
                st.success("✅ MySQL 데이터가 초기화되었습니다.")
        
        # 현재 로드된 테이블 정보 표시
        if st.session_state.mysql_data:
            st.markdown("#### 📊 로드된 테이블 정보")
            for table_name, df in st.session_state.mysql_data.items():
                with st.expander(f"📋 {table_name} ({len(df):,}행)", expanded=False):
                    st.markdown(f"**컬럼**: {', '.join(df.columns.tolist())}")
                    st.dataframe(df.head(3), use_container_width=True)
    else:
        st.warning("❌ 사용 가능한 테이블이 없습니다. 데이터베이스 연결을 확인해주세요.")
    
    st.divider()
    
    # 웹사이트 크롤링 섹션
    st.subheader("🌐 웹사이트 크롤링")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        website_url = st.text_input(
            "🔗 크롤링할 웹사이트 URL",
            placeholder="예: example.com 또는 https://example.com",
            help="도메인명만 입력해도 됩니다 (http:// 자동 추가)"
        )
    
    with col2:
        max_pages = st.number_input(
            "📄 최대 페이지 수",
            min_value=1,
            max_value=10,
            value=3,
            help="너무 많은 페이지는 시간이 오래 걸립니다"
        )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 웹사이트 크롤링 시작", type="primary"):
            if website_url.strip():
                with st.spinner(f"🕷️ {website_url} 크롤링 중... (최대 {max_pages}페이지)"):
                    scraped_data = scrape_website_simple(website_url.strip(), max_pages)
                    
                    if scraped_data:
                        # 기존 웹사이트 데이터에 추가
                        st.session_state.website_data.extend(scraped_data)
                        st.success(f"✅ {len(scraped_data)}개 페이지 크롤링 완료!")
                    else:
                        st.error("❌ 웹사이트 크롤링에 실패했습니다.")
            else:
                st.warning("URL을 입력해주세요.")
    
    with col2:
        if st.button("🗑️ 웹사이트 데이터 초기화"):
            st.session_state.website_data = []
            st.success("✅ 웹사이트 데이터가 초기화되었습니다.")
    
    # 현재 크롤링된 웹사이트 정보 표시
    if st.session_state.website_data:
        st.markdown("#### 🌐 크롤링된 웹사이트 정보")
        for i, page in enumerate(st.session_state.website_data):
            with st.expander(f"📄 페이지 {i+1}: {page['title']}", expanded=False):
                st.markdown(f"**URL**: {page['url']}")
                st.markdown(f"**내용 미리보기**: {page['content'][:200]}...")
    
    st.divider()
    
    # 파일 업로드 섹션  
    st.subheader("📄 문서 파일 업로드")
    
    uploaded_files = st.file_uploader(
        "📂 분석할 문서 파일을 업로드하세요",
        accept_multiple_files=True,
        type=['txt', 'csv', 'json', 'md'],
        help="여러 파일을 한 번에 업로드할 수 있습니다."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 파일 처리", type="primary"):
            if uploaded_files:
                with st.spinner("📄 파일을 처리하는 중..."):
                    processed_files = process_files(uploaded_files)
                    
                    if processed_files:
                        # 기존 파일 데이터에 추가
                        st.session_state.files_data.extend(processed_files)
                        total_size = sum(f['size'] for f in processed_files)
                        st.success(f"✅ {len(processed_files)}개 파일 처리 완료! (총 {total_size:,}자)")
                    else:
                        st.error("❌ 파일 처리에 실패했습니다.")
            else:
                st.warning("파일을 업로드해주세요.")
    
    with col2:
        if st.button("🗑️ 문서 데이터 초기화"):
            st.session_state.files_data = []
            st.success("✅ 문서 데이터가 초기화되었습니다.")
    
    # 현재 업로드된 파일 정보 표시
    if st.session_state.files_data:
        st.markdown("#### 📚 업로드된 문서 정보")
        for i, file_data in enumerate(st.session_state.files_data):
            with st.expander(f"📄 {file_data['name']} ({file_data['size']:,}자)", expanded=False):
                st.markdown(f"**내용 미리보기**: {file_data['content'][:200]}...")
    
    st.divider()
    
    # 전체 RAG 데이터 요약
    st.subheader("📊 전체 RAG 데이터 요약")
    
    total_sources = 0
    summary_parts = []
    
    if st.session_state.mysql_data:
        table_count = len(st.session_state.mysql_data)
        row_count = sum(len(df) for df in st.session_state.mysql_data.values())
        summary_parts.append(f"🗄️ **MySQL**: {table_count}개 테이블, {row_count:,}행")
        total_sources += table_count
    
    if st.session_state.website_data:
        page_count = len(st.session_state.website_data)
        summary_parts.append(f"🌐 **웹사이트**: {page_count}개 페이지")
        total_sources += page_count
    
    if st.session_state.files_data:
        file_count = len(st.session_state.files_data)
        total_chars = sum(f['size'] for f in st.session_state.files_data)
        summary_parts.append(f"📄 **문서**: {file_count}개 파일, {total_chars:,}자")
        total_sources += file_count
    
    if summary_parts:
        st.success(f"✅ **총 {total_sources}개 RAG 소스 준비됨**")
        for part in summary_parts:
            st.markdown(f"- {part}")
        
        # 예상 컨텍스트 크기 표시
        test_context, _ = create_rag_context(
            mysql_data=st.session_state.mysql_data if st.session_state.mysql_data else None,
            website_data=st.session_state.website_data if st.session_state.website_data else None,
            files_data=st.session_state.files_data if st.session_state.files_data else None,
            model_name="claude-3-5-sonnet-20241022"  # 테스트용
        )
        
        context_size = len(test_context)
        if context_size > 0:
            st.info(f"💡 **예상 RAG 컨텍스트 크기**: {context_size:,}자")
            
            # 모델별 크기 제한 정보
            size_info = []
            if context_size > 7000000:
                size_info.append("⚠️ Claude 모델 제한 (7MB) 초과")
            if context_size > 3000000:
                size_info.append("⚠️ GPT 모델 제한 (3MB) 초과")
            if context_size > 800000:
                size_info.append("⚠️ o1 모델 제한 (800KB) 초과")
            
            if size_info:
                st.warning("크기 제한을 초과한 모델들:")
                for info in size_info:
                    st.markdown(f"- {info}")
                st.info("💡 큰 데이터는 자동으로 청크 단위로 나누어 처리됩니다.")
    else:
        st.warning("⚠️ RAG 데이터가 준비되지 않았습니다. 위의 섹션에서 데이터를 로드해주세요.") 

# Tab 3: 대화 이력 조회
with tab3:
    st.header("📝 대화 이력 조회")
    
    # 검색 및 필터 옵션
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input(
            "🔍 검색어",
            placeholder="제목 또는 질문 내용으로 검색",
            help="대화 제목이나 질문 내용을 검색할 수 있습니다."
        )
    
    with col2:
        model_filter = st.selectbox(
            "🎯 모델 필터",
            ["전체", "claude", "gpt", "o1"],
            help="특정 AI 모델로 필터링할 수 있습니다."
        )
    
    with col3:
        limit = st.number_input(
            "📊 조회 개수",
            min_value=5,
            max_value=100,
            value=20,
            step=5
        )
    
    # 대화 이력 조회
    conversations = get_conversation_history(
        limit=limit,
        search_term=search_term if search_term.strip() else None,
        model_filter=model_filter
    )
    
    if conversations:
        st.success(f"✅ {len(conversations)}개의 대화를 찾았습니다.")
        
        for conv in conversations:
            with st.expander(
                f"💬 {conv['session_title']} | {conv['model_name']} | {conv['created_at'].strftime('%Y-%m-%d %H:%M')}",
                expanded=False
            ):
                # 질문 표시
                st.markdown("**❓ 질문:**")
                st.markdown(conv['user_query'])
                
                # 응답 표시
                st.markdown("**🤖 AI 응답:**")
                st.markdown(conv['assistant_response'])
                
                # 메타데이터 표시
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"**🎯 모델**: {conv['model_name']}")
                    if conv['execution_time_seconds']:
                        st.markdown(f"**⏱️ 소요시간**: {conv['execution_time_seconds']}초")
                
                with col2:
                    if conv['rag_sources_used']:
                        st.markdown(f"**📚 RAG 소스**: {conv['rag_sources_used']}개")
                    
                    if conv['has_reasoning']:
                        st.markdown("**🧠 Reasoning**: ✅")
                
                with col3:
                    st.markdown(f"**📅 생성일**: {conv['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Reasoning 내용 표시 (있는 경우)
                if conv['has_reasoning'] and conv['reasoning_content']:
                    st.markdown("**🧠 AI 사고 과정:**")
                    with st.container():
                        # details 태그를 사용하여 접힌 형태로 표시
                        reasoning_content = conv['reasoning_content']
                        reasoning_html = f"""
                        <details>
                            <summary style="cursor: pointer; font-weight: bold; color: #1f77b4;">
                                🧠 Reasoning 내용 보기
                            </summary>
                            <div style="margin-top: 10px; padding: 10px; background-color: #f0f2f6; border-radius: 5px; max-height: 400px; overflow-y: auto; color: #000000;">
                                {reasoning_content.replace('\n', '<br>')}
                            </div>
                        </details>
                        """
                        st.markdown(reasoning_html, unsafe_allow_html=True)
                
                st.markdown("---")
    
    else:
        if search_term or model_filter != "전체":
            st.warning("🔍 검색 조건에 맞는 대화를 찾을 수 없습니다.")
        else:
            st.info("💬 아직 저장된 대화가 없습니다. AI 챗봇 탭에서 대화를 시작해보세요!")

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    
    # Reasoning 표시 설정
    st.subheader("🧠 AI 사고 과정 (Reasoning)")
    
    enable_reasoning = st.checkbox(
        "🔄 Reasoning 과정 표시",
        value=st.session_state.get('enable_sidebar_reasoning', False),
        help="Claude Reasoning 모델의 사고 과정을 사이드바에 표시합니다."
    )
    st.session_state.enable_sidebar_reasoning = enable_reasoning
    
    if enable_reasoning:
        thinking_budget = st.slider(
            "💭 Thinking 토큰 예산",
            min_value=1000,
            max_value=8000,
            value=4000,
            step=500,
            help="Reasoning 과정에 사용할 토큰 수입니다."
        )
        st.session_state.thinking_budget = thinking_budget
        
        # 현재 대화의 Reasoning 표시
        if (st.session_state.get('current_conversation') and 
            st.session_state.current_conversation.get('has_thinking') and
            st.session_state.current_conversation.get('thinking')):
            
            st.markdown("### 🧠 최신 AI 사고 과정")
            with st.container():
                # details 태그를 사용하여 접힌 형태로 표시
                reasoning_content = st.session_state.current_conversation['thinking']
                reasoning_html = f"""
                <details>
                    <summary style="cursor: pointer; font-weight: bold; color: #1f77b4;">
                        🧠 Reasoning 내용 보기
                    </summary>
                    <div style="margin-top: 10px; padding: 10px; background-color: #f0f2f6; border-radius: 5px; max-height: 400px; overflow-y: auto; color: #000000;">
                        {reasoning_content.replace('\n', '<br>')}
                    </div>
                </details>
                """
                st.markdown(reasoning_html, unsafe_allow_html=True)
    
    st.divider()
    
    # RAG 소스 정보
    st.subheader("📚 현재 RAG 소스")
    
    if st.session_state.get('rag_sources_used'):
        for i, source in enumerate(st.session_state.rag_sources_used):
            st.markdown(f"**{i+1}. {source['name']}**")
            st.markdown(f"- 타입: {source['type']}")
            st.markdown(f"- 상세: {source['details']}")
            if i < len(st.session_state.rag_sources_used) - 1:
                st.markdown("---")
    else:
        st.info("RAG 소스 정보가 없습니다.")
    
    st.divider()
    
    # 스마트 RAG 처리 정보
    st.subheader("🚀 스마트 RAG 처리")
    
    # 현재 대화가 청크 처리되었는지 확인
    if (st.session_state.get('current_conversation') and 
        st.session_state.current_conversation.get('chunked')):
        st.success("✅ 청크 기반 처리 완료")
        st.info("대용량 데이터를 여러 청크로 나누어 처리했습니다.")
    else:
        st.info("💡 일반 RAG 처리 모드")
    
    # 모델별 처리 방식 안내
    st.markdown("**📖 모델별 최적화 정보**")
    model_info_html = """
    <details>
        <summary style="cursor: pointer; font-weight: bold; color: #1f77b4;">
            모델별 제한사항 보기
        </summary>
        <div style="margin-top: 10px; padding: 10px; background-color: #f0f2f6; border-radius: 5px; color: #000000;">
            <strong>Claude 모델</strong>: 7MB 제한, 1행 샘플<br><br>
            <strong>GPT 모델</strong>: 3MB 제한, 3행 샘플<br><br>
            <strong>o1 모델</strong>: 800KB 제한, 2행 샘플<br><br>
            큰 데이터는 자동으로 청크 단위로 분할하여 처리됩니다.
        </div>
    </details>
    """
    st.markdown(model_info_html, unsafe_allow_html=True)
    
    st.divider()
    
    # 시스템 정보
    st.subheader("ℹ️ 시스템 정보")
    
    # 현재 로드된 데이터 요약
    data_summary = []
    if st.session_state.mysql_data:
        data_summary.append(f"🗄️ MySQL: {len(st.session_state.mysql_data)}개")
    if st.session_state.website_data:
        data_summary.append(f"🌐 웹: {len(st.session_state.website_data)}개")
    if st.session_state.files_data:
        data_summary.append(f"📄 문서: {len(st.session_state.files_data)}개")
    
    if data_summary:
        st.success("**로드된 데이터:**")
        for summary in data_summary:
            st.markdown(f"- {summary}")
    else:
        st.warning("데이터 없음")
    
    # 버전 정보
    st.markdown("---")
    st.caption("🤖 RAG 챗봇 v2.0")
    st.caption("청크 처리 지원 버전") 