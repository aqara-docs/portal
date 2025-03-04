import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="주간업무 뷰어", page_icon="📊", layout="wide")

def connect_to_db():
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
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

def get_week_dates(selected_date=None):
    if selected_date is None:
        selected_date = datetime.now()
    else:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d')
    
    # 선택된 날짜의 월요일 찾기
    monday = selected_date - timedelta(days=selected_date.weekday())
    # 해당 주의 금요일
    friday = monday + timedelta(days=4)
    
    # 시간을 00:00:00으로 설정
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    friday = friday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return monday, friday

def get_weekly_report(monday, friday):
    conn = connect_to_db()
    if not conn:
        return None
    
    try:
        # 선택된 주의 업무 데이터 가져오기 (daily)
        last_week_query = """
        WITH numbered_rows AS (
            SELECT 담당자,
                   업무일지,
                   진행현황,
                   ROW_NUMBER() OVER (PARTITION BY 담당자 ORDER BY id) as row_num,
                   일자
            FROM newbiz_daily
            WHERE DATE(일자) BETWEEN DATE(%s) AND DATE(%s)
        )
        SELECT 담당자,
               GROUP_CONCAT(
                   CONCAT(row_num, '. ', IFNULL(업무일지, ''))
                   ORDER BY 일자, row_num
                   SEPARATOR '\n'
               ) as 전주업무,
               GROUP_CONCAT(
                   CONCAT(row_num, '. ', IFNULL(진행현황, ''))
                   ORDER BY 일자, row_num
                   SEPARATOR '\n'
               ) as 진행상황
        FROM numbered_rows
        GROUP BY 담당자
        """
        
        # daily 테이블에서 데이터 조회
        df_last_week = pd.read_sql(last_week_query, conn, params=(monday, friday))
        
        # daily 테이블에 데이터가 없으면 weekly 테이블에서 이전 주 데이터 조회
        if df_last_week.empty:
            last_week_from_weekly_query = """
            WITH numbered_rows AS (
                SELECT 담당자,
                       금주업무,
                       완료일정,  -- 진행현황 대신 완료일정
                       ROW_NUMBER() OVER (PARTITION BY 담당자 ORDER BY id) as row_num
                FROM newbiz_weekly
                WHERE DATE(일자) = DATE(%s)  -- 이전 주 월요일
            )
            SELECT 담당자,
                   GROUP_CONCAT(
                       CONCAT(row_num, '. ', IFNULL(금주업무, ''))
                       ORDER BY row_num
                       SEPARATOR '\n'
                   ) as 전주업무,
                   GROUP_CONCAT(
                       CONCAT(row_num, '. ', 
                             CASE 
                                 WHEN 완료일정 REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                                 THEN DATE_FORMAT(STR_TO_DATE(LEFT(완료일정, 10), '%Y-%m-%d'), '%Y.%m.%d')
                                 WHEN 완료일정 REGEXP '^[0-9]{4}.[0-9]{2}.[0-9]{2}'
                                 THEN LEFT(완료일정, 10)
                                 ELSE IFNULL(완료일정, '')
                             END)
                       ORDER BY row_num
                       SEPARATOR '\n'
                   ) as 진행상황
            FROM numbered_rows
            GROUP BY 담당자
            """
            # 이전 주 월요일 계산
            last_monday = monday - timedelta(days=7)
            df_last_week = pd.read_sql(last_week_from_weekly_query, conn, params=(last_monday,))

        # 현재 주의 계획 데이터 가져오기 (weekly)
        this_week_query = """
        WITH numbered_rows AS (
            SELECT 담당자,
                   금주업무,
                   완료일정,
                   비고,
                   ROW_NUMBER() OVER (PARTITION BY 담당자 ORDER BY id) as row_num
            FROM newbiz_weekly
            WHERE DATE(일자) = DATE(%s)
        )
        SELECT 담당자,
               GROUP_CONCAT(
                   CONCAT(row_num, '. ', IFNULL(금주업무, ''))
                   ORDER BY row_num
                   SEPARATOR '\n'
               ) as 금주업무,
               GROUP_CONCAT(
                   CONCAT(row_num, '. ', 
                         CASE 
                             WHEN 완료일정 REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                             THEN DATE_FORMAT(STR_TO_DATE(LEFT(완료일정, 10), '%Y-%m-%d'), '%Y.%m.%d')
                             WHEN 완료일정 REGEXP '^[0-9]{4}.[0-9]{2}.[0-9]{2}'
                             THEN LEFT(완료일정, 10)
                             ELSE IFNULL(완료일정, '')
                         END)
                   ORDER BY row_num
                   SEPARATOR '\n'
               ) as 완료일정,
               GROUP_CONCAT(
                   CONCAT(row_num, '. ', IFNULL(비고, ''))
                   ORDER BY row_num
                   SEPARATOR '\n'
               ) as 비고
        FROM numbered_rows
        GROUP BY 담당자
        """
        
        # 현재 주 데이터 조회
        df_this_week = pd.read_sql(this_week_query, conn, params=(monday,))
        
        # 데이터 병합 전 담당자 컬럼 정리
        df_last_week['담당자'] = df_last_week['담당자'].str.strip()
        df_this_week['담당자'] = df_this_week['담당자'].str.strip()
        
        # 데이터 병합
        df_combined = pd.merge(df_last_week, df_this_week, on='담당자', how='outer')
        
        return df_combined
        
    except Exception as e:
        st.error(f"데이터 조회 오류: {e}")
        return None
    finally:
        conn.close()

