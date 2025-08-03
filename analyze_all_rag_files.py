import os
import pandas as pd
import glob

def estimate_tokens_for_file(file_path):
    """파일의 토큰 수를 추정합니다."""
    try:
        file_size = os.path.getsize(file_path)
        
        # 파일 확장자별 처리
        if file_path.endswith(('.xlsx', '.xls')):
            try:
                excel_file = pd.ExcelFile(file_path)
                total_tokens = 0
                
                for sheet in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet)
                    text_length = 0
                    for col in df.columns:
                        col_length = df[col].astype(str).str.len().sum()
                        text_length += col_length
                    
                    estimated_tokens = text_length // 4
                    total_tokens += estimated_tokens
                
                return total_tokens
                
            except Exception as e:
                print(f"  Excel 분석 실패: {e}")
                return file_size // 4  # 파일 크기 기반 추정
        
        elif file_path.endswith('.pptx'):
            # PowerPoint는 이미 처리됨
            return 2000  # 추정값
        
        elif file_path.endswith('.pdf'):
            return file_size // 4  # 파일 크기 기반 추정
        
        elif file_path.endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return len(content) // 4
        
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return len(content) // 4
        
        else:
            return file_size // 4  # 기본 추정
    
    except Exception as e:
        print(f"  분석 실패: {e}")
        return 0

def analyze_all_files():
    """rag_files 폴더의 모든 파일을 분석합니다."""
    rag_files_path = "./pages/rag_files"
    
    all_files = []
    
    # 모든 하위 폴더 포함하여 파일 찾기
    for root, dirs, files in os.walk(rag_files_path):
        for file in files:
            if not file.startswith('.') and not file.endswith('.DS_Store'):
                file_path = os.path.join(root, file)
                all_files.append(file_path)
    
    print(f"=== rag_files 폴더 전체 분석 ===")
    print(f"총 파일 수: {len(all_files)}")
    print()
    
    total_tokens = 0
    large_files = []
    
    for file_path in all_files:
        tokens = estimate_tokens_for_file(file_path)
        total_tokens += tokens
        
        if tokens > 10000:  # 10,000 토큰 이상인 파일들
            large_files.append((file_path, tokens))
        
        print(f"{file_path}: {tokens:,} 토큰")
    
    print(f"\n=== 총 토큰 수: {total_tokens:,} ===")
    print(f"토큰 제한 대비: {total_tokens/300000*100:.1f}%")
    
    if large_files:
        print(f"\n=== 대용량 파일들 (10,000 토큰 이상) ===")
        for file_path, tokens in sorted(large_files, key=lambda x: x[1], reverse=True):
            print(f"{file_path}: {tokens:,} 토큰")
    
    if total_tokens > 300000:
        print(f"\n⚠️  경고: 총 토큰 수가 제한을 초과합니다!")
        print("다음 파일들을 처리하는 것을 권장합니다:")
        for file_path, tokens in sorted(large_files, key=lambda x: x[1], reverse=True):
            print(f"  - {file_path}")

if __name__ == "__main__":
    analyze_all_files() 