import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

# Set page configuration
st.set_page_config(page_title="사고방식 특성 자가진단서 뷰어", page_icon="🔍", layout="wide")

# Page header
st.title("🔍 사고방식 특성 자가진단서 뷰어")
st.subheader("저장된 자가진단 결과를 조회합니다.")

# DB 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_general_ci'
    )

# Google Sheets 연결 설정
def connect_to_sheets():
    SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
    
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    
    return gspread.authorize(creds)

def get_all_names():
    """DB에서 모든 이름 목록을 가져옵니다."""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT name FROM thinking_style_diagnosis ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        return names
    except Exception as e:
        st.error(f"이름 목록 조회 중 오류가 발생했습니다: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_diagnosis_by_name(name):
    """특정 이름의 진단 결과를 모두 가져옵니다."""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT name, department, position, test_date, responses, analysis 
            FROM thinking_style_diagnosis 
            WHERE name = %s 
            ORDER BY test_date DESC
        """, (name,))
        
        columns = ['이름', '부서', '직책', '진단일', '응답내용', '분석결과']
        results = pd.DataFrame(cursor.fetchall(), columns=columns)
        return results
    
    except Exception as e:
        st.error(f"진단 결과 조회 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()

def main():
    # 이름 목록 가져오기
    names = get_all_names()
    
    # 이름 선택 드롭다운
    selected_name = st.selectbox(
        "조회할 이름을 선택하세요",
        options=names,
        index=None,
        placeholder="이름을 선택하세요..."
    )
    
    if selected_name:
        # 선택된 이름의 진단 결과 조회
        results = get_diagnosis_by_name(selected_name)
        
        if not results.empty:
            # 각 진단 결과를 탭으로 표시
            for idx, row in results.iterrows():
                with st.expander(f"진단 결과 ({row['진단일'].strftime('%Y-%m-%d')})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("### 기본 정보")
                        st.write(f"**이름:** {row['이름']}")
                        st.write(f"**부서:** {row['부서']}")
                        st.write(f"**직책:** {row['직책']}")
                        st.write(f"**진단일:** {row['진단일'].strftime('%Y-%m-%d')}")
                    
                    with col2:
                        st.write("### 응답 내용")
                        # 응답 내용을 보기 좋게 포맷팅
                        responses = row['응답내용'].split('\n')
                        for resp in responses:
                            if resp.strip():
                                st.write(resp)
                    
                    st.write("### 분석 결과")
                    st.markdown(row['분석결과'])
                    
                    st.markdown("---")
        else:
            st.warning("해당 이름의 진단 결과가 없습니다.")
    
    # 데이터 다운로드 기능 (하나의 버튼으로 직접 다운로드)
    st.download_button(
        label="📥 전체 데이터 다운로드",
        data=get_markdown_content(),  # 함수로 분리
        file_name="thinking_style_diagnosis.md",
        mime="text/markdown"
    )

def get_markdown_content():
    """전체 데이터를 마크다운 형식으로 변환"""
    try:
        conn = connect_to_db()
        query = "SELECT * FROM thinking_style_diagnosis ORDER BY test_date DESC"
        df = pd.read_sql(query, conn)
        
        markdown_content = "# 사고방식 특성 자가진단 결과\n\n"
        
        for idx, row in df.iterrows():
            markdown_content += f"## 진단 결과 {row['test_date'].strftime('%Y-%m-%d')}\n\n"
            markdown_content += f"### 기본 정보\n"
            markdown_content += f"- 이름: {row['name']}\n"
            markdown_content += f"- 부서: {row['department']}\n"
            markdown_content += f"- 직책: {row['position']}\n"
            markdown_content += f"- 진단일: {row['test_date'].strftime('%Y-%m-%d')}\n\n"
            
            markdown_content += f"### 응답 내용\n"
            responses = row['responses'].split('\n')
            for resp in responses:
                if resp.strip():
                    markdown_content += f"{resp}\n"
            markdown_content += "\n"
            
            markdown_content += f"### 분석 결과\n"
            markdown_content += f"{row['analysis']}\n\n"
            markdown_content += "---\n\n"
        
        return markdown_content
        
    except Exception as e:
        st.error(f"데이터 다운로드 중 오류가 발생했습니다: {e}")
        return ""
    finally:
        conn.close()

if __name__ == "__main__":
    main() 