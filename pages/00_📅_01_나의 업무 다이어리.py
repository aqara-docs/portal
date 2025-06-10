import streamlit as st
import mysql.connector
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, date
import base64
import io
from PIL import Image
import json
import tempfile
import re

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="나의 업무 다이러리",
    page_icon="📅",
    layout="wide"
)

st.title("📅 나의 업무 다이어리")

# 인증 기능 (간단한 비밀번호 보호)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

admin_pw = os.getenv('ADMIN_PASSWORD')
if not admin_pw:
    st.error('환경변수(ADMIN_PASSWORD)가 설정되어 있지 않습니다. .env 파일을 확인하세요.')
    st.stop()

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == admin_pw:
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

def connect_to_db():
    """데이터베이스 연결"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

def get_diary_by_date_and_author(work_date, author):
    """특정 날짜와 작성자의 업무일지 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT diary_id, author, work_date, po_content, customs_content, 
                   inventory_content, partner_content, other_content, todo_list, created_at, updated_at
            FROM work_diary 
            WHERE work_date = %s AND author = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (work_date, author))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'diary_id': result[0],
                'author': result[1],
                'work_date': result[2],
                'po_content': result[3] or '',
                'customs_content': result[4] or '',
                'inventory_content': result[5] or '',
                'partner_content': result[6] or '',
                'other_content': result[7] or '',
                'todo_list': result[8],
                'created_at': result[9],
                'updated_at': result[10]
            }
        return None
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 조회 오류: {err}")
        return None

def save_work_diary(diary_data, diary_id=None):
    """업무일지 저장 (새로 생성 또는 업데이트)"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        cursor = conn.cursor()
        
        if diary_id:
            # 기존 데이터 업데이트
            cursor.execute("""
                UPDATE work_diary 
                SET author = %s, work_date = %s, po_content = %s, customs_content = %s, 
                    inventory_content = %s, partner_content = %s, other_content = %s, todo_list = %s
                WHERE diary_id = %s
            """, (
                diary_data['author'],
                diary_data['work_date'],
                diary_data['po_content'],
                diary_data['customs_content'],
                diary_data['inventory_content'],
                diary_data['partner_content'],
                diary_data['other_content'],
                diary_data.get('todo_list'),
                diary_id
            ))
            result_id = diary_id
        else:
            # 새 데이터 생성
            cursor.execute("""
                INSERT INTO work_diary 
                (author, work_date, po_content, customs_content, inventory_content, partner_content, other_content, todo_list)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                diary_data['author'],
                diary_data['work_date'],
                diary_data['po_content'],
                diary_data['customs_content'],
                diary_data['inventory_content'],
                diary_data['partner_content'],
                diary_data['other_content'],
                diary_data.get('todo_list')
            ))
            result_id = cursor.lastrowid
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return result_id
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 저장 오류: {err}")
        return None

def save_work_diary_file(diary_id, work_type, file_data):
    """업무일지 파일 저장"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 파일 내용을 바이너리로 읽기
        file_content = file_data.read()
        file_data.seek(0)  # 파일 포인터 리셋
        
        # file_type 처리 - 길이 제한 및 기본값 설정
        if hasattr(file_data, 'type') and file_data.type:
            file_type = file_data.type[:50]  # 50자로 제한
        else:
            # 파일 확장자로부터 타입 추정
            filename = file_data.name.lower()
            if filename.endswith(('.jpg', '.jpeg')):
                file_type = 'image/jpeg'
            elif filename.endswith('.png'):
                file_type = 'image/png'
            elif filename.endswith('.pdf'):
                file_type = 'application/pdf'
            elif filename.endswith(('.xlsx', '.xls')):
                file_type = 'application/excel'
            elif filename.endswith('.csv'):
                file_type = 'text/csv'
            elif filename.endswith('.txt'):
                file_type = 'text/plain'
            elif filename.endswith('.json'):
                file_type = 'application/json'
            elif filename.endswith(('.md', '.markdown')):
                file_type = 'text/markdown'
            elif filename.endswith('.html'):
                file_type = 'text/html'
            elif filename.endswith('.xml'):
                file_type = 'text/xml'
            else:
                file_type = 'unknown'
        
        cursor.execute("""
            INSERT INTO work_diary_files 
            (diary_id, work_type, filename, file_type, file_content, file_size)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            diary_id,
            work_type,
            file_data.name,
            file_type,
            file_content,
            len(file_content)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"파일 저장 오류: {err}")
        return False

