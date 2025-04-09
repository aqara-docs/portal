import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sqlite3
from sqlite3 import Connection

# 데이터베이스 설정
def get_connection() -> Connection:
    """SQLite 데이터베이스 연결 생성"""
    if not os.path.exists("./data"):
        os.mkdir("./data")
    conn = sqlite3.connect("./data/joint_venture.db", check_same_thread=False)
    return conn

def init_db(conn: Connection):
    """데이터베이스 테이블 초기화"""
    cursor = conn.cursor()
    
    # 부품 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_code TEXT NOT NULL,
        part_name TEXT NOT NULL,
        supplier TEXT DEFAULT 'YUER',
        unit_price REAL NOT NULL,
        lead_time INTEGER NOT NULL,
        stock INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 10,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 주문 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT NOT NULL,
        order_date TIMESTAMP NOT NULL,
        expected_arrival TIMESTAMP,
        status TEXT DEFAULT 'Pending',
        total_amount REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 주문 상세 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        part_id INTEGER,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (part_id) REFERENCES parts (id)
    )
    ''')
    
    # 제품 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        product_name TEXT NOT NULL,
        brand TEXT DEFAULT 'Korean Brand',
        selling_price REAL NOT NULL,
        production_cost REAL,
        stock INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 생산 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT NOT NULL,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        status TEXT DEFAULT 'Planned',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    # 자재 소요량 테이블 (BOM)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bill_of_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        part_id INTEGER,
        quantity INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (part_id) REFERENCES parts (id)
    )
    ''')
    
    # 판매 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT NOT NULL,
        sale_date TIMESTAMP NOT NULL,
        customer TEXT,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_amount REAL,
        status TEXT DEFAULT 'Completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    conn.commit()

# 샘플 데이터 생성
def create_sample_data(conn: Connection):
    """샘플 데이터 추가"""
    cursor = conn.cursor()
    
    # 이미 데이터가 있는지 확인
    cursor.execute("SELECT COUNT(*) FROM parts")
    if cursor.fetchone()[0] > 0:
        return
    
    # 부품 데이터
    parts_data = [
        ('P001', 'Acrylic Dome', 120.5, 14, 50, 10),
        ('P002', 'Light Tube Assembly', 85.3, 10, 100, 20),
        ('P003', 'Flashing Kit', 45.0, 7, 80, 15),
        ('P004', 'Aluminum Frame', 150.2, 21, 30, 5),
        ('P005', 'Sealant Kit', 25.5, 5, 150, 30),
    ]
    
    for part in parts_data:
        cursor.execute(
            "INSERT INTO parts (part_code, part_name, unit_price, lead_time, stock, min_stock) VALUES (?, ?, ?, ?, ?, ?)",
            part
        )
    
    # 제품 데이터
    products_data = [
        ('SK001', 'Standard Skylight 60cm', 450.0, 280.0),
        ('SK002', 'Premium Skylight 90cm', 750.0, 480.0),
        ('SK003', 'Deluxe Skylight 120cm', 1200.0, 780.0),
        ('SK004', 'Ventilated Skylight 60cm', 580.0, 350.0),
        ('SK005', 'Solar Powered Skylight 90cm', 1500.0, 950.0),
    ]
    
    for product in products_data:
        cursor.execute(
            "INSERT INTO products (product_code, product_name, selling_price, production_cost) VALUES (?, ?, ?, ?)",
            product
        )
    
    # BOM 데이터
    # 각 제품에 필요한 부품과 수량 (제품ID, 부품ID, 수량)
    bom_data = [
        (1, 1, 1), (1, 2, 1), (1, 3, 1), (1, 5, 2),
        (2, 1, 1), (2, 2, 2), (2, 3, 1), (2, 4, 1), (2, 5, 3),
        (3, 1, 2), (3, 2, 2), (3, 3, 2), (3, 4, 2), (3, 5, 4),
        (4, 1, 1), (4, 2, 1), (4, 3, 1), (4, 4, 1), (4, 5, 2),
        (5, 1, 1), (5, 2, 2), (5, 3, 1), (5, 4, 1), (5, 5, 3),
    ]
    
    for bom in bom_data:
        cursor.execute(
            "INSERT INTO bill_of_materials (product_id, part_id, quantity) VALUES (?, ?, ?)",
            bom
        )
    
    # 주문 및 판매 데이터 생성
    # 현재 날짜로부터 60일 전 ~ 현재까지의 주문 생성
    current_date = datetime.now()
    
    # 주문 데이터
    for i in range(1, 11):
        order_date = current_date - timedelta(days=np.random.randint(1, 60))
        expected_arrival = order_date + timedelta(days=np.random.randint(7, 30))
        
        status_options = ['Pending', 'Shipped', 'Delivered', 'Cancelled']
        status_weights = [0.2, 0.3, 0.4, 0.1]
        status = np.random.choice(status_options, p=status_weights)
        
        # 금액은 나중에 계산
        cursor.execute(
            "INSERT INTO orders (order_number, order_date, expected_arrival, status) VALUES (?, ?, ?, ?)",
            (f'ORD-2023-{i:03d}', order_date, expected_arrival, status)
        )
        
        order_id = cursor.lastrowid
        
        # 주문 상세 - 몇 개의 부품을 랜덤하게 선택
        num_parts = np.random.randint(1, 4)
        part_ids = np.random.choice(range(1, 6), size=num_parts, replace=False)
        
        total_amount = 0
        for part_id in part_ids:
            quantity = np.random.randint(10, 101)
            
            # 부품 가격 조회
            cursor.execute("SELECT unit_price FROM parts WHERE id = ?", (part_id,))
            unit_price = cursor.fetchone()[0]
            
            cursor.execute(
                "INSERT INTO order_details (order_id, part_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, part_id, quantity, unit_price)
            )
            
            total_amount += quantity * unit_price
        
        # 주문 총액 업데이트
        cursor.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (total_amount, order_id)
        )
    
    # 생산 데이터
    for i in range(1, 16):
        product_id = np.random.randint(1, 6)
        quantity = np.random.randint(5, 51)
        
        start_date = current_date - timedelta(days=np.random.randint(1, 45))
        end_date = start_date + timedelta(days=np.random.randint(1, 10))
        
        status_options = ['Planned', 'In Progress', 'Completed', 'Delayed']
        status_weights = [0.2, 0.3, 0.4, 0.1]
        status = np.random.choice(status_options, p=status_weights)
        
        cursor.execute(
            "INSERT INTO production (batch_number, product_id, quantity, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
            (f'BATCH-2023-{i:03d}', product_id, quantity, start_date, end_date, status)
        )
    
    # 판매 데이터
    for i in range(1, 31):
        product_id = np.random.randint(1, 6)
        quantity = np.random.randint(1, 11)
        
        # 제품 가격 조회
        cursor.execute("SELECT selling_price FROM products WHERE id = ?", (product_id,))
        unit_price = cursor.fetchone()[0]
        
        sale_date = current_date - timedelta(days=np.random.randint(1, 50))
        
        customer_list = ['가구나라', '홈플러스', '롯데하이마트', '이케아코리아', '한샘', '까사미아', 
                         '현대백화점', '신세계백화점', '롯데백화점', '온라인 쇼핑몰']
        customer = np.random.choice(customer_list)
        
        cursor.execute(
            "INSERT INTO sales (invoice_number, sale_date, customer, product_id, quantity, unit_price, total_amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f'INV-2023-{i:03d}', sale_date, customer, product_id, quantity, unit_price, quantity * unit_price)
        )
    
    conn.commit()

