import streamlit as st

def split_rag_data_into_chunks(mysql_data=None, website_data=None, files_data=None, model_name=None, max_chunk_size=800000):
    """RAG 데이터를 청크로 분할하여 반환"""
    chunks = []
    
    # 모델별 청크 크기 설정
    if model_name and model_name.startswith('claude'):
        max_chunk_size = 6000000  # 6MB
    elif model_name and model_name.startswith('o1'):
        max_chunk_size = 600000   # 600KB
    elif model_name and (model_name.startswith('gpt-4') or model_name.startswith('gpt-3')):
        max_chunk_size = 2500000  # 2.5MB
    else:
        max_chunk_size = 800000   # 800KB
    
    # 소스별로 데이터 수집
    data_sources = []
    
    # MySQL 데이터 준비
    if mysql_data:
        for table_name, df in mysql_data.items():
            table_info = {
                'type': 'mysql',
                'name': table_name,
                'data': df,
                'size_estimate': len(str(df.head(3))) + len(', '.join(df.columns)) + 200
            }
            data_sources.append(table_info)
    
    # 웹사이트 데이터 준비
    if website_data:
        for i, page_data in enumerate(website_data):
            page_info = {
                'type': 'website',
                'name': f"페이지_{i+1}",
                'data': page_data,
                'size_estimate': len(page_data['content'][:500]) + len(page_data['title']) + 100
            }
            data_sources.append(page_info)
    
    # 파일 데이터 준비
    if files_data:
        for file_data in files_data:
            file_info = {
                'type': 'files',
                'name': file_data['name'],
                'data': file_data,
                'size_estimate': len(file_data['content'][:500]) + 100
            }
            data_sources.append(file_info)
    
    # 크기 기준으로 정렬 (작은 것부터)
    data_sources.sort(key=lambda x: x['size_estimate'])
    
    # 청크로 분할
    current_chunk = []
    current_size = 0
    
    for source in data_sources:
        if current_size + source['size_estimate'] > max_chunk_size and current_chunk:
            # 현재 청크가 꽉 찼으므로 새 청크 시작
            chunks.append(current_chunk)
            current_chunk = [source]
            current_size = source['size_estimate']
        else:
            current_chunk.append(source)
            current_size += source['size_estimate']
    
    # 마지막 청크 추가
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def create_chunk_context(chunk_data, model_name=None):
    """특정 청크의 RAG 컨텍스트 생성"""
    context_parts = []
    
    # 모델별 설정
    if model_name and model_name.startswith('claude'):
        MYSQL_SAMPLE_ROWS = 1
        CONTENT_PREVIEW_SIZE = 200
    elif model_name and model_name.startswith('o1'):
        MYSQL_SAMPLE_ROWS = 2
        CONTENT_PREVIEW_SIZE = 300
    else:
        MYSQL_SAMPLE_ROWS = 3
        CONTENT_PREVIEW_SIZE = 500
    
    # 소스별로 컨텍스트 생성
    mysql_tables = []
    website_pages = []
    file_names = []
    
    for source in chunk_data:
        if source['type'] == 'mysql':
            df = source['data']
            table_context = f"\n[{source['name']}] 테이블:\n"
            table_context += f"- 행 수: {len(df):,}개\n"
            table_context += f"- 컬럼: {', '.join(df.columns.tolist())}\n"
            
            if len(df) > 0:
                table_context += "- 샘플 데이터:\n"
                sample_data = df.head(MYSQL_SAMPLE_ROWS).to_string(index=False, max_cols=5)
                if len(sample_data) > 500:
                    sample_data = sample_data[:500] + "..."
                table_context += sample_data + "\n"
            
            context_parts.append(table_context)
            mysql_tables.append(source['name'])
            
        elif source['type'] == 'website':
            page_data = source['data']
            page_context = f"\n[{source['name']}] {page_data['title']}\n"
            page_context += f"URL: {page_data['url']}\n"
            content_preview = page_data['content'][:CONTENT_PREVIEW_SIZE] + "..."
            page_context += f"내용: {content_preview}\n"
            
            context_parts.append(page_context)
            website_pages.append(source['name'])
            
        elif source['type'] == 'files':
            file_data = source['data']
            file_context = f"\n[문서] {file_data['name']}\n"
            file_context += f"크기: {file_data['size']:,}자\n"
            content_preview = file_data['content'][:CONTENT_PREVIEW_SIZE] + "..."
            file_context += f"내용: {content_preview}\n"
            
            context_parts.append(file_context)
            file_names.append(file_data['name'])
    
    # 헤더 추가
    if mysql_tables:
        context_parts.insert(0, f"=== MySQL 테이블 ({len(mysql_tables)}개) ===")
    if website_pages:
        context_parts.insert(-len(website_pages) if website_pages else 0, f"=== 웹사이트 페이지 ({len(website_pages)}개) ===")
    if file_names:
        context_parts.append(f"=== 문서 파일 ({len(file_names)}개) ===")
    
    context_text = "\n".join(context_parts)
    
    # 소스 정보 생성
    rag_sources = []
    if mysql_tables:
        rag_sources.append({
            'type': 'mysql',
            'name': f'MySQL 테이블 ({len(mysql_tables)}개)',
            'details': ', '.join(mysql_tables[:3]) + ('...' if len(mysql_tables) > 3 else ''),
            'tables': mysql_tables
        })
    if website_pages:
        rag_sources.append({
            'type': 'website',
            'name': f'웹사이트 ({len(website_pages)}개)',
            'details': ', '.join(website_pages[:3]) + ('...' if len(website_pages) > 3 else ''),
            'pages': website_pages
        })
    if file_names:
        rag_sources.append({
            'type': 'files',
            'name': f'문서 ({len(file_names)}개)',
            'details': ', '.join(file_names[:3]) + ('...' if len(file_names) > 3 else ''),
            'files': file_names
        })
    
    return context_text, rag_sources

