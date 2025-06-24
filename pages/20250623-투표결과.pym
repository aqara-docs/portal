import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from dotenv import load_dotenv
from langchain.chat_models import ChatOllama
from langchain.embeddings import CacheBackedEmbeddings, OllamaEmbeddings
from langchain.vectorstores.faiss import FAISS
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import DirectoryLoader
from langchain.document_loaders import (
    UnstructuredMarkdownLoader,
    UnstructuredPDFLoader,
    UnstructuredFileLoader,
    DirectoryLoader
)
import tempfile
import requests
import json
from openai import OpenAI
import anthropic
from langchain_openai import OpenAI as LangOpenAI
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Vote 결과", page_icon="📊", layout="wide")

# Page header
st.title("🗳️ 투표 결과")

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
        if password:  # 비밀번호가 입력된 경우에만 오류 메시지 표시
            st.error("관리자 권한이 필요합니다")
        st.stop()


# MySQL 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def get_all_questions():
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT q.*, 
                   COUNT(DISTINCT r.response_id) as total_votes,
                   COUNT(DISTINCT r.voter_name) as unique_voters
            FROM vote_questions q
            LEFT JOIN vote_responses r ON q.question_id = r.question_id
            GROUP BY q.question_id
            ORDER BY q.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_question_results(question_id):
    """투표 결과와 투표자 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 전체 투표 수 조회
        cursor.execute("""
            SELECT COUNT(DISTINCT r.response_id) as total_votes
            FROM vote_responses r
            WHERE question_id = %s
        """, (question_id,))
        total_votes = cursor.fetchone()['total_votes']
        
        # 옵션별 결과 조회
        cursor.execute("""
            SELECT 
                o.option_id,
                o.option_text,
                COUNT(DISTINCT r.response_id) as vote_count,
                COALESCE(
                    ROUND(COUNT(DISTINCT r.response_id) * 100.0 / NULLIF(%s, 0), 1),
                    0.0
                ) as vote_percentage,
                GROUP_CONCAT(DISTINCT r.reasoning SEPARATOR '\n') as reasonings
            FROM vote_options o
            LEFT JOIN vote_responses r ON o.option_id = r.option_id
            WHERE o.question_id = %s
            GROUP BY o.option_id, o.option_text
            ORDER BY vote_count DESC
        """, (total_votes, question_id))
        results = cursor.fetchall()
        
        # 투표자 목록 조회 (신뢰도 점수 포함)
        cursor.execute("""
            SELECT DISTINCT 
                r.voter_name,
                COALESCE(uc.credibility_score, 1.0) as credibility_score
            FROM vote_responses r
            LEFT JOIN dot_user_credibility uc 
                ON r.voter_name COLLATE utf8mb4_unicode_ci = uc.user_name COLLATE utf8mb4_unicode_ci
            WHERE r.question_id = %s AND r.voter_name IS NOT NULL
            ORDER BY r.voter_name
        """, (question_id,))
        voters = cursor.fetchall()
        
        return results, voters
    finally:
        cursor.close()
        conn.close()

def ai_vote_llm(question, options, model_name, context=None):
    """LLM 투표 (OpenAI/Anthropic/Ollama 자동 선택)"""
    prompt = f"""
당신은 투표 시스템의 참여자입니다. 아래 질문과 선택지를 신중히 분석하고 가장 적절한 답을 선택하세요.

질문: {question}

선택지:
{options}
"""
    if context:
        prompt += f"\n[참고 문맥]\n{context}\n"
    prompt += """
다음 JSON 형식으로 정확히 답변하세요:
{
  "selection": <선택한 번호>,
  "reasoning": "<선택한 이유에 대한 상세 설명>",
  "reference": "<참고한 문맥 내용 요약 또는 '문맥 없음'>"
}
"""
    if model_name.startswith('gpt'):
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )
        return response.choices[0].message.content
    elif model_name.startswith('claude'):
        client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.1, max_tokens=800)
        response = client.invoke([
            {"role": "user", "content": prompt}
        ])
        return response.content if hasattr(response, 'content') else str(response)
    else:
        # Ollama fallback
        return ask_llm(question, options, model_name, context or "")

def get_available_models():
    """사용 가능한 LLM 모델 목록 반환 (OpenAI/Anthropic/Ollama)"""
    models = []
    has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
    if has_anthropic_key:
        models.extend([
            'claude-3-7-sonnet-latest',
            'claude-3-5-sonnet-latest',
            'claude-3-5-haiku-latest',
        ])
    has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
    if has_openai_key:
        models.extend(['gpt-4o', 'gpt-4o-mini'])
    # Ollama 기본 모델
    models.extend([
        "deepseek-r1:70b",
        "deepseek-r1:32b",
        "deepseek-r1:14b",
        "phi4:latest",
        "gemma2:latest",
        "llama3.1:latest",
        "mistral:latest",
        "llama2:latest",
        "llama3.2:latest"
    ])
    # gpt-4o-mini가 있으면 디폴트, 없으면 첫 번째
    default_model = 'gpt-4o-mini' if 'gpt-4o-mini' in models else (models[0] if models else None)
    return models, default_model

def get_llm_vote(question_id, model_name):
    """LLM의 투표 결과와 이유 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    result = None
    
    try:
        cursor.execute("""
            SELECT o.option_text, lr.reasoning
            FROM vote_llm_responses lr
            JOIN vote_options o ON lr.option_id = o.option_id
            WHERE lr.question_id = %s AND lr.llm_model = %s
            ORDER BY lr.voted_at DESC
            LIMIT 1
        """, (question_id, model_name))
        
        # 결과를 완전히 읽어옴
        result = cursor.fetchone()
        
    except mysql.connector.Error as err:
        st.error(f"LLM 투표 결과 조회 중 오류 발생: {err}")
    finally:
        # 커서와 연결 정리
        cursor.close()
        conn.close()
    
    return result

