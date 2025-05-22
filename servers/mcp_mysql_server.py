import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# 기본 포트 설정
PORT = 3000

# 커맨드 라인에서 포트 받기
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])

# MySQL 연결 설정
# Hardcoded as requested
default_config = {
    "host": "localhost",
    "port": 3306,
    "user": "iotuser",
    "password": "iot12345",
    "database": "newbiz"
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
        self.wfile.write(json.dumps({"error": message}, cls=DateTimeEncoder).encode())
    
    def do_GET(self):
        if self.path == "/status":
            self._set_headers()
            status = {
                "status": "running",
                "type": "mysql",
                "tools": ["mysql_query"]
            }
            self.wfile.write(json.dumps(status, cls=DateTimeEncoder).encode())
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
        # Always use the hardcoded config, ignore any db_config in params
        db_config = default_config
        
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
            self.wfile.write(json.dumps({"results": results}, cls=DateTimeEncoder).encode())
        except Error as e:
            self._handle_error(500, str(e))

def run_server(port):
    server_address = ('', port)
    try:
        httpd = HTTPServer(server_address, MCPHandler)
        print(f"MySQL MCP server running on port {port}")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"포트 {port}가 이미 사용 중입니다. MySQL MCP 서버가 이미 실행 중일 수 있습니다.")
            return
        raise  # 다른 OSError는 그대로 발생시킴

if __name__ == "__main__":
    port = PORT
    run_server(port)
