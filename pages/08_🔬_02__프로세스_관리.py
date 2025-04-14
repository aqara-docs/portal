import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 환경 변수 로드
load_dotenv()

# 데이터베이스 설정
def get_connection():
    """MySQL 데이터베이스 연결 생성"""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except Error as e:
        st.error(f"데이터베이스 연결 실패: {str(e)}")
        return None

# 샘플 데이터 생성
def create_sample_data(conn):
    """샘플 데이터 생성"""
    cursor = conn.cursor()
    
    try:
        # 외래 키 체크 비활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS sales")
        cursor.execute("DROP TABLE IF EXISTS products")
        conn.commit()
        
        # 1. 테이블 생성
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
        conn.commit()
            
        # 2. 제품 데이터 생성
        products = [
            ('PR001', 'V6 엔진', '고정식', '대형', 'YUER', 5000000, 3000000, 10),
            ('PR002', 'V8 엔진', '고정식', '대형', 'YUER', 8000000, 4800000, 5),
            ('PR003', 'I4 엔진', '개폐식', '중형', 'YUER', 3000000, 1800000, 15),
            ('PR004', '디젤 엔진', '고정식', '대형', 'YUER', 6000000, 3600000, 8),
            ('PR005', '하이브리드 엔진', '자동식', '중형', 'YUER', 7000000, 4200000, 12)
        ]
        
        try:
            cursor.executemany('''
                INSERT INTO products (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', products)
            conn.commit()
        except mysql.connector.Error as err:
            if err.errno == 1062:  # Duplicate entry error
                st.warning(f"중복된 제품 코드가 발견되었습니다. 건너뜁니다: {err}")
                conn.rollback()
            else:
                raise
        
        # 제품 ID 확인
        cursor.execute("SELECT id FROM products")
        product_ids = [row[0] for row in cursor.fetchall()]
        
        if not product_ids:
            st.error("제품 데이터가 생성되지 않았습니다. 샘플 데이터 생성을 중단합니다.")
            return False
        
        # 외래 키 체크 다시 활성화
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"샘플 데이터 생성 중 오류 발생: {err}")
        return False
    finally:
        cursor.close()

# 앱 레이아웃 및 기능
def main():
    st.set_page_config(
        page_title="YUER-한국 조인트벤처 관리 시스템",
        page_icon="🏭",
        layout="wide"
    )
    
    # 데이터베이스 초기화
    conn = get_connection()
    if conn:
        # 테이블 생성 확인
        if not create_sample_data(conn):
            st.error("테이블 생성에 실패했습니다. 데이터베이스 관리 페이지에서 테이블을 생성해주세요.")
            return
            
        # 사이드바 메뉴
        st.sidebar.title("YUER-한국 조인트벤처")
        menu = st.sidebar.selectbox(
            "메뉴 선택",
            ["대시보드", "부품 관리", "부품 주문", "생산 관리", "제품 관리", "판매 관리", "판매 분석", "재고 관리", "설정"]
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
        elif menu == "판매 관리":
            display_sales_management(conn)
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
        SELECT DATE_FORMAT(order_date, '%Y-%m') as month, SUM(total_amount) as total
        FROM orders
        WHERE status != 'Cancelled'
        GROUP BY month
        ORDER BY month
        """)
        order_data = cursor.fetchall()
        
        # 월별 판매 데이터
        cursor.execute("""
        SELECT DATE_FORMAT(sale_date, '%Y-%m') as month, SUM(total_amount) as total
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
                        "INSERT INTO parts (part_code, part_name, supplier, unit_price, lead_time, stock, min_stock) VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
                "SELECT part_code, part_name, supplier, unit_price, lead_time, stock, min_stock FROM parts WHERE id = %s",
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
                            "UPDATE parts SET part_code = %s, part_name = %s, supplier = %s, unit_price = %s, lead_time = %s, stock = %s, min_stock = %s WHERE id = %s",
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
            
            st.dataframe(orders_df.style.applymap(highlight_status, subset=['상태']), use_container_width=True)
            
            # 주문 상세 정보 표시
            st.subheader("주문 상세 정보")
            selected_order = st.selectbox("주문 선택", orders_df['주문번호'].tolist())
            
            if selected_order:
                order_id = int(orders_df.loc[orders_df['주문번호'] == selected_order, 'ID'].iloc[0])
                
                cursor.execute("""
                SELECT od.id, p.part_code, p.part_name, p.part_category, od.quantity, od.unit_price, (od.quantity * od.unit_price) as subtotal
                FROM order_details od
                JOIN parts p ON od.part_id = p.id
                WHERE od.order_id = %s
                """, (order_id,))
                order_details = cursor.fetchall()
                
                if order_details:
                    details_df = pd.DataFrame(order_details, 
                                            columns=['ID', '부품 코드', '부품명', '카테고리', '수량', '단가(₩)', '소계(₩)'])
                    st.dataframe(details_df, use_container_width=True)
                    
                    total_amount = float(details_df['소계(₩)'].sum())
                    st.metric("주문 총액", f"₩{total_amount:,.0f}")
                else:
                    st.info("이 주문에 대한 상세 정보가 없습니다.")
        else:
            st.info("등록된 주문이 없습니다.")
    
    with tab2:
        st.subheader("새 주문 생성")
        
        today = datetime.now().date()
        
        with st.form("new_order_form"):
            order_number = st.text_input("주문번호", value=f"ORD-{today.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}")
            order_date = st.date_input("주문일자", value=today)
            expected_arrival = st.date_input("예상도착일", value=today + timedelta(days=14))
            
            # 부품 선택을 위한 멀티셀렉트
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, part_code, part_name, part_category, unit_price 
                FROM parts 
                ORDER BY part_category, part_code
            """)
            available_parts = cursor.fetchall()
            
            if available_parts:
                part_options = {f"{p[1]} - {p[2]} ({p[3]}) (₩{p[4]:,.0f})": p[0] for p in available_parts}
                selected_parts = st.multiselect("주문할 부품 선택", list(part_options.keys()))
                
                quantities = {}
                total_amount = 0
                
                if selected_parts:
                    st.write("각 부품의 주문 수량을 입력하세요:")
                    
                    for part in selected_parts:
                        part_id = int(part_options[part])
                        part_name = part.split(' - ')[1].split(' (')[0]
                        
                        cursor.execute("SELECT unit_price FROM parts WHERE id = %s", (part_id,))
                        unit_price = float(cursor.fetchone()[0])
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(part)
                        with col2:
                            quantity = int(st.number_input(f"{part_name} 수량", min_value=1, value=10, key=f"qty_{part_id}"))
                            quantities[part_id] = quantity
                            total_amount += quantity * unit_price
                
                st.metric("주문 총액", f"₩{float(total_amount):,.0f}")
                
                submitted = st.form_submit_button("주문 생성")
                
                if submitted:
                    if not selected_parts:
                        st.error("최소한 하나 이상의 부품을 선택해야 합니다.")
                    else:
                        cursor.execute(
                            "INSERT INTO orders (order_number, order_date, expected_arrival, status, total_amount) VALUES (%s, %s, %s, %s, %s)",
                            (order_number, order_date, expected_arrival, "Pending", float(total_amount))
                        )
                        conn.commit()
                        
                        cursor.execute("SELECT LAST_INSERT_ID()")
                        order_id = int(cursor.fetchone()[0])
                        
                        for part_id, quantity in quantities.items():
                            cursor.execute("SELECT unit_price FROM parts WHERE id = %s", (int(part_id),))
                            unit_price = float(cursor.fetchone()[0])
                            
                            cursor.execute(
                                "INSERT INTO order_details (order_id, part_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                                (order_id, part_id, quantity, unit_price)
                            )
                        
                        conn.commit()
                        st.success(f"주문 '{order_number}' 생성 완료!")
            else:
                st.error("등록된 부품이 없습니다. 먼저 부품을 등록해주세요.")
    
    with tab3:
        st.subheader("주문 상태 관리")
        
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
            
            active_orders_df['주문일자'] = pd.to_datetime(active_orders_df['주문일자']).dt.strftime('%Y-%m-%d')
            active_orders_df['예상도착일'] = pd.to_datetime(active_orders_df['예상도착일']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(active_orders_df, use_container_width=True)
            
            st.write("주문 상태 업데이트")
            
            col1, col2 = st.columns(2)
            
            with col1:
                order_to_update = st.selectbox("업데이트할 주문 선택", active_orders_df['주문번호'].tolist())
            
            with col2:
                new_status = st.selectbox("새 상태", ["Pending", "Shipped", "Delivered", "Cancelled"])
            
            if st.button("상태 업데이트"):
                order_id = int(active_orders_df.loc[active_orders_df['주문번호'] == order_to_update, 'ID'].iloc[0])
                
                cursor.execute(
                    "UPDATE orders SET status = %s WHERE id = %s",
                    (new_status, order_id)
                )
                conn.commit()
                
                if new_status == "Delivered":
                    cursor.execute("""
                    SELECT part_id, quantity
                    FROM order_details
                    WHERE order_id = %s
                    """, (order_id,))
                    order_details = cursor.fetchall()
                    
                    for part_id, quantity in order_details:
                        cursor.execute(
                            "UPDATE parts SET stock = stock + %s WHERE id = %s",
                            (int(quantity), int(part_id))
                        )
                    
                    conn.commit()
                    st.success(f"주문 '{order_to_update}' 상태가 '{new_status}'로 변경되었습니다. 부품 재고가 업데이트되었습니다.")
                else:
                    st.success(f"주문 '{order_to_update}' 상태가 '{new_status}'로 변경되었습니다.")
        else:
            st.info("대기 중이거나 배송 중인 주문이 없습니다.")

# 생산 관리 페이지
def display_production_management(conn):
    """생산 관리 대시보드"""
    st.header("생산 관리")
    
    # 생산 현황 조회
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            p.batch_number,
            pr.product_name,
            p.quantity,
            p.start_date,
            p.end_date,
            p.status
        FROM production p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.start_date DESC
    """)
    productions = cursor.fetchall()
    
    # 생산 현황 표시
    if productions:
        df = pd.DataFrame(productions)
        
        # 상태별 색상 지정
        def highlight_status(val):
            color = 'lightgray'
            if val == 'Completed':
                color = 'lightgreen'
            elif val == 'In Progress':
                color = 'lightblue'
            elif val == 'Delayed':
                color = 'lightcoral'
            return f'background-color: {color}'
        
        st.dataframe(
            df.style.applymap(highlight_status, subset=['status']),
            use_container_width=True
        )
        
        # 부족 부품 확인
        shortage = False  # Initialize shortage variable
        for production in productions:
            if production['status'] == 'Delayed':
                shortage = True
                break
        
        if shortage:
            st.warning("⚠️ 일부 생산이 지연되고 있습니다. 부품 재고를 확인해주세요.")
            
            # 부족 부품 목록 조회
            cursor.execute("""
                SELECT 
                    pa.part_name,
                    pa.stock,
                    pa.min_stock
                FROM parts pa
                WHERE pa.stock < pa.min_stock
            """)
            shortage_parts = cursor.fetchall()
            
            if shortage_parts:
                st.subheader("부족 부품 목록")
                shortage_df = pd.DataFrame(shortage_parts)
                st.dataframe(shortage_df, use_container_width=True)
    
    else:
        st.info("생산 데이터가 없습니다.")
    
    cursor.close()

# 판매 관리 페이지
def display_sales_management(conn):
    """판매 관리 페이지"""
    st.title("판매 관리")
    
    tab1, tab2 = st.tabs(["판매 기록", "새 판매 등록"])
    
    with tab1:
        st.subheader("판매 기록")
        
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
            
            # 데이터프레임 표시
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("등록된 판매 기록이 없습니다.")
    
    with tab2:
        st.subheader("새 판매 등록")
        
        with st.form("new_sale_form"):
            today = datetime.now().date()
            invoice_number = st.text_input("송장번호", value=f"INV-{today.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}")
            sale_date = st.date_input("판매일자", value=today)
            customer = st.text_input("고객명")
            
            # 제품 선택
            cursor = conn.cursor()
            cursor.execute("SELECT id, product_code, product_name, selling_price, stock FROM products ORDER BY product_name")
            products = cursor.fetchall()
            
            if products:
                product_options = {f"{p[1]} - {p[2]} (₩{p[3]:,.0f}) (재고: {p[4]}개)": p[0] for p in products}
                selected_product = st.selectbox("제품 선택", list(product_options.keys()))
                
                if selected_product:
                    product_id = product_options[selected_product]
                    
                    # 선택한 제품의 재고 확인
                    cursor.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
                    current_stock = cursor.fetchone()[0]
                    
                    quantity = st.number_input("수량", min_value=1, max_value=current_stock, value=1)
                    
                    # 선택한 제품의 단가 조회
                    cursor.execute("SELECT selling_price FROM products WHERE id = %s", (product_id,))
                    unit_price = float(cursor.fetchone()[0])
                    total_amount = quantity * unit_price
                    
                    st.metric("총 판매액", f"₩{total_amount:,.0f}")
                    
                    payment_method = st.selectbox("결제방법", ["현금", "카드", "계좌이체", "기타"])
                    notes = st.text_area("비고")
                    
                    submitted = st.form_submit_button("판매 등록")
                    
                    if submitted:
                        if not customer:
                            st.error("고객명을 입력해주세요.")
                        else:
                            try:
                                # 트랜잭션 시작
                                conn.start_transaction()
                                
                                # 판매 기록 추가
                                cursor.execute("""
                                    INSERT INTO sales (
                                        invoice_number, sale_date, customer, product_id, quantity,
                                        unit_price, total_amount, payment_method, notes
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (invoice_number, sale_date, customer, product_id, quantity,
                                      unit_price, total_amount, payment_method, notes))
                                
                                # 제품 재고 업데이트
                                cursor.execute("""
                                    UPDATE products SET stock = stock - %s WHERE id = %s
                                """, (quantity, product_id))
                                
                                # 트랜잭션 커밋
                                conn.commit()
                                st.success("판매가 등록되었습니다.")
                                st.rerun()
                                
                            except mysql.connector.Error as err:
                                # 에러 발생 시 롤백
                                conn.rollback()
                                st.error(f"판매 등록 중 오류 발생: {err}")
                            finally:
                                cursor.close()
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
- 기반 기술: Python, Streamlit, MySQL""")
    
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

def display_products_management(conn):
    """제품 관리 페이지"""
    st.title("제품 관리")
    
    tab1, tab2 = st.tabs(["제품 목록", "제품 추가/수정"])
    
    with tab1:
        st.subheader("제품 목록")
        
        # 제품 데이터 조회
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, product_code, product_name, product_type, size, brand, 
               selling_price, production_cost, stock
        FROM products
        ORDER BY product_code
        """)
        products_data = cursor.fetchall()
        
        if products_data:
            products_df = pd.DataFrame(products_data, 
                                    columns=['ID', '제품 코드', '제품명', '제품 유형', '크기', '브랜드', 
                                            '판매가(₩)', '생산비용(₩)', '재고'])
            
            # 데이터프레임 표시
            st.dataframe(products_df, use_container_width=True)
            
            # 제품별 재고 차트
            st.subheader("제품별 재고 상태")
            
            fig = px.bar(products_df, 
                       x='제품명', y='재고',
                       title='제품별 재고 수준',
                       color='재고',
                       labels={'제품명': '제품명', '재고': '재고 수량'})
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 제품별 수익성 분석
            st.subheader("제품별 수익성 분석")
            
            # 마진 계산
            products_df['마진(₩)'] = products_df['판매가(₩)'] - products_df['생산비용(₩)']
            products_df['마진율(%)'] = (products_df['마진(₩)'] / products_df['판매가(₩)'] * 100).round(1)
            
            # 수익성 차트
            fig = px.bar(products_df, 
                       x='제품명', y='마진(₩)',
                       title='제품별 마진',
                       color='마진율(%)',
                       labels={'제품명': '제품명', '마진(₩)': '마진(₩)'})
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 상세 수익성 테이블
            st.dataframe(products_df[['제품명', '판매가(₩)', '생산비용(₩)', '마진(₩)', '마진율(%)']], 
                        use_container_width=True)
        else:
            st.info("등록된 제품이 없습니다.")
    
    with tab2:
        st.subheader("제품 추가/수정")
        
        # 제품 추가 폼
        with st.form("product_form"):
            st.write("새 제품 등록")
            product_code = st.text_input("제품 코드")
            product_name = st.text_input("제품명")
            product_type = st.selectbox("제품 유형", ["고정식", "개폐식", "자동식"])
            size = st.text_input("크기")
            brand = st.text_input("브랜드", value="YUER")
            selling_price = st.number_input("판매가(₩)", min_value=0.0, step=0.1)
            production_cost = st.number_input("생산비용(₩)", min_value=0.0, step=0.1)
            stock = st.number_input("초기 재고", min_value=0, step=1)
            
            submitted = st.form_submit_button("제품 추가")
            
            if submitted:
                if not product_code or not product_name:
                    st.error("제품 코드와 제품명은 필수입니다.")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO products (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock)
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
                "SELECT product_code, product_name, product_type, size, brand, selling_price, production_cost, stock FROM products WHERE id = %s",
                (product_id,)
            )
            product_data = cursor.fetchone()
            
            if product_data:
                with st.form("edit_product_form"):
                    st.write(f"'{product_data[1]}' 정보 수정")
                    
                    edit_product_code = st.text_input("제품 코드", value=product_data[0])
                    edit_product_name = st.text_input("제품명", value=product_data[1])
                    edit_product_type = st.selectbox("제품 유형", ["고정식", "개폐식", "자동식"], 
                                                  index=["고정식", "개폐식", "자동식"].index(product_data[2]))
                    edit_size = st.text_input("크기", value=product_data[3])
                    edit_brand = st.text_input("브랜드", value=product_data[4])
                    edit_selling_price = st.number_input("판매가(₩)", min_value=0.0, step=0.1, value=float(product_data[5]))
                    edit_production_cost = st.number_input("생산비용(₩)", min_value=0.0, step=0.1, value=float(product_data[6]))
                    edit_stock = st.number_input("재고", min_value=0, step=1, value=int(product_data[7]))
                    
                    update_submitted = st.form_submit_button("정보 업데이트")
                    
                    if update_submitted:
                        cursor.execute(
                            "UPDATE products SET product_code = %s, product_name = %s, product_type = %s, size = %s, brand = %s, selling_price = %s, production_cost = %s, stock = %s WHERE id = %s",
                            (edit_product_code, edit_product_name, edit_product_type, edit_size, edit_brand, 
                             edit_selling_price, edit_production_cost, edit_stock, product_id)
                        )
                        conn.commit()
                        st.success(f"제품 '{edit_product_name}' 정보 업데이트 완료!")
        else:
            st.info("등록된 제품이 없습니다.")

if __name__ == "__main__":
    main() 