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
st.set_page_config(page_title="주간업무보고", page_icon="📋", layout="wide")

# Page header
st.write("# 주간 업무 보고")

# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Load credentials from the JSON file
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])

# Connect to Google Sheets
gc = gspread.authorize(creds)

# Google Sheet ID and Worksheet name

NEWBIZ_WEEKLY_SPREADSHEET_ID = os.getenv('NEWBIZ_WEEKLY_SPREADSHEET_ID')
NEWBIZ_WEEKLY_WORKSHEET_NAME = os.getenv('NEWBIZ_WEEKLY_WORKSHEET_NAME') 
# Open the worksheet
sheet = gc.open_by_key(NEWBIZ_WEEKLY_SPREADSHEET_ID).worksheet(NEWBIZ_WEEKLY_WORKSHEET_NAME)

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
st.subheader("금주 주간 업무 계획만 작성해 주세요.")

# 일자와 담당자 입력 후 전주 업무 자동 로드를 위한 함수
def load_last_week_tasks(일자, 담당자):
    try:
        # 전주 월요일 계산
        selected_date = datetime.strptime(일자.strftime('%Y-%m-%d'), '%Y-%m-%d')
        last_monday = selected_date - timedelta(days=7)
        
        # 전주 데이터 조회 쿼리
        cursor.execute("""
            WITH numbered_rows AS (
                SELECT 금주업무, 완료일정,
                       ROW_NUMBER() OVER (ORDER BY id) as row_num
                FROM newbiz_weekly
                WHERE DATE(일자) = DATE(%s) AND 담당자 = %s
            )
            SELECT 
                GROUP_CONCAT(
                    CONCAT(row_num, '. ', 
                           IFNULL(금주업무, ''), 
                           ' (완료일정: ', 
                           CASE 
                               WHEN 완료일정 REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                               THEN DATE_FORMAT(STR_TO_DATE(LEFT(완료일정, 10), '%Y-%m-%d'), '%Y.%m.%d')
                               WHEN 완료일정 REGEXP '^[0-9]{4}.[0-9]{2}.[0-9]{2}'
                               THEN LEFT(완료일정, 10)
                               ELSE IFNULL(완료일정, '')
                           END,
                           ')')
                    ORDER BY row_num
                    SEPARATOR '\n'
                ) as last_week_summary
            FROM numbered_rows
        """, (last_monday, 담당자))
        
        result = cursor.fetchone()
        return result[0] if result and result[0] else ""
    except Exception as e:
        st.error(f"전주 업무 로드 중 오류 발생: {e}")
        return ""

# 일자와 담당자 입력 후 전주 업무 자동 로드
일자 = st.date_input("일자", value=current_time)
담당자 = st.selectbox("담당자", ["장창환", "박성범","김성현","이상현","기타"])

# 전주 업무 자동 로드
last_week_tasks = load_last_week_tasks(일자, 담당자)

# 전주업무종합 텍스트 영역에 자동으로 채우기
전주업무종합 = st.text_area("전주업무종합", 
                      value=last_week_tasks,
                      height=200,
                      help="전주의 금주업무와 완료일정이 자동으로 로드됩니다.")

# 카테고리 
카테고리 = st.selectbox("카테고리", ["프로젝트", "내부미팅","고객사미팅", "세미나","교육","해외파트너미팅","업무지원","기타"])
금주업무 = st.text_area("금주업무", height=100)# 구글 시트에서 기존 데이터 검색
# MySQL에서 동일한 날짜와 업무유형을 가진 데이터 검색
registered_date_for_query = 일자.strftime('%Y.%m.%d')  # 시간 제외
cursor.execute("""
    SELECT 완료일정, 비고 , 전주업무종합
    FROM newbiz_weekly 
    WHERE DATE(일자) = %s AND 담당자 = %s AND 카테고리 = %s AND 금주업무 = %s
""", (registered_date_for_query, 담당자, 카테고리,금주업무))

existing_data = cursor.fetchone()

# 만약 기존 데이터가 있으면 폼에 자동으로 채워 넣음
if existing_data:
    st.info("Existing entry found. Fields are pre-filled.")
    완료일정 = st.date_input("완료일정", value=existing_data[0])
    비고 = st.text_area("비고", value=existing_data[1], height=250)
else:
    완료일정 = st.date_input("완료일정", value=current_time)
    비고 = st.text_area("비고",height=250)


sheet_data = sheet.get_all_values()
df_sheet = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
#st.write("Column names from Google Sheet:", df_sheet.columns.tolist())

# 구글 시트에 동일한 등록 날짜와 업무유형을 가진 데이터 검색
matching_rows = df_sheet[(df_sheet['일자'] == registered_date_for_query) & (df_sheet['담당자'] == 담당자) & (df_sheet['카테고리'] == 카테고리) & (df_sheet['금주업무'] == 금주업무)]

# Submit button to save to Google Sheets and MySQL
if st.button("Save to Google Sheets and MySQL"):
    # Format the date to string format that can be written to Google Sheets
    registered_date_str = 일자.strftime('%Y.%m.%d')
    완료일정_str = 완료일정.strftime('%Y.%m.%d')  # 완료일정도 문자열로 변환

    # 새로운 데이터 행
    new_row = [registered_date_str, 담당자, 카테고리, 금주업무, 완료일정_str, 비고,전주업무종합]  # 완료일정_str 사용

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
        SELECT id FROM newbiz_weekly
        WHERE DATE(일자) = %s AND 담당자 = %s AND 카테고리 = %s AND 금주업무 = %s
    """, (registered_date_for_query, 담당자, 카테고리, 금주업무))

    existing_entry = cursor.fetchone()

    if existing_entry:
        # 기존 데이터가 있으면 업데이트
        cursor.execute("""
            UPDATE newbiz_weekly
            SET 완료일정 = %s, 비고 = %s 
            WHERE id = %s
        """, (완료일정, 비고, existing_entry[0]))
        st.success("The work journal has been updated in MySQL!")
    else:
        # 새로운 데이터 삽입
        cursor.execute("""
            INSERT INTO newbiz_weekly (일자, 담당자, 카테고리, 금주업무, 완료일정, 비고,전주업무종합) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (registered_date_for_db, 담당자, 카테고리, 금주업무, 완료일정, 비고,전주업무종합))
        st.success("The work journal has been saved to MySQL!")

# Fetch the sheet data to display the current data in the sheet
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# Display the updated DataFrame in Streamlit
st.dataframe(df)

# Close MySQL connection
cursor.close()
conn.close()