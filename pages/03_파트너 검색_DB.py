import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(page_title="신규사업 파트너 검색", page_icon="📋", layout="wide")

# Page header
st.write("# 신규사업 파트너 검색")

# MySQL connection setup
def get_db_connection():
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
    except Error as e:
        st.error(f"Database connection error: {e}")
        return None

# Fetch data from the database
def fetch_data_from_db(query, params=None):
    connection = get_db_connection()
    if connection is None:
        return None
    try:
        df = pd.read_sql(query, con=connection, params=params)
        return df
    except Error as e:
        st.error(f"Error fetching data: {e}")
        return None
    finally:
        connection.close()

# Query to fetch all data from partner_candidates
query = """
    SELECT 등록일, 분야, 회사, 회사소개, 웹사이트, 연락처, 제품범주, 
           제품명, 제품특징, 비고
    FROM partner_candidates
"""
df = fetch_data_from_db(query)

if df is not None:
    # Replace NaN values with empty strings for consistency
    df = df.fillna(value="")
    df['등록일'] = pd.to_datetime(df['등록일'], errors='coerce')

    # Step 1: 분야 선택
    selected_field = st.selectbox("분야 선택", options=["전체"] + df['분야'].dropna().unique().tolist())

    # Step 2: 분야에 맞는 회사 리스트 업데이트
    if selected_field != "전체":
        companies = df[df['분야'] == selected_field]['회사'].dropna().unique().tolist()
    else:
        companies = df['회사'].dropna().unique().tolist()

    selected_company = st.selectbox("회사 선택", options=["전체"] + companies)

    # Step 3: 회사와 분야에 맞는 제품 범주 리스트 업데이트
    if selected_field != "전체" and selected_company != "전체":
        product_categories = df[(df['분야'] == selected_field) & (df['회사'] == selected_company)]['제품범주'].dropna().unique().tolist()
    elif selected_field != "전체":
        product_categories = df[df['분야'] == selected_field]['제품범주'].dropna().unique().tolist()
    elif selected_company != "전체":
        product_categories = df[df['회사'] == selected_company]['제품범주'].dropna().unique().tolist()
    else:
        product_categories = df['제품범주'].dropna().unique().tolist()

    selected_product_category = st.selectbox("제품범주 선택", options=["전체"] + product_categories)

    # 검색 버튼
    if st.button("검색"):
        # Apply filters
        filtered_df = df.copy()

        if selected_field != "전체":
            filtered_df = filtered_df[filtered_df['분야'] == selected_field]

        if selected_company != "전체":
            filtered_df = filtered_df[filtered_df['회사'] == selected_company]

        if selected_product_category != "전체":
            filtered_df = filtered_df[filtered_df['제품범주'] == selected_product_category]

        # 검색 결과 출력
        st.write("## 검색 결과 (테이블)")
        st.table(filtered_df)

        # 검색 결과를 JSON 형식으로 출력
        st.write("## 검색 결과 (Readable JSON)")
        try:
            # Create readable output with each key-value pair on a new line
            filtered_dict = filtered_df.to_dict(orient='records')
            for record in filtered_dict:
                st.write("---")  # Separator between records
                for key, value in record.items():
                    st.write(f"**{key}:** {value}")
        except TypeError as e:
            st.write(f"Error: {e}")
else:
    st.error("Failed to load data from the database.")