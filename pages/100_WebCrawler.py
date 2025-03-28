import streamlit as st
import asyncio
from crawl4ai import AsyncWebCrawler
import re
from urllib.parse import unquote, urlparse, urlunparse, urljoin
import html2text
from bs4 import BeautifulSoup

def normalize_url(url):
    """URL을 정규화하는 함수"""
    if ':/' in url and '://' not in url:
        url = url.replace(':/', '://')
    
    parsed = urlparse(url)
    normalized = urlunparse(parsed)
    
    return normalized

def extract_main_content(html_content, base_url):
    """HTML에서 메인 콘텐츠만 추출하는 함수"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 모든 상대 경로 URL을 절대 경로로 변환
    for tag in soup.find_all(['a', 'img']):
        if tag.get('href'):
            tag['href'] = urljoin(base_url, tag['href'])
        if tag.get('src'):
            tag['src'] = urljoin(base_url, tag['src'])
    
    # 뉴스 목록 페이지인 경우
    news_list = soup.select('.elementor-posts-container article')
    if news_list:
        container = soup.new_tag('div')
        for article in news_list:
            container.append(article)
        return str(container)
    
    # 개별 뉴스 페이지인 경우
    news_content = soup.select_one('.elementor-widget-theme-post-content')
    if news_content:
        return str(news_content)
    
    # 일반적인 메인 콘텐츠 영역 선택자들 (fallback)
    content_selectors = [
        '.elementor-location-single',  # Aqara 사이트 특화
        'main',
        'article',
        '#content', '#main-content', '#main',
        '.content', '.main-content', '.main',
    ]
    
    for selector in content_selectors:
        content = soup.select_one(selector)
        if content:
            return str(content)
    
    return str(soup.body) if soup.body else str(soup)

st.title("웹 크롤러")

# URL 입력 필드
url = st.text_input("크롤링할 웹사이트 URL을 입력하세요:", "https://example.com")

# 크롤링 버튼
if st.button("크롤링 시작"):
    if url:
        with st.spinner("크롤링 중..."):
            async def crawl():
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url)
                    
                    # 메인 콘텐츠 추출 (base_url 전달)
                    main_content = extract_main_content(result.html, url)
                    
                    # HTML을 마크다운으로 변환
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.ignore_images = False
                    h.body_width = 0
                    return h.handle(main_content)

            result = asyncio.run(crawl())
            
            st.subheader("크롤링 결과:")
            st.markdown(result)
            
            st.download_button(
                label="마크다운 파일 다운로드",
                data=result,
                file_name="crawled_content.md",
                mime="text/markdown"
            )
    else:
        st.error("URL을 입력해주세요.")