import streamlit as st
import os
import pandas as pd
import mysql.connector
from datetime import datetime, timedelta
import time
import re
import json
import requests
from dotenv import load_dotenv
import concurrent.futures
import threading
import asyncio

# 환경 변수 로드
load_dotenv()

# 환경 변수 강제 재로드 (디버깅용)
from pathlib import Path
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)

# 페이지 설정
st.set_page_config(
    page_title="🤖 AI Sourcing RPA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일링
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    text-align: center;
    color: white;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.metric-container {
    background: white;
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    margin: 0.5rem 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.agent-card {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
    border: 1px solid #e1e5e9;
}
</style>
""", unsafe_allow_html=True)

# 메인 헤더
st.markdown("""
<div class="main-header">
    <h1>🤖 AI-Powered Sourcing RPA System</h1>
    <p>인공지능 기반 소싱 프로세스 완전 자동화 시스템</p>
    💡 6개 전문 에이전트가 협력하여 최적의 소싱 전략을 수립합니다
</div>
""", unsafe_allow_html=True) 

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

# ===== 데이터베이스 및 유틸리티 함수들 =====

def connect_to_db():
    """데이터베이스 연결"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('SQL_HOST'),
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 연결 오류: {err}")
        return None

def check_tables_exist():
    """필요한 테이블들이 존재하는지 확인"""
    try:
        connection = connect_to_db()
        if not connection:
            return False, [], []
        
        cursor = connection.cursor()
        
        # 확인할 테이블 목록
        required_tables = [
            'sourcing_rpa_sessions',
            'sourcing_rpa_agent_results', 
            'sourcing_suppliers',
            'sourcing_rpa_automation_logs',
            'scm_suppliers'
        ]
        
        existing_tables = []
        for table in required_tables:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if cursor.fetchone():
                existing_tables.append(table)
        
        cursor.close()
        connection.close()
        
        return len(existing_tables) == len(required_tables), existing_tables, required_tables
        
    except Exception as e:
        st.error(f"❌ 테이블 확인 오류: {str(e)}")
        return False, [], []

def web_search_with_perplexity(query, max_results=5):
    """Perplexity API를 사용한 웹 검색"""
    try:
        api_key = os.environ.get('PERPLEXITY_API_KEY')
        if not api_key:
            st.warning("⚠️ PERPLEXITY_API_KEY가 설정되지 않았습니다.")
            return []
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides current, accurate information from web searches."
                },
                {
                    "role": "user", 
                    "content": f"Search for: {query}. Provide current, relevant information with sources."
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.2,
            "top_p": 0.9,
            "search_domain_filter": ["perplexity.ai"],
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "month",
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return [{"content": content, "source": "Perplexity Search"}]
        else:
            st.error(f"Perplexity API 오류: {response.status_code}")
            return []
            
    except Exception as e:
        st.error(f"웹 검색 오류: {str(e)}")
        return []

def search_suppliers_with_perplexity(query, target_count=10):
    """Perplexity를 사용하여 실제 공급업체 검색"""
    try:
        api_key = os.environ.get('PERPLEXITY_API_KEY')
        if not api_key:
            return []
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        search_prompt = f"""
Find {target_count} REAL companies and suppliers for: {query}

Please provide information in this EXACT format for each company:
COMPANY: [Company Name]
WEBSITE: [Full Website URL starting with http:// or https://]
EMAIL: [Contact Email]
PHONE: [Phone Number]
LOCATION: [City, Country]
SPECIALIZATION: [What they specialize in]

---

Focus on:
- REAL, existing companies with working websites
- Include complete contact information
- Prioritize manufacturers, suppliers, and service providers
- Include companies from various countries (China, Vietnam, Korea, etc.)
"""
        
        data = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [{"role": "user", "content": search_prompt}],
            "max_tokens": 4000,
            "temperature": 0.3,
            "top_p": 0.9,
            "search_domain_filter": [],
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "month",
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return content
        else:
            st.error(f"Perplexity API 오류: {response.status_code}")
            return ""
            
    except Exception as e:
        st.error(f"공급업체 검색 오류: {str(e)}")
        return ""

def parse_supplier_information(raw_text):
    """공급업체 정보 파싱"""
    suppliers = []
    
    try:
        # 구조화된 형식으로 파싱 시도
        sections = raw_text.split('COMPANY:')
        
        for section in sections[1:]:  # 첫 번째는 빈 문자열이므로 제외
            try:
                lines = section.strip().split('\n')
                supplier = {}
                
                # 회사명 추출
                supplier['company_name'] = lines[0].strip()
                
                # 나머지 정보 추출
                for line in lines[1:]:
                    line = line.strip()
                    if line.startswith('WEBSITE:'):
                        supplier['website'] = extract_url(line)
                    elif line.startswith('EMAIL:'):
                        supplier['email'] = extract_email(line)
                    elif line.startswith('PHONE:'):
                        supplier['phone'] = extract_phone(line)
                    elif line.startswith('LOCATION:'):
                        supplier['location'] = extract_location(line)
                    elif line.startswith('SPECIALIZATION:'):
                        supplier['specialization'] = extract_specialization(line)
                
                # 필수 필드 확인
                if supplier.get('company_name'):
                    suppliers.append(supplier)
                    
            except Exception as e:
                continue
    
    except Exception as e:
        st.error(f"파싱 오류: {str(e)}")
    
    return suppliers

def extract_url(line):
    """URL 추출 및 정리"""
    try:
        # 마크다운 링크 패턴 [text](url) 먼저 확인
        markdown_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        markdown_match = re.search(markdown_pattern, line)
        if markdown_match:
            url = markdown_match.group(2)
            # URL에서 불필요한 문자 제거
            url = re.sub(r'[)\]\},;]+$', '', url)
            if url.startswith(('http://', 'https://')):
                return url
        
        # 일반 URL 패턴
        url_pattern = r'https?://[^\s\)\]\},;]+'
        url_match = re.search(url_pattern, line)
        if url_match:
            url = url_match.group(0)
            # URL 끝의 불필요한 문자 제거
            url = re.sub(r'[)\]\},;]+$', '', url)
            return url
        
        # www로 시작하는 도메인
        www_pattern = r'www\.[^\s\)\]\},;]+'
        www_match = re.search(www_pattern, line)
        if www_match:
            domain = www_match.group(0)
            domain = re.sub(r'[)\]\},;]+$', '', domain)
            return f"https://{domain}"
        
        # 콜론 이후의 텍스트에서 도메인 추출
        parts = line.split(':', 1)
        if len(parts) > 1:
            domain_text = parts[1].strip()
            domain_text = re.sub(r'[)\]\},;]+$', '', domain_text)
            if '.' in domain_text and not domain_text.startswith(('http://', 'https://')):
                return f"https://{domain_text}"
            return domain_text
        
        return ""
    except:
        return ""

def extract_email(line):
    """이메일 추출"""
    try:
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, line)
        return match.group(0) if match else ""
    except:
        return ""

def extract_phone(line):
    """전화번호 추출"""
    try:
        parts = line.split(':', 1)
        return parts[1].strip() if len(parts) > 1 else ""
    except:
        return ""

def extract_location(line):
    """위치 정보 추출"""
    try:
        parts = line.split(':', 1)
        return parts[1].strip() if len(parts) > 1 else ""
    except:
        return ""

def extract_specialization(line):
    """전문분야 추출"""
    try:
        parts = line.split(':', 1)
        return parts[1].strip() if len(parts) > 1 else ""
    except:
        return ""

def get_ai_response(prompt, model_name, system_prompt=""):
    """AI 모델로부터 응답을 받는 함수 (Virtual Company와 동일한 구조)"""
    try:
        if model_name.startswith('claude'):
            from langchain_anthropic import ChatAnthropic
            
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key or api_key.strip() == '' or api_key == 'NA':
                return "❌ Anthropic API 키가 설정되지 않았습니다. .env 파일에 ANTHROPIC_API_KEY를 설정해주세요."
            
            client = ChatAnthropic(
                model=model_name, 
                api_key=api_key, 
                temperature=0.7, 
                max_tokens=8192
            )
            response = client.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            return response.content if hasattr(response, 'content') else str(response)
        else:
            from openai import OpenAI
            
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                return "❌ OpenAI API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정해주세요."
            
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8192,
                temperature=0.7
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"❌ AI 응답 생성 중 오류가 발생했습니다: {str(e)}"

# ===== SCM 시스템 함수들 =====

def get_scm_suppliers(search_term="", country="전체", status="전체", risk_level="전체", 
                     company_size="전체", min_rating="전체", sort_by="최근 등록순"):
    """SCM 공급업체 데이터 조회"""
    try:
        connection = connect_to_db()
        if not connection:
            return []
        
        cursor = connection.cursor(dictionary=True)
        
        # 기본 쿼리
        query = "SELECT * FROM scm_suppliers WHERE 1=1"
        params = []
        
        # 검색 조건 추가
        if search_term:
            query += " AND (supplier_name LIKE %s OR supplier_code LIKE %s OR specialization LIKE %s)"
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])
        
        if country != "전체":
            query += " AND country LIKE %s"
            params.append(f"%{country}%")
        
        if status != "전체":
            query += " AND supplier_status = %s"
            params.append(status)
        
        if risk_level != "전체":
            query += " AND risk_level = %s"
            params.append(risk_level)
        
        if company_size != "전체":
            query += " AND company_size = %s"
            params.append(company_size)
        
        if min_rating != "전체":
            rating_value = float(min_rating.replace('+', ''))
            query += " AND overall_rating >= %s"
            params.append(rating_value)
        
        # 정렬 조건 추가
        if sort_by == "최근 등록순":
            query += " ORDER BY created_at DESC"
        elif sort_by == "업체명":
            query += " ORDER BY supplier_name ASC"
        elif sort_by == "종합 평점":
            query += " ORDER BY overall_rating DESC"
        elif sort_by == "마지막 평가일":
            query += " ORDER BY last_evaluated_at DESC"
        
        query += " LIMIT 100"
        
        cursor.execute(query, params)
        suppliers = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return suppliers
        
    except Exception as e:
        st.error(f"❌ 공급업체 조회 오류: {str(e)}")
        return []

def display_scm_suppliers_table(suppliers):
    """SCM 공급업체 테이블 표시"""
    try:
        df_data = []
        for supplier in suppliers:
            df_data.append({
                'ID': supplier.get('supplier_id'),
                '업체코드': supplier.get('supplier_code', '-'),
                '업체명': supplier.get('supplier_name', '-'),
                '국가': supplier.get('country', '-'),
                '산업': supplier.get('industry', '-'),
                '규모': supplier.get('company_size', '-'),
                '종합평점': f"{float(supplier.get('overall_rating', 0)):.1f}" if supplier.get('overall_rating') else '-',
                '품질평점': f"{float(supplier.get('quality_rating', 0)):.1f}" if supplier.get('quality_rating') else '-',
                '위험도': supplier.get('risk_level', '-'),
                '상태': supplier.get('supplier_status', '-'),
                '등록일': supplier.get('created_at').strftime('%Y-%m-%d') if supplier.get('created_at') else '-'
            })
        
        df = pd.DataFrame(df_data)
        
        # 상세 정보 조회를 위한 업체 선택
        selected_supplier = st.selectbox(
            "상세 정보를 보려는 업체를 선택하세요:",
            ["선택하세요..."] + [f"{s['업체명']} ({s['업체코드']})" for s in df_data],
            key="selected_scm_supplier"
        )
        
        # 테이블 표시
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 선택된 업체의 상세 정보 표시
        if selected_supplier != "선택하세요...":
            selected_idx = [f"{s['업체명']} ({s['업체코드']})" for s in df_data].index(selected_supplier)
            supplier = suppliers[selected_idx]
            display_supplier_details(supplier)
            
    except Exception as e:
        st.error(f"❌ 테이블 표시 오류: {str(e)}")

