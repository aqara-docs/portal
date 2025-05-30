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
import time
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
import logging

# NLTK punkt package download
nltk.download('punkt')
nltk.data.path.append('/path/to/your/nltk_data')

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up page config
st.set_page_config(
    page_title="Website GPT", 
    page_icon="🤖"
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

# 크롤링 설정
st.sidebar.title("크롤링 설정")
max_pages = st.sidebar.number_input(
    "최대 페이지 수:", 
    min_value=1, 
    max_value=100, 
    value=10,
    help="크롤링할 최대 페이지 수를 설정합니다."
)

respect_robots = st.sidebar.checkbox(
    "robots.txt 준수", 
    value=True,
    help="웹사이트의 robots.txt 파일을 확인하고 크롤링 허용 여부를 판단합니다."
)

delay_between_requests = st.sidebar.slider(
    "요청 간 지연시간(초):", 
    min_value=0.0, 
    max_value=5.0, 
    value=1.0, 
    step=0.5,
    help="서버 부하를 줄이기 위한 요청 간 지연시간입니다."
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
def get_llm_website(model_name, temp):
    return ChatOllama(
        model=model_name,
        temperature=temp,
        streaming=True,
        callbacks=[ChatCallbackHandler()],
    )

def check_robots_txt(url, user_agent='*'):
    """robots.txt 파일을 확인하여 크롤링 허용 여부를 판단"""
    try:
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        
        can_fetch = rp.can_fetch(user_agent, url)
        logger.info(f"robots.txt 확인 - URL: {url}, 허용: {can_fetch}")
        return can_fetch
    except Exception as e:
        logger.warning(f"robots.txt 확인 중 오류: {e}")
        return True  # 확인할 수 없는 경우 허용으로 처리

def is_valid_url(url, base_domain):
    """URL이 유효하고 같은 도메인인지 확인"""
    try:
        parsed_url = urlparse(url)
        base_parsed = urlparse(base_domain)
        
        # 유효한 스키마인지 확인
        if parsed_url.scheme not in ['http', 'https']:
            logger.info(f"유효하지 않은 스키마: {url}")
            return False
        
        # 첫 번째 URL인 경우 무조건 허용
        if url == base_domain:
            return True
            
        # 같은 도메인인지 확인 (서브도메인도 허용)
        if not (parsed_url.netloc == base_parsed.netloc or 
                parsed_url.netloc.endswith('.' + base_parsed.netloc)):
            logger.info(f"다른 도메인: {url} (기준: {base_domain})")
            return False
            
        # 파일 확장자 필터링 (이미지, PDF 등 제외)
        excluded_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.xml', '.zip', '.exe']
        if any(url.lower().endswith(ext) for ext in excluded_extensions):
            logger.info(f"제외된 파일 확장자: {url}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"URL 유효성 검사 오류: {e}")
        return False

def test_url_accessibility(url):
    """URL 접근 가능성 테스트"""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        return True, response.status_code, response.headers.get('content-type', 'unknown')
    except Exception as e:
        return False, str(e), None

# Function to scrape website pages and extract text
def scrape_website(url, max_pages=10, respect_robots=True, delay=1.0):
    """개선된 웹사이트 스크래핑 함수"""
    
    # URL 정규화
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    st.info(f"🔍 크롤링 시작: {url}")
    
    # URL 접근 가능성 테스트
    accessible, status, content_type = test_url_accessibility(url)
    if not accessible:
        st.error(f"❌ URL에 접근할 수 없습니다: {status}")
        return []
    
    st.success(f"✅ URL 접근 성공 (상태코드: {status}, 콘텐츠 타입: {content_type})")
    
    visited_urls = set()
    base_domain = url
    texts = []
    urls_to_visit = [url]
    
    # 세션 설정
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    debug_info = st.empty()
    
    page_count = 0
    failed_urls = []
    
    while urls_to_visit and page_count < max_pages:
        current_url = urls_to_visit.pop(0)
        
        if current_url in visited_urls:
            continue
            
        # URL 유효성 검사
        if not is_valid_url(current_url, base_domain):
            logger.info(f"유효하지 않은 URL 건너뜀: {current_url}")
            continue
            
        # robots.txt 확인
        if respect_robots and not check_robots_txt(current_url):
            logger.info(f"robots.txt에 의해 크롤링이 금지된 URL: {current_url}")
            failed_urls.append((current_url, "robots.txt 차단"))
            continue
            
        try:
            status_text.text(f"🔄 크롤링 중: {current_url}")
            debug_info.text(f"📊 진행상황: {page_count}/{max_pages} 페이지, {len(texts)}개 텍스트 수집됨")
            
            # 요청 보내기
            response = session.get(current_url, timeout=10)
            response.raise_for_status()
            
            visited_urls.add(current_url)
            page_count += 1
            
            # Content-Type 확인
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                logger.info(f"HTML이 아닌 콘텐츠 건너뜀: {current_url} ({content_type})")
                continue
            
            # HTML 파싱
            soup = BeautifulSoup(response.content, "html.parser")
            
            # 불필요한 태그 제거
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
                tag.decompose()
            
            # 텍스트 추출 및 정리
            page_text = soup.get_text(separator="\n", strip=True)
            
            # 빈 줄 제거 및 텍스트 정리
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            # 텍스트 길이 및 품질 확인
            if len(cleaned_text) > 200:  # 최소 길이를 200자로 조정
                # 의미있는 텍스트인지 확인 (문자와 공백의 비율)
                text_chars = sum(1 for c in cleaned_text if c.isalnum() or c.isspace())
                if text_chars / len(cleaned_text) > 0.8:  # 80% 이상이 일반 텍스트
                    page_title = soup.title.string.strip() if soup.title and soup.title.string else 'No Title'
                    texts.append({
                        'content': cleaned_text,
                        'url': current_url,
                        'title': page_title,
                        'length': len(cleaned_text)
                    })
                    logger.info(f"텍스트 수집 성공: {current_url} ({len(cleaned_text)}자)")
                else:
                    logger.info(f"텍스트 품질 불량으로 건너뜀: {current_url}")
            else:
                logger.info(f"텍스트 길이 부족으로 건너뜀: {current_url} ({len(cleaned_text)}자)")
            
            # 새로운 링크 찾기 (최대 페이지 수가 남아있는 경우에만)
            if page_count < max_pages:
                new_links_found = 0
                for link in soup.find_all("a", href=True):
                    absolute_link = urljoin(current_url, link['href'])
                    # URL 정리 (앵커 제거)
                    absolute_link = absolute_link.split('#')[0]
                    
                    if (absolute_link not in visited_urls and 
                        absolute_link not in urls_to_visit and 
                        is_valid_url(absolute_link, base_domain)):
                        urls_to_visit.append(absolute_link)
                        new_links_found += 1
                        if new_links_found >= 10:  # 한 페이지에서 최대 10개 링크만
                            break
                
                logger.info(f"새로운 링크 {new_links_found}개 발견: {current_url}")
            
            # 진행률 업데이트
            progress = min(page_count / max_pages, 1.0)
            progress_bar.progress(progress)
            
            # 지연시간
            if delay > 0:
                time.sleep(delay)
                
        except requests.RequestException as e:
            error_msg = f"요청 오류 - {current_url}: {str(e)}"
            logger.error(error_msg)
            failed_urls.append((current_url, str(e)))
            continue
        except Exception as e:
            error_msg = f"크롤링 오류 - {current_url}: {str(e)}"
            logger.error(error_msg)
            failed_urls.append((current_url, str(e)))
            continue
    
    progress_bar.empty()
    status_text.empty()
    debug_info.empty()
    
    # 결과 요약
    if texts:
        total_text_length = sum(t['length'] for t in texts)
        st.success(f"✅ 총 {len(texts)}개의 페이지를 성공적으로 크롤링했습니다. (총 {total_text_length:,}자)")
        
        # 통계 저장
        st.session_state.last_crawl_stats = {
            'pages': len(texts),
            'total_chars': total_text_length,
            'failed_urls': len(failed_urls),
            'success_rate': len(texts) / (len(texts) + len(failed_urls)) * 100 if (len(texts) + len(failed_urls)) > 0 else 0
        }
        
        # 상세 정보 표시
        with st.expander("📋 크롤링 상세 정보"):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("성공한 페이지", len(texts))
                st.metric("실패한 페이지", len(failed_urls))
            with col2:
                success_rate = st.session_state.last_crawl_stats['success_rate']
                st.metric("성공률", f"{success_rate:.1f}%")
                st.metric("평균 페이지 길이", f"{total_text_length // len(texts):,}자")
            
            st.write("**수집된 페이지:**")
            for i, text_info in enumerate(texts[:5]):  # 상위 5개만 표시
                st.write(f"{i+1}. **{text_info['title']}** ({text_info['length']:,}자)")
                st.write(f"   URL: {text_info['url']}")
            
            if len(texts) > 5:
                st.write(f"... 외 {len(texts)-5}개 페이지")
    else:
        st.error(f"❌ 크롤링된 텍스트가 없습니다.")
        
        # 통계 저장 (실패 케이스)
        st.session_state.last_crawl_stats = {
            'pages': 0,
            'total_chars': 0,
            'failed_urls': len(failed_urls),
            'success_rate': 0
        }
        
        # 실패 원인 분석
        if failed_urls:
            with st.expander("❌ 실패한 URL들"):
                for url, reason in failed_urls[:10]:  # 상위 10개만 표시
                    st.write(f"- {url}: {reason}")
        
        # 디버깅 제안
        st.info("""
        💡 **문제 해결 방법:**
        1. robots.txt 준수를 비활성화해보세요
        2. 다른 URL을 시도해보세요
        3. 최대 페이지 수를 늘려보세요
        4. 지연시간을 늘려보세요
        """)
    
    return texts

# Function to embed the website's scraped text
@st.cache_data(show_spinner="Embedding website content...")
def embed_website(url, model_name, max_pages=10, respect_robots=True, delay=1.0):
    # 독립적인 캐시 디렉토리 사용
    safe_url = url.replace('/', '_').replace(':', '_').replace('?', '_').replace('&', '_')
    cache_dir = LocalFileStore(f"./website_embeddings/{safe_url}")
    
    # 텍스트 분할기 설정 개선
    splitter = CharacterTextSplitter.from_tiktoken_encoder(
        separator="\n",
        chunk_size=800,  # 청크 사이즈 증가
        chunk_overlap=200,  # 오버랩 증가
    )

    # 웹사이트 텍스트 스크래핑
    web_data = scrape_website(url, max_pages, respect_robots, delay)
    
    if not web_data:
        st.error("크롤링된 내용이 없습니다. URL을 확인해주세요.")
        return None
    
    # Document 객체 생성 (메타데이터 포함)
    docs = []
    for data in web_data:
        docs.append(Document(
            page_content=data['content'], 
            metadata={
                "source": data['url'],
                "title": data['title'],
                "domain": urlparse(url).netloc
            }
        ))

    # 문서 분할
    split_docs = []
    for doc in docs:
        split_texts = splitter.split_text(doc.page_content)
        for i, split_text in enumerate(split_texts):
            split_docs.append(Document(
                page_content=split_text, 
                metadata={
                    **doc.metadata,
                    "chunk_id": i
                }
            ))

    if not split_docs:
        st.error("분할된 문서가 없습니다.")
        return None

    # 임베딩 및 벡터스토어 생성
    try:
        embeddings = OllamaEmbeddings(model=model_name)
        cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)

        vectorstore = FAISS.from_documents(split_docs, cached_embeddings)
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}  # 더 많은 문서 검색
        )

        return retriever
    except Exception as e:
        st.error(f"임베딩 생성 중 오류가 발생했습니다: {e}")
        return None

