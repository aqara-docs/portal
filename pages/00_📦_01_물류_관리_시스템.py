import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import time

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="재고 관리 시스템",
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

# --- 재고 관련 기본 함수들 ---
def get_stock(product_id):
    """제품의 현재 재고 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT COALESCE(stock, 0) as stock, 
                   is_certified, 
                   certificate_number
            FROM inventory_logistics 
            WHERE product_id = %s
        """, (product_id,))
        result = cursor.fetchone()
        # 결과를 명시적으로 읽고 반환
        if result:
            return {
                'stock': int(result['stock']),
                'is_certified': bool(result['is_certified']),
                'certificate_number': result['certificate_number']
            }
        return {'stock': 0, 'is_certified': False, 'certificate_number': None}
    finally:
        # 커서를 닫기 전에 모든 결과를 읽었는지 확인
        while cursor.nextset():
            pass
        cursor.close()
        conn.close()

def update_stock(product_id, quantity_change, change_type, reference_number, notes='', destination=''):
    """재고 업데이트 및 이력 기록"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 1. 재고 업데이트
        cursor.execute("""
            INSERT INTO inventory_logistics 
            (product_id, stock, is_certified)
            VALUES (%s, %s, TRUE)
            ON DUPLICATE KEY UPDATE 
            stock = stock + %s
        """, (product_id, quantity_change, quantity_change))
        
        # 2. 재고 이력 기록
        cursor.execute("""
            INSERT INTO inventory_transactions 
            (product_id, change_type, quantity, 
             destination, notes, reference_number, date)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (
            product_id, change_type, quantity_change,
            destination, notes, reference_number
        ))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

