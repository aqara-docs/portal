import streamlit as st
import mysql.connector
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import base64
import io
from io import StringIO
from openai import OpenAI
import anthropic
import requests
import traceback
import graphviz
import re
from typing import Dict, List, Any, Optional
import docx
import PyPDF2
import openpyxl
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfutils
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import tempfile

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="프로젝트 리뷰 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("📊 프로젝트 리뷰 시스템")

# 인증 기능 (간단한 비밀번호 보호)
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

# AI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 모델 설정
OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 16384},
    "gpt-4o": {"max_tokens": 8192},
    "gpt-4o-mini": {"max_tokens": 8192},
}

# 사용 가능한 모델 확인
has_anthropic_key = os.environ.get("ANTHROPIC_API_KEY") is not None
has_openai_key = os.environ.get("OPENAI_API_KEY") is not None
available_models = []
if has_anthropic_key:
    available_models.extend([
        "claude-3-7-sonnet-latest",
        "claude-3-5-sonnet-latest", 
        "claude-3-5-haiku-latest",
    ])
if has_openai_key:
    available_models.extend(["gpt-4o", "gpt-4o-mini"])
if not available_models:
    available_models = ["claude-3-7-sonnet-latest"]

def connect_to_db():
    """MySQL DB 연결"""
    try:
        return mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