# Function to save chat messages
def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)

def save_message(message, role):
    if "website_messages" not in st.session_state:
        st.session_state["website_messages"] = []
    st.session_state["website_messages"].append({"message": message, "role": role})

# Function to display chat history
def paint_history():
    if "website_messages" in st.session_state:
        for message in st.session_state["website_messages"]:
            send_message(
                message["message"],
                message["role"],
                save=False,
            )

# Function to format retrieved documents
def format_docs(docs):
    formatted_docs = []
    for i, doc in enumerate(docs):
        content = doc.page_content
        source = doc.metadata.get('source', 'Unknown')
        title = doc.metadata.get('title', 'No Title')
        
        formatted_docs.append(f"[문서 {i+1}]\n제목: {title}\n출처: {source}\n내용: {content}")
    
    return "\n\n".join(formatted_docs)

# 개선된 프롬프트 템플릿
prompt = ChatPromptTemplate.from_template(
    """아래 제공된 문서들의 정보만을 바탕으로 질문에 답해주세요. 
    문서에 없는 내용은 추측하지 말고, "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답해주세요.
    답변할 때는 관련된 출처(URL)도 함께 언급해주세요.
    
    검색된 문서들:
    {context}
    
    질문: {question}
    
    답변:"""
)

st.title("Website Scraping GPT")
st.markdown(f"🤖 현재 선택된 모델: **{selected_model}**")