# --- 공급업체 및 제품 관련 함수들 ---
def get_suppliers():
    """공급업체 목록 조회 및 초기화"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. 현재 등록된 공급업체 확인
        cursor.execute("SELECT * FROM suppliers ORDER BY supplier_id")
        suppliers = cursor.fetchall()
        
        # Ewinlight가 없으면 추가
        ewinlight_exists = any(s['supplier_name'] == 'Ewinlight' for s in suppliers)
        if not ewinlight_exists:
            cursor.execute(
                "INSERT INTO suppliers (supplier_name, contact_person, email, phone, address) VALUES (%s, %s, %s, %s, %s)",
                ("Ewinlight", "Ewinlight", "ewinlight@example.com", "123-456-7896", "Ewinlight Address")
            )
            conn.commit()
            # 다시 조회
            cursor.execute("SELECT * FROM suppliers ORDER BY supplier_id")
            suppliers = cursor.fetchall()
        
        # Acrel가 없으면 추가
        acrel_exists = any(s['supplier_name'] == 'Acrel' for s in suppliers)
        if not acrel_exists:
            cursor.execute(
                "INSERT INTO suppliers (supplier_name, contact_person, email, phone, address) VALUES (%s, %s, %s, %s, %s)",
                ("Acrel", "Acrel", "acrel@example.com", "123-456-7897", "Acrel Address")
            )
            conn.commit()
            # 다시 조회
            cursor.execute("SELECT * FROM suppliers ORDER BY supplier_id")
            suppliers = cursor.fetchall()
        
        return suppliers
    except Exception as e:
        conn.rollback()
        st.error(f"공급업체 목록 조회 중 오류가 발생했습니다: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_products(supplier_id=None):
    """제품 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        if supplier_id:
            cursor.execute("""
                SELECT p.product_id, p.supplier_id, p.model_name, p.moq, p.lead_time, p.notes, p.created_at, p.updated_at, s.supplier_name,
                       COALESCE(i.stock, 0) as current_stock,
                       i.is_certified, 
                       i.certificate_number
                FROM products_logistics p
                JOIN suppliers s ON p.supplier_id = s.supplier_id
                LEFT JOIN (
                    SELECT product_id, stock, is_certified, certificate_number
                    FROM inventory_logistics
                ) i ON p.product_id = i.product_id
                WHERE p.supplier_id = %s 
                ORDER BY p.model_name
            """, (supplier_id,))
        else:
            cursor.execute("""
                SELECT p.product_id, p.supplier_id, p.model_name, p.moq, p.lead_time, p.notes, p.created_at, p.updated_at, s.supplier_name,
                       COALESCE(i.stock, 0) as current_stock,
                       i.is_certified, 
                       i.certificate_number
                FROM products_logistics p
                JOIN suppliers s ON p.supplier_id = s.supplier_id
                LEFT JOIN (
                    SELECT product_id, stock, is_certified, certificate_number
                    FROM inventory_logistics
                ) i ON p.product_id = i.product_id
                ORDER BY p.model_name
            """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# --- PI 관련 함수들 ---
def get_pi_list(supplier_id=None):
    """PI 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT pi.*, s.supplier_name,
                   GROUP_CONCAT(
                       CONCAT(p.model_name, ' (', pi_items.quantity, '개)')
                       SEPARATOR ', '
                   ) as items_summary,
                   SUM(pi_items.quantity) as total_ordered_qty,
                   SUM(COALESCE(received.received_qty, 0)) as total_received_qty
            FROM proforma_invoices pi
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            JOIN pi_items ON pi.pi_id = pi_items.pi_id
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            LEFT JOIN (
                SELECT pi_item_id, SUM(quantity) as received_qty
                FROM ci_items
                GROUP BY pi_item_id
            ) as received ON pi_items.pi_item_id = received.pi_item_id
            WHERE 1=1
        """
        params = []
        
        if supplier_id:
            query += " AND pi.supplier_id = %s"
            params.append(supplier_id)
            
        query += " GROUP BY pi.pi_id ORDER BY pi.issue_date DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_pi_items(pi_id):
    """PI 항목 상세 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT pi_items.*, p.model_name, p.unit_price as base_price,
                   COALESCE(SUM(ci_items.quantity), 0) as received_qty
            FROM pi_items
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            WHERE pi_items.pi_id = %s
            GROUP BY pi_items.pi_item_id
        """, (pi_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_pi_by_number(pi_number):
    """PI 번호로 PI 정보 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # PI 기본 정보 조회 - 모든 컬럼 포함
        cursor.execute("""
            SELECT 
                pi.*,
                s.supplier_name,
                s.supplier_id
            FROM proforma_invoices pi
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            WHERE pi.pi_number = %s
        """, (pi_number,))
        pi_info = cursor.fetchone()
        
        if pi_info:
            # PI 항목 정보 조회
            cursor.execute("""
                SELECT 
                    pi_items.*,
                    p.model_name,
                    p.unit_price as base_price,
                    p.moq,
                    p.lead_time,
                    COALESCE(SUM(ci_items.quantity), 0) as received_qty
                FROM pi_items
                JOIN products_logistics p ON pi_items.product_id = p.product_id
                LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
                WHERE pi_items.pi_id = %s
                GROUP BY pi_items.pi_item_id
            """, (pi_info['pi_id'],))
            pi_info['items'] = cursor.fetchall()
            
            # 관련 CI 정보 조회
            cursor.execute("""
                SELECT 
                    ci.*,
                    GROUP_CONCAT(
                        CONCAT(p.model_name, ' (', ci_items.quantity, '개)')
                        SEPARATOR ', '
                    ) as items_summary
                FROM commercial_invoices ci
                JOIN ci_items ON ci.ci_id = ci_items.ci_id
                JOIN products_logistics p ON ci_items.product_id = p.product_id
                WHERE ci.pi_id = %s
                GROUP BY ci.ci_id
                ORDER BY ci.shipping_date DESC
            """, (pi_info['pi_id'],))
            pi_info['related_cis'] = cursor.fetchall()
        
        return pi_info
    finally:
        cursor.close()
        conn.close()

def create_pi(pi_data, items_data):
    """PI 생성 또는 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. PI 번호로 기존 PI 상세 정보 확인
        cursor.execute("""
            SELECT pi.*, s.supplier_name
            FROM proforma_invoices pi
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            WHERE pi.pi_number = %s
        """, (pi_data['pi_number'],))
        existing_pi = cursor.fetchone()

        if existing_pi:
            # 기존 PI 업데이트
            cursor.execute("""
                UPDATE proforma_invoices 
                SET supplier_id = %s,
                    issue_date = %s,
                    expected_delivery_date = %s,
                    total_amount = %s,
                    payment_terms = %s,
                    shipping_terms = %s,
                    project_name = %s,
                    notes = %s
                WHERE pi_id = %s
            """, (
                pi_data['supplier_id'],
                pi_data['issue_date'],
                pi_data['expected_delivery_date'],
                0,  # total_amount
                pi_data['payment_terms'],
                pi_data['shipping_terms'],
                pi_data.get('project_name', ''),
                pi_data['notes'],
                existing_pi['pi_id']
            ))
            pi_id = existing_pi['pi_id']
            
            # 기존 PI 항목 조회
            cursor.execute("""
                SELECT pi_items.pi_item_id, pi_items.product_id, pi_items.quantity, 
                       COALESCE(SUM(ci_items.quantity), 0) as received_qty
                FROM pi_items
                LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
                WHERE pi_items.pi_id = %s
                GROUP BY pi_items.pi_item_id
            """, (pi_id,))
            existing_items = {item['product_id']: item for item in cursor.fetchall()}
            
            # PI 항목 업데이트 또는 추가
            for item in items_data:
                if item['product_id'] in existing_items:
                    # 기존 항목 업데이트
                    existing_item = existing_items[item['product_id']]
                    cursor.execute("""
                        UPDATE pi_items 
                        SET quantity = %s,
                            unit_price = %s,
                            total_price = %s
                        WHERE pi_item_id = %s
                    """, (
                        item['quantity'],
                        0,  # unit_price
                        0,  # total_price
                        existing_item['pi_item_id']
                    ))
                else:
                    # 새로운 항목 추가
                    cursor.execute("""
                        INSERT INTO pi_items 
                        (pi_id, product_id, quantity, unit_price, total_price)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        pi_id, item['product_id'], item['quantity'],
                        0,  # unit_price
                        0   # total_price
                    ))
            
            # 더 이상 필요하지 않은 항목은 수량을 0으로 설정
            for existing_item in existing_items.values():
                if not any(item['product_id'] == existing_item['product_id'] for item in items_data):
                    cursor.execute("""
                        UPDATE pi_items 
                        SET quantity = 0,
                            total_price = 0
                        WHERE pi_item_id = %s
                    """, (existing_item['pi_item_id'],))
        else:
            # 새로운 PI 생성
            cursor.execute("""
                INSERT INTO proforma_invoices 
                (pi_number, supplier_id, issue_date, expected_delivery_date, 
                 total_amount, payment_terms, shipping_terms, 
                 project_name, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pi_data['pi_number'], pi_data['supplier_id'],
                pi_data['issue_date'], pi_data['expected_delivery_date'],
                0,  # total_amount
                pi_data['payment_terms'],
                pi_data['shipping_terms'], pi_data.get('project_name', ''), pi_data['notes']
            ))
            pi_id = cursor.lastrowid

            # 새로운 PI 항목 추가
            for item in items_data:
                cursor.execute("""
                    INSERT INTO pi_items 
                    (pi_id, product_id, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    pi_id, item['product_id'], item['quantity'],
                    0,  # unit_price
                    0   # total_price
                ))
        
        conn.commit()
        return True, pi_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def update_pi(pi_id, pi_data, items_data):
    """PI 수정"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. PI 기본 정보 업데이트
        cursor.execute("""
            UPDATE proforma_invoices 
            SET issue_date = %s,
                expected_delivery_date = %s,
                total_amount = %s,
                payment_terms = %s,
                shipping_terms = %s,
                notes = %s
            WHERE pi_id = %s
        """, (
            pi_data['issue_date'],
            pi_data['expected_delivery_date'],
            0,  # total_amount
            pi_data['payment_terms'],
            pi_data['shipping_terms'],
            pi_data['notes'],
            pi_id
        ))
        
        # 2. 기존 PI 항목 조회
        cursor.execute("""
            SELECT pi_items.pi_item_id, pi_items.product_id, pi_items.quantity, 
                   COALESCE(SUM(ci_items.quantity), 0) as received_qty
            FROM pi_items
            LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            WHERE pi_items.pi_id = %s
            GROUP BY pi_items.pi_item_id
        """, (pi_id,))
        existing_items = {item['product_id']: item for item in cursor.fetchall()}
        
        # 3. PI 항목 업데이트
        for item in items_data:
            if item['product_id'] in existing_items:
                # 기존 항목 업데이트
                existing_item = existing_items[item['product_id']]
                if item['quantity'] < existing_item['received_qty']:
                    raise Exception(f"제품 {item['product_id']}의 수량은 이미 입고된 수량({existing_item['received_qty']}개)보다 작을 수 없습니다.")
                
                cursor.execute("""
                    UPDATE pi_items 
                    SET quantity = %s,
                        unit_price = %s,
                        total_price = %s
                    WHERE pi_item_id = %s
                """, (
                    item['quantity'],
                    0,  # unit_price
                    0,  # total_price
                    existing_item['pi_item_id']
                ))
                del existing_items[item['product_id']]
            else:
                # 새로운 항목 추가
                cursor.execute("""
                    INSERT INTO pi_items 
                    (pi_id, product_id, quantity, unit_price, 
                     total_price, expected_production_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    pi_id, item['product_id'], item['quantity'],
                    0,  # unit_price
                    0,  # total_price
                    item['expected_production_date']
                ))
        
        # 4. 삭제된 항목 처리
        for existing_item in existing_items.values():
            if existing_item['received_qty'] > 0:
                raise Exception(f"이미 입고된 항목은 삭제할 수 없습니다. (입고 수량: {existing_item['received_qty']}개)")
            cursor.execute("DELETE FROM pi_items WHERE pi_item_id = %s", (existing_item['pi_item_id'],))
        
        conn.commit()
        return True, "PI가 성공적으로 수정되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

# --- CI 관련 함수들 ---
def create_ci(ci_data, items_data):
    """CI 생성 및 재고 등록 (FIFO로 여러 PI 미입고분 자동 소진)"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 1. CI 기본 정보 저장
        cursor.execute("""
            INSERT INTO commercial_invoices 
            (ci_number, pi_id, supplier_id, shipping_date, arrival_date,
             total_amount, shipping_details, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ci_data['ci_number'], ci_data.get('pi_id'),
            ci_data['supplier_id'], ci_data['shipping_date'],
            ci_data['arrival_date'], 0,  # total_amount
            ci_data['shipping_details'], ci_data['notes']
        ))
        ci_id = cursor.lastrowid
        
        # 2. FIFO 매칭: 동일 제품의 미입고 PI 항목을 오래된 순으로 소진
        from decimal import Decimal
        for item in items_data:
            product_id = item['product_id']
            total_quantity = int(item['quantity'])
            unit_price = 0  # 무조건 0
            total_price = 0  # 무조건 0
            notes = item.get('notes', '')
            supplier_id = ci_data['supplier_id']
            # 미입고 PI 항목 조회 (오래된 순)
            pending_items = get_pending_pi_items(supplier_id)
            pending_items = [pi for pi in pending_items if pi['product_id'] == product_id and (pi['ordered_qty'] - pi['received_qty']) > 0]
            pending_items.sort(key=lambda x: x['issue_date'])
            remaining_qty = total_quantity
            for pi_item in pending_items:
                if remaining_qty == 0:
                    break
                available = int(pi_item['ordered_qty'] - pi_item['received_qty'])
                to_receive = min(remaining_qty, available)
                if to_receive > 0:
                    cursor.execute("""
                        INSERT INTO ci_items 
                        (ci_id, pi_item_id, product_id, quantity, unit_price, total_price, shipping_date, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        ci_id, pi_item['pi_item_id'], product_id, to_receive, 0, 0, ci_data['shipping_date'], notes
                    ))
                    # 재고 등록
                    update_stock(
                        product_id=product_id,
                        quantity_change=to_receive,
                        change_type='입고',
                        reference_number=ci_data['ci_number'],
                        notes=f"CI 등록: {ci_data['ci_number']}",
                        destination=ci_data.get('shipping_details', '')
                    )
                    remaining_qty -= to_receive
        conn.commit()
        return True, ci_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def get_ci_list(supplier_id=None, start_date=None, end_date=None):
    """CI 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT ci.*, s.supplier_name,
                   GROUP_CONCAT(
                       CONCAT(p.model_name, ' (', ci_items.quantity, '개)')
                       SEPARATOR ', '
                   ) as items_summary
            FROM commercial_invoices ci
            JOIN suppliers s ON ci.supplier_id = s.supplier_id
            JOIN ci_items ON ci.ci_id = ci_items.ci_id
            JOIN products_logistics p ON ci_items.product_id = p.product_id
            WHERE 1=1
        """
        params = []
        
        if supplier_id:
            query += " AND ci.supplier_id = %s"
            params.append(supplier_id)
        if start_date:
            query += " AND ci.issue_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND ci.issue_date <= %s"
            params.append(end_date)
            
        query += " GROUP BY ci.ci_id ORDER BY ci.issue_date DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# --- 재고 분석 관련 함수들 ---
def get_stock_statistics():
    """재고 통계 데이터 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 전체 재고 현황
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT p.product_id) as total_products,
                COALESCE(SUM(COALESCE(i.stock, 0)), 0) as total_stock,
                COUNT(CASE WHEN COALESCE(i.stock, 0) = 0 THEN 1 END) as out_of_stock
            FROM products_logistics p
            LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
        """)
        overall_stats = cursor.fetchone()
        
        # 공급업체별 재고 현황
        cursor.execute("""
            SELECT 
                s.supplier_name,
                COUNT(DISTINCT p.product_id) as product_count,
                COALESCE(SUM(COALESCE(i.stock, 0)), 0) as total_stock,
                COUNT(CASE WHEN COALESCE(i.stock, 0) = 0 THEN 1 END) as out_of_stock
            FROM suppliers s
            JOIN products_logistics p ON s.supplier_id = p.supplier_id
            LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
            GROUP BY s.supplier_id, s.supplier_name
        """)
        supplier_stats = cursor.fetchall()
        
        return {
            'overall': overall_stats,
            'suppliers': supplier_stats
        }
    finally:
        cursor.close()
        conn.close()

def get_stock_movements(days=30):
    """재고 이동 추이 분석"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                DATE(t.date) as date,
                p.model_name,
                s.supplier_name,
                SUM(CASE WHEN t.change_type = '입고' THEN t.quantity ELSE 0 END) as in_qty,
                SUM(CASE WHEN t.change_type = '출고' THEN t.quantity ELSE 0 END) as out_qty
            FROM inventory_transactions t
            JOIN products_logistics p ON t.product_id = p.product_id
            JOIN suppliers s ON p.supplier_id = s.supplier_id
            WHERE t.date >= DATE_SUB(CURRENT_DATE, INTERVAL %s DAY)
            GROUP BY DATE(t.date), p.model_name, s.supplier_name
            ORDER BY date DESC, p.model_name
        """, (days,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_pending_pi_items(supplier_id=None):
    """미입고된 PI 항목 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                pi.pi_id,
                pi.pi_number,
                pi.issue_date,
                pi.expected_delivery_date,
                s.supplier_name,
                p.model_name,
                pi_items.pi_item_id,
                pi_items.product_id,
                pi_items.quantity as ordered_qty,
                pi_items.expected_production_date,
                COALESCE(SUM(ci_items.quantity), 0) as received_qty
            FROM pi_items
            JOIN proforma_invoices pi ON pi_items.pi_id = pi.pi_id
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
        """
        params = []
        if supplier_id:
            query += " WHERE pi.supplier_id = %s"
            params.append(supplier_id)
        query += " GROUP BY pi_items.pi_item_id HAVING ordered_qty > received_qty ORDER BY pi.expected_delivery_date"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def match_ci_with_pi(ci_number, supplier_id):
    """CI와 미입고 PI 매칭"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. 미입고 PI 항목 조회
        pending_items = get_pending_pi_items(supplier_id)
        
        # 2. CI 항목과 매칭
        matched_items = []
        for item in pending_items:
            cursor.execute("""
                SELECT 
                    ci_items.ci_item_id,
                    ci_items.quantity as received_qty,
                    ci_items.shipping_date,
                    ci_items.notes
                FROM ci_items
                JOIN commercial_invoices ci ON ci_items.ci_id = ci.ci_id
                WHERE ci.ci_number = %s 
                AND ci_items.product_id = %s
            """, (ci_number, item['product_id']))
            
            ci_item = cursor.fetchone()
            if ci_item:
                matched_items.append({
                    'pi_item_id': item['pi_item_id'],
                    'product_id': item['product_id'],
                    'model_name': item['model_name'],
                    'ordered_qty': item['ordered_qty'],
                    'received_qty': ci_item['received_qty'],
                    'shipping_date': ci_item['shipping_date'],
                    'notes': ci_item['notes'],
                    'pi_number': item['pi_number']
                })
        
        return matched_items
    finally:
        cursor.close()
        conn.close()

def delete_pi(pi_id):
    """PI 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # PI 항목의 입고 여부 확인
        cursor.execute("""
            SELECT COALESCE(SUM(ci_items.quantity), 0) as received_qty
            FROM pi_items
            LEFT JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            WHERE pi_items.pi_id = %s
            GROUP BY pi_items.pi_item_id
        """, (pi_id,))
        received_items = cursor.fetchall()
        
        # 이미 입고된 항목이 있는지 확인
        if any(item[0] > 0 for item in received_items):
            return False, "이미 입고된 항목이 있어 PI를 삭제할 수 없습니다."
        
        # PI 삭제 (CASCADE로 인해 관련 항목도 자동 삭제)
        cursor.execute("DELETE FROM proforma_invoices WHERE pi_id = %s", (pi_id,))
        conn.commit()
        return True, "PI가 성공적으로 삭제되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def delete_ci(ci_id, handle_stock=True):
    """CI 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 트랜잭션 시작
        conn.start_transaction()
        
        # CI 항목 조회
        cursor.execute("""
            SELECT ci_items.*, p.model_name
            FROM ci_items
            JOIN products_logistics p ON ci_items.product_id = p.product_id
            WHERE ci_items.ci_id = %s
        """, (ci_id,))
        ci_items = cursor.fetchall()
        
        if handle_stock:
            # 재고 차감
            for item in ci_items:
                cursor.execute("""
                    UPDATE inventory_logistics 
                    SET stock = stock - %s
                    WHERE product_id = %s
                """, (item['quantity'], item['product_id']))
                
                # 재고 이력 기록
                cursor.execute("""
                    INSERT INTO inventory_transactions 
                    (product_id, change_type, quantity, reference_number, 
                     notes, date, destination)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                """, (
                    item['product_id'],
                    '출고',
                    -item['quantity'],
                    f"CI_DELETE_{ci_id}",
                    f"CI 삭제로 인한 재고 차감 - {item['model_name']}",
                    "CI 삭제"
                ))
        
        # CI 삭제 (CASCADE로 인해 관련 항목도 자동 삭제)
        cursor.execute("DELETE FROM commercial_invoices WHERE ci_id = %s", (ci_id,))
        
        conn.commit()
        return True, "CI가 성공적으로 삭제되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def get_product_by_model(model_name, supplier_id):
    """모델명으로 제품 정보 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT p.*, i.is_certified, i.certificate_number
            FROM products_logistics p
            LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
            WHERE p.model_name = %s AND p.supplier_id = %s
        """, (model_name, supplier_id))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def update_product(product_id, product_data):
    """제품 정보 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 1. 제품 정보 업데이트
        cursor.execute("""
            UPDATE products_logistics 
            SET notes = %s
            WHERE product_id = %s
        """, (
            product_data['notes'],
            product_id
        ))
        
        # 2. 인증 정보 업데이트
        cursor.execute("""
            UPDATE inventory_logistics 
            SET is_certified = %s,
                certificate_number = %s
            WHERE product_id = %s
        """, (
            product_data['is_certified'],
            product_data['certificate_number'] if product_data['is_certified'] else None,
            product_id
        ))
        
        conn.commit()
        return True, "제품이 성공적으로 수정되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

# --- 재고 보정 함수 ---
def correct_inventory_records():
    """모든 제품에 대해 inventory_logistics에 1개의 레코드가 있도록 보정 (중복 제거 포함)"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 1. 중복된 product_id에 대해 inventory_id가 가장 큰(최근) 레코드만 남기고 삭제
        cursor.execute('''
            DELETE il1 FROM inventory_logistics il1
            INNER JOIN inventory_logistics il2
              ON il1.product_id = il2.product_id
              AND il1.inventory_id < il2.inventory_id;
        ''')
        # 2. 누락된 product_id에 대해 0 재고로 추가
        cursor.execute('''
            INSERT INTO inventory_logistics (product_id, stock, is_certified)
            SELECT p.product_id, 0, FALSE
            FROM products_logistics p
            LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
            WHERE i.product_id IS NULL
        ''')
        conn.commit()
        return True, "재고 보정이 완료되었습니다. (중복 제거 및 누락된 제품의 재고가 0으로 추가됨)"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("📦 재고 관리 시스템")
    
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
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["재고 현황", "입고 관리", "출고 관리", "재고 조정", "재고 분석", "PI 관리", "제품 관리", "재고 이력"]
    )
    
    if menu == "재고 현황":
        st.header("📊 재고 현황")
        
        # 재고 통계 데이터 조회
        stats = get_stock_statistics()
        
        # 재고 현황 요약
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "전체 제품 수",
                int(stats['overall']['total_products'] or 0),
                help="등록된 전체 제품 수"
            )
        with col2:
            st.metric(
                "전체 재고 수량",
                int(stats['overall']['total_stock'] or 0),
                help="전체 제품의 현재 재고 수량 합계"
            )
        with col3:
            st.metric(
                "재고 없음",
                int(stats['overall']['out_of_stock'] or 0),
                delta=None,
                delta_color="inverse",
                help="현재 재고가 0인 제품 수"
            )
        
        # 공급업체별 재고 현황
        st.subheader("공급업체별 재고 현황")
        
        # 공급업체 선택
        suppliers = get_suppliers()
        selected_supplier = st.selectbox(
            "공급업체 선택",
            options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
            format_func=lambda x: x['supplier_name'],
            key="inventory_supplier"
        )
        
        # 제품 목록 조회
        products = get_products(selected_supplier['supplier_id'] if selected_supplier['supplier_id'] else None)
        # 키워드 검색 입력란 추가
        keyword = st.text_input('키워드 검색 (모델명, 인증서번호, 비고 등)', key='inventory_keyword')
        if keyword:
            keyword_lower = keyword.lower()
            products = [p for p in products if (
                keyword_lower in str(p.get('model_name', '')).lower() or
                keyword_lower in str(p.get('certificate_number', '')).lower() or
                keyword_lower in str(p.get('notes', '')).lower()
            )]
        # 재고가 있는 제품만 보기 체크박스 추가
        show_only_in_stock = st.checkbox('재고가 있는 제품만 보기', value=False)
        if show_only_in_stock:
            products = [p for p in products if p['current_stock'] > 0]
        if products:
            # 재고현황 표에서 모델명, supplier_name, 현재 재고만 보이도록 DataFrame 컬럼 제한
            df = pd.DataFrame(products)
            df = df[['model_name', 'supplier_name', 'current_stock']]
            def highlight_status(row):
                if row['current_stock'] == 0:
                    return ['background-color: #b71c1c; color: white'] * len(row)
                return [''] * len(row)
            st.dataframe(
                df.style.apply(highlight_status, axis=1),
                column_config={
                    "model_name": "모델명",
                    "supplier_name": "공급업체",
                    "current_stock": st.column_config.NumberColumn("현재 재고", format="%d개")
                },
                hide_index=True
            )
        else:
            st.info("등록된 제품이 없습니다.")
        
        # 재고 보정 버튼 추가
        if st.button('재고 DB 보정 실행', type='secondary'):
            success, msg = correct_inventory_records()
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(f"재고 보정 중 오류: {msg}")
    
    elif menu == "입고 관리":
        st.header("📥 입고 관리")
        
        # 입고 방식 선택
        entry_type = st.radio(
            "입고 방식 선택",
            ["PI 기반 CI 등록", "기존 CI 매칭"],
            horizontal=True
        )
        
        if entry_type == "PI 기반 CI 등록":
            # 세션 상태에서 선택된 PI 확인
            selected_pi_number = st.session_state.get('selected_pi_for_ci')
            if selected_pi_number:
                st.info(f"선택된 PI: {selected_pi_number}")
                # PI 선택 상태 초기화
                st.session_state['selected_pi_for_ci'] = None
            
            # PI 목록 조회
            pi_list = get_pi_list()
            
            if not pi_list:
                st.info("등록된 PI가 없습니다.")
            else:
                # PI 선택
                selected_pi = st.selectbox(
                    "PI 선택",
                    options=pi_list,
                    format_func=lambda x: f"{x['pi_number']} - {x['supplier_name']} ({x['items_summary']})"
                )
                
                if selected_pi:
                    # PI 상세 정보 조회
                    pi_info = get_pi_by_number(selected_pi['pi_number'])
                    
                    if pi_info:
                        # PI 기본 정보 표시
                        st.subheader("PI 정보")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**PI 번호:** {pi_info['pi_number']}")
                            st.write(f"**공급업체:** {pi_info['supplier_name']}")
                            st.write(f"**발행일:** {pi_info['issue_date'].strftime('%Y-%m-%d')}")
                        with col2:
                            st.write(f"**예상 납기일:** {pi_info['expected_delivery_date'].strftime('%Y-%m-%d')}")
                            st.write(f"**통화:** {pi_info['currency']}")
                            st.write(f"**총액:** {pi_info['total_amount']:,.2f} {pi_info['currency']}")
                        
                        # CI 등록/수정 폼
                        with st.form("ci_form"):
                            # CI 기본 정보
                            ci_number = st.text_input(
                                "CI 번호",
                                value=pi_info['pi_number'].replace('PI', 'CI'),
                                help="PI 번호에서 'PI'를 'CI'로 변경한 번호가 자동으로 입력됩니다."
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                shipping_date = st.date_input(
                                    "선적일",
                                    value=date.today()
                                )
                            with col2:
                                arrival_date = st.date_input(
                                    "입고일",
                                    value=date.today()
                                )
                                shipping_details = st.text_area("선적 정보")
                            
                            # PI 항목 정보 표시 및 입고 수량 입력
                            st.subheader("입고 항목")
                            items_data = []
                            
                            for item in pi_info['items']:
                                st.markdown(f"##### {item['model_name']}")
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    st.write(f"**주문 수량:** {item['quantity']}개")
                                with col2:
                                    max_qty = int(item['quantity'] - item['received_qty'])
                                    quantity = st.number_input(
                                        "입고 수량",
                                        min_value=0,
                                        max_value=max_qty,
                                        value=0,
                                        step=1,
                                        key=f"ci_quantity_{item['pi_item_id']}"
                                    )
                                
                                with col3:
                                    item_notes = st.text_input(
                                        "항목 비고",
                                        key=f"ci_item_note_{item['pi_item_id']}"
                                    )
                                
                                if quantity > 0:
                                    items_data.append({
                                        'pi_item_id': item['pi_item_id'],
                                        'product_id': item['product_id'],
                                        'quantity': quantity,
                                        'notes': item_notes
                                    })
                            
                            notes = st.text_area("비고")
                            
                            # 제출 버튼
                            submitted = st.form_submit_button("CI 등록")
                        
                        # 폼 제출 후 처리
                        if submitted and ci_number and items_data:
                            try:
                                # CI 데이터 준비
                                ci_data = {
                                    'ci_number': ci_number,
                                    'pi_id': pi_info['pi_id'],
                                    'supplier_id': pi_info['supplier_id'],
                                    'shipping_date': shipping_date,
                                    'arrival_date': arrival_date,
                                    'shipping_details': shipping_details,
                                    'notes': notes
                                }
                                
                                # CI 생성 또는 업데이트
                                success, result = create_ci(ci_data, items_data)
                                if success:
                                    st.success("CI가 성공적으로 등록되었습니다.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"CI 등록 중 오류가 발생했습니다: {result}")
                            except Exception as e:
                                st.error(f"CI 등록 중 오류가 발생했습니다: {str(e)}")
                        
                        # 관련 CI 목록 표시
                        if pi_info['related_cis']:
                            st.subheader("관련 CI 목록")
                            for ci in pi_info['related_cis']:
                                with st.expander(f"CI 번호: {ci['ci_number']} ({ci['shipping_date'].strftime('%Y-%m-%d')})"):
                                    st.write(f"**발행일:** {ci['shipping_date'].strftime('%Y-%m-%d')}")
                                    st.write(f"**실제 납기일:** {ci['shipping_date'].strftime('%Y-%m-%d')}")
                                    st.write(f"**총액:** {ci['total_amount']:,.2f} {ci['currency']}")
                                    st.write(f"**항목:** {ci['items_summary']}")
                                    if ci['shipping_details']:
                                        st.write(f"**선적 정보:** {ci['shipping_details']}")
                                    if ci['notes']:
                                        st.write(f"**비고:** {ci['notes']}")
                                    
                                    # CI 삭제 폼
                                    with st.form(f"ci_delete_form_{ci['ci_id']}"):
                                        st.warning(f"⚠️ CI {ci['ci_number']}를 삭제하시겠습니까?")
                                        handle_stock = st.checkbox(
                                            "재고 차감 처리",
                                            value=True,
                                            help="체크하면 CI 삭제 시 해당 재고도 함께 차감됩니다."
                                        )
                                        
                                        submitted = st.form_submit_button("CI 삭제")
                                        
                                        if submitted:
                                            success, message = delete_ci(ci['ci_id'], handle_stock)
                                            if success:
                                                st.success(message)
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(f"CI 삭제 중 오류가 발생했습니다: {message}")
        
        else:  # 기존 CI 매칭
            st.subheader("기존 CI와 미입고 PI 매칭")
            
            # 공급업체 선택
            suppliers = get_suppliers()
            selected_supplier = st.selectbox(
                "공급업체 선택",
                options=suppliers,
                format_func=lambda x: x['supplier_name'],
                key="ci_matching_supplier"
            )
            
            # CI 번호 입력
            ci_number = st.text_input("CI 번호")
            
            if ci_number and selected_supplier:
                # CI와 미입고 PI 매칭
                matched_items = match_ci_with_pi(ci_number, selected_supplier['supplier_id'])
                
                if matched_items:
                    st.success(f"CI {ci_number}와 매칭된 미입고 항목을 찾았습니다.")
                    
                    # 매칭된 항목 표시
                    for item in matched_items:
                        with st.expander(f"PI: {item['pi_number']} - {item['model_name']}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**주문 수량:** {item['ordered_qty']}개")
                                st.write(f"**입고 수량:** {item['received_qty']}개")
                                st.write(f"**미입고 수량:** {item['ordered_qty'] - item['received_qty']}개")
                            with col2:
                                st.write(f"**실제 납기일:** {item['shipping_date'].strftime('%Y-%m-%d')}")
                                st.write(f"**선적일:** {item['shipping_date'].strftime('%Y-%m-%d')}")
                                if item['notes']:
                                    st.write(f"**비고:** {item['notes']}")
                
                    # 매칭 확인 및 처리 폼
                    with st.form("ci_matching_form"):
                        st.write("매칭된 항목을 확인하고 입고 처리를 진행합니다.")
                        submitted = st.form_submit_button("매칭 확인 및 입고 처리")
                        
                        if submitted:
                            try:
                                conn = connect_to_db()
                                cursor = conn.cursor()
                                
                                # 트랜잭션 시작
                                conn.start_transaction()
                                
                                for item in matched_items:
                                    # 재고 업데이트
                                    cursor.execute("""
                                        UPDATE inventory_logistics 
                                        SET stock = stock + %s
                                        WHERE product_id = %s
                                    """, (int(item['received_qty']), item['product_id']))  # Convert to int
                                    
                                    # 재고 이력 기록
                                    cursor.execute("""
                                        INSERT INTO inventory_transactions 
                                        (product_id, change_type, quantity, reference_number, 
                                         notes, date, destination)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        item['product_id'],
                                        '입고',
                                        int(item['received_qty']),  # Convert to int
                                        ci_number,
                                        f"CI {ci_number} 매칭 입고 - PI {item['pi_number']}",
                                        item['shipping_date'],
                                        "CI 매칭 입고"
                                    ))
                                
                                conn.commit()
                                st.success("매칭된 항목의 입고 처리가 완료되었습니다.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"입고 처리 중 오류가 발생했습니다: {str(e)}")
                            finally:
                                cursor.close()
                                conn.close()
                else:
                    st.warning(f"CI {ci_number}와 매칭되는 미입고 항목을 찾을 수 없습니다.")
    
    elif menu == "출고 관리":
        st.header("📤 출고 관리")
        
        # 공급업체 목록을 먼저 가져옵니다
        suppliers = get_suppliers()
        
        # 공급업체 선택을 위한 옵션 생성
        supplier_options = [(s['supplier_id'], s['supplier_name']) for s in suppliers]
        
        # 공급업체 선택 (폼 밖에서)
        selected_supplier_id = st.selectbox(
            "공급업체 선택",
            options=[s[0] for s in supplier_options],
            format_func=lambda x: next((s[1] for s in supplier_options if s[0] == x), ''),
            key="outbound_supplier_select"
        )
        
        # 선택된 공급업체 정보 가져오기
        selected_supplier = next((s for s in suppliers if s['supplier_id'] == selected_supplier_id), None)
        
        # 제품 목록 가져오기
        products = []
        if selected_supplier:
            # 제품 목록 조회 시 재고 정보도 함께 가져오기
            products = get_products(selected_supplier['supplier_id'])
            
            if products:
                # 각 제품의 재고 정보를 최신 상태로 업데이트
                updated_products = []
                for product in products:
                    try:
                        stock_info = get_stock(product['product_id'])
                        product['current_stock'] = stock_info['stock']
                        updated_products.append(product)
                    except Exception as e:
                        st.error(f"제품 {product['model_name']}의 재고 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")
                        continue
                
                products = updated_products  # 업데이트된 제품 목록으로 교체
        
        # 출고 폼
        with st.form("outbound_form"):
            # 제품 선택
            selected_product = None
            current_stock = 0
            
            if products:
                # 재고가 있는 제품만 필터링
                available_products = [p for p in products if p['current_stock'] > 0]
                
                if available_products:
                    product_options = [(p['product_id'], p['model_name'], p['current_stock']) for p in available_products]
                    selected_product_id = st.selectbox(
                        "제품 선택",
                        options=[p[0] for p in product_options],
                        format_func=lambda x: next((f"{p[1]} (재고: {p[2]}개)" for p in product_options if p[0] == x), ''),
                        key="outbound_product_select"
                    )
                    
                    # 선택된 제품 정보 가져오기
                    selected_product = next((p for p in available_products if p['product_id'] == selected_product_id), None)
                    
                    if selected_product:
                        # 재고 정보를 직접 데이터베이스에서 다시 조회
                        stock_info = get_stock(selected_product['product_id'])
                        current_stock = stock_info['stock']
                        st.info(f"현재 재고: {current_stock}개")
                else:
                    st.warning("현재 재고가 있는 제품이 없습니다.")
            
            # 출고 정보 입력 (재고가 있는 경우에만 표시)
            quantity = 0
            reference_number = ""
            destination = ""
            notes = ""
            
            if selected_product and current_stock > 0:
                col1, col2 = st.columns(2)
                with col1:
                    quantity = st.number_input(
                        "출고 수량",
                        min_value=1,
                        max_value=current_stock,
                        value=min(1, current_stock),
                        step=1
                    )
                    reference_number = st.text_input(
                        "참조 번호",
                        value=f"MANUAL_OUT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    )
                with col2:
                    destination = st.text_input("출고지")
                    notes = st.text_area("비고")
            elif selected_product:
                st.warning("현재 재고가 없어 출고할 수 없습니다.")
            
            # 제출 버튼
            submitted = st.form_submit_button(
                "출고 처리",
                disabled=not (selected_product is not None and current_stock > 0)
            )
        
        # 폼 제출 후 처리
        if submitted and selected_product and current_stock > 0:
            try:
                # 재고 업데이트 전 최종 확인
                final_stock_check = get_stock(selected_product['product_id'])
                if final_stock_check['stock'] < quantity:
                    st.error("재고가 부족합니다. 다른 사용자가 재고를 변경했을 수 있습니다.")
                    return
                # 재고 업데이트 실행
                conn = connect_to_db()
                cursor = conn.cursor()
                try:
                    # 트랜잭션 시작
                    conn.start_transaction()
                    # 1. 재고 업데이트
                    new_stock = current_stock - quantity
                    cursor.execute("""
                        UPDATE inventory_logistics 
                        SET stock = %s
                        WHERE product_id = %s
                    """, (new_stock, selected_product['product_id']))
                    # 2. 재고 이력 기록
                    cursor.execute("""
                        INSERT INTO inventory_transactions 
                        (product_id, change_type, quantity, reference_number, 
                         notes, date, destination)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        selected_product['product_id'],
                        '출고',
                        -quantity,
                        reference_number,
                        notes,
                        datetime.now(),
                        destination
                    ))
                    # 트랜잭션 커밋
                    conn.commit()
                    st.success("재고가 성공적으로 출고되었습니다.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    cursor.close()
                    conn.close()
            except Exception as e:
                st.error(f"출고 처리 중 오류가 발생했습니다: {str(e)}")
    
    elif menu == "재고 조정":
        st.header("⚖️ 재고 조정")
        
        # 재고 초기화 섹션 추가
        st.subheader("재고 초기화")
        st.warning("⚠️ 주의: 이 작업은 모든 제품의 재고를 0으로 초기화합니다. 신중하게 진행해주세요.")
        
        if st.button("재고 초기화 실행", type="primary"):
            conn = connect_to_db()
            cursor = conn.cursor()
            try:
                # 1. 재고 이력 기록
                cursor.execute("""
                    INSERT INTO inventory_transactions 
                    (product_id, change_type, quantity, reference_number, notes, date)
                    SELECT 
                        p.product_id,
                        '출고',
                        COALESCE(i.stock, 0),
                        'STOCK_RESET',
                        '재고 초기화 작업',
                        NOW()
                    FROM products_logistics p
                    LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
                    WHERE COALESCE(i.stock, 0) > 0
                """)
                
                # 2. 재고 초기화
                cursor.execute("""
                    UPDATE inventory_logistics 
                    SET stock = 0
                """)
                
                # 3. 재고가 없는 제품에 대해 새로 레코드 생성
                cursor.execute("""
                    INSERT INTO inventory_logistics (product_id, stock, is_certified)
                    SELECT p.product_id, 0, FALSE
                    FROM products_logistics p
                    LEFT JOIN inventory_logistics i ON p.product_id = i.product_id
                    WHERE i.product_id IS NULL
                """)
                
                conn.commit()
                st.success("모든 재고가 성공적으로 초기화되었습니다.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"재고 초기화 중 오류가 발생했습니다: {str(e)}")
            finally:
                cursor.close()
                conn.close()
        
        st.divider()
        
        # 기존 재고 조정 폼
        with st.form("adjustment_form"):
            # 공급업체 선택
            suppliers = get_suppliers()
            selected_supplier = st.selectbox(
                "공급업체 선택",
                options=suppliers,
                format_func=lambda x: x['supplier_name'],
                key="adjustment_supplier"
            )
            
            # 제품 선택 및 조정 정보
            selected_product = None
            current_stock = 0  # 기본값을 정수로 변경
            
            if selected_supplier:
                products = get_products(selected_supplier['supplier_id'])
                if products:
                    selected_product = st.selectbox(
                        "제품 선택",
                        options=products,
                        format_func=lambda x: x['model_name'],
                        key="adjustment_product"
                    )
                    
                    if selected_product:
                        stock_info = get_stock(selected_product['product_id'])
                        current_stock = stock_info['stock']  # 정수값으로 직접 할당
                        st.info(f"현재 재고: {current_stock}개")
            
            # 조정 정보 입력
            new_stock = current_stock
            reference_number = ""
            reason = ""
            
            if selected_product is not None:  # 제품이 선택된 경우에만 입력 필드 표시
                col1, col2 = st.columns(2)
                with col1:
                    new_stock = st.number_input(
                        "조정 후 재고",
                        min_value=0,
                        value=current_stock,
                        step=1
                    )
                    reference_number = st.text_input(
                        "참조 번호",
                        value=f"MANUAL_ADJ_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    )
                with col2:
                    reason = st.text_area("조정 사유")
            
            # 제출 버튼 - 폼 컨텍스트 내에서 직접 호출
            # 디버깅을 위한 상태 표시 추가
            st.write(f"Debug - Selected Product: {selected_product is not None}, Current Stock: {current_stock}")
            submitted = st.form_submit_button(
                "재고 조정",
                disabled=selected_product is None
            )
        
        # 폼 제출 후 처리
        if submitted and selected_product is not None:
            if new_stock != current_stock:
                try:
                    update_stock(
                        product_id=selected_product['product_id'],
                        quantity_change=new_stock - current_stock,
                        change_type='입고' if new_stock > current_stock else '출고',
                        reference_number=reference_number,
                        notes=reason
                    )
                    st.success("재고가 성공적으로 조정되었습니다.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"재고 조정 중 오류가 발생했습니다: {str(e)}")
            else:
                st.warning("재고 수량이 변경되지 않았습니다.")
    
    elif menu == "재고 분석":
        st.header("📈 재고 분석")
        
        # 분석 기간 선택
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "분석 시작일",
                value=date.today() - timedelta(days=30)
            )
        with col2:
            end_date = st.date_input(
                "분석 종료일",
                value=date.today()
            )
        
        # 재고 이동 추이
        st.subheader("재고 이동 추이")
        movements = get_stock_movements((end_date - start_date).days)
        if movements:
            df_movements = pd.DataFrame(movements)
            
            # 차트 데이터 준비
            fig = px.line(
                df_movements,
                x='date',
                y=['in_qty', 'out_qty'],
                color='model_name',
                title='제품별 입출고 추이',
                labels={
                    'date': '날짜',
                    'value': '수량',
                    'variable': '구분',
                    'model_name': '제품명'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 상세 데이터
            st.dataframe(
                df_movements,
                column_config={
                    "date": st.column_config.DateColumn(
                        "날짜",
                        format="YYYY-MM-DD"
                    ),
                    "model_name": "제품명",
                    "supplier_name": "공급업체",
                    "in_qty": st.column_config.NumberColumn(
                        "입고 수량",
                        format="%d개"
                    ),
                    "out_qty": st.column_config.NumberColumn(
                        "출고 수량",
                        format="%d개"
                    )
                },
                hide_index=True
            )
        else:
            st.info("분석 기간의 재고 변동 데이터가 없습니다.")
        
        # 재고 통계
        st.subheader("재고 통계")
        stats = get_stock_statistics()
        
        # 공급업체별 재고 현황 차트
        supplier_df = pd.DataFrame(stats['suppliers'])
        # low_stock 컬럼이 없으면 0으로 추가
        if 'low_stock' not in supplier_df.columns:
            supplier_df['low_stock'] = 0
        # 컬럼 타입을 모두 int로 변환
        for col in ['total_stock', 'out_of_stock', 'low_stock']:
            if col in supplier_df.columns:
                supplier_df[col] = pd.to_numeric(supplier_df[col], errors='coerce').fillna(0).astype(int)
        fig = px.bar(
            supplier_df,
            x='supplier_name',
            y=['total_stock', 'out_of_stock', 'low_stock'],
            title='공급업체별 재고 현황',
            labels={
                'supplier_name': '공급업체',
                'value': '수량',
                'variable': '구분'
            },
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)

    elif menu == "PI 관리":
        st.header("📄 PI 관리")
        
        pi_submenu = st.radio(
            "PI 관리 메뉴",
            ["PI 등록", "PI 현황", "미입고 현황"],
            horizontal=True
        )
        
        if pi_submenu == "PI 등록":
            st.header("PI 등록")
            
            # 공급업체 선택 (폼 밖에서)
            suppliers = get_suppliers()
            selected_supplier = st.selectbox(
                "공급업체 선택",
                options=suppliers,
                format_func=lambda x: x['supplier_name']
            )
            
            # 기존 PI 선택 드롭다운 추가
            pi_list = get_pi_list(selected_supplier['supplier_id']) if selected_supplier else []
            existing_pi_numbers = [pi['pi_number'] for pi in pi_list]
            selected_existing_pi = st.selectbox(
                "수정할 기존 PI 선택 (신규 등록 시 선택하지 마세요)",
                options=[None] + existing_pi_numbers,
                format_func=lambda x: x if x else "신규 등록"
            )
            pi_info = get_pi_by_number(selected_existing_pi) if selected_existing_pi else None
            
            if selected_supplier:
                # 선택된 공급업체의 제품 목록 가져오기 (폼 밖에서)
                products = get_products(selected_supplier['supplier_id'])
                
                if products:
                    with st.form("pi_form"):
                        # PI 기본 정보
                        st.subheader("PI 기본 정보")
                        col1, col2 = st.columns(2)
                        with col1:
                            pi_number = st.text_input("PI 번호", value=pi_info['pi_number'] if pi_info else "")
                            issue_date = st.date_input("발행일", value=pi_info['issue_date'] if pi_info else date.today())
                            currency = st.selectbox(
                                "통화",
                                ["USD", "CNY", "EUR"],
                                index=["USD", "CNY", "EUR"].index(pi_info['currency']) if pi_info and 'currency' in pi_info and pi_info['currency'] in ["USD", "CNY", "EUR"] else 0
                            )
                        with col2:
                            expected_delivery_date = st.date_input("예상 납기일", value=pi_info['expected_delivery_date'] if pi_info else date.today())
                            payment_terms = st.text_area("지불 조건", value=pi_info['payment_terms'] if pi_info else "")
                            shipping_terms = st.text_area("선적 조건", value=pi_info['shipping_terms'] if pi_info else "")
                        
                        # 주문 항목
                        st.subheader("주문 항목")
                        if pi_info:
                            # 기존 PI 항목 정보로 채우기
                            existing_items = {item['product_id']: item for item in pi_info['items']}
                        else:
                            existing_items = {}
                        item_count = st.number_input(
                            "주문 항목 수",
                            min_value=1,
                            max_value=30,
                            value=len(existing_items) if existing_items else 1,
                            step=1,
                            help="주문할 제품의 갯수를 입력하세요 (최대 30개)"
                        )
                        items_data = []
                        total_amount = 0
                        has_valid_items = False
                        for i in range(item_count):
                            st.markdown(f"### 주문 항목 {i+1}")
                            col1, col2, col3 = st.columns(3)
                            # 기존 항목 정보 가져오기
                            if pi_info and i < len(pi_info['items']):
                                existing_item = pi_info['items'][i]
                                default_product_id = existing_item['product_id']
                                default_quantity = existing_item['quantity']
                            else:
                                existing_item = None
                                default_product_id = 0
                                default_quantity = 1
                            with col1:
                                selected_product = st.selectbox(
                                    "제품 선택",
                                    options=[(0, "제품을 선택하세요")] + [(p['product_id'], p['model_name']) for p in products],
                                    format_func=lambda x: x[1],
                                    key=f"product_{i}_edit" if pi_info else f"product_{i}",
                                    index=next((j+1 for j, p in enumerate(products) if p['product_id'] == default_product_id), 0) if pi_info else 0
                                )
                            with col2:
                                quantity = st.number_input(
                                    "수량",
                                    min_value=1,
                                    value=default_quantity,
                                    step=1,
                                    key=f"quantity_{i}_edit" if pi_info else f"quantity_{i}"
                                )
                            # 각 항목의 유효성 검사 및 총액 계산
                            if selected_product[0] != 0 and quantity > 0:
                                item_total = quantity * float(existing_item['unit_price']) if existing_item else 0.0
                                st.text(f"항목 총액: {item_total:.2f}")
                                total_amount += item_total
                                has_valid_items = True
                                items_data.append({
                                    'product_id': selected_product[0],
                                    'quantity': int(quantity),
                                    'total_price': float(item_total)
                                })
                            elif selected_product[0] != 0:
                                st.warning("수량과 단가를 모두 입력해주세요.")
                        # 전체 총액 표시
                        if has_valid_items:
                            st.markdown(f"### 전체 주문 금액: {total_amount:.2f} {currency}")
                        notes = st.text_area("비고", value=pi_info['notes'] if pi_info else "")
                        # 제출 버튼
                        if pi_info:
                            submitted = st.form_submit_button("PI 수정")
                        else:
                            submitted = st.form_submit_button("PI 등록")
                        # 폼 제출 처리
                        if submitted:
                            if not items_data:
                                st.error("최소 하나 이상의 제품을 선택하고 수량과 단가를 입력해주세요.")
                            elif not pi_number:
                                st.error("PI 번호를 입력해주세요.")
                            else:
                                try:
                                    pi_data = {
                                        'pi_number': pi_number,
                                        'supplier_id': selected_supplier['supplier_id'],
                                        'issue_date': issue_date,
                                        'expected_delivery_date': expected_delivery_date,
                                        'payment_terms': payment_terms,
                                        'shipping_terms': shipping_terms,
                                        'notes': notes
                                    }
                                    if pi_info:
                                        # 수정
                                        success, result = update_pi(pi_info['pi_id'], pi_data, items_data)
                                    else:
                                        # 신규 등록
                                        success, result = create_pi(pi_data, items_data)
                                    if success:
                                        st.success("PI가 성공적으로 저장되었습니다.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"PI 저장 중 오류가 발생했습니다: {result}")
                                except Exception as e:
                                    st.error(f"PI 저장 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.warning("선택한 공급업체에 등록된 제품이 없습니다.")
        
        elif pi_submenu == "PI 현황":
            # 공급업체 선택
            suppliers = get_suppliers()
            selected_supplier = st.selectbox(
                "공급업체 선택",
                options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                format_func=lambda x: x['supplier_name'],
                key="pi_supplier"
            )
            
            # PI 목록 조회
            pi_list = get_pi_list(
                supplier_id=selected_supplier['supplier_id'] if selected_supplier['supplier_id'] else None
            )
            
            if pi_list:
                # 데이터프레임 변환
                df = pd.DataFrame(pi_list)
                df = df.drop(columns=['total_amount', 'currency'], errors='ignore')
                df['입고율'] = (df['total_received_qty'] / df['total_ordered_qty'] * 100).round(1)
                def highlight_received(row):
                    if row['입고율'] == 100:
                        return ['background-color: #1b5e20; color: white'] * len(row)
                    elif row['입고율'] > 0:
                        return ['background-color: #e65100; color: white'] * len(row)
                    return [''] * len(row)
                st.dataframe(
                    df.style.apply(highlight_received, axis=1),
                    column_config={
                        "pi_number": "PI 번호",
                        "supplier_name": "공급업체",
                        "issue_date": st.column_config.DateColumn("발행일", format="YYYY-MM-DD"),
                        "expected_delivery_date": st.column_config.DateColumn("예상 납기일", format="YYYY-MM-DD"),
                        "total_ordered_qty": st.column_config.NumberColumn("주문 수량", format="%d개"),
                        "total_received_qty": st.column_config.NumberColumn("입고 수량", format="%d개"),
                        "입고율": st.column_config.NumberColumn("입고율", format="%.1f%%"),
                        "items_summary": "주문 항목",
                        "payment_terms": "지불 조건",
                        "shipping_terms": "선적 조건",
                        "notes": "비고"
                    },
                    hide_index=True
                )
                
                # PI 수정 기능
                st.subheader("PI 수정")
                selected_pi_number = st.selectbox(
                    "수정할 PI 선택",
                    options=[pi['pi_number'] for pi in pi_list],
                    key="edit_pi"
                )
                
                if selected_pi_number:
                    pi_info = get_pi_by_number(selected_pi_number)
                    if pi_info:
                        with st.form("edit_pi_form"):
                            st.info(f"PI 번호: {pi_info['pi_number']} (수정 불가)")
                            
                            # PI 기본 정보
                            col1, col2 = st.columns(2)
                            with col1:
                                issue_date = st.date_input(
                                    "발행일",
                                    value=pi_info['issue_date'],
                                    key="edit_issue_date"
                                )
                            with col2:
                                expected_delivery_date = st.date_input(
                                    "예상 납기일",
                                    value=pi_info['expected_delivery_date'],
                                    key="edit_delivery_date"
                                )
                                payment_terms = st.text_area(
                                    "지불 조건",
                                    value=pi_info['payment_terms'],
                                    key="edit_payment_terms"
                                )
                                shipping_terms = st.text_area(
                                    "선적 조건",
                                    value=pi_info['shipping_terms'],
                                    key="edit_shipping_terms"
                                )
                            
                            # 제품 목록
                            st.subheader("주문 제품 목록")
                            products = get_products(pi_info['supplier_id'])
                            
                            # 기존 항목 정보를 딕셔너리로 변환
                            existing_items = {item['product_id']: item for item in pi_info['items']}
                            
                            items_data = []
                            for i, product in enumerate(products):
                                existing_item = existing_items.get(product['product_id'])
                                st.markdown(f"##### {product['model_name']}")
                                
                                # 기존 항목이 있는 경우 입고 수량 표시
                                if existing_item:
                                    st.info(f"현재 주문: {existing_item['quantity']}개 (입고: {existing_item['received_qty']}개)")
                                
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    quantity = st.number_input(
                                        "수량",
                                        min_value=product['moq'],
                                        value=existing_item['quantity'] if existing_item else product['moq'],
                                        step=1,
                                        key=f"edit_quantity_{i}"
                                    )
                                with col2:
                                    expected_prod_date = st.date_input(
                                        "예상 생산일",
                                        value=existing_item['expected_production_date'] if existing_item else date.today() + timedelta(days=product['lead_time']),
                                        key=f"edit_prod_{i}"
                                    )
                                
                                if quantity > 0:
                                    items_data.append({
                                        'product_id': product['product_id'],
                                        'quantity': quantity,
                                        'expected_production_date': expected_prod_date
                                    })
                            
                            notes = st.text_area(
                                "비고",
                                value=pi_info['notes'],
                                key="edit_notes"
                            )
                            
                            # 제출 버튼 - 폼 컨텍스트 내에서 직접 호출
                            submitted = st.form_submit_button("PI 수정")
                        
                        # 폼 제출 후 처리
                        if submitted:
                            if not items_data:
                                st.error("최소 하나 이상의 제품을 주문해야 합니다.")
                            else:
                                pi_data = {
                                    'issue_date': issue_date,
                                    'expected_delivery_date': expected_delivery_date,
                                    'payment_terms': payment_terms,
                                    'shipping_terms': shipping_terms,
                                    'notes': notes
                                }
                                
                                success, message = update_pi(pi_info['pi_id'], pi_data, items_data)
                                if success:
                                    st.success(message)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"PI 수정 중 오류가 발생했습니다: {message}")
        elif pi_submenu == "미입고 현황":
            st.subheader("미입고 현황 관리")
            
            # 필터 옵션
            col1, col2, col3 = st.columns(3)
            with col1:
                # 공급업체 선택
                suppliers = get_suppliers()
                selected_supplier = st.selectbox(
                    "공급업체 선택",
                    options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="pending_pi_supplier"
                )
            
            with col2:
                # 입고 예정일 기준 필터
                date_filter = st.selectbox(
                    "입고 예정일 기준",
                    ["전체", "이번 주", "이번 달", "다음 달", "지연"],
                    key="date_filter"
                )
            
            with col3:
                # 정렬 기준
                sort_by = st.selectbox(
                    "정렬 기준",
                    ["입고 예정일", "지연일수", "미입고 수량"],
                    key="sort_by"
                )
            
            # PI 목록 조회
            pi_list = get_pi_list(
                supplier_id=selected_supplier['supplier_id'] if selected_supplier['supplier_id'] else None
            )
            
            # 미입고 항목이 있는 PI만 필터링
            pending_pis = []
            for pi in pi_list:
                items = get_pi_items(pi['pi_id'])
                pending_items = [item for item in items if item['quantity'] > item['received_qty']]
                if pending_items:
                    pi['pending_items'] = pending_items
                    pi['total_pending_qty'] = sum(item['quantity'] - item['received_qty'] for item in pending_items)
                    pi['max_delay_days'] = max(
                        (date.today() - item['expected_production_date']).days
                        if item['expected_production_date'] is not None else 0
                        for item in pending_items
                    )
                    pending_pis.append(pi)
            
            # 날짜 필터 적용
            if date_filter != "전체":
                today = date.today()
                filtered_pis = []
                for pi in pending_pis:
                    if date_filter == "이번 주":
                        if any(today <= item['expected_production_date'] <= today + timedelta(days=7) 
                              for item in pi['pending_items']):
                            filtered_pis.append(pi)
                    elif date_filter == "이번 달":
                        if any(today <= item['expected_production_date'] <= today.replace(day=28) + timedelta(days=4)
                              for item in pi['pending_items']):
                            filtered_pis.append(pi)
                    elif date_filter == "다음 달":
                        next_month = today.replace(day=28) + timedelta(days=4)
                        if any(next_month <= item['expected_production_date'] <= next_month.replace(day=28) + timedelta(days=4)
                              for item in pi['pending_items']):
                            filtered_pis.append(pi)
                    elif date_filter == "지연":
                        if any(item['expected_production_date'] < today for item in pi['pending_items']):
                            filtered_pis.append(pi)
                pending_pis = filtered_pis
            
            # 정렬 적용
            if sort_by == "입고 예정일":
                pending_pis.sort(
                    key=lambda x: min(
                        (item['expected_production_date'] for item in x['pending_items'] if item['expected_production_date'] is not None),
                        default=date.max
                    )
                )
            elif sort_by == "지연일수":
                pending_pis.sort(key=lambda x: x['max_delay_days'], reverse=True)
            elif sort_by == "미입고 수량":
                pending_pis.sort(key=lambda x: x['total_pending_qty'], reverse=True)
            
            if pending_pis:
                # 미입고 현황 요약
                total_pending_pis = len(pending_pis)
                total_pending_items = int(sum(int(pi['total_pending_qty']) for pi in pending_pis))
                delayed_items = int(sum(1 for pi in pending_pis if pi['max_delay_days'] > 0))
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("미입고 PI 수", int(total_pending_pis))
                with col2:
                    st.metric("미입고 항목 수", int(total_pending_items))
                with col3:
                    st.metric("지연 항목 수", int(delayed_items), 
                             delta=f"{delayed_items}개 지연" if delayed_items > 0 else None,
                             delta_color="inverse")
                
                # 미입고 상세 목록
                for pi in pending_pis:
                    with st.expander(f"PI 번호: {pi['pi_number']} - {pi['supplier_name']} "
                                   f"(미입고: {pi['total_pending_qty']}개)"):
                        # PI 기본 정보
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**발행일:** {pi['issue_date'].strftime('%Y-%m-%d')}")
                            st.write(f"**예상 납기일:** {pi['expected_delivery_date'].strftime('%Y-%m-%d')}")
                        with col2:
                            st.write(f"**통화:** {pi['currency']}")
                            st.write(f"**총액:** {pi['total_amount']:,.2f} {pi['currency']}")
                        
                        # 미입고 항목 테이블
                        pending_items_data = []
                        for item in pi['pending_items']:
                            pending_qty = item['quantity'] - item['received_qty']
                            if item['expected_production_date'] is not None:
                                delay_days = (date.today() - item['expected_production_date']).days
                            else:
                                delay_days = 0
                            status = "지연" if delay_days > 0 else "예정"
                            
                            pending_items_data.append({
                                "제품명": item['model_name'],
                                "주문 수량": item['quantity'],
                                "입고 수량": item['received_qty'],
                                "미입고 수량": pending_qty,
                                "예상 생산일": item['expected_production_date'],
                                "지연일수": delay_days if delay_days > 0 else 0,
                                "상태": status,
                                "PI 번호": pi['pi_number']  # PI 번호 추가
                            })
                        
                        df = pd.DataFrame(pending_items_data)
                        
                        # 상태별 색상 지정
                        def highlight_pending_status(row):
                            if row['지연일수'] > 0:
                                return ['background-color: #b71c1c; color: white'] * len(row)  # 진한 빨간색
                            return [''] * len(row)
                        
                        st.dataframe(
                            df.style.apply(highlight_pending_status, axis=1),
                            column_config={
                                "제품명": "제품명",
                                "주문 수량": st.column_config.NumberColumn(
                                    "주문 수량",
                                    format="%d개"
                                ),
                                "입고 수량": st.column_config.NumberColumn(
                                    "입고 수량",
                                    format="%d개"
                                ),
                                "미입고 수량": st.column_config.NumberColumn(
                                    "미입고 수량",
                                    format="%d개"
                                ),
                                "예상 생산일": st.column_config.DateColumn(
                                    "예상 생산일",
                                    format="YYYY-MM-DD"
                                ),
                                "지연일수": st.column_config.NumberColumn(
                                    "지연일수",
                                    format="%d일"
                                ),
                                "상태": "상태",
                                "PI 번호": "PI 번호"
                            },
                            hide_index=True
                        )
                        
                        # CI 매칭 버튼 추가
                        if st.button("CI 매칭", key=f"match_ci_{pi['pi_id']}"):
                            st.session_state['selected_pi_for_matching'] = pi['pi_number']
                            st.rerun()
            else:
                st.info("미입고된 PI가 없습니다.")

    elif menu == "제품 관리":
        st.header("📝 제품 관리")
        
        # 제품 관리 서브메뉴
        product_submenu = st.radio(
            "제품 관리 메뉴",
            ["제품 등록", "제품 목록"],
            horizontal=True
        )
        
        # 공급업체 목록 가져오기
        suppliers = get_suppliers()
        
        if not suppliers:
            st.error("등록된 공급업체가 없습니다. 먼저 공급업체를 등록해주세요.")
        else:
            if product_submenu == "제품 등록":
                with st.form("product_registration_form"):
                    # 공급업체 선택
                    selected_supplier = st.selectbox(
                        "공급업체 선택",
                        options=suppliers,
                        format_func=lambda x: x['supplier_name'],
                        index=0  # YUER를 기본값으로 설정
                    )
                    
                    # 제품 정보 입력
                    col1, col2 = st.columns(2)
                    with col1:
                        model_name = st.text_input("모델명")
                        existing_product = None
                        if model_name and selected_supplier:
                            existing_product = get_product_by_model(model_name, selected_supplier['supplier_id'])
                            if existing_product:
                                st.info(f"기존 제품 정보를 불러왔습니다.")
                        # 단가 입력란 제거됨
                    with col2:
                        is_certified = st.checkbox(
                            "인증 제품",
                            value=bool(existing_product['is_certified']) if existing_product else False
                        )
                        certificate_number = st.text_input(
                            "인증서 번호",
                            value=existing_product['certificate_number'] if existing_product and existing_product['is_certified'] else ""
                        ) if is_certified else None
                    
                    notes = st.text_area(
                        "비고",
                        value=existing_product['notes'] if existing_product else ""
                    )
                    
                    # 제출 버튼
                    submitted = st.form_submit_button("제품 등록/수정")
                
                # 폼 제출 후 처리
                if submitted:
                    if not model_name or not selected_supplier:
                        st.error("필수 항목을 모두 입력해주세요.")
                    else:
                        try:
                            if existing_product:
                                # 기존 제품 수정
                                product_data = {
                                    'is_certified': is_certified,
                                    'certificate_number': certificate_number if is_certified else None,
                                    'notes': notes
                                }
                                success, message = update_product(existing_product['product_id'], product_data)
                            else:
                                # 새로운 제품 등록
                                conn = connect_to_db()
                                cursor = conn.cursor()
                                try:
                                    # 1. 제품 등록
                                    cursor.execute("""
                                        INSERT INTO products_logistics 
                                        (supplier_id, model_name, notes)
                                        VALUES (%s, %s, %s)
                                    """, (
                                        selected_supplier['supplier_id'],
                                        model_name,
                                        notes
                                    ))
                                    product_id = cursor.lastrowid
                                    
                                    # 2. 재고 정보 등록
                                    cursor.execute("""
                                        INSERT INTO inventory_logistics 
                                        (product_id, stock, is_certified, certificate_number)
                                        VALUES (%s, 0, %s, %s)
                                    """, (
                                        product_id,
                                        is_certified,
                                        certificate_number if is_certified else None
                                    ))
                                    
                                    conn.commit()
                                    success, message = True, "제품이 성공적으로 등록되었습니다."
                                except Exception as e:
                                    conn.rollback()
                                    raise e
                                finally:
                                    cursor.close()
                                    conn.close()
                                
                                if success:
                                    st.success(message)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"처리 중 오류가 발생했습니다: {message}")
                        except Exception as e:
                            st.error(f"처리 중 오류가 발생했습니다: {str(e)}")
            
            elif product_submenu == "제품 목록":
                # 공급업체 선택
                selected_supplier = st.selectbox(
                    "공급업체 선택",
                    options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="product_list_supplier"
                )
                
                # 제품 목록 조회
                products = get_products(
                    supplier_id=selected_supplier['supplier_id'] if selected_supplier['supplier_id'] else None
                )
                
                if products:
                    # 데이터프레임 변환
                    df = pd.DataFrame(products)
                    
                    # 상태별 색상 지정
                    def highlight_status(row):
                        if row['current_stock'] == 0:
                            return ['background-color: #b71c1c; color: white'] * len(row)  # 진한 빨간색
                        return [''] * len(row)
                    
                    st.dataframe(
                        df.style.apply(highlight_status, axis=1),
                        column_config={
                            "model_name": "모델명",
                            "supplier_name": "공급업체",
                            "current_stock": st.column_config.NumberColumn(
                                "현재 재고",
                                format="%d개"
                            ),
                            "is_certified": st.column_config.Column(
                                "인증 상태",
                                width="small"
                            ),
                            "certificate_number": "인증서 번호",
                            "notes": "비고"
                        },
                        hide_index=True
                    )

                    # 제품별 삭제 버튼 추가
                    st.subheader("제품 삭제")
                    for product in products:
                        with st.expander(f"{product['model_name']} (공급업체: {product['supplier_name']})"):
                            st.write(f"현재 재고: {product['current_stock']}개")
                            st.write(f"비고: {product['notes']}")
                            if st.button("제품 삭제", key=f"delete_product_{product['product_id']}"):
                                # 삭제 확인
                                if st.warning(f"정말로 이 제품을 삭제하시겠습니까? (모든 재고 정보도 함께 삭제됩니다)"):
                                    try:
                                        conn = connect_to_db()
                                        cursor = conn.cursor()
                                        # 재고 정보 먼저 삭제
                                        cursor.execute("DELETE FROM inventory_logistics WHERE product_id = %s", (product['product_id'],))
                                        # 제품 정보 삭제
                                        cursor.execute("DELETE FROM products_logistics WHERE product_id = %s", (product['product_id'],))
                                        conn.commit()
                                        cursor.close()
                                        conn.close()
                                        st.success("제품이 성공적으로 삭제되었습니다.")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"제품 삭제 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.info("등록된 제품이 없습니다.")

    elif menu == "재고 이력":
        st.header("📜 재고 입출고 이력")
        conn = connect_to_db()
        # 기간 필터
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작일", value=date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("종료일", value=date.today())
        # 검색어 입력
        search_term = st.text_input("검색어 (제품명, 변경유형, 참조번호, 비고 등)")
        # 쿼리 작성
        query = '''
            SELECT t.date, p.model_name, t.change_type, t.quantity, t.reference_number, t.notes, t.destination
            FROM inventory_transactions t
            JOIN products_logistics p ON t.product_id = p.product_id
            WHERE DATE(t.date) >= %s AND DATE(t.date) <= %s
        '''
        params = [start_date, end_date]
        if search_term:
            query += ''' AND (
                p.model_name LIKE %s OR
                t.change_type LIKE %s OR
                t.reference_number LIKE %s OR
                t.notes LIKE %s OR
                t.destination LIKE %s
            )'''
            for _ in range(5):
                params.append(f"%{search_term}%")
        query += " ORDER BY t.date DESC"
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        st.dataframe(df, use_container_width=True)
        # 엑셀 다운로드
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "엑셀 다운로드",
                csv,
                f"재고이력_{start_date}_{end_date}.csv",
                "text/csv",
                key='download-xlsx'
            )

if __name__ == "__main__":
    main() 