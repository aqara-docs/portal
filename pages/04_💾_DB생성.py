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

def create_or_modify_table(table_name, columns, unique_keys):
    """테이블 생성 또는 수정"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 기존 테이블 삭제
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # 새 테이블 생성
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
        
        # 유니크 키 추가
        for key in unique_keys:
            column_defs.append(f"UNIQUE KEY {key['name']} ({key['columns']})")
        
        create_table_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
        cursor.execute(create_table_sql)
        
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
        
        if search_term:
            # 모든 컬럼에 대해 검색
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            columns = [col[0] for col in cursor.fetchall()]
            search_conditions = [f"{col} LIKE %s" for col in columns]
            query = f"SELECT * FROM {table_name} WHERE {' OR '.join(search_conditions)}"
            cursor.execute(query, [f"%{search_term}%"] * len(columns))
        else:
            cursor.execute(f"SELECT * FROM {table_name}")
        
        data = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        
        return pd.DataFrame(data, columns=columns)
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

def main():
    st.title("DB 테이블 관리 시스템")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["테이블 목록", "테이블 생성/수정", "테이블 삭제", "데이터 조회", "Rayleigh Skylights 테이블 생성"]
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
        # 테이블 생성/수정 폼 구현
        # ...
    
    elif menu == "테이블 삭제":
        st.header("테이블 삭제")
        # 테이블 삭제 폼 구현
        # ...
    
    elif menu == "데이터 조회":
        st.header("테이블 데이터 조회")
        # 데이터 조회 폼 구현
        # ...
    
    elif menu == "Rayleigh Skylights 테이블 생성":
        st.header("Rayleigh Skylights 테이블 생성")
        if st.button("Rayleigh Skylights 테이블 생성"):
            if create_rayleigh_skylights_tables():
                st.success("Rayleigh Skylights 관련 테이블이 성공적으로 생성되었습니다.")
            else:
                st.error("테이블 생성 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main() 