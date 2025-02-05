from langchain.prompts import ChatPromptTemplate
from langchain.document_loaders import UnstructuredFileLoader
from langchain.embeddings import CacheBackedEmbeddings, OllamaEmbeddings
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.storage import LocalFileStore
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.chat_models import ChatOllama
from langchain.callbacks.base import BaseCallbackHandler
import streamlit as st
import os
import nltk

# NLTK punkt 패키지 다운로드
nltk.download('punkt')

# NLTK 데이터를 사용하는 곳에서 다운로드를 먼저 수행하게 설정
nltk.data.path.append('/Users/aqaralife/nltk_data')

st.set_page_config(
    page_title="FILE GPT",
    page_icon="🔒",
)


class ChatCallbackHandler(BaseCallbackHandler):
    message = ""

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)


llm = ChatOllama(
    model="gemma2",
    temperature=0.1,
    streaming=True,
    callbacks=[
        ChatCallbackHandler(),
    ],
)

@st.cache_data(show_spinner="Embedding files...")
def embed_files(files):
    # Define the directory path
    directory = "./private_files/"
    
    # Create the directory if it does not exist
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    all_docs = []
    
    for file in files:
        # Save the file to the directory
        file_path = os.path.join(directory, file.name)
        
        with open(file_path, "wb") as f:
            f.write(file.read())
        
        cache_dir = LocalFileStore(f"./private_embeddings/{file.name}")
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            separator="\n",
            chunk_size=600,
            chunk_overlap=100,
        )
        
        loader = UnstructuredFileLoader(file_path)
        docs = loader.load_and_split(text_splitter=splitter)
        all_docs.extend(docs)
    
    embeddings = OllamaEmbeddings(model="gemma2")
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)
    
    vectorstore = FAISS.from_documents(all_docs, cached_embeddings)
    retriever = vectorstore.as_retriever()
    
    return retriever


def save_message(message, role):
    st.session_state["messages"].append({"message": message, "role": role})


def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)


def paint_history():
    for message in st.session_state["messages"]:
        send_message(
            message["message"],
            message["role"],
            save=False,
        )


def format_docs(docs):
    return "\n\n".join(document.page_content for document in docs)


prompt = ChatPromptTemplate.from_template(
    """Answer the question using ONLY the following context and not your training data. If you don't know the answer just say you don't know. DON'T make anything up.
    
    Context: {context}
    Question:{question}
    """
)


st.title("FILE GPT")

st.markdown(
    """
Welcome!
            
Use this chatbot to ask questions to an AI about your files!

Upload your files on the sidebar.
"""
)

with st.sidebar:
    files = st.file_uploader(
        "Upload .md .txt .pdf or .docx files",
        type=["md","pdf", "txt", "docx"],
        accept_multiple_files=True  # Enable multiple file upload
    )

if files:  # Check if any files were uploaded
    retriever = embed_files(files)  # Process all uploaded files
    send_message("I'm ready! Ask away!", "ai", save=False)
    paint_history()
    message = st.chat_input("Ask anything about your files...")
    if message:
        send_message(message, "human")
        chain = (
            {
                "context": retriever | RunnableLambda(format_docs),
                "question": RunnablePassthrough(),
            }
            | prompt
            | llm
        )
        with st.chat_message("ai"):
            chain.invoke(message)


else:
    st.session_state["messages"] = []