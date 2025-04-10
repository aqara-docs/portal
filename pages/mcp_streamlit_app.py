import streamlit as st
import requests
import asyncio
import json
import os
import sys
import subprocess
import time
from datetime import datetime
import threading
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Load environment variables
load_dotenv()

# Get API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# MCP 서버 프로세스 저장
if 'mcp_server_process' not in st.session_state:
    st.session_state.mcp_server_process = None
    st.session_state.mcp_server_logs = []

# Function to start the MCP server
def start_mcp_server(server_type, port):
    if st.session_state.mcp_server_process is not None:
        st.warning("이미 MCP 서버가 실행 중입니다. 새 서버를 시작하기 전에 중지하세요.")
        return False, "MCP server is already running"
    
    try:
        # Python 실행 경로
        python_executable = sys.executable
        
        # 서버 유형에 따른 스크립트 선택
        if server_type == "mysql":
            script_path = os.path.join(os.path.dirname(__file__), "mcp_mysql_server.py")
            
            # 스크립트가 없으면 생성
            if not os.path.exists(script_path):
                with open(script_path, "w") as f:
                    f.write("""
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import mysql.connector
from mysql.connector import Error

# 기본 포트 설정
PORT = 3000

# 커맨드 라인에서 포트 받기
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])

# MySQL 연결 설정
default_config = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": ""
}

class MCPHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
    
    def _handle_error(self, status, message):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
    
    def do_GET(self):
        if self.path == "/status":
            self._set_headers()
            status = {
                "status": "running",
                "type": "mysql",
                "tools": ["mysql_query"]
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self._handle_error(404, "Not found")
    
    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            if "tool" not in request or "parameters" not in request:
                return self._handle_error(400, "Missing tool or parameters")
            
            tool = request["tool"]
            params = request["parameters"]
            
            if tool == "mysql_query":
                return self.execute_mysql_query(params)
            else:
                return self._handle_error(400, f"Unknown tool: {tool}")
        else:
            self._handle_error(404, "Not found")
    
    def execute_mysql_query(self, params):
        if "query" not in params:
            return self._handle_error(400, "Missing query parameter")
        
        query = params["query"]
        db_config = params.get("db_config", default_config)
        
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            
            try:
                # SELECT 쿼리 결과 가져오기
                results = cursor.fetchall()
                # 결과 리스트가 비어있으면 다른 유형의 쿼리로 간주
                if not results:
                    conn.commit()
                    results = {"affectedRows": cursor.rowcount}
            except Error:
                # SELECT가 아닌 쿼리 (INSERT, UPDATE 등) 처리
                conn.commit()
                results = {"affectedRows": cursor.rowcount}
            
            cursor.close()
            conn.close()
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": results}).encode())
        except Error as e:
            self._handle_error(500, str(e))

def run_server(port):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MCPHandler)
    print(f"MySQL MCP server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = PORT
    run_server(port)
""")
                    
        elif server_type == "perplexity":
            script_path = os.path.join(os.path.dirname(__file__), "mcp_perplexity_server.py")
            
            # 스크립트가 없으면 생성
            if not os.path.exists(script_path):
                with open(script_path, "w") as f:
                    f.write("""
import sys
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 기본 포트 설정
PORT = 3001

# 커맨드 라인에서 포트 받기
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])

# API 키 설정
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

class MCPHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
    
    def _handle_error(self, status, message):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
    
    def do_GET(self):
        if self.path == "/status":
            self._set_headers()
            status = {
                "status": "running",
                "type": "perplexity",
                "tools": ["search"]
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self._handle_error(404, "Not found")
    
    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            if "tool" not in request or "parameters" not in request:
                return self._handle_error(400, "Missing tool or parameters")
            
            tool = request["tool"]
            params = request["parameters"]
            
            if tool == "search":
                return self.execute_perplexity_search(params)
            else:
                return self._handle_error(400, f"Unknown tool: {tool}")
        else:
            self._handle_error(404, "Not found")
    
    def execute_perplexity_search(self, params):
        if "query" not in params:
            return self._handle_error(400, "Missing query parameter")
        
        if not PERPLEXITY_API_KEY:
            return self._handle_error(500, "PERPLEXITY_API_KEY not set in environment")
        
        query = params["query"]
        
        try:
            # Perplexity API 호출
            headers = {
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{"role": "user", "content": query}]
            }
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                return self._handle_error(response.status_code, f"Perplexity API error: {response.text}")
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": response.json()}).encode())
        except Exception as e:
            self._handle_error(500, str(e))

def run_server(port):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MCPHandler)
    print(f"Perplexity MCP server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = PORT
    run_server(port)
""")
        elif server_type == "firecrawl":
            script_path = os.path.join(os.path.dirname(__file__), "mcp_firecrawl_server.py")
            
            # 스크립트가 없으면 생성
            if not os.path.exists(script_path):
                with open(script_path, "w") as f:
                    f.write("""
import sys
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 기본 포트 설정
PORT = 3002

# 커맨드 라인에서 포트 받기
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])

# API 키 설정
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

class MCPHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
    
    def _handle_error(self, status, message):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
    
    def do_GET(self):
        if self.path == "/status":
            self._set_headers()
            status = {
                "status": "running",
                "type": "firecrawl",
                "tools": ["search", "crawl"]
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self._handle_error(404, "Not found")
    
    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            if "tool" not in request or "parameters" not in request:
                return self._handle_error(400, "Missing tool or parameters")
            
            tool = request["tool"]
            params = request["parameters"]
            
            if tool == "search":
                return self.execute_firecrawl_search(params)
            elif tool == "crawl":
                return self.execute_firecrawl_crawl(params)
            else:
                return self._handle_error(400, f"Unknown tool: {tool}")
        else:
            self._handle_error(404, "Not found")
    
    def execute_firecrawl_search(self, params):
        if "query" not in params:
            return self._handle_error(400, "Missing query parameter")
        
        if not FIRECRAWL_API_KEY:
            return self._handle_error(500, "FIRECRAWL_API_KEY not set in environment")
        
        query = params["query"]
        
        try:
            # FireCrawl API 호출
            headers = {
                "x-api-key": FIRECRAWL_API_KEY,
                "Content-Type": "application/json"
            }
            
            data = {
                "query": query,
                "max_results": params.get("max_results", 10)
            }
            
            response = requests.post(
                "https://api.firecrawl.dev/search",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                return self._handle_error(response.status_code, f"FireCrawl API error: {response.text}")
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": response.json()}).encode())
        except Exception as e:
            self._handle_error(500, str(e))

    def execute_firecrawl_crawl(self, params):
        if "url" not in params:
            return self._handle_error(400, "Missing url parameter")
        
        if not FIRECRAWL_API_KEY:
            return self._handle_error(500, "FIRECRAWL_API_KEY not set in environment")
        
        url = params["url"]
        
        try:
            # FireCrawl API 호출
            headers = {
                "x-api-key": FIRECRAWL_API_KEY,
                "Content-Type": "application/json"
            }
            
            data = {
                "url": url,
                "include_links": params.get("include_links", False),
                "include_images": params.get("include_images", False)
            }
            
            response = requests.post(
                "https://api.firecrawl.dev/crawl",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                return self._handle_error(response.status_code, f"FireCrawl API error: {response.text}")
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": response.json()}).encode())
        except Exception as e:
            self._handle_error(500, str(e))

def run_server(port):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MCPHandler)
    print(f"FireCrawl MCP server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = PORT
    run_server(port)
""")
        else:
            return False, f"Unsupported server type: {server_type}"
        
        # 서버 프로세스 시작
        process = subprocess.Popen(
            [python_executable, script_path, str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        st.session_state.mcp_server_process = process
        
        # 로그 캡처 스레드 시작
        def capture_logs():
            while st.session_state.mcp_server_process:
                line = process.stdout.readline()
                if line:
                    st.session_state.mcp_server_logs.append(line.strip())
                    if len(st.session_state.mcp_server_logs) > 100:
                        st.session_state.mcp_server_logs.pop(0)
                else:
                    time.sleep(0.1)
        
        log_thread = threading.Thread(target=capture_logs)
        log_thread.daemon = True
        log_thread.start()
        
        # 서버 시작 대기
        for i in range(5):  # 최대 5초 대기
            try:
                # 서버 상태 확인
                response = requests.get(f"http://localhost:{port}/status", timeout=1)
                if response.status_code == 200:
                    return True, f"{server_type.upper()} MCP 서버가 포트 {port}에서 시작되었습니다."
            except:
                pass
            time.sleep(1)
        
        return True, f"{server_type.upper()} MCP 서버 시작 중입니다. 잠시 후 연결을 시도하세요."
        
    except Exception as e:
        return False, f"MCP 서버 시작 오류: {str(e)}"

# Function to stop the MCP server
def stop_mcp_server():
    if st.session_state.mcp_server_process is None:
        return False, "MCP 서버가 실행 중이 아닙니다."
    
    try:
        st.session_state.mcp_server_process.terminate()
        st.session_state.mcp_server_process = None
        return True, "MCP 서버가 중지되었습니다."
    except Exception as e:
        return False, f"MCP 서버 중지 오류: {str(e)}"

class SimpleMCPClient:
    """간단한 MCP 클라이언트 구현"""
    
    def __init__(self, server_url: str, server_type: str, db_config=None):
        # MCP 서버 기본 포트 설정
        if ":" not in server_url:
            if server_type == "mysql":
                server_url = f"{server_url}:3000"  # MySQL MCP 서버 기본 포트
            elif server_type == "perplexity":
                server_url = f"{server_url}:3001"  # Perplexity MCP 서버 기본 포트
            else:
                server_url = f"{server_url}:3002"  # FireCrawl MCP 서버 기본 포트
        
        self.server_url = server_url if server_url.startswith(("http://", "https://")) else f"http://{server_url}"
        self.server_type = server_type
        self.is_mcp_server = False
        self.mcp_server_command = None
        self.mcp_server_args = None
        self.mcp_server_type = None
        self.api_key = None
        
        # 서버 설정
        if server_type == "mysql":
            if db_config:
                self.db_config = db_config
            else:
                self.db_config = {
                    "host": "localhost",
                    "port": 3306,
                    "user": "root",
                    "password": ""
                }
    
    def get_server_info(self):
        """서버 정보 조회"""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                
            response = requests.get(
                f"{self.server_url}/status",
                headers=headers,
                timeout=5  # 5초 타임아웃 설정
            )
            if response.status_code == 200:
                server_info = response.json()
                # 서버에서 반환한 유형 정보가 있으면 업데이트
                if "type" in server_info:
                    self.server_type = server_info["type"]
                
                if self.server_type == "mysql":
                    server_info["db_config"] = {
                        "host": self.db_config["host"] if hasattr(self, 'db_config') and self.db_config else "localhost",
                        "port": self.db_config["port"] if hasattr(self, 'db_config') and self.db_config else 3306,
                        "user": self.db_config["user"] if hasattr(self, 'db_config') and self.db_config else "root"
                    }
                return server_info
            raise Exception(f"서버 상태 조회 실패: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"서버 연결 실패: {str(e)}")
    
    def execute_tool(self, tool_name: str, params: dict):
        """도구 실행"""
        if self.server_type == "mysql" and hasattr(self, 'db_config') and self.db_config:
            # MySQL 설정 추가
            params["db_config"] = self.db_config
        
        try:
            headers = {"Content-Type": "application/json"}
            
            # 서버 유형에 따라 적절한 인증 헤더 설정
            if self.api_key:
                if self.server_type == "firecrawl":
                    # FireCrawl은 Bearer 인증 사용
                    headers["Authorization"] = f"Bearer {self.api_key}"
                elif self.server_type == "perplexity":
                    # Perplexity도 Bearer 인증 사용
                    headers["Authorization"] = f"Bearer {self.api_key}"
                else:
                    # 기타 서버 유형
                    headers["Authorization"] = f"Bearer {self.api_key}"
            
            # 디버그 정보 출력
            print(f"서버 요청: {self.server_url}/execute")
            print(f"헤더: {headers}")
            print(f"요청 데이터: tool={tool_name}, params={params}")
                
            response = requests.post(
                f"{self.server_url}/execute",
                headers=headers,
                json={
                    "tool": tool_name,
                    "parameters": params
                },
                timeout=30  # 30초 타임아웃 설정
            )
            
            # 응답 디버그 정보
            print(f"응답 코드: {response.status_code}")
            if response.status_code != 200:
                print(f"응답 내용: {response.text}")
                
            if response.status_code == 200:
                return response.json()
            raise Exception(f"도구 실행 실패: {response.status_code}, {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"서버 요청 실패: {str(e)}")
    
    def close(self):
        """연결 종료"""
        pass  # HTTP 기반이므로 특별한 정리가 필요 없음

# Initialize session state for storing MCP configs
if 'mcp_configs' not in st.session_state:
    st.session_state.mcp_configs = {}

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Function to call Claude API
def call_claude_api(user_input, model="claude-3-5-sonnet-20240620"):
    API_URL = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": model,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": user_input}]
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        sql_query = response.json()["content"][0]["text"].strip()
        return sql_query
    except Exception as e:
        return None, f"Error calling Claude API: {str(e)}"

# Function to initialize MCP server from configuration
def initialize_mcp_server(config_data):
    try:
        # 디버깅: 설정 데이터 출력
        st.write("**설정 데이터 구조:**")
        st.json(config_data)
        
        # 연결 테스트 건너뛰기 옵션
        skip_connection_test = config_data.get("skipConnectionTest", False)
        
        # API 키 설정
        api_key = config_data.get("apiKey", None)
        
        # MySQL 설정 가져오기
        db_config = config_data.get("db_config", None)
        
        # MCP 서버 정보 추출
        is_mcp_server_config = False
        mcp_server_command = None
        mcp_server_args = None
        mcp_server_type = None
        
        # mcpServers 객체 감지 및 정보 추출
        if isinstance(config_data, dict) and "mcpServers" in config_data and config_data["mcpServers"]:
            is_mcp_server_config = True
            server_name = list(config_data["mcpServers"].keys())[0]
            server_config = config_data["mcpServers"][server_name]
            
            if "command" in server_config and "args" in server_config:
                mcp_server_command = server_config["command"]
                mcp_server_args = server_config["args"]
                
                # 인자에서 서버 유형 감지
                args_str = " ".join(str(arg) for arg in mcp_server_args)
                if "mcp-mysql-server" in args_str or "mysql" in args_str.lower():
                    mcp_server_type = "mysql"
                elif "mcp-perplexity-server" in args_str or "perplexity" in args_str.lower():
                    mcp_server_type = "perplexity"
                elif "mcp-firecrawl-server" in args_str or "firecrawl" in args_str.lower():
                    mcp_server_type = "firecrawl"
                
                # MCP 서버 관련 정보 표시
                st.info(f"### MCP 서버 설정 감지됨 (유형: {mcp_server_type or '감지 실패'})")
                st.code(f"서버 이름: {server_name}\n명령어: {mcp_server_command}\n인자: {' '.join(str(arg) for arg in mcp_server_args)}")
        
        # Extract server parameters from config
        server_url = None
        server_type = None
        
        # 다양한 설정 형식 처리
        if isinstance(config_data, str):
            # 문자열인 경우 URL로 간주
            server_url = config_data
            server_type = "mysql"  # 기본값
            st.info(f"설정이 문자열로 제공되었습니다. URL: {server_url}")
        elif isinstance(config_data, dict):
            # 딕셔너리 형태로 제공된 경우
            if "serverUrl" in config_data:
                server_url = config_data["serverUrl"]
                server_type = config_data.get("serverType", "mysql")  # 기본값은 mysql
                st.info(f"serverUrl 형식 발견: {server_url}")
            elif "url" in config_data:
                server_url = config_data["url"]
                server_type = config_data.get("type", "mysql")  # 기본값은 mysql
                st.info(f"url 형식 발견: {server_url}")
            elif "mcpServers" in config_data and config_data["mcpServers"]:
                # mcpServers에서 URL을 추출해야 함
                # 기본 포트 설정
                if mcp_server_type == "mysql":
                    server_url = "localhost:3000"
                elif mcp_server_type == "perplexity":
                    server_url = "localhost:3001"
                elif mcp_server_type == "firecrawl":
                    server_url = "localhost:3002"
                else:
                    server_url = "localhost:3000"  # 기본값
                
                # 서버 유형 설정 - mcp_server_type이 있으면 사용, 없으면 기본값
                server_type = mcp_server_type or "mysql"
                
                st.info(f"mcpServers 형식 발견: 기본 URL {server_url}로 설정됨, 서버 유형: {server_type}")
            elif "command" in config_data and "args" in config_data:
                # 스미서리 커맨드 형식
                st.info("command/args 형식 발견")
                
                # 인자에서 서버 유형 감지
                args_str = " ".join(str(arg) for arg in config_data.get("args", []))
                if "mcp-mysql-server" in args_str or "mysql" in args_str.lower():
                    server_type = "mysql"
                elif "mcp-perplexity-server" in args_str or "perplexity" in args_str.lower():
                    server_type = "perplexity"
                elif "mcp-firecrawl-server" in args_str or "firecrawl" in args_str.lower():
                    server_type = "firecrawl"
                else:
                    server_type = "mysql"  # 기본값
                
                server_url = f"localhost:{3000 if server_type=='mysql' else 3001 if server_type=='perplexity' else 3002}"
                
                # args에서 호스트/포트 추출 시도
                try:
                    args = config_data.get("args", [])
                    for arg in args:
                        if arg.startswith("--host="):
                            host = arg.split("=")[1]
                            server_url = f"{host}:{3000 if server_type=='mysql' else 3001 if server_type=='perplexity' else 3002}"
                        elif arg.startswith("--port="):
                            port = arg.split("=")[1]
                            if ":" in server_url:
                                host = server_url.split(":")[0]
                                server_url = f"{host}:{port}"
                            else:
                                server_url = f"{server_url}:{port}"
                    st.info(f"command/args에서 추출된 URL: {server_url}, 서버 유형: {server_type}")
                except Exception as e:
                    st.error(f"command/args 처리 중 오류: {str(e)}")
            else:
                st.warning("알려진 설정 형식을 찾을 수 없습니다. 설정 키:")
                st.write(list(config_data.keys()))
        else:
            st.error(f"지원되지 않는 설정 데이터 타입: {type(config_data)}")
        
        # 설정이 없는 경우, 기본값 사용
        if not server_url:
            st.warning("서버 URL을 찾을 수 없습니다. 기본값을 사용합니다.")
            server_url = "localhost:3000"
            server_type = "mysql"
        
        # URL 형식 확인 및 수정
        if not server_url.startswith(("http://", "https://")):
            # HTTP 프로토콜 추가
            if ":" in server_url:
                # 포트가 있는 경우
                host, port = server_url.split(":", 1)
                server_url = f"http://{host}:{port}"
            else:
                # 포트가 없는 경우
                if server_type == "mysql":
                    server_url = f"http://{server_url}:3000"
                elif server_type == "perplexity":
                    server_url = f"http://{server_url}:3001"
                elif server_type == "firecrawl":
                    server_url = f"http://{server_url}:3002"
            
            st.info(f"URL 형식 수정: {server_url}")
        
        # 클라이언트 생성
        st.info(f"서버에 연결 시도: {server_url}, 타입: {server_type}")
        client = SimpleMCPClient(server_url, server_type, db_config)
        
        # API 키가 있으면 설정
        if api_key:
            client.api_key = api_key
        
        # MCP 서버 설정 정보 저장
        if is_mcp_server_config:
            client.is_mcp_server = True
            client.mcp_server_command = mcp_server_command
            client.mcp_server_args = mcp_server_args
            client.mcp_server_type = mcp_server_type
        else:
            client.is_mcp_server = False
        
        # 연결 테스트 건너뛰기가 설정된 경우
        if skip_connection_test:
            st.warning("연결 테스트를 건너뛰고 설정만 저장합니다.")
            return client, f"Connection test skipped. Configuration saved for {server_url}"
        
        try:
            # 연결성 테스트 (타임아웃 3초)
            response = requests.get(f"{server_url}/status", timeout=3)
            st.success(f"서버 응답: HTTP {response.status_code}")
            
            # 정상 응답이 아닌 경우
            if response.status_code != 200:
                st.warning(f"서버가 비정상 응답을 반환했습니다: HTTP {response.status_code}")
                if st.button("그래도 계속하기"):
                    return client, f"서버가 비정상 응답을 반환했지만, 설정을 저장했습니다. ({server_url})"
                else:
                    raise Exception(f"서버가 비정상 응답을 반환했습니다: HTTP {response.status_code}")
            
            # 서버 정보 가져오기
            server_info = client.get_server_info()
            
            # 도구 목록 확인
            tools = []
            if "tools" in server_info:
                tools = server_info["tools"]
                st.success(f"사용 가능한 도구: {tools}")
            
            return client, f"Successfully connected to {server_url}. Server type: {server_type}"
        except requests.exceptions.ConnectTimeout:
            st.error(f"서버 연결 시간이 초과되었습니다: {server_url}")
            # 사용자에게 연결 테스트를 건너뛰고 계속할 수 있는 옵션 제공
            if st.button("연결 문제가 있지만 계속하기"):
                return client, f"서버 연결 테스트에 실패했지만, 설정을 저장했습니다. ({server_url})"
            raise
        except requests.exceptions.ConnectionError as e:
            st.error(f"서버 연결 오류: {str(e)}")
            
            # 연결 에러 해결 제안
            st.markdown("""
            ### 연결 오류 해결 방법
            
            1. **서버가 실행 중인지 확인하세요**
            2. **포트 번호가 올바른지 확인하세요**
            3. **'localhost' 대신 '127.0.0.1'을 시도해보세요**
            4. **다른 포트로 연결을 시도해보세요**
            5. **방화벽 설정을 확인하세요**
            """)
            
            # 사용자에게 연결 테스트를 건너뛰고 계속할 수 있는 옵션 제공
            if st.button("연결 문제가 있지만 계속하기"):
                return client, f"서버 연결 테스트에 실패했지만, 설정을 저장했습니다. ({server_url})"
            
            raise
        except Exception as e:
            st.error(f"서버 연결 테스트 실패: {str(e)}")
            
            # 사용자에게 연결 테스트를 건너뛰고 계속할 수 있는 옵션 제공
            if st.button("오류가 발생했지만 계속하기"):
                return client, f"서버 연결 테스트 중 오류가 발생했지만, 설정을 저장했습니다. ({server_url})"
            
            raise
        
    except Exception as e:
        return None, f"Error initializing MCP server: {str(e)}"

# Function to communicate with MCP server
def communicate_with_mcp_server(client, tool_name, params):
    try:
        # Call the tool
        result = client.execute_tool(tool_name, params)
        return result, None
    except Exception as e:
        return None, f"Error communicating with MCP server: {str(e)}"

# Function to convert natural language to SQL using Claude API
def natural_language_to_sql(query: str, model="claude-3-5-sonnet-20240620") -> str:
    API_URL = "https://api.anthropic.com/v1/messages"
    
    system_prompt = """You are an expert SQL translator. 
    Your task is to translate natural language queries into correct SQL statements.
    Only return the SQL statement, nothing else. Do not include any explanations or markdown formatting.
    If the query doesn't seem to be asking for a SQL statement, return the original query.
    Always make sure the SQL statements are properly formatted and valid.
    """
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": model,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": f"Convert this natural language query to SQL: {query}"}]
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        sql_query = response.json()["content"][0]["text"].strip()
        return sql_query
    except Exception as e:
        return None, f"Error converting to SQL: {str(e)}"

