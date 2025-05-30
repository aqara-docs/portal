from langchain.prompts import ChatPromptTemplate
from langchain.document_loaders import UnstructuredFileLoader
from langchain.embeddings import CacheBackedEmbeddings, OllamaEmbeddings
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.storage import LocalFileStore
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.chat_models import ChatOllama
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import Document
import streamlit as st
import os
import nltk
import pandas as pd
from pathlib import Path
import hashlib
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NLTK punkt 패키지 다운로드
try:
    nltk.download('punkt', quiet=True)
    # NLTK 데이터 경로 설정 (사용자 환경에 맞게 수정)
    nltk.data.path.append('/Users/aqaralife/nltk_data')
except Exception as e:
    logger.warning(f"NLTK 설정 경고: {e}")

st.set_page_config(
    page_title="📄 File GPT",
    page_icon="📄",
    layout="wide"
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

# 지원되는 파일 형식과 최대 크기 설정
SUPPORTED_FILE_TYPES = {
    "txt": {"max_size_mb": 10, "description": "텍스트 파일"},
    "md": {"max_size_mb": 10, "description": "마크다운 파일"},
    "pdf": {"max_size_mb": 50, "description": "PDF 문서"},
    "docx": {"max_size_mb": 50, "description": "Word 문서"},
    "csv": {"max_size_mb": 20, "description": "CSV 파일"},
    "json": {"max_size_mb": 20, "description": "JSON 파일"},
    "xml": {"max_size_mb": 20, "description": "XML 파일"},
    "html": {"max_size_mb": 10, "description": "HTML 파일"}
}

# 사이드바 설정
st.sidebar.title("🔧 모델 설정")
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

# 고급 설정
st.sidebar.title("⚙️ 고급 설정")
chunk_size = st.sidebar.slider(
    "청크 크기:",
    min_value=200,
    max_value=1500,
    value=800,
    step=100,
    help="텍스트를 나누는 단위 크기입니다. 클수록 맥락이 더 유지되지만 정확도가 떨어질 수 있습니다."
)

chunk_overlap = st.sidebar.slider(
    "청크 오버랩:",
    min_value=0,
    max_value=300,
    value=150,
    step=50,
    help="청크 간 중복되는 텍스트 길이입니다. 적절한 오버랩은 맥락 유지에 도움됩니다."
)

retrieval_k = st.sidebar.slider(
    "검색할 문서 수:",
    min_value=3,
    max_value=10,
    value=5,
    help="질문 답변시 참조할 관련 문서의 개수입니다."
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

# Ollama 모델 초기화 함수
@st.cache_resource
def get_llm_file(model_name, temp):
    return ChatOllama(
        model=model_name,
        temperature=temp,
        streaming=True,
        callbacks=[ChatCallbackHandler()],
    )

def validate_file(file):
    """파일 유효성 검사"""
    errors = []
    
    # 파일 확장자 확인
    file_ext = file.name.split('.')[-1].lower()
    if file_ext not in SUPPORTED_FILE_TYPES:
        errors.append(f"지원되지 않는 파일 형식: {file_ext}")
        return errors
    
    # 파일 크기 확인
    file_size_mb = file.size / (1024 * 1024)
    max_size = SUPPORTED_FILE_TYPES[file_ext]["max_size_mb"]
    if file_size_mb > max_size:
        errors.append(f"파일 크기가 너무 큽니다: {file_size_mb:.1f}MB (최대: {max_size}MB)")
    
    # 파일명 길이 확인
    if len(file.name) > 255:
        errors.append("파일명이 너무 깁니다 (최대 255자)")
    
    return errors

def get_file_hash(file_content):
    """파일 해시 생성"""
    return hashlib.md5(file_content).hexdigest()

def analyze_file_content(file_path):
    """파일 내용 분석"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            return {"error": f"파일 읽기 오류: {e}"}
    except Exception as e:
        return {"error": f"파일 분석 오류: {e}"}
    
    # 기본 통계
    lines = content.split('\n')
    words = content.split()
    
    return {
        "char_count": len(content),
        "word_count": len(words),
        "line_count": len(lines),
        "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0,
        "preview": content[:500] + "..." if len(content) > 500 else content
    }

@st.cache_data(show_spinner="파일을 임베딩하는 중...")
def embed_files(files, model_name, chunk_size_val, chunk_overlap_val, retrieval_k_val):
    """개선된 파일 임베딩 함수"""
    # 독립적인 디렉토리 경로 사용
    directory = "./file_uploads/"
    embeddings_dir = "./file_embeddings/"
    
    # 디렉토리 생성
    for dir_path in [directory, embeddings_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    all_docs = []
    file_info = []
    processing_errors = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(files)
    
    for idx, file in enumerate(files):
        try:
            status_text.text(f"📄 처리 중: {file.name} ({idx + 1}/{total_files})")
            
            # 파일 저장
            file_path = os.path.join(directory, file.name)
            file_content = file.read()
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # 파일 정보 수집
            file_hash = get_file_hash(file_content)
            file_analysis = analyze_file_content(file_path)
            
            if "error" in file_analysis:
                processing_errors.append(f"{file.name}: {file_analysis['error']}")
                continue
            
            file_info.append({
                "name": file.name,
                "size_mb": file.size / (1024 * 1024),
                "hash": file_hash,
                "char_count": file_analysis["char_count"],
                "word_count": file_analysis["word_count"],
                "line_count": file_analysis["line_count"]
            })
            
            # 독립적인 임베딩 캐시 디렉토리 사용
            cache_dir = LocalFileStore(f"./file_embeddings/{file_hash}")
            
            # 향상된 텍스트 분할기 설정
            splitter = CharacterTextSplitter.from_tiktoken_encoder(
                separator="\n\n",  # 문단 단위로 분할
                chunk_size=chunk_size_val,
                chunk_overlap=chunk_overlap_val,
            )
            
            # 문서 로드 및 분할
            loader = UnstructuredFileLoader(file_path)
            docs = loader.load()
            
            # 메타데이터 추가
            for doc in docs:
                doc.metadata.update({
                    "filename": file.name,
                    "file_hash": file_hash,
                    "file_size": file.size,
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            # 문서 분할
            split_docs = splitter.split_documents(docs)
            all_docs.extend(split_docs)
            
            # 진행률 업데이트
            progress_bar.progress((idx + 1) / total_files)
            
        except Exception as e:
            error_msg = f"{file.name}: {str(e)}"
            processing_errors.append(error_msg)
            logger.error(f"파일 처리 오류: {error_msg}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    if not all_docs:
        st.error("❌ 처리된 문서가 없습니다.")
        if processing_errors:
            with st.expander("🔍 오류 세부사항"):
                for error in processing_errors:
                    st.error(error)
        return None, None
    
    try:
        # 임베딩 생성 및 벡터스토어 구성
        status_text.text("🔄 벡터 데이터베이스 생성 중...")
        
        embeddings = OllamaEmbeddings(model=model_name)
        # 마지막 파일의 해시를 사용하여 캐시 디렉토리 설정
        cache_dir = LocalFileStore(f"./file_embeddings/combined_{hash(str(file_info))}")
        cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)
        
        vectorstore = FAISS.from_documents(all_docs, cached_embeddings)
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": retrieval_k_val}
        )
        
        status_text.empty()
        
        # 처리 결과 저장
        processing_stats = {
            "total_files": len(file_info),
            "total_chunks": len(all_docs),
            "total_chars": sum(info["char_count"] for info in file_info),
            "total_words": sum(info["word_count"] for info in file_info),
            "processing_errors": processing_errors
        }
        
        return retriever, {"file_info": file_info, "stats": processing_stats}
        
    except Exception as e:
        st.error(f"❌ 벡터 데이터베이스 생성 중 오류: {e}")
        return None, None

def save_message(message, role):
    if "file_messages" not in st.session_state:
        st.session_state["file_messages"] = []
    st.session_state["file_messages"].append({"message": message, "role": role})

def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)

def paint_history():
    if "file_messages" in st.session_state:
        for message in st.session_state["file_messages"]:
            send_message(
                message["message"],
                message["role"],
                save=False,
            )

def format_docs_enhanced(docs):
    """향상된 문서 포맷팅"""
    formatted_docs = []
    for i, doc in enumerate(docs):
        content = doc.page_content
        filename = doc.metadata.get('filename', 'Unknown')
        
        formatted_docs.append(f"[문서 {i+1} - {filename}]\n{content}")
    
    return "\n\n".join(formatted_docs)

# 한국어 지원 프롬프트 템플릿
prompt = ChatPromptTemplate.from_template(
    """아래 제공된 문서들의 내용만을 바탕으로 질문에 답해주세요. 
    문서에 없는 내용은 추측하지 말고, "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해주세요.
    답변할 때는 어떤 문서에서 해당 정보를 찾았는지도 함께 언급해주세요.

제공된 문서들:
{context}

질문: {question}

답변:"""
)

# 메인 UI
st.title("📄 File GPT")
st.markdown(f"🤖 **현재 선택된 모델:** {selected_model}")

# 데이터베이스 정보 표시
with st.expander("📋 시스템 정보"):
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**지원 파일 형식:** {', '.join(SUPPORTED_FILE_TYPES.keys())}")
        st.write(f"**청크 크기:** {chunk_size}")
    with col2:
        st.write(f"**청크 오버랩:** {chunk_overlap}")
        st.write(f"**검색 문서 수:** {retrieval_k}")

st.markdown(
    """
    💡 **사용법:**
    1. 사이드바에서 파일을 업로드하세요
    2. 모델과 설정을 조정하세요 (선택사항)
    3. 파일 처리가 완료되면 AI에게 질문하세요!
    
    **예시 질문:**
    - "이 문서의 주요 내용을 요약해주세요"
    - "특정 키워드가 언급된 부분을 찾아주세요"
    - "문서들 간의 공통점이나 차이점은 무엇인가요?"
    - "이 내용과 관련된 추천사항이 있나요?"
    """
)

# 파일 업로드 섹션
with st.sidebar:
    st.title("📁 파일 업로드")
    
    # 지원 파일 형식 정보
    with st.expander("📋 지원되는 파일 형식"):
        for ext, info in SUPPORTED_FILE_TYPES.items():
            st.write(f"**{ext.upper()}**: {info['description']} (최대 {info['max_size_mb']}MB)")
    
    files = st.file_uploader(
        "파일을 선택하세요",
        type=list(SUPPORTED_FILE_TYPES.keys()),
        accept_multiple_files=True,
        help="여러 파일을 동시에 업로드할 수 있습니다."
    )
    
    # 파일 검증
    if files:
        st.subheader("📋 업로드된 파일")
        valid_files = []
        total_size = 0
        
        for file in files:
            errors = validate_file(file)
            file_size_mb = file.size / (1024 * 1024)
            total_size += file_size_mb
            
            if errors:
                st.error(f"❌ {file.name}")
                for error in errors:
                    st.write(f"   • {error}")
            else:
                st.success(f"✅ {file.name} ({file_size_mb:.1f}MB)")
                valid_files.append(file)
        
        st.write(f"**총 파일 크기:** {total_size:.1f}MB")
        
        if total_size > 200:
            st.warning("⚠️ 파일 크기가 클 경우 처리 시간이 오래 걸릴 수 있습니다.")

# 채팅 기록 표시
paint_history()

# 파일 처리 및 RAG 시스템
if files:
    valid_files = [file for file in files if not validate_file(file)]
    
    if valid_files:
        try:
            retriever, file_data = embed_files(
                valid_files, 
                selected_model, 
                chunk_size, 
                chunk_overlap, 
                retrieval_k
            )
            
            if retriever and file_data:
                # 처리 완료 메시지
                stats = file_data["stats"]
                success_msg = f"""🎉 파일 처리가 완료되었습니다!

📊 **처리 결과:**
- 처리된 파일: {stats['total_files']}개
- 생성된 청크: {stats['total_chunks']}개  
- 총 문자 수: {stats['total_chars']:,}자
- 총 단어 수: {stats['total_words']:,}개

이제 파일 내용에 대해 무엇이든 질문해보세요!"""
                
                send_message(success_msg, "ai", save=False)
                
                # 처리 오류가 있는 경우 표시
                if stats["processing_errors"]:
                    with st.expander("⚠️ 처리 중 발생한 오류들"):
                        for error in stats["processing_errors"]:
                            st.warning(error)
                
                # 현재 로드된 파일 정보 표시
                st.write("### 📊 로드된 파일 정보")
                
                file_info_df = pd.DataFrame(file_data["file_info"])
                if not file_info_df.empty:
                    # 컬럼명 한국어로 변경
                    file_info_df = file_info_df.rename(columns={
                        "name": "파일명",
                        "size_mb": "크기(MB)", 
                        "char_count": "문자수",
                        "word_count": "단어수",
                        "line_count": "줄수"
                    })
                    
                    # 숫자 포맷팅
                    file_info_df["크기(MB)"] = file_info_df["크기(MB)"].round(2)
                    file_info_df["문자수"] = file_info_df["문자수"].apply(lambda x: f"{x:,}")
                    file_info_df["단어수"] = file_info_df["단어수"].apply(lambda x: f"{x:,}")
                    file_info_df["줄수"] = file_info_df["줄수"].apply(lambda x: f"{x:,}")
                    
                    st.dataframe(file_info_df.drop(columns=["hash"], errors="ignore"), use_container_width=True)
                
                # 세션 상태에 저장
                st.session_state["file_retriever"] = retriever
                st.session_state["file_data"] = file_data
                
            else:
                st.error("❌ 파일 처리에 실패했습니다.")
        
        except Exception as e:
            st.error(f"❌ 파일 처리 중 오류가 발생했습니다: {e}")
            logger.error(f"파일 처리 오류: {e}")
    else:
        st.warning("⚠️ 유효한 파일이 없습니다. 파일을 확인해주세요.")

# 채팅 인터페이스
if "file_retriever" in st.session_state:
    message = st.chat_input("파일 내용에 대해 질문해보세요...")
    if message:
        send_message(message, "human")
        
        with st.chat_message("ai"):
            try:
                # 현재 선택된 모델로 LLM 초기화
                llm = get_llm_file(selected_model, temperature)
                
                chain = (
                    {
                        "context": st.session_state["file_retriever"] | RunnableLambda(format_docs_enhanced),
                        "question": RunnablePassthrough(),
                    }
                    | prompt
                    | llm
                )
                
                chain.invoke(message)
                
            except Exception as e:
                st.error(f"답변 생성 중 오류가 발생했습니다: {e}")
                st.info("💡 **해결 방법:** 질문을 다시 작성하거나 파일을 다시 업로드해보세요.")

# 사이드바 하단 정보
with st.sidebar:
    st.markdown("---")
    
    # 현재 세션 정보
    if "file_data" in st.session_state:
        st.markdown("### 📊 현재 세션 정보")
        stats = st.session_state["file_data"]["stats"]
        col1, col2 = st.columns(2)
        with col1:
            st.metric("로드된 파일", f"{stats['total_files']}개")
            st.metric("생성된 청크", f"{stats['total_chunks']}개")
        with col2:
            st.metric("총 문자수", f"{stats['total_chars']:,}")
            st.metric("총 단어수", f"{stats['total_words']:,}")
    
    # 도움말
    st.markdown("### 💡 팁")
    with st.expander("효과적인 질문 방법"):
        st.markdown("""
        **좋은 질문 예시:**
        - "문서의 핵심 아이디어 3가지는?"
        - "특정 개념에 대한 설명을 찾아주세요"
        - "문서에서 수치나 통계를 요약해주세요"
        - "결론 부분의 내용을 정리해주세요"
        
        **피해야 할 질문:**
        - 문서에 없는 일반적인 지식 요청
        - 너무 추상적이거나 모호한 질문
        - 문서 외부 정보와의 비교 요청
        """)
    
    with st.expander("파일 처리 최적화"):
        st.markdown("""
        **처리 속도 향상:**
        - 파일 크기를 적정 수준으로 유지
        - 불필요한 서식이나 이미지 제거
        - 텍스트 위주의 깔끔한 파일 사용
        
        **정확도 향상:**
        - 청크 크기를 내용에 맞게 조정
        - 관련 문서들을 함께 업로드
        - 명확하고 구체적인 질문 작성
        """)

# 대화 초기화 버튼
if st.sidebar.button("💬 대화 내용 초기화"):
    st.session_state["file_messages"] = []
    st.rerun()

# 파일 데이터 초기화 버튼  
if st.sidebar.button("🗑️ 파일 데이터 초기화"):
    # 세션 상태 초기화
    keys_to_remove = ["file_messages", "file_retriever", "file_data"]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# 세션 상태 초기화
if "file_messages" not in st.session_state:
    st.session_state["file_messages"] = []