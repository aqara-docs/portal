import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
import graphviz
import time

load_dotenv()

def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def create_simple_decision_tables():
    """간단한 의사결정 트리 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS simple_decision_options")
        cursor.execute("DROP TABLE IF EXISTS simple_decision_nodes")
        cursor.execute("DROP TABLE IF EXISTS simple_decision_trees")
        
        # 의사결정 트리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simple_decision_trees (
                tree_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES dot_user_credibility(user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 노드 테이블 - node_type ENUM 수정
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simple_decision_nodes (
                node_id INT AUTO_INCREMENT PRIMARY KEY,
                tree_id INT NOT NULL,
                parent_id INT,
                node_type ENUM('의사결정', '확률', '결과') NOT NULL,
                question TEXT NOT NULL,
                weight DECIMAL(5,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tree_id) REFERENCES simple_decision_trees(tree_id),
                FOREIGN KEY (parent_id) REFERENCES simple_decision_nodes(node_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 선택지 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simple_decision_options (
                option_id INT AUTO_INCREMENT PRIMARY KEY,
                node_id INT NOT NULL,
                option_text TEXT NOT NULL,
                score DECIMAL(5,2),            -- 선택지 점수
                cost DECIMAL(10,2),            -- 비용 (선택사항)
                probability DECIMAL(5,2),       -- 확률 (%)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES simple_decision_nodes(node_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        conn.commit()
        st.success("✅ 간단한 의사결정 트리 테이블이 생성되었습니다!")
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류가 발생했습니다: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def create_decision_tree():
    """새로운 의사결정 트리 생성"""
    st.write("## 새 의사결정 트리 생성")
    
    with st.form("new_simple_tree"):
        title = st.text_input("제목", placeholder="예: 사무실 이전 결정")
        description = st.text_area("설명", placeholder="의사결정의 목적과 고려사항을 설명해주세요")
        
        submit = st.form_submit_button("생성", type="primary")
        
        if submit:
            if not title or not description:
                st.error("제목과 설명을 모두 입력해주세요.")
                return
            
            conn = connect_to_db()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO simple_decision_trees 
                    (title, description, created_by)
                    VALUES (%s, %s, %s)
                """, (
                    title, 
                    description,
                    st.session_state.get('user_id', 1)  # 기본값 1
                ))
                
                conn.commit()
                st.success("✅ 의사결정 트리가 생성되었습니다!")
                st.session_state['show_create_form'] = False  # 폼 닫기
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                conn.rollback()
            
            finally:
                cursor.close()
                conn.close()

