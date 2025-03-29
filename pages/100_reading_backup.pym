import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def main():
    st.title("독서토론 조회")
    
    # 필터 옵션
    col1, col2 = st.columns(2)
    
    with col1:
        # 책 제목으로 필터링 (기본값: 퍼스널 MBA)
        titles = get_book_titles()
        if "퍼스널 MBA" not in titles:
            titles = ["퍼스널 MBA"] + titles
        
        selected_title = st.selectbox(
            "책 선택",
            titles,
            index=titles.index("퍼스널 MBA") if "퍼스널 MBA" in titles else 0
        )
    
    with col2:
        # 자료 유형 선택
        type_mapping = {
            "요약": "summary",
            "적용": "application"
        }
        material_type = st.selectbox(
            "자료 유형",
            list(type_mapping.keys())
        )
    
    # 선택된 책과 유형에 해당하는 파일 목록 조회
    files = get_files(selected_title, type_mapping[material_type])
    
    if files:
        # 파일 선택
        selected_file = st.selectbox(
            "파일 선택",
            files,
            format_func=lambda x: f"{x['file_name']} ({x['created_at'].strftime('%Y-%m-%d')})"
        )
        
        # 선택된 파일 내용 표시
        if selected_file:
            st.write(f"### {selected_file['file_name']}")
            st.markdown(selected_file['content'])
            st.write("---")
            st.write(f"*등록일: {selected_file['created_at'].strftime('%Y-%m-%d')}*")
    else:
        st.info(f"{selected_title}의 {material_type} 자료가 없습니다.")

def get_files(book_title, material_type):
    """파일 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT *
            FROM reading_materials
            WHERE book_title = %s
            AND type = %s
            ORDER BY created_at DESC
        """, (book_title, material_type))
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_book_titles():
    """저장된 책 제목 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT book_title
            FROM reading_materials
            ORDER BY book_title
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 