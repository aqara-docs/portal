import streamlit as st
from langchain.agents import create_sql_agent
from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.callbacks.base import BaseCallbackHandler
import pandas as pd
import mysql.connector
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
load_dotenv()

# Database connection settings
db_user = os.getenv('SQL_USER')
db_password = os.getenv('SQL_PASSWORD')
db_host = os.getenv('SQL_HOST')
db_database = os.getenv('SQL_DATABASE_NEWBIZ')

# Setting up Streamlit page
st.set_page_config(
    page_title="MySQL DB GPT",
    page_icon="🤖",
)
st.title("🤖 MySQL DB GPT")

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

# 사용 가능한 모델 목록 (크기 순)
AVAILABLE_MODELS = [
    {"name": "llama3.2:latest", "size": "2.0 GB"},
    {"name": "llama2:latest", "size": "3.8 GB"},
    {"name": "mistral:latest", "size": "4.1 GB"},
    {"name": "llama3.1:latest", "size": "4.9 GB"},
    {"name": "llama3.1:8b", "size": "4.9 GB"},
    {"name": "gemma:latest", "size": "5.0 GB"},
    {"name": "gemma2:latest", "size": "5.4 GB"},
    {"name": "deepseek-r1:14b", "size": "9.0 GB"},
    {"name": "phi4:latest", "size": "9.1 GB"},
    {"name": "deepseek-r1:32b", "size": "19 GB"},
    {"name": "llama3.3:latest", "size": "42 GB"}
]

# 모델 선택 UI
st.sidebar.title("모델 설정")
selected_model = st.sidebar.selectbox(
    "사용할 모델을 선택하세요:",
    options=[model["name"] for model in AVAILABLE_MODELS],
    format_func=lambda x: f"{x} ({next(m['size'] for m in AVAILABLE_MODELS if m['name'] == x)})",
    index=2  # mistral:latest를 기본값으로 설정
)

# Temperature 설정
temperature = st.sidebar.slider(
    "Temperature:", 
    min_value=0.0, 
    max_value=2.0, 
    value=0.1, 
    step=0.1,
    help="값이 높을수록 더 창의적인 응답을 생성합니다."
)

# Custom callback handler inheriting from BaseCallbackHandler
class ChatCallbackHandler(BaseCallbackHandler):
    message = ""

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)

# Ollama 모델 초기화 함수
@st.cache_resource
def get_llm_mysql(model_name, temp):
    return ChatOllama(
        model=model_name,
        temperature=temp,
        streaming=True,
        callbacks=[ChatCallbackHandler()],
    )

# Function to save the conversation history
def save_message(message, role):
    if "mysql_messages" not in st.session_state:
        st.session_state["mysql_messages"] = []
    st.session_state["mysql_messages"].append({"message": message, "role": role})

# Function to send message and render in UI
def send_message(message, role, save=True):
    if isinstance(message, dict) and "content" in message:
        message = message["content"]
    elif hasattr(message, 'content'):
        message = message.content

    if isinstance(message, str) and message.strip():
        with st.chat_message(role):
            st.markdown(message)
        if save:
            save_message(message, role)

# Function to show chat history
def paint_history():
    if "mysql_messages" in st.session_state:
        for message in st.session_state["mysql_messages"]:
            send_message(
                message["message"],
                message["role"],
                save=False,
            )

# Function to load MySQL tables into pandas DataFrames
@st.cache_data(show_spinner="Loading data...")
def load_database_data(tables):
    try:
        connection = mysql.connector.connect(
            host=db_host,
            database=db_database,
            user=db_user,
            password=db_password,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )

        data_frames = {}
        for table in tables:
            query = f"SELECT * FROM {table}"
            df = pd.read_sql(query, connection)
            data_frames[table] = df

        return data_frames

    except mysql.connector.Error as err:
        st.error(f"Error connecting to MySQL: {err}")
        return None
    finally:
        if connection.is_connected():
            connection.close()