def get_work_diaries(search_author=None, search_date=None, search_content=None):
    """업무일지 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return pd.DataFrame()
        
        cursor = conn.cursor()
        
        # 명시적 컬럼 지정으로 순서 보장
        query = """SELECT diary_id, author, work_date, po_content, customs_content, 
                          inventory_content, partner_content, other_content, todo_list, created_at, updated_at
                   FROM work_diary WHERE 1=1"""
        params = []
        
        if search_author:
            query += " AND author LIKE %s"
            params.append(f"%{search_author}%")
        
        if search_date:
            query += " AND work_date = %s"
            params.append(search_date)
        
        if search_content:
            query += """ AND (
                po_content LIKE %s OR 
                customs_content LIKE %s OR 
                inventory_content LIKE %s OR 
                partner_content LIKE %s OR 
                other_content LIKE %s
            )"""
            search_param = f"%{search_content}%"
            params.extend([search_param] * 5)
        
        query += " ORDER BY work_date DESC, created_at DESC"
        
        cursor.execute(query, params)
        data = cursor.fetchall()
        
        columns = ['diary_id', 'author', 'work_date', 'po_content', 'customs_content', 
                  'inventory_content', 'partner_content', 'other_content', 'todo_list', 'created_at', 'updated_at']
        
        cursor.close()
        conn.close()
        
        return pd.DataFrame(data, columns=columns)
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 조회 오류: {err}")
        return pd.DataFrame()

def get_work_diary_files(diary_id):
    """특정 업무일지의 파일 목록 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return pd.DataFrame()
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT file_id, work_type, filename, file_type, file_size, uploaded_at
            FROM work_diary_files 
            WHERE diary_id = %s
            ORDER BY work_type, uploaded_at
        """, (diary_id,))
        
        data = cursor.fetchall()
        columns = ['file_id', 'work_type', 'filename', 'file_type', 'file_size', 'uploaded_at']
        
        cursor.close()
        conn.close()
        
        return pd.DataFrame(data, columns=columns)
        
    except mysql.connector.Error as err:
        st.error(f"파일 목록 조회 오류: {err}")
        return pd.DataFrame()

def get_file_binary_data(file_id):
    """파일 바이너리 데이터 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT filename, file_type, file_content
            FROM work_diary_files 
            WHERE file_id = %s
        """, (file_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'filename': result[0],
                'file_type': result[1],
                'binary_data': result[2]
            }
        return None
        
    except mysql.connector.Error as err:
        st.error(f"파일 데이터 조회 오류: {err}")
        return None

def display_file_preview(file_data, file_type, filename):
    """파일 미리보기 표시 - 프로젝트 리뷰와 동일한 방식"""
    try:
        file_type_lower = file_type.lower()
        # 파일 확장자 추출
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # 이미지 파일 미리보기
        if (file_type_lower in ['jpg', 'jpeg', 'png', 'gif'] or 'image' in file_type_lower or 
            file_extension in ['jpg', 'jpeg', 'png', 'gif']):
            if file_data.get('binary_data'):
                st.image(
                    file_data['binary_data'],
                    caption=f"🖼️ {filename}",
                    use_column_width=True
                )
                return True
            else:
                st.info("이미지 데이터를 찾을 수 없습니다.")
                return False
        
        # PDF 파일 미리보기 (iframe 사용)
        elif file_type_lower == 'pdf' or 'pdf' in file_type_lower or file_extension == 'pdf':
            if file_data.get('binary_data'):
                # PDF를 base64로 인코딩하여 iframe에 표시
                pdf_base64 = base64.b64encode(file_data['binary_data']).decode('utf-8')
                pdf_display = f"""
                <iframe src="data:application/pdf;base64,{pdf_base64}" 
                        width="100%" height="600px" type="application/pdf">
                    <p>PDF를 표시할 수 없습니다. 
                    <a href="data:application/pdf;base64,{pdf_base64}" target="_blank">
                    여기를 클릭하여 새 탭에서 열어보세요.</a></p>
                </iframe>
                """
                st.markdown(pdf_display, unsafe_allow_html=True)
                return True
            else:
                st.info("PDF 데이터를 찾을 수 없습니다.")
                return False
        
        # Excel 파일 미리보기
        elif (file_type_lower in ['xlsx', 'xls'] or 'excel' in file_type_lower or 'spreadsheet' in file_type_lower or
              file_extension in ['xlsx', 'xls']):
            if file_data.get('binary_data'):
                try:
                    # 파일 확장자 결정
                    if file_extension in ['xlsx', 'xls']:
                        temp_suffix = f'.{file_extension}'
                    elif 'xlsx' in file_type_lower or 'openxml' in file_type_lower:
                        temp_suffix = '.xlsx'
                    else:
                        temp_suffix = '.xls'
                    
                    # 바이너리 데이터를 임시 파일로 저장하여 pandas로 읽기
                    with tempfile.NamedTemporaryFile(suffix=temp_suffix, delete=False) as tmp_file:
                        tmp_file.write(file_data['binary_data'])
                        tmp_file_path = tmp_file.name
                    
                    # Excel 파일 읽기
                    df = pd.read_excel(tmp_file_path)
                    
                    # 임시 파일 삭제
                    os.unlink(tmp_file_path)
                    
                    st.subheader(f"📊 Excel 파일 미리보기: {filename}")
                    st.dataframe(df, use_container_width=True)
                    
                    # 기본 통계 정보
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("행 수", len(df))
                    with col2:
                        st.metric("열 수", len(df.columns))
                    with col3:
                        st.metric("데이터 타입", len(df.dtypes.unique()))
                    
                    return True
                except Exception as e:
                    st.error(f"Excel 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("Excel 데이터를 찾을 수 없습니다.")
                return False
        
        # CSV 파일 미리보기
        elif file_type_lower == 'csv' or 'csv' in file_type_lower or file_extension == 'csv':
            if file_data.get('binary_data'):
                try:
                    # CSV 데이터를 문자열로 변환
                    csv_content = file_data['binary_data'].decode('utf-8')
                    
                    # StringIO를 사용하여 pandas로 읽기
                    from io import StringIO
                    df = pd.read_csv(StringIO(csv_content))
                    
                    st.subheader(f"📈 CSV 파일 미리보기: {filename}")
                    st.dataframe(df, use_container_width=True)
                    
                    # 기본 통계 정보
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("행 수", len(df))
                    with col2:
                        st.metric("열 수", len(df.columns))
                    with col3:
                        st.metric("데이터 타입", len(df.dtypes.unique()))
                    
                    return True
                except Exception as e:
                    st.error(f"CSV 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("CSV 데이터를 찾을 수 없습니다.")
                return False
        
        # JSON 파일 미리보기
        elif file_type_lower == 'json' or 'json' in file_type_lower or file_extension == 'json':
            if file_data.get('binary_data'):
                try:
                    json_content = file_data['binary_data'].decode('utf-8')
                    json_data = json.loads(json_content)
                    
                    st.subheader(f"📋 JSON 파일 미리보기: {filename}")
                    st.json(json_data)
                    return True
                except Exception as e:
                    st.error(f"JSON 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("JSON 데이터를 찾을 수 없습니다.")
                return False
        
        # 텍스트 파일 미리보기 (TXT, MD, XML, HTML 등)
        elif (file_type_lower in ['txt', 'md', 'xml', 'html', 'markdown'] or 
              'text' in file_type_lower or 'html' in file_type_lower or 'xml' in file_type_lower or
              file_extension in ['txt', 'md', 'markdown', 'xml', 'html']):
            if file_data.get('binary_data'):
                try:
                    text_content = file_data['binary_data'].decode('utf-8')
                    
                    st.subheader(f"📄 텍스트 파일 미리보기: {filename}")
                    
                    if file_type_lower == 'md' or file_extension in ['md', 'markdown']:
                        # Markdown 파일은 렌더링하여 표시
                        st.markdown(text_content)
                    elif file_type_lower == 'html' or file_extension == 'html':
                        # HTML 파일은 코드로 표시 (보안상 렌더링하지 않음)
                        st.code(text_content, language='html')
                    elif file_type_lower == 'xml' or file_extension == 'xml':
                        # XML 파일은 코드로 표시
                        st.code(text_content, language='xml')
                    else:
                        # 일반 텍스트
                        st.text_area(
                            "파일 내용",
                            value=text_content,
                            height=400,
                            disabled=True
                        )
                    
                    return True
                except Exception as e:
                    st.error(f"텍스트 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("텍스트 데이터를 찾을 수 없습니다.")
                return False
        
        # 지원하지 않는 파일 형식
        else:
            st.info(f"📁 {file_type.upper()} 파일은 미리보기를 지원하지 않습니다.")
            st.caption("다운로드하여 해당 프로그램에서 열어보세요.")
            return False
            
    except Exception as e:
        st.error(f"파일 미리보기 중 오류 발생: {str(e)}")
        return False

def get_work_diary_by_id(diary_id):
    """특정 업무일지 조회"""
    try:
        conn = connect_to_db()
        if not conn:
            return None
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT diary_id, author, work_date, po_content, customs_content, 
                   inventory_content, partner_content, other_content, todo_list, created_at, updated_at
            FROM work_diary 
            WHERE diary_id = %s
        """, (diary_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'diary_id': result[0],
                'author': result[1],
                'work_date': result[2],
                'po_content': result[3],
                'customs_content': result[4],
                'inventory_content': result[5],
                'partner_content': result[6],
                'other_content': result[7],
                'todo_list': result[8],
                'created_at': result[9],
                'updated_at': result[10]
            }
        return None
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 조회 오류: {err}")
        return None