def display_supplier_details(supplier):
    """공급업체 상세 정보 표시"""
    st.markdown("---")
    st.markdown(f"### 📊 {supplier.get('supplier_name', '업체명 없음')} 상세 정보")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🏢 기본 정보**")
        st.write(f"• **업체코드:** {supplier.get('supplier_code', '-')}")
        st.write(f"• **업체명:** {supplier.get('supplier_name', '-')}")
        st.write(f"• **영문명:** {supplier.get('supplier_name_en', '-')}")
        st.write(f"• **사업자번호:** {supplier.get('business_registration_number', '-')}")
        st.write(f"• **국가:** {supplier.get('country', '-')}")
        st.write(f"• **지역:** {supplier.get('region', '-')}")
        st.write(f"• **도시:** {supplier.get('city', '-')}")
        st.write(f"• **주소:** {supplier.get('address', '-')}")
    
    with col2:
        st.markdown("**📞 연락처 정보**")
        st.write(f"• **담당자:** {supplier.get('primary_contact_name', '-')}")
        st.write(f"• **직책:** {supplier.get('primary_contact_title', '-')}")
        st.write(f"• **전화번호:** {supplier.get('primary_phone', '-')}")
        st.write(f"• **이메일:** {supplier.get('primary_email', '-')}")
        website = supplier.get('website', '-')
        if website != '-' and website:
            st.write(f"• **웹사이트:** [{website}]({website})")
        else:
            st.write(f"• **웹사이트:** {website}")
        
        st.markdown("**🏭 비즈니스 정보**")
        st.write(f"• **기업 규모:** {supplier.get('company_size', '-')}")
        st.write(f"• **직원 수:** {supplier.get('employee_count', '-')}")
        st.write(f"• **설립년도:** {supplier.get('established_year', '-')}")
    
    with col3:
        st.markdown("**⭐ 평가 정보**")
        st.write(f"• **종합 평점:** {float(supplier.get('overall_rating', 0)):.1f}" if supplier.get('overall_rating') else '미평가')
        st.write(f"• **품질 평점:** {float(supplier.get('quality_rating', 0)):.1f}" if supplier.get('quality_rating') else '미평가')
        st.write(f"• **비용 평점:** {float(supplier.get('cost_rating', 0)):.1f}" if supplier.get('cost_rating') else '미평가')
        st.write(f"• **배송 평점:** {float(supplier.get('delivery_rating', 0)):.1f}" if supplier.get('delivery_rating') else '미평가')
        st.write(f"• **서비스 평점:** {float(supplier.get('service_rating', 0)):.1f}" if supplier.get('service_rating') else '미평가')
        
        st.markdown("**⚠️ 리스크 관리**")
        st.write(f"• **위험 수준:** {supplier.get('risk_level', '-')}")
        st.write(f"• **컴플라이언스:** {supplier.get('compliance_status', '-')}")
        st.write(f"• **상태:** {supplier.get('supplier_status', '-')}")
    
    # 업체 관리 버튼들
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("✏️ 업체 정보 수정", key=f"edit_{supplier.get('supplier_id')}"):
            st.session_state.edit_supplier_id = supplier.get('supplier_id')
            st.success("편집 모드로 전환합니다. '공급업체 추가/수정' 탭을 확인하세요.")
    
    with col2:
        if st.button("⭐ 평가 추가", key=f"eval_{supplier.get('supplier_id')}"):
            st.session_state.eval_supplier_id = supplier.get('supplier_id')
            st.success("평가 등록 모드로 전환합니다. '평가 관리' 탭을 확인하세요.")
    
    with col3:
        if st.button("📞 연락처 관리", key=f"contact_{supplier.get('supplier_id')}"):
            st.session_state.contact_supplier_id = supplier.get('supplier_id')
            st.success("연락처 관리 모드로 전환합니다. '연락처 관리' 탭을 확인하세요.")
    
    with col4:
        if st.button("🗑️ 업체 삭제", key=f"delete_{supplier.get('supplier_id')}"):
            if st.button(f"정말 삭제하시겠습니까?", key=f"confirm_delete_{supplier.get('supplier_id')}"):
                delete_scm_supplier(supplier.get('supplier_id'))

