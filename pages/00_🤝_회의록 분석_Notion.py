import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import openai

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Notion 데이터 읽기",
    page_icon="📝",
    layout="wide"
)
st.title("📝 회의록 데이터 분석")
# 인증 기능 (간단한 비밀번호 보호)
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
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

# 사이드바 설정
st.sidebar.title("⚙️ 설정")

# Notion API 설정 (.env에서 읽어오기)
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DB_URL = os.getenv("NOTION_DB_URL")

class LLMClient:
    """다양한 LLM 클라이언트를 관리하는 클래스"""
    
    def __init__(self):
        self.clients = {}
        self.models = {}
        self.setup_clients()
    
    def setup_clients(self):
        """사용 가능한 LLM 클라이언트들을 설정"""
        # OpenAI 클라이언트 (기본)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            try:
                self.clients['openai'] = openai.OpenAI(api_key=openai_key)
                self.models['openai'] = [
                    'gpt-4o-mini',
                    'gpt-4o',
                    'gpt-4-turbo',
                    'gpt-4',
                    'gpt-3.5-turbo'
                ]
            except Exception as e:
                pass
        
        # Ollama 클라이언트 (로컬 LLM) - 선택적
        try:
            import requests
            # Ollama 서버 연결 테스트 (짧은 타임아웃)
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.clients['ollama'] = requests
                self.models['ollama'] = [
                    'mistral:latest',
                    'llama3.1:latest',
                    'llama3.1:8b',
                    'phi4:latest',
                    'llama2:latest',
                    'gemma2:latest',
                    'gemma:latest',
                    'llama3.2:latest',
                    'deepseek-r1:14b',
                    'nomic-embed-text:latest'
                ]
        except Exception as e:
            # Ollama 연결 실패 시 조용히 무시
            pass
        
        # Perplexity 클라이언트
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if perplexity_key:
            try:
                self.clients['perplexity'] = openai.OpenAI(
                    api_key=perplexity_key,
                    base_url="https://api.perplexity.ai"
                )
                self.models['perplexity'] = [
                    "sonar-pro",
                    "sonar-small-chat"
                ]
            except Exception as e:
                pass
        
        # Anthropic 클라이언트 (Claude)
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_api_key:
            try:
                from langchain_anthropic import ChatAnthropic
                self.clients['anthropic'] = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    anthropic_api_key=anthropic_api_key,
                    temperature=0.1,
                    max_tokens=4000
                )
                self.models['anthropic'] = [
                    'claude-3-7-sonnet-latest',
                    'claude-3-5-sonnet-20241022',
                    'claude-3-5-haiku-20241022',
                    'claude-3-5-sonnet-20241022',
                    'claude-3-haiku-20240307'
                ]
            except Exception as e:
                pass
        
        # Google 클라이언트 (Gemini)
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if google_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_api_key)
                self.clients['google'] = genai
                self.models['google'] = [
                    'gemini-1.5-pro',
                    'gemini-1.5-flash',
                    'gemini-1.0-pro'
                ]
            except Exception as e:
                pass
    
    def get_available_providers(self):
        """사용 가능한 LLM 제공자 목록 반환"""
        return list(self.clients.keys())
    
    def get_models_for_provider(self, provider):
        """특정 제공자의 모델 목록 반환"""
        return self.models.get(provider, [])
    
    def generate_response(self, provider, model, messages, temperature=0.7, max_tokens=2000):
        """선택된 LLM으로 응답 생성"""
        try:
            if provider not in self.clients:
                return None, f"클라이언트가 설정되지 않은 제공자: {provider}"
            
            if provider == 'ollama':
                return self._generate_ollama_response(model, messages, temperature, max_tokens)
            elif provider == 'openai':
                return self._generate_openai_response(model, messages, temperature, max_tokens)
            elif provider == 'perplexity':
                return self._generate_perplexity_response(model, messages, temperature, max_tokens)
            elif provider == 'anthropic':
                return self._generate_anthropic_response(model, messages, temperature, max_tokens)
            elif provider == 'google':
                return self._generate_google_response(model, messages, temperature, max_tokens)
            else:
                return None, f"지원하지 않는 제공자: {provider}"
        except Exception as e:
            return None, f"응답 생성 오류: {str(e)}"
    
    def _generate_ollama_response(self, model, messages, temperature, max_tokens):
        """Ollama 응답 생성"""
        try:
            # Ollama API 형식에 맞게 메시지 변환
            ollama_messages = []
            for msg in messages:
                if msg['role'] == 'system':
                    continue
                elif msg['role'] == 'user':
                    ollama_messages.append({
                        'role': 'user',
                        'content': msg['content']
                    })
                elif msg['role'] == 'assistant':
                    ollama_messages.append({
                        'role': 'assistant',
                        'content': msg['content']
                    })
            
            # 시스템 메시지가 있으면 첫 번째 사용자 메시지에 포함
            system_content = ""
            for msg in messages:
                if msg['role'] == 'system':
                    system_content = msg['content']
                    break
            
            if system_content and ollama_messages:
                ollama_messages[0]['content'] = f"{system_content}\n\n{ollama_messages[0]['content']}"
            
            # Ollama API 호출
            response = self.clients['ollama'].post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['message']['content'], None
            else:
                return None, f"Ollama API 오류: {response.status_code}"
                
        except Exception as e:
            return None, f"Ollama 응답 생성 오류: {str(e)}"
    
    def _generate_openai_response(self, model, messages, temperature, max_tokens):
        """OpenAI 응답 생성"""
        try:
            response = self.clients['openai'].chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content, None
        except Exception as e:
            return None, f"OpenAI 응답 생성 오류: {str(e)}"
    
    def _generate_perplexity_response(self, model, messages, temperature, max_tokens):
        """Perplexity 응답 생성"""
        try:
            response = self.clients['perplexity'].chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content, None
        except Exception as e:
            return None, f"Perplexity 응답 생성 오류: {str(e)}"
    
    def _generate_anthropic_response(self, model, messages, temperature, max_tokens):
        """Anthropic 응답 생성"""
        try:
            # LangChain ChatAnthropic을 사용
            response = self.clients['anthropic'].invoke(messages)
            return response.content, None
        except Exception as e:
            return None, f"Anthropic 응답 생성 오류: {str(e)}"
    
    def _generate_google_response(self, model, messages, temperature, max_tokens):
        """Google 응답 생성"""
        try:
            # Google Gemini API 사용
            model_obj = self.clients['google'].GenerativeModel(model)
            # 메시지를 Gemini 형식으로 변환
            prompt = ""
            for msg in messages:
                if msg['role'] == 'user':
                    prompt += f"User: {msg['content']}\n"
                elif msg['role'] == 'assistant':
                    prompt += f"Assistant: {msg['content']}\n"
                elif msg['role'] == 'system':
                    prompt = f"System: {msg['content']}\n" + prompt
            
            response = model_obj.generate_content(prompt)
            return response.text, None
        except Exception as e:
            return None, f"Google 응답 생성 오류: {str(e)}"