# 앱 레이아웃 및 기능
def main():
    st.set_page_config(
        page_title="YUER-한국 조인트벤처 관리 시스템",
        page_icon="🏭",
        layout="wide"
    )
    
    # 데이터베이스 초기화
    conn = get_connection()
    init_db(conn)
    create_sample_data(conn)
    
    # 사이드바 메뉴
    st.sidebar.title("YUER-한국 조인트벤처")
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["대시보드", "부품 관리", "부품 주문", "생산 관리", "제품 관리", "판매 분석", "재고 관리", "설정"]
    )
    
    # 메뉴별 페이지 렌더링
    if menu == "대시보드":
        display_dashboard(conn)
    elif menu == "부품 관리":
        display_parts_management(conn)
    elif menu == "부품 주문":
        display_orders_management(conn)
    elif menu == "생산 관리":
        display_production_management(conn)
    elif menu == "제품 관리":
        display_products_management(conn)
    elif menu == "판매 분석":
        display_sales_analysis(conn)
    elif menu == "재고 관리":
        display_inventory_management(conn)
    elif menu == "설정":
        display_settings(conn)
    
    # 데이터베이스 연결 종료
    conn.close()

# 대시보드 페이지
def display_dashboard(conn):
    st.title("조인트벤처 대시보드")
    
    # 주요 KPI를 상단에 표시
    col1, col2, col3, col4 = st.columns(4)
    
    # 총 부품 수입액
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(total_amount) FROM orders WHERE status != 'Cancelled'")
    total_import = cursor.fetchone()[0]
    if total_import is None:
        total_import = 0
    
    # 총 생산량
    cursor.execute("SELECT SUM(quantity) FROM production WHERE status = 'Completed'")
    total_production = cursor.fetchone()[0]
    if total_production is None:
        total_production = 0
    
    # 총 판매액
    cursor.execute("SELECT SUM(total_amount) FROM sales")
    total_sales = cursor.fetchone()[0]
    if total_sales is None:
        total_sales = 0
    
    # 부품 재고 부족 항목 수
    cursor.execute("SELECT COUNT(*) FROM parts WHERE stock < min_stock")
    low_stock_items = cursor.fetchone()[0]
    
    with col1:
        st.metric(label="총 부품 수입액", value=f"₩{total_import:,.0f}")
    
    with col2:
        st.metric(label="총 생산량", value=f"{total_production:,} 개")
    
    with col3:
        st.metric(label="총 판매액", value=f"₩{total_sales:,.0f}")
    
    with col4:
        st.metric(label="재고 부족 항목", value=f"{low_stock_items} 개")
    
    st.markdown("---")
    
    # 두 번째 행: 차트
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("월별 부품 수입 및 제품 판매 추이")
        
        # 월별 주문 데이터
        cursor.execute("""
        SELECT strftime('%Y-%m', order_date) as month, SUM(total_amount) as total
        FROM orders
        WHERE status != 'Cancelled'
        GROUP BY month
        ORDER BY month
        """)
        order_data = cursor.fetchall()
        
        # 월별 판매 데이터
        cursor.execute("""
        SELECT strftime('%Y-%m', sale_date) as month, SUM(total_amount) as total
        FROM sales
        GROUP BY month
        ORDER BY month
        """)
        sales_data = cursor.fetchall()
        
        # 데이터프레임으로 변환
        order_df = pd.DataFrame(order_data, columns=['month', 'total'])
        order_df['type'] = '부품 수입'
        
        sales_df = pd.DataFrame(sales_data, columns=['month', 'total'])
        sales_df['type'] = '제품 판매'
        
        # 데이터 결합
        combined_df = pd.concat([order_df, sales_df])
        
        if not combined_df.empty:
            fig = px.line(combined_df, x='month', y='total', color='type',
                        title='월별 부품 수입 및 제품 판매 추이',
                        labels={'month': '월', 'total': '금액 (₩)', 'type': '유형'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("데이터가 충분하지 않습니다.")
    
    with col2:
        st.subheader("제품별 판매 분포")
        
        # 제품별 판매 데이터
        cursor.execute("""
        SELECT p.product_name, SUM(s.quantity) as total_quantity
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.product_name
        ORDER BY total_quantity DESC
        """)
        product_sales = cursor.fetchall()
        
        if product_sales:
            product_sales_df = pd.DataFrame(product_sales, columns=['product_name', 'total_quantity'])
            fig = px.pie(product_sales_df, values='total_quantity', names='product_name',
                        title='제품별 판매 분포')
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("판매 데이터가 없습니다.")
    
    # 세 번째 행: 부품 재고 상황 및 생산 현황
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("부품 재고 상황")
        
        # 부품 재고 데이터
        cursor.execute("""
        SELECT part_name, stock, min_stock
        FROM parts
        ORDER BY (stock * 1.0 / min_stock) ASC
        """)
        part_stocks = cursor.fetchall()
        
        if part_stocks:
            part_stocks_df = pd.DataFrame(part_stocks, columns=['part_name', 'stock', 'min_stock'])
            
            # 수평 막대 그래프 생성
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=part_stocks_df['part_name'],
                x=part_stocks_df['stock'],
                orientation='h',
                name='현재 재고',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Bar(
                y=part_stocks_df['part_name'],
                x=part_stocks_df['min_stock'],
                orientation='h',
                name='최소 재고',
                marker_color='rgba(255, 0, 0, 0.5)',
                opacity=0.5
            ))
            
            fig.update_layout(
                title='부품별 재고 상황',
                xaxis_title='수량',
                yaxis_title='부품명',
                barmode='overlay'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("부품 데이터가 없습니다.")
    
    with col2:
        st.subheader("생산 현황")
        
        # 상태별 생산 데이터
        cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM production
        GROUP BY status
        """)
        production_status = cursor.fetchall()
        
        if production_status:
            production_status_df = pd.DataFrame(production_status, columns=['status', 'count'])
            
            colors = {
                'Planned': '#FFA15A',
                'In Progress': '#636EFA',
                'Completed': '#00CC96',
                'Delayed': '#EF553B'
            }
            
            fig = px.bar(production_status_df, x='status', y='count',
                        title='생산 상태별 배치 수',
                        labels={'status': '상태', 'count': '배치 수'},
                        color='status',
                        color_discrete_map=colors)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 최근 생산 배치 목록
            st.subheader("최근 생산 배치")
            
            cursor.execute("""
            SELECT p.batch_number, pr.product_name, p.quantity, p.status, p.start_date, p.end_date
            FROM production p
            JOIN products pr ON p.product_id = pr.id
            ORDER BY p.start_date DESC
            LIMIT 5
            """)
            recent_production = cursor.fetchall()
            
            if recent_production:
                recent_production_df = pd.DataFrame(recent_production, 
                                                   columns=['배치 번호', '제품명', '수량', '상태', '시작일', '종료일'])
                st.dataframe(recent_production_df, use_container_width=True)
            else:
                st.info("생산 데이터가 없습니다.")
        else:
            st.info("생산 데이터가 없습니다.")

# 부품 관리 페이지
def display_parts_management(conn):
    st.title("부품 관리")
    
    tab1, tab2 = st.tabs(["부품 목록", "부품 추가/수정"])
    
    with tab1:
        st.subheader("부품 목록")
        
        # 부품 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, part_code, part_name, supplier, unit_price, lead_time, stock, min_stock
        FROM parts
        ORDER BY part_code
        """)
        parts_data = cursor.fetchall()
        
        if parts_data:
            parts_df = pd.DataFrame(parts_data, 
                                  columns=['ID', '부품 코드', '부품명', '공급업체', '단가(₩)', '리드타임(일)', '현재 재고', '최소 재고'])
            
            # 재고 상태 계산
            parts_df['재고 상태'] = parts_df.apply(
                lambda row: '부족' if row['현재 재고'] < row['최소 재고'] else '정상', 
                axis=1
            )
            
            # 데이터프레임 표시
            st.dataframe(parts_df, use_container_width=True)
            
            # 부품별 재고 차트
            st.subheader("부품별 재고 상태")
            
            chart_data = parts_df[['부품명', '현재 재고', '최소 재고']]
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=chart_data['부품명'],
                y=chart_data['현재 재고'],
                name='현재 재고',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Scatter(
                x=chart_data['부품명'],
                y=chart_data['최소 재고'],
                name='최소 재고',
                mode='lines+markers',
                marker_color='red'
            ))
            
            fig.update_layout(
                title='부품별 재고 상태',
                xaxis_title='부품명',
                yaxis_title='수량'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("등록된 부품이 없습니다.")
    
    with tab2:
        st.subheader("부품 추가/수정")
        
        # 부품 추가 폼
        with st.form("part_form"):
            st.write("새 부품 등록")
            part_code = st.text_input("부품 코드")
            part_name = st.text_input("부품명")
            supplier = st.text_input("공급업체", value="YUER")
            unit_price = st.number_input("단가(₩)", min_value=0.0, step=0.1)
            lead_time = st.number_input("리드타임(일)", min_value=1, step=1)
            stock = st.number_input("현재 재고", min_value=0, step=1)
            min_stock = st.number_input("최소 재고", min_value=0, step=1)
            
            submitted = st.form_submit_button("부품 추가")
            
            if submitted:
                if not part_code or not part_name:
                    st.error("부품 코드와 부품명은 필수입니다.")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO parts (part_code, part_name, supplier, unit_price, lead_time, stock, min_stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (part_code, part_name, supplier, unit_price, lead_time, stock, min_stock)
                    )
                    conn.commit()
                    st.success(f"부품 '{part_name}' 추가 완료!")
        
        # 부품 수정 섹션
        st.markdown("---")
        st.write("부품 정보 수정")
        
        # 부품 목록 조회
        cursor = conn.cursor()
        cursor.execute("SELECT id, part_code, part_name FROM parts ORDER BY part_code")
        parts = cursor.fetchall()
        
        if parts:
            part_options = {f"{p[1]} - {p[2]}": p[0] for p in parts}
            selected_part = st.selectbox("수정할 부품 선택", list(part_options.keys()))
            
            part_id = part_options[selected_part]
            
            # 선택한 부품 정보 조회
            cursor.execute(
                "SELECT part_code, part_name, supplier, unit_price, lead_time, stock, min_stock FROM parts WHERE id = ?",
                (part_id,)
            )
            part_data = cursor.fetchone()
            
            if part_data:
                with st.form("edit_part_form"):
                    st.write(f"'{part_data[1]}' 정보 수정")
                    
                    edit_part_code = st.text_input("부품 코드", value=part_data[0])
                    edit_part_name = st.text_input("부품명", value=part_data[1])
                    edit_supplier = st.text_input("공급업체", value=part_data[2])
                    edit_unit_price = st.number_input("단가(₩)", min_value=0.0, step=0.1, value=float(part_data[3]))
                    edit_lead_time = st.number_input("리드타임(일)", min_value=1, step=1, value=int(part_data[4]))
                    edit_stock = st.number_input("현재 재고", min_value=0, step=1, value=int(part_data[5]))
                    edit_min_stock = st.number_input("최소 재고", min_value=0, step=1, value=int(part_data[6]))
                    
                    update_submitted = st.form_submit_button("정보 업데이트")
                    
                    if update_submitted:
                        cursor.execute(
                            "UPDATE parts SET part_code = ?, part_name = ?, supplier = ?, unit_price = ?, lead_time = ?, stock = ?, min_stock = ? WHERE id = ?",
                            (edit_part_code, edit_part_name, edit_supplier, edit_unit_price, edit_lead_time, edit_stock, edit_min_stock, part_id)
                        )
                        conn.commit()
                        st.success(f"부품 '{edit_part_name}' 정보 업데이트 완료!")
        else:
            st.info("등록된 부품이 없습니다.")

# 부품 주문 관리 페이지
def display_orders_management(conn):
    st.title("부품 주문 관리")
    
    tab1, tab2, tab3 = st.tabs(["주문 목록", "새 주문 생성", "주문 상태 관리"])
    
    with tab1:
        st.subheader("주문 목록")
        
        # 주문 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT o.id, o.order_number, o.order_date, o.expected_arrival, o.status, o.total_amount,
               COUNT(od.id) as item_count, SUM(od.quantity) as total_quantity
        FROM orders o
        LEFT JOIN order_details od ON o.id = od.order_id
        GROUP BY o.id
        ORDER BY o.order_date DESC
        """)
        orders_data = cursor.fetchall()
        
        if orders_data:
            orders_df = pd.DataFrame(orders_data, 
                                   columns=['ID', '주문번호', '주문일자', '예상도착일', '상태', '총액(₩)', '품목 수', '총 수량'])
            
            # 날짜 형식 변환
            orders_df['주문일자'] = pd.to_datetime(orders_df['주문일자']).dt.strftime('%Y-%m-%d')
            orders_df['예상도착일'] = pd.to_datetime(orders_df['예상도착일']).dt.strftime('%Y-%m-%d')
            
            # 상태별 색상 지정
            def highlight_status(val):
                if val == 'Delivered':
                    return 'background-color: #d4f7d4'
                elif val == 'Shipped':
                    return 'background-color: #d4e5f7'
                elif val == 'Pending':
                    return 'background-color: #f7f7d4'
                elif val == 'Cancelled':
                    return 'background-color: #f7d4d4'
                return ''
            
            # 스타일 적용된 데이터프레임 표시
            st.dataframe(orders_df.style.applymap(highlight_status, subset=['상태']), use_container_width=True)
            
            # 주문 상세 정보 표시
            st.subheader("주문 상세 정보")
            selected_order = st.selectbox("주문 선택", orders_df['주문번호'].tolist())
            
            if selected_order:
                # 선택한 주문의 ID 찾기
                order_id = orders_df.loc[orders_df['주문번호'] == selected_order, 'ID'].iloc[0]
                
                # 주문 상세 정보 조회
                cursor.execute("""
                SELECT od.id, p.part_code, p.part_name, od.quantity, od.unit_price, (od.quantity * od.unit_price) as subtotal
                FROM order_details od
                JOIN parts p ON od.part_id = p.id
                WHERE od.order_id = ?
                """, (order_id,))
                order_details = cursor.fetchall()
                
                if order_details:
                    details_df = pd.DataFrame(order_details, 
                                            columns=['ID', '부품 코드', '부품명', '수량', '단가(₩)', '소계(₩)'])
                    st.dataframe(details_df, use_container_width=True)
                    
                    # 총액 표시
                    total_amount = details_df['소계(₩)'].sum()
                    st.metric("주문 총액", f"₩{total_amount:,.0f}")
                else:
                    st.info("이 주문에 대한 상세 정보가 없습니다.")
        else:
            st.info("등록된 주문이 없습니다.")
    
    with tab2:
        st.subheader("새 주문 생성")
        
        # 현재 날짜를 기본값으로 설정
        today = datetime.now().date()
        
        with st.form("new_order_form"):
            order_number = st.text_input("주문번호", value=f"ORD-{today.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}")
            order_date = st.date_input("주문일자", value=today)
            expected_arrival = st.date_input("예상도착일", value=today + timedelta(days=14))
            
            # 부품 선택을 위한 멀티셀렉트
            cursor = conn.cursor()
            cursor.execute("SELECT id, part_code, part_name, unit_price FROM parts ORDER BY part_code")
            available_parts = cursor.fetchall()
            
            if available_parts:
                part_options = {f"{p[1]} - {p[2]} (₩{p[3]:,.0f})": p[0] for p in available_parts}
                selected_parts = st.multiselect("주문할 부품 선택", list(part_options.keys()))
                
                # 선택한 부품에 대한 수량 입력
                quantities = {}
                total_amount = 0
                
                if selected_parts:
                    st.write("각 부품의 주문 수량을 입력하세요:")
                    
                    for part in selected_parts:
                        part_id = part_options[part]
                        part_name = part.split(' - ')[1].split(' (')[0]
                        
                        # 해당 부품의 단가 조회
                        cursor.execute("SELECT unit_price FROM parts WHERE id = ?", (part_id,))
                        unit_price = cursor.fetchone()[0]
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(part)
                        with col2:
                            quantity = st.number_input(f"{part_name} 수량", min_value=1, value=10, key=f"qty_{part_id}")
                            quantities[part_id] = quantity
                            total_amount += quantity * unit_price
                
                st.metric("주문 총액", f"₩{total_amount:,.0f}")
                
                submitted = st.form_submit_button("주문 생성")
                
                if submitted:
                    if not selected_parts:
                        st.error("최소한 하나 이상의 부품을 선택해야 합니다.")
                    else:
                        # 주문 생성
                        cursor.execute(
                            "INSERT INTO orders (order_number, order_date, expected_arrival, status, total_amount) VALUES (?, ?, ?, ?, ?)",
                            (order_number, order_date, expected_arrival, "Pending", total_amount)
                        )
                        conn.commit()
                        
                        # 주문 ID 가져오기
                        cursor.execute("SELECT last_insert_rowid()")
                        order_id = cursor.fetchone()[0]
                        
                        # 주문 상세 정보 추가
                        for part_id, quantity in quantities.items():
                            # 부품 단가 조회
                            cursor.execute("SELECT unit_price FROM parts WHERE id = ?", (part_id,))
                            unit_price = cursor.fetchone()[0]
                            
                            cursor.execute(
                                "INSERT INTO order_details (order_id, part_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                                (order_id, part_id, quantity, unit_price)
                            )
                        
                        conn.commit()
                        st.success(f"주문 '{order_number}' 생성 완료!")
            else:
                st.error("등록된 부품이 없습니다. 먼저 부품을 등록해주세요.")
    
    with tab3:
        st.subheader("주문 상태 관리")
        
        # 대기 중 또는 배송 중인 주문 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, order_number, order_date, expected_arrival, status, total_amount
        FROM orders
        WHERE status IN ('Pending', 'Shipped')
        ORDER BY order_date
        """)
        active_orders = cursor.fetchall()
        
        if active_orders:
            active_orders_df = pd.DataFrame(active_orders, 
                                         columns=['ID', '주문번호', '주문일자', '예상도착일', '현재 상태', '총액(₩)'])
            
            # 날짜 형식 변환
            active_orders_df['주문일자'] = pd.to_datetime(active_orders_df['주문일자']).dt.strftime('%Y-%m-%d')
            active_orders_df['예상도착일'] = pd.to_datetime(active_orders_df['예상도착일']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(active_orders_df, use_container_width=True)
            
            # 주문 상태 업데이트 폼
            st.write("주문 상태 업데이트")
            
            col1, col2 = st.columns(2)
            
            with col1:
                order_to_update = st.selectbox("업데이트할 주문 선택", active_orders_df['주문번호'].tolist())
            
            with col2:
                new_status = st.selectbox("새 상태", ["Pending", "Shipped", "Delivered", "Cancelled"])
            
            if st.button("상태 업데이트"):
                # 선택한 주문의 ID 찾기
                order_id = active_orders_df.loc[active_orders_df['주문번호'] == order_to_update, 'ID'].iloc[0]
                
                # 주문 상태 업데이트
                cursor.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (new_status, order_id)
                )
                conn.commit()
                
                # 배송 완료인 경우 재고 업데이트
                if new_status == "Delivered":
                    # 주문 상세 정보 조회
                    cursor.execute("""
                    SELECT part_id, quantity
                    FROM order_details
                    WHERE order_id = ?
                    """, (order_id,))
                    order_details = cursor.fetchall()
                    
                    # 재고 업데이트
                    for part_id, quantity in order_details:
                        cursor.execute(
                            "UPDATE parts SET stock = stock + ? WHERE id = ?",
                            (quantity, part_id)
                        )
                    
                    conn.commit()
                    st.success(f"주문 '{order_to_update}' 상태가 '{new_status}'로 변경되었습니다. 부품 재고가 업데이트되었습니다.")
                else:
                    st.success(f"주문 '{order_to_update}' 상태가 '{new_status}'로 변경되었습니다.")
        else:
            st.info("대기 중이거나 배송 중인 주문이 없습니다.")

