import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Dot Collector - 회의 참여",
    page_icon="💭",
    layout="wide"
)

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

def get_or_create_user(user_name):
    """사용자 조회 또는 생성"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기존 사용자 조회
        cursor.execute("""
            SELECT * FROM dot_user_credibility 
            WHERE user_name = %s
        """, (user_name,))
        user = cursor.fetchone()
        
        if user:
            return user['user_id']
            
        # 새 사용자 생성
        cursor.execute("""
            INSERT INTO dot_user_credibility (user_name)
            VALUES (%s)
        """, (user_name,))
        conn.commit()
        return cursor.lastrowid
        
    finally:
        cursor.close()
        conn.close()

def get_active_meetings():
    """진행 중인 회의 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM dot_meetings 
            WHERE status = 'active' 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_meeting_ideas(meeting_id):
    """회의의 의견 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                i.*,
                uc.user_name,
                uc.credibility_score,
                (
                    SELECT COUNT(*)
                    FROM dot_ratings r2
                    WHERE r2.idea_id = i.idea_id
                ) as rating_count,
                (
                    SELECT AVG(rating_value)
                    FROM dot_ratings r3
                    WHERE r3.idea_id = i.idea_id AND r3.rating_type = 'agreement'
                ) as avg_agreement,
                (
                    SELECT AVG(rating_value)
                    FROM dot_ratings r4
                    WHERE r4.idea_id = i.idea_id AND r4.rating_type = 'feasibility'
                ) as avg_feasibility,
                (
                    SELECT AVG(rating_value)
                    FROM dot_ratings r5
                    WHERE r5.idea_id = i.idea_id AND r5.rating_type = 'impact'
                ) as avg_impact
            FROM dot_ideas i
            JOIN dot_user_credibility uc ON i.user_id = uc.user_id
            WHERE i.meeting_id = %s
            ORDER BY i.created_at DESC
        """, (meeting_id,))
        
        results = cursor.fetchall()
        
        # 디버그: 각 의견의 평가 데이터 확인
        for idea in results:
            cursor.execute("""
                SELECT rating_type, rating_value
                FROM dot_ratings
                WHERE idea_id = %s
            """, (idea['idea_id'],))
            ratings = cursor.fetchall()
            if ratings:
                st.write(f"의견 ID {idea['idea_id']}의 평가:")
                for rating in ratings:
                    st.write(f"- {rating['rating_type']}: {rating['rating_value']}")
        
        return results
    finally:
        cursor.close()
        conn.close()

def save_idea(meeting_id, user_id, idea_text, category):
    """새로운 의견 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dot_ideas 
            (meeting_id, user_id, idea_text, category)
            VALUES (%s, %s, %s, %s)
        """, (meeting_id, user_id, idea_text, category))
        
        conn.commit()
        return True, "의견이 성공적으로 저장되었습니다!"
    except mysql.connector.Error as err:
        return False, f"의견 저장 중 오류가 발생했습니다: {err}"
    finally:
        cursor.close()
        conn.close()

def initialize_tables():
    """필요한 테이블 초기화"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 테이블이 없을 때만 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_ratings (
                rating_id INT AUTO_INCREMENT PRIMARY KEY,
                idea_id INT NOT NULL,
                rater_id INT NOT NULL,
                rating_type ENUM('agreement', 'feasibility', 'impact') NOT NULL,
                rating_value INT NOT NULL,
                expertise_score FLOAT DEFAULT 1.0,
                credibility_score FLOAT DEFAULT 1.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_rating (idea_id, rater_id, rating_type),
                FOREIGN KEY (idea_id) REFERENCES dot_ideas(idea_id) ON DELETE CASCADE,
                FOREIGN KEY (rater_id) REFERENCES dot_user_credibility(user_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 기존 테이블에 컬럼 추가 (이미 있는 경우 무시)
        try:
            cursor.execute("""
                ALTER TABLE dot_ratings
                ADD COLUMN expertise_score FLOAT DEFAULT 1.0,
                ADD COLUMN credibility_score FLOAT DEFAULT 1.0
            """)
            conn.commit()
            st.success("평가 테이블이 성공적으로 업데이트되었습니다.")
        except mysql.connector.Error as err:
            if err.errno != 1060:  # 1060은 "Duplicate column name" 에러
                raise err
        
        # 테이블이 제대로 생성되었는지 확인
        cursor.execute("SHOW TABLES LIKE 'dot_ratings'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_ratings,
                    AVG(expertise_score) as avg_expertise,
                    AVG(credibility_score) as avg_credibility
                FROM dot_ratings
            """)
            stats = cursor.fetchone()
            avg_expertise = float(stats[1]) if stats[1] is not None else 1.0
            avg_credibility = float(stats[2]) if stats[2] is not None else 1.0
            
            st.write(
                "현재 저장된 평가 통계:\n"
                f"- 총 평가 수: {stats[0]}\n"
                f"- 평균 전문성 점수: {avg_expertise:.2f}\n"
                f"- 평균 신뢰도 점수: {avg_credibility:.2f}"
            )
        
        conn.commit()
    except mysql.connector.Error as err:
        st.error(f"테이블 초기화 중 오류 발생: {err}")
    finally:
        cursor.close()
        conn.close()

