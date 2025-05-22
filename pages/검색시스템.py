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

# 환경 변수 로드
load_dotenv()

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

def get_table_columns(table_name):
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute(f"DESCRIBE {table_name}")
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return columns

def search_table(table, column, query, limit=10):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    sql = f"SELECT * FROM `{table}` WHERE `{column}` LIKE %s LIMIT %s"
    cursor.execute(sql, (f"%{query}%", limit))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# --- DB 스키마 정보 가져오기 ---
def get_schema_info():
    tables = get_table_names()
    schema = {}
    for t in tables:
        schema[t] = get_table_columns(t)
    return schema

# --- LLM을 이용한 자연어→SQL 변환 ---
def generate_sql_from_question(question, schema_info, table=None):
    # schema_info: {table: [col1, col2, ...], ...}
    schema_str = "\n".join([f"{t}: {', '.join(cols)}" for t, cols in schema_info.items()])
    if table and table != '전체':
        prompt = f"""
아래는 MySQL 데이터베이스의 테이블과 컬럼 정보입니다.
{table}: {', '.join(schema_info[table])}

사용자 질문: {question}

위 테이블을 활용하여 적절한 SELECT 쿼리(SQL)를 한 줄로 생성해 주세요. (예: SELECT * FROM {table} WHERE ...)
반드시 LIMIT 10을 붙이세요. INSERT/UPDATE/DELETE는 금지. 쿼리만 출력하세요.
"""
    else:
        prompt = f"""
아래는 MySQL 데이터베이스의 테이블과 컬럼 정보입니다.
{schema_str}

사용자 질문: {question}

적절한 테이블을 선택하여 SELECT 쿼리(SQL)를 한 줄로 생성해 주세요. (예: SELECT * FROM ... WHERE ...)
반드시 LIMIT 10을 붙이세요. INSERT/UPDATE/DELETE는 금지. 쿼리만 출력하세요.
"""
    # OpenAI로 SQL 생성 (Claude는 SQL 생성 신뢰도가 낮음)
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        temperature=0.0
    )
    # --- SQL 추출: 마크다운 태그 제거 및 쿼리만 추출 ---
    sql_raw = response.choices[0].message.content.strip()
    # Remove markdown code block if present
    if sql_raw.startswith('```'):
        sql_raw = sql_raw.split('\n', 1)[-1]  # remove first line (```sql or ```)
    sql = sql_raw.replace('```', '').strip()
    # 쿼리만 추출 (여러 줄일 경우 첫 번째 세미콜론까지)
    sql = sql.split(';')[0]
    return sql

# --- SQL 실행 함수 (SELECT만 허용) ---
def run_sql_query(sql):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
    except Exception as e:
        results = []
        st.error(f'SQL 실행 오류: {e}')
    cursor.close()
    conn.close()
    return results