def create_project_review_tables():
    """프로젝트 리뷰 관련 테이블 생성"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # 기존 테이블에 file_binary_data 컬럼 추가 (이미 존재하면 무시)
        try:
            cursor.execute("""
                ALTER TABLE project_review_files 
                ADD COLUMN file_binary_data LONGTEXT
            """)
            conn.commit()
        except mysql.connector.Error:
            # 컬럼이 이미 존재하는 경우 무시
            pass
        # 프로젝트 리뷰 메인 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_reviews (
                review_id INT AUTO_INCREMENT PRIMARY KEY,
                project_name VARCHAR(255) NOT NULL,
                project_type VARCHAR(100) NOT NULL,
                start_date DATE,
                end_date DATE,
                project_manager VARCHAR(100),
                team_members TEXT,
                budget DECIMAL(15,2),
                actual_cost DECIMAL(15,2),
                revenue DECIMAL(15,2),
                status ENUM('completed', 'ongoing', 'cancelled', 'on_hold') DEFAULT 'completed',
                overall_rating INT CHECK (overall_rating BETWEEN 1 AND 10),
                description TEXT,
                objectives TEXT,
                deliverables TEXT,
                challenges TEXT,
                lessons_learned TEXT,
                recommendations TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 프로젝트 파일 첨부 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_review_files (
                file_id INT AUTO_INCREMENT PRIMARY KEY,
                review_id INT NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(50) NOT NULL,
                file_content LONGTEXT,
                file_binary_data LONGTEXT,
                file_size INT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES project_reviews(review_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # AI 분석 결과 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_ai_analysis (
                analysis_id INT AUTO_INCREMENT PRIMARY KEY,
                review_id INT NOT NULL,
                agent_type VARCHAR(50) NOT NULL,
                model_name VARCHAR(100) NOT NULL,
                analysis_content LONGTEXT NOT NULL,
                recommendations TEXT,
                risk_assessment TEXT,
                score INT CHECK (score BETWEEN 1 AND 10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES project_reviews(review_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        # 프로젝트 메트릭스 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_metrics (
                metric_id INT AUTO_INCREMENT PRIMARY KEY,
                review_id INT NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value DECIMAL(10,4),
                metric_unit VARCHAR(50),
                target_value DECIMAL(10,4),
                category VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES project_reviews(review_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"테이블 생성 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def parse_uploaded_file(uploaded_file):
    """업로드된 파일 파싱 - 원본 바이너리 데이터와 텍스트 내용 모두 저장"""
    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        content = ""
        
        # 파일을 처음부터 읽기 위해 포인터를 처음으로 이동
        uploaded_file.seek(0)
        
        # 원본 바이너리 데이터 저장 (Base64 인코딩)
        binary_data = uploaded_file.read()
        binary_base64 = base64.b64encode(binary_data).decode('utf-8')
        
        # 텍스트 추출을 위해 다시 파일 포인터를 처음으로 이동
        uploaded_file.seek(0)
        
        if file_extension == 'pdf':
            # PDF 파일 파싱
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"
                
        elif file_extension == 'docx':
            # DOCX 파일 파싱
            doc = docx.Document(uploaded_file)
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
                
        elif file_extension in ['txt', 'md']:
            # 텍스트 파일 파싱
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('utf-8')
            
        elif file_extension in ['xlsx', 'xls']:
            # Excel 파일 파싱
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file)
            content = df.to_string()
            
        elif file_extension == 'csv':
            # CSV 파일 파싱
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file)
            content = df.to_string()
            
        elif file_extension in ['json']:
            # JSON 파일 파싱
            uploaded_file.seek(0)
            try:
                json_data = json.load(uploaded_file)
                content = json.dumps(json_data, indent=2, ensure_ascii=False)
            except:
                content = uploaded_file.read().decode('utf-8', errors='ignore')
                
        elif file_extension in ['xml', 'html']:
            # XML/HTML 파일 파싱
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            
        elif file_extension in ['jpg', 'jpeg', 'png', 'gif']:
            # 이미지 파일
            content = f"[{file_extension.upper()} 이미지 파일 - {uploaded_file.name}]"
            
        elif file_extension in ['zip', 'rar']:
            # 압축 파일
            content = f"[{file_extension.upper()} 압축 파일 - {uploaded_file.name}]"
            
        else:
            # 기타 파일 형식
            try:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode('utf-8', errors='ignore')
                if not content.strip():
                    content = f"[{file_extension.upper()} 파일 - 텍스트 추출 불가]"
            except:
                content = f"[{file_extension.upper()} 파일 - 텍스트 추출 불가]"
            
        return {
            'filename': uploaded_file.name,
            'file_type': file_extension,
            'content': content,
            'binary_data': binary_base64,
            'size': len(binary_data)
        }
        
    except Exception as e:
        st.error(f"파일 파싱 오류: {str(e)}")
        return None

def save_project_review(review_data):
    """프로젝트 리뷰 저장"""
    conn = connect_to_db()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO project_reviews 
            (project_name, project_type, start_date, end_date, project_manager, 
             team_members, budget, actual_cost, revenue, value_type, cost_savings,
             customer_satisfaction, brand_value, efficiency_improvement, risk_reduction,
             status, overall_rating, description, objectives, deliverables, challenges, 
             lessons_learned, recommendations, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            review_data['project_name'],
            review_data['project_type'],
            review_data['start_date'],
            review_data['end_date'],
            review_data['project_manager'],
            review_data['team_members'],
            review_data['budget'],
            review_data['actual_cost'],
            review_data['revenue'],
            review_data.get('value_type', '매출 창출'),
            review_data.get('cost_savings', 0),
            review_data.get('customer_satisfaction', 0),
            review_data.get('brand_value', 0),
            review_data.get('efficiency_improvement', 0),
            review_data.get('risk_reduction', 0),
            review_data['status'],
            review_data['overall_rating'],
            review_data['description'],
            review_data['objectives'],
            review_data['deliverables'],
            review_data['challenges'],
            review_data['lessons_learned'],
            review_data['recommendations'],
            review_data['created_by']
        ))
        
        review_id = cursor.lastrowid
        conn.commit()
        return review_id
        
    except mysql.connector.Error as err:
        st.error(f"프로젝트 리뷰 저장 오류: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def save_project_file(review_id, file_data):
    """프로젝트 파일 저장 - 원본 바이너리 데이터와 텍스트 내용 모두 저장"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO project_review_files 
            (review_id, filename, file_type, file_content, file_binary_data, file_size)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            review_id,
            file_data['filename'],
            file_data['file_type'],
            file_data['content'],
            file_data['binary_data'],
            file_data['size']
        ))
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"파일 저장 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def save_ai_analysis(review_id, agent_type, model_name, analysis_content, recommendations, risk_assessment, score):
    """AI 분석 결과 저장"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO project_ai_analysis 
            (review_id, agent_type, model_name, analysis_content, recommendations, risk_assessment, score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (review_id, agent_type, model_name, analysis_content, recommendations, risk_assessment, score))
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"AI 분석 저장 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_project_reviews():
    """프로젝트 리뷰 목록 조회"""
    conn = connect_to_db()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM project_reviews 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_project_files(review_id):
    """프로젝트 파일 목록 조회"""
    conn = connect_to_db()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM project_review_files 
            WHERE review_id = %s
            ORDER BY uploaded_at
        """, (review_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_ai_analysis(review_id):
    """AI 분석 결과 조회"""
    conn = connect_to_db()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM project_ai_analysis 
            WHERE review_id = %s
            ORDER BY created_at DESC
        """, (review_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_project_review(review_id, review_data):
    """프로젝트 리뷰 수정"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE project_reviews SET
            project_name = %s, project_type = %s, start_date = %s, end_date = %s,
            project_manager = %s, team_members = %s, budget = %s, actual_cost = %s,
            revenue = %s, value_type = %s, cost_savings = %s, customer_satisfaction = %s,
            brand_value = %s, efficiency_improvement = %s, risk_reduction = %s,
            status = %s, overall_rating = %s, description = %s, objectives = %s,
            deliverables = %s, challenges = %s, lessons_learned = %s, recommendations = %s,
            updated_at = CURRENT_TIMESTAMP
            WHERE review_id = %s
        """, (
            review_data['project_name'],
            review_data['project_type'],
            review_data['start_date'],
            review_data['end_date'],
            review_data['project_manager'],
            review_data['team_members'],
            review_data['budget'],
            review_data['actual_cost'],
            review_data['revenue'],
            review_data.get('value_type', '매출 창출'),
            review_data.get('cost_savings', 0),
            review_data.get('customer_satisfaction', 0),
            review_data.get('brand_value', 0),
            review_data.get('efficiency_improvement', 0),
            review_data.get('risk_reduction', 0),
            review_data['status'],
            review_data['overall_rating'],
            review_data['description'],
            review_data['objectives'],
            review_data['deliverables'],
            review_data['challenges'],
            review_data['lessons_learned'],
            review_data['recommendations'],
            review_id
        ))
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"프로젝트 리뷰 수정 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_project_review_by_id(review_id):
    """특정 프로젝트 리뷰 조회"""
    conn = connect_to_db()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM project_reviews 
            WHERE review_id = %s
        """, (review_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def delete_project_review(review_id):
    """프로젝트 리뷰 삭제"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # 외래 키 제약으로 인해 관련 데이터도 자동 삭제됨
        cursor.execute("""
            DELETE FROM project_reviews 
            WHERE review_id = %s
        """, (review_id,))
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"프로젝트 리뷰 삭제 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def delete_project_file(file_id):
    """프로젝트 파일 삭제"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM project_review_files 
            WHERE file_id = %s
        """, (file_id,))
        
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        st.error(f"파일 삭제 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def delete_ai_analysis(review_id):
    """프로젝트의 모든 AI 분석 결과 삭제"""
    conn = connect_to_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM project_ai_analysis 
            WHERE review_id = %s
        """, (review_id,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
        
    except mysql.connector.Error as err:
        st.error(f"AI 분석 결과 삭제 오류: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def search_files(search_term=None, file_type=None):
    """파일 검색"""
    conn = connect_to_db()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT f.*, p.project_name, p.project_type, p.created_by
            FROM project_review_files f
            JOIN project_reviews p ON f.review_id = p.review_id
            WHERE 1=1
        """
        params = []
        
        if search_term:
            query += " AND (f.filename LIKE %s OR f.file_content LIKE %s OR p.project_name LIKE %s)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if file_type and file_type != "전체":
            query += " AND f.file_type = %s"
            params.append(file_type)
        
        query += " ORDER BY f.uploaded_at DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    except mysql.connector.Error as err:
        st.error(f"파일 검색 오류: {err}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_all_file_types():
    """모든 파일 타입 조회"""
    conn = connect_to_db()
    if not conn:
        return []
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT file_type 
            FROM project_review_files 
            ORDER BY file_type
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def get_file_binary_data(file_id):
    """파일의 원본 바이너리 데이터 조회"""
    conn = connect_to_db()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT filename, file_type, file_binary_data, file_size
            FROM project_review_files 
            WHERE file_id = %s
        """, (file_id,))
        result = cursor.fetchone()
        
        if result and result['file_binary_data']:
            # Base64 디코딩하여 원본 바이너리 데이터 반환
            binary_data = base64.b64decode(result['file_binary_data'])
            return {
                'filename': result['filename'],
                'file_type': result['file_type'],
                'binary_data': binary_data,
                'file_size': result['file_size']
            }
        return None
        
    except mysql.connector.Error as err:
        st.error(f"파일 데이터 조회 오류: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_file_mime_type(file_type):
    """파일 타입에 따른 MIME 타입 반환"""
    mime_types = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'csv': 'text/csv',
        'json': 'application/json',
        'xml': 'application/xml',
        'html': 'text/html',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'zip': 'application/zip',
        'rar': 'application/x-rar-compressed'
    }
    return mime_types.get(file_type.lower(), 'application/octet-stream')

def display_file_preview(file_data, file_type, filename):
    """파일 미리보기 표시"""
    try:
        file_type_lower = file_type.lower()
        
        # 이미지 파일 미리보기
        if file_type_lower in ['jpg', 'jpeg', 'png', 'gif']:
            if file_data.get('binary_data'):
                st.image(
                    file_data['binary_data'],
                    caption=f"🖼️ {filename}",
                    use_column_width=True
                )
                return True
            else:
                st.info("이미지 데이터를 찾을 수 없습니다.")
                return False
        
        # PDF 파일 미리보기 (1MB 초과시 1페이지씩)
        elif file_type_lower == 'pdf':
            if file_data.get('binary_data'):
                import math
                from PyPDF2 import PdfReader, PdfWriter
                import tempfile, os

                total_size = file_data['file_size'] if 'file_size' in file_data else len(file_data['binary_data'])
                if total_size > 1 * 1024 * 1024:
                    key = f"pdf_preview_page_start_{filename}"
                    if key not in st.session_state:
                        st.session_state[key] = 0  # 0-based index

                    # PDF 전체 페이지 수 구하기
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_in:
                        tmp_in.write(file_data['binary_data'])
                        tmp_in_path = tmp_in.name
                    reader = PdfReader(tmp_in_path)
                    total_pages = len(reader.pages)
                    os.unlink(tmp_in_path)

                    page_start = st.session_state[key]
                    page_end = min(page_start + 1, total_pages)

                    col_prev, col_next = st.columns([1, 1])
                    with col_prev:
                        if st.button("⬅️ 이전", disabled=page_start == 0, key=f"prev_{filename}"):
                            st.session_state[key] = max(0, page_start - 1)
                            st.rerun()
                    with col_next:
                        if st.button("다음 ➡️", disabled=page_end >= total_pages, key=f"next_{filename}"):
                            st.session_state[key] = min(total_pages - 1, page_start + 1)
                            st.rerun()

                    # 미리보기 PDF 생성 (1페이지)
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_in:
                            tmp_in.write(file_data['binary_data'])
                            tmp_in_path = tmp_in.name
                        reader = PdfReader(tmp_in_path)
                        writer = PdfWriter()
                        for i in range(page_start, page_end):
                            writer.add_page(reader.pages[i])
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_out:
                            writer.write(tmp_out)
                            tmp_out_path = tmp_out.name
                        with open(tmp_out_path, "rb") as f:
                            preview_pdf_bytes = f.read()
                        os.unlink(tmp_in_path)
                        os.unlink(tmp_out_path)
                        st.markdown(f"**페이지 {page_start+1} / {total_pages}**")
                        pdf_base64 = base64.b64encode(preview_pdf_bytes).decode('utf-8')
                        pdf_display = f"""
                        <iframe src=\"data:application/pdf;base64,{pdf_base64}\" 
                                width=\"100%\" height=\"600px\" type=\"application/pdf\">
                            <p>PDF를 표시할 수 없습니다. 
                            <a href=\"data:application/pdf;base64,{pdf_base64}\" target=\"_blank\">
                            여기를 클릭하여 새 탭에서 열어보세요.</a></p>
                        </iframe>
                        """
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"PDF 미리보기 생성 중 오류: {e}")

                    st.download_button(
                        label="💾 전체 PDF 다운로드",
                        data=file_data['binary_data'],
                        file_name=filename,
                        mime="application/pdf"
                    )
                    return True
                else:
                    # PDF를 base64로 인코딩하여 iframe에 표시 (전체 미리보기)
                    pdf_base64 = base64.b64encode(file_data['binary_data']).decode('utf-8')
                    pdf_display = f"""
                    <iframe src=\"data:application/pdf;base64,{pdf_base64}\" 
                            width=\"100%\" height=\"600px\" type=\"application/pdf\">
                        <p>PDF를 표시할 수 없습니다. 
                        <a href=\"data:application/pdf;base64,{pdf_base64}\" target=\"_blank\">
                        여기를 클릭하여 새 탭에서 열어보세요.</a></p>
                    </iframe>
                    """
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    return True
            else:
                st.info("PDF 데이터를 찾을 수 없습니다.")
                return False
        
        # Excel 파일 미리보기
        elif file_type_lower in ['xlsx', 'xls']:
            if file_data.get('binary_data'):
                try:
                    # 바이너리 데이터를 임시 파일로 저장하여 pandas로 읽기
                    with tempfile.NamedTemporaryFile(suffix=f'.{file_type_lower}', delete=False) as tmp_file:
                        tmp_file.write(file_data['binary_data'])
                        tmp_file_path = tmp_file.name
                    
                    # Excel 파일 읽기
                    df = pd.read_excel(tmp_file_path)
                    
                    # 임시 파일 삭제
                    os.unlink(tmp_file_path)
                    
                    st.subheader(f"📊 Excel 파일 미리보기: {filename}")
                    st.dataframe(df, use_container_width=True)
                    
                    # 기본 통계 정보
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("행 수", len(df))
                    with col2:
                        st.metric("열 수", len(df.columns))
                    with col3:
                        st.metric("데이터 타입", len(df.dtypes.unique()))
                    
                    return True
                except Exception as e:
                    st.error(f"Excel 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("Excel 데이터를 찾을 수 없습니다.")
                return False
        
        # CSV 파일 미리보기
        elif file_type_lower == 'csv':
            if file_data.get('binary_data'):
                try:
                    # CSV 데이터를 문자열로 변환
                    csv_content = file_data['binary_data'].decode('utf-8')
                    
                    # StringIO를 사용하여 pandas로 읽기
                    from io import StringIO
                    df = pd.read_csv(StringIO(csv_content))
                    
                    st.subheader(f"📈 CSV 파일 미리보기: {filename}")
                    st.dataframe(df, use_container_width=True)
                    
                    # 기본 통계 정보
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("행 수", len(df))
                    with col2:
                        st.metric("열 수", len(df.columns))
                    with col3:
                        st.metric("데이터 타입", len(df.dtypes.unique()))
                    
                    return True
                except Exception as e:
                    st.error(f"CSV 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("CSV 데이터를 찾을 수 없습니다.")
                return False
        
        # JSON 파일 미리보기
        elif file_type_lower == 'json':
            if file_data.get('binary_data'):
                try:
                    json_content = file_data['binary_data'].decode('utf-8')
                    json_data = json.loads(json_content)
                    
                    st.subheader(f"📋 JSON 파일 미리보기: {filename}")
                    st.json(json_data)
                    return True
                except Exception as e:
                    st.error(f"JSON 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("JSON 데이터를 찾을 수 없습니다.")
                return False
        
        # 텍스트 파일 미리보기 (TXT, MD, XML, HTML 등)
        elif file_type_lower in ['txt', 'md', 'xml', 'html']:
            if file_data.get('binary_data'):
                try:
                    text_content = file_data['binary_data'].decode('utf-8')
                    
                    st.subheader(f"📄 텍스트 파일 미리보기: {filename}")
                    
                    if file_type_lower == 'md':
                        # Markdown 파일은 렌더링하여 표시
                        st.markdown(text_content)
                    elif file_type_lower == 'html':
                        # HTML 파일은 코드로 표시 (보안상 렌더링하지 않음)
                        st.code(text_content, language='html')
                    elif file_type_lower == 'xml':
                        # XML 파일은 코드로 표시
                        st.code(text_content, language='xml')
                    else:
                        # 일반 텍스트
                        st.text_area(
                            "파일 내용",
                            value=text_content,
                            height=400,
                            disabled=True
                        )
                    
                    return True
                except Exception as e:
                    st.error(f"텍스트 파일을 읽는 중 오류 발생: {str(e)}")
                    return False
            else:
                st.info("텍스트 데이터를 찾을 수 없습니다.")
                return False
        
        # 지원하지 않는 파일 형식
        else:
            st.info(f"📁 {file_type.upper()} 파일은 미리보기를 지원하지 않습니다.")
            st.caption("다운로드하여 해당 프로그램에서 열어보세요.")
            return False
            
    except Exception as e:
        st.error(f"파일 미리보기 중 오류 발생: {str(e)}")
        return False

def get_agent_tools(agent_type):
    """에이전트별 특화 도구 반환"""
    tools = {
        'project_manager_agent': """
프로젝트 관리 분석 도구:
1. 일정 관리 분석: 계획 대비 실제 일정 준수율
2. 예산 관리 분석: 예산 대비 실제 비용 분석
3. 리소스 활용도 분석: 인력 및 자원 효율성
4. 위험 관리 평가: 식별된 위험과 대응 효과성
5. 의사소통 효과성: 팀 내외 커뮤니케이션 품질
6. 변경 관리: 범위 변경 및 요구사항 변화 대응
7. 품질 관리: 산출물 품질 및 검토 프로세스

각 도구를 활용하여 프로젝트 관리 측면의 성과를 분석해주세요.
""",
        'technical_agent': """
기술적 분석 도구:
1. 기술 아키텍처 평가: 설계 품질 및 확장성
2. 코드 품질 분석: 유지보수성, 가독성, 성능
3. 기술 부채 평가: 누적된 기술적 문제점
4. 보안 분석: 보안 취약점 및 대응 방안
5. 성능 분석: 시스템 성능 및 최적화
6. 기술 스택 적합성: 선택된 기술의 적절성
7. 혁신성 평가: 새로운 기술 도입 및 활용

각 도구를 활용하여 기술적 측면의 성과를 분석해주세요.
""",
        'business_agent': """
비즈니스 분석 도구:
1. ROI 분석: 투자 대비 수익률 계산
2. 비즈니스 가치 평가: 프로젝트의 비즈니스 기여도
3. 시장 영향도 분석: 시장 포지션 변화
4. 고객 만족도 분석: 사용자 피드백 및 만족도
5. 경쟁 우위 분석: 경쟁사 대비 차별화 요소
6. 비용 효율성: 비용 대비 효과 분석
7. 전략적 정렬도: 기업 전략과의 일치성

각 도구를 활용하여 비즈니스 측면의 성과를 분석해주세요.
""",
        'quality_agent': """
품질 분석 도구:
1. 품질 메트릭스: 결함률, 테스트 커버리지
2. 사용자 경험 평가: UI/UX 품질 분석
3. 성능 품질: 응답시간, 처리량, 안정성
4. 보안 품질: 보안 표준 준수도
5. 유지보수성: 코드 복잡도, 문서화 수준
6. 호환성: 다양한 환경에서의 동작 품질
7. 접근성: 사용자 접근성 표준 준수

각 도구를 활용하여 품질 측면의 성과를 분석해주세요.
""",
        'risk_agent': """
리스크 분석 도구:
1. 리스크 식별: 프로젝트 전반의 위험 요소
2. 리스크 평가: 발생 가능성과 영향도 분석
3. 리스크 대응: 완화 전략의 효과성
4. 잔여 리스크: 해결되지 않은 위험 요소
5. 리스크 모니터링: 위험 추적 및 관리
6. 비상 계획: 위기 상황 대응 준비도
7. 교훈 학습: 향후 프로젝트를 위한 위험 관리 개선

각 도구를 활용하여 리스크 관리 측면을 분석해주세요.
""",
        'team_agent': """
팀 성과 분석 도구:
1. 팀 생산성: 개인별/팀별 성과 분석
2. 협업 효과성: 팀워크 및 협력 수준
3. 스킬 개발: 팀원 역량 향상도
4. 만족도 조사: 팀원 만족도 및 참여도
5. 리더십 효과성: 프로젝트 리더십 평가
6. 의사소통: 팀 내 커뮤니케이션 품질
7. 갈등 관리: 팀 내 갈등 해결 능력

각 도구를 활용하여 팀 성과 측면을 분석해주세요.
""",
        'financial_agent': """
재무 분석 도구:
1. ROI 상세 분석: 투자 대비 수익률의 정확한 계산 및 평가
2. NPV/IRR 분석: 순현재가치 및 내부수익률 계산
3. 비용 효율성 분석: 예산 대비 실제 비용의 상세 분석
4. 재무 성과 지표: 매출 증대, 비용 절감, 생산성 향상 등 정량적 성과
5. 투자 회수 기간: Payback Period 및 투자 회수 가능성 평가
6. 재무 리스크 평가: 재무적 위험 요소 및 영향도 분석
7. 경제적 가치 창출: 프로젝트로 인한 경제적 부가가치 측정
8. 비용-편익 분석: 총 비용 대비 총 편익의 정량적 비교
9. 재무 지속가능성: 장기적 재무 영향 및 지속가능성 평가

각 도구를 활용하여 프로젝트의 재무적 성과와 ROI를 전문적으로 분석해주세요.
""",
        'integration_agent': """
종합 평가 분석 도구:
1. 다차원 통합 분석: 모든 전문가 의견의 종합적 검토
2. 상호 연관성 분석: 각 영역 간의 상호 영향 관계
3. 우선순위 매트릭스: 개선 과제의 중요도 및 시급성 평가
4. 전체적 균형 평가: 프로젝트의 전반적 균형성 검토
5. 통합 리스크 평가: 모든 영역의 리스크를 종합한 전체 위험도
6. 종합 성과 지표: 전체적인 프로젝트 성공도 측정
7. 전략적 제언: 조직 차원의 개선 방향 제시

다른 전문가들의 분석 결과를 종합하여 통합적 관점에서 프로젝트를 평가해주세요.
"""
    }
    return tools.get(agent_type, "")

def analyze_with_integration_ai(review_data, files_content, other_analyses, model_name):
    """종합 평가 에이전트 - 다른 에이전트들의 결과를 통합 분석"""
    import time
    
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            agent_tools = get_agent_tools('integration_agent')
            
            # 파일 내용 요약
            files_summary = ""
            if files_content:
                files_summary = "\n\n[첨부 파일 내용]\n"
                for file in files_content:
                    files_summary += f"파일명: {file['filename']}\n"
                    files_summary += f"내용: {file['content'][:1000]}...\n\n"
            
            # 다른 에이전트들의 분석 결과 요약
            other_analyses_summary = ""
            if other_analyses:
                other_analyses_summary = "\n\n[다른 전문가들의 분석 결과]\n"
                agent_names = {
                    'project_manager_agent': '프로젝트 관리 전문가',
                    'technical_agent': '기술 전문가',
                    'business_agent': '비즈니스 전문가',
                    'quality_agent': '품질 전문가',
                    'risk_agent': '리스크 전문가',
                    'team_agent': '팀 성과 전문가',
                    'financial_agent': '재무 전문가'
                }
                
                for agent_type, analysis in other_analyses.items():
                    agent_name = agent_names.get(agent_type, agent_type)
                    other_analyses_summary += f"\n=== {agent_name} 분석 ===\n"
                    other_analyses_summary += f"점수: {analysis['score']}/10\n"
                    other_analyses_summary += f"핵심 분석: {analysis['analysis'][:500]}...\n"
                    other_analyses_summary += f"추천사항: {analysis['recommendations'][:300]}...\n"
                    other_analyses_summary += f"위험평가: {analysis['risk_assessment'][:300]}...\n\n"
            
            # 추가 분석 지침 처리
            additional_instructions = ""
            if 'additional_instructions' in review_data and review_data['additional_instructions']:
                additional_instructions = f"\n\n[추가 분석 지침]\n{review_data['additional_instructions']}\n"
            
            prompt = f"""
당신은 종합 평가 전문가입니다.
다른 전문가들의 분석 결과를 종합하여 프로젝트에 대한 통합적 평가를 수행해주세요.

[프로젝트 기본 정보]
프로젝트명: {review_data['project_name']}
프로젝트 유형: {review_data['project_type']}
기간: {review_data['start_date']} ~ {review_data['end_date']}
프로젝트 매니저: {review_data['project_manager']}
팀원: {review_data['team_members']}
예산: {review_data['budget']:,}원
실제 비용: {review_data['actual_cost']:,}원
매출액: {review_data.get('revenue', 0):,}원
ROI: {((review_data.get('revenue', 0) - review_data['actual_cost']) / review_data['actual_cost'] * 100) if review_data['actual_cost'] > 0 else 0:+.1f}%
상태: {review_data['status']}
전체 평점: {review_data['overall_rating']}/10
작성자: {review_data.get('created_by', 'N/A')}

[가치 지표 및 성과]
가치 측정 방식: {review_data.get('value_type', '매출 창출')}
매출액: {review_data.get('revenue', 0):,}원
비용 절약액: {review_data.get('cost_savings', 0):,}원
전통적 ROI: {((review_data.get('revenue', 0) - review_data['actual_cost']) / review_data['actual_cost'] * 100) if review_data['actual_cost'] > 0 else 0:+.1f}%
비용 절약 기준 ROI: {((review_data.get('cost_savings', 0) - review_data['actual_cost']) / review_data['actual_cost'] * 100) if review_data['actual_cost'] > 0 and review_data.get('cost_savings', 0) > 0 else 0:+.1f}%

[정성적 가치 지표 (0-10점)]
고객 만족도 개선: {review_data.get('customer_satisfaction', 0)}/10
브랜드 가치 향상: {review_data.get('brand_value', 0)}/10
업무 효율성 개선: {review_data.get('efficiency_improvement', 0)}/10
리스크 감소 효과: {review_data.get('risk_reduction', 0)}/10

상태: {review_data['status']}
전체 평점: {review_data['overall_rating']}/10
작성자: {review_data.get('created_by', 'N/A')}

[프로젝트 상세]
설명: {review_data['description']}
목표: {review_data['objectives']}
산출물: {review_data['deliverables']}
도전과제: {review_data['challenges']}
교훈: {review_data['lessons_learned']}
권고사항: {review_data['recommendations']}

{files_summary}

{other_analyses_summary}

{additional_instructions}

[종합 평가 도구]
{agent_tools}

**중요**: 위에 제공된 첨부 파일들의 내용과 다른 전문가들의 분석 결과를 종합적으로 활용하여 통합 평가를 수행하세요.
- 첨부 문서에서 확인된 구체적 데이터와 각 전문가의 의견을 교차 검증하세요
- 전문가들 간의 의견 일치점과 차이점을 첨부 문서 내용과 연결하여 분석하세요
- 문서에 기록된 실제 성과와 전문가들의 평가 간의 일관성을 검토하세요
- 각 전문가가 놓친 부분이 첨부 문서에서 발견되는지 확인하세요
- 문서와 전문가 의견을 종합하여 가장 객관적이고 균형잡힌 평가를 제시하세요
- **재무적 성과 통합 분석**: 매출액과 ROI 데이터를 모든 전문가 의견과 연계하여 종합적인 비즈니스 가치를 평가하세요
- **투자 대비 효과 종합 평가**: ROI 수치와 각 영역별 전문가 분석을 연결하여 전체적인 투자 효율성을 판단하세요
- **프로젝트 유형별 종합 가치 평가**: 
  * 매출 창출형: 직접적 ROI와 시장 확대 효과를 전문가 의견과 연계 분석
  * 비용 절약형: 비용 절약액과 효율성 개선을 전문가 분석과 통합 평가  
  * 무형 가치형(POC, 마케팅 등): 정성적 지표와 장기적 전략 가치를 종합 평가
  * 복합 가치형: 정량적/정성적 가치를 전문가 의견과 함께 다면적 종합 분석

다음 형식으로 종합 분석해주세요:

1. 전문가 의견 통합 요약 (첨부 문서와의 일치성 포함)
2. 재무적 성과 통합 분석 (매출액, ROI와 전문가 의견 연계)
3. 영역별 상호 연관성 분석 (문서 데이터 기반)
4. 전체적 강점과 약점 (문서와 전문가 의견 종합)
5. 우선순위별 개선 과제 (증거 기반 우선순위)
6. 통합 리스크 평가 (문서와 전문가 분석 통합)
7. 전략적 제언 및 향후 방향 (종합적 근거 제시)
8. 종합 점수 (1-10점, 모든 정보와 재무 성과를 종합한 최종 평가)

**종합 분석 시각화**: 반드시 다음과 같은 형식으로 통합 Mermaid 다이어그램을 포함해주세요.

```mermaid
graph TD
    A[프로젝트 종합 평가] --> B[프로젝트 관리]
    A --> C[기술적 측면]
    A --> D[비즈니스 가치]
    A --> E[품질 수준]
    A --> F[리스크 관리]
    A --> G[팀 성과]
    A --> H[재무 성과]
    B --> I[종합 결론]
    C --> I
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[최종 권고사항]
```

**Mermaid 차트 작성 규칙**:
- 반드시 `graph TD` 또는 `graph LR`로 시작하세요
- 노드 이름은 A, B, C... 등 영문자를 사용하세요
- 노드 내용은 대괄호 [내용]로 감싸세요
- 화살표는 `-->` 를 사용하세요
- 통합 관점에서 각 전문가 의견의 연관성을 보여주세요
- 최종 결론과 권고사항으로 수렴되도록 구성하세요

위 규칙을 지켜서 통합적 관점의 종합 분석 차트를 생성해주세요.
"""

            if model_name.startswith("claude"):
                response = anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 4000})["max_tokens"],
                    messages=[{"role": "user", "content": prompt}]
                )
                analysis_content = response.content[0].text
            else:
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 4000})["max_tokens"]
                )
                analysis_content = response.choices[0].message.content
            
            # 추천사항과 위험평가 추출
            recommendations = extract_recommendations(analysis_content)
            risk_assessment = extract_risk_assessment(analysis_content)
            score = extract_score(analysis_content)
            
            return {
                'analysis': analysis_content,
                'recommendations': recommendations,
                'risk_assessment': risk_assessment,
                'score': score
            }
            
        except Exception as e:
            error_message = str(e)
            
            # 특정 오류 타입에 따른 처리
            if "overloaded" in error_message.lower() or "529" in error_message:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    st.warning(f"⚠️ 종합 평가 중 API 서버가 과부하 상태입니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ 종합 평가 API 서버 과부하로 인해 {max_retries}번의 재시도 후에도 실패했습니다.")
                    return None
            
            elif "rate_limit" in error_message.lower() or "429" in error_message:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + 5
                    st.warning(f"⚠️ 종합 평가 중 API 요청 한도에 도달했습니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ 종합 평가 API 요청 한도 초과로 인해 {max_retries}번의 재시도 후에도 실패했습니다.")
                    return None
            
            elif "authentication" in error_message.lower() or "401" in error_message:
                st.error("❌ 종합 평가 API 키 인증에 실패했습니다. API 키를 확인해주세요.")
                return None
            
            elif "invalid_request" in error_message.lower() or "400" in error_message:
                st.error(f"❌ 종합 평가 잘못된 요청입니다: {error_message}")
                return None
            
            else:
                if attempt < max_retries - 1:
                    delay = base_delay * (attempt + 1)
                    st.warning(f"⚠️ 종합 평가 중 예상치 못한 오류가 발생했습니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    st.caption(f"오류 내용: {error_message}")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ 종합 평가 {max_retries}번의 재시도 후에도 분석에 실패했습니다.")
                    st.error(f"최종 오류: {error_message}")
                    return None
    
    return None

