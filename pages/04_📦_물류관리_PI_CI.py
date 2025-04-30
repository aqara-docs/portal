import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="PI/CI 관리 시스템",
    page_icon="📦",
    layout="wide"
)

# 데이터베이스 연결
def connect_to_db():
    return mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )

# 공급업체 목록 가져오기
def get_suppliers():
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM suppliers ORDER BY supplier_name")
    suppliers = cursor.fetchall()
    cursor.close()
    conn.close()
    return suppliers

# 제품 목록 가져오기
def get_products(supplier_id=None):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    if supplier_id:
        cursor.execute("""
            SELECT * FROM products_logistics 
            WHERE supplier_id = %s 
            ORDER BY product_name
        """, (supplier_id,))
    else:
        cursor.execute("SELECT * FROM products_logistics ORDER BY product_name")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return products

# PI 생성
def create_pi(pi_data, items_data):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # PI 기본 정보 저장
        cursor.execute("""
            INSERT INTO proforma_invoices 
            (pi_number, supplier_id, issue_date, expected_delivery_date, 
             total_amount, currency, status, payment_terms, shipping_terms, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            pi_data['pi_number'], pi_data['supplier_id'], pi_data['issue_date'],
            pi_data['expected_delivery_date'], pi_data['total_amount'],
            pi_data['currency'], pi_data['status'], pi_data['payment_terms'],
            pi_data['shipping_terms'], pi_data['notes']
        ))
        pi_id = cursor.lastrowid
        
        # PI 항목 저장
        for item in items_data:
            cursor.execute("""
                INSERT INTO pi_items 
                (pi_id, product_id, quantity, unit_price, total_price, 
                 expected_production_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                pi_id, item['product_id'], item['quantity'],
                item['unit_price'], item['total_price'],
                item['expected_production_date'], 'pending'
            ))
        
        conn.commit()
        return True, pi_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

# CI 생성
def create_ci(ci_data, items_data):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # CI 기본 정보 저장
        cursor.execute("""
            INSERT INTO commercial_invoices 
            (ci_number, pi_id, supplier_id, issue_date, actual_delivery_date,
             total_amount, currency, status, shipping_details, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ci_data['ci_number'], ci_data['pi_id'], ci_data['supplier_id'],
            ci_data['issue_date'], ci_data['actual_delivery_date'],
            ci_data['total_amount'], ci_data['currency'], ci_data['status'],
            ci_data['shipping_details'], ci_data['notes']
        ))
        ci_id = cursor.lastrowid
        
        # CI 항목 저장
        for item in items_data:
            cursor.execute("""
                INSERT INTO ci_items 
                (ci_id, pi_item_id, product_id, quantity, unit_price, 
                 total_price, actual_production_date, shipping_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ci_id, item['pi_item_id'], item['product_id'],
                item['quantity'], item['unit_price'], item['total_price'],
                item['actual_production_date'], item['shipping_date'],
                item['notes']
            ))
        
        conn.commit()
        return True, ci_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

# PI 목록 가져오기
def get_pi_list(supplier_id=None, status=None):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT pi.*, s.supplier_name
        FROM proforma_invoices pi
        JOIN suppliers s ON pi.supplier_id = s.supplier_id
        WHERE 1=1
    """
    params = []
    
    if supplier_id:
        query += " AND pi.supplier_id = %s"
        params.append(supplier_id)
    if status:
        query += " AND pi.status = %s"
        params.append(status)
    
    query += " ORDER BY pi.created_at DESC"
    
    cursor.execute(query, params)
    pi_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return pi_list

# CI 목록 가져오기
def get_ci_list(supplier_id=None, status=None):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT ci.*, s.supplier_name, pi.pi_number
        FROM commercial_invoices ci
        JOIN suppliers s ON ci.supplier_id = s.supplier_id
        LEFT JOIN proforma_invoices pi ON ci.pi_id = pi.pi_id
        WHERE 1=1
    """
    params = []
    
    if supplier_id:
        query += " AND ci.supplier_id = %s"
        params.append(supplier_id)
    if status:
        query += " AND ci.status = %s"
        params.append(status)
    
    query += " ORDER BY ci.created_at DESC"
    
    cursor.execute(query, params)
    ci_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return ci_list

