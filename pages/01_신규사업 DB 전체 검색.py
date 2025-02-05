import streamlit as st
import pandas as pd
import mysql.connector
import json
import re
import html  # HTML 이스케이프를 위한 모듈
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

import json
from decimal import Decimal

# Decimal 값을 처리하기 위한 변환 함수
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)  # 또는 str(obj)로 변환 가능
    raise TypeError

# MySQL Database configuration for cs


db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# 테이블 리스트
tables = ['meeting_minutes','newbiz_preparation','partner_candidates','work_journal','weekly_journal','contact_list']

def get_actual_columns(table_name, db_config):
    """Fetch actual column names from a specific table in the database."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        columns = cursor.fetchall()
        cursor.close()
        conn.close()

        return [column[0] for column in columns]
    except mysql.connector.Error as err:
        st.error(f"Error fetching columns for {table_name}: {err}")
        return []

def search_data_from_table(table_name, keyword=None, start_date=None, end_date=None, db_config=None, search_type="AND"):
    """Search data in a specific table in MySQL database based on given filters."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Get actual columns for the table
        actual_columns = get_actual_columns(table_name, db_config)
        query = f"SELECT * FROM {table_name} WHERE 1=1"
        filters = []

        if keyword:
            keyword_conditions = []
            keywords = keyword.split()  # Split the keyword for AND/OR search

            if search_type == "Exact Match":
                exact_keyword = ' '.join(keywords)
                for col in actual_columns:
                    keyword_conditions.append(f"REPLACE({col}, ' ', '') LIKE %s")
                query += " AND (" + " OR ".join(keyword_conditions) + ")"
                filters.extend([f'%{exact_keyword.replace(" ", "")}%'] * len(actual_columns))
            else:
                for col in actual_columns:
                    if search_type == "AND":
                        keyword_conditions.append(" AND ".join([f"{col} LIKE %s" for _ in keywords]))
                    else:  # OR search
                        keyword_conditions.append(" OR ".join([f"{col} LIKE %s" for _ in keywords]))
                query += " AND (" + " OR ".join(keyword_conditions) + ")"
                filters.extend([f'%{k}%' for k in keywords] * len(actual_columns))

        if start_date and end_date:
            if 'registered_date' in actual_columns:
                query += " AND registered_date BETWEEN %s AND %s"
                filters.extend([start_date, end_date])

        cursor.execute(query, tuple(filters))
        rows = cursor.fetchall()

        # Close cursor and connection
        cursor.close()
        conn.close()

        # Convert datetime objects to string for JSON serialization
        for row in rows:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.strftime('%Y-%m-%d %H:%M:%S')

        return pd.DataFrame(rows), rows  # Return both DataFrame and raw data for JSON display
    except mysql.connector.Error as err:
        st.error(f"Error querying table {table_name}: {err}")
        return pd.DataFrame(), []  # Return empty values in case of error

def highlight_keywords(text, keyword, search_type="AND"):
    """Highlight keywords in text based on the search type and remove newlines."""
    if not keyword:
        return text

    # Clean and escape the text, remove newlines
    text = html.escape(str(text)).replace("\n", "")  # '\n'을 제거
    text = html.escape(str(text)).replace("\t", "")  # '\t'을 제거

    if search_type == "Exact Match":
        # Escape the entire keyword phrase for exact match
        escaped_keyword = re.escape(keyword.strip())
        highlighted = f"<mark style='background-color: yellow'>{keyword.strip()}</mark>"
        text = re.sub(f"({escaped_keyword})", highlighted, text, flags=re.IGNORECASE)
    else:
        # Highlight individual words for AND/OR search
        keywords = keyword.split()
        for word in keywords:
            escaped_word = re.escape(word)  # Escape special characters in the word
            highlighted = f"<mark style='background-color: yellow'>{word}</mark>"
            text = re.sub(f"({escaped_word})", highlighted, text, flags=re.IGNORECASE)

    return text

def highlight_keywords_in_dataframe(df, keyword, search_type="AND"):
    """Apply keyword highlighting to all text columns in the DataFrame."""
    if not keyword:
        return df

    # Copy the DataFrame to avoid modifying the original
    highlighted_df = df.copy()

    # Apply highlighting to all object (text) columns and remove newlines
    for col in highlighted_df.select_dtypes(include=['object']).columns:
        highlighted_df[col] = highlighted_df[col].apply(lambda x: highlight_keywords(x, keyword, search_type))

    return highlighted_df

# Streamlit UI components
st.write("# 신규 사업 DB 검색 시스템")

# Calculate 30 days before the current date
default_start_date = datetime.now() - timedelta(days=365)

# 검색 유형 선택
search_option = st.radio("검색 옵션을 선택하세요", ["전체 검색", "테이블별 검색"])

# Input fields for search filters with default values
keyword = st.text_input("키워드로 검색", "")
search_type = st.radio("검색 타입 선택", ("AND", "OR", "Exact Match"))  # Choose search type
start_date = st.date_input("시작 날짜", value=default_start_date)  # Default start date set to 30 days ago
end_date = st.date_input("종료 날짜", value=datetime.now())  # Default end date is today

# Convert date to string format for SQL compatibility
start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None
end_date_str = end_date.strftime('%Y-%m-%d') if end_date else None

if search_option == "전체 검색":
    if st.button("전체 검색 실행"):
        combined_dataframes = {}
        combined_json = []
        
        for table in tables:
            st.write(f"### {table} 테이블 검색 결과")
            df, json_data = search_data_from_table(table, keyword=keyword, start_date=start_date_str, end_date=end_date_str, db_config=db_config, search_type=search_type)

            if not df.empty:
                # Apply keyword highlighting and remove newlines
                highlighted_df = highlight_keywords_in_dataframe(df, keyword, search_type)
                st.write(highlighted_df.to_html(escape=False, index=False), unsafe_allow_html=True)
                st.json(json.dumps(json_data, default=decimal_default, ensure_ascii=False, indent=4))
            else:
                st.warning(f"{table} 테이블에서 결과를 찾을 수 없습니다.")
else:
    # 특정 테이블을 선택하는 UI 제공
    selected_table = st.selectbox("검색할 테이블을 선택하세요", tables)

    if st.button(f"{selected_table} 테이블 검색"):
        df, json_data = search_data_from_table(selected_table, keyword=keyword, start_date=start_date_str, end_date=end_date_str, db_config=db_config, search_type=search_type)
        
        if not df.empty:
            st.write(f"### {selected_table} 테이블 검색 결과")
            # Apply keyword highlighting and remove newlines
            highlighted_df = highlight_keywords_in_dataframe(df, keyword, search_type)
            st.write(highlighted_df.to_html(escape=False, index=False), unsafe_allow_html=True)
            st.json(json.dumps(json_data, default=decimal_default, ensure_ascii=False, indent=4))
        else:
            st.warning(f"{selected_table} 테이블에서 결과를 찾을 수 없습니다.")