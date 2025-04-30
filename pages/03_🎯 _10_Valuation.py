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

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# MySQL Database configuration
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# 페이지 설정
st.set_page_config(page_title="기업 가치 평가 시스템", page_icon="🎯", layout="wide")

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
        
        return cursor.fetchall()
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

def main():
    st.title("🎯 기업 가치 평가 시스템")
    
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
        
        # 기본 정보 입력
        st.header("기업 정보 입력")
        company_name = st.text_input(
            "기업명",
            help="평가 대상 기업의 이름을 입력하세요.",
            placeholder="예: 조명 벤처 기업 A",
            value=""
        )
        industry = st.text_input(
            "산업군",
            help="기업이 속한 주요 산업 분야를 입력하세요.",
            placeholder="예: 전기/전자/조명",
            value=""
        )
        company_description = st.text_area(
            "기업 설명", 
            help="기업의 주요 사업 영역, 제품, 특징 등을 간단히 설명해주세요.",
            placeholder="예: LED 조명 제품을 전문으로 제조하는 벤처기업으로, 특히 스마트 조명 제어 시스템에 강점이 있음",
            value=""
        )
        
        # 통화 선택
        currency = st.selectbox(
            "기준 통화",
            options=["KRW", "USD", "CNY", "EUR", "JPY"],
            help="재무 정보의 기준이 되는 통화를 선택하세요.",
            index=0
        )
        
        # 재무 데이터
        st.subheader("재무 정보")
        col1, col2 = st.columns(2)
        
        with col1:
            revenue = st.number_input(
                "매출액",
                help="최근 연간 매출액을 입력하세요.",
                placeholder="예: 25,000,000",
                min_value=0.0,
                value=0.0,
                step=1000000.0,
                format="%.1f"
            )
            operating_profit = st.number_input(
                "영업이익",
                help="최근 연간 영업이익을 입력하세요.",
                placeholder="예: 5,000,000",
                min_value=0.0,
                value=0.0,
                step=1000000.0,
                format="%.1f"
            )
            depreciation = st.number_input(
                "감가상각비",
                help="연간 유형자산 감가상각비를 입력하세요.",
                placeholder="예: 1,500,000",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.1f"
            )
            amortization = st.number_input(
                "무형자산상각비",
                help="연간 무형자산 상각비를 입력하세요.",
                placeholder="예: 500,000",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.1f"
            )
            net_income = st.number_input(
                "당기순이익",
                help="최근 연간 당기순이익을 입력하세요.",
                placeholder="예: 4,000,000",
                min_value=0.0,
                value=0.0,
                step=1000000.0,
                format="%.1f"
            )
            operating_margin = operating_profit / revenue if revenue else 0
            ebitda = operating_profit + depreciation + amortization
            st.info(f"영업이익률: {operating_margin:.2%}")
            st.info(f"EBITDA: {format_currency(ebitda, currency)}")
        
        with col2:
            current_fcf = st.number_input(
                "현재 FCF (Free Cash Flow)",
                help="최근 연간 잉여현금흐름을 입력하세요. (영업활동 현금흐름 - 자본적 지출)",
                placeholder="예: 4,500,000",
                min_value=0.0,
                value=0.0,
                step=1000000.0,
                format="%.1f"
            )
            growth_rate = st.slider(
                "예상 연간 성장률 (%)",
                help="향후 5년간 예상되는 연평균 성장률을 입력하세요.",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=0.5
            ) / 100
            discount_rate = st.slider(
                "할인율 (%)",
                help="기업의 가중평균자본비용(WACC) 또는 요구수익률을 입력하세요.",
                min_value=5.0,
                max_value=25.0,
                value=15.0,
                step=0.5
            ) / 100
            terminal_growth_rate = st.slider(
                "영구 성장률 (%)",
                help="영구가치 산정을 위한 장기 성장률을 입력하세요. (일반적으로 2~3%)",
                min_value=1.0,
                max_value=5.0,
                value=3.0,
                step=0.1
            ) / 100
            net_debt = st.number_input(
                "순차입금 (총차입금 - 현금성자산)",
                help="총차입금에서 현금성자산을 차감한 순차입금을 입력하세요.",
                placeholder="예: 2,000,000",
                value=0.0,
                step=1000000.0,
                format="%.1f"
            )

        # EV/EBITDA 멀티플 설정
        st.subheader("EV/EBITDA 멀티플 설정")
        evebitda_values = st.multiselect(
            "사용할 EV/EBITDA 멀티플",
            help="기업가치 산정에 사용할 EV/EBITDA 배수를 선택하세요. (산업 평균: 8-12배)",
            options=[6, 8, 10, 12, 14, 16, 18, 20],
            default=[8, 12, 16]
        )
        
        # PER 관련 정보
        st.subheader("PER 배수 설정")
        per_values = st.multiselect(
            "사용할 PER 배수",
            help="기업가치 산정에 사용할 PER(주가수익비율) 배수를 선택하세요. (산업 평균: 15-20배)",
            options=[8, 10, 12, 15, 18, 20, 24, 30],
            default=[12, 18, 24]
        )
        
        # 무형자산 관련 정보
        st.subheader("무형자산 및 기술가치 정보")
        col1, col2 = st.columns(2)
        
        with col1:
            r_and_d_cost = st.number_input(
                "R&D 투자 비용",
                help="연간 연구개발 투자 비용을 입력하세요.",
                placeholder="예: 2,000,000",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.1f"
            )
            patents_count = st.number_input(
                "특허 개수",
                help="보유하고 있는 등록 특허 수를 입력하세요.",
                placeholder="예: 30",
                min_value=0,
                value=0,
                step=1
            )
            trademarks_count = st.number_input(
                "상표권 개수",
                help="보유하고 있는 상표권 수를 입력하세요.",
                placeholder="예: 5",
                min_value=0,
                value=0,
                step=1
            )
        
        with col2:
            technology_impact = st.slider(
                "기술 영향력 (0-1)",
                help="기술의 시장 영향력을 0~1 사이 값으로 평가해주세요. (1: 매우 높음)",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.01
            )
            market_size = st.number_input(
                "관련 시장 규모",
                help="기업이 속한 전체 시장의 규모(TAM)를 입력하세요.",
                placeholder="예: 1,000,000,000",
                min_value=0.0,
                value=0.0,
                step=10000000.0,
                format="%.1f"
            )
            market_share = st.slider(
                "시장 점유율 (%)",
                help="전체 시장에서 차지하는 점유율을 입력하세요.",
                min_value=0.0,
                max_value=100.0,
                value=2.5,
                step=0.1
            ) / 100

        # 계산 버튼
        if st.button("기업가치 평가 실행", type="primary"):
            # 입력 데이터 구성
            company_info = {
                'name': company_name,
                'industry': industry,
                'description': company_description,
                'currency': currency
            }
            
            financial_data = {
                'revenue': revenue,
                'operating_profit': operating_profit,
                'net_income': net_income,
                'current_fcf': current_fcf,
                'growth_rate': growth_rate,
                'discount_rate': discount_rate,
                'terminal_growth_rate': terminal_growth_rate,
                'r_and_d_cost': r_and_d_cost
            }
            
            market_data = {
                'per_values': per_values,
                'market_size': market_size,
                'market_share': market_share,
                'technology_impact': technology_impact,
                'patents_count': patents_count,
                'trademarks_count': trademarks_count
            }
            
            # 멀티 에이전트 분석 실행
            with st.spinner("AI 에이전트들이 분석중입니다..."):
                analysis_results = analyze_with_valuation_agents(
                    company_info,
                    financial_data,
                    market_data,
                    active_agents,
                    debug_mode,
                    model_name
                )
                
                if analysis_results:
                    st.write("## AI 에이전트 분석 결과")
                    
                    # 에이전트별 탭 생성
                    agent_tabs = st.tabs([
                        agent_name.replace('_', ' ').title() 
                        for agent_name, is_active in active_agents.items() 
                        if is_active
                    ])
                    
                    for tab, (agent_name, analysis) in zip(
                        agent_tabs,
                        {k: v for k, v in analysis_results.items() 
                         if active_agents.get(k, False)}.items()
                    ):
                        with tab:
                            st.markdown(f"### {agent_name.replace('_', ' ').title()} 분석")
                            display_mermaid_chart(analysis['analysis'])
                            
                            st.markdown("#### 가치평가 요약")
                            display_mermaid_chart(analysis['valuation_summary'])
                            
                            st.markdown("#### 리스크 평가")
                            display_mermaid_chart(analysis['risk_assessment'])
            
            # 기존 계산 로직 실행
            dcf_results = calculate_dcf(
                current_fcf, 
                growth_rate, 
                discount_rate, 
                terminal_growth_rate
            )
            
            per_results = calculate_per_valuation(net_income, per_values)
            
            intangible_results = estimate_intangible_asset_value(
                r_and_d_cost,
                patents_count,
                trademarks_count,
                technology_impact,
                market_size,
                market_share
            )
            
            # EV/EBITDA 결과
            st.subheader("4. EV/EBITDA 방식 가치평가")
            
            # EBITDA 계산
            ebitda = operating_profit + depreciation + amortization
            
            # 기본 EV/EBITDA 계산
            evebitda_results = calculate_ev_ebitda_valuation(ebitda, evebitda_values, net_debt)
            
            # 산업 기반 상세 분석
            current_multiple = evebitda_values[len(evebitda_values)//2]  # 중간값 사용
            detailed_analysis = analyze_evebitda_valuation(
                industry, 
                ebitda, 
                net_debt, 
                current_multiple,
                growth_rate
            )

            # 기본 EV/EBITDA 결과 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                ev_base = ebitda * current_multiple
                st.metric(
                    "기업가치 (EV/EBITDA)",
                    format_currency(ev_base, currency)
                )
            with col2:
                ev_krw = convert_currency(ev_base, currency, 'KRW', exchange_rates)
                st.metric(
                    "기업가치 (KRW)",
                    format_currency(ev_krw, 'KRW')
                )
            with col3:
                ev_usd = convert_currency(ev_base, currency, 'USD', exchange_rates)
                st.metric(
                    "기업가치 (USD)",
                    format_currency(ev_usd, 'USD')
                )

            # 산업 평균 분석 결과
            st.markdown("#### 산업 평균 대비 분석")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"- EBITDA: {format_currency(ebitda, currency)}")
                st.write(f"- 순차입금: {format_currency(net_debt, currency)}")
                st.write(f"- 산업 평균 멀티플: {detailed_analysis['industry_median']:.1f}배")
                st.write(f"- 산업 일반 범위: {detailed_analysis['industry_range'][0]:.1f}배 ~ {detailed_analysis['industry_range'][1]:.1f}배")
            
            with col2:
                st.write(f"- 성장성 반영 범위: {detailed_analysis['adjusted_range'][0]:.1f}배 ~ {detailed_analysis['adjusted_range'][1]:.1f}배")
                st.write(f"- 현재 평가: {detailed_analysis['assessment']}")
                st.write(f"- 적용 멀티플: {current_multiple}배")

            # 산업 기반 가치 평가 결과 표시
            st.markdown("#### 산업 평균 기반 추정 가치")
            industry_based_data = []
            for label, ev in detailed_analysis['enterprise_values'].items():
                eq = detailed_analysis['equity_values'][label]
                ev_krw = convert_currency(ev, currency, 'KRW', exchange_rates)
                ev_usd = convert_currency(ev, currency, 'USD', exchange_rates)
                eq_krw = convert_currency(eq, currency, 'KRW', exchange_rates)
                eq_usd = convert_currency(eq, currency, 'USD', exchange_rates)
                
                industry_based_data.append({
                    '구분': label.capitalize(),
                    f'기업가치 ({currency})': format_currency(ev, currency),
                    '기업가치 (KRW)': format_currency(ev_krw, 'KRW'),
                    '기업가치 (USD)': format_currency(ev_usd, 'USD'),
                    f'주주가치 ({currency})': format_currency(eq, currency),
                    '주주가치 (KRW)': format_currency(eq_krw, 'KRW'),
                    '주주가치 (USD)': format_currency(eq_usd, 'USD')
                })
            
            st.table(pd.DataFrame(industry_based_data))

            # 선택한 멀티플별 결과 표시
            st.markdown("#### 선택 멀티플별 추정 가치")
            evebitda_data = []
            for multiple in sorted(evebitda_values):
                ev = ebitda * multiple
                eq = ev - net_debt
                ev_krw = convert_currency(ev, currency, 'KRW', exchange_rates)
                ev_usd = convert_currency(ev, currency, 'USD', exchange_rates)
                eq_krw = convert_currency(eq, currency, 'KRW', exchange_rates)
                eq_usd = convert_currency(eq, currency, 'USD', exchange_rates)
                
                evebitda_data.append({
                    'EV/EBITDA': f'{multiple}배',
                    f'기업가치 ({currency})': format_currency(ev, currency),
                    '기업가치 (KRW)': format_currency(ev_krw, 'KRW'),
                    '기업가치 (USD)': format_currency(ev_usd, 'USD'),
                    f'주주가치 ({currency})': format_currency(eq, currency),
                    '주주가치 (KRW)': format_currency(eq_krw, 'KRW'),
                    '주주가치 (USD)': format_currency(eq_usd, 'USD')
                })
            
            st.table(pd.DataFrame(evebitda_data))

            # 주요 고려 요인 표시
            st.markdown("#### 주요 고려 요인")
            col1, col2 = st.columns(2)
            with col1:
                st.write("상향 요인:")
                for factor in detailed_analysis['factors']['high']:
                    st.write(f"- {factor}")
            with col2:
                st.write("하향 요인:")
                for factor in detailed_analysis['factors']['low']:
                    st.write(f"- {factor}")

            # 분석 결과를 데이터베이스에 저장
            valuation_results = {
                'dcf': dcf_results,
                'per': per_results,
                'intangible': intangible_results,
                'evebitda': {
                    'basic': evebitda_results,
                    'detailed': detailed_analysis
                }
            }
            
            success, analysis_id = save_valuation_analysis(
                company_info,
                financial_data,
                market_data,
                analysis_results,
                valuation_results
            )
            
            if success:
                st.success(f"분석 결과가 성공적으로 저장되었습니다. (분석 ID: {analysis_id})")
    
    with tab2:
        st.header("저장된 가치 평가 분석")
        analyses = get_saved_analyses()
        
        if analyses:
            # 분석 목록을 데이터프레임으로 표시
            df = pd.DataFrame(analyses)
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            df['revenue'] = df['revenue'].apply(lambda x: format_currency(x, 'KRW'))
            df['operating_profit'] = df['operating_profit'].apply(lambda x: format_currency(x, 'KRW'))
            df['market_size'] = df['market_size'].apply(lambda x: format_currency(x, 'KRW'))
            df['market_share'] = df['market_share'].apply(lambda x: f"{x*100:.1f}%")
            
            st.dataframe(df)
            
            # 상세 정보 조회
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_analysis = st.selectbox(
                    "상세 정보를 조회할 분석 선택",
                    options=analyses,
                    format_func=lambda x: f"{x['company_name']} ({x['created_at']})"
                )
            
            if selected_analysis:
                with col2:
                    if st.button("🗑️ 선택한 분석 삭제", type="secondary", help="선택한 분석을 데이터베이스에서 삭제합니다"):
                        if delete_valuation_analysis(selected_analysis['analysis_id']):
                            st.success("분석이 성공적으로 삭제되었습니다.")
                            st.rerun()  # 페이지 새로고침
                        else:
                            st.error("분석 삭제 중 오류가 발생했습니다.")
                
                st.write("### 상세 분석 정보")
                details = get_analysis_detail(selected_analysis['analysis_id'])
                
                if details:
                    # 기본 정보 표시
                    st.write("#### 기업 정보")
                    st.write(f"- 기업명: {details['basic_info']['company_name']}")
                    st.write(f"- 산업: {details['basic_info']['industry']}")
                    st.write(f"- 설명: {details['basic_info']['company_description']}")
                    
                    # 재무 정보 표시
                    st.write("#### 재무 정보")
                    financial_df = pd.DataFrame([details['financial_data']])
                    st.dataframe(financial_df)
                    
                    # AI 에이전트 분석 결과 표시
                    st.write("#### AI 에이전트 분석 결과")
                    
                    # 일반 에이전트 결과 먼저 표시
                    for analysis in [a for a in details['agent_analyses'] if a['agent_type'] != 'integration_agent']:
                        with st.expander(f"{analysis['agent_type'].replace('_', ' ').title()} 분석"):
                            st.write("분석 내용:")
                            display_mermaid_chart(analysis['analysis_content'])
                            
                            st.write("가치평가 요약:")
                            display_mermaid_chart(analysis['valuation_summary'])
                            
                            st.write("리스크 평가:")
                            display_mermaid_chart(analysis['risk_assessment'])
                    
                    # 통합 분석 결과 별도 표시
                    integration_analysis = next((a for a in details['agent_analyses'] if a['agent_type'] == 'integration_agent'), None)
                    if integration_analysis:
                        st.write("### 통합 분석 결과")
                        display_mermaid_chart(integration_analysis['analysis_content'])
                    
                    # 평가 결과 표시
                    st.write("#### 평가 결과")
                    
                    # DCF 분석 결과
                    dcf_result = next((r for r in details['valuation_results'] if r['valuation_method'] == 'dcf'), None)
                    if dcf_result:
                        st.write("### 1. DCF 방식 가치평가")
                        dcf_data = json.loads(dcf_result['result_data'])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(
                                "기업가치 (DCF)",
                                format_currency(dcf_data['company_value'], details['basic_info']['base_currency'])
                            )
                        with col2:
                            dcf_krw = convert_currency(dcf_data['company_value'], 
                                                     details['basic_info']['base_currency'], 
                                                     'KRW', 
                                                     get_exchange_rates())
                            st.metric(
                                "기업가치 (KRW)",
                                format_currency(dcf_krw, 'KRW')
                            )
                        with col3:
                            dcf_usd = convert_currency(dcf_data['company_value'], 
                                                     details['basic_info']['base_currency'], 
                                                     'USD', 
                                                     get_exchange_rates())
                            st.metric(
                                "기업가치 (USD)",
                                format_currency(dcf_usd, 'USD')
                            )
                        
                        # DCF 상세 정보
                        st.write("#### DCF 분석 상세")
                        fcf_data = []
                        for i, (fcf, pv) in enumerate(zip(dcf_data['future_fcfs'], dcf_data['present_values'])):
                            fcf_data.append({
                                '연도': f'Year {i+1}',
                                'FCF': format_currency(fcf, details['basic_info']['base_currency']),
                                '현재가치': format_currency(pv, details['basic_info']['base_currency'])
                            })
                        st.table(pd.DataFrame(fcf_data))
                        
                        st.write("#### 잔여가치")
                        st.write(f"- 잔여가치: {format_currency(dcf_data['terminal_value'], details['basic_info']['base_currency'])}")
                        st.write(f"- 잔여가치의 현재가치: {format_currency(dcf_data['terminal_value_pv'], details['basic_info']['base_currency'])}")
                    
                    # PER 분석 결과
                    per_result = next((r for r in details['valuation_results'] if r['valuation_method'] == 'per'), None)
                    if per_result:
                        st.write("### 2. PER 방식 가치평가")
                        per_data = json.loads(per_result['result_data'])
                        
                        per_table_data = []
                        for per, value in per_data.items():
                            value_krw = convert_currency(value, details['basic_info']['base_currency'], 'KRW', get_exchange_rates())
                            value_usd = convert_currency(value, details['basic_info']['base_currency'], 'USD', get_exchange_rates())
                            
                            per_table_data.append({
                                'PER': f'{per}배',
                                f'기업가치 ({details["basic_info"]["base_currency"]})': format_currency(value, details['basic_info']['base_currency']),
                                '기업가치 (KRW)': format_currency(value_krw, 'KRW'),
                                '기업가치 (USD)': format_currency(value_usd, 'USD')
                            })
                        st.table(pd.DataFrame(per_table_data))
                    
                    # 무형자산 가치 평가 결과
                    intangible_result = next((r for r in details['valuation_results'] if r['valuation_method'] == 'intangible'), None)
                    if intangible_result:
                        st.write("### 3. 무형자산 가치평가")
                        intangible_data = json.loads(intangible_result['result_data'])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(
                                "원가법 기반 가치",
                                format_currency(intangible_data['cost_based_value'], details['basic_info']['base_currency'])
                            )
                            st.metric(
                                "IP 기반 가치",
                                format_currency(intangible_data['ip_value'], details['basic_info']['base_currency'])
                            )
                        with col2:
                            st.metric(
                                "시장 기반 가치",
                                format_currency(intangible_data['market_based_value'], details['basic_info']['base_currency'])
                            )
                            st.metric(
                                "가중 평균 가치",
                                format_currency(intangible_data['weighted_value'], details['basic_info']['base_currency'])
                            )
                    
                    # EV/EBITDA 분석 결과
                    evebitda_result = next((r for r in details['valuation_results'] if r['valuation_method'] == 'evebitda'), None)
                    if evebitda_result:
                        st.write("### 4. EV/EBITDA 방식 가치평가")
                        evebitda_data = json.loads(evebitda_result['result_data'])
                        
                        # 기본 EV/EBITDA 결과
                        st.write("#### 기본 EV/EBITDA 분석")
                        evebitda_table_data = []
                        for multiple, values in evebitda_data['basic'].items():
                            ev = values['enterprise_value']
                            eq = values['equity_value']
                            
                            ev_krw = convert_currency(ev, details['basic_info']['base_currency'], 'KRW', get_exchange_rates())
                            ev_usd = convert_currency(ev, details['basic_info']['base_currency'], 'USD', get_exchange_rates())
                            eq_krw = convert_currency(eq, details['basic_info']['base_currency'], 'KRW', get_exchange_rates())
                            eq_usd = convert_currency(eq, details['basic_info']['base_currency'], 'USD', get_exchange_rates())
                            
                            evebitda_table_data.append({
                                'EV/EBITDA': f'{multiple}배',
                                f'기업가치 ({details["basic_info"]["base_currency"]})': format_currency(ev, details['basic_info']['base_currency']),
                                '기업가치 (KRW)': format_currency(ev_krw, 'KRW'),
                                '기업가치 (USD)': format_currency(ev_usd, 'USD'),
                                f'주주가치 ({details["basic_info"]["base_currency"]})': format_currency(eq, details['basic_info']['base_currency']),
                                '주주가치 (KRW)': format_currency(eq_krw, 'KRW'),
                                '주주가치 (USD)': format_currency(eq_usd, 'USD')
                            })
                        st.table(pd.DataFrame(evebitda_table_data))
                        
                        # 상세 분석 결과
                        detailed = evebitda_data['detailed']
                        st.write("#### 산업 평균 대비 분석")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"- 산업 평균 멀티플: {detailed['industry_median']:.1f}배")
                            st.write(f"- 산업 일반 범위: {detailed['industry_range'][0]:.1f}배 ~ {detailed['industry_range'][1]:.1f}배")
                        
                        with col2:
                            st.write(f"- 성장성 반영 범위: {detailed['adjusted_range'][0]:.1f}배 ~ {detailed['adjusted_range'][1]:.1f}배")
                            st.write(f"- 현재 평가: {detailed['assessment']}")
                        
                        # 주요 고려 요인
                        st.write("#### 주요 고려 요인")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("상향 요인:")
                            for factor in detailed['factors']['high']:
                                st.write(f"- {factor}")
                        with col2:
                            st.write("하향 요인:")
                            for factor in detailed['factors']['low']:
                                st.write(f"- {factor}")
        else:
            st.info("저장된 분석이 없습니다.")

if __name__ == "__main__":
    main() 