# UI Components
st.title("🧠 Streamlit MCP Host")
st.write("A Streamlit app that functions as an MCP host, using Claude API and connecting to Smithery MCP servers.")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # MCP Server management
    st.subheader("MCP 서버 관리")
    
    # 서버 시작/중지 컨트롤
    server_col1, server_col2 = st.columns(2)
    
    with server_col1:
        local_server_type = st.selectbox(
            "서버 유형",
            ["mysql", "perplexity", "firecrawl"],
            format_func=lambda x: {
                "mysql": "MySQL", 
                "perplexity": "Perplexity", 
                "firecrawl": "FireCrawl"
            }.get(x, x)
        )
    
    with server_col2:
        local_server_port = st.number_input(
            "포트",
            value=3000 if local_server_type == "mysql" else (3001 if local_server_type == "perplexity" else 3002),
            min_value=1000,
            max_value=9999
        )
    
    # 서버 상태 표시
    server_status = "정지됨"
    if st.session_state.mcp_server_process is not None:
        if st.session_state.mcp_server_process.poll() is None:
            server_status = "실행 중"
        else:
            server_status = "비정상 종료됨"
            st.session_state.mcp_server_process = None
    
    st.metric("서버 상태", server_status)
    
    # 시작/중지 버튼
    if st.session_state.mcp_server_process is None:
        if st.button("MCP 서버 시작"):
            success, message = start_mcp_server(local_server_type, local_server_port)
            if success:
                st.success(message)
            else:
                st.error(message)
    else:
        if st.button("MCP 서버 중지"):
            success, message = stop_mcp_server()
            if success:
                st.success(message)
            else:
                st.error(message)
    
    # 서버 로그 표시
    if st.session_state.mcp_server_process is not None:
        with st.expander("서버 로그", expanded=False):
            log_text = "\n".join(st.session_state.mcp_server_logs)
            st.code(log_text)
        
        # 연결 정보 자동 설정
        if st.button("이 서버에 연결"):
            if local_server_type == "mysql":
                port = local_server_port
                config_name = f"local-mysql-{port}"
                config_data = {
                    "serverUrl": f"http://localhost:{port}",
                    "serverType": "mysql"
                }
            elif local_server_type == "perplexity":
                port = local_server_port
                config_name = f"local-perplexity-{port}"
                config_data = {
                    "serverUrl": f"http://localhost:{port}",
                    "serverType": "perplexity"
                }
            else:
                port = local_server_port
                config_name = f"local-firecrawl-{port}"
                # FireCrawl API 키를 환경에서 로드
                firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "fc-f4745f41d5fd4e8c9d24d97b65e8a96c")
                config_data = {
                    "serverUrl": f"http://localhost:{port}",
                    "serverType": "firecrawl",
                    "apiKey": firecrawl_api_key  # API 키 추가
                }
            
            with st.spinner("Connecting to MCP server..."):
                client, message = initialize_mcp_server(config_data)
                
                if client:
                    st.session_state.mcp_configs[config_name] = {
                        "client": client,
                        "config": config_data,
                        "added_time": datetime.now()
                    }
                    st.success(message)
                else:
                    st.error(message)
    
    # Claude API settings
    st.subheader("Claude API Settings")
    claude_model = st.selectbox(
        "Select Claude Model",
        ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"]
    )
    
    # MCP Server configuration
    st.subheader("MCP 서버 연결")
    
    # Create tabs for file upload and direct input
    config_tab1, config_tab2, config_tab3, config_tab4 = st.tabs(["Upload JSON File", "Paste JSON", "Quick Connect", "Smithery AI"])
    
    with config_tab1:
        uploaded_file = st.file_uploader("Upload MCP Server JSON Configuration", type=["json"])
        config_data = None
        if uploaded_file is not None:
            try:
                config_data = json.load(uploaded_file)
            except Exception as e:
                st.error(f"Error parsing JSON file: {str(e)}")
    
    # 사용자 친화적인 JSON 직접 입력 필드
    with config_tab2:
        # JSON 예시 추가
        st.markdown("""
        **JSON 설정 예시:**
        ```json
        {
          "serverUrl": "localhost:3000",
          "serverType": "mysql"
        }
        ```
        또는 심플 URL만 입력:
        ```json
        "localhost:3000"
        ```
        
        또는 Smithery MCP 서버 설정:
        ```json
        {
          "mcpServers": {
            "mcp-mysql-server": {
              "command": "npx",
              "args": [
                "-y",
                "@smithery/cli@latest",
                "run",
                "@f4ww4z/mcp-mysql-server",
                "--key",
                "your-key-here"
              ]
            }
          }
        }
        ```
        """)
        
        # 심플 URL 입력 옵션
        use_simple_url = st.checkbox("간단한 URL 직접 입력")
        
        if use_simple_url:
            simple_url = st.text_input(
                "서버 URL 입력",
                value="localhost:3000",
                help="MCP 서버 URL을 직접 입력하세요 (예: localhost:3000)"
            )
            server_type_option = st.radio(
                "서버 타입",
                ["mysql", "perplexity", "firecrawl"]
            )
            
            if simple_url:
                config_data = {"serverUrl": simple_url, "serverType": server_type_option}
                
                # FireCrawl인 경우 API 키 추가
                if server_type_option == "firecrawl":
                    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "fc-f4745f41d5fd4e8c9d24d97b65e8a96c")
                    config_data["apiKey"] = firecrawl_api_key
                
                # 설정 이름 입력란 표시
                config_name = st.text_input(
                    "설정 이름",
                    value=f"{server_type_option}-{simple_url}",
                    key="simple_url_config_name"
                )
                
                # 연결 버튼
                if st.button("간단한 URL로 연결", key="simple_url_connect"):
                    with st.spinner("Connecting to MCP server..."):
                        client, message = initialize_mcp_server(config_data)
                        
                        if client:
                            st.session_state.mcp_configs[config_name] = {
                                "client": client,
                                "config": config_data,
                                "added_time": datetime.now()
                            }
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                            st.error("서버 연결에 실패했습니다. 설정을 확인하고 다시 시도하세요.")
        else:
            json_input = st.text_area(
                "MCP 서버 JSON 설정 붙여넣기",
                height=200,
                help="MCP 서버 설정을 JSON 형식으로 붙여넣으세요"
            )
            
            json_config_data = None
            if json_input:
                try:
                    json_config_data = json.loads(json_input)
                    
                    # JSON이 성공적으로 파싱되었을 때 설정 이름 입력란 표시
                    json_config_name = st.text_input(
                        "설정 이름",
                        value=f"Config_{int(time.time())}",
                        key="json_config_name"
                    )
                    
                    # MySQL 관련 설정인 경우 추가 설정 필드 표시
                    has_mysql = False
                    
                    # mcpServers 객체가 있고 그 안에 적어도 하나의 서버가 있는지 확인
                    if isinstance(json_config_data, dict) and "mcpServers" in json_config_data and json_config_data["mcpServers"]:
                        # mcpServers에서 첫 번째 서버 가져오기
                        server_name = list(json_config_data["mcpServers"].keys())[0]
                        server_config = json_config_data["mcpServers"][server_name]
                        
                        # 커맨드가 있고 args에 'mcp-mysql-server'가 포함되어 있으면 MySQL 관련 설정으로 간주
                        if "command" in server_config and "args" in server_config:
                            args_str = " ".join(str(arg) for arg in server_config["args"])
                            if "mysql" in args_str.lower():
                                has_mysql = True
                    
                    # 서버 타입이 명시적으로 mysql인 경우에도 MySQL 설정 표시
                    if "serverType" in json_config_data and json_config_data["serverType"] == "mysql":
                        has_mysql = True
                    
                    # MySQL 관련 설정인 경우 사용자 정보 입력란 표시
                    mysql_db_config = None
                    if has_mysql:
                        st.markdown("#### MySQL 연결 설정")
                        st.warning("JSON 설정에 MySQL 관련 설정이 감지되었습니다. MySQL 연결 정보를 입력하세요.")
                        
                        mysql_col1, mysql_col2 = st.columns(2)
                        with mysql_col1:
                            mysql_host = st.text_input("MySQL 호스트", value="localhost", key="json_mysql_host")
                            mysql_user = st.text_input("MySQL 사용자", value="root", key="json_mysql_user")
                        with mysql_col2:
                            mysql_port = st.number_input("MySQL 포트", value=3306, min_value=1, max_value=65535, key="json_mysql_port")
                            mysql_password = st.text_input("MySQL 비밀번호", type="password", key="json_mysql_password")
                        
                        mysql_db_config = {
                            "host": mysql_host,
                            "port": mysql_port,
                            "user": mysql_user,
                            "password": mysql_password
                        }
                        
                        # MySQL 데이터베이스 선택 (선택 사항)
                        mysql_database = st.text_input("MySQL 데이터베이스 (선택 사항)", key="json_mysql_database")
                        if mysql_database:
                            mysql_db_config["database"] = mysql_database
                    
                    # 연결 버튼
                    if st.button("JSON으로 연결", key="json_connect"):
                        # MySQL 설정이 있으면 config에 추가
                        if mysql_db_config:
                            json_config_data["db_config"] = mysql_db_config
                        
                        with st.spinner("Connecting to MCP server..."):
                            client, message = initialize_mcp_server(json_config_data)
                            
                            if client:
                                st.session_state.mcp_configs[json_config_name] = {
                                    "client": client,
                                    "config": json_config_data,
                                    "added_time": datetime.now()
                                }
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                except Exception as e:
                    st.error(f"JSON 파싱 오류: {str(e)}")
                    st.error("올바른 JSON 형식이 아닙니다. 예시를 참고하세요.")

    # 빠른 연결 옵션
    with config_tab3:
        st.markdown("### 빠른 연결")
        
        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("호스트", value="localhost")
        with col2:
            port = st.number_input("포트", value=3000, min_value=1, max_value=65535)
        
        server_type = st.radio(
            "서버 타입",
            ["mysql", "perplexity", "firecrawl"]
        )
        
        # MySQL 설정 (선택한 서버 타입이 mysql인 경우)
        mysql_db_config = None
        if server_type == "mysql":
            st.markdown("#### MySQL 연결 설정")
            mysql_host = st.text_input("MySQL 호스트", value="localhost", key="quick_mysql_host")
            mysql_port = st.number_input("MySQL 포트", value=3306, min_value=1, max_value=65535, key="quick_mysql_port")
            mysql_user = st.text_input("MySQL 사용자", value="root", key="quick_mysql_user")
            mysql_password = st.text_input("MySQL 비밀번호", type="password", key="quick_mysql_password")
            
            mysql_db_config = {
                "host": mysql_host,
                "port": mysql_port,
                "user": mysql_user,
                "password": mysql_password
            }
        
        # 고급 옵션
        with st.expander("고급 옵션", expanded=False):
            use_https = st.checkbox("HTTPS 사용")
            test_connection = st.checkbox("연결 테스트 건너뛰기", help="서버에 연결할 수 없지만 설정을 저장하려는 경우 선택하세요")
        
        # FireCrawl인 경우 API 키 입력 필드 표시
        firecrawl_api_key = None
        if server_type == "firecrawl":
            firecrawl_api_key = st.text_input(
                "FireCrawl API 키", 
                value=os.getenv("FIRECRAWL_API_KEY", "fc-f4745f41d5fd4e8c9d24d97b65e8a96c"),
                type="password",
                help="FireCrawl API 키를 입력하세요"
            )
        
        quick_connect_button = st.button("빠른 연결", key="quick_connect_button")
        
        if quick_connect_button:
            protocol = "https" if use_https else "http"
            server_url = f"{protocol}://{host}:{port}"
            config_name = f"{server_type}-{host}-{port}"
            
            config_data = {
                "serverUrl": server_url,
                "serverType": server_type,
                "skipConnectionTest": test_connection
            }
            
            # MySQL 설정이 있으면 추가
            if mysql_db_config:
                config_data["db_config"] = mysql_db_config
            
            # FireCrawl API 키가 있으면 추가
            if server_type == "firecrawl" and firecrawl_api_key:
                config_data["apiKey"] = firecrawl_api_key
            
            st.info(f"MCP 서버 {server_url}에 연결 중...")
            
            with st.spinner("Connecting to MCP server..."):
                client, message = initialize_mcp_server(config_data)
                
                if client:
                    st.session_state.mcp_configs[config_name] = {
                        "client": client,
                        "config": config_data,
                        "added_time": datetime.now()
                    }
                    st.success(message)
                    # 세션 상태 업데이트 후 페이지 리프레시
                    st.rerun()
                else:
                    st.error(message)

    # Smithery AI MCP 서버 연결
    with config_tab4:
        st.markdown("### Smithery AI MCP 서버 연결")
        
        st.markdown("""
        Smithery AI는 여러 유형의 MCP 서버를 제공합니다. 원하는 서버를 선택하고 연결하세요.
        
        Smithery AI 계정에서 제공하는 MCP 서버 URL과 API 키가 필요합니다.
        """)
        
        # Smithery 서버 선택
        smithery_server_type = st.selectbox(
            "Smithery AI 서버 유형",
            ["mysql", "perplexity", "firecrawl", "postgres", "azure-openai", "anthropic", "gemini"],
            format_func=lambda x: {
                "mysql": "MySQL",
                "perplexity": "Perplexity",
                "firecrawl": "FireCrawl",
                "postgres": "PostgreSQL",
                "azure-openai": "Azure OpenAI",
                "anthropic": "Anthropic",
                "gemini": "Google Gemini"
            }.get(x, x)
        )
        
        # MySQL 설정 (선택한 서버 타입이 mysql인 경우)
        mysql_db_config = None
        if smithery_server_type == "mysql":
            st.markdown("#### MySQL 연결 설정")
            mysql_host = st.text_input("MySQL 호스트", value="localhost", key="smithery_mysql_host")
            mysql_port = st.number_input("MySQL 포트", value=3306, min_value=1, max_value=65535, key="smithery_mysql_port")
            mysql_user = st.text_input("MySQL 사용자", value="root", key="smithery_mysql_user")
            mysql_password = st.text_input("MySQL 비밀번호", type="password", key="smithery_mysql_password")
            
            mysql_db_config = {
                "host": mysql_host,
                "port": mysql_port,
                "user": mysql_user,
                "password": mysql_password
            }
        
        # 서버 URL 설정
        smithery_url = st.text_input(
            "Smithery MCP 서버 URL",
            value="",
            placeholder="예: https://your-smithery-subdomain.smithery.host",
            help="Smithery AI에서 제공한 MCP 서버 URL을 입력하세요"
        )
        
        # API 키 입력
        smithery_api_key = st.text_input(
            "Smithery API 키 (선택사항)",
            type="password",
            help="Smithery API 키가 필요한 경우 입력하세요"
        )
        
        # Smithery 설정 이름
        smithery_config_name = st.text_input(
            "설정 이름",
            value=f"smithery-{smithery_server_type}",
            help="이 설정을 식별하기 위한 이름"
        )
        
        # 연결 버튼
        smithery_connect_button = st.button("Smithery 서버에 연결", key="smithery_connect_button")
        
        if smithery_connect_button:
            if not smithery_url:
                st.error("Smithery MCP 서버 URL을 입력하세요")
            else:
                # URL 형식 확인
                if not smithery_url.startswith(("http://", "https://")):
                    smithery_url = f"https://{smithery_url}"
                
                # 설정 생성
                smithery_config = {
                    "serverUrl": smithery_url,
                    "serverType": smithery_server_type
                }
                
                # API 키가 있으면 추가
                if smithery_api_key:
                    smithery_config["apiKey"] = smithery_api_key
                
                # MySQL 설정이 있으면 추가
                if mysql_db_config:
                    smithery_config["db_config"] = mysql_db_config
                
                # 연결 테스트 건너뛰기 옵션
                smithery_config["skipConnectionTest"] = st.checkbox(
                    "연결 테스트 건너뛰기", 
                    value=False,
                    help="서버에 연결할 수 없지만 설정을 저장하려는 경우 선택하세요"
                )
                
                config_data = smithery_config
                config_name = smithery_config_name
                
                st.info(f"Smithery MCP 서버 {smithery_url}에 연결 중...")
                
                with st.spinner("Connecting to Smithery MCP server..."):
                    client, message = initialize_mcp_server(config_data)
                    
                    if client:
                        st.session_state.mcp_configs[config_name] = {
                            "client": client,
                            "config": config_data,
                            "added_time": datetime.now()
                        }
                        st.success(message)
                        # 세션 상태 업데이트 후 페이지 리프레시
                        st.rerun()
                    else:
                        st.error(message)

    # Display added configurations
    if st.session_state.mcp_configs:
        st.subheader("Added MCP Servers")
        for config_name in st.session_state.mcp_configs:
            st.write(f"- {config_name}")

