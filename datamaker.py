import pandas as pd
import unicodedata
from sqlalchemy import create_engine
import os
import warnings

# 경고 메시지 무시
warnings.filterwarnings('ignore')

# -------------------------------------------------------
# 1. 유틸리티 함수
# -------------------------------------------------------
def clean_text(text):
    if pd.isna(text): return ""
    text = str(text)
    text = unicodedata.normalize('NFC', text)
    return " ".join(text.split())

def load_public_data(file_path):
    """
    공공데이터용 로더 (CP949 우선 + 강제 로딩)
    - 표제부 파일처럼 인코딩이나 파싱 오류가 있는 파일도 강제로 읽어냅니다.
    """
    if not os.path.exists(file_path):
        print(f"❌ 파일 없음: {file_path}")
        return None
    
    # 공공데이터는 99% cp949입니다. (euc-kr 포함)
    # utf-8은 순위에서 뒤로 미룹니다.
    encodings = ['cp949', 'euc-kr', 'utf-8', 'utf-8-sig']
    
    for enc in encodings:
        try:
            # [핵심 복구] encoding_errors='replace': 깨진 글자 무시하고 강제 로드
            df = pd.read_csv(
                file_path, 
                encoding=enc, 
                encoding_errors='replace',  # ★ 이게 있어야 표제부 읽힘
                on_bad_lines='skip',        # ★ 줄바꿈 오류 무시
                low_memory=False
            )
            df.columns = df.columns.str.strip() # 컬럼 공백 제거
            print(f"   ✅ [공공데이터] 로드 성공: {file_path} ({enc})")
            return df
        except Exception as e:
            # print(f"   ⚠️ {enc} 실패: {e}") # 로그 너무 길어서 생략
            continue
            
    print(f"❌ [치명적] 로드 실패: {file_path}")
    return None

def load_our_data(file_path):
    """
    우리가 만든 데이터용 로더 (UTF-8-SIG 고정)
    - seoul_exact_luris_final.csv 전용
    """
    if not os.path.exists(file_path):
        print(f"❌ 파일 없음: {file_path}")
        return None
    
    try:
        # 우리가 만든건 무조건 utf-8-sig
        df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
        df.columns = df.columns.str.strip()
        print(f"   ✅ [GIS데이터] 로드 성공: {file_path} (utf-8-sig)")
        return df
    except Exception as e:
        print(f"❌ GIS 데이터 로드 실패: {e}")
        return None

# -------------------------------------------------------
# 2. 메인 로직
# -------------------------------------------------------

# 파일 경로
input_file_land = "서울시_토지특성정보.csv"
input_file_bldg = "서울시 건축물대장 표제부.csv" 
input_file_gis  = "seoul_exact_luris_final.csv" 

print("📂 데이터 로딩 시작...")

# [전략] 파일 성격에 맞는 로더 사용
df_land = load_public_data(input_file_land) # 공공데이터 -> cp949 강제
df_bldg = load_public_data(input_file_bldg) # 공공데이터 -> cp949 강제 (표제부 해결)
df_gis  = load_our_data(input_file_gis)     # 우리데이터 -> utf-8-sig (PNU 해결)

