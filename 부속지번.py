import pandas as pd
import os

def refine_building_aux_address(input_file, output_file):
    # 결과를 저장할 딕셔너리 {(고유번호, 대지위치): [부속지번_고유번호리스트]}
    processed_data = {}
    
    # 공공데이터는 주로 cp949 또는 utf-8 인코딩을 사용합니다.
    encoding_type = 'utf-8' 
    
    if not os.path.exists(input_file):
        print(f"파일을 찾을 수 없습니다: {input_file}")
        return

    print("데이터 처리를 시작합니다...")
    
    with open(input_file, 'r', encoding=encoding_type) as f:
        for line in f:
            # 파이프(|) 기호로 분리
            parts = line.strip().split('|')
            
            # 최소 필요한 컬럼 수가 있는지 확인 (최소 28개 이상)
            if len(parts) < 28:
                continue
            
            # 1. 서울특별시 데이터만 필터링 (주소 또는 시군구코드 11 활용)
            address = parts[5]
            sigungu_code = parts[8]
            
            if not (address.startswith("서울특별시") or sigungu_code.startswith("11")):
                continue
                
            # 2. 정보 추출
            pk = parts[0]          # 고유번호 (대표)
            # 대지위치 = address   # 대표지번 주소 (parts[5])
            
            # 3. 부속지번 고유번호(PNU) 생성 
            # 시군구(5)+법정동(5)+대지구분(1)+본번(4)+부번(4) = 19자리
            aux_sigungu = parts[23]
            aux_bjdong = parts[24]
            aux_san = parts[25]
            aux_bun = parts[26]
            aux_ji = parts[27]
            
            aux_pnu = f"{aux_sigungu}{aux_bjdong}{aux_san}{aux_bun}{aux_ji}"
            
            # 4. 그룹화 작업
            key = (pk, address)
            if key not in processed_data:
                processed_data[key] = set() # 중복 제거를 위해 set 사용
            
            processed_data[key].add(aux_pnu)

    # 5. 데이터프레임으로 변환 및 CSV 저장
    rows = []
    for (pk, addr), aux_list in processed_data.items():
        rows.append({
            '고유번호': pk,
            '대지위치': addr,
            '부속지번': ",".join(sorted(list(aux_list))) # 쉼표로 구분된 문자열
        })
    
    result_df = pd.DataFrame(rows)
    
    # 엑셀에서 바로 열 수 있도록 utf-8-sig로 저장
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"성공적으로 저장되었습니다: {output_file}")
    print(f"총 {len(result_df)}건의 대표지번 데이터가 생성되었습니다.")

# 실행
input_filename = 'mart_djy_05.txt'
output_filename = 'seoul_building_aux_lots.csv'
refine_building_aux_address(input_filename, output_filename)