# Main interface
tab1, tab2 = st.tabs(["Chat", "MCP Tools"])

# Chat tab
with tab1:
    st.header("Chat with Claude")
    
    # Display chat history
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.write(f"You: {message['content']}")
        else:
            st.write(f"Claude: {message['content']}")
    
    # Chat input
    user_input = st.text_area("Enter your message:", height=100)
    
    if st.button("Send to Claude"):
        if user_input:
            # Add user message to history
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            # Call Claude API
            response, error = call_claude_api(user_input, model=claude_model)
            
            if response:
                # Add Claude response to history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
            else:
                st.error(error)

# MCP Tools tab
with tab2:
    st.header("MCP Tools")
    
    if not st.session_state.mcp_configs:
        st.info("Please add an MCP server configuration in the sidebar first.")
    else:
        # Select MCP configuration
        selected_config = st.selectbox(
            "Select MCP Server Configuration",
            list(st.session_state.mcp_configs.keys())
        )
        
        if selected_config:
            client = st.session_state.mcp_configs[selected_config]["client"]
            server_type = client.server_type
            
            # 서버 정보 표시
            with st.expander("MCP 서버 연결 정보", expanded=True):
                st.markdown(f"**서버 유형**: {server_type}")
                st.markdown(f"**서버 URL**: {client.server_url}")
                
                if client.is_mcp_server:
                    st.markdown("### Smithery MCP 서버 정보")
                    st.markdown(f"**명령어**: `{client.mcp_server_command}`")
                    if client.mcp_server_args:
                        st.markdown("**인자**:")
                        for arg in client.mcp_server_args:
                            st.markdown(f"- `{arg}`")
                    
                    # MCP 서버 유형 표시
                    if hasattr(client, 'mcp_server_type') and client.mcp_server_type:
                        st.markdown(f"**MCP 서버 유형**: `{client.mcp_server_type}`")
                    
                    # 특별히 key가 있는 경우 마스킹하여 표시
                    for arg in client.mcp_server_args or []:
                        if "--key" in str(arg):
                            key_index = client.mcp_server_args.index(arg) + 1
                            if key_index < len(client.mcp_server_args):
                                key_value = client.mcp_server_args[key_index]
                                # 키 일부 마스킹
                                if len(str(key_value)) > 8:
                                    masked_key = str(key_value)[:4] + "*" * (len(str(key_value)) - 8) + str(key_value)[-4:]
                                    st.markdown(f"**API 키**: `{masked_key}`")
                
                # MySQL 연결 정보
                if server_type == "mysql" and hasattr(client, 'db_config') and client.db_config:
                    st.markdown("### MySQL 연결 정보")
                    st.markdown(f"**호스트**: `{client.db_config.get('host', 'N/A')}`")
                    st.markdown(f"**포트**: `{client.db_config.get('port', 'N/A')}`")
                    st.markdown(f"**사용자**: `{client.db_config.get('user', 'N/A')}`")
                    # 비밀번호는 보안을 위해 마스킹
                    if 'password' in client.db_config and client.db_config['password']:
                        st.markdown("**비밀번호**: `********`")
            
            # 서버 유형에 따른 도구 표시
            if server_type == "mysql":
                tool_name = "mysql_query"
                st.subheader("MySQL Query")
                st.markdown("""
                MySQL 쿼리를 입력하세요. 자연어 또는 SQL 문법을 사용할 수 있습니다.
                예시:
                - "모든 데이터베이스를 보여줘"
                - "Show me all tables in the current database"
                - "SELECT * FROM users LIMIT 5"
                """)
                
                # 쿼리 입력
                query = st.text_area("쿼리 입력:", height=100)
                
                # 자연어 처리 옵션
                use_claude_for_nl = st.checkbox("자연어 쿼리를 SQL로 변환 (Claude API 사용)", value=True)
                
                # 쿼리 실행 전 쿼리 미리보기
                if st.button("쿼리 변환 미리보기") and query:
                    if use_claude_for_nl and ANTHROPIC_API_KEY:
                        with st.spinner("자연어를 SQL로 변환 중..."):
                            sql_query = natural_language_to_sql(query)
                            if sql_query:
                                st.code(sql_query, language="sql")
                                st.session_state.last_converted_sql = sql_query
                            else:
                                st.error("SQL 변환 실패")
                    else:
                        st.info("원본 쿼리가 그대로 사용됩니다.")
                        st.code(query)
                        st.session_state.last_converted_sql = query
                
                # 실행 버튼 - SQL로 변환 후 실행
                if st.button("실행"):
                    if query:
                        # 자연어를 SQL로 변환 (옵션 및 API 키가 있는 경우)
                        execute_query = query
                        if use_claude_for_nl and ANTHROPIC_API_KEY:
                            with st.spinner("자연어를 SQL로 변환 중..."):
                                sql_query = natural_language_to_sql(query)
                                if sql_query:
                                    st.info("자연어가 SQL로 변환되었습니다.")
                                    st.code(sql_query, language="sql")
                                    execute_query = sql_query
                                else:
                                    st.warning("SQL 변환에 실패했습니다. 원본 쿼리를 실행합니다.")
                        
                        # 마지막으로 미리보기한 SQL이 있다면 그것을 사용
                        if 'last_converted_sql' in st.session_state and use_claude_for_nl:
                            execute_query = st.session_state.last_converted_sql
                        
                        # 쿼리 실행
                        with st.spinner("쿼리 실행 중..."):
                            params = {"query": execute_query, "format": "json"}
                            result, error = communicate_with_mcp_server(client, tool_name, params)
                            
                            if result:
                                st.subheader("쿼리 결과")
                                st.json(result)
                                
                                # 쿼리 히스토리 저장 (옵션)
                                if 'query_history' not in st.session_state:
                                    st.session_state.query_history = []
                                
                                st.session_state.query_history.append({
                                    'original_query': query,
                                    'executed_query': execute_query,
                                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'success': True
                                })
                            else:
                                st.error(error)
                                
                                # 실패한 쿼리도 히스토리에 저장
                                if 'query_history' not in st.session_state:
                                    st.session_state.query_history = []
                                
                                st.session_state.query_history.append({
                                    'original_query': query,
                                    'executed_query': execute_query,
                                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'success': False,
                                    'error': error
                                })
            
            elif server_type == "perplexity":
                tool_name = "search"
                st.subheader("Perplexity Search")
                st.markdown("""
                검색하고 싶은 내용을 자연어로 입력하세요. Perplexity API를 통해 검색 결과를 얻습니다.
                예시:
                - "최신 머신러닝 연구 동향"
                - "에너지 효율을 높이는 최신 기술"
                - "지속 가능한 농업 방법"
                """)
                
                query = st.text_area("검색 쿼리:", height=100)
                
                # 검색 버튼
                if st.button("검색"):
                    if query:
                        with st.spinner("Perplexity 검색 중..."):
                            params = {"query": query, "format": "json"}
                            result, error = communicate_with_mcp_server(client, tool_name, params)
                            
                            if result:
                                st.subheader("검색 결과")
                                
                                # 응답에서 텍스트 추출 및 표시
                                if "results" in result and isinstance(result["results"], dict):
                                    perplexity_result = result["results"]
                                    
                                    if "choices" in perplexity_result and perplexity_result["choices"]:
                                        content = perplexity_result["choices"][0].get("message", {}).get("content", "")
                                        
                                        if content:
                                            st.markdown(f"### 답변\n{content}")
                                        
                                        # 인용 정보 표시
                                        if "citations" in perplexity_result and perplexity_result["citations"]:
                                            st.markdown("### 출처")
                                            for citation in perplexity_result["citations"]:
                                                if isinstance(citation, dict):
                                                    title = citation.get('title', 'Source')
                                                    url = citation.get('url', '#')
                                                    st.markdown(f"- [{title}]({url})")
                                                elif isinstance(citation, str):
                                                    st.markdown(f"- {citation}")
                                                else:
                                                    st.markdown(f"- {str(citation)}")
                                
                                # 원본 응답 데이터 (접기 형태로 표시)
                                with st.expander("원본 응답 데이터", expanded=False):
                                    st.json(result)
                            else:
                                st.error(error)
            
            elif server_type == "firecrawl":
                st.subheader("FireCrawl Tools")
                
                # 탭 생성
                firecrawl_tab1, firecrawl_tab2 = st.tabs(["Search", "Crawl"])
                
                with firecrawl_tab1:
                    st.markdown("""
                    ### FireCrawl Search
                    
                    검색하고 싶은 내용을 입력하세요. FireCrawl API를 통해 웹 검색 결과를 얻습니다.
                    """)
                    
                    search_query = st.text_area("검색어:", height=100)
                    max_results = st.slider("최대 결과 수", min_value=1, max_value=50, value=10)
                    
                    # 검색 버튼
                    if st.button("웹 검색", key="firecrawl_search"):
                        if search_query:
                            with st.spinner("FireCrawl 검색 중..."):
                                params = {"query": search_query, "max_results": max_results, "format": "json"}
                                result, error = communicate_with_mcp_server(client, "search", params)
                                
                                if result:
                                    st.subheader("검색 결과")
                                    
                                    # 결과 표시
                                    if "results" in result:
                                        firecrawl_results = result["results"]
                                        
                                        if isinstance(firecrawl_results, dict) and "results" in firecrawl_results:
                                            for item in firecrawl_results["results"]:
                                                with st.expander(item.get("title", "검색 결과")):
                                                    st.markdown(f"**URL**: [{item.get('url', '#')}]({item.get('url', '#')})")
                                                    st.markdown(f"**내용**: {item.get('content', '')}")
                                        else:
                                            st.json(firecrawl_results)
                                    
                                    # 원본 응답 데이터
                                    with st.expander("원본 응답 데이터", expanded=False):
                                        st.json(result)
                                else:
                                    st.error(error)
                
                with firecrawl_tab2:
                    st.markdown("""
                    ### FireCrawl Web Crawling
                    
                    크롤링하려는 웹 페이지의 URL을 입력하세요. FireCrawl API를 통해 페이지 내용을 추출합니다.
                    """)
                    
                    crawl_url = st.text_input("웹 페이지 URL:", placeholder="https://example.com")
                    include_links = st.checkbox("링크 포함", value=False)
                    include_images = st.checkbox("이미지 정보 포함", value=False)
                    
                    # 크롤링 버튼
                    if st.button("페이지 크롤링", key="firecrawl_crawl"):
                        if crawl_url:
                            with st.spinner("웹 페이지 크롤링 중..."):
                                params = {
                                    "url": crawl_url, 
                                    "include_links": include_links, 
                                    "include_images": include_images,
                                    "format": "json"
                                }
                                result, error = communicate_with_mcp_server(client, "crawl", params)
                                
                                if result:
                                    st.subheader("크롤링 결과")
                                    
                                    # 결과 표시
                                    if "results" in result:
                                        crawl_results = result["results"]
                                        
                                        if isinstance(crawl_results, dict):
                                            st.markdown(f"**제목**: {crawl_results.get('title', '(제목 없음)')}")
                                            st.markdown(f"**URL**: {crawl_results.get('url', crawl_url)}")
                                            
                                            with st.expander("본문 내용", expanded=True):
                                                st.markdown(crawl_results.get("content", "(내용 없음)"))
                                            
                                            if include_links and "links" in crawl_results:
                                                with st.expander("발견된 링크", expanded=False):
                                                    for link in crawl_results["links"]:
                                                        st.markdown(f"- [{link.get('text', link.get('url', '#'))}]({link.get('url', '#')})")
                                            
                                            if include_images and "images" in crawl_results:
                                                with st.expander("발견된 이미지", expanded=False):
                                                    for image in crawl_results["images"]:
                                                        st.markdown(f"- ![이미지]({image.get('src', '#')})")
                                                        st.markdown(f"  - Alt: {image.get('alt', '(대체 텍스트 없음)')}")
                                        else:
                                            st.json(crawl_results)
                                    
                                    # 원본 응답 데이터
                                    with st.expander("원본 응답 데이터", expanded=False):
                                        st.json(result)
                                else:
                                    st.error(error)
            
            else:
                st.info(f"서버 유형 '{server_type}'에 대한 인터페이스가 준비되지 않았습니다.")
                st.write("아래 정보를 확인하여 서버에 적합한 도구를 사용하세요:")
                
                # 서버 상태 정보 요청
                try:
                    server_info = client.get_server_info()
                    st.json(server_info)
                    
                    # 도구 목록 표시
                    if "tools" in server_info and server_info["tools"]:
                        st.subheader("사용 가능한 도구")
                        for tool in server_info["tools"]:
                            st.markdown(f"- `{tool}`")
                except Exception as e:
                    st.error(f"서버 정보 조회 실패: {str(e)}")

