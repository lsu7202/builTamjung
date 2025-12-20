import pandas as pd
import re

def create_python_list_meta(input_file, output_file):
    # 1. CSV 파일 읽기 (모든 데이터를 문자열로 읽기 위해 dtype=str 설정)
    try:
        df = pd.read_csv(input_file, dtype=str, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(input_file, dtype=str, encoding='cp949')

    # 원하는 컬럼 리스트
    target_columns = ['지목', '형상', '도로', '용도지역', '주용도', '기타용도', '토지이용상황']
    
    # 실제 존재하는 컬럼만 선별
    existing_cols = [col for col in target_columns if col in df.columns]
    
    output_lines = []

    for col in existing_cols:
        # 2. 결측치 제거 및 쉼표 분리
        # explode를 통해 'A, B'를 ['A', 'B']로 나누어 각 행으로 전개
        values_series = df[col].dropna().str.split(',').explode().str.strip()
        
        # 3. '용도지역' 컬럼의 경우 괄호와 그 안의 내용 제거
        if col == '용도지역':
            # 정규표현식: \s*\(.*?\) -> 공백(있을수도없을수도) + ( + 내용 + ) 제거
            values_series = values_series.apply(lambda x: re.sub(r'\s*\(.*?\)', '', str(x)))
        
        # 4. 중복 제거 및 정렬
        unique_list = sorted(values_series.unique())
        
        # 5. 파이썬 변수 대입 형태의 문자열 생성 (예: 지목 = ['대', '전', ...])
        line = f"{col} = {unique_list}"
        output_lines.append(line)

    # 6. .txt 파일로 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"텍스트 파일 생성이 완료되었습니다: {output_file}")

# 실행 섹션
input_filename = 'seoul_land_info_final.csv'  # 실제 파일명으로 수정하세요
output_filename = 'meta_info.txt'
create_python_list_meta(input_filename, output_filename)