# Function to get table list from database
@st.cache_data(show_spinner="Fetching table list...")
def get_database_tables():
    """데이터베이스에서 테이블 목록을 가져오는 함수"""
    try:
        connection = mysql.connector.connect(
            host=db_host,
            database=db_database,
            user=db_user,
            password=db_password,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )

        cursor = connection.cursor()
        
        # newbiz 데이터베이스의 모든 테이블 조회
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        # 튜플에서 테이블명만 추출
        table_names = [table[0] for table in tables]
        
        # 테이블 정보 가져오기 (선택사항)
        table_info = {}
        for table_name in table_names:
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            table_info[table_name] = {
                'columns': len(columns),
                'column_details': [(col[0], col[1], col[2]) for col in columns]  # name, type, null
            }
        
        return table_names, table_info

    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return [], {}
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Function to get table row counts
@st.cache_data(show_spinner="Counting table rows...")
def get_table_row_counts(table_names):
    """각 테이블의 행 수를 가져오는 함수"""
    try:
        connection = mysql.connector.connect(
            host=db_host,
            database=db_database,
            user=db_user,
            password=db_password,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )

        cursor = connection.cursor()
        row_counts = {}
        
        for table_name in table_names:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            row_counts[table_name] = count
        
        return row_counts

    except mysql.connector.Error as err:
        st.error(f"행 수 조회 오류: {err}")
        return {}
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Function to create context with schema information
def create_enhanced_context(data_frames, max_context_size=50000):
    """데이터와 스키마 정보를 포함한 컨텍스트 생성 (크기 제한 포함)"""
    if not data_frames:
        return "", "", ""
    
    # 테이블명 목록
    table_names = ", ".join(data_frames.keys())
    
    # 스키마 정보 생성
    schema_info = []
    for table_name, df in data_frames.items():
        schema = f"\n[{table_name}]"
        schema += f"\n- 행 수: {len(df):,}개"
        schema += f"\n- 컬럼: "
        
        # 컬럼 정보와 데이터 타입 (간소화)
        column_info = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            # 타입 간소화
            if 'int' in dtype:
                dtype = 'INT'
            elif 'float' in dtype:
                dtype = 'FLOAT'
            elif 'object' in dtype:
                dtype = 'TEXT'
            elif 'datetime' in dtype:
                dtype = 'DATETIME'
            
            column_info.append(f"{col}({dtype})")
        
        schema += ", ".join(column_info)
        schema_info.append(schema)
    
    # 데이터 컨텍스트 (샘플 데이터 포함, 크기 제한)
    context_parts = []
    current_size = 0
    
    for table_name, df in data_frames.items():
        if current_size > max_context_size:
            context_parts.append(f"\n=== {table_name} 테이블 ===\n컨텍스트 크기 제한으로 생략됨")
            continue
            
        # 각 테이블의 요약 정보
        table_context = f"\n=== {table_name} 테이블 ===\n"
        
        # 상위 3개 행만 포함 (성능 최적화)
        if len(df) > 0:
            sample_size = min(3, len(df))
            table_context += f"샘플 데이터 ({sample_size}행):\n"
            
            # 컬럼이 너무 많으면 일부만 표시
            if len(df.columns) > 10:
                display_df = df.iloc[:sample_size, :10]
                table_context += display_df.to_string(index=False)
                table_context += f"\n... (총 {len(df.columns)}개 컬럼 중 10개만 표시)"
            else:
                table_context += df.head(sample_size).to_string(index=False)
            
            if len(df) > sample_size:
                table_context += f"\n... (총 {len(df)}행 중 상위 {sample_size}행만 표시)"
        else:
            table_context += "데이터 없음"
        
        context_parts.append(table_context)
        current_size += len(table_context)
    
    return table_names, "\n".join(schema_info), "\n".join(context_parts)

# 테이블 선택 시 기본값을 주요 테이블만으로 제한
def get_default_tables(available_tables):
    """주요 테이블만 기본 선택하도록 필터링"""
    # 주요 테이블 우선순위
    priority_tables = [
        'partner_candidates', 'newbiz_preparation', 'work_journal', 
        'weekly_journal', 'contact_list', 'suppliers', 'vote_questions',
        'vote_responses', 'vote_options'
    ]
    
    # 우선순위 테이블 중 존재하는 것들만 선택
    default_tables = [table for table in priority_tables if table in available_tables]
    
    # 우선순위 테이블이 5개 미만이면 다른 테이블도 추가 (최대 10개)
    if len(default_tables) < 5:
        remaining_tables = [table for table in available_tables if table not in default_tables]
        default_tables.extend(remaining_tables[:10-len(default_tables)])
    
    return default_tables[:10]  # 최대 10개만