st.markdown(
    """
    Welcome! 
    Enter a website URL to scrape and use the content for AI-powered question answering.
    
    ⚠️ **주의사항:**
    - 웹사이트의 이용약관과 robots.txt를 준수합니다
    - 과도한 크롤링으로 인한 서버 부하를 방지하기 위해 지연시간을 설정합니다
    - 개인정보나 저작권이 있는 콘텐츠는 주의해서 사용하세요
    """
)

# User inputs URL in the sidebar
with st.sidebar:
    st.title("웹사이트 입력")
    website_url = st.text_input("Enter website URL", placeholder="https://example.com")
    
    # URL 테스트 기능
    if website_url:
        if st.button("🔍 URL 접근 테스트"):
            # URL 정규화
            test_url = website_url
            if not test_url.startswith(('http://', 'https://')):
                test_url = 'https://' + test_url
            
            with st.spinner("URL 테스트 중..."):
                accessible, status, content_type = test_url_accessibility(test_url)
                
                if accessible:
                    st.success(f"✅ 접근 성공!")
                    st.write(f"**상태코드:** {status}")
                    st.write(f"**콘텐츠 타입:** {content_type}")
                    
                    # robots.txt 확인
                    if respect_robots:
                        robots_allowed = check_robots_txt(test_url)
                        if robots_allowed:
                            st.success("✅ robots.txt 허용")
                        else:
                            st.warning("⚠️ robots.txt에서 크롤링 차단됨")
                    
                    # 간단한 크롤링 테스트
                    try:
                        response = requests.get(test_url, timeout=10)
                        soup = BeautifulSoup(response.content, "html.parser")
                        
                        # 페이지 정보
                        title = soup.title.string if soup.title else "제목 없음"
                        links = len(soup.find_all("a", href=True))
                        text_length = len(soup.get_text())
                        
                        st.write(f"**페이지 제목:** {title}")
                        st.write(f"**링크 수:** {links}개")
                        st.write(f"**텍스트 길이:** {text_length:,}자")
                        
                    except Exception as e:
                        st.error(f"상세 분석 실패: {e}")
                else:
                    st.error(f"❌ 접근 실패: {status}")
                    
                    # 일반적인 해결 방법 제안
                    st.info("""
                    💡 **해결 방법:**
                    - URL이 올바른지 확인
                    - 'http://' 또는 'https://' 포함 여부 확인
                    - 웹사이트가 실제로 존재하는지 확인
                    - 방화벽이나 네트워크 설정 확인
                    """)

