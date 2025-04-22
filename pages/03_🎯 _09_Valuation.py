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

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

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

def main():
    st.title("🎯 기업 가치 평가 시스템")
    
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
    company_name = st.text_input("기업명", value="YUER")
    industry = st.text_input("산업군", value="기술/제조")
    company_description = st.text_area(
        "기업 설명", 
        value="YUER은 IoT 기반 스마트 홈 제품을 제조하는 중국 기업으로, 특히 스마트 가전 및 에너지 관리 솔루션에 특화되어 있음"
    )
    
    # 통화 선택
    currency = st.selectbox(
        "기준 통화",
        options=["CNY", "KRW", "USD", "EUR", "JPY"],
        index=0
    )
    
    # 재무 데이터
    st.subheader("재무 정보")
    col1, col2 = st.columns(2)
    
    with col1:
        revenue = st.number_input("매출액", value=25000000.0, step=100000.0)
        operating_profit = st.number_input("영업이익", value=6250000.0, step=10000.0)
        net_income = st.number_input("당기순이익", value=5300000.0, step=10000.0)
        operating_margin = operating_profit / revenue if revenue else 0
        st.info(f"영업이익률: {operating_margin:.2%}")
    
    with col2:
        current_fcf = st.number_input("현재 FCF (Free Cash Flow)", value=5300000.0, step=10000.0)
        growth_rate = st.slider("예상 연간 성장률 (%)", 0.0, 30.0, 10.0) / 100
        discount_rate = st.slider("할인율 (%)", 5.0, 25.0, 15.0) / 100
        terminal_growth_rate = st.slider("영구 성장률 (%)", 1.0, 5.0, 3.0) / 100
    
    # PER 관련 정보
    st.subheader("PER 배수 설정")
    per_values = st.multiselect(
        "사용할 PER 배수",
        options=[8, 10, 12, 15, 18, 20, 24, 30],
        default=[12, 18, 24]
    )
    
    # 무형자산 관련 정보
    st.subheader("무형자산 및 기술가치 정보")
    col1, col2 = st.columns(2)
    
    with col1:
        r_and_d_cost = st.number_input("R&D 투자 비용", value=2000000.0, step=100000.0)
        patents_count = st.number_input("특허 개수", value=31, step=1)
        trademarks_count = st.number_input("상표권 개수", value=4, step=1)
    
    with col2:
        technology_impact = st.slider("기술 영향력 (0-1)", 0.0, 1.0, 0.7, step=0.01)
        market_size = st.number_input("관련 시장 규모", value=1000000000.0, step=10000000.0)
        market_share = st.slider("시장 점유율 (%)", 0.0, 10.0, 2.5) / 100
    
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
        
        # 결과 표시
        st.header("정량적 가치평가 결과")
        
        # DCF 결과
        st.subheader("1. DCF 방식 가치평가")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "기업가치 (DCF)",
                format_currency(dcf_results['company_value'], currency)
            )
        with col2:
            krw_value = convert_currency(dcf_results['company_value'], currency, 'KRW', exchange_rates)
            st.metric(
                "기업가치 (KRW)",
                format_currency(krw_value, 'KRW')
            )
        with col3:
            usd_value = convert_currency(dcf_results['company_value'], currency, 'USD', exchange_rates)
            st.metric(
                "기업가치 (USD)",
                format_currency(usd_value, 'USD')
            )
        
        # PER 결과
        st.subheader("2. PER 방식 가치평가")
        per_data = []
        for per, value in per_results.items():
            krw_value = convert_currency(value, currency, 'KRW', exchange_rates)
            usd_value = convert_currency(value, currency, 'USD', exchange_rates)
            per_data.append({
                'PER 배수': f'{per}배',
                f'기업가치 ({currency})': format_currency(value, currency),
                '기업가치 (KRW)': format_currency(krw_value, 'KRW'),
                '기업가치 (USD)': format_currency(usd_value, 'USD')
            })
        
        st.table(pd.DataFrame(per_data))
        
        # 무형자산 가치 결과
        st.subheader("3. 무형자산 가치평가")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "가중평균 무형자산 가치",
                format_currency(intangible_results['weighted_value'], currency)
            )
        with col2:
            krw_value = convert_currency(intangible_results['weighted_value'], currency, 'KRW', exchange_rates)
            st.metric(
                "무형자산 가치 (KRW)",
                format_currency(krw_value, 'KRW')
            )

if __name__ == "__main__":
    main() 