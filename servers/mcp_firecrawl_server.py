import sys
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv
import time

# 환경 변수 로드
load_dotenv()

# 기본 포트 설정
PORT = 3002

# 커맨드 라인에서 포트 받기
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])

# API 키 설정
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not FIRECRAWL_API_KEY or FIRECRAWL_API_KEY == "":
    # 환경 변수에서 로드되지 않은 경우 직접 값 설정
    FIRECRAWL_API_KEY = "fc-f4745f41d5fd4e8c9d24d97b65e8a96c"

print(f"FireCrawl API 키: {FIRECRAWL_API_KEY[:4]}...{FIRECRAWL_API_KEY[-4:]}")  # 보안을 위해 일부만 표시

# API 키 설정 - 하드코딩
FIRECRAWL_API_KEY = "fc-f4745f41d5fd4e8c9d24d97b65e8a96c"  # 하드코딩된 API 키
print(f"FireCrawl API 키: {FIRECRAWL_API_KEY}")  # 전체 API 키 출력 (디버깅용)

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
        max_results = params.get("max_results", 10)
        
        try:
            # FireCrawl API 호출 - 여러 인증 형식 시도
            headers = {
                "X-API-Key": FIRECRAWL_API_KEY,  # 일반적인 API 키 형식
                "x-api-key": FIRECRAWL_API_KEY,  # 소문자 버전
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",  # Bearer 토큰 형식
                "Content-Type": "application/json"
            }
            
            # 요청 데이터 단순화
            data = {
                "url": f"https://www.google.com/search?q={query}"
            }
            
            print(f"FireCrawl API 요청 URL: https://api.firecrawl.dev/v1/scrape")
            print(f"FireCrawl API 요청 헤더: {headers}")
            print(f"FireCrawl API 요청 데이터: {data}")
            
            # V0 버전 API 시도
            response = requests.post(
                "https://api.firecrawl.dev/scrape",
                headers=headers,
                json=data
            )
            
            print(f"FireCrawl API 응답 코드: {response.status_code}")
            if response.status_code != 200:
                print(f"FireCrawl API 오류: {response.text}")
                return self._handle_error(response.status_code, f"FireCrawl API error: {response.text}")
            
            # 응답 파싱
            firecrawl_response = response.json()
            
            if not firecrawl_response.get("success", False):
                return self._handle_error(500, f"FireCrawl API error: {firecrawl_response.get('error', 'Unknown error')}")
            
            # 마크다운 내용 추출
            markdown_content = firecrawl_response.get("data", {}).get("markdown", "")
            metadata = firecrawl_response.get("data", {}).get("metadata", {})
            title = metadata.get("title", "검색 결과")
            
            # 검색 결과 형식화
            content = f"### 검색 결과: {query}\n\n{markdown_content}"
            
            # 인용 정보 추가
            citations = [{
                "title": title,
                "url": metadata.get("sourceURL", f"https://www.google.com/search?q={query}"),
                "source": "FireCrawl"
            }]
            
            # Perplexity API 응답 구조와 유사하게 만들기
            smithery_response = {
                "id": f"firecrawl-search-{hash(query)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "citations": citations,
                "usage": {
                    "prompt_tokens": len(query),
                    "completion_tokens": len(content),
                    "total_tokens": len(query) + len(content)
                },
                "raw_response": firecrawl_response
            }
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": smithery_response}).encode())
        except Exception as e:
            self._handle_error(500, str(e))

    def execute_firecrawl_crawl(self, params):
        if "url" not in params:
            return self._handle_error(400, "Missing url parameter")
        
        if not FIRECRAWL_API_KEY:
            return self._handle_error(500, "FIRECRAWL_API_KEY not set in environment")
        
        url = params["url"]
        
        try:
            # FireCrawl API 호출 - 여러 인증 형식 시도
            headers = {
                "X-API-Key": FIRECRAWL_API_KEY,  # 일반적인 API 키 형식
                "x-api-key": FIRECRAWL_API_KEY,  # 소문자 버전
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",  # Bearer 토큰 형식
                "Content-Type": "application/json"
            }
            
            # 요청 데이터 단순화
            data = {
                "url": url
            }
            
            print(f"FireCrawl API 요청 URL: https://api.firecrawl.dev/v1/scrape")
            print(f"FireCrawl API 요청 헤더: {headers}")
            print(f"FireCrawl API 요청 데이터: {data}")
            
            # V0 버전 API 시도
            response = requests.post(
                "https://api.firecrawl.dev/scrape",
                headers=headers,
                json=data
            )
            
            print(f"FireCrawl API 응답 코드: {response.status_code}")
            if response.status_code != 200:
                print(f"FireCrawl API 오류: {response.text}")
                return self._handle_error(response.status_code, f"FireCrawl API error: {response.text}")
            
            # 응답 파싱
            firecrawl_response = response.json()
            
            if not firecrawl_response.get("success", False):
                return self._handle_error(500, f"FireCrawl API error: {firecrawl_response.get('error', 'Unknown error')}")
            
            # 마크다운 내용 추출
            markdown_content = firecrawl_response.get("data", {}).get("markdown", "")
            metadata = firecrawl_response.get("data", {}).get("metadata", {})
            title = metadata.get("title", "페이지 내용")
            
            # Perplexity API 응답 구조와 유사하게 만들기
            smithery_response = {
                "id": f"firecrawl-crawl-{hash(url)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": markdown_content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "citations": [
                    {
                        "title": title,
                        "url": url,
                        "source": "FireCrawl"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(url),
                    "completion_tokens": len(markdown_content),
                    "total_tokens": len(url) + len(markdown_content)
                },
                "raw_response": firecrawl_response
            }
            
            self._set_headers()
            self.wfile.write(json.dumps({"results": smithery_response}).encode())
        except Exception as e:
            self._handle_error(500, str(e))

def run_server(port):
    server_address = ('', port)
    try:
        httpd = HTTPServer(server_address, MCPHandler)
        print(f"Firecrawl MCP server running on port {port}")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"포트 {port}가 이미 사용 중입니다. Firecrawl MCP 서버가 이미 실행 중일 수 있습니다.")
            return
        raise  # 다른 OSError는 그대로 발생시킴

if __name__ == "__main__":
    port = PORT
    run_server(port) 