# Database ID 추출 함수
def extract_database_id(url: str) -> str:
    """Notion URL에서 Database ID를 추출합니다."""
    import re
    
    # 다양한 URL 패턴에서 Database ID 추출
    patterns = [
        r'notion\.so/workspace/([a-zA-Z0-9]{32})',
        r'notion\.so/([a-zA-Z0-9]{32})',
        r'notion\.so/workspace/([a-zA-Z0-9]{32})\?',
        r'notion\.so/([a-zA-Z0-9]{32})\?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

# Database ID 추출
DATABASE_ID = None
if NOTION_DB_URL:
    DATABASE_ID = extract_database_id(NOTION_DB_URL)
else:
    pass

# 수동 Database ID 입력 (백업용)
MANUAL_DATABASE_ID = st.sidebar.text_input(
    "Database ID (수동 입력)",
    help="자동 추출이 실패한 경우 수동으로 Database ID를 입력하세요."
)

# 최종 Database ID 결정
FINAL_DATABASE_ID = DATABASE_ID or MANUAL_DATABASE_ID

if NOTION_API_KEY:
    pass
else:
    pass

# 메인 함수들
def test_notion_connection(api_key: str) -> Dict:
    """Notion API 연결을 테스트합니다."""
    url = "https://api.notion.com/v1/users/me"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "status_code": response.status_code if 'response' in locals() else None}

