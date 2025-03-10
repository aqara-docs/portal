import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Vote 참여", page_icon="🗳️", layout="wide")

# Page header
st.title("투표 참여")

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

def get_active_questions():
    """활성화된 투표 목록 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM vote_questions 
            WHERE status = 'active' 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_question_options(question_id):
    """질문의 선택지 목록 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM vote_options 
            WHERE question_id = %s
            ORDER BY option_id
        """, (question_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def check_duplicate_vote(question_id, voter_name):
    """중복 투표 확인"""
    if voter_name == "익명":
        return False
        
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM vote_responses 
            WHERE question_id = %s AND voter_name = %s
        """, (question_id, voter_name))
        count = cursor.fetchone()[0]
        return count > 0
    finally:
        cursor.close()
        conn.close()

def save_vote(question_id, option_ids, voter_name, reasoning=""):
    """투표 저장"""
    if check_duplicate_vote(question_id, voter_name):
        return False, "이미 투표하셨습니다."
    
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        for option_id in option_ids:
            cursor.execute("""
                INSERT INTO vote_responses 
                (question_id, option_id, voter_name, reasoning)
                VALUES (%s, %s, %s, %s)
            """, (question_id, option_id, voter_name, reasoning))
        conn.commit()
        return True, "투표가 성공적으로 저장되었습니다!"
    except mysql.connector.Error as err:
        return False, f"투표 저장 중 오류가 발생했습니다: {err}"
    finally:
        cursor.close()
        conn.close()

def main():
    # 사용자 이름 입력 (선택사항)
    if 'voter_name' not in st.session_state:
        st.session_state.voter_name = ""
    
    st.session_state.voter_name = st.text_input(
        "이름 (선택사항)",
        value=st.session_state.voter_name,
        help="이름을 입력하지 않으면 '익명'으로 투표됩니다."
    )
    
    # 활성화된 투표 목록 가져오기
    questions = get_active_questions()
    
    if not questions:
        st.info("현재 진행 중인 투표가 없습니다.")
        return
    
    # 각 투표에 대한 폼 생성
    for q in questions:
        st.write("---")
        st.write(f"## {q['title']}")
        st.write(q['description'])
        
        options = get_question_options(q['question_id'])
        if not options:
            st.error("선택지가 없는 투표입니다.")
            continue
        
        with st.form(f"vote_form_{q['question_id']}"):
            if q['multiple_choice']:
                selected_options = []
                for opt in options:
                    if st.checkbox(opt['option_text'], key=f"opt_{q['question_id']}_{opt['option_id']}"):
                        selected_options.append(opt['option_id'])
            else:
                option_texts = [opt['option_text'] for opt in options]
                selected_index = st.radio(
                    "선택지",
                    range(len(options)),
                    format_func=lambda x: option_texts[x],
                    key=f"radio_{q['question_id']}"
                )
                selected_options = [options[selected_index]['option_id']]
            
            # 선택 이유 입력 필드 추가
            reasoning = st.text_area(
                "선택 이유 (선택사항)",
                help="선택하신 이유를 자유롭게 작성해주세요."
            )
            
            if st.form_submit_button("투표하기"):
                if not selected_options:
                    st.error("최소 하나의 선택지를 선택해주세요.")
                else:
                    success, message = save_vote(
                        q['question_id'], 
                        selected_options,
                        st.session_state.voter_name or "익명",
                        reasoning
                    )
                    
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

if __name__ == "__main__":
    main() 