import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="아카라라이프 미션 & 비전",
    page_icon="🚀",
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

# 스타일 적용
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 700;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #2563EB;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .mission-card {
        background-color: #EFF6FF;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-left: 5px solid #3B82F6;
    }
    .vision-card {
        background-color: #F0FDF4;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-left: 5px solid #10B981;
    }
    .mission-title {
        font-size: 1.5rem;
        color: #1F2937;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .vision-title {
        font-size: 1.5rem;
        color: #1F2937;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .mission-text, .vision-text {
        font-size: 1.1rem;
        color: #1F2937;
        line-height: 1.6;
    }
    .objective-category {
        font-size: 1.3rem;
        color: #1F2937;
        font-weight: 600;
        margin-top: 1.2rem;
        margin-bottom: 0.8rem;
        background-color: #F3F4F6;
        padding: 0.5rem 1rem;
        border-radius: 5px;
    }
    .objective-item {
        background-color: #F9FAFB;
        border-radius: 5px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #6B7280;
        font-size: 1rem;
        color: #1F2937;
    }
    .value-card {
        background-color: #FEF3C7;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border-left: 5px solid #F59E0B;
    }
    .value-title {
        font-size: 1.2rem;
        color: #1F2937;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .value-description {
        font-size: 1rem;
        color: #1F2937;
        white-space: pre-line;
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
    mark {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.1rem 0.2rem;
        border-radius: 3px;
    }
    .no-results {
        text-align: center;
        padding: 2rem;
        background-color: #F3F4F6;
        border-radius: 10px;
        color: #4B5563;
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# 데이터 가져오기 함수
def get_mission_vision_data():
    """미션 & 비전 데이터를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM mission_vision LIMIT 1")
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        return data
    except mysql.connector.Error as err:
        st.error(f"미션 & 비전 데이터 조회 중 오류 발생: {err}")
        return None

def get_key_objectives_data():
    """핵심 목표 데이터를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM key_objectives ORDER BY category, sort_order")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except mysql.connector.Error as err:
        st.error(f"핵심 목표 데이터 조회 중 오류 발생: {err}")
        return []

def get_core_values_data():
    """핵심 가치 데이터를 가져옵니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM core_values ORDER BY sort_order")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except mysql.connector.Error as err:
        st.error(f"핵심 가치 데이터 조회 중 오류 발생: {err}")
        return []

def search_mission_vision_data(keyword):
    """미션 & 비전 데이터에서 키워드를 검색합니다."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 미션 & 비전 검색
        cursor.execute("""
        SELECT * FROM mission_vision 
        WHERE mission_text LIKE %s OR vision_text LIKE %s
        LIMIT 1
        """, (f'%{keyword}%', f'%{keyword}%'))
        mission_vision_data = cursor.fetchone()
        
        # 핵심 목표 검색
        cursor.execute("""
        SELECT * FROM key_objectives 
        WHERE category LIKE %s OR objective_text LIKE %s
        ORDER BY category, sort_order
        """, (f'%{keyword}%', f'%{keyword}%'))
        key_objectives_data = cursor.fetchall()
        
        # 핵심 가치 검색
        cursor.execute("""
        SELECT * FROM core_values 
        WHERE value_title LIKE %s OR value_description LIKE %s
        ORDER BY sort_order
        """, (f'%{keyword}%', f'%{keyword}%'))
        core_values_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'mission_vision': mission_vision_data,
            'key_objectives': key_objectives_data,
            'core_values': core_values_data
        }
    except mysql.connector.Error as err:
        st.error(f"검색 중 오류 발생: {err}")
        return {
            'mission_vision': None,
            'key_objectives': [],
            'core_values': []
        }

def highlight_text(text, keyword):
    """텍스트에서 키워드를 강조 표시합니다."""
    if not keyword or not text:
        return text
    
    # 키워드를 강조 표시
    highlighted_text = text.replace(keyword, f"<mark>{keyword}</mark>")
    return highlighted_text

# 메인 헤더
st.markdown('<h1 class="main-header">아카라라이프 신사업실 미션 & 비전</h1>', unsafe_allow_html=True)

# 검색 기능
st.markdown('<div class="search-container">', unsafe_allow_html=True)
st.markdown('<div class="search-title">🔍 미션 & 비전 검색</div>', unsafe_allow_html=True)
keyword = st.text_input("키워드 입력", placeholder="검색어를 입력하세요...")
st.markdown('</div>', unsafe_allow_html=True)

# 탭 설정
tab1, tab2, tab3 = st.tabs(["미션 & 비전", "핵심 목표", "핵심 가치"])

# 검색 결과 또는 전체 데이터 표시
if keyword:
    search_results = search_mission_vision_data(keyword)
    
    with tab1:
        st.markdown('<h2 class="sub-header">미션 & 비전</h2>', unsafe_allow_html=True)
        
        mission_vision_data = search_results['mission_vision']
        if mission_vision_data:
            # 미션 카드
            st.markdown(f"""
            <div class="mission-card">
                <div class="mission-title">미션 (Mission)</div>
                <div class="mission-text">{highlight_text(mission_vision_data['mission_text'], keyword)}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 비전 카드
            st.markdown(f"""
            <div class="vision-card">
                <div class="vision-title">비전 (Vision)</div>
                <div class="vision-text">{highlight_text(mission_vision_data['vision_text'], keyword)}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="no-results">검색 결과가 없습니다.</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<h2 class="sub-header">핵심 목표 (Key Objectives)</h2>', unsafe_allow_html=True)
        
        key_objectives_data = search_results['key_objectives']
        if key_objectives_data:
            # 카테고리별로 그룹화
            categories = {}
            for obj in key_objectives_data:
                if obj['category'] not in categories:
                    categories[obj['category']] = []
                categories[obj['category']].append(obj)
            
            # 카테고리별로 표시
            for category, objectives in categories.items():
                st.markdown(f'<div class="objective-category">{highlight_text(category, keyword)}</div>', unsafe_allow_html=True)
                
                for obj in objectives:
                    st.markdown(f"""
                    <div class="objective-item">{highlight_text(obj['objective_text'], keyword)}</div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="no-results">검색 결과가 없습니다.</div>', unsafe_allow_html=True)
    
    with tab3:
        st.markdown('<h2 class="sub-header">핵심 가치 (Core Values)</h2>', unsafe_allow_html=True)
        
        core_values_data = search_results['core_values']
        if core_values_data:
            for value in core_values_data:
                st.markdown(f"""
                <div class="value-card">
                    <div class="value-title">{highlight_text(value['value_title'], keyword)}</div>
                    <div class="value-description">{highlight_text(value['value_description'], keyword)}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="no-results">검색 결과가 없습니다.</div>', unsafe_allow_html=True)
else:
    # 전체 데이터 표시
    mission_vision_data = get_mission_vision_data()
    key_objectives_data = get_key_objectives_data()
    core_values_data = get_core_values_data()
    
    with tab1:
        st.markdown('<h2 class="sub-header">미션 & 비전</h2>', unsafe_allow_html=True)
        
        if mission_vision_data:
            # 미션 카드
            st.markdown(f"""
            <div class="mission-card">
                <div class="mission-title">미션 (Mission)</div>
                <div class="mission-text">{mission_vision_data['mission_text']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 비전 카드
            st.markdown(f"""
            <div class="vision-card">
                <div class="vision-title">비전 (Vision)</div>
                <div class="vision-text">{mission_vision_data['vision_text']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("미션 & 비전 데이터가 없습니다. 관리자 페이지에서 데이터를 추가해주세요.")
    
    with tab2:
        st.markdown('<h2 class="sub-header">핵심 목표 (Key Objectives)</h2>', unsafe_allow_html=True)
        
        if key_objectives_data:
            # 카테고리별로 그룹화
            categories = {}
            for obj in key_objectives_data:
                if obj['category'] not in categories:
                    categories[obj['category']] = []
                categories[obj['category']].append(obj)
            
            # 카테고리별로 표시
            for category, objectives in categories.items():
                st.markdown(f'<div class="objective-category">{category}</div>', unsafe_allow_html=True)
                
                for obj in objectives:
                    st.markdown(f"""
                    <div class="objective-item">{obj['objective_text']}</div>
                    """, unsafe_allow_html=True)
        else:
            st.info("핵심 목표 데이터가 없습니다. 관리자 페이지에서 데이터를 추가해주세요.")
    
    with tab3:
        st.markdown('<h2 class="sub-header">핵심 가치 (Core Values)</h2>', unsafe_allow_html=True)
        
        if core_values_data:
            for value in core_values_data:
                st.markdown(f"""
                <div class="value-card">
                    <div class="value-title">{value['value_title']}</div>
                    <div class="value-description">{value['value_description']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("핵심 가치 데이터가 없습니다. 관리자 페이지에서 데이터를 추가해주세요.") 