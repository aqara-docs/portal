import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import time
import numpy as np
from scipy import stats

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
        
        # AQARA가 없으면 추가
        aqara_exists = any(s['supplier_name'] == 'AQARA' for s in suppliers)
        if not aqara_exists:
            cursor.execute(
                "INSERT INTO suppliers (supplier_name, contact_person, email, phone, address) VALUES (%s, %s, %s, %s, %s)",
                ("AQARA", "AQARA", "aqara@example.com", "123-456-7898", "AQARA Address")
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
                ORDER BY p.product_id
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
                ORDER BY p.product_id
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
            SELECT pi_items.*, p.model_name,
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
                    payment_terms = %s,
                    shipping_terms = %s,
                    project_name = %s,
                    notes = %s
                WHERE pi_id = %s
            """, (
                pi_data['supplier_id'],
                pi_data['issue_date'],
                pi_data['expected_delivery_date'],
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
                        SET quantity = %s
                        WHERE pi_item_id = %s
                    """, (
                        item['quantity'],
                        existing_item['pi_item_id']
                    ))
                else:
                    # 새로운 항목 추가
                    cursor.execute("""
                        INSERT INTO pi_items 
                        (pi_id, product_id, quantity)
                        VALUES (%s, %s, %s)
                    """, (
                        pi_id, item['product_id'], item['quantity']
                    ))
            # 더 이상 필요하지 않은 항목은 수량을 0으로 설정
            for existing_item in existing_items.values():
                if not any(item['product_id'] == existing_item['product_id'] for item in items_data):
                    cursor.execute("""
                        UPDATE pi_items 
                        SET quantity = 0
                        WHERE pi_item_id = %s
                    """, (existing_item['pi_item_id'],))
        else:
            # 새로운 PI 생성
            cursor.execute("""
                INSERT INTO proforma_invoices 
                (pi_number, supplier_id, issue_date, expected_delivery_date, 
                 payment_terms, shipping_terms, 
                 project_name, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pi_data['pi_number'], pi_data['supplier_id'],
                pi_data['issue_date'], pi_data['expected_delivery_date'],
                pi_data['payment_terms'],
                pi_data['shipping_terms'], pi_data.get('project_name', ''), pi_data['notes']
            ))
            pi_id = cursor.lastrowid
            # 새로운 PI 항목 추가
            for item in items_data:
                cursor.execute("""
                    INSERT INTO pi_items 
                    (pi_id, product_id, quantity)
                    VALUES (%s, %s, %s)
                """, (
                    pi_id, item['product_id'], item['quantity']
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
                payment_terms = %s,
                shipping_terms = %s,
                notes = %s
            WHERE pi_id = %s
        """, (
            pi_data['issue_date'],
            pi_data['expected_delivery_date'],
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
                    SET quantity = %s
                    WHERE pi_item_id = %s
                """, (
                    item['quantity'],
                    existing_item['pi_item_id']
                ))
                del existing_items[item['product_id']]
            else:
                # 새로운 항목 추가
                cursor.execute("""
                    INSERT INTO pi_items 
                    (pi_id, product_id, quantity, expected_production_date)
                    VALUES (%s, %s, %s, %s)
                """, (
                    pi_id, item['product_id'], item['quantity'],
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
             shipping_details, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            ci_data['ci_number'], ci_data.get('pi_id'),
            ci_data['supplier_id'], ci_data['shipping_date'],
            ci_data['arrival_date'],
            ci_data['shipping_details'], ci_data['notes']
        ))
        ci_id = cursor.lastrowid
        
        # 2. FIFO 매칭: 동일 제품의 미입고 PI 항목을 오래된 순으로 소진
        from decimal import Decimal
        for item in items_data:
            product_id = item['product_id']
            total_quantity = int(item['quantity'])
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
                        (ci_id, pi_item_id, product_id, quantity, shipping_date, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        ci_id, pi_item['pi_item_id'], product_id, to_receive, ci_data['shipping_date'], notes
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
            query += " AND ci.shipping_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND ci.shipping_date <= %s"
            params.append(end_date)
            
        query += " GROUP BY ci.ci_id ORDER BY ci.shipping_date DESC"
        
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
        # 트랜잭션 시작
        conn.start_transaction()
        
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
        
        # 1. 먼저 PI 항목들을 삭제 (pi_items 테이블)
        cursor.execute("DELETE FROM pi_items WHERE pi_id = %s", (pi_id,))
        
        # 2. 그 다음 PI를 삭제 (proforma_invoices 테이블)
        cursor.execute("DELETE FROM proforma_invoices WHERE pi_id = %s", (pi_id,))
        
        # 트랜잭션 커밋
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
    
    # 인증 기능 (간단한 비밀번호 보호, .env 필수)
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    admin_pw = os.getenv('ADMIN_PASSWORD')
    if not admin_pw:
        st.error('환경변수(ADMIN_PASSWORD)가 설정되어 있지 않습니다. .env 파일을 확인하세요.')
        st.stop()

    if not st.session_state.authenticated:
        password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
        if password == admin_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
                st.error("관리자 권한이 필요합니다")
            st.stop()
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["재고 현황", "입고 관리", "A/S 지원 입고", "출고 관리", "재고 조정", "재고 분석", "PI 관리", "CI 관리", "제품 관리", "재고 이력"]
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
                            # 총액 표기 제거
                        
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
                                    # 총액 표기 제거
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
            st.subheader("🔗 CI와 미입고 PI 매칭 관리")
            
            # 탭으로 기능 분리
            tab1, tab2, tab3 = st.tabs(["📋 미입고 PI 현황", "🔗 새 CI 매칭", "📊 매칭 이력"])
            
            with tab1:
                st.write("### 📋 미입고 PI 현황")
                
                # 공급업체 선택
                suppliers = get_suppliers()
                selected_supplier = st.selectbox(
                    "공급업체 선택",
                    options=suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="pending_pi_supplier"
                )
                
                if selected_supplier:
                    # 미입고 PI 항목 조회
                    pending_items = get_pending_pi_items(selected_supplier['supplier_id'])
                    
                    if pending_items:
                        st.success(f"{selected_supplier['supplier_name']}의 미입고 항목: {len(pending_items)}건")
                        
                        # 미입고 항목을 DataFrame으로 표시
                        df_pending = pd.DataFrame(pending_items)
                        df_pending['미입고수량'] = df_pending['ordered_qty'] - df_pending['received_qty']
                        df_pending['입고율(%)'] = (df_pending['received_qty'] / df_pending['ordered_qty'] * 100).round(1)
                        
                        # 표시할 컬럼 선택
                        display_df = df_pending[['pi_number', 'model_name', 'ordered_qty', 'received_qty', '미입고수량', '입고율(%)', 'expected_delivery_date']].copy()
                        display_df.columns = ['PI번호', '모델명', '주문수량', '입고수량', '미입고수량', '입고율(%)', '예상납기일']
                        
                        # 스타일 적용
                        def highlight_pending(row):
                            if row['미입고수량'] > 0:
                                return ['background-color: #f44336; color: white'] * len(row)  # 빨간색 배경, 흰색 글자
                            return [''] * len(row)
                        
                        st.dataframe(
                            display_df.style.apply(highlight_pending, axis=1),
                            use_container_width=True,
                            height=400
                        )
                        
                        # 요약 정보
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("총 미입고 건수", len(pending_items))
                        with col2:
                            total_pending_qty = df_pending['미입고수량'].sum()
                            st.metric("총 미입고 수량", f"{total_pending_qty:,}개")
                        with col3:
                            avg_completion = df_pending['입고율(%)'].mean()
                            st.metric("평균 입고율", f"{avg_completion:.1f}%")
                        with col4:
                            overdue_count = len(df_pending[df_pending['expected_delivery_date'] < date.today()])
                            st.metric("지연 건수", overdue_count)
                    else:
                        st.info(f"{selected_supplier['supplier_name']}의 미입고 항목이 없습니다.")
            
            with tab2:
                st.write("### 🔗 새 CI와 미입고 PI 매칭")
                
                # 공급업체 선택
                suppliers = get_suppliers()
                selected_supplier_ci = st.selectbox(
                    "공급업체 선택",
                    options=suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="ci_matching_supplier"
                )
                
                if selected_supplier_ci:
                    # 미입고 PI 항목 조회
                    pending_items = get_pending_pi_items(selected_supplier_ci['supplier_id'])
                    
                    if pending_items:
                        st.info(f"매칭 가능한 미입고 항목: {len(pending_items)}건")
                        
                        # CI 정보 입력
                        with st.form("new_ci_matching_form"):
                            st.write("#### CI 기본 정보")
                            col1, col2 = st.columns(2)
                            with col1:
                                ci_number = st.text_input("CI 번호*", placeholder="CI-2024-001")
                                shipping_date = st.date_input("선적일*", value=datetime.now().date())
                            with col2:
                                arrival_date = st.date_input("도착 예정일", value=datetime.now().date() + timedelta(days=7))
                                shipping_details = st.text_input("선적 상세", placeholder="컨테이너 번호, 선박명 등")
                            
                            notes = st.text_area("비고")
                            
                            st.write("#### 매칭할 제품 선택")
                            
                            # 제품별로 그룹화하여 표시
                            product_groups = {}
                            for item in pending_items:
                                product_id = item['product_id']
                                if product_id not in product_groups:
                                    product_groups[product_id] = {
                                        'model_name': item['model_name'],
                                        'total_pending': 0,
                                        'pi_items': []
                                    }
                                product_groups[product_id]['total_pending'] += int(item['ordered_qty'] - item['received_qty'])  # int로 변환
                                product_groups[product_id]['pi_items'].append(item)
                            
                            selected_items = []
                            
                            for product_id, group in product_groups.items():
                                st.write(f"**{group['model_name']}** (총 미입고: {group['total_pending']}개)")
                                
                                # 이 제품의 입고 수량 입력
                                received_qty = st.number_input(
                                    f"{group['model_name']} 입고 수량",
                                    min_value=0,
                                    max_value=int(group['total_pending']),  # int로 변환
                                    value=0,
                                    step=1,
                                    key=f"qty_{product_id}"
                                )
                                
                                if received_qty > 0:
                                    selected_items.append({
                                        'product_id': product_id,
                                        'model_name': group['model_name'],
                                        'quantity': received_qty,
                                        'pi_items': group['pi_items']
                                    })
                                
                                # 관련 PI 목록 표시
                                with st.expander(f"{group['model_name']} 관련 PI 목록"):
                                    for pi_item in group['pi_items']:
                                        pending_qty = pi_item['ordered_qty'] - pi_item['received_qty']
                                        st.write(f"- PI: {pi_item['pi_number']}, 미입고: {pending_qty}개, 예상납기: {pi_item['expected_delivery_date']}")
                            
                            # 매칭 처리 버튼
                            submitted = st.form_submit_button("CI 생성 및 PI 매칭 처리", type="primary")
                            
                            if submitted and ci_number and selected_items:
                                try:
                                    # CI 생성 및 FIFO 매칭 처리
                                    ci_data = {
                                        'ci_number': ci_number,
                                        'supplier_id': selected_supplier_ci['supplier_id'],
                                        'shipping_date': shipping_date,
                                        'arrival_date': arrival_date,
                                        'shipping_details': shipping_details,
                                        'notes': notes
                                    }
                                    
                                    success, ci_id = create_ci(ci_data, selected_items)
                                    
                                    if success:
                                        st.success(f"✅ CI {ci_number}가 성공적으로 생성되고 미입고 PI와 매칭되었습니다!")
                                        
                                        # 매칭 결과 표시
                                        st.write("#### 매칭 결과")
                                        for item in selected_items:
                                            st.write(f"- {item['model_name']}: {item['quantity']}개 입고 처리")
                                        
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"CI 생성 중 오류가 발생했습니다: {ci_id}")
                                        
                                except Exception as e:
                                    st.error(f"처리 중 오류가 발생했습니다: {str(e)}")
                            elif submitted and not ci_number:
                                st.error("CI 번호를 입력해주세요.")
                            elif submitted and not selected_items:
                                st.error("입고할 제품을 선택해주세요.")
                    else:
                        st.info(f"{selected_supplier_ci['supplier_name']}의 미입고 항목이 없습니다.")
            
            with tab3:
                st.write("### 📊 CI-PI 매칭 이력")
                
                # 공급업체 선택
                suppliers = get_suppliers()
                selected_supplier_history = st.selectbox(
                    "공급업체 선택",
                    options=suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="history_supplier"
                )
                
                # 기간 선택
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("시작일", value=datetime.now().date() - timedelta(days=30))
                with col2:
                    end_date = st.date_input("종료일", value=datetime.now().date())
                
                if selected_supplier_history:
                    # CI 목록 조회
                    ci_list = get_ci_list(selected_supplier_history['supplier_id'], start_date, end_date)
                    
                    if ci_list:
                        st.success(f"조회 기간 내 CI: {len(ci_list)}건")
                        
                        # CI별 매칭 정보 표시
                        for ci in ci_list:
                            with st.expander(f"CI: {ci['ci_number']} ({ci['shipping_date']})"):
                                # CI 항목 조회
                                conn = connect_to_db()
                                cursor = conn.cursor(dictionary=True)
                                try:
                                    cursor.execute("""
                                        SELECT 
                                            ci_items.*,
                                            p.model_name,
                                            pi.pi_number
                                        FROM ci_items
                                        JOIN products_logistics p ON ci_items.product_id = p.product_id
                                        LEFT JOIN pi_items ON ci_items.pi_item_id = pi_items.pi_item_id
                                        LEFT JOIN proforma_invoices pi ON pi_items.pi_id = pi.pi_id
                                        WHERE ci_items.ci_id = %s
                                    """, (ci['ci_id'],))
                                    ci_items = cursor.fetchall()
                                    
                                    if ci_items:
                                        for item in ci_items:
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.write(f"**제품:** {item['model_name']}")
                                                st.write(f"**수량:** {item['quantity']}개")
                                            with col2:
                                                if item['pi_number']:
                                                    st.write(f"**연결 PI:** {item['pi_number']}")
                                                else:
                                                    st.write("**연결 PI:** 직접 입고")
                                            with col3:
                                                st.write(f"**입고일:** {item['shipping_date']}")
                                                if item['notes']:
                                                    st.write(f"**비고:** {item['notes']}")
                                finally:
                                    cursor.close()
                                    conn.close()
                    else:
                        st.info("조회 기간 내 CI가 없습니다.")
    
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
        
        # 제품 선택 (form 밖에서)
        selected_product = None
        current_stock = 0
        
        if products:
            # 재고가 있는 제품만 필터링
            available_products = [p for p in products if p['current_stock'] > 0]
            
            if available_products:
                selected_product = st.selectbox(
                    "제품 선택",
                    options=available_products,
                    format_func=lambda p: f"{p['model_name']} (ID:{p['product_id']}, 재고: {p['current_stock']}개)",
                    key="outbound_product_select"
                )
                
                if selected_product:
                    stock_info = get_stock(selected_product['product_id'])
                    current_stock = int(stock_info['stock'])
                    st.info(f"현재 재고: {current_stock}개")
            else:
                st.warning("현재 재고가 있는 제품이 없습니다.")

        # 출고 폼
        with st.form("outbound_form"):
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
                        value=current_stock if current_stock > 1 else 1,
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
        
        # 분석 탭 추가
        analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs(["재고 현황", "재고 이동", "리드타임 분석"])
        
        with analysis_tab1:
            # 기존 재고 분석 코드
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
        
        with analysis_tab2:
            st.subheader("재고 이동 분석")
            # 기존 재고 이동 분석 코드는 그대로 유지
            movements = get_stock_movements(30)
            if movements:
                df_movements = pd.DataFrame(movements)
                
                # 월별 집계
                df_movements['month'] = pd.to_datetime(df_movements['date']).dt.strftime('%Y-%m')
                monthly_movements = df_movements.groupby(['month', 'model_name']).agg({
                    'in_qty': 'sum',
                    'out_qty': 'sum'
                }).reset_index()
                
                fig = px.bar(
                    monthly_movements,
                    x='month',
                    y=['in_qty', 'out_qty'],
                    color='model_name',
                    title='월별 제품별 입출고 현황',
                    barmode='group'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with analysis_tab3:
            st.subheader("📊 리드타임 분석 및 예측")
            
            # 리드타임 분석 서브탭
            lt_tab1, lt_tab2, lt_tab3, lt_tab4 = st.tabs(["📈 리드타임 통계", "🔮 리드타임 예측", "📅 리드타임 추이", "⚡ 실시간 분석"])
            
            with lt_tab1:
                st.write("### 📈 리드타임 통계 분석")
                
                # 필터 옵션
                col1, col2, col3 = st.columns(3)
                with col1:
                    suppliers = get_suppliers()
                    selected_supplier_lt = st.selectbox(
                        "공급업체 선택",
                        options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                        format_func=lambda x: x['supplier_name'],
                        key="lt_supplier"
                    )
                
                with col2:
                    lt_start_date = st.date_input(
                        "분석 시작일",
                        value=date.today() - timedelta(days=180),
                        key="lt_start"
                    )
                
                with col3:
                    lt_end_date = st.date_input(
                        "분석 종료일",
                        value=date.today(),
                        key="lt_end"
                    )
                
                # 리드타임 데이터 조회
                lead_time_data = get_lead_time_data(
                    supplier_id=selected_supplier_lt['supplier_id'] if selected_supplier_lt['supplier_id'] else None,
                    start_date=lt_start_date,
                    end_date=lt_end_date
                )
                
                if lead_time_data:
                    # 통계 계산
                    stats = calculate_lead_time_statistics(lead_time_data)
                    
                    if stats:
                        # 전체 통계
                        st.subheader("📊 전체 리드타임 통계")
                        overall = stats['overall']
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("총 주문 수", f"{overall['total_orders']:,}건")
                            st.metric("평균 리드타임", f"{overall['avg_lead_time']:.1f}일")
                        with col2:
                            st.metric("중간값 리드타임", f"{overall['median_lead_time']:.1f}일")
                            st.metric("표준편차", f"{overall['std_lead_time']:.1f}일")
                        with col3:
                            st.metric("최소 리드타임", f"{overall['min_lead_time']:.1f}일")
                            st.metric("최대 리드타임", f"{overall['max_lead_time']:.1f}일")
                        with col4:
                            st.metric("평균 지연일", f"{overall['avg_delay']:.1f}일")
                            st.metric("정시 납기율", f"{overall['on_time_rate']:.1f}%")
                        
                        # 공급업체별 통계
                        st.subheader("🏢 공급업체별 리드타임 통계")
                        supplier_stats = stats['supplier']
                        
                        if not supplier_stats.empty:
                            # 통계 테이블 표시
                            st.dataframe(
                                supplier_stats,
                                use_container_width=True,
                                column_config={
                                    "actual_lead_time": st.column_config.NumberColumn("실제 리드타임", format="%.1f일"),
                                    "delay_days": st.column_config.NumberColumn("지연일수", format="%.1f일")
                                }
                            )
                            
                            # 공급업체별 평균 리드타임 차트
                            fig = px.bar(
                                x=supplier_stats.index,
                                y=supplier_stats[('actual_lead_time', 'mean')],
                                title="공급업체별 평균 리드타임",
                                labels={'x': '공급업체', 'y': '평균 리드타임 (일)'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # 제품별 통계
                        st.subheader("📦 제품별 리드타임 통계")
                        product_stats = stats['product']
                        
                        if not product_stats.empty:
                            # 상위 10개 제품만 표시
                            top_products = product_stats.head(10)
                            
                            st.dataframe(
                                top_products,
                                use_container_width=True,
                                column_config={
                                    "actual_lead_time": st.column_config.NumberColumn("실제 리드타임", format="%.1f일"),
                                    "delay_days": st.column_config.NumberColumn("지연일수", format="%.1f일")
                                }
                            )
                            
                            # 제품별 평균 리드타임 차트
                            fig2 = px.bar(
                                x=[f"{idx[0]} - {idx[1]}" for idx in top_products.index],
                                y=top_products[('actual_lead_time', 'mean')],
                                title="제품별 평균 리드타임 (상위 10개)",
                                labels={'x': '공급업체 - 제품명', 'y': '평균 리드타임 (일)'}
                            )
                            fig2.update_xaxes(tickangle=45)
                            st.plotly_chart(fig2, use_container_width=True)
                        
                        # 리드타임 분포 히스토그램
                        st.subheader("📊 리드타임 분포")
                        raw_data = stats['raw_data']
                        
                        fig3 = px.histogram(
                            raw_data,
                            x='actual_lead_time',
                            nbins=20,
                            title="실제 리드타임 분포",
                            labels={'actual_lead_time': '리드타임 (일)', 'count': '주문 수'}
                        )
                        st.plotly_chart(fig3, use_container_width=True)
                        
                        # 지연일수 분포
                        fig4 = px.histogram(
                            raw_data,
                            x='delay_days',
                            nbins=20,
                            title="지연일수 분포",
                            labels={'delay_days': '지연일수 (일)', 'count': '주문 수'}
                        )
                        st.plotly_chart(fig4, use_container_width=True)
                        
                else:
                    st.info("분석 기간 내 리드타임 데이터가 없습니다.")
            
            with lt_tab2:
                st.write("### 🔮 리드타임 예측")
                
                # 예측 대상 선택
                col1, col2 = st.columns(2)
                with col1:
                    suppliers = get_suppliers()
                    selected_supplier_pred = st.selectbox(
                        "공급업체 선택",
                        options=suppliers,
                        format_func=lambda x: x['supplier_name'],
                        key="pred_supplier"
                    )
                
                with col2:
                    if selected_supplier_pred:
                        products = get_products(selected_supplier_pred['supplier_id'])
                        selected_product_pred = st.selectbox(
                            "제품 선택",
                            options=products,
                            format_func=lambda x: x['model_name'],
                            key="pred_product"
                        )
                    else:
                        selected_product_pred = None
                
                # 신뢰도 설정
                confidence_level = st.slider(
                    "예측 신뢰도",
                    min_value=0.7,
                    max_value=0.95,
                    value=0.8,
                    step=0.05,
                    help="높은 신뢰도는 더 넓은 예측 구간을 제공합니다."
                )
                
                if selected_supplier_pred and selected_product_pred:
                    # 예측 실행
                    if st.button("리드타임 예측 실행", type="primary"):
                        with st.spinner("예측 분석 중..."):
                            prediction, error = predict_lead_time(
                                selected_supplier_pred['supplier_id'],
                                selected_product_pred['product_id'],
                                confidence_level
                            )
                        
                        if prediction:
                            st.success("✅ 리드타임 예측 완료!")
                            
                            # 예측 결과 표시
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric(
                                    "예상 리드타임",
                                    f"{prediction['expected_lead_time']}일",
                                    f"±{prediction['std_deviation']:.1f}일"
                                )
                            with col2:
                                st.metric(
                                    "신뢰구간",
                                    f"{prediction['confidence_interval'][0]}~{prediction['confidence_interval'][1]}일",
                                    f"{confidence_level*100:.0f}% 신뢰도"
                                )
                            with col3:
                                st.metric(
                                    "데이터 포인트",
                                    f"{prediction['data_points']}건",
                                    f"최근 {len(prediction['recent_trend'])}건 기준"
                                )
                            
                            # 상세 정보
                            st.subheader("📋 예측 상세 정보")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**과거 최소 리드타임:** {prediction['min_historical']}일")
                                st.write(f"**과거 최대 리드타임:** {prediction['max_historical']}일")
                                st.write(f"**표준편차:** {prediction['std_deviation']}일")
                            with col2:
                                st.write(f"**신뢰구간 하한:** {prediction['confidence_interval'][0]}일")
                                st.write(f"**신뢰구간 상한:** {prediction['confidence_interval'][1]}일")
                                st.write(f"**분석 기반 주문 수:** {prediction['data_points']}건")
                            
                            # 최근 추이
                            if len(prediction['recent_trend']) > 1:
                                st.subheader("📈 최근 리드타임 추이")
                                fig = px.line(
                                    x=range(len(prediction['recent_trend'])),
                                    y=prediction['recent_trend'],
                                    title="최근 5건 리드타임 추이",
                                    labels={'x': '주문 순서 (최신순)', 'y': '리드타임 (일)'}
                                )
                                fig.add_hline(y=prediction['expected_lead_time'], line_dash="dash", line_color="red", 
                                             annotation_text=f"예측 평균: {prediction['expected_lead_time']}일")
                                st.plotly_chart(fig, use_container_width=True)
                            
                            # 예측 활용 가이드
                            st.subheader("💡 예측 활용 가이드")
                            st.info(f"""
                            **권장 발주 시점:** 현재 날짜로부터 {prediction['expected_lead_time']}일 전
                            
                            **안전 마진:** {prediction['confidence_interval'][1] - prediction['expected_lead_time']}일 추가 여유
                            
                            **최대 지연 대비:** {prediction['max_historical'] - prediction['expected_lead_time']}일 추가 준비
                            """)
                        
                        elif error:
                            st.error(f"예측 실패: {error}")
                        else:
                            st.warning("예측을 위한 충분한 데이터가 없습니다.")
                else:
                    st.info("공급업체와 제품을 선택한 후 예측을 실행하세요.")
            
            with lt_tab3:
                st.write("### 📅 리드타임 추이 분석")
                
                # 추이 분석 필터
                col1, col2 = st.columns(2)
                with col1:
                    suppliers = get_suppliers()
                    selected_supplier_trend = st.selectbox(
                        "공급업체 선택",
                        options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                        format_func=lambda x: x['supplier_name'],
                        key="trend_supplier"
                    )
                
                with col2:
                    trend_days = st.selectbox(
                        "분석 기간",
                        options=[30, 60, 90, 180, 365],
                        format_func=lambda x: f"{x}일",
                        index=2
                    )
                
                # 리드타임 추이 데이터 조회
                trend_data = get_lead_time_trends(
                    supplier_id=selected_supplier_trend['supplier_id'] if selected_supplier_trend['supplier_id'] else None,
                    days=trend_days
                )
                
                if trend_data:
                    df_trend = pd.DataFrame(trend_data)
                    
                    # 월별 평균 리드타임 추이
                    st.subheader("📈 월별 평균 리드타임 추이")
                    
                    monthly_avg = df_trend.groupby('month').agg({
                        'avg_lead_time': 'mean',
                        'order_count': 'sum',
                        'avg_delay': 'mean'
                    }).reset_index()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig1 = px.line(
                            monthly_avg,
                            x='month',
                            y='avg_lead_time',
                            title="월별 평균 리드타임",
                            labels={'month': '월', 'avg_lead_time': '평균 리드타임 (일)'}
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    
                    with col2:
                        fig2 = px.line(
                            monthly_avg,
                            x='month',
                            y='avg_delay',
                            title="월별 평균 지연일수",
                            labels={'month': '월', 'avg_delay': '평균 지연일수 (일)'}
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                    
                    # 공급업체별 추이
                    if selected_supplier_trend['supplier_id'] is None:
                        st.subheader("🏢 공급업체별 리드타임 추이")
                        supplier_trend = df_trend.groupby(['month', 'supplier_name']).agg({
                            'avg_lead_time': 'mean'
                        }).reset_index()
                        
                        fig3 = px.line(
                            supplier_trend,
                            x='month',
                            y='avg_lead_time',
                            color='supplier_name',
                            title="공급업체별 월별 리드타임",
                            labels={'month': '월', 'avg_lead_time': '평균 리드타임 (일)', 'supplier_name': '공급업체'}
                        )
                        st.plotly_chart(fig3, use_container_width=True)
                    
                    # 상세 데이터 테이블
                    st.subheader("📊 상세 추이 데이터")
                    st.dataframe(
                        df_trend,
                        column_config={
                            "month": "월",
                            "supplier_name": "공급업체",
                            "model_name": "제품명",
                            "avg_lead_time": st.column_config.NumberColumn("평균 리드타임", format="%.1f일"),
                            "order_count": st.column_config.NumberColumn("주문 수", format="%d건"),
                            "avg_delay": st.column_config.NumberColumn("평균 지연일수", format="%.1f일")
                        },
                        hide_index=True
                    )
                    
                else:
                    st.info("분석 기간 내 리드타임 추이 데이터가 없습니다.")
            
            with lt_tab4:
                st.write("### ⚡ 실시간 리드타임 분석")
                
                # 실시간 분석 옵션
                col1, col2 = st.columns(2)
                with col1:
                    realtime_supplier = st.selectbox(
                        "공급업체 선택",
                        options=suppliers,
                        format_func=lambda x: x['supplier_name'],
                        key="realtime_supplier"
                    )
                
                with col2:
                    analysis_type = st.selectbox(
                        "분석 유형",
                        ["전체 제품", "특정 제품", "지연 위험 제품"],
                        key="realtime_analysis"
                    )
                
                if realtime_supplier:
                    # 실시간 데이터 조회
                    recent_data = get_lead_time_data(
                        supplier_id=realtime_supplier['supplier_id'],
                        start_date=date.today() - timedelta(days=30)
                    )
                    
                    if recent_data:
                        df_recent = pd.DataFrame(recent_data)
                        
                        if analysis_type == "전체 제품":
                            st.subheader("📊 전체 제품 리드타임 현황")
                            
                            # 제품별 요약
                            product_summary = df_recent.groupby('model_name').agg({
                                'actual_lead_time': ['mean', 'count', 'std'],
                                'delay_days': 'mean'
                            }).round(1)
                            
                            # 위험도 평가
                            product_summary['risk_level'] = product_summary.apply(
                                lambda x: '🔴' if x[('delay_days', 'mean')] > 5 else '🟡' if x[('delay_days', 'mean')] > 0 else '🟢', axis=1
                            )
                            
                            st.dataframe(
                                product_summary,
                                use_container_width=True,
                                column_config={
                                    "actual_lead_time": st.column_config.NumberColumn("평균 리드타임", format="%.1f일"),
                                    "delay_days": st.column_config.NumberColumn("평균 지연일수", format="%.1f일")
                                }
                            )
                        
                        elif analysis_type == "특정 제품":
                            st.subheader("🎯 특정 제품 상세 분석")
                            
                            products = get_products(realtime_supplier['supplier_id'])
                            selected_product_detail = st.selectbox(
                                "분석할 제품 선택",
                                options=products,
                                format_func=lambda x: x['model_name'],
                                key="detail_product"
                            )
                            
                            if selected_product_detail:
                                product_data = df_recent[df_recent['model_name'] == selected_product_detail['model_name']]
                                
                                if not product_data.empty:
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("평균 리드타임", f"{product_data['actual_lead_time'].mean():.1f}일")
                                        st.metric("최소 리드타임", f"{product_data['actual_lead_time'].min():.1f}일")
                                    with col2:
                                        st.metric("최대 리드타임", f"{product_data['actual_lead_time'].max():.1f}일")
                                        st.metric("표준편차", f"{product_data['actual_lead_time'].std():.1f}일")
                                    with col3:
                                        st.metric("평균 지연일수", f"{product_data['delay_days'].mean():.1f}일")
                                        st.metric("정시 납기율", f"{len(product_data[product_data['delay_days'] <= 0]) / len(product_data) * 100:.1f}%")
                                    
                                    # 리드타임 분포
                                    fig = px.histogram(
                                        product_data,
                                        x='actual_lead_time',
                                        nbins=10,
                                        title=f"{selected_product_detail['model_name']} 리드타임 분포",
                                        labels={'actual_lead_time': '리드타임 (일)', 'count': '주문 수'}
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                        
                        elif analysis_type == "지연 위험 제품":
                            st.subheader("⚠️ 지연 위험 제품 분석")
                            
                            # 지연 위험 제품 필터링
                            risk_products = df_recent[df_recent['delay_days'] > 0].groupby('model_name').agg({
                                'delay_days': ['mean', 'count'],
                                'actual_lead_time': 'mean'
                            }).round(1)
                            
                            if not risk_products.empty:
                                st.warning(f"지연 위험이 있는 제품: {len(risk_products)}개")
                                
                                # 위험도별 정렬
                                risk_products['risk_score'] = risk_products[('delay_days', 'mean')] * risk_products[('delay_days', 'count')]
                                risk_products = risk_products.sort_values('risk_score', ascending=False)
                                
                                st.dataframe(
                                    risk_products,
                                    use_container_width=True,
                                    column_config={
                                        "delay_days": st.column_config.NumberColumn("평균 지연일수", format="%.1f일"),
                                        "actual_lead_time": st.column_config.NumberColumn("평균 리드타임", format="%.1f일")
                                    }
                                )
                                
                                # 위험 제품 추이
                                fig = px.bar(
                                    x=risk_products.index,
                                    y=risk_products[('delay_days', 'mean')],
                                    title="지연 위험 제품별 평균 지연일수",
                                    labels={'x': '제품명', 'y': '평균 지연일수 (일)'}
                                )
                                fig.update_xaxes(tickangle=45)
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.success("✅ 지연 위험이 있는 제품이 없습니다.")
                    
                    else:
                        st.info("최근 30일 내 리드타임 데이터가 없습니다.")

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
                        with col2:
                            expected_delivery_date = st.date_input("예상 납기일", value=pi_info['expected_delivery_date'] if pi_info else date.today())
                            payment_terms = st.text_area("지불 조건", value=pi_info['payment_terms'] if pi_info else "")
                            shipping_terms = st.text_area("선적 조건", value=pi_info['shipping_terms'] if pi_info else "")
                        
                        # 주문 항목
                        st.subheader("주문 항목")
                        if pi_info:
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
                        for i in range(item_count):
                            st.markdown(f"### 주문 항목 {i+1}")
                            col1, col2 = st.columns(2)
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
                            if selected_product[0] != 0 and quantity > 0:
                                items_data.append({
                                    'product_id': selected_product[0],
                                    'quantity': int(quantity)
                                })
                        notes = st.text_area("비고", value=pi_info['notes'] if pi_info else "")
                        if pi_info:
                            submitted = st.form_submit_button("PI 수정")
                        else:
                            submitted = st.form_submit_button("PI 등록")
                        if submitted:
                            if not items_data:
                                st.error("최소 하나 이상의 제품을 선택하고 수량을 입력해주세요.")
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
                                        success, result = update_pi(pi_info['pi_id'], pi_data, items_data)
                                    else:
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
                
                # PI 수정/삭제 기능
                st.subheader("PI 수정/삭제")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### PI 수정")
                    selected_pi_number = st.selectbox(
                        "수정할 PI 선택",
                        options=[pi['pi_number'] for pi in pi_list],
                        key="edit_pi"
                    )
                
                with col2:
                    st.markdown("#### PI 삭제")
                    selected_pi_for_delete = st.selectbox(
                        "삭제할 PI 선택",
                        options=[pi['pi_number'] for pi in pi_list],
                        key="delete_pi_select"
                    )
                    
                    if selected_pi_for_delete:
                        # 선택된 PI 정보 조회
                        pi_to_delete = next((pi for pi in pi_list if pi['pi_number'] == selected_pi_for_delete), None)
                        if pi_to_delete:
                            st.info(f"PI: {pi_to_delete['pi_number']}")
                            st.info(f"공급업체: {pi_to_delete['supplier_name']}")
                            st.info(f"입고율: {(pi_to_delete['total_received_qty'] / pi_to_delete['total_ordered_qty'] * 100):.1f}%")
                            
                            # 삭제 버튼
                            if pi_to_delete['total_received_qty'] > 0:
                                st.error("⚠️ 이미 입고된 항목이 있어 삭제할 수 없습니다.")
                            else:
                                if st.button("PI 삭제", type="secondary", key="delete_pi_btn"):
                                    # 삭제 확인
                                    if st.session_state.get(f"confirm_delete_{selected_pi_for_delete}") != True:
                                        st.session_state[f"confirm_delete_{selected_pi_for_delete}"] = True
                                        st.warning("⚠️ 한 번 더 클릭하면 PI가 완전히 삭제됩니다.")
                                        st.rerun()
                                    else:
                                        # 실제 삭제 수행
                                        success, message = delete_pi(pi_to_delete['pi_id'])
                                        if success:
                                            st.success(message)
                                            # 확인 상태 초기화
                                            if f"confirm_delete_{selected_pi_for_delete}" in st.session_state:
                                                del st.session_state[f"confirm_delete_{selected_pi_for_delete}"]
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error(f"PI 삭제 중 오류: {message}")
                                            # 확인 상태 초기화
                                            if f"confirm_delete_{selected_pi_for_delete}" in st.session_state:
                                                del st.session_state[f"confirm_delete_{selected_pi_for_delete}"]
                
                # PI 수정 폼
                if selected_pi_number:
                    pi_info = get_pi_by_number(selected_pi_number)
                    if pi_info:
                        st.divider()
                        st.subheader("PI 수정 폼")
                        
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
                            
                            # 제출 버튼
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
                            # 지연 상태 표시
                            if pi['max_delay_days'] > 0:
                                st.error(f"⚠️ {pi['max_delay_days']}일 지연")
                            else:
                                st.success("✅ 정상 진행 중")
                        
                        # 미입고 제품 상세 목록
                        st.subheader("📦 미입고 제품 목록")
                        for item in pi['pending_items']:
                            pending_qty = int(item['quantity']) - int(item['received_qty'])
                            progress_percent = float((int(item['received_qty']) / int(item['quantity'])) * 100)
                            
                            col1, col2, col3 = st.columns([3, 2, 2])
                            with col1:
                                st.write(f"**{item['model_name']}**")
                                st.progress(progress_percent / 100, 
                                          text=f"진행률: {progress_percent:.1f}%")
                            with col2:
                                st.metric(
                                    "미입고 수량",
                                    f"{pending_qty}개",
                                    f"전체 {item['quantity']}개 중"
                                )
                            with col3:
                                if item['expected_production_date']:
                                    days_remaining = (item['expected_production_date'] - date.today()).days
                                    if days_remaining < 0:
                                        st.error(f"{abs(days_remaining)}일 지연")
                                    elif days_remaining == 0:
                                        st.warning("오늘 예정")
                                    else:
                                        st.info(f"{days_remaining}일 남음")
                                    st.caption(f"예정일: {item['expected_production_date'].strftime('%Y-%m-%d')}")
                                else:
                                    st.caption("예정일 미정")
                            
                            # 구분선 추가
                            if item != pi['pending_items'][-1]:  # 마지막 항목이 아닌 경우
                                st.divider()
                        
                        # CI로 가기 버튼 추가
                        if st.button(f"CI 등록하기", key=f"goto_ci_{pi['pi_id']}"):
                            st.session_state['selected_pi_for_ci'] = pi['pi_number']
                            st.info(f"PI {pi['pi_number']}이 선택되었습니다. 입고 관리 메뉴로 이동하세요.")
                            # 페이지 변경을 위한 세션 상태 설정은 별도로 구현 필요
            else:
                st.info("미입고된 PI가 없습니다.")

    elif menu == "CI 관리":
        st.header("📋 CI 관리")
        
        # 공급업체 선택
        suppliers = get_suppliers()
        selected_supplier = st.selectbox(
            "공급업체 선택",
            options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
            format_func=lambda x: x['supplier_name'],
            key="ci_supplier"
        )
        
        # CI 목록 조회
        ci_list = get_ci_list(
            supplier_id=selected_supplier['supplier_id'] if selected_supplier['supplier_id'] else None
        )
        
        if ci_list:
            # 데이터프레임 변환
            df = pd.DataFrame(ci_list)
            
            st.dataframe(
                df,
                column_config={
                    "ci_number": "CI 번호",
                    "supplier_name": "공급업체",
                    "shipping_date": st.column_config.DateColumn("선적일", format="YYYY-MM-DD"),
                    "arrival_date": st.column_config.DateColumn("입고일", format="YYYY-MM-DD"),
                    "items_summary": "주문 항목",
                    "shipping_details": "선적 정보",
                    "notes": "비고"
                },
                hide_index=True
            )
            
            # CI 삭제 기능
            st.subheader("CI 삭제")
            
            selected_ci_for_delete = st.selectbox(
                "삭제할 CI 선택",
                options=[ci['ci_number'] for ci in ci_list],
                key="delete_ci_select"
            )
            
            if selected_ci_for_delete:
                # 선택된 CI 정보 조회
                ci_to_delete = next((ci for ci in ci_list if ci['ci_number'] == selected_ci_for_delete), None)
                if ci_to_delete:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**CI 번호:** {ci_to_delete['ci_number']}")
                        st.info(f"**공급업체:** {ci_to_delete['supplier_name']}")
                        st.info(f"**선적일:** {ci_to_delete['shipping_date']}")
                        st.info(f"**입고일:** {ci_to_delete['arrival_date']}")
                    
                    with col2:
                        st.info(f"**항목:** {ci_to_delete['items_summary']}")
                        if ci_to_delete['shipping_details']:
                            st.info(f"**선적 정보:** {ci_to_delete['shipping_details']}")
                        
                        handle_stock = st.checkbox(
                            "재고 차감 처리",
                            value=True,
                            help="체크하면 CI 삭제 시 해당 재고도 함께 차감됩니다."
                        )
                    
                    # 삭제 버튼
                    if st.button("CI 삭제", type="secondary", key="delete_ci_btn"):
                        # 삭제 확인
                        if st.session_state.get(f"confirm_delete_ci_{selected_ci_for_delete}") != True:
                            st.session_state[f"confirm_delete_ci_{selected_ci_for_delete}"] = True
                            st.warning("⚠️ 한 번 더 클릭하면 CI가 완전히 삭제됩니다.")
                            st.rerun()
                        else:
                            # 실제 삭제 수행
                            success, message = delete_ci(ci_to_delete['ci_id'], handle_stock)
                            if success:
                                st.success(message)
                                # 확인 상태 초기화
                                if f"confirm_delete_ci_{selected_ci_for_delete}" in st.session_state:
                                    del st.session_state[f"confirm_delete_ci_{selected_ci_for_delete}"]
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"CI 삭제 중 오류: {message}")
                                # 확인 상태 초기화
                                if f"confirm_delete_ci_{selected_ci_for_delete}" in st.session_state:
                                    del st.session_state[f"confirm_delete_ci_{selected_ci_for_delete}"]
        else:
            st.info("등록된 CI가 없습니다.")

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

    elif menu == "A/S 지원 입고":
        st.header("🔧 A/S 지원 입고")
        
        # A/S 지원 입고 서브메뉴
        as_submenu = st.radio(
            "A/S 지원 메뉴",
            ["A/S 지원 입고 등록", "A/S 지원 이력", "A/S 지원 통계"],
            horizontal=True
        )
        
        if as_submenu == "A/S 지원 입고 등록":
            st.subheader("🔧 A/S 지원 물량 입고 등록")
            st.info("💡 공급처에서 A/S 발생 시 사용하라고 무상으로 제공된 제품을 등록합니다.")
            
            # 공급업체 선택 (form 밖에서)
            suppliers = get_suppliers()
            selected_supplier = st.selectbox(
                "공급업체 선택",
                options=suppliers,
                format_func=lambda x: x['supplier_name'],
                key="as_supplier"
            )
            
            # 선택된 공급업체의 제품 목록 가져오기 (form 밖에서)
            selected_product = None
            products = []
            if selected_supplier:
                products = get_products(selected_supplier['supplier_id'])
                if products:
                    selected_product = st.selectbox(
                        "제품 선택",
                        options=products,
                        format_func=lambda x: f"{x['model_name']} (현재 재고: {x['current_stock']}개)",
                        key="as_product"
                    )
                else:
                    st.warning("선택한 공급업체에 등록된 제품이 없습니다.")
            
            # A/S 지원 입고 form
            if selected_supplier and selected_product:
                with st.form("as_support_form"):
                    # 제품 정보 표시
                    st.info(f"선택된 제품: {selected_product['model_name']} (공급업체: {selected_supplier['supplier_name']})")
                    
                    # 수량 입력
                    col1, col2 = st.columns(2)
                    with col1:
                        quantity = st.number_input(
                            "A/S 지원 수량",
                            min_value=1,
                            value=1,
                            step=1,
                            help="공급처에서 제공한 A/S 지원 물량 수량"
                        )
                    with col2:
                        support_date = st.date_input(
                            "지원 제공일",
                            value=date.today(),
                            help="공급처에서 A/S 지원 물량을 제공한 날짜"
                        )
                    
                    # A/S 관련 정보
                    col1, col2 = st.columns(2)
                    with col1:
                        as_case_number = st.text_input(
                            "A/S 케이스 번호",
                            placeholder="AS-2024-001",
                            help="A/S 발생 케이스 번호 (선택사항)"
                        )
                        reference_number = st.text_input(
                            "참조 번호",
                            value=f"AS_SUPPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            help="시스템에서 자동 생성된 참조 번호"
                        )
                    
                    with col2:
                        as_reason = st.text_area(
                            "A/S 발생 사유",
                            placeholder="예: 초기 불량, 사용자 오작동 등",
                            help="A/S가 발생한 원인이나 사유"
                        )
                        supplier_contact = st.text_input(
                            "공급처 담당자",
                            placeholder="담당자명 또는 연락처",
                            help="A/S 지원을 제공한 공급처 담당자 정보"
                        )
                    
                    notes = st.text_area(
                        "추가 비고",
                        placeholder="기타 특이사항이나 추가 정보",
                        help="A/S 지원과 관련된 추가 정보"
                    )
                    
                    # 제출 버튼
                    submitted = st.form_submit_button("A/S 지원 입고 등록", type="primary")
                
                # 폼 제출 후 처리
                if submitted and selected_product and quantity > 0:
                    try:
                        # A/S 지원 입고 처리
                        notes_detail = f"A/S 지원 물량 입고"
                        if as_case_number:
                            notes_detail += f" | 케이스번호: {as_case_number}"
                        if as_reason:
                            notes_detail += f" | 사유: {as_reason}"
                        if supplier_contact:
                            notes_detail += f" | 담당자: {supplier_contact}"
                        if notes:
                            notes_detail += f" | 비고: {notes}"
                        
                        # 재고 업데이트 (기존 함수 활용)
                        success = update_stock(
                            product_id=selected_product['product_id'],
                            quantity_change=quantity,
                            change_type='입고',
                            reference_number=reference_number,
                            notes=f"[A/S지원] {notes_detail}",
                            destination=f"공급처: {selected_supplier['supplier_name']}"
                        )
                        
                        if success:
                            st.success(f"✅ A/S 지원 물량 {quantity}개가 성공적으로 입고되었습니다!")
                            
                            # 입고 결과 요약 표시
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("입고 제품", selected_product['model_name'])
                            with col2:
                                st.metric("입고 수량", f"{quantity}개")
                            with col3:
                                current_stock = get_stock(selected_product['product_id'])['stock']
                                st.metric("현재 총 재고", f"{current_stock}개")
                            
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("A/S 지원 입고 처리 중 오류가 발생했습니다.")
                            
                    except Exception as e:
                        st.error(f"A/S 지원 입고 처리 중 오류가 발생했습니다: {str(e)}")
                elif submitted and not selected_product:
                    st.error("제품을 선택해주세요.")
                elif submitted and quantity <= 0:
                    st.error("수량을 1개 이상 입력해주세요.")
        
        elif as_submenu == "A/S 지원 이력":
            st.subheader("📋 A/S 지원 입고 이력")
            
            # 필터 옵션
            col1, col2, col3 = st.columns(3)
            with col1:
                # 공급업체 선택
                suppliers = get_suppliers()
                selected_supplier = st.selectbox(
                    "공급업체 선택",
                    options=[{"supplier_id": None, "supplier_name": "전체"}] + suppliers,
                    format_func=lambda x: x['supplier_name'],
                    key="as_history_supplier"
                )
            
            with col2:
                start_date = st.date_input(
                    "시작일",
                    value=date.today() - timedelta(days=30),
                    key="as_history_start"
                )
            
            with col3:
                end_date = st.date_input(
                    "종료일",
                    value=date.today(),
                    key="as_history_end"
                )
            
            # A/S 지원 이력 조회
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            try:
                query = """
                    SELECT 
                        t.date,
                        p.model_name,
                        s.supplier_name,
                        t.quantity,
                        t.reference_number,
                        t.notes,
                        t.destination
                    FROM inventory_transactions t
                    JOIN products_logistics p ON t.product_id = p.product_id
                    JOIN suppliers s ON p.supplier_id = s.supplier_id
                    WHERE t.change_type = '입고'
                    AND t.notes LIKE '%[A/S지원]%'
                    AND DATE(t.date) >= %s 
                    AND DATE(t.date) <= %s
                """
                params = [start_date, end_date]
                
                if selected_supplier and selected_supplier['supplier_id']:
                    query += " AND s.supplier_id = %s"
                    params.append(selected_supplier['supplier_id'])
                
                query += " ORDER BY t.date DESC"
                
                cursor.execute(query, params)
                as_history = cursor.fetchall()
                
                if as_history:
                    st.success(f"조회 기간 내 A/S 지원 입고: {len(as_history)}건")
                    
                    # 데이터프레임으로 표시
                    df = pd.DataFrame(as_history)
                    
                    # 날짜 포맷 변경
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    st.dataframe(
                        df,
                        column_config={
                            "date": st.column_config.TextColumn("입고일시", width="medium"),
                            "model_name": st.column_config.TextColumn("제품명", width="medium"),
                            "supplier_name": st.column_config.TextColumn("공급업체", width="medium"),
                            "quantity": st.column_config.NumberColumn("수량", format="%d개"),
                            "reference_number": st.column_config.TextColumn("참조번호", width="medium"),
                            "notes": st.column_config.TextColumn("상세내용", width="large"),
                            "destination": st.column_config.TextColumn("공급처", width="medium")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # 요약 통계
                    st.subheader("📊 요약 통계")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        total_quantity = sum(item['quantity'] for item in as_history)
                        st.metric("총 A/S 지원 수량", f"{total_quantity}개")
                    
                    with col2:
                        unique_products = len(set(item['model_name'] for item in as_history))
                        st.metric("지원 제품 종류", f"{unique_products}종")
                    
                    with col3:
                        unique_suppliers = len(set(item['supplier_name'] for item in as_history))
                        st.metric("지원 공급업체", f"{unique_suppliers}개사")
                    
                    with col4:
                        avg_quantity = total_quantity / len(as_history) if as_history else 0
                        st.metric("평균 지원 수량", f"{avg_quantity:.1f}개")
                    
                    # 엑셀 다운로드
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        "📥 A/S 지원 이력 다운로드",
                        csv,
                        f"AS_지원이력_{start_date}_{end_date}.csv",
                        "text/csv",
                        key='download-as-history'
                    )
                    
                else:
                    st.info("조회 기간 내 A/S 지원 입고 이력이 없습니다.")
                    
            finally:
                cursor.close()
                conn.close()
        
        elif as_submenu == "A/S 지원 통계":
            st.subheader("📈 A/S 지원 통계 분석")
            
            # 분석 기간 선택
            col1, col2 = st.columns(2)
            with col1:
                analysis_start = st.date_input(
                    "분석 시작일",
                    value=date.today() - timedelta(days=90),
                    key="as_stats_start"
                )
            with col2:
                analysis_end = st.date_input(
                    "분석 종료일",
                    value=date.today(),
                    key="as_stats_end"
                )
            
            # A/S 지원 통계 데이터 조회
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            try:
                # 1. 공급업체별 A/S 지원 현황
                cursor.execute("""
                    SELECT 
                        s.supplier_name,
                        COUNT(*) as support_count,
                        SUM(t.quantity) as total_quantity,
                        AVG(t.quantity) as avg_quantity
                    FROM inventory_transactions t
                    JOIN products_logistics p ON t.product_id = p.product_id
                    JOIN suppliers s ON p.supplier_id = s.supplier_id
                    WHERE t.change_type = '입고'
                    AND t.notes LIKE '%[A/S지원]%'
                    AND DATE(t.date) >= %s 
                    AND DATE(t.date) <= %s
                    GROUP BY s.supplier_id, s.supplier_name
                    ORDER BY total_quantity DESC
                """, (analysis_start, analysis_end))
                supplier_stats = cursor.fetchall()
                
                # 2. 제품별 A/S 지원 현황
                cursor.execute("""
                    SELECT 
                        p.model_name,
                        s.supplier_name,
                        COUNT(*) as support_count,
                        SUM(t.quantity) as total_quantity
                    FROM inventory_transactions t
                    JOIN products_logistics p ON t.product_id = p.product_id
                    JOIN suppliers s ON p.supplier_id = s.supplier_id
                    WHERE t.change_type = '입고'
                    AND t.notes LIKE '%[A/S지원]%'
                    AND DATE(t.date) >= %s 
                    AND DATE(t.date) <= %s
                    GROUP BY p.product_id, p.model_name, s.supplier_name
                    ORDER BY total_quantity DESC
                """, (analysis_start, analysis_end))
                product_stats = cursor.fetchall()
                
                # 3. 월별 A/S 지원 추이
                cursor.execute("""
                    SELECT 
                        DATE_FORMAT(t.date, '%%Y-%%m') as month,
                        COUNT(*) as support_count,
                        SUM(t.quantity) as total_quantity
                    FROM inventory_transactions t
                    JOIN products_logistics p ON t.product_id = p.product_id
                    WHERE t.change_type = '입고'
                    AND t.notes LIKE '%[A/S지원]%'
                    AND DATE(t.date) >= %s 
                    AND DATE(t.date) <= %s
                    GROUP BY DATE_FORMAT(t.date, '%%Y-%%m')
                    ORDER BY month
                """, (analysis_start, analysis_end))
                monthly_stats = cursor.fetchall()
                
                if supplier_stats or product_stats or monthly_stats:
                    # 공급업체별 통계
                    if supplier_stats:
                        st.subheader("🏢 공급업체별 A/S 지원 현황")
                        df_supplier = pd.DataFrame(supplier_stats)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # 공급업체별 지원 수량 차트
                            fig = px.bar(
                                df_supplier,
                                x='supplier_name',
                                y='total_quantity',
                                title='공급업체별 A/S 지원 수량',
                                labels={'supplier_name': '공급업체', 'total_quantity': '총 지원 수량'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # 공급업체별 지원 횟수 차트
                            fig2 = px.pie(
                                df_supplier,
                                values='support_count',
                                names='supplier_name',
                                title='공급업체별 A/S 지원 횟수 비율'
                            )
                            st.plotly_chart(fig2, use_container_width=True)
                        
                        # 상세 테이블
                        st.dataframe(
                            df_supplier,
                            column_config={
                                "supplier_name": "공급업체",
                                "support_count": st.column_config.NumberColumn("지원 횟수", format="%d회"),
                                "total_quantity": st.column_config.NumberColumn("총 지원 수량", format="%d개"),
                                "avg_quantity": st.column_config.NumberColumn("평균 지원 수량", format="%.1f개")
                            },
                            hide_index=True
                        )
                    
                    # 제품별 통계
                    if product_stats:
                        st.subheader("📦 제품별 A/S 지원 현황")
                        df_product = pd.DataFrame(product_stats)
                        
                        # 상위 10개 제품만 표시
                        top_products = df_product.head(10)
                        
                        fig3 = px.bar(
                            top_products,
                            x='model_name',
                            y='total_quantity',
                            color='supplier_name',
                            title='제품별 A/S 지원 수량 (상위 10개)',
                            labels={'model_name': '제품명', 'total_quantity': '총 지원 수량', 'supplier_name': '공급업체'}
                        )
                        fig3.update_xaxes(tickangle=45)
                        st.plotly_chart(fig3, use_container_width=True)
                        
                        st.dataframe(
                            df_product,
                            column_config={
                                "model_name": "제품명",
                                "supplier_name": "공급업체",
                                "support_count": st.column_config.NumberColumn("지원 횟수", format="%d회"),
                                "total_quantity": st.column_config.NumberColumn("총 지원 수량", format="%d개")
                            },
                            hide_index=True
                        )
                    
                    # 월별 추이
                    if monthly_stats:
                        st.subheader("📅 월별 A/S 지원 추이")
                        df_monthly = pd.DataFrame(monthly_stats)
                        
                        # 데이터 타입 통일 (정수형으로 변환)
                        df_monthly['support_count'] = pd.to_numeric(df_monthly['support_count'], errors='coerce').fillna(0).astype(int)
                        df_monthly['total_quantity'] = pd.to_numeric(df_monthly['total_quantity'], errors='coerce').fillna(0).astype(int)
                        
                        # 두 개의 차트를 나누어서 생성
                        col1, col2 = st.columns(2)
                        with col1:
                            fig4_1 = px.line(
                                df_monthly,
                                x='month',
                                y='support_count',
                                title='월별 A/S 지원 횟수',
                                labels={'month': '월', 'support_count': '지원 횟수'}
                            )
                            st.plotly_chart(fig4_1, use_container_width=True)
                        
                        with col2:
                            fig4_2 = px.line(
                                df_monthly,
                                x='month',
                                y='total_quantity',
                                title='월별 A/S 지원 수량',
                                labels={'month': '월', 'total_quantity': '총 지원 수량'}
                            )
                            st.plotly_chart(fig4_2, use_container_width=True)
                        
                        st.dataframe(
                            df_monthly,
                            column_config={
                                "month": "월",
                                "support_count": st.column_config.NumberColumn("지원 횟수", format="%d회"),
                                "total_quantity": st.column_config.NumberColumn("총 지원 수량", format="%d개")
                            },
                            hide_index=True
                        )
                
                else:
                    st.info("분석 기간 내 A/S 지원 데이터가 없습니다.")
                    
            finally:
                cursor.close()
                conn.close()

# --- 리드타임 분석 관련 함수들 ---
def get_lead_time_data(supplier_id=None, start_date=None, end_date=None):
    """리드타임 데이터 조회"""
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
                s.supplier_id,
                p.model_name,
                p.product_id,
                pi_items.quantity as ordered_qty,
                pi_items.expected_production_date,
                ci.shipping_date,
                ci.arrival_date,
                DATEDIFF(ci.arrival_date, pi.issue_date) as actual_lead_time,
                DATEDIFF(pi.expected_delivery_date, pi.issue_date) as expected_lead_time,
                DATEDIFF(ci.arrival_date, pi.expected_delivery_date) as delay_days
            FROM proforma_invoices pi
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            JOIN pi_items ON pi.pi_id = pi_items.pi_id
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            JOIN commercial_invoices ci ON ci_items.ci_id = ci.ci_id
            WHERE ci.arrival_date IS NOT NULL
            AND pi.issue_date IS NOT NULL
        """
        params = []
        
        if supplier_id:
            query += " AND pi.supplier_id = %s"
            params.append(supplier_id)
        if start_date:
            query += " AND pi.issue_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND pi.issue_date <= %s"
            params.append(end_date)
            
        query += " ORDER BY pi.issue_date DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def calculate_lead_time_statistics(lead_time_data):
    """리드타임 통계 계산"""
    if not lead_time_data:
        return None
    
    df = pd.DataFrame(lead_time_data)
    
    # 공급업체별 통계
    supplier_stats = df.groupby('supplier_name').agg({
        'actual_lead_time': ['mean', 'median', 'std', 'min', 'max', 'count'],
        'delay_days': ['mean', 'median', 'std', 'min', 'max']
    }).round(1)
    
    # 제품별 통계
    product_stats = df.groupby(['supplier_name', 'model_name']).agg({
        'actual_lead_time': ['mean', 'median', 'std', 'min', 'max', 'count'],
        'delay_days': ['mean', 'median', 'std', 'min', 'max']
    }).round(1)
    
    # 전체 통계
    overall_stats = {
        'total_orders': len(df),
        'avg_lead_time': df['actual_lead_time'].mean(),
        'median_lead_time': df['actual_lead_time'].median(),
        'std_lead_time': df['actual_lead_time'].std(),
        'min_lead_time': df['actual_lead_time'].min(),
        'max_lead_time': df['actual_lead_time'].max(),
        'avg_delay': df['delay_days'].mean(),
        'on_time_rate': len(df[df['delay_days'] <= 0]) / len(df) * 100
    }
    
    return {
        'overall': overall_stats,
        'supplier': supplier_stats,
        'product': product_stats,
        'raw_data': df
    }

def predict_lead_time(supplier_id, product_id, confidence_level=0.8):
    """리드타임 예측"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 해당 공급업체/제품의 과거 리드타임 데이터 조회
        cursor.execute("""
            SELECT 
                DATEDIFF(ci.arrival_date, pi.issue_date) as actual_lead_time
            FROM proforma_invoices pi
            JOIN pi_items ON pi.pi_id = pi_items.pi_id
            JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            JOIN commercial_invoices ci ON ci_items.ci_id = ci.ci_id
            WHERE pi.supplier_id = %s 
            AND pi_items.product_id = %s
            AND ci.arrival_date IS NOT NULL
            ORDER BY pi.issue_date DESC
            LIMIT 20
        """, (supplier_id, product_id))
        
        lead_times = [row['actual_lead_time'] for row in cursor.fetchall()]
        
        if len(lead_times) < 2:
            return None, "예측을 위한 충분한 데이터가 없습니다. (최소 2개 주문 필요)"
        
        # 통계 계산
        mean_lt = np.mean(lead_times)
        std_lt = np.std(lead_times)
        
        # 신뢰구간 계산
        confidence_interval = stats.norm.interval(confidence_level, loc=mean_lt, scale=std_lt/np.sqrt(len(lead_times)))
        
        # 예측 결과
        prediction = {
            'expected_lead_time': round(mean_lt, 1),
            'confidence_interval': (round(confidence_interval[0], 1), round(confidence_interval[1], 1)),
            'std_deviation': round(std_lt, 1),
            'data_points': len(lead_times),
            'min_historical': min(lead_times),
            'max_historical': max(lead_times),
            'recent_trend': lead_times[:5] if len(lead_times) >= 5 else lead_times
        }
        
        return prediction, None
        
    finally:
        cursor.close()
        conn.close()

def get_lead_time_trends(supplier_id=None, days=90):
    """리드타임 추이 분석"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                DATE_FORMAT(pi.issue_date, '%%Y-%%m') as month,
                s.supplier_name,
                p.model_name,
                AVG(DATEDIFF(ci.arrival_date, pi.issue_date)) as avg_lead_time,
                COUNT(*) as order_count,
                AVG(DATEDIFF(ci.arrival_date, pi.expected_delivery_date)) as avg_delay
            FROM proforma_invoices pi
            JOIN suppliers s ON pi.supplier_id = s.supplier_id
            JOIN pi_items ON pi.pi_id = pi_items.pi_id
            JOIN products_logistics p ON pi_items.product_id = p.product_id
            JOIN ci_items ON pi_items.pi_item_id = ci_items.pi_item_id
            JOIN commercial_invoices ci ON ci_items.ci_id = ci.ci_id
            WHERE ci.arrival_date IS NOT NULL
            AND pi.issue_date >= DATE_SUB(CURRENT_DATE, INTERVAL %s DAY)
        """
        params = [days]
        
        if supplier_id:
            query += " AND pi.supplier_id = %s"
            params.append(supplier_id)
            
        query += """
            GROUP BY DATE_FORMAT(pi.issue_date, '%%Y-%%m'), s.supplier_name, p.model_name
            ORDER BY month DESC, avg_lead_time DESC
        """
        
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 