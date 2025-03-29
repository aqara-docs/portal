import streamlit as st
import os
from datetime import datetime
from pathlib import Path
import markdown
import pdfkit
import shutil
import pandas as pd

# 기본 디렉토리 설정
ROOT_DIR = "/Users/aqaralife/Documents/Github/obsidian"

def get_subdirectories(base_path):
    """지정된 기본 경로의 모든 하위 디렉토리를 찾습니다."""
    subdirs = []
    for root, dirs, files in os.walk(base_path):
        # 숨김 폴더 제외
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for dir in dirs:
            full_path = os.path.join(root, dir)
            relative_path = os.path.relpath(full_path, base_path)
            subdirs.append(relative_path)
    return sorted(subdirs)

def ensure_upload_dir(base_dir):
    """지정된 업로드 디렉토리 생성"""
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def get_server_files(directory):
    """지정된 디렉토리의 마크다운 파일 목록 반환"""
    upload_dir = ensure_upload_dir(directory)
    files = []
    for file in os.listdir(upload_dir):
        if file.endswith(('.md', '.markdown')):
            file_path = os.path.join(upload_dir, file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            size = os.path.getsize(file_path)
            files.append({
                'name': file,
                'path': file_path,
                'modified': mod_time,
                'size': size
            })
    return sorted(files, key=lambda x: x['modified'], reverse=True)

def convert_to_pdf(markdown_content):
    """마크다운을 PDF로 변환하고 바이트 데이터 반환"""
    try:
        # 마크다운을 HTML로 변환
        html_content = markdown.markdown(markdown_content)
        
        # HTML 템플릿 생성
        html_template = f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #2c3e50; }}
                    h2 {{ color: #34495e; }}
                    p {{ line-height: 1.6; }}
                    code {{ background-color: #f7f7f7; padding: 2px 5px; }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
        </html>
        """
        
        # wkhtmltopdf 설정
        options = {
            'encoding': 'UTF-8',
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '20mm',
        }
        
        # 임시 파일 경로
        temp_dir = os.path.join(ROOT_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_html = os.path.join(temp_dir, "temp.html")
        temp_pdf = os.path.join(temp_dir, "temp.pdf")
        
        # HTML 파일 생성
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        # HTML을 PDF로 변환
        pdfkit.from_file(temp_html, temp_pdf, options=options)
        
        # PDF 파일 읽기
        with open(temp_pdf, 'rb') as pdf_file:
            pdf_data = pdf_file.read()
        
        # 임시 파일 삭제
        os.remove(temp_html)
        os.remove(temp_pdf)
        
        return pdf_data
    except Exception as e:
        st.error(f"PDF 변환 중 오류 발생: {str(e)}")
        return None

def main():
    st.title("Markdown File Editor")

    # 세션 상태 초기화
    if 'file_path' not in st.session_state:
        st.session_state['file_path'] = None
    if 'content' not in st.session_state:
        st.session_state['content'] = ""
    if 'pdf_data' not in st.session_state:
        st.session_state['pdf_data'] = None
    if 'download_format' not in st.session_state:
        st.session_state['download_format'] = 'Markdown (.md)'
    if 'current_directory' not in st.session_state:
        st.session_state['current_directory'] = "최상위"
    if 'current_file_name' not in st.session_state:
        st.session_state['current_file_name'] = None
    if 'uploaded_content' not in st.session_state:
        st.session_state['uploaded_content'] = None
    if 'selection_mode' not in st.session_state:
        st.session_state['selection_mode'] = "새 파일 업로드"

    # 파일 선택 방식
    selection_mode = st.radio(
        "파일 선택 방식",
        ["새 파일 업로드", "서버 파일 선택"],
        horizontal=True,
        index=0  # 새 파일 업로드를 기본값으로 설정
    )

    # 모든 서브디렉토리 가져오기
    subdirs = ["최상위"] + get_subdirectories(ROOT_DIR)

    if selection_mode == "서버 파일 선택":
        # 디렉토리 선택
        selected_directory = st.selectbox(
            "작업 디렉토리 선택",
            options=subdirs,
            index=subdirs.index(st.session_state['current_directory'])
        )
        
        if selected_directory != st.session_state['current_directory']:
            st.session_state['current_directory'] = selected_directory
            st.session_state['file_path'] = None
            st.session_state['content'] = ""
            st.rerun()

        current_dir = ROOT_DIR if selected_directory == "최상위" else os.path.join(ROOT_DIR, selected_directory)
        server_files = get_server_files(current_dir)
        st.info(f"현재 디렉토리: {os.path.abspath(ensure_upload_dir(current_dir))}")
        
        if not server_files:
            st.info("현재 디렉토리에 마크다운 파일이 없습니다.")
        else:
            # 파일 목록을 테이블로 표시
            files_df = pd.DataFrame(server_files)
            files_df['modified'] = files_df['modified'].dt.strftime('%Y-%m-%d %H:%M:%S')
            files_df['size'] = files_df['size'].apply(lambda x: f"{x:,} bytes")
            st.dataframe(
                files_df[['name', 'modified', 'size']],
                column_config={
                    "name": "파일명",
                    "modified": "수정일시",
                    "size": "크기"
                },
                hide_index=True
            )
            
            # 파일 선택
            selected_file = st.selectbox(
                "편집할 파일을 선택하세요",
                options=server_files,
                format_func=lambda x: x['name']
            )
            
            if selected_file:
                file_path = selected_file['path']
                if st.session_state['file_path'] != file_path:
                    st.session_state['file_path'] = file_path
                    st.session_state['current_file_name'] = selected_file['name']
                    with open(file_path, 'r', encoding='utf-8') as f:
                        st.session_state['content'] = f.read()
                    st.session_state['pdf_data'] = None
                
                # 편집 영역
                st.markdown("### Edit Content")
                edited_content = st.text_area(
                    "Edit markdown content:",
                    value=st.session_state['content'],
                    height=400
                )

                # 다운로드 섹션
                st.markdown("### Download Options")
                st.session_state['download_format'] = st.radio(
                    "다운로드 형식 선택:",
                    ('Markdown (.md)', 'PDF (.pdf)'),
                    key='format_radio'
                )

                if st.session_state['download_format'] == 'Markdown (.md)':
                    st.download_button(
                        label="Download as Markdown",
                        data=edited_content.encode('utf-8'),
                        file_name=st.session_state['current_file_name'],
                        mime="text/markdown",
                        key='download_md'
                    )
                else:
                    if st.session_state['pdf_data'] is None:
                        if st.button("Generate PDF", key='generate_pdf'):
                            with st.spinner("PDF 생성 중..."):
                                st.session_state['pdf_data'] = convert_to_pdf(edited_content)
                            if st.session_state['pdf_data'] is not None:
                                st.success("PDF 생성 완료!")
                                st.rerun()

                    if st.session_state['pdf_data'] is not None:
                        st.download_button(
                            label="Download as PDF",
                            data=st.session_state['pdf_data'],
                            file_name=f"{Path(st.session_state['current_file_name']).stem}.pdf",
                            mime="application/pdf",
                            key='download_pdf'
                        )

                # 파일 정보 표시
                st.sidebar.markdown("---")
                st.sidebar.write("파일 정보:")
                st.sidebar.write(f"- 파일명: {st.session_state['current_file_name']}")
                st.sidebar.write(f"- 크기: {len(edited_content):,} bytes")
                st.sidebar.write(f"- 저장 경로: {st.session_state['file_path']}")
                
                # 마지막 수정 시간 표시
                if os.path.exists(st.session_state['file_path']):
                    mod_time = os.path.getmtime(st.session_state['file_path'])
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

    else:
        # 새 파일 업로드 시 저장할 디렉토리 선택
        selected_directory = st.selectbox(
            "저장할 디렉토리 선택",
            options=subdirs
        )
        current_dir = ROOT_DIR if selected_directory == "최상위" else os.path.join(ROOT_DIR, selected_directory)
        
        uploaded_file = st.file_uploader("마크다운 파일을 선택하세요", type=['md', 'markdown'])
        if uploaded_file is not None:
            # 파일 내용 읽기
            content = uploaded_file.read().decode('utf-8')
            st.session_state['uploaded_content'] = content
            
            # 파일 내용 표시
            st.markdown("### 업로드된 파일 내용")
            edited_content = st.text_area(
                "Edit markdown content:",
                value=content,
                height=400
            )
            
            # 저장 버튼
            if st.button("선택한 디렉토리에 저장"):
                try:
                    file_path = os.path.join(ensure_upload_dir(current_dir), uploaded_file.name)
                    with open(file_path, "w", encoding='utf-8') as f:
                        f.write(edited_content)
                    
                    st.success(f"""
                    파일이 성공적으로 저장되었습니다!
                    - 저장 위치: {file_path}
                    """)
                    
                    # 세션 상태 업데이트
                    st.session_state['file_path'] = file_path
                    st.session_state['current_file_name'] = uploaded_file.name
                    st.session_state['content'] = edited_content
                    st.session_state['pdf_data'] = None
                    
                except Exception as e:
                    st.error(f"파일 저장 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()
