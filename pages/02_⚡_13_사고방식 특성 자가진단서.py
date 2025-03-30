import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
import requests

load_dotenv()

# Set page configuration
st.set_page_config(page_title="사고방식 특성 자가진단", page_icon="🧠", layout="wide")

# Page header
st.title("🧠 사고방식 특성 자가진단")
st.subheader("자신의 사고방식과 성향을 파악하여 AI와의 효과적인 협업 방식을 설계합니다.")

# DB 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_general_ci'
    )

# Google Sheets 연결 설정
def connect_to_sheets():
    # Path to your service account JSON file
    SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

    # Load credentials from the JSON file
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )

    # Connect to Google Sheets
    gc = gspread.authorize(creds)

    try:
        # Google Sheet ID and Worksheet name
        THINKING_STYLE_SPREADSHEET_ID = os.getenv('THINKING_STYLE_SPREADSHEET_ID')
        THINKING_STYLE_WORKSHEET_NAME = os.getenv('THINKING_STYLE_WORKSHEET_NAME')
        
        # Open the worksheet
        sheet = gc.open_by_key(THINKING_STYLE_SPREADSHEET_ID).worksheet(THINKING_STYLE_WORKSHEET_NAME)
        return gc
    except Exception as e:
        st.error(f"Google Sheets 연결 테스트 실패: {e}")
        st.error(f"SERVICE_ACCOUNT_FILE: {SERVICE_ACCOUNT_FILE}")
        st.error(f"Spreadsheet ID: {THINKING_STYLE_SPREADSHEET_ID}")
        st.error(f"Worksheet Name: {THINKING_STYLE_WORKSHEET_NAME}")
        return None

# AI 분석 함수
def analyze_thinking_style(answers, model="deepseek-r1:14b"):
    try:
        prompt = f"""
        다음은 사고방식 특성 자가진단 결과입니다. 이를 바탕으로 응답자의 사고방식 특성을 분석하고,
        AI와의 효과적인 협업 방식을 제안해주세요. 특히 다음 사항에 중점을 두어 분석해주세요:

        1. 주요 사고방식 특성
        2. 의사결정 스타일
        3. 정보 처리 선호도
        4. AI 협업 시 최적의 상호작용 방식
        5. 개선 및 발전 가능한 영역

        응답 내용:
        {answers}

        분석 결과를 다음 형식으로 작성해주세요:
        
        ## 사고방식 프로필
        [전반적인 사고방식 특성 요약]

        ## 강점
        - [주요 강점 1]
        - [주요 강점 2]
        - [주요 강점 3]

        ## AI 협업 최적화 제안
        - [구체적인 협업 방식 제안]
        - [커뮤니케이션 방식 제안]
        - [업무 프로세스 제안]

        ## 발전 기회
        - [개선 가능한 영역]
        - [구체적인 발전 방안]
        """
        
        response = requests.post('http://localhost:11434/api/generate',
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            })
        if response.status_code == 200:
            return response.json()['response'].strip()
        return "분석 생성 실패"
    except Exception as e:
        return f"분석 중 오류 발생: {str(e)}"

