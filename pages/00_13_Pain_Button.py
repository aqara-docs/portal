import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from langchain.chat_models import ChatOllama, ChatOpenAI
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API 키 확인 및 설정
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')

# OpenAI를 기본 모델로 설정
default_model = "gpt-4o-mini"

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

def get_model_display_name(model_name):
    """모델 표시 이름 생성"""
    if model_name == "gpt-4o-mini":
        return "GPT-4-mini (OpenAI)"
    elif ':' in model_name:
        return f"{model_name.split(':')[0]} ({model_name.split(':')[1]})"
    else:
        return model_name

def get_available_models():
    """사용 가능한 LLM 모델 목록"""
    return [
        "gpt-4o-mini",       # OpenAI 기본 모델 (빠르고 정확)
        "mistral:latest",     # 소형 모델 (오프라인 가능)
        "gemma2:latest",      # 소형 모델 (오프라인 가능)
        "llama3.1:latest",    # 소형 모델 (오프라인 가능)
    ]

def init_db():
    """데이터베이스 초기화"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기존 테이블 존재 여부 확인
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name = 'dot_meetings'
        """)
        
        if cursor.fetchone()['count'] == 0:
            st.error("기본 테이블이 없습니다. 회의 시스템을 먼저 설정해주세요.")
            return False
        
        # Pain Button 테이블 존재 여부 확인
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name IN ('pain_events', 'pain_discussions', 'pain_metrics')
        """)
        
        # 테이블이 이미 존재하면 초기화 완료로 간주
        if cursor.fetchone()['count'] == 3:
            return True
        
        # Pain Button 테이블 생성
        cursor.execute("DROP TABLE IF EXISTS pain_metrics")
        cursor.execute("DROP TABLE IF EXISTS pain_discussions")
        cursor.execute("DROP TABLE IF EXISTS pain_events")
        
        # pain_events 테이블 생성
        cursor.execute("""
            CREATE TABLE pain_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                meeting_id INT,
                sender_id INT NOT NULL,
                target_id INT NOT NULL,
                pain_level INT NOT NULL,
                category VARCHAR(50) NOT NULL,
                emotion VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                context TEXT,
                reflection TEXT,
                llm_analysis TEXT,
                llm_model VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                resolution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES dot_meetings(meeting_id),
                FOREIGN KEY (sender_id) REFERENCES dot_user_credibility(user_id),
                FOREIGN KEY (target_id) REFERENCES dot_user_credibility(user_id)
            )
        """)
        
        # pain_discussions 테이블 생성
        cursor.execute("""
            CREATE TABLE pain_discussions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pain_event_id INT NOT NULL,
                user_id INT NOT NULL,
                comment TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pain_event_id) REFERENCES pain_events(id),
                FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id)
            )
        """)
        
        # pain_metrics 테이블 생성
        cursor.execute("""
            CREATE TABLE pain_metrics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                meeting_id INT,
                metric_type VARCHAR(50) NOT NULL,
                metric_value FLOAT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES dot_meetings(meeting_id)
            )
        """)
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"테이블 생성 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_team_members():
    """팀 멤버 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 사용자 정보 조회
        cursor.execute("""
            SELECT 
                user_id,
                user_name,
                credibility_score,
                0 as pain_count,
                0 as avg_pain_level
            FROM dot_user_credibility
            ORDER BY user_name
        """)
        
        team_members = cursor.fetchall()
        
        # pain_events 테이블이 있고 필요한 컬럼이 있는지 확인
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'pain_events'
            AND column_name IN ('id', 'target_id', 'pain_level')
        """)
        
        columns_exist = cursor.fetchone()['count'] == 3
        
        if columns_exist:
            # pain_events 테이블이 있고 필요한 컬럼이 모두 있으면 Pain 통계 업데이트
            for member in team_members:
                cursor.execute("""
                    SELECT 
                        COUNT(id) as pain_count,
                        AVG(pain_level) as avg_pain_level
                    FROM pain_events
                    WHERE target_id = %s
                """, (member['user_id'],))
                stats = cursor.fetchone()
                if stats:
                    member['pain_count'] = stats['pain_count'] or 0
                    member['avg_pain_level'] = stats['avg_pain_level'] or 0
        
        return team_members
    finally:
        cursor.close()
        conn.close()

def get_active_meetings():
    """현재 활성화된 회의 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 현재 사용자가 참여한 활성 회의만 조회
        cursor.execute("""
            SELECT 
                m.*,
                COUNT(DISTINCT mp.user_id) as participant_count,
                GROUP_CONCAT(DISTINCT u.user_name) as participants,
                COUNT(DISTINCT pe.id) as pain_count,
                AVG(pe.pain_level) as avg_pain_level
            FROM dot_meetings m
            JOIN dot_meeting_participants mp ON m.meeting_id = mp.meeting_id
            LEFT JOIN dot_user_credibility u ON mp.user_id = u.user_id
            LEFT JOIN pain_events pe ON m.meeting_id = pe.meeting_id
            WHERE m.status = 'active'
            AND EXISTS (
                SELECT 1 FROM dot_meeting_participants mp2
                WHERE mp2.meeting_id = m.meeting_id
                AND mp2.user_id = (
                    SELECT user_id FROM dot_user_credibility 
                    WHERE user_name = %s
                )
            )
            GROUP BY m.meeting_id
            ORDER BY m.created_at DESC
        """, (st.session_state.user_name,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_meeting_participants(meeting_id):
    """회의 참여자 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                u.user_id,
                u.user_name,
                u.credibility_score,
                COUNT(pe.id) as pain_count,
                AVG(pe.pain_level) as avg_pain_level
            FROM dot_meeting_participants mp
            JOIN dot_user_credibility u ON mp.user_id = u.user_id
            LEFT JOIN pain_events pe ON u.user_id = pe.target_id 
                AND pe.meeting_id = mp.meeting_id
            WHERE mp.meeting_id = %s
            GROUP BY u.user_id, u.user_name
            ORDER BY u.user_name
        """, (meeting_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"참여자 정보 조회 중 오류 발생: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def save_pain_event(data):
    """Pain 이벤트 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 회의 모드인 경우 회의 참여자 확인
        if data.get('meeting_id'):
            cursor.execute("""
                SELECT COUNT(*) as is_participant
                FROM dot_meeting_participants
                WHERE meeting_id = %s AND user_id = %s
            """, (data['meeting_id'], data['target_id']))
            
            if cursor.fetchone()['is_participant'] == 0:
                return False, "대상자가 해당 회의의 참여자가 아닙니다.", None
        
        # Pain 이벤트 저장
        cursor.execute("""
            INSERT INTO pain_events (
                meeting_id, sender_id, target_id, pain_level,
                category, emotion, description, context,
                reflection, llm_analysis, llm_model, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            data['meeting_id'], data['sender_id'], data['target_id'],
            data['pain_level'], data['category'], data['emotion'],
            data['description'], data.get('context'), data.get('reflection'),
            data.get('llm_analysis'), data.get('llm_model')
        ))
        
        pain_event_id = cursor.lastrowid
        
        # 신뢰도 점수 업데이트
        cursor.execute("""
            UPDATE dot_user_credibility
            SET credibility_score = GREATEST(0, credibility_score - %s)
            WHERE user_id = %s
        """, (data['pain_level'] * 0.1, data['target_id']))
        
        conn.commit()
        return True, "Pain이 기록되었습니다.", pain_event_id
            
    except Exception as e:
        return False, f"오류 발생: {str(e)}", None
    finally:
        cursor.close()
        conn.close()

def add_discussion(pain_event_id, user_id, comment):
    """Pain 이벤트에 대한 토론 추가"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO pain_discussions (
                pain_event_id, user_id, comment
            ) VALUES (%s, %s, %s)
        """, (pain_event_id, user_id, comment))
        
        conn.commit()
        return True, "의견이 추가되었습니다."
    except Exception as e:
        return False, f"오류 발생: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def get_discussions(pain_event_id):
    """Pain 이벤트의 토론 내용 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                d.*,
                u.user_name
            FROM pain_discussions d
            JOIN dot_user_credibility u ON d.user_id = u.user_id
            WHERE d.pain_event_id = %s
            ORDER BY d.created_at
        """, (pain_event_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def analyze_with_llm(pain_data, model_name):
    """LLM을 사용하여 Pain 데이터 분석"""
    try:
        # OpenAI 모델 사용
        if model_name == "gpt-4o-mini":
            llm = ChatOpenAI(
                model_name=MODEL_NAME,
                openai_api_key=OPENAI_API_KEY,
                temperature=0.1
            )
        # Ollama 모델 사용
        else:
            llm = ChatOllama(
                model=model_name,
                temperature=0.1
            )
        
        # 패턴 분석인 경우와 개별 Pain 분석인 경우를 구분
        if 'frequency' in pain_data:  # 패턴 분석
            prompt = f"""당신은 조직 문화와 갈등 해결 전문가입니다. 
다음 Pain 패턴을 분석하고 해결 방안을 제시해주세요.

카테고리: {pain_data['category']}
감정: {pain_data['emotion']}
발생 빈도: {pain_data['frequency']}회
평균 Pain 레벨: {pain_data['avg_pain_level']:.1f}
발생 사례:
{pain_data['descriptions']}

다음 관점에서 분석해주세요:
1. 패턴 진단: 이런 Pain이 반복되는 근본적인 원인
2. 조직적 해결: 조직 차원에서 취할 수 있는 조치
3. 예방 전략: 유사 패턴의 재발 방지를 위한 제안
4. 조직 문화: 이 패턴이 조직 문화에 주는 시사점
5. 개선 계획: 구체적인 개선 계획 제안

한국어로 답변해주세요."""

        else:  # 개별 Pain 분석
            meeting_info = (
                f"회의: {pain_data.get('meeting_title', '일반 상황')}\n"
                if pain_data.get('meeting_title') 
                else "상황: 일반 피드백\n"
            )
            
            prompt = f"""당신은 조직 문화와 갈등 해결 전문가입니다. 
다음 Pain 상황을 분석하고 해결 방안을 제시해주세요.

{meeting_info}
발신자: {pain_data.get('sender_name', '익명')}
대상자: {pain_data.get('target_name', '익명')}
카테고리: {pain_data['category']}
Pain 레벨: {pain_data['pain_level']}
감정: {pain_data['emotion']}
상황 설명: {pain_data['description']}
맥락: {pain_data.get('context', '')}

다음 관점에서 분석해주세요:
1. 상황 진단: 이 Pain이 발생한 근본적인 원인
2. 즉각적 해결: 현재 상황에서 취할 수 있는 조치
3. 장기적 개선: 유사 상황 예방을 위한 제안
4. 조직 문화: 이 상황이 조직 문화에 주는 시사점
5. 대화 제안: 건설적인 대화를 위한 구체적인 제안

한국어로 답변해주세요."""
        
        response = llm.invoke(prompt)
        return response.content
            
    except Exception as e:
        st.error(f"LLM 분석 중 오류 발생: {str(e)}")
        return None

def get_pain_patterns():
    """저장된 Pain 패턴 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 필요한 테이블과 컬럼이 모두 있는지 확인
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name IN ('pain_events', 'dot_meetings')
        """)
        
        if cursor.fetchone()['count'] < 2:
            return []
        
        # Pain 패턴 조회
        cursor.execute("""
            SELECT 
                pe.category,
                AVG(pe.pain_level) as pain_level,
                pe.emotion,
                COUNT(*) as frequency,
                AVG(pe.pain_level) as avg_pain_level,
                GROUP_CONCAT(
                    CONCAT(
                        DATE_FORMAT(pe.created_at, '%Y-%m-%d %H:%i'), 
                        ': ', 
                        pe.description,
                        CASE 
                            WHEN pe.meeting_id IS NOT NULL 
                            THEN CONCAT(' (회의: ', m.title, ')')
                            ELSE ''
                        END
                    ) 
                    ORDER BY pe.created_at DESC 
                    SEPARATOR '\n'
                ) as descriptions,
                MAX(pe.created_at) as last_occurred
            FROM pain_events pe
            LEFT JOIN dot_meetings m ON pe.meeting_id = m.meeting_id
            GROUP BY pe.category, pe.emotion
            HAVING COUNT(*) > 1
            ORDER BY frequency DESC, avg_pain_level DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_pain_history():
    """Pain 이벤트 히스토리 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                pe.*,
                sender.user_name as sender_name,
                target.user_name as target_name,
                m.title as meeting_title
            FROM pain_events pe
            JOIN dot_user_credibility sender ON pe.sender_id = sender.user_id
            JOIN dot_user_credibility target ON pe.target_id = target.user_id
            LEFT JOIN dot_meetings m ON pe.meeting_id = m.meeting_id
            ORDER BY pe.created_at DESC
            LIMIT 50
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_unresolved_pains(meeting_id=None):
    """미해결된 Pain 이벤트 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 기본 쿼리
        query = """
            SELECT 
                pe.*,
                sender.user_name as sender_name,
                target.user_name as target_name,
                m.title as meeting_title,
                COUNT(pd.id) as discussion_count
            FROM pain_events pe
            JOIN dot_user_credibility sender ON pe.sender_id = sender.user_id
            JOIN dot_user_credibility target ON pe.target_id = target.user_id
            LEFT JOIN dot_meetings m ON pe.meeting_id = m.meeting_id
            LEFT JOIN pain_discussions pd ON pe.id = pd.pain_event_id
            WHERE pe.status != 'resolved'
        """
        
        if meeting_id:
            query += " AND pe.meeting_id = %s"
            cursor.execute(query + " GROUP BY pe.id ORDER BY pe.created_at DESC", (meeting_id,))
        else:
            cursor.execute(query + " GROUP BY pe.id ORDER BY pe.created_at DESC")
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_pain_status(pain_id, status, resolution=None):
    """Pain 이벤트 상태 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # status 컬럼이 있는지 확인
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'pain_events'
            AND column_name = 'status'
        """)
        
        if cursor.fetchone()['count'] == 0:
            # status 컬럼 추가
            cursor.execute("""
                ALTER TABLE pain_events
                ADD COLUMN status VARCHAR(20) DEFAULT 'pending'
            """)
        
        # 상태 업데이트
        if resolution:
            cursor.execute("""
                UPDATE pain_events
                SET status = %s, resolution = %s
                WHERE id = %s
            """, (status, resolution, pain_id))
        else:
            cursor.execute("""
                UPDATE pain_events
                SET status = %s
                WHERE id = %s
            """, (status, pain_id))
        
        conn.commit()
        return True, "상태가 업데이트되었습니다."
    except Exception as e:
        return False, f"오류 발생: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def get_meeting_metrics(meeting_id):
    """회의의 Pain 지표 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(pe.id) as pain_count,
                AVG(pe.pain_level) as avg_pain_level,
                COUNT(DISTINCT pe.target_id) as affected_users,
                COUNT(DISTINCT pd.id) as discussion_count,
                COUNT(CASE WHEN pe.status = 'resolved' THEN 1 END) as resolved_count,
                GROUP_CONCAT(DISTINCT pe.category) as pain_categories
            FROM dot_meetings m
            LEFT JOIN pain_events pe ON m.meeting_id = pe.meeting_id
            LEFT JOIN pain_discussions pd ON pe.id = pd.pain_event_id
            WHERE m.meeting_id = %s
            GROUP BY m.meeting_id
        """, (meeting_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def update_pain_metrics(meeting_id):
    """회의의 Pain 지표 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 기존 지표 삭제
        cursor.execute("""
            DELETE FROM pain_metrics 
            WHERE meeting_id = %s
        """, (meeting_id,))
        
        # 새로운 지표 계산 및 저장
        metrics = [
            ("pain_frequency", "COUNT(*)", "Pain 발생 빈도"),
            ("avg_pain_level", "AVG(pain_level)", "평균 Pain 레벨"),
            ("affected_ratio", "COUNT(DISTINCT target_id) / COUNT(DISTINCT p.user_id) * 100", "영향 받은 참여자 비율"),
            ("resolution_rate", "COUNT(CASE WHEN status = 'resolved' THEN 1 END) / COUNT(*) * 100", "해결률"),
            ("discussion_rate", "COUNT(DISTINCT pd.id) / COUNT(*) * 100", "토론 참여율")
        ]
        
        for metric_type, calc_expr, desc in metrics:
            cursor.execute(f"""
                INSERT INTO pain_metrics (
                    meeting_id, metric_type, metric_value, description
                )
                SELECT 
                    %s,
                    %s,
                    {calc_expr},
                    %s
                FROM pain_events pe
                LEFT JOIN pain_discussions pd ON pe.id = pd.pain_event_id
                JOIN dot_meeting_participants p ON pe.meeting_id = p.meeting_id
                WHERE pe.meeting_id = %s
                GROUP BY pe.meeting_id
            """, (meeting_id, metric_type, desc, meeting_id))
        
        conn.commit()
        return True, "지표가 업데이트되었습니다."
    except Exception as e:
        return False, f"오류 발생: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def get_pain_metrics(meeting_id):
    """회의의 Pain 지표 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT metric_type, metric_value, description
            FROM pain_metrics
            WHERE meeting_id = %s
            ORDER BY created_at DESC
        """, (meeting_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_user_id(user_name):
    """사용자 이름으로 ID 조회 (없으면 생성)"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 사용자 조회
        cursor.execute("""
            SELECT user_id
            FROM dot_user_credibility
            WHERE user_name = %s
        """, (user_name,))
        
        result = cursor.fetchone()
        if result:
            return result['user_id']
        
        # 새 사용자 생성
        cursor.execute("""
            INSERT INTO dot_user_credibility (user_name, credibility_score)
            VALUES (%s, 5.0)
        """, (user_name,))
        
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()

def main():
    # DB 초기화 (가장 먼저 실행)
    if not init_db():
        st.error("테이블 생성 실패. 프로그램을 종료합니다.")
        st.stop()
    
    st.title("Pain Button 🔴")
    st.subheader("조직의 성장을 위한 정직한 피드백")
    
    # 사용자 인증
    if 'user_name' not in st.session_state:
        st.session_state.user_name = ""
    
    col1, col2 = st.columns([3, 1])
    with col1:
        user_name = st.text_input(
            "이름을 입력하세요",
            value=st.session_state.user_name,
            key="user_name_input"
        )
    with col2:
        submit = st.button("참여하기", use_container_width=True)
    
    # Enter 키나 버튼 클릭으로 진행
    if (user_name and user_name != st.session_state.user_name) or submit:
        if not user_name:
            st.warning("참여하려면 이름을 입력하세요.")
            st.stop()
        st.session_state.user_name = user_name
        st.rerun()
    
    if not st.session_state.user_name:
        st.info("이름을 입력하고 Enter 키를 누르거나 '참여하기' 버튼을 클릭하세요.")
        st.stop()
    
    # 모드 선택
    mode = st.radio(
        "모드 선택",
        ["독립 모드", "회의 모드"],
        help="독립 모드: 일반적인 피드백 / 회의 모드: 회의 중 피드백"
    )
    
    # 회의 정보 초기화
    selected_meeting = None
    
    if mode == "회의 모드":
        active_meetings = get_active_meetings()
        if not active_meetings:
            st.warning("참여 가능한 회의가 없습니다. 독립 모드를 이용해주세요.")
            mode = "독립 모드"
        else:
            try:
                selected_meeting = st.selectbox(
                    "회의 선택",
                    active_meetings,
                    format_func=lambda x: (
                        f"{x['title']} "
                        f"(참여자: {x['participant_count']}명, "
                        f"Pain: {x['pain_count'] or 0}건)"
                    )
                )
                if selected_meeting:
                    # 회의 참여자 목록 표시
                    participants = get_meeting_participants(selected_meeting['meeting_id'])
                    st.write("### 현재 회의")
                    st.write(f"제목: {selected_meeting['title']}")
                    st.write("참여자:")
                    for p in participants:
                        st.write(f"- {p['user_name']} (신뢰도: {p['credibility_score']:.2f})")
                else:
                    st.error("회의를 선택해주세요.")
                    st.stop()
            except Exception as e:
                st.error(f"회의 정보 로드 중 오류 발생: {str(e)}")
                st.stop()
    
    # LLM 모델 선택
    models = get_available_models()
    
    # AI 분석 설정
    with st.sidebar:
        st.subheader("AI 분석 설정")
        enable_ai = st.toggle("AI 분석 활성화", value=False)
        
        if enable_ai:
            st.info("""
            **모델 선택 가이드:**
            - GPT-4-mini: 빠르고 정확한 분석 (기본값)
            - Mistral: 오프라인 사용 가능, 한국어 성능 우수
            - Gemma2: 가벼운 분석에 적합
            - LLaMA: 복잡한 분석에 적합
            """)
            
            # session_state 초기화
            if 'llm_model' not in st.session_state:
                st.session_state.llm_model = default_model
            
            selected_model = st.selectbox(
                "🤖 LLM 모델 선택",
                models,
                index=models.index(st.session_state.llm_model),
                format_func=get_model_display_name
            )
            
            # 선택된 모델이 변경된 경우 session_state 업데이트
            if selected_model != st.session_state.llm_model:
                st.session_state.llm_model = selected_model
    
    # AI 분석이 비활성화된 경우 session_state에서 llm_model 제거
    if not enable_ai and 'llm_model' in st.session_state:
        del st.session_state.llm_model
    
    # 탭 구성
    tabs = st.tabs(["Pain 기록", "패턴 분석", "토론/해결"])
    
    with tabs[0]:
        st.header("Pain Button")
        
        # 팀 멤버별 Pain Button
        team_members = get_team_members()
        
        # 현재 사용자 ID 확인
        current_user_id = get_user_id(user_name)
        
        for member in team_members:
            if member['user_name'] != user_name:  # 자신에게는 Pain Button을 표시하지 않음
                with st.expander(f"😣 {member['user_name']} (신뢰도: {member['credibility_score']:.2f})"):
                    col1, col2 = st.columns([2, 3])
                    
                    with col1:
                        pain_level = st.slider(
                            "Pain 레벨",
                            1, 5, 3,
                            help="1: 약한 불편함, 5: 극도의 고통",
                            key=f"pain_level_{member['user_id']}"
                        )
                        
                        category = st.selectbox(
                            "카테고리",
                            ["의사결정", "커뮤니케이션", "실행", "관계",
                             "시간관리", "리더십", "기술적 문제", "기타"],
                            key=f"category_{member['user_id']}"
                        )
                        
                        emotion = st.selectbox(
                            "감정",
                            ["좌절", "분노", "불안", "두려움", "슬픔",
                             "당황", "부끄러움", "죄책감", "기타"],
                            key=f"emotion_{member['user_id']}"
                        )
                    
                    with col2:
                        description = st.text_area(
                            "상황 설명",
                            key=f"description_{member['user_id']}"
                        )
                        context = st.text_area(
                            "맥락/배경",
                            key=f"context_{member['user_id']}"
                        )
                    
                    if st.button("Pain 전달", key=f"send_{member['user_id']}"):
                        if not description:
                            st.error("상황 설명을 작성해주세요.")
                        else:
                            # 회의 모드에서 참여자가 아닌 경우 차단
                            if selected_meeting:
                                participants = get_meeting_participants(selected_meeting['meeting_id'])
                                if not any(p['user_id'] == member['user_id'] for p in participants):
                                    st.error("선택한 사용자는 현재 회의의 참여자가 아닙니다.")
                                    return
                            pain_data = {
                                'meeting_id': selected_meeting['meeting_id'] if selected_meeting else None,
                                'sender_id': current_user_id,
                                'target_id': member['user_id'],
                                'pain_level': pain_level,
                                'category': category,
                                'emotion': emotion,
                                'description': description,
                                'context': context,
                                'sender_name': user_name,
                                'target_name': member['user_name']
                            }
                            
                            # AI 분석은 선택적으로 실행
                            if enable_ai:
                                with st.spinner("AI가 분석 중입니다..."):
                                    analysis = analyze_with_llm(pain_data, st.session_state.llm_model)
                                    if analysis:
                                        pain_data['llm_analysis'] = analysis
                                        pain_data['llm_model'] = st.session_state.llm_model
                            
                            success, msg, pain_event_id = save_pain_event(pain_data)
                            if success:
                                st.success(msg)
                                if enable_ai and 'llm_analysis' in pain_data:
                                    st.markdown("#### 🤖 AI 분석 결과")
                                    st.write(pain_data['llm_analysis'])
                            else:
                                st.error(msg)
    
    with tabs[1]:
        st.header("Pain 패턴 분석")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 기존의 차트들
            patterns = get_pain_patterns()
            if patterns:
                df_category = pd.DataFrame(patterns)
                
                # 카테고리별 Pain 빈도
                fig1 = px.bar(
                    df_category,
                    x='category',
                    y='frequency',
                    color='avg_pain_level',
                    title="카테고리별 Pain 빈도와 평균 강도",
                    labels={
                        'category': '카테고리',
                        'frequency': '발생 빈도',
                        'avg_pain_level': '평균 Pain 레벨'
                    }
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                # 감정별 Pain 분포
                fig2 = px.pie(
                    df_category,
                    values='frequency',
                    names='emotion',
                    title="감정별 Pain 분포",
                    labels={'emotion': '감정'}
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                # Pain 통계
                total_pains = sum(p['frequency'] for p in patterns)
                if total_pains > 0:  # 0으로 나누기 방지
                    avg_pain = sum(p['avg_pain_level'] * p['frequency'] for p in patterns) / total_pains
                    most_common = max(patterns, key=lambda x: x['frequency'])
                    most_painful = max(patterns, key=lambda x: x['avg_pain_level'])
                    
                    with col2:
                        st.subheader("주요 Pain 지표")
                        st.metric("총 Pain 발생", f"{total_pains}건")
                        st.metric("평균 Pain 레벨", f"{avg_pain:.1f}")
                        st.metric("가장 빈번한 Pain", 
                                f"{most_common['category']} ({most_common['frequency']}회)")
                        st.metric("가장 강도 높은 Pain",
                                f"{most_painful['category']} (레벨 {most_painful['avg_pain_level']:.1f})")
            else:
                st.info("아직 기록된 Pain이 없습니다.")
        
        # 상세 패턴 분석
        st.subheader("상세 패턴 분석")
        for pattern in patterns:
            with st.expander(
                f"{pattern['category']} - {pattern['emotion']} "
                f"(빈도: {pattern['frequency']}, 평균 Pain: {pattern['avg_pain_level']:.1f})"
            ):
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    st.write("**발생 사례:**")
                    for desc in pattern['descriptions'].split('\n'):
                        st.write(f"- {desc}")
                    
                    st.write(f"**마지막 발생:** {pattern['last_occurred']}")
                
                with col2:
                    st.write("#### 🤖 AI 분석")
                    # AI 패턴 분석
                    if enable_ai:
                        if st.button(f"패턴 분석하기", key=f"analyze_{pattern['category']}_{pattern['emotion']}"):
                            with st.spinner("패턴을 분석 중입니다..."):
                                pattern_data = {
                                    'category': pattern['category'],
                                    'emotion': pattern['emotion'],
                                    'frequency': pattern['frequency'],
                                    'avg_pain_level': pattern['avg_pain_level'],
                                    'descriptions': pattern['descriptions']
                                }
                                analysis = analyze_with_llm(pattern_data, st.session_state.llm_model)
                                if analysis:
                                    st.markdown(analysis)
                    else:
                        st.info("AI 분석을 사용하려면 사이드바에서 AI 분석을 활성화하세요.")
    
    with tabs[2]:
        st.header("Pain 토론 & 해결")
        
        # 회의별 필터
        show_all = st.checkbox("모든 회의의 Pain 보기")
        
        if show_all or mode == "독립 모드":
            unresolved = get_unresolved_pains()
        else:
            unresolved = get_unresolved_pains(selected_meeting['meeting_id'])
        
        # Pain 지표 (회의 모드일 때만 표시)
        if mode == "회의 모드" and selected_meeting:
            st.subheader("Pain 지표")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # 지표 업데이트
                if st.button("지표 업데이트"):
                    with st.spinner("지표를 업데이트하는 중..."):
                        success, msg = update_pain_metrics(selected_meeting['meeting_id'])
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                
                # 지표 표시
                metrics = get_pain_metrics(selected_meeting['meeting_id'])
                if metrics:
                    for metric in metrics:
                        st.metric(
                            metric['description'],
                            f"{metric['metric_value']:.1f}%"
                            if metric['metric_type'].endswith('_rate')
                            or metric['metric_type'].endswith('_ratio')
                            else f"{metric['metric_value']:.1f}"
                        )
        
        with col2:
            st.info("""
            **지표 설명**
            - Pain 발생 빈도: 총 Pain 발생 횟수
            - 평균 Pain 레벨: Pain의 평균 강도
            - 영향 받은 참여자 비율: Pain을 받은 참여자의 비율
            - 해결률: 해결된 Pain의 비율
            - 토론 참여율: Pain당 평균 토론 수
            """)
        
        # 미해결 Pain 목록
        if unresolved:
            for pain in unresolved:
                with st.expander(
                    f"💬 {pain['created_at']} - {pain['category']} "
                    f"(Pain 레벨: {pain['pain_level']}, 토론: {pain['discussion_count']})"
                ):
                    col1, col2 = st.columns([3, 2])
                    
                    with col1:
                        st.write(f"**발신자:** {pain['sender_name']}")
                        st.write(f"**대상자:** {pain['target_name']}")
                        st.write(f"**회의:** {pain['meeting_title']}")
                        st.write(f"**상황:** {pain['description']}")
                        
                        if pain['context']:
                            st.write(f"**맥락:** {pain['context']}")
                        
                        # 토론
                        st.write("---")
                        st.write("**💬 토론:**")
                        
                        discussions = get_discussions(pain['id'])
                        for d in discussions:
                            st.write(f"- **{d['user_name']}:** {d['comment']}")
                        
                        # 새 의견 추가
                        new_comment = st.text_area(
                            "의견 추가",
                            key=f"comment_{pain['id']}"
                        )
                        
                        if st.button("의견 등록", key=f"add_comment_{pain['id']}"):
                            if new_comment:
                                success, msg = add_discussion(
                                    pain['id'],
                                    current_user_id,
                                    new_comment
                                )
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    with col2:
                        st.write("**🤖 AI 분석:**")
                        if pain['llm_analysis']:
                            st.write(pain['llm_analysis'])
                        
                        st.write("---")
                        st.write("**✅ 해결 상태:**")
                        
                        resolution = st.text_area(
                            "해결 방안",
                            key=f"resolution_{pain['id']}"
                        )
                        
                        status = st.selectbox(
                            "상태",
                            ["pending", "in_progress", "resolved"],
                            key=f"status_{pain['id']}"
                        )
                        
                        if st.button("상태 업데이트", key=f"update_{pain['id']}"):
                            success, msg = update_pain_status(pain['id'], status, resolution)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("현재 미해결된 Pain이 없습니다. 👍")

if __name__ == "__main__":
    main() 