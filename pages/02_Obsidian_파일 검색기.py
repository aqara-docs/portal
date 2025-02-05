import streamlit as st
import os
import pandas as pd
from pathlib import Path
import markdown
import re
from datetime import datetime

def get_folder_structure(directory):
    """디렉토리 구조를 분석하여 카테고리와 파일 정보를 반환합니다."""
    data = []
    
    # 모든 하위 디렉토리 순회
    for root, dirs, files in os.walk(directory):
        # 숨김 폴더 제외
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        # 현재 디렉토리의 상대 경로 계산
        rel_path = os.path.relpath(root, directory)
        category = rel_path if rel_path != '.' else '최상위'
        
        # 마크다운 파일만 처리
        for file in files:
            if file.endswith('.md'):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    data.append({
                        'path': full_path,
                        'relative_path': os.path.relpath(full_path, directory),
                        'category': category,
                        'name': file,
                        'modified': datetime.fromtimestamp(os.stat(full_path).st_mtime),
                        'size': os.stat(full_path).st_size,
                        'content': content
                    })
                except Exception as e:
                    st.error(f"Error reading file {file}: {str(e)}")
    
    return pd.DataFrame(data)

def highlight_text(text, search_term):
    """검색어를 하이라이트 처리합니다."""
    if not search_term:
        return text
    
    # 검색어를 대소문자 구분 없이 찾기 위한 패턴
    pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
    
    # HTML 스타일의 하이라이트로 변경
    highlighted = pattern.sub(r'<span style="background-color: #FFFF00; color: #000000">\1</span>', text)
    
    return highlighted

def find_context_lines(content, search_term, context_lines=2):
    """검색어가 포함된 라인과 그 주변 컨텍스트를 찾습니다."""
    if not search_term:
        return content

    lines = content.split('\n')
    result_lines = []
    found_locations = []

    for i, line in enumerate(lines):
        if search_term.lower() in line.lower():
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            found_locations.append((start, end, i))

    # 중복 제거 및 연속된 범위 병합
    if found_locations:
        found_locations.sort()
        merged_locations = [found_locations[0]]
        
        for start, end, match_line in found_locations[1:]:
            prev_start, prev_end, _ = merged_locations[-1]
            if start <= prev_end:
                merged_locations[-1] = (prev_start, max(end, prev_end), match_line)
            else:
                merged_locations.append((start, end, match_line))

        # 결과 조합
        for start, end, match_line in merged_locations:
            if result_lines:
                result_lines.append('...')
            
            section = lines[start:end]
            result_lines.extend(section)

        return '\n'.join(result_lines)
    
    return content

def main():
    st.title("마크다운 문서 검색 시스템")

    # 기본 디렉토리 설정
    base_directory = "/Users/aqaralife/Documents/GitHub/obsidian"

    # 데이터 로드
    df = get_folder_structure(base_directory)

    # 사이드바 필터링 옵션
    st.sidebar.header("검색 필터")
    
    # 카테고리(폴더) 선택
    categories = ["전체"] + sorted(df['category'].unique().tolist())
    selected_category = st.sidebar.selectbox(
        "폴더 선택",
        categories,
        help="검색할 폴더를 선택하세요"
    )

    # 파일 선택 (선택된 카테고리에 따라 동적 업데이트)
    if selected_category != "전체":
        files = sorted(df[df['category'] == selected_category]['name'].unique().tolist())
    else:
        files = sorted(df['name'].unique().tolist())
    
    selected_file = st.sidebar.selectbox(
        "파일 선택",
        ["전체"] + files,
        help="검색할 파일을 선택하세요"
    )

    # 키워드 검색
    search_term = st.sidebar.text_input(
        "키워드 검색",
        help="검색할 키워드를 입력하세요"
    )

    # 검색 버튼
    if st.sidebar.button("검색", help="선택한 조건으로 검색합니다"):
        # 필터링
        filtered_df = df.copy()
        
        if selected_category != "전체":
            filtered_df = filtered_df[filtered_df['category'] == selected_category]
        
        if selected_file != "전체":
            filtered_df = filtered_df[filtered_df['name'] == selected_file]
        
        if search_term:
            filtered_df = filtered_df[
                filtered_df['content'].str.contains(search_term, case=False, na=False)
            ]

        # 검색 결과 표시
        st.write(f"## 검색 결과 ({len(filtered_df)} 건)")
        
        for idx, row in filtered_df.iterrows():
            with st.expander(f"📄 {row['relative_path']} ({row['modified'].strftime('%Y-%m-%d %H:%M:%S')})"):
                # 메타데이터 표시
                st.write("### 문서 정보")
                st.write(f"- 폴더: {row['category']}")
                st.write(f"- 파일명: {row['name']}")
                st.write(f"- 경로: {row['relative_path']}")
                st.write(f"- 크기: {row['size']:,} bytes")
                st.write(f"- 수정일: {row['modified']}")
                
                # 검색어가 있는 경우 컨텍스트 표시
                if search_term:
                    st.write("### 검색 결과 컨텍스트")
                    context_content = find_context_lines(row['content'], search_term)
                    highlighted_context = highlight_text(context_content, search_term)
                    st.markdown(highlighted_context, unsafe_allow_html=True)
                    
                    st.write("### 전체 내용")
                    highlighted_content = highlight_text(row['content'], search_term)
                    st.markdown(highlighted_content, unsafe_allow_html=True)
                else:
                    st.write("### 전체 내용")
                    st.markdown(row['content'])

                # 다운로드 버튼
                st.download_button(
                    label="파일 다운로드",
                    data=row['content'],
                    file_name=row['name'],
                    mime="text/markdown",
                    key=f"download_btn_{idx}"
                )

if __name__ == "__main__":
    main()