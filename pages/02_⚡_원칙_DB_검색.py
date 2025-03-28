import streamlit as st
import pandas as pd
import mysql.connector
import json
import re
import html
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="아카라라이프 원칙 검색",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MySQL Database configuration
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# 원칙 DB 테이블 리스트
principles_tables = [
    'principles', 
    'sub_principles', 
    'action_items', 
    'introduction', 
    'summary'
]

# 스타일 적용
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: 700;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #2563EB;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .card {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #3B82F6;
    }
    .principle-title {
        font-size: 1.3rem;
        color: #1F2937;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .sub-principle-title {
        font-size: 1.1rem;
        color: #1F2937;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        background-color: #E5E7EB;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .action-item {
        background-color: #EFF6FF;
        border-radius: 5px;
        padding: 0.8rem;
        margin-top: 0.5rem;
        border-left: 3px solid #60A5FA;
        color: #1F2937;
    }
    mark {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.1rem 0.2rem;
        border-radius: 3px;
    }
    .search-container {
        background-color: #F3F4F6;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        border: 1px solid #D1D5DB;
    }
    .result-count {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1rem;
        font-weight: 500;
    }
    .no-results {
        text-align: center;
        padding: 2rem;
        color: #6B7280;
        font-size: 1.2rem;
    }
    .intro-text {
        background-color: #EFF6FF;
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        border: 1px solid #BFDBFE;
        color: #1E3A8A;
        font-style: italic;
    }
    .summary-item {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.8rem;
        border-left: 4px solid #3B82F6;
    }
    .summary-title {
        font-weight: 600;
        color: #1F2937;
        margin-bottom: 0.5rem;
    }
    .summary-text {
        color: #1F2937;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2563EB;
    }
    .metric-label {
        color: #1F2937;
        font-size: 0.9rem;
    }
    .search-container {
        background-color: #F3F4F6;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        border: 1px solid #D1D5DB;
    }
    .search-title {
        font-size: 1.5rem;
        color: #1F2937;
        margin-bottom: 1rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

def get_actual_columns(table_name, db_config):
    """테이블의 실제 컬럼명을 가져옵니다."""
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

def search_principles_data(table_name, keyword=None, db_config=None, search_type="AND"):
    """원칙 DB의 특정 테이블에서 키워드로 데이터를 검색합니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 테이블의 실제 컬럼 가져오기
        actual_columns = get_actual_columns(table_name, db_config)
        query = f"SELECT * FROM {table_name} WHERE 1=1"
        filters = []

        if keyword:
            keyword_conditions = []
            keywords = keyword.split()  # 키워드를 AND/OR 검색을 위해 분리

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
                    else:  # OR 검색
                        keyword_conditions.append(" OR ".join([f"{col} LIKE %s" for _ in keywords]))
                query += " AND (" + " OR ".join(keyword_conditions) + ")"
                filters.extend([f'%{k}%' for k in keywords] * len(actual_columns))

        cursor.execute(query, tuple(filters))
        rows = cursor.fetchall()

        # 커서와 연결 닫기
        cursor.close()
        conn.close()

        # datetime 객체를 JSON 직렬화를 위해 문자열로 변환
        for row in rows:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.strftime('%Y-%m-%d %H:%M:%S')

        return pd.DataFrame(rows), rows
    except mysql.connector.Error as err:
        st.error(f"Error querying table {table_name}: {err}")
        return pd.DataFrame(), []

def highlight_keywords(text, keyword, search_type="AND"):
    """검색 유형에 따라 텍스트에서 키워드를 강조 표시합니다."""
    if not keyword or not text:
        return text

    # 텍스트 정리 및 이스케이프, 줄바꿈 제거
    text = html.escape(str(text)).replace("\n", " ").replace("\t", " ")

    if search_type == "Exact Match":
        # 정확한 일치를 위해 전체 키워드 구문 이스케이프
        escaped_keyword = re.escape(keyword.strip())
        highlighted = f"<mark>{keyword.strip()}</mark>"
        text = re.sub(f"({escaped_keyword})", highlighted, text, flags=re.IGNORECASE)
    else:
        # AND/OR 검색을 위한 개별 단어 강조
        keywords = keyword.split()
        for word in keywords:
            escaped_word = re.escape(word)
            highlighted = f"<mark>{word}</mark>"
            text = re.sub(f"({escaped_word})", highlighted, text, flags=re.IGNORECASE)

    return text

def highlight_keywords_in_dataframe(df, keyword, search_type="AND"):
    """DataFrame의 모든 텍스트 열에 키워드 강조를 적용합니다."""
    if not keyword:
        return df

    # 원본을 수정하지 않기 위해 DataFrame 복사
    highlighted_df = df.copy()

    # 모든 객체(텍스트) 열에 강조 적용 및 줄바꿈 제거
    for col in highlighted_df.select_dtypes(include=['object']).columns:
        highlighted_df[col] = highlighted_df[col].apply(lambda x: highlight_keywords(x, keyword, search_type))

    return highlighted_df

def get_joined_principles_data(keyword=None, search_type="AND"):
    """원칙, 세부 원칙, 실행 항목을 조인하여 계층적 데이터를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 기본 원칙 데이터 쿼리
        principles_query = """
        SELECT 
            p.principle_id, 
            p.principle_number, 
            p.principle_title,
            sp.sub_principle_id,
            sp.sub_principle_number,
            sp.sub_principle_title,
            ai.action_item_id,
            ai.action_item_text
        FROM 
            principles p
        LEFT JOIN 
            sub_principles sp ON p.principle_id = sp.principle_id
        LEFT JOIN 
            action_items ai ON sp.sub_principle_id = ai.sub_principle_id
        """
        
        # 요약 데이터 쿼리
        summary_query = """
        SELECT 
            NULL as principle_id,
            999 as principle_number, 
            '요약' as principle_title,
            NULL as sub_principle_id,
            'S' as sub_principle_number,
            s.summary_title as sub_principle_title,
            NULL as action_item_id,
            s.summary_text as action_item_text
        FROM 
            summary s
        """
        
        # 서문 데이터 쿼리
        intro_query = """
        SELECT 
            NULL as principle_id,
            998 as principle_number, 
            '서문' as principle_title,
            NULL as sub_principle_id,
            'I' as sub_principle_number,
            '서문' as sub_principle_title,
            NULL as action_item_id,
            i.intro_text as action_item_text
        FROM 
            introduction i
        """
        
        # 키워드 검색 조건 추가
        if keyword:
            if search_type == "AND":
                conditions = []
                for word in keyword.split():
                    principles_conditions = f"""
                    (
                        p.principle_title LIKE '%{word}%' OR
                        sp.sub_principle_title LIKE '%{word}%' OR
                        ai.action_item_text LIKE '%{word}%'
                    )
                    """
                    summary_conditions = f"""
                    (
                        s.summary_title LIKE '%{word}%' OR
                        s.summary_text LIKE '%{word}%'
                    )
                    """
                    intro_conditions = f"i.intro_text LIKE '%{word}%'"
                    
                    conditions.append(principles_conditions)
                    
                principles_query += " WHERE " + " AND ".join(conditions)
                summary_query += " WHERE " + " AND ".join([f"(s.summary_title LIKE '%{word}%' OR s.summary_text LIKE '%{word}%')" for word in keyword.split()])
                intro_query += " WHERE " + " AND ".join([f"i.intro_text LIKE '%{word}%'" for word in keyword.split()])
                
            elif search_type == "OR":
                words = keyword.split()
                principles_conditions = []
                summary_conditions = []
                intro_conditions = []
                
                for word in words:
                    principles_conditions.extend([
                        f"p.principle_title LIKE '%{word}%'",
                        f"sp.sub_principle_title LIKE '%{word}%'",
                        f"ai.action_item_text LIKE '%{word}%'"
                    ])
                    
                    summary_conditions.extend([
                        f"s.summary_title LIKE '%{word}%'",
                        f"s.summary_text LIKE '%{word}%'"
                    ])
                    
                    intro_conditions.append(f"i.intro_text LIKE '%{word}%'")
                
                principles_query += f" WHERE ({' OR '.join(principles_conditions)})"
                summary_query += f" WHERE ({' OR '.join(summary_conditions)})"
                intro_query += f" WHERE ({' OR '.join(intro_conditions)})"
                
            else:  # Exact Match
                principles_query += f"""
                WHERE (
                    p.principle_title LIKE '%{keyword}%' OR
                    sp.sub_principle_title LIKE '%{keyword}%' OR
                    ai.action_item_text LIKE '%{keyword}%'
                )
                """
                summary_query += f"""
                WHERE (
                    s.summary_title LIKE '%{keyword}%' OR
                    s.summary_text LIKE '%{keyword}%'
                )
                """
                intro_query += f"WHERE i.intro_text LIKE '%{keyword}%'"
        
        # 모든 쿼리 결합
        combined_query = f"""
        {principles_query}
        UNION ALL
        {summary_query}
        UNION ALL
        {intro_query}
        ORDER BY principle_number, sub_principle_number
        """
        
        cursor.execute(combined_query)
        rows = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return pd.DataFrame(rows), rows
    except mysql.connector.Error as err:
        st.error(f"Error fetching joined principles data: {err}")
        return pd.DataFrame(), []

def get_introduction_text():
    """서문 텍스트를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT intro_text FROM introduction LIMIT 1")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result['intro_text'] if result else ""
    except mysql.connector.Error as err:
        st.error(f"Error fetching introduction: {err}")
        return ""

def get_summary_data():
    """요약 데이터를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT summary_title, summary_text FROM summary")
        rows = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return pd.DataFrame(rows), rows
    except mysql.connector.Error as err:
        st.error(f"Error fetching summary data: {err}")
        return pd.DataFrame(), []

def get_principles_stats():
    """원칙 데이터의 통계 정보를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 원칙 수
        cursor.execute("SELECT COUNT(*) as count FROM principles")
        principles_count = cursor.fetchone()['count']
        
        # 세부 원칙 수
        cursor.execute("SELECT COUNT(*) as count FROM sub_principles")
        sub_principles_count = cursor.fetchone()['count']
        
        # 실행 항목 수
        cursor.execute("SELECT COUNT(*) as count FROM action_items")
        action_items_count = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return {
            'principles_count': principles_count,
            'sub_principles_count': sub_principles_count,
            'action_items_count': action_items_count
        }
    except mysql.connector.Error as err:
        st.error(f"Error fetching principles stats: {err}")
        return None

# 메인 헤더
st.markdown('<h1 class="main-header">아카라라이프 신사업실 일의 원칙 검색 시스템</h1>', unsafe_allow_html=True)

# 검색 기능을 메인 화면으로 이동
st.markdown('<div class="search-container">', unsafe_allow_html=True)
st.markdown('<div class="search-title">🔍 원칙 검색</div>', unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    keyword = st.text_input("키워드 입력", placeholder="검색어를 입력하세요...")
with col2:
    search_type = st.radio("검색 방식", ["AND", "OR", "Exact Match"], 
                          help="AND: 모든 단어 포함, OR: 하나 이상의 단어 포함, Exact Match: 정확한 구문 일치")

st.markdown('</div>', unsafe_allow_html=True)

# 탭 설정
tab1, tab2, tab3 = st.tabs(["원칙 개요", "검색 결과", "원칙 계층적 보기"])

with tab1:
    st.markdown('<h2 class="sub-header">원칙 개요</h2>', unsafe_allow_html=True)
    
    # 서문 표시
    intro_text = get_introduction_text()
    if intro_text:
        st.markdown('<h3 class="sub-header">서문</h3>', unsafe_allow_html=True)
        st.markdown(f'<div class="intro-text">{intro_text}</div>', unsafe_allow_html=True)
    
    # 요약 표시
    summary_df, summary_data = get_summary_data()
    if not summary_df.empty:
        st.markdown('<h3 class="sub-header">원칙 요약</h3>', unsafe_allow_html=True)
        
        for _, row in summary_df.iterrows():
            st.markdown(f"""
            <div class="summary-item">
                <div class="summary-title">{row['summary_title']}</div>
                <div class="summary-text">{row['summary_text']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # 통계 정보 표시
    stats = get_principles_stats()
    if stats:
        st.markdown('<h3 class="sub-header">원칙 통계</h3>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['principles_count']}</div>
                <div class="metric-label">원칙 수</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['sub_principles_count']}</div>
                <div class="metric-label">세부 원칙 수</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['action_items_count']}</div>
                <div class="metric-label">실행 항목 수</div>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    if keyword:
        st.markdown('<h2 class="sub-header">검색 결과</h2>', unsafe_allow_html=True)
        
        # 조인된 데이터에서 검색
        df, json_data = get_joined_principles_data(keyword, search_type)
        
        if not df.empty:
            # 결과 수 표시
            st.markdown(f'<div class="result-count">총 {len(df)} 개의 결과를 찾았습니다.</div>', unsafe_allow_html=True)
            
            # 계층적으로 결과 표시
            current_principle = None
            current_sub_principle = None
            
            for _, row in df.iterrows():
                # 새로운 원칙인 경우
                if current_principle != row['principle_number']:
                    # 이전 원칙 카드 닫기
                    if current_principle is not None:
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    current_principle = row['principle_number']
                    st.markdown(f"""
                    <div class="card">
                        <div class="principle-title">{row['principle_number']}. {highlight_keywords(row['principle_title'], keyword, search_type)}</div>
                    """, unsafe_allow_html=True)
                
                # 새로운 세부 원칙인 경우
                if current_sub_principle != row['sub_principle_number']:
                    current_sub_principle = row['sub_principle_number']
                    st.markdown(f"""
                    <div class="sub-principle-title">{row['sub_principle_number']} {highlight_keywords(row['sub_principle_title'], keyword, search_type)}</div>
                    """, unsafe_allow_html=True)
                
                # 실행 항목이 있는 경우
                if pd.notna(row['action_item_text']):
                    st.markdown(f"""
                    <div class="action-item">{highlight_keywords(row['action_item_text'], keyword, search_type)}</div>
                    """, unsafe_allow_html=True)
            
            # 마지막 원칙 카드 닫기
            if current_principle is not None:
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="no-results">검색 결과가 없습니다.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<h2 class="sub-header">검색 결과</h2>', unsafe_allow_html=True)
        st.info("상단의 검색창에서 검색어를 입력하세요.")

with tab3:
    st.markdown('<h2 class="sub-header">원칙 계층적 보기</h2>', unsafe_allow_html=True)
    
    # 모든 원칙 데이터 가져오기
    df, _ = get_joined_principles_data()
    
    if not df.empty:
        # 원칙별로 그룹화하여 표시
        principles_grouped = df.groupby(['principle_number', 'principle_title'])
        
        for (principle_num, principle_title), principle_group in principles_grouped:
            with st.expander(f"{principle_num}. {principle_title}"):
                # 세부 원칙별로 그룹화
                sub_principles_grouped = principle_group.groupby(['sub_principle_number', 'sub_principle_title'])
                
                for (sub_num, sub_title), sub_group in sub_principles_grouped:
                    st.markdown(f"""
                    <div class="sub-principle-title">{sub_num} {sub_title}</div>
                    """, unsafe_allow_html=True)
                    
                    # 실행 항목 표시
                    for _, row in sub_group.iterrows():
                        if pd.notna(row['action_item_text']):
                            st.markdown(f"""
                            <div class="action-item">{row['action_item_text']}</div>
                            """, unsafe_allow_html=True)
    else:
        st.warning("데이터를 불러올 수 없습니다.")

# 검색어가 입력되면 자동으로 검색 결과 탭으로 이동
if keyword:
    tab2.selectbox = True 