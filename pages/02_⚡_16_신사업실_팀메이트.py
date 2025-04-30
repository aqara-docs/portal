import streamlit as st
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
    page_title="팀메이트 관리",
    page_icon="👥",
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

def check_table_exists():
    """팀메이트 테이블 존재 여부 확인"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'self_introductions'
        """, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        
        result = cursor.fetchone()
        return result[0] > 0
    except mysql.connector.Error as e:
        st.error(f"테이블 확인 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def create_table_if_not_exists():
    """팀메이트 테이블이 없으면 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS self_introductions")
        
        # 새 테이블 생성
        cursor.execute("""
            CREATE TABLE self_introductions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(100) NOT NULL,
                name VARCHAR(100) NOT NULL,
                position VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                expertise TEXT NOT NULL,
                current_tasks TEXT NOT NULL,
                collaboration_style TEXT NOT NULL,
                support_areas TEXT NOT NULL,
                need_help_areas TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"테이블 생성 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_introduction(data):
    """팀메이트 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO self_introductions 
            (email, password, name, position, department, expertise, current_tasks, 
             collaboration_style, support_areas, need_help_areas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['email'], data['password'], data['name'], data['position'], data['department'],
            data['expertise'], data['current_tasks'],
            data['collaboration_style'], data['support_areas'],
            data['need_help_areas']
        ))
        
        conn.commit()
        return True
    except mysql.connector.Error as e:
        if e.errno == 1062:  # 중복 키 에러
            st.error(f"이미 등록된 이메일입니다. 수정하시려면 수정 기능을 이용해주세요.")
        else:
            st.error(f"저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def verify_password(id, password):
    """팀메이트 비밀번호 확인"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT password FROM self_introductions 
            WHERE id = %s
        """, (id,))
        result = cursor.fetchone()
        return result and result['password'] == password
    finally:
        cursor.close()
        conn.close()

def update_introduction(id, data, current_password):
    """팀메이트 수정"""
    # 비밀번호 확인
    if not verify_password(id, current_password):
        st.error("비밀번호가 일치하지 않습니다.")
        return False
        
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE self_introductions 
            SET email = %s, password = %s, name = %s, position = %s, department = %s,
                expertise = %s, current_tasks = %s,
                collaboration_style = %s, support_areas = %s,
                need_help_areas = %s
            WHERE id = %s
        """, (
            data['email'], data['password'], data['name'], data['position'], data['department'],
            data['expertise'], data['current_tasks'],
            data['collaboration_style'], data['support_areas'],
            data['need_help_areas'], id
        ))
        
        conn.commit()
        return True
    except mysql.connector.Error as e:
        if e.errno == 1062:  # 중복 키 에러
            st.error(f"이미 등록된 이메일입니다. 다른 이메일을 사용해주세요.")
        else:
            st.error(f"수정 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_introduction_by_email(email):
    """이메일로 팀메이트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM self_introductions 
            WHERE email = %s
        """, (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_introduction(id):
    """팀메이트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM self_introductions 
            WHERE id = %s
        """, (id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def search_introductions(keyword):
    """팀메이트 검색"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM self_introductions 
            WHERE expertise LIKE %s 
            OR support_areas LIKE %s
            OR current_tasks LIKE %s
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_all_introductions():
    """모든 팀메이트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM self_introductions ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def ai_search_help(query):
    """AI를 통한 검색 도움"""
    try:
        # 모든 자기소개서 데이터 가져오기
        introductions = get_all_introductions()
        
        # AI 프롬프트 생성
        prompt = f"""
        다음은 회사 직원들의 팀메이트 목록입니다:
        
        {json.dumps([{
            '이름': intro['name'],
            '직책': intro['position'],
            '부서': intro['department'],
            '전문분야': intro['expertise'],
            '현재업무': intro['current_tasks'],
            '협업스타일': intro['collaboration_style'],
            '지원가능영역': intro['support_areas'],
            '도움필요영역': intro['need_help_areas']
        } for intro in introductions], ensure_ascii=False, indent=2)}
        
        다음 요청에 가장 적합한 직원을 찾아주세요:
        "{query}"
        
        다음 형식으로 응답해주세요:
        1. 추천 직원 (우선순위 순)
        2. 추천 이유
        3. 협업 제안
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 회사의 인재 매칭 전문가입니다. 업무 요청에 가장 적합한 직원을 찾아 매칭해주는 역할을 합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def delete_introduction(id, password=None, is_admin=False):
    """팀메이트 삭제"""
    # 관리자가 아닌 경우 비밀번호 확인
    if not is_admin and not verify_password(id, password):
        st.error("비밀번호가 일치하지 않습니다.")
        return False
        
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM self_introductions WHERE id = %s", (id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def verify_admin_password(input_password):
    """관리자 비밀번호 확인"""
    return input_password == os.getenv('ADMIN_PASSWORD')

def main():
    # 세션 상태 초기화
    if 'delete_state' not in st.session_state:
        st.session_state.delete_state = False
    
    # 테이블 존재 여부 확인
    if not check_table_exists():
        st.error("자기소개서 테이블이 없습니다. DB 생성 페이지에서 테이블을 먼저 생성해주세요.")
        return
        
    st.title("👥 팀메이트 관리")
    
    tab1, tab2, tab3 = st.tabs(["🔍 검색", "📝 등록/수정", "⚙️ 관리자 모드"])
    
    with tab1:
        st.header("도움이 필요한 분야 검색")
        
        search_query = st.text_input(
            "검색어를 입력하세요",
            placeholder="예: 파이썬 개발, 프로젝트 관리, 디자인 등"
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
                    results = search_introductions(search_query)
                    if results:
                        for result in results:
                            with st.expander(f"{result['name']} ({result['position']} - {result['department']})"):
                                st.write("#### 전문 분야/강점")
                                st.write(result['expertise'])
                                st.write("#### 현재 담당 업무")
                                st.write(result['current_tasks'])
                                st.write("#### 지원 가능 영역")
                                st.write(result['support_areas'])
                                st.write("#### 선호하는 협업 방식")
                                st.write(result['collaboration_style'])
                    else:
                        st.info("검색 결과가 없습니다.")
                else:  # AI 도움
                    with st.spinner("AI가 적합한 동료를 찾고 있습니다..."):
                        ai_result = ai_search_help(search_query)
                        if ai_result:
                            st.write("### AI 추천 결과")
                            st.write(ai_result)
    
    with tab2:
        st.header("팀메이트 등록/수정")
        
        # 이메일과 비밀번호 입력 컬럼
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("이메일 (필수)", placeholder="example@company.com", key="email_input")
        with col2:
            password = st.text_input("비밀번호 (필수)", type="password", help="자기소개서 수정 및 삭제 시 필요합니다", key="password_input")
        
        # 이메일과 비밀번호가 모두 입력된 경우에만 기존 데이터 확인
        existing_data = None
        show_form = False
        
        if email and password:
            existing_data = get_introduction_by_email(email)
            if existing_data:
                if verify_password(existing_data['id'], password):
                    st.success(f"'{email}' 계정으로 등록된 자기소개서를 불러왔습니다.")
                    show_form = True
                    
                    # 삭제 기능
                    if 'delete_state' not in st.session_state:
                        st.session_state.delete_state = False
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col3:
                        if not st.session_state.delete_state:
                            if st.button("🗑️ 삭제", type="secondary", use_container_width=True, key="delete_btn"):
                                st.session_state.delete_state = True
                                st.rerun()
                        else:
                            st.warning("정말 삭제하시겠습니까?")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("취소", use_container_width=True, key="cancel_btn"):
                                    st.session_state.delete_state = False
                                    st.rerun()
                            with col2:
                                if st.button("삭제 확인", type="primary", use_container_width=True, key="confirm_delete_btn"):
                                    if delete_introduction(existing_data['id'], password):
                                        st.success("자기소개서가 삭제되었습니다!")
                                        st.session_state.delete_state = False
                                        time.sleep(1)
                                        st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")
            else:
                st.info("새로운 자기소개서를 작성합니다.")
                show_form = True
        
        # 폼 표시
        if show_form and not st.session_state.delete_state:
            with st.form("introduction_form"):
                if existing_data:
                    name = st.text_input("이름", value=existing_data['name'])
                    position = st.text_input("직책", value=existing_data['position'])
                    department = st.text_input("부서", value=existing_data['department'])
                    expertise = st.text_area("전문 분야/강점", value=existing_data['expertise'])
                    current_tasks = st.text_area("현재 담당 업무", value=existing_data['current_tasks'])
                    collaboration_style = st.text_area("선호하는 협업 방식", value=existing_data['collaboration_style'])
                    support_areas = st.text_area("지원 가능 영역", value=existing_data['support_areas'])
                    need_help_areas = st.text_area("도움이 필요한 부분", value=existing_data['need_help_areas'])
                else:
                    name = st.text_input("이름")
                    position = st.text_input("직책")
                    department = st.text_input("부서")
                    expertise = st.text_area("전문 분야/강점", placeholder="핵심 기술과 잘하는 분야를 작성해주세요")
                    current_tasks = st.text_area("현재 담당 업무", placeholder="주요 책임과 프로젝트를 작성해주세요")
                    collaboration_style = st.text_area("선호하는 협업 방식", placeholder="의사소통 스타일과 업무 처리 방식을 작성해주세요")
                    support_areas = st.text_area("지원 가능 영역", placeholder="현 업무 외에 도움 줄 수 있는 분야를 작성해주세요")
                    need_help_areas = st.text_area("도움이 필요한 부분", placeholder="협업이나 지원이 필요한 영역을 작성해주세요")
                
                submit_button = st.form_submit_button("저장", type="primary")
                
                if submit_button:
                    data = {
                        'email': email,
                        'password': password,
                        'name': name,
                        'position': position,
                        'department': department,
                        'expertise': expertise,
                        'current_tasks': current_tasks,
                        'collaboration_style': collaboration_style,
                        'support_areas': support_areas,
                        'need_help_areas': need_help_areas
                    }
                    
                    if all(data.values()):  # 모든 필드가 입력되었는지 확인
                        success = False
                        if existing_data:  # 수정
                            success = update_introduction(existing_data['id'], data, password)
                            if success:
                                st.success("자기소개서가 성공적으로 수정되었습니다! 🎉")
                                time.sleep(1)  # 메시지를 잠시 보여줌
                                st.rerun()
                        else:  # 새로 저장
                            success = save_introduction(data)
                            if success:
                                st.success("자기소개서가 성공적으로 저장되었습니다! 🎉")
                                time.sleep(1)  # 메시지를 잠시 보여줌
                                st.rerun()
                    else:
                        st.error("모든 항목을 입력해주세요.")
        elif not email:
            st.info("이메일을 입력해주세요.")
        elif not password:
            st.info("비밀번호를 입력해주세요.")

    with tab3:
        st.header("관리자 모드")
        
        # 관리자 인증
        admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
        if admin_password:
            if verify_admin_password(admin_password):
                st.success("관리자 인증 성공")
                
                # 모든 자기소개서 목록 표시
                all_intros = get_all_introductions()
                if all_intros:
                    st.subheader("등록된 자기소개서 목록")
                    
                    # 검색 필터
                    search_term = st.text_input("이름, 부서, 이메일로 검색", key="admin_search")
                    filtered_intros = all_intros
                    if search_term:
                        filtered_intros = [
                            intro for intro in all_intros
                            if search_term.lower() in intro['name'].lower() or
                               search_term.lower() in intro['department'].lower() or
                               search_term.lower() in intro['email'].lower()
                        ]
                    
                    # 자기소개서 목록 표시
                    for intro in filtered_intros:
                        with st.expander(f"{intro['name']} ({intro['position']} - {intro['department']})"):
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"**이메일:** {intro['email']}")
                                st.write("#### 전문 분야/강점")
                                st.write(intro['expertise'])
                                st.write("#### 현재 담당 업무")
                                st.write(intro['current_tasks'])
                                st.write("#### 지원 가능 영역")
                                st.write(intro['support_areas'])
                            with col2:
                                if st.button("🗑️ 삭제", key=f"admin_delete_{intro['id']}", type="secondary"):
                                    if delete_introduction(intro['id'], is_admin=True):
                                        st.success(f"{intro['name']}의 자기소개서가 삭제되었습니다.")
                                        time.sleep(1)
                                        st.rerun()
                else:
                    st.info("등록된 자기소개서가 없습니다.")
            else:
                st.error("관리자 비밀번호가 일치하지 않습니다.")

if __name__ == "__main__":
    main() 