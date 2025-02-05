import streamlit as st
from langchain.prompts import ChatPromptTemplate
from langchain.embeddings import CacheBackedEmbeddings, OllamaEmbeddings
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.storage import LocalFileStore
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.chat_models import ChatOllama
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import Document

from bs4 import BeautifulSoup
import requests
import nltk
import os

# NLTK punkt package download
nltk.download('punkt')
nltk.data.path.append('/path/to/your/nltk_data')

# Set up page config
st.set_page_config(page_title="Website GPT", page_icon="🔒")

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
    model="llama3.2",
    temperature=0.1,
    streaming=True,
    callbacks=[
        ChatCallbackHandler(),
    ],
)

# Function to scrape website pages and extract text
def scrape_website(url):
    visited_urls = set()
    base_url = url
    texts = []

    def scrape_page(current_url):
        if current_url in visited_urls or not current_url.startswith(base_url):
            return
        visited_urls.add(current_url)

        # Request the page
        response = requests.get(current_url)
        soup = BeautifulSoup(response.content, "html.parser")

        # Extract text from the page
        page_text = soup.get_text(separator="\n").strip()
        texts.append(page_text)

        # Find all links on the page and recursively scrape them
        for link in soup.find_all("a", href=True):
            absolute_link = requests.compat.urljoin(base_url, link['href'])
            if absolute_link not in visited_urls:
                scrape_page(absolute_link)

    scrape_page(base_url)
    return texts

# Function to embed the website's scraped text


@st.cache_data(show_spinner="Embedding website content...")
def embed_website(url):
    cache_dir = LocalFileStore(f"./private_embeddings/{url.replace('/', '_')}")
    splitter = CharacterTextSplitter.from_tiktoken_encoder(
        separator="\n",
        chunk_size=600,
        chunk_overlap=100,
    )

    # Scrape website text
    web_texts = scrape_website(url)
    
    # Create Document objects with proper page_content
    docs = [Document(page_content=text, metadata={"source": url}) for text in web_texts]

    # Split the documents using the splitter
    split_docs = []
    for doc in docs:
        split_texts = splitter.split_text(doc.page_content)
        for split_text in split_texts:
            split_docs.append(Document(page_content=split_text, metadata=doc.metadata))

    embeddings = OllamaEmbeddings(model="llama3.2")
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)

    # Create vector store
    vectorstore = FAISS.from_documents(split_docs, cached_embeddings)
    retriever = vectorstore.as_retriever()

    return retriever

# Function to save chat messages
def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)

def save_message(message, role):
    st.session_state["messages"].append({"message": message, "role": role})

# Function to display chat history
def paint_history():
    for message in st.session_state["messages"]:
        send_message(
            message["message"],
            message["role"],
            save=False,
        )

# Function to format retrieved documents
def format_docs(docs):
    return "\n\n".join(document.page_content for document in docs)

# Chat prompt template
prompt = ChatPromptTemplate.from_template(
    """제공된 매락에서만 대답해 주세요. 내용을 만들어서 답하지 말고, 맥락에 제공된 내용만 이야기해 주세요.
    
    Context: {context}
    Question: {question}
    """
)

st.title("Website Scraping GPT")

st.markdown(
    """
    Welcome! 
    Enter a website URL to scrape and use the content for AI-powered question answering.
    """
)

# User inputs URL in the sidebar
with st.sidebar:
    website_url = st.text_input("Enter website URL", "")

if website_url:
    retriever = embed_website(website_url)
    send_message("The website data is ready! Ask anything.", "ai", save=False)
    paint_history()
    
    message = st.chat_input("Ask anything about the website content...")
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