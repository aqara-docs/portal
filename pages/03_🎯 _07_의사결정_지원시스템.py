import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import json

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 페이지 설정
st.set_page_config(page_title="의사결정 지원 시스템", page_icon="🎯", layout="wide")

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

def save_decision_case(title, description, decision_maker, created_by):
    """의사결정 안건 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_cases 
            (title, description, decision_maker, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, decision_maker, created_by))
        
        case_id = cursor.lastrowid
        conn.commit()
        return case_id
    except Exception as e:
        st.error(f"안건 저장 중 오류 발생: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def save_decision_option(case_id, option_data):
    """의사결정 옵션 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_options 
            (case_id, option_name, advantages, disadvantages, 
             estimated_duration, priority, additional_info)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            case_id,
            option_data['name'],
            option_data['advantages'],
            option_data['disadvantages'],
            option_data['duration'],
            option_data['priority'],
            option_data.get('additional_info', '')
        ))
        
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()

def save_ai_analysis(case_id, model_name, analysis_content, recommendation, risk_assessment):
    """AI 분석 결과 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_ai_analysis 
            (case_id, model_name, analysis_content, recommendation, risk_assessment)
            VALUES (%s, %s, %s, %s, %s)
        """, (case_id, model_name, analysis_content, recommendation, risk_assessment))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"AI 분석 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_decision_cases():
    """의사결정 안건 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_cases 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_case_options(case_id):
    """안건의 옵션 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_options 
            WHERE case_id = %s 
            ORDER BY priority
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_ai_analysis(case_id):
    """AI 분석 결과 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_ai_analysis 
            WHERE case_id = %s 
            ORDER BY created_at DESC
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_case_status(case_id, status, final_option_id, final_comment):
    """의사결정 상태 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE decision_cases 
            SET status = %s, 
                final_option_id = %s, 
                final_comment = %s,
                decided_at = NOW()
            WHERE case_id = %s
        """, (status, final_option_id, final_comment, case_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"상태 업데이트 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def read_markdown_file(uploaded_file):
    """업로드된 마크다운 파일 읽기"""
    try:
        content = uploaded_file.read().decode('utf-8')
        return {
            'filename': uploaded_file.name,
            'content': content
        }
    except Exception as e:
        st.error(f"파일 읽기 오류: {str(e)}")
        return None

def analyze_with_ai(title, description, options, reference_files=None, model_choice="claude-3-7-sonnet-latest"):
    """AI 분석 수행"""
    try:
        base_prompt = f"""
다음 의사결정 안건을 분석해주세요:

제목: {title}
설명: {description}
"""

        if reference_files:
            base_prompt += "\n추가 참고 자료:\n"
            for file in reference_files:
                base_prompt += f"""
파일명: {file['filename']}
내용:
{file['content']}
---
"""

        base_prompt += f"""
옵션들:
{json.dumps([{
    '이름': opt['name'],
    '장점': opt['advantages'],
    '단점': opt['disadvantages'],
    '예상기간': opt['duration'],
    '우선순위': opt['priority']
} for opt in options], ensure_ascii=False, indent=2)}

다음 형식으로 분석해주세요:

1. 각 옵션별 객관적 분석
2. 각 옵션의 실현 가능성과 위험도
3. 우선순위 추천과 그 이유
4. 최종 추천안과 구체적인 실행 방안