# --- LLM 답변 생성 함수 (DB 결과를 context로) ---
def generate_llm_answer_rag(user_query, db_results, model_name, sql):
    max_results = 3
    max_val_len = 100
    if not db_results:
        context = f"[DB 검색 결과: SQL=\n{sql}\n\n결과 없음]"
    else:
        context = f"[DB 검색 결과: SQL=\n{sql}\n\n{len(db_results)}건]\n"
        for i, row in enumerate(db_results[:max_results], 1):
            row_str = ", ".join([f"{k}: {str(v)[:max_val_len]}" for k, v in row.items()])
            context += f"{i}. {row_str}\n"
        if len(db_results) > max_results:
            context += f"... (이하 {len(db_results)-max_results}건 생략)\n"
    prompt = f"""
아래는 사용자의 질문과 데이터베이스 검색 결과입니다. 검색 결과를 참고하여 사용자의 질문에 대해 최대한 구체적이고 친절하게 답변해 주세요. 만약 검색 결과가 부족하다면, 일반적인 지식도 활용해 답변해 주세요.\n\n[사용자 질문]\n{user_query}\n\n{context}\n\n[답변]"""
    if model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=1200)
        response = client.invoke([
            {"role": "user", "content": prompt}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.3
        )
        return response.choices[0].message.content

# Streamlit UI
st.set_page_config(page_title="🔎 DB RAG 검색 시스템", layout="wide")
st.title("🔎 MySQL DB RAG 검색 챗봇")

# 모델 선택
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

# --- 디폴트 모델: gpt-4o-mini가 있으면 그걸로, 없으면 첫 번째 모델로 ---
if 'selected_model' not in st.session_state:
    if 'gpt-4o-mini' in available_models:
        st.session_state.selected_model = 'gpt-4o-mini'
    else:
        st.session_state.selected_model = available_models[0]

st.session_state.selected_model = st.selectbox(
    'AI 모델 선택',
    options=available_models,
    index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
    help='Claude(Anthropic)는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
)

# 테이블/컬럼 선택
with st.sidebar:
    st.header('🔗 DB 테이블/컬럼 선택')
    tables = get_table_names()
    table_options = ['전체'] + tables if tables else ['전체']
    table = st.selectbox('테이블 선택', table_options)
    if table == '전체':
        columns = ['전체']
    else:
        columns = ['전체'] + get_table_columns(table) if table else ['전체']
    column = st.selectbox('검색 컬럼 선택', columns) if columns else None
    st.markdown('---')
    st.caption('DB에서 원하는 테이블/컬럼을 선택 후, 아래 챗봇에 질문을 입력하세요.')

# --- 멀티컬럼 OR-LIKE 검색 함수 ---
def search_table_multicolumn(table, query, limit=10):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    columns = get_table_columns(table)
    # 키워드 추출 (띄어쓰기 기준, 2글자 이상)
    keywords = [w for w in query.split() if len(w) > 1]
    if not keywords:
        keywords = [query]
    like_clauses = []
    params = []
    for col in columns:
        for kw in keywords:
            like_clauses.append(f"`{col}` LIKE %s")
            params.append(f"%{kw}%")
    sql = f"SELECT * FROM `{table}` WHERE {' OR '.join(like_clauses)} LIMIT %s"
    params.append(limit)
    cursor.execute(sql, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# 전체 테이블/전체 컬럼 검색

def search_all_tables_multicolumn(query, limit=5):
    results = []
    tables = get_table_names()
    for t in tables:
        try:
            partial = search_table_multicolumn(t, query, limit)
            if partial:
                for row in partial:
                    results.append({'table': t, **row})
        except Exception as e:
            continue
    return results

# 챗봇 UI
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

user_input = st.chat_input('질문을 입력하세요 (예: 특정 고객의 주문 내역을 알려줘)')

if user_input and tables:
    # --- 분기: 전체/특정 테이블/컬럼 ---
    if table == '전체' and (column == '전체' or column is None):
        # 1. 전체 테이블/전체 컬럼: 키워드 기반 멀티테이블 검색 → LLM 요약 (진짜 RAG)
        st.info('🔎 전체 테이블/전체 컬럼에서 키워드로 먼저 검색 후, LLM이 요약합니다.')
        search_results = search_all_tables_multicolumn(user_input, limit=10)
        st.write('🔍 [DB 검색 결과]', search_results)
        if not search_results:
            st.warning('DB에서 관련 정보를 찾지 못했습니다. 질문을 더 간단히 하거나, DB에 실제로 있는 단어로 검색해 보세요.')
        with st.spinner('AI가 답변을 생성 중입니다...'):
            progress_bar = st.progress(0)
            for percent in range(0, 100, 5):
                time.sleep(0.01)
                progress_bar.progress(percent + 1)
            answer = generate_llm_answer_rag(user_input, search_results, st.session_state.selected_model, '[키워드 기반 전체 테이블 검색]')
            progress_bar.progress(100)
            progress_bar.empty()
            # ChatGPT 스타일 스트리밍 출력
            placeholder = st.empty()
            display_text = ""
            for char in answer:
                display_text += char
                placeholder.markdown(display_text)
                time.sleep(0.01)
            st.session_state.chat_history.append({'user': user_input, 'bot': answer, 'search': search_results, 'sql': '[키워드 기반 전체 테이블 검색]'})
    else:
        # 2. 특정 테이블/컬럼: LLM이 SQL 생성 → 실행 → 결과를 LLM에 전달
        with st.spinner('AI가 SQL 쿼리를 생성 중입니다...'):
            schema_info = get_schema_info()
            try:
                sql = generate_sql_from_question(user_input, schema_info, table if table != '전체' else None)
            except Exception as e:
                st.error(f'LLM SQL 생성 실패: {e}')
                sql = None
        st.write('📝 [LLM이 생성한 SQL]', sql)
        db_results = []
        if sql:
            db_results = run_sql_query(sql)
        st.write('🔍 [DB 검색 결과]', db_results)
        if not db_results:
            st.warning('DB에서 관련 정보를 찾지 못했습니다. 질문을 더 간단히 하거나, DB에 실제로 있는 단어로 검색해 보세요.')
        with st.spinner('AI가 답변을 생성 중입니다...'):
            progress_bar = st.progress(0)
            for percent in range(0, 100, 5):
                time.sleep(0.01)
                progress_bar.progress(percent + 1)
            answer = generate_llm_answer_rag(user_input, db_results, st.session_state.selected_model, sql or '(SQL 생성 실패)')
            progress_bar.progress(100)
            progress_bar.empty()
            # ChatGPT 스타일 스트리밍 출력
            placeholder = st.empty()
            display_text = ""
            for char in answer:
                display_text += char
                placeholder.markdown(display_text)
                time.sleep(0.01)
            st.session_state.chat_history.append({'user': user_input, 'bot': answer, 'search': db_results, 'sql': sql})

# --- 대화 기록 표시 (최신 대화가 아래쪽에 오도록, ChatGPT 스타일) ---
for chat in st.session_state.chat_history:
    with st.chat_message('user'):
        st.markdown(chat['user'])
    with st.chat_message('assistant'):
        st.markdown(chat['bot'])
        if chat.get('sql'):
            st.caption(f"[LLM이 생성한 SQL]: {chat['sql']}")
        if chat['search']:
            with st.expander('🔍 DB 검색 결과 펼치기'):
                df = pd.DataFrame(chat['search'])
                st.dataframe(df)

if not tables:
    st.warning('DB에 테이블이 없습니다. DB를 먼저 생성해 주세요.')
else:
    st.info('DB에서 원하는 테이블/컬럼을 선택하지 않으면, 기본적으로 전체 테이블/전체 컬럼에서 검색합니다. 챗봇에 자연어로 질문을 입력하면, DB 검색 결과와 LLM을 활용해 답변을 생성합니다. (RAG 방식)') 