# 최종 들여쓰기 수정 스크립트

# 파일 읽기
with open('pages/00_📦_01_물류_관리_시스템.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 문제가 있는 부분들을 정확한 들여쓰기로 교체
fixes = [
    # 재고 조정 섹션의 제품 선택 부분
    ('                        selected_product = st.selectbox(\n                            "제품 선택",\n                            options=products,\n                        format_func=lambda x: x[\'model_name\'],\n                        key="adjustment_product"\n                    )',
     '                        selected_product = st.selectbox(\n                            "제품 선택",\n                            options=products,\n                            format_func=lambda x: x[\'model_name\'],\n                            key="adjustment_product"\n                        )'),
    
    # PI 관리 섹션의 col1, col2 부분
    ('                col1, col2 = st.columns(2)\n                with col1:',
     '                        col1, col2 = st.columns(2)\n                        with col1:'),
    
    # PI 관리 섹션의 with col2 부분
    ('                with col2:',
     '                        with col2:'),
]

# 교체 실행
for old, new in fixes:
    content = content.replace(old, new)

# 파일 쓰기
with open('pages/00_📦_01_물류_관리_시스템.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('최종 들여쓰기 수정 완료') 