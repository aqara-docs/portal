import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Vote Question 등록", page_icon="📋", layout="wide")

# Page header
st.title("🗳️ 투표 문제 등록")

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

def save_question(title, description, multiple_choice, max_choices, options, created_by):
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 문제 저장 - max_choices 컬럼 추가
        cursor.execute("""
            INSERT INTO vote_questions 
            (title, description, multiple_choice, max_choices, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, description, multiple_choice, max_choices, created_by))
        
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

def save_subjective_question(title, description, multiple_answers, max_answers, created_by):
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO subjective_questions 
            (title, description, multiple_answers, max_answers, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, description, multiple_answers, max_answers, created_by))
        
        conn.commit()
        return True, "주관식 질문이 성공적으로 저장되었습니다!"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"저장 중 오류가 발생했습니다: {err}"
        
    finally:
        cursor.close()
        conn.close()

def main():
    #st.title("투표 문제 등록")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📊 객관식 질문", "✏️ 주관식 질문"])
    
    with tab1:
        st.write("## 새로운 객관식 질문 등록")
        # 기존의 객관식 질문 등록 코드
        if 'option_count' not in st.session_state:
            st.session_state.option_count = 4
        
        with st.form("vote_question_form"):
            title = st.text_input("제목", help="투표 문제의 제목을 입력하세요")
            description = st.text_area("설명", help="문제에 대한 자세한 설명을 입력하세요")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                multiple_choice = st.checkbox("다중 선택 허용", help="참가자가 여러 개의 옵션을 선택할 수 있도록 허용")
            
            max_choices = None
            with col2:
                if multiple_choice:
                    choice_options = {
                        "2개까지 선택 가능": 2,
                        "3개까지 선택 가능": 3,
                        "4개까지 선택 가능": 4,
                        "제한 없음": None
                    }
                    selected_option = st.selectbox(
                        "최대 선택 개수",
                        options=list(choice_options.keys()),
                        help="참가자가 선택할 수 있는 최대 옵션 개수"
                    )
                    max_choices = choice_options[selected_option]
            
            created_by = st.text_input("작성자", help="문제 작성자의 이름을 입력하세요")
            
            st.write("### 선택지 입력")
            st.caption("최소 2개의 선택지가 필요합니다. 빈 칸은 무시됩니다.")
            
            options = []
            for i in range(st.session_state.option_count):
                option = st.text_input(f"선택지 {i+1}", key=f"option_{i}")
                options.append(option)
            
            submit_button = st.form_submit_button("저장")
            
            if submit_button:
                if not title:
                    st.error("제목을 입력해주세요.")
                    return
                    
                if not created_by:
                    st.error("작성자 이름을 입력해주세요.")
                    return
                    
                valid_options = [opt for opt in options if opt.strip()]
                if len(valid_options) < 2:
                    st.error("최소 2개의 선택지를 입력해주세요.")
                    return
                
                if multiple_choice and max_choices is not None:
                    if max_choices > len(valid_options):
                        st.error(f"최대 선택 개수({max_choices})가 전체 선택지 개수({len(valid_options)})보다 많을 수 없습니다.")
                        return
                
                success, message = save_question(
                    title, description, multiple_choice, max_choices, valid_options, created_by
                )
                
                if success:
                    st.success(message)
                    st.session_state.option_count = 4
                    st.rerun()
                else:
                    st.error(message)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 선택지 추가") and st.session_state.option_count < 15:
                st.session_state.option_count += 1
                st.rerun()
        
        with col2:
            if st.button("➖ 선택지 제거") and st.session_state.option_count > 2:
                st.session_state.option_count -= 1
                st.rerun()
        
        st.caption(f"현재 선택지 수: {st.session_state.option_count} (최대 15개)")
    
    with tab2:
        st.write("## 새로운 주관식 질문 등록")
        
        with st.form("subjective_question_form"):
            title = st.text_input("제목", help="주관식 질문의 제목을 입력하세요", key="subj_title")
            description = st.text_area("설명", help="질문에 대한 자세한 설명을 입력하세요", key="subj_desc")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                multiple_answers = st.checkbox("다중 답변 허용", 
                                            help="참가자가 여러 개의 답변을 입력할 수 있도록 허용",
                                            key="subj_multiple")
            
            max_answers = None
            with col2:
                if multiple_answers:
                    answer_options = {
                        "2개까지 입력 가능": 2,
                        "3개까지 입력 가능": 3,
                        "4개까지 입력 가능": 4,
                        "5개까지 입력 가능": 5,
                        "제한 없음": None
                    }
                    selected_option = st.selectbox(
                        "최대 답변 개수",
                        options=list(answer_options.keys()),
                        help="참가자가 입력할 수 있는 최대 답변 개수",
                        key="subj_max"
                    )
                    max_answers = answer_options[selected_option]
            
            created_by = st.text_input("작성자", 
                                     help="질문 작성자의 이름을 입력하세요",
                                     key="subj_author")
            
            submit_button = st.form_submit_button("저장")
            
            if submit_button:
                if not title:
                    st.error("제목을 입력해주세요.")
                    return
                    
                if not created_by:
                    st.error("작성자 이름을 입력해주세요.")
                    return
                
                success, message = save_subjective_question(
                    title, description, multiple_answers, max_answers, created_by
                )
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    # 등록된 질문 목록 표시
    st.write("## 등록된 투표 문제 목록")
    
    # 객관식/주관식 선택 라디오 버튼
    question_type = st.radio("질문 유형", ["객관식", "주관식"], horizontal=True)
    
    if question_type == "객관식":
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
                    if q['multiple_choice']:
                        max_choices_text = "제한 없음" if q['max_choices'] is None else f"{q['max_choices']}개까지 선택 가능"
                        st.write(f"**최대 선택 개수:** {max_choices_text}")
                    st.write(f"**선택지 수:** {q['option_count']}")
                    st.write(f"**총 응답 수:** {q['response_count']}")
                    st.write(f"**상태:** {q['status']}")
                    
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
    else:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT q.*, 
                       COUNT(DISTINCT r.response_id) as response_count,
                       COUNT(DISTINCT r.voter_name) as unique_voters
                FROM subjective_questions q
                LEFT JOIN subjective_responses r ON q.question_id = r.question_id
                GROUP BY q.question_id
                ORDER BY q.created_at DESC
            """)
            questions = cursor.fetchall()
            
            for q in questions:
                with st.expander(f"✏️ {q['title']} ({q['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                    st.write(f"**설명:** {q['description']}")
                    st.write(f"**작성자:** {q['created_by']}")
                    st.write(f"**다중 답변:** {'예' if q['multiple_answers'] else '아니오'}")
                    if q['multiple_answers']:
                        max_answers_text = "제한 없음" if q['max_answers'] is None else f"{q['max_answers']}개까지 입력 가능"
                        st.write(f"**최대 답변 개수:** {max_answers_text}")
                    st.write(f"**총 응답 수:** {q['response_count']}")
                    st.write(f"**참여자 수:** {q['unique_voters']}")
                    st.write(f"**상태:** {q['status']}")
        
        except mysql.connector.Error as err:
            st.error(f"데이터 조회 중 오류가 발생했습니다: {err}")
        
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main() 