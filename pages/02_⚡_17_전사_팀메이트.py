import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import time

load_dotenv()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 페이지 설정
st.set_page_config(
    page_title="전사 팀메이트 관리",
    page_icon="⚡",
    layout="wide"
)

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def check_table_exists(table_name):
    """팀메이트 테이블 존재 여부 확인"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        result = cursor.fetchone()
        return result[0] > 0
    except mysql.connector.Error as e:
        st.error(f"테이블 확인 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def create_table(table_name, columns, primary_keys):
    """팀메이트 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제
        st.write("### 테이블 생성 과정")
        st.write("1. 기존 테이블 삭제 중...")
        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
        
        # 컬럼 정의 생성
        st.write("2. 컬럼 정의 생성 중...")
        column_definitions = []
        for col in columns:
            # 컬럼명을 백틱으로 감싸서 특수문자 처리
            if col in primary_keys:
                column_definitions.append(f"`{col}` VARCHAR(100) NOT NULL")
            else:
                column_definitions.append(f"`{col}` TEXT")
        
        # 테이블 생성 쿼리
        create_query = f"""
            CREATE TABLE `{table_name}` (
                {', '.join(column_definitions)},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY ({', '.join(f'`{pk}`' for pk in primary_keys)})
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
        
        st.write("3. 테이블 생성 쿼리:")
        st.code(create_query, language='sql')
        
        cursor.execute(create_query)
        conn.commit()
        
        # 테이블 생성 확인
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        if cursor.fetchone()[0] > 0:
            st.write("4. ✅ 테이블이 성공적으로 생성되었습니다!")
            
            # 테이블 구조 확인
            cursor.execute(f"DESCRIBE `{table_name}`")
            table_structure = cursor.fetchall()
            st.write("5. 생성된 테이블 구조:")
            structure_df = pd.DataFrame(table_structure, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
            st.dataframe(structure_df)
            
            return True
        else:
            st.error("테이블 생성을 확인할 수 없습니다.")
            return False
            
    except Exception as e:
        st.error(f"테이블 생성 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_teammates_from_excel(table_name, df, primary_keys):
    """엑셀 데이터를 DB에 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 컬럼 목록 생성
        columns = df.columns.tolist()
        placeholders = ', '.join(['%s'] * len(columns))
        
        # INSERT 쿼리 생성 (컬럼명에 백틱 추가)
        insert_query = f"""
            INSERT INTO `{table_name}` ({', '.join(f'`{col}`' for col in columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
            {', '.join(f"`{col}` = VALUES(`{col}`)" for col in columns if col not in primary_keys)}
        """
        
        # 데이터 삽입
        for _, row in df.iterrows():
            cursor.execute(insert_query, row.tolist())
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"데이터 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_teammate_by_keys(table_name, key_values, primary_keys):
    """primary keys로 팀메이트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        where_conditions = " AND ".join([f"`{key}` = %s" for key in primary_keys])
        cursor.execute(f"""
            SELECT * FROM `{table_name}` 
            WHERE {where_conditions}
        """, list(key_values.values()))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def update_teammate(table_name, data, primary_keys):
    """팀메이트 정보 수정"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # UPDATE 쿼리 생성 (컬럼명에 백틱 추가)
        columns = list(data.keys())
        update_query = f"""
            UPDATE `{table_name}` 
            SET {', '.join(f"`{col}` = %s" for col in columns if col not in primary_keys)}
            WHERE {' AND '.join(f"`{key}` = %s" for key in primary_keys)}
        """
        
        # 파라미터 생성
        update_params = [data[col] for col in columns if col not in primary_keys]
        where_params = [data[key] for key in primary_keys]
        params = update_params + where_params
        
        cursor.execute(update_query, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"수정 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_table_columns(table_name):
    """테이블의 컬럼 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = %s
            AND COLUMN_NAME NOT IN ('created_at', 'updated_at')
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        columns = [row[0] for row in cursor.fetchall()]
        return columns
    finally:
        cursor.close()
        conn.close()

def search_teammates(table_name, keyword):
    """팀메이트 검색"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 테이블 존재 여부 확인
        if not check_table_exists(table_name):
            st.error(f"테이블 '{table_name}'이(가) 존재하지 않습니다.")
            return []
        
        # 모든 컬럼 가져오기 (created_at, updated_at 제외)
        columns = get_table_columns(table_name)
        
        if not columns:
            st.error("테이블에서 검색 가능한 컬럼을 찾을 수 없습니다.")
            return []
        
        # 검색 조건 생성
        search_conditions = " OR ".join([f"`{col}` LIKE %s" for col in columns])
        search_params = [f"%{keyword}%" for _ in columns]
        
        # 검색 쿼리
        search_query = f"""
            SELECT * FROM `{table_name}`
            WHERE {search_conditions}
            ORDER BY created_at DESC
        """
        
        # 검색 쿼리 실행
        cursor.execute(search_query, search_params)
        results = cursor.fetchall()
        
        return results
        
    except Exception as e:
        st.error(f"검색 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_all_teammates(table_name):
    """모든 팀메이트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(f"SELECT * FROM `{table_name}` ORDER BY created_at DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def ai_search_help(table_name, query):
    """AI를 통한 검색 도움"""
    try:
        # 모든 팀메이트 데이터 가져오기
        teammates = get_all_teammates(table_name)
        
        if not teammates:
            return "등록된 팀메이트가 없습니다."
        
        # 필요한 필드만 선택하여 데이터 최적화
        simplified_data = []
        for t in teammates:
            teammate_data = {}
            for key, value in t.items():
                if key not in ['created_at', 'updated_at']:
                    # None이나 빈 문자열 처리
                    processed_value = value if value and str(value).strip() not in ['', 'None', 'N/A'] else None
                    if processed_value:  # 값이 있는 경우에만 포함
                        teammate_data[key] = processed_value
            if teammate_data:  # 데이터가 있는 경우에만 추가
                simplified_data.append(teammate_data)
        
        if not simplified_data:
            return "팀메이트 정보가 충분하지 않습니다."
        
        # AI 프롬프트 생성
        prompt = f"""
        다음은 회사 팀메이트들의 목록입니다:
        
        {json.dumps(simplified_data, ensure_ascii=False, indent=2)}
        
        요청: "{query}"
        
        위 요청에 가장 적합한 팀메이트를 찾아 다음 형식으로 응답해주세요:
        1. 추천 팀메이트 (최대 3명)
        2. 추천 이유 (각 팀메이트별로 구체적인 이유)
        3. 협업 제안 (실질적인 협업 방안)
        
        주의사항:
        - 실제 데이터에 기반하여 추천해주세요
        - 각 팀메이트의 실제 업무와 전문성을 고려해주세요
        - 구체적인 협업 방안을 제시해주세요
        """
        
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "당신은 회사의 인재 매칭 전문가입니다. 업무 요청에 가장 적합한 팀메이트를 찾아 매칭해주는 역할을 합니다. 항상 실제 데이터에 기반하여 추천하며, 데이터가 불충분할 경우 그 사실을 명확히 알립니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000  # 응답 길이 증가
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def verify_admin_password(input_password):
    """관리자 비밀번호 확인"""
    return input_password == os.getenv('ADMIN_PASSWORD')

def delete_teammate(table_name, key_values, primary_keys, is_admin=False):
    """팀메이트 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        where_conditions = " AND ".join([f"`{key}` = %s" for key in primary_keys])
        cursor.execute(f"""
            DELETE FROM `{table_name}` 
            WHERE {where_conditions}
        """, list(key_values.values()))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_primary_keys(table_name):
    """테이블의 Primary Key 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = %s
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def get_available_tables():
    """사용 가능한 테이블 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
        """, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("⚡ 전사 팀메이트 관리")
    
    # 세션 상태 초기화
    if 'current_table' not in st.session_state:
        st.session_state.current_table = 'company_teammates'
    
    tab1, tab2, tab3 = st.tabs(["🔍 검색", "📝 등록/수정", "⚙️ 관리자 모드"])
    
    # 테이블 목록 조회
    tables = get_available_tables()
    if 'company_teammates' not in tables:
        tables = ['company_teammates'] + [t for t in tables if t != 'company_teammates']
    
    with tab1:
        st.header("팀메이트 검색")
        
        if not check_table_exists('company_teammates'):
            st.warning("팀메이트 테이블이 없습니다. 등록/수정 탭에서 데이터를 먼저 등록해주세요.")
        else:
            selected_table = st.selectbox(
                "테이블 선택", 
                tables, 
                key="search_table",
                index=tables.index('company_teammates') if 'company_teammates' in tables else 0
            )
            st.session_state.current_table = selected_table
            
            if selected_table:
                search_query = st.text_input(
                    "검색어를 입력하세요",
                    placeholder="이름, 부서, 직책 등"
                )
                
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    search_type = st.radio(
                        "검색 방식",
                        ["일반 검색", "AI 도움"]
                    )
                
                with col2:
                    if st.button("검색", type="primary"):
                        if search_type == "일반 검색":
                            if search_query:
                                # 디버깅을 위한 임시 출력
                                st.write("검색어:", search_query)
                                
                                results = search_teammates(selected_table, search_query)
                                
                                # 디버깅을 위한 임시 출력
                                st.write("DB 검색 결과:", results)
                                
                                if results:
                                    valid_results = []
                                    for result in results:
                                        # 실제 데이터가 하나라도 있는지 확인
                                        has_valid_data = False
                                        display_values = {}
                                        
                                        for key, value in result.items():
                                            if key not in ['created_at', 'updated_at']:
                                                if value and str(value).strip() not in ['', 'None', 'N/A']:
                                                    has_valid_data = True
                                                    display_values[key] = value
                                        
                                        if has_valid_data:
                                            valid_results.append(display_values)
                                    
                                    if valid_results:
                                        st.success(f"{len(valid_results)}개의 결과를 찾았습니다.")
                                        st.write("### 검색 결과 목록")
                                        
                                        # 결과 데이터 준비 및 표시
                                        for result in valid_results:
                                            name = result.get('성명', '')  # '이름' 대신 '성명' 사용
                                            position = result.get('직책', '')
                                            department = result.get('사업부/부문', '')  # '부서/부문' 대신 '사업부/부문' 사용
                                            
                                            if name:  # 이름이 있는 경우만 표시
                                                col1, col2, col3 = st.columns([2, 2, 3])
                                                with col1:
                                                    st.markdown(f"**성명:** {name}")
                                                with col2:
                                                    if position:
                                                        st.markdown(f"**직책:** {position}")
                                                with col3:
                                                    if department:
                                                        st.markdown(f"**사업부/부문:** {department}")
                                                
                                                # 상세 정보 expander
                                                with st.expander(f"🔍 {name}님의 상세 정보"):
                                                    for key, value in result.items():
                                                        if key not in ['created_at', 'updated_at']:
                                                            st.markdown(f"**{key}:** {value}")
                                                
                                                # 구분선 추가
                                                st.divider()
                                    else:
                                        st.info("검색 결과가 없습니다.")
                                else:
                                    st.info("검색 결과가 없습니다.")
                        else:  # AI 도움
                            if search_query:
                                with st.spinner("AI가 적합한 팀메이트를 찾고 있습니다..."):
                                    ai_result = ai_search_help(selected_table, search_query)
                                    if ai_result:
                                        st.write("### AI 추천 결과")
                                        # 결과를 마크다운 형식으로 표시
                                        st.markdown(ai_result)
                                        
                                        # 추가 안내 메시지
                                        st.info("💡 더 정확한 추천을 위해서는 팀메이트들의 상세 정보가 필요합니다. 등록/수정 탭에서 정보를 업데이트해주세요.")
                            else:
                                st.warning("검색어를 입력해주세요.")

    with tab2:
        st.header("팀메이트 등록/수정")
        
        upload_method = st.radio(
            "등록 방식 선택",
            ["엑셀 파일 업로드", "수동 입력"],
            horizontal=True
        )
        
        if upload_method == "엑셀 파일 업로드":
            # 테이블 이름 입력
            table_name = st.text_input(
                "테이블 이름 입력",
                placeholder="영문, 숫자, 언더스코어(_)만 사용 가능",
                help="생성할 테이블의 이름을 입력해주세요. 이미 존재하는 테이블은 덮어쓰기됩니다."
            )
            
            if table_name:
                # 테이블 이름 유효성 검사
                if not table_name.replace('_', '').isalnum():
                    st.error("테이블 이름은 영문, 숫자, 언더스코어(_)만 사용할 수 있습니다.")
                    st.stop()
                
                uploaded_file = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xls'])
                
                if uploaded_file:
                    try:
                        # 원본 데이터 미리보기
                        st.write("### 원본 데이터 미리보기")
                        df_raw = pd.read_excel(uploaded_file)
                        st.dataframe(df_raw)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            header_row = st.number_input("제목 행 번호", min_value=1, value=1) - 1
                        with col2:
                            data_start_row = st.number_input("데이터 시작 행 번호", min_value=1, value=2) - 1
                        
                        # 선택한 헤더 행으로 데이터프레임 생성
                        df = pd.read_excel(uploaded_file, header=header_row)
                        
                        # NaN이나 빈 문자열인 컬럼명 처리
                        df.columns = [f'Column_{i+1}' if pd.isna(col) or str(col).strip() == '' 
                                    else str(col).strip() 
                                    for i, col in enumerate(df.columns)]
                        
                        # 중복된 컬럼명 처리
                        seen_columns = {}
                        new_columns = []
                        for col in df.columns:
                            if col in seen_columns:
                                seen_columns[col] += 1
                                new_columns.append(f"{col}_{seen_columns[col]}")
                            else:
                                seen_columns[col] = 1
                                new_columns.append(col)
                        df.columns = new_columns
                        
                        columns = df.columns.tolist()
                        
                        # 컬럼 선택
                        st.write("### 사용할 컬럼 선택")
                        st.write("테이블에 포함할 컬럼들을 선택해주세요. 선택하지 않은 컬럼은 제외됩니다.")
                        st.write("⚠️ 자동 생성된 컬럼명: Column_N (빈 컬럼명인 경우), 컬럼명_N (중복된 경우)")
                        
                        # 컬럼 선택을 위한 체크박스 (3열 레이아웃)
                        selected_columns = []
                        cols = st.columns(3)
                        for i, col in enumerate(columns):
                            with cols[i % 3]:
                                if st.checkbox(f"📋 {col}", value=True, key=f"col_{i}"):
                                    selected_columns.append(col)
                        
                        if not selected_columns:
                            st.error("최소 하나 이상의 컬럼을 선택해주세요.")
                            st.stop()
                        
                        # 선택된 컬럼으로 데이터프레임 필터링
                        preview_df = df[selected_columns].copy()
                        if data_start_row > header_row:
                            preview_df = preview_df.iloc[data_start_row-header_row:]
                        
                        # NaN 값을 빈 문자열로 변환
                        preview_df = preview_df.fillna('')
                        
                        # 선택한 헤더 행과 데이터 미리보기
                        st.write(f"### 선택한 컬럼으로 처리된 데이터 미리보기")
                        st.write("선택된 컬럼 목록:", ", ".join(selected_columns))
                        st.dataframe(preview_df)
                        
                        # Primary Keys 선택
                        st.write("### Primary Keys 선택")
                        st.write("테이블의 고유 식별자로 사용될 컬럼들을 선택해주세요.")
                        
                        # Primary Key 선택을 위한 체크박스 (3열 레이아웃)
                        primary_keys = []
                        cols = st.columns(3)
                        for i, col in enumerate(selected_columns):
                            with cols[i % 3]:
                                if st.checkbox(f"✓ {col}", key=f"pk_{i}"):
                                    primary_keys.append(col)
                        
                        if not primary_keys:
                            st.warning("최소 하나 이상의 Primary Key를 선택해주세요.")
                        
                        if st.button("테이블 생성 및 데이터 저장", type="primary", disabled=not primary_keys):
                            # Primary Key 컬럼들의 조합이 유일한지 확인
                            is_unique = preview_df.duplicated(subset=primary_keys).sum() == 0
                            
                            if not is_unique:
                                st.error("선택한 Primary Key 조합이 고유하지 않습니다. 다른 컬럼을 추가로 선택해주세요.")
                            else:
                                # 테이블 생성
                                if create_table(table_name, preview_df.columns.tolist(), primary_keys):
                                    st.success(f"테이블 '{table_name}'이(가) 생성되었습니다.")
                                    
                                    # 데이터 저장
                                    if save_teammates_from_excel(table_name, preview_df, primary_keys):
                                        st.success("데이터가 성공적으로 저장되었습니다! 🎉")
                                        time.sleep(1)
                                        st.rerun()
                
                    except Exception as e:
                        st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
                        st.write("상세 오류 정보:")
                        st.write(e)
        
        else:  # 수동 입력
            if not tables:
                st.error("등록된 테이블이 없습니다. 먼저 엑셀 파일을 업로드하여 테이블을 생성해주세요.")
            else:
                selected_table = st.selectbox("테이블 선택", tables, key="edit_table")
                if selected_table:
                    # 컬럼 정보 가져오기
                    columns = get_table_columns(selected_table)
                    
                    # Primary Keys 가져오기
                    primary_keys = get_primary_keys(selected_table)
                    
                    # Primary Keys 입력 필드 생성
                    st.write("### Primary Key 값 입력")
                    key_values = {}
                    
                    # Primary Keys 입력
                    for key in primary_keys:
                        key_values[key] = st.text_input(f"{key} 입력")
                    
                    if all(key_values.values()):
                        # 기존 데이터 확인
                        existing_data = get_teammate_by_keys(selected_table, key_values, primary_keys)
                        
                        with st.form("teammate_form"):
                            data = key_values.copy()
                            
                            # 나머지 필드 입력
                            for col in columns:
                                if col not in primary_keys:
                                    default_value = existing_data.get(col, '') if existing_data else ''
                                    data[col] = st.text_input(col, value=default_value)
                            
                            submit_button = st.form_submit_button(
                                "수정" if existing_data else "저장",
                                type="primary"
                            )
                            
                            if submit_button:
                                if all(data.values()):  # 모든 필드가 입력되었는지 확인
                                    if existing_data:  # 수정
                                        if update_teammate(selected_table, data, primary_keys):
                                            st.success("데이터가 성공적으로 수정되었습니다! 🎉")
                                            time.sleep(1)
                                            st.rerun()
                                    else:  # 새로 저장
                                        if save_teammates_from_excel(selected_table, pd.DataFrame([data]), primary_keys):
                                            st.success("데이터가 성공적으로 저장되었습니다! 🎉")
                                            time.sleep(1)
                                            st.rerun()
                                else:
                                    st.error("모든 항목을 입력해주세요.")
    
    with tab3:
        st.header("관리자 모드")
        
        # 관리자 인증
        admin_password = st.text_input("관리자 비밀번호", type="password")
        if admin_password:
            if verify_admin_password(admin_password):
                st.success("관리자 인증 성공")
                
                if not tables:
                    st.warning("등록된 테이블이 없습니다.")
                else:
                    selected_table = st.selectbox("테이블 선택", tables, key="admin_table")
                    if selected_table:
                        # 모든 팀메이트 목록 표시
                        all_teammates = get_all_teammates(selected_table)
                        if all_teammates:
                            st.subheader(f"테이블 '{selected_table}' 등록 데이터 목록")
                            
                            # 검색 필터
                            search_term = st.text_input("이름, 부서, 직책으로 검색")
                            filtered_teammates = all_teammates
                            if search_term:
                                filtered_teammates = [
                                    teammate for teammate in all_teammates
                                    if any(search_term.lower() in str(value).lower() 
                                          for key, value in teammate.items() 
                                          if key not in ['created_at', 'updated_at'])
                                ]
                            
                            valid_teammates = []
                            for teammate in filtered_teammates:
                                # 실제 데이터가 하나라도 있는지 확인
                                has_valid_data = False
                                display_values = {}
                                for key, value in teammate.items():
                                    if key not in ['created_at', 'updated_at']:
                                        if value and str(value).strip() not in ['', 'None', 'N/A']:
                                            has_valid_data = True
                                            display_values[key] = value
                                
                                if has_valid_data:
                                    valid_teammates.append((teammate, display_values))
                            
                            if valid_teammates:
                                for teammate, display_values in valid_teammates:
                                    # 제목에 표시할 정보 준비
                                    name = display_values.get('이름', '')
                                    position = display_values.get('직책', '')
                                    department = display_values.get('부서/부문', '')
                                    
                                    # 제목 생성
                                    title_parts = []
                                    if name: title_parts.append(name)
                                    if position: title_parts.append(f"({position}")
                                    if department: title_parts.append(f"- {department})")
                                    elif position: title_parts.append(")")
                                    
                                    title = " ".join(title_parts)
                                    
                                    with st.expander(title):
                                        col1, col2 = st.columns([4, 1])
                                        with col1:
                                            # 이름을 먼저 표시
                                            if '이름' in display_values:
                                                st.write(f"**이름:** {display_values['이름']}")
                                            
                                            # 나머지 정보 표시
                                            for key, value in display_values.items():
                                                if key != '이름':
                                                    st.write(f"**{key}:** {value}")
                                        
                                        with col2:
                                            # Primary Keys 가져오기
                                            primary_keys = get_primary_keys(selected_table)
                                            
                                            # Primary Key 값들 추출
                                            key_values = {key: teammate[key] for key in primary_keys}
                                            
                                            # 고유한 버튼 키 생성
                                            button_key = "_".join([
                                                str(teammate.get(key, '')) 
                                                for key in primary_keys
                                            ])
                                            
                                            if st.button("🗑️ 삭제", 
                                                        key=f"admin_delete_{button_key}", 
                                                        type="secondary"):
                                                if delete_teammate(selected_table, key_values, primary_keys, is_admin=True):
                                                    st.success(f"{name}의 정보가 삭제되었습니다.")
                                                    time.sleep(1)
                                                    st.rerun()
                            else:
                                st.info("표시할 데이터가 없습니다.")
                        else:
                            st.info(f"테이블 '{selected_table}'에 등록된 데이터가 없습니다.")
            else:
                st.error("관리자 비밀번호가 일치하지 않습니다.")

if __name__ == "__main__":
    main() 