if df_land is not None and df_bldg is not None and df_gis is not None:
    print("\n✅ 모든 파일 로드 완료. 데이터 병합 프로세스 시작...")

    # =======================================================
    # [A] 토지 데이터 전처리
    # =======================================================
    print("   -> [1/4] 토지 데이터 처리 중...")
    cols_land = [
        '고유번호', '법정동명', '지번', '지목명', '토지면적', 
        '용도지역명1', '용도지역명2', '토지이용상황', 
        '지형형상', '도로접면', '공시지가'
    ]
    # 있는 컬럼만 선택 (오류 방지)
    valid_cols_land = [c for c in cols_land if c in df_land.columns]
    df_land = df_land[valid_cols_land].copy()

    target_jimo = ['대', '잡종지', '공장용지', '주차장']
    jimo_col = '지목명' if '지목명' in df_land.columns else '지목코드명'
    if jimo_col in df_land.columns:
        df_land = df_land[df_land[jimo_col].isin(target_jimo)].copy()

    df_land['통합주소'] = (df_land['법정동명'].astype(str) + " " + df_land['지번'].astype(str)).apply(clean_text)
    if '고유번호' in df_land.columns:
        df_land['고유번호'] = df_land['고유번호'].astype(str)


    # =======================================================
    # [B] GIS 분석 데이터 병합
    # =======================================================
    print("   -> [2/4] GIS 데이터 매칭 중...")
    
    # 컬럼 확인 및 복구
    if 'PNU' not in df_gis.columns:
        # 혹시라도 utf-8-sig가 실패해서 다른 걸로 읽혔을 때 깨진 컬럼명 복구
        cols = df_gis.columns.tolist()
        for c in cols:
            if 'PNU' in str(c):
                df_gis.rename(columns={c: 'PNU'}, inplace=True)
                break
    
    if 'PNU' in df_gis.columns:
        df_gis['PNU'] = df_gis['PNU'].astype(str)
        
        cols_to_merge = ['PNU', '건폐율(토지이음)', '용적률(토지이음)', '산정_층수', '상세내역']
        valid_gis_cols = [c for c in cols_to_merge if c in df_gis.columns]
        
        df_land = pd.merge(
            df_land,
            df_gis[valid_gis_cols], 
            left_on='고유번호', 
            right_on='PNU', 
            how='left'
        )
        
        rename_map_gis = {
            '건폐율(토지이음)': '법정건폐율',
            '용적률(토지이음)': '법정용적율',
            '상세내역': '용도지역_분석결과'
        }
        df_land.rename(columns=rename_map_gis, inplace=True)
    else:
        print("   ⚠️ 경고: GIS 데이터에서 PNU 컬럼을 찾지 못해 병합을 건너뜁니다.")


    # =======================================================
    # [C] 건물 데이터 전처리
    # =======================================================
    print("   -> [3/4] 건물 데이터 컬럼 매핑...")

    rename_map_bldg = {
        '대지_위치': '대지위치', '도로명_대지_위치': '도로명주소', '건물_명': '건물명',
        '주_용도_코드_명': '주요용도명', '주용도코드명': '주요용도명',
        '대지_면적': '건물대지면적', '연_면적': '건물연면적', '건축_면적': '건축면적',
        '건폐_율': '건폐율', '용적_율': '용적율', '용적_율_산정_연_면적': '용적률산정연면적',
        '사용_승인_일': '사용승인일자', '지상_층_수': '지상층수', '지하_층_수': '지하층수',
        '승용_승강기_수': '승용승강기수', '비상용_승강기_수': '비상용승강기수',
        '부속_건축물_ 수': '기타용동', '총_동_연_면적': '총동연면적' 
    }
    
    df_bldg.rename(columns=rename_map_bldg, inplace=True)

    cols_bldg_target = [
        '대지위치', '건물명', '주요용도명', '건물대지면적', '건폐율', '건물연면적', 
        '용적율', '용적률산정연면적', '사용승인일자', '지상층수', '지하층수',
        '승용승강기수', '건축면적', '비상용승강기수', '기타용동'
    ]
    valid_cols_bldg = [c for c in cols_bldg_target if c in df_bldg.columns]
    df_bldg = df_bldg[valid_cols_bldg].copy()

    if '대지위치' in df_bldg.columns:
        df_bldg['통합주소'] = df_bldg['대지위치'].astype(str).str.replace('번지', '').apply(clean_text)


    # =======================================================
    # [D] 최종 병합 및 저장
    # =======================================================
    print("   -> [4/4] 최종 병합 및 저장...")
    
    df_matched = pd.merge(
        df_land,
        df_bldg,
        on='통합주소',
        how='left',
        suffixes=('', '_건물')
    )
    
    final_columns_target = [
        '통합주소', '고유번호', 
        '지목명', '토지면적', '토지이용상황', 
        '지형형상', '도로접면', '공시지가', 
        '법정건폐율', '법정용적율', '용도지역_분석결과',
        '건물명', '주요용도명', '건물대지면적', '건폐율', '건물연면적', '용적율', '용적률산정연면적',
        '사용승인일자', '지상층수', '지하층수', '승용승강기수','건축면적',
        '비상용승강기수','기타용동'
    ]
    
    cols_to_save = [c for c in final_columns_target if c in df_matched.columns]
    df_to_upload = df_matched[cols_to_save].copy()
    
    print(f"\n💾 저장 시작 ({len(df_to_upload)}건)...")
    
    try:
        # DB 저장
        engine = create_engine('postgresql+psycopg2://iseung-ug@localhost:5432/addresses')
        df_to_upload.to_sql('seoul_land_info', con=engine, if_exists='replace', index=False, chunksize=5000)
        print("   ✅ DB 저장 완료")
        
        # CSV 저장
        csv_filename = "seoul_land_info_final.csv"
        df_to_upload.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"   ✅ CSV 저장 완료 ('{csv_filename}')")
        
    except Exception as e:
        print(f"❌ 저장 오류: {e}")

else:
    print("\n❌ 로드 실패. 파일 경로와 인코딩을 확인하세요.")