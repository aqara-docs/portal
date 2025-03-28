import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import numpy as np
import os
from dotenv import load_dotenv
load_dotenv()

# Set page configuration
st.set_page_config(page_title="회의록 저장하기", page_icon="📋", layout="wide")

# Page header
st.write("# 회의록 파일 저장")

# Get current date and time
current_time = datetime.now()
# MySQL 연결 설정
conn = mysql.connector.connect(
    user =  os.getenv('SQL_USER'),
    password =  os.getenv('SQL_PASSWORD'),
    host =  os.getenv('SQL_HOST'),
    database =  os.getenv('SQL_DATABASE_NEWBIZ'),
    charset='utf8mb4',
    collation='utf8mb4_general_ci'
)
conn.autocommit = True
cursor = conn.cursor()

# Create form fields for the user input
st.subheader("회의록을 등록해 주세요!!")

# Registered date field (default is current time)
등록일 = st.date_input("등록일", value=current_time)

# Task type selection
meeting_type = st.selectbox("미팅 유형", ["고객 미팅", "파트너 미팅","사내 미팅","유튜브 강의","기타"])

# 작업자 선택
writer = st.selectbox("담당자", ["김현철","장창환","박성범","이상현","기타"])

# 파일 업로더 추가
uploaded_file = st.file_uploader("미팅 내용 Markdown 파일 선택", type=['md'])
minutes = ""
if uploaded_file is not None:
    # 파일 내용 읽기
    minutes = uploaded_file.read().decode('utf-8')
    st.markdown("### 업로드된 미팅 내용:")
    st.markdown(minutes)

remarks = st.text_area("비고", height=200)

if st.button("Save to MySQL"):
    if not minutes:
        st.error("미팅 내용 파일을 업로드해주세요.")
    else:
        # Format the date to string format
        registered_date_str = 등록일.strftime('%Y.%m.%d')

        # 새로운 데이터 행
        new_row = [registered_date_str, meeting_type, writer, minutes, remarks]

        # MySQL 등록 날짜는 시간/분/초를 00:00:00으로 설정
        registered_date_for_db = datetime.combine(등록일, datetime.min.time())

        # 새로운 데이터 삽입
        cursor.execute("""
            INSERT INTO meeting_minutes (등록일, 미팅유형, 작성자, 미팅요약, 비고) 
            VALUES (%s, %s, %s, %s, %s)
        """, (registered_date_for_db, meeting_type, writer, minutes, remarks))
        st.success("The minutes of the meeting has been saved to MySQL!")
