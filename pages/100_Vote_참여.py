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
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT q.*, COUNT(DISTINCT o.option_id) as option_count
            FROM vote_questions q
            LEFT JOIN vote_options o ON q.question_id = o.question_id
            WHERE q.status = 'active'
            GROUP BY q.question_id
            ORDER BY q.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_question_options(question_id):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT option_id, option_text
            FROM vote_options
            WHERE question_id = %s
            ORDER BY option_id
        """, (question_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_vote(question_id, selected_options, voter_name):
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 이전 투표 확인 (같은 사용자가 같은 질문에 투표했는지)
        if voter_name != "익명":
            cursor.execute("""
                SELECT COUNT(*) 
                FROM vote_responses 
                WHERE question_id = %s AND voter_name = %s
            """, (question_id, voter_name))
            
            if cursor.fetchone()[0] > 0:
                return False, "이미 이 질문에 투표하셨습니다."
        
        # 새 투표 저장
        for option_id in selected_options:
            cursor.execute("""
                INSERT INTO vote_responses 
                (question_id, option_id, voter_name)
                VALUES (%s, %s, %s)
            """, (question_id, option_id, voter_name))
        
        conn.commit()
        return True, "투표가 성공적으로 저장되었습니다!"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"투표 저장 중 오류가 발생했습니다: {err}"
        
    finally:
        cursor.close()
        conn.close()

def main():
    # 사용자 이름 입력 (세션 상태 관리)
    if 'voter_name' not in st.session_state:
        st.session_state.voter_name = "익명"
    
    # 사용자 이름 입력 UI
    col1, col2 = st.columns([3, 1])
    with col1:
        st.session_state.voter_name = st.text_input(
            "이름 (선택사항)", 
            value=st.session_state.voter_name,
            help="익명으로 투표하려면 비워두세요"
        )
    with col2:
        if st.button("익명으로 투표"):
            st.session_state.voter_name = "익명"
            st.rerun()
    
    # 활성화된 투표 목록 가져오기
    questions = get_active_questions()
    
    if not questions:
        st.info("현재 진행 중인 투표가 없습니다.")
        return
    
    # 투표 선택 및 참여
    for q in questions:
        st.write("---")
        st.write(f"## {q['title']}")
        st.write(q['description'])
        
        if q['multiple_choice']:
            st.write("(다중 선택 가능)")
        else:
            st.write("(단일 선택)")
        
        # 선택지 가져오기
        options = get_question_options(q['question_id'])
        
        # 투표 폼
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
            
            if st.form_submit_button("투표하기"):
                if not selected_options:
                    st.error("최소 하나의 선택지를 선택해주세요.")
                else:
                    success, message = save_vote(
                        q['question_id'], 
                        selected_options,
                        st.session_state.voter_name or "익명"
                    )
                    
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

if __name__ == "__main__":
    main() 