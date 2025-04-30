import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def connect_to_db():
    """데이터베이스 연결"""
    return mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def create_subjective_llm_tables():
    """주관식 LLM 응답 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # subjective_llm_responses 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjective_llm_responses (
                response_id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT NOT NULL,
                llm_model VARCHAR(50) NOT NULL,
                response_text TEXT NOT NULL,
                reasoning TEXT,
                weight INT DEFAULT 1,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES subjective_questions(question_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        conn.commit()
        print("주관식 LLM 응답 테이블이 생성되었습니다.")
        
    except mysql.connector.Error as err:
        print(f"테이블 생성 중 오류 발생: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_subjective_llm_tables() 