def add_decision_node(tree_id):
    """의사결정 노드 추가"""
    st.write("## 노드 추가")
    
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기존 노드 조회
        cursor.execute("""
            SELECT node_id, question, node_type
            FROM simple_decision_nodes
            WHERE tree_id = %s
            ORDER BY created_at
        """, (tree_id,))
        existing_nodes = cursor.fetchall()
        
        with st.form(key=f"new_node_{tree_id}"):  # 고유한 폼 키 사용
            # 상위 노드 선택
            parent_options = [("", "최상위 노드")] + [(str(node['node_id']), node['question']) for node in existing_nodes]
            parent_id = st.selectbox(
                "상위 노드",
                options=[id for id, _ in parent_options],
                format_func=lambda x: dict(parent_options)[x]
            )
            parent_id = int(parent_id) if parent_id else None
            
            # 노드 정보 입력
            node_type = st.selectbox(
                "노드 타입",
                ["의사결정", "확률", "결과"]
            )
            
            question = st.text_input("질문/설명")
            
            # 중요도 입력 UI 개선
            st.write("### ⚖️ 의사결정 중요도")
            weight = st.select_slider(
                "이 의사결정이 얼마나 중요한가요?",
                options=[1, 2, 3, 4, 5],
                value=3,
                format_func=lambda x: {
                    1: "매우 낮음 (1배)",
                    2: "낮음 (2배)",
                    3: "보통 (3배)",
                    4: "높음 (4배)",
                    5: "매우 높음 (5배)"
                }[x],
                help="이 의사결정의 중요도에 따라 점수가 배수로 반영됩니다"
            )
            
            # 중요도 설명 추가
            st.info(f"""
            #### 💡 현재 설정된 중요도: {weight}배
            - 선택지 점수에 {weight}배가 곱해집니다
            - 예시) 점수 70점인 선택지의 경우:
              - 비용 감점 전: 70 × {weight} = {70*weight}점
              - 비용 1000만원 감점 후: (70 - 10) × {weight} = {(70-10)*weight}점
            """)
            
            # 비용 단위 선택 추가
            cost_unit = st.selectbox(
                "비용 단위",
                ["만원", "억원"],
                help="비용을 입력할 때 사용할 단위를 선택하세요"
            )
            
            st.info("""
            #### 💡 비용 입력 가이드
            - 실제 발생하는 비용만 입력하세요
            - 평가 요소는 점수로만 반영 (비용 입력 X)
            
            예시:
            1. 교통 편의성 평가
               - 지하철역 5분 거리 (점수: 90, 비용: 0)
               - 지하철역 15분 거리 (점수: 60, 비용: 0)
            
            2. 층고 선택
               - 20층 (점수: 85, 비용: 1000만원)
               - 10층 (점수: 70, 비용: 800만원)
            """)
            
            # 선택지 데이터 초기화
            options_data = []
            
            if node_type != "결과":
                # 선택지 입력 설명
                st.write("### 선택지")
                st.info("""
                #### 💡 점수와 비용 입력 가이드
                - **점수 (0-100)**: 각 선택지의 바람직한 정도를 나타내는 상대적 점수
                    - 100: 최고의 선택지
                    - 75: 매우 좋은 선택지
                    - 50: 보통인 선택지
                    - 25: 좋지 않은 선택지
                    - 0: 최악의 선택지
                    
                - **비용**: 선택지 실행에 필요한 실제 비용 (단위: 만원)
                    - 예: 임대료, 구매비용, 인건비 등
                    - 비용이 클수록 최종 점수에서 차감
                """)
                
                for i in range(5):  # 최대 5개 선택지
                    st.write(f"#### 선택지 {i+1}")
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        option = st.text_input(
                            "선택지 내용",
                            key=f"opt_{i}",
                            help="구체적인 선택 내용을 입력하세요"
                        )
                        score = st.slider(
                            "선택지 점수",
                            0, 100, 50,
                            key=f"score_{i}",
                            help="이 선택지가 얼마나 바람직한지를 0-100 사이의 점수로 평가"
                        )
                    with col2:
                        if node_type == "확률":
                            prob = st.number_input(
                                "발생 확률 (%)",
                                min_value=0,
                                max_value=100,
                                key=f"prob_{i}",
                                help="이 상황이 발생할 확률"
                            )
                        else:
                            cost = st.number_input(
                                f"소요 비용 ({cost_unit})",
                                min_value=0.0,  # float로 변경
                                key=f"cost_{i}",
                                help=f"이 선택지를 실행하는데 필요한 비용 ({cost_unit} 단위)"
                            )
                            # 단위 변환 (모든 비용을 만원 단위로 저장)
                            if cost_unit == "억원":
                                cost = cost * 10000
                    
                    if option:  # 입력된 선택지만 저장
                        options_data.append({
                            "text": option,
                            "score": score,
                            "probability": prob if node_type == "확률" else None,
                            "cost": cost if node_type == "의사결정" else None
                        })

                # 확률 노드의 경우 확률 합계 체크
                if node_type == "확률":
                    total_prob = sum(opt['probability'] or 0 for opt in options_data)
                    if total_prob != 100:
                        st.warning(f"⚠️ 확률의 합이 100%가 되어야 합니다. (현재: {total_prob}%)")
            
            submit_button = st.form_submit_button("저장", type="primary")
            
            if submit_button:
                if not question:
                    st.error("질문을 입력해주세요.")
                    return
                
                if node_type != "결과" and not options_data:
                    st.error("최소 하나의 선택지를 입력해주세요.")
                    return
                
                try:
                    # 노드 저장
                    cursor.execute("""
                        INSERT INTO simple_decision_nodes 
                        (tree_id, parent_id, node_type, question, weight)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        tree_id,
                        parent_id if parent_id else None,
                        node_type,
                        question,
                        weight if node_type != "결과" else None
                    ))
                    
                    node_id = cursor.lastrowid
                    
                    # 선택지 저장 (결과 노드가 아닐 때만)
                    if node_type != "결과" and options_data:
                        for opt in options_data:
                            cursor.execute("""
                                INSERT INTO simple_decision_options 
                                (node_id, option_text, score, probability, cost)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                node_id,
                                opt['text'],
                                opt['score'],
                                opt.get('probability'),
                                opt.get('cost')
                            ))
                    
                    conn.commit()
                    st.success("✅ 노드가 추가되었습니다!")
                    
                    # 폼 상태 초기화
                    add_node_key = f"add_node_{tree_id}"
                    st.session_state[add_node_key] = False
                    
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                    conn.rollback()
    
    finally:
        cursor.close()
        conn.close()