# 메인 앱
def main():
    # 기본 정보 입력
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("이름")
        department = st.text_input("부서")
    with col2:
        position = st.text_input("직책")
        date = st.date_input("진단일", value=datetime.now())

    # 설문 섹션
    sections = {
        "1. 정보 처리 방식": [
            ("새로운 프로젝트를 시작할 때, 어떤 방식을 선호하시나요?",
             ["세부 단계와 구체적인 실행 계획부터 수립", "전체적인 방향과 큰 그림부터 구상", "A와 B를 비슷하게 혼합"]),
            ("문제 해결 시 어떤 접근법이 더 편하신가요?",
             ["데이터와 사실에 기반한 논리적 분석", "경험과 직관에 기반한 통찰적 접근", "상황에 따라 두 가지 방식을 혼용"]),
            ("정보를 가장 잘 이해하고 기억하는 방식은?",
             ["문서화된 텍스트와 숫자 데이터", "도표, 이미지, 다이어그램", "두 가지 모두 비슷하게 선호"])
        ],
        "2. AI 협업 성향": [
            ("AI와의 협업에 대한 태도는?",
             ["적극적으로 활용하고 실험하길 원함", "필요한 영역에서 선택적으로 활용", "검증된 영역에서만 활용", "아직 신중한 접근 선호"]),
            ("AI에게 기대하는 역할은?",
             ["창의적인 아이디어와 새로운 관점 제시", "데이터 분석과 객관적 판단 지원", "반복적 업무의 자동화", "간단한 보조 도구로 활용"]),
            ("AI와 협업 시 선호하는 소통 방식은?",
             ["자유로운 대화와 브레인스토밍", "구조화된 질의응답", "명확한 지시와 결과물", "최소한의 필수 상호작용"])
        ],
        "3. MBTI 및 성격 유형": [
            ("MBTI 유형은 무엇인가요?",
             ["ISTJ", "ISFJ", "INFJ", "INTJ", "ISTP", "ISFP", "INFP", "INTP", 
              "ESTP", "ESFP", "ENFP", "ENTP", "ESTJ", "ESFJ", "ENFJ", "ENTJ", "모름/기타"]),
            ("에너지를 얻는 방식은?",
             ["혼자만의 시간을 통해 (내향형)", "다른 사람과의 교류를 통해 (외향형)", "상황에 따라 다름"]),
            ("정보를 인식하는 방식은?",
             ["오감을 통한 구체적 정보 선호 (감각형)", "직관과 가능성 중심 (직관형)", "둘 다 비슷하게 활용"]),
            ("의사결정 방식은?",
             ["논리와 객관성 기반 (사고형)", "가치와 감정 고려 (감정형)", "상황에 따라 다르게 적용"]),
            ("생활양식 선호도는?",
             ["계획적이고 체계적인 방식 (판단형)", "유연하고 즉흥적인 방식 (인식형)", "상황에 따라 조절"]),
            ("MBTI 관련 본인의 주요 강점은?",
             ["분석적 사고", "창의적 문제해결", "체계적 실행력", "공감능력", "리더십", "적응력", "기타"]),
            ("MBTI 관련 주의해야 할 점은?",
             ["과도한 완벽주의", "결정 지연", "감정적 대응", "독단적 판단", "우유부단함", "기타"])
        ],
        "4. 학습 및 성장 스타일": [
            ("선호하는 학습 방식은?",
             ["체계적인 커리큘럼 기반 학습", "실전 경험을 통한 학습", "자율적 탐구와 연구", "멘토링과 코칭"]),
            ("새로운 기술/도구 습득 속도는?",
             ["매우 빠른 편", "평균적인 속도", "천천히 깊이 있게", "상황에 따라 다름"]),
            ("선호하는 피드백 주기는?",
             ["수시로 자주", "정기적으로", "중요한 시점에만", "요청할 때만"])
        ],
        "5. 스트레스 관리": [
            ("스트레스 해소 방식은?",
             ["운동이나 신체 활동", "취미 활동", "명상이나 휴식", "사람들과의 대화", "업무에 더 집중"]),
            ("업무 스트레스 대처 방식은?",
             ["즉시 해결 방안 모색", "잠시 거리두기 후 해결", "동료와 상담/공유", "개인적으로 해결"])
        ],
        "6. 커뮤니케이션 선호도": [
            ("선호하는 의사소통 스타일은?",
             ["직접적이고 명확한 소통", "우회적이고 부드러운 소통", "상황에 따라 유연하게 조절"]),
            ("피드백 수용 방식은?",
             ["즉각적인 피드백 선호", "정리된 형태의 피드백 선호", "1:1 대화를 통한 피드백 선호"]),
        ],
        
        "7. 연락 및 회의 선호도": [
            ("선호하는 연락 방식은?",
             ["이메일", "메신저", "전화", "대면"]),
            ("선호하는 회의 방식은?",
             ["대면", "화상", "음성", "문자"]),
            ("긴급 연락 시 선호 방식은?",
             ["전화", "메시지", "이메일", "기타"]),
            ("업무 외 시간 연락 선호도는?",
             ["선호", "상황에 따라", "지양"]),
        ],

        "8. 업무 시간 선호도": [
            ("선호하는 업무 시간대는?",
             ["이른 아침(6-9시)", "오전(9-12시)", "오후(12-18시)", "저녁(18시 이후)"]),
            ("집중 업무 선호 시간은?",
             ["아침", "오전", "오후", "저녁"]),
            ("회의 선호 시간대는?",
             ["오전", "점심 전후", "오후", "저녁"]),
            ("선호하는 업무 주기는?",
             ["단기집중형", "장기지속형", "혼합형"]),
        ],

        "9. 전문성 및 경력": [
            ("주요 경력 분야는?",
             ["기술/개발", "기획/전략", "영업/마케팅", "디자인/UX", "재무/회계", "운영/관리", "기타"]),
            ("산업 경험은?",
             ["IT/소프트웨어", "제조/하드웨어", "금융/투자", "유통/서비스", "컨설팅", "스타트업", "기타"]),
            ("전문 기술/도구 활용 능력은?",
             ["프로그래밍/개발 도구", "데이터 분석 도구", "디자인/그래픽 도구", "프로젝트 관리 도구", "재무/회계 도구", "AI/ML 도구", "기타"]),
        ],

        "10. 성장 및 발전": [
            ("향후 발전하고 싶은 역량은?",
             ["기술/전문성 심화", "리더십/관리 능력", "새로운 분야 역량", "비즈니스 통찰력", "AI/디지털 역량", "기타"]),
            ("선호하는 업무 영역은?",
             ["전략 수립/기획", "실행/구현", "분석/리서치", "협업/조정", "관리/감독", "혁신/창의", "기타"]),
        ]
    }

    # 응답 저장용 딕셔너리
    if 'responses' not in st.session_state:
        st.session_state.responses = {}

    # 설문 표시
    for section, questions in sections.items():
        st.subheader(section)
        for q, options in questions:
            key = f"{section}_{q}"
            st.session_state.responses[key] = st.radio(q, options, key=key)
            st.markdown("---")

    # 분석 버튼
    if st.button("진단 결과 분석"):
        # 응답 데이터 정리
        responses_text = "\n".join([f"Q: {q.split('_')[1]}\nA: {a}" 
                                  for q, a in st.session_state.responses.items()])
        
        # AI 분석 실행
        analysis = analyze_thinking_style(responses_text)
        
        # 결과 표시
        st.markdown("## 🎯 진단 결과")
        st.markdown(analysis)
        
        # DB에 저장
        conn = connect_to_db()
        cursor = conn.cursor()
        
        try:
            # MySQL DB 저장
            cursor.execute("""
                INSERT INTO thinking_style_diagnosis 
                (name, department, position, test_date, responses, analysis)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, department, position, date, responses_text, analysis))
            conn.commit()  # DB 변경사항 커밋 추가
            
            # Google Sheets 저장 부분
            try:
                gc = connect_to_sheets()
                if gc is not None:
                    spreadsheet = gc.open_by_key(os.getenv('THINKING_STYLE_SPREADSHEET_ID'))
                    worksheet = spreadsheet.worksheet(os.getenv('THINKING_STYLE_WORKSHEET_NAME'))
                    
                    # 데이터 행 생성
                    new_row = [
                        date.strftime('%Y-%m-%d'),
                        name,
                        department,
                        position,
                        responses_text,
                        analysis
                    ]
                    
                    worksheet.append_row(new_row)
                    st.success("진단 결과가 DB와 Google Sheets에 성공적으로 저장되었습니다!")
                else:
                    st.warning("Google Sheets 연결에 실패하여 DB에만 저장되었습니다.")
            except Exception as e:
                st.error(f"Google Sheets 저장 중 오류가 발생했습니다: {e}")
                st.error(f"Spreadsheet ID: {os.getenv('THINKING_STYLE_SPREADSHEET_ID')}")
                st.error(f"Worksheet Name: {os.getenv('THINKING_STYLE_WORKSHEET_NAME')}")
                st.success("진단 결과가 DB에만 저장되었습니다.")
            
        except Exception as db_error:
            st.error(f"DB 저장 중 오류가 발생했습니다: {db_error}")
        
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main() 