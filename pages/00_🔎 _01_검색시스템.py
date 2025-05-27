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
# Streamlit UI
st.set_page_config(page_title="🔎 DB RAG 검색 시스템", layout="wide")
st.title("🔎 MySQL DB RAG 검색 챗봇")
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

# --- LLM 답변 생성 함수 (DB 결과를 context로, 개선) ---
def generate_llm_answer_rag(user_query, db_results, model_name, sql):
    max_results = 3
    max_val_len = 100
    if not db_results:
        context = f"[DB 검색 결과: '{user_query}'로 전체 테이블/컬럼에서 검색했으나 결과가 없습니다.]"
    else:
        context = f"[DB 검색 결과: '{user_query}'로 전체 테이블/컬럼에서 검색한 결과 {len(db_results)}건]\n"
        from collections import defaultdict
        table_counts = defaultdict(int)
        shown = 0
        for row in db_results:
            t = row.get('table', 'unknown')
            if table_counts[t] >= 5:
                continue
            row_str = f"[테이블: {t}] " + ", ".join([f"{k}: {str(v)[:max_val_len]}" for k, v in row.items() if k != 'table'])
            context += f"{shown+1}. {row_str}\n"
            table_counts[t] += 1
            shown += 1
        if len(db_results) > shown:
            context += f"... (이하 {len(db_results)-shown}건 생략)\n"
    prompt = f"""
아래는 사용자의 질문과 DB에서 '{user_query}'로 검색한 결과입니다.

- 반드시 아래 DB 검색 결과를 최대한 활용하여 답변하세요.
- DB 결과가 부족하면, 부족한 부분만 일반 지식으로 보완하세요.
- DB 결과를 요약/분석/활용해서 실제로 전략보고서의 각 항목(목표, 현황, 전략, 실행계획 등)에 구체적으로 반영하세요.
- DB 결과가 전혀 없으면, 'DB에 관련 데이터가 없습니다'라고 명확히 답변하세요.

[사용자 질문]
{user_query}

[DB 검색 결과]
{context}

[전략보고서 예시 포맷]
1. 목표 및 배경:
2. 현황 분석:
3. 전략 제안:
4. 실행 계획:
5. 기대 효과 및 결론:

[답변]
"""
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

# --- 검색 모드 선택 ---
search_mode = st.radio(
    "검색 방식 선택",
    options=["OR", "AND", "EXACT"],
    index=0,
    horizontal=True,
    help="여러 키워드 중 하나라도 포함(OR), 모두 포함(AND), 완전 일치(EXACT)"
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

# 챗봇 UI
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 결과/진행상황 표시용 컨테이너 ---
result_area = st.empty()

user_input = st.chat_input('질문을 입력하세요 (예: 특정 고객의 주문 내역을 알려줘)')

if user_input and tables:
    with result_area.container():
        if table == '전체' and (column == '전체' or column is None):
            st.info(f'🔎 전체 테이블/전체 컬럼에서 [{search_mode}] 방식으로 먼저 검색 후, LLM이 요약합니다.')
            search_results = search_all_tables_multicolumn_mode(user_input, search_mode, limit=10)
            st.write('🔍 [DB 검색 결과]', search_results)
            if not search_results:
                st.warning('DB에서 관련 정보를 찾지 못했습니다. 질문을 더 간단히 하거나, DB에 실제로 있는 단어로 검색해 보세요.')
            with st.spinner('AI가 답변을 생성 중입니다...'):
                progress_bar = st.progress(0)
                for percent in range(0, 100, 5):
                    time.sleep(0.01)
                    progress_bar.progress(percent + 1)
                answer = generate_llm_answer_rag(user_input, search_results, st.session_state.selected_model, f'[{search_mode} 검색]')
                progress_bar.progress(100)
                progress_bar.empty()
                placeholder = st.empty()
                display_text = ""
                for char in answer:
                    display_text += char
                    placeholder.markdown(display_text)
                    time.sleep(0.01)
                # --- DB 레퍼런스 표기 ---
                reference_text = summarize_db_reference(search_results)
                if reference_text:
                    st.markdown("---")
                    st.markdown("**[참고한 DB 레퍼런스]**")
                    st.markdown(reference_text)
                st.session_state.chat_history.append({'user': user_input, 'bot': answer, 'search': search_results, 'sql': f'[{search_mode} 검색]'})
        else:
            st.info(f'🔎 {table} 테이블에서 [{search_mode}] 방식으로 먼저 검색 후, LLM이 요약합니다.')
            search_results = search_table_multicolumn_mode(table, user_input, search_mode, limit=10)
            st.write('🔍 [DB 검색 결과]', search_results)
            if not search_results:
                st.warning('DB에서 관련 정보를 찾지 못했습니다. 질문을 더 간단히 하거나, DB에 실제로 있는 단어로 검색해 보세요.')
            with st.spinner('AI가 답변을 생성 중입니다...'):
                progress_bar = st.progress(0)
                for percent in range(0, 100, 5):
                    time.sleep(0.01)
                    progress_bar.progress(percent + 1)
                answer = generate_llm_answer_rag(user_input, search_results, st.session_state.selected_model, f'[{search_mode} 검색]')
                progress_bar.progress(100)
                progress_bar.empty()
                placeholder = st.empty()
                display_text = ""
                for char in answer:
                    display_text += char
                    placeholder.markdown(display_text)
                    time.sleep(0.01)
                # --- DB 레퍼런스 표기 ---
                reference_text = summarize_db_reference(search_results)
                if reference_text:
                    st.markdown("---")
                    st.markdown("**[참고한 DB 레퍼런스]**")
                    st.markdown(reference_text)
                st.session_state.chat_history.append({'user': user_input, 'bot': answer, 'search': search_results, 'sql': f'[{search_mode} 검색]'})

# --- 대화 기록 표시 (최신 대화가 아래쪽에 오도록, ChatGPT 스타일) ---
for chat in st.session_state.chat_history:
    with st.chat_message('user'):
        st.markdown(chat['user'])
    with st.chat_message('assistant'):
        st.markdown(chat['bot'])
        if chat.get('sql'):
            st.caption(f"[검색 방식]: {chat['sql']}")
        if chat['search']:
            with st.expander('🔍 DB 검색 결과 펼치기'):
                df = pd.DataFrame(chat['search'])
                st.dataframe(df)

if not tables:
    st.warning('DB에 테이블이 없습니다. DB를 먼저 생성해 주세요.')
else:
    st.info('DB에서 원하는 테이블/컬럼을 선택하지 않으면, 기본적으로 전체 테이블/전체 컬럼에서 검색합니다. 챗봇에 자연어로 질문을 입력하면, DB 검색 결과와 LLM을 활용해 답변을 생성합니다. (RAG 방식)') 