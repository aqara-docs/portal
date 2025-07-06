import streamlit as st
import os
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
from langchain_openai import OpenAI as LangOpenAI
from langchain_anthropic import ChatAnthropic
import pandas as pd
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="MySQL DB RAG 검색 챗봇", layout="wide")

st.title("🔎 MySQL DB RAG 검색 챗봇 🔎")

# 환경 변수 로드
load_dotenv()

# 임베딩 모델 초기화
@st.cache_resource
def get_embedding_model():
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 텍스트 임베딩 생성
def get_text_embedding(text, model):
    if not text or pd.isna(text):
        return np.zeros(384)  # 모델의 임베딩 차원
    return model.encode(str(text))

# 텍스트 유사도 계산
def calculate_similarity(query_embedding, text_embedding):
    return cosine_similarity([query_embedding], [text_embedding])[0][0]

# DB 연결 함수 (00_💾_01_DB생성.py 참고)
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def get_table_names():
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables

def get_table_columns(table):
    """테이블의 컬럼 목록 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f"DESCRIBE {table}")
        columns = [row[0] for row in cursor.fetchall()]
        return columns
    except Exception as e:
        print(f"Error getting columns for table {table}: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

# --- 검색 모드별 멀티컬럼 검색 함수 ---
def search_table_multicolumn_mode(table, query, mode="OR", limit=10):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    columns = get_table_columns(table)
    keywords = [w for w in query.split() if w]
    if not keywords:
        keywords = [query]
    where_clauses = []
    params = []
    if mode == "OR":
        for col in columns:
            for kw in keywords:
                where_clauses.append(f"`{col}` LIKE %s")
                params.append(f"%{kw}%")
        where_sql = " OR ".join(where_clauses)
    elif mode == "AND":
        for kw in keywords:
            sub = []
            for col in columns:
                sub.append(f"`{col}` LIKE %s")
                params.append(f"%{kw}%")
            where_clauses.append("(" + " OR ".join(sub) + ")")
        where_sql = " AND ".join(where_clauses)
    elif mode == "EXACT":
        for col in columns:
            where_clauses.append(f"`{col}` = %s")
            params.append(query)
        where_sql = " OR ".join(where_clauses)
    else:
        where_sql = "1=0"
    sql = f"SELECT * FROM `{table}` WHERE {where_sql} LIMIT %s"
    params.append(limit)
    cursor.execute(sql, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def search_all_tables_multicolumn_mode(query, mode="OR", limit=5):
    results = []
    tables = get_table_names()
    for t in tables:
        try:
            partial = search_table_multicolumn_mode(t, query, mode, limit)
            if partial:
                for row in partial:
                    results.append({'table': t, **row})
        except Exception as e:
            continue
    return results

def get_table_schema_definitions():
    """테이블별 스키마 정의 및 칼럼 특성 정의"""
    return {
        'meeting_records': {
            'weight': 1.0,
            'columns': {
                'title': {
                    'type': 'text',
                    'importance': 1.0,
                    'search_weight': 1.0,
                    'description': '회의 제목',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'summary': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '회의 요약',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'content': {
                    'type': 'long_text',
                    'importance': 0.8,
                    'search_weight': 0.7,
                    'description': '회의 상세 내용',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'decisions': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '의사결정 사항',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'action_items': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.8,
                    'description': '액션 아이템',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'participants': {
                    'type': 'text',
                    'importance': 0.7,
                    'search_weight': 0.6,
                    'description': '참석자',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'meeting_date': {
                    'type': 'date',
                    'importance': 0.8,
                    'search_weight': 0.0,
                    'description': '회의 날짜',
                    'preprocessing': None
                }
            }
        },
        'analyses': {
            'weight': 0.9,
            'columns': {
                'title': {
                    'type': 'text',
                    'importance': 1.0,
                    'search_weight': 1.0,
                    'description': '분석 제목',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'content': {
                    'type': 'long_text',
                    'importance': 0.9,
                    'search_weight': 0.8,
                    'description': '분석 내용',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'summary': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '분석 요약',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'conclusions': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '분석 결론',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'created_at': {
                    'type': 'date',
                    'importance': 0.7,
                    'search_weight': 0.0,
                    'description': '작성일',
                    'preprocessing': None
                }
            }
        },
        'book_discussions': {
            'weight': 0.8,
            'columns': {
                'title': {
                    'type': 'text',
                    'importance': 1.0,
                    'search_weight': 1.0,
                    'description': '도서/토론 제목',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'content': {
                    'type': 'long_text',
                    'importance': 0.9,
                    'search_weight': 0.8,
                    'description': '토론 내용',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'summary': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '토론 요약',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'key_insights': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '주요 인사이트',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'discussion_date': {
                    'type': 'date',
                    'importance': 0.7,
                    'search_weight': 0.0,
                    'description': '토론일',
                    'preprocessing': None
                }
            }
        },
        'action_items': {
            'weight': 0.9,
            'columns': {
                'title': {
                    'type': 'text',
                    'importance': 1.0,
                    'search_weight': 1.0,
                    'description': '액션 아이템 제목',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'description': {
                    'type': 'text',
                    'importance': 0.9,
                    'search_weight': 0.9,
                    'description': '상세 설명',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'status': {
                    'type': 'category',
                    'importance': 0.8,
                    'search_weight': 0.7,
                    'description': '진행 상태',
                    'preprocessing': lambda x: x.lower() if x else x
                },
                'assignee': {
                    'type': 'text',
                    'importance': 0.8,
                    'search_weight': 0.7,
                    'description': '담당자',
                    'preprocessing': lambda x: x.strip() if x else x
                },
                'due_date': {
                    'type': 'date',
                    'importance': 0.8,
                    'search_weight': 0.0,
                    'description': '마감일',
                    'preprocessing': None
                }
            }
        }
    }

def get_column_definition(table, column):
    """테이블의 특정 칼럼 정의 가져오기"""
    schema_defs = get_table_schema_definitions()
    table_def = schema_defs.get(table, {'columns': {}})
    return table_def['columns'].get(column, {
        'type': 'unknown',
        'importance': 0.5,
        'search_weight': 0.5,
        'description': '알 수 없는 칼럼',
        'preprocessing': lambda x: str(x) if x is not None else None
    })

def preprocess_value(table, column, value):
    """칼럼 특성에 따른 값 전처리"""
    if value is None:
        return None
        
    col_def = get_column_definition(table, column)
    if col_def['preprocessing']:
        return col_def['preprocessing'](value)
    return value

def search_table_hybrid_mode(table, query, embedding_model, mode="OR", limit=None, semantic_weight=0.5):
    """키워드 검색과 의미론적 검색을 결합한 하이브리드 검색"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. 테이블 구조 파악
        cursor.execute(f"DESCRIBE {table}")
        columns = [row['Field'] for row in cursor.fetchall()]
        
        # 2. 검색할 컬럼 결정 및 가중치 계산
        column_weights = {}
        for col in columns:
            col_def = get_column_definition(table, col)
            if col_def['type'] in ['text', 'long_text', 'category']:
                column_weights[col] = col_def['search_weight']
        
        if not column_weights:
            return []
        
        # 3. 검색 쿼리 구성
        where_clauses = []
        params = []
        
        for col, weight in column_weights.items():
            if mode == "OR":
                where_clauses.extend([f"({col} LIKE %s)" for _ in query.split()])
                params.extend([f"%{kw}%" for kw in query.split()])
            elif mode == "AND":
                where_clauses.append("(" + " OR ".join([f"{col} LIKE %s" for _ in query.split()]) + ")")
                params.extend([f"%{kw}%" for kw in query.split()])
            else:  # EXACT
                where_clauses.append(f"({col} LIKE %s)")
                params.append(f"%{query}%")
        
        # 4. 날짜 정렬을 위한 컬럼 찾기
        date_columns = []
        for col in columns:
            col_def = get_column_definition(table, col)
            if col_def['type'] == 'date':
                date_columns.append(col)
        
        order_by = f"ORDER BY {date_columns[0] if date_columns else '1'} DESC"
        
        # 5. SQL 실행 - 모든 결과를 가져옴
        sql = f"""
        SELECT * 
        FROM {table}
        WHERE {" OR ".join(where_clauses) if mode == "OR" else " AND ".join(where_clauses)}
        {order_by}
        """
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        # 6. 의미론적 검색 및 결과 스코어링
        if results:
            query_embedding = get_text_embedding(query, embedding_model)
            scored_results = []
            
            for row in results:
                # 각 칼럼의 특성을 고려한 텍스트 결합
                text_parts = []
                for col, value in row.items():
                    col_def = get_column_definition(table, col)
                    if col_def['type'] in ['text', 'long_text']:
                        processed_value = preprocess_value(table, col, value)
                        if processed_value:
                            text_parts.append(processed_value)
                
                text_content = " ".join(text_parts)
                
                if text_content.strip():
                    # 의미론적 유사도 계산
                    text_embedding = get_text_embedding(text_content, embedding_model)
                    semantic_score = calculate_similarity(query_embedding, text_embedding)
                    
                    # 키워드 매칭 점수 계산 (칼럼 가중치 적용)
                    keyword_score = 0
                    for col, value in row.items():
                        if value and col in column_weights:
                            processed_value = preprocess_value(table, col, value)
                            if processed_value and any(kw.lower() in processed_value.lower() for kw in query.split()):
                                keyword_score += column_weights[col]
                    
                    # 최종 점수 계산
                    schema_defs = get_table_schema_definitions()
                    table_weight = schema_defs.get(table, {'weight': 0.7})['weight']
                    
                    final_score = table_weight * (
                        semantic_weight * semantic_score + 
                        (1 - semantic_weight) * keyword_score
                    )
                    
                    scored_results.append((final_score, row))
            
            # 점수에 따라 정렬
            scored_results.sort(reverse=True, key=lambda x: x[0])
            
            # 각 결과에 점수 포함
            results = []
            for score, row in scored_results:
                results.append({**row, '_score': score})
            
            return results
        
        return []
        
    except Exception as e:
        print(f"Error searching table {table}: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def search_all_tables_hybrid_mode(query, embedding_model, mode="OR", limit=None, semantic_weight=0.5):
    """모든 테이블에 대해 하이브리드 검색 수행"""
    all_results = []
    tables = get_table_names()
    table_importance = get_table_schema_definitions()
    
    # 각 테이블 검색 (limit 제한 없이)
    for table in tables:
        try:
            results = search_table_hybrid_mode(table, query, embedding_model, mode, None, semantic_weight)
            if results:
                # 테이블 메타데이터 추가
                for row in results:
                    score = row.pop('_score', 0)  # 점수를 임시로 제거
                    all_results.append({
                        'table': table,
                        'importance': table_importance.get(table, {'weight': 0.7})['weight'],
                        '_score': score,  # 점수 저장
                        **row
                    })
        except Exception as e:
            continue
    
    # 전체 결과를 점수에 따라 정렬
    all_results.sort(key=lambda x: x['_score'], reverse=True)
    
    # 점수 필드 제거
    for row in all_results:
        row.pop('_score', None)
    
    # limit 적용
    return all_results[:limit] if limit else all_results

class ConversationManager:
    def __init__(self):
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """세션 상태 초기화"""
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []
        if 'last_search_results' not in st.session_state:
            st.session_state.last_search_results = None
        if 'context_summary' not in st.session_state:
            st.session_state.context_summary = ""
    
    def add_to_history(self, role, content, search_results=None):
        """대화 히스토리에 새 메시지 추가"""
        timestamp = datetime.now().isoformat()
        entry = {
            'timestamp': timestamp,
            'role': role,
            'content': content,
            'search_results': search_results if search_results else None
        }
        st.session_state.conversation_history.append(entry)
        
        # 마지막 검색 결과 업데이트
        if search_results:
            st.session_state.last_search_results = search_results
    
    def get_recent_context(self, num_messages=5):
        """최근 대화 컨텍스트 가져오기"""
        history = st.session_state.conversation_history[-num_messages:] if st.session_state.conversation_history else []
        context = []
        
        for entry in history:
            context.append(f"{entry['role']}: {entry['content']}")
            if entry['search_results']:
                context.append(f"[검색 결과: {len(entry['search_results'])}건]")
        
        return "\n".join(context)
    
    def get_last_search_results(self):
        """마지막 검색 결과 가져오기"""
        return st.session_state.last_search_results
    
    def update_context_summary(self, summary):
        """컨텍스트 요약 업데이트"""
        st.session_state.context_summary = summary
    
    def get_context_summary(self):
        """현재 컨텍스트 요약 가져오기"""
        return st.session_state.context_summary

def generate_llm_answer_rag(user_query, db_results, model_name, sql, conversation_manager=None):
    max_results_per_table = 3  # 테이블당 최대 결과 수
    max_val_len = 100  # 각 필드 값의 최대 길이
    max_recent_messages = 3  # 최근 대화 히스토리 수
    
    # 컨텍스트 구성
    if not db_results:
        context = f"[DB 검색 결과: '{user_query}'로 전체 테이블/컬럼에서 검색했으나 결과가 없습니다.]"
    else:
        context = f"[DB 검색 결과: '{user_query}'로 검색한 결과 {len(db_results)}건]\n\n"
        
        # 테이블별 결과 그룹화
        table_results = {}
        for row in db_results:
            table = row.get('table', 'unknown')
            if table not in table_results:
                table_results[table] = []
            if len(table_results[table]) < max_results_per_table:  # 테이블당 최대 결과 수 제한
                table_results[table].append(row)
        
        # 각 테이블의 결과를 처리
        for table, rows in table_results.items():
            context += f"[테이블: {table}]\n"
            
            for row in rows:
                # 날짜 정보 찾기
                date_value = None
                for key, value in row.items():
                    if any(date_type in key.lower() for date_type in ['date', 'time', 'created', 'updated']):
                        date_value = value
                        break
                
                if date_value:
                    context += f"날짜: {date_value}\n"
                
                # 주요 필드 표시 (중요도 순)
                important_fields = [
                    'title', 'summary', 'content', 'description', 'decisions', 
                    'action_items', 'conclusions', 'key_insights'
                ]
                
                field_count = 0  # 표시된 필드 수 추적
                for field in important_fields:
                    if field in row and row[field] and not pd.isna(row[field]):
                        value = str(row[field])[:max_val_len]
                        if len(value) == max_val_len:
                            value += "..."
                        context += f"{field}: {value}\n"
                        field_count += 1
                        if field_count >= 5:  # 최대 5개 필드만 표시
                            break
                
                context += "\n"
    
    # 대화 컨텍스트 추가 (최근 3개 메시지만)
    conversation_context = ""
    if conversation_manager:
        recent_context = conversation_manager.get_recent_context(max_recent_messages)
        context_summary = conversation_manager.get_context_summary()
        if context_summary:
            conversation_context = f"\n[이전 대화 요약]\n{context_summary}\n"
        if recent_context:
            conversation_context += f"\n[최근 대화 내용]\n{recent_context}\n"
    
    prompt = f"""
아래는 사용자의 질문과 아카라라이프의 데이터베이스에서 '{user_query}'로 검색한 결과입니다.
{conversation_context}

[중요 지침]
1. DB의 모든 관련 정보를 종합적으로 분석하여 답변하세요.
2. 이전 대화 내용과 연결하여 맥락을 유지하세요.
3. 회의록, 분석 자료, 토론 내용 등을 시간 순서대로 연결하여 맥락을 제공하세요.
4. 의사결정 사항과 액션 아이템은 날짜와 함께 구체적으로 명시하세요.
5. 여러 자료의 연관성을 파악하여 종합적인 인사이트를 제공하세요.
6. DB에 없는 내용은 추측하지 말고, 정보가 부족한 부분을 명확히 표시하세요.

[사용자 질문]
{user_query}

[DB 검색 결과]
{context}

[답변 형식]
1. 종합 요약:
   - 검색된 정보의 전체적인 맥락과 의미
   - 시간순 흐름에 따른 변화/발전 사항
   - 이전 대화와의 연관성

2. 주요 내용 분석:
   - 회의/문서별 핵심 포인트
   - 의사결정 사항 및 배경
   - 주요 논의 사항과 결론

3. 실행 현황:
   - 액션 아이템 및 진행 상태
   - 후속 조치 사항
   - 담당자/책임자 정보

4. 연관 정보:
   - 관련 회의/문서 간 연결점
   - 보완적 정보들의 통합적 의미
   - 이전 대화에서 언급된 관련 내용

5. 결론 및 제언:
   - 종합적 인사이트
   - 부족한 정보 영역
   - 향후 필요한 액션 제안

[답변]
"""
    
    if st.session_state.selected_ai_api == 'Anthropic (Claude)':
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=1500)
        response = client.invoke([
            {"role": "user", "content": prompt}
        ])
        answer = response.content if hasattr(response, 'content') else str(response)
    else:  # OpenAI (GPT)
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3
        )
        answer = response.choices[0].message.content
    
    # 대화 히스토리 업데이트
    if conversation_manager:
        conversation_manager.add_to_history('assistant', answer, db_results)
    
    return answer

