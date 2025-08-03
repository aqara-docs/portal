import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import openai
import glob
import re
import io

# Google Drive API 관련 라이브러리
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import pickle
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    st.warning("Google Drive API 라이브러리가 설치되지 않았습니다. `pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client`를 실행하세요.")

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Google Meet 회의록 분석",
    page_icon="📝",
    layout="wide"
)
st.title("📝 Google Meet 회의록 데이터 분석")

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

# Google Drive API 설정
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_google_drive_service():
    """Google Drive API 서비스를 생성합니다."""
    if not GOOGLE_DRIVE_AVAILABLE:
        return None

    try:
        # 환경변수 로딩 확인
        from dotenv import load_dotenv
        load_dotenv()
        
        # 방법 1: 서비스 계정 키 사용 (권장 - 매번 인증 불필요)
        service_account_key = os.getenv('SERVICE_ACCOUNT_FILE')
        
        # 디버깅 정보
        st.info(f"🔍 환경변수 확인: SERVICE_ACCOUNT_FILE = {service_account_key}")
        
        # 파일 존재 확인 및 대안 파일 검색
        if service_account_key:
            st.info(f"📁 파일 존재 확인: {os.path.exists(service_account_key)}")
            
            # 지정된 파일이 없으면 대안 파일들 검색
            if not os.path.exists(service_account_key):
                st.info("🔍 대안 파일들을 검색합니다...")
                alternative_files = [
                    "/Users/aqaralife/Documents/GitHub/portal/credentials.json",
                    "/Users/aqaralife/Documents/GitHub/portal/service-account-key.json",
                    "/Users/aqaralife/Documents/GitHub/portal/google-service-account.json"
                ]
                
                for alt_file in alternative_files:
                    if os.path.exists(alt_file):
                        st.success(f"✅ 대안 파일을 찾았습니다: {alt_file}")
                        service_account_key = alt_file
                        break
                else:
                    st.error("❌ 서비스 계정 키 파일을 찾을 수 없습니다.")
                    st.info("💡 해결 방법:")
                    st.info("1. .env 파일에서 SERVICE_ACCOUNT_FILE 경로를 올바른 파일로 수정")
                    st.info("2. 또는 프로젝트 루트에 credentials.json 파일을 배치")
                    return None
            
            if os.path.exists(service_account_key):
                try:
                    from google.oauth2 import service_account
                    credentials = service_account.Credentials.from_service_account_file(
                        service_account_key, scopes=SCOPES)
                    service = build('drive', 'v3', credentials=credentials)
                    
                    # 서비스 계정 이메일 확인
                    try:
                        with open(service_account_key, 'r') as f:
                            import json
                            key_data = json.load(f)
                            client_email = key_data.get('client_email', '알 수 없음')
                            st.success(f"✅ 서비스 계정 키로 Google Drive API에 연결되었습니다. (파일: {os.path.basename(service_account_key)})")
                            st.info(f"📧 서비스 계정 이메일: {client_email}")
                            st.info("💡 폴더 접근이 안 되면 이 이메일로 폴더를 공유하세요!")
                    except Exception as e:
                        st.success(f"✅ 서비스 계정 키로 Google Drive API에 연결되었습니다. (파일: {os.path.basename(service_account_key)})")
                    
                    return service
                except Exception as e:
                    st.error(f"서비스 계정 키 인증 오류: {str(e)}")
                    st.info(f"파일 경로: {service_account_key}")
                    st.info("파일이 존재하고 올바른 JSON 형식인지 확인하세요.")
                    
                    # 파일 내용 확인 (첫 몇 줄만)
                    try:
                        with open(service_account_key, 'r') as f:
                            first_lines = f.readlines()[:3]
                            st.info("파일 내용 (첫 3줄):")
                            for line in first_lines:
                                st.code(line.strip())
                    except Exception as read_error:
                        st.error(f"파일 읽기 오류: {str(read_error)}")
                    
                    return None
            else:
                st.error(f"❌ 파일이 존재하지 않습니다: {service_account_key}")
                st.info("💡 해결 방법:")
                st.info("1. 파일 경로가 올바른지 확인")
                st.info("2. 파일이 실제로 존재하는지 확인")
                st.info("3. .env 파일에서 경로를 다시 확인")
                return None
        else:
            st.warning("⚠️ SERVICE_ACCOUNT_FILE 환경변수가 설정되지 않았습니다.")
            st.info("💡 해결 방법:")
            st.info("1. .env 파일에 SERVICE_ACCOUNT_FILE 경로 추가")
            st.info("2. 앱을 다시 시작")
            st.info("3. 환경변수가 올바르게 로드되었는지 확인")
            return None

        # 방법 2: OAuth Token (백업 옵션)
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists('credentials.json'):
                    st.warning("⚠️ 서비스 계정 키가 설정되지 않았습니다.")
                    st.info("💡 더 간단한 방법: 서비스 계정 키를 사용하세요")
                    st.info("1. Google Cloud Console에서 서비스 계정 생성")
                    st.info("2. JSON 키 파일 다운로드")
                    st.info("3. 환경변수 SERVICE_ACCOUNT_FILE에 파일 경로 설정")
                    st.info("4. .env 파일에 추가: SERVICE_ACCOUNT_FILE=/path/to/your/key.json")
                    
                    # OAuth를 사용할지 묻기
                    use_oauth = st.checkbox("OAuth 인증을 사용하시겠습니까? (매번 인증 필요)")
                    if not use_oauth:
                        st.info("서비스 계정 키 설정 후 앱을 다시 시작하세요.")
                        return None
                    
                    try:
                        # ngrok URL을 사용하는 OAuth 설정
                        from google_auth_oauthlib.flow import Flow
                        flow = Flow.from_client_secrets_file(
                            'credentials.json', 
                            SCOPES,
                            redirect_uri='https://aqaranewbiz.ngrok.app'
                        )
                        # Streamlit에서 OAuth 흐름 처리
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        st.info(f"🔗 다음 링크를 클릭하여 Google 계정에 로그인하세요: {auth_url}")
                        
                        # 사용자가 수동으로 인증 코드를 입력하도록 안내
                        auth_code = st.text_input("인증 코드를 입력하세요:", help="위 링크에서 인증 후 받은 코드를 입력하세요")
                        
                        if auth_code:
                            try:
                                flow.fetch_token(code=auth_code)
                                creds = flow.credentials
                            except Exception as e:
                                st.error(f"인증 코드 처리 오류: {str(e)}")
                                return None
                        else:
                            st.warning("인증 코드를 입력해주세요.")
                            return None
                            
                    except ValueError as e:
                        if "Client secrets must be for a web or installed app" in str(e):
                            st.error("❌ OAuth 클라이언트 타입 오류")
                            st.error("Google Cloud Console에서 OAuth 클라이언트 ID를 '웹 애플리케이션'으로 설정해야 합니다.")
                            st.info("해결 방법:")
                            st.info("1. Google Cloud Console → API 및 서비스 → 사용자 인증 정보")
                            st.info("2. OAuth 2.0 클라이언트 ID 선택")
                            st.info("3. 애플리케이션 유형을 '웹 애플리케이션'으로 변경")
                            st.info("4. 승인된 리디렉션 URI에 'https://aqaranewbiz.ngrok.app' 추가")
                            st.info("5. credentials.json 파일을 다시 다운로드")
                            return None
                        else:
                            st.error(f"OAuth 인증 오류: {str(e)}")
                            return None
                    except Exception as e:
                        st.error(f"Google Drive 인증 오류: {str(e)}")
                        return None
                else:
                    st.error("❌ Google Drive API 인증 파일이 필요합니다.")
                    st.info("서비스 계정 키 또는 credentials.json 파일을 설정하세요.")
                    return None
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
        try:
            service = build('drive', 'v3', credentials=creds)
            st.success("✅ OAuth로 Google Drive API에 연결되었습니다.")
            return service
        except Exception as e:
            st.error(f"Google Drive 서비스 생성 오류: {str(e)}")
            return None
    except Exception as e:
        st.error(f"Google Drive API 설정 오류: {str(e)}")
        return None

