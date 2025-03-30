import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
import markdown
import glob

def init_db():
    """데이터베이스 초기화"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 테이블 삭제 (참조하는 테이블부터 순서대로)
        cursor.execute("DROP TABLE IF EXISTS discussion_participants")
        cursor.execute("DROP TABLE IF EXISTS reading_discussions")
        cursor.execute("DROP TABLE IF EXISTS reading_materials")
        
        # 새 테이블 생성
        cursor.execute("""
            CREATE TABLE reading_materials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                book_title VARCHAR(255) NOT NULL,    -- 책 제목
                file_name VARCHAR(255) NOT NULL,     -- 원본 파일명
                content TEXT NOT NULL,               -- 파일 내용
                type VARCHAR(20) NOT NULL,           -- summary 또는 application
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_book_type (book_title, type)  -- 검색 성능을 위한 인덱스
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 토론 기록 테이블 생성
        cursor.execute("""
            CREATE TABLE reading_discussions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                discussion_date DATE NOT NULL,
                base_material_id INT,
                reading_material_id INT,
                applied_content TEXT,
                insights TEXT,
                action_items TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (base_material_id) REFERENCES reading_materials(id),
                FOREIGN KEY (reading_material_id) REFERENCES reading_materials(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 참여자 테이블 생성
        cursor.execute("""
            CREATE TABLE discussion_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                discussion_id INT NOT NULL,
                user_id INT NOT NULL,
                contributions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (discussion_id) REFERENCES reading_discussions(id),
                FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        st.success("데이터베이스 테이블이 생성되었습니다.")
        return True
        
    except Exception as e:
        st.error(f"DB 초기화 중 오류 발생: {str(e)}")
        return False
    finally:
        # 에러가 발생해도 외래 키 체크는 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.close()
        conn.close()

def load_markdown_files():
    """data 폴더의 markdown 파일 로드"""
    md_files = glob.glob("data/*.md")
    
    for file_path in md_files:
        file_name = os.path.basename(file_path)
        
        # 이미 등록된 파일인지 확인
        if not is_file_registered(file_name):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 첫 번째 줄을 제목으로 사용
            title = content.split('\n')[0].strip('# ')
            
            # 카테고리 추정
            category = 'Reading Material'
            if '사업계획서' in file_name:
                category = 'Business Plan'
            
            # DB에 저장
            save_material(title, file_name, content, category)

def main():
    st.title("독서토론 관리")
    
    # 환경 변수 로드 확인
    load_dotenv()
    
    # 테이블 존재 여부 확인 및 생성 (처음 한 번만)
    create_tables_if_not_exist()
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["파일 등록", "토론 기록", "통계 및 분석"]
    )
    
    if menu == "파일 등록":
        register_files()
    elif menu == "토론 기록":
        record_discussion()
    else:
        show_statistics()

def register_files():
    """파일 등록"""
    st.header("독서토론 파일 등록")
    
    # 책 제목 입력 (기본값: 퍼스널 MBA)
    book_title = st.text_input("책 제목", value="퍼스널 MBA")
    
    # 파일 선택
    col1, col2 = st.columns(2)
    
    with col1:
        summary_file = st.file_uploader(
            "독서토론 요약 파일 (md)",
            type=['md'],
            key='summary'
        )
        if summary_file:
            st.info(f"선택된 요약 파일: {summary_file.name}")
    
    with col2:
        application_file = st.file_uploader(
            "독서토론 적용 파일 (md)",
            type=['md'],
            key='application'
        )
        if application_file:
            st.info(f"선택된 적용 파일: {application_file.name}")
    
    if st.button("파일 저장"):
        if not (summary_file or application_file):
            st.error("최소한 하나의 파일을 선택해주세요.")
            return
        
        try:
            saved_files = []
            
            # 요약 파일 저장
            if summary_file:
                content = summary_file.read().decode('utf-8')
                st.write("요약 파일 내용 미리보기:")
                st.markdown(content[:500] + "..." if len(content) > 500 else content)
                
                if save_material(book_title, summary_file.name, content, "summary"):
                    st.success("요약 파일 저장 완료")
                    saved_files.append("요약 파일")
                else:
                    st.error("요약 파일 저장 실패")
            
            # 적용 파일 저장
            if application_file:
                content = application_file.read().decode('utf-8')
                st.write("적용 파일 내용 미리보기:")
                st.markdown(content[:500] + "..." if len(content) > 500 else content)
                
                if save_material(book_title, application_file.name, content, "application"):
                    st.success("적용 파일 저장 완료")
                    saved_files.append("적용 파일")
                else:
                    st.error("적용 파일 저장 실패")
            
            if saved_files:
                st.success(f"{', '.join(saved_files)}이(가) 성공적으로 저장되었습니다.")
                
                # 저장된 파일 다운로드 버튼 제공
                if summary_file:
                    st.download_button(
                        label="📥 요약 파일 다운로드",
                        data=summary_file.getvalue(),
                        file_name=summary_file.name,
                        mime="text/markdown"
                    )
                if application_file:
                    st.download_button(
                        label="📥 적용 파일 다운로드",
                        data=application_file.getvalue(),
                        file_name=application_file.name,
                        mime="text/markdown"
                    )
                
                # 저장된 내용 확인
                check_saved_files(book_title)
            
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {str(e)}")

