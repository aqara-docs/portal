import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
import openai
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from openai import OpenAI

load_dotenv()

# 페이지 설정
st.set_page_config(page_title="Business Model Canvas", page_icon="📊", layout="wide")

# 스타일 설정
st.markdown("""
<style>
    .canvas-block {
        background-color: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        height: 100%;
    }
    .canvas-title {
        color: #0066cc;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .stTextArea textarea {
        height: 150px;
    }
</style>
""", unsafe_allow_html=True)

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def save_canvas(title, description, components):
    """Canvas 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 캔버스 저장
        cursor.execute("""
            INSERT INTO business_model_canvas (title, description, created_by)
            VALUES (%s, %s, %s)
        """, (title, description, st.session_state.get('user_id', 1)))
        
        canvas_id = cursor.lastrowid
        
        # 컴포넌트 저장
        for component_type, content in components.items():
            if content.strip():  # 내용이 있는 경우만 저장
                cursor.execute("""
                    INSERT INTO canvas_components (canvas_id, component_type, content)
                    VALUES (%s, %s, %s)
                """, (canvas_id, component_type, content))
        
        conn.commit()
        return True, canvas_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_canvas(canvas_id):
    """Canvas 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 메인 캔버스 정보 로드
        cursor.execute("""
            SELECT * FROM business_model_canvas WHERE canvas_id = %s
        """, (canvas_id,))
        canvas = cursor.fetchone()
        
        # 컴포넌트 로드
        cursor.execute("""
            SELECT * FROM canvas_components WHERE canvas_id = %s
        """, (canvas_id,))
        components = {row['component_type']: row['content'] for row in cursor.fetchall()}
        
        return canvas, components
    except Exception as e:
        st.error(f"캔버스 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def get_canvas_list():
    """저장된 Canvas 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT canvas_id, title, description, created_at, status
            FROM business_model_canvas
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_swot(title, description, items):
    """SWOT 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 SWOT 저장
        cursor.execute("""
            INSERT INTO swot_analysis (title, description, created_by)
            VALUES (%s, %s, %s)
        """, (title, description, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # SWOT 항목 저장
        for category, content_list in items.items():
            for priority, content in enumerate(content_list):
                if content.strip():
                    cursor.execute("""
                        INSERT INTO swot_items (analysis_id, category, content, priority)
                        VALUES (%s, %s, %s, %s)
                    """, (analysis_id, category, content, priority))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_swot(analysis_id):
    """SWOT 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 메인 SWOT 정보 로드
        cursor.execute("""
            SELECT * FROM swot_analysis WHERE analysis_id = %s
        """, (analysis_id,))
        analysis = cursor.fetchone()
        
        # SWOT 항목 로드
        cursor.execute("""
            SELECT * FROM swot_items 
            WHERE analysis_id = %s 
            ORDER BY category, priority
        """, (analysis_id,))
        items = cursor.fetchall()
        
        # 카테고리별로 항목 정리
        categorized_items = {
            'strength': [],
            'weakness': [],
            'opportunity': [],
            'threat': []
        }
        for item in items:
            categorized_items[item['category']].append(item['content'])
        
        return analysis, categorized_items
    except Exception as e:
        st.error(f"SWOT 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def get_swot_list():
    """저장된 SWOT 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, created_at, status
            FROM swot_analysis
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_marketing_mix(title, description, analysis_type, components):
    """마케팅 믹스 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 마케팅 믹스 저장
        cursor.execute("""
            INSERT INTO marketing_mix_analysis (title, description, analysis_type, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, analysis_type, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # 마케팅 믹스 컴포넌트 저장
        for component_type, content in components.items():
            if content.strip():  # 내용이 있는 경우만 저장
                cursor.execute("""
                    INSERT INTO marketing_mix_components (analysis_id, component_type, content)
                    VALUES (%s, %s, %s)
                """, (analysis_id, component_type, content))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_marketing_mix(analysis_id):
    """마케팅 믹스 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 메인 마케팅 믹스 정보 로드
        cursor.execute("""
            SELECT * FROM marketing_mix_analysis WHERE analysis_id = %s
        """, (analysis_id,))
        analysis = cursor.fetchone()
        
        # 마케팅 믹스 컴포넌트 로드
        cursor.execute("""
            SELECT * FROM marketing_mix_components WHERE analysis_id = %s
        """, (analysis_id,))
        components = {row['component_type']: row['content'] for row in cursor.fetchall()}
        
        return analysis, components
    except Exception as e:
        st.error(f"마케팅 믹스 분석 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def get_marketing_mix_list():
    """저장된 마케팅 믹스 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, analysis_type, created_at, status
            FROM marketing_mix_analysis
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def save_pestel(title, description, industry, components):
    """PESTEL 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기본 분석 정보 저장
        cursor.execute("""
            INSERT INTO business_analysis 
            (analysis_type, title, description, industry) 
            VALUES ('pestel', %s, %s, %s)
        """, (title, description, industry))
        
        analysis_id = cursor.lastrowid
        
        # PESTEL 요소 저장
        for component_type, data in components.items():
            cursor.execute("""
                INSERT INTO pestel_components 
                (analysis_id, component_type, content, impact, trend, recommendations) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                analysis_id,
                component_type,
                data['content'],
                data['impact'],
                data['trend'],
                data['recommendations']
            ))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_pestel(analysis_id):
    """PESTEL 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 분석 정보 조회
        cursor.execute("""
            SELECT * FROM business_analysis 
            WHERE analysis_id = %s AND analysis_type = 'pestel'
        """, (analysis_id,))
        analysis_data = cursor.fetchone()
        
        # PESTEL 컴포넌트 조회
        cursor.execute("""
            SELECT * FROM pestel_components 
            WHERE analysis_id = %s
        """, (analysis_id,))
        components = {row['component_type']: {
            'content': row['content'],
            'impact': row['impact'],
            'trend': row['trend'],
            'recommendations': row['recommendations']
        } for row in cursor.fetchall()}
        
        return analysis_data, components
    except Exception as e:
        st.error(f"PESTEL 분석 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def save_five_forces(title, description, components):
    """5 Forces 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 5 Forces 저장
        cursor.execute("""
            INSERT INTO five_forces_analysis (title, description, created_by)
            VALUES (%s, %s, %s)
        """, (title, description, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # 5 Forces 컴포넌트 저장
        for component_type, data in components.items():
            if data['content'].strip():
                cursor.execute("""
                    INSERT INTO five_forces_components 
                    (analysis_id, component_type, content, threat_level, key_factors, recommendations)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (analysis_id, component_type, data['content'], 
                     data['threat_level'], data['key_factors'], data['recommendations']))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def save_value_chain(title, description, components):
    """Value Chain 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 Value Chain 저장
        cursor.execute("""
            INSERT INTO value_chain_analysis (title, description, created_by)
            VALUES (%s, %s, %s)
        """, (title, description, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # Value Chain 컴포넌트 저장
        for activity_type, data in components.items():
            if data['content'].strip():
                cursor.execute("""
                    INSERT INTO value_chain_components 
                    (analysis_id, activity_type, activity_category, content, 
                     strength_level, improvement_points, cost_impact, value_impact)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (analysis_id, activity_type, data['category'], data['content'],
                     data['strength'], data['improvements'], data['cost_impact'], 
                     data['value_impact']))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def save_gap_analysis(title, description, industry, items):
    """Gap 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기본 분석 정보 저장
        cursor.execute("""
            INSERT INTO business_analysis 
            (analysis_type, title, description, industry) 
            VALUES ('gap', %s, %s, %s)
        """, (title, description, industry))
        
        analysis_id = cursor.lastrowid
        
        # Gap 항목 저장
        for item in items:
            if item.get('category'):  # 카테고리가 있는 항목만 저장
                cursor.execute("""
                    INSERT INTO gap_analysis_items 
                    (analysis_id, category, current_state, desired_state, gap_description, 
                     priority, action_plan, timeline, resources, metrics) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    analysis_id,
                    item['category'],
                    item['current_state'],
                    item['desired_state'],
                    item['gap_description'],
                    item['priority'],
                    item['action_plan'],
                    item['timeline'],
                    item['resources'],
                    item['metrics']
                ))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def save_blue_ocean(title, description, industry, actions, canvas_factors):
    """Blue Ocean 전략 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기본 분석 정보 저장
        cursor.execute("""
            INSERT INTO business_analysis 
            (analysis_type, title, description, industry) 
            VALUES ('blue_ocean', %s, %s, %s)
        """, (title, description, industry))
        
        analysis_id = cursor.lastrowid
        
        # 4 Actions Framework 데이터 저장
        for action_type, items in actions.items():
            for item in items:
                if item.get('factor'):  # 빈 항목 제외
                    cursor.execute("""
                        INSERT INTO blue_ocean_actions 
                        (analysis_id, action_type, factor, description, impact, priority) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        analysis_id,
                        action_type,
                        item['factor'],
                        item['description'],
                        item['impact'],
                        item['priority']
                    ))
        
        # Strategy Canvas 데이터 저장
        for factor in canvas_factors:
            if factor.get('name'):  # 빈 항목 제외
                cursor.execute("""
                    INSERT INTO blue_ocean_canvas 
                    (analysis_id, factor_name, industry_score, company_score, description) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    analysis_id,
                    factor['name'],
                    factor['industry_score'],
                    factor['company_score'],
                    factor['description']
                ))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def save_innovators_dilemma(title, description, industry, current_tech, disruptive_tech, strategies):
    """Innovator's Dilemma 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 분석 저장
        cursor.execute("""
            INSERT INTO innovators_dilemma_analysis (title, description, industry, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, industry, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # 현재 기술/제품 저장
        for tech in current_tech:
            if tech['name'].strip():
                cursor.execute("""
                    INSERT INTO innovators_current_tech 
                    (analysis_id, tech_name, description, market_position, performance_level,
                     customer_demand, market_size, profit_margin)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (analysis_id, tech['name'], tech['description'], tech['position'],
                     tech['performance'], tech['demand'], tech['market_size'], 
                     tech['profit_margin']))
        
        # 파괴적 혁신 저장
        for tech in disruptive_tech:
            if tech['name'].strip():
                cursor.execute("""
                    INSERT INTO innovators_disruptive_tech 
                    (analysis_id, tech_name, description, innovation_type, current_performance,
                     expected_growth_rate, potential_market_size, development_status, risk_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (analysis_id, tech['name'], tech['description'], tech['type'],
                     tech['performance'], tech['growth_rate'], tech['market_size'],
                     tech['status'], tech['risk']))
        
        # 대응 전략 저장
        for strategy in strategies:
            if strategy['description'].strip():
                cursor.execute("""
                    INSERT INTO innovators_strategies 
                    (analysis_id, strategy_type, description, implementation_plan,
                     required_resources, timeline, success_metrics, priority)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (analysis_id, strategy['type'], strategy['description'],
                     strategy['plan'], strategy['resources'], strategy['timeline'],
                     strategy['metrics'], strategy['priority']))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def save_portfolio(title, description, analysis_type, items):
    """Portfolio 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 메인 Portfolio 분석 저장
        cursor.execute("""
            INSERT INTO portfolio_analysis (title, description, analysis_type, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, analysis_type, st.session_state.get('user_id', 1)))
        
        analysis_id = cursor.lastrowid
        
        # Portfolio 항목 저장
        for item in items:
            if item['name'].strip():
                cursor.execute("""
                    INSERT INTO portfolio_items 
                    (analysis_id, item_name, description, market_growth, market_share,
                     market_attractiveness, business_strength, market_penetration,
                     market_development, product_development, diversification,
                     current_revenue, potential_revenue, investment_required,
                     risk_level, priority, recommendations)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (analysis_id, item['name'], item['description'],
                     item.get('market_growth', 0), item.get('market_share', 0),
                     item.get('market_attractiveness', 5), item.get('business_strength', 5),
                     item.get('market_penetration', 0), item.get('market_development', 0),
                     item.get('product_development', 0), item.get('diversification', 0),
                     item.get('current_revenue', 0), item.get('potential_revenue', 0),
                     item.get('investment_required', 0), item['risk_level'],
                     item['priority'], item['recommendations']))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def show_portfolio():
    tab1, tab2 = st.tabs(["Portfolio 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 Portfolio 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="Portfolio 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # 분석 유형 선택
        analysis_type = st.radio("분석 유형", ["bcg", "ge_mckinsey", "ansoff"])
        
        # Portfolio 항목 입력
        st.markdown("### Portfolio 항목")
        
        if 'portfolio_items' not in st.session_state:
            st.session_state.portfolio_items = [{}]
        
        if st.button("➕ Portfolio 항목 추가"):
            st.session_state.portfolio_items.append({})
            st.rerun()
        
        items = []
        for i, _ in enumerate(st.session_state.portfolio_items):
            with st.expander(f"Portfolio 항목 {i+1}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("항목명", key=f"name_{i}")
                    description = st.text_area("설명", key=f"desc_{i}")
                    
                    if analysis_type == "bcg":
                        market_growth = st.number_input("시장 성장률(%)", -100.0, 1000.0, 0.0, key=f"growth_{i}")
                        market_share = st.number_input("상대적 시장 점유율", 0.0, 10.0, 1.0, key=f"share_{i}")
                    
                    elif analysis_type == "ge_mckinsey":
                        market_attractiveness = st.slider("시장 매력도", 1, 9, 5, key=f"attractiveness_{i}")
                        business_strength = st.slider("사업 경쟁력", 1, 9, 5, key=f"strength_{i}")
                    
                    else:  # ansoff
                        market_penetration = st.number_input("시장 침투(%)", 0.0, 100.0, 0.0, key=f"penetration_{i}")
                        market_development = st.number_input("시장 개발(%)", 0.0, 100.0, 0.0, key=f"market_dev_{i}")
                        product_development = st.number_input("제품 개발(%)", 0.0, 100.0, 0.0, key=f"product_dev_{i}")
                        diversification = st.number_input("다각화(%)", 0.0, 100.0, 0.0, key=f"diversification_{i}")
                
                with col2:
                    current_revenue = st.number_input("현재 매출(억원)", 0.0, 10000.0, 0.0, key=f"revenue_{i}")
                    potential_revenue = st.number_input("잠재 매출(억원)", 0.0, 10000.0, 0.0, key=f"potential_{i}")
                    investment_required = st.number_input("필요 투자금(억원)", 0.0, 10000.0, 0.0, key=f"investment_{i}")
                    risk_level = st.select_slider("위험 수준",
                                               ['low', 'medium', 'high'],
                                               key=f"risk_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"priority_{i}")
                    recommendations = st.text_area("권고사항", key=f"recommendations_{i}")
                
                if st.button("🗑️ 삭제", key=f"delete_{i}"):
                    st.session_state.portfolio_items.pop(i)
                    st.rerun()
                
                item = {
                    'name': name,
                    'description': description,
                    'current_revenue': current_revenue,
                    'potential_revenue': potential_revenue,
                    'investment_required': investment_required,
                    'risk_level': risk_level,
                    'priority': priority,
                    'recommendations': recommendations
                }
                
                if analysis_type == "bcg":
                    item.update({
                        'market_growth': market_growth,
                        'market_share': market_share
                    })
                elif analysis_type == "ge_mckinsey":
                    item.update({
                        'market_attractiveness': market_attractiveness,
                        'business_strength': business_strength
                    })
                else:
                    item.update({
                        'market_penetration': market_penetration,
                        'market_development': market_development,
                        'product_development': product_development,
                        'diversification': diversification
                    })
                
                items.append(item)
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title:
                st.error("분석 제목을 입력해주세요.")
                return
            
            if not items:
                st.error("최소 하나의 Portfolio 항목을 입력해주세요.")
                return
            
            success, result = save_portfolio(title, description, analysis_type, items)
            if success:
                st.success("Portfolio 분석이 성공적으로 저장되었습니다!")
                st.balloons()
                st.session_state.portfolio_items = [{}]
                st.rerun()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 Portfolio 분석 목록")
        
        analyses = get_portfolio_list()
        if not analyses:
            st.info("저장된 Portfolio 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                st.markdown(f"**분석 유형:** {analysis['analysis_type']}")
                
                analysis_data, items = load_portfolio(analysis['analysis_id'])
                if items:
                    # Portfolio 항목 표시
                    for i, item in enumerate(items):
                        st.markdown(f"### 항목 {i+1}: {item['name']}")
                        st.markdown(f"**설명:** {item['description']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if analysis['analysis_type'] == 'bcg':
                                st.markdown(f"**시장 성장률:** {item['market_growth']}%")
                                st.markdown(f"**상대적 시장 점유율:** {item['market_share']}")
                            elif analysis['analysis_type'] == 'ge_mckinsey':
                                st.markdown(f"**시장 매력도:** {item['market_attractiveness']}")
                                st.markdown(f"**사업 경쟁력:** {item['business_strength']}")
                            else:  # ansoff
                                st.markdown(f"**시장 침투:** {item['market_penetration']}%")
                                st.markdown(f"**시장 개발:** {item['market_development']}%")
                                st.markdown(f"**제품 개발:** {item['product_development']}%")
                                st.markdown(f"**다각화:** {item['diversification']}%")
                        
                        with col2:
                            st.markdown(f"**현재 매출:** {item['current_revenue']}억원")
                            st.markdown(f"**잠재 매출:** {item['potential_revenue']}억원")
                            st.markdown(f"**필요 투자금:** {item['investment_required']}억원")
                            st.markdown(f"**위험 수준:** {item['risk_level']}")
                            st.markdown(f"**우선순위:** {item['priority']}")
                    
                    # 시각화 섹션
                    st.markdown("### 📈 시각화")
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        if analysis['analysis_type'] == 'bcg':
                            # BCG 매트릭스
                            bcg_fig = go.Figure()
                            
                            bcg_fig.add_trace(go.Scatter(
                                x=[item['market_share'] for item in items],
                                y=[item['market_growth'] for item in items],
                                mode='markers+text',
                                text=[item['name'] for item in items],
                                textposition="top center",
                                marker=dict(
                                    size=[item['current_revenue']/10 for item in items],
                                    color=[item['priority'] for item in items],
                                    colorscale='Viridis',
                                    showscale=True
                                )
                            ))
                            
                            bcg_fig.update_layout(
                                title="BCG Matrix",
                                xaxis_title="상대적 시장 점유율",
                                yaxis_title="시장 성장률(%)"
                            )
                            
                            st.plotly_chart(bcg_fig, use_container_width=True)
                            
                        elif analysis['analysis_type'] == 'ge_mckinsey':
                            # GE/McKinsey 매트릭스
                            ge_fig = go.Figure()
                            
                            ge_fig.add_trace(go.Scatter(
                                x=[item['business_strength'] for item in items],
                                y=[item['market_attractiveness'] for item in items],
                                mode='markers+text',
                                text=[item['name'] for item in items],
                                textposition="top center",
                                marker=dict(
                                    size=[item['current_revenue']/10 for item in items],
                                    color=[item['priority'] for item in items],
                                    colorscale='Viridis',
                                    showscale=True
                                )
                            ))
                            
                            ge_fig.update_layout(
                                title="GE/McKinsey Matrix",
                                xaxis_title="사업 경쟁력",
                                yaxis_title="시장 매력도"
                            )
                            
                            st.plotly_chart(ge_fig, use_container_width=True)
                            
                        else:  # ansoff
                            # Ansoff 매트릭스
                            ansoff_data = []
                            for item in items:
                                ansoff_data.extend([
                                    {'Strategy': 'Market Penetration', 'Value': item['market_penetration'], 'Product': item['name']},
                                    {'Strategy': 'Market Development', 'Value': item['market_development'], 'Product': item['name']},
                                    {'Strategy': 'Product Development', 'Value': item['product_development'], 'Product': item['name']},
                                    {'Strategy': 'Diversification', 'Value': item['diversification'], 'Product': item['name']}
                                ])
                            
                            ansoff_df = pd.DataFrame(ansoff_data)
                            ansoff_fig = px.bar(
                                ansoff_df,
                                x='Strategy',
                                y='Value',
                                color='Product',
                                title="Ansoff Matrix Analysis"
                            )
                            
                            st.plotly_chart(ansoff_fig, use_container_width=True)
                    
                    with col4:
                        # 재무 분석 차트
                        finance_fig = go.Figure()
                        
                        finance_fig.add_trace(go.Bar(
                            name='현재 매출',
                            x=[item['name'] for item in items],
                            y=[item['current_revenue'] for item in items],
                            marker_color='#2ecc71'
                        ))
                        
                        finance_fig.add_trace(go.Bar(
                            name='잠재 매출',
                            x=[item['name'] for item in items],
                            y=[item['potential_revenue'] for item in items],
                            marker_color='#3498db'
                        ))
                        
                        finance_fig.add_trace(go.Bar(
                            name='필요 투자금',
                            x=[item['name'] for item in items],
                            y=[item['investment_required'] for item in items],
                            marker_color='#e74c3c'
                        ))
                        
                        finance_fig.update_layout(
                            title="재무 분석",
                            barmode='group',
                            xaxis_tickangle=-45
                        )
                        
                        st.plotly_chart(finance_fig, use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': analysis['title'],
                                'description': analysis['description'],
                                'analysis_type': analysis['analysis_type'],
                                'items': items
                            }
                            insights = get_ai_insights("Portfolio", analysis_data)
                            st.markdown(insights)

def main():
    st.title("📊 비즈니스 분석 도구")
    
    # 도구 선택
    tool = st.selectbox(
        "분석 도구 선택",
        ["Business Model Canvas", "SWOT 분석", "마케팅 믹스 분석", "PESTEL 분석", "5 Forces 분석", "Value Chain 분석", "GAP 분석", "Blue Ocean 전략 분석", "Innovator's Dilemma 분석", "Portfolio 분석"],
        key="tool_selector"
    )
    
    if tool == "Business Model Canvas":
        show_business_model_canvas()
    elif tool == "SWOT 분석":
        show_swot_analysis()
    elif tool == "마케팅 믹스 분석":
        show_marketing_mix()
    elif tool == "PESTEL 분석":
        show_pestel_analysis()
    elif tool == "5 Forces 분석":
        show_five_forces()
    elif tool == "Value Chain 분석":
        show_value_chain()
    elif tool == "GAP 분석":
        show_gap_analysis()
    elif tool == "Blue Ocean 전략 분석":
        show_blue_ocean()
    elif tool == "Innovator's Dilemma 분석":
        show_innovators_dilemma()
    elif tool == "Portfolio 분석":
        show_portfolio()

def show_swot_analysis():
    tab1, tab2 = st.tabs(["SWOT 분석 작성", "저장된 SWOT"])
    
    with tab1:
        st.markdown("### 새로운 SWOT 분석")
        
        # 기본 정보 입력
        title = st.text_input("SWOT 제목", placeholder="분석 대상의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # SWOT 입력 폼
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">💪 강점 (Strengths)</p>', unsafe_allow_html=True)
            strengths = [st.text_area(f"강점 {i+1}", key=f"strength_{i}") for i in range(3)]
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🎯 기회 (Opportunities)</p>', unsafe_allow_html=True)
            opportunities = [st.text_area(f"기회 {i+1}", key=f"opportunity_{i}") for i in range(3)]
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🔧 약점 (Weaknesses)</p>', unsafe_allow_html=True)
            weaknesses = [st.text_area(f"약점 {i+1}", key=f"weakness_{i}") for i in range(3)]
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">⚠️ 위협 (Threats)</p>', unsafe_allow_html=True)
            threats = [st.text_area(f"위협 {i+1}", key=f"threat_{i}") for i in range(3)]
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 저장 버튼
        if st.button("SWOT 저장", type="primary", use_container_width=True):
            if not title:
                st.error("SWOT 제목을 입력해주세요.")
                return
            
            items = {
                'strength': strengths,
                'weakness': weaknesses,
                'opportunity': opportunities,
                'threat': threats
            }
            
            success, result = save_swot(title, description, items)
            if success:
                st.success("SWOT 분석이 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 SWOT 분석 목록")
        
        analyses = get_swot_list()
        if not analyses:
            st.info("저장된 SWOT 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                
                analysis_data, items = load_swot(analysis['analysis_id'])
                if items:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 💪 강점 (Strengths)")
                        for item in items['strength']:
                            st.markdown(f"- {item}")
                        
                        st.markdown("#### 🎯 기회 (Opportunities)")
                        for item in items['opportunity']:
                            st.markdown(f"- {item}")
                    
                    with col2:
                        st.markdown("#### 🔧 약점 (Weaknesses)")
                        for item in items['weakness']:
                            st.markdown(f"- {item}")
                        
                        st.markdown("#### ⚠️ 위협 (Threats)")
                        for item in items['threat']:
                            st.markdown(f"- {item}")
                    
                    # 시각화 추가
                    st.plotly_chart(create_swot_chart(items), use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': analysis['title'],
                                'description': analysis['description'],
                                'strengths': items['strength'],
                                'weaknesses': items['weakness'],
                                'opportunities': items['opportunity'],
                                'threats': items['threat']
                            }
                            insights = get_ai_insights("SWOT", analysis_data)
                            st.markdown(insights)

def show_business_model_canvas():
    tab1, tab2 = st.tabs(["Business Model Canvas 작성", "저장된 Canvas"])
    
    with tab1:
        st.markdown("### 새로운 Business Model Canvas 작성")
        
        # 기본 정보 입력
        title = st.text_input("Canvas 제목", placeholder="비즈니스 모델의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="비즈니스 모델에 대한 간단한 설명을 입력하세요")
        
        # Canvas 컴포넌트 입력
        st.markdown("### Canvas 구성요소")
        
        col1, col2, col3 = st.columns([1,1,1])
        
        with col1:
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🤝 핵심 파트너</p>', unsafe_allow_html=True)
                key_partners = st.text_area("핵심 파트너", placeholder="누가 우리의 핵심 파트너인가?", key="key_partners")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💰 비용 구조</p>', unsafe_allow_html=True)
                cost_structure = st.text_area("비용 구조", placeholder="주요 비용은 무엇인가?", key="cost_structure")
                st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🎯 핵심 활동</p>', unsafe_allow_html=True)
                key_activities = st.text_area("핵심 활동", placeholder="어떤 핵심 활동이 필요한가?", key="key_activities")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💎 가치 제안</p>', unsafe_allow_html=True)
                value_propositions = st.text_area("가치 제안", placeholder="어떤 가치를 제공하는가?", key="value_propositions")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💫 고객 관계</p>', unsafe_allow_html=True)
                customer_relationships = st.text_area("고객 관계", placeholder="어떻게 고객 관계를 유지하는가?", key="customer_relationships")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💸 수익원</p>', unsafe_allow_html=True)
                revenue_streams = st.text_area("수익원", placeholder="어떻게 수익을 창출하는가?", key="revenue_streams")
                st.markdown('</div>', unsafe_allow_html=True)

        with col3:
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🔑 핵심 자원</p>', unsafe_allow_html=True)
                key_resources = st.text_area("핵심 자원", placeholder="어떤 핵심 자원이 필요한가?", key="key_resources")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">📮 채널</p>', unsafe_allow_html=True)
                channels = st.text_area("채널", placeholder="어떤 채널을 통해 고객에게 도달하는가?", key="channels")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">👥 고객 세그먼트</p>', unsafe_allow_html=True)
                customer_segments = st.text_area("고객 세그먼트", placeholder="누가 우리의 고객인가?", key="customer_segments")
                st.markdown('</div>', unsafe_allow_html=True)

        # 저장 버튼
        if st.button("Canvas 저장", type="primary", use_container_width=True):
            if not title:
                st.error("Canvas 제목을 입력해주세요.")
                return
            
            components = {
                'key_partners': key_partners,
                'key_activities': key_activities,
                'key_resources': key_resources,
                'value_propositions': value_propositions,
                'customer_relationships': customer_relationships,
                'channels': channels,
                'customer_segments': customer_segments,
                'cost_structure': cost_structure,
                'revenue_streams': revenue_streams
            }
            
            success, result = save_canvas(title, description, components)
            if success:
                st.success("Canvas가 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 Business Model Canvas 목록")
        
        canvases = get_canvas_list()
        if not canvases:
            st.info("저장된 Business Model Canvas가 없습니다.")
            return
        
        for canvas in canvases:
            with st.expander(f"📊 {canvas['title']} ({canvas['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if canvas['description']:
                    st.markdown(f"**설명:** {canvas['description']}")
                
                canvas_data, components = load_canvas(canvas['canvas_id'])
                if components:
                    col1, col2, col3 = st.columns([1,2,1])
                    
                    with col1:
                        st.markdown("### 🔑 핵심 파트너")
                        st.markdown(components.get('key_partners', ''))
                        
                        st.markdown("### 💰 비용 구조")
                        st.markdown(components.get('cost_structure', ''))
                    
                    with col2:
                        st.markdown("### 📋 핵심 활동")
                        st.markdown(components.get('key_activities', ''))
                        
                        st.markdown("### 💎 가치 제안")
                        st.markdown(components.get('value_propositions', ''))
                        
                        st.markdown("### 💫 고객 관계")
                        st.markdown(components.get('customer_relationships', ''))
                    
                    with col3:
                        st.markdown("### 🎯 고객 세그먼트")
                        st.markdown(components.get('customer_segments', ''))
                        
                        st.markdown("### 💸 수익원")
                        st.markdown(components.get('revenue_streams', ''))
                    
                    # 시각화 섹션
                    st.markdown("### 📈 시각화")
                    col4, col5 = st.columns(2)
                    
                    with col4:
                        # 컴포넌트 분포 차트
                        component_lengths = {
                            k.replace('_', ' ').title(): len(v.split())
                            for k, v in components.items() if v
                        }
                        
                        dist_fig = go.Figure(data=[go.Bar(
                            x=list(component_lengths.keys()),
                            y=list(component_lengths.values()),
                            marker_color='#3498db'
                        )])
                        
                        dist_fig.update_layout(
                            title="컴포넌트별 상세도",
                            xaxis_title="컴포넌트",
                            yaxis_title="단어 수",
                            xaxis_tickangle=-45
                        )
                        
                        st.plotly_chart(dist_fig, use_container_width=True)
                    
                    with col5:
                        # 비즈니스 모델 밸런스 차트
                        balance_data = {
                            '가치 창출': len(components.get('value_propositions', '').split()),
                            '고객 관리': len(components.get('customer_relationships', '').split()) + 
                                     len(components.get('customer_segments', '').split()),
                            '인프라 관리': len(components.get('key_activities', '').split()) + 
                                      len(components.get('key_partners', '').split()),
                            '재무 관리': len(components.get('cost_structure', '').split()) + 
                                    len(components.get('revenue_streams', '').split())
                        }
                        
                        balance_fig = go.Figure(data=[go.Scatterpolar(
                            r=list(balance_data.values()),
                            theta=list(balance_data.keys()),
                            fill='toself'
                        )])
                        
                        balance_fig.update_layout(
                            title="비즈니스 모델 밸런스",
                            polar=dict(radialaxis=dict(visible=True, range=[0, max(balance_data.values())])),
                            showlegend=False
                        )
                        
                        st.plotly_chart(balance_fig, use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{canvas['canvas_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': canvas['title'],
                                'description': canvas['description'],
                                'components': {
                                    k: v for k, v in components.items() if v.strip()
                                }
                            }
                            insights = get_ai_insights("Business Model Canvas", analysis_data)
                            st.markdown(insights)

def show_marketing_mix():
    tab1, tab2 = st.tabs(["4P/7P 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 마케팅 믹스 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="마케팅 믹스 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # 4P/7P 선택
        analysis_type = st.radio("분석 유형", ["4P", "7P"])
        
        # 컴포넌트 입력
        st.markdown("### 마케팅 믹스 구성요소")
        
        col1, col2 = st.columns(2)
        
        components = {}
        
        with col1:
            # 4P 기본 요소
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🏭 Product (제품)</p>', unsafe_allow_html=True)
                components['product'] = st.text_area("제품", placeholder="제품/서비스의 특징과 가치는?")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💰 Price (가격)</p>', unsafe_allow_html=True)
                components['price'] = st.text_area("가격", placeholder="가격 전략과 정책은?")
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">📍 Place (유통)</p>', unsafe_allow_html=True)
                components['place'] = st.text_area("유통", placeholder="유통 채널과 전략은?")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">📢 Promotion (촉진)</p>', unsafe_allow_html=True)
                components['promotion'] = st.text_area("촉진", placeholder="마케팅 커뮤니케이션 전략은?")
                st.markdown('</div>', unsafe_allow_html=True)
        
        # 7P 추가 요소
        if analysis_type == "7P":
            col3, col4 = st.columns(2)
            
            with col3:
                with st.container():
                    st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                    st.markdown('<p class="canvas-title">👥 People (사람)</p>', unsafe_allow_html=True)
                    components['people'] = st.text_area("사람", placeholder="인적 자원 관리와 고객 서비스는?")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                    st.markdown('<p class="canvas-title">⚙️ Process (프로세스)</p>', unsafe_allow_html=True)
                    components['process'] = st.text_area("프로세스", placeholder="서비스 제공 프로세스는?")
                    st.markdown('</div>', unsafe_allow_html=True)
            
            with col4:
                with st.container():
                    st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                    st.markdown('<p class="canvas-title">🏢 Physical Evidence (물리적 증거)</p>', unsafe_allow_html=True)
                    components['physical_evidence'] = st.text_area("물리적 증거", placeholder="서비스의 물리적 요소는?")
                    st.markdown('</div>', unsafe_allow_html=True)
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title:
                st.error("분석 제목을 입력해주세요.")
                return
            
            success, result = save_marketing_mix(title, description, analysis_type, components)
            if success:
                st.success("마케팅 믹스 분석이 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 마케팅 믹스 분석 목록")
        
        analyses = get_marketing_mix_list()
        if not analyses:
            st.info("저장된 마케팅 믹스 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                st.markdown(f"**분석 유형:** {analysis['analysis_type']}")
                
                analysis_data, components = load_marketing_mix(analysis['analysis_id'])
                if components:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🏭 Product (제품)")
                        st.markdown(components.get('product', ''))
                        st.markdown("#### 💰 Price (가격)")
                        st.markdown(components.get('price', ''))
                    
                    with col2:
                        st.markdown("#### 📍 Place (유통)")
                        st.markdown(components.get('place', ''))
                        st.markdown("#### 📢 Promotion (촉진)")
                        st.markdown(components.get('promotion', ''))
                    
                    if analysis['analysis_type'] == '7P':
                        col3, col4 = st.columns(2)
                        
                        with col3:
                            st.markdown("#### 👥 People (사람)")
                            st.markdown(components.get('people', ''))
                            st.markdown("#### ⚙️ Process (프로세스)")
                            st.markdown(components.get('process', ''))
                        
                        with col4:
                            st.markdown("#### 🏢 Physical Evidence (물리적 증거)")
                            st.markdown(components.get('physical_evidence', ''))

def show_pestel_analysis():
    tab1, tab2 = st.tabs(["PESTEL 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 PESTEL 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="PESTEL 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # PEST/PESTEL 선택
        analysis_type = st.radio("분석 유형", ["PEST", "PESTEL"])
        
        # 컴포넌트 입력
        st.markdown("### PESTEL 분석 요소")
        
        components = {}
        
        # 기본 PEST 요소
        col1, col2 = st.columns(2)
        
        with col1:
            # Political
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🏛️ Political (정치적)</p>', unsafe_allow_html=True)
                political_content = st.text_area("정치적 요인", placeholder="정치적 영향 요인은?")
                political_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='political_impact')
                political_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='political_trend')
                components['political'] = {
                    'content': political_content,
                    'impact': political_impact,
                    'trend': political_trend
                }
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Social
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">👥 Social (사회적)</p>', unsafe_allow_html=True)
                social_content = st.text_area("사회적 요인", placeholder="사회적 영향 요인은?")
                social_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='social_impact')
                social_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='social_trend')
                components['social'] = {
                    'content': social_content,
                    'impact': social_impact,
                    'trend': social_trend
                }
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            # Economic
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">💰 Economic (경제적)</p>', unsafe_allow_html=True)
                economic_content = st.text_area("경제적 요인", placeholder="경제적 영향 요인은?")
                economic_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='economic_impact')
                economic_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='economic_trend')
                components['economic'] = {
                    'content': economic_content,
                    'impact': economic_impact,
                    'trend': economic_trend
                }
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Technological
            with st.container():
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown('<p class="canvas-title">🔧 Technological (기술적)</p>', unsafe_allow_html=True)
                technological_content = st.text_area("기술적 요인", placeholder="기술적 영향 요인은?")
                technological_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='technological_impact')
                technological_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='technological_trend')
                components['technological'] = {
                    'content': technological_content,
                    'impact': technological_impact,
                    'trend': technological_trend
                }
                st.markdown('</div>', unsafe_allow_html=True)
        
        # PESTEL 추가 요소
        if analysis_type == "PESTEL":
            col3, col4 = st.columns(2)
            
            with col3:
                # Environmental
                with st.container():
                    st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                    st.markdown('<p class="canvas-title">🌍 Environmental (환경적)</p>', unsafe_allow_html=True)
                    environmental_content = st.text_area("환경적 요인", placeholder="환경적 영향 요인은?")
                    environmental_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='environmental_impact')
                    environmental_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='environmental_trend')
                    components['environmental'] = {
                        'content': environmental_content,
                        'impact': environmental_impact,
                        'trend': environmental_trend
                    }
                    st.markdown('</div>', unsafe_allow_html=True)
            
            with col4:
                # Legal
                with st.container():
                    st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                    st.markdown('<p class="canvas-title">⚖️ Legal (법적)</p>', unsafe_allow_html=True)
                    legal_content = st.text_area("법적 요인", placeholder="법적 영향 요인은?")
                    legal_impact = st.select_slider("영향도", ['low', 'medium', 'high'], key='legal_impact')
                    legal_trend = st.select_slider("추세", ['decreasing', 'stable', 'increasing'], key='legal_trend')
                    components['legal'] = {
                        'content': legal_content,
                        'impact': legal_impact,
                        'trend': legal_trend
                    }
                    st.markdown('</div>', unsafe_allow_html=True)
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title:
                st.error("분석 제목을 입력해주세요.")
                return
            
            success, result = save_pestel(title, description, analysis_type, components)
            if success:
                st.success("PESTEL 분석이 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 PESTEL 분석 목록")
        
        analyses = get_pestel_list()
        if not analyses:
            st.info("저장된 PESTEL 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                st.markdown(f"**분석 유형:** {analysis['analysis_type']}")
                
                analysis_data, components = load_pestel(analysis['analysis_id'])
                if components:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🏛️ 정치적 요인 (Political)")
                        st.markdown(components.get('political', {}).get('content', ''))
                        st.markdown("#### 💰 경제적 요인 (Economic)")
                        st.markdown(components.get('economic', {}).get('content', ''))
                        st.markdown("#### 👥 사회적 요인 (Social)")
                        st.markdown(components.get('social', {}).get('content', ''))
                    
                    with col2:
                        st.markdown("#### 🔧 기술적 요인 (Technological)")
                        st.markdown(components.get('technological', {}).get('content', ''))
                        if analysis['analysis_type'] == 'PESTEL':
                            st.markdown("#### 🌍 환경적 요인 (Environmental)")
                            st.markdown(components.get('environmental', {}).get('content', ''))
                            st.markdown("#### ⚖️ 법적 요인 (Legal)")
                            st.markdown(components.get('legal', {}).get('content', ''))
                    
                    # 시각화 섹션
                    st.markdown("### 📈 시각화")
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        # 영향도 레이더 차트
                        st.plotly_chart(create_pestel_radar(components), use_container_width=True)
                    
                    with col4:
                        # 트렌드 분석 차트
                        trend_data = {k: v['trend'] for k, v in components.items()}
                        trend_fig = go.Figure(data=[go.Bar(
                            x=list(trend_data.keys()),
                            y=[1 if x == 'increasing' else -1 if x == 'decreasing' else 0 for x in trend_data.values()],
                            marker_color=['#2ecc71' if x == 'increasing' else '#e74c3c' if x == 'decreasing' else '#f1c40f' for x in trend_data.values()]
                        )])
                        trend_fig.update_layout(
                            title="요인별 트렌드 분석",
                            yaxis_title="트렌드 방향",
                            showlegend=False
                        )
                        st.plotly_chart(trend_fig, use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': analysis['title'],
                                'description': analysis['description'],
                                'analysis_type': analysis['analysis_type'],
                                'factors': {
                                    k: {
                                        'content': v['content'],
                                        'impact': v['impact'],
                                        'trend': v['trend']
                                    } for k, v in components.items()
                                }
                            }
                            insights = get_ai_insights("PESTEL", analysis_data)
                            st.markdown(insights)

def show_five_forces():
    tab1, tab2 = st.tabs(["5 Forces 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 5 Forces 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="5 Forces 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # 컴포넌트 입력
        st.markdown("### Porter's 5 Forces 분석 요소")
        
        components = {}
        
        # 중앙에 경쟁 강도 배치
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">⚔️ 기존 경쟁자와의 경쟁 강도</p>', unsafe_allow_html=True)
            rivalry_content = st.text_area("경쟁 상황", placeholder="현재 시장의 경쟁 상황은?")
            rivalry_level = st.select_slider(
                "위협 수준", 
                ['very_low', 'low', 'medium', 'high', 'very_high'],
                key='rivalry_level'
            )
            rivalry_factors = st.text_area("주요 요인", placeholder="경쟁 강도에 영향을 미치는 주요 요인", key='rivalry_factors')
            rivalry_recommendations = st.text_area("대응 방안", placeholder="경쟁 상황에 대한 대응 전략", key='rivalry_recommendations')
            components['rivalry'] = {
                'content': rivalry_content,
                'threat_level': rivalry_level,
                'key_factors': rivalry_factors,
                'recommendations': rivalry_recommendations
            }
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 상하좌우에 나머지 요소 배치
        col1, col2 = st.columns(2)
        
        with col1:
            # 신규 진입자
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🆕 신규 진입자의 위협</p>', unsafe_allow_html=True)
            new_entrants_content = st.text_area("신규 진입 위협", placeholder="새로운 경쟁자의 진입 가능성은?")
            new_entrants_level = st.select_slider(
                "위협 수준",
                ['very_low', 'low', 'medium', 'high', 'very_high'],
                key='new_entrants_level'
            )
            new_entrants_factors = st.text_area("주요 요인", placeholder="진입 장벽에 영향을 미치는 요인", key='new_entrants_factors')
            new_entrants_recommendations = st.text_area("대응 방안", placeholder="신규 진입에 대한 대응 전략", key='new_entrants_recommendations')
            components['new_entrants'] = {
                'content': new_entrants_content,
                'threat_level': new_entrants_level,
                'key_factors': new_entrants_factors,
                'recommendations': new_entrants_recommendations
            }
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 공급자의 교섭력
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🏭 공급자의 교섭력</p>', unsafe_allow_html=True)
            supplier_power_content = st.text_area("공급자 영향력", placeholder="공급자들의 협상력은?")
            supplier_power_level = st.select_slider(
                "위협 수준",
                ['very_low', 'low', 'medium', 'high', 'very_high'],
                key='supplier_power_level'
            )
            supplier_power_factors = st.text_area("주요 요인", placeholder="공급자 교섭력에 영향을 미치는 요인", key='supplier_power_factors')
            supplier_power_recommendations = st.text_area("대응 방안", placeholder="공급자 관계 전략", key='supplier_power_recommendations')
            components['supplier_power'] = {
                'content': supplier_power_content,
                'threat_level': supplier_power_level,
                'key_factors': supplier_power_factors,
                'recommendations': supplier_power_recommendations
            }
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            # 대체재의 위협
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🔄 대체재의 위협</p>', unsafe_allow_html=True)
            substitutes_content = st.text_area("대체재 위협", placeholder="대체 가능한 제품/서비스의 위협은?")
            substitutes_level = st.select_slider(
                "위협 수준",
                ['very_low', 'low', 'medium', 'high', 'very_high'],
                key='substitutes_level'
            )
            substitutes_factors = st.text_area("주요 요인", placeholder="대체재 위협에 영향을 미치는 요인", key='substitutes_factors')
            substitutes_recommendations = st.text_area("대응 방안", placeholder="대체재 대응 전략", key='substitutes_recommendations')
            components['substitutes'] = {
                'content': substitutes_content,
                'threat_level': substitutes_level,
                'key_factors': substitutes_factors,
                'recommendations': substitutes_recommendations
            }
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 구매자의 교섭력
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">👥 구매자의 교섭력</p>', unsafe_allow_html=True)
            buyer_power_content = st.text_area("구매자 영향력", placeholder="구매자들의 협상력은?")
            buyer_power_level = st.select_slider(
                "위협 수준",
                ['very_low', 'low', 'medium', 'high', 'very_high'],
                key='buyer_power_level'
            )
            buyer_power_factors = st.text_area("주요 요인", placeholder="구매자 교섭력에 영향을 미치는 요인", key='buyer_power_factors')
            buyer_power_recommendations = st.text_area("대응 방안", placeholder="구매자 관계 전략", key='buyer_power_recommendations')
            components['buyer_power'] = {
                'content': buyer_power_content,
                'threat_level': buyer_power_level,
                'key_factors': buyer_power_factors,
                'recommendations': buyer_power_recommendations
            }
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title:
                st.error("분석 제목을 입력해주세요.")
                return
            
            success, result = save_five_forces(title, description, components)
            if success:
                st.success("5 Forces 분석이 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 5 Forces 분석 목록")
        
        analyses = get_five_forces_list()
        if not analyses:
            st.info("저장된 5 Forces 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                
                analysis_data, components = load_five_forces(analysis['analysis_id'])
                if components:
                    # 중앙에 경쟁 강도 표시
                    st.markdown("### ⚔️ 기존 경쟁자와의 경쟁 강도")
                    st.markdown(components.get('rivalry', {}).get('content', ''))
                    st.markdown(f"**위협 수준:** {components.get('rivalry', {}).get('threat_level', '')}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🆕 신규 진입자의 위협")
                        st.markdown(components.get('new_entrants', {}).get('content', ''))
                        st.markdown(f"**위협 수준:** {components.get('new_entrants', {}).get('threat_level', '')}")
                        
                        st.markdown("#### 🏭 공급자의 교섭력")
                        st.markdown(components.get('supplier_power', {}).get('content', ''))
                        st.markdown(f"**위협 수준:** {components.get('supplier_power', {}).get('threat_level', '')}")
                    
                    with col2:
                        st.markdown("#### 🔄 대체재의 위협")
                        st.markdown(components.get('substitutes', {}).get('content', ''))
                        st.markdown(f"**위협 수준:** {components.get('substitutes', {}).get('threat_level', '')}")
                        
                        st.markdown("#### 👥 구매자의 교섭력")
                        st.markdown(components.get('buyer_power', {}).get('content', ''))
                        st.markdown(f"**위협 수준:** {components.get('buyer_power', {}).get('threat_level', '')}")
                    
                    # 시각화 섹션
                    st.markdown("### 📈 시각화")
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        # 위협 수준 레이더 차트
                        st.plotly_chart(create_five_forces_chart(components), use_container_width=True)
                    
                    with col4:
                        # 주요 요인 분석 차트
                        factors_fig = go.Figure()
                        for force, data in components.items():
                            if data.get('key_factors'):
                                factors = len(data['key_factors'].split('\n'))
                                factors_fig.add_trace(go.Bar(
                                    x=[force.replace('_', ' ').title()],
                                    y=[factors],
                                    name=force
                                ))
                        
                        factors_fig.update_layout(
                            title="주요 요인 분포",
                            yaxis_title="요인 수",
                            showlegend=False
                        )
                        st.plotly_chart(factors_fig, use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': analysis['title'],
                                'description': analysis['description'],
                                'forces': {
                                    k: {
                                        'content': v['content'],
                                        'threat_level': v['threat_level'],
                                        'key_factors': v['key_factors'],
                                        'recommendations': v['recommendations']
                                    } for k, v in components.items()
                                }
                            }
                            insights = get_ai_insights("5 Forces", analysis_data)
                            st.markdown(insights)

def show_value_chain():
    tab1, tab2 = st.tabs(["Value Chain 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 Value Chain 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="Value Chain 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        
        # 주요 활동 (Primary Activities)
        st.markdown("### 주요 활동 (Primary Activities)")
        
        components = {}
        
        # 주요 활동 입력
        col1, col2 = st.columns(2)
        
        primary_activities = {
            'inbound_logistics': '구매 물류',
            'operations': '운영',
            'outbound_logistics': '출하 물류',
            'marketing_sales': '마케팅/판매',
            'service': '서비스'
        }
        
        for i, (activity_type, activity_name) in enumerate(primary_activities.items()):
            with col1 if i % 2 == 0 else col2:
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown(f'<p class="canvas-title">📦 {activity_name}</p>', unsafe_allow_html=True)
                content = st.text_area(f"{activity_name} 활동", placeholder=f"{activity_name}과 관련된 활동은?", key=f"primary_{activity_type}")
                strength = st.select_slider(
                    "강점 수준",
                    ['very_weak', 'weak', 'moderate', 'strong', 'very_strong'],
                    key=f"strength_{activity_type}"
                )
                improvements = st.text_area("개선점", placeholder="개선이 필요한 부분은?", key=f"improvements_{activity_type}")
                col_cost, col_value = st.columns(2)
                with col_cost:
                    cost_impact = st.number_input("비용 영향도 (1-5)", 1, 5, 3, key=f"cost_{activity_type}")
                with col_value:
                    value_impact = st.number_input("가치 영향도 (1-5)", 1, 5, 3, key=f"value_{activity_type}")
                
                components[activity_type] = {
                    'category': 'primary',
                    'content': content,
                    'strength': strength,
                    'improvements': improvements,
                    'cost_impact': float(cost_impact),
                    'value_impact': float(value_impact)
                }
                st.markdown('</div>', unsafe_allow_html=True)
        
        # 지원 활동 (Support Activities)
        st.markdown("### 지원 활동 (Support Activities)")
        
        support_activities = {
            'firm_infrastructure': '기업 인프라',
            'hr_management': '인적 자원 관리',
            'technology_development': '기술 개발',
            'procurement': '조달'
        }
        
        col1, col2 = st.columns(2)
        
        for i, (activity_type, activity_name) in enumerate(support_activities.items()):
            with col1 if i % 2 == 0 else col2:
                st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
                st.markdown(f'<p class="canvas-title">🔧 {activity_name}</p>', unsafe_allow_html=True)
                content = st.text_area(f"{activity_name} 활동", placeholder=f"{activity_name}과 관련된 활동은?", key=f"support_{activity_type}")
                strength = st.select_slider(
                    "강점 수준",
                    ['very_weak', 'weak', 'moderate', 'strong', 'very_strong'],
                    key=f"strength_{activity_type}"
                )
                improvements = st.text_area("개선점", placeholder="개선이 필요한 부분은?", key=f"improvements_{activity_type}")
                col_cost, col_value = st.columns(2)
                with col_cost:
                    cost_impact = st.number_input("비용 영향도 (1-5)", 1, 5, 3, key=f"cost_{activity_type}")
                with col_value:
                    value_impact = st.number_input("가치 영향도 (1-5)", 1, 5, 3, key=f"value_{activity_type}")
                
                components[activity_type] = {
                    'category': 'support',
                    'content': content,
                    'strength': strength,
                    'improvements': improvements,
                    'cost_impact': float(cost_impact),
                    'value_impact': float(value_impact)
                }
                st.markdown('</div>', unsafe_allow_html=True)
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title:
                st.error("분석 제목을 입력해주세요.")
                return
            
            success, result = save_value_chain(title, description, components)
            if success:
                st.success("Value Chain 분석이 성공적으로 저장되었습니다!")
                st.balloons()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 Value Chain 분석 목록")
        
        analyses = get_value_chain_list()
        if not analyses:
            st.info("저장된 Value Chain 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                
                analysis_data, components = load_value_chain(analysis['analysis_id'])
                if components:
                    # 주요 활동 표시
                    st.markdown("### 🔄 주요 활동")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 주요 활동 (Primary Activities)")
                        primary_activities = ['inbound_logistics', 'operations', 'outbound_logistics', 
                                           'marketing_sales', 'service']
                        for activity in primary_activities:
                            if activity in components:
                                st.markdown(f"**{activity.replace('_', ' ').title()}**")
                                st.markdown(f"내용: {components[activity].get('content', '')}")
                                st.markdown(f"비용 영향: {components[activity].get('cost_impact', '')}")
                                st.markdown(f"가치 영향: {components[activity].get('value_impact', '')}")
                    
                    with col2:
                        st.markdown("#### 지원 활동 (Support Activities)")
                        support_activities = ['firm_infrastructure', 'hr_management', 
                                           'technology_development', 'procurement']
                        for activity in support_activities:
                            if activity in components:
                                st.markdown(f"**{activity.replace('_', ' ').title()}**")
                                st.markdown(f"내용: {components[activity].get('content', '')}")
                                st.markdown(f"비용 영향: {components[activity].get('cost_impact', '')}")
                                st.markdown(f"가치 영향: {components[activity].get('value_impact', '')}")
                    
                    # 시각화 섹션
                    st.markdown("### 📈 시각화")
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        # Value Chain 매트릭스
                        st.plotly_chart(create_value_chain_matrix(components), use_container_width=True)
                    
                    with col4:
                        # 활동별 영향도 분석
                        impact_fig = go.Figure()
                        
                        activities = []
                        cost_impacts = []
                        value_impacts = []
                        
                        for activity, data in components.items():
                            activities.append(activity.replace('_', ' ').title())
                            cost_impacts.append(float(data.get('cost_impact', 0)))
                            value_impacts.append(float(data.get('value_impact', 0)))
                        
                        impact_fig.add_trace(go.Bar(
                            name='비용 영향',
                            x=activities,
                            y=cost_impacts,
                            marker_color='#e74c3c'
                        ))
                        
                        impact_fig.add_trace(go.Bar(
                            name='가치 영향',
                            x=activities,
                            y=value_impacts,
                            marker_color='#2ecc71'
                        ))
                        
                        impact_fig.update_layout(
                            title="활동별 비용/가치 영향도",
                            barmode='group',
                            xaxis_tickangle=-45
                        )
                        
                        st.plotly_chart(impact_fig, use_container_width=True)
                    
                    # AI 분석 섹션
                    st.markdown("### 🤖 AI 분석")
                    if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                        with st.spinner("AI가 분석을 진행 중입니다..."):
                            analysis_data = {
                                'title': analysis['title'],
                                'description': analysis['description'],
                                'activities': {
                                    k: {
                                        'content': v['content'],
                                        'cost_impact': v['cost_impact'],
                                        'value_impact': v['value_impact']
                                    } for k, v in components.items()
                                }
                            }
                            insights = get_ai_insights("Value Chain", analysis_data)
                            st.markdown(insights)

def show_gap_analysis():
    """Gap 분석 도구 표시"""
    st.header("🔍 Gap 분석")
    
    # 탭 설정
    tab1, tab2 = st.tabs(["새 분석 작성", "저장된 분석"])
    
    with tab1:
        create_gap_analysis()
    
    with tab2:
        # 저장된 분석 목록 조회
        analyses = get_gap_analysis_list()  # 함수 이름 수정
        
        if analyses:
            selected_analysis = st.selectbox(
                "저장된 Gap 분석",
                analyses,
                format_func=lambda x: f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d')})"
            )
            
            if selected_analysis:
                display_gap_analysis(selected_analysis['analysis_id'])
        else:
            st.info("저장된 Gap 분석이 없습니다.")

def show_blue_ocean():
    tab1, tab2 = st.tabs(["Blue Ocean 전략 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 Blue Ocean 전략 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="Blue Ocean 전략 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        industry = st.text_input("산업 분야", placeholder="분석 대상 산업을 입력하세요")
        
        # 4 Actions Framework
        st.markdown("### 4 Actions Framework")
        
        actions = {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Eliminate
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">🗑️ 제거 (Eliminate)</p>', unsafe_allow_html=True)
            eliminate_items = []
            for i in range(3):
                with st.expander(f"제거 항목 {i+1}", expanded=True):
                    factor = st.text_input("제거할 요소", key=f"eliminate_factor_{i}")
                    description = st.text_area("상세 설명", key=f"eliminate_desc_{i}")
                    impact = st.slider("영향도", 1, 5, 3, key=f"eliminate_impact_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"eliminate_priority_{i}")
                    eliminate_items.append({
                        'factor': factor,
                        'description': description,
                        'impact': impact,
                        'priority': priority
                    })
            actions['eliminate'] = eliminate_items
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Raise
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">⬆️ 증가 (Raise)</p>', unsafe_allow_html=True)
            raise_items = []
            for i in range(3):
                with st.expander(f"증가 항목 {i+1}", expanded=True):
                    factor = st.text_input("증가할 요소", key=f"raise_factor_{i}")
                    description = st.text_area("상세 설명", key=f"raise_desc_{i}")
                    impact = st.slider("영향도", 1, 5, 3, key=f"raise_impact_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"raise_priority_{i}")
                    raise_items.append({
                        'factor': factor,
                        'description': description,
                        'impact': impact,
                        'priority': priority
                    })
            actions['raise'] = raise_items
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            # Reduce
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">⬇️ 감소 (Reduce)</p>', unsafe_allow_html=True)
            reduce_items = []
            for i in range(3):
                with st.expander(f"감소 항목 {i+1}", expanded=True):
                    factor = st.text_input("감소할 요소", key=f"reduce_factor_{i}")
                    description = st.text_area("상세 설명", key=f"reduce_desc_{i}")
                    impact = st.slider("영향도", 1, 5, 3, key=f"reduce_impact_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"reduce_priority_{i}")
                    reduce_items.append({
                        'factor': factor,
                        'description': description,
                        'impact': impact,
                        'priority': priority
                    })
            actions['reduce'] = reduce_items
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Create
            st.markdown('<div class="canvas-block">', unsafe_allow_html=True)
            st.markdown('<p class="canvas-title">✨ 창조 (Create)</p>', unsafe_allow_html=True)
            create_items = []
            for i in range(3):
                with st.expander(f"창조 항목 {i+1}", expanded=True):
                    factor = st.text_input("창조할 요소", key=f"create_factor_{i}")
                    description = st.text_area("상세 설명", key=f"create_desc_{i}")
                    impact = st.slider("영향도", 1, 5, 3, key=f"create_impact_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"create_priority_{i}")
                    create_items.append({
                        'factor': factor,
                        'description': description,
                        'impact': impact,
                        'priority': priority
                    })
            actions['create'] = create_items
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Strategy Canvas
        st.markdown("### Strategy Canvas")
        
        if 'canvas_factors' not in st.session_state:
            st.session_state.canvas_factors = [{}]
        
        if st.button("➕ 경쟁 요소 추가"):
            st.session_state.canvas_factors.append({})
            st.rerun()
        
        canvas_factors = []
        for i, _ in enumerate(st.session_state.canvas_factors):
            col1, col2, col3, col4 = st.columns([2,1,1,1])
            
            with col1:
                name = st.text_input("경쟁 요소", key=f"factor_name_{i}")
            with col2:
                industry_score = st.slider("산업 평균", 1, 10, 5, key=f"industry_{i}")
            with col3:
                company_score = st.slider("자사", 1, 10, 5, key=f"company_{i}")
            with col4:
                if st.button("🗑️", key=f"delete_factor_{i}"):
                    st.session_state.canvas_factors.pop(i)
                    st.rerun()
            
            description = st.text_area("설명", key=f"factor_desc_{i}")
            
            canvas_factors.append({
                'name': name,
                'industry_score': industry_score,
                'company_score': company_score,
                'description': description
            })
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title or not industry:
                st.error("제목과 산업 분야를 입력해주세요.")
                return
            
            success, result = save_blue_ocean(title, description, industry, actions, canvas_factors)
            if success:
                st.success("Blue Ocean 전략 분석이 성공적으로 저장되었습니다!")
                st.balloons()
                st.session_state.canvas_factors = [{}]
                st.rerun()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")
    
    with tab2:
        st.markdown("### 저장된 Blue Ocean 전략 분석 목록")
        
        analyses = get_blue_ocean_list()
        if not analyses:
            st.info("저장된 Blue Ocean 전략 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                st.markdown(f"**산업:** {analysis['industry']}")
                
                analysis_data, actions, canvas = load_blue_ocean(analysis['analysis_id'])
                
                # 4 Actions Framework 표시
                st.markdown("### 4 Actions Framework")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🗑️ 제거 (Eliminate)")
                    for item in actions.get('eliminate', []):
                        st.markdown(f"- {item['factor']}")
                        st.markdown(f"  영향도: {item['impact']}, 우선순위: {item['priority']}")
                    
                    st.markdown("#### ⬆️ 증가 (Raise)")
                    for item in actions.get('raise', []):
                        st.markdown(f"- {item['factor']}")
                        st.markdown(f"  영향도: {item['impact']}, 우선순위: {item['priority']}")
                
                with col2:
                    st.markdown("#### ⬇️ 감소 (Reduce)")
                    for item in actions.get('reduce', []):
                        st.markdown(f"- {item['factor']}")
                        st.markdown(f"  영향도: {item['impact']}, 우선순위: {item['priority']}")
                    
                    st.markdown("#### ✨ 창조 (Create)")
                    for item in actions.get('create', []):
                        st.markdown(f"- {item['factor']}")
                        st.markdown(f"  영향도: {item['impact']}, 우선순위: {item['priority']}")
                
                # 시각화 섹션
                st.markdown("### 📈 시각화")
                col3, col4 = st.columns(2)
                
                with col3:
                    # Strategy Canvas 차트
                    canvas_fig = go.Figure()
                    
                    # 산업 평균 라인
                    canvas_fig.add_trace(go.Scatter(
                        x=[factor['name'] for factor in canvas],
                        y=[factor['industry_score'] for factor in canvas],
                        name='산업 평균',
                        line=dict(color='#e74c3c')
                    ))
                    
                    # 자사 라인
                    canvas_fig.add_trace(go.Scatter(
                        x=[factor['name'] for factor in canvas],
                        y=[factor['company_score'] for factor in canvas],
                        name='자사',
                        line=dict(color='#2ecc71')
                    ))
                    
                    canvas_fig.update_layout(
                        title="Strategy Canvas",
                        xaxis_title="경쟁 요소",
                        yaxis_title="수준",
                        showlegend=True
                    )
                    
                    st.plotly_chart(canvas_fig, use_container_width=True)
                
                with col4:
                    # 4 Actions 영향도 분석
                    impact_data = {
                        'Eliminate': np.mean([item['impact'] for item in actions.get('eliminate', [])]),
                        'Reduce': np.mean([item['impact'] for item in actions.get('reduce', [])]),
                        'Raise': np.mean([item['impact'] for item in actions.get('raise', [])]),
                        'Create': np.mean([item['impact'] for item in actions.get('create', [])])
                    }
                    
                    impact_fig = go.Figure(data=[go.Bar(
                        x=list(impact_data.keys()),
                        y=list(impact_data.values()),
                        marker_color=['#e74c3c', '#f1c40f', '#2ecc71', '#3498db']
                    )])
                    
                    impact_fig.update_layout(
                        title="4 Actions 평균 영향도",
                        yaxis_title="영향도",
                        showlegend=False
                    )
                    
                    st.plotly_chart(impact_fig, use_container_width=True)
                
                # AI 분석 섹션
                st.markdown("### 🤖 AI 분석")
                if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                    with st.spinner("AI가 분석을 진행 중입니다..."):
                        analysis_data = {
                            'title': analysis['title'],
                            'description': analysis['description'],
                            'industry': analysis['industry'],
                            'actions': actions,
                            'canvas_factors': canvas
                        }
                        insights = get_ai_insights("Blue Ocean", analysis_data)
                        st.markdown(insights)

def show_innovators_dilemma():
    tab1, tab2 = st.tabs(["Innovator's Dilemma 분석 작성", "저장된 분석"])
    
    with tab1:
        st.markdown("### 새로운 Innovator's Dilemma 분석")
        
        # 기본 정보 입력
        title = st.text_input("분석 제목", placeholder="Innovator's Dilemma 분석의 제목을 입력하세요")
        description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
        industry = st.text_input("산업 분야", placeholder="분석 대상 산업을 입력하세요")
        
        # 현재 기술/제품 분석
        st.markdown("### 현재 기술/제품 분석")
        
        if 'current_tech_items' not in st.session_state:
            st.session_state.current_tech_items = [{}]
        
        if st.button("➕ 현재 기술/제품 추가"):
            st.session_state.current_tech_items.append({})
            st.rerun()
        
        current_tech = []
        for i, _ in enumerate(st.session_state.current_tech_items):
            with st.expander(f"현재 기술/제품 {i+1}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("기술/제품명", key=f"current_name_{i}")
                    description = st.text_area("설명", key=f"current_desc_{i}")
                    position = st.selectbox("시장 포지션",
                                         ['low', 'mid', 'high'],
                                         key=f"current_position_{i}")
                    performance = st.slider("성능 수준", 1, 10, 3, key=f"current_performance_{i}")
                
                with col2:
                    demand = st.slider("고객 수요", 1, 10, 5, key=f"current_demand_{i}")
                    market_size = st.number_input("시장 규모(억원)", 0.0, 10000.0, 100.0, key=f"current_market_{i}")
                    profit_margin = st.number_input("이익률(%)", 0.0, 100.0, 20.0, key=f"current_profit_{i}")
                
                if st.button("🗑️ 항목 삭제", key=f"delete_current_{i}"):
                    st.session_state.current_tech_items.pop(i)
                    st.rerun()
                
                current_tech.append({
                    'name': name,
                    'description': description,
                    'position': position,
                    'performance': performance,
                    'demand': demand,
                    'market_size': float(market_size),
                    'profit_margin': float(profit_margin)
                })
        
        # 파괴적 혁신 분석
        st.markdown("### 파괴적 혁신 분석")
        
        if 'disruptive_tech_items' not in st.session_state:
            st.session_state.disruptive_tech_items = [{}]
        
        if st.button("➕ 파괴적 혁신 추가"):
            st.session_state.disruptive_tech_items.append({})
            st.rerun()
        
        disruptive_tech = []
        for i, _ in enumerate(st.session_state.disruptive_tech_items):
            with st.expander(f"파괴적 혁신 {i+1}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("기술/제품명", key=f"disruptive_name_{i}")
                    description = st.text_area("설명", key=f"disruptive_desc_{i}")
                    innovation_type = st.selectbox("혁신 유형",
                                                ['low_end', 'new_market'],
                                                key=f"disruptive_type_{i}")
                    performance = st.slider("현재 성능 수준", 1, 10, 3, key=f"disruptive_performance_{i}")
                
                with col2:
                    growth_rate = st.number_input("예상 성장률(%)", 0.0, 1000.0, 50.0, key=f"disruptive_growth_{i}")
                    market_size = st.number_input("잠재 시장 규모(억원)", 0.0, 10000.0, 500.0, key=f"disruptive_market_{i}")
                    status = st.selectbox("개발 단계",
                                       ['research', 'development', 'testing', 'market_entry'],
                                       key=f"disruptive_status_{i}")
                    risk = st.selectbox("위험 수준",
                                     ['low', 'medium', 'high'],
                                     key=f"disruptive_risk_{i}")
                
                if st.button("🗑️ 삭제", key=f"delete_disruptive_{i}"):
                    st.session_state.disruptive_tech_items.pop(i)
                    st.rerun()
                
                disruptive_tech.append({
                    'name': name,
                    'description': description,
                    'type': innovation_type,
                    'performance': performance,
                    'growth_rate': float(growth_rate),
                    'market_size': float(market_size),
                    'status': status,
                    'risk': risk
                })
        
        # 대응 전략
        st.markdown("### 대응 전략")
        
        if 'strategy_items' not in st.session_state:
            st.session_state.strategy_items = [{}]
        
        if st.button("➕ 전략 추가"):
            st.session_state.strategy_items.append({})
            st.rerun()
        
        strategies = []
        for i, _ in enumerate(st.session_state.strategy_items):
            with st.expander(f"전략 {i+1}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    strategy_type = st.selectbox("전략 유형",
                                              ['defend', 'adapt', 'disrupt'],
                                              key=f"strategy_type_{i}")
                    description = st.text_area("전략 설명", key=f"strategy_desc_{i}")
                    plan = st.text_area("실행 계획", key=f"strategy_plan_{i}")
                
                with col2:
                    resources = st.text_area("필요 자원", key=f"strategy_resources_{i}")
                    timeline = st.text_input("실행 일정", key=f"strategy_timeline_{i}")
                    metrics = st.text_area("성과 지표", key=f"strategy_metrics_{i}")
                    priority = st.number_input("우선순위", 1, 10, i+1, key=f"strategy_priority_{i}")
                
                if st.button("🗑️ 삭제", key=f"delete_strategy_{i}"):
                    st.session_state.strategy_items.pop(i)
                    st.rerun()
                
                strategies.append({
                    'type': strategy_type,
                    'description': description,
                    'plan': plan,
                    'resources': resources,
                    'timeline': timeline,
                    'metrics': metrics,
                    'priority': priority
                })
        
        # 저장 버튼
        if st.button("분석 저장", type="primary", use_container_width=True):
            if not title or not industry:
                st.error("제목과 산업 분야를 입력해주세요.")
                return
            
            success, result = save_innovators_dilemma(title, description, industry,
                                                        current_tech, disruptive_tech, strategies)
            if success:
                st.success("Innovator's Dilemma 분석이 성공적으로 저장되었습니다!")
                st.balloons()
                # 입력 폼 초기화
                st.session_state.current_tech_items = [{}]
                st.session_state.disruptive_tech_items = [{}]
                st.session_state.strategy_items = [{}]
                st.rerun()
            else:
                st.error(f"저장 중 오류가 발생했습니다: {result}")

    with tab2:
        st.markdown("### 저장된 Innovator's Dilemma 분석 목록")
        
        analyses = get_innovators_dilemma_list()
        if not analyses:
            st.info("저장된 Innovator's Dilemma 분석이 없습니다.")
            return
        
        for analysis in analyses:
            with st.expander(f"📊 {analysis['title']} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})"):
                if analysis['description']:
                    st.markdown(f"**설명:** {analysis['description']}")
                st.markdown(f"**산업:** {analysis['industry']}")
                
                analysis_data, current_tech, disruptive_tech, strategies = load_innovators_dilemma(analysis['analysis_id'])
                
                # 현재 기술/제품 표시
                st.markdown("### 현재 기술/제품")
                for tech in current_tech:
                    st.markdown(f"#### {tech['name']}")
                    st.markdown(f"**설명:** {tech['description']}")
                    st.markdown(f"**시장 포지션:** {tech['position']}")
                    st.markdown(f"**성능 수준:** {tech['performance']}")
                    st.markdown(f"**고객 수요:** {tech['demand']}")
                    st.markdown(f"**시장 규모:** {tech['market_size']}억원")
                    st.markdown(f"**이익률:** {tech['profit_margin']}%")
                
                # 파괴적 혁신 표시
                st.markdown("### 파괴적 혁신")
                for tech in disruptive_tech:
                    st.markdown(f"#### {tech['name']}")
                    st.markdown(f"**설명:** {tech['description']}")
                    st.markdown(f"**혁신 유형:** {tech['type']}")
                    st.markdown(f"**현재 성능:** {tech['performance']}")
                    st.markdown(f"**예상 성장률:** {tech['growth_rate']}%")
                    st.markdown(f"**잠재 시장:** {tech['market_size']}억원")
                    st.markdown(f"**개발 단계:** {tech['status']}")
                    st.markdown(f"**위험 수준:** {tech['risk']}")
                
                # 시각화 섹션
                st.markdown("### 📈 시각화")
                col1, col2 = st.columns(2)
                
                with col1:
                    # 성능-시장 매트릭스
                    performance_fig = go.Figure()
                    
                    # 현재 기술
                    performance_fig.add_trace(go.Scatter(
                        x=[tech['performance'] for tech in current_tech],
                        y=[tech['market_size'] for tech in current_tech],
                        mode='markers+text',
                        name='현재 기술',
                        text=[tech['name'] for tech in current_tech],
                        marker=dict(size=15, color='#3498db')
                    ))
                    
                    # 파괴적 혁신
                    performance_fig.add_trace(go.Scatter(
                        x=[tech['performance'] for tech in disruptive_tech],
                        y=[tech['market_size'] for tech in disruptive_tech],
                        mode='markers+text',
                        name='파괴적 혁신',
                        text=[tech['name'] for tech in disruptive_tech],
                        marker=dict(size=15, color='#e74c3c')
                    ))
                    
                    performance_fig.update_layout(
                        title="성능-시장 매트릭스",
                        xaxis_title="성능 수준",
                        yaxis_title="시장 규모(억원)",
                        showlegend=True
                    )
                    
                    st.plotly_chart(performance_fig, use_container_width=True)
                
                with col2:
                    # 전략 우선순위 분석
                    strategy_fig = go.Figure()
                    
                    strategy_types = ['defend', 'adapt', 'disrupt']
                    strategy_counts = {t: len([s for s in strategies if s['type'] == t]) for t in strategy_types}
                    
                    strategy_fig.add_trace(go.Bar(
                        x=list(strategy_counts.keys()),
                        y=list(strategy_counts.values()),
                        marker_color=['#2ecc71', '#f1c40f', '#e74c3c']
                    ))
                    
                    strategy_fig.update_layout(
                        title="전략 유형별 분포",
                        xaxis_title="전략 유형",
                        yaxis_title="전략 수",
                        showlegend=False
                    )
                    
                    st.plotly_chart(strategy_fig, use_container_width=True)
                
                # AI 분석 섹션
                st.markdown("### 🤖 AI 분석")
                if st.button("AI 분석 시작", key=f"ai_button_{analysis['analysis_id']}"):
                    with st.spinner("AI가 분석을 진행 중입니다..."):
                        analysis_data = {
                            'title': analysis['title'],
                            'description': analysis['description'],
                            'industry': analysis['industry'],
                            'current_tech': current_tech,
                            'disruptive_tech': disruptive_tech,
                            'strategies': strategies
                        }
                        insights = get_ai_insights("Innovator's Dilemma", analysis_data)
                        st.markdown(insights)

def get_ai_insights(analysis_type, data):
    """AI 기반 분석 인사이트 생성"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        messages = [
            {"role": "system", "content": """
             당신은 경영 전략 전문가입니다. 비즈니스 분석 데이터를 기반으로 
             실용적이고 구체적인 인사이트와 추천 사항을 제공해주세요.
             """},
            {"role": "user", "content": f"""
            다음 {analysis_type} 분석 데이터를 검토하고 주요 인사이트와 
            실행 가능한 추천 사항을 제시해주세요:
            
            {data}
            
            다음 형식으로 답변해주세요:
            
            주요 인사이트:
            1. ...
            2. ...
            3. ...
            
            개선 기회:
            1. ...
            2. ...
            
            우선순위 실행 과제:
            1. ...
            2. ...
            3. ...
            """}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        if hasattr(response.choices[0].message, 'content'):
            return response.choices[0].message.content
        else:
            st.error("API 응답에 content가 없습니다.")
            return None
            
    except Exception as e:
        st.error(f"AI 인사이트 생성 중 오류가 발생했습니다: {str(e)}")
        return None

def show_ai_insights(analysis_type, data):
    """AI 인사이트 표시"""
    with st.expander("🤖 AI 분석 인사이트", expanded=True):
        if st.button("AI 인사이트 생성"):
            with st.spinner("AI가 분석을 진행 중입니다..."):
                insights = get_ai_insights(analysis_type, data)
                st.markdown(insights)

def create_swot_chart(items):
    """SWOT 분석 결과를 시각화"""
    # 각 항목의 개수를 계산
    counts = {
        'Strengths': len([x for x in items['strength'] if x.strip()]),
        'Weaknesses': len([x for x in items['weakness'] if x.strip()]),
        'Opportunities': len([x for x in items['opportunity'] if x.strip()]),
        'Threats': len([x for x in items['threat'] if x.strip()])
    }
    
    # 색상 설정
    colors = ['#2ecc71', '#e74c3c', '#3498db', '#f1c40f']
    
    # 차트 생성
    fig = go.Figure(data=[go.Bar(
        x=list(counts.keys()),
        y=list(counts.values()),
        marker_color=colors
    )])
    
    fig.update_layout(
        title="SWOT 분석 요소 분포",
        xaxis_title="SWOT 요소",
        yaxis_title="항목 수",
        showlegend=False
    )
    
    return fig

def create_pestel_radar(components):
    """PESTEL 분석 결과를 레이더 차트로 시각화"""
    categories = []
    impact_scores = []
    trend_scores = {'decreasing': -1, 'stable': 0, 'increasing': 1}
    
    for component_type, data in components.items():
        categories.append(component_type.upper())
        # 영향도를 수치화 (low=1, medium=2, high=3)
        impact = {'low': 1, 'medium': 2, 'high': 3}[data['impact']]
        impact_scores.append(impact)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=impact_scores,
        theta=categories,
        fill='toself',
        name='Impact Level'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 3]
            )),
        showlegend=True,
        title="PESTEL 분석 영향도"
    )
    
    return fig

def create_five_forces_chart(components):
    """5 Forces 분석 결과를 방사형 차트로 시각화"""
    threat_levels = {
        'very_low': 1,
        'low': 2,
        'medium': 3,
        'high': 4,
        'very_high': 5
    }
    
    categories = []
    scores = []
    
    for force, data in components.items():
        categories.append(force.replace('_', ' ').title())
        scores.append(threat_levels[data['threat_level']])
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=scores,
        theta=categories,
        fill='toself',
        name='Threat Level'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 5]
            )),
        showlegend=True,
        title="Porter's 5 Forces Analysis"
    )
    
    return fig

def create_value_chain_matrix(components):
    """Value Chain 분석 결과를 매트릭스로 시각화"""
    activities = []
    cost_impacts = []
    value_impacts = []
    
    for activity_type, data in components.items():
        activities.append(activity_type.replace('_', ' ').title())
        cost_impacts.append(data['cost_impact'])
        value_impacts.append(data['value_impact'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=cost_impacts,
        y=value_impacts,
        mode='markers+text',
        text=activities,
        textposition="top center",
        marker=dict(
            size=15,
            color=np.arange(len(activities)),
            colorscale='Viridis',
            showscale=True
        )
    ))
    
    fig.update_layout(
        title="Value Chain Impact Matrix",
        xaxis_title="Cost Impact",
        yaxis_title="Value Impact",
        showlegend=False
    )
    
    return fig

def get_five_forces_list():
    """저장된 5 Forces 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, created_at, status
            FROM five_forces_analysis
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def load_five_forces(analysis_id):
    """5 Forces 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 메인 5 Forces 정보 로드
        cursor.execute("""
            SELECT * FROM five_forces_analysis WHERE analysis_id = %s
        """, (analysis_id,))
        analysis = cursor.fetchone()
        
        # 5 Forces 컴포넌트 로드
        cursor.execute("""
            SELECT * FROM five_forces_components WHERE analysis_id = %s
        """, (analysis_id,))
        components = {row['component_type']: {
            'content': row['content'],
            'threat_level': row['threat_level'],
            'key_factors': row['key_factors'],
            'recommendations': row['recommendations']
        } for row in cursor.fetchall()}
        
        return analysis, components
    except Exception as e:
        st.error(f"5 Forces 분석 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def get_blue_ocean_list():
    """저장된 Blue Ocean 전략 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'blue_ocean'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Blue Ocean 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def load_blue_ocean(analysis_id):
    """Blue Ocean 전략 분석 데이터 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 분석 정보 조회
        cursor.execute("""
            SELECT * FROM business_analysis 
            WHERE analysis_id = %s AND analysis_type = 'blue_ocean'
        """, (analysis_id,))
        analysis_data = cursor.fetchone()
        
        # 4 Actions Framework 데이터 조회
        cursor.execute("""
            SELECT * FROM blue_ocean_actions 
            WHERE analysis_id = %s 
            ORDER BY action_type, priority
        """, (analysis_id,))
        actions_data = cursor.fetchall()
        
        # Strategy Canvas 데이터 조회
        cursor.execute("""
            SELECT * FROM blue_ocean_canvas 
            WHERE analysis_id = %s
        """, (analysis_id,))
        canvas_data = cursor.fetchall()
        
        # 4 Actions 데이터 구조화
        actions = {
            'eliminate': [],
            'reduce': [],
            'raise': [],
            'create': []
        }
        
        for action in actions_data:
            actions[action['action_type']].append({
                'factor': action['factor'],
                'description': action['description'],
                'impact': action['impact'],
                'priority': action['priority']
            })
        
        return analysis_data, actions, canvas_data
    except Exception as e:
        st.error(f"Blue Ocean 분석 데이터 로드 중 오류 발생: {str(e)}")
        return None, None, None
    finally:
        cursor.close()
        conn.close()

def get_pestel_list():
    """저장된 PESTEL 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'pestel'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"PESTEL 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def save_pestel(title, description, industry, components):
    """PESTEL 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기본 분석 정보 저장
        cursor.execute("""
            INSERT INTO business_analysis 
            (analysis_type, title, description, industry) 
            VALUES ('pestel', %s, %s, %s)
        """, (title, description, industry))
        
        analysis_id = cursor.lastrowid
        
        # PESTEL 요소 저장
        for component_type, data in components.items():
            cursor.execute("""
                INSERT INTO pestel_components 
                (analysis_id, component_type, content, impact, trend, recommendations) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                analysis_id,
                component_type,
                data['content'],
                data['impact'],
                data['trend'],
                data['recommendations']
            ))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_pestel(analysis_id):
    """PESTEL 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 분석 정보 조회
        cursor.execute("""
            SELECT * FROM business_analysis 
            WHERE analysis_id = %s AND analysis_type = 'pestel'
        """, (analysis_id,))
        analysis_data = cursor.fetchone()
        
        # PESTEL 컴포넌트 조회
        cursor.execute("""
            SELECT * FROM pestel_components 
            WHERE analysis_id = %s
        """, (analysis_id,))
        components = {row['component_type']: {
            'content': row['content'],
            'impact': row['impact'],
            'trend': row['trend'],
            'recommendations': row['recommendations']
        } for row in cursor.fetchall()}
        
        return analysis_data, components
    except Exception as e:
        st.error(f"PESTEL 분석 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def get_value_chain_list():
    """저장된 Value Chain 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'value_chain'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Value Chain 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_gap_analysis_list():
    """저장된 Gap 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'gap'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Gap 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_innovators_dilemma_list():
    """저장된 Innovator's Dilemma 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'innovators_dilemma'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Innovator's Dilemma 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_portfolio_analysis_list():
    """저장된 Portfolio 분석 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT analysis_id, title, description, industry, created_at
            FROM business_analysis
            WHERE analysis_type = 'portfolio'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Portfolio 분석 목록 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_gap_list():
    """저장된 Gap 분석 목록 조회 (별칭 함수)"""
    return get_gap_analysis_list()

def get_portfolio_list():
    """저장된 Portfolio 분석 목록 조회 (별칭 함수)"""
    return get_portfolio_analysis_list()

def get_innovators_list():
    """저장된 Innovator's Dilemma 분석 목록 조회 (별칭 함수)"""
    return get_innovators_dilemma_list()

def get_value_list():
    """저장된 Value Chain 분석 목록 조회 (별칭 함수)"""
    return get_value_chain_list()

def create_gap_analysis():
    """Gap 분석 작성 폼"""
    st.markdown("### 새로운 Gap 분석")
    
    # 기본 정보 입력
    title = st.text_input("분석 제목", placeholder="Gap 분석의 제목을 입력하세요")
    description = st.text_area("설명", placeholder="분석 대상에 대한 간단한 설명을 입력하세요")
    industry = st.text_input("산업/분야", placeholder="관련 산업이나 분야를 입력하세요")
    
    # Gap 항목 입력
    st.markdown("### Gap 분석 항목")
    
    # 분석 항목 추가 버튼
    if 'gap_items' not in st.session_state:
        st.session_state.gap_items = [{}]
    
    if st.button("➕ 분석 항목 추가"):
        st.session_state.gap_items.append({})
        st.rerun()
    
    items = []
    for i, _ in enumerate(st.session_state.gap_items):
        with st.expander(f"분석 항목 {i+1}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                category = st.text_input("카테고리", 
                                       placeholder="예: 기술, 프로세스, 인력 등",
                                       key=f"category_{i}")
                current_state = st.text_area("현재 상태",
                                           placeholder="현재 상황을 설명하세요",
                                           key=f"current_{i}")
                desired_state = st.text_area("목표 상태",
                                           placeholder="달성하고자 하는 상태를 설명하세요",
                                           key=f"desired_{i}")
                gap_description = st.text_area("차이점 분석",
                                             placeholder="현재와 목표 상태의 차이를 분석하세요",
                                             key=f"gap_{i}")
            
            with col2:
                priority = st.select_slider("우선순위",
                                          options=['low', 'medium', 'high'],
                                          key=f"priority_{i}")
                action_plan = st.text_area("실행 계획",
                                         placeholder="차이를 줄이기 위한 구체적인 계획",
                                         key=f"action_{i}")
                timeline = st.text_input("일정",
                                      placeholder="예: 2024년 Q2",
                                      key=f"timeline_{i}")
                resources = st.text_area("필요 자원",
                                       placeholder="필요한 인력, 예산, 기술 등",
                                       key=f"resources_{i}")
                metrics = st.text_area("성과 지표",
                                     placeholder="진행 상황을 측정할 지표",
                                     key=f"metrics_{i}")
            
            if st.button("🗑️ 항목 삭제", key=f"delete_{i}"):
                st.session_state.gap_items.pop(i)
                st.rerun()
            
            items.append({
                'category': category,
                'current_state': current_state,
                'desired_state': desired_state,
                'gap_description': gap_description,
                'priority': priority,
                'action_plan': action_plan,
                'timeline': timeline,
                'resources': resources,
                'metrics': metrics
            })
    
    # 저장 버튼
    if st.button("분석 저장", type="primary", use_container_width=True):
        if not title:
            st.error("분석 제목을 입력해주세요.")
            return
        
        if not items or not any(item.get('category') for item in items):
            st.error("최소 하나의 분석 항목을 입력해주세요.")
            return
        
        success, result = save_gap_analysis(title, description, industry, items)
        if success:
            st.success("Gap 분석이 성공적으로 저장되었습니다!")
            st.balloons()
            st.session_state.gap_items = [{}]  # 초기화
            st.rerun()
        else:
            st.error(f"저장 중 오류가 발생했습니다: {result}")

def display_gap_analysis(analysis_id):
    """저장된 Gap 분석 표시"""
    analysis_data, items = load_gap_analysis(analysis_id)
    
    if not analysis_data or not items:
        st.error("Gap 분석 데이터를 불러올 수 없습니다.")
        return
    
    st.markdown(f"## {analysis_data['title']}")
    
    if analysis_data['description']:
        st.markdown(f"**설명:** {analysis_data['description']}")
    
    if analysis_data['industry']:
        st.markdown(f"**산업/분야:** {analysis_data['industry']}")
    
    # 항목별 상세 내용 표시
    for i, item in enumerate(items):
        st.markdown(f"### 분석 항목 {i+1}: {item['category']}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**현재 상태:**")
            st.markdown(item['current_state'])
            st.markdown("**목표 상태:**")
            st.markdown(item['desired_state'])
        
        with col2:
            st.markdown("**차이점 분석:**")
            st.markdown(item['gap_description'])
            st.markdown("**우선순위:** " + item['priority'])
    
    # 시각화 섹션
    st.markdown("### 📈 시각화")
    col3, col4 = st.columns(2)
    
    with col3:
        # 우선순위별 분포 차트
        priority_counts = {
            'high': len([x for x in items if x['priority'] == 'high']),
            'medium': len([x for x in items if x['priority'] == 'medium']),
            'low': len([x for x in items if x['priority'] == 'low'])
        }
        
        priority_fig = go.Figure(data=[go.Bar(
            x=list(priority_counts.keys()),
            y=list(priority_counts.values()),
            marker_color=['#e74c3c', '#f1c40f', '#2ecc71']
        )])
        
        priority_fig.update_layout(
            title="우선순위별 Gap 분포",
            xaxis_title="우선순위",
            yaxis_title="항목 수"
        )
        
        st.plotly_chart(priority_fig, use_container_width=True)
    
    with col4:
        # 카테고리별 타임라인 차트
        timeline_data = []
        for item in items:
            if item['timeline']:
                timeline_data.append({
                    'Category': item['category'],
                    'Timeline': item['timeline'],
                    'Priority': item['priority']
                })
        
        if timeline_data:
            timeline_df = pd.DataFrame(timeline_data)
            timeline_fig = px.timeline(
                timeline_df,
                x_start='Timeline',
                y='Category',
                color='Priority',
                title="실행 계획 타임라인"
            )
            st.plotly_chart(timeline_fig, use_container_width=True)
    
    # AI 분석 섹션
    st.markdown("### 🤖 AI 분석")
    if st.button("AI 분석 시작", key=f"ai_button_{analysis_id}"):
        with st.spinner("AI가 분석을 진행 중입니다..."):
            analysis_data = {
                'title': analysis_data['title'],
                'description': analysis_data['description'],
                'gaps': [{
                    'category': item['category'],
                    'current_state': item['current_state'],
                    'desired_state': item['desired_state'],
                    'gap_description': item['gap_description'],
                    'priority': item['priority'],
                    'action_plan': item['action_plan'],
                    'timeline': item['timeline'],
                    'resources': item['resources'],
                    'metrics': item['metrics']
                } for item in items]
            }
            insights = get_ai_insights("GAP", analysis_data)
            st.markdown(insights)

def save_gap_analysis(title, description, industry, items):
    """Gap 분석 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기본 분석 정보 저장
        cursor.execute("""
            INSERT INTO business_analysis 
            (analysis_type, title, description, industry) 
            VALUES ('gap', %s, %s, %s)
        """, (title, description, industry))
        
        analysis_id = cursor.lastrowid
        
        # Gap 항목 저장
        for item in items:
            if item.get('category'):  # 카테고리가 있는 항목만 저장
                cursor.execute("""
                    INSERT INTO gap_analysis_items 
                    (analysis_id, category, current_state, desired_state, gap_description, 
                     priority, action_plan, timeline, resources, metrics) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    analysis_id,
                    item['category'],
                    item['current_state'],
                    item['desired_state'],
                    item['gap_description'],
                    item['priority'],
                    item['action_plan'],
                    item['timeline'],
                    item['resources'],
                    item['metrics']
                ))
        
        conn.commit()
        return True, analysis_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def load_gap_analysis(analysis_id):
    """Gap 분석 로드"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 분석 정보 조회
        cursor.execute("""
            SELECT * FROM business_analysis 
            WHERE analysis_id = %s AND analysis_type = 'gap'
        """, (analysis_id,))
        analysis_data = cursor.fetchone()
        
        # Gap 항목 조회
        cursor.execute("""
            SELECT * FROM gap_analysis_items 
            WHERE analysis_id = %s
        """, (analysis_id,))
        items = cursor.fetchall()
        
        return analysis_data, items
    except Exception as e:
        st.error(f"Gap 분석 로드 중 오류 발생: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 