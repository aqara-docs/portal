import os
import pandas as pd

# 문제가 될 만한 대용량 파일들
large_files = [
    "./pages/rag_files/process/☆ 신규입사자 온보딩 자료_250403.pptx",
    "./pages/rag_files/process/[경영지원_전자서명_006] 전자서명_모두싸인 사용가이드_250331.pptx",
    "./pages/rag_files/process/[인증_KC_001] KC인증 프로세Aqara_KC_Certification List_250422.xlsx"
]

print("=== 대용량 파일 분석 ===")

for file_path in large_files:
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        print(f"\n파일: {file_path}")
        print(f"크기: {file_size / 1024 / 1024:.1f} MB")
        
        # Excel 파일인 경우 상세 분석
        if file_path.endswith(('.xlsx', '.xls')):
            try:
                excel_file = pd.ExcelFile(file_path)
                print(f"시트 수: {len(excel_file.sheet_names)}")
                
                total_tokens = 0
                for sheet in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet)
                    print(f"  {sheet}: {len(df)}행 x {len(df.columns)}열")
                    
                    # 텍스트 길이 분석
                    text_length = 0
                    for col in df.columns:
                        col_length = df[col].astype(str).str.len().sum()
                        text_length += col_length
                    
                    # 토큰 수 추정
                    estimated_tokens = text_length // 4
                    total_tokens += estimated_tokens
                    print(f"    추정 토큰 수: {estimated_tokens:,}")
                
                print(f"  총 추정 토큰 수: {total_tokens:,}")
                print(f"  토큰 제한 대비: {total_tokens/300000*100:.1f}%")
                
            except Exception as e:
                print(f"  분석 실패: {e}")
        
        # PowerPoint 파일인 경우
        elif file_path.endswith('.pptx'):
            print("  PowerPoint 파일 - 텍스트 추출 시 토큰 수가 매우 클 수 있음")
            print("  추정 토큰 수: 50,000-200,000 (파일 크기에 따라)")
    
    else:
        print(f"\n파일 없음: {file_path}")

print("\n=== 권장사항 ===")
print("1. 9MB 이상의 PowerPoint 파일들은 토큰 제한을 초과할 가능성이 높습니다.")
print("2. 이 파일들을 임시로 다른 폴더로 이동하거나 삭제하는 것을 권장합니다.")
print("3. 또는 파일 크기를 줄이거나 텍스트만 추출하여 사용하세요.") 