# PI 상세 정보 가져오기
def get_pi_details(pi_id):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    # PI 기본 정보
    cursor.execute("""
        SELECT pi.*, s.supplier_name
        FROM proforma_invoices pi
        JOIN suppliers s ON pi.supplier_id = s.supplier_id
        WHERE pi.pi_id = %s
    """, (pi_id,))
    pi_info = cursor.fetchone()
    
    # PI 항목 정보
    cursor.execute("""
        SELECT pi_items.*, p.product_name, p.product_code
        FROM pi_items
        JOIN products_logistics p ON pi_items.product_id = p.product_id
        WHERE pi_items.pi_id = %s
    """, (pi_id,))
    pi_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return pi_info, pi_items

# CI 상세 정보 가져오기
def get_ci_details(ci_id):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    # CI 기본 정보
    cursor.execute("""
        SELECT ci.*, s.supplier_name, pi.pi_number
        FROM commercial_invoices ci
        JOIN suppliers s ON ci.supplier_id = s.supplier_id
        LEFT JOIN proforma_invoices pi ON ci.pi_id = pi.pi_id
        WHERE ci.ci_id = %s
    """, (ci_id,))
    ci_info = cursor.fetchone()
    
    # CI 항목 정보
    cursor.execute("""
        SELECT ci_items.*, p.product_name, p.product_code,
               pi_items.expected_production_date
        FROM ci_items
        JOIN products_logistics p ON ci_items.product_id = p.product_id
        LEFT JOIN pi_items ON ci_items.pi_item_id = pi_items.pi_item_id
        WHERE ci_items.ci_id = %s
    """, (ci_id,))
    ci_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return ci_info, ci_items

