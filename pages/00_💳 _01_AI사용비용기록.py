import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
import requests
from datetime import datetime, date
import certifi
import plotly.express as px
import plotly.graph_objects as go

load_dotenv()
st.set_page_config(page_title="AI 사용비용 기록", page_icon="💸", layout="wide")
st.title("🤖💸 AI Tool 비용 정산")
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
        if password:
            st.error("관리자 권한이 필요합니다")
        st.stop()

def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def get_exchange_rate():
    api_key = os.getenv('EXCHANGE_API')
    if not api_key:
        return None
    try:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        resp = requests.get(url)
        data = resp.json()
        if data['result'] == 'success':
            return data['conversion_rates']['KRW']
        else:
            return None
    except Exception:
        return None

def get_exim_exchange_rate(base, target='KRW', date_str=None):
    """한국수출입은행 환율 API로 환율 조회 (개선된 버전 - 주말/공휴일 대응)"""
    api_key = os.getenv('EXIM_API_KEY')
    if not api_key:
        st.warning("🔑 EXIM_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return None
    
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')
    
    url = "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
    
    # 최대 7일 이전까지 검색하여 유효한 환율 데이터 찾기
    from datetime import timedelta
    
    try:
        original_date = datetime.strptime(date_str, '%Y%m%d')
        current_date = original_date
        
        for attempt in range(8):  # 최대 7일 이전까지 검색
            current_date_str = current_date.strftime('%Y%m%d')
            
            params = {
                "authkey": api_key,
                "searchdate": current_date_str,
                "data": "AP01"
            }
            
            try:
                # timeout 설정으로 API 응답 시간 제한
                resp = requests.get(url, params=params, verify=False, timeout=10)
                resp.raise_for_status()  # HTTP 오류 체크
                
                data = resp.json()
                
                # API 응답이 리스트이고 데이터가 있는지 확인
                if isinstance(data, list) and len(data) > 0:
                    # 데이터가 있으면 사용자에게 알림
                    if current_date_str != date_str:
                        formatted_original = original_date.strftime('%Y-%m-%d')
                        formatted_current = current_date.strftime('%Y-%m-%d')
                        st.info(f"📅 {formatted_original} 환율 데이터가 없어 {formatted_current}(최근 영업일) 데이터를 사용합니다.")
                    
                    # 환율 계산 로직
                    if base == 'KRW' and target != 'KRW':
                        for row in data:
                            if row['cur_unit'].startswith(target):
                                rate = float(row['deal_bas_r'].replace(',', ''))
                                return 1 / rate if rate else None
                    elif target == 'KRW' and base != 'KRW':
                        for row in data:
                            if row['cur_unit'].startswith(base):
                                rate = float(row['deal_bas_r'].replace(',', ''))
                                return rate
                    elif base == 'KRW' and target == 'KRW':
                        return 1.0
                    else:
                        base_rate = None
                        target_rate = None
                        for row in data:
                            if row['cur_unit'].startswith(base):
                                base_rate = float(row['deal_bas_r'].replace(',', ''))
                            if row['cur_unit'].startswith(target):
                                target_rate = float(row['deal_bas_r'].replace(',', ''))
                        if base_rate and target_rate:
                            return base_rate / target_rate
                        else:
                            return None
                
                # 데이터가 없으면 하루 이전으로 이동
                current_date = current_date - timedelta(days=1)
                
            except requests.exceptions.Timeout:
                if attempt == 0:  # 첫 번째 시도에서만 경고
                    st.warning("⏰ 환율 API 응답 시간 초과 (10초)")
                return None
            except requests.exceptions.RequestException as e:
                if attempt == 0:  # 첫 번째 시도에서만 경고
                    st.warning(f"🌐 환율 API 네트워크 오류: {e}")
                return None
            except ValueError as e:
                if attempt == 0:  # 첫 번째 시도에서만 경고
                    st.warning(f"📊 환율 데이터 파싱 오류: {e}")
                return None
        
        # 7일 동안 검색해도 데이터를 찾지 못한 경우
        formatted_original = original_date.strftime('%Y-%m-%d')
        st.warning(f"⚠️ {formatted_original}부터 7일 이전까지 환율 데이터를 찾지 못했습니다. 대체 환율을 사용합니다.")
        return None
                
    except Exception as e:
        st.warning(f"❌ 환율 API 예상치 못한 오류: {e}")
        return None

def get_fallback_exchange_rate(base, target='KRW'):
    """대체 환율 (고정값) - API 실패 시 사용"""
    fallback_rates = {
        'USD': 1300,  # 대략적인 USD-KRW 환율
        'EUR': 1400,  # 대략적인 EUR-KRW 환율
        'JPY': 9,     # 대략적인 JPY-KRW 환율
        'CNY': 180,   # 대략적인 CNY-KRW 환율
    }
    
    if base == 'KRW' and target != 'KRW':
        return 1 / fallback_rates.get(target, 1300)
    elif target == 'KRW' and base != 'KRW':
        return fallback_rates.get(base, 1300)
    elif base == 'KRW' and target == 'KRW':
        return 1.0
    else:
        base_rate = fallback_rates.get(base, 1300)
        target_rate = fallback_rates.get(target, 1300)
        return base_rate / target_rate

def convert_currency_exim(amount, base, target='KRW', use_fallback=True):
    """개선된 환율 변환 함수"""
    # 우선 실시간 환율 시도
    rate = get_exim_exchange_rate(base, target)
    
    if rate is not None:
        return amount * rate
    
    # 실시간 환율 실패 시 대체 환율 사용
    if use_fallback:
        fallback_rate = get_fallback_exchange_rate(base, target)
        st.info(f"💡 실시간 환율 조회 실패로 대체 환율({base}: {fallback_rate:.2f} KRW)을 사용합니다.")
        return amount * fallback_rate
    
    return None

def ensure_billing_cycle_column():
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM ai_tool_expenses LIKE 'billing_cycle'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE ai_tool_expenses ADD COLUMN billing_cycle VARCHAR(20) DEFAULT '월'")
            conn.commit()
    except Exception as e:
        st.warning(f"billing_cycle 컬럼 추가 중 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def insert_expense(reg_date, tool_name, amount, currency, note, billing_cycle):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ai_tool_expenses (reg_date, tool_name, amount, currency, note, billing_cycle) VALUES (%s, %s, %s, %s, %s, %s)",
            (reg_date, tool_name, amount, currency, note, billing_cycle)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"등록 오류: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_expense(id, reg_date, tool_name, amount, currency, note, billing_cycle):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE ai_tool_expenses SET reg_date=%s, tool_name=%s, amount=%s, currency=%s, note=%s, billing_cycle=%s WHERE id=%s",
            (reg_date, tool_name, amount, currency, note, billing_cycle, id)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"수정 오류: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def delete_expense(id):
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ai_tool_expenses WHERE id=%s", (id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"삭제 오류: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def fetch_expenses(start_date=None, end_date=None):
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT * FROM ai_tool_expenses"
        params = []
        if start_date and end_date:
            query += " WHERE reg_date BETWEEN %s AND %s"
            params = [start_date, end_date]
        query += " ORDER BY reg_date DESC, id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return pd.DataFrame(rows)
    finally:
        cursor.close()
        conn.close()

def convert_currency(amount, base, target):
    api_key = os.getenv('EXCHANGE_API')
    if not api_key:
        return None
    try:
        url = "https://www.ratexchanges.com/api/v1/convert"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
            "api_key": api_key
        }
        data = {
            "base": base,
            "target": target,
            "amount": amount
        }
        resp = requests.post(url, headers=headers, data=data)
        data = resp.json()
        if data.get('success') and 'converted_amount' in data:
            return data['converted_amount']
        else:
            return None
    except Exception as e:
        st.warning(f"환율 변환 오류: {e}")
        return None

def main():

    ensure_billing_cycle_column()
    tab1, tab2 = st.tabs(["비용 등록", "비용 내역/정산"])

    with tab1:
        st.header("AI Tool 사용비용 등록")
        with st.form("expense_form"):
            reg_date = st.date_input("등록일자", value=date.today())
            tool_name = st.text_input("툴 이름")
            amount = st.number_input("비용", min_value=0.0, step=0.01, format="%.2f")
            currency = st.selectbox("통화", ["USD", "KRW"])
            billing_cycle = st.selectbox("결제주기", ["월", "년", "1회", "분기"], index=0)
            note = st.text_area("비고")
            submitted = st.form_submit_button("등록")
        if submitted:
            if not tool_name or amount <= 0:
                st.error("툴 이름과 금액을 올바르게 입력하세요.")
            else:
                if insert_expense(reg_date, tool_name, amount, currency, note, billing_cycle):
                    st.success("비용이 성공적으로 등록되었습니다!")

    with tab2:
        st.header("AI Tool 사용비용 내역 및 정산")
        st.markdown("---")
        st.subheader("월 구독 자동입력")
        with st.form("auto_monthly_form"):
            auto_tool_name = st.text_input("툴 이름 (월 구독)", key="auto_tool_name")
            auto_start_date = st.date_input("구독 시작일", value=date.today(), key="auto_start_date")
            auto_amount = st.number_input("비용 (월 구독)", min_value=0.0, step=0.01, format="%.2f", key="auto_amount")
            auto_currency = st.selectbox("통화 (월 구독)", ["USD", "KRW"], key="auto_currency")
            auto_note = st.text_area("비고 (월 구독)", key="auto_note")
            auto_submitted = st.form_submit_button("월 구독 자동입력")
        if auto_submitted:
            if not auto_tool_name or auto_amount <= 0:
                st.error("툴 이름과 금액을 올바르게 입력하세요.")
            else:
                from datetime import timedelta
                today = date.today()
                current = auto_start_date
                inserted = 0
                while current <= today:
                    # 이미 DB에 있는지 확인 (툴 이름+날짜+결제주기(월)로 중복 체크)
                    df_exist = fetch_expenses(current, current)
                    exists = False
                    if not df_exist.empty:
                        exists = (
                            (df_exist['tool_name'] == auto_tool_name) &
                            (df_exist['reg_date'] == current) &
                            (df_exist['billing_cycle'] == '월')
                        ).any()
                    if not exists:
                        if insert_expense(current, auto_tool_name, auto_amount, auto_currency, auto_note, '월'):
                            inserted += 1
                    # 다음 달로 이동
                    year = current.year + (current.month // 12)
                    month = (current.month % 12) + 1
                    # 월말 문제 방지: 시작일이 29,30,31일이면 다음 달에 없는 경우 28일로 대체
                    day = min(current.day, 28)
                    try:
                        current = date(year, month, day)
                    except:
                        current = date(year, month, 28)
                st.success(f"{inserted}건의 월 구독 결제 내역이 자동 등록되었습니다.")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작일", value=date(2025, 1, 1), key="start")
        with col2:
            end_date = st.date_input("종료일", value=date.today(), key="end")
        df = fetch_expenses(start_date, end_date)
        if df.empty:
            st.info("해당 기간에 등록된 비용이 없습니다.")
        else:
            st.write(f"### {start_date} ~ {end_date} 비용 내역")
            st.dataframe(df)
            # 커스텀 표 + row별 버튼
            header_cols = st.columns([2, 2, 1, 1, 1.5, 2, 1, 1])
            headers = ["등록일자", "툴 이름", "비용", "통화", "결제주기", "비고", "수정", "삭제"]
            for col, h in zip(header_cols, headers):
                col.markdown(f"**{h}**")
            if 'edit_row_id' not in st.session_state:
                st.session_state.edit_row_id = None
            if 'edit_form_data' not in st.session_state:
                st.session_state.edit_form_data = None
            for idx, row in df.iterrows():
                cols = st.columns([2, 2, 1, 1, 1.5, 2, 1, 1])
                cols[0].write(row['reg_date'])
                cols[1].write(row['tool_name'])
                cols[2].write(row['amount'])
                cols[3].write(row['currency'])
                cols[4].write(row['billing_cycle'])
                cols[5].write(row['note'])
                if cols[6].button("수정", key=f"edit_{row['id']}"):
                    st.session_state.edit_row_id = row['id']
                    st.session_state.edit_form_data = row
                if cols[7].button("삭제", key=f"delete_{row['id']}"):
                    st.session_state.delete_row_id = row['id']
                # 삭제 확인 단계
                if st.session_state.get("delete_row_id") == row['id']:
                    confirm_col, cancel_col = st.columns([1,1])
                    if confirm_col.button(f"정말로 삭제하시겠습니까? (ID: {row['id']})", key=f"confirm_delete_{row['id']}"):
                        if delete_expense(row['id']):
                            st.success("삭제되었습니다.")
                            st.session_state.edit_row_id = None
                            st.session_state.delete_row_id = None
                            st.rerun()
                    if cancel_col.button("취소", key=f"cancel_delete_{row['id']}"):
                        st.session_state.delete_row_id = None
            # 수정 폼
            if st.session_state.edit_row_id:
                edit_row = st.session_state.edit_form_data
                st.write(f"### 기록 수정 (ID: {edit_row['id']})")
                with st.form("edit_expense_form"):
                    reg_date = st.date_input("등록일자", value=pd.to_datetime(edit_row['reg_date']).date(), key="edit_reg_date")
                    tool_name = st.text_input("툴 이름", value=edit_row['tool_name'], key="edit_tool_name")
                    amount = st.number_input("비용", min_value=0.0, step=0.01, format="%.2f", value=float(edit_row['amount']), key="edit_amount")
                    currency = st.selectbox("통화", ["USD", "KRW"], index=["USD", "KRW"].index(edit_row['currency']), key="edit_currency")
                    billing_cycle = st.selectbox("결제주기", ["월", "년", "1회", "분기"], index=["월", "년", "1회", "분기"].index(edit_row['billing_cycle'] if edit_row['billing_cycle'] else '월'), key="edit_billing_cycle")
                    note = st.text_area("비고", value=edit_row['note'], key="edit_note")
                    submitted = st.form_submit_button("저장")
                if submitted:
                    if not tool_name or amount <= 0:
                        st.error("툴 이름과 금액을 올바르게 입력하세요.")
                    else:
                        if update_expense(edit_row['id'], reg_date, tool_name, amount, currency, note, billing_cycle):
                            st.success("수정이 완료되었습니다.")
                            st.session_state.edit_row_id = None
                            st.rerun()
            # 통화별 합계
            total_usd = df[df['currency']=='USD']['amount'].sum()
            total_krw = df[df['currency']=='KRW']['amount'].sum()
            # 결제주기별 합계, 월 환산 합계, 1회(원타임) 결제 합계 계산만 (출력 X)
            for cycle in ["월", "년", "1회", "분기"]:
                cycle_sum = df[df['billing_cycle'].fillna('월') == cycle]['amount'].sum()
                # (출력 제거)
            def get_monthly_equiv(row):
                amt = row['amount']
                cycle = row.get('billing_cycle', '월') or '월'
                if cycle == '년':
                    return amt / 12
                elif cycle == '분기':
                    return amt / 3
                elif cycle == '1회':
                    return 0
                else:
                    return amt
            df['월환산금액'] = df.apply(get_monthly_equiv, axis=1)
            monthly_total = df['월환산금액'].sum()
            onetime_total = df[df['billing_cycle'] == '1회']['amount'].sum()
            # 실시간 환산 총계(원화, Exim API) - 개선된 버전
            st.subheader("💱 실시간 환율 환산")
            
            total_krw_converted = 0
            conversion_status = []
            
            # 환산 과정 표시를 위한 컨테이너
            status_container = st.container()
            
            with status_container:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_rows = len(df)
                
                for idx, row in df.iterrows():
                    amt = row['amount']
                    cur = row['currency']
                    tool = row['tool_name']
                    
                    # 진행률 업데이트
                    progress = (idx + 1) / total_rows
                    progress_bar.progress(progress)
                    status_text.text(f"환율 변환 중... {idx + 1}/{total_rows} ({tool})")
                    
                    if cur == 'KRW':
                        total_krw_converted += amt
                        conversion_status.append({
                            '툴명': tool,
                            '원금액': f"{cur} {amt:,.2f}",
                            '환산금액': f"₩{amt:,.0f}",
                            '상태': '✅ 원화'
                        })
                    else:
                        converted = convert_currency_exim(amt, cur, 'KRW', use_fallback=True)
                        if converted is not None:
                            total_krw_converted += converted
                            conversion_status.append({
                                '툴명': tool,
                                '원금액': f"{cur} {amt:,.2f}",
                                '환산금액': f"₩{converted:,.0f}",
                                '상태': '✅ 환산완료'
                            })
                        else:
                            conversion_status.append({
                                '툴명': tool,
                                '원금액': f"{cur} {amt:,.2f}",
                                '환산금액': '환산실패',
                                '상태': '❌ 실패'
                            })
                
                # 완료 후 진행률 바 제거
                progress_bar.empty()
                status_text.text("✅ 환율 변환 완료!")
            
            # 환산 상세 내역 표시
            if conversion_status:
                st.write("**환산 상세 내역:**")
                conversion_df = pd.DataFrame(conversion_status)
                st.dataframe(conversion_df, use_container_width=True)
                
                # 실패한 항목 개수 체크
                failed_count = len([s for s in conversion_status if '❌' in s['상태']])
                if failed_count > 0:
                    st.warning(f"⚠️ {failed_count}개 항목의 환율 변환에 실패했습니다. 대체 환율이 사용되었습니다.")
                else:
                    st.success("🎉 모든 항목의 환율 변환이 완료되었습니다!")
            
            # 월별 비용 막대그래프 추가
            st.subheader("📊 월별 비용 현황 (환율 변환 적용)")
            
            # 환율 변환된 데이터로 월별 집계 생성
            df_chart = df.copy()
            df_chart['reg_date'] = pd.to_datetime(df_chart['reg_date'])
            df_chart['year_month'] = df_chart['reg_date'].dt.strftime('%Y-%m')
            
            # 각 행에 대해 KRW 변환 금액 계산
            df_chart['krw_amount'] = 0.0
            
            for idx, row in df_chart.iterrows():
                amt = row['amount']
                cur = row['currency']
                
                if cur == 'KRW':
                    df_chart.loc[idx, 'krw_amount'] = amt
                else:
                    # 이미 변환된 결과 사용
                    converted = convert_currency_exim(amt, cur, 'KRW', use_fallback=True)
                    if converted is not None:
                        df_chart.loc[idx, 'krw_amount'] = converted
                    else:
                        df_chart.loc[idx, 'krw_amount'] = 0  # 변환 실패시 0으로 처리
            
            # 월별 집계
            monthly_krw_summary = df_chart.groupby('year_month')['krw_amount'].sum().reset_index()
            monthly_krw_summary.columns = ['월', 'KRW 변환 금액']
            
            if not monthly_krw_summary.empty:
                # 월별 KRW 변환 금액 막대그래프
                fig1 = go.Figure()
                
                fig1.add_trace(go.Bar(
                    x=monthly_krw_summary['월'],
                    y=monthly_krw_summary['KRW 변환 금액'],
                    name='KRW 변환 금액',
                    marker_color='#1f77b4',
                    text=monthly_krw_summary['KRW 변환 금액'].round(0),
                    texttemplate='₩%{text:,.0f}',
                    textposition='auto'
                ))
                
                fig1.update_layout(
                    title='월별 AI Tool 사용비용 (KRW 환율 적용)',
                    xaxis_title='월',
                    yaxis_title='비용 (₩)',
                    yaxis_tickformat=',.0f',
                    height=400,
                    showlegend=False
                )
                
                st.plotly_chart(fig1, use_container_width=True)
                
                # 결제주기별 월별 현황 (KRW 변환 적용)
                st.subheader("💳 결제주기별 월별 현황 (KRW 변환 적용)")
                billing_krw_summary = df_chart.groupby(['year_month', 'billing_cycle'])['krw_amount'].sum().reset_index()
                
                if not billing_krw_summary.empty:
                    # 결제주기별 색상 지정
                    billing_color_map = {
                        '월': '#1f77b4',
                        '년': '#ff7f0e', 
                        '1회': '#2ca02c',
                        '분기': '#d62728'
                    }
                    
                    fig2 = go.Figure()
                    
                    for billing_cycle in billing_krw_summary['billing_cycle'].unique():
                        billing_data = billing_krw_summary[billing_krw_summary['billing_cycle'] == billing_cycle]
                        fig2.add_trace(go.Bar(
                            x=billing_data['year_month'],
                            y=billing_data['krw_amount'],
                            name=f'{billing_cycle} 결제',
                            marker_color=billing_color_map.get(billing_cycle, '#9467bd'),
                            text=billing_data['krw_amount'].round(0),
                            texttemplate='₩%{text:,.0f}',
                            textposition='auto'
                        ))
                    
                    fig2.update_layout(
                        title='결제주기별 월별 비용 현황 (KRW 변환 적용)',
                        xaxis_title='월',
                        yaxis_title='비용 (₩)',
                        yaxis_tickformat=',.0f',
                        barmode='stack',
                        height=400,
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig2, use_container_width=True)
                
                # 월별 통계 테이블 (KRW 변환 적용)
                st.subheader("📋 월별 상세 통계 (KRW 변환 적용)")
                monthly_stats_krw = df_chart.groupby('year_month').agg({
                    'krw_amount': ['sum', 'count', 'mean'],
                    'tool_name': 'nunique'
                }).round(0)
                
                monthly_stats_krw.columns = ['총 비용 (₩)', '거래 건수', '평균 비용 (₩)', '사용 툴 수']
                monthly_stats_krw = monthly_stats_krw.reset_index()
                monthly_stats_krw.columns = ['월', '총 비용 (₩)', '거래 건수', '평균 비용 (₩)', '사용 툴 수']
                
                # 숫자 포맷팅
                monthly_stats_krw['총 비용 (₩)'] = monthly_stats_krw['총 비용 (₩)'].apply(lambda x: f"₩{x:,.0f}")
                monthly_stats_krw['평균 비용 (₩)'] = monthly_stats_krw['평균 비용 (₩)'].apply(lambda x: f"₩{x:,.0f}")
                
                st.dataframe(monthly_stats_krw, use_container_width=True)
                
                # 월별 증감율 계산 및 표시
                if len(monthly_krw_summary) > 1:
                    st.subheader("📈 월별 증감 추이")
                    monthly_change = monthly_krw_summary.copy()
                    monthly_change['전월 대비 증감액'] = monthly_change['KRW 변환 금액'].diff()
                    monthly_change['전월 대비 증감율 (%)'] = (monthly_change['KRW 변환 금액'].pct_change() * 100).round(1)
                    
                    # 증감 정보 차트
                    fig3 = go.Figure()
                    
                    # 월별 금액 (막대)
                    fig3.add_trace(go.Bar(
                        x=monthly_change['월'],
                        y=monthly_change['KRW 변환 금액'],
                        name='월별 비용',
                        marker_color='#1f77b4',
                        yaxis='y'
                    ))
                    
                    # 증감율 (선)
                    fig3.add_trace(go.Scatter(
                        x=monthly_change['월'],
                        y=monthly_change['전월 대비 증감율 (%)'],
                        name='전월 대비 증감율 (%)',
                        mode='lines+markers',
                        marker_color='red',
                        yaxis='y2'
                    ))
                    
                    fig3.update_layout(
                        title='월별 비용 및 증감율 추이',
                        xaxis_title='월',
                        yaxis=dict(title='비용 (₩)', side='left'),
                        yaxis2=dict(title='증감율 (%)', side='right', overlaying='y'),
                        height=400
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
                    
                    # 증감 테이블
                    change_display = monthly_change[['월', 'KRW 변환 금액', '전월 대비 증감액', '전월 대비 증감율 (%)']].copy()
                    change_display['KRW 변환 금액'] = change_display['KRW 변환 금액'].apply(lambda x: f"₩{x:,.0f}")
                    change_display['전월 대비 증감액'] = change_display['전월 대비 증감액'].apply(lambda x: f"₩{x:,.0f}" if pd.notna(x) else "-")
                    change_display['전월 대비 증감율 (%)'] = change_display['전월 대비 증감율 (%)'].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "-")
                    
                    st.dataframe(change_display, use_container_width=True)
            else:
                st.info("월별 차트를 표시할 데이터가 없습니다.")
            
            # CSV 다운로드
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("CSV 다운로드", csv, "ai_tool_expenses.csv", "text/csv")
            # 집계 정보 표로 출력 (중복 방지: 이 위치에만 출력)
            summary_data = [
                {"구분": "USD 합계", "금액": f"${total_usd:,.2f}"},
                {"구분": "원화 합계", "금액": f"₩{total_krw:,.0f}"},
                {"구분": "월 결제 합계", "금액": f"{df[df['billing_cycle'].fillna('월') == '월']['amount'].sum():,.2f} (원/달러 혼합)"},
                {"구분": "년 결제 합계", "금액": f"{df[df['billing_cycle'].fillna('월') == '년']['amount'].sum():,.2f} (원/달러 혼합)"},
                {"구분": "1회 결제 합계", "금액": f"{df[df['billing_cycle'].fillna('월') == '1회']['amount'].sum():,.2f} (원/달러 혼합)"},
                {"구분": "분기 결제 합계", "금액": f"{df[df['billing_cycle'].fillna('월') == '분기']['amount'].sum():,.2f} (원/달러 혼합)"},
                {"구분": "월 환산 총계(1회 결제 제외)", "금액": f"{monthly_total:,.2f} (원/달러 혼합)"},
                {"구분": "1회(원타임) 결제 합계", "금액": f"{onetime_total:,.2f} (원/달러 혼합, 월환산 총계에 미포함)"},
                {"구분": "실시간 환산 총계(원화, Exim API)", "금액": f"₩{total_krw_converted:,.0f}"},
            ]
            df_summary = pd.DataFrame(summary_data)
            st.table(df_summary)
            st.info("월환산 총계는 월/년/분기 결제만 포함하며, 1회(원타임) 결제는 별도 합계로 표기됩니다.")

if __name__ == "__main__":
    main() 