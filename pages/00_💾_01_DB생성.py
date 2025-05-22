import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
import time
load_dotenv()

# 페이지 설정 - 테이블 생성/수정/삭제 시스템
st.set_page_config(
    page_title="DB 테이블 생성/수정/삭제 시스템",
    page_icon="💾",
    layout="wide"
)

def connect_to_db():
    """데이터베이스 연결"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

# 인증 기능 (간단한 비밀번호 보호)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == os.getenv('ADMIN_PASSWORD', 'mds0118!'):  # 환경 변수에서 비밀번호 가져오기
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

def create_or_modify_table(table_name, columns, unique_keys, mode="migrate"):
    """테이블 생성 또는 수정 (mode: migrate=기존 데이터 보존, reset=기존 데이터 삭제)"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        if mode == "reset":
            # 기존 테이블 삭제
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            # 새 테이블 생성 (기존 코드와 동일)
            column_defs = []
            for col in columns:
                col_def = f"{col['name']} {col['type']}"
                if col.get('not_null'):
                    col_def += " NOT NULL"
                if col.get('default'):
                    col_def += f" DEFAULT {col['default']}"
                if col.get('auto_increment'):
                    col_def += " AUTO_INCREMENT"
                if col.get('primary_key'):
                    col_def += " PRIMARY KEY"
                column_defs.append(col_def)
            for key in unique_keys:
                column_defs.append(f"UNIQUE KEY {key['name']} ({key['columns']})")
            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
            cursor.execute(create_table_sql)
        else:
            # migrate: 기존 데이터 보존, ALTER TABLE로 구조만 변경
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                # 테이블이 없으면 새로 생성
                column_defs = []
                for col in columns:
                    col_def = f"{col['name']} {col['type']}"
                    if col.get('not_null'):
                        col_def += " NOT NULL"
                    if col.get('default'):
                        col_def += f" DEFAULT {col['default']}"
                    if col.get('auto_increment'):
                        col_def += " AUTO_INCREMENT"
                    if col.get('primary_key'):
                        col_def += " PRIMARY KEY"
                    column_defs.append(col_def)
                for key in unique_keys:
                    column_defs.append(f"UNIQUE KEY {key['name']} ({key['columns']})")
                create_table_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
                cursor.execute(create_table_sql)
            else:
                # 테이블이 있으면 ALTER TABLE로 컬럼 추가/수정
                for col in columns:
                    col_name = col['name']
                    col_type = col['type']
                    # 칼럼 존재 여부 확인
                    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{col_name}'")
                    column_exists = cursor.fetchone() is not None
                    if column_exists:
                        # 기존 칼럼 수정
                        cursor.execute(f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} {col_type}")
                    else:
                        # 새 칼럼 추가
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                # 유니크 키 등 추가는 필요시 구현
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
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
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
        cursor = conn.cursor()
        
        # 먼저 테이블의 컬럼 정보를 가져옴
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]
        
        if search_term:
            # 각 컬럼에 대해 LIKE 조건 생성
            search_conditions = []
            params = []
            for col_name in column_names:
                search_conditions.append(f"`{col_name}` LIKE %s")
                params.append(f"%{search_term}%")
            
            # 검색 쿼리 실행
            query = f"SELECT * FROM {table_name} WHERE {' OR '.join(search_conditions)}"
            cursor.execute(query, params)
        else:
            cursor.execute(f"SELECT * FROM {table_name}")
        
        data = cursor.fetchall()
        result_columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        
        return pd.DataFrame(data, columns=result_columns)
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return pd.DataFrame()