분석시 제공된 모든 정보(설명 및 추가 참고 자료)를 종합적으로 고려해주세요.
분석은 객관적이고 전문적인 관점에서 수행해주세요."""

        if model_choice == "gpt-4o-mini":
            response = client.chat.completions.create(
                model=model_choice,
                messages=[{"role": "user", "content": base_prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        else:  # Claude 모델 사용
            response = anthropic_client.messages.create(
                model=model_choice,
                max_tokens=2000,
                messages=[{"role": "user", "content": base_prompt}]
            )
            return response.content[0].text

    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return None

def delete_decision_case(case_id):
    """의사결정 안건 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 외래 키 제약 조건으로 인해 자동으로 관련 옵션과 AI 분석도 삭제됨
        cursor.execute("""
            DELETE FROM decision_cases 
            WHERE case_id = %s
        """, (case_id,))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"안건 삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_reference_file(case_id, filename, content):
    """참고 자료 파일 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_reference_files 
            (case_id, filename, file_content)
            VALUES (%s, %s, %s)
        """, (case_id, filename, content))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"파일 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_reference_files(case_id):
    """참고 자료 파일 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_reference_files 
            WHERE case_id = %s 
            ORDER BY created_at
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("🎯 의사결정 지원 시스템")
    
    # 세션 상태 초기화
    if 'current_case_id' not in st.session_state:
        st.session_state.current_case_id = None
    if 'ai_analysis_result' not in st.session_state:
        st.session_state.ai_analysis_result = None
    if 'options' not in st.session_state:
        st.session_state.options = []
    
    tab1, tab2 = st.tabs(["의사결정 안건 등록", "의사결정 현황"])
    
    with tab1:
        st.header("새로운 의사결정 안건 등록")
        
        # 기본 정보 입력
        title = st.text_input("안건 제목")
        description = st.text_area("안건 설명")
        
        # 여러 마크다운 파일 업로드
        uploaded_files = st.file_uploader(
            "참고 자료 업로드 (여러 파일 선택 가능)", 
            type=['md', 'txt'],
            accept_multiple_files=True,
            help="추가 참고 자료가 있다면 마크다운(.md) 또는 텍스트(.txt) 파일로 업로드해주세요."
        )
        
        reference_files = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_data = read_markdown_file(uploaded_file)
                if file_data:
                    reference_files.append(file_data)
            
            if reference_files:
                with st.expander("업로드된 참고 자료 목록"):
                    for file in reference_files:
                        st.markdown(f"### 📄 {file['filename']}")
                        st.markdown(file['content'])
                        st.markdown("---")
        
        decision_maker = st.text_input("최종 의사결정자")
        created_by = st.text_input("작성자")
        
        # 옵션 입력
        st.subheader("의사결정 옵션")
        num_options = st.number_input("옵션 수", min_value=1, max_value=10, value=2)
        
        # 옵션 목록 업데이트
        if len(st.session_state.options) != num_options:
            st.session_state.options = [None] * num_options
        
        options = []
        for i in range(num_options):
            with st.expander(f"옵션 {i+1}"):
                option = {
                    'name': st.text_input(f"옵션 {i+1} 이름", key=f"name_{i}"),
                    'advantages': st.text_area(f"장점", key=f"adv_{i}"),
                    'disadvantages': st.text_area(f"단점", key=f"dis_{i}"),
                    'duration': st.text_input(f"예상 소요 기간", key=f"dur_{i}"),
                    'priority': st.number_input(f"우선순위", 1, 10, key=f"pri_{i}"),
                    'additional_info': st.text_area(f"추가 정보", key=f"add_{i}")
                }
                st.session_state.options[i] = option
                options.append(option)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("안건 저장", type="primary"):
                if title and description and decision_maker and created_by:
                    case_id = save_decision_case(title, description, decision_maker, created_by)
                    if case_id:
                        st.session_state.current_case_id = case_id
                        for option in options:
                            save_decision_option(case_id, option)
                        # 참고 자료 파일 저장
                        if reference_files:
                            for file in reference_files:
                                save_reference_file(
                                    case_id,
                                    file['filename'],
                                    file['content']
                                )
                        st.success("✅ 의사결정 안건이 저장되었습니다!")
                else:
                    st.error("모든 필수 항목을 입력해주세요.")
        
        with col2:
            # AI 모델 선택 수정
            model_choice = st.selectbox(
                "AI 모델 선택",
                [
                    "claude-3-7-sonnet-latest",
                    "gpt-4o-mini"
                ],
                help="분석에 사용할 AI 모델을 선택하세요"
            )
            
            if st.button("AI 분석 요청"):
                if not st.session_state.current_case_id:
                    st.error("먼저 안건을 저장해주세요.")
                    return
                
                if title and description and all(opt['name'] for opt in options):
                    with st.spinner("AI가 분석중입니다..."):
                        analysis = analyze_with_ai(
                            title, 
                            description, 
                            options, 
                            reference_files if reference_files else None,
                            model_choice
                        )
                        if analysis:
                            st.session_state.ai_analysis_result = analysis
                            # 안건 ID가 있을 때만 AI 분석 결과 저장
                            save_ai_analysis(
                                st.session_state.current_case_id,
                                model_choice,
                                analysis,
                                "",  # 추천사항
                                ""   # 위험평가
                            )
                else:
                    st.error("안건 정보와 옵션을 먼저 입력해주세요.")
        
        # AI 분석 결과 표시
        if st.session_state.ai_analysis_result:
            st.write("### AI 분석 결과")
            st.markdown(st.session_state.ai_analysis_result)

    with tab2:
        st.header("의사결정 현황")
        
        # 안건 목록 조회
        cases = get_decision_cases()
        
        for case in cases:
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌',
                'deferred': '⏸️'
            }.get(case['status'], '❓')
            
            with st.expander(f"{status_emoji} {case['title']} ({case['created_at'].strftime('%Y-%m-%d')})"):
                # 삭제 버튼을 우측에 배치
                col1, col2 = st.columns([5, 1])
                with col2:
                    # 삭제 확인을 위한 체크박스
                    delete_checkbox = st.checkbox("삭제 확인", key=f"delete_confirm_{case['case_id']}")
                    if delete_checkbox:
                        if st.button("🗑️ 삭제", key=f"delete_{case['case_id']}", type="primary"):
                            if delete_decision_case(case['case_id']):
                                st.success("✅ 의사결정 안건이 삭제되었습니다.")
                                st.rerun()
                    else:
                        st.button("🗑️ 삭제", key=f"delete_{case['case_id']}", disabled=True)
                        st.caption("삭제하려면 먼저 체크박스를 선택하세요")
                
                with col1:
                    st.write(f"**설명:** {case['description']}")
                    st.write(f"**의사결정자:** {case['decision_maker']}")
                    st.write(f"**상태:** {case['status'].upper()}")
                
                # 옵션 목록 표시
                options = get_case_options(case['case_id'])
                st.write("### 옵션 목록")
                
                # 옵션들을 표 형태로 표시
                for opt in options:
                    is_selected = case['final_option_id'] == opt['option_id']
                    st.markdown(f"""
                    ### {'✅ ' if is_selected else ''}옵션 {opt['option_name']}
                    **우선순위:** {opt['priority']}
                    
                    **장점:**
                    {opt['advantages']}
                    
                    **단점:**
                    {opt['disadvantages']}
                    
                    **예상 기간:** {opt['estimated_duration']}
                    {f"**추가 정보:**\n{opt['additional_info']}" if opt.get('additional_info') else ''}
                    ---
                    """)
                
                # AI 분석 결과 표시
                analyses = get_ai_analysis(case['case_id'])
                if analyses:
                    st.write("### AI 분석 결과")
                    for idx, analysis in enumerate(analyses, 1):
                        st.markdown(f"""
                        #### AI 분석 {idx} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})
                        **모델:** {analysis['model_name']}
                        
                        **분석 내용:**
                        {analysis['analysis_content']}
                        
                        {f"**추천 의견:**\n{analysis['recommendation']}" if analysis['recommendation'] else ''}
                        {f"**위험도 평가:**\n{analysis['risk_assessment']}" if analysis['risk_assessment'] else ''}
                        ---
                        """)
                
                # 의사결정 입력 (pending 상태일 때만)
                if case['status'] == 'pending':
                    st.write("### 최종 의사결정")
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        decision_status = st.selectbox(
                            "결정 상태",
                            ['approved', 'rejected', 'deferred'],
                            key=f"status_{case['case_id']}"
                        )
                    
                    with col2:
                        selected_option = st.selectbox(
                            "선택된 옵션",
                            options,
                            format_func=lambda x: x['option_name'],
                            key=f"option_{case['case_id']}"
                        )
                    
                    final_comment = st.text_area(
                        "최종 코멘트",
                        key=f"comment_{case['case_id']}"
                    )
                    
                    if st.button("의사결정 확정", key=f"decide_{case['case_id']}", type="primary"):
                        if update_case_status(
                            case['case_id'],
                            decision_status,
                            selected_option['option_id'],
                            final_comment
                        ):
                            st.success("✅ 의사결정이 저장되었습니다!")
                            st.rerun()
                else:
                    if case['final_comment']:
                        st.write("### 최종 의사결정 내용")
                        st.write(case['final_comment'])

                # 참고 자료 파일 표시
                reference_files = get_reference_files(case['case_id'])
                if reference_files:
                    st.write("### 📎 참고 자료")
                    for file in reference_files:
                        st.markdown(f"""
                        #### 📄 {file['filename']}
                        ```
                        {file['file_content']}
                        ```
                        ---
                        """)

if __name__ == "__main__":
    main() 