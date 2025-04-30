import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# ... existing code ...

# 제품 등록
def create_product(product_data):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products_logistics 
            (supplier_id, product_code, product_name, unit_price, 
             moq, lead_time, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            product_data['supplier_id'], product_data['product_code'],
            product_data['product_name'], product_data['unit_price'],
            product_data['moq'], product_data['lead_time'],
            product_data['notes']
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
        ["PI/CI 현황", "제품 등록", "PI 등록", "CI 등록", "PI 목록", "CI 목록", "배송 현황", "배송 현황 등록"]
    )

    # ... existing code ...

    elif menu == "제품 등록":
        st.header("제품 등록")
        
        # 공급업체 선택
        suppliers = get_suppliers()
        selected_supplier = st.selectbox(
            "공급업체 선택",
            options=suppliers,
            format_func=lambda x: x['supplier_name']
        )
        
        if selected_supplier:
            with st.form("product_form"):
                col1, col2 = st.columns(2)
                with col1:
                    product_code = st.text_input("제품 코드")
                    product_name = st.text_input("제품명")
                    unit_price = st.number_input("기준 단가", min_value=0.0, format="%.2f")
                
                with col2:
                    moq = st.number_input("최소 주문 수량", min_value=1)
                    lead_time = st.number_input("리드타임 (일)", min_value=1)
                    notes = st.text_area("비고")
                
                if st.form_submit_button("제품 등록"):
                    if not product_code or not product_name:
                        st.error("필수 항목을 모두 입력해주세요.")
                    else:
                        product_data = {
                            'supplier_id': selected_supplier['supplier_id'],
                            'product_code': product_code,
                            'product_name': product_name,
                            'unit_price': unit_price,
                            'moq': moq,
                            'lead_time': lead_time,
                            'notes': notes
                        }
                        
                        success, result = create_product(product_data)
                        if success:
                            st.success("제품이 성공적으로 등록되었습니다.")
                        else:
                            st.error(f"제품 등록 중 오류가 발생했습니다: {result}")
            
            # 등록된 제품 목록 표시
            st.subheader(f"{selected_supplier['supplier_name']} 등록 제품 목록")
            products = get_products(selected_supplier['supplier_id'])
            if products:
                product_df = pd.DataFrame(products)
                product_df = product_df[[
                    'product_code', 'product_name', 'unit_price', 
                    'moq', 'lead_time', 'notes'
                ]]
                product_df.columns = [
                    '제품 코드', '제품명', '기준 단가', 
                    '최소 주문 수량', '리드타임', '비고'
                ]
                st.dataframe(product_df)
            else:
                st.info("등록된 제품이 없습니다.")

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
            # 제품 목록 미리 로드
            products = get_products(selected_supplier['supplier_id'])
            if not products:
                st.warning(f"{selected_supplier['supplier_name']}의 등록된 제품이 없습니다. 먼저 제품을 등록해주세요.")
                if st.button("제품 등록 페이지로 이동"):
                    st.switch_page("pages/09_📦_물류관리_PI_CI.py")  # 현재 페이지 다시 로드 (제품 등록 메뉴)
            else:
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
                    num_products = st.number_input("제품 수", min_value=1, value=1)
                    
                    items_data = []
                    for i in range(num_products):
                        st.markdown(f"##### 제품 {i+1}")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            product = st.selectbox(
                                "제품 선택",
                                options=products,
                                format_func=lambda x: f"{x['product_code']} - {x['product_name']}",
                                key=f"product_{i}"
                            )
                        with col2:
                            quantity = st.number_input(
                                "수량",
                                min_value=product['moq'] if product else 1,
                                value=product['moq'] if product else 1,
                                key=f"quantity_{i}"
                            )
                        with col3:
                            unit_price = st.number_input(
                                "단가",
                                min_value=0.0,
                                value=float(product['unit_price']) if product else 0.0,
                                format="%.2f",
                                key=f"price_{i}"
                            )
                        with col4:
                            default_date = date.today()
                            if product:
                                default_date = date.today() + pd.Timedelta(days=int(product['lead_time']))
                            expected_prod_date = st.date_input(
                                "예상 생산일",
                                value=default_date,
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

    # ... rest of the code ... 