def analyze_with_ai(review_data, files_content, agent_type, model_name):
    """AI 분석 수행 - 재시도 로직 포함"""
    import time
    
    max_retries = 3
    base_delay = 2  # 기본 대기 시간 (초)
    
    for attempt in range(max_retries):
        try:
            agent_tools = get_agent_tools(agent_type)
            
            # 파일 내용 분석 (RAG 방식)
            files_summary = ""
            if files_content:
                files_summary = "\n\n[첨부 파일 분석 자료]\n"
                files_summary += "다음은 프로젝트와 관련된 첨부 문서들입니다. 이 자료들을 참고하여 더 정확하고 구체적인 종합 분석을 수행해주세요:\n\n"
                
                for file in files_content:
                    file_content = file['content']
                    filename = file['filename']
                    
                    # 파일 타입별 처리
                    if filename.lower().endswith(('.pdf', '.docx', '.doc', '.txt', '.md')):
                        # 문서 파일: 더 많은 내용 포함 (최대 3000자)
                        content_preview = file_content[:3000] if len(file_content) > 3000 else file_content
                        if len(file_content) > 3000:
                            content_preview += "\n... (문서 내용이 더 있습니다)"
                    elif filename.lower().endswith(('.xlsx', '.xls', '.csv')):
                        # 데이터 파일: 구조와 주요 데이터 포함
                        content_preview = file_content[:2000] if len(file_content) > 2000 else file_content
                        if len(file_content) > 2000:
                            content_preview += "\n... (데이터가 더 있습니다)"
                    elif filename.lower().endswith('.json'):
                        # JSON 파일: 구조 분석
                        content_preview = file_content[:1500] if len(file_content) > 1500 else file_content
                        if len(file_content) > 1500:
                            content_preview += "\n... (JSON 구조가 더 있습니다)"
                    else:
                        # 기타 파일: 기본 처리
                        content_preview = file_content[:1000] if len(file_content) > 1000 else file_content
                        if len(file_content) > 1000:
                            content_preview += "\n... (내용이 더 있습니다)"
                    
                    files_summary += f"📄 **파일명**: {filename}\n"
                    files_summary += f"**내용**:\n{content_preview}\n"
                    files_summary += "---\n\n"
                
                files_summary += "위 첨부 자료들과 다른 전문가들의 분석을 종합하여 다음 관점에서 통합 평가해주세요:\n"
                files_summary += "- 문서에서 확인되는 구체적인 성과 지표와 전문가 의견의 일치성\n"
                files_summary += "- 프로젝트 진행 과정에서의 실제 이슈들과 전문가들이 지적한 문제점의 연관성\n"
                files_summary += "- 데이터로 뒷받침되는 정량적 분석과 전문가 평가의 종합\n"
                files_summary += "- 문서에 기록된 교훈과 전문가들의 권고사항 통합\n\n"
            
            # 추가 분석 지침 처리
            additional_instructions = ""
            if 'additional_instructions' in review_data and review_data['additional_instructions']:
                additional_instructions = f"\n\n[추가 분석 지침]\n{review_data['additional_instructions']}\n"
            
            prompt = f"""
당신은 {agent_type.replace('_', ' ').title()}입니다.
다음 프로젝트를 분석해주세요:

[프로젝트 기본 정보]
프로젝트명: {review_data['project_name']}
프로젝트 유형: {review_data['project_type']}
기간: {review_data['start_date']} ~ {review_data['end_date']}
프로젝트 매니저: {review_data['project_manager']}
팀원: {review_data['team_members']}
예산: {review_data['budget']:,}원
실제 비용: {review_data['actual_cost']:,}원
매출액: {review_data.get('revenue', 0):,}원
ROI: {((review_data.get('revenue', 0) - review_data['actual_cost']) / review_data['actual_cost'] * 100) if review_data['actual_cost'] > 0 else 0:+.1f}%
상태: {review_data['status']}
전체 평점: {review_data['overall_rating']}/10
작성자: {review_data.get('created_by', 'N/A')}

[프로젝트 상세]
설명: {review_data['description']}
목표: {review_data['objectives']}
산출물: {review_data['deliverables']}
도전과제: {review_data['challenges']}
교훈: {review_data['lessons_learned']}
권고사항: {review_data['recommendations']}

{files_summary}

{additional_instructions}

[분석 도구]
{agent_tools}

**중요**: 위에 제공된 첨부 파일들의 내용을 반드시 참고하여 분석하세요. 
- 문서에서 언급된 구체적인 데이터, 수치, 사실들을 인용하여 분석의 근거로 활용하세요
- 첨부 파일에서 발견된 문제점이나 성과를 구체적으로 언급하세요
- 프로젝트 기본 정보와 첨부 문서 내용 간의 일치성 또는 차이점을 분석하세요
- 문서에 기록된 실제 데이터를 바탕으로 정량적 평가를 수행하세요
- **재무적 성과 분석**: 매출액과 실제 비용을 바탕으로 ROI를 분석하고, 투자 대비 수익성을 평가하세요
- **비즈니스 가치 평가**: ROI가 양수/음수인지에 따른 프로젝트의 비즈니스 성공도를 평가하세요
- **프로젝트 유형별 가치 평가**: 
  * 매출 창출형: 직접적 ROI와 시장 확대 효과 중심 분석
  * 비용 절약형: 비용 절약액과 효율성 개선 중심 분석  
  * 무형 가치형(POC, 마케팅 등): 정성적 지표와 장기적 전략 가치 중심 분석
  * 복합 가치형: 정량적/정성적 가치를 종합한 다면적 분석

다음 형식으로 분석해주세요:

1. 핵심 성과 분석 (첨부 문서의 구체적 데이터 인용)
2. 재무적 성과 분석 (매출액, ROI, 수익성 평가)
3. 강점과 약점 (문서에서 확인된 사실 기반)
4. 개선 권고사항 (문서 분석 결과 기반)
5. 향후 프로젝트를 위한 교훈 (문서에 기록된 경험 활용)
6. 종합 점수 (1-10점, 문서 내용과 재무 성과를 종합한 근거 제시)

**분석 결과 시각화**: 반드시 다음과 같은 형식으로 Mermaid 다이어그램을 포함해주세요.

```mermaid
graph TD
    A[프로젝트 성과] --> B[주요 성과 1]
    A --> C[주요 성과 2] 
    A --> D[주요 성과 3]
    B --> E[구체적 결과 1]
    C --> F[구체적 결과 2]
    D --> G[구체적 결과 3]
    E --> H[개선 포인트 1]
    F --> I[개선 포인트 2]
    G --> J[개선 포인트 3]
```

**Mermaid 차트 작성 규칙**:
- 반드시 `graph TD` 또는 `graph LR`로 시작하세요
- 노드 이름은 A, B, C... 등 영문자를 사용하세요 
- 노드 내용은 대괄호 [내용]로 감싸세요
- 화살표는 `-->` 를 사용하세요
- 각 노드는 분석 내용과 실제로 연관된 의미 있는 내용이어야 합니다
- 최소 5개 이상의 노드를 포함하세요

위 규칙을 지켜서 귀하의 전문 분야에 맞는 분석 차트를 생성해주세요.
"""

            if model_name.startswith("claude"):
                response = anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 4000})["max_tokens"],
                    messages=[{"role": "user", "content": prompt}]
                )
                analysis_content = response.content[0].text
            else:
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 4000})["max_tokens"]
                )
                analysis_content = response.choices[0].message.content
            
            # 추천사항과 위험평가 추출
            recommendations = extract_recommendations(analysis_content)
            risk_assessment = extract_risk_assessment(analysis_content)
            score = extract_score(analysis_content)
            
            return {
                'analysis': analysis_content,
                'recommendations': recommendations,
                'risk_assessment': risk_assessment,
                'score': score
            }
            
        except Exception as e:
            error_message = str(e)
            
            # 특정 오류 타입에 따른 처리
            if "overloaded" in error_message.lower() or "529" in error_message:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 지수 백오프
                    st.warning(f"⚠️ API 서버가 과부하 상태입니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ API 서버 과부하로 인해 {max_retries}번의 재시도 후에도 실패했습니다. 잠시 후 다시 시도해주세요.")
                    return None
            
            elif "rate_limit" in error_message.lower() or "429" in error_message:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + 5  # 레이트 리미트는 더 긴 대기
                    st.warning(f"⚠️ API 요청 한도에 도달했습니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ API 요청 한도 초과로 인해 {max_retries}번의 재시도 후에도 실패했습니다. 잠시 후 다시 시도해주세요.")
                    return None
            
            elif "authentication" in error_message.lower() or "401" in error_message:
                st.error("❌ API 키 인증에 실패했습니다. API 키를 확인해주세요.")
                return None
            
            elif "invalid_request" in error_message.lower() or "400" in error_message:
                st.error(f"❌ 잘못된 요청입니다: {error_message}")
                return None
            
            else:
                # 기타 오류의 경우 재시도
                if attempt < max_retries - 1:
                    delay = base_delay * (attempt + 1)
                    st.warning(f"⚠️ 예상치 못한 오류가 발생했습니다. {delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                    st.caption(f"오류 내용: {error_message}")
                    time.sleep(delay)
                    continue
                else:
                    st.error(f"❌ {max_retries}번의 재시도 후에도 분석에 실패했습니다.")
                    st.error(f"최종 오류: {error_message}")
                    return None
    
    return None

def extract_recommendations(text):
    """텍스트에서 추천사항 추출"""
    lines = text.split('\n')
    recommendations = []
    in_recommendations = False
    
    for line in lines:
        line = line.strip()
        if '권고' in line or '추천' in line or 'recommendation' in line.lower():
            in_recommendations = True
            continue
        if line and (line.startswith('#') or line.startswith('==')):
            in_recommendations = False
        if in_recommendations and line and not line.startswith('#'):
            recommendations.append(line)
    
    return '\n'.join(recommendations) if recommendations else "추천사항을 추출할 수 없습니다."

def extract_risk_assessment(text):
    """텍스트에서 위험평가 추출"""
    lines = text.split('\n')
    risks = []
    in_risks = False
    
    for line in lines:
        line = line.strip()
        if '위험' in line or '리스크' in line or 'risk' in line.lower():
            in_risks = True
            continue
        if line and (line.startswith('#') or line.startswith('==')):
            in_risks = False
        if in_risks and line and not line.startswith('#'):
            risks.append(line)
    
    return '\n'.join(risks) if risks else "위험평가를 추출할 수 없습니다."

def extract_score(text):
    """텍스트에서 점수 추출"""
    import re
    score_patterns = [
        r'종합 점수[:\s]*(\d+)',
        r'점수[:\s]*(\d+)',
        r'(\d+)점',
        r'(\d+)/10'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, text)
        if match:
            score = int(match.group(1))
            if 1 <= score <= 10:
                return score
    
    return 5  # 기본값

def validate_mermaid_chart(markdown_text):
    """Mermaid 차트의 품질을 검증하는 함수"""
    if not isinstance(markdown_text, str):
        return {'has_chart': False, 'is_valid': False, 'issues': ['텍스트가 문자열이 아님']}
    
    # Mermaid 차트 존재 여부 확인
    mermaid_patterns = [
        r"```mermaid\n(.*?)\n```",
        r"```mermaid\r?\n(.*?)\r?\n```",
        r"```mermaid\s*\n(.*?)\n\s*```",
        r"```mermaid(.*?)```"
    ]
    
    mermaid_code = None
    for pattern in mermaid_patterns:
        matches = re.findall(pattern, markdown_text, flags=re.DOTALL | re.IGNORECASE)
        if matches:
            mermaid_code = matches[0].strip()
            break
    
    if not mermaid_code:
        return {'has_chart': False, 'is_valid': False, 'issues': ['Mermaid 차트를 찾을 수 없음']}
    
    # 차트 유효성 검증
    issues = []
    
    # 1. 기본 구조 확인
    lines = mermaid_code.split('\n')
    has_graph_declaration = False
    
    for line in lines:
        line = line.strip()
        if re.match(r'^\s*(graph|flowchart)\s+(TD|TB|BT|RL|LR|)\s*$', line, re.IGNORECASE):
            has_graph_declaration = True
            break
    
    if not has_graph_declaration:
        issues.append('graph 또는 flowchart 선언이 없음')
    
    # 2. 노드 존재 확인
    node_patterns = [
        r'([A-Za-z0-9_가-힣]+)\[([^\]]+)\]',
        r'([A-Za-z0-9_가-힣]+)\(([^)]+)\)',
        r'([A-Za-z0-9_가-힣]+)\{([^}]+)\}',
        r'([A-Za-z0-9_가-힣]+)\(\(([^)]+)\)\)'
    ]
    
    nodes_found = 0
    for pattern in node_patterns:
        matches = re.findall(pattern, mermaid_code)
        nodes_found += len(matches)
    
    if nodes_found < 3:
        issues.append(f'노드가 너무 적음 (발견: {nodes_found}개, 최소: 3개)')
    
    # 3. 엣지 존재 확인
    edge_patterns = [
        r'([A-Za-z0-9_가-힣]+)\s*-->\s*([A-Za-z0-9_가-힣]+)',
        r'([A-Za-z0-9_가-힣]+)\s*->\s*([A-Za-z0-9_가-힣]+)',
        r'([A-Za-z0-9_가-힣]+)\s*---\s*([A-Za-z0-9_가-힣]+)',
        r'([A-Za-z0-9_가-힣]+)\s*--\s*([A-Za-z0-9_가-힣]+)'
    ]
    
    edges_found = 0
    for pattern in edge_patterns:
        matches = re.findall(pattern, mermaid_code)
        edges_found += len(matches)
    
    if edges_found < 2:
        issues.append(f'엣지가 너무 적음 (발견: {edges_found}개, 최소: 2개)')
    
    # 4. 문법 오류 확인
    if '[]' in mermaid_code:
        issues.append('빈 노드 레이블 발견')
    
    if '-->' not in mermaid_code and '->' not in mermaid_code and '---' not in mermaid_code and '--' not in mermaid_code:
        issues.append('연결 화살표를 찾을 수 없음')
    
    is_valid = len(issues) == 0
    
    return {
        'has_chart': True,
        'is_valid': is_valid,
        'issues': issues,
        'nodes_count': nodes_found,
        'edges_count': edges_found,
        'chart_code': mermaid_code
    }

def display_mermaid_chart(markdown_text):
    """Mermaid 차트가 포함된 마크다운 텍스트를 표시 - 개선된 버전"""
    if not isinstance(markdown_text, str):
        st.warning("차트 데이터가 문자열 형식이 아닙니다.")
        return
    
    # 더 유연한 Mermaid 패턴 매칭
    mermaid_patterns = [
        r"```mermaid\n(.*?)\n```",  # 기본 패턴
        r"```mermaid\r?\n(.*?)\r?\n```",  # 윈도우 줄바꿈 고려
        r"```mermaid\s*\n(.*?)\n\s*```",  # 공백 포함
        r"```mermaid(.*?)```"  # 줄바꿈 없는 경우
    ]
    
    mermaid_found = False
    
    for pattern in mermaid_patterns:
        matches = re.findall(pattern, markdown_text, flags=re.DOTALL | re.IGNORECASE)
        if matches:
            mermaid_found = True
            # 일반 텍스트와 Mermaid 차트 분리
            parts = re.split(pattern, markdown_text, flags=re.DOTALL | re.IGNORECASE)
            
            chart_index = 0
            for i, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue
                    
                # 일반 텍스트 부분
                if i % 2 == 0:
                    if part:
                        st.markdown(part)
                else:
                    # Mermaid 차트 부분
                    mermaid_code = part.strip()
                    if mermaid_code:
                        chart_index += 1
                        
                        # 디버그 모드에서 차트 품질 정보 표시
                        if st.session_state.get('debug_mode', False):
                            validation = validate_mermaid_chart(f"```mermaid\n{mermaid_code}\n```")
                            if validation['is_valid']:
                                st.success(f"✅ 차트 {chart_index}: 품질 우수 (노드: {validation['nodes_count']}, 엣지: {validation['edges_count']})")
                            else:
                                st.warning(f"⚠️ 차트 {chart_index}: {', '.join(validation['issues'])}")
                        
                        # Graphviz로 변환 시도
                        try:
                            dot = mermaid_to_graphviz(mermaid_code)
                            if dot:
                                st.graphviz_chart(dot.source)
                                
                                # 디버그 모드에서만 원본 코드 표시
                                if st.session_state.get('debug_mode', False):
                                    st.markdown("**🔍 Mermaid 차트 원본 코드:**")
                                    st.code(mermaid_code, language="mermaid")
                            else:
                                # 변환 실패 시 Mermaid 코드를 보기 좋게 표시
                                st.markdown("**📊 Mermaid 차트:**")
                                st.code(mermaid_code, language="mermaid")
                                st.info("💡 차트 변환에 실패했습니다. 위 코드를 Mermaid 에디터에서 확인해보세요.")
                        except Exception as e:
                            st.error(f"차트 처리 중 오류 발생: {str(e)}")
                            st.markdown("**📊 Mermaid 차트:**")
                            st.code(mermaid_code, language="mermaid")
            break
    
    # Mermaid 차트가 없는 경우 일반 마크다운으로 표시
    if not mermaid_found:
        st.markdown(markdown_text)

def mermaid_to_graphviz(mermaid_code):
    """Mermaid 코드를 Graphviz로 변환 - 개선된 버전"""
    try:
        if not mermaid_code or not mermaid_code.strip():
            return None
            
        nodes = {}
        edges = []
        
        # 코드 정리
        mermaid_code = mermaid_code.strip()
        lines = mermaid_code.split('\n')
        
        # 그래프 타입 확인 및 제거
        graph_type_patterns = [
            r'^\s*graph\s+(TD|TB|BT|RL|LR)\s*$',
            r'^\s*flowchart\s+(TD|TB|BT|RL|LR)\s*$',
            r'^\s*graph\s*$',
            r'^\s*flowchart\s*$'
        ]
        
        processed_lines = []
        direction = 'TD'  # 기본 방향
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 그래프 타입 라인 건너뛰기
            is_graph_type = False
            for pattern in graph_type_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # 방향 정보 추출
                    if 'LR' in line.upper():
                        direction = 'LR'
                    elif 'RL' in line.upper():
                        direction = 'RL'
                    elif 'BT' in line.upper():
                        direction = 'BT'
                    else:
                        direction = 'TD'
                    is_graph_type = True
                    break
            
            if not is_graph_type:
                processed_lines.append(line)
        
        # 처리된 라인들에서 노드와 엣지 추출
        content = '\n'.join(processed_lines)
        
        # 개선된 노드 패턴 (다양한 형태 지원)
        node_patterns = [
            r'([A-Za-z0-9_가-힣]+)\[([^\]]+)\]',  # A[내용] - 한글 지원
            r'([A-Za-z0-9_가-힣]+)\(([^)]+)\)',   # A(내용) - 원형
            r'([A-Za-z0-9_가-힣]+)\{([^}]+)\}',   # A{내용} - 다이아몬드
            r'([A-Za-z0-9_가-힣]+)\(\(([^)]+)\)\)', # A((내용)) - 원
        ]
        
        for pattern in node_patterns:
            for match in re.finditer(pattern, content):
                node_id, node_label = match.groups()
                nodes[node_id] = node_label.strip()
        
        # 개선된 엣지 패턴 (다양한 화살표 지원)
        edge_patterns = [
            r'([A-Za-z0-9_가-힣]+)\s*-->\s*([A-Za-z0-9_가-힣]+)',  # A --> B
            r'([A-Za-z0-9_가-힣]+)\s*->\s*([A-Za-z0-9_가-힣]+)',   # A -> B
            r'([A-Za-z0-9_가-힣]+)\s*---\s*([A-Za-z0-9_가-힣]+)',  # A --- B
            r'([A-Za-z0-9_가-힣]+)\s*--\s*([A-Za-z0-9_가-힣]+)',   # A -- B
        ]
        
        for pattern in edge_patterns:
            matches = re.findall(pattern, content)
            edges.extend(matches)
        
        # 노드나 엣지가 없으면 None 반환
        if not nodes and not edges:
            return None
        
        # Graphviz 객체 생성
        dot = graphviz.Digraph()
        
        # 방향 설정
        if direction == 'LR':
            dot.attr(rankdir='LR')
        elif direction == 'RL':
            dot.attr(rankdir='RL')
        elif direction == 'BT':
            dot.attr(rankdir='BT')
        else:
            dot.attr(rankdir='TB')
        
        # 스타일 개선
        dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
        dot.attr('edge', color='darkblue')
        
        # 노드 추가
        for node_id, node_label in nodes.items():
            # 긴 레이블 처리
            if len(node_label) > 20:
                # 긴 텍스트를 여러 줄로 분할
                words = node_label.split()
                lines = []
                current_line = []
                for word in words:
                    if len(' '.join(current_line + [word])) <= 20:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                node_label = '\\n'.join(lines)
            
            dot.node(node_id, node_label)
        
        # 엣지에서 참조된 노드 중 정의되지 않은 것들 추가
        all_edge_nodes = set()
        for src, dst in edges:
            all_edge_nodes.add(src)
            all_edge_nodes.add(dst)
        
        for node_id in all_edge_nodes:
            if node_id not in nodes:
                dot.node(node_id, node_id)  # 기본 레이블로 추가
        
        # 엣지 추가
        for src, dst in edges:
            dot.edge(src, dst)
        
        return dot
        
    except Exception as e:
        st.error(f"차트 변환 중 오류 발생: {str(e)}")
        # 디버그 정보 제공
        if st.session_state.get('debug_mode', False):
            st.code(f"원본 Mermaid 코드:\n{mermaid_code}")
        return None

def create_dashboard_charts(reviews_df):
    """대시보드 차트 생성"""
    charts = {}
    
    if not reviews_df.empty:
        # 프로젝트 상태 분포
        status_counts = reviews_df['status'].value_counts()
        charts['status'] = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="프로젝트 상태 분포"
        )
        
        # 프로젝트 유형별 분포
        type_counts = reviews_df['project_type'].value_counts()
        charts['type'] = px.bar(
            x=type_counts.index,
            y=type_counts.values,
            title="프로젝트 유형별 분포"
        )
        
        # 예산 vs 실제 비용
        charts['budget'] = px.scatter(
            reviews_df,
            x='budget',
            y='actual_cost',
            title="예산 vs 실제 비용",
            hover_data=['project_name']
        )
        
        # 평점 분포
        charts['rating'] = px.histogram(
            reviews_df,
            x='overall_rating',
            title="프로젝트 평점 분포",
            nbins=10
        )
        
        # 월별 프로젝트 완료 추이
        if 'end_date' in reviews_df.columns:
            reviews_df['end_month'] = pd.to_datetime(reviews_df['end_date']).dt.to_period('M')
            monthly_counts = reviews_df['end_month'].value_counts().sort_index()
            charts['monthly'] = px.line(
                x=monthly_counts.index.astype(str),
                y=monthly_counts.values,
                title="월별 프로젝트 완료 추이"
            )
    
    return charts

