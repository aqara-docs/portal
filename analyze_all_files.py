import pandas as pd
import openpyxl
import os
import glob

def analyze_excel_file(file_path):
    """Excel 파일 분석"""
    try:
        excel_file = pd.ExcelFile(file_path)
        total_tokens = 0
        
        for sheet in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            
            # 텍스트 길이 분석
            text_length = 0
            for col in df.columns:
                col_length = df[col].astype(str).str.len().sum()
                text_length += col_length
            
            # 토큰 수 추정
            estimated_tokens = text_length // 4
            total_tokens += estimated_tokens
            
        return total_tokens, len(excel_file.sheet_names)
    except Exception as e:
        print(f"  오류: {e}")
        return 0, 0

# 모든 Excel 파일 찾기
excel_files = []
for root, dirs, files in os.walk('./pages/rag_files'):
    for file in files:
        if file.endswith(('.xlsx', '.xls')):
            excel_files.append(os.path.join(root, file))

print('=== 전체 Excel 파일 분석 ===')
total_all_tokens = 0

for file_path in excel_files:
    print(f'\n파일: {file_path}')
    tokens, sheets = analyze_excel_file(file_path)
    print(f'  - 추정 토큰 수: {tokens:,}')
    print(f'  - 시트 수: {sheets}')
    total_all_tokens += tokens

print(f'\n=== 전체 분석 ===')
print(f'총 Excel 파일 수: {len(excel_files)}')
print(f'총 추정 토큰 수: {total_all_tokens:,}')
print(f'토큰 제한 대비: {total_all_tokens/300000*100:.1f}%')

# 다른 파일들도 확인
print(f'\n=== 다른 파일들 ===')
other_files = []
for root, dirs, files in os.walk('./pages/rag_files'):
    for file in files:
        if not file.endswith(('.xlsx', '.xls')):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tokens = len(content) // 4
                    print(f'{file_path}: {tokens:,} 토큰')
                    total_all_tokens += tokens
            except:
                print(f'{file_path}: 읽기 실패') 