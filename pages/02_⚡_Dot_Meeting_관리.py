import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Dot Collector - 회의 관리",
    page_icon="🎯",
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

def create_meeting(title, description, created_by, primary_area_id, related_area_ids=None):
    """분야가 지정된 회의 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 1. 회의 생성
        cursor.execute("""
            INSERT INTO dot_meetings 
            (title, description, created_by, primary_area_id)
            VALUES (%s, %s, %s, %s)
        """, (title, description, created_by, primary_area_id))
        
        meeting_id = cursor.lastrowid
        
        # 2. 관련 분야 연결
        if related_area_ids:
            for area_id in related_area_ids:
                cursor.execute("""
                    INSERT INTO dot_meeting_areas 
                    (meeting_id, area_id, is_primary)
                    VALUES (%s, %s, %s)
                """, (
                    meeting_id, 
                    area_id, 
                    area_id == primary_area_id
                ))
        
        # 3. 생성자를 참여자로 자동 등록
        cursor.execute("""
            INSERT INTO dot_meeting_participants
            (meeting_id, user_id)
            SELECT %s, user_id
            FROM dot_user_credibility
            WHERE user_name = %s
        """, (meeting_id, created_by))
        
        conn.commit()
        return True, "회의가 생성되었습니다!"
    except mysql.connector.Error as err:
        return False, f"오류 발생: {err}"
    finally:
        cursor.close()
        conn.close()

def get_active_meetings():
    """진행 중인 회의 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT m.*,
                   COUNT(DISTINCT i.idea_id) as idea_count,
                   COUNT(DISTINCT r.rating_id) as rating_count
            FROM dot_meetings m
            LEFT JOIN dot_ideas i ON m.meeting_id = i.meeting_id
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            WHERE m.status = 'active'
            GROUP BY m.meeting_id
            ORDER BY m.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def close_meeting(meeting_id):
    """회의 종료"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE dot_meetings 
            SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE meeting_id = %s
        """, (meeting_id,))
        
        conn.commit()
        return True, "회의가 성공적으로 종료되었습니다!"
    except mysql.connector.Error as err:
        return False, f"회의 종료 중 오류가 발생했습니다: {err}"
    finally:
        cursor.close()
        conn.close()

