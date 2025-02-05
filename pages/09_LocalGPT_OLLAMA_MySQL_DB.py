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
    page_icon="🔒",
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

# Using Ollama's model for LLM
llm = ChatOllama(
    model="llama3.2",
    temperature=0.1,
    streaming=True,
    callbacks=[ChatCallbackHandler()],  # Instantiate the callback handler
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
        
        # Define chain only if we have context from database
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

        # result = chain.invoke(message)
    
        # # Send only one response
        # if isinstance(result, dict) and "content" in result:
        #     send_message(result["content"], "ai")
        # else:
        #     send_message(result, "ai")
    
    # Reset the message list after sending to avoid repetition
    else:
        st.session_state["messages"] = []