def find_meet_recordings_folder(service):
    """Google Drive에서 Meet Recordings 폴더를 찾습니다."""
    try:
        # 세션 상태로 폴더 검색 완료 여부 관리
        if 'folder_search_completed' in st.session_state and st.session_state.folder_search_completed:
            return st.session_state.selected_folder_info
        
        # 사용자가 직접 폴더 ID를 입력할 수 있는 옵션
        st.subheader("📁 Google Meet 폴더 설정")
        
        # 방법 1: 직접 폴더 ID 입력 (가장 확실한 방법)
        folder_id_input = st.text_input(
            "Google Meet 폴더 ID를 직접 입력하세요:",
            value="1ecLBd7jfwvO2VAGANtFX0rmmgS8o3bFi",
            help="Google Drive URL에서 폴더 ID를 복사하세요. 예: https://drive.google.com/drive/folders/1ecLBd7jfwvO2VAGANtFX0rmmgS8o3bFi",
            key=f"folder_id_input_{id(service)}"
        )
        
        if folder_id_input and folder_id_input.strip():
            try:
                # 폴더 ID로 직접 접근
                folder_info = service.files().get(fileId=folder_id_input.strip(), fields='id,name,permissions').execute()
                st.success(f"✅ 폴더를 찾았습니다: {folder_info['name']} (ID: {folder_info['id']})")
                folder_result = {'type': 'google_drive', 'folder_id': folder_info['id'], 'name': folder_info['name']}
                st.session_state.folder_search_completed = True
                st.session_state.selected_folder_info = folder_result
                return folder_result
            except Exception as e:
                st.error(f"❌ 폴더 ID 오류: {str(e)}")
                st.info("💡 해결 방법:")
                st.info("1. 폴더에 대한 접근 권한이 있는지 확인")
                st.info("2. 폴더 ID가 올바른지 확인")
                st.info("3. 서비스 계정이 폴더에 접근할 수 있는지 확인")
                st.info("4. 아래의 자동 검색을 사용해보세요")
        
        # 방법 2: 자동 검색 (백업)
        st.info("🔍 자동으로 폴더를 검색합니다...")
        
        # 먼저 사용자가 소유한 폴더들 검색
        st.info("사용자 소유 폴더에서 검색 중...")
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false and 'me' in owners"
        
        all_user_folders = []
        page_token = None
        
        while True:
            results = service.files().list(
                q=query, 
                spaces='drive', 
                fields='files(id, name), nextPageToken',
                pageSize=1000,
                pageToken=page_token
            ).execute()
            
            user_folders = results.get('files', [])
            all_user_folders.extend(user_folders)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        # Meet 관련 폴더 필터링
        meet_folders = []
        for folder in all_user_folders:
            name_lower = folder['name'].lower()
            if any(keyword in name_lower for keyword in ['meet', '녹화', 'recording', 'google']):
                meet_folders.append(folder)
        
        if meet_folders:
            st.success(f"✅ {len(meet_folders)}개의 Meet 관련 폴더를 찾았습니다:")
            for folder in meet_folders:
                st.info(f"  - {folder['name']} (ID: {folder['id']})")
            
            # 사용자가 선택할 수 있도록 폴더 목록 제공
            folder_options = [f"{folder['name']} (ID: {folder['id']})" for folder in meet_folders]
            selected_folder = st.selectbox(
                "사용할 폴더를 선택하세요:",
                folder_options,
                help="Google Meet 녹화 파일이 있는 폴더를 선택하세요",
                key=f"user_folder_select_{id(service)}"
            )
            
            if selected_folder:
                # 선택된 폴더에서 ID 추출
                folder_id = selected_folder.split("(ID: ")[1].split(")")[0]
                folder_name = selected_folder.split(" (ID: ")[0]
                st.success(f"✅ 선택된 폴더: {folder_name}")
                folder_result = {'type': 'google_drive', 'folder_id': folder_id, 'name': folder_name}
                st.session_state.folder_search_completed = True
                st.session_state.selected_folder_info = folder_result
                return folder_result
        
        # 방법 3: 공유된 폴더 검색
        st.info("공유된 폴더에서 검색 중...")
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false and sharedWithMe=true"
        
        all_shared_folders = []
        page_token = None
        
        while True:
            results = service.files().list(
                q=query, 
                spaces='drive', 
                fields='files(id, name), nextPageToken',
                pageSize=1000,
                pageToken=page_token
            ).execute()
            
            shared_folders = results.get('files', [])
            all_shared_folders.extend(shared_folders)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        meet_shared_folders = []
        for folder in all_shared_folders:
            name_lower = folder['name'].lower()
            if any(keyword in name_lower for keyword in ['meet', '녹화', 'recording', 'google']):
                meet_shared_folders.append(folder)
        
        if meet_shared_folders:
            st.success(f"✅ {len(meet_shared_folders)}개의 공유된 Meet 폴더를 찾았습니다:")
            for folder in meet_shared_folders:
                st.info(f"  - {folder['name']} (ID: {folder['id']})")
            
            folder_options = [f"{folder['name']} (ID: {folder['id']})" for folder in meet_shared_folders]
            selected_folder = st.selectbox(
                "사용할 공유 폴더를 선택하세요:",
                folder_options,
                help="Google Meet 녹화 파일이 있는 공유 폴더를 선택하세요",
                key=f"shared_folder_select_{id(service)}"
            )
            
            if selected_folder:
                folder_id = selected_folder.split("(ID: ")[1].split(")")[0]
                folder_name = selected_folder.split(" (ID: ")[0]
                st.success(f"✅ 선택된 폴더: {folder_name}")
                folder_result = {'type': 'google_drive', 'folder_id': folder_id, 'name': folder_name}
                st.session_state.folder_search_completed = True
                st.session_state.selected_folder_info = folder_result
                return folder_result
        
        # 방법 4: 모든 폴더에서 키워드 검색
        st.info("전체 폴더에서 키워드 검색 중...")
        keywords = ['meet', '녹화', 'recording', 'google meet', '미팅', '회의']
        
        for i, keyword in enumerate(keywords):
            query = f"name contains '{keyword}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            all_keyword_files = []
            page_token = None
            
            while True:
                results = service.files().list(
                    q=query, 
                    spaces='drive', 
                    fields='files(id, name), nextPageToken',
                    pageSize=1000,
                    pageToken=page_token
                ).execute()
                
                files = results.get('files', [])
                all_keyword_files.extend(files)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if all_keyword_files:
                st.info(f"키워드 '{keyword}'로 찾은 폴더들:")
                for file in all_keyword_files[:5]:  # 최대 5개만 표시
                    st.info(f"  - {file['name']} (ID: {file['id']})")
                
                # 사용자가 선택할 수 있도록 폴더 목록 제공
                folder_options = [f"{file['name']} (ID: {file['id']})" for file in all_keyword_files[:10]]
                if folder_options:
                    selected_folder = st.selectbox(
                        f"키워드 '{keyword}'로 찾은 폴더 중 선택하세요:",
                        folder_options,
                        help="Google Meet 녹화 파일이 있는 폴더를 선택하세요",
                        key=f"keyword_folder_select_{i}_{id(service)}"
                    )
                    
                    if selected_folder:
                        # 선택된 폴더에서 ID 추출
                        folder_id = selected_folder.split("(ID: ")[1].split(")")[0]
                        folder_name = selected_folder.split(" (ID: ")[0]
                        st.success(f"✅ 선택된 폴더: {folder_name}")
                        folder_result = {'type': 'google_drive', 'folder_id': folder_id, 'name': folder_name}
                        st.session_state.folder_search_completed = True
                        st.session_state.selected_folder_info = folder_result
                        return folder_result
        
        st.error("❌ Google Drive에서 Meet Recordings 폴더를 찾을 수 없습니다.")
        st.info("💡 해결 방법:")
        st.info("1. 폴더에 대한 접근 권한 확인")
        st.info("2. 서비스 계정에 폴더 공유 권한 부여")
        st.info("3. Google Meet에서 녹화를 생성했는지 확인")
        st.info("4. 폴더명이 다를 수 있으니 위의 선택 옵션에서 확인")
        return None
        
    except Exception as e:
        st.error(f"Google Drive 폴더 검색 오류: {str(e)}")
        return None

