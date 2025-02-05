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


# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(page_title="연락처", page_icon="📋", layout="wide")

# Page header
st.write("# 연락처")

# Google Sheets 인증 설정
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[os.getenv('SCOPES')])
gc = gspread.authorize(creds)

# Google Sheets ID와 Worksheet name
CONTACT_SPREADSHEET_ID = os.getenv('CONTACT_SPREADSHEET_ID')
CONTACT_SPREADSHEET_NAME = os.getenv('CONTACT_SPREADSHEET_NAME')

# 워크시트 열기
sheet = gc.open_by_key(CONTACT_SPREADSHEET_ID).worksheet(CONTACT_SPREADSHEET_NAME)

# Google Sheets에서 데이터를 불러와 DataFrame으로 변환
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])
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

# 사용자 입력 필드
st.write("## 새로운 데이터 입력")
registered_date = st.date_input("등록일", value=datetime.now())
name = st.text_input("성명")
company = st.text_input("회사")

cursor.execute("""
    SELECT 등록일, 메일, 전화, 위챗, 비고 
    FROM contact_list 
    WHERE 성명 = %s AND 회사 = %s
""", (name, company))

existing_data = cursor.fetchone()

# 만약 기존 데이터가 있으면 폼에 자동으로 채워 넣음
if existing_data:
    st.info("Existing entry found. Fields are pre-filled.")
    mail = st.text_input("메일", value=existing_data[1])
    phone = st.text_input("전화", value=existing_data[2])
    wechat = st.text_input("위챗", value=existing_data[3])
    remarks = st.text_area("비고", value=existing_data[4],height=200)
else:
      mail = st.text_input("메일")
      phone = st.text_input("전화")
      wechat = st.text_input("위챗")
      remarks = st.text_area("비고",height=200)


# 데이터를 Google Sheets에 추가하는 함수
def add_data_to_google_sheets(sheet, data):
    try:
        sheet.append_row(data)  # Google Sheets에 새 행 추가
        st.success("데이터가 성공적으로 추가되었습니다.")
    except Exception as e:
        st.error(f"데이터 추가 중 오류 발생: {e}")

# '추가' 버튼을 클릭하면 새로운 데이터를 추가
if st.button("추가"):
    # 모든 입력 필드가 비어있는지 확인
    if registered_date and name and company:
        registered_date_str = registered_date.strftime("%Y.%m.%d")
        new_data = [registered_date_str,name, company, mail, phone, wechat, remarks]
        add_data_to_google_sheets(sheet, new_data)
    else:
        st.error("모든 필드를 입력해 주세요.")

# MySQL 등록 날짜는 시간/분/초를 00:00:00으로 설정
    registered_date_for_db = datetime.combine(registered_date, datetime.min.time())

    # MySQL에서 동일한 날짜와 업무유형이 있는지 확인
    cursor.execute("""
        SELECT id FROM contact_list
        WHERE 성명 = %s AND 회사 = %s
    """, (name, company))

    existing_entry = cursor.fetchone()

    if existing_entry:
        # 기존 데이터가 있으면 업데이트
        cursor.execute("""
            UPDATE contact_list
            SET 등록일 = %s, 성명 = %s, 회사 = %s,메일 = %s,전화 = %s,위챗 = %s,비고 = %s
            WHERE id = %s
        """, (registered_date_for_db, name, company, mail,phone,wechat,remarks,existing_entry[0]))
        st.success("The work journal has been updated in MySQL!")
    else:
        # 새로운 데이터 삽입
        cursor.execute("""
            INSERT INTO contact_list (등록일, 성명, 회사, 메일, 전화, 위챗, 비고) 
            VALUES (%s, %s, %s, %s, %s,%s, %s)
        """, (registered_date_for_db, name, company,mail,phone,wechat,remarks))
        st.success("The work journal has been saved to MySQL!")

# Fetch the sheet data to display the current data in the sheet
data = sheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

# Display the updated DataFrame in Streamlit
st.dataframe(df)

# Close MySQL connection
cursor.close()
conn.close()        