def get_page_content(page_id: str, api_key: str) -> str:
    """Notion 페이지의 전체 내용을 가져옵니다."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        blocks_data = response.json()
        
        content = ""
        for block in blocks_data.get("results", []):
            block_type = block.get("type", "")
            if block_type == "paragraph":
                rich_text = block.get("paragraph", {}).get("rich_text", [])
                for text in rich_text:
                    content += text.get("plain_text", "") + "\n"
            elif block_type == "heading_1":
                rich_text = block.get("heading_1", {}).get("rich_text", [])
                for text in rich_text:
                    content += text.get("plain_text", "") + "\n"
            elif block_type == "heading_2":
                rich_text = block.get("heading_2", {}).get("rich_text", [])
                for text in rich_text:
                    content += text.get("plain_text", "") + "\n"
            elif block_type == "heading_3":
                rich_text = block.get("heading_3", {}).get("rich_text", [])
                for text in rich_text:
                    content += text.get("plain_text", "") + "\n"
            elif block_type == "bulleted_list_item":
                rich_text = block.get("bulleted_list_item", {}).get("rich_text", [])
                for text in rich_text:
                    content += "• " + text.get("plain_text", "") + "\n"
            elif block_type == "numbered_list_item":
                rich_text = block.get("numbered_list_item", {}).get("rich_text", [])
                for text in rich_text:
                    content += "- " + text.get("plain_text", "") + "\n"
            elif block_type == "to_do":
                rich_text = block.get("to_do", {}).get("rich_text", [])
                checked = block.get("to_do", {}).get("checked", False)
                for text in rich_text:
                    checkbox = "[x]" if checked else "[ ]"
                    content += f"{checkbox} " + text.get("plain_text", "") + "\n"
        
        return content.strip()
        
    except requests.exceptions.RequestException as e:
        return ""

def search_notion_content(api_key: str, query: str, database_id: str = None, start_date: str = None, end_date: str = None):
    """Notion Search API를 사용하여 전체 내용에서 검색 (사용하지 않음)"""
    pass

def get_notion_database(database_id: str, api_key: str, start_date: str = None, end_date: str = None, search_term: str = None, search_full_content: bool = False) -> Dict:
    """Notion 데이터베이스에서 데이터를 가져옵니다."""
    # Database Query API 사용 (Search API 대신)
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        all_results = []
        has_more = True
        start_cursor = None
        page_count = 0
        
        with st.spinner("데이터를 가져오는 중..."):
            while has_more:
                page_count += 1
                st.info(f"페이지 {page_count} 가져오는 중... (현재 {len(all_results)}개)")
                
                # 요청 본문 구성
                request_body = {
                    "page_size": 100  # 최대 100개씩 가져오기
                }
                
                if start_cursor:
                    request_body["start_cursor"] = start_cursor
                
                response = requests.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                notion_data = response.json()
                
                # 결과 추가
                current_results = notion_data.get("results", [])
                all_results.extend(current_results)
                
                # 다음 페이지 확인
                has_more = notion_data.get("has_more", False)
                start_cursor = notion_data.get("next_cursor")
                
                st.info(f"페이지 {page_count} 완료: {len(current_results)}개 추가 (총 {len(all_results)}개)")
        
        st.success(f"✅ 데이터 가져오기 완료: 총 {len(all_results)}개 항목 ({page_count}페이지)")
        
        # 전체 결과를 하나의 응답 형태로 구성
        notion_data = {
            "results": all_results,
            "has_more": False,
            "next_cursor": None
        }
        
        # 검색어가 있으면 클라이언트에서 필터링
        if search_term:
            filtered_results = []
            
            for result in notion_data.get("results", []):
                # 제목에서 검색
                title = ""
                if "properties" in result:
                    name_prop = result["properties"].get("이름", {})
                    if name_prop.get("type") == "title":
                        title_rich_text = name_prop.get("title", [])
                        title = "".join([text.get("plain_text", "") for text in title_rich_text])
                
                # 제목에서 검색어 발견
                if search_term.lower() in title.lower():
                    filtered_results.append(result)
                    continue
                
                # 전체 내용 검색이 선택된 경우에만 내용에서 검색
                if search_full_content:
                    page_id = result.get("id", "")
                    if page_id:
                        page_content = get_page_content(page_id, api_key)
                        if page_content and search_term.lower() in page_content.lower():
                            filtered_results.append(result)
                            continue
            
            notion_data["results"] = filtered_results
        
        return notion_data
        
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 오류: {e}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"상태 코드: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                st.error(f"오류 상세: {error_detail}")
            except:
                st.error(f"응답 내용: {e.response.text}")
        return None

def parse_notion_properties(properties: Dict) -> Dict:
    """Notion 속성들을 파싱합니다."""
    parsed = {}
    
    for key, value in properties.items():
        prop_type = value.get("type")
        
        if prop_type == "title":
            title_content = value.get("title", [])
            if title_content:
                parsed[key] = title_content[0].get("plain_text", "")
            else:
                parsed[key] = ""
                
        elif prop_type == "rich_text":
            rich_text_content = value.get("rich_text", [])
            if rich_text_content:
                parsed[key] = rich_text_content[0].get("plain_text", "")
            else:
                parsed[key] = ""
                
        elif prop_type == "number":
            parsed[key] = value.get("number")
            
        elif prop_type == "select":
            select_value = value.get("select")
            if select_value:
                parsed[key] = select_value.get("name", "")
            else:
                parsed[key] = ""
                
        elif prop_type == "multi_select":
            multi_select_values = value.get("multi_select", [])
            parsed[key] = ", ".join([item.get("name", "") for item in multi_select_values])
            
        elif prop_type == "date":
            date_value = value.get("date")
            if date_value:
                parsed[key] = date_value.get("start", "")
            else:
                parsed[key] = ""
                
        elif prop_type == "checkbox":
            parsed[key] = value.get("checkbox", False)
            
        elif prop_type == "url":
            parsed[key] = value.get("url", "")
            
        elif prop_type == "email":
            parsed[key] = value.get("email", "")
            
        elif prop_type == "phone_number":
            parsed[key] = value.get("phone_number", "")
            
        else:
            parsed[key] = str(value)
    
    return parsed

def convert_to_dataframe(notion_data: Dict, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Notion 데이터를 DataFrame으로 변환하고 날짜 필터링을 적용합니다."""
    if not notion_data or "results" not in notion_data:
        return pd.DataFrame()
    
    rows = []
    for page in notion_data["results"]:
        # Search API와 Database Query API의 구조가 다름
        if "properties" in page:
            # Database Query API 결과
            properties = page.get("properties", {})
            parsed_properties = parse_notion_properties(properties)
        else:
            # Search API 결과 - 기본 정보만 추출
            parsed_properties = {
                "이름": page.get("title", [{}])[0].get("plain_text", "") if page.get("title") else "",
                "page_id": page.get("id", ""),
                "created_time": page.get("created_time", ""),
                "last_edited_time": page.get("last_edited_time", ""),
                "url": page.get("url", "")
            }
        
        # 페이지 ID와 생성/수정 시간 추가 (이미 있는 경우 덮어쓰지 않음)
        if "page_id" not in parsed_properties:
            parsed_properties["page_id"] = page.get("id", "")
        if "created_time" not in parsed_properties:
            parsed_properties["created_time"] = page.get("created_time", "")
        if "last_edited_time" not in parsed_properties:
            parsed_properties["last_edited_time"] = page.get("last_edited_time", "")
        
        rows.append(parsed_properties)
    
    df = pd.DataFrame(rows)
    
    # 날짜 필터링 적용 (Search API에서 이미 필터링된 경우 제외)
    if not df.empty and (start_date or end_date):
        try:
            # created_time을 datetime으로 변환하고 한국 시간대(KST)로 변환
            df['created_time_dt'] = pd.to_datetime(df['created_time']).dt.tz_convert('Asia/Seoul')
        except:
            # 시간대 변환에 실패하면 UTC로 처리하고 9시간 추가 (KST = UTC+9)
            df['created_time_dt'] = pd.to_datetime(df['created_time']) + pd.Timedelta(hours=9)
        
        # 날짜만 비교하도록 시간 정보 제거
        df['created_time_date'] = df['created_time_dt'].dt.date
        
        if start_date and end_date:
            start_dt = pd.to_datetime(start_date).date()
            end_dt = pd.to_datetime(end_date).date()
            mask = (df['created_time_date'] >= start_dt) & (df['created_time_date'] <= end_dt)
        elif start_date:
            start_dt = pd.to_datetime(start_date).date()
            mask = df['created_time_date'] >= start_dt
        elif end_date:
            end_dt = pd.to_datetime(end_date).date()
            mask = df['created_time_date'] <= end_dt
        else:
            mask = pd.Series([True] * len(df), index=df.index)
        
        df = df[mask]
        
        # 임시 컬럼 제거
        if 'created_time_dt' in df.columns:
            df = df.drop('created_time_dt', axis=1)
        if 'created_time_date' in df.columns:
            df = df.drop('created_time_date', axis=1)
    
    return df



