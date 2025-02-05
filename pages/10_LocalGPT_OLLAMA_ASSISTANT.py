import streamlit as st
from langchain.schema import HumanMessage, AIMessage
from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.callbacks.base import BaseCallbackHandler

# 페이지 설정
st.set_page_config(
    page_title="LocalLLM OLLAMA",
    page_icon="🔒",
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
llm = ChatOllama(
    model="llama3.2",
    temperature=0.1,
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

# Streamlit UI
st.title("LocalLLM with OLLAMA")
st.markdown("Welcome! Ask anything to the AI below:")

# 기존 메시지 기록 그리기
paint_history()

# 새로운 입력을 처리
message = st.chat_input("Ask anything...")

if message:
    send_message(message, "human")
    
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
       
else: 
    st.session_state["messages"] = []