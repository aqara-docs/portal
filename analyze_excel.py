import pandas as pd
import openpyxl

# Excel 파일 분석
excel_file = pd.ExcelFile('./pages/rag_files/colleagues/20250714_2025년 하반기 부서별 임직원별 R&R.xlsx')

print('=== 시트별 크기 분석 ===')
total_tokens = 0

for sheet in excel_file.sheet_names:
    df = pd.read_excel(excel_file, sheet_name=sheet)
    print(f'{sheet}: {len(df)}행 x {len(df.columns)}열')
    
    # 메모리 사용량
    memory_usage = df.memory_usage(deep=True).sum() / 1024
    print(f'  - 메모리 사용량: {memory_usage:.1f} KB')
    
    # 텍스트 길이 분석
    text_length = 0
    for col in df.columns:
        col_length = df[col].astype(str).str.len().sum()
        text_length += col_length
        print(f'    열({col}): {col_length:,} 문자')
    
    print(f'  - 텍스트 길이 합계: {text_length:,} 문자')
    
    # 토큰 수 추정 (대략적으로 1토큰 = 4문자)
    estimated_tokens = text_length // 4
    print(f'  - 추정 토큰 수: {estimated_tokens:,}')
    total_tokens += estimated_tokens
    
    print()

print(f'=== 전체 분석 ===')
print(f'총 추정 토큰 수: {total_tokens:,}')
print(f'토큰 제한 대비: {total_tokens/300000*100:.1f}%') 