def get_notion_page_content(page_id: str, api_key: str) -> Dict:
    """Notion 페이지의 상세 내용을 가져옵니다."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"페이지 내용 가져오기 오류: {e}")
        return None

def get_notion_page_blocks(page_id: str, api_key: str) -> List[Dict]:
    """Notion 페이지의 블록 내용을 가져옵니다."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("results", [])
    except requests.exceptions.RequestException as e:
        st.error(f"블록 내용 가져오기 오류: {e}")
        return []

def parse_notion_blocks(blocks: List[Dict], api_key: str = None) -> str:
    """Notion 블록들을 텍스트로 파싱합니다."""
    content = []
    
    for block in blocks:
        block_type = block.get("type")
        
        if block_type == "paragraph":
            rich_text = block.get("paragraph", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(text)
                    
        elif block_type == "heading_1":
            rich_text = block.get("heading_1", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"# {text}")
                    
        elif block_type == "heading_2":
            rich_text = block.get("heading_2", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"## {text}")
                    
        elif block_type == "heading_3":
            rich_text = block.get("heading_3", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"### {text}")
                    
        elif block_type == "bulleted_list_item":
            rich_text = block.get("bulleted_list_item", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"• {text}")
                    
        elif block_type == "numbered_list_item":
            rich_text = block.get("numbered_list_item", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"1. {text}")
                    
        elif block_type == "quote":
            rich_text = block.get("quote", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"> {text}")
                    
        elif block_type == "code":
            rich_text = block.get("code", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"```\n{text}\n```")
                    
        elif block_type == "divider":
            content.append("---")
            
        elif block_type == "table_of_contents":
            content.append("[목차]")
            
        elif block_type == "callout":
            rich_text = block.get("callout", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    icon = block.get("callout", {}).get("icon", {}).get("emoji", "💡")
                    content.append(f"{icon} {text}")
                    
        elif block_type == "toggle":
            rich_text = block.get("toggle", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    content.append(f"▶ {text}")
                    
        elif block_type == "to_do":
            rich_text = block.get("to_do", {}).get("rich_text", [])
            if rich_text:
                text = "".join([rt.get("plain_text", "") for rt in rich_text])
                if text.strip():
                    checked = block.get("to_do", {}).get("checked", False)
                    checkbox = "☑" if checked else "☐"
                    content.append(f"{checkbox} {text}")
                    
        elif block_type == "synced_block":
            # 동기화된 블록은 하위 블록들을 재귀적으로 처리
            children = block.get("synced_block", {}).get("children", [])
            if children:
                child_content = parse_notion_blocks(children, api_key)
                if child_content.strip():
                    content.append(child_content)
                    
        elif block_type == "child_database":
            # 하위 데이터베이스는 링크로 표시
            database_id = block.get("child_database", {}).get("id", "")
            if database_id:
                content.append(f"[📊 하위 데이터베이스](https://notion.so/{database_id})")
                
        elif block_type == "child_page":
            # 하위 페이지의 실제 내용을 가져와서 표시
            page_id = block.get("child_page", {}).get("id", "")
            if page_id and api_key:
                # 하위 페이지의 제목 가져오기
                page_info = get_notion_page_content(page_id, api_key)
                if page_info:
                    properties = page_info.get("properties", {})
                    title = ""
                    
                    # 제목 속성 찾기
                    for prop_name, prop_value in properties.items():
                        if prop_value.get("type") == "title":
                            title_content = prop_value.get("title", [])
                            if title_content:
                                title = title_content[0].get("plain_text", "")
                                break
                    
                    if title:
                        content.append(f"## 📄 {title}")
                        
                        # 하위 페이지의 블록 내용 가져오기
                        child_blocks = get_notion_page_blocks(page_id, api_key)
                        if child_blocks:
                            child_content = parse_notion_blocks(child_blocks, api_key)
                            if child_content.strip():
                                content.append(child_content)
                            else:
                                content.append("*[내용 없음]*")
                        else:
                            content.append("*[내용을 가져올 수 없음]*")
                    else:
                        content.append(f"[📄 하위 페이지](https://notion.so/{page_id})")
                else:
                    content.append(f"[📄 하위 페이지](https://notion.so/{page_id})")
            else:
                content.append(f"[📄 하위 페이지](https://notion.so/{page_id})")
                
        elif block_type == "embed":
            # 임베드된 콘텐츠
            url = block.get("embed", {}).get("url", "")
            if url:
                content.append(f"[🔗 임베드 링크]({url})")
                
        elif block_type == "image":
            # 이미지
            url = block.get("image", {}).get("file", {}).get("url", "")
            if url:
                content.append(f"![이미지]({url})")
                
        elif block_type == "video":
            # 비디오
            url = block.get("video", {}).get("file", {}).get("url", "")
            if url:
                content.append(f"🎥 [비디오]({url})")
                
        elif block_type == "file":
            # 파일
            url = block.get("file", {}).get("file", {}).get("url", "")
            if url:
                content.append(f"📎 [파일]({url})")
                
        elif block_type == "pdf":
            # PDF
            url = block.get("pdf", {}).get("file", {}).get("url", "")
            if url:
                content.append(f"📄 [PDF]({url})")
                
        elif block_type == "bookmark":
            # 북마크
            url = block.get("bookmark", {}).get("url", "")
            if url:
                content.append(f"🔖 [북마크]({url})")
                
        elif block_type == "equation":
            # 수식
            expression = block.get("equation", {}).get("expression", "")
            if expression:
                content.append(f"$${expression}$$")
                
        elif block_type == "table":
            # 테이블 (간단한 텍스트로 표시)
            content.append("[📊 테이블]")
            
        elif block_type == "column_list":
            # 컬럼 리스트
            content.append("[📋 컬럼 레이아웃]")
            
        elif block_type == "column":
            # 컬럼
            content.append("[📋 컬럼]")
            
        elif block_type == "template":
            # 템플릿
            content.append("[📋 템플릿]")
            
        elif block_type == "link_preview":
            # 링크 미리보기
            url = block.get("link_preview", {}).get("url", "")
            if url:
                content.append(f"🔗 [링크 미리보기]({url})")
                
        elif block_type == "unsupported":
            # 지원되지 않는 블록
            content.append("[⚠️ 지원되지 않는 블록]")
            
        else:
            # 알 수 없는 블록 타입
            content.append(f"[❓ 알 수 없는 블록: {block_type}]")
    
    return "\n\n".join(content)

def get_meeting_content_for_search(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """검색을 위해 회의록 내용을 가져와서 데이터프레임에 추가합니다."""
    if df.empty:
        return df
    
    # 회의록 항목들만 필터링 (이름이 있는 항목들)
    meeting_items = df[df['이름'].notna() & (df['이름'] != '')]
    
    if meeting_items.empty:
        return df
    
    # 내용 컬럼 추가
    df_with_content = df.copy()
    df_with_content['회의_내용'] = ""
    
    # 각 회의록의 내용을 가져와서 추가
    for idx, row in meeting_items.iterrows():
        page_id = row['page_id']
        try:
            blocks = get_notion_page_blocks(page_id, api_key)
            if blocks:
                content = parse_notion_blocks(blocks, api_key)
                if content.strip():
                    df_with_content.at[idx, '회의_내용'] = content
        except Exception as e:
            # 오류가 발생해도 계속 진행
            continue
    
    return df_with_content

def display_meeting_details(df: pd.DataFrame, api_key: str):
    """회의록 상세 내용을 표시합니다."""
    if df.empty:
        return
    
    # 회의록 항목들만 필터링 (이름이 있는 항목들)
    meeting_items = df[df['이름'].notna() & (df['이름'] != '')]
    
    if meeting_items.empty:
        return
    
    st.subheader("📋 회의록 상세 내용")
    
    # 회의록 선택
    selected_meeting = st.selectbox(
        "회의록 선택",
        options=meeting_items['이름'].tolist(),
        index=0,
        help="분석할 회의록을 선택하세요"
    )
    
    if selected_meeting:
        # 선택된 회의록의 페이지 ID 찾기
        selected_row = meeting_items[meeting_items['이름'] == selected_meeting].iloc[0]
        page_id = selected_row['page_id']
        
        pass
        
        # 페이지 내용 가져오기
        with st.spinner("회의록 내용을 가져오는 중..."):
            blocks = get_notion_page_blocks(page_id, api_key)
            
            if blocks:
                # 블록 타입 분석
                block_types = [block.get("type", "unknown") for block in blocks]
                type_counts = {}
                for block_type in block_types:
                    type_counts[block_type] = type_counts.get(block_type, 0) + 1
                
                content = parse_notion_blocks(blocks, api_key)
                
                if content.strip():
                    st.markdown("---")
                    st.markdown("### 📝 회의록 내용")
                    st.markdown(content)
                    
                    # 회의록 내용 다운로드
                    meeting_title = selected_meeting.replace("/", "_").replace("\\", "_")
                    file_name = f"{meeting_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    
                    # 회의록 내용을 마크다운 형식으로 구성
                    markdown_content = f"""# {selected_meeting}

## 회의 정보
- **생성일**: {selected_row['created_time']}
- **수정일**: {selected_row['last_edited_time']}
- **페이지 ID**: {page_id}

## 회의록 내용

{content}

---
*이 문서는 Notion 회의록에서 자동으로 생성되었습니다.*
"""
                    
                    st.download_button(
                        label="📄 회의록 내용 다운로드",
                        data=markdown_content,
                        file_name=file_name,
                        mime="text/markdown"
                    )
                    
                    # LLM 분석 기능
                    st.markdown("---")
                    st.subheader("🤖 LLM 분석")
                    
                    # 분석 범위 선택
                    analysis_scope = st.radio(
                        "분석 범위 선택",
                        ["현재 선택된 회의록", "전체 회의록 (기간별 가져온 모든 회의록)"],
                        help="분석할 회의록의 범위를 선택하세요"
                    )
                    
                    # LLM 선택
                    llm_client = LLMClient()
                    available_providers = llm_client.get_available_providers()
                    
                    if available_providers:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            selected_provider = st.selectbox(
                                "🤖 LLM 제공자 선택",
                                available_providers,
                                help="분석에 사용할 LLM 제공자를 선택하세요"
                            )
                        
                        with col2:
                            available_models = llm_client.get_models_for_provider(selected_provider)
                            if available_models:
                                selected_model = st.selectbox(
                                    "📋 모델 선택",
                                    available_models,
                                    help="사용할 모델을 선택하세요"
                                )
                            else:
                                selected_model = None
                                st.warning(f"{selected_provider}에서 사용 가능한 모델이 없습니다.")
                    else:
                        st.error("❌ 사용 가능한 LLM 제공자가 없습니다. API 키를 확인해주세요.")
                        selected_provider = "openai"
                        selected_model = "gpt-4o-mini"
                    
                    # 참고 프롬프트 입력
                    reference_prompt = st.text_area(
                        "📝 LLM 분석 시 참고할 프롬프트",
                        placeholder="예시:\n- 특정 키워드나 주제에 집중해서 분석해주세요\n- 특정 참석자의 발언을 중점적으로 살펴보세요\n- 특정 기간의 진행 상황을 추적해주세요\n- 특정 프로젝트나 이슈에 대한 논의를 찾아주세요",
                        help="LLM이 분석할 때 반드시 참고할 내용을 입력하세요. 비워두면 일반적인 분석을 수행합니다.",
                        height=100
                    )
                    
                    # 분석 옵션
                    analysis_type = st.selectbox(
                        "분석 유형 선택",
                        [
                            "회의록 요약",
                            "주요 논의 사항 추출",
                            "액션 아이템 추출",
                            "결정 사항 정리",
                            "참석자별 역할 분석",
                            "사업 Ideation",
                            "사업 전략",
                            "전체 분석 리포트"
                        ],
                        help="원하는 분석 유형을 선택하세요"
                    )
                    
                    if st.button("🔍 LLM 분석 시작", type="primary"):
                        with st.spinner("LLM이 분석 중입니다..."):
                            if analysis_scope == "현재 선택된 회의록":
                                # 현재 선택된 회의록만 분석
                                analysis_result = analyze_with_llm(content, analysis_type, False, reference_prompt, selected_provider, selected_model)
                                file_name = f"{selected_meeting}_분석결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            else:
                                # 전체 회의록 분석
                                all_contents = get_all_meeting_contents(df, api_key)
                                if all_contents:
                                    analysis_result = analyze_with_llm(all_contents, analysis_type, True, reference_prompt, selected_provider, selected_model)
                                    file_name = f"전체회의록_분석결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                                else:
                                    analysis_result = "❌ 분석할 회의록 내용을 찾을 수 없습니다."
                                    file_name = ""
                            
                            if analysis_result and not analysis_result.startswith("❌"):
                                st.markdown("### 📊 분석 결과")
                                st.markdown(analysis_result)
                                
                                # 분석 결과 다운로드
                                if file_name:
                                    st.download_button(
                                        label="📄 분석 결과 다운로드",
                                        data=analysis_result,
                                        file_name=file_name,
                                        mime="text/markdown"
                                    )
                            else:
                                st.error(analysis_result)
                    
                    # 원본 JSON 데이터 (디버깅용)
                    with st.expander("🔧 원본 데이터 보기"):
                        st.json(blocks)
                        
                    # 블록 타입별 상세 정보
                    with st.expander("🔍 블록 타입별 상세 정보"):
                        for i, block in enumerate(blocks):
                            block_type = block.get("type", "unknown")
                            st.write(f"**블록 {i+1}**: {block_type}")
                            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
                                rich_text = block.get(block_type, {}).get("rich_text", [])
                                if rich_text:
                                    text = "".join([rt.get("plain_text", "") for rt in rich_text])
                                    st.write(f"  내용: {text}")
                            st.write("---")
                else:
                    # 디버깅을 위해 원본 데이터 표시
                    with st.expander("🔧 디버깅: 원본 블록 데이터"):
                        st.json(blocks)
            else:
                # 페이지 정보 확인
                page_info = get_notion_page_content(page_id, api_key)
                if page_info:
                    with st.expander("🔧 페이지 정보"):
                        st.json(page_info)

def analyze_with_llm(content: str, analysis_type: str, is_multiple_meetings: bool = False, reference_prompt: str = "", provider: str = "openai", model: str = None) -> str:
    """LLM을 사용하여 회의록을 분석합니다."""
    try:
        # LLMClient 인스턴스 생성
        llm_client = LLMClient()
        
        # 사용 가능한 제공자 확인
        available_providers = llm_client.get_available_providers()
        if not available_providers:
            return "❌ 사용 가능한 LLM 제공자가 없습니다. API 키를 확인해주세요."
        
        # 제공자가 설정되지 않은 경우 첫 번째 사용 가능한 제공자 사용
        if provider not in available_providers:
            provider = available_providers[0]
        
        # 모델이 설정되지 않은 경우 기본 모델 사용
        if not model:
            available_models = llm_client.get_models_for_provider(provider)
            if available_models:
                model = available_models[0]
            else:
                return f"❌ {provider}에서 사용 가능한 모델이 없습니다."
        
        # 분석 프롬프트 생성
        if is_multiple_meetings:
            prompts = {
                "회의록 요약": "다음 여러 회의록들을 종합적으로 요약해주세요. 각 회의의 주요 내용과 전체적인 흐름을 정리해주세요.",
                "주요 논의 사항 추출": "다음 여러 회의록들에서 주요 논의 사항들을 추출해주세요. 공통 주제와 각 회의별 특이사항을 구분해서 정리해주세요.",
                "액션 아이템 추출": "다음 여러 회의록들에서 액션 아이템들을 추출해주세요. 담당자와 기한이 있다면 함께 표시하고, 우선순위를 정해주세요.",
                "결정 사항 정리": "다음 여러 회의록들에서 결정된 사항들을 정리해주세요. 각 결정 사항의 배경과 진행 상황을 포함해주세요.",
                "참석자별 역할 분석": "다음 여러 회의록들에서 참석자들의 역할과 기여도를 종합적으로 분석해주세요. 각자의 책임과 역할 변화를 정리해주세요.",
                "사업 Ideation": "다음 여러 회의록들을 분석하여 새로운 사업 아이디어를 도출해주세요. 시장 기회, 고객 니즈, 기술 트렌드, 경쟁 환경을 고려하여 혁신적이고 실행 가능한 사업 아이디어를 제시해주세요. 각 아이디어에 대해 시장성, 수익성, 실행 가능성을 평가해주세요.",
                "사업 전략": "다음 여러 회의록들을 분석하여 사업 전략을 도출해주세요. 현재 상황 분석, 목표 설정, 핵심 전략, 실행 계획, 리스크 관리 등을 포함한 종합적인 사업 전략을 제시해주세요.",
                "전체 분석 리포트": "다음 여러 회의록들을 종합적으로 분석해주세요. 전체적인 요약, 주요 논의 사항, 액션 아이템, 결정 사항, 참석자 역할을 모두 포함한 종합 리포트를 작성해주세요."
            }
        else:
            prompts = {
                "회의록 요약": "다음 회의록을 간결하게 요약해주세요. 주요 내용을 3-4개의 핵심 포인트로 정리해주세요.",
                "주요 논의 사항 추출": "다음 회의록에서 주요 논의 사항들을 추출해주세요. 각 항목을 명확하게 구분해서 정리해주세요.",
                "액션 아이템 추출": "다음 회의록에서 액션 아이템(해야 할 일)들을 추출해주세요. 담당자와 기한이 있다면 함께 표시해주세요.",
                "결정 사항 정리": "다음 회의록에서 결정된 사항들을 정리해주세요. 각 결정 사항의 배경과 이유도 포함해주세요.",
                "참석자별 역할 분석": "다음 회의록에서 참석자들의 역할과 기여도를 분석해주세요. 각자의 책임과 역할을 정리해주세요.",
                "사업 Ideation": "다음 회의록을 분석하여 새로운 사업 아이디어를 도출해주세요. 시장 기회, 고객 니즈, 기술 트렌드, 경쟁 환경을 고려하여 혁신적이고 실행 가능한 사업 아이디어를 제시해주세요. 각 아이디어에 대해 시장성, 수익성, 실행 가능성을 평가해주세요.",
                "사업 전략": "다음 회의록을 분석하여 사업 전략을 도출해주세요. 현재 상황 분석, 목표 설정, 핵심 전략, 실행 계획, 리스크 관리 등을 포함한 종합적인 사업 전략을 제시해주세요.",
                "전체 분석 리포트": "다음 회의록을 종합적으로 분석해주세요. 요약, 주요 논의 사항, 액션 아이템, 결정 사항, 참석자 역할을 모두 포함한 리포트를 작성해주세요."
            }
        
        prompt = prompts.get(analysis_type, "다음 회의록을 분석해주세요.")
        
        # 참고 프롬프트가 있으면 추가
        if reference_prompt.strip():
            prompt += f"\n\n[참고사항]\n{reference_prompt}\n\n위 참고사항을 반드시 고려하여 분석해주세요."
        
        # 메시지 구성
        messages = [
            {"role": "system", "content": "당신은 회의록 분석 전문가입니다. 주어진 회의록을 체계적으로 분석하고 명확하게 정리해주세요."},
            {"role": "user", "content": f"{prompt}\n\n회의록 내용:\n{content}"}
        ]
        
        # LLM 호출
        response, error = llm_client.generate_response(
            provider=provider,
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=3000 if is_multiple_meetings else 2000
        )
        
        if error:
            return f"❌ LLM 분석 중 오류가 발생했습니다: {error}"
        
        return response
        
    except Exception as e:
        return f"❌ LLM 분석 중 오류가 발생했습니다: {str(e)}"

def get_all_meeting_contents(df: pd.DataFrame, api_key: str) -> str:
    """모든 회의록의 내용을 가져와서 하나의 텍스트로 합칩니다."""
    if df.empty:
        return ""
    
    # 회의록 항목들만 필터링 (이름이 있는 항목들)
    meeting_items = df[df['이름'].notna() & (df['이름'] != '')]
    
    if meeting_items.empty:
        return ""
    
    all_contents = []
    
    for idx, row in meeting_items.iterrows():
        page_id = row['page_id']
        meeting_name = row['이름']
        created_date = row['created_time'][:10] if row['created_time'] else "날짜 없음"
        
        try:
            blocks = get_notion_page_blocks(page_id, api_key)
            if blocks:
                content = parse_notion_blocks(blocks, api_key)
                if content.strip():
                    all_contents.append(f"=== {meeting_name} ({created_date}) ===\n{content}\n")
        except Exception as e:
            # 오류가 발생해도 계속 진행
            continue
    
    return "\n\n".join(all_contents)

# 메인 앱
def main():
  
    st.markdown("---")
    
    # 세션 상태 초기화
    if 'notion_data' not in st.session_state:
        st.session_state.notion_data = None
    if 'selected_meeting' not in st.session_state:
        st.session_state.selected_meeting = None
    if 'meeting_content' not in st.session_state:
        st.session_state.meeting_content = None
    
    # API 키와 데이터베이스 ID 확인
    if not NOTION_API_KEY:
        return
    
    # API 연결 테스트
    if st.button("🔗 API 연결 테스트", type="secondary"):
        with st.spinner("API 연결을 테스트하는 중..."):
            test_result = test_notion_connection(NOTION_API_KEY)
            
            if test_result["success"]:
                st.json(test_result["data"])
            else:
                pass
    
    if not FINAL_DATABASE_ID:
        return
    
    # 데이터 가져오기 설정
    st.subheader("🔍 통합 검색으로 데이터 가져오기")
    
    # 검색 조건 설정
    col1, col2 = st.columns(2)
    
    with col1:
        # 날짜 선택 옵션
        date_filter_option = st.selectbox(
            "날짜 필터 옵션",
            ["전체 기간", "특정 기간 선택", "최근 7일", "최근 30일", "최근 90일", "이번 달", "지난 달"],
            help="가져올 데이터의 기간을 선택하세요"
        )
        
        start_date = None
        end_date = None
        
        if date_filter_option == "특정 기간 선택":
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                start_date = st.date_input("시작일", value=None)
            with col1_2:
                end_date = st.date_input("종료일", value=None)
        elif date_filter_option == "최근 7일":
            from datetime import datetime, timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
        elif date_filter_option == "최근 30일":
            from datetime import datetime, timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        elif date_filter_option == "최근 90일":
            from datetime import datetime, timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=90)
        elif date_filter_option == "이번 달":
            from datetime import datetime
            now = datetime.now()
            start_date = now.replace(day=1).date()
            end_date = now.date()
        elif date_filter_option == "지난 달":
            from datetime import datetime, timedelta
            now = datetime.now()
            last_month = now.replace(day=1) - timedelta(days=1)
            start_date = last_month.replace(day=1).date()
            end_date = last_month.date()
    
    with col2:
        # 검색어 설정
        search_term = st.text_input("검색어", placeholder="제목에서 검색할 키워드를 입력하세요", help="기본적으로 제목에서만 검색합니다")
        
        # 전체 내용 검색 옵션
        search_full_content = st.checkbox(
            "전체 내용에서 검색 (느림)",
            help="체크하면 제목뿐만 아니라 회의 내용 전체에서도 검색합니다.",
            key="search_full_content_main"
        )
    
    # 선택된 조건 표시
    search_conditions = []
    if start_date or end_date:
        if start_date and end_date:
            search_conditions.append(f"날짜: {start_date} ~ {end_date}")
        elif start_date:
            search_conditions.append(f"날짜: {start_date} 이후")
        elif end_date:
            search_conditions.append(f"날짜: {end_date} 이전")
    else:
        search_conditions.append("날짜: 전체 기간")
    
    if search_term:
        search_scope = "제목 + 내용" if search_full_content else "제목만"
        search_conditions.append(f"검색어: '{search_term}' ({search_scope})")
    else:
        search_conditions.append("검색어: 없음")
    
    st.info("🔍 검색 조건: " + " AND ".join(search_conditions))
    st.info("⏰ Notion의 created_time은 UTC 시간이며, 한국 시간(KST)으로 변환하여 필터링합니다.")
    
    # 데이터 가져오기 버튼
    if st.button("🔄 데이터 가져오기", type="primary"):
        try:
            # 날짜를 ISO 형식으로 변환
            start_date_str = start_date.isoformat() if start_date else None
            end_date_str = end_date.isoformat() if end_date else None
            
            # 데이터 가져오기
            notion_data = get_notion_database(FINAL_DATABASE_ID, NOTION_API_KEY, start_date_str, end_date_str, search_term, search_full_content)
            
            if notion_data:
                # 데이터프레임 변환
                df = convert_to_dataframe(notion_data, start_date_str, end_date_str)
                    
                if not df.empty:
                    # Search API를 사용하므로 추가 필터링이 필요 없음
                    # (Search API가 이미 전체 내용에서 검색을 수행함)
                    st.session_state.notion_data = df
                    
                    # 검색 결과 요약
                    if search_term:
                        st.success(f"✅ 검색 결과: {len(df)}개 항목")
                    else:
                        st.success(f"✅ 데이터 가져오기 완료: {len(df)}개 항목")
                    
                    # 데이터 미리보기
                    st.subheader("📊 데이터 미리보기")
                    st.dataframe(df, use_container_width=True)
                    
                    # 데이터 통계
                    st.subheader("📈 데이터 통계")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("총 항목 수", len(df))
                    
                    with col2:
                        st.metric("컬럼 수", len(df.columns))
                    
                    with col3:
                        st.metric("데이터 크기", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
                    
                    # 회의록 상세 내용 표시
                    display_meeting_details(df, NOTION_API_KEY)
                    
                else:
                    st.warning("❌ 검색 결과가 없습니다.")
                    if search_term:
                        st.info(f"검색어 '{search_term}'에 대한 결과가 없습니다.")
            else:
                st.error("❌ API 응답이 없습니다. API 키와 Database ID를 확인해주세요.")
                    
        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {str(e)}")
    
    # 세션에 저장된 데이터가 있으면 표시
    elif st.session_state.notion_data is not None:
        df = st.session_state.notion_data
        
        # 새로운 데이터 가져오기 옵션
        st.subheader("🔄 새로운 데이터 가져오기")
        if st.button("📅 기간별 데이터 다시 가져오기", type="secondary"):
            st.session_state.notion_data = None
            st.rerun()
        
        # 기존 데이터 필터링
        st.subheader("📅 기존 데이터 필터링")
        
        # 날짜 필터 옵션
        filter_option = st.selectbox(
            "필터 옵션",
            ["전체 데이터", "날짜 범위로 필터링"],
            help="기존 데이터를 날짜 범위로 필터링할 수 있습니다"
        )
        
        if filter_option == "날짜 범위로 필터링":
            col1, col2 = st.columns(2)
            with col1:
                filter_start_date = st.date_input("필터 시작일", value=None)
            with col2:
                filter_end_date = st.date_input("필터 종료일", value=None)
            
            if filter_start_date or filter_end_date:
                try:
                    # created_time을 datetime으로 변환하고 한국 시간대(KST)로 변환
                    df['created_time_dt'] = pd.to_datetime(df['created_time']).dt.tz_convert('Asia/Seoul')
                except:
                    # 시간대 변환에 실패하면 UTC로 처리하고 9시간 추가 (KST = UTC+9)
                    df['created_time_dt'] = pd.to_datetime(df['created_time']) + pd.Timedelta(hours=9)
                
                if filter_start_date and filter_end_date:
                    # 날짜만 비교하도록 시간 정보 제거
                    mask = (df['created_time_dt'].dt.date >= filter_start_date) & (df['created_time_dt'].dt.date <= filter_end_date)
                elif filter_start_date:
                    mask = df['created_time_dt'].dt.date >= filter_start_date
                elif filter_end_date:
                    mask = df['created_time_dt'].dt.date <= filter_end_date
                else:
                    mask = pd.Series([True] * len(df), index=df.index)
                
                filtered_df = df[mask]
                st.info(f"📊 필터링 결과: {len(filtered_df)}개 항목 (전체 {len(df)}개 중)")
                df = filtered_df
            else:
                st.info("📊 전체 데이터 표시")
        
        # 데이터 미리보기
        st.subheader("📊 데이터 미리보기")
        st.dataframe(df, use_container_width=True)
        
        # 회의록 상세 내용 표시
        display_meeting_details(df, NOTION_API_KEY)
        
        # 데이터 통계
        st.subheader("📈 데이터 통계")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 항목 수", len(df))
        
        with col2:
            st.metric("컬럼 수", len(df.columns))
        
        with col3:
            st.metric("데이터 크기", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        

        
        

# 앱 실행
if __name__ == "__main__":
    main()