def calculate_path_scores(tree_id):
    """경로별 점수 계산"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        paths = []
        
        def get_node_options(node_id):
            cursor.execute("""
                SELECT * FROM simple_decision_options
                WHERE node_id = %s
            """, (node_id,))
            return cursor.fetchall() or []  # 결과가 없으면 빈 리스트 반환
        
        def get_child_nodes(node_id):
            cursor.execute("""
                SELECT * FROM simple_decision_nodes
                WHERE parent_id = %s
            """, (node_id,))
            return cursor.fetchall() or []  # 결과가 없으면 빈 리스트 반환
        
        def calculate_option_score(opt, weight=1):
            """선택지의 점수 계산 개선"""
            # Decimal을 float로 변환
            base_score = float(opt['score'])  # 기본 점수 (0-100)
            weight = float(weight)  # 가중치도 float로 변환
            cost_penalty = 0
            
            if opt['cost']:
                # 비용 범위별 감점 로직
                cost_in_man = float(opt['cost'])  # 만원 단위로 통일
                
                if cost_in_man <= 1000:  # 1000만원 이하
                    cost_penalty = (cost_in_man / 1000) * 10  # 최대 10점 감점
                elif cost_in_man <= 10000:  # 1억원 이하
                    cost_penalty = 10 + ((cost_in_man - 1000) / 9000) * 10  # 추가 10점 감점
                else:  # 1억원 초과
                    cost_penalty = 20 + ((cost_in_man - 10000) / 90000) * 10  # 추가 10점 감점
                    cost_penalty = min(cost_penalty, 40)  # 최대 40점까지만 감점
            
            # 최종 점수 = (기본 점수 - 비용 감점) * 가중치
            final_score = (base_score - cost_penalty) * weight
            
            # 최소 0점 보장
            return max(0, final_score)
        
        def traverse_tree(node_id, current_path=None, current_score=0, current_prob=1, total_cost=0):
            if current_path is None:
                current_path = []
            
            # 노드 정보 조회
            cursor.execute("""
                SELECT * FROM simple_decision_nodes
                WHERE node_id = %s
            """, (node_id,))
            node = cursor.fetchone()
            
            if not node:
                return
            
            # 선택지와 자식 노드 조회
            options = get_node_options(node_id)
            children = get_child_nodes(node_id)
            
            if not children:  # 리프 노드
                if options:  # 선택지가 있는 경우만 처리
                    for opt in options:
                        score = calculate_option_score(opt, node['weight'] or 1)
                        prob = float(opt['probability'])/100 if opt['probability'] else 1
                        final_score = current_score + (score * current_prob * prob)
                        new_total_cost = total_cost + float(opt['cost'] or 0)
                        
                        path_desc = current_path + [f"{node['question']}: {opt['option_text']}"]
                        paths.append({
                            'path': ' → '.join(path_desc),
                            'score': final_score,
                            'probability': current_prob * prob * 100,
                            'total_cost': new_total_cost,
                            'formatted_cost': format_cost(new_total_cost)
                        })
            else:
                if options:  # 선택지가 있는 경우만 처리
                    for opt in options:
                        score = calculate_option_score(opt, node['weight'] or 1)
                        prob = float(opt['probability'])/100 if opt['probability'] else 1
                        new_score = current_score + (score * current_prob * prob)
                        new_total_cost = total_cost + float(opt['cost'] or 0)
                        new_path = current_path + [f"{node['question']}: {opt['option_text']}"]
                        
                        for child in children:
                            traverse_tree(
                                child['node_id'], 
                                new_path, 
                                new_score, 
                                current_prob * prob,
                                new_total_cost
                            )
        
        # 루트 노드 찾기
        cursor.execute("""
            SELECT node_id FROM simple_decision_nodes
            WHERE tree_id = %s AND parent_id IS NULL
            LIMIT 1
        """, (tree_id,))
        root = cursor.fetchone()
        
        if root:
            traverse_tree(root['node_id'])
        
        return paths
    
    finally:
        cursor.close()
        conn.close()

def check_tables_exist():
    """테이블 존재 여부 확인"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name IN ('simple_decision_trees', 'simple_decision_nodes', 'simple_decision_options')
        """, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        
        count = cursor.fetchone()[0]
        return count == 3
    finally:
        cursor.close()
        conn.close()

def format_cost(cost):
    """비용을 읽기 쉬운 형태로 변환"""
    if cost >= 10000:  # 1억원 이상
        return f"{cost/10000:.1f} 억원"
    return f"{cost:,.0f} 만원"

def main():
    st.title("간단한 의사결정 트리")
    
    # DB 테이블 관리
    with st.sidebar:
        st.write("### DB 관리")
        if not check_tables_exist():
            st.warning("⚠️ 필요한 테이블이 없습니다. 테이블을 생성해주세요.")
        if st.button("테이블 생성/재생성"):
            create_simple_decision_tables()
            st.rerun()
    
    # 테이블이 없으면 여기서 중단
    if not check_tables_exist():
        st.error("테이블이 없습니다. 사이드바의 '테이블 생성' 버튼을 클릭해주세요.")
        return
        
    # 기존 트리 목록 조회
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT t.*, COUNT(n.node_id) as node_count
            FROM simple_decision_trees t
            LEFT JOIN simple_decision_nodes n ON t.tree_id = n.tree_id
            GROUP BY t.tree_id
            ORDER BY t.created_at DESC
        """)
        trees = cursor.fetchall()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("## 의사결정 트리 목록")
        with col2:
            if st.button("➕ 새 트리 만들기", type="primary"):
                st.session_state['show_create_form'] = True
                st.rerun()
        
        if st.session_state.get('show_create_form', False):
            create_decision_tree()
        else:
            if trees:
                for tree in trees:
                    with st.expander(f"🌳 {tree['title']} ({tree['created_at'].strftime('%Y-%m-%d')})"):
                        st.write(f"**설명:** {tree['description']}")
                        st.write(f"**노드 수:** {tree['node_count']}")
                        
                        # 노드 추가 상태 관리
                        add_node_key = f"add_node_{tree['tree_id']}"
                        if add_node_key not in st.session_state:
                            st.session_state[add_node_key] = False
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("노드 추가", key=f"add_{tree['tree_id']}"):
                                st.session_state[add_node_key] = True
                        
                        # 노드 추가 폼 표시
                        if st.session_state[add_node_key]:
                            add_decision_node(tree['tree_id'])
                        
                        # 경로 분석
                        paths = calculate_path_scores(tree['tree_id'])
                        if paths:
                            st.write("### 📊 경로 분석")
                            
                            # 점수 기준으로 정렬
                            paths.sort(key=lambda x: x['score'], reverse=True)
                            
                            # 결과 테이블
                            df = pd.DataFrame(paths)
                            df.columns = ['의사결정 경로', '종합 점수', '확률 (%)', '총 비용', '비용']
                            st.dataframe(
                                df,
                                column_config={
                                    "종합 점수": st.column_config.NumberColumn(
                                        "종합 점수",
                                        help="가중치, 확률, 비용이 반영된 점수",
                                        format="%.1f"
                                    ),
                                    "확률 (%)": st.column_config.NumberColumn(
                                        "확률 (%)",
                                        help="경로의 실현 확률",
                                        format="%.1f"
                                    ),
                                    "총 비용": st.column_config.NumberColumn(
                                        "내부 비용",
                                        help="경로의 총 소요 비용 (만원)",
                                        format="%d"
                                    ),
                                    "비용": st.column_config.TextColumn(
                                        "소요 비용",
                                        help="경로의 총 소요 비용 (자동 단위 변환)"
                                    )
                                },
                                hide_index=True
                            )
                            
                            # 최적 경로 강조
                            st.success(f"""
                            🌟 추천 경로: {paths[0]['path']}
                            - 종합 점수: {paths[0]['score']:.1f}
                            - 확률: {paths[0]['probability']:.1f}%
                            - 소요 비용: {paths[0]['formatted_cost']}
                            """)
            else:
                st.info("등록된 의사결정 트리가 없습니다. 새로운 트리를 만들어보세요!")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 