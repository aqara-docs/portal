import os
import shutil

def process_large_files():
    """대용량 파일들을 임시 폴더로 이동합니다."""
    
    # 대용량 파일 목록
    large_files = [
        "./pages/rag_files/finance/Coolux price for LED Blue Skylight series -250606.pdf",
        "./pages/rag_files/process/★ AqaraLife_ASP(표준업무프로세스)_v1.0_250422_공유용.docx",
        "./pages/rag_files/process/[구매_일반_001] 구매 및 샘플특송 프로세스_250410.docx",
        "./pages/rag_files/process/[인증_WWST_002] WWST_인증 프로세스.pdf"
    ]
    
    temp_folder = "./pages/rag_files/temp_large_files"
    
    # 임시 폴더가 없으면 생성
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    
    print("=== 대용량 파일 처리 ===")
    
    for file_path in large_files:
        if os.path.exists(file_path):
            # 파일명 추출
            file_name = os.path.basename(file_path)
            temp_path = os.path.join(temp_folder, file_name)
            
            # 파일 이동
            shutil.move(file_path, temp_path)
            print(f"✅ {file_name} → temp_large_files/")
        else:
            print(f"❌ 파일 없음: {file_path}")
    
    print("\n=== 처리 완료 ===")
    print("대용량 파일들이 temp_large_files 폴더로 이동되었습니다.")
    print("필요시 나중에 다시 가져올 수 있습니다.")

if __name__ == "__main__":
    process_large_files() 