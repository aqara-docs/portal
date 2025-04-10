
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
