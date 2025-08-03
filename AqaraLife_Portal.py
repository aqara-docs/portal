import streamlit as st
from PIL import Image
import os
import base64


st.set_page_config(
    page_title="AqaraLife",
    page_icon="👋",
)

# 🔥 사이드바 맨 위에 로고를 강제로 배치하는 함수
def display_logo_at_top():
    logo_path = "아카라라이프로고.jpg"
    
    try:
        if os.path.exists(logo_path):
            # Streamlit 기본 이미지 표시
            logo = Image.open(logo_path)
            st.sidebar.image(logo, width=150)
            
            # CSS로 로고를 맨 위에 고정
            st.sidebar.markdown("""
            <style>
                /* 여러 Streamlit 버전 호환 CSS */
                [data-testid="stSidebar"] .stImage:first-child,
                .css-1d391kg .stImage:first-child,
                .stSidebar .stImage:first-child {
                    order: -999 !important;
                    margin-top: 10px !important;
                }
                
                /* 사이드바 전체 스타일 조정 */
                [data-testid="stSidebar"] > div:first-child {
                    padding-top: 0 !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
            st.sidebar.markdown("---")
            return True
            
        else:
            st.sidebar.error(f"로고 파일을 찾을 수 없습니다: {logo_path}")
            st.sidebar.info(f"현재 작업 디렉토리: {os.getcwd()}")
            return False
            
    except Exception as e:
        st.sidebar.error(f"로고 로딩 중 오류 발생: {str(e)}")
        st.sidebar.info(f"오류 유형: {type(e).__name__}")
        return False

# 메인 화면에 로고 표시 함수
def display_main_logo():
    logo_path = "아카라라이프로고.jpg"
    
    try:
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            # 메인 화면 중앙에 로고 표시 (적절한 크기로)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(logo, width=300)
            return True
        else:
            st.error(f"메인 로고 파일을 찾을 수 없습니다: {logo_path}")
            return False
    except Exception as e:
        st.error(f"메인 로고 로딩 중 오류: {str(e)}")
        return False

# 로고를 가장 먼저 표시
logo_displayed = display_logo_at_top()

# 메인 페이지 제목
st.write("# &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;아카라라이프 포털!  🤖📱 🏡😊 ")
st.write("## &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;&nbsp;&nbsp; 스마트 하게, 우리 삶을 더 행복하게")

# 메인 화면에 로고 표시
st.markdown("---")  # 구분선
display_main_logo()
st.markdown("---")  # 구분선

# 사이드바 메뉴 안내
st.sidebar.success("업무 관련 메뉴를 선택하세요!!")

st.markdown(
    """
    
"""
)