def export_to_csv(data, filename):
    """CSV로 데이터 내보내기"""
    csv = data.to_csv(index=False).encode('utf-8-sig')
    return csv

def export_to_excel(data, filename):
    """Excel로 데이터 내보내기"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        data.to_excel(writer, index=False, sheet_name='Project Reviews')
    return output.getvalue()

def generate_pdf_report(review_data, ai_analyses):
    """PDF 리포트 생성"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # 제목
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1  # 중앙 정렬
        )
        story.append(Paragraph(f"프로젝트 리뷰 리포트: {review_data['project_name']}", title_style))
        story.append(Spacer(1, 12))
        
        # 프로젝트 기본 정보
        story.append(Paragraph("프로젝트 기본 정보", styles['Heading2']))
        project_info = [
            ['항목', '내용'],
            ['프로젝트명', review_data['project_name']],
            ['프로젝트 유형', review_data['project_type']],
            ['프로젝트 매니저', review_data['project_manager']],
            ['기간', f"{review_data['start_date']} ~ {review_data['end_date']}"],
            ['예산', f"{review_data['budget']:,}원"],
            ['실제 비용', f"{review_data['actual_cost']:,}원"],
            ['전체 평점', f"{review_data['overall_rating']}/10"]
        ]
        
        table = Table(project_info)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
        story.append(Spacer(1, 12))
        
        # AI 분석 결과
        if ai_analyses:
            story.append(Paragraph("AI 분석 결과", styles['Heading2']))
            for analysis in ai_analyses:
                story.append(Paragraph(f"{analysis['agent_type']} 분석", styles['Heading3']))
                story.append(Paragraph(analysis['analysis_content'][:500] + "...", styles['Normal']))
                story.append(Spacer(1, 12))
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None