def save_rating(idea_id, rater_id, rating_type, rating_value):
    """평가 저장 - 전문성 가중치 반영"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 회의의 주요 분야 확인
        cursor.execute("""
            SELECT m.primary_area_id, ue.expertise_score, uc.credibility_score
            FROM dot_ideas i
            JOIN dot_meetings m ON i.meeting_id = m.meeting_id
            LEFT JOIN dot_user_expertise ue ON ue.user_id = %s 
                AND ue.area_id = m.primary_area_id
            JOIN dot_user_credibility uc ON uc.user_id = %s
            WHERE i.idea_id = %s
        """, (rater_id, rater_id, idea_id))
        expertise_info = cursor.fetchone()
        
        # 평가 저장 시 전문성 정보도 함께 저장
        cursor.execute("""
            INSERT INTO dot_ratings 
            (idea_id, rater_id, rating_type, rating_value, expertise_score, credibility_score)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            rating_value = VALUES(rating_value),
            expertise_score = VALUES(expertise_score),
            credibility_score = VALUES(credibility_score)
        """, (
            idea_id, 
            rater_id, 
            rating_type, 
            rating_value,
            expertise_info['expertise_score'] or 1.0,
            expertise_info['credibility_score']
        ))
        
        conn.commit()
        return True, "평가가 저장되었습니다."
    except mysql.connector.Error as err:
        return False, f"평가 저장 중 오류 발생: {err}"
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("💭 Dot Collector - 회의 참여")
    
    # 테이블 초기화
    initialize_tables()
    
    # 사용자 이름 입력
    if 'user_name' not in st.session_state:
        st.session_state.user_name = ""
    
    st.session_state.user_name = st.text_input(
        "이름을 입력하세요",
        value=st.session_state.user_name,
        help="회의에 참여하시는 분의 이름을 입력해주세요."
    )
    
    if not st.session_state.user_name:
        st.warning("참여하시려면 이름을 입력해주세요.")
        st.stop()
    
    # 사용자 ID 가져오기
    user_id = get_or_create_user(st.session_state.user_name)
    
    # 진행 중인 회의 선택
    meetings = get_active_meetings()
    if not meetings:
        st.info("현재 진행 중인 회의가 없습니다.")
        st.stop()
    
    meeting = st.selectbox(
        "참여할 회의를 선택하세요",
        meetings,
        format_func=lambda x: f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d %H:%M')})"
    )
    
    # 의견 입력 폼
    with st.form("new_idea_form"):
        st.write("### 새로운 의견 제시")
        idea_text = st.text_area("의견", help="회의 주제에 대한 의견을 자유롭게 작성해주세요.")
        category = st.selectbox(
            "카테고리",
            ["suggestion", "concern", "question", "other"],
            format_func=lambda x: {
                "suggestion": "💡 제안",
                "concern": "⚠️ 우려사항",
                "question": "❓ 질문",
                "other": "📝 기타"
            }[x]
        )
        
        if st.form_submit_button("의견 제출"):
            if not idea_text:
                st.error("의견을 입력해주세요.")
            else:
                success, message = save_idea(
                    meeting['meeting_id'],
                    user_id,
                    idea_text,
                    category
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    # 의견 목록 및 평가
    st.write("## 회의 의견 목록")
    ideas = get_meeting_ideas(meeting['meeting_id'])
    
    if not ideas:
        st.info("아직 등록된 의견이 없습니다.")
    else:
        st.info("다른 사람의 의견에 대해 평가해주세요. (1: 매우 낮음 ~ 5: 매우 높음)")
        
        for idea in ideas:
            with st.expander(
                f"{idea['category'].upper()}: {idea['idea_text'][:50]}... "
                f"(by {idea['user_name']})"
            ):
                st.write(f"**전체 의견:** {idea['idea_text']}")
                st.write(f"**작성자:** {idea['user_name']}")
                
                # 자신의 의견이 아닌 경우에만 평가 가능
                if idea['user_id'] != user_id:
                    st.write("### ⭐ 이 의견 평가하기")
                    cols = st.columns(3)
                    
                    with cols[0]:
                        agreement = st.slider(
                            "동의도",
                            1, 5, 3,
                            help="1: 전혀 동의하지 않음, 5: 매우 동의함",
                            key=f"agreement_{idea['idea_id']}"
                        )
                        if st.button("동의도 평가", key=f"btn_agreement_{idea['idea_id']}"):
                            success, msg = save_rating(
                                idea['idea_id'],
                                user_id,
                                'agreement',
                                agreement
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with cols[1]:
                        feasibility = st.slider(
                            "실현가능성",
                            1, 5, 3,
                            help="1: 매우 어려움, 5: 매우 쉬움",
                            key=f"feasibility_{idea['idea_id']}"
                        )
                        if st.button("실현가능성 평가", key=f"btn_feasibility_{idea['idea_id']}"):
                            success, msg = save_rating(
                                idea['idea_id'],
                                user_id,
                                'feasibility',
                                feasibility
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with cols[2]:
                        impact = st.slider(
                            "영향력",
                            1, 5, 3,
                            help="1: 영향력 낮음, 5: 영향력 높음",
                            key=f"impact_{idea['idea_id']}"
                        )
                        if st.button("영향력 평가", key=f"btn_impact_{idea['idea_id']}"):
                            success, msg = save_rating(
                                idea['idea_id'],
                                user_id,
                                'impact',
                                impact
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                else:
                    st.info("자신의 의견은 평가할 수 없습니다.")
                
                # 현재 평가 상태 표시
                st.write("### 📊 현재 평가 상태")
                st.write(f"- 평가 수: {idea['rating_count']}")
                if idea['avg_agreement']:
                    st.write(f"- 평균 동의도: {idea['avg_agreement']:.1f}/5")
                if idea['avg_feasibility']:
                    st.write(f"- 평균 실현가능성: {idea['avg_feasibility']:.1f}/5")
                if idea['avg_impact']:
                    st.write(f"- 평균 영향력: {idea['avg_impact']:.1f}/5")

if __name__ == "__main__":
    main() 