import pandas as pd
import unicodedata
from sqlalchemy import create_engine

# -------------------------------------------------------
# 1. 핵심 유틸리티 함수
# -------------------------------------------------------

def clean_text(text):
    """
    텍스트 정규화 함수:
    1. NaN 값을 빈 문자열로 변환
    2. 한글 자소 분리(NFD)를 완성형(NFC)으로 통일
    3. 중복 공백 제거 및 앞뒤 공백 제거 (다림질)
    """
    if pd.isna(text): return ""
    text = str(text)
    text = unicodedata.normalize('NFC', text)
    return " ".join(text.split())

def loadCSV(file_path):
    """파일 로드 (인코딩 자동 감지)"""
    try:
        print(f"📂 로딩 시작: {file_path}")
        df = pd.read_csv(file_path, encoding='cp949')
        return df
    except Exception:
        print(f"⚠️ cp949 읽기 실패, utf-8로 재시도: {file_path}")
        try:
            return pd.read_csv(file_path, encoding='utf-8')
        except Exception as e:
            print(f"❌ 파일 읽기 실패: {e}")
            return None

# -------------------------------------------------------
# 2. 메인 로직
# -------------------------------------------------------

# 파일 경로 설정
input_file_land = "서울시_토지특성정보.csv"   # 토지 데이터 (Left)
input_file_bldg = "강남구 표제부.csv"        # 건물 데이터 (Right)

# 파일 로드
df_land = loadCSV(input_file_land)
df_bldg = loadCSV(input_file_bldg)

if df_land is not None and df_bldg is not None:
    print("✅ 파일 로드 완료. 데이터 전처리 시작...")

    # =======================================================
    # [A] 토지 데이터 전처리 (df_land)
    # =======================================================
    # 1. 필요한 컬럼만 선택
    cols_land = [
        '법정동명', '지번', '지목명', '토지면적', 
        '용도지역명1', '용도지역명2', '토지이용상황', 
        '지형형상', '도로접면', '공시지가'
    ]
    # 실제 존재하는 컬럼만 선택
    valid_cols_land = [c for c in cols_land if c in df_land.columns]
    df_land = df_land[valid_cols_land].copy()

    # 2. 지목 필터링 (대, 잡종지, 공장용지, 주차장)
    target_jimo = ['대', '잡종지', '공장용지', '주차장']
    # 지목 컬럼명 찾기 ('지목명' 또는 '지목코드명')
    jimo_col = '지목명' if '지목명' in df_land.columns else '지목코드명'
    
    if jimo_col in df_land.columns:
        df_land = df_land[df_land[jimo_col].isin(target_jimo)].copy()
        print(f"   -> 토지 필터링 완료: {len(df_land)}건")

    # 3. 키(Key) 생성: [법정동명 + " " + 지번] -> 정규화
    df_land['통합주소'] = (df_land['법정동명'].astype(str) + " " + df_land['지번'].astype(str)).apply(clean_text)


    # =======================================================
    # [B] 건물 데이터 전처리 (df_bldg)
    # =======================================================
    # 1. 컬럼명 변경 (원본 -> DB용)
    rename_map = {
        '주용도코드명': '주요용도명',
        '대지면적(㎡)': '건물대지면적',
        '건폐율(%)': '건폐율',
        '연면적(㎡)': '건물연면적',
        '용적률(%)': '용적율',
        '용적률산정연면적(㎡)': '용적률산정연면적',
        '사용승인일': '사용승인일자',
        '세대수(세대)': '세대수',
        '가구수(가구)': '가구수',
        '건축면적(㎡)': '건축면적'
    }
    df_bldg.rename(columns=rename_map, inplace=True)

    # 2. 필요한 컬럼 선택
    cols_bldg = [
        '대지위치', # 키 생성용
        '건물명', '주요용도명', '건물대지면적', '건폐율', '건물연면적', 
        '용적율', '용적률산정연면적', '사용승인일자', '지상층수', '지하층수',
        '승용승강기수','건축면적','비상용승강기수','기타용동'
    ]
    valid_cols_bldg = [c for c in cols_bldg if c in df_bldg.columns]
    df_bldg = df_bldg[valid_cols_bldg].copy()

    # 3. 키(Key) 생성: [대지위치에서 '번지' 제거] -> 정규화
    # 예: "서울특별시 강남구 역삼동 123-4번지" -> "서울특별시 강남구 역삼동 123-4"
    df_bldg['통합주소'] = df_bldg['대지위치'].astype(str).str.replace('번지', '').apply(clean_text)
    
    print(f"   -> 건물 데이터 준비 완료: {len(df_bldg)}건")


    # =======================================================
    # [C] 데이터 병합 (Merge)
    # =======================================================
    print("🔄 데이터 병합 중... (Left Join: 토지 기준)")
    
    df_matched = pd.merge(
        df_land,
        df_bldg,
        on='통합주소',
        how='left',           # 토지 정보는 모두 살리고, 건물 정보가 있으면 붙임
        suffixes=('', '_건물') # 충돌 시 접미사
    )
    
    print(f"   -> 병합 완료. 총 {len(df_matched)}건")


    # =======================================================
    # [D] 최종 컬럼 선택 및 DB 저장
    # =======================================================
    
    # DB에 저장할 최종 컬럼 목록
    final_columns_target = [
        '통합주소',
        '지목명', '토지면적', '용도지역명1', '용도지역명2', '토지이용상황', 
        '지형형상', '도로접면', '공시지가', 
        '건물명', '주요용도명', '건물대지면적', '건폐율', '건물연면적', '용적율', '용적률산정연면적',
        '사용승인일자', '지상층수', '지하층수', '승용승강기수','건축면적',
'비상용승강기수',
'기타용동'
    ]
    
    # 실제 존재하는 컬럼만 필터링 (에러 방지)
    cols_to_save = [c for c in final_columns_target if c in df_matched.columns]
    
    df_to_upload = df_matched[cols_to_save].copy()
    
    print(f"💾 데이터베이스 저장 시작... ({len(df_to_upload)}건)")
    
    try:
        # PostgreSQL 연결
        # [주의] 사용자 계정정보 확인 필요
        engine = create_engine('postgresql+psycopg2://iseung-ug@localhost:5432/addresses')
        
        # to_sql 실행
        # chunksize: 데이터를 5000건씩 나누어 저장 (메모리 부하 방지)
        df_to_upload.to_sql(
            name='seoul_land_info',
            con=engine,
            if_exists='replace', # 기존 테이블 있으면 덮어쓰기
            index=False,
            chunksize=5000       
        )
        print("🎉 [성공] 모든 데이터가 'seoul_land_info' 테이블에 저장되었습니다.")
        
    except Exception as e:
        print(f"❌ DB 저장 중 오류 발생: {e}")

else:
    print("❌ 파일 로드에 실패하여 작업을 중단합니다.")