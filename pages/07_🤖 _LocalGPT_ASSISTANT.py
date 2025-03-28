import streamlit as st
from langchain.schema import HumanMessage, AIMessage
from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.callbacks.base import BaseCallbackHandler

# 페이지 설정
st.set_page_config(
    page_title="LocalLLM OLLAMA",
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
    {"name": "llama3.3:latest", "size": "42 GB"},
    {"name": "deepseek-r1:70b", "size": "42 GB"},
]

# 모델 선택 UI
st.sidebar.title("모델 설정")
selected_model = st.sidebar.selectbox(
    "사용할 모델을 선택하세요:",
    options=[model["name"] for model in AVAILABLE_MODELS],
    format_func=lambda x: f"{x} ({next(m['size'] for m in AVAILABLE_MODELS if m['name'] == x)})",
    index=0  # 기본값으로 가장 작은 모델 선택
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

# ChatCallbackHandler 클래스 정의
class ChatCallbackHandler(BaseCallbackHandler):
    message = ""

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)

# Ollama의 Chat 모델 사용
@st.cache_resource
def get_llm(model_name, temp):
    return ChatOllama(
        model=model_name,
        temperature=temp,
        streaming=True,
        callbacks=[ChatCallbackHandler()],
    )

# 메시지 기록을 세션에 저장하는 함수
def save_message(message, role):
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    st.session_state["messages"].append({"message": message, "role": role})

# 메시지를 화면에 출력하는 함수
def send_message(message, role, save=True):
    if isinstance(message, dict) and "content" in message:
        message = message["content"]
    elif hasattr(message, 'content'):
        message = message.content

    if isinstance(message, str) and message.strip():
        st.chat_message(role).markdown(message)
        if save:
            save_message(message, role)

# 메시지 기록을 그리는 함수
def paint_history():
    if "messages" in st.session_state:
        for message in st.session_state["messages"]:
            send_message(message["message"], message["role"], save=False)

# Prompt 템플릿 정의
prompt = ChatPromptTemplate.from_template(
    """
    Answer the question based on the context below. 
    Context: {context}
    Question: {question}
    """
)

# 메인 UI
st.title("LocalLLM with OLLAMA")
st.markdown(f"현재 선택된 모델: **{selected_model}**")

# 기존 메시지 기록 그리기
paint_history()

# 새로운 입력을 처리
message = st.chat_input("Ask anything...")

if message:
    send_message(message, "human")
    
    # 현재 선택된 모델로 LLM 초기화
    llm = get_llm(selected_model, temperature)
    
    # 질문을 처리하기 위한 chain 정의
    context = "This is a sample context for the conversation."
    
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
    st.rerun()