# 생산 관리 페이지
def display_production_management(conn):
    st.title("생산 관리")
    
    tab1, tab2, tab3 = st.tabs(["생산 계획 목록", "새 생산 계획", "생산 현황 관리"])
    
    with tab1:
        st.subheader("생산 계획 목록")
        
        # 생산 계획 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT p.id, p.batch_number, pr.product_name, p.quantity, p.start_date, p.end_date, p.status
        FROM production p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.start_date DESC
        """)
        production_data = cursor.fetchall()
        
        if production_data:
            production_df = pd.DataFrame(production_data, 
                                       columns=['ID', '배치번호', '제품명', '수량', '시작일', '종료일', '상태'])
            
            # 날짜 형식 변환
            production_df['시작일'] = pd.to_datetime(production_df['시작일']).dt.strftime('%Y-%m-%d')
            production_df['종료일'] = pd.to_datetime(production_df['종료일']).dt.strftime('%Y-%m-%d')
            
            # 상태별 색상 지정
            def highlight_status(val):
                if val == 'Completed':
                    return 'background-color: #d4f7d4'
                elif val == 'In Progress':
                    return 'background-color: #d4e5f7'
                elif val == 'Planned':
                    return 'background-color: #f7f7d4'
                elif val == 'Delayed':
                    return 'background-color: #f7d4d4'
                return ''
            
            # 스타일 적용된 데이터프레임 표시
            st.dataframe(production_df.style.applymap(highlight_status, subset=['상태']), use_container_width=True)
            
            # 생산 현황 차트
            st.subheader("생산 현황")
            
            # 상태별 수량 계산
            status_counts = production_df['상태'].value_counts().reset_index()
            status_counts.columns = ['상태', '건수']
            
            # 차트 생성
            fig = px.pie(status_counts, values='건수', names='상태',
                       title='생산 계획 상태별 분포',
                       color='상태',
                       color_discrete_map={
                           'Completed': '#00CC96',
                           'In Progress': '#636EFA',
                           'Planned': '#FFA15A',
                           'Delayed': '#EF553B'
                       })
            fig.update_traces(textposition='inside', textinfo='percent+label')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 제품별 생산량 차트
            product_production = production_df.groupby('제품명')['수량'].sum().reset_index()
            
            fig = px.bar(product_production, x='제품명', y='수량',
                       title='제품별 총 생산량',
                       labels={'제품명': '제품명', '수량': '총 생산량'})
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("등록된 생산 계획이 없습니다.")
    
    with tab2:
        st.subheader("새 생산 계획 생성")
        
        # 제품 목록 조회
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_code, product_name FROM products ORDER BY product_code")
        products = cursor.fetchall()
        
        if products:
            with st.form("new_production_form"):
                # 현재 날짜를 기본값으로 설정
                today = datetime.now().date()
                
                batch_number = st.text_input("배치번호", value=f"BATCH-{today.strftime('%Y%m%d')}-{np.random.randint(100, 999)}")
                
                # 제품 선택
                product_options = {f"{p[1]} - {p[2]}": p[0] for p in products}
                selected_product = st.selectbox("제품 선택", list(product_options.keys()))
                product_id = product_options[selected_product]
                
                quantity = st.number_input("생산 수량", min_value=1, value=10)
                start_date = st.date_input("시작일", value=today)
                end_date = st.date_input("종료 예정일", value=today + timedelta(days=5))
                
                status = st.selectbox("초기 상태", ["Planned", "In Progress"])
                
                # 생산에 필요한 부품 확인
                cursor.execute("""
                SELECT p.part_name, b.quantity, p.stock, (b.quantity * ?) as required_qty
                FROM bill_of_materials b
                JOIN parts p ON b.part_id = p.id
                WHERE b.product_id = ?
                """, (quantity, product_id))
                bom_data = cursor.fetchall()
                
                if bom_data:
                    st.write("생산에 필요한 부품:")
                    
                    bom_df = pd.DataFrame(bom_data, columns=['부품명', '단위당 필요수량', '현재 재고', '총 필요수량'])
                    
                    # 부족한 부품 표시
                    bom_df['부족량'] = bom_df.apply(lambda row: max(0, row['총 필요수량'] - row['현재 재고']), axis=1)
                    bom_df['상태'] = bom_df.apply(lambda row: '부족' if row['부족량'] > 0 else '충분', axis=1)
                    
                    # 상태별 색상 지정
                    def highlight_status(val):
                        if val == '충분':
                            return 'background-color: #d4f7d4'
                        elif val == '부족':
                            return 'background-color: #f7d4d4'
                        return ''
                    
                    st.dataframe(bom_df.style.applymap(highlight_status, subset=['상태']), use_container_width=True)
                    
                    # 부족한 부품이 있는지 확인
                    shortage = bom_df['부족량'].sum() > 0
                    
                    if shortage:
                        st.warning("일부 부품의 재고가 부족합니다. 부품 재고를 확인하세요.")
                
                submitted = st.form_submit_button("생산 계획 생성")
                
                if submitted:
                    if start_date > end_date:
                        st.error("종료일은 시작일보다 이후여야 합니다.")
                    else:
                        # 생산 계획 생성
                        cursor.execute(
                            "INSERT INTO production (batch_number, product_id, quantity, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                            (batch_number, product_id, quantity, start_date, end_date, status)
                        )
                        conn.commit()
                        
                        st.success(f"생산 계획 '{batch_number}'이(가) 생성되었습니다!")
                        
                        if shortage:
                            st.warning("일부 부품의 재고가 부족합니다. 부품 재고를 확인하세요.")
        else:
            st.error("등록된 제품이 없습니다. 먼저 제품을 등록해주세요.")

# 판매 분석 페이지
def display_sales_analysis(conn):
    st.title("판매 분석")
    
    # 판매 데이터 조회
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.id, s.invoice_number, s.sale_date, s.customer, p.product_name, s.quantity, s.unit_price, s.total_amount
    FROM sales s
    JOIN products p ON s.product_id = p.id
    ORDER BY s.sale_date DESC
    """)
    sales_data = cursor.fetchall()
    
    if sales_data:
        sales_df = pd.DataFrame(sales_data, 
                             columns=['ID', '송장번호', '판매일', '고객', '제품명', '수량', '단가(₩)', '총액(₩)'])
        
        # 날짜 형식 변환
        sales_df['판매일'] = pd.to_datetime(sales_df['판매일']).dt.strftime('%Y-%m-%d')
        
        # 기간 선택 필터
        st.subheader("기간 선택")
        col1, col2 = st.columns(2)
        
        with col1:
            # 최소/최대 날짜 계산
            min_date = pd.to_datetime(sales_df['판매일']).min()
            max_date = pd.to_datetime(sales_df['판매일']).max()
            
            start_date = st.date_input("시작일", min_date, min_value=min_date, max_value=max_date)
        
        with col2:
            end_date = st.date_input("종료일", max_date, min_value=min_date, max_value=max_date)
        
        # 필터링된 데이터
        filtered_df = sales_df[
            (pd.to_datetime(sales_df['판매일']) >= pd.to_datetime(start_date)) & 
            (pd.to_datetime(sales_df['판매일']) <= pd.to_datetime(end_date))
        ]
        
        # 시간 집계 단위 선택
        time_unit = st.selectbox("시간 단위", ["일별", "주별", "월별"])
        
        # 집계 데이터 생성
        time_df = pd.to_datetime(filtered_df['판매일'])
        
        if time_unit == "일별":
            filtered_df['집계기간'] = time_df.dt.strftime('%Y-%m-%d')
        elif time_unit == "주별":
            filtered_df['집계기간'] = time_df.dt.strftime('%Y-W%U')
        else:  # 월별
            filtered_df['집계기간'] = time_df.dt.strftime('%Y-%m')
        
        # 집계 데이터
        agg_data = filtered_df.groupby('집계기간').agg({
            '총액(₩)': 'sum',
            'ID': 'count'
        }).reset_index()
        agg_data.columns = ['기간', '총 판매액(₩)', '판매 건수']
        
        # KPI 메트릭
        st.subheader("판매 요약")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_sales = filtered_df['총액(₩)'].sum()
            st.metric("총 판매액", f"₩{total_sales:,.0f}")
        
        with col2:
            total_orders = len(filtered_df)
            st.metric("총 판매 건수", f"{total_orders}")
        
        with col3:
            if total_orders > 0:
                avg_order_value = total_sales / total_orders
                st.metric("평균 판매액", f"₩{avg_order_value:,.0f}")
            else:
                st.metric("평균 판매액", "₩0")
        
        # 판매 추이 차트
        st.subheader(f"{time_unit} 판매 추이")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=agg_data['기간'],
            y=agg_data['총 판매액(₩)'],
            name='총 판매액',
            marker_color='#1f77b4'
        ))
        
        fig.add_trace(go.Scatter(
            x=agg_data['기간'],
            y=agg_data['판매 건수'],
            name='판매 건수',
            mode='lines+markers',
            marker_color='red',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f"{time_unit} 판매 추이",
            xaxis_title='기간',
            yaxis_title='판매액 (₩)',
            yaxis2=dict(
                title='판매 건수',
                overlaying='y',
                side='right'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 제품별 판매 분석
        st.subheader("제품별 판매 분석")
        
        # 제품별 집계
        product_agg = filtered_df.groupby('제품명').agg({
            '총액(₩)': 'sum',
            '수량': 'sum',
            'ID': 'count'
        }).reset_index()
        product_agg.columns = ['제품명', '총 판매액(₩)', '총 판매량', '판매 건수']
        
        # 제품별 점유율 계산
        product_agg['매출 점유율(%)'] = (product_agg['총 판매액(₩)'] / product_agg['총 판매액(₩)'].sum() * 100).round(1)
        product_agg['수량 점유율(%)'] = (product_agg['총 판매량'] / product_agg['총 판매량'].sum() * 100).round(1)
        
        # 정렬
        product_agg = product_agg.sort_values('총 판매액(₩)', ascending=False).reset_index(drop=True)
        
        # 테이블 표시
        st.dataframe(product_agg, use_container_width=True)
        
        # 제품별 판매액 파이 차트
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(product_agg, values='총 판매액(₩)', names='제품명',
                      title='제품별 판매액 점유율',
                      hover_data=['매출 점유율(%)'],
                      labels={'총 판매액(₩)': '판매액'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(product_agg, values='총 판매량', names='제품명',
                      title='제품별 판매량 점유율',
                      hover_data=['수량 점유율(%)'],
                      labels={'총 판매량': '판매량'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        # 고객별 판매 분석
        st.subheader("고객별 판매 분석")
        
        # 고객별 집계
        customer_agg = filtered_df.groupby('고객').agg({
            '총액(₩)': 'sum',
            'ID': 'count'
        }).reset_index()
        customer_agg.columns = ['고객', '총 판매액(₩)', '판매 건수']
        
        # 고객별 점유율 계산
        customer_agg['매출 점유율(%)'] = (customer_agg['총 판매액(₩)'] / customer_agg['총 판매액(₩)'].sum() * 100).round(1)
        
        # 정렬
        customer_agg = customer_agg.sort_values('총 판매액(₩)', ascending=False).reset_index(drop=True)
        
        # 테이블 표시
        st.dataframe(customer_agg, use_container_width=True)
        
        # 상위 고객 막대 차트
        top_n = min(len(customer_agg), 10)  # 최대 10개까지만 표시
        
        fig = px.bar(customer_agg.head(top_n), 
                   x='고객', y='총 판매액(₩)',
                   title=f'상위 {top_n} 고객 매출',
                   color='총 판매액(₩)',
                   labels={'고객': '고객명', '총 판매액(₩)': '총 판매액(₩)'})
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 판매 데이터 테이블
        st.subheader("판매 상세 데이터")
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("판매 데이터가 없습니다.")

# 재고 관리 페이지
def display_inventory_management(conn):
    st.title("재고 관리")
    
    tab1, tab2 = st.tabs(["부품 재고", "제품 재고"])
    
    with tab1:
        st.subheader("부품 재고 현황")
        
        # 부품 재고 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, part_code, part_name, supplier, stock, min_stock, unit_price, (stock * unit_price) as stock_value
        FROM parts
        ORDER BY (stock * 1.0 / min_stock) ASC
        """)
        parts_stock_data = cursor.fetchall()
        
        if parts_stock_data:
            parts_stock_df = pd.DataFrame(parts_stock_data, 
                                        columns=['ID', '부품 코드', '부품명', '공급업체', '현재 재고', '최소 재고', '단가(₩)', '재고 가치(₩)'])
            
            # 재고 상태 계산
            parts_stock_df['재고 상태'] = parts_stock_df.apply(
                lambda row: '부족' if row['현재 재고'] < row['최소 재고'] else '정상', 
                axis=1
            )
            
            # 상태별 색상 지정
            def highlight_status(val):
                if val == '정상':
                    return 'background-color: #d4f7d4'
                elif val == '부족':
                    return 'background-color: #f7d4d4'
                return ''
            
            # 스타일 적용된 데이터프레임 표시
            st.dataframe(parts_stock_df.style.applymap(highlight_status, subset=['재고 상태']), use_container_width=True)
            
            # 재고 가치 계산
            total_stock_value = parts_stock_df['재고 가치(₩)'].sum()
            st.metric("총 부품 재고 가치", f"₩{total_stock_value:,.0f}")
            
            # 부품 재고 차트
            st.subheader("부품 재고 수준")
            
            # 재고 부족 부품 필터링
            low_stock_parts = parts_stock_df[parts_stock_df['재고 상태'] == '부족']
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=parts_stock_df['부품명'],
                y=parts_stock_df['현재 재고'],
                name='현재 재고',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Scatter(
                x=parts_stock_df['부품명'],
                y=parts_stock_df['최소 재고'],
                name='최소 재고',
                mode='lines+markers',
                marker_color='red'
            ))
            
            fig.update_layout(
                title='부품별 재고 수준',
                xaxis_title='부품명',
                yaxis_title='수량'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 재고 부족 부품 표시
            if not low_stock_parts.empty:
                st.subheader("재고 부족 부품")
                st.dataframe(low_stock_parts[['부품 코드', '부품명', '현재 재고', '최소 재고', '재고 상태']], use_container_width=True)
                
                # 재고 부족 부품에 대한 주문 권장
                st.warning(f"{len(low_stock_parts)}개 부품의 재고가 부족합니다. 주문을 검토하세요.")
                
                if st.button("주문 페이지로 이동"):
                    st.session_state.menu = "부품 주문"
                    st.experimental_rerun()
            else:
                st.success("모든 부품의 재고가 충분합니다.")
        else:
            st.info("등록된 부품이 없습니다.")
    
    with tab2:
        st.subheader("제품 재고 현황")
        
        # 제품 재고 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, product_code, product_name, brand, stock, selling_price, (stock * selling_price) as stock_value
        FROM products
        ORDER BY stock ASC
        """)
        products_stock_data = cursor.fetchall()
        
        if products_stock_data:
            products_stock_df = pd.DataFrame(products_stock_data, 
                                          columns=['ID', '제품 코드', '제품명', '브랜드', '현재 재고', '판매가(₩)', '재고 가치(₩)'])
            
            # 재고 가치 계산
            total_product_value = products_stock_df['재고 가치(₩)'].sum()
            
            # 테이블 표시
            st.dataframe(products_stock_df, use_container_width=True)
            
            # 총 재고 가치 표시
            st.metric("총 제품 재고 가치", f"₩{total_product_value:,.0f}")
            
            # 제품 재고 차트
            st.subheader("제품 재고 현황")
            
            fig = px.bar(products_stock_df, 
                       x='제품명', y='현재 재고',
                       title='제품별 재고 수준',
                       color='현재 재고',
                       labels={'제품명': '제품명', '현재 재고': '재고 수량'})
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 제품 재고 가치 파이 차트
            st.subheader("제품별 재고 가치 비중")
            
            fig = px.pie(products_stock_df, values='재고 가치(₩)', names='제품명',
                       title='제품별 재고 가치 비중',
                       hover_data=['현재 재고'],
                       labels={'재고 가치(₩)': '재고 가치'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 재고 없는 제품 필터링
            no_stock_products = products_stock_df[products_stock_df['현재 재고'] == 0]
            
            if not no_stock_products.empty:
                st.subheader("재고 없는 제품")
                st.dataframe(no_stock_products[['제품 코드', '제품명', '현재 재고']], use_container_width=True)
                
                st.warning(f"{len(no_stock_products)}개 제품의 재고가 없습니다. 생산 계획을 검토하세요.")
                
                if st.button("생산 페이지로 이동"):
                    st.session_state.menu = "생산 관리"
                    st.experimental_rerun()
        else:
            st.info("등록된 제품이 없습니다.")

# 설정 페이지
def display_settings(conn):
    st.title("시스템 설정")
    
    st.subheader("회사 정보")
    
    with st.form("company_info_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("회사명", value="YUER-한국 조인트벤처")
            jv_name = st.text_input("조인트벤처명", value="YUER Korea Skylights")
            foundation_date = st.date_input("설립일", value=datetime.now().date())
        
        with col2:
            company_address = st.text_input("회사 주소", value="서울특별시 강남구 테헤란로 123")
            company_phone = st.text_input("회사 전화번호", value="02-1234-5678")
            company_email = st.text_input("회사 이메일", value="info@yuer-korea.com")
        
        submitted = st.form_submit_button("저장")
        
        if submitted:
            st.success("회사 정보가 저장되었습니다.")
    
    st.markdown("---")
    
    st.subheader("데이터베이스 관리")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("샘플 데이터 초기화", help="현재 데이터를 삭제하고 샘플 데이터를 다시 생성합니다."):
            # 모든 테이블 데이터 삭제
            cursor = conn.cursor()
            tables = ['sales', 'production', 'bill_of_materials', 'products', 'order_details', 'orders', 'parts']
            
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            
            conn.commit()
            
            # 샘플 데이터 생성
            create_sample_data(conn)
            
            st.success("샘플 데이터가 초기화되었습니다.")
    
    with col2:
        if st.button("모든 데이터 삭제", help="시스템의 모든 데이터를 삭제합니다. 이 작업은 되돌릴 수 없습니다."):
            # 확인 대화상자
            if st.checkbox("정말로 모든 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다."):
                # 모든 테이블 데이터 삭제
                cursor = conn.cursor()
                tables = ['sales', 'production', 'bill_of_materials', 'products', 'order_details', 'orders', 'parts']
                
                for table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                
                conn.commit()
                
                st.success("모든 데이터가 삭제되었습니다.")
    
    st.markdown("---")
    
    st.subheader("시스템 정보")
    
    # 간단한 시스템 정보 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""**시스템 정보**
- 애플리케이션: YUER-한국 조인트벤처 관리 시스템
- 버전: 1.0.0
- 개발: Claude AI
- 기반 기술: Python, Streamlit, SQLite""")
    
    with col2:
        # 현재 DB 통계
        cursor = conn.cursor()
        
        # 테이블별 레코드 수 조회
        cursor.execute("SELECT COUNT(*) FROM parts")
        parts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        orders_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM production")
        production_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        st.info("**데이터베이스 통계**\n"
               f"- 부품: {parts_count}개\n"
               f"- 제품: {products_count}개\n"
               f"- 주문: {orders_count}개\n"
               f"- 생산 계획: {production_count}개\n"
               f"- 판매 기록: {sales_count}개"
        )

if __name__ == "__main__":
    main()
    
    with tab3:
        st.subheader("생산 현황 관리")
        
        # 진행 중이거나 계획된 생산 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT p.id, p.batch_number, pr.product_name, p.quantity, p.start_date, p.end_date, p.status
        FROM production p
        JOIN products pr ON p.product_id = pr.id
        WHERE p.status IN ('Planned', 'In Progress', 'Delayed')
        ORDER BY p.start_date
        """)
        active_production = cursor.fetchall()
        
        if active_production:
            active_production_df = pd.DataFrame(active_production, 
                                              columns=['ID', '배치번호', '제품명', '수량', '시작일', '종료일', '현재 상태'])
            
            # 날짜 형식 변환
            active_production_df['시작일'] = pd.to_datetime(active_production_df['시작일']).dt.strftime('%Y-%m-%d')
            active_production_df['종료일'] = pd.to_datetime(active_production_df['종료일']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(active_production_df, use_container_width=True)
            
            # 생산 상태 업데이트 폼
            st.write("생산 상태 업데이트")
            
            col1, col2 = st.columns(2)
            
            with col1:
                production_to_update = st.selectbox("업데이트할 생산 계획 선택", active_production_df['배치번호'].tolist())
            
            with col2:
                new_status = st.selectbox("새 상태", ["Planned", "In Progress", "Completed", "Delayed"])
            
            if st.button("상태 업데이트"):
                # 선택한 생산의 ID와 수량 찾기
                production_row = active_production_df.loc[active_production_df['배치번호'] == production_to_update]
                production_id = production_row['ID'].iloc[0]
                production_quantity = production_row['수량'].iloc[0]
                
                # 생산 상태 업데이트
                cursor.execute(
                    "UPDATE production SET status = ? WHERE id = ?",
                    (new_status, production_id)
                )
                conn.commit()
                
                # 완료된 경우 제품 재고 업데이트 및 부품 재고 차감
                if new_status == "Completed":
                    # 제품 ID 조회
                    cursor.execute("SELECT product_id FROM production WHERE id = ?", (production_id,))
                    product_id = cursor.fetchone()[0]
                    
                    # 제품 재고 업데이트
                    cursor.execute(
                        "UPDATE products SET stock = stock + ? WHERE id = ?",
                        (production_quantity, product_id)
                    )
                    
                    # BOM 조회하여 부품 재고 차감
                    cursor.execute("""
                    SELECT part_id, quantity
                    FROM bill_of_materials
                    WHERE product_id = ?
                    """, (product_id,))
                    bom_items = cursor.fetchall()
                    
                    for part_id, qty_per_unit in bom_items:
                        total_qty = qty_per_unit * production_quantity
                        cursor.execute(
                            "UPDATE parts SET stock = stock - ? WHERE id = ?",
                            (total_qty, part_id)
                        )
                    
                    conn.commit()
                    st.success(f"생산 '{production_to_update}'의 상태가 '{new_status}'로 변경되었습니다. 제품 재고와 부품 재고가 업데이트되었습니다.")
                else:
                    st.success(f"생산 '{production_to_update}'의 상태가 '{new_status}'로 변경되었습니다.")
        else:
            st.info("진행 중이거나 계획된 생산이 없습니다.")

# 제품 관리 페이지
def display_products_management(conn):
    st.title("제품 관리")
    
    tab1, tab2, tab3 = st.tabs(["제품 목록", "제품 추가/수정", "BOM 관리"])
    
    with tab1:
        st.subheader("제품 목록")
        
        # 제품 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, product_code, product_name, brand, selling_price, production_cost, stock
        FROM products
        ORDER BY product_code
        """)
        products_data = cursor.fetchall()
        
        if products_data:
            products_df = pd.DataFrame(products_data, 
                                    columns=['ID', '제품 코드', '제품명', '브랜드', '판매가(₩)', '생산원가(₩)', '현재 재고'])
            
            # 마진 계산
            products_df['마진(₩)'] = products_df['판매가(₩)'] - products_df['생산원가(₩)']
            products_df['마진율(%)'] = (products_df['마진(₩)'] / products_df['판매가(₩)'] * 100).round(1)
            
            # 데이터프레임 표시
            st.dataframe(products_df, use_container_width=True)
            
            # 제품별 판매가/원가 차트
            st.subheader("제품별 판매가 및 원가")
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=products_df['제품명'],
                y=products_df['판매가(₩)'],
                name='판매가',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Bar(
                x=products_df['제품명'],
                y=products_df['생산원가(₩)'],
                name='생산원가',
                marker_color='#ff7f0e'
            ))
            
            fig.add_trace(go.Scatter(
                x=products_df['제품명'],
                y=products_df['마진율(%)'],
                name='마진율(%)',
                yaxis='y2',
                mode='lines+markers',
                marker_color='red'
            ))
            
            fig.update_layout(
                title='제품별 판매가 및 원가',
                xaxis_title='제품명',
                yaxis_title='금액 (₩)',
                yaxis2=dict(
                    title='마진율 (%)',
                    overlaying='y',
                    side='right',
                    range=[0, 100]
                ),
                barmode='group'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 제품별 재고 현황
            st.subheader("제품별 재고 현황")
            
            fig = px.bar(products_df, x='제품명', y='현재 재고',
                       title='제품별 재고 수준',
                       color='현재 재고',
                       labels={'제품명': '제품명', '현재 재고': '재고 수량'})
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("등록된 제품이 없습니다.")
    
    with tab2:
        st.subheader("제품 추가/수정")
        
        # 제품 추가 폼
        with st.form("product_form"):
            st.write("새 제품 등록")
            product_code = st.text_input("제품 코드")
            product_name = st.text_input("제품명")
            brand = st.text_input("브랜드", value="Korean Brand")
            selling_price = st.number_input("판매가(₩)", min_value=0.0, step=0.1)
            production_cost = st.number_input("생산원가(₩)", min_value=0.0, step=0.1)
            stock = st.number_input("초기 재고", min_value=0, step=1)
            
            submitted = st.form_submit_button("제품 추가")
            
            if submitted:
                if not product_code or not product_name:
                    st.error("제품 코드와 제품명은 필수입니다.")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO products (product_code, product_name, brand, selling_price, production_cost, stock) VALUES (?, ?, ?, ?, ?, ?)",
                        (product_code, product_name, brand, selling_price, production_cost, stock)
                    )
                    conn.commit()
                    st.success(f"제품 '{product_name}' 추가 완료!")
        
        # 제품 수정 섹션
        st.markdown("---")
        st.write("제품 정보 수정")
        
        # 제품 목록 조회
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_code, product_name FROM products ORDER BY product_code")
        products = cursor.fetchall()
        
        if products:
            product_options = {f"{p[1]} - {p[2]}": p[0] for p in products}
            selected_product = st.selectbox("수정할 제품 선택", list(product_options.keys()))
            
            product_id = product_options[selected_product]
            
            # 선택한 제품 정보 조회
            cursor.execute(
                "SELECT product_code, product_name, brand, selling_price, production_cost, stock FROM products WHERE id = ?",
                (product_id,)
            )
            product_data = cursor.fetchone()
            
            if product_data:
                with st.form("edit_product_form"):
                    st.write(f"'{product_data[1]}' 정보 수정")
                    
                    edit_product_code = st.text_input("제품 코드", value=product_data[0])
                    edit_product_name = st.text_input("제품명", value=product_data[1])
                    edit_brand = st.text_input("브랜드", value=product_data[2])
                    edit_selling_price = st.number_input("판매가(₩)", min_value=0.0, step=0.1, value=float(product_data[3]))
                    edit_production_cost = st.number_input("생산원가(₩)", min_value=0.0, step=0.1, value=float(product_data[4]))
                    edit_stock = st.number_input("현재 재고", min_value=0, step=1, value=int(product_data[5]))
                    
                    update_submitted = st.form_submit_button("정보 업데이트")
                    
                    if update_submitted:
                        cursor.execute(
                            "UPDATE products SET product_code = ?, product_name = ?, brand = ?, selling_price = ?, production_cost = ?, stock = ? WHERE id = ?",
                            (edit_product_code, edit_product_name, edit_brand, edit_selling_price, edit_production_cost, edit_stock, product_id)
                        )
                        conn.commit()
                        st.success(f"제품 '{edit_product_name}' 정보 업데이트 완료!")
        else:
            st.info("등록된 제품이 없습니다.")
    
    with tab3:
        st.subheader("BOM(Bill of Materials) 관리")
        
        # 제품 목록 조회
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_code, product_name FROM products ORDER BY product_code")
        products = cursor.fetchall()
        
        if products:
            product_options = {f"{p[1]} - {p[2]}": p[0] for p in products}
            selected_product = st.selectbox("BOM을 관리할 제품 선택", list(product_options.keys()), key="bom_product")
            
            product_id = product_options[selected_product]
            
            # 현재 BOM 목록 표시
            cursor.execute("""
            SELECT b.id, p.part_code, p.part_name, b.quantity, p.unit_price, (b.quantity * p.unit_price) as total_cost
            FROM bill_of_materials b
            JOIN parts p ON b.part_id = p.id
            WHERE b.product_id = ?
            ORDER BY p.part_code
            """, (product_id,))
            bom_data = cursor.fetchall()
            
            if bom_data:
                st.write(f"'{selected_product.split(' - ')[1]}' 제품의 BOM")
                
                bom_df = pd.DataFrame(bom_data, 
                                    columns=['ID', '부품 코드', '부품명', '필요 수량', '단가(₩)', '소계(₩)'])
                
                st.dataframe(bom_df, use_container_width=True)
                
                # 총 원가 계산
                total_cost = bom_df['소계(₩)'].sum()
                st.metric("총 원가", f"₩{total_cost:,.0f}")
                
                # 생산원가와 BOM 원가 비교
                cursor.execute("SELECT production_cost FROM products WHERE id = ?", (product_id,))
                production_cost = cursor.fetchone()[0]
                
                st.write(f"현재 설정된 생산원가: ₩{production_cost:,.0f}")
                
                if abs(total_cost - production_cost) > 0.01:
                    st.warning(f"BOM 원가(₩{total_cost:,.0f})와 설정된 생산원가(₩{production_cost:,.0f})가 일치하지 않습니다. 생산원가를 업데이트하세요.")
                    
                    if st.button("생산원가를 BOM 원가로 업데이트"):
                        cursor.execute(
                            "UPDATE products SET production_cost = ? WHERE id = ?",
                            (total_cost, product_id)
                        )
                        conn.commit()
                        st.success("생산원가가 업데이트되었습니다.")
            else:
                st.info(f"'{selected_product.split(' - ')[1]}' 제품의 BOM이 없습니다. BOM을 구성해주세요.")
            
            # BOM 항목 추가
            st.markdown("---")
            st.write("BOM 항목 추가")
            
            # 부품 목록 조회
            cursor.execute("SELECT id, part_code, part_name, unit_price FROM parts ORDER BY part_code")
            available_parts = cursor.fetchall()
            
            if available_parts:
                with st.form("add_bom_item_form"):
                    # 이미 BOM에 있는 부품 ID 목록
                    existing_part_ids = []
                    if bom_data:
                        cursor.execute(
                            "SELECT part_id FROM bill_of_materials WHERE product_id = ?", 
                            (product_id,)
                        )
                        existing_part_ids = [row[0] for row in cursor.fetchall()]
                    
                    # 아직 BOM에 추가되지 않은 부품만 필터링
                    available_parts_filtered = [p for p in available_parts if p[0] not in existing_part_ids]
                    
                    if available_parts_filtered:
                        part_options = {f"{p[1]} - {p[2]} (₩{p[3]:,.0f})": p[0] for p in available_parts_filtered}
                        selected_part = st.selectbox("부품 선택", list(part_options.keys()))
                        part_id = part_options[selected_part]
                        
                        quantity = st.number_input("필요 수량", min_value=1, value=1)
                        
                        submitted = st.form_submit_button("BOM 항목 추가")
                        
                        if submitted:
                            # 이미 있는지 확인
                            cursor.execute(
                                "SELECT COUNT(*) FROM bill_of_materials WHERE product_id = ? AND part_id = ?",
                                (product_id, part_id)
                            )
                            if cursor.fetchone()[0] > 0:
                                st.error("이 부품은 이미 BOM에 있습니다.")
                            else:
                                cursor.execute(
                                    "INSERT INTO bill_of_materials (product_id, part_id, quantity) VALUES (?, ?, ?)",
                                    (product_id, part_id, quantity)
                                )
                                conn.commit()
                                st.success("BOM 항목이 추가되었습니다.")
                    else:
                        st.info("추가할 수 있는 부품이 없습니다. 모든 부품이 이미 BOM에 포함되어 있습니다.")
            else:
                st.error("등록된 부품이 없습니다. 먼저 부품을 등록해주세요.")
            
            # BOM 항목 수정/삭제
            if bom_data:
                st.markdown("---")
                st.write("BOM 항목 수정/삭제")
                
                bom_item_options = {f"{row[2]} (필요 수량: {row[3]})": row[0] for row in bom_data}
                selected_bom_item = st.selectbox("수정/삭제할 BOM 항목 선택", list(bom_item_options.keys()))
                bom_item_id = bom_item_options[selected_bom_item]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 현재 수량 조회
                    cursor.execute("SELECT quantity FROM bill_of_materials WHERE id = ?", (bom_item_id,))
                    current_quantity = cursor.fetchone()[0]
                    
                    new_quantity = st.number_input("새 수량", min_value=1, value=current_quantity)
                    
                    if st.button("수량 업데이트"):
                        cursor.execute(
                            "UPDATE bill_of_materials SET quantity = ? WHERE id = ?",
                            (new_quantity, bom_item_id)
                        )
                        conn.commit()
                        st.success("BOM 항목이 업데이트되었습니다.")
                
                with col2:
                    if st.button("항목 삭제", type="primary", help="이 항목을 BOM에서 삭제합니다."):
                        cursor.execute(
                            "DELETE FROM bill_of_materials WHERE id = ?",
                            (bom_item_id,)
                        )
                        conn.commit()
                        st.success("BOM 항목이 삭제되었습니다.")
        else:
            st.error("등록된 제품이 없습니다. 먼저 제품을 등록해주세요.")

if __name__ == "__main__":
    main() 