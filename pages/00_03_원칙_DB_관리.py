import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="아카라라이프 원칙 DB 관리",
    page_icon="⚙️",
    layout="wide"
)

# 인증 기능 (간단한 비밀번호 보호)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    if password == os.getenv('ADMIN_PASSWORD', 'admin123'):  # 환경 변수에서 비밀번호 가져오기
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()

# MySQL 연결 설정
db_config = {
    'user': os.getenv('SQL_USER'),
    'password': os.getenv('SQL_PASSWORD'),
    'host': os.getenv('SQL_HOST'),
    'database': os.getenv('SQL_DATABASE_NEWBIZ'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# 필요한 테이블 생성 함수
def ensure_tables_exist():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # mission_vision 테이블 생성
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mission_vision (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mission_text TEXT,
            vision_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        # key_objectives 테이블 생성
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_objectives (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(255),
            objective_text TEXT,
            sort_order INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        # core_values 테이블 생성
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS core_values (
            id INT AUTO_INCREMENT PRIMARY KEY,
            value_title VARCHAR(255),
            value_description TEXT,
            sort_order INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        st.error(f"테이블 생성 중 오류 발생: {err}")

# 테이블 존재 확인 및 생성
ensure_tables_exist()

# 관리 기능 구현
st.title("아카라라이프 원칙 DB 관리 시스템")

# 탭 설정
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "원칙 관리", "세부 원칙 관리", "실행 항목 관리", "서문 관리", "요약 관리", "미션 & 비전 관리"
])

# 원칙 관리 탭
with tab1:
    st.header("원칙 관리")
    
    # 원칙 목록 표시
    conn = mysql.connector.connect(**db_config)
    principles_df = pd.read_sql("SELECT * FROM principles ORDER BY principle_number", conn)
    conn.close()
    
    st.subheader("현재 원칙 목록")
    st.dataframe(principles_df)
    
    # 원칙 추가 폼
    st.subheader("새 원칙 추가")
    with st.form("add_principle_form"):
        principle_number = st.number_input("원칙 번호", min_value=1, step=1)
        principle_title = st.text_input("원칙 제목")
        submit_add = st.form_submit_button("원칙 추가")
    
    if submit_add and principle_title:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO principles (principle_number, principle_title) VALUES (%s, %s)",
                (principle_number, principle_title)
            )
            conn.commit()
            conn.close()
            st.success(f"원칙 '{principle_title}'이(가) 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 원칙 수정/삭제
    st.subheader("원칙 수정/삭제")
    if not principles_df.empty:
        selected_principle_id = st.selectbox(
            "수정/삭제할 원칙 선택",
            options=principles_df['principle_id'].tolist(),
            format_func=lambda x: f"{principles_df[principles_df['principle_id']==x]['principle_number'].iloc[0]}. {principles_df[principles_df['principle_id']==x]['principle_title'].iloc[0]}"
        )
        
        selected_principle = principles_df[principles_df['principle_id'] == selected_principle_id].iloc[0]
        
        with st.form("edit_principle_form"):
            edit_number = st.number_input("원칙 번호", value=int(selected_principle['principle_number']), min_value=1, step=1)
            edit_title = st.text_input("원칙 제목", value=selected_principle['principle_title'])
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit = st.form_submit_button("원칙 수정")
            with col2:
                submit_delete = st.form_submit_button("원칙 삭제", type="primary")
        
        if submit_edit:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE principles SET principle_number = %s, principle_title = %s WHERE principle_id = %s",
                    (edit_number, edit_title, selected_principle_id)
                )
                conn.commit()
                conn.close()
                st.success("원칙이 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                
                # 관련 실행 항목 삭제
                cursor.execute(
                    """
                    DELETE ai FROM action_items ai
                    JOIN sub_principles sp ON ai.sub_principle_id = sp.sub_principle_id
                    WHERE sp.principle_id = %s
                    """,
                    (selected_principle_id,)
                )
                
                # 관련 세부 원칙 삭제
                cursor.execute(
                    "DELETE FROM sub_principles WHERE principle_id = %s",
                    (selected_principle_id,)
                )
                
                # 원칙 삭제
                cursor.execute(
                    "DELETE FROM principles WHERE principle_id = %s",
                    (selected_principle_id,)
                )
                
                conn.commit()
                conn.close()
                st.success("원칙과 관련 세부 원칙, 실행 항목이 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")

# 세부 원칙 관리 탭
with tab2:
    st.header("세부 원칙 관리")
    
    # 세부 원칙 목록 표시
    conn = mysql.connector.connect(**db_config)
    sub_principles_df = pd.read_sql("""
        SELECT sp.*, p.principle_number, p.principle_title 
        FROM sub_principles sp
        JOIN principles p ON sp.principle_id = p.principle_id
        ORDER BY p.principle_number, sp.sub_principle_number
    """, conn)
    
    # 원칙 목록 가져오기 (드롭다운용)
    principles_df = pd.read_sql("SELECT * FROM principles ORDER BY principle_number", conn)
    conn.close()
    
    st.subheader("현재 세부 원칙 목록")
    st.dataframe(sub_principles_df)
    
    # 세부 원칙 추가 폼
    st.subheader("새 세부 원칙 추가")
    with st.form("add_sub_principle_form"):
        # 원칙 선택
        principle_id = st.selectbox(
            "원칙 선택",
            options=principles_df['principle_id'].tolist(),
            format_func=lambda x: f"{principles_df[principles_df['principle_id']==x]['principle_number'].iloc[0]}. {principles_df[principles_df['principle_id']==x]['principle_title'].iloc[0]}",
            key="add_sp_principle"
        )
        
        sub_principle_number = st.text_input("세부 원칙 번호 (예: 1.1, 2.3)")
        sub_principle_title = st.text_area("세부 원칙 제목")
        submit_add_sp = st.form_submit_button("세부 원칙 추가")
    
    if submit_add_sp and sub_principle_title and sub_principle_number:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sub_principles (principle_id, sub_principle_number, sub_principle_title) VALUES (%s, %s, %s)",
                (principle_id, sub_principle_number, sub_principle_title)
            )
            conn.commit()
            conn.close()
            st.success(f"세부 원칙 '{sub_principle_title}'이(가) 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 세부 원칙 수정/삭제
    st.subheader("세부 원칙 수정/삭제")
    if not sub_principles_df.empty:
        selected_sub_principle_id = st.selectbox(
            "수정/삭제할 세부 원칙 선택",
            options=sub_principles_df['sub_principle_id'].tolist(),
            format_func=lambda x: f"{sub_principles_df[sub_principles_df['sub_principle_id']==x]['principle_number'].iloc[0]}.{sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_number'].iloc[0]} {sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_title'].iloc[0]}"
        )
        
        selected_sub_principle = sub_principles_df[sub_principles_df['sub_principle_id'] == selected_sub_principle_id].iloc[0]
        
        with st.form("edit_sub_principle_form"):
            edit_principle_id = st.selectbox(
                "원칙 선택",
                options=principles_df['principle_id'].tolist(),
                format_func=lambda x: f"{principles_df[principles_df['principle_id']==x]['principle_number'].iloc[0]}. {principles_df[principles_df['principle_id']==x]['principle_title'].iloc[0]}",
                index=principles_df.index[principles_df['principle_id'] == selected_sub_principle['principle_id']].tolist()[0] if not principles_df.empty else 0,
                key="edit_sp_principle"
            )
            
            edit_sub_number = st.text_input("세부 원칙 번호", value=selected_sub_principle['sub_principle_number'])
            edit_sub_title = st.text_area("세부 원칙 제목", value=selected_sub_principle['sub_principle_title'])
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit_sp = st.form_submit_button("세부 원칙 수정")
            with col2:
                submit_delete_sp = st.form_submit_button("세부 원칙 삭제", type="primary")
        
        if submit_edit_sp:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE sub_principles SET principle_id = %s, sub_principle_number = %s, sub_principle_title = %s WHERE sub_principle_id = %s",
                    (edit_principle_id, edit_sub_number, edit_sub_title, selected_sub_principle_id)
                )
                conn.commit()
                conn.close()
                st.success("세부 원칙이 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete_sp:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                
                # 관련 실행 항목 삭제
                cursor.execute(
                    "DELETE FROM action_items WHERE sub_principle_id = %s",
                    (selected_sub_principle_id,)
                )
                
                # 세부 원칙 삭제
                cursor.execute(
                    "DELETE FROM sub_principles WHERE sub_principle_id = %s",
                    (selected_sub_principle_id,)
                )
                
                conn.commit()
                conn.close()
                st.success("세부 원칙과 관련 실행 항목이 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")

# 실행 항목 관리 탭
with tab3:
    st.header("실행 항목 관리")
    
    # 실행 항목 목록 표시
    conn = mysql.connector.connect(**db_config)
    action_items_df = pd.read_sql("""
        SELECT ai.*, sp.sub_principle_number, sp.sub_principle_title, 
               p.principle_number, p.principle_title
        FROM action_items ai
        JOIN sub_principles sp ON ai.sub_principle_id = sp.sub_principle_id
        JOIN principles p ON sp.principle_id = p.principle_id
        ORDER BY p.principle_number, sp.sub_principle_number
    """, conn)
    
    # 세부 원칙 목록 가져오기 (드롭다운용)
    sub_principles_df = pd.read_sql("""
        SELECT sp.*, p.principle_number, p.principle_title 
        FROM sub_principles sp
        JOIN principles p ON sp.principle_id = p.principle_id
        ORDER BY p.principle_number, sp.sub_principle_number
    """, conn)
    conn.close()
    
    st.subheader("현재 실행 항목 목록")
    st.dataframe(action_items_df)
    
    # 실행 항목 추가 폼
    st.subheader("새 실행 항목 추가")
    with st.form("add_action_item_form"):
        # 세부 원칙 선택
        sub_principle_id = st.selectbox(
            "세부 원칙 선택",
            options=sub_principles_df['sub_principle_id'].tolist(),
            format_func=lambda x: f"{sub_principles_df[sub_principles_df['sub_principle_id']==x]['principle_number'].iloc[0]}.{sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_number'].iloc[0]} {sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_title'].iloc[0]}",
            key="add_ai_sub_principle"
        )
        
        action_item_text = st.text_area("실행 항목 내용")
        submit_add_ai = st.form_submit_button("실행 항목 추가")
    
    if submit_add_ai and action_item_text:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO action_items (sub_principle_id, action_item_text) VALUES (%s, %s)",
                (sub_principle_id, action_item_text)
            )
            conn.commit()
            conn.close()
            st.success("실행 항목이 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 실행 항목 수정/삭제
    st.subheader("실행 항목 수정/삭제")
    if not action_items_df.empty:
        selected_action_item_id = st.selectbox(
            "수정/삭제할 실행 항목 선택",
            options=action_items_df['action_item_id'].tolist(),
            format_func=lambda x: f"{action_items_df[action_items_df['action_item_id']==x]['principle_number'].iloc[0]}.{action_items_df[action_items_df['action_item_id']==x]['sub_principle_number'].iloc[0]} - {action_items_df[action_items_df['action_item_id']==x]['action_item_text'].iloc[0][:50]}..."
        )
        
        selected_action_item = action_items_df[action_items_df['action_item_id'] == selected_action_item_id].iloc[0]
        
        with st.form("edit_action_item_form"):
            edit_sub_principle_id = st.selectbox(
                "세부 원칙 선택",
                options=sub_principles_df['sub_principle_id'].tolist(),
                format_func=lambda x: f"{sub_principles_df[sub_principles_df['sub_principle_id']==x]['principle_number'].iloc[0]}.{sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_number'].iloc[0]} {sub_principles_df[sub_principles_df['sub_principle_id']==x]['sub_principle_title'].iloc[0]}",
                index=sub_principles_df.index[sub_principles_df['sub_principle_id'] == selected_action_item['sub_principle_id']].tolist()[0] if not sub_principles_df.empty else 0,
                key="edit_ai_sub_principle"
            )
            
            edit_action_text = st.text_area("실행 항목 내용", value=selected_action_item['action_item_text'])
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit_ai = st.form_submit_button("실행 항목 수정")
            with col2:
                submit_delete_ai = st.form_submit_button("실행 항목 삭제", type="primary")
        
        if submit_edit_ai:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE action_items SET sub_principle_id = %s, action_item_text = %s WHERE action_item_id = %s",
                    (edit_sub_principle_id, edit_action_text, selected_action_item_id)
                )
                conn.commit()
                conn.close()
                st.success("실행 항목이 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete_ai:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM action_items WHERE action_item_id = %s",
                    (selected_action_item_id,)
                )
                conn.commit()
                conn.close()
                st.success("실행 항목이 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")

# 서문 관리 탭
with tab4:
    st.header("서문 관리")
    
    # 서문 데이터 가져오기
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM introduction")
    intro_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # 서문 표시 및 수정
    st.subheader("서문 내용")
    
    with st.form("edit_intro_form"):
        intro_text = st.text_area(
            "서문 내용",
            value=intro_data['intro_text'] if intro_data else "",
            height=300
        )
        
        submit_intro = st.form_submit_button("서문 저장")
    
    if submit_intro:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            
            if intro_data:
                # 기존 서문 업데이트
                cursor.execute(
                    "UPDATE introduction SET intro_text = %s",
                    (intro_text,)
                )
            else:
                # 새 서문 추가
                cursor.execute(
                    "INSERT INTO introduction (intro_text) VALUES (%s)",
                    (intro_text,)
                )
            
            conn.commit()
            conn.close()
            st.success("서문이 저장되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")

# 요약 관리 탭
with tab5:
    st.header("요약 관리")
    
    # 요약 목록 표시
    conn = mysql.connector.connect(**db_config)
    summary_df = pd.read_sql("SELECT * FROM summary ORDER BY summary_id", conn)
    conn.close()
    
    st.subheader("현재 요약 목록")
    st.dataframe(summary_df)
    
    # 요약 추가 폼
    st.subheader("새 요약 추가")
    with st.form("add_summary_form"):
        summary_title = st.text_input("요약 제목")
        summary_text = st.text_area("요약 내용")
        submit_add_summary = st.form_submit_button("요약 추가")
    
    if submit_add_summary and summary_title and summary_text:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO summary (summary_title, summary_text) VALUES (%s, %s)",
                (summary_title, summary_text)
            )
            conn.commit()
            conn.close()
            st.success(f"요약 '{summary_title}'이(가) 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 요약 수정/삭제
    st.subheader("요약 수정/삭제")
    if not summary_df.empty:
        selected_summary_id = st.selectbox(
            "수정/삭제할 요약 선택",
            options=summary_df['summary_id'].tolist(),
            format_func=lambda x: f"{summary_df[summary_df['summary_id']==x]['summary_title'].iloc[0]}"
        )
        
        selected_summary = summary_df[summary_df['summary_id'] == selected_summary_id].iloc[0]
        
        with st.form("edit_summary_form"):
            edit_summary_title = st.text_input("요약 제목", value=selected_summary['summary_title'])
            edit_summary_text = st.text_area("요약 내용", value=selected_summary['summary_text'])
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit_summary = st.form_submit_button("요약 수정")
            with col2:
                submit_delete_summary = st.form_submit_button("요약 삭제", type="primary")
        
        if submit_edit_summary:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE summary SET summary_title = %s, summary_text = %s WHERE summary_id = %s",
                    (edit_summary_title, edit_summary_text, selected_summary_id)
                )
                conn.commit()
                conn.close()
                st.success("요약이 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete_summary:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM summary WHERE summary_id = %s",
                    (selected_summary_id,)
                )
                conn.commit()
                conn.close()
                st.success("요약이 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")

# 미션 & 비전 관리 탭
with tab6:
    st.header("미션 & 비전 관리")
    
    # 미션 & 비전 데이터 가져오기
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # 미션 & 비전 데이터
    cursor.execute("SELECT * FROM mission_vision LIMIT 1")
    mission_vision_data = cursor.fetchone()
    
    # 핵심 목표 데이터
    cursor.execute("SELECT * FROM key_objectives ORDER BY category, sort_order")
    key_objectives_data = cursor.fetchall()
    
    # 핵심 가치 데이터
    cursor.execute("SELECT * FROM core_values ORDER BY sort_order")
    core_values_data = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # 미션 & 비전 섹션
    st.subheader("미션 & 비전")
    
    with st.form("edit_mission_vision_form"):
        mission_text = st.text_area(
            "미션 (Mission)",
            value=mission_vision_data['mission_text'] if mission_vision_data else "",
            height=150
        )
        
        vision_text = st.text_area(
            "비전 (Vision)",
            value=mission_vision_data['vision_text'] if mission_vision_data else "",
            height=150
        )
        
        submit_mission_vision = st.form_submit_button("미션 & 비전 저장")
    
    if submit_mission_vision:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            
            if mission_vision_data:
                # 기존 데이터 업데이트
                cursor.execute(
                    "UPDATE mission_vision SET mission_text = %s, vision_text = %s WHERE id = %s",
                    (mission_text, vision_text, mission_vision_data['id'])
                )
            else:
                # 새 데이터 추가
                cursor.execute(
                    "INSERT INTO mission_vision (mission_text, vision_text) VALUES (%s, %s)",
                    (mission_text, vision_text)
                )
            
            conn.commit()
            conn.close()
            st.success("미션 & 비전이 저장되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 핵심 목표 섹션
    st.subheader("핵심 목표 (Key Objectives)")
    
    # 현재 핵심 목표 표시
    if key_objectives_data:
        objectives_df = pd.DataFrame(key_objectives_data)
        st.dataframe(objectives_df)
    
    # 핵심 목표 추가
    with st.form("add_objective_form"):
        objective_category = st.text_input("목표 카테고리 (예: 매출 목표, 사업 영역 확장)")
        objective_text = st.text_area("목표 내용")
        objective_order = st.number_input("정렬 순서", min_value=1, step=1)
        
        submit_add_objective = st.form_submit_button("핵심 목표 추가")
    
    if submit_add_objective and objective_category and objective_text:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO key_objectives (category, objective_text, sort_order) VALUES (%s, %s, %s)",
                (objective_category, objective_text, objective_order)
            )
            conn.commit()
            conn.close()
            st.success("핵심 목표가 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 핵심 목표 수정/삭제
    if key_objectives_data:
        st.subheader("핵심 목표 수정/삭제")
        
        objective_ids = [obj['id'] for obj in key_objectives_data]
        objective_names = [f"{obj['category']} - {obj['objective_text'][:50]}..." for obj in key_objectives_data]
        
        selected_objective_index = st.selectbox(
            "수정/삭제할 핵심 목표 선택",
            range(len(objective_ids)),
            format_func=lambda i: objective_names[i]
        )
        
        selected_objective = key_objectives_data[selected_objective_index]
        
        with st.form("edit_objective_form"):
            edit_objective_category = st.text_input("목표 카테고리", value=selected_objective['category'])
            edit_objective_text = st.text_area("목표 내용", value=selected_objective['objective_text'])
            edit_objective_order = st.number_input("정렬 순서", value=selected_objective['sort_order'], min_value=1, step=1)
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit_objective = st.form_submit_button("핵심 목표 수정")
            with col2:
                submit_delete_objective = st.form_submit_button("핵심 목표 삭제", type="primary")
        
        if submit_edit_objective:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE key_objectives SET category = %s, objective_text = %s, sort_order = %s WHERE id = %s",
                    (edit_objective_category, edit_objective_text, edit_objective_order, selected_objective['id'])
                )
                conn.commit()
                conn.close()
                st.success("핵심 목표가 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete_objective:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM key_objectives WHERE id = %s",
                    (selected_objective['id'],)
                )
                conn.commit()
                conn.close()
                st.success("핵심 목표가 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
    
    # 핵심 가치 섹션
    st.subheader("핵심 가치 (Core Values)")
    
    # 현재 핵심 가치 표시
    if core_values_data:
        values_df = pd.DataFrame(core_values_data)
        st.dataframe(values_df)
    
    # 핵심 가치 추가
    with st.form("add_value_form"):
        value_title = st.text_input("가치 제목 (예: 유의주의와 끊임없는 시도)")
        value_description = st.text_area("가치 설명")
        value_order = st.number_input("정렬 순서", min_value=1, step=1, key="add_value_order")
        
        submit_add_value = st.form_submit_button("핵심 가치 추가")
    
    if submit_add_value and value_title and value_description:
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO core_values (value_title, value_description, sort_order) VALUES (%s, %s, %s)",
                (value_title, value_description, value_order)
            )
            conn.commit()
            conn.close()
            st.success("핵심 가치가 추가되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"오류 발생: {err}")
    
    # 핵심 가치 수정/삭제
    if core_values_data:
        st.subheader("핵심 가치 수정/삭제")
        
        value_ids = [val['id'] for val in core_values_data]
        value_names = [val['value_title'] for val in core_values_data]
        
        selected_value_index = st.selectbox(
            "수정/삭제할 핵심 가치 선택",
            range(len(value_ids)),
            format_func=lambda i: value_names[i]
        )
        
        selected_value = core_values_data[selected_value_index]
        
        with st.form("edit_value_form"):
            edit_value_title = st.text_input("가치 제목", value=selected_value['value_title'])
            edit_value_description = st.text_area("가치 설명", value=selected_value['value_description'])
            edit_value_order = st.number_input("정렬 순서", value=selected_value['sort_order'], min_value=1, step=1)
            
            col1, col2 = st.columns(2)
            with col1:
                submit_edit_value = st.form_submit_button("핵심 가치 수정")
            with col2:
                submit_delete_value = st.form_submit_button("핵심 가치 삭제", type="primary")
        
        if submit_edit_value:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE core_values SET value_title = %s, value_description = %s, sort_order = %s WHERE id = %s",
                    (edit_value_title, edit_value_description, edit_value_order, selected_value['id'])
                )
                conn.commit()
                conn.close()
                st.success("핵심 가치가 수정되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
        
        if submit_delete_value:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM core_values WHERE id = %s",
                    (selected_value['id'],)
                )
                conn.commit()
                conn.close()
                st.success("핵심 가치가 삭제되었습니다.")
                st.rerun()
            except mysql.connector.Error as err:
                st.error(f"오류 발생: {err}")
    
    # 미션 & 비전 데이터 초기 로드 버튼
    st.subheader("미션 & 비전 데이터 초기화")
    
    if st.button("신사업실 미션 & 비전 데이터 로드", type="primary"):
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM mission_vision")
            cursor.execute("DELETE FROM key_objectives")
            cursor.execute("DELETE FROM core_values")
            
            # 미션 & 비전 데이터 추가
            mission_text = "AI와 IoT 기술로 사람들의 삶을 더 안전하고, 건강하고, 편리하게 하는 스마트 공간 솔루션을 개발하여 회사의 성장 동력을 창출하고 혁신적인 조직 문화를 선도한다."
            vision_text = "2027년까지 500억 매출 달성으로 IPO 기반을 마련하고, 인테리어 업계의 AI+IoT 통합 솔루션 표준을 제시하는 혁신 리더가 된다."
            
            cursor.execute(
                "INSERT INTO mission_vision (mission_text, vision_text) VALUES (%s, %s)",
                (mission_text, vision_text)
            )
            
            # 핵심 목표 데이터 추가
            key_objectives = [
                ("매출 목표", "1년차: 60억 달성", 1),
                ("매출 목표", "2년차: 200억 달성", 2),
                ("매출 목표", "3년차: 500억 달성", 3),
                ("매출 목표", "5년차: 1,200억 달성", 4),
                ("사업 영역 확장", "스마트 조명 및 일반 조명 시장 진입 및 확대", 1),
                ("사업 영역 확장", "AI 조명 제어 시스템 개발 및 상용화", 2),
                ("사업 영역 확장", "인테리어 B2B 플랫폼 구축 및 시장 선점", 3),
                ("조직 역량 강화", "AI 활용 기술 습득 및 내재화", 1),
                ("조직 역량 강화", "관련 자격증(전기 등) 취득", 2),
                ("조직 역량 강화", "리더 육성을 위한 독서 및 학습 프로그램 운영", 3)
            ]
            
            for category, text, order in key_objectives:
                cursor.execute(
                    "INSERT INTO key_objectives (category, objective_text, sort_order) VALUES (%s, %s, %s)",
                    (category, text, order)
                )
            
            # 핵심 가치 데이터 추가
            core_values = [
                ("유의주의(有意注意)와 끊임없는 시도", "목표를 향한 의식적인 집중과 지속적인 도전 정신 함양\n실패를 두려워하지 않는 문화 조성", 1),
                ("투명성과 진실성에 기반한 협력", "솔직한 소통과 신뢰를 바탕으로 한 팀워크 구축\n데이터 기반 의사결정과 신뢰도 가중 투표 시스템 도입", 2),
                ("아이디어 성과주의", "혁신적인 아이디어와 실질적 성과에 대한 인정과 보상\n레이 달리오의 \"원칙\"을 기반으로 한 성과 중심 문화 정착", 3),
                ("합리적 효율성", "\"매출은 늘리고, 비용은 줄이고, 기회는 붙잡고, 문제는 해결하는\" 사고방식 내재화\nAI 활용을 통한 업무 효율화 추구", 4)
            ]
            
            for title, description, order in core_values:
                cursor.execute(
                    "INSERT INTO core_values (value_title, value_description, sort_order) VALUES (%s, %s, %s)",
                    (title, description, order)
                )
            
            conn.commit()
            conn.close()
            st.success("미션 & 비전 데이터가 성공적으로 로드되었습니다.")
            st.rerun()
        except mysql.connector.Error as err:
            st.error(f"데이터 로드 중 오류 발생: {err}") 