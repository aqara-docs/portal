import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="DB 테이블 생성/수정/삭제 시스템",
    page_icon="💾",
    layout="wide"
)

# 인증 기능 (간단한 비밀번호 보호)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == os.getenv('ADMIN_PASSWORD', 'admin123'):  # 환경 변수에서 비밀번호 가져오기
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

# MySQL Database configuration
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

def get_existing_tables():
    """기존 테이블 목록 조회"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        conn.close()
        return tables
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return []

def get_table_schema(table_name):
    """테이블 스키마 조회"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        cursor.close()
        conn.close()
        return columns
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return []

def create_or_modify_table(table_name, columns, unique_keys):
    """테이블 생성 또는 수정"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 테이블 존재 여부 확인
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # 기존 테이블 수정
            for col_name, col_type, _ in columns:
                if col_name != 'id':
                    try:
                        # 칼럼 존재 여부 확인
                        cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{col_name}'")
                        column_exists = cursor.fetchone() is not None

                        if column_exists:
                            # 기존 칼럼 수정
                            cursor.execute(f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} {col_type}")
                            st.info(f"칼럼 '{col_name}'이(가) 수정되었습니다.")
                        else:
                            # 새 칼럼 추가
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                            st.info(f"새 칼럼 '{col_name}'이(가) 추가되었습니다.")
                    except mysql.connector.Error as err:
                        st.error(f"칼럼 {col_name} 처리 중 오류 발생: {err}")
                        continue

            # Unique Key 처리
            if unique_keys:
                try:
                    # 기존 unique key 제거 (PRIMARY 제외)
                    cursor.execute(f"SHOW INDEX FROM {table_name}")
                    existing_indexes = cursor.fetchall()
                    for index in existing_indexes:
                        if index[2] != 'PRIMARY':
                            cursor.execute(f"DROP INDEX {index[2]} ON {table_name}")
                    
                    # 새로운 unique key 추가
                    unique_columns = ", ".join(unique_keys)
                    cursor.execute(f"ALTER TABLE {table_name} ADD UNIQUE KEY unique_record ({unique_columns})")
                    st.info(f"Unique Key가 업데이트되었습니다: {unique_columns}")
                except mysql.connector.Error as err:
                    st.error(f"Unique Key 설정 중 오류 발생: {err}")

        else:
            # 새 테이블 생성
            create_query = f"""
            CREATE TABLE {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                {', '.join([f"{col[0]} {col[1]}" for col in columns if col[0] != 'id'])}
            """
            if unique_keys:
                unique_columns = ", ".join(unique_keys)
                create_query += f", UNIQUE KEY unique_record ({unique_columns})"
            create_query += ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci"
            
            cursor.execute(create_query)
            st.success("새 테이블이 생성되었습니다.")

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def delete_table(table_name):
    """테이블 삭제"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 삭제 전 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        if count > 0:
            st.warning(f"이 테이블에는 {count}개의 데이터가 있습니다. 정말 삭제하시겠습니까?")
            if not st.button("예, 삭제합니다"):
                return False
                
        cursor.execute(f"DROP TABLE {table_name}")
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def get_table_data(table_name, search_term=None):
    """테이블 데이터 조회"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        if search_term:
            # 테이블의 모든 컬럼 가져오기
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            columns = [column['Field'] for column in cursor.fetchall()]
            
            # 각 컬럼에 대해 LIKE 검색 조건 생성
            search_conditions = " OR ".join([f"{col} LIKE '%{search_term}%'" for col in columns])
            query = f"SELECT * FROM {table_name} WHERE {search_conditions}"
        else:
            query = f"SELECT * FROM {table_name}"
            
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return []

def create_vote_tables():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vote_questions (
                question_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                multiple_choice BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status ENUM('active', 'closed') DEFAULT 'active',
                created_by VARCHAR(50)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vote_options (
                option_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                option_text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES vote_questions(question_id)
                ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vote_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                option_id INT,
                voter_name VARCHAR(50),
                reasoning TEXT,
                voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES vote_questions(question_id)
                ON DELETE CASCADE,
                FOREIGN KEY (option_id) REFERENCES vote_options(option_id)
                ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vote_llm_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                option_id INT,
                llm_model VARCHAR(50),
                reasoning TEXT,
                weight INT DEFAULT 1,
                voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES vote_questions(question_id)
                ON DELETE CASCADE,
                FOREIGN KEY (option_id) REFERENCES vote_options(option_id)
                ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 기존 테이블에 weight 컬럼 추가 시도
        try:
            cursor.execute("""
                ALTER TABLE vote_llm_responses
                ADD COLUMN weight INT DEFAULT 1
            """)
        except mysql.connector.Error as err:
            if err.errno == 1060:  # Duplicate column error
                pass  # 이미 컬럼이 존재하면 무시
            else:
                raise err

        # 기존 테이블에 reasoning 컬럼 추가 시도
        try:
            cursor.execute("""
                ALTER TABLE vote_responses
                ADD COLUMN reasoning TEXT
            """)
        except mysql.connector.Error as err:
            if err.errno == 1060:  # Duplicate column error
                pass
            else:
                raise err

        conn.commit()
        st.success("투표 시스템 테이블이 성공적으로 생성/수정되었습니다!")

    except mysql.connector.Error as err:
        st.error(f"테이블 생성/수정 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def create_dot_collector_tables():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 회의/토픽 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_meetings (
                meeting_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status ENUM('active', 'closed') DEFAULT 'active',
                created_by VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 사용자 신뢰도 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_user_credibility (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                user_name VARCHAR(50) NOT NULL UNIQUE,
                credibility_score FLOAT DEFAULT 1.0,
                total_dots_given INT DEFAULT 0,
                total_dots_received INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 의견/아이디어 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_ideas (
                idea_id INT AUTO_INCREMENT PRIMARY KEY,
                meeting_id INT,
                user_id INT,
                idea_text TEXT NOT NULL,
                category ENUM('suggestion', 'concern', 'question', 'other'),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES dot_meetings(meeting_id),
                FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 평가(dots) 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_ratings (
                rating_id INT AUTO_INCREMENT PRIMARY KEY,
                idea_id INT,
                rater_id INT,
                rating_type ENUM('agreement', 'feasibility', 'impact') NOT NULL,
                rating_value INT NOT NULL,  # 1-5 scale
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (idea_id) REFERENCES dot_ideas(idea_id),
                FOREIGN KEY (rater_id) REFERENCES dot_user_credibility(user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        conn.commit()
        st.success("Dot Collector 테이블이 성공적으로 생성되었습니다!")

    except mysql.connector.Error as err:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def create_dot_expertise_tables():
    """분야별 전문성 관리를 위한 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 분야 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_expertise_areas (
                area_id INT PRIMARY KEY,
                area_code VARCHAR(20) NOT NULL UNIQUE,
                area_name VARCHAR(50) NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # 사용자별 분야 전문성 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_user_expertise (
                user_id INT,
                area_id INT,
                expertise_score FLOAT DEFAULT 1.0,
                total_ideas INT DEFAULT 0,
                total_ratings INT DEFAULT 0,
                successful_ratings INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, area_id),
                FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id),
                FOREIGN KEY (area_id) REFERENCES dot_expertise_areas(area_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # 회의-분야 연결 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dot_meeting_areas (
                meeting_id INT,
                area_id INT,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (meeting_id, area_id),
                FOREIGN KEY (meeting_id) REFERENCES dot_meetings(meeting_id),
                FOREIGN KEY (area_id) REFERENCES dot_expertise_areas(area_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # meetings 테이블에 area_id 컬럼 추가 (안전하게 처리)
        try:
            # 컬럼 존재 여부 확인
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'dot_meetings' 
                AND COLUMN_NAME = 'primary_area_id'
            """)
            column_exists = cursor.fetchone()[0] > 0
            
            if not column_exists:
                # 컬럼 추가
                cursor.execute("""
                    ALTER TABLE dot_meetings
                    ADD COLUMN primary_area_id INT,
                    ADD FOREIGN KEY (primary_area_id) 
                    REFERENCES dot_expertise_areas(area_id)
                """)
        except mysql.connector.Error as err:
            st.warning(f"meetings 테이블 수정 중 오류 (무시 가능): {err}")
        
        conn.commit()
        return True, "분야별 전문성 관리 테이블이 생성되었습니다!"
    except mysql.connector.Error as err:
        return False, f"테이블 생성 중 오류가 발생했습니다: {err}"
    finally:
        cursor.close()
        conn.close()

def create_business_strategy_tables():
    """사업 전략 관련 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 사업 전략 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_strategies (
                strategy_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                industry VARCHAR(100),
                target_market VARCHAR(200),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                content TEXT,
                analysis_result TEXT,
                status ENUM('draft', 'completed', 'analyzed') DEFAULT 'draft'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 전략 평가 히스토리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_evaluations (
                evaluation_id INT AUTO_INCREMENT PRIMARY KEY,
                strategy_id INT,
                evaluation_type VARCHAR(50),
                score DECIMAL(3,1),
                feedback TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES business_strategies(strategy_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        conn.commit()
        st.success("사업 전략 테이블이 성공적으로 생성되었습니다!")

    except mysql.connector.Error as err:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def create_decision_tree_tables():
    """비즈니스 의사결정 트리 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 의사결정 트리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_trees (
                tree_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                discount_rate DECIMAL(5,2),  -- 할인율
                analysis_period INT,         -- 분석기간(년)
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 의사결정 노드 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_nodes (
                node_id INT AUTO_INCREMENT PRIMARY KEY,
                tree_id INT NOT NULL,
                parent_id INT,
                node_type ENUM('decision', 'chance', 'outcome') NOT NULL,
                question TEXT NOT NULL,
                description TEXT,
                market_size DECIMAL(15,2),      -- 시장 규모
                market_growth DECIMAL(5,2),      -- 시장 성장률
                competition_level INT,           -- 경쟁 강도 (1-5)
                risk_level INT,                  -- 위험도 (1-5)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tree_id) REFERENCES decision_trees(tree_id),
                FOREIGN KEY (parent_id) REFERENCES decision_nodes(node_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 선택지/시나리오 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_options (
                option_id INT AUTO_INCREMENT PRIMARY KEY,
                node_id INT NOT NULL,
                option_text TEXT NOT NULL,
                initial_investment DECIMAL(15,2),  -- 초기 투자비용
                operating_cost DECIMAL(15,2),      -- 연간 운영비용
                expected_revenue DECIMAL(15,2),    -- 연간 예상 매출
                market_share DECIMAL(5,2),         -- 예상 시장 점유율
                probability DECIMAL(5,2),          -- 발생 확률
                npv DECIMAL(15,2),                -- 순현재가치
                roi DECIMAL(5,2),                 -- 투자수익률
                payback_period DECIMAL(5,2),      -- 회수기간
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES decision_nodes(node_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ 비즈니스 의사결정 트리 테이블이 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def drop_decision_tree_tables():
    """의사결정 트리 테이블 삭제"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 외래 키 제약 조건으로 인해 역순으로 삭제
        cursor.execute("DROP TABLE IF EXISTS decision_options")
        cursor.execute("DROP TABLE IF EXISTS decision_nodes")
        cursor.execute("DROP TABLE IF EXISTS decision_trees")

        conn.commit()
        st.success("✅ 의사결정 트리 테이블이 삭제되었습니다!")

    except mysql.connector.Error as err:
        st.error(f"테이블 삭제 중 오류가 발생했습니다: {err}")
    finally:
        cursor.close()
        conn.close()

def create_strategy_framework_tables():
    """전략 프레임워크 적용을 위한 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 전략 프레임워크 적용 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_framework_applications (
                application_id INT AUTO_INCREMENT PRIMARY KEY,
                original_strategy TEXT NOT NULL,
                framework_id INT NOT NULL,
                modified_strategy TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 경영 이론 마스터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS management_theories (
                theory_id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(100) NOT NULL,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 경영 이론 데이터 초기화
        cursor.execute("TRUNCATE TABLE management_theories")
        
        # 경영 이론 데이터 입력
        theories_data = [
            # 1. 경영 전략 (Strategic Management)
            ("경영 전략", "SWOT 분석", "기업의 내부 강점/약점과 외부 기회/위협을 분석하여 전략을 수립하는 프레임워크"),
            ("경영 전략", "PESTEL 분석", "거시환경 분석을 위한 정치, 경제, 사회, 기술, 환경, 법률적 요소 분석"),
            ("경영 전략", "포터의 5가지 힘 분석", "산업의 경쟁 구조를 분석하는 프레임워크"),
            ("경영 전략", "블루오션 전략", "경쟁이 없는 새로운 시장 공간을 창출하는 전략"),
            ("경영 전략", "경쟁 우위", "지속 가능한 경쟁 우위를 확보하기 위한 전략"),
            ("경영 전략", "VRIO 프레임워크", "자원의 가치, 희소성, 모방 가능성, 조직을 분석하는 프레임워크"),
            ("경영 전략", "밸류 체인 분석", "기업의 가치 창출 활동을 분석하는 프레임워크"),
            ("경영 전략", "전략적 그룹 분석", "산업 내 유사한 전략을 가진 기업들을 그룹화하여 분석"),
            ("경영 전략", "핵심 역량 이론", "기업의 핵심 경쟁력을 식별하고 개발하는 이론"),
            ("경영 전략", "시장 지위 이론", "시장에서의 포지셔닝 전략을 수립하는 이론"),
            
            # 2. 리더십 (Leadership)
            ("리더십", "상황적 리더십 이론", "상황에 따라 적절한 리더십 스타일을 적용하는 이론"),
            ("리더십", "변혁적 리더십", "비전과 카리스마로 조직원들의 변화를 이끄는 리더십"),
            ("리더십", "거래적 리더십", "보상과 처벌을 통한 성과 관리 중심의 리더십"),
            ("리더십", "카리스마 리더십", "개인의 특별한 영향력을 통한 리더십"),
            ("리더십", "서번트 리더십", "구성원을 섬기고 지원하는 리더십"),
            ("리더십", "권력과 영향력 이론", "조직 내 권력 구조와 영향력 행사 방식"),
            ("리더십", "리더십 그리드 이론", "과업과 관계 중심의 리더십 스타일 매트릭스"),
            ("리더십", "감성 리더십", "감성 지능을 활용한 리더십"),
            ("리더십", "유목 리더십", "유연하고 적응적인 리더십"),
            ("리더십", "윤리적 리더십", "도덕성과 윤리를 중시하는 리더십"),
            
            # 3. 조직 관리 (Organizational Management)
            ("조직 관리", "조직 행동 이론", "조직 내 개인과 그룹의 행동을 이해하고 관리하는 이론"),
            ("조직 관리", "맥그리거의 XY 이론", "인간의 본성에 대한 두 가지 상반된 관점을 통한 관리 이론"),
            ("조직 관리", "조직 문화 이론", "조직의 가치, 신념, 행동 양식을 이해하고 관리하는 이론"),
            ("조직 관리", "홀의 문화 차원 이론", "문화적 차이가 조직에 미치는 영향을 분석하는 이론"),
            ("조직 관리", "리더-구성원 교환 이론", "리더와 구성원 간의 관계 품질에 관한 이론"),
            ("조직 관리", "학습 조직", "지속적인 학습과 혁신을 추구하는 조직 모델"),
            ("조직 관리", "아지리스의 성숙-미성숙 이론", "개인의 성장과 조직 발전의 관계를 설명하는 이론"),
            ("조직 관리", "조직 내 커뮤니케이션 이론", "조직 내 효과적인 의사소통 방법론"),
            ("조직 관리", "직무 설계 이론", "효율적인 직무 구조화와 설계 방법"),
            ("조직 관리", "경영혁신 이론", "조직의 혁신적 변화 관리 방법론"),
            
            # 4. 마케팅 (Marketing)
            ("마케팅", "4P 마케팅 믹스", "제품, 가격, 유통, 촉진의 통합적 마케팅 전략"),
            ("마케팅", "STP 전략", "시장 세분화, 타겟팅, 포지셔닝의 전략적 접근"),
            ("마케팅", "고객 여정 지도", "고객 경험의 전체 과정을 시각화하고 분석하는 도구"),
            ("마케팅", "브랜드 자산 이론", "브랜드의 가치와 영향력을 측정하고 관리하는 이론"),
            ("마케팅", "퍼미션 마케팅", "고객의 동의를 기반으로 하는 마케팅 접근법"),
            ("마케팅", "관계 마케팅", "고객과의 장기적 관계 구축을 중시하는 마케팅"),
            ("마케팅", "제품 수명 주기 이론", "제품의 시장 진입부터 쇠퇴까지의 단계별 전략"),
            ("마케팅", "콘텐츠 마케팅 전략", "가치 있는 콘텐츠를 통한 고객 확보 전략"),
            ("마케팅", "충성도 프로그램 이론", "고객 충성도 향상을 위한 프로그램 설계"),
            ("마케팅", "구전 마케팅", "고객 간 자발적 정보 전파를 활용한 마케팅"),
            
            # 5. 운영 관리 (Operations Management)
            ("운영 관리", "린 생산 방식", "낭비를 제거하고 가치를 최적화하는 생산 방식"),
            ("운영 관리", "식스 시그마", "품질 향상과 변동성 감소를 위한 체계적 접근"),
            ("운영 관리", "칸반 시스템", "작업 흐름을 시각화하고 관리하는 시스템"),
            ("운영 관리", "품질 관리 이론", "전사적 품질 관리를 위한 종합적 접근"),
            ("운영 관리", "제약 이론", "시스템의 제약요소를 관리하여 성과를 개선하는 이론"),
            ("운영 관리", "지속 가능성 운영", "환경과 사회를 고려한 지속 가능한 운영 방식"),
            ("운영 관리", "적시생산", "재고를 최소화하고 생산 효율을 높이는 시스템"),
            ("운영 관리", "공급망 관리", "공급망 전체의 효율성을 최적화하는 관리 방식"),
            ("운영 관리", "ERP 시스템", "기업 자원을 통합적으로 관리하는 시스템"),
            ("운영 관리", "서비스 운영 관리", "서비스 제공 프로세스의 효율적 관리"),
            
            # 6. 혁신과 창의성 (Innovation & Creativity)
            ("혁신과 창의성", "개방형 혁신", "외부 자원을 활용한 혁신 전략"),
            ("혁신과 창의성", "파괴적 혁신", "기존 시장을 근본적으로 변화시키는 혁신"),
            ("혁신과 창의성", "혁신 확산 이론", "혁신이 사회에 퍼져나가는 과정을 설명하는 이론"),
            ("혁신과 창의성", "설계 사고", "사용자 중심의 문제 해결 방법론"),
            ("혁신과 창의성", "기술 수명 주기 이론", "기술의 발전과 쇠퇴 과정을 설명하는 이론"),
            ("혁신과 창의성", "삼중 나선 모델", "산학연 협력을 통한 혁신 창출 모델"),
            ("혁신과 창의성", "클레이튼 크리스텐슨의 혁신 이론", "지속적/파괴적 혁신의 특성과 영향"),
            ("혁신과 창의성", "창의성의 5단계 이론", "창의적 문제 해결의 단계별 접근"),
            ("혁신과 창의성", "이노베이션 킷캣 모델", "혁신의 단계적 실행 방법론"),
            ("혁신과 창의성", "혁신 생태계 이론", "혁신 주체들 간의 상호작용과 발전 과정"),
            
            # 7. 재무 관리 (Financial Management)
            ("재무 관리", "EVA", "기업의 실질적인 경제적 부가가치 측정"),
            ("재무 관리", "자본 비용 이론", "자본 조달 비용의 최적화 방안"),
            ("재무 관리", "자본 구조 이론", "부채와 자기자본의 최적 비율 결정"),
            ("재무 관리", "현금 흐름 분석", "기업의 현금 유입과 유출 관리"),
            ("재무 관리", "기업가치 평가", "기업의 실질 가치 산정 방법"),
            ("재무 관리", "효율적 시장 가설", "시장 가격의 정보 반영 효율성"),
            ("재무 관리", "투자 포트폴리오 이론", "위험과 수익의 최적 균형 달성"),
            ("재무 관리", "재무비율 분석", "기업의 재무 상태와 성과 평가"),
            ("재무 관리", "위험 관리 이론", "재무적 위험의 식별과 관리"),
            ("재무 관리", "M&A 전략", "기업 인수합병의 전략적 접근"),
            
            # 8. 인사 관리 (Human Resources Management)
            ("인사 관리", "직무 만족 이론", "직원의 직무 만족도 향상 방안"),
            ("인사 관리", "인재 관리", "핵심 인재의 확보와 육성 전략"),
            ("인사 관리", "동기 부여 이론", "직원의 동기 부여 메커니즘"),
            ("인사 관리", "공정성 이론", "조직 내 공정성 인식과 영향"),
            ("인사 관리", "목표 설정 이론", "효과적인 목표 설정과 성과 관리"),
            ("인사 관리", "사회적 교환 이론", "조직과 구성원 간의 상호 호혜적 관계"),
            ("인사 관리", "직무 분석 이론", "직무의 체계적 분석과 설계"),
            ("인사 관리", "성과 평가 이론", "공정하고 효과적인 성과 평가 방법"),
            ("인사 관리", "팀 다이내믹스", "팀의 형성과 발전 과정"),
            ("인사 관리", "인재 유지 전략", "핵심 인재의 이탈 방지 전략"),
            
            # 9. 경영 정보 시스템 (Management Information Systems)
            ("경영 정보 시스템", "정보 시스템 전략", "IT 자원의 전략적 활용 방안"),
            ("경영 정보 시스템", "빅데이터 분석", "대규모 데이터의 분석과 활용"),
            ("경영 정보 시스템", "디지털 전환 전략", "디지털 기술을 통한 비즈니스 혁신"),
            ("경영 정보 시스템", "클라우드 컴퓨팅", "클라우드 기반의 IT 인프라 구축"),
            ("경영 정보 시스템", "ERP 시스템 이론", "전사적 자원 관리 시스템의 구축과 운영"),
            ("경영 정보 시스템", "데이터 거버넌스", "데이터의 품질과 보안 관리"),
            ("경영 정보 시스템", "IoT 경영 이론", "사물인터넷의 비즈니스 활용"),
            ("경영 정보 시스템", "블록체인 응용", "블록체인 기술의 비즈니스 적용"),
            ("경영 정보 시스템", "사이버 보안 관리", "정보 보안 위험의 관리"),
            ("경영 정보 시스템", "AI 기반 의사결정 시스템", "인공지능을 활용한 의사결정 지원"),
            
            # 10. 기타 경영 이론
            ("기타 경영 이론", "변화 관리 이론", "조직 변화의 효과적 관리"),
            ("기타 경영 이론", "공유 가치 창출", "사회적 가치와 경제적 가치의 동시 추구"),
            ("기타 경영 이론", "사회적 책임 경영", "기업의 사회적 책임과 지속가능성"),
            ("기타 경영 이론", "지속 가능성 모델", "경제, 사회, 환경의 균형적 발전"),
            ("기타 경영 이론", "아지노모토 이론", "품질과 가치의 최적 균형점 도출"),
            ("기타 경영 이론", "비즈니스 윤리 이론", "윤리적 의사결정과 경영"),
            ("기타 경영 이론", "카이젠 이론", "지속적인 개선과 혁신"),
            ("기타 경영 이론", "균형성과표", "다차원적 성과 측정과 관리"),
            ("기타 경영 이론", "홀라크라시", "자율적이고 분산된 조직 구조"),
            ("기타 경영 이론", "스테이크홀더 이론", "이해관계자 중심의 경영 접근")
        ]
        
        cursor.executemany("""
            INSERT INTO management_theories (category, name, description)
            VALUES (%s, %s, %s)
        """, theories_data)
        
        conn.commit()
        st.success("✅ 전략 프레임워크 테이블이 생성되고 100개의 경영 이론이 입력되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_business_model_canvas_tables():
    """Business Model Canvas 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # Business Model Canvas 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_model_canvas (
                canvas_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                version INT DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Canvas 컴포넌트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canvas_components (
                component_id INT AUTO_INCREMENT PRIMARY KEY,
                canvas_id INT NOT NULL,
                component_type ENUM(
                    'key_partners',
                    'key_activities',
                    'key_resources',
                    'value_propositions',
                    'customer_relationships',
                    'channels',
                    'customer_segments',
                    'cost_structure',
                    'revenue_streams'
                ) NOT NULL,
                content TEXT NOT NULL,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (canvas_id) REFERENCES business_model_canvas(canvas_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Canvas 분석 및 코멘트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canvas_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                canvas_id INT NOT NULL,
                analysis_type ENUM('strength', 'weakness', 'opportunity', 'threat', 'comment') NOT NULL,
                content TEXT NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (canvas_id) REFERENCES business_model_canvas(canvas_id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Business Model Canvas 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_swot_analysis_tables():
    """SWOT 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # SWOT 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swot_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                version INT DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # SWOT 항목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swot_items (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                category ENUM('strength', 'weakness', 'opportunity', 'threat') NOT NULL,
                content TEXT NOT NULL,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES swot_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ SWOT 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_marketing_mix_tables():
    """4P/7P 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 4P/7P 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marketing_mix_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                analysis_type ENUM('4P', '7P') NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 4P/7P 컴포넌트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marketing_mix_components (
                component_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                component_type ENUM(
                    'product',
                    'price',
                    'place',
                    'promotion',
                    'people',
                    'process',
                    'physical_evidence'
                ) NOT NULL,
                content TEXT NOT NULL,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES marketing_mix_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ 4P/7P 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_pestel_analysis_tables():
    """PEST/PESTEL 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # PESTEL 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pestel_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                analysis_type ENUM('PEST', 'PESTEL') NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # PESTEL 컴포넌트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pestel_components (
                component_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                component_type ENUM(
                    'political',
                    'economic',
                    'social',
                    'technological',
                    'environmental',
                    'legal'
                ) NOT NULL,
                content TEXT NOT NULL,
                impact_level ENUM('high', 'medium', 'low') DEFAULT 'medium',
                trend ENUM('increasing', 'stable', 'decreasing') DEFAULT 'stable',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES pestel_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ PEST/PESTEL 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_five_forces_tables():
    """Porter's 5 Forces 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 5 Forces 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS five_forces_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 5 Forces 컴포넌트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS five_forces_components (
                component_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                component_type ENUM(
                    'rivalry',
                    'new_entrants',
                    'substitutes',
                    'buyer_power',
                    'supplier_power'
                ) NOT NULL,
                content TEXT NOT NULL,
                threat_level ENUM('very_low', 'low', 'medium', 'high', 'very_high') DEFAULT 'medium',
                key_factors TEXT,
                recommendations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES five_forces_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Porter's 5 Forces 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_value_chain_tables():
    """Value Chain 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # Value Chain 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS value_chain_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Value Chain 컴포넌트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS value_chain_components (
                component_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                activity_type ENUM(
                    'inbound_logistics',
                    'operations',
                    'outbound_logistics',
                    'marketing_sales',
                    'service',
                    'firm_infrastructure',
                    'hr_management',
                    'technology_development',
                    'procurement'
                ) NOT NULL,
                activity_category ENUM('primary', 'support') NOT NULL,
                content TEXT NOT NULL,
                strength_level ENUM('very_weak', 'weak', 'moderate', 'strong', 'very_strong') DEFAULT 'moderate',
                improvement_points TEXT,
                cost_impact DECIMAL(5,2),
                value_impact DECIMAL(5,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES value_chain_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Value Chain 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_gap_analysis_tables():
    """GAP 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # GAP 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gap_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # GAP 분석 항목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gap_analysis_items (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                category VARCHAR(100) NOT NULL,
                current_state TEXT NOT NULL,
                desired_state TEXT NOT NULL,
                gap_description TEXT NOT NULL,
                priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
                action_plan TEXT,
                timeline VARCHAR(100),
                resources_needed TEXT,
                metrics TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES gap_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ GAP 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_blue_ocean_tables():
    """Blue Ocean 전략 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # Blue Ocean 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blue_ocean_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                industry VARCHAR(100) NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 4 Actions Framework 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blue_ocean_actions (
                action_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                action_type ENUM('eliminate', 'reduce', 'raise', 'create') NOT NULL,
                factor VARCHAR(200) NOT NULL,
                description TEXT,
                impact_level INT DEFAULT 3,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES blue_ocean_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Strategy Canvas 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blue_ocean_canvas (
                canvas_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                competing_factor VARCHAR(200) NOT NULL,
                industry_score INT NOT NULL,
                company_score INT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES blue_ocean_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Blue Ocean 전략 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_innovators_dilemma_tables():
    """Innovator's Dilemma 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # Innovator's Dilemma 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS innovators_dilemma_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                industry VARCHAR(100) NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 현재 기술/제품 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS innovators_current_tech (
                tech_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                tech_name VARCHAR(200) NOT NULL,
                description TEXT,
                market_position ENUM('low', 'mid', 'high') NOT NULL,
                performance_level INT NOT NULL,
                customer_demand INT NOT NULL,
                market_size DECIMAL(10,2),
                profit_margin DECIMAL(5,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES innovators_dilemma_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 파괴적 혁신 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS innovators_disruptive_tech (
                tech_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                tech_name VARCHAR(200) NOT NULL,
                description TEXT,
                innovation_type ENUM('low_end', 'new_market') NOT NULL,
                current_performance INT NOT NULL,
                expected_growth_rate DECIMAL(5,2),
                potential_market_size DECIMAL(10,2),
                development_status ENUM('research', 'development', 'testing', 'market_entry') NOT NULL,
                risk_level ENUM('low', 'medium', 'high') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES innovators_dilemma_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 대응 전략 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS innovators_strategies (
                strategy_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                strategy_type ENUM('defend', 'adapt', 'disrupt') NOT NULL,
                description TEXT NOT NULL,
                implementation_plan TEXT,
                required_resources TEXT,
                timeline VARCHAR(100),
                success_metrics TEXT,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES innovators_dilemma_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Innovator's Dilemma 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_portfolio_analysis_tables():
    """Portfolio 분석 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # Portfolio 분석 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                analysis_type ENUM('bcg', 'ge_mckinsey', 'ansoff') NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('draft', 'completed', 'archived') DEFAULT 'draft',
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Portfolio 항목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_items (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                item_name VARCHAR(200) NOT NULL,
                description TEXT,
                market_growth DECIMAL(5,2),
                market_share DECIMAL(5,2),
                market_attractiveness INT,
                business_strength INT,
                market_penetration DECIMAL(5,2),
                market_development DECIMAL(5,2),
                product_development DECIMAL(5,2),
                diversification DECIMAL(5,2),
                current_revenue DECIMAL(10,2),
                potential_revenue DECIMAL(10,2),
                investment_required DECIMAL(10,2),
                risk_level ENUM('low', 'medium', 'high') DEFAULT 'medium',
                priority INT DEFAULT 0,
                recommendations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES portfolio_analysis(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ Portfolio 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_toc_analysis_tables():
    """TOC 분석을 위한 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS toc_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                area VARCHAR(50) NOT NULL,
                current_state JSON NOT NULL,
                constraints JSON NOT NULL,
                solutions JSON NOT NULL,
                implementation_plan JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ TOC 분석 테이블이 성공적으로 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_decision_making_tables():
    """의사결정 지원 시스템 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS decision_reference_files")
        cursor.execute("DROP TABLE IF EXISTS decision_ai_analysis")
        cursor.execute("DROP TABLE IF EXISTS decision_options")
        cursor.execute("DROP TABLE IF EXISTS decision_cases")
        
        # 의사결정 안건 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_cases (
                case_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                decision_maker VARCHAR(100),
                status ENUM('pending', 'approved', 'rejected', 'deferred') DEFAULT 'pending',
                final_option_id INT NULL,
                final_comment TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                decided_at TIMESTAMP NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 의사결정 옵션 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_options (
                option_id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                option_name VARCHAR(100) NOT NULL,
                advantages TEXT,
                disadvantages TEXT,
                estimated_duration VARCHAR(100),
                priority INT,
                additional_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES decision_cases(case_id)
                ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # AI 분석 결과 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_ai_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                model_name VARCHAR(50),
                analysis_content TEXT,
                recommendation TEXT,
                risk_assessment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES decision_cases(case_id)
                ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 외래 키 참조 설정
        cursor.execute("""
            ALTER TABLE decision_cases
            ADD FOREIGN KEY (final_option_id) 
            REFERENCES decision_options(option_id)
            ON DELETE SET NULL
        """)

        # 참고 자료 파일 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_reference_files (
                file_id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES decision_cases(case_id)
                ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        st.success("✅ 의사결정 지원 시스템 테이블이 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_mcp_server_tables():
    """MCP 서버 설정 테이블 생성"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # MCP 서버 설정 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mcp_server_configs (
                config_id INT AUTO_INCREMENT PRIMARY KEY,
                server_name VARCHAR(100) NOT NULL,
                server_type VARCHAR(50) NOT NULL,
                server_url VARCHAR(255),
                config_json TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_server_name (server_name)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ MCP 서버 설정 테이블이 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("DB 테이블 생성/수정/삭제 시스템")

    # 작업 선택
    operation = st.radio(
        "수행할 작업을 선택하세요",
        ["테이블 생성/수정", "테이블 삭제", "테이블 데이터 검색", "투표 시스템 테이블 생성", "Dot Collector 테이블 생성",
         "분야별 전문성 테이블 생성", "사업 전략 테이블 생성", "의사결정 트리 테이블 생성", "의사결정 트리 테이블 삭제",
         "전략 프레임워크 테이블 생성", "Business Model Canvas 테이블 생성", "SWOT 분석 테이블 생성", "4P/7P 분석 테이블 생성",
         "PESTEL 분석 테이블 생성", "5 Forces 분석 테이블 생성", "Value Chain 분석 테이블 생성", "GAP 분석 테이블 생성", "Blue Ocean 분석 테이블 생성",
         "Innovator's Dilemma 분석 테이블 생성", "Portfolio 분석 테이블 생성", "TOC 분석 테이블 생성", "의사결정 지원 시스템 테이블 생성", "MCP 서버 설정 테이블 생성"]
    )

    # 기존 테이블 목록 표시
    existing_tables = get_existing_tables()
    st.write("### 기존 테이블 목록")
    st.write(existing_tables)

    if operation == "테이블 데이터 검색":
        if existing_tables:
            # 테이블 선택
            selected_table = st.selectbox("검색할 테이블을 선택하세요", existing_tables)
            
            # 검색어 입력
            search_term = st.text_input("검색어를 입력하세요 (모든 필드에서 검색됩니다)")
            
            # 테이블 구조 표시
            st.write("### 테이블 구조")
            schema = get_table_schema(selected_table)
            schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
            st.dataframe(schema_df)
            
            # 데이터 검색 및 표시
            data = get_table_data(selected_table, search_term)
            if data:
                st.write("### 검색 결과")
                df = pd.DataFrame(data)
                
                # 검색 결과 수 표시
                st.success(f"검색 결과: {len(df)}건이 발견되었습니다.")
                
                # 데이터프레임으로 결과 표시
                st.dataframe(df, height=400)
                
                # 데이터 통계
                with st.expander("데이터 통계 보기"):
                    for column in df.columns:
                        if df[column].dtype in ['object', 'string']:
                            st.write(f"### {column} 별 데이터 수")
                            st.write(df[column].value_counts())
            else:
                st.warning("검색 결과가 없거나 테이블이 비어있습니다.")
        else:
            st.warning("검색할 테이블이 없습니다.")

    elif operation == "테이블 삭제":
        if existing_tables:
            table_to_delete = st.selectbox("삭제할 테이블을 선택하세요", existing_tables)
            if st.button("테이블 삭제", type="secondary"):
                if delete_table(table_to_delete):
                    st.success(f"테이블 {table_to_delete}이(가) 성공적으로 삭제되었습니다!")
                    st.rerun()
        else:
            st.warning("삭제할 테이블이 없습니다.")

    elif operation == "투표 시스템 테이블 생성":
        create_vote_tables()

    elif operation == "Dot Collector 테이블 생성":
        create_dot_collector_tables()

    elif operation == "분야별 전문성 테이블 생성":
        if st.button("테이블 생성"):
            success, message = create_dot_expertise_tables()
            if success:
                st.success(message)
            else:
                st.error(message)

    elif operation == "사업 전략 테이블 생성":
        if st.button("테이블 생성"):
            create_business_strategy_tables()

    elif operation == "의사결정 트리 테이블 생성":
        if st.button("테이블 생성"):
            create_decision_tree_tables()

    elif operation == "의사결정 트리 테이블 삭제":  # 새로운 옵션 처리
        if st.button("테이블 삭제", type="secondary"):
            drop_decision_tree_tables()

    elif operation == "전략 프레임워크 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_strategy_framework_tables()

    elif operation == "Business Model Canvas 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_business_model_canvas_tables()

    elif operation == "SWOT 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_swot_analysis_tables()

    elif operation == "4P/7P 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_marketing_mix_tables()

    elif operation == "PESTEL 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_pestel_analysis_tables()

    elif operation == "5 Forces 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_five_forces_tables()

    elif operation == "Value Chain 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_value_chain_tables()

    elif operation == "GAP 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_gap_analysis_tables()

    elif operation == "Blue Ocean 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_blue_ocean_tables()

    elif operation == "Innovator's Dilemma 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_innovators_dilemma_tables()

    elif operation == "Portfolio 분석 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_portfolio_analysis_tables()

    elif operation == "TOC 분석 테이블 생성":  # TOC 분석 테이블 생성 처리
        if st.button("테이블 생성"):
            create_toc_analysis_tables()

    elif operation == "의사결정 지원 시스템 테이블 생성":
        if st.button("테이블 생성 및 초기 데이터 입력"):
            create_decision_making_tables()

    elif operation == "MCP 서버 설정 테이블 생성":
        if st.button("테이블 생성"):
            create_mcp_server_tables()

    else:  # 테이블 생성/수정
        # 테이블 이름 입력
        table_name = st.text_input("테이블 이름을 입력하세요")

        if table_name:
            # 기존 테이블인 경우 스키마 표시
            if table_name in existing_tables:
                st.write("### 현재 테이블 구조")
                current_schema = get_table_schema(table_name)
                st.table(current_schema)
                st.info("기존 테이블 수정 시 입력한 칼럼만 수정되며, 나머지 칼럼은 유지됩니다.")

        # 칼럼 정보 입력
        st.write("### 칼럼 정보 입력")
        num_columns = st.number_input("수정/생성할 칼럼 수를 입력하세요", min_value=1, value=1)
        
        columns = []
        for i in range(int(num_columns)):
            col1, col2, col3 = st.columns(3)
            with col1:
                col_name = st.text_input(f"칼럼 {i+1} 이름", key=f"name_{i}")
            with col2:
                col_type = st.selectbox(f"칼럼 {i+1} 타입", 
                                      ["VARCHAR(255)", "TEXT", "DATETIME", "INT", "FLOAT", "BOOLEAN"],
                                      key=f"type_{i}")
            with col3:
                is_unique = st.checkbox(f"Unique Key에 포함", key=f"unique_{i}")
            
            if col_name and col_type:
                columns.append((col_name, col_type, is_unique))

        # Unique Key 설정
        unique_keys = [col[0] for col in columns if col[2]]

        if st.button("테이블 생성/수정"):
            if table_name and columns:
                if create_or_modify_table(table_name, columns, unique_keys):
                    st.success(f"테이블 {table_name}이(가) 성공적으로 생성/수정되었습니다!")
                    st.write("### 최종 테이블 구조")
                    final_schema = get_table_schema(table_name)
                    st.table(final_schema)
                else:
                    st.error("테이블 생성/수정 중 오류가 발생했습니다.")
            else:
                st.warning("테이블 이름과 최소 하나의 칼럼을 입력해주세요.")

if __name__ == "__main__":
    main() 