def main():
    st.title("📊 주간 업무 현황")
    
    # 날짜 선택 위젯 추가
    today = datetime.now()
    default_date = today - timedelta(days=today.weekday())  # 이번주 월요일
    min_date = default_date - timedelta(weeks=52)  # 52주 전까지 선택 가능
    max_date = default_date + timedelta(weeks=52)  # 52주 후까지 선택 가능
    
    selected_date = st.date_input(
        "조회할 주간 선택",
        value=default_date,
        min_value=min_date,
        max_value=max_date,
        help="원하는 주의 아무 날짜나 선택하세요. 해당 주의 업무가 표시됩니다."
    )
    
    # 선택된 날짜의 주간 정보 가져오기
    monday, friday = get_week_dates(selected_date.strftime('%Y-%m-%d'))
    
    # 날짜 정보를 더 눈에 띄게 표시
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📅 주간 업무 기간: {monday.strftime('%Y.%m.%d')} ~ {friday.strftime('%Y.%m.%d')}")
    with col2:
        st.info(f"📅 작성일: {monday.strftime('%Y.%m.%d')}")

    # get_weekly_report 함수 호출 시 선택된 날짜 전달
    df_report = get_weekly_report(monday, friday)
    
    if df_report is not None and not df_report.empty:
        # 담당자 목록 생성
        all_담당자 = ['전체'] + sorted(df_report['담당자'].str.strip().unique().tolist())
        selected_담당자 = st.selectbox('담당자 선택', all_담당자, key='담당자_선택')
        
        # 스타일 설정
        st.markdown("""
        <style>
        .streamlit-expanderHeader {
            background-color: #f0f2f6;
            color: black;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .custom-textarea {
            width: 100%;
            height: 300px;  /* 150px에서 300px로 높이 증가 */
            padding: 10px;
            background-color: #f8f9fa;
            color: black;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            font-size: 14px;
            resize: none;
            white-space: pre-wrap;
            overflow-wrap: break-word;
            overflow-y: auto;  /* 세로 스크롤 추가 */
            max-height: 500px;  /* 최대 높이 설정 */
        }
        
        /* 스크롤바 스타일링 */
        .custom-textarea::-webkit-scrollbar {
            width: 8px;
        }
        
        .custom-textarea::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        
        .custom-textarea::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        
        .custom-textarea::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 데이터 컨테이너 생성
        data_container = st.container()
        
        with data_container:
            # 각 담당자별로 확장 가능한 섹션으로 표시
            for idx, row in df_report.iterrows():
                # 선택된 담당자의 데이터만 표시
                if selected_담당자 == '전체' or row['담당자'].strip() == selected_담당자.strip():
                    with st.expander(f"📋 {row['담당자']}", expanded=True):
                        col1, col2, col3, col4, col5 = st.columns([2,1,2,1,1])
                        
                        with col1:
                            st.markdown("**🔹 전주 업무**")
                            value = str(row['전주업무']) if pd.notna(row['전주업무']) else ""
                            st.markdown(f"""
                            <div class="custom-textarea">{value}</div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown("**🔸 진행상황**")
                            value = str(row['진행상황']) if pd.notna(row['진행상황']) else ""
                            st.markdown(f"""
                            <div class="custom-textarea">{value}</div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown("**📌 금주 업무**")
                            value = str(row['금주업무']) if pd.notna(row['금주업무']) else ""
                            st.markdown(f"""
                            <div class="custom-textarea">{value}</div>
                            """, unsafe_allow_html=True)
                        
                        with col4:
                            st.markdown("**📅 완료일정**")
                            value = str(row['완료일정']) if pd.notna(row['완료일정']) else ""
                            st.markdown(f"""
                            <div class="custom-textarea">{value}</div>
                            """, unsafe_allow_html=True)
                        
                        with col5:
                            st.markdown("**📝 비고**")
                            value = str(row['비고']) if pd.notna(row['비고']) else ""
                            st.markdown(f"""
                            <div class="custom-textarea">{value}</div>
                            """, unsafe_allow_html=True)
    else:
        st.warning("📢 표시할 업무 데이터가 없습니다. 데이터를 먼저 입력해주세요.")

if __name__ == "__main__":
    main()