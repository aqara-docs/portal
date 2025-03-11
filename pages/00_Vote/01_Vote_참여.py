import streamlit as st

def show_vote_sidebar():
    """Vote 관련 사이드바 메뉴 표시"""
    with st.sidebar:
        st.write("## 📊 Vote 시스템")
        
        selected = st.radio(
            "메뉴 선택",
            ["투표 문제 등록", "투표 참여", "투표 결과"],
            key="vote_menu"
        )
        
        # 선택된 메뉴에 따라 페이지 이동
        if selected == "투표 문제 등록":
            st.page_link("pages/00_Vote/00_Question_등록.py", label="투표 문제 등록")
        elif selected == "투표 참여":
            st.page_link("pages/00_Vote/01_Vote_참여.py", label="투표 참여")
        elif selected == "투표 결과":
            st.page_link("pages/00_Vote/02_Vote_결과.py", label="투표 결과")
        
        st.divider()
        return selected

def main():
    selected_menu = show_vote_sidebar()
    
    if selected_menu == "투표 참여":
        st.title("투표 참여")
        # ... (기존 코드) 