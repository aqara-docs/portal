import streamlit as st
import os
import markdown
from datetime import datetime
from pathlib import Path

def read_markdown_file(markdown_file):
    """마크다운 파일을 읽어서 텍스트로 반환"""
    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def save_markdown_file(content, file_path):
    """마크다운 파일 저장"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return False

def main():
    st.title("Markdown File Editor")

    # 세션 상태 초기화
    if 'file_path' not in st.session_state:
        st.session_state['file_path'] = None
    if 'content' not in st.session_state:
        st.session_state['content'] = ""

    # 파일 업로더 추가
    uploaded_file = st.file_uploader("마크다운 파일을 선택하세요", type=['md', 'markdown'])

    if uploaded_file is not None:
        # 파일 경로 저장
        file_path = os.path.join("temp", uploaded_file.name)
        os.makedirs("temp", exist_ok=True)
        
        # 새로운 파일이 업로드되었을 때만 내용 업데이트
        if st.session_state['file_path'] != file_path:
            st.session_state['file_path'] = file_path
            st.session_state['content'] = uploaded_file.read().decode('utf-8')
            
            # 임시 파일로 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(st.session_state['content'])

        # 편집 영역
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Edit Content")
            edited_content = st.text_area(
                "Edit markdown content:",
                value=st.session_state['content'],
                height=400
            )

            if st.button("Save Changes"):
                if save_markdown_file(edited_content, file_path):
                    st.success("파일이 저장되었습니다!")
                    st.session_state['content'] = edited_content
                    
                    # 다운로드 버튼 제공
                    st.download_button(
                        label="Download edited file",
                        data=edited_content,
                        file_name=uploaded_file.name,
                        mime="text/markdown"
                    )

        with col2:
            st.markdown("### Preview")
            st.markdown(edited_content)

        # 파일 정보 표시
        st.sidebar.markdown("---")
        st.sidebar.write("파일 정보:")
        st.sidebar.write(f"- 파일명: {uploaded_file.name}")
        st.sidebar.write(f"- 크기: {len(edited_content):,} bytes")
        
        # 마지막 수정 시간 표시
        if os.path.exists(file_path):
            mod_time = os.path.getmtime(file_path)
            st.sidebar.write(f"- 마지막 수정: {datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')}")

        # 검색 기능
        search_term = st.sidebar.text_input("내용 검색:")
        if search_term:
            lines = edited_content.split('\n')
            matched_lines = [line for line in lines if search_term.lower() in line.lower()]
            if matched_lines:
                st.sidebar.markdown("### 검색 결과:")
                for line in matched_lines:
                    st.sidebar.write(line)

if __name__ == "__main__":
    main()