def update_work_diary(diary_id, diary_data):
    """업무일지 수정"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE work_diary 
            SET author = %s, work_date = %s, po_content = %s, customs_content = %s, 
                inventory_content = %s, partner_content = %s, other_content = %s, todo_list = %s
            WHERE diary_id = %s
        """, (
            diary_data['author'],
            diary_data['work_date'],
            diary_data['po_content'],
            diary_data['customs_content'],
            diary_data['inventory_content'],
            diary_data['partner_content'],
            diary_data['other_content'],
            diary_data.get('todo_list'),
            diary_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 수정 오류: {err}")
        return False

def delete_work_diary(diary_id):
    """업무일지 삭제 (파일도 함께 삭제됨 - CASCADE)"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM work_diary WHERE diary_id = %s", (diary_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"업무일지 삭제 오류: {err}")
        return False

def delete_work_diary_file(file_id):
    """업무일지 파일 삭제"""
    try:
        conn = connect_to_db()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM work_diary_files WHERE file_id = %s", (file_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"파일 삭제 오류: {err}")
        return False

def fix_corrupted_diary_data(diary_id):
    """손상된 업무일지 데이터 복구 (updated_at 필드에 JSON이 저장된 경우)"""
    try:
        st.info(f"🔧 복구 시작: diary_id = {diary_id}")
        
        conn = connect_to_db()
        if not conn:
            st.error("❌ 데이터베이스 연결에 실패했습니다.")
            return False
        
        cursor = conn.cursor()
        
        # 손상된 데이터 조회
        cursor.execute("""
            SELECT diary_id, todo_list, updated_at
            FROM work_diary 
            WHERE diary_id = %s
        """, (diary_id,))
        
        result = cursor.fetchone()
        if not result:
            st.error(f"❌ ID {diary_id}에 해당하는 업무일지를 찾을 수 없습니다.")
            cursor.close()
            conn.close()
            return False
        
        found_diary_id, current_todo_list, updated_at = result
        
        # updated_at 필드에 JSON이 저장되었는지 확인
        updated_at_str = str(updated_at) if updated_at else ""
        st.info(f"🔍 현재 updated_at 값: {updated_at_str[:100]}...")
        st.info(f"🔍 현재 todo_list 값: {current_todo_list}")
        
        # 데이터 무결성 검사: 필드가 잘못된 위치에 저장된 경우 감지
        updated_at_str = str(updated_at) if updated_at else ""
        todo_list_str = str(current_todo_list) if current_todo_list else ""
        
        # 손상 케이스 감지 - 더 정확한 판단
        is_updated_at_json = (updated_at_str.startswith('[{') and updated_at_str.endswith('}]'))
        
        # todo_list가 실제 datetime 형식인지 확인 (JSON이 아닌 순수 datetime 문자열)
        is_todo_list_timestamp = False
        if current_todo_list and not todo_list_str.startswith('[') and not todo_list_str.startswith('{'):
            # JSON이 아니면서 datetime 패턴과 일치하는 경우
            datetime_pattern = r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$'
            is_todo_list_timestamp = bool(re.match(datetime_pattern, todo_list_str.strip()))
        
        is_corrupted = is_updated_at_json or is_todo_list_timestamp
        
        if is_corrupted:
            st.warning("⚠️ 손상된 데이터가 감지되었습니다. 복구를 시도합니다...")
            
            # 복구할 JSON 데이터와 올바른 updated_at 결정
            json_data = None
            correct_updated_at = None
            
            if is_updated_at_json:
                # updated_at에 JSON이 있는 경우
                json_data = updated_at_str
                correct_updated_at = "CURRENT_TIMESTAMP"
            elif is_todo_list_timestamp:
                # todo_list에 Timestamp가 있는 경우
                correct_updated_at = str(current_todo_list)
                json_data = None
                
                # 다른 곳에서 JSON 데이터 찾기 시도
                if updated_at_str.startswith('[{'):
                    json_data = updated_at_str
            
            try:
                if json_data:
                    # JSON 파싱 시도
                    parsed_json = json.loads(json_data)
                    st.info(f"✅ JSON 파싱 성공: {len(parsed_json)}개 항목 발견")
                    
                    # 복구 쿼리 실행
                    if correct_updated_at == "CURRENT_TIMESTAMP":
                        cursor.execute("""
                            UPDATE work_diary 
                            SET todo_list = %s, updated_at = CURRENT_TIMESTAMP 
                            WHERE diary_id = %s
                        """, (json_data, diary_id))
                    else:
                        cursor.execute("""
                            UPDATE work_diary 
                            SET todo_list = %s, updated_at = %s 
                            WHERE diary_id = %s
                        """, (json_data, correct_updated_at, diary_id))
                else:
                    # JSON 데이터가 없는 경우 todo_list를 NULL로 설정
                    st.warning("⚠️ JSON 데이터를 찾을 수 없어 todo_list를 초기화합니다.")
                    cursor.execute("""
                        UPDATE work_diary 
                        SET todo_list = NULL, updated_at = %s 
                        WHERE diary_id = %s
                    """, (correct_updated_at, diary_id))
                
                affected_rows = cursor.rowcount
                st.info(f"📊 영향받은 행 수: {affected_rows}")
                
                if affected_rows > 0:
                    conn.commit()
                    st.success("✅ 데이터가 성공적으로 복구되었습니다!")
                    cursor.close()
                    conn.close()
                    return True
                else:
                    st.error("❌ 업데이트된 행이 없습니다.")
                    cursor.close()
                    conn.close()
                    return False
                
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON 데이터 복구에 실패했습니다: {str(e)}")
                cursor.close()
                conn.close()
                return False
        else:
            # 데이터가 정상인 경우
            st.success("✅ 데이터가 이미 정상 상태입니다!")
            st.info("📋 현재 TODO 리스트가 올바른 위치에 저장되어 있습니다.")
            
            # 상세 분석 결과 표시
            st.info(f"🔍 **분석 결과:**")
            st.info(f"• updated_at이 JSON인가? {is_updated_at_json}")
            st.info(f"• todo_list가 Timestamp인가? {is_todo_list_timestamp}")
            st.info(f"• updated_at 형태: {type(updated_at).__name__} = {updated_at_str}")
            st.info(f"• todo_list 형태: {type(current_todo_list).__name__} = {str(current_todo_list)[:100]}...")
            
            # TODO 리스트 미리보기 테스트
            if current_todo_list:
                try:
                    test_preview = format_todo_list_display(current_todo_list)
                    st.success(f"🎯 **TODO 미리보기 성공:** {test_preview}")
                except Exception as e:
                    st.error(f"❌ TODO 포맷팅 오류: {str(e)}")
                    st.code(f"원본 데이터: {current_todo_list}")
            
            cursor.close()
            conn.close()
            return True
        
    except mysql.connector.Error as err:
        st.error(f"❌ 데이터베이스 오류: {err}")
        return False
    except Exception as e:
        st.error(f"❌ 예상치 못한 오류: {str(e)}")
        return False

def format_todo_list_display(todo_list_json):
    """TODO 리스트를 보기 좋게 포맷하여 반환"""
    if not todo_list_json:
        return "없음"
    
    try:
        # 다양한 형태의 데이터 처리
        todos_data = None
        
        if isinstance(todo_list_json, str):
            # 문자열인 경우 JSON 파싱
            if todo_list_json.strip() in ['', 'null', 'None']:
                return "없음"
            todos_data = json.loads(todo_list_json)
        elif isinstance(todo_list_json, (list, tuple)):
            # 이미 리스트/튜플인 경우
            todos_data = list(todo_list_json)
        elif todo_list_json is None:
            return "없음"
        else:
            # 기타 타입인 경우 문자열로 변환 후 JSON 파싱 시도
            try:
                todos_data = json.loads(str(todo_list_json))
            except:
                return f"형식 오류 (타입: {type(todo_list_json).__name__})"
        
        if not todos_data or not isinstance(todos_data, (list, tuple)):
            return "없음"
        
        # 유효한 TODO 항목들 분리
        completed_items = []
        pending_items = []
        
        for todo in todos_data:
            if isinstance(todo, dict) and todo.get("text"):
                text = str(todo["text"]).strip()
                if text:  # 빈 문자열이 아닌 경우만 추가
                    if todo.get("completed"):
                        completed_items.append(text)
                    else:
                        pending_items.append(text)
        
        if not completed_items and not pending_items:
            return "없음"
        
        # 통계 정보
        total_count = len(completed_items) + len(pending_items)
        completed_count = len(completed_items)
        
        # 간단한 미리보기 (최대 2개 항목만 표시)
        preview_items = []
        
        # 미완료 항목 먼저 표시 (최대 2개)
        for item in pending_items[:2]:
            preview_items.append(f"⏳ {item[:20]}{'...' if len(item) > 20 else ''}")
        
        # 공간이 남으면 완료 항목도 표시
        if len(preview_items) < 2:
            remaining_slots = 2 - len(preview_items)
            for item in completed_items[:remaining_slots]:
                preview_items.append(f"✅ ~~{item[:15]}{'...' if len(item) > 15 else ''}~~")
        
        # 결과 조합
        if preview_items:
            preview_text = " | ".join(preview_items)
            if total_count > 2:
                preview_text += f" (외 {total_count-2}개)"
            
            # 통계 추가
            preview_text += f" [{completed_count}/{total_count} 완료]"
            return preview_text
        else:
            return "없음"
        
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError) as e:
        # 디버깅 정보 포함
        data_preview = str(todo_list_json)[:50] if todo_list_json else "None"
        return f"형식 오류: {data_preview}... (오류: {str(e)[:20]}...)"

def main():
    # DB 테이블 존재 확인
    conn = connect_to_db()
    if not conn:
        st.error("데이터베이스에 연결할 수 없습니다.")
        return
    
    cursor = conn.cursor()
    try:
        # 업무일지 테이블 존재 확인
        cursor.execute("SHOW TABLES LIKE 'work_diary'")
        if not cursor.fetchone():
            st.error("⚠️ 업무일지 테이블이 생성되지 않았습니다. '💾 DB생성' 페이지에서 '업무일지 테이블 생성'을 먼저 실행해주세요.")
            return
    except mysql.connector.Error as err:
        st.error(f"테이블 확인 중 오류: {err}")
        return
    finally:
        cursor.close()
        conn.close()
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📝 업무일지 작성", "📋 업무일지 조회/수정"])
    
    with tab1:
        st.header("업무일지 작성")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            author = st.text_input("작성자", value="이상현", help="업무일지 작성자를 입력하세요")
        
        with col2:
            work_date = st.date_input("업무 날짜", value=date.today(), help="업무 수행 날짜를 선택하세요")
        
        # 날짜와 작성자가 변경되었을 때 기존 데이터 조회
        if 'last_check_date' not in st.session_state or 'last_check_author' not in st.session_state:
            st.session_state.last_check_date = work_date
            st.session_state.last_check_author = author
            st.session_state.existing_diary = None
        
        # 날짜나 작성자가 변경되었을 때
        if (st.session_state.last_check_date != work_date or 
            st.session_state.last_check_author != author):
            
            st.session_state.last_check_date = work_date
            st.session_state.last_check_author = author
            
            # 기존 데이터 조회
            existing_diary = get_diary_by_date_and_author(work_date, author)
            st.session_state.existing_diary = existing_diary
            
            if existing_diary:
                st.success(f"📅 {work_date}에 작성된 {author}님의 업무일지를 불러왔습니다. (수정 모드)")
                st.info(f"🕒 작성일: {existing_diary['created_at']} | 수정일: {existing_diary['updated_at']}")
        
        st.markdown("---")
        
        # TODO 리스트 섹션
        st.subheader("📋 TODO 리스트")
        
        # 기존 TODO 데이터 로드
        existing_todos = []
        if st.session_state.existing_diary and st.session_state.existing_diary.get('todo_list'):
            try:
                existing_todos = json.loads(st.session_state.existing_diary['todo_list'])
            except (json.JSONDecodeError, TypeError):
                existing_todos = []
        
        # TODO 리스트가 비어있으면 기본 빈 항목들로 초기화
        if not existing_todos:
            existing_todos = [{"text": "", "completed": False} for _ in range(10)]
        
        # TODO 항목들이 10개 미만이면 빈 항목들로 채우기
        while len(existing_todos) < 10:
            existing_todos.append({"text": "", "completed": False})
        
        # TODO 입력 필드들
        todos = []
        for i in range(10):
            col1, col2 = st.columns([0.1, 0.9])
            
            with col1:
                completed = st.checkbox(
                    "",
                    value=existing_todos[i].get("completed", False),
                    key=f"todo_check_{i}",
                    help=f"TODO {i+1} 완료 체크"
                )
            
            with col2:
                todo_text = st.text_input(
                    f"TODO {i+1}",
                    value=existing_todos[i].get("text", ""),
                    key=f"todo_text_{i}",
                    placeholder=f"할일 {i+1}을 입력하세요",
                    label_visibility="collapsed"
                )
            
            # TODO 항목이 비어있지 않거나 체크되어 있으면 저장
            if todo_text.strip() or completed:
                todos.append({"text": todo_text.strip(), "completed": completed})
        
        # 완료된 TODO들을 취소선으로 표시
        if todos:
            st.markdown("### 📋 TODO 상태 미리보기")
            for i, todo in enumerate(todos):
                if todo["text"]:
                    if todo["completed"]:
                        st.markdown(f"~~{i+1}. {todo['text']}~~ ✅")
                    else:
                        st.markdown(f"{i+1}. {todo['text']} ⏳")
        
        st.markdown("---")
        
        # 업무 유형별 입력 섹션
        work_types = {
            "PO": {"label": "🛒 PO (Purchase Order)", "key": "po"},
            "통관": {"label": "🛃 통관", "key": "customs"},
            "재고 관리": {"label": "📦 재고 관리", "key": "inventory"},
            "파트너 관리": {"label": "🤝 파트너 관리", "key": "partner"},
            "기타": {"label": "📌 기타", "key": "other"}
        }
        
        diary_content = {}
        uploaded_files = {}
        
        for work_type, info in work_types.items():
            st.subheader(info["label"])
            
            # 기존 데이터가 있으면 value로 설정
            content_key = f"{info['key']}_content"
            existing_content = ""
            if st.session_state.existing_diary:
                existing_content = st.session_state.existing_diary[content_key]
            
            # 텍스트 입력
            diary_content[content_key] = st.text_area(
                f"{work_type} 업무 내용",
                value=existing_content,
                height=150,
                key=f"content_{info['key']}",
                help=f"{work_type} 관련 업무 내용을 상세히 작성해주세요"
            )
            
            # 파일 업로드
            files = st.file_uploader(
                f"{work_type} 관련 파일 첨부",
                accept_multiple_files=True,
                type=['pdf', 'md', 'txt', 'jpg', 'jpeg', 'png', 'csv', 'xlsx', 'xls', 'json', 'html', 'xml'],
                key=f"files_{info['key']}",
                help="PDF, 마크다운, 텍스트, 이미지, Excel, CSV, JSON 등 다양한 파일을 첨부할 수 있습니다"
            )
            
            if files:
                uploaded_files[work_type] = files
                st.success(f"{len(files)}개 파일이 선택되었습니다.")
            
            # 기존 파일이 있으면 표시
            if st.session_state.existing_diary:
                existing_files = get_work_diary_files(st.session_state.existing_diary['diary_id'])
                work_type_files = existing_files[existing_files['work_type'] == work_type]
                
                if not work_type_files.empty:
                    st.markdown(f"**📎 기존 첨부 파일 ({len(work_type_files)}개):**")
                    for _, file_row in work_type_files.iterrows():
                        st.caption(f"• {file_row['filename']} ({file_row['file_size']:,} bytes)")
            
            st.markdown("---")
        
        # 저장 버튼
        button_text = "💾 업무일지 수정" if st.session_state.existing_diary else "📝 업무일지 저장"
        
        if st.button(button_text, type="primary", use_container_width=True):
            if not author.strip():
                st.error("작성자를 입력해주세요.")
                return
            
            # 내용이 하나라도 있는지 확인
            has_content = any(content.strip() for content in diary_content.values()) or uploaded_files
            
            if not has_content:
                st.error("업무 내용을 하나 이상 입력하거나 파일을 첨부해주세요.")
                return
            
            # TODO 리스트를 JSON으로 변환
            todo_list_json = json.dumps(todos, ensure_ascii=False) if todos else None
            
            # 업무일지 저장/수정
            diary_data = {
                'author': author,
                'work_date': work_date,
                'todo_list': todo_list_json,
                **diary_content
            }
            
            existing_diary_id = st.session_state.existing_diary['diary_id'] if st.session_state.existing_diary else None
            diary_id = save_work_diary(diary_data, existing_diary_id)
            
            if diary_id:
                if existing_diary_id:
                    st.success("✅ 업무일지가 수정되었습니다!")
                else:
                    st.success("✅ 업무일지가 저장되었습니다!")
                
                # 파일 저장
                total_files = 0
                saved_files = 0
                
                for work_type, files in uploaded_files.items():
                    for file in files:
                        total_files += 1
                        if save_work_diary_file(diary_id, work_type, file):
                            saved_files += 1
                
                if total_files > 0:
                    if saved_files == total_files:
                        st.success(f"✅ {saved_files}개 파일이 모두 저장되었습니다!")
                    else:
                        st.warning(f"⚠️ {total_files}개 중 {saved_files}개 파일만 저장되었습니다.")
                
                # 상태 초기화 (다음에 다시 로드하기 위해)
                st.session_state.existing_diary = None
                st.session_state.last_check_date = None
                st.session_state.last_check_author = None
                
                # 성공 후 페이지 새로고침을 위한 빈 컨테이너
                st.balloons()
                
            else:
                st.error("❌ 업무일지 저장에 실패했습니다.")
    
    with tab2:
        st.header("업무일지 조회 및 수정")
        
        # 검색 필터
        st.subheader("🔍 검색 필터")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_author = st.text_input("작성자 검색", help="작성자 이름으로 검색")
        
        with col2:
            search_date = st.date_input("날짜 검색", value=None, help="특정 날짜로 검색")
        
        with col3:
            search_content = st.text_input("내용 검색", help="업무 내용에서 키워드 검색")
        
        # 검색 실행
        if st.button("🔍 검색", type="secondary"):
            st.session_state.search_executed = True
        
        # 검색 결과 표시
        if 'search_executed' not in st.session_state:
            st.session_state.search_executed = True
        
        if st.session_state.search_executed:
            diaries_df = get_work_diaries(search_author, search_date, search_content)
            
            if not diaries_df.empty:
                st.subheader(f"📋 검색 결과 ({len(diaries_df)}건)")
                
                # 업무일지 목록 표시
                for index, row in diaries_df.iterrows():
                    # 데이터 무결성 검사: 필드가 잘못된 위치에 저장된 경우 감지
                    updated_at_str = str(row['updated_at']) if row['updated_at'] else ""
                    todo_list_str = str(row['todo_list']) if row['todo_list'] else ""
                    
                    # 손상 케이스 감지 - 더 정확한 판단
                    is_updated_at_json = (updated_at_str.startswith('[{') and updated_at_str.endswith('}]'))
                    
                    # todo_list가 실제 datetime 형식인지 확인 (JSON이 아닌 순수 datetime 문자열)
                    is_todo_list_timestamp = False
                    if row['todo_list'] and not todo_list_str.startswith('[') and not todo_list_str.startswith('{'):
                        # JSON이 아니면서 datetime 패턴과 일치하는 경우
                        datetime_pattern = r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$'
                        is_todo_list_timestamp = bool(re.match(datetime_pattern, todo_list_str.strip()))
                    
                    is_corrupted = is_updated_at_json or is_todo_list_timestamp
                    
                    # TODO 리스트 미리보기
                    if is_corrupted:
                        # 손상된 데이터인 경우 복구 버튼 표시
                        if is_updated_at_json:
                            todo_preview = "🔧 JSON이 잘못된 위치에 저장됨"
                        elif is_todo_list_timestamp:
                            todo_preview = "🔧 시간 데이터가 잘못된 위치에 저장됨"
                        else:
                            todo_preview = "🔧 데이터 복구 필요"
                        expander_title = f"📅 {row['work_date']} - {row['author']} | ⚠️ {todo_preview} (ID: {row['diary_id']})"
                    else:
                        todo_preview = format_todo_list_display(row.get('todo_list'))
                        expander_title = f"📅 {row['work_date']} - {row['author']} | 📋 TODO: {todo_preview} (ID: {row['diary_id']})"
                    
                    with st.expander(expander_title):
                        
                        # 손상된 데이터 복구 옵션
                        if is_corrupted:
                            st.error("⚠️ **데이터 무결성 문제 감지**: 업데이트 시간 필드에 TODO 데이터가 잘못 저장되어 있습니다.")
                            st.info("📋 **복구 가능한 TODO 데이터**:")
                            
                            # 복구 가능한 데이터 미리보기
                            try:
                                corrupted_json = json.loads(updated_at_str)
                                for i, todo in enumerate(corrupted_json):
                                    if todo.get("text"):
                                        status = "✅ 완료" if todo.get("completed") else "⏳ 진행중"
                                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{i+1}. {todo['text']} ({status})")
                            except:
                                st.code(updated_at_str[:200] + "..." if len(updated_at_str) > 200 else updated_at_str)
                            
                            if st.button("🔧 데이터 복구 실행", key=f"fix_{row['diary_id']}", type="primary"):
                                with st.spinner("데이터 복구 중..."):
                                    success = fix_corrupted_diary_data(row['diary_id'])
                                
                                if success:
                                    st.balloons()  # 성공 애니메이션
                                    st.success("🎉 복구 완료! 페이지를 새로고침합니다...")
                                    st.rerun()
                                else:
                                    st.error("❌ 복구에 실패했습니다. 위의 오류 메시지를 확인해주세요.")
                            
                            st.markdown("---")
                        
                        # 수정 모드 체크박스
                        edit_mode = st.checkbox(f"수정 모드", key=f"edit_{row['diary_id']}")
                        
                        if edit_mode:
                            # 수정 가능한 폼
                            st.markdown("### ✏️ 수정하기")
                            
                            edit_author = st.text_input("작성자", value=row['author'], key=f"edit_author_{row['diary_id']}")
                            edit_date = st.date_input("업무 날짜", value=row['work_date'], key=f"edit_date_{row['diary_id']}")
                            
                            edit_content = {}
                            uploaded_files_edit = {}
                            
                            # TODO 리스트 수정 섹션
                            st.subheader("📋 TODO 리스트 수정")
                            
                            # 기존 TODO 데이터 로드
                            existing_edit_todos = []
                            if row.get('todo_list'):
                                try:
                                    existing_edit_todos = json.loads(row['todo_list'])
                                except (json.JSONDecodeError, TypeError):
                                    existing_edit_todos = []
                            
                            # TODO 리스트가 비어있으면 기본 빈 항목들로 초기화
                            if not existing_edit_todos:
                                existing_edit_todos = [{"text": "", "completed": False} for _ in range(10)]
                            
                            # TODO 항목들이 10개 미만이면 빈 항목들로 채우기
                            while len(existing_edit_todos) < 10:
                                existing_edit_todos.append({"text": "", "completed": False})
                            
                            # TODO 입력 필드들
                            edit_todos = []
                            for i in range(10):
                                col1, col2 = st.columns([0.1, 0.9])
                                
                                with col1:
                                    edit_completed = st.checkbox(
                                        "",
                                        value=existing_edit_todos[i].get("completed", False),
                                        key=f"edit_todo_check_{i}_{row['diary_id']}",
                                        help=f"TODO {i+1} 완료 체크"
                                    )
                                
                                with col2:
                                    edit_todo_text = st.text_input(
                                        f"TODO {i+1}",
                                        value=existing_edit_todos[i].get("text", ""),
                                        key=f"edit_todo_text_{i}_{row['diary_id']}",
                                        placeholder=f"할일 {i+1}을 입력하세요",
                                        label_visibility="collapsed"
                                    )
                                
                                # TODO 항목이 비어있지 않거나 체크되어 있으면 저장
                                if edit_todo_text.strip() or edit_completed:
                                    edit_todos.append({"text": edit_todo_text.strip(), "completed": edit_completed})
                            
                            # 완료된 TODO들을 취소선으로 표시
                            if edit_todos:
                                st.markdown("#### 📋 TODO 상태 미리보기")
                                for i, todo in enumerate(edit_todos):
                                    if todo["text"]:
                                        if todo["completed"]:
                                            st.markdown(f"~~{i+1}. {todo['text']}~~ ✅")
                                        else:
                                            st.markdown(f"{i+1}. {todo['text']} ⏳")
                            
                            st.markdown("---")
                            
                            for work_type, info in work_types.items():
                                st.subheader(f"{info['label']} 수정")
                                
                                content_key = f"{info['key']}_content"
                                current_content = row[content_key] if row[content_key] else ""
                                edit_content[content_key] = st.text_area(
                                    f"{work_type} 업무 내용",
                                    value=current_content,
                                    height=100,
                                    key=f"edit_{content_key}_{row['diary_id']}"
                                )
                                
                                # 파일 업로드 (수정 모드)
                                edit_files = st.file_uploader(
                                    f"{work_type} 관련 파일 추가",
                                    accept_multiple_files=True,
                                    type=['pdf', 'md', 'txt', 'jpg', 'jpeg', 'png', 'csv', 'xlsx', 'xls', 'json'],
                                    key=f"edit_files_{info['key']}_{row['diary_id']}",
                                    help="새로운 파일을 추가할 수 있습니다"
                                )
                                
                                if edit_files:
                                    uploaded_files_edit[work_type] = edit_files
                                    st.success(f"{len(edit_files)}개 새 파일이 선택되었습니다.")
                                
                                # 기존 파일 표시
                                existing_files_edit = get_work_diary_files(row['diary_id'])
                                work_type_files_edit = existing_files_edit[existing_files_edit['work_type'] == work_type]
                                
                                if not work_type_files_edit.empty:
                                    st.markdown(f"**📎 기존 첨부 파일 ({len(work_type_files_edit)}개):**")
                                    for _, file_row_edit in work_type_files_edit.iterrows():
                                        col_file_edit1, col_file_edit2 = st.columns([4, 1])
                                        
                                        with col_file_edit1:
                                            st.caption(f"• {file_row_edit['filename']} ({file_row_edit['file_size']:,} bytes)")
                                        
                                        with col_file_edit2:
                                            if st.button("🗑️", key=f"del_edit_file_{file_row_edit['file_id']}", help="파일 삭제"):
                                                if delete_work_diary_file(file_row_edit['file_id']):
                                                    st.success("파일이 삭제되었습니다.")
                                                    st.rerun()
                                                else:
                                                    st.error("파일 삭제에 실패했습니다.")
                                
                                st.markdown("---")
                            
                            col_save, col_delete = st.columns(2)
                            
                            with col_save:
                                if st.button("💾 수정 저장", key=f"save_{row['diary_id']}", type="primary"):
                                    # TODO 리스트를 JSON으로 변환
                                    edit_todo_list_json = json.dumps(edit_todos, ensure_ascii=False) if edit_todos else None
                                    
                                    edit_data = {
                                        'author': edit_author,
                                        'work_date': edit_date,
                                        'todo_list': edit_todo_list_json,
                                        **edit_content
                                    }
                                    
                                    if update_work_diary(row['diary_id'], edit_data):
                                        # 새 파일들 저장
                                        total_new_files = 0
                                        saved_new_files = 0
                                        
                                        for work_type, files in uploaded_files_edit.items():
                                            for file in files:
                                                total_new_files += 1
                                                if save_work_diary_file(row['diary_id'], work_type, file):
                                                    saved_new_files += 1
                                        
                                        if total_new_files > 0:
                                            if saved_new_files == total_new_files:
                                                st.success(f"✅ 업무일지가 수정되었고, {saved_new_files}개 새 파일이 저장되었습니다!")
                                            else:
                                                st.warning(f"✅ 업무일지는 수정되었지만, {total_new_files}개 중 {saved_new_files}개 파일만 저장되었습니다.")
                                        else:
                                            st.success("✅ 업무일지가 수정되었습니다!")
                                        
                                        st.rerun()
                                    else:
                                        st.error("❌ 수정에 실패했습니다.")
                            
                            with col_delete:
                                if st.button("🗑️ 삭제", key=f"delete_{row['diary_id']}", type="secondary"):
                                    if delete_work_diary(row['diary_id']):
                                        st.success("✅ 업무일지가 삭제되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error("❌ 삭제에 실패했습니다.")
                        
                        else:
                            # 읽기 전용 모드
                            st.markdown(f"**작성일:** {row['created_at']}")
                            if row['updated_at'] != row['created_at']:
                                st.markdown(f"**수정일:** {row['updated_at']}")
                            
                            # TODO 리스트 표시 (개선된 버전)
                            if row.get('todo_list'):
                                try:
                                    todos_data = json.loads(row['todo_list'])
                                    if todos_data:
                                        # 완료된 항목과 미완료 항목 분리
                                        completed_todos = []
                                        pending_todos = []
                                        
                                        for todo in todos_data:
                                            if todo.get("text"):
                                                if todo.get("completed"):
                                                    completed_todos.append(todo["text"])
                                                else:
                                                    pending_todos.append(todo["text"])
                                        
                                        if completed_todos or pending_todos:
                                            st.markdown("### 📋 TODO 리스트")
                                            
                                            # 미완료 항목 먼저 표시
                                            if pending_todos:
                                                st.markdown("**⏳ 진행 중:**")
                                                for i, todo_text in enumerate(pending_todos, 1):
                                                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{i}. {todo_text}")
                                            
                                            # 완료된 항목 표시
                                            if completed_todos:
                                                st.markdown("**✅ 완료:**")
                                                for i, todo_text in enumerate(completed_todos, 1):
                                                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;~~{i}. {todo_text}~~")
                                            
                                            st.markdown("---")
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            
                            # 업무 내용 표시
                            for work_type, info in work_types.items():
                                content_key = f"{info['key']}_content"
                                if row[content_key]:
                                    st.markdown(f"**{info['label']}**")
                                    st.text_area(
                                        "",
                                        value=row[content_key],
                                        height=100,
                                        disabled=True,
                                        key=f"view_{content_key}_{row['diary_id']}"
                                    )
                        
                        # 첨부 파일 표시
                        files_df = get_work_diary_files(row['diary_id'])
                        
                        if not files_df.empty:
                            st.markdown("### 📎 첨부 파일")
                            
                            for file_index, file_row in files_df.iterrows():
                                col_file1, col_file2, col_file3 = st.columns([3, 1, 1])
                                
                                with col_file1:
                                    st.write(f"**{file_row['work_type']}** - {file_row['filename']}")
                                    st.caption(f"크기: {file_row['file_size']:,} bytes | 업로드: {file_row['uploaded_at']}")
                                
                                with col_file2:
                                    # 다운로드 버튼
                                    file_data = get_file_binary_data(file_row['file_id'])
                                    if file_data:
                                        st.download_button(
                                            "💾 다운로드",
                                            data=file_data['binary_data'],
                                            file_name=file_data['filename'],
                                            key=f"download_{file_row['file_id']}"
                                        )
                                
                                with col_file3:
                                    # 미리보기 버튼 (토글 방식)
                                    if st.button("👁️ 미리보기", key=f"preview_{file_row['file_id']}", help="파일 미리보기"):
                                        st.session_state[f"show_preview_{file_row['file_id']}"] = not st.session_state.get(f"show_preview_{file_row['file_id']}", False)
                                
                                # 파일 미리보기 표시
                                if st.session_state.get(f"show_preview_{file_row['file_id']}", False):
                                    st.subheader("📖 파일 미리보기")
                                    
                                    # 원본 파일 데이터 가져오기
                                    file_binary = get_file_binary_data(file_row['file_id'])
                                    
                                    if file_binary:
                                        # 디버깅 정보 표시 (파일 타입 확인용)
                                        st.caption(f"🔍 파일 정보: 타입={file_binary['file_type']}, 이름={file_binary['filename']}")
                                        
                                        # 파일 미리보기 함수 호출
                                        preview_success = display_file_preview(file_binary, file_binary['file_type'], file_binary['filename'])
                                        
                                        # 미리보기가 실패하거나 지원하지 않는 형식인 경우 기본 정보 표시
                                        if not preview_success:
                                            st.info(f"파일 형식: {file_binary['file_type']}")
                                            st.info(f"파일 크기: {file_row['file_size']:,} bytes")
                                    else:
                                        st.error("파일 데이터를 불러올 수 없습니다.")
                                    
                                    # 미리보기 숨기기 버튼
                                    if st.button("🙈 미리보기 숨기기", key=f"hide_preview_{file_row['file_id']}"):
                                        st.session_state[f"show_preview_{file_row['file_id']}"] = False
                                        st.rerun()
                
            else:
                st.info("검색 결과가 없습니다.")

if __name__ == "__main__":
    main() 