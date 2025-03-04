import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Issue Logs 검색", page_icon="🔍", layout="wide")

def connect_to_db():
    try:
        connection = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )
        return connection
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

def search_issue_logs(start_date, end_date, 대분류, 소분류, keyword, 진행상태):
    conn = connect_to_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 기본 쿼리 작성
        query = """
        SELECT 
            DATE_FORMAT(등록일자, '%Y-%m-%d') as 등록일자,
            담당자,
            대분류,
            소분류,
            제목,
            이슈내용,
            DATE_FORMAT(업데이트일자, '%Y-%m-%d') as 업데이트일자,
            해결절차,
            진행상태,
            비고1,
            비고2
        FROM issue_logs
        WHERE 등록일자 BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        
        # 조건 추가
        if 대분류 != "전체":
            query += " AND 대분류 = %s"
            params.append(대분류)
        
        if 소분류 != "전체":
            query += " AND 소분류 = %s"
            params.append(소분류)
        
        if 진행상태 != "전체":
            query += " AND 진행상태 = %s"
            params.append(진행상태)
        
        if keyword:
            query += """ AND (
                제목 LIKE %s OR
                이슈내용 LIKE %s OR
                해결절차 LIKE %s OR
                비고1 LIKE %s OR
                비고2 LIKE %s
            )"""
            keyword_param = f"%{keyword}%"
            params.extend([keyword_param] * 5)
        
        query += " ORDER BY 등록일자 DESC, 업데이트일자 DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return pd.DataFrame(results)
    
    except Exception as e:
        st.error(f"데이터 검색 중 오류 발생: {e}")
        return None
    finally:
        conn.close()

def main():
    st.title("🔍 Issue Logs 검색")
    
    # 검색 필터 컨테이너
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            # 날짜 범위 선택
            start_date = st.date_input(
                "시작일",
                value=datetime.now() - timedelta(days=30),
                max_value=datetime.now()
            )
            
        with col2:
            end_date = st.date_input(
                "종료일",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        # 검색 필터 행
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            대분류_options = ["전체", "SCM", "품질관리", "기타"]
            selected_대분류 = st.selectbox("대분류", 대분류_options)
        
        with col2:
            소분류_options = {
                "전체": ["전체"],
                "SCM": ["전체", "PO", "배송", "통관", "입고"],
                "품질관리": ["전체", "인증", "생산", "불량", "AS"],
                "기타": ["전체"]
            }
            selected_소분류 = st.selectbox(
                "소분류",
                소분류_options.get(selected_대분류, ["전체"])
            )
        
        with col3:
            keyword = st.text_input("키워드 검색", placeholder="검색어를 입력하세요")
        
        with col4:
            진행상태_options = ["전체", "접수", "진행중", "완료", "보류"]
            selected_진행상태 = st.selectbox("진행상태", 진행상태_options)
    
    # 검색 버튼
    if st.button("검색", type="primary"):
        df = search_issue_logs(
            start_date,
            end_date,
            selected_대분류,
            selected_소분류,
            keyword,
            selected_진행상태
        )
        
        if df is not None and not df.empty:
            # 검색 결과 표시
            st.success(f"총 {len(df)}개의 이슈가 검색되었습니다.")
            
            # 각 이슈를 확장 가능한 섹션으로 표시
            for idx, row in df.iterrows():
                with st.expander(f"📋 {row['등록일자']} - {row['제목']} ({row['진행상태']})"):
                    col1, col2 = st.columns([2,1])
                    
                    with col1:
                        st.markdown(f"**담당자:** {row['담당자']}")
                        st.markdown(f"**분류:** {row['대분류']} > {row['소분류']}")
                        st.markdown("**이슈내용:**")
                        st.text(row['이슈내용'])
                        st.markdown("**해결절차:**")
                        st.text(row['해결절차'])
                    
                    with col2:
                        st.markdown(f"**업데이트:** {row['업데이트일자']}")
                        st.markdown(f"**진행상태:** {row['진행상태']}")
                        if row['비고1']:
                            st.markdown("**비고1:**")
                            st.text(row['비고1'])
                        if row['비고2']:
                            st.markdown("**비고2:**")
                            st.text(row['비고2'])
        else:
            st.warning("검색 결과가 없습니다.")

if __name__ == "__main__":
    main()
