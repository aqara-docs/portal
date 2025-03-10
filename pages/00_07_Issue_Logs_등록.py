import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import numpy as np
import os
from dotenv import load_dotenv
import requests
load_dotenv()

# Set page configuration
st.set_page_config(page_title="Issue Logs 등록", page_icon="📋", layout="wide")

# Page header
st.write("# Issue Logs 등록")

# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Load credentials from the JSON file
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])

# Connect to Google Sheets
gc = gspread.authorize(creds)

# Google Sheet ID and Worksheet name
ISSUE_LOGS_SPREADSHEET_ID = os.getenv('ISSUE_LOGS_SPREADSHEET_ID')
ISSUE_LOGS_WORKSHEET_NAME = os.getenv('ISSUE_LOGS_WORKSHEET_NAME') 
# Open the worksheet
sheet = gc.open_by_key(ISSUE_LOGS_SPREADSHEET_ID).worksheet(ISSUE_LOGS_WORKSHEET_NAME)

# Get current date and time
current_time = datetime.now()
# MySQL 연결 설정
conn = mysql.connector.connect(
    user=os.getenv('SQL_USER'),
    password=os.getenv('SQL_PASSWORD'),
    host=os.getenv('SQL_HOST'),
    database=os.getenv('SQL_DATABASE_NEWBIZ'),
    charset='utf8mb4',
    collation='utf8mb4_general_ci'
)
conn.autocommit = True
cursor = conn.cursor()

# MySQL에서 동일한 unique key를 가진 데이터 검색 함수를 상단으로 이동
def get_existing_data(대분류, 소분류, 제목):
    cursor.execute("""
        SELECT id, 진행상태, 해결절차, 비고1, 비고2
        FROM issue_logs 
        WHERE 대분류 = %s AND 소분류 = %s AND 제목 = %s
    """, (대분류, 소분류, 제목))
    return cursor.fetchone()

# 세션 상태 초기화 부분 수정
if 'summary' not in st.session_state:
    st.session_state.summary = ""
    st.session_state.previous_title = ""  # 이전 제목 저장용

# Create form fields for the user input
st.subheader("극단적으로 진실하고 투명하게 이슈로그를 작성해 주세요.")

# 등록일자 (default is current time)
등록일자 = st.date_input("등록일자", value=current_time)

# 담당자 선택
담당자 = st.selectbox("담당자", ["기타", "김성현", "박성범", "이상현"])

# 대분류 선택
대분류 = st.selectbox("대분류", ["SCM", "품질관리", "기타"])

# 소분류 선택 - 대분류에 따라 동적으로 옵션 변경
소분류_options = {
    "SCM": ["PO", "배송", "통관", "입고"],
    "품질관리": ["인증", "생산", "불량", "AS"],
    "기타": []  # 기타의 경우 직접 입력하도록 함
}

if 대분류 == "기타":
    소분류 = st.text_input("소분류")
else:
    소분류 = st.selectbox("소분류", 소분류_options[대분류])

# 제목 입력 후에 existing_data 확인 및 세션 상태 업데이트
제목 = st.text_input("제목")
if 제목 and 제목 != st.session_state.previous_title:  # 제목이 변경된 경우에만 확인
    st.session_state.previous_title = 제목
    existing_data = get_existing_data(대분류, 소분류, 제목)
    if existing_data and existing_data[3]:  # existing_data[3]은 비고1
        st.session_state.summary = existing_data[3]
    else:
        st.session_state.summary = ""

# Ollama 요약 함수 수정 - 한국어 프롬프트 개선
def get_summary_from_ollama(content, model="llama2"):
    try:
        prompt = f"""다음 이슈 로그의 내용을 간단명료하게 요약해주세요. 
        핵심적인 이슈와 해결 상태를 중심으로 3줄 이내로 작성해주세요.

        입력 내용:
        {content}

        요약:"""
        
        response = requests.post('http://localhost:11434/api/generate',
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            })
        if response.status_code == 200:
            return response.json()['response'].strip()
        return "요약 생성 실패"
    except Exception as e:
        return f"요약 생성 중 오류 발생: {str(e)}"

# Ollama 모델 선택 부분 수정
model_options = [
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1:70b",
    "llama3.1",
    "phi4",
    "llama3.3",
    "llama2",
    "gemma2",
    "mistral",
    "gemma",
    "llama3.2"
]
selected_model = st.selectbox("AI 모델 선택", model_options, 
                            help="더 큰 모델(예: deepseek-r1:70b)이 더 나은 요약을 제공할 수 있지만, 처리 시간이 더 걸릴 수 있습니다.")

# 이슈내용 입력
이슈내용 = st.text_area("이슈내용", height=250)

# 업데이트일자
업데이트일자 = st.date_input("업데이트일자", value=current_time)

# 해결절차
해결절차 = st.text_area("해결절차", height=250)

# 진행상태
진행상태 = st.selectbox("진행상태", ["접수", "진행중", "완료", "보류"])

# 요약 버튼 추가
if st.button("내용 요약"):
    full_content = f"""
    이슈내용:
    {이슈내용}
    
    해결절차:
    {해결절차}
    
    진행상태:
    {진행상태}
    """
    
    summary = get_summary_from_ollama(full_content, selected_model)
    st.session_state.summary = summary
    st.rerun()

# 비고1 텍스트 영역 표시
비고1 = st.text_area("AI 요약", value=st.session_state.summary, height=250, key="비고1_input")

# 비고2
비고2 = st.text_area("비고2", height=250)

# Submit button to save to Google Sheets and MySQL
if st.button("Save to Google Sheets and MySQL"):
    # Format the dates to string format
    registered_date_str = 등록일자.strftime('%Y.%m.%d')
    update_date_str = 업데이트일자.strftime('%Y.%m.%d')

    # 새로운 데이터 행
    new_row = [registered_date_str, 담당자, 대분류, 소분류, 제목, 이슈내용, 
               update_date_str, 해결절차, 진행상태, 비고1, 비고2]

    # 구글 시트에 추가
    sheet.append_row(new_row)
    st.success("The issue log has been saved to Google Sheets!")

    # MySQL 등록 날짜는 시간/분/초를 00:00:00으로 설정
    registered_date_for_db = datetime.combine(등록일자, datetime.min.time())
    update_date_for_db = datetime.combine(업데이트일자, datetime.min.time())

    existing_data = get_existing_data(대분류, 소분류, 제목)
    if existing_data:
        cursor.execute("""
            UPDATE issue_logs
            SET 등록일자 = %s, 담당자 = %s, 이슈내용 = %s, 업데이트일자 = %s,
                해결절차 = %s, 진행상태 = %s, 비고1 = %s, 비고2 = %s
            WHERE id = %s
        """, (registered_date_for_db, 담당자, 이슈내용, update_date_for_db,
              해결절차, 진행상태, 비고1, 비고2, existing_data[0]))
    else:
        cursor.execute("""
            INSERT INTO issue_logs (등록일자, 담당자, 대분류, 소분류, 제목, 이슈내용,
                                  업데이트일자, 해결절차, 진행상태, 비고1, 비고2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (registered_date_for_db, 담당자, 대분류, 소분류, 제목, 이슈내용,
              update_date_for_db, 해결절차, 진행상태, 비고1, 비고2))
    
    # 저장 후 세션 상태 완전 초기화
    st.session_state.summary = ""
    st.session_state.previous_title = ""
    st.success("The issue log has been saved to MySQL!")
    st.rerun()

# Fetch the sheet data to display the current data
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# Display the updated DataFrame in Streamlit
st.dataframe(df)

# Close MySQL connection
cursor.close()
conn.close()

