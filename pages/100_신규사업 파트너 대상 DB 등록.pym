import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import numpy as np
import os
from dotenv import load_dotenv
load_dotenv()

# Set page configuration
st.set_page_config(page_title="신규사업 파트너 대상 기업", page_icon="📋", layout="wide")

# Page header
st.write("# 신규사업 파트너 대상 기업")

# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Load credentials from the JSON file
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[os.getenv('SCOPES')])

# Connect to Google Sheets
gc = gspread.authorize(creds)

# Google Sheet ID and Worksheet name
NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID = os.getenv('NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID')
NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME = os.getenv('NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME')  # Replace with your worksheet name



# Open the worksheet
sheet = gc.open_by_key(NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID).worksheet(NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME)

# Fetch the sheet data
data = sheet.get_all_values()

# Create a DataFrame, assuming the first two rows are header and instruction rows
# and the actual data starts from the 3rd row (index 2)
df = pd.DataFrame(data[1:])
df = df.iloc[:, 0:10]

# Define the required columns
required_columns = [
    '등록일','분야', '회사', '회사소개', '웹사이트', '연락처', '제품범주', 
    '제품명', '제품특징', '비고'
]
df.columns = required_columns
df['등록일'] = pd.to_datetime(df['등록일'], errors='coerce')

# Replace empty strings with None
df = df.replace("", None)

st.dataframe(df)

# MySQL 연결 설정
conn = mysql.connector.connect(
        user =  os.getenv('SQL_USER'),
        password =  os.getenv('SQL_PASSWORD'),
        host =  os.getenv('SQL_HOST'),
        database =  os.getenv('SQL_DATABASE_NEWBIZ'),   # 비밀번호
        charset='utf8mb4',       # UTF-8의 하위 집합을 사용하는 문자셋 설정
        collation='utf8mb4_general_ci'  # 일반적인 Collation 설정
)

# Autocommit 활성화
conn.autocommit = True
cursor = conn.cursor()

# Insert or Update query
query = """
INSERT INTO partner_candidates (
    `등록일`, `분야`, `회사`, `회사소개`, `웹사이트`, `연락처`, `제품범주`, 
    `제품명`, `제품특징`, `비고`
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
) ON DUPLICATE KEY UPDATE
    `등록일` = VALUES(`등록일`),
    `분야` = VALUES(`분야`),
    `회사소개` = VALUES(`회사소개`),
    `웹사이트` = VALUES(`웹사이트`),
    `연락처` = VALUES(`연락처`),
    `제품범주` = VALUES(`제품범주`),
    `제품특징` = VALUES(`제품특징`),
    `비고` = VALUES(`비고`);
"""

# MySQL에 데이터 삽입/업데이트
def insert_or_update_data(df):
    try:
        for index, row in df.iterrows():
            # 상품명, 상품옵션, 배송메시지, 특이사항을 None으로 변경
            values = [
                row['등록일'].strftime('%Y-%m-%d %H:%M:%S') if row['등록일'] else None,
                row['분야'] if row['분야'] else None,
                row['회사'] if row['회사'] else None,
                row['회사소개'] if row['회사소개'] else None,
                row['웹사이트'] if row['웹사이트'] else None,
                row['연락처'] if row['연락처'] else None,
                row['제품범주'] if row['제품범주'] else None,
                row['제품명'] if row['제품명'] else None,
                row['제품특징'] if row['제품특징'] else None,
                row['비고'] if row['비고'] else None
            ]
            # 쿼리 실행
            cursor.execute(query, values)
        
        conn.commit()
        st.write("데이터가 성공적으로 MySQL에 저장되었거나 업데이트되었습니다.")
    except Error as e:
        st.write(f"Error while connecting to MySQL: {e}")
    finally:
        cursor.close()
        conn.close()

# df의 데이터를 MySQL에 삽입/업데이트
insert_or_update_data(df)