def main():
    
    
    # 테이블 생성 확인
    if not create_project_review_tables():
        st.error("데이터베이스 테이블 생성에 실패했습니다.")
        return
    
    # 사이드바 설정
    with st.sidebar:
        st.header("설정")
        
        # 디버그 모드 추가
        debug_mode = st.checkbox(
            "🐛 디버그 모드",
            value=False,
            help="Mermaid 차트 변환 과정과 오류를 자세히 표시합니다"
        )
        
        # 세션 상태에 저장
        st.session_state['debug_mode'] = debug_mode
        
        # 모델 선택
        selected_model = st.selectbox(
            "AI 모델 선택",
            options=available_models,
            index=0,
            help="분석에 사용할 AI 모델을 선택하세요"
        )
        
        # AI 에이전트 설정
        st.subheader("🤖 AI 에이전트 기본 설정")
        st.caption("기본으로 사용할 AI 전문가들을 선택하세요 (분석 시 개별 조정 가능)")
        
        # 에이전트 프리셋 선택
        st.markdown("#### 🎯 빠른 설정 프리셋")
        st.caption("💡 자주 사용하는 조합을 빠르게 선택할 수 있습니다")
        preset_option = st.selectbox(
            "프리셋 선택",
            ["사용자 정의", "전체 분석", "핵심 분석", "기술 중심", "비즈니스 중심", "리스크 중심"],
            key="agent_preset",
            help="프리셋을 선택하면 해당 조합으로 자동 설정됩니다. 개별 조정도 가능합니다."
        )
        
        # 선택된 프리셋 설명
        preset_descriptions = {
            "전체 분석": "📊 모든 전문가 (7명) - 가장 포괄적인 분석",
            "핵심 분석": "🎯 핵심 4개 영역 - 프로젝트 관리, 기술, 비즈니스, 재무",
            "기술 중심": "⚙️ 기술 관련 3개 영역 - 기술, 품질, 리스크",
            "비즈니스 중심": "💼 비즈니스 관련 5개 영역 - 프로젝트 관리, 비즈니스, 리스크, 팀, 재무",
            "리스크 중심": "⚠️ 리스크 관련 4개 영역 - 프로젝트 관리, 품질, 리스크, 재무"
        }
        
        if preset_option in preset_descriptions:
            st.info(f"💡 **{preset_option}**: {preset_descriptions[preset_option]}")
        elif preset_option == "사용자 정의":
            st.info("🔧 **사용자 정의**: 아래에서 원하는 전문가들을 개별 선택하세요")
        
        # 프리셋에 따른 에이전트 설정
        if preset_option == "전체 분석":
            for agent in ['project_manager_agent', 'technical_agent', 'business_agent', 'quality_agent', 'risk_agent', 'team_agent', 'financial_agent']:
                st.session_state[f"agent_{agent}"] = True
        elif preset_option == "핵심 분석":
            agents_to_set = {
                'project_manager_agent': True,
                'technical_agent': True,
                'business_agent': True,
                'quality_agent': False,
                'risk_agent': False,
                'team_agent': False,
                'financial_agent': True
            }
            for agent, value in agents_to_set.items():
                st.session_state[f"agent_{agent}"] = value
        elif preset_option == "기술 중심":
            agents_to_set = {
                'project_manager_agent': False,
                'technical_agent': True,
                'business_agent': False,
                'quality_agent': True,
                'risk_agent': True,
                'team_agent': False
            }
            for agent, value in agents_to_set.items():
                st.session_state[f"agent_{agent}"] = value
        elif preset_option == "비즈니스 중심":
            agents_to_set = {
                'project_manager_agent': True,
                'technical_agent': False,
                'business_agent': True,
                'quality_agent': False,
                'risk_agent': True,
                'team_agent': True,
                'financial_agent': True
            }
            for agent, value in agents_to_set.items():
                st.session_state[f"agent_{agent}"] = value
        elif preset_option == "리스크 중심":
            agents_to_set = {
                'project_manager_agent': True,
                'technical_agent': False,
                'business_agent': False,
                'quality_agent': True,
                'risk_agent': True,
                'team_agent': False
            }
            for agent, value in agents_to_set.items():
                st.session_state[f"agent_{agent}"] = value
        
        # 전체 선택/해제 버튼
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 전체 선택", key="select_all_agents"):
                for agent in ['project_manager_agent', 'technical_agent', 'business_agent', 'quality_agent', 'risk_agent', 'team_agent', 'financial_agent']:
                    st.session_state[f"agent_{agent}"] = True
        with col2:
            if st.button("❌ 전체 해제", key="deselect_all_agents"):
                for agent in ['project_manager_agent', 'technical_agent', 'business_agent', 'quality_agent', 'risk_agent', 'team_agent', 'financial_agent']:
                    st.session_state[f"agent_{agent}"] = False
        
        # 개별 에이전트 선택
        # 종합 평가 에이전트 (항상 활성화)
        st.markdown("### 🎯 종합 평가 전문가")
        st.checkbox("🔗 종합 평가 전문가", 
                   value=True, 
                   disabled=True,
                   key="agent_integration_agent_display",
                   help="모든 전문가의 분석을 통합하여 종합 평가 (항상 활성화)")
        
        st.markdown("### 📊 개별 전문가 선택")
        active_agents = {
            'project_manager_agent': st.checkbox("📋 프로젝트 관리 전문가", 
                                               value=st.session_state.get("agent_project_manager_agent", True),
                                               key="agent_project_manager_agent",
                                               help="일정, 예산, 리소스 관리 분석"),
            'technical_agent': st.checkbox("⚙️ 기술 전문가", 
                                         value=st.session_state.get("agent_technical_agent", True),
                                         key="agent_technical_agent",
                                         help="기술 아키텍처, 코드 품질, 성능 분석"),
            'business_agent': st.checkbox("💼 비즈니스 전문가", 
                                        value=st.session_state.get("agent_business_agent", True),
                                        key="agent_business_agent",
                                        help="ROI, 비즈니스 가치, 시장 영향도 분석"),
            'quality_agent': st.checkbox("🎯 품질 전문가", 
                                       value=st.session_state.get("agent_quality_agent", True),
                                       key="agent_quality_agent",
                                       help="품질 메트릭스, 사용자 경험, 테스트 분석"),
            'risk_agent': st.checkbox("⚠️ 리스크 전문가", 
                                    value=st.session_state.get("agent_risk_agent", True),
                                    key="agent_risk_agent",
                                    help="위험 식별, 평가, 대응 전략 분석"),
            'team_agent': st.checkbox("👥 팀 성과 전문가", 
                                    value=st.session_state.get("agent_team_agent", True),
                                    key="agent_team_agent",
                                    help="팀 생산성, 협업, 만족도 분석"),
            'financial_agent': st.checkbox("💰 재무 전문가", 
                                         value=st.session_state.get("agent_financial_agent", True),
                                         key="agent_financial_agent",
                                         help="ROI, NPV/IRR, 비용 효율성, 재무 성과 분석")
        }
        
        # 종합 평가 에이전트는 항상 활성화
        active_agents['integration_agent'] = True
        
        # 선택된 에이전트 수 표시 (종합 평가 에이전트 제외하고 계산)
        individual_agents_count = sum([v for k, v in active_agents.items() if k != 'integration_agent'])
        total_count = sum(active_agents.values())
        
        st.markdown("#### 📊 현재 기본 설정")
        if individual_agents_count > 0:
            st.success(f"✅ **기본 조합**: {individual_agents_count}개 개별 전문가 + 1개 종합 평가 = 총 {total_count}개")
            st.caption("💡 분석 시 '이번 분석만을 위한 전문가 조합 변경'에서 임시로 다른 조합 사용 가능")
        else:
            st.warning("⚠️ 최소 1개의 개별 전문가를 선택해주세요 (종합 평가는 자동 포함)")
            st.caption("💡 위의 프리셋을 선택하거나 개별 전문가를 체크하세요")
    
    # 메인 탭
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 대시보드", "📝 프로젝트 등록", "✏️ 프로젝트 수정", "🤖 AI 분석", "📋 프로젝트 목록", "🔍 파일 검색"])
    
    with tab1:
        st.header("프로젝트 리뷰 대시보드")
        
        # 프로젝트 데이터 로드
        reviews = get_project_reviews()
        
        if reviews:
            reviews_df = pd.DataFrame(reviews)
            
            # 주요 지표
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 프로젝트 수", len(reviews_df))
            
            with col2:
                completed_projects = len(reviews_df[reviews_df['status'] == 'completed'])
                st.metric("완료된 프로젝트", completed_projects)
            
            with col3:
                avg_rating = reviews_df['overall_rating'].mean()
                st.metric("평균 평점", f"{avg_rating:.1f}/10")
            
            with col4:
                total_budget = reviews_df['budget'].sum()
                st.metric("총 예산", f"{total_budget:,.0f}원")
            
            # 차트 생성 및 표시
            charts = create_dashboard_charts(reviews_df)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'status' in charts:
                    st.plotly_chart(charts['status'], use_container_width=True)
                if 'budget' in charts:
                    st.plotly_chart(charts['budget'], use_container_width=True)
            
            with col2:
                if 'type' in charts:
                    st.plotly_chart(charts['type'], use_container_width=True)
                if 'rating' in charts:
                    st.plotly_chart(charts['rating'], use_container_width=True)
            
            if 'monthly' in charts:
                st.plotly_chart(charts['monthly'], use_container_width=True)
            
            # 데이터 내보내기
            st.subheader("데이터 내보내기")
            col1, col2 = st.columns(2)
            
            with col1:
                csv_data = export_to_csv(reviews_df, "project_reviews.csv")
                st.download_button(
                    label="CSV 다운로드",
                    data=csv_data,
                    file_name="project_reviews.csv",
                    mime="text/csv",
                    key="dashboard_csv_download"
                )
            
            with col2:
                excel_data = export_to_excel(reviews_df, "project_reviews.xlsx")
                st.download_button(
                    label="Excel 다운로드",
                    data=excel_data,
                    file_name="project_reviews.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dashboard_excel_download"
                )
        else:
            st.info("등록된 프로젝트가 없습니다. 프로젝트를 먼저 등록해주세요.")
    
    with tab2:
        st.header("새 프로젝트 리뷰 등록")
        
        with st.form("project_review_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                project_name = st.text_input("프로젝트명*", placeholder="프로젝트 이름을 입력하세요")
                project_type = st.selectbox(
                    "프로젝트 유형*",
                    [
                        "스마트 공간 구축-IoT 및 Skylights 설치",
                        "웹 개발", 
                        "모바일 앱", 
                        "데이터 분석", 
                        "AI/ML", 
                        "인프라", 
                        "POC (Proof of Concept)",
                        "마케팅/브랜딩",
                        "R&D/연구개발",
                        "프로세스 개선",
                        "비용 절감",
                        "품질 향상",
                        "기타"
                    ]
                )
                project_manager = st.text_input("프로젝트 매니저*")
                team_members = st.text_area("팀원 목록", placeholder="팀원들의 이름을 입력하세요")
                
            with col2:
                start_date = st.date_input("시작일*")
                end_date = st.date_input("종료일*")
                budget = st.number_input("예산 (원)*", min_value=0, step=1000000)
                actual_cost = st.number_input("실제 비용 (원)*", min_value=0, step=1000000)
                
                # 프로젝트 유형에 따른 가치 지표 선택
                st.subheader("💰 프로젝트 가치 지표")
                
                value_type = st.radio(
                    "가치 측정 방식",
                    [
                        "매출 창출", 
                        "비용 절약", 
                        "무형 가치 (정성적)", 
                        "복합 가치"
                    ],
                    help="프로젝트의 주요 가치 창출 방식을 선택하세요"
                )
                
                revenue = 0
                cost_savings = 0
                
                if value_type == "매출 창출":
                    revenue = st.number_input("매출액 (원)", min_value=0, step=1000000, help="프로젝트로 인해 창출된 직접 매출액")
                    
                elif value_type == "비용 절약":
                    cost_savings = st.number_input("비용 절약액 (원)", min_value=0, step=1000000, help="프로젝트로 인해 절약된 비용 (연간 기준)")
                    
                elif value_type == "무형 가치 (정성적)":
                    st.info("💡 이 프로젝트는 정성적 가치 창출 프로젝트입니다. AI 분석에서 정성적 성과를 중심으로 평가됩니다.")
                    
                elif value_type == "복합 가치":
                    revenue = st.number_input("매출액 (원)", min_value=0, step=1000000, help="직접 매출액")
                    cost_savings = st.number_input("비용 절약액 (원)", min_value=0, step=1000000, help="절약된 비용 (연간 기준)")
                
                # 무형 가치 지표들 (모든 프로젝트에 공통 적용)
                st.subheader("📊 정성적 가치 지표 (선택사항)")
                
                col_qual1, col_qual2 = st.columns(2)
                
                with col_qual1:
                    customer_satisfaction = st.slider("고객 만족도 개선", 0, 10, 0, help="0: 영향 없음, 10: 매우 큰 개선")
                    brand_value = st.slider("브랜드 가치 향상", 0, 10, 0, help="0: 영향 없음, 10: 매우 큰 향상")
                    
                with col_qual2:
                    efficiency_improvement = st.slider("업무 효율성 개선", 0, 10, 0, help="0: 개선 없음, 10: 매우 큰 개선")
                    risk_reduction = st.slider("리스크 감소 효과", 0, 10, 0, help="0: 효과 없음, 10: 매우 큰 효과")
            
            status = st.selectbox(
                "프로젝트 상태*",
                ["completed", "ongoing", "cancelled", "on_hold"]
            )
            
            overall_rating = st.slider("전체 평점*", 1, 10, 5)
            
            description = st.text_area("프로젝트 설명*", height=100)
            objectives = st.text_area("프로젝트 목표", height=100)
            deliverables = st.text_area("주요 산출물", height=100)
            challenges = st.text_area("주요 도전과제", height=100)
            lessons_learned = st.text_area("교훈 및 학습사항", height=100)
            recommendations = st.text_area("향후 권고사항", height=100)
            created_by = st.text_input("작성자*")
            
            # 파일 업로드
            st.subheader("관련 문서 업로드")
            uploaded_files = st.file_uploader(
                "프로젝트 관련 문서를 업로드하세요",
                type=['pdf', 'docx', 'doc', 'txt', 'md', 'xlsx', 'xls', 'csv', 'json', 'xml', 'html', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'rar'],
                accept_multiple_files=True,
                help="다양한 파일 형식을 지원합니다 (PDF, DOCX, TXT, MD, XLSX, 이미지, 압축파일 등)"
            )
            
            submitted = st.form_submit_button("프로젝트 리뷰 저장", type="primary")
            
            if submitted:
                if not all([project_name, project_type, project_manager, start_date, end_date, 
                           budget is not None, actual_cost is not None, description, created_by]):
                    st.error("필수 항목(*)을 모두 입력해주세요.")
                else:
                    review_data = {
                        'project_name': project_name,
                        'project_type': project_type,
                        'start_date': start_date,
                        'end_date': end_date,
                        'project_manager': project_manager,
                        'team_members': team_members,
                        'budget': budget,
                        'actual_cost': actual_cost,
                        'revenue': revenue,
                        'value_type': value_type,
                        'cost_savings': cost_savings,
                        'customer_satisfaction': customer_satisfaction,
                        'brand_value': brand_value,
                        'efficiency_improvement': efficiency_improvement,
                        'risk_reduction': risk_reduction,
                        'status': status,
                        'overall_rating': overall_rating,
                        'description': description,
                        'objectives': objectives,
                        'deliverables': deliverables,
                        'challenges': challenges,
                        'lessons_learned': lessons_learned,
                        'recommendations': recommendations,
                        'created_by': created_by
                    }
                    
                    review_id = save_project_review(review_data)
                    
                    if review_id:
                        st.success(f"✅ 프로젝트 리뷰가 저장되었습니다! (ID: {review_id})")
                        
                        # 파일 저장
                        if uploaded_files:
                            for uploaded_file in uploaded_files:
                                file_data = parse_uploaded_file(uploaded_file)
                                if file_data:
                                    if save_project_file(review_id, file_data):
                                        st.success(f"✅ 파일 '{uploaded_file.name}'이 저장되었습니다.")
                                    else:
                                        st.error(f"❌ 파일 '{uploaded_file.name}' 저장에 실패했습니다.")
                        
                        # 세션 상태에 저장하여 AI 분석 탭에서 사용
                        st.session_state['current_review_id'] = review_id
                        st.session_state['current_review_data'] = review_data
                    else:
                        st.error("❌ 프로젝트 리뷰 저장에 실패했습니다.")
    
    with tab3:
        st.header("프로젝트 리뷰 수정")
        
        # 수정할 프로젝트 선택
        reviews = get_project_reviews()
        
        if not reviews:
            st.info("수정할 프로젝트가 없습니다. 먼저 프로젝트를 등록해주세요.")
        else:
            # 세션 상태에서 선택된 프로젝트 ID 확인
            default_index = 0
            if 'edit_project_id' in st.session_state:
                for i, review in enumerate(reviews):
                    if review['review_id'] == st.session_state['edit_project_id']:
                        default_index = i
                        break
                # 사용 후 세션 상태 클리어
                del st.session_state['edit_project_id']
            
            selected_review = st.selectbox(
                "수정할 프로젝트 선택",
                reviews,
                format_func=lambda x: f"{x['project_name']} ({x['created_at'].strftime('%Y-%m-%d')})",
                key="edit_project_select",
                index=default_index
            )
            
            if selected_review:
                st.info(f"선택된 프로젝트: {selected_review['project_name']}")
                
                # 기존 첨부 파일 관리 (폼 외부)
                existing_files = get_project_files(selected_review['review_id'])
                if existing_files:
                    st.subheader("기존 첨부 파일 관리")
                    for file in existing_files:
                        with st.expander(f"📄 {file['filename']} ({file['file_type'].upper()}) - {file['uploaded_at'].strftime('%Y-%m-%d %H:%M')}"):
                            col1, col2, col3 = st.columns([2, 1, 1])
                            
                            with col1:
                                st.write(f"**파일 크기:** {file['file_size']:,} bytes")
                                st.write(f"**업로드 시간:** {file['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            with col2:
                                # 원본 파일 다운로드
                                file_binary = get_file_binary_data(file['file_id'])
                                if file_binary:
                                    mime_type = get_file_mime_type(file['file_type'])
                                    st.download_button(
                                        label="📥 원본 파일",
                                        data=file_binary['binary_data'],
                                        file_name=file['filename'],
                                        mime=mime_type,
                                        key=f"download_original_{file['file_id']}",
                                        help="원본 파일 형식으로 다운로드"
                                    )
                                    
                                    # 텍스트 내용 다운로드 (AI 분석용)
                                    if file['file_content'] and not file['file_content'].startswith('['):
                                        file_content = file['file_content'].encode('utf-8')
                                        st.download_button(
                                            label="📄 텍스트 내용",
                                            data=file_content,
                                            file_name=f"{file['filename']}_content.txt",
                                            mime="text/plain",
                                            key=f"download_content_{file['file_id']}",
                                            help="추출된 텍스트 내용 다운로드"
                                        )
                                else:
                                    st.error("원본 파일 데이터를 찾을 수 없습니다.")
                            
                            with col3:
                                # 파일 미리보기 버튼
                                if st.button("👁️ 미리보기", key=f"preview_file_{file['file_id']}", help="파일 미리보기"):
                                    st.session_state[f"show_preview_{file['file_id']}"] = not st.session_state.get(f"show_preview_{file['file_id']}", False)
                                
                                if st.button("🗑️ 삭제", key=f"delete_file_{file['file_id']}", help="파일 삭제"):
                                    if delete_project_file(file['file_id']):
                                        st.success(f"파일 '{file['filename']}'이 삭제되었습니다.")
                                        st.rerun()
                                    else:
                                        st.error("파일 삭제에 실패했습니다.")
                            
                            # 파일 미리보기 표시
                            if st.session_state.get(f"show_preview_{file['file_id']}", False):
                                st.subheader("📖 파일 미리보기")
                                
                                # 원본 파일 데이터 가져오기
                                file_binary = get_file_binary_data(file['file_id'])
                                
                                if file_binary:
                                    # 파일 미리보기 함수 호출
                                    preview_success = display_file_preview(file_binary, file['file_type'], file['filename'])
                                    
                                    # 미리보기가 실패하거나 지원하지 않는 형식인 경우 텍스트 내용 표시
                                    if not preview_success and file['file_content']:
                                        st.subheader("📄 추출된 텍스트 내용")
                                        content = file['file_content']
                                        if content.startswith('[') and content.endswith(']'):
                                            st.info(content)
                                        elif len(content) > 2000:
                                            st.text_area(
                                                "파일 내용 (처음 2000자)",
                                                value=content[:2000] + "\n\n... (내용이 더 있습니다. 전체 내용을 보려면 다운로드하세요)",
                                                height=300,
                                                disabled=True,
                                                key=f"preview_text_{file['file_id']}"
                                            )
                                        else:
                                            st.text_area(
                                                "파일 내용",
                                                value=content,
                                                height=300,
                                                disabled=True,
                                                key=f"full_content_{file['file_id']}"
                                            )
                                else:
                                    # 구버전 파일 - 텍스트 내용만 표시
                                    if file['file_content']:
                                        st.subheader("📄 추출된 텍스트 내용")
                                        content = file['file_content']
                                        if content.startswith('[') and content.endswith(']'):
                                            st.info(content)
                                        elif len(content) > 2000:
                                            st.text_area(
                                                "파일 내용 (처음 2000자)",
                                                value=content[:2000] + "\n\n... (내용이 더 있습니다. 전체 내용을 보려면 다운로드하세요)",
                                                height=300,
                                                disabled=True,
                                                key=f"old_preview_{file['file_id']}"
                                            )
                                        else:
                                            st.text_area(
                                                "파일 내용",
                                                value=content,
                                                height=300,
                                                disabled=True,
                                                key=f"old_full_content_{file['file_id']}"
                                            )
                                    else:
                                        st.info("파일 내용이 없습니다.")
                                
                                # 미리보기 숨기기 버튼
                                if st.button("🙈 미리보기 숨기기", key=f"hide_preview_{file['file_id']}"):
                                    st.session_state[f"show_preview_{file['file_id']}"] = False
                                    st.rerun()
                
                with st.form("project_edit_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        project_name = st.text_input(
                            "프로젝트명*", 
                            value=selected_review['project_name'],
                            placeholder="프로젝트 이름을 입력하세요"
                        )
                        project_type = st.selectbox(
                            "프로젝트 유형*",
                            ["매출 창출", "POC (Proof of Concept)", "마케팅/브랜딩", "R&D/연구개발", "프로세스 개선", "비용 절감", "품질 향상", "웹 개발", "모바일 앱", "데이터 분석", "AI/ML", "인프라", "기타"],
                            index=["매출 창출", "POC (Proof of Concept)", "마케팅/브랜딩", "R&D/연구개발", "프로세스 개선", "비용 절감", "품질 향상", "웹 개발", "모바일 앱", "데이터 분석", "AI/ML", "인프라", "기타"].index(selected_review['project_type']) if selected_review['project_type'] in ["매출 창출", "POC (Proof of Concept)", "마케팅/브랜딩", "R&D/연구개발", "프로세스 개선", "비용 절감", "품질 향상", "웹 개발", "모바일 앱", "데이터 분석", "AI/ML", "인프라", "기타"] else 0
                        )
                        project_manager = st.text_input(
                            "프로젝트 매니저*", 
                            value=selected_review['project_manager'] or ""
                        )
                        team_members = st.text_area(
                            "팀원 목록", 
                            value=selected_review['team_members'] or "",
                            placeholder="팀원들의 이름을 입력하세요"
                        )
                        
                    with col2:
                        start_date = st.date_input(
                            "시작일*", 
                            value=selected_review['start_date']
                        )
                        end_date = st.date_input(
                            "종료일*", 
                            value=selected_review['end_date']
                        )
                        budget = st.number_input(
                            "예산 (원)*", 
                            min_value=0, 
                            step=1000000,
                            value=float(selected_review['budget']) if selected_review['budget'] else 0
                        )
                        actual_cost = st.number_input(
                            "실제 비용 (원)*", 
                            min_value=0, 
                            step=1000000,
                            value=float(selected_review['actual_cost']) if selected_review['actual_cost'] else 0
                        )
                    
                    # 프로젝트 가치 측정 방식 선택
                    st.subheader("🎯 프로젝트 가치 측정")
                    
                    current_value_type = selected_review.get('value_type', '매출 창출')
                    value_type = st.radio(
                        "가치 측정 방식을 선택하세요",
                        ["매출 창출", "비용 절약", "무형 가치 (정성적)", "복합 가치"],
                        index=["매출 창출", "비용 절약", "무형 가치 (정성적)", "복합 가치"].index(current_value_type) if current_value_type in ["매출 창출", "비용 절약", "무형 가치 (정성적)", "복합 가치"] else 0,
                        horizontal=True,
                        help="프로젝트의 가치를 어떻게 측정할지 선택하세요"
                    )
                    
                    # 조건부 입력 필드
                    col1, col2 = st.columns(2)
                    
                    revenue = 0
                    cost_savings = 0
                    
                    with col1:
                        if value_type in ["매출 창출", "복합 가치"]:
                            revenue = st.number_input(
                                "매출액 (원)" + ("*" if value_type == "매출 창출" else ""),
                                min_value=0,
                                step=1000000,
                                value=float(selected_review.get('revenue', 0)) if selected_review.get('revenue') else 0,
                                help="프로젝트로 인해 창출된 매출액을 입력하세요"
                            )
                    
                    with col2:
                        if value_type in ["비용 절약", "복합 가치"]:
                            cost_savings = st.number_input(
                                "비용 절약액 (원)" + ("*" if value_type == "비용 절약" else ""),
                                min_value=0,
                                step=1000000,
                                value=float(selected_review.get('cost_savings', 0)) if selected_review.get('cost_savings') else 0,
                                help="프로젝트로 인해 절약된 비용을 입력하세요"
                            )
                    
                    # 정성적 가치 지표 (모든 프로젝트에 공통)
                    if value_type in ["무형 가치 (정성적)", "복합 가치"] or (value_type in ["매출 창출", "비용 절약"] and st.checkbox("정성적 가치도 함께 평가", value=bool(selected_review.get('customer_satisfaction', 0) or selected_review.get('brand_value', 0)))):
                        st.subheader("📊 정성적 가치 지표 (0-10점)")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            customer_satisfaction = st.slider(
                                "고객 만족도 개선",
                                0, 10,
                                value=selected_review.get('customer_satisfaction', 0) if selected_review.get('customer_satisfaction') else 0,
                                help="고객 만족도가 얼마나 개선되었는지 평가하세요"
                            )
                            brand_value = st.slider(
                                "브랜드 가치 향상",
                                0, 10,
                                value=selected_review.get('brand_value', 0) if selected_review.get('brand_value') else 0,
                                help="브랜드 가치나 이미지가 얼마나 향상되었는지 평가하세요"
                            )
                        
                        with col2:
                            efficiency_improvement = st.slider(
                                "업무 효율성 개선",
                                0, 10,
                                value=selected_review.get('efficiency_improvement', 0) if selected_review.get('efficiency_improvement') else 0,
                                help="업무 프로세스나 효율성이 얼마나 개선되었는지 평가하세요"
                            )
                            risk_reduction = st.slider(
                                "리스크 감소 효과",
                                0, 10,
                                value=selected_review.get('risk_reduction', 0) if selected_review.get('risk_reduction') else 0,
                                help="프로젝트로 인한 리스크 감소 효과를 평가하세요"
                            )
                    else:
                        customer_satisfaction = 0
                        brand_value = 0
                        efficiency_improvement = 0
                        risk_reduction = 0
                    
                    status = st.selectbox(
                        "프로젝트 상태*",
                        ["completed", "ongoing", "cancelled", "on_hold"],
                        index=["completed", "ongoing", "cancelled", "on_hold"].index(selected_review['status']) if selected_review['status'] in ["completed", "ongoing", "cancelled", "on_hold"] else 0
                    )
                    
                    overall_rating = st.slider(
                        "전체 평점*", 
                        1, 10, 
                        value=selected_review['overall_rating'] if selected_review['overall_rating'] else 5
                    )
                    
                    description = st.text_area(
                        "프로젝트 설명*", 
                        value=selected_review['description'] or "",
                        height=100
                    )
                    objectives = st.text_area(
                        "프로젝트 목표", 
                        value=selected_review['objectives'] or "",
                        height=100
                    )
                    deliverables = st.text_area(
                        "주요 산출물", 
                        value=selected_review['deliverables'] or "",
                        height=100
                    )
                    challenges = st.text_area(
                        "주요 도전과제", 
                        value=selected_review['challenges'] or "",
                        height=100
                    )
                    lessons_learned = st.text_area(
                        "교훈 및 학습사항", 
                        value=selected_review['lessons_learned'] or "",
                        height=100
                    )
                    recommendations = st.text_area(
                        "향후 권고사항", 
                        value=selected_review['recommendations'] or "",
                        height=100
                    )
                    
                    # 새 파일 업로드
                    st.subheader("새 문서 추가 업로드")
                    uploaded_files = st.file_uploader(
                        "추가할 프로젝트 관련 문서를 업로드하세요",
                        type=['pdf', 'docx', 'doc', 'txt', 'md', 'xlsx', 'xls', 'csv', 'json', 'xml', 'html', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'rar'],
                        accept_multiple_files=True,
                        help="다양한 파일 형식을 지원합니다 (PDF, DOCX, TXT, MD, XLSX, 이미지, 압축파일 등)",
                        key="edit_file_upload"
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        update_submitted = st.form_submit_button("프로젝트 리뷰 수정", type="primary")
                    
                    with col2:
                        delete_submitted = st.form_submit_button("프로젝트 삭제", type="secondary")
                    
                    if update_submitted:
                        # 유효성 검사
                        validation_errors = []
                        
                        # 기본 필수 항목 확인
                        if not all([project_name, project_type, project_manager, start_date, end_date, 
                                   budget is not None, actual_cost is not None, description]):
                            validation_errors.append("필수 항목(*)을 모두 입력해주세요.")
                        
                        # 가치 측정 방식에 따른 유효성 검사
                        if value_type == "매출 창출" and revenue <= 0:
                            validation_errors.append("매출 창출형 프로젝트는 매출액을 입력해야 합니다.")
                        elif value_type == "비용 절약" and cost_savings <= 0:
                            validation_errors.append("비용 절약형 프로젝트는 비용 절약액을 입력해야 합니다.")
                        
                        if validation_errors:
                            for error in validation_errors:
                                st.error(error)
                        else:
                            review_data = {
                                'project_name': project_name,
                                'project_type': project_type,
                                'start_date': start_date,
                                'end_date': end_date,
                                'project_manager': project_manager,
                                'team_members': team_members,
                                'budget': budget,
                                'actual_cost': actual_cost,
                                'status': status,
                                'overall_rating': overall_rating,
                                'description': description,
                                'objectives': objectives,
                                'deliverables': deliverables,
                                'challenges': challenges,
                                'lessons_learned': lessons_learned,
                                'recommendations': recommendations,
                                'value_type': value_type,
                                'revenue': revenue,
                                'cost_savings': cost_savings,
                                'customer_satisfaction': customer_satisfaction,
                                'brand_value': brand_value,
                                'efficiency_improvement': efficiency_improvement,
                                'risk_reduction': risk_reduction
                            }
                            
                            if update_project_review(selected_review['review_id'], review_data):
                                st.success(f"✅ 프로젝트 '{project_name}'이 성공적으로 수정되었습니다!")
                                
                                # 새 파일 저장
                                if uploaded_files:
                                    for uploaded_file in uploaded_files:
                                        file_data = parse_uploaded_file(uploaded_file)
                                        if file_data:
                                            if save_project_file(selected_review['review_id'], file_data):
                                                st.success(f"✅ 파일 '{uploaded_file.name}'이 추가되었습니다.")
                                            else:
                                                st.error(f"❌ 파일 '{uploaded_file.name}' 저장에 실패했습니다.")
                                
                                st.rerun()
                            else:
                                st.error("❌ 프로젝트 리뷰 수정에 실패했습니다.")
                    
                    if delete_submitted:
                        st.session_state['confirm_project_delete'] = selected_review['review_id']
                
                # 프로젝트 삭제 확인 (폼 외부)
                if 'confirm_project_delete' in st.session_state:
                    st.warning("⚠️ 프로젝트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ 정말 삭제하기", key="confirm_delete"):
                            review_id = st.session_state['confirm_project_delete']
                            if delete_project_review(review_id):
                                st.success(f"✅ 프로젝트가 삭제되었습니다.")
                                del st.session_state['confirm_project_delete']
                                st.rerun()
                            else:
                                st.error("❌ 프로젝트 삭제에 실패했습니다.")
                    
                    with col2:
                        if st.button("❌ 취소", key="cancel_delete"):
                            del st.session_state['confirm_project_delete']
                            st.rerun()
    
    with tab4:
        st.header("AI 분석")
        
        # 분석할 프로젝트 선택
        reviews = get_project_reviews()
        
        if not reviews:
            st.info("분석할 프로젝트가 없습니다. 먼저 프로젝트를 등록해주세요.")
            return
        
        selected_review = st.selectbox(
            "분석할 프로젝트 선택",
            reviews,
            format_func=lambda x: f"{x['project_name']} ({x['created_at'].strftime('%Y-%m-%d')})"
        )
        
        if selected_review:
            # 프로젝트 정보 표시
            with st.expander("선택된 프로젝트 정보", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**프로젝트명:** {selected_review['project_name']}")
                    st.write(f"**유형:** {selected_review['project_type']}")
                    st.write(f"**매니저:** {selected_review['project_manager']}")
                    st.write(f"**상태:** {selected_review['status']}")
                    st.write(f"**평점:** {selected_review['overall_rating']}/10")
                
                with col2:
                    st.write(f"**기간:** {selected_review['start_date']} ~ {selected_review['end_date']}")
                    st.write(f"**예산:** {selected_review['budget']:,}원")
                    st.write(f"**실제 비용:** {selected_review['actual_cost']:,}원")
                
                # 가치 지표 표시
                value_type = selected_review.get('value_type', '매출 창출')
                st.markdown("---")
                st.markdown(f"**💰 가치 측정 방식:** {value_type}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if selected_review.get('revenue', 0) > 0:
                        st.write(f"**매출액:** {selected_review['revenue']:,}원")
                        # 매출 기반 ROI 계산
                        if selected_review['actual_cost'] and selected_review['actual_cost'] > 0:
                            roi = ((selected_review['revenue'] - selected_review['actual_cost']) / selected_review['actual_cost']) * 100
                            color = "🟢" if roi > 0 else "🔴" if roi < 0 else "🟡"
                            st.write(f"**매출 ROI:** {color} {roi:+.1f}%")
                    
                    if selected_review.get('cost_savings', 0) > 0:
                        st.write(f"**비용 절약액:** {selected_review['cost_savings']:,}원")
                        # 비용 절약 기반 ROI 계산
                        if selected_review['actual_cost'] and selected_review['actual_cost'] > 0:
                            savings_roi = (selected_review['cost_savings'] / selected_review['actual_cost']) * 100
                            st.write(f"**절약 ROI:** 🟢 {savings_roi:.1f}%")
                
                with col2:
                    # 정성적 가치 지표 표시
                    qualitative_metrics = [
                        ('customer_satisfaction', '고객 만족도'),
                        ('brand_value', '브랜드 가치'),
                        ('efficiency_improvement', '업무 효율성'),
                        ('risk_reduction', '리스크 감소')
                    ]
                    
                    has_qualitative = any(selected_review.get(key, 0) > 0 for key, _ in qualitative_metrics)
                    
                    if has_qualitative:
                        st.markdown("**📊 정성적 가치 지표:**")
                        for key, label in qualitative_metrics:
                            score = selected_review.get(key, 0)
                            if score > 0:
                                stars = "⭐" * score
                                st.write(f"{label}: {stars} ({score}/10)")
                    else:
                        st.write("정성적 가치 지표: 없음")
            
            # 첨부 파일 정보
            project_files = get_project_files(selected_review['review_id'])
            if project_files:
                with st.expander("📄 첨부된 파일 목록 (AI 분석에 활용됨)", expanded=True):
                    st.info("💡 **RAG 분석**: 아래 첨부 파일들의 내용이 AI 분석에 자동으로 포함되어 더 정확하고 구체적인 분석 결과를 제공합니다.")
                    
                    for file in project_files:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.write(f"📄 **{file['filename']}** ({file['file_type'].upper()})")
                            st.caption(f"크기: {file['file_size']:,} bytes | 업로드: {file['uploaded_at'].strftime('%Y-%m-%d %H:%M')}")
                        
                        with col2:
                            # 파일 타입별 AI 분석 활용도 표시
                            if file['filename'].lower().endswith(('.pdf', '.docx', '.doc', '.txt', '.md')):
                                st.success("📖 문서 (최대 3000자)")
                            elif file['filename'].lower().endswith(('.xlsx', '.xls', '.csv')):
                                st.success("📊 데이터 (최대 2000자)")
                            elif file['filename'].lower().endswith('.json'):
                                st.success("🔧 JSON (최대 1500자)")
                            else:
                                st.info("📁 기타 (최대 1000자)")
                    
                    st.markdown("---")
                    st.markdown("**🔍 AI가 파일에서 분석하는 내용:**")
                    st.markdown("""
                    - 📊 **구체적인 성과 지표**: 문서에 기록된 수치, 데이터, KPI
                    - ⚠️ **실제 이슈와 문제점**: 프로젝트 진행 중 발생한 구체적 문제들
                    - 📈 **정량적 분석 데이터**: 측정 가능한 성과와 결과
                    - 💡 **교훈과 개선사항**: 문서에 기록된 경험과 제안사항
                    - 🔗 **프로젝트 정보와의 일치성**: 입력된 기본 정보와 문서 내용 비교
                    """)
            else:
                st.info("📄 첨부된 파일이 없습니다. 파일을 첨부하면 AI가 문서 내용을 분석하여 더 정확한 결과를 제공합니다.")
                st.caption("💡 프로젝트 수정 탭에서 관련 문서를 추가할 수 있습니다.")
            
            # AI 분석 설정
            st.subheader("🔧 분석 설정")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                analysis_instructions = st.text_area(
                    "추가 분석 지침",
                    placeholder="특별히 분석하고 싶은 관점이나 주의사항을 입력하세요",
                    height=100
                )
            
            with col2:
                st.markdown("**🤖 이번 분석에 사용될 전문가:**")
                selected_agents = []
                for agent, is_active in active_agents.items():
                    if is_active:
                        agent_names_current = {
                            'project_manager_agent': '📋 프로젝트 관리',
                            'technical_agent': '⚙️ 기술',
                            'business_agent': '💼 비즈니스',
                            'quality_agent': '🎯 품질',
                            'risk_agent': '⚠️ 리스크',
                            'team_agent': '👥 팀 성과',
                            'financial_agent': '💰 재무',
                            'integration_agent': '🔗 종합 평가'
                        }
                        if agent == 'integration_agent':
                            st.write(f"✅ {agent_names_current.get(agent, agent)} (자동)")
                        else:
                            st.write(f"✅ {agent_names_current.get(agent, agent)}")
                        selected_agents.append(agent)
                
                individual_agents_selected = [a for a in selected_agents if a != 'integration_agent']
                if not individual_agents_selected:
                    st.error("❌ 최소 1개의 개별 전문가를 선택해주세요")
                    st.caption("💡 사이드바에서 기본 설정을 변경하거나, 아래 '전문가 조합 변경'을 사용하세요")
                else:
                    total_selected = len(selected_agents)
                    individual_selected = len(individual_agents_selected)
                    st.caption(f"📊 총 {total_selected}명 (개별 {individual_selected}명 + 종합 1명)")
            
            # 이 분석만을 위한 에이전트 재선택 옵션
            with st.expander("🔧 이번 분석만을 위한 전문가 조합 변경 (선택사항)", expanded=False):
                st.markdown("#### 💡 언제 사용하나요?")
                st.markdown("""
                - **특정 관점 집중**: 이번 프로젝트는 기술적 측면만 중점 분석하고 싶을 때
                - **빠른 분석**: 시간이 부족해서 핵심 전문가만 선택하고 싶을 때  
                - **실험적 분석**: 다른 조합으로 어떤 결과가 나오는지 테스트해보고 싶을 때
                """)
                
                st.markdown("#### 🎯 이번 분석용 전문가 선택")
                st.caption("⚠️ 아래에서 선택하면 사이드바 기본 설정을 무시하고 이 조합으로 분석합니다")
                
                # 빠른 프리셋 버튼들
                st.markdown("**빠른 선택:**")
                preset_cols = st.columns(4)
                
                with preset_cols[0]:
                    if st.button("🎯 핵심만", key="quick_core"):
                        st.session_state.update({
                            'custom_pm_agent': True, 'custom_tech_agent': True,
                            'custom_biz_agent': True, 'custom_financial_agent': True,
                            'custom_quality_agent': False, 'custom_risk_agent': False, 'custom_team_agent': False
                        })
                        st.rerun()
                
                with preset_cols[1]:
                    if st.button("⚙️ 기술 중심", key="quick_tech"):
                        st.session_state.update({
                            'custom_pm_agent': False, 'custom_tech_agent': True,
                            'custom_biz_agent': False, 'custom_financial_agent': False,
                            'custom_quality_agent': True, 'custom_risk_agent': True, 'custom_team_agent': False
                        })
                        st.rerun()
                
                with preset_cols[2]:
                    if st.button("💼 비즈니스", key="quick_biz"):
                        st.session_state.update({
                            'custom_pm_agent': True, 'custom_tech_agent': False,
                            'custom_biz_agent': True, 'custom_financial_agent': True,
                            'custom_quality_agent': False, 'custom_risk_agent': True, 'custom_team_agent': True
                        })
                        st.rerun()
                
                with preset_cols[3]:
                    if st.button("🔄 초기화", key="quick_reset"):
                        for key in ['custom_pm_agent', 'custom_tech_agent', 'custom_biz_agent', 
                                   'custom_quality_agent', 'custom_risk_agent', 'custom_team_agent', 'custom_financial_agent']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                
                st.markdown("---")
                
                custom_agents = {}
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    custom_agents['project_manager_agent'] = st.checkbox(
                        "📋 프로젝트 관리", 
                        key="custom_pm_agent",
                        help="일정, 예산, 리소스 관리"
                    )
                    custom_agents['technical_agent'] = st.checkbox(
                        "⚙️ 기술", 
                        key="custom_tech_agent",
                        help="기술 아키텍처, 성능"
                    )
                    custom_agents['business_agent'] = st.checkbox(
                        "💼 비즈니스", 
                        key="custom_biz_agent",
                        help="시장 영향도, 고객 만족도"
                    )
                
                with col2:
                    custom_agents['quality_agent'] = st.checkbox(
                        "🎯 품질", 
                        key="custom_quality_agent",
                        help="품질 메트릭스, UX"
                    )
                    custom_agents['risk_agent'] = st.checkbox(
                        "⚠️ 리스크", 
                        key="custom_risk_agent",
                        help="위험 식별, 대응"
                    )
                    custom_agents['team_agent'] = st.checkbox(
                        "👥 팀 성과", 
                        key="custom_team_agent",
                        help="팀 생산성, 협업"
                    )
                
                with col3:
                    custom_agents['financial_agent'] = st.checkbox(
                        "💰 재무", 
                        key="custom_financial_agent",
                        help="ROI, NPV/IRR, 재무 성과"
                    )
                
                # 커스텀 에이전트가 선택되었으면 그것을 사용 (종합 평가는 항상 포함)
                if any(custom_agents.values()):
                    active_agents = custom_agents
                    active_agents['integration_agent'] = True  # 종합 평가는 항상 포함
                    individual_count = sum(custom_agents.values())
                    st.success(f"✅ 이번 분석용 조합: {individual_count}개 개별 전문가 + 1개 종합 평가 = 총 {individual_count + 1}개")
                    st.caption("💡 이 설정은 이번 분석에만 적용되며, 사이드바 기본 설정은 유지됩니다")
                else:
                    st.info("📋 현재 사이드바의 기본 설정을 사용합니다")
            
            # API 상태 및 사용 팁 표시
            with st.expander("💡 AI 분석 사용 팁 I", expanded=False):
                st.markdown("""
                **분석 시간 안내:**
                - 각 전문가당 약 30초~2분 소요
                - 여러 전문가 선택 시 순차적으로 진행
                - API 서버 상태에 따라 시간이 달라질 수 있음
                
                **오류 발생 시:**
                - 자동으로 최대 3번 재시도
                - 과부하 오류 시 대기 후 재시도
                - 일부 전문가만 실패해도 성공한 분석 결과는 저장됨
                
                **권장사항:**
                - 처음에는 2-3명의 전문가로 시작
                - 오류 발생 시 잠시 후 다시 시도
                - 중요한 분석은 여러 번 나누어 실행
                """)
            
            # API 상태 및 사용 팁 표시
            with st.expander("💡 AI 분석 사용 팁 II", expanded=False):
                st.markdown("""
                **📄 RAG 분석 활용:**
                - 첨부 파일의 내용이 자동으로 AI 분석에 포함됩니다
                - 문서 파일(PDF, DOCX)은 최대 3000자까지 분석
                - 데이터 파일(Excel, CSV)은 최대 2000자까지 분석
                - AI가 문서의 구체적 데이터를 인용하여 분석 근거를 제시합니다
                - 프로젝트 기본 정보와 첨부 문서 간의 일치성도 검토합니다
                
                **분석 시간 안내:**
                - 각 전문가당 약 30초~2분 소요
                - 여러 전문가 선택 시 순차적으로 진행
                - API 서버 상태에 따라 시간이 달라질 수 있음
                - 첨부 파일이 많을수록 분석 시간이 약간 증가할 수 있음
                
                **오류 발생 시:**
                - 자동으로 최대 3번 재시도
                - 과부하 오류 시 대기 후 재시도
                - 일부 전문가만 실패해도 성공한 분석 결과는 저장됨
                
                **권장사항:**
                - 처음에는 2-3명의 전문가로 시작
                - 오류 발생 시 잠시 후 다시 시도
                - 중요한 분석은 여러 번 나누어 실행
                - 관련 문서를 미리 첨부하면 더 정확한 분석 가능
                """)
            
            if st.button("🤖 AI 분석 시작", type="primary"):
                # 선택된 에이전트가 있는지 확인
                selected_agents_for_analysis = [agent for agent, is_active in active_agents.items() if is_active]
                individual_agents_for_analysis = [agent for agent in selected_agents_for_analysis if agent != 'integration_agent']
                
                if not individual_agents_for_analysis:
                    st.error("❌ 분석을 수행할 개별 AI 전문가를 최소 1명 이상 선택해주세요!")
                    st.info("💡 사이드바에서 AI 에이전트를 선택하거나, 위의 '이번 분석만을 위한 에이전트 선택'에서 선택하세요.")
                else:
                    # 분석 시작 전 확인 메시지
                    total_agents = len(selected_agents_for_analysis)
                    individual_count = len(individual_agents_for_analysis)
                    st.info(f"🚀 {individual_count}명의 개별 전문가 + 1명의 종합 평가 전문가 = 총 {total_agents}명이 분석을 시작합니다.")
                    st.info(f"⏱️ 예상 소요 시간: {total_agents * 1}~{total_agents * 2}분 (개별 분석 후 종합 평가 순서로 진행)")
                    with st.spinner(f"🤖 {total_agents}명의 AI 전문가가 프로젝트를 분석중입니다..."):
                        # 파일 내용 준비
                        files_content = []
                        for file in project_files:
                            files_content.append({
                                'filename': file['filename'],
                                'content': file['file_content']
                            })
                        
                        # 분석 지침 추가
                        if analysis_instructions:
                            selected_review['additional_instructions'] = analysis_instructions
                        
                                                # 각 에이전트별 분석 수행
                        analysis_results = {}
                        failed_agents = []
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        total_agents = len(selected_agents_for_analysis)
                        completed_agents = 0
                        
                        agent_names = {
                            'project_manager_agent': '📋 프로젝트 관리 전문가',
                            'technical_agent': '⚙️ 기술 전문가',
                            'business_agent': '💼 비즈니스 전문가',
                            'quality_agent': '🎯 품질 전문가',
                            'risk_agent': '⚠️ 리스크 전문가',
                            'team_agent': '👥 팀 성과 전문가',
                            'financial_agent': '💰 재무 전문가',
                            'integration_agent': '🔗 종합 평가 전문가'
                        }
                        
                        # 1단계: 개별 전문가 분석 (종합 평가 제외)
                        individual_agents = {k: v for k, v in active_agents.items() if k != 'integration_agent' and v}
                        individual_analysis_results = {}
                        
                        for i, (agent_type, is_active) in enumerate(individual_agents.items()):
                            if not is_active:
                                continue
                            
                            # 진행 상황 업데이트
                            progress = completed_agents / total_agents
                            progress_bar.progress(progress)
                            
                            agent_name = agent_names.get(agent_type, agent_type)
                            status_text.write(f"🔄 {agent_name} 분석 중... ({completed_agents + 1}/{total_agents})")
                            
                            analysis_result = analyze_with_ai(
                                selected_review,
                                files_content,
                                agent_type,
                                selected_model
                            )
                            
                            if analysis_result:
                                # 차트 품질 검증 (디버그 모드에서만)
                                if st.session_state.get('debug_mode', False):
                                    chart_validation = validate_mermaid_chart(analysis_result['analysis'])
                                    if chart_validation['has_chart']:
                                        if chart_validation['is_valid']:
                                            st.success(f"✅ {agent_name}: Mermaid 차트가 올바르게 생성되었습니다")
                                        else:
                                            st.warning(f"⚠️ {agent_name}: Mermaid 차트에 문제가 있습니다 - {chart_validation['issues']}")
                                    else:
                                        st.info(f"ℹ️ {agent_name}: Mermaid 차트가 생성되지 않았습니다")
                                
                                individual_analysis_results[agent_type] = analysis_result
                                analysis_results[agent_type] = analysis_result
                                
                                # DB에 저장
                                save_success = save_ai_analysis(
                                    selected_review['review_id'],
                                    agent_type,
                                    selected_model,
                                    analysis_result['analysis'],
                                    analysis_result['recommendations'],
                                    analysis_result['risk_assessment'],
                                    analysis_result['score']
                                )
                                
                                if save_success:
                                    status_text.write(f"✅ {agent_name} 분석 완료 및 DB 저장!")
                                else:
                                    status_text.write(f"⚠️ {agent_name} 분석 완료 (DB 저장 실패)")
                            else:
                                failed_agents.append(agent_name)
                                status_text.write(f"❌ {agent_name} 분석 실패")
                            
                            completed_agents += 1
                        
                        # 2단계: 종합 평가 전문가 분석 (개별 전문가 결과가 있는 경우에만)
                        if individual_analysis_results and active_agents.get('integration_agent', False):
                            # 진행 상황 업데이트
                            progress = completed_agents / total_agents
                            progress_bar.progress(progress)
                            
                            status_text.write(f"🔄 🔗 종합 평가 전문가 분석 중... ({completed_agents + 1}/{total_agents})")
                            
                            integration_result = analyze_with_integration_ai(
                                selected_review,
                                files_content,
                                individual_analysis_results,
                                selected_model
                            )
                            
                            if integration_result:
                                analysis_results['integration_agent'] = integration_result
                                
                                # DB에 저장
                                save_success = save_ai_analysis(
                                    selected_review['review_id'],
                                    'integration_agent',
                                    selected_model,
                                    integration_result['analysis'],
                                    integration_result['recommendations'],
                                    integration_result['risk_assessment'],
                                    integration_result['score']
                                )
                                
                                if save_success:
                                    status_text.write(f"✅ 🔗 종합 평가 전문가 분석 완료 및 DB 저장!")
                                else:
                                    status_text.write(f"⚠️ 🔗 종합 평가 전문가 분석 완료 (DB 저장 실패)")
                            else:
                                failed_agents.append("🔗 종합 평가 전문가")
                                status_text.write(f"❌ 🔗 종합 평가 전문가 분석 실패")
                            
                            completed_agents += 1
                        
                        # 최종 진행률 업데이트
                        progress_bar.progress(1.0)
                        
                        # 결과 요약 메시지
                        success_count = len(analysis_results)
                        fail_count = len(failed_agents)
                        
                        if success_count == total_agents:
                            status_text.write(f"🎉 모든 분석이 성공적으로 완료되었습니다! ({success_count}/{total_agents})")
                            st.success("✅ AI 분석이 완료되었습니다!")
                        elif success_count > 0:
                            status_text.write(f"⚠️ 일부 분석이 완료되었습니다. 성공: {success_count}, 실패: {fail_count}")
                            st.warning(f"⚠️ {success_count}개의 분석이 완료되었습니다. {fail_count}개의 분석이 실패했습니다.")
                            if failed_agents:
                                st.error(f"실패한 전문가: {', '.join(failed_agents)}")
                                st.info("💡 실패한 분석은 잠시 후 다시 시도해보세요. API 서버 상태가 개선될 수 있습니다.")
                        else:
                            status_text.write(f"❌ 모든 분석이 실패했습니다. ({fail_count}/{total_agents})")
                            st.error("❌ 모든 AI 분석이 실패했습니다. 잠시 후 다시 시도해주세요.")
                            st.info("💡 API 서버가 일시적으로 과부하 상태일 수 있습니다. 몇 분 후 다시 시도해보세요.")
                        
                        # 실패한 에이전트 재시도 옵션
                        if failed_agents:
                            st.subheader("🔄 실패한 분석 재시도")
                            st.write("실패한 전문가들을 개별적으로 다시 시도할 수 있습니다:")
                            
                            retry_cols = st.columns(min(len(failed_agents), 3))
                            for idx, failed_agent in enumerate(failed_agents):
                                col_idx = idx % 3
                                with retry_cols[col_idx]:
                                    if st.button(f"🔄 {failed_agent} 재시도", key=f"retry_{failed_agent}_{idx}"):
                                        # 실패한 에이전트의 타입 찾기
                                        failed_agent_type = None
                                        for agent_type, agent_name in agent_names.items():
                                            if agent_name == failed_agent:
                                                failed_agent_type = agent_type
                                                break
                                        
                                        if failed_agent_type:
                                            with st.spinner(f"🔄 {failed_agent} 재분석 중..."):
                                                retry_result = analyze_with_ai(
                                                    selected_review,
                                                    files_content,
                                                    failed_agent_type,
                                                    selected_model
                                                )
                                                
                                                if retry_result:
                                                    analysis_results[failed_agent_type] = retry_result
                                                    
                                                    # DB에 저장
                                                    save_success = save_ai_analysis(
                                                        selected_review['review_id'],
                                                        failed_agent_type,
                                                        selected_model,
                                                        retry_result['analysis'],
                                                        retry_result['recommendations'],
                                                        retry_result['risk_assessment'],
                                                        retry_result['score']
                                                    )
                                                    
                                                    if save_success:
                                                        st.success(f"✅ {failed_agent} 재분석 성공!")
                                                        st.rerun()
                                                    else:
                                                        st.warning(f"⚠️ {failed_agent} 분석은 성공했지만 DB 저장에 실패했습니다.")
                                                else:
                                                    st.error(f"❌ {failed_agent} 재분석도 실패했습니다.")
                        
                        # 분석 결과 표시
                        if analysis_results:
                            st.subheader("🎯 AI 분석 결과")
                            
                            # 전체 점수 요약
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                avg_score = sum([result['score'] for result in analysis_results.values()]) / len(analysis_results)
                                st.metric("평균 점수", f"{avg_score:.1f}/10")
                            
                            with col2:
                                max_score = max([result['score'] for result in analysis_results.values()])
                                max_agent = [agent for agent, result in analysis_results.items() if result['score'] == max_score][0]
                                agent_names_display = {
                                    'project_manager_agent': '프로젝트 관리',
                                    'technical_agent': '기술',
                                    'business_agent': '비즈니스',
                                    'quality_agent': '품질',
                                    'risk_agent': '리스크',
                                    'team_agent': '팀 성과',
                                    'financial_agent': '재무',
                                    'integration_agent': '종합 평가'
                                }
                                st.metric("최고 점수", f"{max_score}/10", f"{agent_names_display.get(max_agent, max_agent)}")
                            
                            with col3:
                                min_score = min([result['score'] for result in analysis_results.values()])
                                min_agent = [agent for agent, result in analysis_results.items() if result['score'] == min_score][0]
                                st.metric("최저 점수", f"{min_score}/10", f"{agent_names_display.get(min_agent, min_agent)}")
                            
                            # 종합 평가를 맨 앞에 표시하도록 정렬
                            sorted_agents = []
                            if 'integration_agent' in analysis_results:
                                sorted_agents.append('integration_agent')
                            sorted_agents.extend([k for k in analysis_results.keys() if k != 'integration_agent'])
                            
                            # 에이전트별 탭 생성
                            agent_tabs = st.tabs([
                                f"{agent_names_display.get(agent_type, agent_type)} ({analysis_results[agent_type]['score']}/10)"
                                for agent_type in sorted_agents
                            ])
                            
                            for tab, agent_type in zip(agent_tabs, sorted_agents):
                                result = analysis_results[agent_type]
                                with tab:
                                    if agent_type == 'integration_agent':
                                        st.markdown(f"### 🔗 종합 평가 분석")
                                        st.markdown(f"**종합 점수:** {result['score']}/10")
                                        st.info("💡 이 분석은 모든 개별 전문가들의 의견을 종합하여 통합적 관점에서 평가한 결과입니다.")
                                    else:
                                        st.markdown(f"### {agent_type.replace('_', ' ').title()} 분석")
                                        st.markdown(f"**점수:** {result['score']}/10")
                                    
                                    # 디버그 모드에서 차트 품질 정보 표시
                                    if st.session_state.get('debug_mode', False):
                                        chart_validation = validate_mermaid_chart(result['analysis'])
                                        if chart_validation['has_chart']:
                                            if chart_validation['is_valid']:
                                                st.success(f"✅ 차트 품질: 우수 (노드: {chart_validation['nodes_count']}, 엣지: {chart_validation['edges_count']})")
                                            else:
                                                st.warning(f"⚠️ 차트 품질 문제: {', '.join(chart_validation['issues'])}")
                                                with st.expander("차트 원본 코드"):
                                                    st.code(chart_validation['chart_code'], language="mermaid")
                                        else:
                                            st.error("❌ Mermaid 차트를 찾을 수 없습니다")
                                    
                                    display_mermaid_chart(result['analysis'])
                                    
                                    with st.expander("추천사항"):
                                        display_mermaid_chart(result['recommendations'])
                                    
                                    with st.expander("위험평가"):
                                        display_mermaid_chart(result['risk_assessment'])
        
        # 기존 분석 결과 조회
        st.subheader("📊 기존 분석 결과")
        
        if selected_review:
            existing_analyses = get_ai_analysis(selected_review['review_id'])
            
            if existing_analyses:
                # 삭제 버튼과 분석 개수 표시
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.info(f"💡 총 **{len(existing_analyses)}개**의 AI 분석 결과가 있습니다.")
                
                with col2:
                    if st.button("🗑️ 전체 삭제", key="delete_all_analyses", type="secondary"):
                        st.session_state['confirm_delete_analyses'] = True
                
                # 삭제 확인 다이얼로그
                if st.session_state.get('confirm_delete_analyses', False):
                    st.warning("⚠️ **주의**: 이 프로젝트의 모든 AI 분석 결과를 삭제하시겠습니까?")
                    st.markdown("- 삭제된 분석 결과는 복구할 수 없습니다")
                    st.markdown("- 필요시 다시 AI 분석을 실행해야 합니다")
                    
                    col_confirm, col_cancel = st.columns(2)
                    
                    with col_confirm:
                        if st.button("🗑️ 정말 삭제하기", key="btn_confirm_delete_analyses", type="primary"):
                            deleted_count = delete_ai_analysis(selected_review['review_id'])
                            if deleted_count:
                                st.success(f"✅ {deleted_count}개의 AI 분석 결과가 삭제되었습니다.")
                                del st.session_state['confirm_delete_analyses']
                                st.rerun()
                            else:
                                st.error("❌ AI 분석 결과 삭제에 실패했습니다.")
                    
                    with col_cancel:
                        if st.button("❌ 취소", key="btn_cancel_delete_analyses"):
                            del st.session_state['confirm_delete_analyses']
                            st.rerun()
                
                # 분석 결과를 에이전트별로 그룹화
                analyses_by_agent = {}
                for analysis in existing_analyses:
                    agent_type = analysis['agent_type']
                    if agent_type not in analyses_by_agent:
                        analyses_by_agent[agent_type] = []
                    analyses_by_agent[agent_type].append(analysis)
                
                # 에이전트별 탭 생성
                if analyses_by_agent:
                    # 종합 평가를 맨 앞에 표시하도록 정렬
                    sorted_agent_types = []
                    if 'integration_agent' in analyses_by_agent:
                        sorted_agent_types.append('integration_agent')
                    sorted_agent_types.extend([k for k in analyses_by_agent.keys() if k != 'integration_agent'])
                    
                    agent_names_display = {
                        'project_manager_agent': '📋 프로젝트 관리',
                        'technical_agent': '⚙️ 기술',
                        'business_agent': '💼 비즈니스',
                        'quality_agent': '🎯 품질',
                        'risk_agent': '⚠️ 리스크',
                        'team_agent': '👥 팀 성과',
                        'financial_agent': '💰 재무',
                        'integration_agent': '🔗 종합 평가'
                    }
                    
                    agent_tabs = st.tabs([
                        f"{agent_names_display.get(agent_type, agent_type)} ({len(analyses_by_agent[agent_type])}개)"
                        for agent_type in sorted_agent_types
                    ])
                    
                    for tab, agent_type in zip(agent_tabs, sorted_agent_types):
                        agent_analyses = analyses_by_agent[agent_type]
                        with tab:
                            for analysis in agent_analyses:
                                with st.expander(f"{analysis['created_at'].strftime('%Y-%m-%d %H:%M')} - {analysis['model_name']} (점수: {analysis['score']}/10)"):
                                    # 디버그 모드에서 차트 품질 정보 표시
                                    if st.session_state.get('debug_mode', False):
                                        chart_validation = validate_mermaid_chart(analysis['analysis_content'])
                                        if chart_validation['has_chart']:
                                            if chart_validation['is_valid']:
                                                st.success(f"✅ 차트 품질: 우수 (노드: {chart_validation['nodes_count']}, 엣지: {chart_validation['edges_count']})")
                                            else:
                                                st.warning(f"⚠️ 차트 품질 문제: {', '.join(chart_validation['issues'])}")
                                                with st.expander("차트 원본 코드", expanded=False):
                                                    st.code(chart_validation['chart_code'], language="mermaid")
                                        else:
                                            st.error("❌ Mermaid 차트를 찾을 수 없습니다")
                                    
                                    display_mermaid_chart(analysis['analysis_content'])
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.markdown("**추천사항:**")
                                        display_mermaid_chart(analysis['recommendations'])
                                    
                                    with col2:
                                        st.markdown("**위험평가:**")
                                        display_mermaid_chart(analysis['risk_assessment'])
            else:
                st.info("📄 첨부된 파일이 없습니다. 파일을 첨부하면 AI가 문서 내용을 분석하여 더 정확한 결과를 제공합니다.")
                st.caption("💡 프로젝트 수정 탭에서 관련 문서를 추가할 수 있습니다.")
    
    with tab5:
        st.header("프로젝트 목록")
        
        reviews = get_project_reviews()
        
        if reviews:
            st.info(f"📋 총 **{len(reviews)}개**의 프로젝트가 등록되어 있습니다.")
            
            # 정렬 및 필터링 옵션
            col1, col2, col3 = st.columns(3)
            
            with col1:
                sort_by = st.selectbox(
                    "정렬 기준",
                    ["최신순", "이름순", "예산순", "매출순", "평점순", "상태순"],
                    key="project_list_sort"
                )
            
            with col2:
                status_filter = st.selectbox(
                    "상태 필터",
                    ["전체", "completed", "ongoing", "cancelled", "on_hold"],
                    key="project_list_status"
                )
            
            with col3:
                type_filter = st.selectbox(
                    "유형 필터",
                    ["전체"] + list(set([review['project_type'] for review in reviews])),
                    key="project_list_type"
                )
            
            # 필터링
            filtered_reviews = reviews
            if status_filter != "전체":
                filtered_reviews = [r for r in filtered_reviews if r['status'] == status_filter]
            if type_filter != "전체":
                filtered_reviews = [r for r in filtered_reviews if r['project_type'] == type_filter]
            
            # 정렬
            if sort_by == "최신순":
                filtered_reviews.sort(key=lambda x: x['created_at'], reverse=True)
            elif sort_by == "이름순":
                filtered_reviews.sort(key=lambda x: x['project_name'])
            elif sort_by == "예산순":
                filtered_reviews.sort(key=lambda x: x['budget'], reverse=True)
            elif sort_by == "매출순":
                filtered_reviews.sort(key=lambda x: x.get('revenue', 0), reverse=True)
            elif sort_by == "평점순":
                filtered_reviews.sort(key=lambda x: x['overall_rating'], reverse=True)
            elif sort_by == "상태순":
                filtered_reviews.sort(key=lambda x: x['status'])
            
            st.markdown(f"**필터 결과:** {len(filtered_reviews)}개 프로젝트")
            
            # 프로젝트 카드 표시
            for i, review in enumerate(filtered_reviews):
                with st.container():
                    # 상태에 따른 색상 및 아이콘
                    status_info = {
                        'completed': ('🟢', '완료'),
                        'ongoing': ('🟡', '진행중'),
                        'cancelled': ('🔴', '취소'),
                        'on_hold': ('🟠', '보류')
                    }
                    
                    status_icon, status_text = status_info.get(review['status'], ('⚪', review['status']))
                    
                    # 프로젝트 헤더
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"### {review['project_name']}")
                        st.markdown(f"**유형:** {review['project_type']} | **매니저:** {review['project_manager']}")
                    
                    with col2:
                        st.markdown(f"**상태**")
                        st.markdown(f"{status_icon} {status_text}")
                    
                    with col3:
                        st.markdown(f"**평점**")
                        stars = "⭐" * review['overall_rating']
                        st.markdown(f"{stars} ({review['overall_rating']}/10)")
                    
                    # 프로젝트 상세 정보
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📅 프로젝트 기간**")
                        st.write(f"{review['start_date']} ~ {review['end_date']}")
                        
                        st.markdown("**💰 예산 및 비용**")
                        st.write(f"예산: {review['budget']:,}원")
                        st.write(f"실제 비용: {review['actual_cost']:,}원")
                        
                        # 예산 대비 실제 비용 비율
                        if review['budget'] > 0:
                            cost_ratio = (review['actual_cost'] / review['budget']) * 100
                            if cost_ratio <= 100:
                                st.write(f"예산 대비: 🟢 {cost_ratio:.1f}%")
                            elif cost_ratio <= 120:
                                st.write(f"예산 대비: 🟡 {cost_ratio:.1f}%")
                            else:
                                st.write(f"예산 대비: 🔴 {cost_ratio:.1f}%")
                    
                    with col2:
                        # 가치 지표 표시
                        value_type = review.get('value_type', '매출 창출')
                        st.markdown(f"**💎 가치 측정: {value_type}**")
                        
                        # 매출 및 ROI
                        if review.get('revenue', 0) > 0:
                            st.write(f"매출액: {review['revenue']:,}원")
                            if review['actual_cost'] > 0:
                                roi = ((review['revenue'] - review['actual_cost']) / review['actual_cost']) * 100
                                color = "🟢" if roi > 0 else "🔴" if roi < 0 else "🟡"
                                st.write(f"매출 ROI: {color} {roi:+.1f}%")
                        
                        # 비용 절약
                        if review.get('cost_savings', 0) > 0:
                            st.write(f"비용 절약: {review['cost_savings']:,}원")
                            if review['actual_cost'] > 0:
                                savings_roi = (review['cost_savings'] / review['actual_cost']) * 100
                                st.write(f"절약 ROI: 🟢 {savings_roi:.1f}%")
                        
                        # 정성적 가치 지표
                        qualitative_scores = [
                            review.get('customer_satisfaction', 0),
                            review.get('brand_value', 0),
                            review.get('efficiency_improvement', 0),
                            review.get('risk_reduction', 0)
                        ]
                        
                        if any(score > 0 for score in qualitative_scores):
                            valid_scores = [s for s in qualitative_scores if s > 0]
                            avg_qualitative = sum(valid_scores) / len(valid_scores)
                            st.write(f"정성적 가치: ⭐ {avg_qualitative:.1f}/10")
                    
                    # 설명
                    if review.get('description'):
                        with st.expander("📝 프로젝트 설명"):
                            st.write(review['description'])
                    
                    # 팀원 정보
                    if review.get('team_members'):
                        st.markdown("**👥 팀원:** " + review['team_members'])
                    
                    # 구분선
                    if i < len(filtered_reviews) - 1:
                        st.markdown("---")
            
            # 엑셀/CSV 내보내기
            st.markdown("---")
            st.subheader("📊 데이터 내보내기")
            
            if filtered_reviews:
                # 데이터프레임으로 변환
                export_data = []
                for review in filtered_reviews:
                    export_row = {
                        '프로젝트명': review['project_name'],
                        '유형': review['project_type'],
                        '매니저': review['project_manager'],
                        '상태': review['status'],
                        '시작일': review['start_date'],
                        '종료일': review['end_date'],
                        '예산': review['budget'],
                        '실제비용': review['actual_cost'],
                        '평점': review['overall_rating'],
                        '가치측정방식': review.get('value_type', ''),
                        '매출액': review.get('revenue', 0),
                        '비용절약액': review.get('cost_savings', 0),
                        '고객만족도': review.get('customer_satisfaction', 0),
                        '브랜드가치': review.get('brand_value', 0),
                        '업무효율성': review.get('efficiency_improvement', 0),
                        '리스크감소': review.get('risk_reduction', 0),
                        '등록일': review['created_at'].strftime('%Y-%m-%d')
                    }
                    export_data.append(export_row)
                
                export_df = pd.DataFrame(export_data)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    csv_data = export_to_csv(export_df, "filtered_projects.csv")
                    st.download_button(
                        label="📄 CSV 다운로드",
                        data=csv_data,
                        file_name=f"프로젝트목록_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="project_list_csv_download"
                    )
                
                with col2:
                    excel_data = export_to_excel(export_df, "filtered_projects.xlsx")
                    st.download_button(
                        label="📊 Excel 다운로드",
                        data=excel_data,
                        file_name=f"프로젝트목록_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="project_list_excel_download"
                    )
        else:
            st.info("등록된 프로젝트가 없습니다.")
    
    with tab6:
        st.header("🔍 파일 검색 및 내용 조회")
        
        # 검색 상태 초기화
        if 'file_search_results' not in st.session_state:
            st.session_state.file_search_results = None
        if 'last_search_params' not in st.session_state:
            st.session_state.last_search_params = {}
        
        # 검색 옵션
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_term = st.text_input(
                "🔎 검색어 입력",
                placeholder="파일명, 내용, 프로젝트명으로 검색...",
                help="파일명, 파일 내용, 프로젝트명에서 검색합니다",
                key="file_search_term"
            )
        
        with col2:
            # 파일 타입 필터
            all_file_types = get_all_file_types()
            file_type_filter = st.selectbox(
                "📁 파일 타입",
                ["전체"] + all_file_types,
                key="file_search_type_filter"
            )
        
        with col3:
            # 검색 결과 정렬
            sort_option = st.selectbox(
                "🔄 정렬",
                ["최신순", "파일명순", "크기순", "프로젝트순"],
                key="file_search_sort"
            )
        
        # 고급 검색 옵션
        with st.expander("🎛️ 고급 검색 옵션", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # 파일 크기 필터
                st.markdown("**📏 파일 크기 필터**")
                size_filter = st.radio(
                    "크기 범위",
                    ["전체", "1MB 미만", "1MB-10MB", "10MB-50MB", "50MB 이상"],
                    horizontal=True,
                    key="file_size_filter"
                )
            
            with col2:
                # 업로드 날짜 필터
                st.markdown("**📅 업로드 날짜 필터**")
                date_filter = st.radio(
                    "기간",
                    ["전체", "오늘", "이번 주", "이번 달", "3개월 이내", "1년 이내"],
                    horizontal=True,
                    key="file_date_filter"
                )
        
        # 현재 검색 파라미터
        current_search_params = {
            'search_term': search_term,
            'file_type_filter': file_type_filter,
            'sort_option': sort_option,
            'size_filter': size_filter,
            'date_filter': date_filter
        }
        
        # 검색 파라미터가 변경되었는지 확인
        params_changed = st.session_state.last_search_params != current_search_params
        
        # 검색 실행
        search_executed = False
        if st.button("🔍 검색", type="primary", key="execute_file_search"):
            search_executed = True
        elif search_term and (params_changed or st.session_state.file_search_results is None):
            search_executed = True
        elif not search_term and st.session_state.last_search_params.get('search_term'):
            # 검색어가 삭제된 경우 결과 초기화
            st.session_state.file_search_results = None
            st.session_state.last_search_params = current_search_params
        
        # 검색 실행
        if search_executed:
            # 파일 검색 실행
            search_results = search_files(
                search_term=search_term if search_term else None,
                file_type=file_type_filter if file_type_filter != "전체" else None
            )
            
            # 파일 크기 필터 적용
            if size_filter != "전체":
                if size_filter == "1MB 미만":
                    search_results = [f for f in search_results if (f.get('file_size') or 0) < 1024*1024]
                elif size_filter == "1MB-10MB":
                    search_results = [f for f in search_results if 1024*1024 <= (f.get('file_size') or 0) < 10*1024*1024]
                elif size_filter == "10MB-50MB":
                    search_results = [f for f in search_results if 10*1024*1024 <= (f.get('file_size') or 0) < 50*1024*1024]
                elif size_filter == "50MB 이상":
                    search_results = [f for f in search_results if (f.get('file_size') or 0) >= 50*1024*1024]
            
            # 날짜 필터 적용
            if date_filter != "전체":
                now = datetime.now()
                if date_filter == "오늘":
                    cutoff_date = now - timedelta(days=1)
                elif date_filter == "이번 주":
                    cutoff_date = now - timedelta(weeks=1)
                elif date_filter == "이번 달":
                    cutoff_date = now - timedelta(days=30)
                elif date_filter == "3개월 이내":
                    cutoff_date = now - timedelta(days=90)
                elif date_filter == "1년 이내":
                    cutoff_date = now - timedelta(days=365)
                
                search_results = [f for f in search_results if f['uploaded_at'] >= cutoff_date]
            
            # 정렬 적용
            if sort_option == "최신순":
                search_results.sort(key=lambda x: x['uploaded_at'], reverse=True)
            elif sort_option == "파일명순":
                search_results.sort(key=lambda x: x['filename'])
            elif sort_option == "크기순":
                search_results.sort(key=lambda x: x.get('file_size', 0), reverse=True)
            elif sort_option == "프로젝트순":
                search_results.sort(key=lambda x: x['project_name'])
            
            # 검색 결과를 세션 스테이트에 저장
            st.session_state.file_search_results = search_results
            st.session_state.last_search_params = current_search_params
        
        # 저장된 검색 결과 사용
        search_results = st.session_state.file_search_results
        
        # 검색 결과 표시
        if search_results is not None:
            if search_results:
                # 검색 결과 통계
                total_files = len(search_results)
                total_size = sum([f.get('file_size', 0) for f in search_results])
                file_types_count = len(set([f['file_type'] for f in search_results]))
                projects_count = len(set([f['project_name'] for f in search_results]))
                
                st.markdown("---")
                st.markdown("### 📊 검색 결과 통계")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📄 총 파일 수", total_files)
                with col2:
                    st.metric("💾 총 용량", f"{total_size / (1024*1024):.1f} MB")
                with col3:
                    st.metric("📁 파일 형식", f"{file_types_count}종류")
                with col4:
                    st.metric("📋 프로젝트", f"{projects_count}개")
                
                # 파일 타입별 분포 차트
                if total_files > 0:
                    type_counts = {}
                    for file in search_results:
                        file_type = file['file_type']
                        type_counts[file_type] = type_counts.get(file_type, 0) + 1
                    
                    if len(type_counts) > 1:
                        fig = px.pie(
                            values=list(type_counts.values()),
                            names=list(type_counts.keys()),
                            title="📊 파일 타입별 분포"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                st.markdown(f"### 📋 검색 결과 ({total_files}개 파일)")
                
                # 검색 결과 표시
                for i, file in enumerate(search_results):
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            # 파일 아이콘
                            file_icons = {
                                'pdf': '📄', 'docx': '📝', 'doc': '📝', 'txt': '📄', 'md': '📄',
                                'xlsx': '📊', 'xls': '📊', 'csv': '📈',
                                'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
                                'zip': '🗜️', 'rar': '🗜️',
                                'json': '🔧', 'xml': '🔧', 'html': '🌐'
                            }
                            icon = file_icons.get(file['file_type'].lower(), '📁')
                            
                            st.markdown(f"**{icon} {file['filename']}**")
                            st.markdown(f"📋 프로젝트: {file['project_name']} | 📂 유형: {file['project_type']}")
                            
                            # 파일 크기와 업로드 날짜
                            file_size_mb = (file.get('file_size', 0)) / (1024*1024)
                            upload_date = file['uploaded_at'].strftime('%Y-%m-%d %H:%M')
                            st.caption(f"💾 크기: {file_size_mb:.2f}MB | 📅 업로드: {upload_date}")
                        
                        with col2:
                            # 파일 타입과 작성자
                            st.markdown(f"**파일 형식**")
                            st.write(f"📁 {file['file_type'].upper()}")
                            if file.get('created_by'):
                                st.caption(f"✍️ {file['created_by']}")
                        
                        with col3:
                            # 액션 버튼들
                            col_download, col_preview = st.columns(2)
                            
                            with col_download:
                                # 다운로드 버튼
                                file_binary = get_file_binary_data(file['file_id'])
                                if file_binary and file_binary.get('binary_data'):
                                    st.download_button(
                                        label="⬇️",
                                        data=file_binary['binary_data'],
                                        file_name=file['filename'],
                                        mime=get_file_mime_type(file['file_type']),
                                        key=f"download_search_{file['file_id']}",
                                        help="다운로드"
                                    )
                                else:
                                    st.button("⬇️", disabled=True, key=f"download_disabled_{file['file_id']}", help="다운로드 불가")
                            
                            with col_preview:
                                # 미리보기 버튼
                                preview_key = f"show_search_preview_{file['file_id']}"
                                is_showing = st.session_state.get(preview_key, False)
                                
                                if st.button("👁️" if not is_showing else "🙈", key=f"preview_search_{file['file_id']}", help="미리보기" if not is_showing else "숨기기"):
                                    st.session_state[preview_key] = not is_showing
                                    st.rerun()
                        
                        # 파일 내용 미리보기 (접힌 상태로)
                        if file.get('file_content'):
                            with st.expander("📄 추출된 텍스트 내용", expanded=False):
                                content = file['file_content']
                                if content.startswith('[') and content.endswith(']'):
                                    st.info(content)
                                elif len(content) > 1000:
                                    st.text_area(
                                        "내용 미리보기 (처음 1000자)",
                                        value=content[:1000] + "\n\n... (더 많은 내용이 있습니다)",
                                        height=200,
                                        disabled=True,
                                        key=f"content_preview_{file['file_id']}"
                                    )
                                else:
                                    st.text_area(
                                        "파일 내용",
                                        value=content,
                                        height=200,
                                        disabled=True,
                                        key=f"full_content_preview_{file['file_id']}"
                                    )
                        
                        # 파일 미리보기 표시
                        if st.session_state.get(f"show_search_preview_{file['file_id']}", False):
                            st.markdown("---")
                            st.subheader("🔍 파일 미리보기")
                            
                            file_binary = get_file_binary_data(file['file_id'])
                            if file_binary:
                                preview_success = display_file_preview(file_binary, file['file_type'], file['filename'])
                                
                                if not preview_success and file.get('file_content'):
                                    st.subheader("📄 추출된 텍스트 내용")
                                    content = file['file_content']
                                    if not (content.startswith('[') and content.endswith(']')):
                                        st.text_area(
                                            "파일 내용",
                                            value=content,
                                            height=400,
                                            disabled=True,
                                            key=f"detailed_preview_{file['file_id']}"
                                        )
                            else:
                                st.error("파일 데이터를 불러올 수 없습니다.")
                        
                        # 구분선
                        if i < len(search_results) - 1:
                            st.markdown("---")
                
                # 검색 결과 내보내기
                if search_results:
                    st.markdown("---")
                    st.subheader("📊 검색 결과 내보내기")
                    
                    # 검색 결과를 데이터프레임으로 변환
                    export_data = []
                    for file in search_results:
                        export_row = {
                            '파일명': file['filename'],
                            '파일타입': file['file_type'],
                            '프로젝트명': file['project_name'],
                            '프로젝트유형': file['project_type'],
                            '파일크기(MB)': (file.get('file_size', 0)) / (1024*1024),
                            '업로드날짜': file['uploaded_at'].strftime('%Y-%m-%d %H:%M'),
                            '작성자': file.get('created_by', ''),
                            '내용미리보기': (file.get('file_content', '') or '')[:200] + ('...' if len(file.get('file_content', '') or '') > 200 else '')
                        }
                        export_data.append(export_row)
                    
                    export_df = pd.DataFrame(export_data)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        csv_data = export_to_csv(export_df, "file_search_results.csv")
                        st.download_button(
                            label="📄 검색결과 CSV 다운로드",
                            data=csv_data,
                            file_name=f"파일검색결과_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            key="file_search_csv_download"
                        )
                    
                    with col2:
                        excel_data = export_to_excel(export_df, "file_search_results.xlsx")
                        st.download_button(
                            label="📊 검색결과 Excel 다운로드",
                            data=excel_data,
                            file_name=f"파일검색결과_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="file_search_excel_download"
                        )
            
            else:
                st.info("🔍 검색 결과가 없습니다.")
                st.markdown("""
                **검색 팁:**
                - 파일명의 일부만 입력해도 검색됩니다
                - 파일 내용에서도 검색이 가능합니다
                - 프로젝트명으로도 검색할 수 있습니다
                - 고급 검색 옵션을 활용해보세요
                """)
        
        else:
            # 검색 전 초기 화면
            st.markdown("---")
            st.markdown("### 💡 파일 검색 도움말")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **🔍 검색 기능:**
                - **파일명 검색**: 파일 이름으로 검색
                - **내용 검색**: 파일 내부 텍스트 검색
                - **프로젝트 검색**: 프로젝트명으로 검색
                - **복합 검색**: 여러 조건 동시 적용
                """)
            
            with col2:
                st.markdown("""
                **📁 지원 파일 형식:**
                - **문서**: PDF, DOCX, DOC, TXT, MD
                - **데이터**: XLSX, XLS, CSV, JSON, XML
                - **이미지**: JPG, JPEG, PNG, GIF
                - **압축**: ZIP, RAR
                - **기타**: HTML 등
                """)
            
            # 전체 파일 통계
            all_files = search_files()
            if all_files:
                st.markdown("---")
                st.markdown("### 📊 전체 파일 현황")
                
                total_files = len(all_files)
                total_size = sum([f.get('file_size', 0) for f in all_files])
                file_types = list(set([f['file_type'] for f in all_files]))
                projects = list(set([f['project_name'] for f in all_files]))
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📄 총 파일", total_files)
                with col2:
                    st.metric("💾 총 용량", f"{total_size / (1024*1024):.1f} MB")
                with col3:
                    st.metric("📁 파일 형식", f"{len(file_types)}종류")
                with col4:
                    st.metric("📋 프로젝트", f"{len(projects)}개")
                
                # 파일 타입별 통계
                if len(file_types) > 1:
                    type_counts = {}
                    for file in all_files:
                        file_type = file['file_type']
                        type_counts[file_type] = type_counts.get(file_type, 0) + 1
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 파일 타입별 개수
                        fig_count = px.bar(
                            x=list(type_counts.keys()),
                            y=list(type_counts.values()),
                            title="📊 파일 타입별 개수",
                            labels={'x': '파일 타입', 'y': '개수'}
                        )
                        st.plotly_chart(fig_count, use_container_width=True)
                    
                    with col2:
                        # 파일 타입별 분포
                        fig_pie = px.pie(
                            values=list(type_counts.values()),
                            names=list(type_counts.keys()),
                            title="📊 파일 타입별 분포"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("📄 아직 업로드된 파일이 없습니다.")

if __name__ == "__main__":
    main() 