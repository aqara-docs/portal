import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
import graphviz

load_dotenv()

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

def create_decision_tree():
    """비즈니스 의사결정 트리 생성"""
    st.subheader("새 의사결정 트리 생성")
    
    # 성공 메시지 표시
    if 'tree_created' in st.session_state and st.session_state['tree_created']:
        st.success("✅ 의사결정 트리가 생성되었습니다!")
        st.session_state['tree_created'] = False  # 메시지 초기화
    
    with st.form("new_decision_tree"):
        title = st.text_input("의사결정 제목", placeholder="예: 신규 사업 진출 결정")
        description = st.text_area("상세 설명", placeholder="의사결정의 배경과 목적을 설명해주세요")
        
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox(
                "카테고리",
                ["신규 사업", "투자", "마케팅", "R&D", "인수합병", "기타"]
            )
        with col2:
            analysis_period = st.number_input(
                "분석 기간 (년)",
                min_value=1,
                max_value=10,
                value=5,
                help="투자 효과를 분석할 기간"
            )
        
        discount_rate = st.slider(
            "할인율 (%)",
            min_value=5.0,
            max_value=20.0,
            value=10.0,
            step=0.5,
            help="미래 현금흐름의 현재가치 계산에 사용될 할인율"
        )
        
        if st.form_submit_button("의사결정 트리 생성", type="primary"):
            if title and description:
                conn = connect_to_db()
                cursor = conn.cursor()
                
                try:
                    cursor.execute("""
                        INSERT INTO decision_trees 
                        (title, description, category, analysis_period, discount_rate, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        title, description, category, 
                        analysis_period, discount_rate,
                        st.session_state.get('user_id', 1)
                    ))
                    
                    tree_id = cursor.lastrowid
                    conn.commit()
                    
                    st.session_state['tree_created'] = True
                    st.session_state['current_tree_id'] = tree_id
                    st.session_state['adding_node'] = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                finally:
                    cursor.close()
                    conn.close()
            else:
                st.error("제목과 설명은 필수입니다.")

        # 예시 보여주기
        with st.expander("비즈니스 의사결정 트리 작성 예시"):
            st.markdown("""
            ### 의사결정 트리 예시: 신규 시장 진출
            
            **제목**: 동남아 시장 진출 전략
            
            **설명**: 동남아 시장 진출을 위한 전략적 의사결정
            
            **분석 기간**: 5년
            **할인율**: 12%
            
            **의사결정 구조**:
            1. 진입 방식 결정 (의사결정 노드)
               - 직접 진출
                 * 초기 투자: 50억
                 * 운영 비용: 연 10억
                 * 예상 매출: 연 30억
               - 현지 기업 인수
                 * 초기 투자: 100억
                 * 운영 비용: 연 5억
                 * 예상 매출: 연 40억
               
            2. 시장 반응 (확률 노드)
               - 긍정적 (40%)
                 * 시장 점유율: 15%
                 * 매출 증가율: 20%
               - 중립적 (40%)
                 * 시장 점유율: 10%
                 * 매출 증가율: 10%
               - 부정적 (20%)
                 * 시장 점유율: 5%
                 * 매출 감소율: -5%
            """)

def visualize_decision_tree(tree_id):
    """의사결정 트리 시각화"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 노드 정보 조회
        cursor.execute("""
            SELECT n.*, 
                   GROUP_CONCAT(o.option_name SEPARATOR '|') as options
            FROM decision_nodes n
            LEFT JOIN decision_options o ON n.node_id = o.decision_node_id
            WHERE n.tree_id = %s
            GROUP BY n.node_id
        """, (tree_id,))
        nodes = cursor.fetchall()
        
        if nodes:
            # Graphviz 그래프 생성
            dot = graphviz.Digraph()
            dot.attr(rankdir='TB')
            
            # 노드 타입별 아이콘
            icons = {
                'decision': '🔄',
                'chance': '🎲',
                'outcome': '🎯'
            }
            
            # 노드 추가
            for node in nodes:
                node_label = f"{icons[node['node_type']]} {node['question']}"
                if node['options']:
                    options = node['options'].split('|')
                    node_label += f"\n{len(options)}개 선택지"
                
                dot.node(str(node['node_id']), node_label)
                
                # 부모 노드와 연결
                if node['parent_id']:
                    dot.edge(str(node['parent_id']), str(node['node_id']))
            
            # 그래프 표시
            st.graphviz_chart(dot)
            
    except Exception as e:
        st.error(f"트리 시각화 중 오류가 발생했습니다: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def add_decision_node(tree_id, parent_id=None):
    """비즈니스 의사결정 노드 추가"""
    st.subheader("의사결정 노드 추가")
    
    # 트리 시각화
    visualize_decision_tree(tree_id)
    
    # 부모 노드 선택
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT node_id, question, node_type
            FROM decision_nodes
            WHERE tree_id = %s
            ORDER BY created_at
        """, (tree_id,))
        existing_nodes = cursor.fetchall()
        
        if existing_nodes:
            node_options = [("", "최상위 노드")] + [(str(node['node_id']), f"{node['question']} ({node['node_type']})") for node in existing_nodes]
            selected_parent = st.selectbox(
                "상위 노드 선택",
                options=[id for id, _ in node_options],
                format_func=lambda x: dict(node_options)[x],
                help="이 노드가 연결될 상위 노드를 선택하세요"
            )
            parent_id = int(selected_parent) if selected_parent else None
        
        with st.form(f"new_node_{st.session_state['form_key']}"):
            # 기본적으로 submit 버튼 활성화
            submit_disabled = False
            
            node_type = st.selectbox(
                "노드 타입",
                ["의사결정 노드", "확률 노드", "결과 노드"],
                help="의사결정=전략적 선택, 확률=시장 반응/외부 요인, 결과=최종 결과"
            )
            
            question = st.text_input("노드 제목", help="의사결정 사항이나 상황을 입력하세요")
            description = st.text_area("상세 설명", help="의사결정의 배경과 고려사항을 설명하세요")
            
            # 시장 분석 정보
            col1, col2 = st.columns(2)
            with col1:
                market_size = st.number_input(
                    "시장 규모 (억원)", 
                    min_value=0.0,
                    max_value=9999999999.99  # 최대값 제한
                )
                market_growth = st.number_input(
                    "시장 성장률 (%/년)", 
                    min_value=-100.0,
                    max_value=1000.0,
                    value=0.0
                )
            with col2:
                competition_level = st.slider("경쟁 강도", 1, 5)
                risk_level = st.slider("위험도", 1, 5)
            
            # 결과 노드가 필요한지 확인
            if parent_id:
                cursor.execute("""
                    WITH RECURSIVE node_path AS (
                        SELECT node_id, parent_id, node_type, 1 as level
                        FROM decision_nodes
                        WHERE node_id = %s
                        UNION ALL
                        SELECT n.node_id, n.parent_id, n.node_type, p.level + 1
                        FROM decision_nodes n
                        JOIN node_path p ON n.parent_id = p.node_id
                    )
                    SELECT COUNT(*) as outcome_count
                    FROM decision_nodes
                    WHERE tree_id = %s 
                    AND node_type = 'outcome'
                    AND node_id IN (
                        SELECT node_id FROM node_path
                    )
                """, (parent_id, tree_id))
                
                has_outcome = cursor.fetchone()['outcome_count'] > 0
                
                if node_type != 'outcome' and not has_outcome:
                    st.warning("⚠️ 이 경로에는 아직 결과 노드가 없습니다. 결과 노드를 추가해주세요.")

            # 노드 타입별 입력 필드
            if node_type == "의사결정 노드":
                st.write("### 전략적 대안")
                st.info("필요한 대안만 입력하세요. 비어있는 대안은 저장되지 않습니다.")
                options_data = {}
                
                # 고정된 5개의 대안 입력 필드
                for i in range(5):
                    st.write(f"#### 대안 {i+1}")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        option = st.text_input("대안 내용", key=f"option_{i}")
                        initial_investment = st.number_input(
                            "초기 투자비용 (억원)",
                            min_value=0.0,
                            key=f"investment_{i}"
                        )
                    with col2:
                        operating_cost = st.number_input(
                            "연간 운영비용 (억원)",
                            min_value=0.0,
                            key=f"opcost_{i}"
                        )
                        market_share = st.number_input(
                            "예상 시장 점유율 (%)",
                            min_value=0.0,
                            max_value=100.0,
                            key=f"share_{i}"
                        )
                    with col3:
                        expected_revenue = st.number_input(
                            "연간 예상매출 (억원)",
                            min_value=0.0,
                            key=f"revenue_{i}"
                        )
                        revenue_growth = st.number_input(
                            "매출 성장률 (%/년)",
                            value=0.0,
                            key=f"growth_{i}"
                        )
                    
                    if option:  # 대안 내용이 입력된 경우에만 재무 분석 수행
                        # 트리 정보 조회
                        cursor.execute("""
                            SELECT analysis_period, discount_rate
                            FROM decision_trees
                            WHERE tree_id = %s
                        """, (tree_id,))
                        tree_info = cursor.fetchone()
                        
                        if tree_info:
                            analysis_period = float(tree_info['analysis_period'])
                            discount_rate = float(tree_info['discount_rate']) / 100
                            
                            # NPV 계산
                            cash_flows = [-float(initial_investment)]
                            annual_cash_flow = float(expected_revenue) - float(operating_cost)
                            for year in range(int(analysis_period)):
                                cash_flows.append(annual_cash_flow * (1 + float(revenue_growth)/100)**year)
                            
                            npv = sum(float(cf) / (1 + discount_rate)**i for i, cf in enumerate(cash_flows))
                            
                            # ROI 계산
                            total_profit = sum(cash_flows[1:])
                            roi = (total_profit - float(initial_investment)) / float(initial_investment) * 100 if initial_investment > 0 else 0
                            
                            # 회수기간 계산
                            payback_period = float(initial_investment) / annual_cash_flow if annual_cash_flow > 0 else float('inf')
                            
                            options_data[option] = {
                                "initial_investment": initial_investment,
                                "operating_cost": operating_cost,
                                "expected_revenue": expected_revenue,
                                "market_share": market_share,
                                "revenue_growth": revenue_growth,
                                "npv": npv,
                                "roi": roi,
                                "payback_period": payback_period
                            }
                            
                            # 재무 분석 결과 표시
                            st.write("##### 재무 분석 결과")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("순현재가치(NPV)", f"{npv:,.1f} 억원")
                                st.metric("투자수익률(ROI)", f"{roi:,.1f}%")
                            with col2:
                                st.metric("회수기간", f"{payback_period:,.1f}년")
                                st.metric("연간 순이익", f"{annual_cash_flow:,.1f} 억원")
                    st.divider()
            
            elif node_type == "확률 노드":
                st.write("### 발생 가능한 시나리오")
                st.info("시나리오의 확률 합이 100%가 되어야 합니다.")
                options_data = {}
                total_prob = 0
                
                # 고정된 5개의 시나리오 입력 필드
                for i in range(5):
                    st.write(f"#### 시나리오 {i+1}")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        scenario = st.text_input("시나리오 내용", key=f"scenario_{i}")
                        prob = st.number_input(
                            "발생 확률 (%)",
                            min_value=0.0,
                            max_value=100.0,
                            key=f"prob_{i}"
                        )
                    with col2:
                        market_share = st.number_input(
                            "예상 시장 점유율 (%)",
                            min_value=0.0,
                            max_value=100.0,
                            key=f"share_{i}"
                        )
                        revenue_impact = st.number_input(
                            "매출 영향 (%)",
                            min_value=-100.0,
                            max_value=1000.0,
                            help="기존 매출 대비 증감률",
                            key=f"impact_{i}"
                        )
                    
                    if scenario:
                        total_prob += prob
                        options_data[scenario] = {
                            "probability": prob,
                            "market_share": market_share,
                            "revenue_impact": revenue_impact,
                            "expected_revenue": 0  # 기본값 설정
                        }
                
                # 부동소수점 오차를 고려한 확률 합계 체크
                if total_prob > 0 and abs(total_prob - 100) > 0.01:
                    st.warning(f"⚠️ 전체 확률의 합이 100%가 되어야 합니다. (현재: {total_prob:.1f}%)")
            
            else:  # 결과 노드
                st.write("### 최종 결과 분석")
                
                # 자동 계산된 값 표시
                st.info("💡 아래 값들은 선택한 경로를 기반으로 자동 계산됩니다:")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("예상 최종 매출", "자동 계산")
                    st.metric("누적 순이익", "자동 계산")
                with col2:
                    st.metric("최종 시장점유율", "자동 계산")
                    st.metric("투자수익률(ROI)", "자동 계산")
                
                # 사용자 입력 필요 항목
                st.write("#### 🎯 전략적 평가")
                col1, col2 = st.columns(2)
                with col1:
                    market_position = st.selectbox(
                        "시장 포지션",
                        ["리더", "챌린저", "팔로워", "니처"],
                        help="이 결과에서 예상되는 시장 내 위치"
                    )
                with col2:
                    strategic_fit = st.slider(
                        "전략 적합도",
                        min_value=1,
                        max_value=5,
                        help="회사의 전략 방향과의 부합도"
                    )
                
                # 리스크 평가
                st.write("#### ⚠️ 리스크 평가")
                risk_factors = st.multiselect(
                    "주요 리스크 요인",
                    ["기술", "시장", "경쟁", "규제", "운영", "재무"]
                )
                
                # 필수 입력 체크
                if not (market_position and strategic_fit and risk_factors):
                    st.error("결과 노드의 모든 필수 항목을 입력해주세요.")
                    submit_disabled = True
            
            # Submit 버튼
            submit_button = st.form_submit_button("노드 추가", type="primary", disabled=submit_disabled)
            
            if submit_button:
                if question:
                    conn = connect_to_db()
                    cursor = conn.cursor()
                    
                    try:
                        # 시장 규모 값 검증
                        if market_size > 9999999999.99:
                            market_size = 9999999999.99
                        
                        # 노드 타입 매핑
                        node_type_map = {
                            "의사결정 노드": "decision",
                            "확률 노드": "chance",
                            "결과 노드": "outcome"
                        }
                        
                        # 노드 추가
                        cursor.execute("""
                            INSERT INTO decision_nodes 
                            (tree_id, parent_id, node_type, question, description,
                             market_size, market_growth, competition_level, risk_level)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            tree_id,
                            parent_id,
                            node_type_map[node_type],
                            question,
                            description,
                            market_size,
                            market_growth,
                            competition_level,
                            risk_level
                        ))
                        
                        node_id = cursor.lastrowid
                        
                        # 노드 타입별 추가 정보 저장
                        if node_type == "결과 노드":
                            cursor.execute("""
                                INSERT INTO decision_outcomes
                                (decision_node_id, market_position, strategic_fit, risk_factors)
                                VALUES (%s, %s, %s, %s)
                            """, (
                                node_id,
                                market_position,
                                strategic_fit,
                                ','.join(risk_factors) if risk_factors else None
                            ))
                        elif node_type == "의사결정 노드":
                            for option, data in options_data.items():
                                cursor.execute("""
                                    INSERT INTO decision_options
                                    (decision_node_id, option_name, initial_investment, operating_cost,
                                     expected_revenue, market_share, probability, npv, roi,
                                     payback_period)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    node_id,
                                    option,
                                    data['initial_investment'],
                                    data['operating_cost'],
                                    data['expected_revenue'],
                                    data['market_share'],
                                    None,  # probability는 확률 노드에서만 사용
                                    data['npv'],
                                    data['roi'],
                                    data['payback_period']
                                ))
                        elif node_type == "확률 노드":
                            for scenario, data in options_data.items():
                                cursor.execute("""
                                    INSERT INTO decision_options
                                    (decision_node_id, option_name, market_share, probability,
                                     revenue_impact, expected_revenue)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (
                                    node_id,
                                    scenario,
                                    data['market_share'],
                                    data['probability'],
                                    data['revenue_impact'],
                                    data['expected_revenue']
                                ))
                        
                        conn.commit()
                        st.success("✅ 노드가 추가되었습니다!")
                        st.session_state['form_key'] += 1
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                        conn.rollback()
                    finally:
                        cursor.close()
                        conn.close()
                else:
                    st.error("노드 제목은 필수입니다.")

    finally:
        cursor.close()
        conn.close()

