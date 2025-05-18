import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

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

def create_vote():
    st.write("## 객관식 투표 생성")
    
    # 투표 제목
    title = st.text_input("투표 제목", key="vote_title")
    
    # 투표 설명
    description = st.text_area("투표 설명", key="vote_description")
    
    # 선택지 입력
    st.write("### 선택지 입력")
    num_options = st.number_input("선택지 개수", min_value=2, value=2)
    options = []
    
    for i in range(int(num_options)):
        option = st.text_input(f"선택지 {i+1}", key=f"option_{i}")
        options.append(option)
    
    # 작성자 이름
    created_by = st.text_input("작성자 이름", key="vote_created_by")
    
    if st.button("투표 생성", key="create_vote"):
        if not title:
            st.error("투표 제목을 입력해주세요.")
            return
        if not created_by:
            st.error("작성자 이름을 입력해주세요.")
            return
        if not all(options):
            st.error("모든 선택지를 입력해주세요.")
            return
            
        conn = connect_to_db()
        if not conn:
            st.error("데이터베이스 연결에 실패했습니다.")
            return
            
        cursor = conn.cursor()
        try:
            # 투표 질문 저장
            cursor.execute("""
                INSERT INTO vote_questions 
                (title, description, created_by)
                VALUES (%s, %s, %s)
            """, (title, description, created_by))
            
            question_id = cursor.lastrowid
            
            # 선택지 저장
            for option_text in options:
                cursor.execute("""
                    INSERT INTO vote_options 
                    (question_id, option_text)
                    VALUES (%s, %s)
                """, (question_id, option_text))
            
            conn.commit()
            st.success("투표가 성공적으로 생성되었습니다!")
            
            # 입력 필드 초기화
            st.session_state.vote_title = ""
            st.session_state.vote_description = ""
            st.session_state.vote_created_by = ""
            for i in range(len(options)):
                st.session_state[f"option_{i}"] = ""
            
        except mysql.connector.Error as err:
            st.error(f"투표 생성 중 오류가 발생했습니다: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

def create_subjective_question():
    st.write("## 주관식 질문 생성")
    
    # 질문 제목
    title = st.text_input("질문 제목", key="subjective_title")
    
    # 질문 설명
    description = st.text_area("질문 설명", key="subjective_description")
    
    # 다중 선택 허용 여부
    col1, col2 = st.columns([1, 2])
    with col1:
        multiple_answers = st.checkbox("다중 선택 허용", key="multiple_answers")
    
    # 다중 선택 허용 시 응답 개수 선택 (기본값 4)
    max_answers = None
    if multiple_answers:
        with col2:
            max_answers = st.radio(
                "최대 응답 개수",
                options=[2, 3, 4],
                index=2,  # 4를 기본값으로 설정 (0-based index)
                horizontal=True,
                help="응답자가 입력할 수 있는 최대 답변 개수를 선택하세요."
            )
    
    # 작성자 이름
    created_by = st.text_input("작성자 이름", key="subjective_created_by")
    
    if st.button("질문 생성", key="create_subjective"):
        if not title:
            st.error("질문 제목을 입력해주세요.")
            return
        if not created_by:
            st.error("작성자 이름을 입력해주세요.")
            return
            
        conn = connect_to_db()
        if not conn:
            st.error("데이터베이스 연결에 실패했습니다.")
            return
            
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO subjective_questions 
                (title, description, created_by, multiple_answers, max_answers)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, description, created_by, multiple_answers, max_answers))
            
            conn.commit()
            st.success("주관식 질문이 성공적으로 생성되었습니다!")
            
            # 입력 필드 초기화
            st.session_state.subjective_title = ""
            st.session_state.subjective_description = ""
            st.session_state.multiple_answers = False
            st.session_state.subjective_created_by = ""
            
        except mysql.connector.Error as err:
            st.error(f"질문 생성 중 오류가 발생했습니다: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

def main():
    st.title("투표 생성")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📊 객관식 투표", "✏️ 주관식 투표"])
    
    with tab1:
        create_vote()
    
    with tab2:
        create_subjective_question()

if __name__ == "__main__":
    main() 