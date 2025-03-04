import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Vote Question 등록", page_icon="📋", layout="wide")

# Page header
st.title("투표 문제 등록")

# MySQL 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def save_question(title, description, multiple_choice, options, created_by):
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 문제 저장
        cursor.execute("""
            INSERT INTO vote_questions 
            (title, description, multiple_choice, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, multiple_choice, created_by))
        
        # 방금 삽입한 question_id 가져오기
        question_id = cursor.lastrowid
        
        # 선택지 저장
        for option in options:
            if option.strip():  # 빈 옵션은 건너뛰기
                cursor.execute("""
                    INSERT INTO vote_options 
                    (question_id, option_text)
                    VALUES (%s, %s)
                """, (question_id, option))
        
        conn.commit()
        return True, "투표 문제가 성공적으로 저장되었습니다!"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"저장 중 오류가 발생했습니다: {err}"
        
    finally:
        cursor.close()
        conn.close()

def main():
    st.write("## 새로운 투표 문제 등록")
    
    # 입력 폼
    with st.form("vote_question_form"):
        title = st.text_input("제목", help="투표 문제의 제목을 입력하세요")
        description = st.text_area("설명", help="문제에 대한 자세한 설명을 입력하세요")
        multiple_choice = st.checkbox("다중 선택 허용", help="참가자가 여러 개의 옵션을 선택할 수 있도록 허용")
        created_by = st.text_input("작성자", help="문제 작성자의 이름을 입력하세요")
        
        st.write("### 선택지 입력")
        st.write("최대 10개의 선택지를 입력할 수 있습니다. 빈 칸은 무시됩니다.")
        
        # 10개의 선택지 입력 필드
        options = []
        for i in range(10):
            option = st.text_input(f"선택지 {i+1}", key=f"option_{i}")
            options.append(option)
        
        submit_button = st.form_submit_button("저장")
        
        if submit_button:
            # 기본 검증
            if not title:
                st.error("제목을 입력해주세요.")
                return
                
            if not created_by:
                st.error("작성자 이름을 입력해주세요.")
                return
                
            # 최소 2개의 유효한 선택지가 있는지 확인
            valid_options = [opt for opt in options if opt.strip()]
            if len(valid_options) < 2:
                st.error("최소 2개의 선택지를 입력해주세요.")
                return
            
            # 저장 처리
            success, message = save_question(
                title, description, multiple_choice, valid_options, created_by
            )
            
            if success:
                st.success(message)
                # 폼 초기화를 위한 rerun
                st.rerun()
            else:
                st.error(message)

    # 기존 투표 문제 목록 표시
    st.write("## 등록된 투표 문제 목록")
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT q.*, 
                   COUNT(DISTINCT o.option_id) as option_count,
                   COUNT(DISTINCT r.response_id) as response_count
            FROM vote_questions q
            LEFT JOIN vote_options o ON q.question_id = o.question_id
            LEFT JOIN vote_responses r ON q.question_id = r.question_id
            GROUP BY q.question_id
            ORDER BY q.created_at DESC
        """)
        questions = cursor.fetchall()
        
        for q in questions:
            with st.expander(f"📊 {q['title']} ({q['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                st.write(f"**설명:** {q['description']}")
                st.write(f"**작성자:** {q['created_by']}")
                st.write(f"**다중 선택:** {'예' if q['multiple_choice'] else '아니오'}")
                st.write(f"**선택지 수:** {q['option_count']}")
                st.write(f"**총 응답 수:** {q['response_count']}")
                st.write(f"**상태:** {q['status']}")
                
                # 선택지 목록 표시
                cursor.execute("""
                    SELECT option_text, 
                           (SELECT COUNT(*) FROM vote_responses WHERE option_id = vo.option_id) as vote_count
                    FROM vote_options vo
                    WHERE question_id = %s
                """, (q['question_id'],))
                options = cursor.fetchall()
                
                st.write("### 선택지:")
                for opt in options:
                    st.write(f"- {opt['option_text']} (투표 수: {opt['vote_count']})")
                
    except mysql.connector.Error as err:
        st.error(f"데이터 조회 중 오류가 발생했습니다: {err}")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 