def summarize_db_reference(search_results, max_tables=3, max_rows_per_table=1, max_cols=3):
    from collections import defaultdict
    table_rows = defaultdict(list)
    for row in search_results:
        t = row.get('table', 'unknown')
        table_rows[t].append(row)
    ref_lines = []
    for i, (t, rows) in enumerate(table_rows.items()):
        if i >= max_tables:
            ref_lines.append(f"... (이하 {len(table_rows)-max_tables}개 테이블 생략)")
            break
        ref_lines.append(f"- 테이블: {t}")
        if rows:
            # 대표 row 1개, 주요 컬럼 3개만 표시
            row = rows[0]
            cols = [k for k in row.keys() if k != 'table'][:max_cols]
            col_str = ", ".join([f"{k}={row[k]}" for k in cols])
            ref_lines.append(f"  - 예시 데이터: {col_str}")
    return "\n".join(ref_lines)

def main():
    # 인증 기능 (간단한 비밀번호 보호)
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
        if password == os.getenv('ADMIN_PASSWORD', 'mds0118!'):
            st.session_state.authenticated = True
            st.rerun()
        else:
            if password:
                st.error("관리자 권한이 필요합니다")
            st.stop()
    
    # 채팅 기록 초기화
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # 사이드바 설정
    with st.sidebar:
        st.title("MySQL DB RAG 검색 챗봇")
        
        # AI API/모델 선택
        has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
        has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
        available_models = []
        if has_anthropic_key:
            available_models.extend([
                'claude-3-7-sonnet-latest',
                'claude-3-5-sonnet-latest',
                'claude-3-5-haiku-latest',
            ])
        if has_openai_key:
            available_models.extend(['gpt-4o', 'gpt-4o-mini'])
        if not available_models:
            available_models = ['claude-3-7-sonnet-latest']

        col_api, col_model = st.columns([1,2])
        with col_api:
            selected_ai_api = st.selectbox(
                'AI API 선택',
                options=['Anthropic (Claude)', 'OpenAI (GPT)'],
                index=0 if st.session_state.get('selected_ai_api', 'Anthropic (Claude)') == 'Anthropic (Claude)' else 1,
                key='api_selector'
            )
            st.session_state.selected_ai_api = selected_ai_api
        with col_model:
            filtered_models = [m for m in available_models if (('claude' in m and selected_ai_api=='Anthropic (Claude)') or ('gpt' in m and selected_ai_api=='OpenAI (GPT)'))]
            if not filtered_models:
                filtered_models = ['claude-3-7-sonnet-latest']
            selected_model = st.selectbox(
                'AI 모델 선택',
                options=filtered_models,
                index=filtered_models.index(st.session_state.get('selected_model', filtered_models[0])) if st.session_state.get('selected_model') in filtered_models else 0,
                key='model_selector'
            )
            st.session_state.selected_model = selected_model
        
        # 검색 모드 선택
        st.subheader("검색 방식 선택")
        search_mode = st.radio(
            "",
            ["OR", "AND", "EXACT"],
            help="OR: 키워드 중 하나라도 포함\nAND: 모든 키워드 포함\nEXACT: 정확한 문구 매칭"
        )
        
        # 검색 결과 수 설정
        search_limit = st.slider(
            "검색 결과 수",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            help="한 번에 표시할 검색 결과의 최대 개수"
        )
        
        # 상세 결과 표시 여부
        show_details = st.checkbox("검색 결과 상세 표시", value=False)
        
        # 테이블 선택
        st.subheader("검색 대상 테이블")
        tables = get_table_names()
        selected_tables = st.multiselect(
            "테이블 선택 (미선택시 전체 검색)",
            tables
        )
        
        if selected_tables:
            st.subheader("검색 대상 컬럼")
            for table in selected_tables:
                st.write(f"**{table}**")
                columns = get_table_columns(table)
                selected_columns = st.multiselect(
                    f"{table} 컬럼 선택 (미선택시 전체 검색)",
                    columns,
                    key=f"cols_{table}"
                )
    
    # 메인 영역
    # 초기 안내 메시지
    st.info('DB에서 원하는 테이블/컬럼을 선택하지 않으면, 기본적으로 전체 테이블/전체 컬럼에서 검색합니다. 챗봇에 자연어로 질문을 입력하면, DB 검색 결과와 LLM을 활용해 답변을 생성합니다. (RAG 방식)')
    
    # 임베딩 모델 초기화
    embedding_model = get_embedding_model()
    
    # 대화 기록 표시 (최신 대화가 아래쪽에 오도록)
    for chat in st.session_state.chat_history:
        with st.chat_message('user'):
            st.markdown(chat['user'])
        with st.chat_message('assistant'):
            st.markdown(chat['bot'])
            if chat.get('sql'):
                st.caption(f"[검색 방식]: {chat['sql']}")
            if chat.get('search'):
                with st.expander('🔍 DB 검색 결과 펼치기'):
                    df = pd.DataFrame(chat['search'])
                    if len(df) > 0:
                        # 테이블별로 결과 그룹화
                        grouped = df.groupby('table')
                        for table_name, group in grouped:
                            st.write(f"**{table_name}** ({len(group)}건)")
                            display_df = group.copy()
                            if 'table' in display_df.columns:
                                display_df = display_df.drop('table', axis=1)
                            st.dataframe(
                                display_df,
                                hide_index=True,
                                use_container_width=True
                            )
    
    # 사용자 입력 영역
    with st.container():
        user_query = st.text_area(
            "질문을 입력하세요",
            height=100,
            help="예시 질문:\n- 최근 회의에서 논의된 주요 의사결정 사항은?\n- 특정 프로젝트의 진행 상황을 알려주세요\n- 이번 달 주요 액션 아이템은?"
        )
        
        # 실행 버튼을 중앙에 배치
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            submit_button = st.button(
                "🔍 검색 및 답변 생성",
                type="primary",
                use_container_width=True
            )
    
    if submit_button and user_query:
        # ConversationManager 초기화
        conversation_manager = ConversationManager()
        
        # 이전 대화 기록 로드
        for chat in st.session_state.chat_history:
            conversation_manager.add_to_history('user', chat['user'])
            conversation_manager.add_to_history('assistant', chat['bot'])
        
        # 현재 사용자 입력을 대화 히스토리에 추가
        conversation_manager.add_to_history('user', user_query)
        
        # 검색 및 답변 생성
        with st.spinner('검색 중...'):
            results = search_all_tables_hybrid_mode(
                query=user_query,
                embedding_model=embedding_model,
                mode=search_mode,
                limit=search_limit
            )
            
            if results:
                # 결과를 데이터프레임으로 변환
                df = pd.DataFrame(results)
                # 테이블별 결과 수 표시
                table_counts = df['table'].value_counts()
                st.write("🔍 **검색 결과 요약**")
                for table, count in table_counts.items():
                    st.write(f"- {table}: {count}건")
                
                # 테이블별로 결과 표시
                grouped = df.groupby('table')
                for table_name, group in grouped:
                    with st.expander(f"테이블: {table_name} ({len(group)}건)"):
                        display_df = group.copy()
                        if 'table' in display_df.columns:
                            display_df = display_df.drop('table', axis=1)
                        st.dataframe(
                            display_df,
                            hide_index=True,
                            use_container_width=True
                        )
            else:
                st.warning('검색 결과가 없습니다.')
        
        with st.spinner('답변 생성 중...'):
            answer = generate_llm_answer_rag(
                user_query,
                results,
                st.session_state.selected_model,
                f"[{search_mode} 검색]",
                conversation_manager
            )
            
            # 새로운 대화를 채팅 기록에 추가
            st.session_state.chat_history.append({
                'user': user_query,
                'bot': answer,
                'search': results,
                'sql': f"[{search_mode} 검색]"
            })
            
            # 화면 새로고침
            st.rerun()

if __name__ == "__main__":
    main() 