# Sidebar for table selection (개선된 버전)
def table_selector():
    st.sidebar.subheader("📊 데이터베이스 연결")
    
    # 데이터베이스 연결 테스트 버튼
    if st.sidebar.button("🔍 데이터베이스 연결 테스트"):
        try:
            connection = mysql.connector.connect(
                host=db_host,
                database=db_database,
                user=db_user,
                password=db_password,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            if connection.is_connected():
                st.sidebar.success("✅ 데이터베이스 연결 성공!")
                connection.close()
        except mysql.connector.Error as err:
            st.sidebar.error(f"❌ 연결 실패: {err}")
    
    # 테이블 목록 새로고침 버튼
    if st.sidebar.button("🔄 테이블 목록 새로고침"):
        # 캐시 클리어
        get_database_tables.clear()
        get_table_row_counts.clear()
        st.rerun()
    
    # 데이터베이스에서 테이블 목록 가져오기
    available_tables, table_info = get_database_tables()
    
    if not available_tables:
        st.sidebar.error("❌ 테이블을 가져올 수 없습니다.")
        return {}
    
    # 테이블 행 수 가져오기
    row_counts = get_table_row_counts(available_tables)
    
    st.sidebar.subheader(f"📋 사용 가능한 테이블 ({len(available_tables)}개)")
    
    # 테이블 정보 표시 (개선된 레이아웃)
    with st.sidebar.expander("테이블 상세 정보"):
        # 테이블을 행 수 기준으로 정렬
        sorted_tables = sorted(available_tables, 
                             key=lambda x: row_counts.get(x, 0), 
                             reverse=True)
        
        for table_name in sorted_tables:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{table_name}**")
            with col2:
                if table_name in row_counts:
                    st.write(f"{row_counts[table_name]:,}행")
            
            if table_name in table_info:
                info = table_info[table_name]
                st.caption(f"컬럼 {info['columns']}개")
            st.write("---")
    
    # 기본 선택 테이블 (성능 최적화)
    default_tables = get_default_tables(available_tables)
    
    # 테이블 선택 
    selected_tables = st.sidebar.multiselect(
        "분석할 테이블 선택",
        available_tables,
        default=default_tables,
        help="⚠️ 너무 많은 테이블을 선택하면 응답이 느려질 수 있습니다. 주요 테이블만 선택하는 것을 권장합니다."
    )
    
    # 선택된 테이블 정보 요약
    if selected_tables:
        total_rows = sum(row_counts.get(table, 0) for table in selected_tables)
        total_tables = len(selected_tables)
        
        # 경고 표시
        if total_tables > 15:
            st.sidebar.warning(f"⚠️ 선택된 테이블이 많습니다 ({total_tables}개)")
        elif total_rows > 10000:
            st.sidebar.warning(f"⚠️ 데이터가 많습니다 ({total_rows:,}행)")
        
        st.sidebar.info(f"선택된 테이블: {total_tables}개\n총 데이터 행: {total_rows:,}개")
    
    # 데이터 로드 버튼
    load_button = st.sidebar.button("📥 선택된 테이블 로드", type="primary")
    
    if load_button and selected_tables:
        with st.spinner(f"테이블 데이터 로딩 중... ({len(selected_tables)}개 테이블)"):
            data_frames = load_database_data(selected_tables)
            if data_frames:
                st.session_state["mysql_data_frames"] = data_frames
                st.session_state["mysql_selected_tables"] = selected_tables
                
                # 로드 성공 메시지
                total_rows_loaded = sum(len(df) for df in data_frames.values())
                st.success(f"✅ {len(selected_tables)}개 테이블 로드 완료! (총 {total_rows_loaded:,}행)")
                
                # 메모리 사용량 계산
                total_memory = sum(df.memory_usage(deep=True).sum() for df in data_frames.values()) / 1024 / 1024
                if total_memory > 100:
                    st.warning(f"⚠️ 메모리 사용량이 높습니다: {total_memory:.1f}MB")
                
            else:
                st.error("❌ 데이터 로드에 실패했습니다.")
    elif load_button and not selected_tables:
        st.warning("⚠️ 먼저 테이블을 선택해주세요.")

    return st.session_state.get("mysql_data_frames", {})

# Chat Prompt Template
prompt = ChatPromptTemplate.from_template(
    """당신은 MySQL 데이터베이스 분석 전문가입니다. 제공된 데이터만을 사용하여 질문에 답변해주세요.

데이터베이스 정보:
- 데이터베이스명: newbiz
- 로드된 테이블: {table_names}

테이블 스키마 정보:
{schema_info}

데이터 내용:
{context}

질문: {question}

답변 지침:
1. 제공된 데이터만 사용하여 답변하세요
2. 데이터에 없는 내용은 추측하지 마세요
3. 구체적인 수치나 예시를 들어 답변하세요
4. 필요시 SQL 쿼리 예시를 제공하세요
5. 한국어로 답변해주세요

답변:"""
)

# Streamlit UI
st.title("🤖 MySQL DB GPT")
st.markdown(f"**현재 선택된 모델:** {selected_model}")

# 데이터베이스 정보 표시
with st.expander("📋 데이터베이스 정보"):
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**호스트:** {db_host}")
        st.write(f"**데이터베이스:** {db_database}")
    with col2:
        st.write(f"**사용자:** {db_user}")
        st.write(f"**문자셋:** utf8mb4")

st.markdown(
    """
    💡 **사용법:**
    1. 사이드바에서 데이터베이스 연결을 확인하세요
    2. 분석하고 싶은 테이블을 선택하세요 (기본값: 주요 테이블)
    3. 테이블 데이터를 로드하세요
    4. AI에게 데이터에 대한 질문을 해보세요!
    
    **예시 질문:**
    - "각 테이블에 몇 개의 레코드가 있나요?"
    - "partner_candidates 테이블의 주요 컬럼들을 설명해주세요"
    - "가장 최근에 추가된 데이터는 언제인가요?"
    - "vote_responses에서 가장 많이 선택된 답변은?"
    """
)

# Paint chat history
paint_history()

# Database table selection
data_frames = table_selector()

# One-time initial message
if "initial_message_sent" not in st.session_state:
    st.session_state["initial_message_sent"] = False

if data_frames:
    if not st.session_state["initial_message_sent"]:
        selected_tables = st.session_state.get("mysql_selected_tables", [])
        send_message(f"🎉 데이터베이스가 준비되었습니다! \n\n로드된 테이블: {', '.join(selected_tables)}\n\n이제 데이터에 대해 무엇이든 질문해보세요!", "ai", save=False)
        st.session_state["initial_message_sent"] = True

# 현재 로드된 테이블 정보 표시 (개선된 레이아웃)
if data_frames:
    st.write("### 📊 현재 로드된 데이터")
    
    # 테이블 수에 따라 컬럼 수 조정
    num_tables = len(data_frames)
    if num_tables <= 4:
        cols_per_row = num_tables
    elif num_tables <= 8:
        cols_per_row = 4
    else:
        cols_per_row = 5
    
    # 테이블 정보를 행별로 표시
    table_items = list(data_frames.items())
    for i in range(0, len(table_items), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, (table_name, df) in enumerate(table_items[i:i+cols_per_row]):
            with cols[j]:
                st.metric(
                    label=table_name,
                    value=f"{len(df):,}행",
                    delta=f"{len(df.columns)}컬럼",
                    help=f"테이블: {table_name}\n행 수: {len(df):,}\n컬럼 수: {len(df.columns)}"
                )
    
    # 요약 정보
    total_rows = sum(len(df) for df in data_frames.values())
    total_cols = sum(len(df.columns) for df in data_frames.values())
    total_memory = sum(df.memory_usage(deep=True).sum() for df in data_frames.values()) / 1024 / 1024
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 테이블", f"{len(data_frames)}개")
    with col2:
        st.metric("총 행 수", f"{total_rows:,}")
    with col3:
        st.metric("총 컬럼 수", f"{total_cols}")
    with col4:
        st.metric("메모리 사용량", f"{total_memory:.1f}MB")

message = st.chat_input("데이터베이스에 대해 질문해보세요...")
if message:
    send_message(message, "human")
    
    if data_frames:
        # 향상된 컨텍스트 생성 (크기 제한 포함)
        table_names, schema_info, context = create_enhanced_context(data_frames)
        
        # 현재 선택된 모델로 LLM 초기화
        llm = get_llm_mysql(selected_model, temperature)
        
        chain = (
            {
                "table_names": RunnableLambda(lambda _: table_names),
                "schema_info": RunnableLambda(lambda _: schema_info),
                "context": RunnableLambda(lambda _: context),
                "question": RunnablePassthrough(),
            }
            | prompt
            | llm
        )
        
        with st.chat_message("ai"):
            try:
                chain.invoke(message)
            except Exception as e:
                st.error(f"답변 생성 중 오류가 발생했습니다: {e}")
                st.info("💡 **해결 방법:** 선택된 테이블 수를 줄이거나 더 간단한 질문을 해보세요.")
    else:
        send_message("⚠️ 먼저 사이드바에서 테이블을 선택하고 로드해주세요!", "ai", save=False)

# 사이드바 하단에 유용한 정보 추가
with st.sidebar:
    st.markdown("---")
    st.markdown("### 💡 팁")
    with st.expander("효과적인 질문 방법"):
        st.markdown("""
        **좋은 질문 예시:**
        - "각 테이블의 레코드 수는?"
        - "partner_candidates에서 status별 개수는?"
        - "최근 1개월 데이터는 얼마나 있나요?"
        - "이 데이터베이스의 전체 구조를 설명해주세요"
        
        **피해야 할 질문:**
        - 데이터에 없는 정보 요청
        - 너무 복잡한 분석 요청
        - 실시간 데이터 변경 요청
        """)
    
    with st.expander("데이터 새로고침"):
        st.markdown("""
        **언제 새로고침이 필요한가요?**
        - 데이터베이스에 새로운 테이블이 추가된 경우
        - 기존 테이블의 구조가 변경된 경우
        - 연결 오류가 발생한 경우
        
        새로고침 후 다시 테이블을 로드해주세요.
        """)

if st.sidebar.button("💬 대화 내용 초기화"):
    st.session_state["mysql_messages"] = []
    st.session_state["initial_message_sent"] = False
    st.rerun()

# Initialize session state
if "mysql_messages" not in st.session_state:
    st.session_state["mysql_messages"] = [] 