def process_chunked_rag(user_query, mysql_data=None, website_data=None, files_data=None, model_name=None, get_ai_response_func=None):
    """청크 기반 RAG 처리"""
    
    # 데이터를 청크로 분할
    chunks = split_rag_data_into_chunks(mysql_data, website_data, files_data, model_name)
    
    if len(chunks) <= 1:
        # 청크가 1개 이하면 일반 처리
        return None
    
    st.info(f"🔄 **청크 분할 모드**: 데이터가 크기 제한을 초과하여 {len(chunks)}개 청크로 나누어 처리합니다.")
    
    chunk_responses = []
    all_rag_sources = []
    
    # 각 청크별 처리
    for i, chunk in enumerate(chunks):
        st.write(f"**청크 {i+1}/{len(chunks)} 처리 중...**")
        
        # 청크 컨텍스트 생성
        chunk_context, chunk_sources = create_chunk_context(chunk, model_name)
        all_rag_sources.extend(chunk_sources)
        
        # 청크별 프롬프트 구성
        chunk_prompt = f"""
다음은 전체 데이터 중 일부입니다 (청크 {i+1}/{len(chunks)}):

{chunk_context}

질문: {user_query}

이 청크의 데이터만을 기반으로 답변해주세요. 다른 청크의 결과와 나중에 종합될 예정입니다.
"""
        
        # AI 응답 생성
        response = get_ai_response_func(
            prompt=chunk_prompt,
            model_name=model_name,
            system_prompt="당신은 RAG 기반 AI 어시스턴트입니다. 제공된 청크 데이터만을 기반으로 부분적 답변을 제공해주세요.",
            enable_thinking=False  # 청크 처리 시 thinking 비활성화
        )
        
        chunk_responses.append({
            'chunk_id': i+1,
            'content': response['content'],
            'sources': chunk_sources
        })
        
        # 진행 상황 표시
        progress = (i + 1) / len(chunks)
        st.progress(progress)
    
    # 최종 종합 답변 생성
    st.write("**🔄 청크 결과를 종합하는 중...**")
    
    synthesis_prompt = f"""
다음은 동일한 질문에 대해 서로 다른 데이터 청크로부터 얻은 부분적 답변들입니다:

질문: {user_query}

청크별 답변들:
"""
    
    for i, chunk_resp in enumerate(chunk_responses):
        synthesis_prompt += f"\n--- 청크 {chunk_resp['chunk_id']} 답변 ---\n{chunk_resp['content']}\n"
    
    synthesis_prompt += """
위의 모든 청크 답변들을 종합하여 완전하고 일관된 최종 답변을 작성해주세요:
1. 중복된 정보는 통합하기
2. 서로 다른 관점이 있다면 모두 포함하기  
3. 전체적인 인사이트와 결론 제시하기
4. 청크별 세부 정보를 체계적으로 정리하기
"""
    
    final_response = get_ai_response_func(
        prompt=synthesis_prompt,
        model_name=model_name,
        system_prompt="당신은 여러 부분적 답변을 종합하여 완전한 최종 답변을 생성하는 전문가입니다.",
        enable_thinking=st.session_state.get('enable_sidebar_reasoning', False)
    )
    
    return {
        'content': final_response['content'],
        'thinking': final_response.get('thinking', ''),
        'has_thinking': final_response.get('has_thinking', False),
        'chunk_count': len(chunks),
        'chunk_responses': chunk_responses,
        'rag_sources_used': all_rag_sources
    } 