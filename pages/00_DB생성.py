import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
load_dotenv()

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

def main():
    st.title("DB 테이블 생성/수정/삭제 시스템")

    # 작업 선택
    operation = st.radio(
        "수행할 작업을 선택하세요",
        ["테이블 생성/수정", "테이블 삭제", "테이블 데이터 검색", "투표 시스템 테이블 생성", "Dot Collector 테이블 생성",
         "분야별 전문성 테이블 생성", "사업 전략 테이블 생성"]
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