def load_single_file(file_path):
    """단일 파일 로드"""
    try:
        if file_path.endswith('.md'):
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_path.endswith('.pdf'):
            loader = UnstructuredPDFLoader(file_path)
        else:
            loader = UnstructuredFileLoader(file_path)
        
        return loader.load()
    except Exception as e:
        st.error(f"파일 로드 중 오류 발생: {e}")
        return []

def load_files(files):
    """업로드된 파일들을 로드"""
    documents = []
    for file in files:
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp_file:
                tmp_file.write(file.getvalue())
                tmp_file.flush()
                
                # 파일 로드
                docs = load_single_file(tmp_file.name)
                documents.extend(docs)
                
                # 임시 파일 삭제
                os.unlink(tmp_file.name)
        except Exception as e:
            st.error(f"'{file.name}' 파일 처리 중 오류 발생: {e}")
    
    return documents

def create_vectorstore(documents):
    """벡터 스토어 생성"""
    try:
        # 텍스트 분할
        text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        # 문서 분할
        splits = text_splitter.split_documents(documents)
        
        # 임베딩 생성 (기본 모델 사용)
        embeddings = OllamaEmbeddings(
            model="llama2"
        )
        
        # ChromaDB를 사용한 벡터 스토어 생성
        from langchain.vectorstores import Chroma
        
        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=temp_dir  # 임시 디렉토리 지정
            )
            
            return vectorstore
            
    except Exception as e:
        st.error(f"벡터 스토어 생성 중 오류 발생: {e}")
        if "404" in str(e):
            st.info("필요한 모델을 설치하려면 터미널에서 다음 명령어를 실행하세요:\n```bash\nollama pull llama2\n```")
        return None

def get_relevant_context(vectorstore, question, options):
    """질문과 관련된 문맥 검색"""
    if not vectorstore:
        return ""
        
    # 질문과 모든 선택지를 결합하여 검색
    search_text = f"{question}\n{options}"
    
    # 관련 문서 검색
    docs = vectorstore.similarity_search(search_text, k=3)
    
    # 문맥 결합
    context = "\n\n".join([doc.page_content for doc in docs])
    return context

def ask_llm(question, options, model_name, context=""):
    """LLM에게 투표 요청하고 응답 받기"""
    try:
        # Ollama API 직접 호출
        # 프롬프트 구성
        if context:
            prompt = f"""
            당신은 투표 시스템의 참여자입니다. 
            아래 제공된 문맥, 질문, 선택지를 신중히 분석하고 가장 적절한 답을 선택해주세요.
            
            참고할 문맥:
            {context}
            
            질문: {question}
            
            선택지:
            {options}
            """
        else:
            prompt = f"""
            당신은 투표 시스템의 참여자입니다. 
            아래 질문과 선택지를 신중히 분석하고 가장 적절한 답을 선택해주세요.
            
            질문: {question}
            
            선택지:
            {options}
            """
        
        prompt += """
        다음 JSON 형식으로 정확히 답변해주세요:
        {
            "selection": <선택한 번호>,
            "reasoning": "<선택한 이유에 대한 상세 설명>",
            "reference": "<참고한 문맥 내용 요약 또는 '문맥 없음'>"
        }
        """
        
        # Ollama API 호출
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "temperature": 0.1
            }
        )
        
        response.raise_for_status()
        result = response.json()
        
        return result.get('response', '')
        
    except Exception as e:
        st.error(f"LLM 호출 중 오류 발생: {str(e)}")
        return None

def parse_llm_response(response_text):
    """LLM 응답을 파싱하여 선택 번호와 이유 추출"""
    try:
        # JSON 형식 찾기
        import re
        import json
        
        # JSON 형식 찾기 시도
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                response_json = json.loads(json_match.group())
                selection = int(response_json['selection'])
                reasoning = response_json['reasoning']
                return selection, reasoning
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        # JSON 파싱 실패시 기존 방식으로 시도
        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        selection = None
        reasoning = []
        parsing_reason = False
        
        for line in lines:
            if '선택' in line.lower() or 'selection' in line.lower():
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers:
                    selection = numbers[0]
                    continue
            
            if '이유' in line.lower() or 'reasoning' in line.lower() or parsing_reason:
                parsing_reason = True
                current_reason = line.replace('이유:', '').replace('reasoning:', '').strip()
                if current_reason:
                    reasoning.append(current_reason)
        
        if selection is None:
            raise ValueError("선택 번호를 찾을 수 없습니다.")
        
        reasoning_text = ' '.join(reasoning) if reasoning else "이유가 명시되지 않았습니다."
        return selection, reasoning_text
        
    except Exception as e:
        raise ValueError(f"응답 파싱 실패: {str(e)}\n원본 응답: {response_text}")

