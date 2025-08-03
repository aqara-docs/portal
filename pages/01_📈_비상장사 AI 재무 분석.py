import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import json
import base64
import requests
import graphviz
import plotly.express as px
import plotly.graph_objects as go
import mysql.connector
import dart_fss as dart_fss
import concurrent.futures

# 환경 변수 로드
load_dotenv()

# 페이지 설정 (반드시 첫 번째 Streamlit 명령어여야 함)
st.set_page_config(
    page_title="📈 비상장사 AI 재무 분석",
    page_icon="📈",
    layout="wide"
)
st.title("🎯 기업 가치 평가 시스템 (비상장사 + 실시간 AI)")

# 인증 기능
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

admin_pw = os.getenv('ADMIN_PASSWORD')
if not admin_pw:
    st.error('환경변수(ADMIN_PASSWORD)가 설정되어 있지 않습니다.')
    st.stop()

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == admin_pw:
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:
            st.error("관리자 권한이 필요합니다")
        st.stop()



# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# DART API 키 설정
dart_fss.set_api_key(api_key=os.getenv('DART_API_KEY'))

# MySQL Database configuration
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}



# 기본 환율 설정
DEFAULT_EXCHANGE_RATES = {
    'USD_KRW': 1350.0,  # USD to KRW
    'CNY_KRW': 190.0,   # CNY to KRW
    'JPY_KRW': 9.0,     # JPY to KRW
    'EUR_KRW': 1450.0   # EUR to KRW
}

# 환율 정보를 가져오는 함수
def get_exchange_rates():
    try:
        # 실제 API 호출로 대체 가능
        # response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
        # rates = response.json()['rates']
        # return rates
        return DEFAULT_EXCHANGE_RATES
    except:
        st.warning("환율 정보를 가져오는데 실패했습니다. 기본값을 사용합니다.")
        return DEFAULT_EXCHANGE_RATES

# DCF 계산 함수
def calculate_dcf(current_fcf, growth_rate, discount_rate, terminal_growth_rate, years=5):
    """
    DCF(Discounted Cash Flow) 모델을 사용하여 기업가치 계산
    
    Parameters:
    - current_fcf: 현재 잉여현금흐름(Free Cash Flow)
    - growth_rate: 예상 연간 성장률 (예: 0.05 = 5%)
    - discount_rate: 할인율 (예: 0.1 = 10%)
    - terminal_growth_rate: 영구 성장률 (예: 0.03 = 3%)
    - years: 예측 기간 (년)
    
    Returns:
    - 기업가치(현재가치)
    """
    future_fcfs = []
    for year in range(1, years + 1):
        future_fcf = current_fcf * (1 + growth_rate) ** year
        future_fcfs.append(future_fcf)
    
    # 각 미래 FCF의 현재가치 계산
    present_values = []
    for i, fcf in enumerate(future_fcfs):
        present_value = fcf / (1 + discount_rate) ** (i + 1)
        present_values.append(present_value)
    
    # 잔여가치(Terminal Value) 계산 - Gordon Growth Model
    terminal_value = future_fcfs[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    
    # 잔여가치의 현재가치
    terminal_value_pv = terminal_value / (1 + discount_rate) ** years
    
    # 총 기업가치 = 예측 기간 FCF의 현재가치 합계 + 잔여가치의 현재가치
    company_value = sum(present_values) + terminal_value_pv
    
    return {
        'company_value': company_value,
        'future_fcfs': future_fcfs,
        'present_values': present_values,
        'terminal_value': terminal_value,
        'terminal_value_pv': terminal_value_pv
    }

# PER 기반 가치 평가 함수
def calculate_per_valuation(net_income, pers):
    """
    PER(주가수익비율) 기반 기업가치 계산
    
    Parameters:
    - net_income: 당기순이익
    - pers: PER 배수 리스트 (예: [10, 15, 20])
    
    Returns:
    - PER별 기업가치 딕셔너리
    """
    per_valuations = {}
    for per in pers:
        valuation = net_income * per
        per_valuations[per] = valuation
    
    return per_valuations

# 무형자산 가치 평가 함수
def estimate_intangible_asset_value(r_and_d_cost, patents_count, trademarks_count, 
                                   technology_impact, market_size, market_share):
    """
    무형자산 가치 추정 함수
    
    Parameters:
    - r_and_d_cost: R&D 투자 비용
    - patents_count: 특허 개수
    - trademarks_count: 상표권 개수
    - technology_impact: 기술 영향력 (0~1)
    - market_size: 시장 규모
    - market_share: 시장 점유율 (0~1)
    
    Returns:
    - 추정 무형자산 가치
    """
    # 원가법 기반 가치
    cost_based_value = r_and_d_cost * 1.5  # 보수적인 R&D 투자 비용 기반 가치
    
    # 특허 및 상표권 기반 가치
    ip_value = (patents_count * 0.5 + trademarks_count * 0.3) * r_and_d_cost
    
    # 시장 기반 가치
    market_based_value = market_size * market_share * technology_impact
    
    # 가중 평균 가치 (각 방법론에 가중치 부여)
    weighted_value = (cost_based_value * 0.3) + (ip_value * 0.3) + (market_based_value * 0.4)
    
    return {
        'cost_based_value': cost_based_value,
        'ip_value': ip_value,
        'market_based_value': market_based_value,
        'weighted_value': weighted_value
    }

# 통화 변환 함수
def convert_currency(amount, from_currency, to_currency, exchange_rates):
    """
    통화 변환 함수
    
    Parameters:
    - amount: 금액
    - from_currency: 원래 통화 코드 (예: 'USD')
    - to_currency: 변환할 통화 코드 (예: 'KRW')
    - exchange_rates: 환율 정보 딕셔너리
    
    Returns:
    - 변환된 금액
    """
    if from_currency == to_currency:
        return amount
    
    # USD가 기준인 경우 직접 변환
    if from_currency == 'USD' and f'{from_currency}_{to_currency}' in exchange_rates:
        return amount * exchange_rates[f'{from_currency}_{to_currency}']
    
    # KRW가 목표인 경우 직접 변환
    if to_currency == 'KRW' and f'{from_currency}_{to_currency}' in exchange_rates:
        return amount * exchange_rates[f'{from_currency}_{to_currency}']
    
    # 다른 통화끼리의 변환은 KRW를 거쳐서 계산
    if f'{from_currency}_KRW' in exchange_rates and f'USD_KRW' in exchange_rates:
        # 첫 통화 -> KRW -> 대상 통화로 변환
        amount_in_krw = amount * exchange_rates[f'{from_currency}_KRW']
        if to_currency == 'KRW':
            return amount_in_krw
        elif f'{to_currency}_KRW' in exchange_rates:
            return amount_in_krw / exchange_rates[f'{to_currency}_KRW']
    
    # 변환할 수 없는 경우
    st.error(f"{from_currency}에서 {to_currency}로 변환할 수 없습니다.")
    return None

# 숫자 포맷팅 함수
def format_currency(amount, currency='KRW'):
    """
    통화 포맷팅 함수
    
    Parameters:
    - amount: 금액
    - currency: 통화 코드
    
    Returns:
    - 포맷팅된 문자열
    """
    if currency == 'KRW':
        if amount >= 1_000_000_000:
            return f"{amount/1_000_000_000:.2f}십억 원"
        elif amount >= 100_000_000:
            return f"{amount/100_000_000:.2f}억 원"
        elif amount >= 10000:
            return f"{amount/10000:.2f}만 원"
        else:
            return f"{amount:,.0f} 원"
    elif currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'CNY':
        return f"¥{amount:,.2f}"
    elif currency == 'JPY':
        return f"¥{amount:,.0f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def analyze_with_valuation_agents(company_info, financial_data, market_data, active_agents, debug_mode=False, model_name="gpt-4o-mini"):
    """멀티 에이전트 기업 가치 분석 수행"""
    try:
        # 에이전트별 프롬프트 템플릿
        agent_prompts = {
            'financial_agent': """재무 전문가 관점에서 다음 항목들을 분석해주세요:
            1. 수익성 분석 (영업이익률, 순이익률)
            2. 현금흐름 분석 (FCF 추세와 안정성)
            3. 성장성 분석 (매출, 이익 성장률)
            4. 적정 할인율 제시""",
            
            'market_agent': """시장 분석가 관점에서 다음 항목들을 분석해주세요:
            1. 산업 평균 대비 기업 위치
            2. 경쟁사 비교 분석
            3. 시장 성장성과 기회 요인
            4. 적정 PER 배수 제시""",
            
            'tech_agent': """기술 전문가 관점에서 다음 항목들을 분석해주세요:
            1. 기술 경쟁력 평가
            2. R&D 투자 효율성
            3. 특허 가치 평가
            4. 기술 기반 성장 가능성""",
            
            'risk_agent': """리스크 관리자 관점에서 다음 항목들을 분석해주세요:
            1. 재무적 리스크 평가
            2. 시장 리스크 평가
            3. 운영 리스크 평가
            4. 리스크 조정 가치 제시""",
            
            'strategy_agent': """전략 전문가 관점에서 다음 항목들을 분석해주세요:
            1. 사업 모델 경쟁력
            2. 전략적 포지셔닝
            3. 성장 전략 평가
            4. 장기 가치 창출 가능성"""
        }

        results = {}
        
        # 각 에이전트별 분석 수행
        for agent_type, is_active in active_agents.items():
            if not is_active or agent_type == 'integration_agent':
                continue
                
            if debug_mode:
                st.write(f"🤖 {agent_type} 분석 시작...")
            
            # 기본 프롬프트 구성
            base_prompt = f"""
            {agent_prompts.get(agent_type, '전문가로서 분석해주세요:')}

            기업 정보:
            {json.dumps(company_info, ensure_ascii=False, indent=2)}

            재무 데이터:
            {json.dumps(financial_data, ensure_ascii=False, indent=2)}

            시장 데이터:
            {json.dumps(market_data, ensure_ascii=False, indent=2)}

            분석 결과는 다음 형식의 flowchart를 포함해주세요:

            ```mermaid
            graph TD
                A[핵심 가치 요소] --> B[요소 1]
                A --> C[요소 2]
                B --> D[평가 1]
                C --> E[평가 2]
            ```
            """

            # AI 분석 수행
            response = openai.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": base_prompt}],
                temperature=0.7
            )

            results[agent_type] = {
                'analysis': response.choices[0].message.content,
                'valuation_summary': generate_valuation_summary(agent_type, company_info, financial_data),
                'risk_assessment': generate_risk_assessment(agent_type, company_info, financial_data)
            }

        # 통합 분석 수행
        if debug_mode:
            st.write("🤖 통합 분석 시작...")

        # 각 에이전트의 핵심 분석 추출
        summary_results = {
            agent: {
                'key_points': result['analysis'][:500],
                'valuation': result['valuation_summary'][:200]
            } for agent, result in results.items()
        }

        integration_prompt = f"""
        통합 분석가로서 다음 전문가들의 분석을 종합하여 최종 기업가치 평가를 제시해주세요:

        {json.dumps(summary_results, ensure_ascii=False, indent=2)}

        다음 형식으로 종합 분석을 제공해주세요:
        1. 각 전문가의 주요 평가 요약
        2. 평가 간 차이점과 그 이유
        3. 최종 기업가치 제시 (범위로 제시)
        4. 가치 제고를 위한 제언
        """

        integration_response = openai.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": integration_prompt}],
            temperature=0.7
        )

        results['integration_agent'] = {
            'analysis': integration_response.choices[0].message.content,
            'valuation_summary': "통합 분석 기반 최종 가치 평가",
            'risk_assessment': "종합 리스크 평가"
        }

        return results

    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def generate_valuation_summary(agent_type, company_info, financial_data):
    """에이전트별 가치평가 요약 생성"""
    try:
        prompt = f"""
        {agent_type.replace('_', ' ').title()} 관점에서 다음 정보를 바탕으로
        기업의 가치를 평가하고 요약해주세요:

        기업 정보:
        {json.dumps(company_info, ensure_ascii=False, indent=2)}

        재무 데이터:
        {json.dumps(financial_data, ensure_ascii=False, indent=2)}

        분석 결과를 Mermaid 차트로 표현해주세요.
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content
    except Exception as e:
        st.error(f"가치평가 요약 생성 중 오류 발생: {str(e)}")
        return "가치평가 요약을 생성할 수 없습니다."

def generate_risk_assessment(agent_type, company_info, financial_data):
    """에이전트별 리스크 평가 생성"""
    try:
        # 에이전트별 리스크 평가 관점 정의
        risk_perspectives = {
            'financial_agent': """
            1. 재무적 안정성 리스크
            2. 현금흐름 리스크
            3. 부채 관련 리스크
            4. 수익성 리스크
            """,
            'market_agent': """
            1. 시장 경쟁 리스크
            2. 산업 사이클 리스크
            3. 규제 리스크
            4. 시장 점유율 리스크
            """,
            'tech_agent': """
            1. 기술 진부화 리스크
            2. R&D 실패 리스크
            3. 특허 침해 리스크
            4. 기술 인력 이탈 리스크
            """,
            'risk_agent': """
            1. 운영 리스크
            2. 법률 리스크
            3. 평판 리스크
            4. 환경 리스크
            """,
            'strategy_agent': """
            1. 전략 실행 리스크
            2. 시장 진입 리스크
            3. 사업 다각화 리스크
            4. 장기 성장 리스크
            """
        }

        prompt = f"""
        {agent_type.replace('_', ' ').title()} 관점에서 다음 정보를 바탕으로
        주요 리스크를 평가하고 대응 방안을 제시해주세요:

        중점 검토 리스크:
        {risk_perspectives.get(agent_type, '일반적인 리스크 관점에서 평가해주세요.')}

        기업 정보:
        {json.dumps(company_info, ensure_ascii=False, indent=2)}

        재무 데이터:
        {json.dumps(financial_data, ensure_ascii=False, indent=2)}

        분석 결과를 다음과 같은 Mermaid 차트로 표현해주세요:
        ```mermaid
        graph TD
            A[주요 리스크] --> B[리스크 1]
            A --> C[리스크 2]
            B --> D[대응방안 1]
            C --> E[대응방안 2]
        ```
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content
    except Exception as e:
        st.error(f"리스크 평가 생성 중 오류 발생: {str(e)}")
        return "리스크 평가를 생성할 수 없습니다."

