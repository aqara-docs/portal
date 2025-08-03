import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Vote 참여", page_icon="🗳️", layout="wide")

# Page header
st.title(" 🗳️ 투표 참여")

# MySQL 연결 설정
def connect_to_db():
    """데이터베이스 연결"""
    try:
        # 환경 변수 확인
        db_config = {
            'user': os.getenv('SQL_USER'),
            'password': os.getenv('SQL_PASSWORD'),
            'host': os.getenv('SQL_HOST'),
            'database': os.getenv('SQL_DATABASE_NEWBIZ'),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'use_unicode': True,
            'buffered': True
        }
        
        # None인 값이 있는지 확인
        missing_vars = [k for k, v in db_config.items() if v is None and k != 'collation']
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
            
        conn = mysql.connector.connect(**db_config)
        return conn
        
    except mysql.connector.Error as err:
        error_msg = f"MySQL 연결 오류 (Code: {err.errno}): {err.msg}"
        st.error(error_msg)
        return None
    except Exception as e:
        st.error(f"예상치 못한 오류: {str(e)}")
        return None

def get_active_questions():
    """활성화된 투표 목록 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT *, 
                   CASE 
                       WHEN multiple_choice = 1 AND max_choices IS NOT NULL 
                       THEN CONCAT('(최대 ', max_choices, '개 선택 가능)')
                       WHEN multiple_choice = 1 
                       THEN '(다중 선택 가능)'
                       ELSE '(1개만 선택 가능)'
                   END as choice_info
            FROM vote_questions 
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

def validate_vote_selections(question_id, selected_options):
    """투표 선택 검증"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT multiple_choice, max_choices
            FROM vote_questions
            WHERE question_id = %s
        """, (question_id,))
        question = cursor.fetchone()
        
        if not question['multiple_choice']:
            # 단일 선택만 허용
            if len(selected_options) > 1:
                return False, "이 문항은 하나의 선택지만 선택할 수 있습니다."
        else:
            # 다중 선택 제한 확인
            if question['max_choices'] is not None:
                if len(selected_options) > question['max_choices']:
                    return False, f"최대 {question['max_choices']}개까지만 선택할 수 있습니다."
        
        return True, None
        
    finally:
        cursor.close()
        conn.close()

def save_vote(question_id, option_ids, voter_name, reasoning=""):
    """투표 저장"""
    if voter_name != "익명" and check_duplicate_vote(question_id, voter_name):
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

def save_subjective_response(question_id, voter_name, response_text):
    """주관식 답변 저장"""
    if voter_name != "익명":
        conn = connect_to_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) as response_count
                FROM subjective_responses
                WHERE question_id = %s AND voter_name = %s
            """, (question_id, voter_name))
            
            if cursor.fetchone()['response_count'] > 0:
                return False, "이미 답변을 제출하셨습니다."
        finally:
            cursor.close()
            conn.close()
    
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO subjective_responses 
            (question_id, voter_name, response_text)
            VALUES (%s, %s, %s)
        """, (question_id, voter_name, response_text))
        
        conn.commit()
        return True, "답변이 성공적으로 저장되었습니다!"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"저장 중 오류가 발생했습니다: {err}"
        
    finally:
        cursor.close()
        conn.close()

def show_vote_questions():
    st.write("## 객관식 질문 목록")
    
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
            WHERE q.status = 'active'
            GROUP BY q.question_id
            ORDER BY q.created_at DESC
        """)
        questions = cursor.fetchall()
        
        if not questions:
            st.info("현재 진행 중인 객관식 투표가 없습니다.")
            return
        
        for q in questions:
            with st.expander(f"📊 {q['title']} ({q['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                st.write(f"**설명:** {q['description']}")
                st.write(f"**작성자:** {q['created_by']}")
                st.write(f"**다중 선택:** {'예' if q['multiple_choice'] else '아니오'}")
                if q['multiple_choice']:
                    max_choices_text = "제한 없음" if q['max_choices'] is None else f"{q['max_choices']}개까지 선택 가능"
                    st.write(f"**최대 선택 개수:** {max_choices_text}")
                st.write(f"**선택지 수:** {q['option_count']}")
                st.write(f"**총 응답 수:** {q['response_count']}")
                
                # 선택지 목록 조회
                cursor.execute("""
                    SELECT option_id, option_text, 
                           (SELECT COUNT(*) FROM vote_responses WHERE option_id = vo.option_id) as vote_count
                    FROM vote_options vo
                    WHERE question_id = %s
                """, (q['question_id'],))
                options = cursor.fetchall()
                
                # 세션 상태에서 이미 투표했는지 확인
                voted_key = f"voted_{q['question_id']}"
                if voted_key not in st.session_state:
                    st.session_state[voted_key] = False
                
                # 투표 폼
                if not st.session_state[voted_key]:
                    with st.form(f"vote_form_{q['question_id']}"):
                        st.write("### 투표하기")
                        voter_name = st.text_input("이름 (선택사항)", help="이름을 입력하지 않으면 '익명'으로 처리됩니다", key=f"voter_{q['question_id']}")
                        
                        # 이미 투표했는지 확인 (익명이 아닌 경우)
                        if voter_name.strip() and voter_name != "익명":
                            cursor.execute("""
                                SELECT COUNT(*) as vote_count
                                FROM vote_responses
                                WHERE question_id = %s AND voter_name = %s
                            """, (q['question_id'], voter_name))
                            result = cursor.fetchone()
                            
                            if result['vote_count'] > 0:
                                st.error("이미 투표에 참여하셨습니다.")
                                st.stop()
                        
                        # 다중 선택 여부에 따라 적절한 입력 위젯 표시
                        selected_options = []
                        if q['multiple_choice']:
                            for opt in options:
                                if st.checkbox(
                                    f"{opt['option_text']} (현재 {opt['vote_count']}표)", 
                                    key=f"opt_{opt['option_id']}"
                                ):
                                    selected_options.append(opt['option_id'])
                        else:
                            option_texts = [f"{opt['option_text']} (현재 {opt['vote_count']}표)" for opt in options]
                            selected_idx = st.radio(
                                "선택지",
                                range(len(options)),
                                format_func=lambda x: option_texts[x],
                                key=f"radio_{q['question_id']}"
                            )
                            selected_options = [options[selected_idx]['option_id']]
                        
                        submit = st.form_submit_button("투표하기")
                        
                        if submit:
                            # 이름이 입력되지 않은 경우 '익명'으로 처리
                            if not voter_name.strip():
                                voter_name = "익명"
                                
                            if not selected_options:
                                st.error("최소 하나의 선택지를 선택해주세요.")
                                st.stop()
                            
                            # 다중 선택 제한 검증
                            if q['multiple_choice'] and q['max_choices'] is not None:
                                if len(selected_options) > q['max_choices']:
                                    st.error(f"최대 {q['max_choices']}개까지만 선택할 수 있습니다.")
                                    st.stop()
                            
                            # 투표 저장
                            try:
                                for option_id in selected_options:
                                    cursor.execute("""
                                        INSERT INTO vote_responses 
                                        (question_id, option_id, voter_name)
                                        VALUES (%s, %s, %s)
                                    """, (q['question_id'], option_id, voter_name))
                                conn.commit()
                                st.session_state[voted_key] = True
                                st.success("투표가 성공적으로 저장되었습니다!")
                                st.rerun()
                            except mysql.connector.Error as err:
                                conn.rollback()
                                st.error(f"투표 저장 중 오류가 발생했습니다: {err}")
                else:
                    st.info("이미 투표에 참여하셨습니다. 감사합니다!")
                    # 현재 투표 결과 표시
                    st.write("### 현재 투표 결과")
                    for opt in options:
                        st.write(f"- {opt['option_text']}: {opt['vote_count']}표")
    except mysql.connector.Error as err:
        st.error(f"데이터 조회 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def show_subjective_questions():
    st.write("## 주관식 질문")
    
    # 활성화된 주관식 질문 가져오기
    conn = connect_to_db()
    if not conn:
        st.error("데이터베이스 연결에 실패했습니다.")
        return
        
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT question_id, title, description, multiple_answers, max_answers
            FROM subjective_questions
            WHERE status = 'active'
            ORDER BY created_at DESC
        """)
        questions = cursor.fetchall()
        
        if not questions:
            st.info("현재 진행 중인 주관식 질문이 없습니다.")
            return
        
        # 질문 선택
        selected_question = st.selectbox(
            "답변할 질문을 선택하세요",
            questions,
            format_func=lambda x: x['title']
        )
        
        if selected_question:
            # 세션 상태에서 이미 답변했는지 확인
            answered_key = f"answered_{selected_question['question_id']}"
            if answered_key not in st.session_state:
                st.session_state[answered_key] = False

            st.write("### " + selected_question['title'])
            st.write(selected_question['description'])
            
            if st.session_state[answered_key]:
                st.success("이미 답변을 제출하셨습니다. 감사합니다!")
                return
            
            # 이름 입력
            voter_name = st.text_input("이름 (입력하지 않으면 '익명'으로 처리됩니다)", key="subjective_voter_name")
            
            # 이름이 입력된 경우에만 중복 체크
            if voter_name.strip() and voter_name != "익명":
                cursor.execute("""
                    SELECT COUNT(*) as response_count
                    FROM subjective_responses
                    WHERE question_id = %s AND voter_name = %s
                """, (selected_question['question_id'], voter_name))
                response_count = cursor.fetchone()['response_count']
                
                if response_count > 0:
                    st.warning("이미 답변하셨습니다.")
                    return
            
            # 응답 입력 필드
            responses = []
            
            # 다중 답변 여부에 따라 필드 수 설정
            if selected_question['multiple_answers']:
                max_answers = 4  # 다중 답변인 경우 무조건 4개
            else:
                max_answers = 1  # 단일 답변인 경우 1개
            
            for i in range(max_answers):
                field_label = f"답변 {i+1}" if max_answers > 1 else "답변"
                response = st.text_area(
                    field_label,
                    key=f"response_{i}",
                    height=150 if max_answers == 1 else 100
                )
                if response:
                    responses.append(response)
            
            if st.button("답변 제출", key="submit_subjective"):
                if not responses:
                    st.error("답변을 입력해주세요.")
                    return
                
                # 이름이 입력되지 않은 경우 '익명'으로 처리
                if not voter_name.strip():
                    voter_name = "익명"
                
                try:
                    # 각 응답 저장
                    for response_text in responses:
                        if response_text.strip():  # 빈 응답이 아닌 경우에만 저장
                            cursor.execute("""
                                INSERT INTO subjective_responses
                                (question_id, voter_name, response_text)
                                VALUES (%s, %s, %s)
                            """, (selected_question['question_id'], voter_name, response_text))
                    
                    conn.commit()
                    st.session_state[answered_key] = True
                    st.success("답변이 성공적으로 제출되었습니다!")
                    st.rerun()
                    
                except mysql.connector.Error as err:
                    st.error(f"답변 제출 중 오류가 발생했습니다: {err}")
                    conn.rollback()
    
    except mysql.connector.Error as err:
        st.error(f"데이터 조회 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def main():
    #st.title("투표 참여")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📊 객관식 투표", "✏️ 주관식 투표"])
    
    with tab1:
        show_vote_questions()
    
    with tab2:
        show_subjective_questions()

if __name__ == "__main__":
    main() 