def save_material(book_title, file_name, content, type):
    """자료를 DB에 저장"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 기존 파일 확인
        cursor.execute(
            "SELECT id FROM reading_materials WHERE book_title = %s AND file_name = %s AND type = %s",
            (book_title, file_name, type)
        )
        existing = cursor.fetchone()
        cursor.fetchall()  # 남은 결과 정리
        
        if existing:
            # 기존 파일 업데이트
            cursor.execute(
                "UPDATE reading_materials SET content = %s, updated_at = NOW() WHERE id = %s",
                (content, existing[0])
            )
        else:
            # 새 파일 저장
            cursor.execute(
                "INSERT INTO reading_materials (book_title, file_name, content, type) VALUES (%s, %s, %s, %s)",
                (book_title, file_name, content, type)
            )
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"DB 저장 중 오류: {str(e)}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def check_saved_files(book_title):
    """저장된 파일 확인"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, book_title, type, created_at
            FROM reading_materials
            WHERE book_title LIKE %s
        """, (f"{book_title}%",))
        
        results = cursor.fetchall()
        
        if results:
            st.write("### 저장된 파일 목록")
            for r in results:
                st.write(f"- ID: {r['id']}, 제목: {r['book_title']}, 유형: {r['type']}")
        else:
            st.warning("저장된 파일을 찾을 수 없습니다.")
            
    finally:
        cursor.close()
        conn.close()

def show_saved_materials(book_title):
    """저장된 자료 확인"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, book_title, type, created_at
            FROM reading_materials
            WHERE book_title LIKE %s
            ORDER BY created_at DESC
        """, (f"{book_title}%",))
        
        materials = cursor.fetchall()
        if materials:
            st.write("### 저장된 자료")
            for m in materials:
                st.write(f"- {m['book_title']} ({m['type']}) - {m['created_at']}")
        else:
            st.warning(f"{book_title}에 대한 저장된 자료가 없습니다.")
    finally:
        cursor.close()
        conn.close()

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

def is_file_registered(file_name):
    """파일이 이미 DB에 등록되어 있는지 확인"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM reading_materials
            WHERE file_name = %s
        """, (file_name,))
        
        return cursor.fetchone()['count'] > 0
    finally:
        cursor.close()
        conn.close()

def save_book(title, author, description):
    """새 책 정보 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO books (title, author, description)
            VALUES (%s, %s, %s)
        """, (title, author, description))
        
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        st.error(f"책 저장 중 오류 발생: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_materials(category=None):
    """자료 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if category:
            cursor.execute("""
                SELECT *
                FROM reading_materials
                WHERE type = %s
                ORDER BY created_at DESC
            """, (category,))
        else:
            cursor.execute("""
                SELECT *
                FROM reading_materials
                ORDER BY created_at DESC
            """)
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_team_members():
    """팀 멤버 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT user_id, user_name
            FROM dot_user_credibility
            ORDER BY user_name
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_discussion(date, base_id, reading_id, applied_content, insights, action_items, participant_ids):
    """토론 내용 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 토론 기록 저장
        cursor.execute("""
            INSERT INTO reading_discussions (
                discussion_date, base_material_id, reading_material_id,
                applied_content, insights, action_items
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (date, base_id, reading_id, applied_content, insights, action_items))
        
        discussion_id = cursor.lastrowid
        
        # 참여자 정보 저장
        for user_id in participant_ids:
            cursor.execute("""
                INSERT INTO discussion_participants (
                    discussion_id, user_id
                ) VALUES (%s, %s)
            """, (discussion_id, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"토론 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_discussions():
    """토론 기록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                d.*,
                base.book_title as base_title,
                reading.book_title as reading_title,
                GROUP_CONCAT(u.user_name) as participants
            FROM reading_discussions d
            JOIN reading_materials base ON d.base_material_id = base.id
            JOIN reading_materials reading ON d.reading_material_id = reading.id
            LEFT JOIN discussion_participants dp ON d.id = dp.discussion_id
            LEFT JOIN dot_user_credibility u ON dp.user_id = u.user_id
            GROUP BY d.id
            ORDER BY d.discussion_date DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_participant_stats():
    """참여자별 통계"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                u.user_name,
                COUNT(DISTINCT dp.discussion_id) as participation_count,
                COUNT(DISTINCT dp.discussion_id) * 100.0 / 
                    (SELECT COUNT(*) FROM reading_discussions) as participation_rate
            FROM dot_user_credibility u
            LEFT JOIN discussion_participants dp ON u.user_id = dp.user_id
            GROUP BY u.user_id, u.user_name
            ORDER BY participation_count DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_topic_stats():
    """토론 주제 분석"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                rm.type,
                COUNT(*) as usage_count,
                GROUP_CONCAT(DISTINCT rm.book_title) as materials
            FROM reading_discussions rd
            JOIN reading_materials rm ON rd.reading_material_id = rm.id
            GROUP BY rm.type
            ORDER BY usage_count DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def record_discussion():
    """토론 기록"""
    st.header("토론 기록")
    
    # 새 토론 기록
    with st.form("new_discussion"):
        st.subheader("새 토론 기록")
        
        date = st.date_input("토론 날짜", datetime.now())
        
        # 기본 자료 선택 (사업계획서)
        base_materials = get_materials(category="Business Plan")
        base_material = st.selectbox(
            "기본 자료",
            base_materials,
            format_func=lambda x: x['book_title']
        )
        
        # 독서 자료 선택
        reading_materials = get_materials(category="Reading Material")
        reading_material = st.selectbox(
            "독서 자료",
            reading_materials,
            format_func=lambda x: x['book_title']
        )
        
        applied_content = st.text_area("적용된 내용")
        insights = st.text_area("주요 인사이트")
        action_items = st.text_area("실행 계획")
        
        # 참여자 선택
        participants = get_team_members()
        selected_participants = st.multiselect(
            "참여자",
            participants,
            format_func=lambda x: x['user_name']
        )
        
        if st.form_submit_button("저장"):
            success = save_discussion(
                date, base_material['id'], reading_material['id'],
                applied_content, insights, action_items,
                [p['user_id'] for p in selected_participants]
            )
            if success:
                st.success("토론 내용이 저장되었습니다.")
                st.rerun()
    
    # 토론 기록 목록
    discussions = get_discussions()
    if discussions:
        for discussion in discussions:
            with st.expander(f"{discussion['discussion_date']} - {discussion['reading_title']}"):
                st.write(f"기본 자료: {discussion['base_title']}")
                st.write(f"참여자: {discussion['participants']}")
                st.write("### 적용된 내용")
                st.write(discussion['applied_content'])
                st.write("### 주요 인사이트")
                st.write(discussion['insights'])
                st.write("### 실행 계획")
                st.write(discussion['action_items'])

def show_statistics():
    """통계 및 분석"""
    st.header("통계 및 분석")
    
    # 참여자별 통계
    st.subheader("참여자별 통계")
    participant_stats = get_participant_stats()
    if participant_stats:
        df = pd.DataFrame(participant_stats)
        st.dataframe(df)
        
        # 참여율 차트
        st.bar_chart(df.set_index('user_name')['participation_rate'])
    
    # 토론 주제 분석
    st.subheader("주요 토론 주제")
    topic_stats = get_topic_stats()
    if topic_stats:
        st.write(topic_stats)

def create_tables_if_not_exist():
    """필요한 테이블들이 없을 경우에만 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 테이블 존재 여부 확인
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name = 'reading_materials'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        # 테이블이 없을 경우에만 생성
        if not table_exists:
            # 외래 키 체크 비활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # reading_materials 테이블 생성
            cursor.execute("""
                CREATE TABLE reading_materials (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    book_title VARCHAR(255) NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_book_type (book_title, type)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            # reading_discussions 테이블 생성
            cursor.execute("""
                CREATE TABLE reading_discussions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discussion_date DATE NOT NULL,
                    base_material_id INT,
                    reading_material_id INT,
                    applied_content TEXT,
                    insights TEXT,
                    action_items TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (base_material_id) REFERENCES reading_materials(id),
                    FOREIGN KEY (reading_material_id) REFERENCES reading_materials(id)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            # discussion_participants 테이블 생성
            cursor.execute("""
                CREATE TABLE discussion_participants (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discussion_id INT NOT NULL,
                    user_id INT NOT NULL,
                    contributions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (discussion_id) REFERENCES reading_discussions(id),
                    FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            # 외래 키 체크 다시 활성화
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conn.commit()
            st.success("필요한 테이블들이 성공적으로 생성되었습니다.")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 