def mermaid_to_graphviz(mermaid_code):
    """Mermaid 코드를 Graphviz로 변환"""
    try:
        # Mermaid 코드에서 노드와 엣지 추출
        import re
        
        # flowchart/graph 형식 파싱
        nodes = {}
        edges = []
        
        # 노드 정의 찾기 (예: A[내용])
        node_pattern = r'([A-Za-z0-9_]+)\[(.*?)\]'
        for match in re.finditer(node_pattern, mermaid_code):
            node_id, node_label = match.groups()
            nodes[node_id] = node_label
        
        # 엣지 정의 찾기 (예: A --> B)
        edge_pattern = r'([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)'
        edges = re.findall(edge_pattern, mermaid_code)
        
        # Graphviz 객체 생성
        dot = graphviz.Digraph()
        dot.attr(rankdir='LR')  # 왼쪽에서 오른쪽으로 방향 설정
        
        # 노드 추가
        for node_id, node_label in nodes.items():
            dot.node(node_id, node_label)
        
        # 엣지 추가
        for src, dst in edges:
            dot.edge(src, dst)
        
        return dot
    except Exception as e:
        st.error(f"차트 변환 중 오류 발생: {str(e)}")
        return None

def display_mermaid_chart(markdown_text):
    """Mermaid 차트가 포함된 마크다운 텍스트를 표시"""
    try:
        import re
        mermaid_pattern = r"```mermaid\n(.*?)\n```"
        
        # 일반 마크다운과 Mermaid 차트 분리
        parts = re.split(mermaid_pattern, markdown_text, flags=re.DOTALL)
        
        for i, part in enumerate(parts):
            if i % 2 == 0:  # 일반 마크다운
                if part.strip():
                    st.markdown(part)
            else:  # Mermaid 차트
                # Graphviz로 변환하여 표시
                dot = mermaid_to_graphviz(part)
                if dot:
                    st.graphviz_chart(dot)
                else:
                    # 변환 실패 시 코드 표시
                    st.code(part, language="mermaid")
    except Exception as e:
        st.error(f"차트 표시 중 오류 발생: {str(e)}")
        st.markdown(markdown_text)  # 오류 시 일반 텍스트로 표시