if website_url:
    try:
        retriever = embed_website(
            website_url, 
            selected_model, 
            max_pages, 
            respect_robots, 
            delay_between_requests
        )
        
        if retriever:
            send_message("🎉 웹사이트 데이터가 준비되었습니다! 무엇이든 질문해보세요.", "ai", save=False)
            paint_history()
            
            message = st.chat_input("웹사이트 내용에 대해 질문해보세요...")
            if message:
                send_message(message, "human")
                
                # 현재 선택된 모델로 LLM 초기화
                llm = get_llm_website(selected_model, temperature)
                
                chain = (
                    {
                        "context": retriever | RunnableLambda(format_docs),
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
                        st.info("다시 시도해보거나 다른 질문을 해보세요.")
        else:
            st.error("❌ 웹사이트 데이터를 처리할 수 없습니다.")
            
            # 추가 도움말
            with st.expander("🔧 문제 해결 가이드"):
                st.markdown("""
                ### 일반적인 문제들과 해결 방법:
                
                1. **URL 접근 불가**
                   - URL이 올바른지 확인
                   - 웹사이트가 실제로 존재하는지 확인
                   - VPN이나 프록시 설정 확인
                
                2. **robots.txt 차단**
                   - 사이드바에서 "robots.txt 준수" 옵션 해제
                   - 다른 웹사이트로 시도
                
                3. **텍스트 추출 실패**
                   - JavaScript가 많이 사용된 SPA 사이트는 크롤링이 어려울 수 있음
                   - 정적 HTML 콘텐츠가 많은 사이트를 시도
                
                4. **속도 제한**
                   - 요청 간 지연시간을 늘려보세요
                   - 최대 페이지 수를 줄여보세요
                
                ### 추천 테스트 사이트:
                - https://example.com (간단한 테스트)
                - https://httpbin.org (HTTP 테스트)
                - 뉴스 사이트나 블로그 (텍스트 콘텐츠 풍부)
                """)
            
    except Exception as e:
        st.error(f"❌ 오류가 발생했습니다: {e}")
        logger.error(f"전체 프로세스 오류: {e}")
        
        # 디버깅 정보 표시
        with st.expander("🐛 디버깅 정보"):
            st.code(str(e))
            st.write("**오류 타입:**", type(e).__name__)
            
            # 시스템 정보
            st.write("**시스템 정보:**")
            st.write(f"- Python 버전: {os.sys.version}")
            st.write(f"- 현재 디렉토리: {os.getcwd()}")

if st.sidebar.button("💬 대화 내용 초기화"):
    st.session_state["website_messages"] = []
    st.rerun()

# 세션 상태 초기화
if "website_messages" not in st.session_state:
    st.session_state["website_messages"] = []
    
# 추가 정보 사이드바
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📊 크롤링 통계")
    if "last_crawl_stats" in st.session_state:
        stats = st.session_state.last_crawl_stats
        st.metric("마지막 크롤링 페이지", stats.get('pages', 0))
        st.metric("수집된 텍스트 길이", f"{stats.get('total_chars', 0):,}자")
    
    st.markdown("### ℹ️ 도움말")
    with st.expander("사용법"):
        st.markdown("""
        1. 웹사이트 URL 입력
        2. 크롤링 설정 조정
        3. URL 테스트 (선택사항)
        4. 크롤링 실행
        5. AI에게 질문하기
        """)
    
    with st.expander("주의사항"):
        st.markdown("""
        - 저작권 보호 콘텐츠 주의
        - 과도한 크롤링 금지
        - robots.txt 준수 권장
        - 개인정보 포함 사이트 주의
        """)