def get_meeting_results(meeting_id):
    """회의 결과 상세 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                i.*,
                uc.user_name,
                uc.credibility_score,
                i.category,
                COUNT(DISTINCT r.rating_id) as rating_count,
                -- 기본 평균
                AVG(CASE WHEN r.rating_type = 'agreement' THEN r.rating_value END) as avg_agreement,
                AVG(CASE WHEN r.rating_type = 'feasibility' THEN r.rating_value END) as avg_feasibility,
                AVG(CASE WHEN r.rating_type = 'impact' THEN r.rating_value END) as avg_impact
            FROM dot_ideas i
            JOIN dot_user_credibility uc ON i.user_id = uc.user_id
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            WHERE i.meeting_id = %s
            GROUP BY i.idea_id, i.idea_text, uc.user_name, uc.credibility_score, i.category
        """, (meeting_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def calculate_expertise_score(user_id, area_id):
    """분야별 전문성 점수 계산"""
    base_score = 1.0
    
    # 1. 해당 분야 활동 점수
    activity_score = min(0.5, (
        ideas_in_area * 0.1 +        # 해당 분야 의견
        ratings_in_area * 0.05       # 해당 분야 평가
    ))
    
    # 2. 해당 분야 성과 점수
    performance_score = (
        successful_ratings / total_ratings 
        if total_ratings > 0 else 0
    ) * 0.5
    
    # 3. 개인 기본 신뢰도와 결합
    base_credibility = get_user_base_credibility(user_id)
    
    return (base_score + activity_score + performance_score) * base_credibility

# 상수로 분야 정의
EXPERTISE_AREAS = {
    "strategy": {"id": 1, "name": "전략", "description": "기업 전략, 사업 계획, 시장 분석"},
    "business": {"id": 2, "name": "사업", "description": "신규 사업, 사업 운영, 제휴"},
    "finance": {"id": 3, "name": "재무", "description": "재무 관리, 투자, 회계"},
    "tech": {"id": 4, "name": "기술", "description": "기술 개발, R&D, IT 인프라"},
    "sales": {"id": 5, "name": "영업/유통", "description": "영업 전략, 유통 관리, 파트너십"},
    "cs": {"id": 6, "name": "고객서비스", "description": "고객 지원, 서비스 품질, VOC"},
    "marketing": {"id": 7, "name": "마케팅", "description": "브랜드, 광고, 프로모션"},
    "hr": {"id": 8, "name": "인사/조직", "description": "인사 관리, 조직 문화, 교육"},
    "legal": {"id": 9, "name": "법무/규제", "description": "법률 검토, 규제 대응, 계약"},
    "product": {"id": 10, "name": "제품/서비스", "description": "제품 기획, 서비스 개발, UX"}
}

def get_expertise_areas():
    """분야 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM dot_expertise_areas
            ORDER BY area_name
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def initialize_expertise_areas():
    """분야 데이터 초기화"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 분야 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_expertise_areas (
                area_id INT PRIMARY KEY,
                area_code VARCHAR(20) NOT NULL UNIQUE,
                area_name VARCHAR(50) NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 기존 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM dot_expertise_areas")
        if cursor.fetchone()[0] == 0:
            # 초기 데이터 입력
            for code, area in EXPERTISE_AREAS.items():
                cursor.execute("""
                    INSERT INTO dot_expertise_areas 
                    (area_id, area_code, area_name, description)
                    VALUES (%s, %s, %s, %s)
                """, (area['id'], code, area['name'], area['description']))
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def add_rating(idea_id, rater_id, rating_type, rating_value):
    """의견에 대한 평가 추가"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dot_ratings 
            (idea_id, rater_id, rating_type, rating_value, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
            rating_value = %s,
            updated_at = NOW()
        """, (idea_id, rater_id, rating_type, rating_value, rating_value))
        
        conn.commit()
        return True, "평가가 저장되었습니다."
    except mysql.connector.Error as err:
        return False, f"평가 저장 중 오류 발생: {err}"
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("🎯 Dot Collector - 회의 관리")
    
    # 분야 초기화 확인
    initialize_expertise_areas()
    
    # 새 회의 생성 폼
    with st.form("new_meeting_form"):
        st.write("### 새 회의/토픽 생성")
        title = st.text_input("제목", help="회의나 토론할 토픽의 제목을 입력하세요")
        description = st.text_area("설명", help="회의의 목적이나 토론할 내용을 자세히 설명해주세요")
        created_by = st.text_input("작성자", help="회의 생성자의 이름을 입력하세요")
        
        # 분야 선택 (다중 선택 가능)
        areas = get_expertise_areas()
        selected_areas = st.multiselect(
            "관련 분야",
            options=[(area['area_id'], area['area_name']) for area in areas],
            format_func=lambda x: x[1],
            help="회의와 관련된 분야를 선택하세요 (여러 개 선택 가능)"
        )
        
        primary_area = None
        if selected_areas:
            primary_area = st.selectbox(
                "주요 분야",
                options=selected_areas,
                format_func=lambda x: x[1],
                help="가장 중요한 주요 분야를 선택하세요"
            )
        
        if st.form_submit_button("회의 생성"):
            if not (title and created_by and primary_area):
                st.error("제목, 작성자, 주요 분야는 필수 입력 항목입니다.")
            else:
                success, message = create_meeting(
                    title=title,
                    description=description,
                    created_by=created_by,
                    primary_area_id=primary_area[0],
                    related_area_ids=[area[0] for area in selected_areas]
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    # 진행 중인 회의 목록
    st.write("## 진행 중인 회의 목록")
    active_meetings = get_active_meetings()
    
    if not active_meetings:
        st.info("현재 진행 중인 회의가 없습니다.")
    else:
        for meeting in active_meetings:
            with st.expander(f"📌 {meeting['title']} ({meeting['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                st.write(f"**설명:** {meeting['description']}")
                st.write(f"**작성자:** {meeting['created_by']}")
                st.write(f"**의견 수:** {meeting['idea_count']}")
                st.write(f"**평가 수:** {meeting['rating_count']}")
                
                if st.button("회의 종료", key=f"close_{meeting['meeting_id']}"):
                    success, message = close_meeting(meeting['meeting_id'])
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    # 회의 상세 보기
    selected_meeting = st.selectbox("회의 선택", options=[meeting['meeting_id'] for meeting in active_meetings])
    
    if selected_meeting:
        st.write("## 📝 의견 목록")
        ideas = get_meeting_results(selected_meeting)
        
        for idea in ideas:
            with st.expander(f"{idea['category']}: {idea['idea_text'][:50]}..."):
                st.write(f"**전체 의견:** {idea['idea_text']}")
                st.write(f"**작성자:** {idea['user_name']}")
                
                # 평가 섹션
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    agreement = st.slider(
                        "동의도",
                        1, 5, 3,
                        key=f"agreement_{idea['idea_id']}"
                    )
                    if st.button("동의도 평가", key=f"btn_agreement_{idea['idea_id']}"):
                        success, msg = add_rating(
                            idea['idea_id'],
                            st.session_state.user_id,
                            'agreement',
                            agreement
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                
                with col2:
                    feasibility = st.slider(
                        "실현가능성",
                        1, 5, 3,
                        key=f"feasibility_{idea['idea_id']}"
                    )
                    if st.button("실현가능성 평가", key=f"btn_feasibility_{idea['idea_id']}"):
                        success, msg = add_rating(
                            idea['idea_id'],
                            st.session_state.user_id,
                            'feasibility',
                            feasibility
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                
                with col3:
                    impact = st.slider(
                        "영향력",
                        1, 5, 3,
                        key=f"impact_{idea['idea_id']}"
                    )
                    if st.button("영향력 평가", key=f"btn_impact_{idea['idea_id']}"):
                        success, msg = add_rating(
                            idea['idea_id'],
                            st.session_state.user_id,
                            'impact',
                            impact
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)

if __name__ == "__main__":
    main() 