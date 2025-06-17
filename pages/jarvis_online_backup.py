import streamlit as st
import os
import base64
import pandas as pd
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain_anthropic import ChatAnthropic
import anthropic
import mysql.connector
import json
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import io
import re
from sqlalchemy import create_engine
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.tools import DuckDuckGoSearchResults, WikipediaQueryRun, Tool
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.utilities import WikipediaAPIWrapper
import uuid
import openai
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests
import time
from sentence_transformers import SentenceTransformer

# 전역 변수 및 초기 설정
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-4-turbo-preview"

if 'selected_ai_api' not in st.session_state:
    st.session_state.selected_ai_api = "openai"

selected_speaker = "USER"

def get_mysql_connection():
    """MySQL 연결을 반환하는 헬퍼 함수"""
    return mysql.connector.connect(
        host=os.getenv('SQL_HOST'),
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4'
    )

def create_jarvis_rag_tables():
    """Create tables for JARVIS RAG functionality"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # 1. RAG 데이터 소스 정보 테이블
        rag_sources_table = """
        CREATE TABLE IF NOT EXISTS jarvis_rag_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            conversation_id VARCHAR(255) NOT NULL COMMENT '대화 세션 ID',
            source_type ENUM('mysql', 'website', 'files', 'chat_history', 'audio') NOT NULL COMMENT 'RAG 소스 타입',
            source_name VARCHAR(255) NOT NULL COMMENT '소스 이름',
            source_description TEXT COMMENT '소스 설명',
            source_details JSON COMMENT '소스 상세 정보 (테이블명, URL, 파일명 등)',
            data_size INT COMMENT '데이터 크기 (행수, 페이지수, 파일크기 등)',
            content_preview TEXT COMMENT '데이터 미리보기',
            embedding_model VARCHAR(100) COMMENT '임베딩 모델명',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_conversation_id (conversation_id),
            INDEX idx_source_type (source_type),
            INDEX idx_source_name (source_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='JARVIS RAG 데이터 소스 정보';
        """
        cursor.execute(rag_sources_table)
        
        # 2. RAG 임베딩 저장 테이블
        embeddings_table = """
        CREATE TABLE IF NOT EXISTS jarvis_rag_embeddings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_id INT NOT NULL COMMENT 'RAG 소스 ID',
            chunk_index INT NOT NULL COMMENT '청크 인덱스',
            chunk_text TEXT NOT NULL COMMENT '청크 텍스트',
            embedding JSON NOT NULL COMMENT '임베딩 벡터',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES jarvis_rag_sources(id) ON DELETE CASCADE,
            INDEX idx_source_id (source_id),
            INDEX idx_chunk_index (chunk_index)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='JARVIS RAG 임베딩 데이터';
        """
        cursor.execute(embeddings_table)
        
        connection.commit()
        cursor.close()
        connection.close()
        st.success("✅ JARVIS RAG 테이블 생성 완료!")
        
    except Exception as e:
        st.error(f"❌ JARVIS RAG 테이블 생성 중 오류 발생: {str(e)}")

def get_table_relationships():
    """테이블 간의 관계 정보 조회"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 외래 키 관계 조회
        sql = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE 
            REFERENCED_TABLE_SCHEMA = %s 
            AND REFERENCED_TABLE_NAME IS NOT NULL
        """
        
        cursor.execute(sql, (os.getenv('SQL_DATABASE_NEWBIZ'),))
        relationships = cursor.fetchall()
        
        # 관계 정보 구조화
        table_relations = {}
        for rel in relationships:
            if rel['TABLE_NAME'] not in table_relations:
                table_relations[rel['TABLE_NAME']] = []
            table_relations[rel['TABLE_NAME']].append({
                'from_column': rel['COLUMN_NAME'],
                'to_table': rel['REFERENCED_TABLE_NAME'],
                'to_column': rel['REFERENCED_COLUMN_NAME']
            })
        
        cursor.close()
        connection.close()
        return table_relations
        
    except Exception as e:
        st.error(f"테이블 관계 조회 중 오류: {str(e)}")
        return {}

def get_table_importance():
    """테이블 중요도 정보 반환"""
    return {
        'jarvis_interactions': 1.5,  # 대화 기록 (높은 중요도)
        'jarvis_rag_sources': 1.4,   # RAG 소스
        'jarvis_rag_embeddings': 1.4, # RAG 임베딩
        'virtual_company_analyses': 1.3,  # 분석 결과
        'virtual_company_rag_sources': 1.3,  # Virtual Company RAG
        'default': 1.0  # 기본 중요도
    }

def get_enhanced_table_schema(table_name):
    """테이블 스키마 정보를 상세하게 조회"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 컬럼 정보 조회
        cursor.execute("""
            SELECT 
                COLUMN_NAME,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_COMMENT
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        columns = cursor.fetchall()
        
        # 인덱스 정보 조회
        cursor.execute("""
            SELECT 
                INDEX_NAME,
                GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as COLUMNS
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            GROUP BY INDEX_NAME
        """, (os.getenv('SQL_DATABASE_NEWBIZ'), table_name))
        
        indexes = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return {
            'columns': columns,
            'indexes': indexes
        }
        
    except Exception as e:
        st.error(f"스키마 정보 조회 중 오류: {str(e)}")
        return None

def save_rag_source(conversation_id, source_type, source_name, description, details, data_size, preview, model_name=""):
    """RAG 소스 정보를 DB에 저장하고 ID 반환"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        sql = """
        INSERT INTO jarvis_rag_sources 
        (conversation_id, source_type, source_name, source_description, source_details, 
         data_size, content_preview, embedding_model)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            conversation_id,
            source_type,
            source_name,
            description,
            json.dumps(details, ensure_ascii=False),
            data_size,
            preview[:1000] if preview else None,  # 미리보기는 1000자로 제한
            model_name
        )
        
        cursor.execute(sql, values)
        source_id = cursor.lastrowid
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return source_id
    except Exception as e:
        st.error(f"RAG 소스 저장 중 오류: {str(e)}")
        return None

def save_rag_embeddings(source_id, chunks, embeddings):
    """청크 텍스트와 임베딩을 DB에 저장"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        sql = """
        INSERT INTO jarvis_rag_embeddings 
        (source_id, chunk_index, chunk_text, embedding)
        VALUES (%s, %s, %s, %s)
        """
        
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            values = (
                source_id,
                idx,
                chunk,
                json.dumps(embedding.tolist())  # numpy array를 list로 변환
            )
            cursor.execute(sql, values)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
    except Exception as e:
        st.error(f"RAG 임베딩 저장 중 오류: {str(e)}")
        return False

def get_embeddings_model():
    """임베딩 모델 반환 (예: sentence-transformers)"""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

def process_mysql_for_rag_enhanced(table_name, conversation_id, include_related=True):
    """향상된 MySQL RAG 처리 함수"""
    try:
        connection = get_mysql_connection()
        
        # 1. 스키마 정보 조회
        schema = get_enhanced_table_schema(table_name)
        if not schema:
            return None
            
        # 2. 관계 정보 조회
        relationships = get_table_relationships()
        related_tables = relationships.get(table_name, [])
        
        # 3. 테이블 중요도 조회
        importance = get_table_importance().get(table_name, get_table_importance()['default'])
        
        # 4. 메인 테이블 데이터 조회
        query = f"SELECT * FROM {table_name} LIMIT 1000"  # 안전을 위한 제한
        df = pd.read_sql(query, connection)
        
        if df.empty:
            return None
        
        # 5. 연관 테이블 데이터 조회 (옵션)
        related_data = {}
        if include_related:
            for rel in related_tables:
                rel_query = f"""
                SELECT DISTINCT r.* 
                FROM {rel['to_table']} r
                JOIN {table_name} m ON r.{rel['to_column']} = m.{rel['from_column']}
                LIMIT 100
                """
                try:
                    rel_df = pd.read_sql(rel_query, connection)
                    if not rel_df.empty:
                        related_data[rel['to_table']] = rel_df
                except Exception:
                    continue
        
        # 6. 구조화된 텍스트 생성
        text_chunks = []
        
        # 6.1 스키마 정보 추가
        schema_text = f"테이블: {table_name}\n"
        schema_text += "컬럼 정보:\n"
        for col in schema['columns']:
            schema_text += f"- {col['COLUMN_NAME']} ({col['COLUMN_TYPE']})"
            if col['COLUMN_COMMENT']:
                schema_text += f" - {col['COLUMN_COMMENT']}"
            schema_text += "\n"
        text_chunks.append(schema_text)
        
        # 6.2 메인 데이터 청킹
        for _, row in df.iterrows():
            chunk_text = f"[{table_name} 데이터]\n"
            for col, val in row.items():
                if pd.notna(val):
                    # 컬럼 코멘트 추가
                    col_comment = next((c['COLUMN_COMMENT'] for c in schema['columns'] if c['COLUMN_NAME'] == col), '')
                    chunk_text += f"{col}"
                    if col_comment:
                        chunk_text += f"({col_comment})"
                    chunk_text += f": {val}\n"
            text_chunks.append(chunk_text)
        
        # 6.3 연관 데이터 청킹
        for rel_table, rel_df in related_data.items():
            rel_schema = get_enhanced_table_schema(rel_table)
            if rel_schema:
                for _, row in rel_df.iterrows():
                    chunk_text = f"[{rel_table} 연관 데이터]\n"
                    for col, val in row.items():
                        if pd.notna(val):
                            col_comment = next((c['COLUMN_COMMENT'] for c in rel_schema['columns'] if c['COLUMN_NAME'] == col), '')
                            chunk_text += f"{col}"
                            if col_comment:
                                chunk_text += f"({col_comment})"
                            chunk_text += f": {val}\n"
                    text_chunks.append(chunk_text)
        
        # 7. 임베딩 생성
        model = get_embeddings_model()
        embeddings = model.encode(text_chunks)
        
        # 8. 가중치 적용
        embeddings = embeddings * importance
        
        # 9. RAG 소스 저장
        source_id = save_rag_source(
            conversation_id=conversation_id,
            source_type='mysql',
            source_name=table_name,
            description=f"MySQL 테이블: {table_name} (관계: {', '.join([r['to_table'] for r in related_tables])})",
            details={
                'schema': schema,
                'relationships': related_tables,
                'importance': importance,
                'rows': len(df),
                'related_tables': list(related_data.keys())
            },
            data_size=len(df) + sum(len(rd) for rd in related_data.values()),
            preview=schema_text[:1000],
            model_name=model.__class__.__name__
        )
        
        if source_id:
            # 10. 임베딩 저장
            success = save_rag_embeddings(source_id, text_chunks, embeddings)
            if success:
                return {
                    'source_id': source_id,
                    'chunks': len(text_chunks),
                    'total_rows': len(df) + sum(len(rd) for rd in related_data.values()),
                    'related_tables': list(related_data.keys())
                }
                
        connection.close()
        
    except Exception as e:
        st.error(f"MySQL RAG 처리 중 오류: {str(e)}")
    return None

# 메인 코드 시작 시 RAG 테이블 생성
create_jarvis_rag_tables()

# ... existing code ...