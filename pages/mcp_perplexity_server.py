
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
