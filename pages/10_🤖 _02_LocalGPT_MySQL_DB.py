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
def get_llm(model_name, temp):
    return ChatOllama(
        model=model_name,
        temperature=temp,
        streaming=True,
        callbacks=[ChatCallbackHandler()],
    )

# Function to save the conversation history
def save_message(message, role):
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    st.session_state["messages"].append({"message": message, "role": role})

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
    if "messages" in st.session_state:
        for message in st.session_state["messages"]:
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

# Sidebar for table selection
def table_selector():
    available_tables = ["partner_candidates","newbiz_preparation","work_journal","weekly_journal","contact_list"]
    selected_tables = st.sidebar.multiselect("Select tables to load", available_tables, default=available_tables)
    
    load_button = st.sidebar.button("Load selected tables")
    
    if load_button:
        data_frames = load_database_data(selected_tables)
        st.session_state["data_frames"] = data_frames
        st.success(f"Loaded data for tables: {', '.join(selected_tables)}")

    return st.session_state.get("data_frames", {})

# Chat Prompt Template
prompt = ChatPromptTemplate.from_template(
    """Answer the question using ONLY the following context and not your training data. 
    If you don't know the answer just say you don't know. DON'T make anything up.
    
    Context: {context}
    Question: {question}
    """
)

# Streamlit UI
st.title("MySQL DB GPT")
st.markdown(f"현재 선택된 모델: **{selected_model}**")
st.markdown(
    """
Welcome! Use this chatbot to ask questions to an AI about your database! 
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
        send_message("Database is ready! Ask anything about the loaded tables!", "ai", save=False)
        st.session_state["initial_message_sent"] = True

message = st.chat_input("Ask anything about your database...")
if message:
    send_message(message, "human")
    
    if data_frames:
        context = "\n\n".join([df.to_string() for df in data_frames.values()])
        
        # 현재 선택된 모델로 LLM 초기화
        llm = get_llm(selected_model, temperature)
        
        chain = (
            {
                "context": RunnableLambda(lambda _: context),
                "question": RunnablePassthrough(),
            }
            | prompt
            | llm
        )
        with st.chat_message("ai"):
            chain.invoke(message)

if st.sidebar.button("대화 내용 초기화"):
    st.session_state["messages"] = []
    st.session_state["initial_message_sent"] = False
    st.rerun()

else:
    st.session_state["messages"] = []