def create_rayleigh_skylights_tables():
    """Rayleigh skylights 관련 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS sales")
        cursor.execute("DROP TABLE IF EXISTS bill_of_materials")
        cursor.execute("DROP TABLE IF EXISTS parts")
        cursor.execute("DROP TABLE IF EXISTS products")
        conn.commit()
        
        # 제품 테이블 생성
        cursor.execute('''
            CREATE TABLE products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_code VARCHAR(50) UNIQUE NOT NULL,
                product_name VARCHAR(100) NOT NULL,
                product_type VARCHAR(50) NOT NULL,  -- 고정식, 개폐식, 자동식 등
                size VARCHAR(50) NOT NULL,  -- 제품 크기
                brand VARCHAR(100) NOT NULL,
                selling_price DECIMAL(10, 2) NOT NULL,
                production_cost DECIMAL(10, 2) NOT NULL,
                stock INT DEFAULT 0,
                specifications TEXT,  -- 제품 사양 정보
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # 판매 테이블 생성
        cursor.execute('''
            CREATE TABLE sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_number VARCHAR(50) UNIQUE NOT NULL,
                sale_date DATE NOT NULL,
                customer VARCHAR(100) NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        
        # 부품 테이블 생성
        cursor.execute('''
            CREATE TABLE parts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                part_code VARCHAR(50) UNIQUE NOT NULL,
                part_name VARCHAR(100) NOT NULL,
                part_category VARCHAR(50) NOT NULL,  -- 프레임, 글라스, 실링 등
                supplier VARCHAR(100) NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                lead_time INT NOT NULL,
                min_stock INT NOT NULL,
                stock INT DEFAULT 0,
                specifications TEXT,  -- 부품 사양 정보
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # Rayleigh skylights 부품 데이터 삽입
        parts_data = [
            # 1. 광 수집 시스템
            ('DOME-001', '아크릴 돔', '광 수집 시스템', 'YUER', 150000.00, 7, 5, 0, '직경 60cm, UV 차단 코팅'),
            ('DOME-002', '폴리카보네이트 돔', '광 수집 시스템', 'YUER', 120000.00, 7, 5, 0, '직경 60cm, UV 차단 코팅'),
            ('SOLAR-001', '솔라 트래커', '광 수집 시스템', 'YUER', 300000.00, 14, 3, 0, '자동 각도 조절, IoT 연동'),
            
            # 2. 광 경로 제어 시스템
            ('FIBER-001', '광섬유 케이블', '광 경로 제어 시스템', 'YUER', 80000.00, 10, 10, 0, '길이 5m, 고반사율 코팅'),
            ('TUBE-001', '라이트 튜브', '광 경로 제어 시스템', 'YUER', 100000.00, 10, 8, 0, '직경 30cm, 알루미늄 코팅'),
            ('DIFF-001', '빛 확산 필름', '광 경로 제어 시스템', 'YUER', 50000.00, 5, 15, 0, '프리즘 구조, 고반사율'),
            
            # 3. Rayleigh 산란 시뮬레이션 요소
            ('SCAT-001', '산란 필름', '산란 시뮬레이션', 'YUER', 70000.00, 7, 10, 0, '나노구조, 청색 파장 강조'),
            ('FILTER-001', '파장 선택 필터', '산란 시뮬레이션', 'YUER', 60000.00, 7, 8, 0, '청색 파장 선택적 투과'),
            
            # 4. 확산 및 조명 시스템
            ('PANEL-001', '디퓨저 패널', '확산 시스템', 'YUER', 90000.00, 7, 8, 0, '매트 아크릴, 60x60cm'),
            ('PANEL-002', '마이크로렌즈 디퓨저', '확산 시스템', 'YUER', 110000.00, 7, 6, 0, '고급형, 균일한 확산'),
            
            # 5. 보조 전기 시스템
            ('SENSOR-001', '조도 센서', '전기 시스템', 'YUER', 50000.00, 7, 10, 0, 'IoT 연동, 자동 조도 조절'),
            ('LED-001', 'LED 백업 조명', '전기 시스템', 'YUER', 80000.00, 7, 8, 0, '3000K-6500K 조광 가능'),
            ('CTRL-001', '스마트 제어 시스템', '전기 시스템', 'YUER', 150000.00, 14, 5, 0, 'IoT 연동, 앱 제어'),
            
            # 6. 설치 및 마운팅 부품
            ('FRAME-001', '알루미늄 프레임', '설치 부품', 'YUER', 120000.00, 7, 8, 0, '60x60cm, 방수 처리'),
            ('SEAL-001', '실링 키트', '설치 부품', 'YUER', 40000.00, 5, 15, 0, 'EPDM 고무, 방수/단열'),
            ('BRACKET-001', '고정 브래킷', '설치 부품', 'YUER', 30000.00, 5, 20, 0, '스테인리스 스틸')
        ]
        
        cursor.executemany('''
            INSERT INTO parts (part_code, part_name, part_category, supplier, unit_price, lead_time, min_stock, stock, specifications)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', parts_data)
        
        # 제품 데이터 생성
        products = [
            ('PR001', 'V6 엔진', '고정식', '대형', 'YUER', 5000000, 3000000, 10),
            ('PR002', 'V8 엔진', '고정식', '대형', 'YUER', 8000000, 4800000, 5),
            ('PR003', 'I4 엔진', '개폐식', '중형', 'YUER', 3000000, 1800000, 15),
            ('PR004', '디젤 엔진', '고정식', '대형', 'YUER', 6000000, 3600000, 8),
            ('PR005', '하이브리드 엔진', '자동식', '중형', 'YUER', 7000000, 4200000, 12)
        ]
        
        cursor.executemany('''
            INSERT INTO products (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', products)
        
        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def create_self_introduction_table():
    """자기소개서 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS self_introductions")
        
        # 새 테이블 생성
        cursor.execute('''
            CREATE TABLE self_introductions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(100) NOT NULL,  -- 비밀번호 저장 필드
                name VARCHAR(50) NOT NULL,
                position VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                expertise TEXT NOT NULL,
                current_tasks TEXT NOT NULL,
                collaboration_style TEXT NOT NULL,
                support_areas TEXT NOT NULL,
                need_help_areas TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def create_toc_analysis_tables():
    """TOC 분석 관련 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS toc_analyses")
        cursor.execute("DROP TABLE IF EXISTS toc_analysis_relationships")
        cursor.execute("DROP TABLE IF EXISTS toc_model_relationships")
        
        # TOC 분석 테이블 생성
        cursor.execute('''
            CREATE TABLE toc_analyses (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_name VARCHAR(255) NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,  -- 5단계 집중 프로세스, 사고 프로세스, 쓰루풋 회계 등
                description TEXT,
                analysis_data JSON,  -- 분석 데이터 저장 (차트, 결과 등)
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_analysis (analysis_name, analysis_type)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # TOC 분석 결과 간 연관성 테이블 생성
        cursor.execute('''
            CREATE TABLE toc_analysis_relationships (
                relationship_id INT AUTO_INCREMENT PRIMARY KEY,
                source_analysis_id INT,
                target_analysis_id INT,
                relationship_type VARCHAR(50),  -- 인과관계, 영향도, 의존성 등
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_analysis_id) REFERENCES toc_analyses(analysis_id),
                FOREIGN KEY (target_analysis_id) REFERENCES toc_analyses(analysis_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # TOC 모델 간 연관성 메타데이터 테이블 생성
        cursor.execute('''
            CREATE TABLE toc_model_relationships (
                model_relationship_id INT AUTO_INCREMENT PRIMARY KEY,
                source_model VARCHAR(50),  -- 5단계 집중 프로세스, 사고 프로세스 등
                target_model VARCHAR(50),
                relationship_type VARCHAR(50),  -- 보완관계, 선후관계 등
                description TEXT,
                flow_chart TEXT,  -- Mermaid 차트 데이터
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def create_valuation_tables():
    """기업 가치 평가 관련 테이블 생성"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS valuation_analyses")
        cursor.execute("DROP TABLE IF EXISTS valuation_financial_data")
        cursor.execute("DROP TABLE IF EXISTS valuation_market_data")
        cursor.execute("DROP TABLE IF EXISTS valuation_agent_analyses")
        cursor.execute("DROP TABLE IF EXISTS valuation_results")
        
        # 기업 가치 평가 분석 테이블 생성
        cursor.execute('''
            CREATE TABLE valuation_analyses (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                company_name VARCHAR(100) NOT NULL,
                industry VARCHAR(100) NOT NULL,
                company_description TEXT,
                base_currency VARCHAR(10) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # 재무 데이터 테이블 생성
        cursor.execute('''
            CREATE TABLE valuation_financial_data (
                financial_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                revenue DECIMAL(20, 2) NOT NULL,
                operating_profit DECIMAL(20, 2) NOT NULL,
                depreciation DECIMAL(20, 2) NOT NULL,
                amortization DECIMAL(20, 2) NOT NULL,
                net_income DECIMAL(20, 2) NOT NULL,
                current_fcf DECIMAL(20, 2) NOT NULL,
                growth_rate DECIMAL(10, 4) NOT NULL,
                discount_rate DECIMAL(10, 4) NOT NULL,
                terminal_growth_rate DECIMAL(10, 4) NOT NULL,
                net_debt DECIMAL(20, 2) NOT NULL,
                r_and_d_cost DECIMAL(20, 2) NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES valuation_analyses(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # 시장 데이터 테이블 생성
        cursor.execute('''
            CREATE TABLE valuation_market_data (
                market_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                patents_count INT NOT NULL,
                trademarks_count INT NOT NULL,
                technology_impact DECIMAL(10, 4) NOT NULL,
                market_size DECIMAL(20, 2) NOT NULL,
                market_share DECIMAL(10, 4) NOT NULL,
                per_values JSON NOT NULL,
                evebitda_values JSON NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES valuation_analyses(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # AI 에이전트 분석 결과 테이블 생성
        cursor.execute('''
            CREATE TABLE valuation_agent_analyses (
                agent_analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                agent_type VARCHAR(50) NOT NULL,  -- financial_agent, market_agent, tech_agent 등
                analysis_content TEXT NOT NULL,
                valuation_summary TEXT NOT NULL,
                risk_assessment TEXT NOT NULL,
                mermaid_chart TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES valuation_analyses(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # 가치 평가 결과 테이블 생성
        cursor.execute('''
            CREATE TABLE valuation_results (
                result_id INT AUTO_INCREMENT PRIMARY KEY,
                analysis_id INT NOT NULL,
                valuation_method VARCHAR(50) NOT NULL,  -- DCF, PER, EV/EBITDA 등
                result_data JSON NOT NULL,  -- 각 방법론별 상세 결과
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES valuation_analyses(analysis_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        
        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return False

def create_vote_tables():
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 주관식 질문 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjective_questions (
                question_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                multiple_answers BOOLEAN DEFAULT FALSE,
                max_answers INT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('active', 'closed') DEFAULT 'active'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 주관식 응답 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjective_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                answer_text TEXT NOT NULL,
                voter_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id)
                ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 주관식 LLM 응답 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjective_llm_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                answer_text TEXT NOT NULL,
                llm_model VARCHAR(50),
                reasoning TEXT,
                weight INT DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id)
                ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        conn.commit()
        print("주관식 투표 테이블이 성공적으로 생성되었습니다.")
        
    except mysql.connector.Error as err:
        print(f"테이블 생성 중 오류 발생: {err}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_subjective_tables():
    """주관식 질문 관련 테이블 생성"""
    conn = connect_to_db()
    if not conn:
        st.error("데이터베이스 연결에 실패했습니다.")
        return False
        
    cursor = conn.cursor()
    
    try:
        # Drop existing tables if they exist
        cursor.execute("DROP TABLE IF EXISTS subjective_responses")
        cursor.execute("DROP TABLE IF EXISTS subjective_llm_responses")
        cursor.execute("DROP TABLE IF EXISTS subjective_questions")
        
        # Create subjective_questions table
        cursor.execute("""
            CREATE TABLE subjective_questions (
                question_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                created_by VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('active', 'closed') DEFAULT 'active',
                multiple_answers BOOLEAN DEFAULT FALSE,
                max_answers INT,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Create subjective_responses table
        cursor.execute("""
            CREATE TABLE subjective_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT NOT NULL,
                voter_name VARCHAR(100) NOT NULL,
                response_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id) ON DELETE CASCADE,
                INDEX idx_question_voter (question_id, voter_name),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Create subjective_llm_responses table
        cursor.execute("""
            CREATE TABLE subjective_llm_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT NOT NULL,
                llm_model VARCHAR(50) NOT NULL,
                response_text TEXT NOT NULL,
                reasoning TEXT,
                weight INT DEFAULT 1,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id) ON DELETE CASCADE,
                INDEX idx_question_model (question_id, llm_model),
                INDEX idx_voted_at (voted_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        conn.commit()
        st.success("주관식 질문 관련 테이블이 성공적으로 생성되었습니다!")
        
        # Show the created table structures
        st.write("### 생성된 테이블 구조:")
        
        # Show subjective_questions table structure
        st.write("#### 주관식 질문 테이블 (subjective_questions)")
        schema = get_table_schema("subjective_questions")
        if schema:
            schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
            st.dataframe(schema_df)
        
        # Show subjective_responses table structure
        st.write("#### 주관식 응답 테이블 (subjective_responses)")
        schema = get_table_schema("subjective_responses")
        if schema:
            schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
            st.dataframe(schema_df)
        
        # Show subjective_llm_responses table structure
        st.write("#### 주관식 LLM 응답 테이블 (subjective_llm_responses)")
        schema = get_table_schema("subjective_llm_responses")
        if schema:
            schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
            st.dataframe(schema_df)
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {err}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_subjective_llm_tables():
    """주관식 LLM 응답 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # subjective_llm_responses 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjective_llm_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT NOT NULL,
                llm_model VARCHAR(50) NOT NULL,
                response_text TEXT NOT NULL,
                reasoning TEXT,
                weight INT DEFAULT 1,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        print("주관식 LLM 응답 테이블이 생성되었습니다.")
        
    except mysql.connector.Error as err:
        print(f"테이블 생성 중 오류 발생: {err}")
    finally:
        cursor.close()
        conn.close()

def insert_default_suppliers(cursor):
    """기본 공급업체 데이터 삽입"""
    suppliers_data = [
        ('YUER', 'YUER 담당자', 'contact@yuer.com', '+86-123-4567-8901', '중국 광동성 선전시'),
        ('Signcomplex', 'Signcomplex 담당자', 'contact@signcomplex.com', '+86-123-4567-8902', '중국 광동성 광주시'),
        ('Keyun', 'Keyun 담당자', 'contact@keyun.com', '+86-123-4567-8903', '중국 광동성 동관시'),
        ('LEDYi', 'LEDYi 담당자', 'contact@ledyi.com', '+86-123-4567-8904', '중국 광동성 선전시'),
        ('Wellmax', 'Wellmax 담당자', 'contact@wellmax.com', '+86-123-4567-8905', '중국 광동성 광주시'),
        ('FSL', 'FSL 담당자', 'contact@fsl.com', '+86-123-4567-8906', '중국 광동성 동관시')
    ]
    
    try:
        # 기존 데이터 삭제
        cursor.execute("DELETE FROM suppliers")
        
        # 새 데이터 삽입
        cursor.executemany("""
            INSERT INTO suppliers 
            (supplier_name, contact_person, email, phone, address)
            VALUES (%s, %s, %s, %s, %s)
        """, suppliers_data)
        
        return True
    except mysql.connector.Error as err:
        print(f"공급업체 데이터 삽입 중 오류 발생: {err}")
        return False

def get_supplier_names():
    """공급업체 이름 목록 조회 (드롭다운용)"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 공급업체 이름만 조회하고 정렬 순서 지정
        cursor.execute("""
            SELECT supplier_name 
            FROM suppliers 
            ORDER BY FIELD(supplier_name, 'YUER', 'Signcomplex', 'Keyun', 'LEDYi', 'Wellmax', 'FSL'),
            supplier_name
        """)
        
        suppliers = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return suppliers
    except mysql.connector.Error as err:
        print(f"공급업체 목록 조회 중 오류 발생: {err}")
        return []

def create_logistics_tables(mode="migrate"):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        if mode == "reset":
            # --- 기존 테이블 삭제 후 새로 생성 (데이터 삭제) ---
            cursor.execute("DROP TABLE IF EXISTS shipment_tracking")
            cursor.execute("DROP TABLE IF EXISTS ci_items")
            cursor.execute("DROP TABLE IF EXISTS commercial_invoices")
            cursor.execute("DROP TABLE IF EXISTS pi_items")
            cursor.execute("DROP TABLE IF EXISTS proforma_invoices")
            cursor.execute("DROP TABLE IF EXISTS inventory_transactions")
            cursor.execute("DROP TABLE IF EXISTS inventory_logistics")
            cursor.execute("DROP TABLE IF EXISTS products_logistics")
            cursor.execute("DROP TABLE IF EXISTS suppliers")
            conn.commit()

        # --- 문자셋 통일을 위한 마이그레이션 ---
        cursor.execute("""
            ALTER DATABASE {} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """.format(os.getenv('SQL_DATABASE_NEWBIZ')))

        # 공급업체 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_name VARCHAR(100) NOT NULL,
                contact_person VARCHAR(50),
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 기본 공급업체 데이터 삽입
        if insert_default_suppliers(cursor):
            conn.commit()
            print("기본 공급업체 데이터가 성공적으로 삽입되었습니다.")
        else:
            print("기본 공급업체 데이터 삽입에 실패했습니다.")

        # 제품 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products_logistics (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_id INT NOT NULL,
                model_name VARCHAR(200) NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL DEFAULT 0,
                moq INT NOT NULL DEFAULT 1,
                lead_time INT NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 재고 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_logistics (
                inventory_id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                stock INT NOT NULL DEFAULT 0,
                is_certified BOOLEAN NOT NULL DEFAULT TRUE,
                certificate_number VARCHAR(100),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products_logistics(product_id),
                UNIQUE KEY unique_product (product_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 재고 입출고/폐기 이력 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                transaction_id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                change_type ENUM('입고', '출고', '폐기') NOT NULL,
                quantity INT NOT NULL,
                date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                certificate_number VARCHAR(100),
                destination VARCHAR(200),
                notes TEXT,
                reference_number VARCHAR(50),
                FOREIGN KEY (product_id) REFERENCES products_logistics(product_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Proforma Invoice 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proforma_invoices (
                pi_id INT AUTO_INCREMENT PRIMARY KEY,
                pi_number VARCHAR(50) NOT NULL UNIQUE,
                supplier_id INT NOT NULL,
                issue_date DATE NOT NULL,
                expected_delivery_date DATE,
                total_amount DECIMAL(15, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                payment_terms TEXT,
                shipping_terms TEXT,
                project_name VARCHAR(255),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # PI 항목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pi_items (
                pi_item_id INT AUTO_INCREMENT PRIMARY KEY,
                pi_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_price DECIMAL(15, 2) NOT NULL,
                expected_production_date DATE,
                status ENUM('pending', 'partial', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
                delay_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (pi_id) REFERENCES proforma_invoices(pi_id),
                FOREIGN KEY (product_id) REFERENCES products_logistics(product_id),
                UNIQUE KEY unique_product_pi (pi_id, product_id),
                CHECK (quantity > 0)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # --- 기존 테이블 마이그레이션 ---
        cursor.execute("SHOW TABLES LIKE 'pi_items'")
        if cursor.fetchone():
            # 1. status 컬럼 타입 변경
            cursor.execute("""
                ALTER TABLE pi_items 
                MODIFY COLUMN status ENUM('pending', 'partial', 'completed', 'cancelled') 
                NOT NULL DEFAULT 'pending'
            """)
            
            # 2. unique_product_pi 제약조건 추가
            try:
                cursor.execute("""
                    ALTER TABLE pi_items 
                    ADD CONSTRAINT unique_product_pi 
                    UNIQUE (pi_id, product_id)
                """)
            except mysql.connector.Error as err:
                if err.errno == 1061:  # Duplicate key name
                    pass  # 이미 제약조건이 존재하는 경우
                else:
                    raise
            
            # 3. quantity 체크 제약조건 추가
            try:
                cursor.execute("""
                    ALTER TABLE pi_items 
                    ADD CONSTRAINT check_quantity 
                    CHECK (quantity > 0)
                """)
            except mysql.connector.Error as err:
                if err.errno in (3819, 3822):  # Check constraint already exists, Duplicate check constraint name
                    pass  # 이미 제약조건이 존재하는 경우
                else:
                    raise

        # Commercial Invoice 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commercial_invoices (
                ci_id INT AUTO_INCREMENT PRIMARY KEY,
                ci_number VARCHAR(50) NOT NULL UNIQUE,
                pi_id INT,
                supplier_id INT NOT NULL,
                shipping_date DATE NOT NULL,
                arrival_date DATE,
                total_amount DECIMAL(15, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                shipping_details TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (pi_id) REFERENCES proforma_invoices(pi_id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # CI 항목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ci_items (
                ci_item_id INT AUTO_INCREMENT PRIMARY KEY,
                ci_id INT NOT NULL,
                pi_item_id INT,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_price DECIMAL(15, 2) NOT NULL,
                shipping_date DATE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (ci_id) REFERENCES commercial_invoices(ci_id),
                FOREIGN KEY (pi_item_id) REFERENCES pi_items(pi_item_id),
                FOREIGN KEY (product_id) REFERENCES products_logistics(product_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 배송 추적 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shipment_tracking (
                tracking_id INT AUTO_INCREMENT PRIMARY KEY,
                ci_id INT NOT NULL,
                tracking_number VARCHAR(100) NOT NULL,
                carrier VARCHAR(100) NOT NULL,
                shipping_date DATE NOT NULL,
                estimated_arrival_date DATE,
                actual_arrival_date DATE,
                status VARCHAR(20) NOT NULL DEFAULT 'preparing',
                current_location TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (ci_id) REFERENCES commercial_invoices(ci_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # --- 기존 테이블의 문자셋 변경 ---
        tables = [
            'suppliers', 'products_logistics', 'inventory_logistics', 
            'inventory_transactions', 'proforma_invoices', 'pi_items',
            'commercial_invoices', 'ci_items', 'shipment_tracking'
        ]
        for table in tables:
            cursor.execute(f"""
                ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

        conn.commit()
        return True, "물류 관련 테이블이 성공적으로 생성/업데이트되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def create_mcp_analysis_table():
    """MCP 분석 결과 테이블 생성/수정"""
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        if not conn:
            return False
        cursor = conn.cursor()
        
        # 테이블이 존재하는지 확인
        cursor.execute("SHOW TABLES LIKE 'mcp_analysis_results'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # 테이블이 없는 경우 새로 생성
            cursor.execute("""
                CREATE TABLE mcp_analysis_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    query LONGTEXT NOT NULL,
                    title VARCHAR(255),
                    analysis_result JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
        else:
            # 테이블이 있는 경우 query 컬럼 타입 변경 및 title 컬럼 확인
            cursor.execute("""
                ALTER TABLE mcp_analysis_results 
                MODIFY COLUMN query LONGTEXT NOT NULL
            """)
            
            # title 컬럼이 있는지 확인
            cursor.execute("SHOW COLUMNS FROM mcp_analysis_results LIKE 'title'")
            title_exists = cursor.fetchone() is not None
            
            if not title_exists:
                # title 컬럼이 없는 경우에만 추가
                cursor.execute("""
                    ALTER TABLE mcp_analysis_results 
                    ADD COLUMN title VARCHAR(255) AFTER query
                """)
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"테이블 생성/수정 중 오류가 발생했습니다: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_decision_tree_tables():
    """비즈니스 의사결정 트리 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS decision_outcomes")
        cursor.execute("DROP TABLE IF EXISTS decision_options")
        cursor.execute("DROP TABLE IF EXISTS decision_nodes")
        cursor.execute("DROP TABLE IF EXISTS decision_trees")
        
        # 의사결정 트리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_trees (
                tree_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                discount_rate DECIMAL(5,2),
                analysis_period INT,
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
                market_size DECIMAL(20,2),
                market_growth DECIMAL(5,2),
                competition_level INT,
                risk_level INT,
                expected_value DECIMAL(15,2),
                optimal_choice VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tree_id) REFERENCES decision_trees(tree_id) ON DELETE CASCADE,
                FOREIGN KEY (parent_id) REFERENCES decision_nodes(node_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 선택지/시나리오 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_options (
                option_id INT AUTO_INCREMENT PRIMARY KEY,
                decision_node_id INT NOT NULL,
                option_name VARCHAR(255) NOT NULL,
                initial_investment DECIMAL(15,2),
                operating_cost DECIMAL(15,2),
                expected_revenue DECIMAL(15,2),
                market_share DECIMAL(5,2),
                probability DECIMAL(5,2),
                revenue_impact DECIMAL(8,2),
                npv DECIMAL(15,2),
                roi DECIMAL(10,2),
                payback_period DECIMAL(10,2),
                path_probability DECIMAL(5,2),
                path_value DECIMAL(15,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (decision_node_id) REFERENCES decision_nodes(node_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 결과 노드 상세 정보 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                outcome_id INT AUTO_INCREMENT PRIMARY KEY,
                decision_node_id INT NOT NULL,
                final_revenue DECIMAL(15,2),
                cumulative_profit DECIMAL(15,2),
                final_market_share DECIMAL(5,2),
                market_position VARCHAR(20),
                success_rate DECIMAL(5,2),
                strategic_fit INT,
                growth_potential INT,
                competitive_advantage TEXT,
                risk_factors TEXT,
                risk_description TEXT,
                implications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (decision_node_id) REFERENCES decision_nodes(node_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        st.success("✅ 비즈니스 의사결정 트리 테이블이 생성되었습니다!")
        
        # Show the created table structures
        st.write("### 생성된 테이블 구조:")
        
        tables = ["decision_trees", "decision_nodes", "decision_options", "decision_outcomes"]
        for table in tables:
            st.write(f"#### {table} 테이블")
            schema = get_table_schema(table)
            if schema:
                schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                st.dataframe(schema_df)
        
        return True
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def drop_decision_tree_tables():
    """의사결정 트리 테이블 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 외래 키 제약 조건으로 인해 역순으로 삭제
        cursor.execute("DROP TABLE IF EXISTS decision_outcomes")
        cursor.execute("DROP TABLE IF EXISTS decision_options")
        cursor.execute("DROP TABLE IF EXISTS decision_nodes")
        cursor.execute("DROP TABLE IF EXISTS decision_trees")
        
        conn.commit()
        st.success("✅ 의사결정 트리 테이블이 삭제되었습니다.")
        return True
        
    except Exception as e:
        st.error(f"테이블 삭제 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def create_meeting_records_table(mode="migrate"):
    """회의록 테이블 생성/업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        if mode == "reset":
            # 기존 테이블 삭제 후 새로 생성
            cursor.execute("DROP TABLE IF EXISTS meeting_records")
            
            # 새 테이블 생성
            cursor.execute("""
                CREATE TABLE meeting_records (
                    meeting_id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    date DATETIME NOT NULL,
                    participants TEXT,
                    audio_path VARCHAR(255),
                    full_text LONGTEXT,
                    summary LONGTEXT,
                    action_items TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
        else:
            # 기존 테이블이 있는지 확인
            cursor.execute("SHOW TABLES LIKE 'meeting_records'")
            if cursor.fetchone():
                # 기존 테이블의 컬럼 타입 변경
                cursor.execute("""
                    ALTER TABLE meeting_records 
                    MODIFY COLUMN full_text LONGTEXT,
                    MODIFY COLUMN summary LONGTEXT
                """)
            else:
                # 테이블이 없는 경우 새로 생성
                cursor.execute("""
                    CREATE TABLE meeting_records (
                        meeting_id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        date DATETIME NOT NULL,
                        participants TEXT,
                        audio_path VARCHAR(255),
                        full_text LONGTEXT,
                        summary LONGTEXT,
                        action_items TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """)
        
        conn.commit()
        return True, "회의록 테이블이 성공적으로 생성/업데이트되었습니다."
        
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("DB 테이블 관리 시스템")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["테이블 목록", "테이블 생성/수정", "테이블 삭제", "데이터 조회", 
         "Rayleigh Skylights 테이블 생성", "자기소개서 테이블 생성", 
         "TOC 분석 테이블 생성", "기업 가치 평가 테이블 생성", 
         "주관식 질문 관련 테이블 생성", "물류 관리(PI/CI) 테이블 생성", 
         "MCP 분석 테이블 생성", "의사결정 트리 테이블 생성",
         "회의록 테이블 생성/업데이트",
         "decision_options 컬럼 추가(데이터 보호)"]
    )
    
    if menu == "테이블 목록":
        st.header("현재 테이블 목록")
        tables = get_existing_tables()
        if tables:
            st.write(tables)
        else:
            st.info("테이블이 없습니다.")
    
    elif menu == "테이블 생성/수정":
        st.header("테이블 생성/수정")
        
        # 테이블 이름 입력
        table_name = st.text_input("테이블 이름", help="생성할 테이블의 이름을 입력하세요.")
        
        if table_name:
            # 생성/수정 모드 선택
            mode = st.radio(
                "테이블 작업 방식 선택",
                ["구조만 업데이트(기존 데이터 유지)", "테이블 새로 생성(기존 데이터 삭제)"],
                index=0
            )
            mode_value = "migrate" if mode == "구조만 업데이트(기존 데이터 유지)" else "reset"
            # 컬럼 정의
            st.subheader("컬럼 정의")
            num_columns = st.number_input("컬럼 수", min_value=1, value=1)
            
            columns = []
            unique_keys = []
            
            for i in range(int(num_columns)):
                st.write(f"#### 컬럼 {i+1}")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    name = st.text_input(f"컬럼 이름", key=f"col_name_{i}")
                with col2:
                    type_options = ["VARCHAR(100)", "TEXT", "INT", "DECIMAL(10,2)", "DATE", "TIMESTAMP"]
                    col_type = st.selectbox(f"데이터 타입", type_options, key=f"col_type_{i}")
                with col3:
                    not_null = st.checkbox("NOT NULL", key=f"col_notnull_{i}")
                    primary_key = st.checkbox("Primary Key", key=f"col_pk_{i}")
                    auto_increment = st.checkbox("Auto Increment", key=f"col_auto_{i}")
                
                if name and col_type:
                    column = {
                        "name": name,
                        "type": col_type,
                        "not_null": not_null,
                        "primary_key": primary_key,
                        "auto_increment": auto_increment
                    }
                    columns.append(column)
                
                # Unique Key 설정
                is_unique = st.checkbox(f"Unique Key로 설정", key=f"col_unique_{i}")
                if is_unique:
                    unique_key_name = f"uk_{name}"
                    unique_keys.append({
                        "name": unique_key_name,
                        "columns": name
                    })
            
            if st.button("테이블 생성/수정", type="primary"):
                if create_or_modify_table(table_name, columns, unique_keys, mode=mode_value):
                    st.success(f"테이블 '{table_name}'이(가) 성공적으로 생성/수정되었습니다!")
                    # 테이블 구조 확인
                    st.write("### 생성된 테이블 구조:")
                    schema = get_table_schema(table_name)
                    if schema:
                        schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                        st.dataframe(schema_df)
    
    elif menu == "테이블 삭제":
        st.header("테이블 삭제")
        tables = get_existing_tables()
        
        if not tables:
            st.info("삭제할 테이블이 없습니다.")
        else:
            table_to_delete = st.selectbox("삭제할 테이블 선택", tables)
            
            if st.button("테이블 삭제", type="primary"):
                if delete_table(table_to_delete):
                    st.success(f"테이블 '{table_to_delete}'이(가) 성공적으로 삭제되었습니다!")
                    time.sleep(1)
                    st.rerun()
    
    elif menu == "데이터 조회":
        st.header("테이블 데이터 조회")
        tables = get_existing_tables()
        
        if not tables:
            st.info("조회할 테이블이 없습니다.")
        else:
            selected_table = st.selectbox("조회할 테이블 선택", tables)
            
            # 검색 기능
            search_term = st.text_input("검색어 입력 (모든 컬럼에서 검색)")
            
            if selected_table:
                df = get_table_data(selected_table, search_term)
                if not df.empty:
                    st.write(f"### {selected_table} 테이블 데이터")
                    st.dataframe(df)
                    
                    # CSV 다운로드 버튼
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        "CSV 다운로드",
                        csv,
                        f"{selected_table}_data.csv",
                        "text/csv",
                        key='download-csv'
                    )
                else:
                    st.info("데이터가 없거나 검색 결과가 없습니다.")
    
    elif menu == "Rayleigh Skylights 테이블 생성":
        st.header("Rayleigh Skylights 테이블 생성")
        if st.button("Rayleigh Skylights 테이블 생성"):
            if create_rayleigh_skylights_tables():
                st.success("Rayleigh Skylights 관련 테이블이 성공적으로 생성되었습니다.")
            else:
                st.error("테이블 생성 중 오류가 발생했습니다.")
    
    elif menu == "자기소개서 테이블 생성":
        st.header("자기소개서 테이블 생성")
        if st.button("자기소개서 테이블 생성"):
            if create_self_introduction_table():
                st.success("자기소개서 테이블이 성공적으로 생성되었습니다.")
            else:
                st.error("테이블 생성 중 오류가 발생했습니다.")
    
    elif menu == "TOC 분석 테이블 생성":
        st.header("TOC 분석 테이블 생성")
        if st.button("TOC 분석 테이블 생성"):
            if create_toc_analysis_tables():
                st.success("TOC 분석 관련 테이블이 성공적으로 생성되었습니다.")
                
                # 생성된 테이블 구조 표시
                st.write("### 생성된 테이블 구조:")
                
                # toc_analyses 테이블 구조
                st.write("#### TOC 분석 테이블 (toc_analyses)")
                schema = get_table_schema("toc_analyses")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # toc_analysis_relationships 테이블 구조
                st.write("#### TOC 분석 관계 테이블 (toc_analysis_relationships)")
                schema = get_table_schema("toc_analysis_relationships")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # toc_model_relationships 테이블 구조
                st.write("#### TOC 모델 관계 테이블 (toc_model_relationships)")
                schema = get_table_schema("toc_model_relationships")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
            else:
                st.error("테이블 생성 중 오류가 발생했습니다.")
    
    elif menu == "기업 가치 평가 테이블 생성":
        st.header("기업 가치 평가 테이블 생성")
        if st.button("기업 가치 평가 테이블 생성"):
            if create_valuation_tables():
                st.success("기업 가치 평가 관련 테이블이 성공적으로 생성되었습니다.")
                
                # 생성된 테이블 구조 표시
                st.write("### 생성된 테이블 구조:")
                
                # valuation_analyses 테이블 구조
                st.write("#### 기업 가치 평가 분석 테이블 (valuation_analyses)")
                schema = get_table_schema("valuation_analyses")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # valuation_financial_data 테이블 구조
                st.write("#### 재무 데이터 테이블 (valuation_financial_data)")
                schema = get_table_schema("valuation_financial_data")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # valuation_market_data 테이블 구조
                st.write("#### 시장 데이터 테이블 (valuation_market_data)")
                schema = get_table_schema("valuation_market_data")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # valuation_agent_analyses 테이블 구조
                st.write("#### AI 에이전트 분석 결과 테이블 (valuation_agent_analyses)")
                schema = get_table_schema("valuation_agent_analyses")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # valuation_results 테이블 구조
                st.write("#### 가치 평가 결과 테이블 (valuation_results)")
                schema = get_table_schema("valuation_results")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
            else:
                st.error("테이블 생성 중 오류가 발생했습니다.")
    
    elif menu == "주관식 질문 관련 테이블 생성":
        st.header("주관식 질문 관련 테이블 생성")
        if st.button("주관식 질문 관련 테이블 생성"):
            success = create_subjective_tables()
            if success:
                st.success("주관식 질문 관련 테이블이 성공적으로 생성되었습니다!")
                
                # Show the created table structures
                st.write("### 생성된 테이블 구조:")
                
                # Show subjective_questions table structure
                st.write("#### 주관식 질문 테이블 (subjective_questions)")
                schema = get_table_schema("subjective_questions")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
                
                # Show subjective_responses table structure
                st.write("#### 주관식 응답 테이블 (subjective_responses)")
                schema = get_table_schema("subjective_responses")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)

    elif menu == "물류 관리(PI/CI) 테이블 생성":
        st.header("물류 관리(PI/CI) 테이블 생성")
        # --- 새 옵션: 테이블 생성 방식 선택 ---
        mode = st.radio(
            "테이블 작업 방식 선택",
            ["구조만 업데이트(마이그레이션)", "테이블 새로 생성(기존 데이터 삭제)"],
            index=0
        )
        if st.button("물류 관리 테이블 생성/업데이트"):
            success, message = create_logistics_tables(
                mode="reset" if mode == "테이블 새로 생성(기존 데이터 삭제)" else "migrate"
            )
            if success:
                st.success("물류 관리 관련 테이블이 성공적으로 생성/업데이트되었습니다.")
                # 생성된 테이블 구조 표시
                tables = ["suppliers", "products_logistics", "inventory_logistics", "inventory_transactions", "proforma_invoices", 
                         "pi_items", "commercial_invoices", "ci_items", "shipment_tracking"]
                st.write("### 생성된 테이블 구조:")
                for table in tables:
                    st.write(f"#### {table} 테이블")
                    schema = get_table_schema(table)
                    if schema:
                        schema_df = pd.DataFrame(schema, 
                            columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                        st.dataframe(schema_df)
            else:
                st.error(f"테이블 생성/업데이트 중 오류가 발생했습니다: {message}")

    elif menu == "MCP 분석 테이블 생성":
        st.header("MCP 분석 테이블 생성")
        
        # 테이블 작업 방식 선택
        mode = st.radio(
            "테이블 작업 방식 선택",
            ["구조만 업데이트(기존 데이터 유지)", "테이블 새로 생성(기존 데이터 삭제)"],
            index=0
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("MCP 분석 테이블 생성/수정", type="primary"):
                if mode == "테이블 새로 생성(기존 데이터 삭제)":
                    # 기존 테이블 삭제 후 새로 생성
                    try:
                        conn = connect_to_db()
                        if not conn:
                            st.error("데이터베이스 연결에 실패했습니다.")
                            return
                        cursor = conn.cursor()
                        cursor.execute("DROP TABLE IF EXISTS mcp_analysis_results")
                        cursor.execute("""
                            CREATE TABLE mcp_analysis_results (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                query LONGTEXT NOT NULL,
                                title VARCHAR(255),
                                analysis_result JSON NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                        """)
                        conn.commit()
                        st.success("✅ MCP 분석 테이블이 새로 생성되었습니다!")
                    except Exception as e:
                        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
                    finally:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
                else:
                    # 기존 데이터 유지하면서 구조만 업데이트
                    if create_mcp_analysis_table():
                        st.success("✅ MCP 분석 테이블이 성공적으로 업데이트되었습니다!")
                    else:
                        st.error("테이블 업데이트에 실패했습니다.")
        
        with col2:
            if st.button("MCP 분석 테이블 삭제", type="secondary"):
                try:
                    conn = connect_to_db()
                    if not conn:
                        st.error("데이터베이스 연결에 실패했습니다.")
                        return
                    cursor = conn.cursor()
                    cursor.execute("DROP TABLE IF EXISTS mcp_analysis_results")
                    conn.commit()
                    st.success("✅ MCP 분석 테이블이 삭제되었습니다!")
                except Exception as e:
                    st.error(f"테이블 삭제 중 오류가 발생했습니다: {str(e)}")
                finally:
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()

    elif menu == "의사결정 트리 테이블 생성":
        st.header("의사결정 트리 테이블 생성")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("의사결정 트리 테이블 생성", type="primary"):
                create_decision_tree_tables()
        
        with col2:
            if st.button("의사결정 트리 테이블 삭제", type="secondary"):
                drop_decision_tree_tables()
        # --- decision_options decision_node_id NULL 허용 기능 ---
        st.markdown("---")
        st.subheader("decision_options 테이블의 decision_node_id 컬럼 NULL 허용/DEFAULT NULL로 변경")
        if st.button("decision_options decision_node_id NULL 허용", type="primary"):
            try:
                conn = connect_to_db()
                cursor = conn.cursor()
                # decision_options 테이블 존재 여부 확인
                cursor.execute("SHOW TABLES LIKE 'decision_options'")
                if cursor.fetchone():
                    # decision_node_id 컬럼 존재 여부 확인
                    cursor.execute("SHOW COLUMNS FROM decision_options LIKE 'decision_node_id'")
                    if cursor.fetchone():
                        cursor.execute("ALTER TABLE decision_options MODIFY COLUMN decision_node_id INT NULL DEFAULT NULL")
                        conn.commit()
                        st.success("decision_node_id 컬럼이 NULL 허용 및 DEFAULT NULL로 변경되었습니다.")
                    else:
                        st.warning("decision_node_id 컬럼이 존재하지 않습니다.")
                else:
                    st.warning("decision_options 테이블이 존재하지 않습니다.")
                # 변경 후 테이블 구조 표시
                schema = get_table_schema("decision_options")
                if schema:
                    import pandas as pd
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.write("### decision_options 테이블 구조:")
                    st.dataframe(schema_df)
                cursor.close()
                conn.close()
            except Exception as e:
                st.error(f"컬럼 변경 중 오류: {str(e)}")

    elif menu == "회의록 테이블 생성/업데이트":
        st.header("회의록 테이블 생성/업데이트")
        # 테이블 작업 방식 선택
        mode = st.radio(
            "테이블 작업 방식 선택",
            ["구조만 업데이트(기존 데이터 유지)", "테이블 새로 생성(기존 데이터 삭제)"],
            index=0
        )
        if st.button("회의록 테이블 생성/업데이트"):
            success, message = create_meeting_records_table(
                mode="reset" if mode == "테이블 새로 생성(기존 데이터 삭제)" else "migrate"
            )
            if success:
                st.success(message)
                # 생성된 테이블 구조 표시
                st.write("### 생성된 테이블 구조:")
                schema = get_table_schema("meeting_records")
                if schema:
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.dataframe(schema_df)
            else:
                st.error(f"테이블 생성/업데이트 중 오류가 발생했습니다: {message}")

    elif menu == "decision_options 컬럼 추가(데이터 보호)":
        st.header("decision_options 테이블에 분석용 컬럼 추가 (데이터 보호)")
        st.write("이 기능은 기존 데이터를 삭제하지 않고, 필요한 컬럼만 안전하게 추가합니다.")
        if st.button("컬럼 추가/수정 실행", type="primary"):
            try:
                conn = connect_to_db()
                cursor = conn.cursor()
                # 각 컬럼 존재 여부 확인 후 없으면 추가
                alter_sqls = [
                    ("advantages", "TEXT"),
                    ("disadvantages", "TEXT"),
                    ("estimated_duration", "VARCHAR(255)"),
                    ("priority", "INT"),
                    ("additional_info", "TEXT")
                ]
                added = []
                for col, coltype in alter_sqls:
                    cursor.execute(f"SHOW COLUMNS FROM decision_options LIKE '{col}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE decision_options ADD COLUMN {col} {coltype}")
                        added.append(col)
                conn.commit()
                if added:
                    st.success(f"다음 컬럼이 추가되었습니다: {', '.join(added)}")
                else:
                    st.info("모든 컬럼이 이미 존재합니다. 변경 없음.")
                # 변경 후 테이블 구조 표시
                schema = get_table_schema("decision_options")
                if schema:
                    import pandas as pd
                    schema_df = pd.DataFrame(schema, columns=['Field', 'Type', 'Null', 'Key', 'Default', 'Extra'])
                    st.write("### decision_options 테이블 구조:")
                    st.dataframe(schema_df)
                cursor.close()
                conn.close()
            except Exception as e:
                st.error(f"컬럼 추가/수정 중 오류: {str(e)}")

if __name__ == "__main__":
    main() 