# 배송 현황 생성
def create_shipment(shipment_data):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO shipment_tracking 
            (ci_id, tracking_number, carrier, shipping_date, 
             estimated_arrival_date, actual_arrival_date, status, 
             current_location, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            shipment_data['ci_id'], shipment_data['tracking_number'],
            shipment_data['carrier'], shipment_data['shipping_date'],
            shipment_data['estimated_arrival_date'], 
            shipment_data['actual_arrival_date'],
            shipment_data['status'], shipment_data['current_location'],
            shipment_data['notes']
        ))
        
        conn.commit()
        return True, cursor.lastrowid
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("📦 PI/CI 관리 시스템")
    
    # 메뉴 선택
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["PI/CI 현황", "PI 등록", "CI 등록", "PI 목록", "CI 목록", "배송 현황", "배송 현황 등록"]
    )
    
    if menu == "PI/CI 현황":
        st.header("PI/CI 현황")
        
        # 현황 요약 통계
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("진행 중인 PI", len(get_pi_list(status='confirmed')))
        with col2:
            st.metric("진행 중인 CI", len(get_ci_list(status='issued')))
        with col3:
            # 지연된 항목 계산
            conn = connect_to_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM pi_items WHERE status = 'delayed'
            """)
            delayed_items = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            st.metric("지연된 항목", delayed_items, delta=None, delta_color="inverse")
        
        # 공급업체별 현황
        st.subheader("공급업체별 현황")
        suppliers = get_suppliers()
        
        # 데이터 수집
        supplier_data = []
        for supplier in suppliers:
            pi_count = len(get_pi_list(supplier['supplier_id']))
            ci_count = len(get_ci_list(supplier['supplier_id']))
            supplier_data.append({
                'supplier': supplier['supplier_name'],
                'PI 건수': pi_count,
                'CI 건수': ci_count
            })
        
        df = pd.DataFrame(supplier_data)
        
        # 차트 생성
        fig = go.Figure(data=[
            go.Bar(name='PI', x=df['supplier'], y=df['PI 건수']),
            go.Bar(name='CI', x=df['supplier'], y=df['CI 건수'])
        ])
        fig.update_layout(barmode='group')
        st.plotly_chart(fig)
        
        # 최근 지연 항목
        st.subheader("최근 지연 항목")
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT pi_items.*, p.product_name, s.supplier_name, 
                   pi.pi_number, pi.expected_delivery_date
            FROM pi_items
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            JOIN proforma_invoices pi ON pi_items.pi_id = pi.pi_id
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            WHERE pi_items.status = 'delayed'
            ORDER BY pi_items.updated_at DESC
            LIMIT 10
        """)
        delayed_items = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if delayed_items:
            for item in delayed_items:
                with st.expander(f"{item['supplier_name']} - {item['product_name']}"):
                    st.write(f"PI 번호: {item['pi_number']}")
                    st.write(f"예상 납기일: {item['expected_delivery_date']}")
                    st.write(f"지연 사유: {item['delay_reason']}")
    
    elif menu == "PI 등록":
        st.header("PI 등록")
        
        # 공급업체 선택
        suppliers = get_suppliers()
        selected_supplier = st.selectbox(
            "공급업체 선택",
            options=suppliers,
            format_func=lambda x: x['supplier_name']
        )
        
        if selected_supplier:
            with st.form("pi_form"):
                # PI 기본 정보
                col1, col2 = st.columns(2)
                with col1:
                    pi_number = st.text_input("PI 번호")
                    issue_date = st.date_input("발행일")
                    currency = st.selectbox("통화", ["USD", "CNY", "EUR"])
                
                with col2:
                    expected_delivery_date = st.date_input("예상 납기일")
                    payment_terms = st.text_area("지불 조건")
                    shipping_terms = st.text_area("선적 조건")
                
                # 제품 선택 및 수량 입력
                st.subheader("제품 목록")
                products = get_products(selected_supplier['supplier_id'])
                
                items_data = []
                for i in range(st.number_input("제품 수", min_value=1, value=1)):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        product = st.selectbox(
                            f"제품 {i+1}",
                            options=products,
                            format_func=lambda x: x['product_name'],
                            key=f"product_{i}"
                        )
                    with col2:
                        quantity = st.number_input(
                            "수량",
                            min_value=1,
                            key=f"quantity_{i}"
                        )
                    with col3:
                        unit_price = st.number_input(
                            "단가",
                            min_value=0.0,
                            format="%.2f",
                            key=f"price_{i}"
                        )
                    with col4:
                        expected_prod_date = st.date_input(
                            "예상 생산일",
                            key=f"prod_date_{i}"
                        )
                    
                    if product:
                        items_data.append({
                            'product_id': product['product_id'],
                            'quantity': quantity,
                            'unit_price': unit_price,
                            'total_price': quantity * unit_price,
                            'expected_production_date': expected_prod_date
                        })
                
                notes = st.text_area("비고")
                
                if st.form_submit_button("PI 등록"):
                    if not pi_number or not items_data:
                        st.error("필수 항목을 모두 입력해주세요.")
                    else:
                        total_amount = sum(item['total_price'] for item in items_data)
                        pi_data = {
                            'pi_number': pi_number,
                            'supplier_id': selected_supplier['supplier_id'],
                            'issue_date': issue_date,
                            'expected_delivery_date': expected_delivery_date,
                            'total_amount': total_amount,
                            'currency': currency,
                            'status': 'draft',
                            'payment_terms': payment_terms,
                            'shipping_terms': shipping_terms,
                            'notes': notes
                        }
                        
                        success, result = create_pi(pi_data, items_data)
                        if success:
                            st.success("PI가 성공적으로 등록되었습니다.")
                        else:
                            st.error(f"PI 등록 중 오류가 발생했습니다: {result}")
    
    elif menu == "CI 등록":
        st.header("CI 등록")
        
        # PI 선택
        pi_list = get_pi_list(status='confirmed')
        selected_pi = st.selectbox(
            "PI 선택",
            options=pi_list,
            format_func=lambda x: f"{x['pi_number']} ({x['supplier_name']})"
        )
        
        if selected_pi:
            pi_info, pi_items = get_pi_details(selected_pi['pi_id'])
            
            with st.form("ci_form"):
                # CI 기본 정보
                col1, col2 = st.columns(2)
                with col1:
                    ci_number = st.text_input("CI 번호")
                    issue_date = st.date_input("발행일")
                    actual_delivery_date = st.date_input("실제 납기일")
                
                with col2:
                    shipping_details = st.text_area("선적 정보")
                    notes = st.text_area("비고")
                
                # PI 항목에 대한 CI 항목 입력
                st.subheader("제품 목록")
                items_data = []
                for pi_item in pi_items:
                    st.write(f"제품: {pi_item['product_name']}")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        quantity = st.number_input(
                            "수량",
                            min_value=0,
                            max_value=pi_item['quantity'],
                            value=pi_item['quantity'],
                            key=f"qty_{pi_item['pi_item_id']}"
                        )
                    with col2:
                        actual_prod_date = st.date_input(
                            "실제 생산일",
                            key=f"prod_{pi_item['pi_item_id']}"
                        )
                    with col3:
                        shipping_date = st.date_input(
                            "선적일",
                            key=f"ship_{pi_item['pi_item_id']}"
                        )
                    
                    item_notes = st.text_input(
                        "항목 비고",
                        key=f"note_{pi_item['pi_item_id']}"
                    )
                    
                    items_data.append({
                        'pi_item_id': pi_item['pi_item_id'],
                        'product_id': pi_item['product_id'],
                        'quantity': quantity,
                        'unit_price': pi_item['unit_price'],
                        'total_price': quantity * pi_item['unit_price'],
                        'actual_production_date': actual_prod_date,
                        'shipping_date': shipping_date,
                        'notes': item_notes
                    })
                
                if st.form_submit_button("CI 등록"):
                    if not ci_number or not items_data:
                        st.error("필수 항목을 모두 입력해주세요.")
                    else:
                        total_amount = sum(item['total_price'] for item in items_data)
                        ci_data = {
                            'ci_number': ci_number,
                            'pi_id': selected_pi['pi_id'],
                            'supplier_id': selected_pi['supplier_id'],
                            'issue_date': issue_date,
                            'actual_delivery_date': actual_delivery_date,
                            'total_amount': total_amount,
                            'currency': selected_pi['currency'],
                            'status': 'draft',
                            'shipping_details': shipping_details,
                            'notes': notes
                        }
                        
                        success, result = create_ci(ci_data, items_data)
                        if success:
                            st.success("CI가 성공적으로 등록되었습니다.")
                        else:
                            st.error(f"CI 등록 중 오류가 발생했습니다: {result}")
    
    elif menu == "PI 목록":
        st.header("PI 목록")
        
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            filter_supplier = st.selectbox(
                "공급업체 필터",
                options=[None] + get_suppliers(),
                format_func=lambda x: "전체" if x is None else x['supplier_name']
            )
        with col2:
            filter_status = st.selectbox(
                "상태 필터",
                options=[None, 'draft', 'sent', 'confirmed', 'completed', 'cancelled'],
                format_func=lambda x: "전체" if x is None else x.upper()
            )
        
        # PI 목록 표시
        pi_list = get_pi_list(
            supplier_id=filter_supplier['supplier_id'] if filter_supplier else None,
            status=filter_status
        )
        
        for pi in pi_list:
            with st.expander(f"{pi['pi_number']} - {pi['supplier_name']} ({pi['status'].upper()})"):
                pi_info, pi_items = get_pi_details(pi['pi_id'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"발행일: {pi_info['issue_date']}")
                    st.write(f"예상 납기일: {pi_info['expected_delivery_date']}")
                    st.write(f"총액: {pi_info['total_amount']} {pi_info['currency']}")
                
                with col2:
                    st.write(f"지불 조건: {pi_info['payment_terms']}")
                    st.write(f"선적 조건: {pi_info['shipping_terms']}")
                    st.write(f"비고: {pi_info['notes']}")
                
                # 제품 목록 표시
                st.write("### 제품 목록")
                for item in pi_items:
                    st.write(f"""
                    - {item['product_name']} ({item['product_code']})
                      * 수량: {item['quantity']}
                      * 단가: {item['unit_price']} {pi_info['currency']}
                      * 합계: {item['total_price']} {pi_info['currency']}
                      * 예상 생산일: {item['expected_production_date']}
                      * 상태: {item['status'].upper()}
                    """)
    
    elif menu == "CI 목록":
        st.header("CI 목록")
        
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            filter_supplier = st.selectbox(
                "공급업체 필터",
                options=[None] + get_suppliers(),
                format_func=lambda x: "전체" if x is None else x['supplier_name']
            )
        with col2:
            filter_status = st.selectbox(
                "상태 필터",
                options=[None, 'draft', 'issued', 'shipped', 'delivered', 'completed'],
                format_func=lambda x: "전체" if x is None else x.upper()
            )
        
        # CI 목록 표시
        ci_list = get_ci_list(
            supplier_id=filter_supplier['supplier_id'] if filter_supplier else None,
            status=filter_status
        )
        
        for ci in ci_list:
            with st.expander(f"{ci['ci_number']} - {ci['supplier_name']} ({ci['status'].upper()})"):
                ci_info, ci_items = get_ci_details(ci['ci_id'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"PI 번호: {ci_info['pi_number']}")
                    st.write(f"발행일: {ci_info['issue_date']}")
                    st.write(f"실제 납기일: {ci_info['actual_delivery_date']}")
                    st.write(f"총액: {ci_info['total_amount']} {ci_info['currency']}")
                
                with col2:
                    st.write(f"선적 정보: {ci_info['shipping_details']}")
                    st.write(f"비고: {ci_info['notes']}")
                
                # 제품 목록 표시
                st.write("### 제품 목록")
                for item in ci_items:
                    st.write(f"""
                    - {item['product_name']} ({item['product_code']})
                      * 수량: {item['quantity']}
                      * 단가: {item['unit_price']} {ci_info['currency']}
                      * 합계: {item['total_price']} {ci_info['currency']}
                      * 예상 생산일: {item['expected_production_date']}
                      * 실제 생산일: {item['actual_production_date']}
                      * 선적일: {item['shipping_date']}
                    """)
    
    elif menu == "배송 현황":
        st.header("배송 현황")
        
        # 배송 현황 요약
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        # 상태별 배송 건수
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM shipment_tracking
            GROUP BY status
        """)
        status_counts = cursor.fetchall()
        
        # 차트 데이터 준비
        status_labels = []
        status_values = []
        for status in status_counts:
            status_labels.append(status['status'].upper())
            status_values.append(status['count'])
        
        # 도넛 차트 생성
        fig = go.Figure(data=[go.Pie(
            labels=status_labels,
            values=status_values,
            hole=.3
        )])
        st.plotly_chart(fig)
        
        # 최근 배송 현황
        st.subheader("최근 배송 현황")
        cursor.execute("""
            SELECT st.*, ci.ci_number, s.supplier_name
            FROM shipment_tracking st
            JOIN commercial_invoices ci ON st.ci_id = ci.ci_id
            JOIN suppliers s ON ci.supplier_id = s.supplier_id
            ORDER BY st.shipping_date DESC
            LIMIT 10
        """)
        recent_shipments = cursor.fetchall()
        
        for shipment in recent_shipments:
            with st.expander(f"{shipment['ci_number']} - {shipment['supplier_name']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"운송장 번호: {shipment['tracking_number']}")
                    st.write(f"운송사: {shipment['carrier']}")
                    st.write(f"상태: {shipment['status'].upper()}")
                
                with col2:
                    st.write(f"선적일: {shipment['shipping_date']}")
                    st.write(f"예상 도착일: {shipment['estimated_arrival_date']}")
                    st.write(f"실제 도착일: {shipment['actual_arrival_date']}")
                
                st.write(f"현재 위치: {shipment['current_location']}")
                st.write(f"비고: {shipment['notes']}")
        
        cursor.close()
        conn.close()

    elif menu == "배송 현황 등록":
        st.header("배송 현황 등록")
        
        # CI 선택
        ci_list = get_ci_list(status='issued')
        selected_ci = st.selectbox(
            "CI 선택",
            options=ci_list,
            format_func=lambda x: f"{x['ci_number']} ({x['supplier_name']})"
        )
        
        if selected_ci:
            with st.form("shipment_form"):
                col1, col2 = st.columns(2)
                with col1:
                    tracking_number = st.text_input("운송장 번호")
                    carrier = st.text_input("운송사")
                    shipping_date = st.date_input("선적일")
                    estimated_arrival_date = st.date_input("예상 도착일")
                
                with col2:
                    actual_arrival_date = st.date_input("실제 도착일", value=None)
                    status = st.selectbox(
                        "상태",
                        options=['preparing', 'in_transit', 'customs', 'delivered', 'delayed']
                    )
                    current_location = st.text_input("현재 위치")
                    notes = st.text_area("비고")
                
                if st.form_submit_button("배송 현황 등록"):
                    if not tracking_number or not carrier:
                        st.error("필수 항목을 모두 입력해주세요.")
                    else:
                        shipment_data = {
                            'ci_id': selected_ci['ci_id'],
                            'tracking_number': tracking_number,
                            'carrier': carrier,
                            'shipping_date': shipping_date,
                            'estimated_arrival_date': estimated_arrival_date,
                            'actual_arrival_date': actual_arrival_date,
                            'status': status,
                            'current_location': current_location,
                            'notes': notes
                        }
                        
                        success, result = create_shipment(shipment_data)
                        if success:
                            st.success("배송 현황이 성공적으로 등록되었습니다.")
                        else:
                            st.error(f"배송 현황 등록 중 오류가 발생했습니다: {result}")

if __name__ == "__main__":
    main() 