# EV/EBITDA 기반 가치 평가 함수 추가
def calculate_ev_ebitda_valuation(ebitda, multiples, net_debt):
    """
    EV/EBITDA 멀티플 기반 기업가치 계산
    
    Parameters:
    - ebitda: EBITDA (영업이익 + 감가상각비 + 무형자산상각비)
    - multiples: EV/EBITDA 멀티플 리스트 (예: [8, 10, 12])
    - net_debt: 순차입금 (총차입금 - 현금성자산)
    
    Returns:
    - EV/EBITDA 멀티플별 기업가치 딕셔너리
    """
    valuations = {}
    for multiple in multiples:
        enterprise_value = ebitda * multiple
        equity_value = enterprise_value - net_debt  # 기업가치에서 순차입금을 차감하여 주주가치 계산
        valuations[multiple] = {
            'enterprise_value': enterprise_value,
            'equity_value': equity_value
        }
    return valuations

# 산업별 평균 EV/EBITDA 멀티플 데이터 (예시 데이터)
INDUSTRY_EVEBITDA_MULTIPLES = {
    "기술/제조": {
        "median": 12.5,
        "range": (8.5, 16.5),
        "description": "하드웨어 및 장비 제조업체의 일반적인 범위",
        "factors": {
            "high": ["높은 성장성", "강한 시장 지배력", "높은 수익성"],
            "low": ["치열한 경쟁", "낮은 진입장벽", "높은 자본지출 요구"]
        }
    },
    "소프트웨어/IT": {
        "median": 15.0,
        "range": (12.0, 20.0),
        "description": "소프트웨어 및 IT 서비스 기업의 일반적인 범위",
        "factors": {
            "high": ["높은 성장성", "반복적인 수익", "낮은 자본지출"],
            "low": ["기술 변화 위험", "인력 의존도", "경쟁 심화"]
        }
    },
    "소비재": {
        "median": 10.0,
        "range": (7.0, 13.0),
        "description": "소비재 기업의 일반적인 범위",
        "factors": {
            "high": ["브랜드 가치", "안정적 수익", "높은 마진"],
            "low": ["경기 민감도", "원자재 가격 변동", "유통 비용"]
        }
    },
    "의료/바이오": {
        "median": 14.0,
        "range": (11.0, 18.0),
        "description": "의료 및 바이오 기업의 일반적인 범위",
        "factors": {
            "high": ["높은 진입장벽", "특허 보호", "고성장 잠재력"],
            "low": ["규제 리스크", "R&D 비용", "임상 실패 위험"]
        }
    },
    "에너지": {
        "median": 8.0,
        "range": (6.0, 11.0),
        "description": "에너지 기업의 일반적인 범위",
        "factors": {
            "high": ["자원 보유량", "수직 계열화", "규모의 경제"],
            "low": ["원자재 가격 변동", "규제 강화", "높은 자본지출"]
        }
    }
}

def analyze_evebitda_valuation(industry, ebitda, net_debt, current_multiple, growth_rate):
    """
    EV/EBITDA 멀티플 기반의 상세 분석을 수행
    
    Parameters:
    - industry: 산업 분류
    - ebitda: EBITDA 값
    - net_debt: 순차입금
    - current_multiple: 현재 적용된 멀티플
    - growth_rate: 예상 성장률
    
    Returns:
    - 분석 결과 딕셔너리
    """
    industry_data = INDUSTRY_EVEBITDA_MULTIPLES.get(industry, {
        "median": 12.0,
        "range": (8.0, 16.0),
        "description": "일반적인 산업 평균 범위",
        "factors": {
            "high": ["높은 성장성", "강한 시장 지배력"],
            "low": ["치열한 경쟁", "낮은 진입장벽"]
        }
    })
    
    median_multiple = industry_data["median"]
    range_low, range_high = industry_data["range"]
    
    # 적정 멀티플 범위 조정 (성장률 반영)
    growth_adjustment = (growth_rate - 0.10) * 2  # 10% 성장률 기준으로 조정
    adjusted_low = range_low + growth_adjustment
    adjusted_high = range_high + growth_adjustment
    adjusted_median = median_multiple + growth_adjustment
    
    # 기업가치 계산
    ev_low = ebitda * adjusted_low
    ev_median = ebitda * adjusted_median
    ev_high = ebitda * adjusted_high
    
    # 주주가치 계산
    equity_low = ev_low - net_debt
    equity_median = ev_median - net_debt
    equity_high = ev_high - net_debt
    
    # 현재 멀티플과 비교
    multiple_assessment = "적정" if range_low <= current_multiple <= range_high else \
                        "고평가" if current_multiple > range_high else "저평가"
    
    return {
        "industry_median": median_multiple,
        "industry_range": (range_low, range_high),
        "adjusted_range": (adjusted_low, adjusted_high),
        "adjusted_median": adjusted_median,
        "enterprise_values": {
            "low": ev_low,
            "median": ev_median,
            "high": ev_high
        },
        "equity_values": {
            "low": equity_low,
            "median": equity_median,
            "high": equity_high
        },
        "assessment": multiple_assessment,
        "description": industry_data["description"],
        "factors": industry_data["factors"]
    }