def calculate_path_values(tree_id, node_id=None):
    """경로별 기대값 계산"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if node_id is None:
            # 트리의 루트 노드 찾기
            cursor.execute("""
                SELECT node_id 
                FROM decision_nodes 
                WHERE tree_id = %s AND parent_id IS NULL
                LIMIT 1
            """, (tree_id,))
            root = cursor.fetchone()
            if not root:
                return []
            node_id = root['node_id']
        
        # 현재 노드 정보 조회
        cursor.execute("""
            SELECT n.*, 
                   GROUP_CONCAT(
                       CONCAT(o.option_name, ':', 
                             COALESCE(o.probability, ''), ':',
                             COALESCE(o.expected_revenue, 0)
                       ) SEPARATOR '|'
                   ) as options
            FROM decision_nodes n
            LEFT JOIN decision_options o ON n.node_id = o.decision_node_id
            WHERE n.node_id = %s
            GROUP BY n.node_id
        """, (node_id,))
        node = cursor.fetchone()
        
        if not node:
            return []
        
        paths = []
        
        if node['node_type'] == 'decision':
            # 의사결정 노드의 각 선택지는 상호 배타적
            if node['options']:
                for option_data in node['options'].split('|'):
                    option_parts = option_data.split(':')
                    choice = option_parts[0]
                    revenue = float(option_parts[2])
                    
                    # 자식 노드 찾기
                    cursor.execute("""
                        SELECT node_id 
                        FROM decision_nodes 
                        WHERE parent_id = %s
                    """, (node_id,))
                    children = cursor.fetchall()
                    
                    child_paths = []
                    for child in children:
                        child_paths.extend(calculate_path_values(tree_id, child['node_id']))
                    
                    if child_paths:
                        # 자식 경로가 있는 경우
                        for child_path in child_paths:
                            paths.append({
                                'description': f"{choice} → {child_path['description']}",
                                'expected_value': child_path['expected_value'] + revenue,
                                'probability': child_path['probability'],  # 의사결정은 확률에 영향 없음
                                'steps': [choice] + child_path['steps']
                            })
                    else:
                        # 리프 노드인 경우
                        paths.append({
                            'description': choice,
                            'expected_value': revenue,
                            'probability': 100,  # 의사결정 노드는 100% 확률
                            'steps': [choice]
                        })
        
        elif node['node_type'] == 'chance':
            # 확률 노드의 시나리오들의 확률 합은 100%여야 함
            if node['options']:
                total_prob = 0
                for option_data in node['options'].split('|'):
                    option_parts = option_data.split(':')
                    scenario = option_parts[0]
                    prob = float(option_parts[1])
                    revenue_impact = float(option_parts[2])
                    total_prob += prob
                    
                    # 자식 노드 찾기
                    cursor.execute("""
                        SELECT node_id 
                        FROM decision_nodes 
                        WHERE parent_id = %s
                    """, (node_id,))
                    children = cursor.fetchall()
                    
                    child_paths = []
                    for child in children:
                        child_paths.extend(calculate_path_values(tree_id, child['node_id']))
                    
                    if child_paths:
                        # 자식 경로가 있는 경우
                        for child_path in child_paths:
                            paths.append({
                                'description': f"{scenario} ({prob}%) → {child_path['description']}",
                                'expected_value': child_path['expected_value'] * (1 + revenue_impact/100),
                                'probability': prob,  # 현재 시나리오의 확률만 사용
                                'steps': [scenario] + child_path['steps']
                            })
                    else:
                        # 리프 노드인 경우
                        paths.append({
                            'description': f"{scenario} ({prob}%)",
                            'expected_value': revenue_impact,
                            'probability': prob,
                            'steps': [scenario]
                        })
                
                if abs(total_prob - 100) > 0.01:  # 부동소수점 오차 허용
                    st.warning(f"⚠️ 확률의 합이 100%가 아닙니다 (현재: {total_prob:.1f}%)")
        
        return paths
    
    finally:
        cursor.close()
        conn.close()

def update_node_expected_values(tree_id):
    """노드별 기대값 업데이트"""
    paths = calculate_path_values(tree_id)
    
    if not paths:
        return
    
    # 각 경로의 기대값을 기반으로 노드별 최적 선택 결정
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        for path in paths:
            steps = path['steps']
            expected_value = path['expected_value']
            
            # 경로상의 각 노드 업데이트
            for i, step in enumerate(steps):
                cursor.execute("""
                    UPDATE decision_nodes n
                    JOIN decision_options o ON n.node_id = o.decision_node_id
                    SET n.expected_value = GREATEST(COALESCE(n.expected_value, 0), %s),
                        n.optimal_choice = CASE 
                            WHEN %s > COALESCE(n.expected_value, 0) THEN %s 
                            ELSE n.optimal_choice 
                        END
                    WHERE o.option_name = %s
                """, (expected_value, expected_value, step, step))
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def view_decision_tree(tree_id):
    """의사결정 트리 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 트리 정보 조회
        cursor.execute("""
            SELECT dt.*, u.user_name as creator_name
            FROM decision_trees dt
            LEFT JOIN dot_user_credibility u ON dt.created_by = u.user_id
            WHERE dt.tree_id = %s
        """, (tree_id,))
        tree = cursor.fetchone()
        
        if tree:
            st.write(f"## {tree['title']}")
            st.write(f"**카테고리**: {tree['category']}")
            st.write(f"**작성자**: {tree['creator_name']}")
            st.write(f"**분석 기간**: {tree['analysis_period']}년")
            st.write(f"**할인율**: {tree['discount_rate']}%")
            
            if tree['description']:
                st.write("### 설명")
                st.info(tree['description'])
            
            # 노드 정보 조회
            cursor.execute("""
                SELECT n.*,
                       GROUP_CONCAT(
                           CONCAT(
                               o.option_name, ':', 
                               COALESCE(o.initial_investment, 0), ':',
                               COALESCE(o.operating_cost, 0), ':',
                               COALESCE(o.expected_revenue, 0), ':',
                               COALESCE(o.market_share, 0), ':',
                               COALESCE(o.probability, 0), ':',
                               COALESCE(o.npv, 0), ':',
                               COALESCE(o.roi, 0), ':',
                               COALESCE(o.payback_period, 0)
                           ) SEPARATOR '|'
                       ) as options
                FROM decision_nodes n
                LEFT JOIN decision_options o ON n.node_id = o.decision_node_id
                WHERE n.tree_id = %s
                GROUP BY n.node_id
                ORDER BY n.created_at
            """, (tree_id,))
            nodes = cursor.fetchall()
            
            if nodes:
                st.write("### 의사결정 구조")
                
                # 각 노드 정보 표시
                for node in nodes:
                    if node['node_type'] == 'decision':
                        st.write(f"### 🔄 의사결정: {node['question']}")
                        if node['description']:
                            st.info(node['description'])
                        
                        st.write("**시장 분석:**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("시장 규모", f"{node['market_size']:,.0f} 억원")
                            st.metric("시장 성장률", f"{node['market_growth']}%")
                        with col2:
                            st.metric("경쟁 강도", f"{node['competition_level']}/5")
                            st.metric("위험도", f"{node['risk_level']}/5")
                        
                        if node['options']:
                            st.write("**전략적 대안:**")
                            for option_data in node['options'].split('|'):
                                option_parts = option_data.split(':')
                                option = option_parts[0]
                                initial_investment = float(option_parts[1])
                                operating_cost = float(option_parts[2])
                                expected_revenue = float(option_parts[3])
                                market_share = float(option_parts[4])
                                npv = float(option_parts[6])
                                roi = float(option_parts[7])
                                payback = float(option_parts[8])
                                
                                st.write(f"#### {option}")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("초기 투자", f"{initial_investment:,.0f} 억원")
                                    st.metric("운영 비용", f"{operating_cost:,.0f} 억원/년")
                                with col2:
                                    st.metric("예상 매출", f"{expected_revenue:,.0f} 억원/년")
                                    st.metric("시장 점유율", f"{market_share:.1f}%")
                                with col3:
                                    st.metric("NPV", f"{npv:,.0f} 억원")
                                    st.metric("ROI", f"{roi:.1f}%")
                                    st.metric("회수기간", f"{payback:.1f}년")
                    
                    elif node['node_type'] == 'chance':
                        st.write(f"### 🎲 확률 노드: {node['question']}")
                        if node['description']:
                            st.info(node['description'])
                        
                        if node['options']:
                            st.write("**시나리오 분석:**")
                            total_prob = 0
                            for option_data in node['options'].split('|'):
                                option_parts = option_data.split(':')
                                scenario = option_parts[0]
                                market_share = float(option_parts[4])
                                prob = float(option_parts[5])
                                expected_revenue = float(option_parts[3])
                                
                                st.write(f"#### {scenario}")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("발생 확률", f"{prob:.1f}%")
                                    st.metric("시장 점유율", f"{market_share:.1f}%")
                                with col2:
                                    st.metric("예상 매출", f"{expected_revenue:,.0f} 억원")
                                    st.metric("기대 매출", f"{expected_revenue * prob/100:,.0f} 억원")
                                
                                total_prob += prob
                            
                            if total_prob != 100:
                                st.warning(f"⚠️ 전체 확률의 합이 100%가 아닙니다 (현재: {total_prob:.1f}%)")
                    
                    else:  # outcome node
                        st.write(f"### 🎯 결과: {node['question']}")
                        if node['description']:
                            st.info(node['description'])
                
            else:
                st.info("아직 등록된 노드가 없습니다.")
            
            # 경로 분석 결과 표시
            st.write("### 📊 경로 분석")
            paths = calculate_path_values(tree_id)
            
            if paths:
                # 기대값 기준으로 경로 정렬
                paths.sort(key=lambda x: x['expected_value'], reverse=True)
                
                # 최적 경로 표시
                optimal_path = paths[0]
                col1, col2 = st.columns(2)
                with col1:
                    st.success("🌟 최적 경로")
                    st.info(optimal_path['description'])
                with col2:
                    st.metric("기대값", f"{optimal_path['expected_value']:,.0f} 억원")
                    st.metric("성공 확률", f"{optimal_path['probability']:.1f}%")
                
                # 전체 경로 분석 테이블
                st.write("#### 전체 경로 분석")
                
                # 데이터프레임 생성
                path_data = []
                for path in paths:
                    path_data.append({
                        "순위": len(path_data) + 1,
                        "의사결정 경로": path['description'],
                        "기대값 (억원)": f"{path['expected_value']:,.0f}",
                        "확률 (%)": f"{path['probability']:.1f}",
                        "상대 비교": f"{(path['expected_value']/optimal_path['expected_value']*100):.1f}%"
                    })
                
                df = pd.DataFrame(path_data)
                
                # 스타일이 적용된 테이블 표시
                st.dataframe(
                    df,
                    column_config={
                        "순위": st.column_config.NumberColumn(
                            "순위",
                            help="기대값 기준 순위",
                            format="%d"
                        ),
                        "의사결정 경로": st.column_config.TextColumn(
                            "의사결정 경로",
                            help="선택한 대안과 발생 가능한 시나리오",
                            width="large"
                        ),
                        "기대값 (억원)": st.column_config.NumberColumn(
                            "기대값 (억원)",
                            help="경로의 기대 수익",
                            format="%d"
                        ),
                        "확률 (%)": st.column_config.NumberColumn(
                            "확률 (%)",
                            help="경로의 발생 확률",
                            format="%.1f"
                        ),
                        "상대 비교": st.column_config.ProgressColumn(
                            "최적 경로 대비",
                            help="최적 경로 대비 기대값 비율",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # 요약 통계
                st.write("#### 📈 요약 통계")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "평균 기대값",
                        f"{sum(p['expected_value'] for p in paths)/len(paths):,.0f} 억원"
                    )
                with col2:
                    st.metric(
                        "최대 기대값",
                        f"{max(p['expected_value'] for p in paths):,.0f} 억원"
                    )
                with col3:
                    st.metric(
                        "최소 기대값",
                        f"{min(p['expected_value'] for p in paths):,.0f} 억원"
                    )
            else:
                st.info("아직 분석할 경로가 없습니다. 노드를 추가해주세요.")
    
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {str(e)}")
        st.exception(e)
    finally:
        cursor.close()
        conn.close()

def update_decision_tree_tables():
    """의사결정 트리 테이블 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # decision_nodes 테이블 수정
        cursor.execute("""
            ALTER TABLE decision_nodes
            ADD COLUMN IF NOT EXISTS node_type ENUM('decision', 'chance', 'outcome') NOT NULL DEFAULT 'decision',
            ADD COLUMN IF NOT EXISTS probability DECIMAL(5,2),
            ADD COLUMN IF NOT EXISTS cost DECIMAL(15,2),
            ADD COLUMN IF NOT EXISTS reward DECIMAL(15,2),
            ADD COLUMN IF NOT EXISTS expected_value DECIMAL(15,2)
        """)
        
        # decision_options 테이블 수정
        cursor.execute("""
            ALTER TABLE decision_options
            ADD COLUMN IF NOT EXISTS probability DECIMAL(5,2),
            ADD COLUMN IF NOT EXISTS cost DECIMAL(15,2),
            ADD COLUMN IF NOT EXISTS reward DECIMAL(15,2)
        """)
        
        conn.commit()
        st.success("✅ 의사결정 트리 테이블이 업데이트되었습니다.")
        
    except Exception as e:
        st.error(f"테이블 수정 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def reset_session_state():
    """세션 상태 초기화"""
    st.session_state['show_create_form'] = False
    st.session_state['adding_node'] = False
    st.session_state['current_tree_id'] = None
    st.session_state['tree_created'] = False
    st.session_state['form_key'] = 0

def main():
    st.title("의사결정 트리")
    
    # 세션 상태 초기화
    if 'form_key' not in st.session_state:
        st.session_state['form_key'] = 0
    
    if 'current_menu' not in st.session_state:
        st.session_state['current_menu'] = "의사결정 트리 목록"
    
    if 'show_create_form' not in st.session_state:
        st.session_state['show_create_form'] = False
    
    if 'adding_node' not in st.session_state:
        st.session_state['adding_node'] = False
    
    if 'current_tree_id' not in st.session_state:
        st.session_state['current_tree_id'] = None
    
    if 'tree_created' not in st.session_state:
        st.session_state['tree_created'] = False
    
    # DB 테이블 관리 버튼 제거
    # with st.sidebar:
    #     st.write("### DB 관리")
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         if st.button("테이블 생성", type="primary"):
    #             create_decision_tree_tables()
    #     with col2:
    #         if st.button("테이블 삭제", type="secondary"):
    #             drop_decision_tree_tables()
    
    # 메뉴 선택
    menu = st.sidebar.radio(
        "메뉴 선택",
        ["의사결정 트리 목록", "새 의사결정 트리 생성"],
        index=1 if st.session_state['show_create_form'] else 0
    )
    
    if menu == "의사결정 트리 목록":
        # 헤더와 새 트리 추가 버튼을 나란히 배치
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header("의사결정 트리 목록")
        with col2:
            if st.button("➕ 새 트리 추가", type="primary"):
                st.session_state['show_create_form'] = True
                st.rerun()
        
        if not st.session_state['show_create_form']:
            # 카테고리 필터
            categories = ["전체", "사업 전략", "제품 개발", "마케팅", "운영", "인사", "재무", "기타"]
            selected_category = st.selectbox("카테고리 선택", categories)
            
            # 트리 목록 조회
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            
            try:
                if selected_category == "전체":
                    cursor.execute("""
                        SELECT dt.*, u.user_name as creator_name,
                               COUNT(DISTINCT n.node_id) as node_count
                        FROM decision_trees dt
                        LEFT JOIN dot_user_credibility u ON dt.created_by = u.user_id
                        LEFT JOIN decision_nodes n ON dt.tree_id = n.tree_id
                        GROUP BY dt.tree_id
                        ORDER BY dt.created_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT dt.*, u.user_name as creator_name,
                               COUNT(DISTINCT n.node_id) as node_count
                        FROM decision_trees dt
                        LEFT JOIN dot_user_credibility u ON dt.created_by = u.user_id
                        LEFT JOIN decision_nodes n ON dt.tree_id = n.tree_id
                        WHERE dt.category = %s
                        GROUP BY dt.tree_id
                        ORDER BY dt.created_at DESC
                    """, (selected_category,))
                
                trees = cursor.fetchall()
                
                if trees:
                    # 트리 목록을 테이블로 표시
                    tree_data = []
                    for tree in trees:
                        tree_data.append({
                            "제목": tree['title'],
                            "카테고리": tree['category'],
                            "작성자": tree['creator_name'],
                            "노드 수": tree['node_count'],
                            "작성일": tree['created_at'].strftime('%Y-%m-%d'),
                            "tree_id": tree['tree_id']
                        })
                    
                    df = pd.DataFrame(tree_data)
                    
                    # 선택 가능한 트리 목록을 selectbox로 표시
                    selected_tree = st.selectbox(
                        "조회할 의사결정 트리 선택",
                        df['제목'].tolist(),
                        format_func=lambda x: f"{x} ({df[df['제목']==x]['카테고리'].iloc[0]}, {df[df['제목']==x]['작성자'].iloc[0]})"
                    )
                    
                    if selected_tree:
                        selected_tree_id = int(df[df['제목']==selected_tree]['tree_id'].iloc[0])
                        
                        # 노드 추가 옵션을 먼저 표시
                        col1, col2 = st.columns([3, 1])
                        with col2:
                            if st.button("새 노드 추가", type="primary"):
                                st.session_state['adding_node'] = True
                                st.session_state['current_tree_id'] = selected_tree_id
                        
                        # 노드 추가 모드인 경우
                        if st.session_state.get('adding_node', False):
                            add_decision_node(selected_tree_id)
                        
                        # 트리 조회
                        with col1:
                            st.write("### 의사결정 트리 구조")
                            visualize_decision_tree(selected_tree_id)
                            view_decision_tree(selected_tree_id)
                    
                else:
                    st.info(f"{selected_category} 카테고리에 등록된 의사결정 트리가 없습니다.")
                
            finally:
                cursor.close()
                conn.close()

    elif menu == "새 의사결정 트리 생성" or st.session_state['show_create_form']:
        st.header("새 의사결정 트리 생성")
        
        # 목록으로 돌아가기 버튼
        if st.button("← 목록으로 돌아가기"):
            reset_session_state()  # 모든 세션 상태 초기화
            st.rerun()
        
        # 새 트리 생성 폼
        create_decision_tree()

if __name__ == "__main__":
    main() 