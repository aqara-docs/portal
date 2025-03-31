import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

def calculate_npv(cash_flows, discount_rate, initial_investment):
    """순현재가치(NPV) 계산"""
    npv = -initial_investment
    for t, cf in enumerate(cash_flows, 1):
        npv += cf / (1 + discount_rate) ** t
    return npv

def calculate_irr(cash_flows, initial_investment):
    """내부수익률(IRR) 계산"""
    def npv_equation(rate):
        return calculate_npv(cash_flows, rate, initial_investment)
    
    # 이분법으로 IRR 찾기
    low, high = -0.99, 10.0
    for _ in range(1000):
        mid = (low + high) / 2
        if abs(npv_equation(mid)) < 0.000001:
            return mid
        elif npv_equation(mid) > 0:
            low = mid
        else:
            high = mid
    return mid

def calculate_payback_period(cash_flows, initial_investment):
    """회수기간 계산"""
    cumulative = -initial_investment
    for i, cf in enumerate(cash_flows, 1):
        cumulative += cf
        if cumulative >= 0:
            return i + (cumulative - cf) / cf
    return None

def main():
    st.set_page_config(page_title="재무 분석 도구", page_icon="💰", layout="wide")
    st.title("💰 종합 재무 분석 도구")

    # 메인 탭 구성
    tabs = st.tabs([
        "📊 기본 재무 분석",
        "💵 수익성 분석",
        "🎯 투자/가치 분석",
        "💰 비용 분석",
        "⏳ 시간가치 분석",
        "🏦 자금조달 분석"
    ])

    with tabs[0]:  # 기본 재무 분석
        st.header("기본 재무 분석")
        subtabs1 = st.tabs(["투자 분석", "재무비율 계산기", "손익 예측"])
        
        with subtabs1[0]:
            st.subheader("투자 프로젝트 분석")
            
            col1, col2 = st.columns(2)
            
            with col1:
                initial_investment = st.number_input("초기 투자금액", min_value=0.0, value=1000000.0, step=100000.0)
                project_years = st.number_input("프로젝트 기간 (년)", min_value=1, max_value=20, value=5)
                discount_rate = st.number_input("할인율 (%)", min_value=0.0, max_value=100.0, value=10.0) / 100

            with col2:
                st.subheader("연간 현금흐름 입력")
                cash_flows = []
                for year in range(project_years):
                    cf = st.number_input(f"{year+1}년차 현금흐름", value=300000.0, step=10000.0, key=f"cf_{year}")
                    cash_flows.append(cf)

            if st.button("분석 시작", use_container_width=True):
                # NPV 계산
                npv = calculate_npv(cash_flows, discount_rate, initial_investment)
                
                # IRR 계산
                irr = calculate_irr(cash_flows, initial_investment)
                
                # 회수기간 계산
                payback = calculate_payback_period(cash_flows, initial_investment)

                # 결과 표시
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("순현재가치 (NPV)", f"₩{npv:,.0f}")
                
                with col2:
                    st.metric("내부수익률 (IRR)", f"{irr*100:.2f}%")
                
                with col3:
                    st.metric("회수기간", f"{payback:.2f}년" if payback else "회수 불가")

                # 현금흐름 그래프
                cumulative_cf = [-initial_investment]
                for cf in cash_flows:
                    cumulative_cf.append(cumulative_cf[-1] + cf)

                fig = go.Figure()
                
                # 연간 현금흐름
                fig.add_trace(go.Bar(
                    x=list(range(project_years+1)),
                    y=[-initial_investment] + cash_flows,
                    name="연간 현금흐름"
                ))
                
                # 누적 현금흐름
                fig.add_trace(go.Scatter(
                    x=list(range(project_years+1)),
                    y=cumulative_cf,
                    name="누적 현금흐름",
                    line=dict(color='red')
                ))
                
                fig.update_layout(
                    title="현금흐름 분석",
                    xaxis_title="년차",
                    yaxis_title="금액 (₩)",
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)

        with subtabs1[1]:
            st.header("재무비율 계산기")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("수익성 비율")
                sales = st.number_input("매출액", min_value=0.0, value=1000000.0)
                gross_profit = st.number_input("매출총이익", min_value=0.0, value=400000.0)
                operating_income = st.number_input("영업이익", min_value=0.0, value=200000.0)
                net_income = st.number_input("당기순이익", min_value=0.0, value=150000.0)
                
            with col2:
                st.subheader("재무상태")
                total_assets = st.number_input("총자산", min_value=0.0, value=2000000.0)
                total_liabilities = st.number_input("총부채", min_value=0.0, value=800000.0)
                current_assets = st.number_input("유동자산", min_value=0.0, value=600000.0)
                current_liabilities = st.number_input("유동부채", min_value=0.0, value=400000.0)

            if st.button("비율 계산", use_container_width=True):
                # 수익성 비율
                gross_margin = (gross_profit / sales * 100) if sales else 0
                operating_margin = (operating_income / sales * 100) if sales else 0
                net_margin = (net_income / sales * 100) if sales else 0
                
                # 안정성 비율
                debt_ratio = (total_liabilities / total_assets * 100) if total_assets else 0
                current_ratio = (current_assets / current_liabilities * 100) if current_liabilities else 0
                
                # 결과 표시
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("매출총이익률", f"{gross_margin:.1f}%")
                    st.metric("영업이익률", f"{operating_margin:.1f}%")
                    st.metric("순이익률", f"{net_margin:.1f}%")
                
                with col2:
                    st.metric("부채비율", f"{debt_ratio:.1f}%")
                    st.metric("유동비율", f"{current_ratio:.1f}%")
                
                with col3:
                    equity = total_assets - total_liabilities
                    st.metric("자기자본", f"₩{equity:,.0f}")
                    st.metric("부채", f"₩{total_liabilities:,.0f}")

                # 재무상태 파이 차트
                fig = go.Figure(data=[
                    go.Pie(
                        labels=['자기자본', '부채'],
                        values=[equity, total_liabilities],
                        hole=.3
                    )
                ])
                
                fig.update_layout(title="자본 구조")
                st.plotly_chart(fig, use_container_width=True)

        with subtabs1[2]:
            st.header("손익 예측")
            
            col1, col2 = st.columns(2)
            
            with col1:
                base_sales = st.number_input("기준 매출액", min_value=0.0, value=1000000.0)
                growth_rate = st.number_input("연간 성장률 (%)", min_value=-100.0, max_value=100.0, value=5.0)
                forecast_years = st.number_input("예측 기간 (년)", min_value=1, max_value=10, value=5)
            
            with col2:
                cost_ratio = st.number_input("매출원가율 (%)", min_value=0.0, max_value=100.0, value=60.0)
                sga_ratio = st.number_input("판관비율 (%)", min_value=0.0, max_value=100.0, value=20.0)
                tax_rate = st.number_input("법인세율 (%)", min_value=0.0, max_value=100.0, value=22.0)

            if st.button("예측 시작", use_container_width=True):
                # 예측 데이터 생성
                years = list(range(forecast_years + 1))
                sales_forecast = [base_sales * (1 + growth_rate/100) ** year for year in years]
                cogs_forecast = [sales * cost_ratio/100 for sales in sales_forecast]
                gross_profit_forecast = [sales - cogs for sales, cogs in zip(sales_forecast, cogs_forecast)]
                sga_forecast = [sales * sga_ratio/100 for sales in sales_forecast]
                operating_income_forecast = [gp - sga for gp, sga in zip(gross_profit_forecast, sga_forecast)]
                net_income_forecast = [oi * (1 - tax_rate/100) for oi in operating_income_forecast]

                # 데이터프레임 생성
                df = pd.DataFrame({
                    '년도': [f'{year}년차' for year in years],
                    '매출액': sales_forecast,
                    '매출원가': cogs_forecast,
                    '매출총이익': gross_profit_forecast,
                    '판관비': sga_forecast,
                    '영업이익': operating_income_forecast,
                    '당기순이익': net_income_forecast
                })

                st.dataframe(df.style.format({col: '{:,.0f}' for col in df.columns if col != '년도'}))

                # 그래프 표시
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=df['년도'],
                    y=df['매출액'],
                    name="매출액",
                    line=dict(color='blue')
                ))
                
                fig.add_trace(go.Scatter(
                    x=df['년도'],
                    y=df['당기순이익'],
                    name="당기순이익",
                    line=dict(color='green')
                ))
                
                fig.update_layout(
                    title="매출액 및 순이익 예측",
                    xaxis_title="년도",
                    yaxis_title="금액 (₩)",
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:  # 수익성 분석
        st.header("수익성 분석")
        
        # Profit Margin & Markup 분석
        st.subheader("Profit Margin & Markup 분석")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selling_price = st.number_input("판매가격", min_value=0.0, value=10000.0, key="margin_price")
            cost_price = st.number_input("원가", min_value=0.0, value=7000.0, key="margin_cost")
        
        with col2:
            if st.button("마진 계산", key="calc_margin"):
                profit = selling_price - cost_price
                margin_percent = (profit / selling_price * 100) if selling_price > 0 else 0
                markup_percent = (profit / cost_price * 100) if cost_price > 0 else 0
                
                st.metric("Profit Margin (%)", f"{margin_percent:.1f}%")
                st.metric("Markup (%)", f"{markup_percent:.1f}%")
                st.metric("단위당 이익", f"₩{profit:,.0f}")
        
        with col3:
            st.markdown("""
            #### 마진 vs 마크업
            - **Profit Margin**: (판매가 - 원가) / 판매가
            - **Markup**: (판매가 - 원가) / 원가
            """)
            
            # 목표 마진/마크업 계산기 추가
            target_type = st.selectbox("목표 유형", ["Margin", "Markup"])
            target_percent = st.number_input(f"목표 {target_type} (%)", min_value=0.0, max_value=100.0, value=30.0)
            
            if st.button("목표 가격 계산"):
                if target_type == "Margin":
                    target_price = cost_price / (1 - target_percent/100)
                else:  # Markup
                    target_price = cost_price * (1 + target_percent/100)
                
                st.metric("목표 판매가격", f"₩{target_price:,.0f}")

    with tabs[2]:  # 투자/가치 분석
        st.header("투자 및 가치 분석")
        
        # Lifetime Value & AAC
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("고객 생애 가치 (LTV) 분석")
            monthly_revenue = st.number_input("월 평균 수익/고객", min_value=0.0, value=100000.0)
            retention_months = st.number_input("평균 유지 기간(월)", min_value=0, value=24)
            margin_percent = st.number_input("이익률(%)", min_value=0.0, max_value=100.0, value=30.0)
            
            if st.button("LTV 계산"):
                ltv = monthly_revenue * retention_months * (margin_percent/100)
                st.metric("고객 생애 가치(LTV)", f"₩{ltv:,.0f}")
                st.write(f"이 고객을 유치하는데 최대 ₩{ltv*0.3:,.0f} 까지 투자할 수 있습니다. (LTV의 30% 기준)")
        
        with col2:
            st.subheader("허용 획득 비용 (AAC) 분석")
            target_ltv = st.number_input("목표 LTV", min_value=0.0, value=2400000.0)
            overhead_ratio = st.number_input("간접비 비율(%)", min_value=0.0, max_value=100.0, value=20.0)
            profit_margin = st.number_input("목표 이익률(%)", min_value=0.0, max_value=100.0, value=25.0)
            
            if st.button("AAC 계산"):
                overhead = target_ltv * (overhead_ratio/100)
                required_profit = target_ltv * (profit_margin/100)
                aac = target_ltv - overhead - required_profit
                
                st.metric("허용 획득 비용(AAC)", f"₩{aac:,.0f}")
                st.write("#### 비용 구조")
                fig = go.Figure(data=[go.Pie(
                    labels=['AAC', '간접비', '목표 이익'],
                    values=[aac, overhead, required_profit],
                    hole=.3
                )])
                st.plotly_chart(fig)

    with tabs[3]:  # 비용 분석
        st.header("비용 분석")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("비용 구조 분석")
            fixed_costs = st.number_input("월 고정비용", min_value=0.0, value=5000000.0)
            unit_cost = st.number_input("단위당 변동비", min_value=0.0, value=5000.0)
            units = st.number_input("월 판매량", min_value=0, value=1000)
            unit_price = st.number_input("판매 단가", min_value=0.0, value=8000.0)
            
            if st.button("비용 분석"):
                total_variable_costs = unit_cost * units
                total_costs = fixed_costs + total_variable_costs
                revenue = unit_price * units
                profit = revenue - total_costs
                
                st.metric("총 비용", f"₩{total_costs:,.0f}")
                st.metric("영업이익", f"₩{profit:,.0f}")
                
                # 비용 구조 파이 차트
                fig = go.Figure(data=[go.Pie(
                    labels=['고정비', '변동비'],
                    values=[fixed_costs, total_variable_costs],
                    hole=.3
                )])
                fig.update_layout(title="비용 구조")
                st.plotly_chart(fig)
        
        with col2:
            st.subheader("손익분기점 분석")
            if st.button("손익분기점 계산"):
                unit_margin = unit_price - unit_cost
                breakeven_units = fixed_costs / unit_margin
                breakeven_revenue = breakeven_units * unit_price
                
                st.metric("손익분기점 수량", f"{breakeven_units:,.0f}개")
                st.metric("손익분기점 매출", f"₩{breakeven_revenue:,.0f}")
                
                # 손익분기점 그래프
                units_range = np.linspace(0, units*2, 100)
                revenue = units_range * unit_price
                total_costs = fixed_costs + (units_range * unit_cost)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=units_range, y=revenue, name='매출'))
                fig.add_trace(go.Scatter(x=units_range, y=total_costs, name='총비용'))
                fig.add_vline(x=breakeven_units, line_dash="dash", annotation_text="손익분기점")
                
                fig.update_layout(
                    title="손익분기점 분석",
                    xaxis_title="판매량",
                    yaxis_title="금액 (₩)"
                )
                st.plotly_chart(fig)

    with tabs[4]:  # 시간가치 분석
        st.header("시간가치 분석")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("화폐의 시간가치")
            future_value = st.number_input("미래 가치", min_value=0.0, value=1000000.0)
            interest_rate = st.number_input("연이율(%)", min_value=0.0, value=5.0)
            years = st.number_input("기간(년)", min_value=0, value=5)
            
            if st.button("현재가치 계산"):
                present_value = future_value / (1 + interest_rate/100) ** years
                st.metric("현재가치", f"₩{present_value:,.0f}")
                st.write(f"{years}년 후 ₩{future_value:,.0f}를 받기 위해서는 현재 ₩{present_value:,.0f}가 필요합니다.")
        
        with col2:
            st.subheader("복리 효과 분석")
            principal = st.number_input("초기 투자금", min_value=0.0, value=10000000.0)
            compound_rate = st.number_input("연복리율(%)", min_value=0.0, value=7.0)
            compound_years = st.number_input("투자기간(년)", min_value=0, value=10)
            
            if st.button("복리 계산"):
                future_amount = principal * (1 + compound_rate/100) ** compound_years
                total_interest = future_amount - principal
                
                st.metric("미래 가치", f"₩{future_amount:,.0f}")
                st.metric("총 이자", f"₩{total_interest:,.0f}")
                
                # 복리 효과 그래프
                years_range = np.arange(compound_years + 1)
                values = [principal * (1 + compound_rate/100) ** year for year in years_range]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=years_range,
                    y=values,
                    mode='lines+markers',
                    name='투자금 성장'
                ))
                
                fig.update_layout(
                    title="복리 효과",
                    xaxis_title="년차",
                    yaxis_title="금액 (₩)"
                )
                st.plotly_chart(fig)

    with tabs[5]:  # 자금조달 분석
        st.header("자금조달 분석")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("레버리지 분석")
            equity = st.number_input("자기자본", min_value=0.0, value=100000000.0)
            leverage_ratio = st.number_input("레버리지 비율", min_value=0.0, value=2.0)
            expected_return = st.number_input("예상 수익률(%)", min_value=-100.0, value=10.0)
            
            if st.button("레버리지 효과 계산"):
                borrowed = equity * leverage_ratio
                total_investment = equity + borrowed
                
                # 시나리오 분석
                scenarios = {
                    "낙관": expected_return * 1.5,
                    "예상": expected_return,
                    "비관": expected_return * 0.5
                }
                
                results = {}
                for scenario, return_rate in scenarios.items():
                    investment_return = total_investment * (return_rate/100)
                    interest_expense = borrowed * 0.05  # 가정: 5% 이자율
                    net_return = investment_return - interest_expense
                    roi_on_equity = (net_return / equity) * 100
                    results[scenario] = roi_on_equity
                
                # 결과 표시
                for scenario, roi in results.items():
                    st.metric(f"{scenario} 시나리오 ROE", f"{roi:.1f}%")
        
        with col2:
            st.subheader("자금조달 계층 분석")
            funding_needed = st.number_input("필요 자금", min_value=0.0, value=500000000.0)
            control_importance = st.slider("통제권 중요도", 0, 100, 50)
            
            if st.button("자금조달 방안 분석"):
                recommendations = []
                
                if control_importance >= 70:
                    recommendations.append({
                        "방식": "내부 자금조달",
                        "비중": "40-60%",
                        "장점": "통제권 유지, 부채 부담 없음",
                        "단점": "성장 속도 제한"
                    })
                    recommendations.append({
                        "방식": "대출",
                        "비중": "30-40%",
                        "장점": "통제권 유지",
                        "단점": "이자 부담"
                    })
                else:
                    recommendations.append({
                        "방식": "투자 유치",
                        "비중": "40-60%",
                        "장점": "빠른 성장 가능",
                        "단점": "지분 희석"
                    })
                    recommendations.append({
                        "방식": "대출",
                        "비중": "20-30%",
                        "장점": "절충안",
                        "단점": "이자 부담"
                    })
                
                # 결과를 표로 표시
                df_recommendations = pd.DataFrame(recommendations)
                st.table(df_recommendations)

if __name__ == "__main__":
    main() 