def save_valuation_analysis(company_info, financial_data, market_data, analysis_results, valuation_results):
    """기업 가치 평가 결과를 데이터베이스에 저장"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1. valuation_analyses 테이블에 기본 정보 저장
        cursor.execute('''
            INSERT INTO valuation_analyses 
            (company_name, industry, company_description, base_currency)
            VALUES (%s, %s, %s, %s)
        ''', (
            company_info['name'],
            company_info['industry'],
            company_info['description'],
            company_info['currency']
        ))
        analysis_id = cursor.lastrowid

        # 2. valuation_financial_data 테이블에 재무 데이터 저장
        cursor.execute('''
            INSERT INTO valuation_financial_data
            (analysis_id, revenue, operating_profit, depreciation, amortization,
             net_income, current_fcf, growth_rate, discount_rate, terminal_growth_rate,
             net_debt, r_and_d_cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            analysis_id,
            financial_data['revenue'],
            financial_data['operating_profit'],
            financial_data.get('depreciation', 0),
            financial_data.get('amortization', 0),
            financial_data['net_income'],
            financial_data['current_fcf'],
            financial_data['growth_rate'],
            financial_data['discount_rate'],
            financial_data['terminal_growth_rate'],
            financial_data.get('net_debt', 0),
            financial_data['r_and_d_cost']
        ))

        # 3. valuation_market_data 테이블에 시장 데이터 저장
        cursor.execute('''
            INSERT INTO valuation_market_data
            (analysis_id, patents_count, trademarks_count, technology_impact,
             market_size, market_share, per_values, evebitda_values)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            analysis_id,
            market_data['patents_count'],
            market_data['trademarks_count'],
            market_data['technology_impact'],
            market_data['market_size'],
            market_data['market_share'],
            json.dumps(market_data['per_values']),
            json.dumps(market_data.get('evebitda_values', []))
        ))

        # 4. valuation_agent_analyses 테이블에 AI 에이전트 분석 결과 저장
        for agent_type, analysis in analysis_results.items():
            cursor.execute('''
                INSERT INTO valuation_agent_analyses
                (analysis_id, agent_type, analysis_content, valuation_summary,
                 risk_assessment, mermaid_chart)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                analysis_id,
                agent_type,  # integration_agent도 포함
                analysis['analysis'],
                analysis['valuation_summary'],
                analysis['risk_assessment'],
                extract_mermaid_chart(analysis['analysis'])
            ))

        # 5. valuation_results 테이블에 평가 결과 저장
        for method, result in valuation_results.items():
            cursor.execute('''
                INSERT INTO valuation_results
                (analysis_id, valuation_method, result_data)
                VALUES (%s, %s, %s)
            ''', (
                analysis_id,
                method,
                json.dumps(result)
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return True, analysis_id

    except mysql.connector.Error as err:
        st.error(f"데이터베이스 저장 중 오류 발생: {err}")
        return False, None

def extract_mermaid_chart(text):
    """마크다운 텍스트에서 Mermaid 차트 코드 추출"""
    import re
    mermaid_pattern = r"```mermaid\n(.*?)\n```"
    matches = re.findall(mermaid_pattern, text, re.DOTALL)
    return matches[0] if matches else None

def get_saved_analyses():
    """저장된 가치 평가 분석 목록 조회"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT 
                a.analysis_id,
                a.company_name,
                a.industry,
                a.currency,
                a.created_at,
                f.revenue,
                f.operating_profit,
                m.market_size,
                m.market_share
            FROM valuation_analyses a
            LEFT JOIN valuation_financial_data f ON a.analysis_id = f.analysis_id
            LEFT JOIN valuation_market_data m ON a.analysis_id = m.analysis_id
            ORDER BY a.created_at DESC
        ''')
        
        results = cursor.fetchall()
        
        # created_at을 analysis_date로 매핑
        for result in results:
            result['analysis_date'] = result['created_at']
            # currency가 None인 경우 기본값 설정
            if result.get('currency') is None:
                result['currency'] = 'KRW'
        
        return results
    except mysql.connector.Error as err:
        st.error(f"데이터 조회 중 오류 발생: {err}")
        return []
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

def get_analysis_detail(analysis_id):
    """특정 가치 평가 분석의 상세 정보 조회"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 기본 정보 조회
        cursor.execute('''
            SELECT * FROM valuation_analyses 
            WHERE analysis_id = %s
        ''', (analysis_id,))
        basic_info = cursor.fetchone()
        
        # 재무 데이터 조회
        cursor.execute('''
            SELECT * FROM valuation_financial_data 
            WHERE analysis_id = %s
        ''', (analysis_id,))
        financial_data = cursor.fetchone()
        
        # 시장 데이터 조회
        cursor.execute('''
            SELECT * FROM valuation_market_data 
            WHERE analysis_id = %s
        ''', (analysis_id,))
        market_data = cursor.fetchone()
        
        # AI 에이전트 분석 결과 조회
        cursor.execute('''
            SELECT * FROM valuation_agent_analyses 
            WHERE analysis_id = %s
        ''', (analysis_id,))
        agent_analyses = cursor.fetchall()
        
        # 평가 결과 조회
        cursor.execute('''
            SELECT * FROM valuation_results 
            WHERE analysis_id = %s
        ''', (analysis_id,))
        valuation_results = cursor.fetchall()
        
        return {
            'basic_info': basic_info,
            'financial_data': financial_data,
            'market_data': market_data,
            'agent_analyses': agent_analyses,
            'valuation_results': valuation_results
        }
    except mysql.connector.Error as err:
        st.error(f"데이터 조회 중 오류 발생: {err}")
        return None
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

def delete_valuation_analysis(analysis_id):
    """기업 가치 평가 분석 삭제"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 관련 테이블에서 순차적으로 데이터 삭제
        tables = [
            'valuation_results',
            'valuation_agent_analyses',
            'valuation_market_data',
            'valuation_financial_data',
            'valuation_analyses'
        ]

        for table in tables:
            cursor.execute(f'DELETE FROM {table} WHERE analysis_id = %s', (analysis_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except mysql.connector.Error as err:
        st.error(f"데이터베이스 삭제 중 오류 발생: {err}")
        return False

# === [추가] Perplexity 기반 비상장사 종합분석 조사 ===
def get_unlisted_company_analysis_perplexity(company_name):
    """비상장사 종합분석 (Perplexity API)"""
    try:
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_key:
            st.warning('Perplexity API 키가 필요합니다.')
            return None
        from openai import OpenAI
        client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
        prompt = f"""
        {company_name} 비상장 회사의 종합적인 분석을 제공해주세요.
        
        === 기업 개요 ===
        - 기업명: {company_name}
        - 설립일: [설립일]
        - 사업 분야: [주요 사업 분야]
        - 직원 수: [대략적인 직원 수]
        - 매출 규모: [매출 규모 추정]
        
        === 재무 현황 ===
        - 매출액: [매출액 추정]
        - 영업이익: [영업이익 추정]
        - 순이익: [순이익 추정]
        - 자산 규모: [자산 규모 추정]
        - 부채 현황: [부채 현황]
        
        === 사업 모델 ===
        - 주요 제품/서비스: [주요 제품/서비스]
        - 수익 모델: [수익 창출 방식]
        - 고객층: [주요 고객층]
        - 경쟁 우위: [차별화 요소]
        
        === 시장 현황 ===
        - 시장 규모: [해당 시장 규모]
        - 시장 점유율: [시장 점유율 추정]
        - 주요 경쟁사: [주요 경쟁사들]
        - 시장 성장률: [시장 성장률]
        
        === 성장성 및 전망 ===
        - 최근 성장률: [최근 성장률]
        - 성장 동력: [성장을 이끄는 요인]
        - 향후 전망: [향후 3-5년 전망]
        - 리스크 요인: [주요 리스크 요인]
        
        === 투자 현황 ===
        - 투자 유치 이력: [투자 유치 이력]
        - 최근 투자자: [최근 투자자들]
        - 기업가치: [최근 기업가치 추정]
        - IPO 계획: [상장 계획 여부]
        
        === 기술 및 혁신 ===
        - 핵심 기술: [보유 핵심 기술]
        - 특허 현황: [특허 보유 현황]
        - R&D 투자: [R&D 투자 규모]
        - 기술 경쟁력: [기술적 경쟁력]
        
        === 경영진 및 조직 ===
        - 대표자: [대표자 정보]
        - 경영진 구성: [주요 경영진]
        - 조직 문화: [조직 문화 특징]
        - 인재 확보: [인재 확보 현황]
        
        === 최근 이슈 ===
        - 최근 뉴스: [최근 주요 뉴스]
        - 사업 확장: [사업 확장 계획]
        - 파트너십: [주요 파트너십]
        - 사회적 영향: [사회적 기여도]
        
        객관적이고 구체적인 정보를 바탕으로 종합적인 분석을 제공해주세요.
        """
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Perplexity API 오류: {str(e)}")
        return None

# === [추가] Perplexity 기반 비상장사 가치평가법 조사 ===
def get_unlisted_valuation_methods_perplexity(company_name, industry):
    try:
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_key:
            st.warning('Perplexity API 키가 필요합니다.')
            return None
        from openai import OpenAI
        client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
        prompt = f"""
        {company_name} ({industry}) 비상장 회사의 기업가치 평가 방법을 제시해주세요.\n\n=== 적합한 평가 방법 ===\n1. DCF 모델: [적용 가능성 및 방법]\n2. 유사기업비교법: [비교 대상 기업들]\n3. 순자산가치법: [적용 가능성]\n4. 배수법: [적용 가능한 배수]\n\n=== 평가 시 고려사항 ===\n- 업종별 특성: [해당 업종의 특성]\n- 성장 단계: [기업의 성장 단계]\n- 시장 환경: [현재 시장 상황]\n- 유동성 프리미엄: [비상장 할인율]\n\n=== 구체적 계산 방법 ===\n- 매출배수: [적정 배수 범위]\n- 이익배수: [적정 배수 범위]\n- 자산배수: [적정 배수 범위]\n- 할인율: [적정 할인율]\n\n=== 벤치마킹 대상 ===\n- 국내 유사기업: [상장/비상장 유사기업]\n- 해외 유사기업: [해외 유사기업]\n- 업종 평균: [업종 평균 지표]\n\n실무적으로 적용 가능한 구체적인 방법을 제시해주세요."""
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Perplexity API 오류: {str(e)}")
        return None

# === [추가] Perplexity 기반 비상장사 투자기회 조사 ===
def get_unlisted_investment_opportunities_perplexity(company_name):
    try:
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_key:
            st.warning('Perplexity API 키가 필요합니다.')
            return None
        from openai import OpenAI
        client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
        prompt = f"""
        {company_name} 비상장 회사의 투자 기회를 분석해주세요.\n\n=== 투자 기회 분석 ===\n투자 적기: [현재 투자 적기 여부]\n투자 가치: [투자 가치 평가]\n성장 잠재력: [성장 가능성]\n시장 기회: [시장에서의 기회]\n\n=== 투자 방식 ===\n직접 투자: [직접 투자 가능성]\n간접 투자: [펀드 등을 통한 투자]\n지분 매입: [지분 매입 기회]\n전략적 투자: [전략적 투자 가능성]\n\n=== 투자 조건 ===\n최소 투자금액: [최소 투자 금액]\n투자 조건: [투자 시 조건]\n소요 기간: [투자 소요 기간]\n출구 전략: [투자 회수 방안]\n\n=== 리스크 관리 ===\n주요 리스크: [투자 시 주요 위험]\n리스크 완화: [리스크 완화 방안]\n분산 투자: [분산 투자 전략]\n\n=== 실무 가이드 ===\n투자 절차: [실제 투자 절차]\n법적 고려사항: [투자 시 법적 고려사항]\n세무 고려사항: [세무상 고려사항]\n\n실무적으로 적용 가능한 구체적인 정보를 제공해주세요."""
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Perplexity API 오류: {str(e)}")
        return None

# === [추가] Perplexity 기반 비상장사 시장비교 조사 ===
def get_unlisted_market_comparison_perplexity(company_name, industry):
    try:
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_key:
            st.warning('Perplexity API 키가 필요합니다.')
            return None
        from openai import OpenAI
        client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
        prompt = f"""
        {company_name} ({industry}) 비상장 회사의 시장 내 위치와 경쟁력을 분석해주세요.\n\n=== 시장 위치 ===\n시장 규모: [해당 시장의 규모]\n시장 성장률: [시장 성장률]\n시장 점유율: [기업의 시장 점유율]\n시장 순위: [시장 내 순위]\n\n=== 경쟁사 비교 ===\n주요 경쟁사: [주요 경쟁 기업들]\n경쟁사 규모: [경쟁사들의 규모]\n경쟁 우위: [기업의 경쟁 우위]\n경쟁 열위: [기업의 경쟁 열위]\n\n=== 업종 벤치마킹 ===\n업종 평균: [업종 평균 지표]\n업종 성장률: [업종 성장률]\n업종 트렌드: [업종 주요 트렌드]\n업종 리스크: [업종 주요 리스크]\n\n=== 성장성 비교 ===\n매출 성장률: [매출 성장률]\n이익 성장률: [이익 성장률]\n시장 성장률 대비: [시장 대비 성장률]\n경쟁사 대비 성장률: [경쟁사 대비 성장률]\n\n=== 투자 매력도 ===\n업종 내 투자 매력도: [업종 내 투자 매력도]\n성장성 점수: [성장성 점수]\n수익성 점수: [수익성 점수]\n안정성 점수: [안정성 점수]\n\n객관적이고 구체적인 비교 분석을 제공해주세요."""
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Perplexity API 오류: {str(e)}")
        return None

# === [추가] 비상장사 특화 멀티에이전트 정의 ===
UNLISTED_FINANCIAL_AGENTS = {
    "financial_analyst": {
        "name": "💰 재무 분석 전문가",
        "emoji": "💰",
        "description": "재무제표, 재무비율, 수익성 분석 전문가",
        "system_prompt": """당신은 15년 경력의 재무 분석 전문가입니다. 
        
**전문 분야:**
- 재무제표 분석 (손익계산서, 재무상태표, 현금흐름표)
- 재무비율 분석 (수익성, 안정성, 효율성 비율)
- 재무 건전성 평가
- 회계 품질 분석

**분석 관점:**
- 재무 데이터의 정확성과 신뢰성
- 수익성 트렌드와 지속가능성  
- 자본 구조와 재무 안정성
- 현금 창출 능력

재무 데이터를 바탕으로 객관적이고 전문적인 분석을 제공해주세요."""
    },
    
    "investment_analyst": {
        "name": "📊 투자 분석가", 
        "emoji": "📊",
        "description": "밸류에이션, 투자 매력도, 목표주가 분석 전문가",
        "system_prompt": """당신은 10년 경력의 투자 분석가입니다.

**전문 분야:**
- 기업 밸류에이션 (PER, PBR, EV/EBITDA 등)
- 투자 매력도 평가
- 목표주가 산정
- 투자 리스크/리턴 분석

**분석 관점:**
- 현재 주가의 적정성
- 성장 가능성과 투자 기회
- 배당 정책과 주주 환원
- 시장 대비 상대적 매력도

투자자 관점에서 실용적이고 액션 가능한 투자 의견을 제시해주세요."""
    },
    
    "market_analyst": {
        "name": "🏭 시장 분석가",
        "emoji": "🏭", 
        "description": "시장 동향, 경쟁 분석, 산업 트렌드 전문가",
        "system_prompt": """당신은 12년 경력의 시장 분석가입니다.

**전문 분야:**
- 시장 규모 및 성장성 분석
- 경쟁사 비교 분석
- 산업 트렌드 분석
- 시장 점유율 분석

**분석 관점:**
- 시장 내 기업의 위치
- 경쟁 우위/열위 분석
- 시장 기회와 위협
- 산업 발전 단계

시장 관점에서 기업의 경쟁력과 성장 가능성을 분석해주세요."""
    },
    
    "tech_analyst": {
        "name": "🔬 기술 분석가",
        "emoji": "🔬",
        "description": "기술 경쟁력, R&D, 특허 분석 전문가", 
        "system_prompt": """당신은 8년 경력의 기술 분석가입니다.

**전문 분야:**
- 기술 경쟁력 평가
- R&D 투자 효율성 분석
- 특허 및 지적재산권 분석
- 기술 트렌드 분석

**분석 관점:**
- 기술적 차별화 요소
- R&D 투자 대비 성과
- 기술 진부화 리스크
- 기술 기반 성장 가능성

기술 관점에서 기업의 혁신성과 지속가능성을 분석해주세요."""
    },
    
    "risk_manager": {
        "name": "⚠️ 리스크 관리자",
        "emoji": "⚠️",
        "description": "리스크 평가, 위험 관리 전문가",
        "system_prompt": """당신은 10년 경력의 리스크 관리자입니다.

**전문 분야:**
- 재무적 리스크 평가
- 시장 리스크 분석
- 운영 리스크 평가
- 규제 리스크 분석

**분석 관점:**
- 주요 리스크 요인 식별
- 리스크 대응 방안
- 리스크 조정 수익률
- 비상장 특화 리스크

리스크 관점에서 투자 안정성과 위험 요소를 분석해주세요."""
    },
    
    "strategy_analyst": {
        "name": "🎯 전략 분석가",
        "emoji": "🎯",
        "description": "사업 전략, 성장 전략, 경쟁 전략 전문가",
        "system_prompt": """당신은 15년 경력의 전략 분석가입니다.

**전문 분야:**
- 사업 모델 분석
- 성장 전략 평가
- 경쟁 전략 분석
- 시장 진입 전략

**분석 관점:**
- 전략적 포지셔닝
- 성장 동력과 제약요소
- 시장 기회 활용도
- 장기 가치 창출 가능성

전략 관점에서 기업의 지속가능한 성장 가능성을 분석해주세요."""
    }
}

# === [추가] 비상장사 멀티에이전트 분석 실행 함수 ===
def run_unlisted_multi_agent_analysis(company_name, analysis_data, selected_agents, model_name, enable_thinking=False):
    """비상장사 멀티 에이전트 분석 실행"""
    
    # 진행 상황 표시용 컨테이너
    progress_container = st.container()
    
    with progress_container:
        st.info("🚀 **비상장사 멀티 에이전트 분석 시작**")
        
        # 에이전트별 상태 표시
        agent_status = {}
        agent_progress = {}
        
        cols = st.columns(len(selected_agents))
        for i, agent_key in enumerate(selected_agents):
            with cols[i]:
                agent_info = UNLISTED_FINANCIAL_AGENTS[agent_key]
                agent_status[agent_key] = st.empty()
                agent_progress[agent_key] = st.progress(0)
                
                agent_status[agent_key].info(f"{agent_info['emoji']} {agent_info['name']}\n대기 중...")
        
        # 멀티프로세싱으로 에이전트 분석 실행
        st.info("⚡ **병렬 분석 실행 중...**")
        
        # 분석 인자 준비
        analysis_args = []
        for agent_key in selected_agents:
            agent_info = UNLISTED_FINANCIAL_AGENTS[agent_key]
            args = (agent_key, agent_info, analysis_data, model_name, company_name, enable_thinking)
            analysis_args.append(args)
        
        # 병렬 실행
        agent_analyses = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected_agents)) as executor:
            # 모든 에이전트 작업 제출
            future_to_agent = {
                executor.submit(analyze_with_unlisted_agent, args): args[0] 
                for args in analysis_args
            }
            
            # 완료된 작업 처리
            completed = 0
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_key = future_to_agent[future]
                
                try:
                    result = future.result()
                    agent_analyses.append(result)
                    
                    # 진행 상황 업데이트
                    completed += 1
                    progress = completed / len(selected_agents)
                    
                    agent_progress[agent_key].progress(1.0)
                    
                    if result['success']:
                        agent_status[agent_key].success(f"{result['agent_emoji']} {result['agent_name']}\n✅ 분석 완료")
                    else:
                        agent_status[agent_key].error(f"{result['agent_emoji']} {result['agent_name']}\n❌ 분석 실패")
                    
                except Exception as e:
                    st.error(f"에이전트 {agent_key} 실행 중 오류: {str(e)}")
        
        st.success("✅ **모든 에이전트 분석 완료**")
        
        # CFO 종합 분석
        st.info("👔 **CFO 종합 분석 시작...**")
        cfo_analysis = synthesize_unlisted_cfo_analysis(company_name, agent_analyses, analysis_data, model_name)
        
        if cfo_analysis['success']:
            st.success("✅ **CFO 종합 분석 완료**")
        else:
            st.error("❌ **CFO 종합 분석 실패**")
    
    return agent_analyses, cfo_analysis

# === [추가] 비상장사 개별 에이전트 분석 함수 ===
def analyze_with_unlisted_agent(args):
    """비상장사 개별 에이전트 분석 함수 (멀티프로세싱용)"""
    agent_key, agent_info, analysis_data, model_name, company_name, enable_thinking = args
    
    try:
        # 에이전트별 특화 mermaid 차트 가이드
        mermaid_guides = {
            "financial_analyst": """
**Mermaid 차트 요청:**
- pie 차트: 매출 구성 또는 비용 구성
- flowchart: 재무 건전성 평가 프로세스
- timeline: 재무 성과 변화 추세
""",
            "investment_analyst": """
**Mermaid 차트 요청:**
- quadrantChart: 리스크-수익률 매트릭스
- pie 차트: 포트폴리오 비중 추천
- flowchart: 투자 의사결정 프로세스
""",
            "market_analyst": """
**Mermaid 차트 요청:**
- pie 차트: 시장 점유율 분포
- flowchart: 경쟁 구도 분석
- timeline: 산업 발전 단계
""",
            "tech_analyst": """
**Mermaid 차트 요청:**
- flowchart: 기술 경쟁력 평가
- timeline: 기술 발전 단계
- quadrantChart: 기술 매트릭스
""",
            "risk_manager": """
**Mermaid 차트 요청:**
- flowchart: 리스크 관리 프로세스
- mindmap: 리스크 요인 분류
- timeline: 리스크 이벤트 타임라인
""",
            "strategy_analyst": """
**Mermaid 차트 요청:**
- flowchart: 전략 실행 프로세스
- timeline: 성장 단계별 전략
- quadrantChart: 전략 매트릭스
"""
        }
        
        # 에이전트별 특화 프롬프트 생성
        agent_prompt = f"""
{agent_info['system_prompt']}

다음은 {company_name}의 분석 데이터입니다:

{analysis_data}

당신의 전문 분야인 {agent_info['description']} 관점에서 이 비상장 기업을 분석해주세요.

**분석 요청사항:**
1. 주요 발견사항 (3-5개)
2. 장점과 강점
3. 우려사항과 약점  
4. 전문가 의견과 권고사항
5. 점수 평가 (1-10점, 이유 포함)

{mermaid_guides.get(agent_key, "")}

**중요**: 분석 내용에 적절한 Mermaid 차트를 1-2개 포함해주세요. 차트는 ```mermaid 코드블록으로 작성하고, 분석 내용과 잘 연계되도록 해주세요.

구체적이고 실용적인 분석을 제공해주세요.
"""
        
        # AI 응답 생성
        response = get_ai_response(
            prompt=agent_prompt,
            model_name=model_name,
            system_prompt=agent_info['system_prompt'],
            enable_thinking=enable_thinking
        )
        
        return {
            'agent_key': agent_key,
            'agent_name': agent_info['name'],
            'agent_emoji': agent_info['emoji'],
            'analysis': response['content'],
            'thinking': response.get('thinking', ''),
            'has_thinking': response.get('has_thinking', False),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        return {
            'agent_key': agent_key,
            'agent_name': agent_info['name'], 
            'agent_emoji': agent_info['emoji'],
            'analysis': f"분석 중 오류가 발생했습니다: {str(e)}",
            'thinking': '',
            'has_thinking': False,
            'success': False,
            'error': str(e)
        }

# === [추가] 비상장사 CFO 종합 분석 함수 ===
def synthesize_unlisted_cfo_analysis(company_name, agent_analyses, analysis_data, model_name="gpt-4o-mini"):
    """비상장사 CFO가 모든 에이전트 분석을 종합하여 최종 의견 제시"""
    
    # 에이전트 분석 결과 정리
    agent_summaries = []
    for analysis in agent_analyses:
        if analysis['success']:
            agent_summaries.append(f"""
**{analysis['agent_name']} 분석:**
{analysis['analysis']}
""")
    
    cfo_prompt = f"""
당신은 20년 경력의 CFO(최고재무책임자)입니다. 다양한 전문가들이 {company_name} 비상장 기업에 대해 분석한 결과를 종합하여 최종 경영진 관점의 의견을 제시해주세요.

**기업 데이터:**
{analysis_data}

**전문가 분석 결과:**
{''.join(agent_summaries)}

**CFO 종합 분석 요청사항:**
1. **Executive Summary** (경영진 요약)
2. **핵심 발견사항** (각 전문가 의견의 공통점과 차이점)
3. **통합 SWOT 분석** (강점, 약점, 기회, 위협)
4. **재무적 권고사항** (구체적인 액션 아이템)
5. **투자 의견** (투자 적합도 + 목표가치 제시)
6. **리스크 관리 방안**
7. **종합 평점** (1-10점, 상세 이유)

**Mermaid 차트 필수 포함:**
- **SWOT 분석**: mindmap 차트로 강점/약점/기회/위협 시각화
- **의사결정 프로세스**: flowchart로 투자 의사결정 단계 표시
- **포트폴리오 비중**: pie 차트로 추천 투자 비중 제시
- **리스크-수익률 매트릭스**: quadrantChart로 위험도와 수익률 관계 표시

**중요**: 반드시 2-3개의 Mermaid 차트를 ```mermaid 코드블록으로 포함하여 시각적으로 이해하기 쉽게 제시해주세요.

경영진과 투자자들이 의사결정을 내릴 수 있도록 명확하고 실행 가능한 권고안을 제시해주세요.
"""
    
    try:
        response = get_ai_response(
            prompt=cfo_prompt,
            model_name=model_name,
            system_prompt="당신은 20년 경력의 CFO입니다. 비상장 기업 투자에 대한 전문적인 종합 분석을 제공해주세요.",
            enable_thinking=False
        )
        
        return {
            'content': response['content'],
            'thinking': response.get('thinking', ''),
            'has_thinking': response.get('has_thinking', False),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        return {
            'content': f"CFO 종합 분석 중 오류가 발생했습니다: {str(e)}",
            'thinking': '',
            'has_thinking': False,
            'success': False,
            'error': str(e)
        }

# [UI에 Perplexity 조사 결과 표시 예시]
def main():
   
    
    # 탭 생성
    tab1, tab2 = st.tabs(["새 분석 생성", "저장된 분석 조회"])
    
    with tab1:
        # AI 에이전트 설정
        with st.expander("🤖 AI 에이전트 설정"):
            st.subheader("활성화할 에이전트")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                financial_agent = st.checkbox("재무 전문가", value=True)
                market_agent = st.checkbox("시장 분석가", value=True)
                
            with col2:
                tech_agent = st.checkbox("기술 전문가", value=True)
                risk_agent = st.checkbox("리스크 관리자", value=True)
                
            with col3:
                strategy_agent = st.checkbox("전략 전문가", value=True)
                integration_agent = st.checkbox("통합 분석가", value=True, disabled=True)

        # 활성화된 에이전트 정보 저장
        active_agents = {
            'financial_agent': financial_agent,
            'market_agent': market_agent,
            'tech_agent': tech_agent,
            'risk_agent': risk_agent,
            'strategy_agent': strategy_agent,
            'integration_agent': True  # 항상 활성화
        }

        # 디버그 모드 설정
        debug_mode = st.sidebar.checkbox("디버그 모드", value=False)

        # 모델 선택
        model_name = st.selectbox(
            "사용할 모델",
            ["gpt-4o-mini", "gpt-4"],
            index=0
        )

        # 환율 정보 가져오기
        exchange_rates = get_exchange_rates()
        
        # === [NEW] Perplexity 기반 실시간 비상장사 분석 섹션 ===
        st.header("🔍 Perplexity 기반 실시간 비상장사 분석")
        company_name = st.text_input("비상장사명(또는 스타트업명)", "")
        industry = st.text_input("업종/산업(선택)", "")
        
        # 세션 상태 초기화
        if 'perplexity_comprehensive' not in st.session_state:
            st.session_state.perplexity_comprehensive = None
        if 'perplexity_valuation' not in st.session_state:
            st.session_state.perplexity_valuation = None
        if 'perplexity_investment' not in st.session_state:
            st.session_state.perplexity_investment = None
        if 'perplexity_market' not in st.session_state:
            st.session_state.perplexity_market = None
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Perplexity 종합분석"):
                with st.spinner("Perplexity API로 실시간 종합분석 중..."):
                    result = get_unlisted_company_analysis_perplexity(company_name)
                    if result:
                        st.session_state.perplexity_comprehensive = result
                    else:
                        st.session_state.perplexity_comprehensive = "Perplexity 조사 실패 또는 결과 없음."
        with col2:
            if st.button("Perplexity 가치평가법"):
                with st.spinner("Perplexity API로 가치평가법 조사 중..."):
                    result = get_unlisted_valuation_methods_perplexity(company_name, industry)
                    if result:
                        st.session_state.perplexity_valuation = result
                    else:
                        st.session_state.perplexity_valuation = "Perplexity 조사 실패 또는 결과 없음."
        with col3:
            if st.button("Perplexity 투자기회/시장비교"):
                with st.spinner("Perplexity API로 투자기회/시장비교 조사 중..."):
                    invest = get_unlisted_investment_opportunities_perplexity(company_name)
                    market = get_unlisted_market_comparison_perplexity(company_name, industry)
                    if invest:
                        st.session_state.perplexity_investment = invest
                    else:
                        st.session_state.perplexity_investment = "Perplexity 투자기회 조사 실패 또는 결과 없음."
                    if market:
                        st.session_state.perplexity_market = market
                    else:
                        st.session_state.perplexity_market = "Perplexity 시장비교 조사 실패 또는 결과 없음."
        with col4:
            if st.button("🗑️ 결과 초기화"):
                st.session_state.perplexity_comprehensive = None
                st.session_state.perplexity_valuation = None
                st.session_state.perplexity_investment = None
                st.session_state.perplexity_market = None
                st.success("모든 Perplexity 분석 결과가 초기화되었습니다.")
        
        # 결과 표시
        results_displayed = False
        
        if st.session_state.perplexity_comprehensive:
            if results_displayed:
                st.markdown("---")
            st.markdown("#### Perplexity 실시간 종합분석 결과")
            if st.session_state.perplexity_comprehensive == "Perplexity 조사 실패 또는 결과 없음.":
                st.warning(st.session_state.perplexity_comprehensive)
            else:
                st.markdown(st.session_state.perplexity_comprehensive)
            results_displayed = True
        
        if st.session_state.perplexity_valuation:
            if results_displayed:
                st.markdown("---")
            st.markdown("#### Perplexity 가치평가법 조사 결과")
            if st.session_state.perplexity_valuation == "Perplexity 조사 실패 또는 결과 없음.":
                st.warning(st.session_state.perplexity_valuation)
            else:
                st.markdown(st.session_state.perplexity_valuation)
            results_displayed = True
        
        if st.session_state.perplexity_investment:
            if results_displayed:
                st.markdown("---")
            st.markdown("#### Perplexity 투자기회 조사 결과")
            if st.session_state.perplexity_investment == "Perplexity 투자기회 조사 실패 또는 결과 없음.":
                st.warning(st.session_state.perplexity_investment)
            else:
                st.markdown(st.session_state.perplexity_investment)
            results_displayed = True
        
        if st.session_state.perplexity_market:
            if results_displayed:
                st.markdown("---")
            st.markdown("#### Perplexity 시장비교 조사 결과")
            if st.session_state.perplexity_market == "Perplexity 시장비교 조사 실패 또는 결과 없음.":
                st.warning(st.session_state.perplexity_market)
            else:
                st.markdown(st.session_state.perplexity_market)
            results_displayed = True
        
        # === [NEW] 비상장사 멀티에이전트 AI 분석 섹션 ===
        st.header("🚀 [NEW] 비상장사 멀티에이전트 AI 분석")
        
        # 멀티에이전트 설정
        st.subheader("🎯 전문가 에이전트 선택")
        default_agents = ["financial_analyst", "investment_analyst", "market_analyst", "risk_manager"]
        selected_agents = []
        
        cols = st.columns(3)
        for i, (agent_key, agent_info) in enumerate(UNLISTED_FINANCIAL_AGENTS.items()):
            with cols[i % 3]:
                is_selected = st.checkbox(
                    f"{agent_info['emoji']} **{agent_info['name']}**",
                    value=(agent_key in default_agents),
                    help=agent_info['description'],
                    key=f"unlisted_agent_{agent_key}"
                )
                if is_selected:
                    selected_agents.append(agent_key)
        
        if len(selected_agents) == 0:
            st.warning("⚠️ 최소 1명의 전문가를 선택해주세요.")
        elif len(selected_agents) > 6:
            st.warning("⚠️ 최대 6명까지 선택 가능합니다.")
        else:
            st.success(f"✅ {len(selected_agents)}명의 전문가가 선택되었습니다.")
        
        if st.button("🚀 비상장사 멀티에이전트 분석 실행"):
            if company_name and len(selected_agents) > 0:
                with st.spinner("비상장사 멀티에이전트 분석을 수행하고 있습니다..."):
                    # 분석 데이터 구성 (입력값 + Perplexity 조사 결과)
                    analysis_data = f"기업명: {company_name}\n업종: {industry}\n"
                    
                    # Perplexity 조사 결과 추가
                    perplexity_result = get_unlisted_company_analysis_perplexity(company_name)
                    if perplexity_result:
                        analysis_data += f"\nPerplexity 조사 결과:\n{perplexity_result}\n"
                    
                    # 멀티에이전트 분석 실행
                    agent_analyses, cfo_analysis = run_unlisted_multi_agent_analysis(
                        company_name, 
                        analysis_data, 
                        selected_agents, 
                        model_name, 
                        debug_mode
                    )
                    
                    # 분석 결과 표시
                    st.success("✅ **비상장사 멀티에이전트 분석 완료**")
                    
                    # 에이전트별 분석 결과 표시
                    st.markdown("## 📋 전문가별 분석 결과")
                    
                    for analysis in agent_analyses:
                        if analysis['success']:
                            with st.expander(f"{analysis['agent_emoji']} {analysis['agent_name']} 분석", expanded=False):
                                st.markdown(analysis['analysis'])
                                
                                # Reasoning 과정 표시
                                if analysis.get('has_thinking', False) and analysis.get('thinking', '').strip():
                                    st.markdown("---")
                                    st.markdown("### 🧠 AI 사고 과정")
                                    st.text_area(
                                        "Reasoning 과정",
                                        value=analysis['thinking'],
                                        height=150,
                                        disabled=True,
                                        key=f"unlisted_thinking_{analysis['agent_key']}"
                                    )
                        else:
                            st.error(f"❌ {analysis['agent_emoji']} {analysis['agent_name']}: {analysis['error']}")
                    
                    # CFO 종합 분석 표시
                    st.markdown("## 👔 CFO 종합 분석 (Executive Summary)")
                    
                    if cfo_analysis['success']:
                        st.markdown(cfo_analysis['content'])
                    else:
                        st.error(f"CFO 종합 분석 실패: {cfo_analysis['error']}")
            else:
                st.warning("기업명을 입력하고 최소 1명의 전문가를 선택해주세요.")
        
        # === [기존] 기업 정보 입력 섹션 ===
        st.header("기업 정보 입력")
        
        # 기업 기본 정보
        col1, col2 = st.columns(2)
        with col1:
            company_name_legacy = st.text_input("기업명", key="company_name_legacy")
            industry_legacy = st.text_input("업종", key="industry_legacy")
            country = st.selectbox("국가", ["대한민국", "미국", "중국", "일본", "기타"], index=0)
            
        with col2:
            currency = st.selectbox("통화", ["KRW", "USD", "EUR", "JPY", "CNY"], index=0)
            analysis_date = st.date_input("분석 기준일", value=datetime.now().date())
            
        # 재무 정보 입력
        st.subheader("재무 정보")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            revenue = st.number_input("매출액", min_value=0.0, value=1000000000.0, step=100000000.0)
            net_income = st.number_input("당기순이익", min_value=0.0, value=100000000.0, step=10000000.0)
            total_assets = st.number_input("총자산", min_value=0.0, value=2000000000.0, step=100000000.0)
            
        with col2:
            ebitda = st.number_input("EBITDA", min_value=0.0, value=150000000.0, step=10000000.0)
            free_cash_flow = st.number_input("자유현금흐름", min_value=0.0, value=80000000.0, step=10000000.0)
            total_debt = st.number_input("총부채", min_value=0.0, value=500000000.0, step=10000000.0)
            
        with col3:
            market_cap = st.number_input("시가총액", min_value=0.0, value=1500000000.0, step=100000000.0)
            shares_outstanding = st.number_input("발행주식수", min_value=0.0, value=10000000.0, step=100000.0)
            current_price = st.number_input("현재주가", min_value=0.0, value=150.0, step=1.0)
            
        # 성장률 및 할인율 설정
        st.subheader("성장률 및 할인율 설정")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            revenue_growth_rate = st.slider("매출 성장률 (%)", -50.0, 100.0, 10.0, 1.0)
            profit_margin = st.slider("순이익률 (%)", -50.0, 50.0, 10.0, 0.5)
            
        with col2:
            discount_rate = st.slider("할인율 (%)", 5.0, 25.0, 12.0, 0.5)
            terminal_growth_rate = st.slider("터미널 성장률 (%)", 0.0, 10.0, 2.0, 0.1)
            
        with col3:
            beta = st.slider("베타", 0.5, 2.0, 1.0, 0.1)
            risk_free_rate = st.slider("무위험 수익률 (%)", 1.0, 10.0, 3.0, 0.1)
            
        # 시장 데이터
        st.subheader("시장 데이터")
        col1, col2 = st.columns(2)
        
        with col1:
            market_size = st.number_input("시장 규모", min_value=0.0, value=10000000000.0, step=1000000000.0)
            market_share = st.slider("시장 점유율 (%)", 0.0, 100.0, 5.0, 0.1)
            
        with col2:
            competitor_count = st.number_input("주요 경쟁사 수", min_value=0, value=5, step=1)
            industry_growth_rate = st.slider("산업 성장률 (%)", -20.0, 50.0, 8.0, 0.5)
            
        # 무형자산 정보
        st.subheader("무형자산 정보")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            r_and_d_cost = st.number_input("R&D 비용", min_value=0.0, value=50000000.0, step=1000000.0)
            patents_count = st.number_input("특허 수", min_value=0, value=10, step=1)
            
        with col2:
            trademarks_count = st.number_input("상표 수", min_value=0, value=5, step=1)
            technology_impact = st.slider("기술 영향도 (1-10)", 1, 10, 7, 1)
            
        with col3:
            brand_value = st.number_input("브랜드 가치", min_value=0.0, value=100000000.0, step=10000000.0)
            customer_loyalty = st.slider("고객 충성도 (1-10)", 1, 10, 6, 1)
            
        # 분석 실행 버튼
        if st.button("🚀 기업 가치 평가 실행"):
            if company_name_legacy:
                with st.spinner("기업 가치 평가를 수행하고 있습니다..."):
                    # 데이터 준비
                    company_info = {
                        'name': company_name_legacy,
                        'industry': industry_legacy,
                        'country': country,
                        'currency': currency,
                        'analysis_date': analysis_date.strftime('%Y-%m-%d')
                    }
                    
                    financial_data = {
                        'revenue': revenue,
                        'net_income': net_income,
                        'total_assets': total_assets,
                        'ebitda': ebitda,
                        'free_cash_flow': free_cash_flow,
                        'total_debt': total_debt,
                        'market_cap': market_cap,
                        'shares_outstanding': shares_outstanding,
                        'current_price': current_price,
                        'revenue_growth_rate': revenue_growth_rate,
                        'profit_margin': profit_margin,
                        'discount_rate': discount_rate,
                        'terminal_growth_rate': terminal_growth_rate,
                        'beta': beta,
                        'risk_free_rate': risk_free_rate
                    }
                    
                    market_data = {
                        'market_size': market_size,
                        'market_share': market_share,
                        'competitor_count': competitor_count,
                        'industry_growth_rate': industry_growth_rate,
                        'r_and_d_cost': r_and_d_cost,
                        'patents_count': patents_count,
                        'trademarks_count': trademarks_count,
                        'technology_impact': technology_impact,
                        'brand_value': brand_value,
                        'customer_loyalty': customer_loyalty
                    }
                    
                    # 통화 변환
                    if currency != 'KRW':
                        for key in ['revenue', 'net_income', 'total_assets', 'ebitda', 'free_cash_flow', 'total_debt', 'market_cap', 'brand_value', 'r_and_d_cost']:
                            if key in financial_data:
                                financial_data[key] = convert_currency(financial_data[key], currency, 'KRW', exchange_rates)
                            if key in market_data:
                                market_data[key] = convert_currency(market_data[key], currency, 'KRW', exchange_rates)
                    
                    # AI 에이전트 분석 실행
                    analysis_results = analyze_with_valuation_agents(
                        company_info, 
                        financial_data, 
                        market_data, 
                        active_agents, 
                        debug_mode, 
                        model_name
                    )
                    
                    # 가치 평가 계산
                    valuation_results = {}
                    
                    # DCF 모델
                    dcf_value = calculate_dcf(
                        financial_data['free_cash_flow'],
                        financial_data['revenue_growth_rate'] / 100,
                        financial_data['discount_rate'] / 100,
                        financial_data['terminal_growth_rate'] / 100
                    )
                    valuation_results['dcf'] = dcf_value
                    
                    # PER 모델
                    pers = [10, 15, 20, 25, 30]
                    per_values = []
                    for per in pers:
                        per_value = calculate_per_valuation(financial_data['net_income'], per)
                        per_values.append(per_value)
                    valuation_results['per'] = {'pers': pers, 'values': per_values}
                    
                    # EV/EBITDA 모델
                    ev_ebitda_value = calculate_ev_ebitda_valuation(
                        financial_data['ebitda'],
                        [8, 10, 12, 15, 18],
                        financial_data['total_debt']
                    )
                    valuation_results['ev_ebitda'] = ev_ebitda_value
                    
                    # 무형자산 가치
                    intangible_value = estimate_intangible_asset_value(
                        market_data['r_and_d_cost'],
                        market_data['patents_count'],
                        market_data['trademarks_count'],
                        market_data['technology_impact'],
                        market_data['market_size'],
                        market_data['market_share']
                    )
                    valuation_results['intangible'] = intangible_value
                    
                    # 결과 표시
                    st.success("✅ **기업 가치 평가 완료**")
                    
                    # 가치 평가 결과
                    st.subheader("💰 가치 평가 결과")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("DCF 가치", format_currency(dcf_value))
                        
                    with col2:
                        avg_per_value = sum(per_values) / len(per_values)
                        st.metric("평균 PER 가치", format_currency(avg_per_value))
                        
                    with col3:
                        st.metric("EV/EBITDA 가치", format_currency(ev_ebitda_value))
                        
                    with col4:
                        st.metric("무형자산 가치", format_currency(intangible_value))
                    
                    # AI 분석 결과
                    st.subheader("🤖 AI 에이전트 분석 결과")
                    
                    for agent_type, result in analysis_results.items():
                        if result['success']:
                            with st.expander(f"{result['emoji']} {result['title']}", expanded=False):
                                st.markdown(result['content'])
                                
                                if result.get('has_thinking', False) and result.get('thinking', '').strip():
                                    st.markdown("---")
                                    st.markdown("### 🧠 AI 사고 과정")
                                    st.text_area(
                                        "Reasoning 과정",
                                        value=result['thinking'],
                                        height=150,
                                        disabled=True,
                                        key=f"thinking_{agent_type}"
                                    )
                        else:
                            st.error(f"❌ {result['title']}: {result['error']}")
                    
                    # 분석 저장
                    save_valuation_analysis(company_info, financial_data, market_data, analysis_results, valuation_results)
                    
            else:
                st.warning("기업명을 입력해주세요.")
    
    with tab2:
        st.header("저장된 분석 조회")
        
        # 저장된 분석 목록 가져오기
        saved_analyses = get_saved_analyses()
        
        if saved_analyses:
            for analysis in saved_analyses:
                with st.expander(f"📊 {analysis['company_name']} - {analysis['analysis_date']}", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write(f"**업종:** {analysis['industry']}")
                        st.write(f"**통화:** {analysis['currency']}")
                        st.write(f"**매출액:** {format_currency(analysis['revenue'])}")
                        st.write(f"**당기순이익:** {format_currency(analysis['net_income'])}")
                        
                    with col2:
                        if st.button("📋 상세보기", key=f"detail_{analysis['id']}"):
                            detail = get_analysis_detail(analysis['id'])
                            if detail:
                                st.json(detail)
                        
                        if st.button("🗑️ 삭제", key=f"delete_{analysis['id']}"):
                            if delete_valuation_analysis(analysis['id']):
                                st.success("분석이 삭제되었습니다.")
                                st.rerun()
                            else:
                                st.error("삭제 중 오류가 발생했습니다.")
        else:
            st.info("저장된 분석이 없습니다.")

if __name__ == "__main__":
    main() 