def save_llm_vote(question_id, option_id, model_name, reasoning, weight):
    """LLM의 투표 결과를 DB에 저장 (중복 방지)"""
    conn = connect_to_db()
    cursor = conn.cursor()
    try:
        # 기존 LLM 투표 삭제
        cursor.execute(
            "DELETE FROM vote_llm_responses WHERE question_id = %s AND llm_model = %s",
            (question_id, model_name)
        )
        # 새 투표 저장
        cursor.execute("""
            INSERT INTO vote_llm_responses 
            (question_id, option_id, llm_model, reasoning, weight)
            VALUES (%s, %s, %s, %s, %s)
        """, (question_id, option_id, model_name, reasoning, weight))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_combined_results(question_id, apply_weights=False):
    """일반 투표와 LLM 투표 결과 모두 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if apply_weights:
            # 신뢰도 가중치를 적용한 쿼리
            cursor.execute("""
                WITH vote_data AS (
                    SELECT 
                        r.option_id,
                        COUNT(DISTINCT r.response_id) as vote_count,
                        SUM(COALESCE(uc.credibility_score, 1.0)) as total_credibility
                    FROM vote_responses r
                    LEFT JOIN dot_user_credibility uc 
                        ON r.voter_name COLLATE utf8mb4_unicode_ci = uc.user_name COLLATE utf8mb4_unicode_ci
                    WHERE r.question_id = %s
                    GROUP BY r.option_id
                ),
                llm_data AS (
                    SELECT 
                        option_id,
                        SUM(weight) as total_weight
                    FROM vote_llm_responses
                    WHERE question_id = %s
                    GROUP BY option_id
                )
                SELECT 
                    o.option_text,
                    COALESCE(v.vote_count, 0) as raw_human_votes,
                    CAST(COALESCE(v.total_credibility, 0) AS SIGNED) as human_votes,
                    CAST(COALESCE(l.total_weight, 0) AS SIGNED) as weighted_llm_votes,
                    CAST(
                        COALESCE(v.total_credibility, 0) + COALESCE(l.total_weight, 0)
                        AS SIGNED
                    ) as total_votes
                FROM vote_options o
                LEFT JOIN vote_data v ON o.option_id = v.option_id
                LEFT JOIN llm_data l ON o.option_id = l.option_id
                WHERE o.question_id = %s
                ORDER BY total_votes DESC
            """, (question_id, question_id, question_id))
        else:
            cursor.execute("""
                WITH vote_data AS (
                    SELECT 
                        option_id,
                        COUNT(DISTINCT response_id) as vote_count
                    FROM vote_responses
                    WHERE question_id = %s
                    GROUP BY option_id
                ),
                llm_data AS (
                    SELECT 
                        option_id,
                        SUM(weight) as total_weight
                    FROM vote_llm_responses
                    WHERE question_id = %s
                    GROUP BY option_id
                )
                SELECT 
                    o.option_text,
                    COALESCE(v.vote_count, 0) as human_votes,
                    CAST(COALESCE(l.total_weight, 0) AS SIGNED) as weighted_llm_votes,
                    CAST(
                        COALESCE(v.vote_count, 0) + COALESCE(l.total_weight, 0)
                        AS SIGNED
                    ) as total_votes
                FROM vote_options o
                LEFT JOIN vote_data v ON o.option_id = v.option_id
                LEFT JOIN llm_data l ON o.option_id = l.option_id
                WHERE o.question_id = %s
                ORDER BY total_votes DESC
            """, (question_id, question_id, question_id))
        
        results = cursor.fetchall()
        return results
    finally:
        cursor.close()
        conn.close()

def get_question_options(question_id):
    """질문에 대한 선택지 목록 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT option_id, option_text
            FROM vote_options
            WHERE question_id = %s
            ORDER BY option_id
        """, (question_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_vote_results():
    """투표 결과 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                v.option_id,
                o.option_text,
                COUNT(v.vote_id) as vote_count,
                COALESCE(
                    (COUNT(v.vote_id) * 100.0 / 
                    NULLIF((SELECT COUNT(*) FROM votes), 0)), 
                    0
                ) as vote_percentage
            FROM vote_options o
            LEFT JOIN votes v ON o.option_id = v.option_id
            GROUP BY o.option_id, o.option_text
            ORDER BY vote_count DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_subjective_question_results(question_id):
    """주관식 질문의 결과와 응답자 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 전체 응답 수 조회
        cursor.execute("""
            SELECT COUNT(DISTINCT r.response_id) as total_responses
            FROM subjective_responses r
            WHERE question_id = %s
        """, (question_id,))
        total_responses = cursor.fetchone()['total_responses']
        
        # 응답별 결과 조회 (동일 응답 그룹화)
        cursor.execute("""
            SELECT 
                response_text,
                COUNT(*) as response_count,
                COALESCE(
                    ROUND(COUNT(*) * 100.0 / NULLIF(%s, 0), 1),
                    0.0
                ) as response_percentage,
                GROUP_CONCAT(DISTINCT voter_name ORDER BY voter_name SEPARATOR ', ') as voters
            FROM subjective_responses
            WHERE question_id = %s
            GROUP BY response_text
            ORDER BY response_count DESC, response_text
        """, (total_responses, question_id))
        results = cursor.fetchall()
        
        # 응답자 목록 조회 (신뢰도 점수 포함)
        cursor.execute("""
            SELECT DISTINCT 
                r.voter_name,
                COALESCE(uc.credibility_score, 1.0) as credibility_score
            FROM subjective_responses r
            LEFT JOIN dot_user_credibility uc 
                ON r.voter_name COLLATE utf8mb4_unicode_ci = uc.user_name COLLATE utf8mb4_unicode_ci
            WHERE r.question_id = %s AND r.voter_name IS NOT NULL AND r.voter_name != '익명'
            ORDER BY r.voter_name
        """, (question_id,))
        voters = cursor.fetchall()
        
        return results, voters, total_responses
    finally:
        cursor.close()
        conn.close()

def get_subjective_llm_vote(question_id, model_name):
    """LLM의 주관식 답변 결과와 이유 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    result = None
    try:
        # Ensure parameters are scalar, not list
        if isinstance(question_id, list):
            question_id = question_id[0]
        if isinstance(model_name, list):
            model_name = model_name[0]
        cursor.execute("""
            SELECT response_text, reasoning
            FROM subjective_llm_responses
            WHERE question_id = %s AND llm_model = %s
            ORDER BY voted_at DESC
            LIMIT 1
        """, (question_id, model_name))
        result = cursor.fetchone()
    except mysql.connector.Error as err:
        st.error(f"LLM 답변 결과 조회 중 오류 발생: {err}")
    finally:
        cursor.close()
        conn.close()
    return result

