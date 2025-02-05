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
load_dotenv()

# Set page configuration
st.set_page_config(page_title="신사업실 일일 업무일지", page_icon="📋", layout="wide")

# Page header
st.write("# 신사업실 일일 업무일지")

# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Load credentials from the JSON file
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])

# Connect to Google Sheets
gc = gspread.authorize(creds)

# Google Sheet ID and Worksheet name

NEWBIZ_DAILY_SPREADSHEET_ID = os.getenv('NEWBIZ_DAILY_SPREADSHEET_ID')
NEWBIZ_DAILY_WORKSHEET_NAME = os.getenv('NEWBIZ_DAILY_WORKSHEET_NAME') 
# Open the worksheet
sheet = gc.open_by_key(NEWBIZ_DAILY_SPREADSHEET_ID).worksheet(NEWBIZ_DAILY_WORKSHEET_NAME)

# Get current date and time
current_time = datetime.now()
# MySQL 연결 설정
conn = mysql.connector.connect(
    user =  os.getenv('SQL_USER'),
    password =  os.getenv('SQL_PASSWORD'),
    host =  os.getenv('SQL_HOST'),
    database =  os.getenv('SQL_DATABASE_NEWBIZ'),   # 비밀번호
    charset='utf8mb4',       # UTF-8의 하위 집합을 사용하는 문자셋 설정
    collation='utf8mb4_general_ci'  # 일반적인 Collation 설정
)
conn.autocommit = True
cursor = conn.cursor()

# Create form fields for the user input
st.subheader("일일업무 일지 작성해 주세요")

# Registered date field (default is current time)
일자 = st.date_input("일자", value=current_time)

# 담당자 선택
담당자 = st.selectbox("담당자", ["장창환","박성범","이상현","기타"])

# Task type selection
카테고리 = st.selectbox("카테고리", ["프로젝트", "내부미팅","고객사미팅", "세미나","교육","해외파트너미팅","기타"])

업무일지 = st.text_area("업무일지",height=100)



# MySQL에서 동일한 날짜와 업무유형을 가진 데이터 검색
registered_date_for_query = 일자.strftime('%Y.%m.%d')  # 시간 제외
cursor.execute("""
    SELECT 진행현황, 완료일정,비고 
    FROM newbiz_daily
    WHERE DATE(일자) = %s AND 담당자 = %s AND 카테고리 = %s AND 업무일지 = %s
""", (registered_date_for_query, 담당자, 카테고리,업무일지))

existing_data = cursor.fetchone()

# 만약 기존 데이터가 있으면 폼에 자동으로 채워 넣음
if existing_data:
    st.info("기존데이터가 발견되었습니다.")
    진행현황 = st.selectbox("진행현황",["진행중","완료","중단","준비중"],value=existing_data[0])
    완료일정 = st.date_input("완료일정", value=existing_data[1])
    비고 = st.text_area("비고",height=250,value=existing_data[0])
else:
    진행현황 = st.selectbox("진행현황",["진행중","완료","중단","준비중"])
    완료일정 = st.date_input("완료일정", value=current_time )
    비고 = st.text_area("비고",height=250)
# 구글 시트에서 기존 데이터 검색
sheet_data = sheet.get_all_values()
df_sheet = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
#st.write("Column names from Google Sheet:", df_sheet.columns.tolist())

# 구글 시트에 동일한 등록 날짜와 업무유형을 가진 데이터 검색
matching_rows = df_sheet[(df_sheet['일자'] == registered_date_for_query) & (df_sheet['카테고리'] == 카테고리) & (df_sheet['담당자'] == 담당자) & (df_sheet['업무일지'] == 업무일지)]

# Submit button to save to Google Sheets and MySQL
if st.button("Save to Google Sheets and MySQL"):
    # Format the date to string format that can be written to Google Sheets
    registered_date_str = 일자.strftime('%Y.%m.%d')
    완료일정_str = 완료일정.strftime('%Y.%m.%d')  # 완료일정도 문자열로 변환

    # 새로운 데이터 행
    new_row = [registered_date_str, 담당자, 카테고리, 업무일지, 진행현황, 완료일정_str, 비고]  # 완료일정_str 사용

    # 구글 시트에 동일한 데이터가 있을 경우 업데이트, 없을 경우 추가
    if not matching_rows.empty:
        # 업데이트할 행 번호 찾기 (구글 시트는 1부터 시작하므로 +2)
        row_index = matching_rows.index[0] + 2
        sheet.update(f'A{row_index}:G{row_index}', [new_row])
        st.success("The work journal has been updated in Google Sheets!")
    else:
        # 새로운 행 추가
        sheet.append_row(new_row)
        st.success("The work journal has been saved to Google Sheets!")

    # MySQL 등록 날짜는 시간/분/초를 00:00:00으로 설정
    registered_date_for_db = datetime.combine(일자, datetime.min.time())

    # MySQL에서 동일한 날짜와 업무유형이 있는지 확인
    cursor.execute("""
    SELECT id
    FROM newbiz_daily
    WHERE DATE(일자) = %s AND 담당자 = %s AND 카테고리 = %s AND 업무일지 = %s
    """, (registered_date_for_query, 담당자, 카테고리,업무일지))

    existing_entry = cursor.fetchone()

    if existing_entry:
        # 기존 데이터가 있으면 업데이트
        cursor.execute("""
            UPDATE newbiz_daily
            SET 진행현황 = %s, 완료일정 = %s, 비고 = %s 
            WHERE id = %s
        """, (진행현황, 완료일정,비고, existing_entry[0]))
        st.success("The work journal has been updated in MySQL!")
    else:
        # 새로운 데이터 삽입
        cursor.execute("""
            INSERT INTO newbiz_daily (일자, 담당자, 카테고리, 업무일지, 진행현황, 완료일정,비고) 
            VALUES (%s, %s, %s, %s, %s,%s,%s)
        """, (registered_date_for_db,담당자, 카테고리, 업무일지, 진행현황, 완료일정,비고))
        st.success("The work journal has been saved to MySQL!")

# Fetch the sheet data to display the current data in the sheet
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# Display the updated DataFrame in Streamlit
st.dataframe(df)

# Close MySQL connection
cursor.close()
conn.close()