# Footer
st.markdown("---")
st.caption("Streamlit MCP Host Application")

def get_db_config():
    """Get database configuration from session state or environment variables"""
    # Default configuration
    config = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'smithery',
        'raise_on_warnings': True
    }
    
    # Override with session state values if available
    if 'db_config' in st.session_state:
        for key in st.session_state.db_config:
            if key in config and st.session_state.db_config[key]:
                config[key] = st.session_state.db_config[key]
    
    return config

def save_mcp_server_config(config_data):
    """Save MCP server configuration to database"""
    try:
        conn = mysql.connector.connect(**get_db_config())
        cursor = conn.cursor()
        
        # Check if tables exist, create if not
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mcp_server_configs (
                config_id INT AUTO_INCREMENT PRIMARY KEY,
                config_name VARCHAR(100) NOT NULL UNIQUE,
                server_type VARCHAR(50) NOT NULL,
                server_url VARCHAR(255) NOT NULL,
                api_key VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                config_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mcp_mysql_connections (
                connection_id INT AUTO_INCREMENT PRIMARY KEY,
                config_id INT NOT NULL,
                host VARCHAR(255) NOT NULL DEFAULT 'localhost',
                port INT NOT NULL DEFAULT 3306,
                username VARCHAR(100) NOT NULL DEFAULT 'root',
                password VARCHAR(255),
                database_name VARCHAR(100),
                FOREIGN KEY (config_id) REFERENCES mcp_server_configs(config_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # Insert or update the configuration
        server_type = config_data.get('server_type', '')
        server_url = config_data.get('server_url', '')
        api_key = config_data.get('api_key', '')
        config_name = config_data.get('config_name', f"{server_type} - {server_url}")
        
        # Convert config_data to JSON
        import json
        config_json = json.dumps(config_data)
        
        # Check if configuration with this name exists
        cursor.execute("SELECT config_id FROM mcp_server_configs WHERE config_name = %s", (config_name,))
        result = cursor.fetchone()
        
        if result:
            config_id = result[0]
            # Update existing configuration
            cursor.execute("""
                UPDATE mcp_server_configs 
                SET server_type = %s, server_url = %s, api_key = %s, config_data = %s, is_active = TRUE
                WHERE config_id = %s
            """, (server_type, server_url, api_key, config_json, config_id))
        else:
            # Insert new configuration
            cursor.execute("""
                INSERT INTO mcp_server_configs (config_name, server_type, server_url, api_key, config_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (config_name, server_type, server_url, api_key, config_json))
            
            config_id = cursor.lastrowid
            
        # If MySQL server type, save MySQL connection info
        if server_type == 'MySQL' and 'mysql_settings' in config_data:
            mysql_settings = config_data['mysql_settings']
            
            # Check if MySQL connection exists for this config
            cursor.execute("SELECT connection_id FROM mcp_mysql_connections WHERE config_id = %s", (config_id,))
            mysql_result = cursor.fetchone()
            
            if mysql_result:
                # Update existing MySQL connection
                cursor.execute("""
                    UPDATE mcp_mysql_connections
                    SET host = %s, port = %s, username = %s, password = %s, database_name = %s
                    WHERE config_id = %s
                """, (
                    mysql_settings.get('host', 'localhost'),
                    mysql_settings.get('port', 3306),
                    mysql_settings.get('username', 'root'),
                    mysql_settings.get('password', ''),
                    mysql_settings.get('database', ''),
                    config_id
                ))
            else:
                # Insert new MySQL connection
                cursor.execute("""
                    INSERT INTO mcp_mysql_connections (config_id, host, port, username, password, database_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    config_id,
                    mysql_settings.get('host', 'localhost'),
                    mysql_settings.get('port', 3306),
                    mysql_settings.get('username', 'root'),
                    mysql_settings.get('password', ''),
                    mysql_settings.get('database', '')
                ))
        
        conn.commit()
        return True, f"설정 '{config_name}'이(가) 저장되었습니다."
        
    except Error as e:
        return False, f"데이터베이스 오류: {str(e)}"
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

def get_saved_mcp_configs():
    """Retrieve saved MCP server configurations from database"""
    configs = []
    try:
        conn = mysql.connector.connect(**get_db_config())
        cursor = conn.cursor(dictionary=True)
        
        # Get all active configurations
        cursor.execute("""
            SELECT config_id, config_name, server_type, server_url, api_key, config_data
            FROM mcp_server_configs
            WHERE is_active = TRUE
            ORDER BY server_type, config_name
        """)
        
        configs = cursor.fetchall()
        
        # Process each config to include MySQL settings if applicable
        for config in configs:
            if config['server_type'] == 'MySQL':
                cursor.execute("""
                    SELECT host, port, username, password, database_name
                    FROM mcp_mysql_connections
                    WHERE config_id = %s
                """, (config['config_id'],))
                
                mysql_conn = cursor.fetchone()
                if mysql_conn:
                    if config['config_data']:
                        config_data = json.loads(config['config_data'])
                    else:
                        config_data = {}
                        
                    config_data['mysql_settings'] = {
                        'host': mysql_conn['host'],
                        'port': mysql_conn['port'],
                        'username': mysql_conn['username'],
                        'password': mysql_conn['password'],
                        'database': mysql_conn['database_name']
                    }
                    config['config_data'] = json.dumps(config_data)
        
        return configs
    
    except Error as e:
        st.error(f"데이터베이스 오류: {str(e)}")
        return []
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

def delete_mcp_config(config_id):
    """Delete an MCP server configuration (mark as inactive)"""
    try:
        conn = mysql.connector.connect(**get_db_config())
        cursor = conn.cursor()
        
        # Soft delete - mark as inactive
        cursor.execute("""
            UPDATE mcp_server_configs
            SET is_active = FALSE
            WHERE config_id = %s
        """, (config_id,))
        
        conn.commit()
        return True, "설정이 삭제되었습니다."
        
    except Error as e:
        return False, f"데이터베이스 오류: {str(e)}"
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

# Update the sidebar to include saved configurations
def show_sidebar():
    st.sidebar.title("MCP 서버 설정")
    
    # Initialize session state for configurations
    if 'mcp_configs' not in st.session_state:
        st.session_state.mcp_configs = {}
    
    # Tab for selecting saved configurations
    saved_configs_tab, new_config_tab = st.sidebar.tabs(["저장된 설정", "새 설정"])
    
    with saved_configs_tab:
        st.subheader("저장된 MCP 서버 설정")
        
        # Get saved configurations
        saved_configs = get_saved_mcp_configs()
        
        if saved_configs:
            config_options = ["선택하세요..."] + [f"{config['config_name']} ({config['server_type']})" for config in saved_configs]
            selected_config = st.selectbox("저장된 설정에서 선택", config_options)
            
            if selected_config != "선택하세요...":
                selected_index = config_options.index(selected_config) - 1  # -1 because of the "선택하세요..." option
                config = saved_configs[selected_index]
                
                st.write(f"서버 타입: {config['server_type']}")
                st.write(f"서버 URL: {config['server_url']}")
                
                if st.button("이 설정으로 연결"):
                    # Load the selected config
                    config_data = json.loads(config['config_data']) if config['config_data'] else {}
                    config_data['server_type'] = config['server_type']
                    config_data['server_url'] = config['server_url']
                    config_data['api_key'] = config['api_key']
                    config_data['config_name'] = config['config_name']
                    
                    # Initialize the server with this config
                    success, message = initialize_mcp_server(config_data)
                    
                    if success:
                        st.sidebar.success(message)
                    else:
                        st.sidebar.error(message)
                
                if st.button("설정 삭제", key=f"delete_{config['config_id']}"):
                    success, message = delete_mcp_config(config['config_id'])
                    if success:
                        st.sidebar.success(message)
                        st.experimental_rerun()
                    else:
                        st.sidebar.error(message)
        else:
            st.write("저장된 MCP 서버 설정이 없습니다.")
    
    with new_config_tab:
        st.subheader("새 MCP 서버 설정")
        
        # ... existing server selection code ...
        
        st.subheader("연결 정보")
        
        # ... existing connection info code ...
        
        # Add option to save this configuration
        if 'server_type' in st.session_state and st.session_state.server_type:
            save_config = st.checkbox("이 설정을 저장")
            
            if save_config:
                config_name = st.text_input("설정 이름", 
                                          value=f"{st.session_state.server_type} - {st.session_state.server_url if 'server_url' in st.session_state else ''}")
                
                # Save configuration when connecting
                if st.session_state.get('server_url') and st.button("이 설정으로 연결 및 저장"):
                    config_data = {
                        'config_name': config_name,
                        'server_type': st.session_state.server_type,
                        'server_url': st.session_state.server_url,
                        'api_key': st.session_state.get('api_key', '')
                    }
                    
                    # Add MySQL settings if applicable
                    if st.session_state.server_type == 'MySQL' and 'mysql_settings' in st.session_state:
                        config_data['mysql_settings'] = st.session_state.mysql_settings
                    
                    # Save to DB
                    success, save_message = save_mcp_server_config(config_data)
                    
                    if success:
                        st.sidebar.success(save_message)
                        
                        # Initialize the server with this config
                        init_success, init_message = initialize_mcp_server(config_data)
                        
                        if init_success:
                            st.sidebar.success(init_message)
                        else:
                            st.sidebar.error(init_message)
                    else:
                        st.sidebar.error(save_message)
            else:
                # ... existing connect button ...
                pass