def save_subjective_llm_response(question_id, model_name, response_text, reasoning, weight):
    """LLM의 주관식 답변을 DB에 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO subjective_llm_responses 
            (question_id, llm_model, response_text, reasoning, weight)
            VALUES (%s, %s, %s, %s, %s)
        """, (question_id, model_name, response_text, reasoning, weight))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_combined_subjective_results(question_id, apply_weights=False):
    """일반 답변과 LLM 답변 결과 모두 가져오기"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if apply_weights:
            # 신뢰도 가중치를 적용한 쿼리
            cursor.execute("""
                WITH response_data AS (
                    SELECT 
                        response_text,
                        COUNT(*) as response_count,
                        SUM(COALESCE(uc.credibility_score, 1.0)) as total_credibility
                    FROM subjective_responses r
                    LEFT JOIN dot_user_credibility uc 
                        ON r.voter_name COLLATE utf8mb4_unicode_ci = uc.user_name COLLATE utf8mb4_unicode_ci
                    WHERE r.question_id = %s
                    GROUP BY response_text
                ),
                llm_data AS (
                    SELECT 
                        response_text,
                        SUM(weight) as total_weight
                    FROM subjective_llm_responses
                    WHERE question_id = %s
                    GROUP BY response_text
                )
                SELECT 
                    r.response_text,
                    r.response_count as raw_human_responses,
                    CAST(COALESCE(r.total_credibility, 0) AS SIGNED) as human_responses,
                    CAST(COALESCE(l.total_weight, 0) AS SIGNED) as weighted_llm_responses,
                    CAST(
                        COALESCE(r.total_credibility, 0) + COALESCE(l.total_weight, 0)
                        AS SIGNED
                    ) as total_responses
                FROM response_data r
                LEFT JOIN llm_data l ON r.response_text = l.response_text
                UNION
                SELECT 
                    l.response_text,
                    0 as raw_human_responses,
                    0 as human_responses,
                    CAST(l.total_weight AS SIGNED) as weighted_llm_responses,
                    CAST(l.total_weight AS SIGNED) as total_responses
                FROM llm_data l
                LEFT JOIN response_data r ON l.response_text = r.response_text
                WHERE r.response_text IS NULL
                ORDER BY total_responses DESC
            """, (question_id, question_id))
        else:
            cursor.execute("""
                WITH response_data AS (
                    SELECT 
                        response_text,
                        COUNT(*) as response_count
                    FROM subjective_responses
                    WHERE question_id = %s
                    GROUP BY response_text
                ),
                llm_data AS (
                    SELECT 
                        response_text,
                        SUM(weight) as total_weight
                    FROM subjective_llm_responses
                    WHERE question_id = %s
                    GROUP BY response_text
                )
                SELECT 
                    r.response_text,
                    COALESCE(r.response_count, 0) as human_responses,
                    CAST(COALESCE(l.total_weight, 0) AS SIGNED) as weighted_llm_responses,
                    CAST(
                        COALESCE(r.response_count, 0) + COALESCE(l.total_weight, 0)
                        AS SIGNED
                    ) as total_responses
                FROM response_data r
                LEFT JOIN llm_data l ON r.response_text = l.response_text
                UNION
                SELECT 
                    l.response_text,
                    0 as human_responses,
                    CAST(l.total_weight AS SIGNED) as weighted_llm_responses,
                    CAST(l.total_weight AS SIGNED) as total_responses
                FROM llm_data l
                LEFT JOIN response_data r ON l.response_text = r.response_text
                WHERE r.response_text IS NULL
                ORDER BY total_responses DESC
            """, (question_id, question_id))
        
        results = cursor.fetchall()
        return results
    finally:
        cursor.close()
        conn.close()

def main():
    # 모든 투표 문제 가져오기
    questions = get_all_questions()
    
    if not questions:
        st.info("등록된 투표가 없습니다.")
        return
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📊 객관식 투표", "✏️ 주관식 투표"])
    
    with tab1:
        # 문제 선택
        selected_question = st.selectbox(
            "결과를 볼 투표를 선택하세요",
            questions,
            format_func=lambda x: f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d %H:%M')})"
        )
        
        if selected_question:
            st.write("---")
            st.write(f"## {selected_question['title']}")
            st.write(selected_question['description'])
            
            # 투표 상태 표시
            status_color = "🟢" if selected_question['status'] == 'active' else "🔴"
            st.write(f"상태: {status_color} {selected_question['status'].upper()}")
            
            # 기본 통계
            st.write(f"총 투표 수: {selected_question['total_votes']}")
            st.write(f"참여자 수: {selected_question['unique_voters']}")
            
            # 결과 가져오기
            results, voters = get_question_results(selected_question['question_id'])
            
            if results:
                # Create DataFrame with correct column names
                df_results = pd.DataFrame(results).astype({
                    'vote_count': 'int64',
                    'vote_percentage': 'float64'
                })
                
                # 차트 그리기
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("### 투표 결과 차트")
                    fig = px.bar(
                        df_results,
                        x='option_text',
                        y='vote_count',
                        text='vote_count',
                        title="선택지별 투표 수",
                        labels={'option_text': '선택지', 'vote_count': '투표 수'}
                    )
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.write("### 상세 결과")
                    for result in results:
                        st.write(f"#### {result['option_text']}")
                        
                        # 안전한 값 추출
                        vote_count = result.get('vote_count', 0) or 0
                        vote_percentage = result.get('vote_percentage', 0.0) or 0.0
                        
                        # 결과 표시
                        st.write(f"투표 수: {vote_count} ({vote_percentage:.1f}%)")
                        
                        # 선택 이유 표시
                        if result.get('reasonings'):
                            with st.expander("💬 선택 이유 보기"):
                                reasonings = result['reasonings'].split('\n')
                                for reasoning in reasonings:
                                    if reasoning.strip():
                                        st.markdown(f"- {reasoning}")
                
                # 투표자 목록 (익명 제외)
                if voters:
                    with st.expander("투표자 목록 보기 (익명 제외)"):
                        for voter in voters:
                            st.write(f"- {voter['voter_name']} (신뢰도: {voter['credibility_score']:.2f})")
                
                # 관리자 기능
                if selected_question['status'] == 'active':
                    if st.button("투표 종료하기"):
                        conn = connect_to_db()
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                UPDATE vote_questions
                                SET status = 'closed'
                                WHERE question_id = %s
                            """, (selected_question['question_id'],))
                            conn.commit()
                            st.success("투표가 종료되었습니다.")
                            st.rerun()
                        except mysql.connector.Error as err:
                            st.error(f"투표 종료 중 오류가 발생했습니다: {err}")
                        finally:
                            cursor.close()
                            conn.close()

            # LLM 투표 섹션
            st.write("---")
            st.write("## 🤖 LLM 투표")
            
            models, default_model = get_available_models()
            if 'selected_model' not in st.session_state:
                st.session_state.selected_model = default_model
            selected_model = st.selectbox(
                "LLM 모델 선택",
                models,
                index=models.index(st.session_state.selected_model) if st.session_state.selected_model in models else 0
            )
            st.session_state.selected_model = selected_model
            
            # LLM 투표 가중치 설정
            llm_weight = st.slider(
                "LLM 투표 가중치",
                min_value=1,
                max_value=10,
                value=1,
                help="LLM의 투표가 몇 명의 투표와 동일한 가중치를 가질지 설정합니다."
            )
            
            # RAG 사용 여부 선택
            use_rag = st.checkbox("문서 참조 사용 (RAG)", 
                                help="선택한 문서를 참조하여 답변합니다.")
            
            if use_rag:
                # 파일 입력 방식 선택
                input_method = st.radio(
                    "참조 문서 입력 방식",
                    ["파일 업로드", "디렉토리 경로"]
                )
                
                context = ""
                if input_method == "파일 업로드":
                    uploaded_files = st.file_uploader(
                        "참조할 파일 선택 (여러 파일 가능)",
                        accept_multiple_files=True,
                        type=['txt', 'md', 'pdf']
                    )
                    
                    if uploaded_files:
                        with st.spinner("파일 처리 중..."):
                            documents = load_files(uploaded_files)
                            if documents:
                                vectorstore = create_vectorstore(documents)
                                
                else:  # 디렉토리 경로
                    doc_directory = st.text_input(
                        "참조할 문서 디렉토리 경로",
                        help="마크다운/텍스트/PDF 파일이 있는 디렉토리"
                    )
                    
                    if doc_directory and os.path.exists(doc_directory):
                        with st.spinner("디렉토리 처리 중..."):
                            documents = load_documents(doc_directory)
                            if documents:
                                vectorstore = create_vectorstore(documents)
            
            # LLM 투표 버튼
            if st.button("LLM 투표 실행"):
                options = get_question_options(selected_question['question_id'])
                options_text = "\n".join([f"{i+1}. {opt['option_text']}" 
                                        for i, opt in enumerate(options)])
                
                context = ""
                if use_rag and 'vectorstore' in locals():
                    with st.spinner("관련 문맥 검색 중..."):
                        context = get_relevant_context(
                            vectorstore,
                            selected_question['description'],
                            options_text
                        )
                        if context:
                            st.write("### 참조한 문맥:")
                            st.write(context)
                
                # LLM에게 물어보기
                with st.spinner("LLM 응답 대기 중..."):
                    llm_response = ai_vote_llm(
                        selected_question['description'],
                        options_text,
                        selected_model,
                        context if use_rag else ""
                    )
                
                # 응답 파싱 및 저장
                try:
                    selection, reasoning = parse_llm_response(llm_response)
                    
                    if selection < 1 or selection > len(options):
                        st.error(f"LLM이 잘못된 선택지 번호를 반환했습니다: {selection}")
                    else:
                        save_llm_vote(
                            selected_question['question_id'],
                            options[selection - 1]['option_id'],
                            selected_model,
                            reasoning,
                            llm_weight
                        )
                        st.session_state['last_llm_vote'] = {
                            'selection': selection,
                            'reasoning': reasoning,
                            'option_text': options[selection - 1]['option_text'],
                            'model': selected_model,
                            'weight': llm_weight
                        }
                        st.success(f"LLM 투표가 가중치 {llm_weight}로 저장되었습니다!")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"LLM 응답 처리 중 오류 발생: {e}")
            
            # LLM 투표 결과 표시
            if 'last_llm_vote' in st.session_state:
                llm_vote = st.session_state['last_llm_vote']
                st.write("### 🤖 LLM 투표 결과")
                st.write(f"**선택한 항목:** {llm_vote['option_text']}")
                st.write("**선택 이유:**")
                st.write(llm_vote['reasoning'])
            
            # 결과 비교 표시
            st.write("---")
            st.write("## 📊 통합 결과 비교")
            
            # 신뢰도 가중치 적용 여부 선택
            apply_weights = st.checkbox("참여자 신뢰도 가중치 적용", 
                                      help="체크하면 00_12_신뢰도_가중치_부여.py에서 설정된 신뢰도 점수가 투표에 반영됩니다.")
            
            results = get_combined_results(selected_question['question_id'], apply_weights)
            if results:
                # Create DataFrame with correct column names
                df_results = pd.DataFrame(results)
                
                # Convert numeric columns to appropriate types
                numeric_columns = ['human_votes', 'weighted_llm_votes', 'total_votes']
                if apply_weights:
                    numeric_columns.append('raw_human_votes')
                
                for col in numeric_columns:
                    if col in df_results.columns:
                        df_results[col] = pd.to_numeric(df_results[col], errors='coerce').fillna(0).astype('int64')
                
                # 인간 투표 차트
                fig1 = px.bar(
                    df_results,
                    x='option_text',
                    y='raw_human_votes' if apply_weights else 'human_votes',
                    title=f"인간 투표 결과 {'(가중치 적용 전)' if apply_weights else ''}",
                    labels={'option_text': '선택지', 
                           'raw_human_votes': '투표 수', 
                           'human_votes': '투표 수'}
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                if apply_weights:
                    # 가중치가 적용된 인간 투표 차트
                    fig_weighted = px.bar(
                        df_results,
                        x='option_text',
                        y='human_votes',
                        title="인간 투표 결과 (가중치 적용 후)",
                        labels={'option_text': '선택지', 'human_votes': '가중치 적용된 투표 수'}
                    )
                    st.plotly_chart(fig_weighted, use_container_width=True)
                
                # 통합 결과 차트
                df_melted = pd.melt(
                    df_results,
                    id_vars=['option_text'],
                    value_vars=['human_votes', 'weighted_llm_votes']
                )
                
                fig2 = px.bar(
                    df_melted,
                    x='option_text',
                    y='value',
                    color='variable',
                    title=f"통합 투표 결과 (인간{' (가중치 적용)' if apply_weights else ''} + LLM)",
                    labels={
                        'option_text': '선택지',
                        'value': '투표 수',
                        'variable': '투표자 유형'
                    },
                    barmode='stack'
                )
                
                # 범례 이름 변경
                fig2.update_traces(
                    name=f"인간 투표{' (가중치 적용)' if apply_weights else ''}",
                    selector=dict(name="human_votes")
                )
                fig2.update_traces(
                    name="LLM 투표 (가중치 적용)",
                    selector=dict(name="weighted_llm_votes")
                )
                
                st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.write("## 주관식 투표 결과")
        
        # 주관식 질문 목록 가져오기
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT q.*, 
                       COUNT(DISTINCT r.response_id) as total_responses,
                       COUNT(DISTINCT r.voter_name) as unique_voters
                FROM subjective_questions q
                LEFT JOIN subjective_responses r ON q.question_id = r.question_id
                GROUP BY q.question_id
                ORDER BY q.created_at DESC
            """)
            subjective_questions = cursor.fetchall()
            
            if not subjective_questions:
                st.info("등록된 주관식 질문이 없습니다.")
                return
            
            # 질문 선택
            selected_question = st.selectbox(
                "결과를 볼 질문을 선택하세요",
                subjective_questions,
                format_func=lambda x: f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d %H:%M')})",
                key="subjective_question_selector"
            )
            
            if selected_question:
                st.write("---")
                st.write(f"## {selected_question['title']}")
                st.write(selected_question['description'])
                
                # 투표 상태 표시
                status_color = "🟢" if selected_question['status'] == 'active' else "🔴"
                st.write(f"상태: {status_color} {selected_question['status'].upper()}")
                
                # 기본 통계
                st.write(f"총 응답 수: {selected_question['total_responses']}")
                st.write(f"참여자 수: {selected_question['unique_voters']}")
                
                # 결과 가져오기
                results, voters, total_responses = get_subjective_question_results(selected_question['question_id'])
                
                if results:
                    # 결과를 DataFrame으로 변환
                    df_results = pd.DataFrame(results)
                    
                    # 차트 그리기
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write("### 응답 분포 차트")
                        # 상위 10개 응답만 표시
                        top_responses = df_results.head(10)
                        fig = px.bar(
                            top_responses,
                            x='response_text',
                            y='response_count',
                            text='response_count',
                            title="응답별 빈도 (상위 10개)",
                            labels={'response_text': '응답', 'response_count': '응답 수'}
                        )
                        fig.update_traces(textposition='outside')
                        fig.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.write("### 상세 결과")
                        for result in results:
                            with st.expander(f"📝 {result['response_text']} ({result['response_count']}회)"):
                                st.write(f"응답 비율: {result['response_percentage']}%")
                                if result['voters'] and result['voters'] != '익명':
                                    st.write("응답자:")
                                    voters_list = result['voters'].split(', ')
                                    for voter in voters_list:
                                        if voter != '익명':
                                            st.write(f"- {voter}")
                    
                    # LLM 답변 섹션
                    st.write("---")
                    st.write("## 🤖 LLM 답변")
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        selected_model = st.selectbox(
                            "LLM 모델 선택",
                            get_available_models(),
                            key="subjective_llm_model"
                        )
                        
                        # LLM 답변 가중치 설정
                        llm_weight = st.slider(
                            "LLM 답변 가중치",
                            min_value=1,
                            max_value=10,
                            value=1,
                            help="LLM의 답변이 몇 명의 답변과 동일한 가중치를 가질지 설정합니다.",
                            key="subjective_llm_weight"
                        )
                        
                        # RAG 사용 여부 선택
                        use_rag = st.checkbox("문서 참조 사용 (RAG)", 
                                            help="선택한 문서를 참조하여 답변합니다.",
                                            key="subjective_use_rag")
                        
                        if use_rag:
                            # 파일 입력 방식 선택
                            input_method = st.radio(
                                "참조 문서 입력 방식",
                                ["파일 업로드", "디렉토리 경로"],
                                key="subjective_input_method"
                            )
                            
                            context = ""
                            if input_method == "파일 업로드":
                                uploaded_files = st.file_uploader(
                                    "참조할 파일 선택 (여러 파일 가능)",
                                    accept_multiple_files=True,
                                    type=['txt', 'md', 'pdf'],
                                    key="subjective_file_uploader"
                                )
                                
                                if uploaded_files:
                                    with st.spinner("파일 처리 중..."):
                                        documents = load_files(uploaded_files)
                                        if documents:
                                            vectorstore = create_vectorstore(documents)
                                            
                            else:  # 디렉토리 경로
                                doc_directory = st.text_input(
                                    "참조할 문서 디렉토리 경로",
                                    help="마크다운/텍스트/PDF 파일이 있는 디렉토리",
                                    key="subjective_doc_directory"
                                )
                                
                                if doc_directory and os.path.exists(doc_directory):
                                    with st.spinner("디렉토리 처리 중..."):
                                        documents = load_documents(doc_directory)
                                        if documents:
                                            vectorstore = create_vectorstore(documents)
                        
                        # LLM 답변 버튼
                        if st.button("LLM 답변 생성", key="subjective_llm_button"):
                            context = ""
                            if use_rag and 'vectorstore' in locals():
                                with st.spinner("관련 문맥 검색 중..."):
                                    context = get_relevant_context(
                                        vectorstore,
                                        selected_question['description'],
                                        ""
                                    )
                                    if context:
                                        st.write("### 참조한 문맥:")
                                        st.write(context)
                            
                            # LLM에게 물어보기
                            with st.spinner("LLM 응답 대기 중..."):
                                llm_response = ai_vote_llm(
                                    selected_question['description'],
                                    "",
                                    selected_model,
                                    context if use_rag else ""
                                )
                            
                            # 응답 파싱 및 저장
                            try:
                                response_text = llm_response.strip()
                                save_subjective_llm_response(
                                    selected_question['question_id'],
                                    selected_model,
                                    response_text,
                                    context if use_rag else "",
                                    llm_weight
                                )
                                st.success(f"LLM 답변이 가중치 {llm_weight}로 저장되었습니다!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"LLM 응답 처리 중 오류 발생: {e}")
                    
                    with col2:
                        # 기존 LLM 답변 결과 표시
                        llm_response = get_subjective_llm_vote(selected_question['question_id'], selected_model)
                        if llm_response:
                            st.write("### 🤖 LLM 답변 결과")
                            st.write(f"**답변:** {llm_response['response_text']}")
                            if llm_response['reasoning']:
                                st.write("**참조한 문맥:**")
                                st.write(llm_response['reasoning'])
                    
                    # 결과 비교 표시
                    st.write("---")
                    st.write("## 📊 통합 결과 비교")
                    
                    # 신뢰도 가중치 적용 여부 선택
                    apply_weights = st.checkbox(
                        "참여자 신뢰도 가중치 적용", 
                        help="체크하면 00_12_신뢰도_가중치_부여.py에서 설정된 신뢰도 점수가 답변에 반영됩니다.",
                        key="subjective_apply_weights"
                    )
                    
                    combined_results = get_combined_subjective_results(selected_question['question_id'], apply_weights)
                    if combined_results:
                        # Create DataFrame with correct column names
                        df_combined = pd.DataFrame(combined_results)
                        
                        # Convert numeric columns to appropriate types
                        numeric_columns = ['human_responses', 'weighted_llm_responses', 'total_responses']
                        if apply_weights:
                            numeric_columns.append('raw_human_responses')
                        
                        for col in numeric_columns:
                            if col in df_combined.columns:
                                df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0).astype('int64')
                        
                        # 인간 답변 차트
                        fig1 = px.bar(
                            df_combined,
                            x='response_text',
                            y='raw_human_responses' if apply_weights else 'human_responses',
                            title=f"인간 답변 결과 {'(가중치 적용 전)' if apply_weights else ''}",
                            labels={'response_text': '답변', 
                                   'raw_human_responses': '답변 수', 
                                   'human_responses': '답변 수'}
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                        
                        if apply_weights:
                            # 가중치가 적용된 인간 답변 차트
                            fig_weighted = px.bar(
                                df_combined,
                                x='response_text',
                                y='human_responses',
                                title="인간 답변 결과 (가중치 적용 후)",
                                labels={'response_text': '답변', 'human_responses': '가중치 적용된 답변 수'}
                            )
                            st.plotly_chart(fig_weighted, use_container_width=True)
                        
                        # 통합 결과 차트
                        df_melted = pd.melt(
                            df_combined,
                            id_vars=['response_text'],
                            value_vars=['human_responses', 'weighted_llm_responses']
                        )
                        
                        fig2 = px.bar(
                            df_melted,
                            x='response_text',
                            y='value',
                            color='variable',
                            title=f"통합 답변 결과 (인간{' (가중치 적용)' if apply_weights else ''} + LLM)",
                            labels={
                                'response_text': '답변',
                                'value': '답변 수',
                                'variable': '답변자 유형'
                            },
                            barmode='stack'
                        )
                        
                        # 범례 이름 변경
                        fig2.update_traces(
                            name=f"인간 답변{' (가중치 적용)' if apply_weights else ''}",
                            selector=dict(name="human_responses")
                        )
                        fig2.update_traces(
                            name="LLM 답변 (가중치 적용)",
                            selector=dict(name="weighted_llm_responses")
                        )
                        
                        st.plotly_chart(fig2, use_container_width=True)

        except mysql.connector.Error as err:
            st.error(f"데이터 조회 중 오류가 발생했습니다: {err}")
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    os.environ['PYTHONPATH'] = os.getcwd()
    main() 