def list_files_in_folder(service, folder_id):
    """폴더 내의 파일들을 나열합니다."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, mimeType, createdTime, modifiedTime)',
            orderBy='createdTime desc'
        ).execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"파일 목록 가져오기 오류: {str(e)}")
        return []

def download_file_content(service, file_id):
    """파일의 내용을 다운로드합니다."""
    try:
        request = service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        return file.getvalue().decode('utf-8')
    except Exception as e:
        st.error(f"파일 다운로드 오류: {str(e)}")
        return None

def get_meet_recordings_folder():
    """Google Meet가 생성한 회의록 폴더 경로를 반환합니다."""
    # Google Drive API 사용 가능한 경우
    if GOOGLE_DRIVE_AVAILABLE:
        service = get_google_drive_service()
        if service:
            folder_info = find_meet_recordings_folder(service)
            if folder_info:
                return {"type": "google_drive", "folder_id": folder_info['folder_id'], "name": folder_info['name'], "service": service}
    
    # 로컬 파일 시스템 폴더 확인 (백업)
    possible_paths = [
        "Meet Recordings",
        "Meet 녹화",
        "Meet recordings",
        "Google Meet Recordings",
        "Meet_Recordings",
        "../Meet Recordings",
        "./Meet Recordings",
        os.path.expanduser("~/Meet Recordings"),
        os.path.expanduser("~/Google Drive/Meet Recordings"),
        os.path.expanduser("~/Documents/Meet Recordings")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return {"type": "local", "path": path, "name": os.path.basename(path)}
    
    return None

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

def read_meeting_file(file_path: str) -> Dict:
    """회의록 파일을 읽어서 구조화된 데이터로 반환합니다."""
    try:
        # 파일 확장자 확인
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 지원하는 파일 형식
        supported_extensions = ['.txt', '.md', '.markdown', '.docx', '.pdf', '.html', '.htm']
        
        if file_ext not in supported_extensions:
            st.warning(f"지원하지 않는 파일 형식입니다: {file_ext}")
            return None
        
        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 파일명에서 정보 추출
        filename = os.path.basename(file_path)
        
        # 파일 수정 시간
        file_stat = os.stat(file_path)
        modified_time = datetime.fromtimestamp(file_stat.st_mtime)
        
        # 파일명에서 날짜 추출 시도
        date_match = re.search(r'(\d{4})[-_](\d{1,2})[-_](\d{1,2})', filename)
        if date_match:
            year, month, day = date_match.groups()
            created_time = f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00Z"
        else:
            created_time = modified_time.isoformat() + "Z"
        
        # 마크다운 파일인 경우 특별 처리
        if file_ext in ['.md', '.markdown']:
            # 마크다운 헤더에서 제목 추출
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                display_name = title_match.group(1).strip()
            else:
                display_name = filename.replace('.md', '').replace('.markdown', '')
        else:
            display_name = filename.replace('.txt', '').replace('.md', '').replace('.markdown', '')
        
        return {
            "이름": display_name,
            "page_id": file_path,  # 파일 경로를 ID로 사용
            "created_time": created_time,
            "last_edited_time": modified_time.isoformat() + "Z",
            "content": content,
            "file_path": file_path,
            "file_type": file_ext
        }
        
    except Exception as e:
        st.error(f"파일 읽기 오류 ({file_path}): {str(e)}")
        return None

def read_google_drive_file(file_info: Dict, service) -> Dict:
    """Google Drive 파일의 내용을 읽습니다."""
    try:
        file_id = file_info['id']
        file_name = file_info['name']
        mime_type = file_info.get('mimeType', '')
        created_time = file_info.get('createdTime', '')
        modified_time = file_info.get('modifiedTime', '')
        
        content = ""
        
        # Google Docs 파일인지 확인
        if mime_type in [
            'application/vnd.google-apps.document',  # Google Docs
            'application/vnd.google-apps.spreadsheet',  # Google Sheets
            'application/vnd.google-apps.presentation',  # Google Slides
            'application/vnd.google-apps.drawing',  # Google Drawings
            'application/vnd.google-apps.form',  # Google Forms
        ]:
            # Google Docs 파일은 Export API 사용
            try:
                if mime_type == 'application/vnd.google-apps.document':
                    # Google Docs를 텍스트로 내보내기
                    response = service.files().export_media(
                        fileId=file_id,
                        mimeType='text/plain'
                    ).execute()
                    content = response.decode('utf-8')
                elif mime_type == 'application/vnd.google-apps.spreadsheet':
                    # Google Sheets를 CSV로 내보내기
                    response = service.files().export_media(
                        fileId=file_id,
                        mimeType='text/csv'
                    ).execute()
                    content = response.decode('utf-8')
                else:
                    # 기타 Google Apps 파일은 텍스트로 내보내기
                    response = service.files().export_media(
                        fileId=file_id,
                        mimeType='text/plain'
                    ).execute()
                    content = response.decode('utf-8')
                
            except Exception as e:
                st.error(f"Google Docs 파일 내보내기 오류: {str(e)}")
                content = f"[Google Docs 파일 - 읽을 수 없음: {file_name}]"
        
        else:
            # 일반 파일은 직접 다운로드
            try:
                response = service.files().get_media(fileId=file_id).execute()
                content = response.decode('utf-8')
                
            except Exception as e:
                st.error(f"파일 다운로드 오류: {str(e)}")
                content = f"[파일 읽기 오류: {file_name}]"
        
        # 마크다운 파일인 경우 특별 처리
        if file_name.lower().endswith(('.md', '.markdown')):
            # 마크다운 헤더에서 제목 추출
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                display_name = title_match.group(1).strip()
            else:
                display_name = file_name
        else:
            display_name = file_name
        
        return {
            '이름': display_name,
            'id': file_id,
            'content': content,
            'created_time': created_time,
            'last_edited_time': modified_time,
            'mime_type': mime_type
        }
        
    except Exception as e:
        st.error(f"파일 읽기 오류: {str(e)}")
        return None

def get_meeting_files(folder_info, start_date=None, end_date=None, search_term=None, search_full_content=True):
    """폴더에서 회의 파일들을 가져옵니다."""
    if not folder_info:
        return []
    
    try:
        if folder_info["type"] == "google_drive":
            service = folder_info["service"]
            folder_id = folder_info["folder_id"]
            
            # Google Drive에서 파일 목록 가져오기 (페이지네이션 지원)
            all_files = []
            page_token = None
            
            while True:
                query = f"'{folder_id}' in parents and trashed=false"
                results = service.files().list(
                    q=query, 
                    spaces='drive', 
                    fields='files(id, name, mimeType, createdTime, modifiedTime), nextPageToken',
                    pageSize=1000,  # 최대 1000개씩 가져오기
                    pageToken=page_token
                ).execute()
                
                files = results.get('files', [])
                all_files.extend(files)
                
                # 다음 페이지가 있는지 확인
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            st.info(f"📁 폴더에서 {len(all_files)}개의 파일을 찾았습니다.")
            
            meeting_files = []
            for file in all_files:
                # 파일 정보 읽기
                file_content = read_google_drive_file(file, service)
                if file_content and file_content.get('content', '').strip():
                    # 검색어 필터링
                    if search_term and search_term.strip():
                        file_name = file_content.get('이름', '').lower()
                        file_content_text = file_content.get('content', '').lower()
                        search_term_lower = search_term.lower()
                        
                        # 제목에서 검색
                        title_match = search_term_lower in file_name
                        
                        # 검색 범위에 따른 매칭 결정
                        if search_full_content:
                            # 전체 내용에서 검색 (제목 또는 내용)
                            content_match = search_term_lower in file_content_text
                            is_match = title_match or content_match
                        else:
                            # 제목에서만 검색
                            is_match = title_match
                        
                        # 검색 조건에 맞지 않으면 건너뛰기
                        if not is_match:
                            continue
                    
                    # 날짜 필터링
                    if start_date and end_date:
                        file_date = file_content.get('created_time', '')
                        if file_date:
                            try:
                                file_date_obj = datetime.fromisoformat(file_date.replace('Z', '+00:00'))
                                if start_date <= file_date_obj.date() <= end_date:
                                    meeting_files.append(file_content)
                            except:
                                meeting_files.append(file_content)
                    else:
                        meeting_files.append(file_content)
            
            st.success(f"✅ {len(meeting_files)}개의 회의 파일을 가져왔습니다.")
            return meeting_files
            
        elif folder_info["type"] == "local":
            folder_path = folder_info["path"]
            meeting_files = []
            
            # 지원하는 파일 확장자 (더 많은 형식 지원)
            extensions = [
                '*.txt', '*.md', '*.markdown',  # 텍스트 및 마크다운
                '*.docx', '*.doc',              # Word 문서
                '*.pdf',                        # PDF
                '*.html', '*.htm',              # HTML
                '*.rtf',                        # Rich Text Format
                '*.csv',                        # CSV 파일
                '*.json'                        # JSON 파일
            ]
            
            for ext in extensions:
                pattern = os.path.join(folder_path, ext)
                files = glob.glob(pattern)
                
                for file_path in files:
                    file_content = read_meeting_file(file_path)
                    if file_content:
                        # 검색어 필터링
                        if search_term and search_term.strip():
                            file_name = file_content.get('이름', '').lower()
                            file_content_text = file_content.get('content', '').lower()
                            search_term_lower = search_term.lower()
                            
                            # 제목에서 검색
                            title_match = search_term_lower in file_name
                            
                            # 검색 범위에 따른 매칭 결정
                            if search_full_content:
                                # 전체 내용에서 검색 (제목 또는 내용)
                                content_match = search_term_lower in file_content_text
                                is_match = title_match or content_match
                            else:
                                # 제목에서만 검색
                                is_match = title_match
                            
                            # 검색 조건에 맞지 않으면 건너뛰기
                            if not is_match:
                                continue
                        
                        # 날짜 필터링
                        if start_date and end_date:
                            file_date = file_content.get('created_time', '')
                            if file_date:
                                try:
                                    file_date_obj = datetime.fromisoformat(file_date.replace('Z', '+00:00'))
                                    if start_date <= file_date_obj.date() <= end_date:
                                        meeting_files.append(file_content)
                                except:
                                    meeting_files.append(file_content)
                        else:
                            meeting_files.append(file_content)
            
            return meeting_files
    
    except Exception as e:
        st.error(f"파일 가져오기 오류: {str(e)}")
        return []

def convert_to_dataframe(meetings: List[Dict]) -> pd.DataFrame:
    """회의록 데이터를 DataFrame으로 변환합니다."""
    if not meetings:
        return pd.DataFrame()
    
    data = []
    for meeting in meetings:
        if meeting and 'content' in meeting:
            data.append({
                '이름': meeting.get('이름', 'Unknown'),
                'id': meeting.get('id', ''),
                'content': meeting.get('content', ''),
                'created_time': meeting.get('created_time', ''),
                'last_edited_time': meeting.get('last_edited_time', ''),
                'mime_type': meeting.get('mime_type', ''),
                'file_path': meeting.get('file_path', 'Google Drive')
            })
    
    df = pd.DataFrame(data)
    
    # 날짜 컬럼 정렬을 위해 datetime으로 변환
    if 'created_time' in df.columns:
        df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
        df = df.sort_values('created_time', ascending=False)
    
    return df

def display_meeting_details(df: pd.DataFrame):
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
        # 선택된 회의록의 데이터 찾기
        selected_row = meeting_items[meeting_items['이름'] == selected_meeting].iloc[0]
        content = selected_row['content']
        
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
- **파일 경로**: {selected_row['file_path']}

## 회의록 내용

{content}

---
*이 문서는 Google Meet 회의록에서 자동으로 생성되었습니다.*
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
                        all_contents = get_all_meeting_contents(df)
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
        else:
            st.warning("❌ 회의록 내용이 비어있습니다.")

def chunk_text(text: str, max_tokens: int = 80000) -> List[str]:
    """텍스트를 토큰 수에 따라 청크로 나눕니다."""
    # 더 보수적인 토큰 추정 (영어 기준 약 3글자 = 1토큰, 한글 기준 약 1.5글자 = 1토큰)
    def estimate_tokens(text: str) -> int:
        english_chars = sum(1 for c in text if ord(c) < 128)
        korean_chars = len(text) - english_chars
        return english_chars // 3 + int(korean_chars // 1.5)
    
    if estimate_tokens(text) <= max_tokens:
        return [text]
    
    # 텍스트를 문단 단위로 분할
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        test_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
        if estimate_tokens(test_chunk) <= max_tokens:
            current_chunk = test_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

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
        
        # 전체 회의록 분석인 경우 각 회의록을 개별 정리 후 종합
        if is_multiple_meetings:
            st.info("📋 전체 회의록 분석: 각 회의록을 개별 정리 후 종합 분석합니다...")
            
            # 회의록들을 개별적으로 분리 (=== 구분자 기준)
            meeting_sections = content.split("===")
            meeting_summaries = []
            
            for i, section in enumerate(meeting_sections):
                if not section.strip():
                    continue
                
                # 회의록 제목과 내용 분리
                lines = section.strip().split('\n', 1)
                if len(lines) < 2:
                    continue
                
                meeting_title = lines[0].strip()
                meeting_content = lines[1].strip()
                
                if not meeting_content:
                    continue
                
                st.info(f"📄 회의록 {i}/{len(meeting_sections)-1} 분석 중: {meeting_title[:50]}...")
                
                # 각 회의록을 간단히 요약
                summary_prompt = f"다음 회의록을 간결하게 요약해주세요. 주요 내용을 2-3개의 핵심 포인트로 정리해주세요.\n\n회의록: {meeting_title}\n내용:\n{meeting_content}"
                
                messages = [
                    {"role": "system", "content": "회의록 분석 전문가입니다."},
                    {"role": "user", "content": summary_prompt}
                ]
                
                response, error = llm_client.generate_response(
                    provider=provider,
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1000
                )
                
                if error:
                    return f"❌ 회의록 {i} 분석 중 오류가 발생했습니다: {error}"
                
                meeting_summaries.append(f"=== {meeting_title} ===\n{response}")
            
            # 모든 회의록 요약을 종합
            combined_summaries = "\n\n".join(meeting_summaries)
            
            # 종합 분석 요청
            st.info("🔄 전체 회의록 종합 분석 중...")
            
            final_prompt = f"{prompt}\n\n다음은 여러 회의록들의 요약입니다:\n\n{combined_summaries}"
            
            messages = [
                {"role": "system", "content": "당신은 회의록 분석 전문가입니다. 여러 회의록의 요약을 종합하여 체계적으로 분석해주세요."},
                {"role": "user", "content": final_prompt}
            ]
            
            final_response, error = llm_client.generate_response(
                provider=provider,
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=3000
            )
            
            if error:
                return f"❌ 종합 분석 중 오류가 발생했습니다: {error}"
            
            return final_response
        
        else:
            # 단일 회의록 분석 (기존 로직)
            # 텍스트를 청크로 분할 (프롬프트 길이를 고려하여 더 작게 설정)
            chunks = chunk_text(content, max_tokens=60000)
            
            if len(chunks) == 1:
                # 단일 청크인 경우 일반 처리
                messages = [
                    {"role": "system", "content": "당신은 회의록 분석 전문가입니다. 주어진 회의록을 체계적으로 분석하고 명확하게 정리해주세요."},
                    {"role": "user", "content": f"{prompt}\n\n회의록 내용:\n{content}"}
                ]
                
                response, error = llm_client.generate_response(
                    provider=provider,
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )
                
                if error:
                    return f"❌ LLM 분석 중 오류가 발생했습니다: {error}"
                
                return response
            else:
                # 여러 청크인 경우 각 청크를 개별 분석 후 종합
                st.info(f"📝 긴 텍스트를 {len(chunks)}개 청크로 나누어 분석합니다...")
                
                chunk_analyses = []
                for i, chunk in enumerate(chunks):
                    st.info(f"📄 청크 {i+1}/{len(chunks)} 분석 중...")
                    
                    # 청크별 분석을 위한 간단한 프롬프트
                    chunk_prompt = f"다음 회의록 부분을 분석해주세요: {analysis_type}"
                    
                    messages = [
                        {"role": "system", "content": "회의록 분석 전문가입니다."},
                        {"role": "user", "content": f"{chunk_prompt}\n\n{chunk}"}
                    ]
                    
                    response, error = llm_client.generate_response(
                        provider=provider,
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=1500
                    )
                    
                    if error:
                        return f"❌ 청크 {i+1} 분석 중 오류가 발생했습니다: {error}"
                    
                    chunk_analyses.append(response)
                
                # 모든 청크 분석 결과를 종합
                combined_analysis = "\n\n".join(chunk_analyses)
                
                # 종합 분석 요청
                st.info("🔄 분석 결과를 종합합니다...")
                
                summary_messages = [
                    {"role": "system", "content": "당신은 회의록 분석 전문가입니다. 여러 부분의 분석 결과를 종합하여 일관성 있는 최종 분석을 제공해주세요."},
                    {"role": "user", "content": f"다음은 긴 회의록을 여러 부분으로 나누어 분석한 결과입니다. 이를 종합하여 {analysis_type}에 맞는 최종 분석을 제공해주세요:\n\n{combined_analysis}"}
                ]
                
                final_response, error = llm_client.generate_response(
                    provider=provider,
                    model=model,
                    messages=summary_messages,
                    temperature=0.3,
                    max_tokens=2000
                )
                
                if error:
                    return f"❌ 종합 분석 중 오류가 발생했습니다: {error}"
                
                return final_response
        
    except Exception as e:
        return f"❌ LLM 분석 중 오류가 발생했습니다: {str(e)}"

def get_all_meeting_contents(df: pd.DataFrame) -> str:
    """모든 회의록의 내용을 가져와서 하나의 텍스트로 합칩니다."""
    if df.empty:
        return ""
    
    # 회의록 항목들만 필터링 (이름이 있는 항목들)
    meeting_items = df[df['이름'].notna() & (df['이름'] != '')]
    
    if meeting_items.empty:
        return ""
    
    all_contents = []
    
    for idx, row in meeting_items.iterrows():
        meeting_name = row['이름']
        
        # created_time이 Timestamp 객체인 경우를 처리
        if pd.notna(row['created_time']):
            if isinstance(row['created_time'], str):
                created_date = row['created_time'][:10]
            else:
                # Timestamp 객체인 경우
                created_date = row['created_time'].strftime('%Y-%m-%d')
        else:
            created_date = "날짜 없음"
        
        content = row['content']
        
        if content.strip():
            all_contents.append(f"=== {meeting_name} ({created_date}) ===\n{content}\n")
    
    return "\n\n".join(all_contents)

# 메인 앱
def main():
    st.markdown("---")
    
    # 세션 상태 초기화
    if 'meetings' not in st.session_state:
        st.session_state.meetings = None
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'folder_search_completed' not in st.session_state:
        st.session_state.folder_search_completed = False
    if 'selected_folder_info' not in st.session_state:
        st.session_state.selected_folder_info = None
    
    # Meet_Recordings 폴더 경로 확인
    folder_info = get_meet_recordings_folder()
    
    if not folder_info:
        st.error("❌ Google Meet 회의록 폴더를 찾을 수 없습니다.")
        st.info("Google Meet의 AI 요약 기능이 생성한 폴더가 있는지 확인해주세요:")
        st.info("- Meet Recordings")
        st.info("- Meet 녹화")
        st.info("- Meet recordings")
        st.info("- Google Meet Recordings")
        return
    
    st.success(f"✅ Google Meet 회의록 폴더 발견: {folder_info['name']}")
    
    # Google Drive API 설정 안내
    if folder_info['type'] == 'google_drive':
        st.info("🔐 Google Drive API가 설정되어 있습니다.")
    else:
        st.info("📁 로컬 파일 시스템을 사용합니다.")
        if GOOGLE_DRIVE_AVAILABLE:
            st.info("💡 Google Drive를 사용하려면 다음 단계를 따르세요:")
            st.info("1. Google Cloud Console에서 프로젝트 생성")
            st.info("2. Google Drive API 활성화")
            st.info("3. OAuth 2.0 클라이언트 ID 생성")
            st.info("4. credentials.json 파일 다운로드하여 프로젝트 루트에 저장")
        else:
            st.warning("⚠️ Google Drive API 라이브러리가 설치되지 않았습니다.")
            st.info("다음 명령어로 설치하세요:")
            st.code("pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    
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
        # 검색어 입력
        search_term = st.text_input(
            "검색어 입력 (선택사항)",
            placeholder="회의 제목이나 내용에서 검색",
            help="회의 제목이나 내용에서 특정 키워드를 검색합니다"
        )
        
        # 전체 내용 검색 옵션
        search_full_content = st.checkbox(
            "전체 내용에서 검색",
            value=False,
            help="체크하면 회의 내용 전체에서 검색합니다"
        )
    
    # 검색 조건 표시
    search_conditions = []
    if start_date and end_date:
        search_conditions.append(f"기간: {start_date} ~ {end_date}")
    elif start_date:
        search_conditions.append(f"시작일: {start_date}")
    elif end_date:
        search_conditions.append(f"종료일: {end_date}")
    else:
        search_conditions.append("전체 기간")
    
    if search_term:
        search_scope = "제목 + 내용" if search_full_content else "제목만"
        search_conditions.append(f"검색어: '{search_term}' ({search_scope})")
    
    st.info("🔍 검색 조건: " + " AND ".join(search_conditions))
    
    # 데이터 가져오기
    if st.button("📥 데이터 가져오기", type="primary"):
        # 폴더 검색 완료 상태 초기화
        st.session_state.folder_search_completed = False
        st.session_state.selected_folder_info = None
        
        with st.spinner("Google Meet 폴더를 찾는 중..."):
            folder_info = get_meet_recordings_folder()
            
        if folder_info:
            st.success(f"✅ 폴더를 찾았습니다: {folder_info.get('name', 'Unknown')}")
            
            with st.spinner("회의 파일을 가져오는 중..."):
                meetings = get_meeting_files(folder_info, start_date, end_date, search_term, search_full_content)
                
            if meetings:
                st.session_state.meetings = meetings
                st.session_state.df = convert_to_dataframe(meetings)
                st.success(f"✅ {len(meetings)}개의 회의 파일을 가져왔습니다.")
                st.rerun()
            else:
                st.warning("선택한 조건에 맞는 회의 파일을 찾을 수 없습니다.")
        else:
            st.error("Google Meet 폴더를 찾을 수 없습니다.")
            st.info("💡 해결 방법:")
            st.info("1. Google Meet에서 녹화를 생성했는지 확인")
            st.info("2. Google Drive에서 'Meet Recordings' 폴더가 있는지 확인")
            st.info("3. 위의 폴더 선택 옵션에서 올바른 폴더를 선택했는지 확인")
    
    # 세션에 저장된 데이터가 있으면 표시
    if 'meetings' in st.session_state and st.session_state.meetings:
        st.subheader("📊 가져온 데이터")
        
        df = st.session_state.df
        st.dataframe(df[['이름', 'created_time', 'last_edited_time']], use_container_width=True)
        
        # 데이터 통계
        st.subheader("📈 데이터 통계")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 항목 수", len(df))
        
        with col2:
            st.metric("컬럼 수", len(df.columns))
        
        with col3:
            total_size = sum(len(str(content)) for content in df['content'])
            st.metric("데이터 크기", f"{total_size / 1024:.1f} KB")
        
        # 회의록 상세 내용 및 LLM 분석 기능
        display_meeting_details(df)

# 앱 실행
if __name__ == "__main__":
    main() 