def delete_scm_supplier(supplier_id):
    """SCM 공급업체 삭제"""
    try:
        connection = connect_to_db()
        if not connection:
            st.error("데이터베이스 연결 실패")
            return False
        
        cursor = connection.cursor()
        cursor.execute("DELETE FROM scm_suppliers WHERE supplier_id = %s", (supplier_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        st.success("✅ 공급업체가 성공적으로 삭제되었습니다.")
        st.rerun()
        return True
        
    except Exception as e:
        st.error(f"❌ 공급업체 삭제 오류: {str(e)}")
        return False

def create_scm_supplier(supplier_data):
    """새 SCM 공급업체 생성"""
    try:
        connection = connect_to_db()
        if not connection:
            st.error("데이터베이스 연결 실패")
            return False
        
        cursor = connection.cursor()
        
        # 업체코드 중복 확인
        cursor.execute("SELECT COUNT(*) FROM scm_suppliers WHERE supplier_code = %s", (supplier_data['supplier_code'],))
        if cursor.fetchone()[0] > 0:
            st.error(f"❌ 업체코드 '{supplier_data['supplier_code']}'가 이미 존재합니다.")
            cursor.close()
            connection.close()
            return False
        
        # INSERT 쿼리 실행
        insert_query = """
            INSERT INTO scm_suppliers (
                supplier_code, supplier_name, supplier_name_en, business_registration_number, tax_number,
                country, region, city, address, postal_code, industry, sub_industry, specialization, main_products,
                primary_contact_name, primary_contact_title, primary_phone, primary_email, website,
                company_size, annual_revenue, employee_count, established_year,
                risk_level, compliance_status, supplier_status, discovered_by, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        cursor.execute(insert_query, (
            supplier_data['supplier_code'], supplier_data['supplier_name'], supplier_data['supplier_name_en'],
            supplier_data['business_registration_number'], supplier_data['tax_number'],
            supplier_data['country'], supplier_data['region'], supplier_data['city'], 
            supplier_data['address'], supplier_data['postal_code'],
            supplier_data['industry'], supplier_data['sub_industry'], supplier_data['specialization'], 
            supplier_data['main_products'], supplier_data['primary_contact_name'], supplier_data['primary_contact_title'],
            supplier_data['primary_phone'], supplier_data['primary_email'], supplier_data['website'],
            supplier_data['company_size'], supplier_data['annual_revenue'], supplier_data['employee_count'], 
            supplier_data['established_year'], supplier_data['risk_level'], supplier_data['compliance_status'],
            supplier_data['supplier_status'], supplier_data['discovered_by'], supplier_data['created_by']
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        st.error(f"❌ 공급업체 생성 오류: {str(e)}")
        return False

def display_add_supplier_form():
    """새 공급업체 추가 폼"""
    st.markdown("### ➕ 새 공급업체 등록")
    
    with st.form("add_supplier_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏢 기본 정보**")
            supplier_code = st.text_input("업체코드 *", help="고유한 업체 식별 코드 (예: SUP001)")
            supplier_name = st.text_input("업체명 *")
            supplier_name_en = st.text_input("영문 업체명")
            business_reg_num = st.text_input("사업자등록번호")
            tax_number = st.text_input("세금 번호")
            
            st.markdown("**📍 위치 정보**")
            country = st.selectbox("국가 *", ["", "중국", "베트남", "한국", "일본", "대만", "태국", "인도", "기타"])
            region = st.text_input("지역/주")
            city = st.text_input("도시")
            address = st.text_area("주소")
            postal_code = st.text_input("우편번호")
            
        with col2:
            st.markdown("**🏭 산업 정보**")
            industry = st.selectbox("산업분야 *", ["", "전자부품", "기계제조", "화학", "자동차", "섬유", "의료기기", "기타"])
            sub_industry = st.text_input("세부 산업분야")
            specialization = st.text_area("전문분야/기술")
            main_products = st.text_area("주요 제품")
            
            st.markdown("**📞 연락처**")
            primary_contact_name = st.text_input("주 담당자명")
            primary_contact_title = st.text_input("담당자 직책")
            primary_phone = st.text_input("전화번호")
            primary_email = st.text_input("이메일")
            website = st.text_input("웹사이트")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🏢 기업 정보**")
            company_size = st.selectbox("기업 규모", ["medium", "startup", "small", "large", "enterprise"])
            annual_revenue = st.number_input("연매출 (USD)", min_value=0.0, step=1000.0)
            employee_count = st.number_input("직원 수", min_value=0, step=1)
            established_year = st.number_input("설립년도", min_value=1900, max_value=datetime.now().year, step=1)
        
        with col2:
            st.markdown("**⚠️ 관리 정보**")
            risk_level = st.selectbox("리스크 수준", ["medium", "low", "high", "critical"])
            compliance_status = st.selectbox("컴플라이언스 상태", ["under_review", "compliant", "non_compliant"])
            supplier_status = st.selectbox("업체 상태", ["pending_approval", "active", "inactive", "suspended", "blacklisted"])
            discovered_by = st.text_input("발굴 출처")
        
        st.markdown("---")
        submitted = st.form_submit_button("✅ 공급업체 등록", type="primary")
        
        if submitted:
            # 필수 필드 검증
            if not supplier_code or not supplier_name or not country or not industry:
                st.error("❌ 필수 필드(*)를 모두 입력해주세요.")
                return
            
            # 공급업체 등록 실행
            success = create_scm_supplier({
                'supplier_code': supplier_code,
                'supplier_name': supplier_name,
                'supplier_name_en': supplier_name_en,
                'business_registration_number': business_reg_num,
                'tax_number': tax_number,
                'country': country,
                'region': region,
                'city': city,
                'address': address,
                'postal_code': postal_code,
                'industry': industry,
                'sub_industry': sub_industry,
                'specialization': specialization,
                'main_products': main_products,
                'primary_contact_name': primary_contact_name,
                'primary_contact_title': primary_contact_title,
                'primary_phone': primary_phone,
                'primary_email': primary_email,
                'website': website,
                'company_size': company_size,
                'annual_revenue': annual_revenue if annual_revenue > 0 else None,
                'employee_count': employee_count if employee_count > 0 else None,
                'established_year': established_year if established_year > 1900 else None,
                'risk_level': risk_level,
                'compliance_status': compliance_status,
                'supplier_status': supplier_status,
                'discovered_by': discovered_by,
                'created_by': 'System Admin'
            })
            
            if success:
                st.success("✅ 공급업체가 성공적으로 등록되었습니다!")
                st.balloons()

def display_edit_supplier_form():
    """기존 공급업체 수정 폼"""
    st.markdown("### ✏️ 기존 공급업체 수정")
    
    suppliers = get_scm_suppliers()
    if not suppliers:
        st.warning("⚠️ 등록된 공급업체가 없습니다.")
        return
    
    supplier_options = ["선택하세요..."] + [f"{s['supplier_name']} ({s['supplier_code']})" for s in suppliers]
    selected_supplier = st.selectbox("수정할 공급업체를 선택하세요:", supplier_options)
    
    if selected_supplier == "선택하세요...":
        st.info("👆 수정할 공급업체를 선택해주세요.")
        return
    
    selected_idx = supplier_options.index(selected_supplier) - 1
    supplier = suppliers[selected_idx]
    
    st.info(f"📝 선택된 업체: {supplier.get('supplier_name')} ({supplier.get('supplier_code')})")
    st.info("💡 현재는 수정 기능이 구현 중입니다. 향후 업데이트에서 제공됩니다.")

def display_evaluation_history():
    """평가 내역 조회"""
    st.markdown("### 📊 공급업체 평가 내역")
    st.info("💡 평가 기능은 향후 구현 예정입니다.")

def display_add_evaluation_form():
    """새 평가 등록 폼"""
    st.markdown("### ➕ 새 공급업체 평가 등록")
    st.info("💡 평가 등록 기능은 향후 구현 예정입니다.")

def display_contacts_list():
    """연락처 목록 조회"""
    st.markdown("### 📋 공급업체 연락처 목록")
    st.info("💡 연락처 관리 기능은 향후 구현 예정입니다.")

def display_add_contact_form():
    """연락처 추가 폼"""
    st.markdown("### ➕ 새 연락처 추가")
    st.info("💡 연락처 추가 기능은 향후 구현 예정입니다.")

def display_activity_logs():
    """활동 로그 조회"""
    st.markdown("### 📊 공급업체 활동 로그")
    st.info("💡 활동 로그 기능은 향후 구현 예정입니다.")

def get_rpa_discovered_suppliers():
    """RPA로 발견된 공급업체 목록 조회"""
    try:
        connection = connect_to_db()
        if not connection:
            return []
        
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT * FROM sourcing_suppliers 
        ORDER BY created_at DESC
        """
        cursor.execute(query)
        suppliers = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return suppliers
        
    except Exception as e:
        st.error(f"❌ RPA 공급업체 조회 오류: {str(e)}")
        return []

def display_rpa_discovered_suppliers():
    """RPA로 발견된 공급업체 표시 및 관리"""
    st.markdown("### 🤖 RPA 자동화로 발견된 공급업체 목록")
    st.info("이 탭에서는 RPA 자동화 과정에서 발견된 공급업체들을 확인하고 SCM 시스템으로 이전할 수 있습니다.")
    
    # 새로고침 버튼
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 새로고침", type="secondary"):
            st.rerun()
    
    with col2:
        show_raw_data = st.checkbox("🔍 원본 데이터 표시", value=False)
    
    # RPA 발견 공급업체 조회
    rpa_suppliers = get_rpa_discovered_suppliers()
    
    if not rpa_suppliers:
        st.warning("🔍 RPA로 발견된 공급업체가 없습니다.")
        st.info("💡 **사용 방법:**")
        st.info("1. 탭 1에서 RPA 자동화를 실행하세요")
        st.info("2. 'company_finder' 에이전트가 공급업체를 발견하면 여기에 표시됩니다")
        st.info("3. 발견된 공급업체를 SCM 시스템으로 이전할 수 있습니다")
        return
    
    st.success(f"✅ 총 **{len(rpa_suppliers)}개**의 공급업체가 발견되었습니다.")
    
    # 검색 및 필터링
    search_term = st.text_input("🔍 공급업체명 검색", placeholder="업체명으로 검색")
    
    # 필터링된 결과
    filtered_suppliers = rpa_suppliers
    if search_term:
        filtered_suppliers = [
            s for s in rpa_suppliers 
            if search_term.lower() in s.get('company_name', '').lower()
        ]
    
    # 페이지네이션 설정
    items_per_page = 10
    total_pages = (len(filtered_suppliers) + items_per_page - 1) // items_per_page
    
    if total_pages > 1:
        page = st.selectbox("📄 페이지", range(1, total_pages + 1))
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_suppliers = filtered_suppliers[start_idx:end_idx]
    else:
        page_suppliers = filtered_suppliers
    
    # 공급업체 목록 표시
    for i, supplier in enumerate(page_suppliers):
        with st.expander(f"🏢 {supplier.get('company_name', 'Unknown Company')} ({supplier.get('created_at', 'Unknown Date')})"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # 기본 정보
                st.markdown("**📋 기본 정보**")
                st.write(f"• **업체명:** {supplier.get('company_name', 'N/A')}")
                st.write(f"• **웹사이트:** {supplier.get('website', 'N/A')}")
                st.write(f"• **이메일:** {supplier.get('email', 'N/A')}")
                st.write(f"• **전화번호:** {supplier.get('phone', 'N/A')}")
                st.write(f"• **위치:** {supplier.get('location', 'N/A')}")
                st.write(f"• **전문분야:** {supplier.get('specialization', 'N/A')}")
                
                # 발견 정보
                st.markdown("**🔍 발견 정보**")
                st.write(f"• **발견 방법:** {supplier.get('discovered_by', 'N/A')}")
                st.write(f"• **검색 쿼리:** {supplier.get('search_query', 'N/A')}")
                st.write(f"• **발견 일시:** {supplier.get('created_at', 'N/A')}")
                
                # 원본 데이터 표시
                if show_raw_data and supplier.get('raw_data'):
                    st.markdown("**📊 원본 데이터**")
                    try:
                        raw_data = json.loads(supplier.get('raw_data', '{}'))
                        st.json(raw_data)
                    except:
                        st.text(supplier.get('raw_data', 'N/A'))
            
            with col2:
                st.markdown("**⚡ 작업**")
                
                # SCM 시스템으로 이전 버튼
                if st.button(f"📤 SCM으로 이전", key=f"transfer_{supplier['id']}", type="primary"):
                    if transfer_to_scm_system(supplier):
                        st.success("✅ SCM 시스템으로 성공적으로 이전되었습니다!")
                        st.rerun()
                    else:
                        st.error("❌ SCM 이전에 실패했습니다.")
                
                # 삭제 버튼
                if st.button(f"🗑️ 삭제", key=f"delete_rpa_{supplier['id']}", type="secondary"):
                    if delete_rpa_supplier(supplier['id']):
                        st.success("✅ 공급업체가 삭제되었습니다!")
                        st.rerun()
                    else:
                        st.error("❌ 삭제에 실패했습니다.")
                
                # 상세보기 버튼
                if st.button(f"👁️ 상세보기", key=f"detail_rpa_{supplier['id']}"):
                    st.session_state[f"show_detail_{supplier['id']}"] = True
    
    # 통계 정보
    st.markdown("---")
    st.markdown("### 📊 발견 통계")
    
    # 발견 방법별 통계
    discovered_by_stats = {}
    search_query_stats = {}
    
    for supplier in rpa_suppliers:
        discovered_by = supplier.get('discovered_by', 'Unknown')
        search_query = supplier.get('search_query', 'Unknown')
        
        discovered_by_stats[discovered_by] = discovered_by_stats.get(discovered_by, 0) + 1
        search_query_stats[search_query] = search_query_stats.get(search_query, 0) + 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔍 발견 방법별**")
        for method, count in discovered_by_stats.items():
            st.write(f"• {method}: {count}개")
    
    with col2:
        st.markdown("**🔎 검색어별 (상위 5개)**")
        sorted_queries = sorted(search_query_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        for query, count in sorted_queries:
            short_query = query[:30] + "..." if len(query) > 30 else query
            st.write(f"• {short_query}: {count}개")

def transfer_to_scm_system(rpa_supplier):
    """RPA 발견 공급업체를 SCM 시스템으로 이전"""
    try:
        connection = connect_to_db()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # SCM suppliers 테이블에 데이터 삽입
        supplier_data = {
            'supplier_code': f"RPA_{rpa_supplier['id']:06d}",
            'supplier_name': rpa_supplier.get('company_name', 'Unknown Company'),
            'business_name': rpa_supplier.get('company_name', 'Unknown Company'),
            'website': rpa_supplier.get('website', ''),
            'email': rpa_supplier.get('email', ''),
            'phone': rpa_supplier.get('phone', ''),
            'address': rpa_supplier.get('location', ''),
            'country': 'Unknown',  # RPA에서는 상세 국가 정보를 얻기 어려움
            'city': rpa_supplier.get('location', ''),
            'business_registration_number': '',
            'tax_id': '',
            'industry': rpa_supplier.get('specialization', ''),
            'business_type': 'Unknown',
            'company_size': 'unknown',
            'established_year': None,
            'main_products': rpa_supplier.get('specialization', ''),
            'certifications': '',
            'contact_person': '',
            'contact_title': '',
            'contact_phone': rpa_supplier.get('phone', ''),
            'contact_email': rpa_supplier.get('email', ''),
            'payment_terms': '',
            'delivery_terms': 'FOB',
            'lead_time': '',
            'minimum_order': '',
            'quality_rating': 3.0,  # 기본값
            'delivery_rating': 3.0,  # 기본값
            'price_rating': 3.0,  # 기본값
            'communication_rating': 3.0,  # 기본값
            'overall_rating': 3.0,  # 기본값
            'risk_level': 'medium',  # 기본값
            'status': 'pending_approval',  # 검토 필요 상태
            'notes': f"RPA 자동화로 발견됨 (검색어: {rpa_supplier.get('search_query', 'N/A')})",
            'created_by': 'RPA_System',
            'last_evaluated': None
        }
        
        # INSERT 쿼리 실행
        insert_query = """
        INSERT INTO scm_suppliers (
            supplier_code, supplier_name, business_name, website, email, phone,
            address, country, city, business_registration_number, tax_id, industry,
            business_type, company_size, established_year, main_products, certifications,
            contact_person, contact_title, contact_phone, contact_email,
            payment_terms, delivery_terms, lead_time, minimum_order,
            quality_rating, delivery_rating, price_rating, communication_rating, overall_rating,
            risk_level, status, notes, created_by, last_evaluated
        ) VALUES (
            %(supplier_code)s, %(supplier_name)s, %(business_name)s, %(website)s, %(email)s, %(phone)s,
            %(address)s, %(country)s, %(city)s, %(business_registration_number)s, %(tax_id)s, %(industry)s,
            %(business_type)s, %(company_size)s, %(established_year)s, %(main_products)s, %(certifications)s,
            %(contact_person)s, %(contact_title)s, %(contact_phone)s, %(contact_email)s,
            %(payment_terms)s, %(delivery_terms)s, %(lead_time)s, %(minimum_order)s,
            %(quality_rating)s, %(delivery_rating)s, %(price_rating)s, %(communication_rating)s, %(overall_rating)s,
            %(risk_level)s, %(status)s, %(notes)s, %(created_by)s, %(last_evaluated)s
        )
        """
        
        cursor.execute(insert_query, supplier_data)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        st.error(f"❌ SCM 이전 오류: {str(e)}")
        return False

def delete_rpa_supplier(supplier_id):
    """RPA 발견 공급업체 삭제"""
    try:
        connection = connect_to_db()
        if not connection:
            return False
        
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sourcing_suppliers WHERE id = %s", (supplier_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        st.error(f"❌ 공급업체 삭제 오류: {str(e)}")
        return False

# ===== 자동화 에이전트 시스템 =====

def execute_sourcing_agent(agent_key, query, session_id):
    """단일 에이전트 실행"""
    try:
        agent_configs = {
            "market_research": {
                "name": "🔍 시장 조사 전문가",
                "description": "목표 시장 및 산업 동향 분석",
                "prompt": f"""
                다음 요청에 대한 시장 조사를 수행하세요: {query}
                
                분석 내용:
                1. 산업 규모 및 성장률
                2. 주요 플레이어 분석
                3. 시장 트렌드 및 기회
                4. 경쟁 환경 분석
                5. 가격 범위 및 비용 구조
                
                실제 데이터와 통계를 기반으로 정확한 정보를 제공하세요.
                """
            },
            "company_finder": {
                "name": "🏢 공급업체 발굴 전문가",
                "description": "타겟 공급업체 발굴 및 검증",
                "prompt": f"""
                다음 요구사항에 맞는 실제 공급업체를 찾아주세요: {query}
                
                찾을 정보:
                1. 회사명 및 기본 정보
                2. 웹사이트 및 연락처
                3. 전문 분야 및 주요 제품
                4. 위치 및 규모
                5. 인증 및 자격 사항
                
                검증된 실제 업체만 추천하세요.
                """
            },
            "compliance_checker": {
                "name": "⚖️ 컴플라이언스 검토 전문가",
                "description": "법적 요구사항 및 규정 준수 검토",
                "prompt": f"""
                다음 비즈니스에 대한 컴플라이언스 요건을 분석하세요: {query}
                
                검토 항목:
                1. 해당 산업 규제 및 표준
                2. 수입/수출 관련 법규
                3. 품질 인증 요구사항
                4. 안전 및 환경 규정
                5. 세관 및 관세 고려사항
                
                실제 적용 가능한 실무적 가이드라인을 제공하세요.
                """
            },
            "risk_assessor": {
                "name": "⚠️ 리스크 평가 전문가",
                "description": "공급망 리스크 평가 및 완화 전략",
                "prompt": f"""
                다음 공급망에 대한 리스크 평가를 수행하세요: {query}
                
                평가 영역:
                1. 공급업체 신뢰성 리스크
                2. 지정학적 리스크
                3. 운송 및 물류 리스크
                4. 품질 및 안전 리스크
                5. 재정적 리스크
                
                각 리스크에 대한 완화 전략도 제시하세요.
                """
            },
            "cost_optimizer": {
                "name": "💰 비용 최적화 전문가",
                "description": "비용 구조 분석 및 최적화 방안",
                "prompt": f"""
                다음 소싱 요청에 대한 비용 최적화 분석을 수행하세요: {query}
                
                분석 내용:
                1. 예상 비용 구조 분석
                2. 지역별 가격 비교
                3. 대량 구매 할인 가능성
                4. 운송비 최적화 방안
                5. 총 소유 비용(TCO) 계산
                
                구체적인 절약 방안을 제시하세요.
                """
            },
            "strategy_planner": {
                "name": "📋 전략 수립 전문가",
                "description": "종합적인 소싱 전략 수립",
                "prompt": f"""
                앞선 분석들을 종합하여 다음에 대한 실행 가능한 소싱 전략을 수립하세요: {query}
                
                전략 구성요소:
                1. 우선순위 공급업체 리스트
                2. 단계별 실행 계획
                3. 협상 전략 및 포인트
                4. 품질 관리 방안
                5. 장기적 파트너십 전략
                
                실무진이 바로 실행할 수 있는 구체적인 액션 플랜을 제공하세요.
                """
            }
        }
        
        if agent_key not in agent_configs:
            return {"error": "Unknown agent"}
        
        config = agent_configs[agent_key]
        
        # AI 응답 생성 (백업 옵션 포함)
        if agent_key == "company_finder":
            # 공급업체 발굴 에이전트는 실제 검색 수행
            def is_valid_key(key, min_length=15):
                """간단한 키 유효성 검사"""
                return key and key.strip() and key.strip() not in ['NA', 'None', 'null'] and len(key.strip()) >= min_length
            
            perplexity_key = os.environ.get('PERPLEXITY_API_KEY', '').strip()
            
            if is_valid_key(perplexity_key, 15):
                raw_results = search_suppliers_with_perplexity(query, target_count=10)
                suppliers = parse_supplier_information(raw_results)
                
                # 발견된 공급업체를 데이터베이스에 저장
                save_success = save_discovered_suppliers(session_id, suppliers, agent_key, query)
                
                # 저장 상태에 따른 메시지 추가
                if save_success and len(suppliers) > 0:
                    storage_status = f"✅ {len(suppliers)}개 공급업체가 DB에 성공적으로 저장되었습니다."
                elif len(suppliers) > 0:
                    storage_status = f"⚠️ {len(suppliers)}개 공급업체를 발견했지만 DB 저장에 실패했습니다."
                else:
                    storage_status = "ℹ️ 검색 결과에서 공급업체 정보를 추출하지 못했습니다."
                
                result = {
                    "agent_name": config["name"],
                    "content": f"{raw_results}\n\n📊 **DB 저장 상태:** {storage_status}",
                    "suppliers_found": len(suppliers),
                    "structured_data": suppliers,
                    "storage_status": storage_status,
                    "save_success": save_success
                }
            else:
                result = {
                    "agent_name": config["name"],
                    "content": """
❌ **공급업체 검색을 위한 Perplexity API 키가 필요합니다.**

🔧 **해결 방법:**
1. `.env` 파일에 `PERPLEXITY_API_KEY=your_api_key` 추가
2. [Perplexity API](https://www.perplexity.ai/settings/api)에서 키 발급
3. 서버 재시작 후 다시 실행

💡 **임시 대안:** 수동으로 공급업체를 검색하여 SCM 시스템에 등록해주세요.
                    """,
                    "suppliers_found": 0,
                    "structured_data": []
                }
        else:
            # 기타 에이전트들은 AI 분석 수행 (개선된 백업 옵션)
            def is_valid_key(key, min_length=15):
                """간단한 키 유효성 검사"""
                return key and key.strip() and key.strip() not in ['NA', 'None', 'null'] and len(key.strip()) >= min_length
            
            openai_key = os.environ.get('OPENAI_API_KEY', '').strip()
            anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
            perplexity_key = os.environ.get('PERPLEXITY_API_KEY', '').strip()
            
            content = None
            used_service = None
            
            # 1차 시도: Claude (Virtual Company와 동일한 기본 모델)
            if is_valid_key(anthropic_key, 20):
                content = get_ai_response(config["prompt"], "claude-3-7-sonnet-latest")
                if not ("API 키" in content and "설정되지 않았습니다" in content):
                    used_service = "Anthropic Claude-3-7-Sonnet"
                else:
                    content = None
            
            # 2차 시도: OpenAI (Claude 실패 시)
            if not content and is_valid_key(openai_key, 20) and (openai_key.startswith('sk-') or openai_key.startswith('org-')):
                content = get_ai_response(config["prompt"], "gpt-4o-mini")
                if not ("API 키" in content and "설정되지 않았습니다" in content):
                    used_service = "OpenAI GPT-4o-mini"
                else:
                    content = None
            
            # 3차 시도: Perplexity 웹 검색 (AI 모델 모두 실패 시)
            if not content and is_valid_key(perplexity_key, 15):
                search_results = web_search_with_perplexity(f"{config['prompt'][:200]}...")
                if search_results:
                    content = f"""
🔍 **웹 검색 기반 분석 결과** (AI 모델 대신 Perplexity 검색 사용)

{search_results[0].get('content', '검색 결과 없음')}

---
⚠️ **참고:** AI 모델 API 키가 설정되지 않아 웹 검색 결과로 대체되었습니다.
더 정확한 분석을 위해서는 OpenAI 또는 Anthropic API 키를 설정해주세요.
                    """
                    used_service = "Perplexity Web Search"
            
            # 모든 옵션 실패 시
            if not content:
                # 각 API 키의 정확한 상태 확인
                openai_status = "✅ 설정됨" if is_valid_key(openai_key, 20) and (openai_key.startswith('sk-') or openai_key.startswith('org-')) else \
                               f"❌ 형식 오류 (길이: {len(openai_key)}, 시작: {openai_key[:3]}...)" if openai_key else "❌ 없음"
                               
                anthropic_status = "✅ 설정됨" if is_valid_key(anthropic_key, 20) else \
                                  f"❌ 너무 짧음 (길이: {len(anthropic_key)})" if anthropic_key else "❌ 없음"
                                  
                perplexity_status = "✅ 설정됨" if is_valid_key(perplexity_key, 15) else \
                                   f"❌ 너무 짧음 (길이: {len(perplexity_key)})" if perplexity_key else "❌ 없음"
                
                content = f"""
❌ **분석 서비스를 사용할 수 없습니다.**

**API 키 상태 진단:**
- OpenAI: {openai_status}
- Anthropic: {anthropic_status}
- Perplexity: {perplexity_status}

🔧 **해결 방법:**
1. **디버깅 정보 확인**: 사이드바의 "🔍 API 키 디버깅 정보 보기" 체크
2. **API 키 재설정**: .env 파일에서 키 값 확인
3. **임시 해결**: 사이드바의 "⚡ 임시 API 키 입력" 사용

💡 **추천 순서:**
1. OpenAI (sk-로 시작, 50+ 글자)
2. Perplexity (15+ 글자)  
3. Anthropic (20+ 글자)
                """
                used_service = "None (모든 서비스 실패)"
            
            result = {
                "agent_name": config["name"],
                "content": content,
                "suppliers_found": 0,
                "service_used": used_service
            }
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

def save_discovered_suppliers(session_id, suppliers, discovered_by, search_query):
    """발견된 공급업체를 데이터베이스에 저장 (강화된 오류 처리)"""
    
    # 단계별 진단 정보
    diagnosis_info = {
        "step": "시작",
        "suppliers_count": len(suppliers) if suppliers else 0,
        "connection": False,
        "table_exists": False,
        "columns_ok": False,
        "saved_count": 0,
        "failed_count": 0,
        "errors": []
    }
    
    try:
        # 1단계: 데이터 검증
        diagnosis_info["step"] = "1. 데이터 검증"
        st.info(f"🔍 **{diagnosis_info['step']}**: {diagnosis_info['suppliers_count']}개 공급업체 데이터 확인 중...")
        
        if not suppliers or len(suppliers) == 0:
            st.warning("💡 저장할 공급업체 데이터가 없습니다.")
            show_diagnosis_info(diagnosis_info)
            return False
        
        # 2단계: 데이터베이스 연결
        diagnosis_info["step"] = "2. 데이터베이스 연결"
        st.info(f"🔗 **{diagnosis_info['step']}**: MySQL 연결 시도 중...")
        
        connection = connect_to_db()
        if not connection:
            diagnosis_info["errors"].append("데이터베이스 연결 실패")
            st.error("❌ 데이터베이스 연결 실패")
            show_diagnosis_info(diagnosis_info)
            return False
        
        diagnosis_info["connection"] = True
        st.success("✅ 데이터베이스 연결 성공")
        
        cursor = connection.cursor()
        
        # 3단계: 테이블 존재 확인
        diagnosis_info["step"] = "3. 테이블 확인"
        st.info(f"🗃️ **{diagnosis_info['step']}**: sourcing_suppliers 테이블 확인 중...")
        
        cursor.execute("SHOW TABLES LIKE 'sourcing_suppliers'")
        table_exists = cursor.fetchone()
        diagnosis_info["table_exists"] = bool(table_exists)
        
        if not table_exists:
            st.warning("⚠️ sourcing_suppliers 테이블이 없습니다. 자동 생성을 시도합니다...")
            try:
                cursor.execute("""
                    CREATE TABLE sourcing_suppliers (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        company_name VARCHAR(255) NOT NULL DEFAULT 'Unknown Company',
                        website VARCHAR(500) DEFAULT '',
                        email VARCHAR(255) DEFAULT '',
                        phone VARCHAR(100) DEFAULT '',
                        location VARCHAR(255) DEFAULT '',
                        specialization TEXT DEFAULT '',
                        discovered_by VARCHAR(100) DEFAULT '',
                        search_query TEXT DEFAULT '',
                        raw_data LONGTEXT DEFAULT '',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_company_name (company_name),
                        INDEX idx_discovered_by (discovered_by),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                connection.commit()
                diagnosis_info["table_exists"] = True
                st.success("✅ sourcing_suppliers 테이블 생성 완료")
            except Exception as create_error:
                diagnosis_info["errors"].append(f"테이블 생성 실패: {str(create_error)}")
                st.error(f"❌ 테이블 생성 실패: {str(create_error)}")
                show_diagnosis_info(diagnosis_info)
                return False
        else:
            st.success("✅ sourcing_suppliers 테이블 존재 확인")
        
        # 4단계: 컬럼 구조 확인
        diagnosis_info["step"] = "4. 컬럼 구조 확인"
        st.info(f"📋 **{diagnosis_info['step']}**: 테이블 컬럼 구조 확인 중...")
        
        cursor.execute("DESCRIBE sourcing_suppliers")
        columns_info = cursor.fetchall()
        columns = [row[0] for row in columns_info]
        
        required_columns = ['id', 'company_name', 'website', 'email', 'phone', 'location', 'specialization', 'discovered_by', 'search_query', 'raw_data', 'created_at']
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            diagnosis_info["errors"].append(f"누락된 컬럼: {', '.join(missing_columns)}")
            st.error(f"❌ 누락된 컬럼: {', '.join(missing_columns)}")
            st.info("💡 해결방법: 00_DB생성.py를 실행하여 테이블을 재생성하세요.")
            show_diagnosis_info(diagnosis_info)
            return False
        
        diagnosis_info["columns_ok"] = True
        st.success(f"✅ 모든 필수 컬럼 확인됨 ({len(columns)}개)")
        
        # 5단계: 테이블 구조 확인 및 데이터 저장
        diagnosis_info["step"] = "5. 테이블 구조 확인 및 데이터 저장"
        st.info(f"💾 **{diagnosis_info['step']}**: 테이블 구조 확인 후 {len(suppliers)}개 공급업체 저장...")
        
        # 테이블 구조 확인
        cursor.execute("DESCRIBE sourcing_suppliers")
        table_columns = cursor.fetchall()
        column_names = [col[0] for col in table_columns]
        
        st.info(f"🔍 **테이블 구조**: {len(column_names)}개 컬럼 확인됨")
        st.caption(f"📋 **컬럼 목록**: {', '.join(column_names[:8])}{'...' if len(column_names) > 8 else ''}")
        
        # 동적 컬럼 매핑
        column_mapping = {}
        required_columns = {
            'company_name': ['company_name', 'name', 'supplier_name', 'company'],
            'website': ['website', 'url', 'web_url', 'homepage'],
            'email': ['email', 'contact_email', 'email_address'],
            'phone': ['phone', 'contact_phone', 'phone_number', 'tel'],
            'location': ['location', 'address', 'country', 'region'],
            'specialization': ['specialization', 'description', 'products', 'services'],
            'discovered_by': ['discovered_by', 'source', 'found_by', 'agent'],
            'search_query': ['search_query', 'query', 'search_term', 'keyword'],
            'raw_data': ['raw_data', 'data', 'json_data', 'details']
        }
        
        # 실제 존재하는 컬럼과 매핑
        for logical_name, possible_names in required_columns.items():
            for possible_name in possible_names:
                if possible_name in column_names:
                    column_mapping[logical_name] = possible_name
                    break
            else:
                column_mapping[logical_name] = None
        
        # 매핑 결과 표시
        mapped_columns = [f"{k}→{v}" for k, v in column_mapping.items() if v]
        st.caption(f"🔗 **컬럼 매핑**: {', '.join(mapped_columns[:5])}{'...' if len(mapped_columns) > 5 else ''}")
        
        saved_count = 0
        failed_count = 0
        error_details = []
        
        for i, supplier in enumerate(suppliers):
            try:
                # 실제 존재하는 컬럼만으로 INSERT 쿼리 구성
                insert_columns = []
                insert_values = []
                insert_placeholders = []
                
                # 데이터 정리 및 검증
                data_fields = {
                    'company_name': supplier.get('company_name', f'Unknown Company {i+1}')[:255],
                    'website': supplier.get('website', '')[:500],
                    'email': supplier.get('email', '')[:255],
                    'phone': supplier.get('phone', '')[:100],
                    'location': supplier.get('location', '')[:255],
                    'specialization': supplier.get('specialization', ''),
                    'discovered_by': (discovered_by[:100] if discovered_by else ''),
                    'search_query': search_query,
                    'raw_data': None
                }
                
                # JSON 데이터 검증
                try:
                    data_fields['raw_data'] = json.dumps(supplier, ensure_ascii=False)
                except Exception as json_error:
                    data_fields['raw_data'] = str(supplier)
                
                # 너무 긴 텍스트 자르기
                if len(data_fields['specialization']) > 65535:
                    data_fields['specialization'] = data_fields['specialization'][:65532] + "..."
                if len(data_fields['raw_data']) > 16777215:
                    data_fields['raw_data'] = data_fields['raw_data'][:16777212] + "..."
                
                # 실제 존재하는 컬럼만 INSERT에 포함
                for logical_name, value in data_fields.items():
                    actual_column = column_mapping.get(logical_name)
                    if actual_column and actual_column in column_names:
                        insert_columns.append(actual_column)
                        insert_values.append(value)
                        insert_placeholders.append('%s')
                
                # INSERT 쿼리 실행
                if insert_columns:
                    query = f"""
                        INSERT INTO sourcing_suppliers 
                        ({', '.join(insert_columns)}) 
                        VALUES ({', '.join(insert_placeholders)})
                    """
                    cursor.execute(query, insert_values)
                    saved_count += 1
                else:
                    # 컬럼이 없는 경우 id만으로 최소 저장 시도
                    if 'id' in column_names:
                        cursor.execute("INSERT INTO sourcing_suppliers () VALUES ()")
                        saved_count += 1
                    else:
                        raise Exception("저장할 수 있는 컬럼이 없습니다")
                
                # 진행률 표시
                if (i + 1) % 5 == 0 or i == len(suppliers) - 1:
                    st.info(f"📝 진행률: {i+1}/{len(suppliers)} ({((i+1)/len(suppliers)*100):.1f}%)")
                
            except Exception as insert_error:
                failed_count += 1
                company_name = supplier.get('company_name', f'Unknown Company {i+1}')
                error_detail = f"공급업체 #{i+1} ({company_name}): {str(insert_error)}"
                error_details.append(error_detail)
                
                # 오류 타입별 상세 메시지
                if "Unknown column" in str(insert_error):
                    st.error(f"❌ {error_detail}")
                    st.info(f"💡 **컬럼 문제**: 현재 테이블 컬럼과 매핑이 실패했습니다")
                elif "Data too long" in str(insert_error):
                    st.warning(f"⚠️ {error_detail}")
                    st.info(f"💡 **데이터 길이**: 자동으로 자르기를 시도했지만 여전히 너무 깁니다")
                else:
                    st.warning(f"⚠️ {error_detail}")
        
        diagnosis_info["saved_count"] = saved_count
        diagnosis_info["failed_count"] = failed_count
        diagnosis_info["errors"].extend(error_details)
        
        # 6단계: 커밋 및 정리
        diagnosis_info["step"] = "6. 트랜잭션 완료"
        st.info(f"✅ **{diagnosis_info['step']}**: 변경사항 저장 중...")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # 최종 결과 요약
        if saved_count > 0:
            st.success(f"🎉 **DB 저장 성공**: {saved_count}개 공급업체가 성공적으로 저장되었습니다!")
            if failed_count > 0:
                st.warning(f"⚠️ {failed_count}개 공급업체 저장 실패")
        else:
            st.error("❌ 모든 공급업체 저장에 실패했습니다.")
            
            # DB 저장 완전 실패 시 자동 백업
            st.warning("💾 **자동 백업 시작**: DB 저장이 실패했으므로 CSV 파일로 백업합니다...")
            backup_success = save_suppliers_to_file(suppliers, discovered_by, search_query)
            if backup_success:
                st.info("✅ **백업 완료**: 공급업체 데이터가 CSV 파일로 안전하게 저장되었습니다!")
        
        show_diagnosis_info(diagnosis_info)
        return saved_count > 0
        
    except Exception as e:
        diagnosis_info["errors"].append(f"예상치 못한 오류: {str(e)}")
        st.error(f"❌ 공급업체 저장 중 오류 발생: {str(e)}")
        
        # 상세한 오류 정보 표시
        st.error("🔍 **오류 상세 정보:**")
        st.code(f"오류 타입: {type(e).__name__}\n오류 메시지: {str(e)}")
        
        # 오류 발생 시에도 백업 시도
        if suppliers and len(suppliers) > 0:
            st.warning("💾 **비상 백업 시작**: 오류로 인해 DB 저장이 실패했으므로 CSV 파일로 백업합니다...")
            try:
                backup_success = save_suppliers_to_file(suppliers, discovered_by, search_query)
                if backup_success:
                    st.info("✅ **비상 백업 완료**: 공급업체 데이터가 안전하게 보존되었습니다!")
            except Exception as backup_error:
                st.error(f"❌ 백업도 실패했습니다: {str(backup_error)}")
        
        show_diagnosis_info(diagnosis_info)
        return False

def test_db_connection_detailed():
    """상세한 데이터베이스 연결 테스트"""
    st.markdown("### 🧪 상세 DB 연결 테스트")
    
    with st.spinner("DB 연결 테스트 진행 중..."):
        # 환경 변수 확인
        env_vars = {
            'SQL_HOST': os.getenv('SQL_HOST'),
            'SQL_USER': os.getenv('SQL_USER'), 
            'SQL_PASSWORD': os.getenv('SQL_PASSWORD'),
            'SQL_DATABASE_NEWBIZ': os.getenv('SQL_DATABASE_NEWBIZ')
        }
        
        st.markdown("#### 📋 환경 변수 상태")
        for key, value in env_vars.items():
            if value:
                st.success(f"✅ {key}: {value[:10]}..." if len(value) > 10 else f"✅ {key}: {value}")
            else:
                st.error(f"❌ {key}: 설정되지 않음")
        
        # 연결 테스트
        st.markdown("#### 🔗 연결 테스트")
        try:
            connection = mysql.connector.connect(
                host=env_vars['SQL_HOST'],
                user=env_vars['SQL_USER'],
                password=env_vars['SQL_PASSWORD'],
                database=env_vars['SQL_DATABASE_NEWBIZ'],
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            
            if connection.is_connected():
                st.success("✅ MySQL 서버 연결 성공")
                
                cursor = connection.cursor()
                
                # 서버 정보
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                st.info(f"MySQL 버전: {version}")
                
                cursor.execute("SELECT DATABASE()")
                current_db = cursor.fetchone()[0]
                st.info(f"현재 데이터베이스: {current_db}")
                
                cursor.execute("SELECT USER()")
                current_user = cursor.fetchone()[0]
                st.info(f"현재 사용자: {current_user}")
                
                # 테이블 확인
                cursor.execute("SHOW TABLES LIKE 'sourcing_suppliers'")
                table_exists = cursor.fetchone()
                
                if table_exists:
                    st.success("✅ sourcing_suppliers 테이블 존재")
                    
                    # 테이블 구조 확인
                    cursor.execute("DESCRIBE sourcing_suppliers")
                    columns = cursor.fetchall()
                    st.info(f"테이블 컬럼 수: {len(columns)}")
                    
                    # 테이블 구조 상세 확인
                    cursor.execute("DESCRIBE sourcing_suppliers")
                    columns = cursor.fetchall()
                    st.info(f"테이블 컬럼 수: {len(columns)}")
                    
                    column_names = [col[0] for col in columns]
                    st.caption(f"컬럼 목록: {', '.join(column_names[:5])}...")
                    
                    # 권한 테스트 (실제 존재하는 컬럼 사용)
                    try:
                        # ID 컬럼만 사용한 안전한 테스트
                        cursor.execute("SELECT COUNT(*) FROM sourcing_suppliers LIMIT 1")
                        count_result = cursor.fetchone()
                        
                        # 실제 컬럼명 확인 후 테스트
                        if 'company_name' in column_names:
                            test_column = 'company_name'
                            test_value = 'TEST_COMPANY'
                        elif 'name' in column_names:
                            test_column = 'name'
                            test_value = 'TEST_COMPANY'
                        else:
                            # 첫 번째 문자열 컬럼 찾기
                            for col_name, col_type, _, _, _, _ in columns:
                                if 'varchar' in col_type.lower() or 'text' in col_type.lower():
                                    test_column = col_name
                                    test_value = 'TEST'
                                    break
                            else:
                                test_column = None
                        
                        if test_column:
                            cursor.execute(f"INSERT INTO sourcing_suppliers ({test_column}) VALUES (%s)", (test_value,))
                            cursor.execute(f"DELETE FROM sourcing_suppliers WHERE {test_column} = %s", (test_value,))
                            connection.commit()
                            st.success("✅ INSERT/DELETE 권한 확인")
                        else:
                            st.warning("⚠️ 테스트할 적절한 컬럼을 찾을 수 없음")
                            
                    except Exception as perm_error:
                        st.error(f"❌ 권한 오류: {str(perm_error)}")
                        
                        # 오류 상세 분석
                        error_str = str(perm_error)
                        if "Unknown column" in error_str:
                            st.error("🔍 **문제 진단**: 테이블 구조가 잘못되었습니다")
                            st.info("💡 **해결책**: 아래 '테이블 재생성' 버튼을 클릭하세요")
                        elif "Access denied" in error_str:
                            st.error("🔍 **문제 진단**: 데이터베이스 권한 부족")
                            st.info("💡 **해결책**: DB 관리자에게 INSERT/DELETE 권한을 요청하세요")
                        
                        # 테이블 재생성 옵션
                        if st.button("🔄 테이블 재생성", help="sourcing_suppliers 테이블을 올바른 구조로 재생성합니다"):
                            try:
                                # 기존 테이블 삭제 (주의: 데이터 손실 가능)
                                if st.checkbox("⚠️ 기존 데이터 삭제에 동의합니다 (복구 불가능)", key="confirm_delete"):
                                    cursor.execute("DROP TABLE IF EXISTS sourcing_suppliers")
                                    
                                    # 올바른 구조로 재생성
                                    cursor.execute("""
                                        CREATE TABLE sourcing_suppliers (
                                            id INT AUTO_INCREMENT PRIMARY KEY,
                                            company_name VARCHAR(255) NOT NULL DEFAULT 'Unknown Company',
                                            website VARCHAR(500) DEFAULT '',
                                            email VARCHAR(255) DEFAULT '',
                                            phone VARCHAR(100) DEFAULT '',
                                            location VARCHAR(255) DEFAULT '',
                                            specialization TEXT DEFAULT '',
                                            discovered_by VARCHAR(100) DEFAULT '',
                                            search_query TEXT DEFAULT '',
                                            raw_data LONGTEXT DEFAULT '',
                                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                            INDEX idx_company_name (company_name),
                                            INDEX idx_discovered_by (discovered_by),
                                            INDEX idx_created_at (created_at)
                                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                                    """)
                                    connection.commit()
                                    st.success("✅ 테이블 재생성 완료!")
                                    st.rerun()
                            except Exception as recreate_error:
                                st.error(f"❌ 테이블 재생성 실패: {str(recreate_error)}")
                        
                else:
                    st.warning("⚠️ sourcing_suppliers 테이블이 존재하지 않음")
                    
                    # 테이블 생성 시도
                    if st.button("🔧 테이블 생성 시도"):
                        try:
                            cursor.execute("""
                                CREATE TABLE sourcing_suppliers (
                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                    company_name VARCHAR(255) NOT NULL DEFAULT 'Unknown Company',
                                    website VARCHAR(500) DEFAULT '',
                                    email VARCHAR(255) DEFAULT '',
                                    phone VARCHAR(100) DEFAULT '',
                                    location VARCHAR(255) DEFAULT '',
                                    specialization TEXT DEFAULT '',
                                    discovered_by VARCHAR(100) DEFAULT '',
                                    search_query TEXT DEFAULT '',
                                    raw_data LONGTEXT DEFAULT '',
                                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    INDEX idx_company_name (company_name),
                                    INDEX idx_discovered_by (discovered_by),
                                    INDEX idx_created_at (created_at)
                                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                            """)
                            connection.commit()
                            st.success("✅ sourcing_suppliers 테이블 생성 성공!")
                        except Exception as create_error:
                            st.error(f"❌ 테이블 생성 실패: {str(create_error)}")
                
                cursor.close()
                connection.close()
                
            else:
                st.error("❌ MySQL 연결 실패")
                
        except mysql.connector.Error as err:
            st.error(f"❌ MySQL 연결 오류: {err}")
        except Exception as e:
            st.error(f"❌ 예상치 못한 오류: {str(e)}")

def save_suppliers_to_file(suppliers, discovered_by, search_query):
    """공급업체 데이터를 파일로 임시 저장"""
    try:
        import tempfile
        import csv
        from datetime import datetime
        
        # 임시 파일 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"suppliers_backup_{timestamp}.csv"
        
        # CSV 파일로 저장
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['company_name', 'website', 'email', 'phone', 'location', 'specialization', 'discovered_by', 'search_query', 'raw_data']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for supplier in suppliers:
                row = {
                    'company_name': supplier.get('company_name', ''),
                    'website': supplier.get('website', ''),
                    'email': supplier.get('email', ''),
                    'phone': supplier.get('phone', ''),
                    'location': supplier.get('location', ''),
                    'specialization': supplier.get('specialization', ''),
                    'discovered_by': discovered_by,
                    'search_query': search_query,
                    'raw_data': json.dumps(supplier, ensure_ascii=False)
                }
                writer.writerow(row)
        
        st.success(f"📁 백업 파일 저장됨: {filename}")
        st.info("💡 이 파일을 나중에 수동으로 데이터베이스에 가져올 수 있습니다.")
        
        # 파일 다운로드 링크 제공
        with open(filename, 'rb') as f:
            st.download_button(
                label="📥 백업 파일 다운로드",
                data=f.read(),
                file_name=filename,
                mime='text/csv'
            )
            
        return True
        
    except Exception as e:
        st.error(f"❌ 파일 저장 오류: {str(e)}")
        return False

def show_diagnosis_info(diagnosis_info):
    """진단 정보를 상세히 표시"""
    with st.expander("🔍 상세 진단 정보", expanded=True):
        st.markdown("### 📊 저장 과정 진단")
        
        # 진행 단계
        st.markdown(f"**현재 단계:** {diagnosis_info['step']}")
        
        # 기본 정보
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("공급업체 수", diagnosis_info['suppliers_count'])
        with col2:
            st.metric("저장 성공", diagnosis_info['saved_count'])
        with col3:
            st.metric("저장 실패", diagnosis_info['failed_count'])
        
        # 단계별 체크리스트
        st.markdown("### ✅ 단계별 진행 상황")
        
        checks = [
            ("데이터베이스 연결", diagnosis_info['connection']),
            ("테이블 존재", diagnosis_info['table_exists']),
            ("컬럼 구조 확인", diagnosis_info['columns_ok']),
        ]
        
        for check_name, status in checks:
            if status:
                st.success(f"✅ {check_name}")
            else:
                st.error(f"❌ {check_name}")
        
        # 오류 목록
        if diagnosis_info['errors']:
            st.markdown("### ❌ 발생한 오류들")
            for i, error in enumerate(diagnosis_info['errors'], 1):
                st.error(f"{i}. {error}")
        
        # 대안책 제공
        st.markdown("### 🔧 권장 해결 방법")
        
        if not diagnosis_info['connection']:
            st.info("**데이터베이스 연결 문제:**")
            st.info("1. .env 파일의 데이터베이스 설정을 확인하세요")
            st.info("2. MySQL 서버가 실행 중인지 확인하세요")
            st.info("3. 네트워크 연결을 확인하세요")
            st.info("4. 사이드바의 '🧪 DB 연결 테스트' 버튼을 클릭하세요")
            
        elif not diagnosis_info['table_exists']:
            st.info("**테이블 문제:**")
            st.info("1. `00_DB생성.py`를 실행하세요")
            st.info("2. 또는 `pages/00_💾_01_DB생성.py`를 실행하세요")
            st.info("3. 사이드바의 DB 테스트에서 테이블 생성을 시도하세요")
            
        elif not diagnosis_info['columns_ok']:
            st.info("**테이블 구조 문제:**")
            st.info("1. 기존 테이블을 삭제하고 재생성하세요")
            st.info("2. `DROP TABLE sourcing_suppliers;` 후 DB생성 스크립트 실행")
            
        elif diagnosis_info['failed_count'] > 0:
            st.info("**데이터 저장 문제:**")
            st.info("1. 공급업체 데이터 형식을 확인하세요")
            st.info("2. 데이터베이스 용량을 확인하세요")
            st.info("3. MySQL 권한을 확인하세요")
        
        # 임시 해결책
        if diagnosis_info['suppliers_count'] > 0:
            st.markdown("### 💾 임시 해결책")
            st.info("DB 저장이 실패하더라도 데이터를 잃지 않기 위해 파일로 백업할 수 있습니다.")
            
            if st.button("📁 CSV 파일로 백업 저장", key="backup_suppliers"):
                # 이 부분은 실제 공급업체 데이터가 있을 때 호출되어야 합니다
                st.info("💡 이 기능은 실제 RPA 실행 중에 자동으로 활성화됩니다.")

def execute_agent_parallel(agent_data):
    """병렬 처리를 위한 에이전트 실행 함수"""
    agent_key, user_request, session_id, result_id = agent_data
    
    try:
        # 데이터베이스 연결 (각 스레드마다 별도 연결)
        connection = connect_to_db()
        if not connection:
            return {"error": "데이터베이스 연결 실패", "agent_key": agent_key}
        
        cursor = connection.cursor()
        
        start_time = time.time()
        
        # 에이전트 실행
        result = execute_sourcing_agent(agent_key, user_request, session_id)
        
        execution_time = int(time.time() - start_time)
        
        # 결과 업데이트
        if "error" in result:
            cursor.execute("""
                UPDATE sourcing_rpa_agent_results 
                SET status = 'failed', error_message = %s
                WHERE id = %s
            """, (result["error"], result_id))
        else:
            cursor.execute("""
                UPDATE sourcing_rpa_agent_results 
                SET status = 'completed', result_data = %s
                WHERE id = %s
            """, (json.dumps(result), result_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # 실행 시간과 에이전트 키 추가
        result["execution_time"] = execution_time
        result["agent_key"] = agent_key
        
        return result
        
    except Exception as e:
        return {"error": str(e), "agent_key": agent_key}

def execute_rpa_workflow(user_request, workflow_type, automation_mode, model_name):
    """RPA 워크플로우 실행 (병렬 처리 지원)"""
    try:
        # 세션 생성
        connection = connect_to_db()
        if not connection:
            st.error("데이터베이스 연결 실패")
            return None
        
        cursor = connection.cursor()
        
        # 세션 제목 생성
        session_title = f"소싱 RPA - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 세션 등록
        cursor.execute("""
            INSERT INTO sourcing_rpa_sessions (
                session_title, workflow_type, automation_mode, user_request, model_name
            ) VALUES (%s, %s, %s, %s, %s)
        """, (session_title, workflow_type, automation_mode, user_request, model_name))
        
        session_id = cursor.lastrowid
        connection.commit()
        
        # 에이전트 순서 정의
        agent_sequence = [
            "market_research",
            "company_finder", 
            "compliance_checker",
            "risk_assessor",
            "cost_optimizer",
            "strategy_planner"
        ]
        
        # 결과 저장을 위한 컨테이너
        progress_container = st.container()
        results_container = st.container()
        
        # 실행 시간 추적
        rpa_start_time = time.time()
        
        with progress_container:
            st.markdown("### 🔄 RPA 실행 진행 상황")
            if automation_mode == "완전 자동" and len(agent_sequence) > 1:
                st.info("🚀 **병렬 처리 모드** - 모든 에이전트가 동시에 실행됩니다")
            else:
                st.info("🔄 **순차 처리 모드** - 에이전트가 순서대로 실행됩니다")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        # 에이전트 결과 기록 미리 생성
        agent_result_ids = []
        for i, agent_key in enumerate(agent_sequence):
            cursor.execute("""
                INSERT INTO sourcing_rpa_agent_results (
                    session_id, agent_key, agent_name, status
                ) VALUES (%s, %s, %s, 'pending')
            """, (session_id, agent_key, f"Agent {i+1}"))
            agent_result_ids.append(cursor.lastrowid)
        
        connection.commit()
        
        total_suppliers = 0
        
        # 병렬 처리 vs 순차 처리 선택
        if automation_mode == "완전 자동" and len(agent_sequence) > 1:
            # 🚀 병렬 처리 모드
            status_text.text("🚀 모든 에이전트를 병렬로 실행 중...")
            
            # 병렬 실행을 위한 데이터 준비
            agent_tasks = [
                (agent_key, user_request, session_id, result_id) 
                for agent_key, result_id in zip(agent_sequence, agent_result_ids)
            ]
            
            # ThreadPoolExecutor를 사용한 병렬 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(agent_sequence))) as executor:
                # 모든 에이전트를 동시에 시작
                future_to_agent = {
                    executor.submit(execute_agent_parallel, task): task[0] 
                    for task in agent_tasks
                }
                
                completed_count = 0
                results = []
                
                # 완료되는 순서대로 결과 수집
                for future in concurrent.futures.as_completed(future_to_agent):
                    agent_key = future_to_agent[future]
                    completed_count += 1
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # 진행 상태 업데이트
                        progress = completed_count / len(agent_sequence)
                        progress_bar.progress(progress)
                        status_text.text(f"진행 상황: {completed_count}/{len(agent_sequence)} 에이전트 완료")
                        
                                                 # 실시간 결과 표시
                        with results_container:
                            if "error" not in result:
                                service_info = f" ({result.get('service_used', '서비스 정보 없음')})" if result.get('service_used') else ""
                                st.markdown(f"**✅ {result.get('agent_name', agent_key)} 완료 (병렬){service_info}**")
                                st.text(f"실행 시간: {result.get('execution_time', 0)}초")
                                
                                # 공급업체 발견 및 저장 상태 표시
                                if result.get("suppliers_found", 0) > 0:
                                    st.success(f"🏢 {result['suppliers_found']}개 공급업체 발견")
                                    total_suppliers += result['suppliers_found']
                                    
                                    # DB 저장 상태 표시
                                    if result.get('save_success'):
                                        st.success("💾 공급업체가 DB에 저장됨")
                                    elif 'save_success' in result:
                                        st.error("❌ DB 저장 실패")
                                        
                                elif result.get('service_used') and "Perplexity" in result.get('service_used'):
                                    st.info("🔍 웹 검색 결과로 분석 완료")
                                elif result.get('service_used') and "None" in result.get('service_used'):
                                    st.warning("⚠️ API 키 부족으로 분석 제한됨")
                                    
                                # 저장 상태 메시지가 있으면 표시
                                if result.get('storage_status'):
                                    st.caption(result['storage_status'])
                            else:
                                st.error(f"❌ {agent_key} 오류: {result['error']}")
                                
                    except Exception as e:
                        st.error(f"❌ {agent_key} 실행 중 오류: {str(e)}")
        
        else:
            # 🔄 순차 처리 모드 (기존 방식)
            for i, agent_key in enumerate(agent_sequence):
                # 진행 상태 업데이트
                progress = (i / len(agent_sequence))
                progress_bar.progress(progress)
                status_text.text(f"진행 중: {agent_key} 에이전트 실행 중...")
                
                result_id = agent_result_ids[i]
                
                # 상태를 running으로 업데이트
                cursor.execute("""
                    UPDATE sourcing_rpa_agent_results 
                    SET status = 'running'
                    WHERE id = %s
                """, (result_id,))
                connection.commit()
                
                start_time = time.time()
                
                # 에이전트 실행
                result = execute_sourcing_agent(agent_key, user_request, session_id)
                
                execution_time = int(time.time() - start_time)
                
                # 결과 업데이트
                if "error" in result:
                    cursor.execute("""
                        UPDATE sourcing_rpa_agent_results 
                        SET status = 'failed', error_message = %s
                        WHERE id = %s
                    """, (result["error"], result_id))
                else:
                    suppliers_found = result.get("suppliers_found", 0)
                    total_suppliers += suppliers_found
                    
                    cursor.execute("""
                        UPDATE sourcing_rpa_agent_results 
                        SET status = 'completed', result_data = %s
                        WHERE id = %s
                    """, (json.dumps(result), result_id))
                
                connection.commit()
                
                # 실시간 결과 표시
                with results_container:
                    service_info = f" ({result.get('service_used', '서비스 정보 없음')})" if result.get('service_used') else ""
                    st.markdown(f"**✅ {result.get('agent_name', agent_key)} 완료 (순차){service_info}**")
                    if "error" not in result:
                        st.text(f"실행 시간: {execution_time}초")
                        
                        # 공급업체 발견 및 저장 상태 표시
                        if result.get("suppliers_found", 0) > 0:
                            st.success(f"🏢 {result['suppliers_found']}개 공급업체 발견")
                            
                            # DB 저장 상태 표시
                            if result.get('save_success'):
                                st.success("💾 공급업체가 DB에 저장됨")
                            elif 'save_success' in result:
                                st.error("❌ DB 저장 실패")
                                
                        elif result.get('service_used') and "Perplexity" in result.get('service_used'):
                            st.info("🔍 웹 검색 결과로 분석 완료")
                        elif result.get('service_used') and "None" in result.get('service_used'):
                            st.warning("⚠️ API 키 부족으로 분석 제한됨")
                            
                        # 저장 상태 메시지가 있으면 표시
                        if result.get('storage_status'):
                            st.caption(result['storage_status'])
                    else:
                        st.error(f"❌ 오류: {result['error']}")
        
        # 세션 완료 처리
        progress_bar.progress(1.0)
        if automation_mode == "완전 자동" and len(agent_sequence) > 1:
            status_text.text("✅ 모든 에이전트 병렬 실행 완료!")
        else:
            status_text.text("✅ 모든 에이전트 순차 실행 완료!")
        
        # 최종 결과 요약 
        st.markdown("---")
        st.markdown("### 📊 **최종 실행 결과**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("실행된 에이전트", len(agent_sequence))
        with col2:
            st.metric("총 발견 공급업체", total_suppliers)
        with col3:
            execution_duration = time.time() - rpa_start_time
            st.metric("실행 시간", f"{execution_duration:.1f}초")
        
        # DB 진단 및 디버깅 정보
        if total_suppliers == 0:
            st.warning("⚠️ **공급업체 발견 없음**")
            with st.expander("🔍 **검색 개선 제안**"):
                st.markdown("""
                **더 나은 결과를 위한 팁:**
                - 영어 키워드 사용: 'LED lighting manufacturer'
                - 지역 포함: 'Korea textile supplier'  
                - 산업 분야 명시: 'electronic components distributor'
                - 회사 규모: 'large scale manufacturer'
                """)
        else:
            st.success(f"🎉 **성공적으로 {total_suppliers}개 공급업체를 발견했습니다!**")
            
            # DB 저장 상태 확인
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM sourcing_suppliers 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
                """)
                recent_saves = cursor.fetchone()[0]
                
                if recent_saves > 0:
                    st.success(f"✅ **DB 저장 확인**: 최근 5분간 {recent_saves}개 공급업체가 저장됨")
                else:
                    st.error("❌ **DB 저장 실패**: 발견된 공급업체가 DB에 저장되지 않았습니다")
                    st.info("💡 **해결 방법**: 사이드바의 '🧪 DB 연결 테스트'를 실행하세요")
                    
            except Exception as db_check_error:
                st.warning(f"⚠️ DB 상태 확인 불가: {str(db_check_error)}")
        
        cursor.execute("""
            UPDATE sourcing_rpa_sessions 
            SET status = 'completed', end_time = NOW(), completed_agents = %s
            WHERE id = %s
        """, (len(agent_sequence), session_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        if automation_mode == "완전 자동" and len(agent_sequence) > 1:
            st.success("🎉 병렬 RPA 워크플로우가 성공적으로 완료되었습니다!")
            st.info(f"⚡ **성능 향상**: 병렬 처리로 {len(agent_sequence)}개 에이전트를 동시 실행했습니다!")
        else:
            st.success("🎉 순차 RPA 워크플로우가 성공적으로 완료되었습니다!")
            st.info("🛡️ **안정성 우선**: 모든 에이전트가 순차적으로 안전하게 실행되었습니다!")
        
        st.balloons()
        
        return session_id
        
    except Exception as e:
        st.error(f"RPA 실행 오류: {str(e)}")
        return None

def get_session_results(session_id=None):
    """세션 결과 조회"""
    try:
        connection = connect_to_db()
        if not connection:
            return None, []
        
        cursor = connection.cursor(dictionary=True)
        
        if session_id:
            # 특정 세션 조회
            cursor.execute("""
                SELECT * FROM sourcing_rpa_sessions WHERE id = %s
            """, (session_id,))
            session = cursor.fetchone()
            
            cursor.execute("""
                SELECT * FROM sourcing_rpa_agent_results 
                WHERE session_id = %s ORDER BY id
            """, (session_id,))
            results = cursor.fetchall()
        else:
            # 모든 세션 조회
            cursor.execute("""
                SELECT * FROM sourcing_rpa_sessions 
                ORDER BY created_at DESC LIMIT 10
            """)
            sessions = cursor.fetchall()
            
            cursor.close()
            connection.close()
            return sessions, []
        
        cursor.close()
        connection.close()
        
        return session, results
        
    except Exception as e:
        st.error(f"결과 조회 오류: {str(e)}")
        return None, []

# ===== 메인 UI 코드 =====

def main():
    """메인 애플리케이션"""
    
    # 사이드바 설정
    with st.sidebar:
        st.markdown("## 📊 시스템 상태")
        
        # 데이터베이스 연결 상태 (상세 진단)
        try:
            connection = connect_to_db()
            if connection:
                st.success("✅ 데이터베이스 연결 정상")
                
                # 추가 DB 테스트
                cursor = connection.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                st.caption(f"MySQL 버전: {version[0] if version else 'Unknown'}")
                
                cursor.execute("SELECT DATABASE()")
                current_db = cursor.fetchone()
                st.caption(f"현재 DB: {current_db[0] if current_db else 'Unknown'}")
                
                cursor.close()
                connection.close()
            else:
                st.error("❌ 데이터베이스 연결 실패")
        except Exception as db_error:
            st.error("❌ 데이터베이스 연결 실패")
            st.caption(f"오류: {str(db_error)}")
        
        # DB 수동 테스트 버튼
        if st.button("🧪 DB 연결 테스트", help="데이터베이스 연결을 수동으로 테스트합니다"):
            test_db_connection_detailed()
        
        # 테이블 상태 확인
        st.markdown("### 🗃️ 테이블 상태")
        tables_ok, existing_tables, required_tables = check_tables_exist()
        
        if tables_ok:
            st.success(f"✅ 모든 테이블 준비됨 ({len(existing_tables)}/{len(required_tables)})")
            
            # 테이블별 데이터 현황 표시
            try:
                connection = connect_to_db()
                cursor = connection.cursor()
                
                # 공급업체 수 확인
                cursor.execute("SELECT COUNT(*) FROM sourcing_suppliers")
                total_suppliers = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM sourcing_suppliers WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)")
                recent_suppliers = cursor.fetchone()[0]
                
                # 최근 세션 확인
                cursor.execute("SELECT COUNT(*) FROM sourcing_rpa_sessions WHERE status = 'completed'")
                completed_sessions = cursor.fetchone()[0]
                
                st.caption(f"📊 저장된 공급업체: {total_suppliers}개 (최근 1시간: {recent_suppliers}개)")
                st.caption(f"🎯 완료된 세션: {completed_sessions}개")
                
                cursor.close()
                connection.close()
                
            except Exception as db_info_error:
                st.caption(f"⚠️ 데이터 현황 확인 불가: {str(db_info_error)}")
        else:
            st.error(f"❌ 테이블 부족 ({len(existing_tables)}/{len(required_tables)})")
            
            # 누락된 테이블 표시
            missing_tables = set(required_tables) - set(existing_tables)
            if missing_tables:
                st.warning("누락된 테이블:")
                for table in missing_tables:
                    st.text(f"• {table}")
            
            st.markdown("---")
            st.markdown("### 🔧 테이블 생성 방법")
            st.info("📝 **테이블을 생성하려면:**\n1. `00_DB생성.py` 파일을 실행하세요\n2. 또는 터미널에서 `python 00_DB생성.py` 명령을 실행하세요")
            
            # 긴급 테이블 생성 버튼
            if st.button("🚨 긴급 테이블 생성", help="기본 테이블을 즉시 생성합니다"):
                with st.spinner("테이블 생성 중..."):
                    try:
                        connection = connect_to_db()
                        cursor = connection.cursor()
                        
                        # sourcing_suppliers 테이블 생성
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS sourcing_suppliers (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                company_name VARCHAR(255) NOT NULL DEFAULT 'Unknown Company',
                                website VARCHAR(500) DEFAULT '',
                                email VARCHAR(255) DEFAULT '',
                                phone VARCHAR(100) DEFAULT '',
                                location VARCHAR(255) DEFAULT '',
                                specialization TEXT DEFAULT '',
                                discovered_by VARCHAR(100) DEFAULT '',
                                search_query TEXT DEFAULT '',
                                raw_data LONGTEXT DEFAULT '',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                INDEX idx_company_name (company_name),
                                INDEX idx_discovered_by (discovered_by),
                                INDEX idx_created_at (created_at)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """)
                        
                        # 다른 필수 테이블들도 생성
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS sourcing_rpa_sessions (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                session_title VARCHAR(255) DEFAULT '',
                                workflow_type VARCHAR(100) DEFAULT '',
                                automation_mode VARCHAR(100) DEFAULT '',
                                user_request TEXT DEFAULT '',
                                model_name VARCHAR(100) DEFAULT '',
                                status VARCHAR(50) DEFAULT 'pending',
                                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                                end_time DATETIME DEFAULT NULL,
                                completed_agents INT DEFAULT 0
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """)
                        
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS sourcing_rpa_agent_results (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                session_id INT,
                                agent_key VARCHAR(100),
                                agent_name VARCHAR(255),
                                status VARCHAR(50) DEFAULT 'pending',
                                result_data LONGTEXT,
                                error_message TEXT,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (session_id) REFERENCES sourcing_rpa_sessions(id)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """)
                        
                        connection.commit()
                        cursor.close()
                        connection.close()
                        
                        st.success("✅ 테이블 생성 완료! 페이지를 새로고침하세요.")
                        st.rerun()
                        
                    except Exception as create_error:
                        st.error(f"❌ 테이블 생성 실패: {str(create_error)}")
                        st.info("💡 수동으로 00_💾_01_DB생성.py 페이지를 실행해보세요.")
        
        st.markdown("---")
        st.markdown("### 🔑 API 키 상태")
        
        # API 키 상태 확인 (개선된 검증 로직)
        api_keys = {
            "OpenAI": os.environ.get('OPENAI_API_KEY', '').strip(),
            "Anthropic": os.environ.get('ANTHROPIC_API_KEY', '').strip(),
            "Perplexity": os.environ.get('PERPLEXITY_API_KEY', '').strip()
        }
        
        # 디버깅 정보 (개발 중에만 표시)
        if st.checkbox("🔍 API 키 디버깅 정보 보기", value=False):
            st.write("**디버깅 정보:**")
            for name, key in api_keys.items():
                st.write(f"- {name}: 길이={len(key)}, 값='{key[:20]}...' (처음 20자)" if key else f"- {name}: 없음")
        
        def is_valid_api_key(key, api_type="general"):
            """API 키 유효성 검사"""
            if not key or key.strip() == '':
                return False, "키 없음"
            
            key = key.strip()
            
            if key in ['NA', 'None', 'null', '']:
                return False, "무효한 값"
            
            # API별 최소 길이 검사 (실제 API 키 길이 고려)
            min_lengths = {
                "OpenAI": 20,      # sk-로 시작하는 긴 키
                "Anthropic": 20,   # claude 키도 비교적 길음
                "Perplexity": 15   # 비교적 짧을 수 있음
            }
            
            min_length = min_lengths.get(api_type, 15)
            
            if len(key) < min_length:
                return False, f"너무 짧음 (최소 {min_length}자 필요, 현재 {len(key)}자)"
            
            # OpenAI 키는 보통 sk-로 시작
            if api_type == "OpenAI" and not key.startswith(('sk-', 'org-')):
                return False, "형식 오류 (sk- 또는 org-로 시작해야 함)"
            
            return True, "유효"
        
        valid_apis = []
        
        for api_name, api_key in api_keys.items():
            is_valid, reason = is_valid_api_key(api_key, api_name)
            
            if is_valid:
                st.success(f"✅ {api_name} API 설정됨")
                st.caption(f"키: {api_key[:10]}...{api_key[-4:]} (길이: {len(api_key)})")
                valid_apis.append(api_name)
            else:
                if api_key:
                    st.error(f"❌ {api_name} API 키 오류: {reason}")
                    st.caption(f"현재 값 길이: {len(api_key)}자")
                else:
                    st.warning(f"⚠️ {api_name} API 키 없음")
                
        if not valid_apis:
            st.error("❌ **모든 API 키가 누락되었습니다!**")
            
            with st.expander("⚡ 임시 API 키 입력"):
                st.warning("⚠️ **임시 해결책**: 세션 동안만 유효합니다. 영구 설정은 .env 파일을 사용하세요.")
                
                temp_openai = st.text_input("OpenAI API Key", type="password", key="temp_openai")
                temp_anthropic = st.text_input("Anthropic API Key", type="password", key="temp_anthropic")
                temp_perplexity = st.text_input("Perplexity API Key", type="password", key="temp_perplexity")
                
                if st.button("🔑 임시 키 적용"):
                    if temp_openai.strip():
                        os.environ['OPENAI_API_KEY'] = temp_openai.strip()
                        st.success("✅ OpenAI API 키 임시 설정됨")
                    if temp_anthropic.strip():
                        os.environ['ANTHROPIC_API_KEY'] = temp_anthropic.strip()
                        st.success("✅ Anthropic API 키 임시 설정됨")
                    if temp_perplexity.strip():
                        os.environ['PERPLEXITY_API_KEY'] = temp_perplexity.strip()
                        st.success("✅ Perplexity API 키 임시 설정됨")
                    
                    if any([temp_openai.strip(), temp_anthropic.strip(), temp_perplexity.strip()]):
                        st.info("🔄 페이지를 새로고침하거나 RPA를 다시 실행해주세요.")
                        try:
                            st.rerun()
                        except:
                            try:
                                st.experimental_rerun()
                            except:
                                st.info("수동으로 페이지를 새로고침해주세요.")
            
            with st.expander("🔧 영구 API 키 설정 방법"):
                st.markdown("""
                **1. .env 파일 생성 (프로젝트 루트)**
                ```
                OPENAI_API_KEY=your_openai_api_key_here
                ANTHROPIC_API_KEY=your_anthropic_api_key_here
                PERPLEXITY_API_KEY=your_perplexity_api_key_here
                ```
                
                **2. API 키 발급 사이트:**
                - 🔗 [OpenAI API Keys](https://platform.openai.com/api-keys)
                - 🔗 [Anthropic Console](https://console.anthropic.com/)
                - 🔗 [Perplexity API](https://www.perplexity.ai/settings/api)
                
                **3. 서버 재시작**
                - Streamlit 앱을 재시작해주세요
                
                **4. 비용 관리**
                - OpenAI: $5-20/월 (일반 사용)
                - Anthropic: $15-50/월 (고급 분석)
                - Perplexity: $20/월 (웹 검색)
                """)
        else:
            st.info(f"💡 사용 가능한 API: {', '.join(valid_apis)}")
            
            if len(valid_apis) < 3:
                missing_apis = [name for name in api_keys.keys() if name not in valid_apis]
                st.warning(f"⚠️ 누락된 API: {', '.join(missing_apis)}")
                st.caption("더 많은 API를 설정하면 안정성이 향상됩니다.")
    
    # 메인 탭 구성
    tab1, tab2, tab3 = st.tabs(["🚀 자동화 실행", "📊 결과 조회", "🏢 SCM 관리"])
    
    # ===== 탭 1: 자동화 실행 =====
    with tab1:
        st.markdown("## 🚀 AI 소싱 자동화 실행")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📝 소싱 요청 정보")
            
            user_request = st.text_area(
                "소싱 요청 내용을 상세히 입력하세요:",
                placeholder="예: 스마트폰 케이스 제조업체를 찾고 있습니다. 월 10,000개 생산 가능한 중국 또는 베트남 업체를 원합니다.",
                height=150
            )
            
            col1_sub, col2_sub = st.columns(2)
            
            with col1_sub:
                workflow_type = st.selectbox(
                    "워크플로우 유형:",
                    ["종합 소싱", "시장 조사만", "공급업체 발굴만", "리스크 평가만"]
                )
                
                automation_mode = st.selectbox(
                    "자동화 모드:",
                    ["완전 자동", "반자동 (승인 필요)", "수동 단계별"]
                )
            
            with col2_sub:
                # AI 모델 선택 (Virtual Company와 동일한 구조)
                available_models = []
                has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
                if has_anthropic_key:
                    available_models.extend([
                        'claude-3-7-sonnet-latest',
                        'claude-3-5-sonnet-latest', 
                        'claude-3-5-haiku-latest',
                    ])
                has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
                if has_openai_key:
                    available_models.extend(['gpt-4o', 'gpt-4o-mini'])
                
                if not available_models:
                    st.error("❌ API 키가 설정되지 않았습니다.")
                    available_models = ['claude-3-7-sonnet-latest']  # 기본값
                
                model_name = st.selectbox(
                    "AI 모델 선택:",
                    available_models,
                    index=0,
                    help="Claude는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요"
                )
                
                execution_mode = st.selectbox(
                    "실행 모드:",
                    ["🚀 병렬 실행 (빠름)", "🔄 순차 실행 (안정)"],
                    help="병렬 실행: 모든 에이전트가 동시에 실행 (빠름)\n순차 실행: 에이전트가 순서대로 실행 (안정)"
                )
        
        with col2:
            st.markdown("### 🤖 에이전트 구성")
            
            agents = [
                {"name": "🔍 시장 조사 전문가", "desc": "시장 분석 및 트렌드"},
                {"name": "🏢 공급업체 발굴 전문가", "desc": "실제 업체 검색"},
                {"name": "⚖️ 컴플라이언스 검토 전문가", "desc": "법규 준수 확인"},
                {"name": "⚠️ 리스크 평가 전문가", "desc": "위험 요소 분석"},
                {"name": "💰 비용 최적화 전문가", "desc": "가격 협상 전략"},
                {"name": "📋 전략 수립 전문가", "desc": "종합 실행 계획"}
            ]
            
            for agent in agents:
                st.markdown(f"**{agent['name']}**")
                st.caption(agent['desc'])
            
            st.markdown("---")
            
            # 실행 모드 성능 정보
            if "병렬" in execution_mode:
                st.success("🚀 **병렬 처리 모드 선택됨**")
                st.info("""
                **장점:**
                - ⚡ 실행 시간 최대 6배 단축
                - 🔄 6개 에이전트 동시 실행
                - 💨 빠른 결과 도출
                
                **적합한 경우:**
                - 빠른 결과가 필요한 경우
                - 시스템 자원이 충분한 경우
                """)
            else:
                st.info("🔄 **순차 처리 모드 선택됨**")
                st.info("""
                **장점:**
                - 🛡️ 안정적인 실행
                - 📝 단계별 결과 확인 가능
                - 🔧 디버깅 용이
                
                **적합한 경우:**
                - 안정성이 중요한 경우
                - 단계별 모니터링이 필요한 경우
                """)
        
        st.markdown("---")
        
        # 실행 버튼
        if st.button("🚀 RPA 자동화 시작", type="primary", use_container_width=True):
            if not user_request.strip():
                st.error("❌ 소싱 요청 내용을 입력해주세요.")
            else:
                with st.spinner("🔄 RPA 시스템 실행 중..."):
                    # 실행 모드 결정
                    is_parallel = "병렬" in execution_mode
                    final_automation_mode = "완전 자동" if is_parallel else automation_mode
                    
                    session_id = execute_rpa_workflow(
                        user_request, workflow_type, final_automation_mode, model_name
                    )
                    
                    if session_id:
                        st.session_state.last_session_id = session_id
                        st.success(f"✅ 세션 ID: {session_id}")
    
    # ===== 탭 2: 결과 조회 =====
    with tab2:
        st.markdown("## 📊 RPA 실행 결과 조회")
        
        # 세션 목록 조회
        sessions, _ = get_session_results()
        
        if not sessions:
            st.info("🔍 실행된 세션이 없습니다. 먼저 자동화를 실행해주세요.")
            return
        
        # 세션 선택
        session_options = [
            f"세션 {s.get('id', 'Unknown')}: {s.get('session_title', 'No Title')} ({s.get('status', 'Unknown')})"
            for s in sessions
        ]
        
        selected_session = st.selectbox("조회할 세션을 선택하세요:", session_options)
        
        if selected_session:
            session_id = int(selected_session.split(":")[0].replace("세션 ", ""))
            session, results = get_session_results(session_id)
            
            if session:
                # 세션 정보 표시
                col1, col2, col3, col4 = st.columns(4)
                
                # 변수들을 미리 정의
                execution_time = session.get('total_execution_time', 0)
                suppliers_found = session.get('total_suppliers_found', 0)
                
                with col1:
                    st.metric("세션 상태", session.get('status', 'Unknown'))
                
                with col2:
                    completed = session.get('completed_agents', 0)
                    total = session.get('total_agents', 0)
                    st.metric("완료된 에이전트", f"{completed}/{total}")
                
                with col3:
                    if suppliers_found > 0:
                        st.metric("발견 공급업체", suppliers_found)
                
                with col4:
                    if execution_time > 0:
                        st.metric("총 실행시간", f"{execution_time}초")
                
                st.markdown("---")
                
                # 에이전트 결과 표시
                st.markdown("### 🤖 에이전트별 실행 결과")
                
                for result in results:
                    with st.expander(f"{result['agent_name']} - {result['status']}"):
                        if result['status'] == 'completed' and result['result_data']:
                            try:
                                data = json.loads(result['result_data'])
                                execution_time = result.get('execution_time', 0)
                                if execution_time > 0:
                                    st.markdown(f"**실행 시간:** {execution_time}초")
                                
                                if data.get('suppliers_found', 0) > 0:
                                    st.success(f"🏢 {data['suppliers_found']}개 공급업체 발견")
                                
                                st.markdown("**결과 내용:**")
                                st.text(data.get('content', '내용 없음'))
                                
                            except:
                                st.text(result['result_data'])
                        
                        elif result['status'] == 'failed':
                            st.error(f"❌ 오류: {result.get('error_message', '알 수 없는 오류')}")
                        
                        else:
                            st.info("⏳ 실행 대기 중...")
    
    # ===== 탭 3: SCM 관리 =====
    with tab3:
        st.markdown("## 🏢 SCM 공급업체 관리 시스템")
        
        # SCM 서브 탭 구성
        scm_tab1, scm_tab2, scm_tab3, scm_tab4, scm_tab5, scm_tab6 = st.tabs([
            "🔍 공급업체 조회", "➕ 공급업체 추가/수정", "⭐ 평가 관리", "📞 연락처 관리", "📊 활동 로그", "🤖 RPA 발견 공급업체"
        ])
        
        # SCM 탭 1: 공급업체 조회
        with scm_tab1:
            st.markdown("### 🔍 공급업체 검색 및 조회")
            
            # 검색 및 필터링 옵션
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_term = st.text_input("🔍 검색어", placeholder="업체명, 업체코드, 전문분야로 검색")
                country_filter = st.selectbox("🌍 국가", ["전체", "중국", "베트남", "한국", "일본", "대만", "태국", "인도"])
                
            with col2:
                status_filter = st.selectbox("📊 상태", ["전체", "active", "pending_approval", "inactive", "suspended"])
                risk_filter = st.selectbox("⚠️ 위험도", ["전체", "low", "medium", "high", "critical"])
                
            with col3:
                size_filter = st.selectbox("🏢 규모", ["전체", "startup", "small", "medium", "large", "enterprise"])
                rating_filter = st.selectbox("⭐ 최소 평점", ["전체", "4.0+", "3.5+", "3.0+", "2.5+"])
                sort_filter = st.selectbox("🔄 정렬", ["최근 등록순", "업체명", "종합 평점", "마지막 평가일"])
            
            # 검색 실행
            if st.button("🔍 검색", type="primary"):
                suppliers = get_scm_suppliers(
                    search_term=search_term,
                    country=country_filter,
                    status=status_filter,
                    risk_level=risk_filter,
                    company_size=size_filter,
                    min_rating=rating_filter,
                    sort_by=sort_filter
                )
                
                if suppliers:
                    st.success(f"✅ {len(suppliers)}개 공급업체를 찾았습니다.")
                    display_scm_suppliers_table(suppliers)
                else:
                    st.info("🔍 검색 조건에 맞는 공급업체가 없습니다.")
        
        # SCM 탭 2: 공급업체 추가/수정
        with scm_tab2:
            sub_tab1, sub_tab2 = st.tabs(["➕ 새 업체 등록", "✏️ 기존 업체 수정"])
            
            with sub_tab1:
                display_add_supplier_form()
            
            with sub_tab2:
                display_edit_supplier_form()
        
        # SCM 탭 3: 평가 관리
        with scm_tab3:
            eval_sub_tab1, eval_sub_tab2 = st.tabs(["📊 평가 내역", "➕ 새 평가 등록"])
            
            with eval_sub_tab1:
                display_evaluation_history()
            
            with eval_sub_tab2:
                display_add_evaluation_form()
        
        # SCM 탭 4: 연락처 관리
        with scm_tab4:
            contact_sub_tab1, contact_sub_tab2 = st.tabs(["📋 연락처 목록", "➕ 연락처 추가"])
            
            with contact_sub_tab1:
                display_contacts_list()
            
            with contact_sub_tab2:
                display_add_contact_form()
        
        # SCM 탭 5: 활동 로그
        with scm_tab5:
            display_activity_logs()
            
        # SCM 탭 6: RPA 발견 공급업체
        with scm_tab6:
            display_rpa_discovered_suppliers()

# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🤖 <strong>AI-Powered Sourcing RPA System</strong></p>
    <p>인공지능 기반 소싱 프로세스 완전 자동화 | Powered by Multi-Agent AI</p>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main() 