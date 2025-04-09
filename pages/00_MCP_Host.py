import streamlit as st
import json
from typing import Dict, Optional, List
import requests
from datetime import datetime

class SimpleMCPClient:
    """간단한 MCP 클라이언트 구현"""
    
    def __init__(self, server_url: str, server_type: str):
        # MCP 서버 기본 포트 설정
        if ":" not in server_url:
            if server_type == "mysql":
                server_url = f"{server_url}:3000"  # MySQL MCP 서버 기본 포트
            else:
                server_url = f"{server_url}:3001"  # Perplexity MCP 서버 기본 포트
        
        self.server_url = server_url if server_url.startswith(("http://", "https://")) else f"http://{server_url}"
        self.server_type = server_type
        
        # 서버 설정
        if server_type == "mysql":
            self.db_config = {
                "host": "localhost",
                "port": 3306,
                "user": "root",  # 실제 환경에서는 환경 변수나 설정 파일에서 읽어와야 함
                "password": ""    # 실제 환경에서는 환경 변수나 설정 파일에서 읽어와야 함
            }
    
    def get_server_info(self) -> Dict:
        """서버 정보 조회"""
        try:
            response = requests.get(
                f"{self.server_url}/status",
                timeout=5  # 5초 타임아웃 설정
            )
            if response.status_code == 200:
                server_info = response.json()
                if self.server_type == "mysql":
                    server_info["db_config"] = {
                        "host": self.db_config["host"],
                        "port": self.db_config["port"]
                    }
                return server_info
            raise Exception(f"서버 상태 조회 실패: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"서버 연결 실패: {str(e)}")
    
    def execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """도구 실행"""
        if self.server_type == "mysql":
            # MySQL 설정 추가
            params["db_config"] = self.db_config
        
        try:
            response = requests.post(
                f"{self.server_url}/execute",
                json={
                    "tool": tool_name,
                    "parameters": params
                },
                timeout=30  # 30초 타임아웃 설정
            )
            if response.status_code == 200:
                return response.json()
            raise Exception(f"도구 실행 실패: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"서버 요청 실패: {str(e)}")
    
    def close(self):
        """연결 종료"""
        pass  # HTTP 기반이므로 특별한 정리가 필요 없음

st.title("MCP 서버 호스트")

def connect_to_mcp_server(server_url: str, server_type: str) -> Dict:
    """MCP 서버 연결"""
    try:
        # MCP 클라이언트 생성
        client = SimpleMCPClient(server_url, server_type)
        
        # 서버 연결 및 기능 확인
        server_info = client.get_server_info()
        
        # 서버 타입별 메시지 생성
        if server_type == "mysql":
            db_config = server_info.get("db_config", {})
            message = f"MySQL MCP 서버에 연결되었습니다. (DB: {db_config.get('host')}:{db_config.get('port')})"
        else:
            message = "Perplexity MCP 서버에 연결되었습니다."
        
        return {
            "success": True,
            "message": message,
            "server_info": server_info,
            "client": client
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"연결 실패: {str(e)}"
        }

def execute_mcp_query(query: str, client: SimpleMCPClient, server_type: str) -> Dict:
    """MCP 서버를 통한 쿼리 실행"""
    try:
        # 서버 타입에 따른 적절한 도구 선택
        if server_type == "mysql":
            # MySQL 쿼리 실행
            result = client.execute_tool("mysql_query", {
                "query": query,
                "format": "json"
            })
        else:
            # Perplexity 검색 실행
            result = client.execute_tool("search", {
                "query": query,
                "format": "json"
            })
        
        return {
            "success": True,
            "results": result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

# 서버 상태 관리
if 'server_status' not in st.session_state:
    st.session_state.server_status = {
        'connected': False,
        'connect_time': None,
        'server_type': None,
        'server_url': None,
        'client': None,
        'query_history': []
    }

# 사이드바에 서버 설정
with st.sidebar:
    st.header("MCP 서버 연결")
    
    # 서버 유형 선택
    server_type = st.selectbox(
        "서버 유형",
        ["mysql", "perplexity"],
        format_func=lambda x: "MySQL MCP 서버" if x == "mysql" else "Perplexity MCP 서버"
    )
    
    # 서버 URL 입력
    default_port = "3000" if server_type == "mysql" else "3001"
    server_url = st.text_input(
        "서버 URL",
        value=f"localhost:{default_port}",
        help=f"연결할 MCP 서버의 URL을 입력하세요 (예: localhost:{default_port})"
    )
    
    if server_type == "mysql":
        with st.expander("MySQL 설정", expanded=False):
            mysql_host = st.text_input("MySQL 호스트", value="localhost")
            mysql_port = st.number_input("MySQL 포트", value=3306, min_value=1, max_value=65535)
            mysql_user = st.text_input("MySQL 사용자", value="root")
            mysql_password = st.text_input("MySQL 비밀번호", type="password")
    
    # 서버 연결/해제 버튼
    if not st.session_state.server_status['connected']:
        if st.button(f"{server_type.upper()} MCP 서버 연결"):
            with st.spinner("서버 연결 중..."):
                result = connect_to_mcp_server(server_url, server_type)
                if result["success"]:
                    st.session_state.server_status.update({
                        'connected': True,
                        'connect_time': datetime.now(),
                        'server_type': server_type,
                        'server_url': server_url,
                        'client': result["client"],
                        'server_info': result.get("server_info", {})
                    })
                    st.success(result["message"])
                else:
                    st.error(f"연결 실패: {result.get('error', 'Unknown error')}")
    else:
        if st.button("서버 연결 해제"):
            if st.session_state.server_status.get('client'):
                st.session_state.server_status['client'].close()
            st.session_state.server_status.update({
                'connected': False,
                'connect_time': None,
                'server_type': None,
                'server_url': None,
                'client': None,
                'server_info': None
            })
            st.warning("MCP 서버 연결이 해제되었습니다.")

# 메인 영역에 서버 상태 및 기능 표시
if st.session_state.server_status['connected']:
    st.header("서버 상태")
    
    # 서버 정보 표시
    col1, col2 = st.columns(2)
    with col1:
        st.metric("상태", "연결됨")
        st.metric("서버 유형", server_type.upper())
    with col2:
        uptime = datetime.now() - st.session_state.server_status['connect_time']
        st.metric("연결 시간", f"{uptime.seconds//3600}시간 {(uptime.seconds//60)%60}분")
        st.metric("쿼리 수행 횟수", len(st.session_state.server_status['query_history']))
    
    # 서버 정보 표시
    if st.session_state.server_status.get('server_info'):
        with st.expander("서버 정보", expanded=False):
            st.json(st.session_state.server_status['server_info'])
    
    # 쿼리 실행 영역
    st.header("쿼리 실행")
    if server_type == "mysql":
        st.markdown("""
        자연어로 MySQL 쿼리를 작성하세요.
        예시:
        ```
        Show me all tables in the newbiz database
        Get the first 5 users from the users table
        ```
        """)
    else:
        st.markdown("검색하고 싶은 내용을 자연어로 입력하세요.")
    
    query = st.text_area("쿼리 입력", height=200)
    
    if st.button("실행"):
        if query:
            with st.spinner("실행 중..."):
                result = execute_mcp_query(
                    query,
                    st.session_state.server_status['client'],
                    server_type
                )
                
                if result["success"]:
                    st.markdown("### 실행 결과")
                    st.json(result["results"])
                    
                    # 쿼리 기록 저장
                    st.session_state.server_status['query_history'].append({
                        'query': query,
                        'timestamp': result["timestamp"],
                        'result': "성공"
                    })
                else:
                    st.error(f"실행 실패: {result['error']}")
    
    # 쿼리 기록 표시
    if st.session_state.server_status['query_history']:
        st.header("쿼리 기록")
        for idx, query in enumerate(reversed(st.session_state.server_status['query_history'][-5:])):
            with st.expander(f"쿼리 #{len(st.session_state.server_status['query_history']) - idx}: ({query['timestamp']})"):
                st.code(query['query'])
                st.text(query['result'])
else:
    st.info("MCP 서버에 연결되어 있지 않습니다. 사이드바에서 서버에 연결해주세요.")