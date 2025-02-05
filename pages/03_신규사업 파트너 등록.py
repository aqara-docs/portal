import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(page_title="신규사업 파트너 등록", page_icon="📋", layout="wide")

# Page header
st.write("# 신규사업 파트너 등록")

# Google Sheets 인증 설정
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[os.getenv('SCOPES')])
gc = gspread.authorize(creds)

# Google Sheets ID와 Worksheet name
NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID = os.getenv('NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID')
NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME = os.getenv('NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME')

# 워크시트 열기
sheet = gc.open_by_key(NEW_PARTNERS_CANDIDATES_SPREADSHEET_ID).worksheet(NEW_PARTNERS_CANDIDATES_SPREADSHEET_NAME)



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

# 회사 이름 선택
#st.write("## 회사 선택 또는 새 회사 입력")
company_list_query = "SELECT DISTINCT 회사 FROM partner_candidates"
cursor.execute(company_list_query)
company_list = [row[0] for row in cursor.fetchall()]
company_list.insert(0, "새 회사 입력")  # '새 회사 입력'을 리스트의 첫 번째 옵션으로 추가

selected_company = st.selectbox("회사 선택 또는 새 회사 입력", company_list)

if selected_company == "새 회사 입력":
    company = st.text_input("새로운 회사 이름을 입력하세요")
else:
    company = selected_company

# 회사에 해당하는 제품명 리스트 업
product_name = ""
if company and company != "새 회사 입력":
    product_query = "SELECT DISTINCT 제품명 FROM partner_candidates WHERE 회사 = %s"
    cursor.execute(product_query, (company,))
    product_list = [row[0] for row in cursor.fetchall()]
    product_name = st.selectbox("제품명 선택", ["새로운 제품 입력"] + product_list)

if product_name == "새로운 제품 입력" or not product_name:
    product_name = st.text_input("새로운 제품명을 입력하세요")

# 기존 데이터 검색 및 입력 필드 자동 채우기
cursor.execute("""
    SELECT 등록일, 분야, 회사소개, 웹사이트, 연락처, 제품범주, 제품특징, 비고
    FROM partner_candidates
    WHERE 회사 = %s AND 제품명 = %s
""", (company, product_name))
existing_data = cursor.fetchone()

# 데이터 입력 폼
if existing_data:
    st.info("기존 데이터를 불러왔습니다.")
    registered_date = st.date_input("등록일", value=existing_data[0])
    field = st.text_input("분야", value=existing_data[1])
    company_intro = st.text_area("회사소개", value=existing_data[2], height=200)
    website = st.text_input("웹사이트", value=existing_data[3])
    contact = st.text_input("연락처", value=existing_data[4])
    product_category = st.text_input("제품범주", value=existing_data[5])
    product_feature = st.text_area("제품특징", value=existing_data[6], height=200)
    remarks = st.text_area("비고", value=existing_data[7])
else:
    registered_date = st.date_input("등록일", value=datetime.now())
    field = st.text_input("분야")
    company_intro = st.text_area("회사소개", height=200)
    website = st.text_input("웹사이트")
    contact = st.text_input("연락처")
    product_category = st.text_input("제품범주")
    product_feature = st.text_area("제품특징", height=200)
    remarks = st.text_area("비고")


# 구글 시트에서 기존 데이터 검색
sheet_data = sheet.get_all_values()
df_sheet = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
#st.write("Column names from Google Sheet:", df_sheet.columns.tolist())

# 구글 시트에 동일한 등록 날짜와 업무유형을 가진 데이터 검색
matching_rows = df_sheet[(df_sheet['회사'] == company) & (df_sheet['제품명'] == product_name)]

# 데이터 추가/업데이트
if st.button("저장"):
    registered_date_str = registered_date.strftime('%Y.%m.%d')

    # 새로운 데이터 행
    new_row = [registered_date_str, field, company, company_intro, website,contact, product_category,product_name, product_feature,remarks]

    # 구글 시트에 동일한 데이터가 있을 경우 업데이트, 없을 경우 추가
    if not matching_rows.empty:
        # 업데이트할 행 번호 찾기 (구글 시트는 1부터 시작하므로 +2)
        row_index = matching_rows.index[0] + 2
        sheet.update(f'A{row_index}:J{row_index}', [new_row])
        st.success("The work journal has been updated in Google Sheets!")
    else:
        # 새로운 행 추가
        sheet.append_row(new_row)
        st.success("The work journal has been saved to Google Sheets!")



    registered_date_for_db = datetime.combine(registered_date, datetime.min.time())

    # 기존 데이터가 있으면 업데이트
    cursor.execute("""
        SELECT id FROM partner_candidates
        WHERE 회사 = %s AND 제품명 = %s
    """, (company, product_name))
    existing_entry = cursor.fetchone()

    if existing_entry:
        cursor.execute("""
            UPDATE partner_candidates
            SET 등록일 = %s, 분야 = %s, 회사소개 = %s, 웹사이트 = %s, 연락처 = %s, 제품범주 = %s, 제품특징 = %s, 비고 = %s
            WHERE id = %s
        """, (registered_date_for_db, field, company_intro, website, contact, product_category, product_feature, remarks, existing_entry[0]))
        st.success("데이터가 성공적으로 업데이트되었습니다.")
    else:
        cursor.execute("""
            INSERT INTO partner_candidates (등록일, 분야, 회사, 회사소개, 웹사이트, 연락처, 제품범주, 제품명, 제품특징, 비고)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (registered_date_for_db, field, company, company_intro, website, contact, product_category, product_name, product_feature, remarks))
        st.success("데이터가 성공적으로 저장되었습니다.")

# Close MySQL connection
cursor.close()
conn.close()