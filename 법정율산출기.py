import geopandas as gpd
import pandas as pd
import re 
import numpy as np

# =======================================================
# [0] 설정: 파일 경로
# =======================================================
FILE_LAND_SHP = "연속지적도_서울/LSMD_CONT_LDREG_11_202511.shp" 
FILE_ZONE_SHP = "용도지역_서울/LSMD_CONT_UQ111_11_202511.shp" 

# =======================================================
# [1] 브이월드 공식 좌표계 정의 (EPSG:5186)
# =======================================================
# 설명: GRS80 타원체, 중부원점(Longitude 127), False Northing 600,000m
CRS_VWORLD_STD = "EPSG:5186"  # 연속지적도 표준
CRS_ANALYSIS   = "EPSG:5179"  # 분석/계산용 (UTM-K)

# Bessel(5174)일 경우를 대비한 보정 파라미터 (Towgs84)
CRS_BESSEL_CORRECTED = "+proj=tmerc +lat_0=38 +lon_0=127.0028902777778 +k=1 +x_0=200000 +y_0=500000 +ellps=bessel +units=m +no_defs +towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43"

# [2] 매핑 데이터
CODE_TO_NAME = {
    'UQA100': '주거지역', 'UQA110': '전용주거지역',
    'UQA111': '제1종전용주거지역', 'UQA112': '제2종전용주거지역',
    'UQA120': '일반주거지역', 'UQA121': '제1종일반주거지역',
    'UQA122': '제2종일반주거지역', 'UQA123': '제3종일반주거지역',
    'UQA130': '준주거지역', 'UQA200': '상업지역',
    'UQA210': '중심상업지역', 'UQA220': '일반상업지역',
    'UQA230': '근린상업지역', 'UQA240': '유통상업지역',
    'UQA300': '공업지역', 'UQA310': '전용공업지역',
    'UQA320': '일반공업지역', 'UQA330': '준공업지역',
    'UQA400': '녹지지역', 'UQA410': '보전녹지지역',
    'UQA420': '생산녹지지역', 'UQA430': '자연녹지지역',
    'UQA500': '도시지역미지정', 'UQA999': '도시지역기타'
}

LEGAL_LIMITS = {
    '제1종전용주거지역': (50, 100), '제2종전용주거지역': (40, 120),
    '제1종일반주거지역': (60, 150), '제2종일반주거지역': (60, 200),
    '제3종일반주거지역': (50, 250), '준주거지역': (60, 400),
    '중심상업지역': (60, 1000), '일반상업지역': (60, 800),
    '근린상업지역': (60, 600), '유통상업지역': (60, 600),
    '전용공업지역': (60, 300), '일반공업지역': (60, 350),
    '준공업지역': (60, 400), '보전녹지지역': (20, 50),
    '생산녹지지역': (20, 50), '자연녹지지역': (20, 50)
}

def clean_geometry(gdf):
    """위상(Topology) 오류 수정 (필수)"""
    gdf['geometry'] = gdf['geometry'].buffer(0)
    return gdf[~gdf['geometry'].is_empty]

def run_vworld_standard_analysis():
    print(f"🚀 브이월드 표준({CRS_VWORLD_STD}) 기반 정밀 분석 시작...")

    # [1] 파일 로드
    try:
        print("1. SHP 파일 로딩 중...")
        gdf_land = gpd.read_file(FILE_LAND_SHP, encoding='cp949') 
        gdf_zone = gpd.read_file(FILE_ZONE_SHP, encoding='cp949')
        
        gdf_land = gdf_land[['PNU', 'JIBUN', 'geometry']]
        if 'MNUM' in gdf_zone.columns:
            gdf_zone = gdf_zone[['MNUM', 'geometry']]
        else:
            print("❌ 오류: 용도지역도에 MNUM 컬럼 없음.")
            return
    except Exception as e:
        print(f"❌ 파일 로드 실패: {e}")
        return

    # [2] 좌표계 정의 및 통일 (★ 핵심 수정)
    print(f"2. 좌표계 설정 (연속지적도 기준: {CRS_VWORLD_STD})...")

    # 2-1. 연속지적도 (User 확인: 5186 확실)
    if not gdf_land.crs:
        print(f"   -> 연속지적도에 좌표계 정보가 없어 {CRS_VWORLD_STD}를 할당합니다.")
        gdf_land.set_crs(CRS_VWORLD_STD, inplace=True)
    else:
        # 만약 파일에 이미 CRS가 있다면 그걸 믿되, 5186으로 변환
        print(f"   -> 연속지적도 원본 CRS: {gdf_land.crs.name}")
        gdf_land = gdf_land.to_crs(CRS_VWORLD_STD)

    # 2-2. 용도지역도 (User 확인: 5186 혹은 5174)
    # 용도지역도는 CRS 정보가 없을 경우 5186으로 가정하되,
    # 좌표 값의 범위(Y좌표)를 보고 5174(Bessel)인지 5186(GRS80)인지 판단하는 로직 추가
    if not gdf_zone.crs:
        # 샘플 좌표 확인 (Y좌표가 500,000 대면 Bessel, 600,000 대면 GRS80)
        sample_y = gdf_zone.geometry.iloc[0].centroid.y
        if 400000 < sample_y < 550000:
            print("   ⚠️ 주의: 용도지역도 Y좌표가 50만 대역입니다. (Bessel 5174 추정)")
            print("   -> Bessel 보정 파라미터를 적용하여 변환합니다.")
            gdf_zone.set_crs(CRS_BESSEL_CORRECTED, inplace=True)
        else:
            print(f"   -> 용도지역도 좌표가 {CRS_VWORLD_STD} 대역으로 보입니다.")
            gdf_zone.set_crs(CRS_VWORLD_STD, inplace=True)

    # [3] 분석용 좌표계(5179)로 통일
    # 오버레이 계산을 위해 두 레이어를 동일한 GRS80 기반인 5179로 맞춥니다.
    gdf_land = gdf_land.to_crs(CRS_ANALYSIS)
    gdf_zone = gdf_zone.to_crs(CRS_ANALYSIS)

    # 지오메트리 정제
    gdf_land = clean_geometry(gdf_land)
    gdf_zone = clean_geometry(gdf_zone)
    
    # 원본 대지면적 저장
    gdf_land['원본_대지면적'] = gdf_land.geometry.area 

    # [4] 코드 해독
    print("3. 용도지역 데이터 매핑...")
    def parse_zone_name(mnum):
        if not isinstance(mnum, str): return "미상"
        match = re.search(r'(UQA[0-9A-Z]{3})', mnum)
        if match:
            return CODE_TO_NAME.get(match.group(1), "미상")
        return "미상"
    gdf_zone['용도지역명'] = gdf_zone['MNUM'].apply(parse_zone_name)

    # [5] 공간 교차 (Overlay)
    print("4. 공간 교차 분석 수행...")
    try:
        gdf_overlay = gpd.overlay(gdf_land, gdf_zone, how='intersection', keep_geom_type=True)
        gdf_overlay['조각면적'] = gdf_overlay.geometry.area
    except Exception as e:
        print(f"❌ Overlay 실패: {e}")
        return

    # [6] 데이터 계산 (토지이음 기준)
    print("5. 법정 지표 산출 중...")

    def is_valid_zone(name):
        return name in LEGAL_LIMITS and name != "미상"
    
    valid_overlay = gdf_overlay[gdf_overlay['용도지역명'].apply(is_valid_zone)].copy()

    # 비율 검증
    valid_overlay['구성비율'] = valid_overlay['조각면적'] / valid_overlay['원본_대지면적'] * 100

    # 법정 한도 매핑
    valid_overlay['법정건폐율'] = valid_overlay['용도지역명'].apply(lambda x: LEGAL_LIMITS.get(x)[0])
    valid_overlay['법정용적율'] = valid_overlay['용도지역명'].apply(lambda x: LEGAL_LIMITS.get(x)[1])

    # 가중치 분자 계산
    valid_overlay['건폐율_가중분'] = valid_overlay['조각면적'] * valid_overlay['법정건폐율']
    valid_overlay['용적율_가중분'] = valid_overlay['조각면적'] * valid_overlay['법정용적율']

    # 상세 내역 텍스트
    valid_overlay['상세내역_임시'] = valid_overlay.apply(
        lambda r: f"{r['용도지역명']}({r['조각면적']:.1f}㎡, {r['구성비율']:.1f}%)", axis=1
    )

    # [7] 최종 집계
    agg_funcs = {
        '조각면적': 'sum',
        '건폐율_가중분': 'sum',
        '용적율_가중분': 'sum',
        '법정건폐율': 'max',      # 토지이음: 건폐율은 최대값 표시
        '상세내역_임시': lambda x: ', '.join(x)
    }
    
    result_df = valid_overlay.groupby('PNU').agg(agg_funcs).reset_index()
    
    # 원본 정보 병합
    result_df = result_df.merge(gdf_land[['PNU', 'JIBUN', '원본_대지면적']].drop_duplicates('PNU'), on='PNU', how='left')

    # 1. 분석 커버리지 (누락 여부 확인용)
    result_df['분석_커버리지'] = (result_df['조각면적'] / result_df['원본_대지면적'] * 100)

    # 2. 적용 분모 (98% 이상이면 100%로 보정)
    result_df['적용_분모'] = np.where(
        result_df['분석_커버리지'] >= 98.0, 
        result_df['조각면적'], 
        result_df['원본_대지면적']
    )

    # 3. 가중평균 계산 (용적률)
    result_df['가중평균_건폐율'] = result_df['건폐율_가중분'] / result_df['적용_분모']
    result_df['가중평균_용적율'] = result_df['용적율_가중분'] / result_df['적용_분모']

    # 4. 토지이음 표시값 생성
    result_df.rename(columns={'법정건폐율': '토지이음_건폐율_MAX'}, inplace=True) # 건폐율은 Max
    result_df['토지이음_용적율_표시'] = result_df['가중평균_용적율'].round(0).astype(int) # 용적률은 Avg

    # 5. 층수 산정 (가중평균 용적률 / 최대 건폐율, 소수점 버림)
    result_df['산정_층수'] = result_df.apply(
        lambda row: int(row['가중평균_용적율'] / row['토지이음_건폐율_MAX']) 
        if row['토지이음_건폐율_MAX'] > 0 else 0, 
        axis=1
    )

    # [8] 결과 저장
    final_cols = [
        'PNU', 'JIBUN', '원본_대지면적',
        '토지이음_건폐율_MAX', '토지이음_용적율_표시', '산정_층수',
        '가중평균_건폐율', '가중평균_용적율',
        '상세내역_임시', '분석_커버리지'
    ]
    
    result_df = result_df[final_cols]
    result_df.rename(columns={
        'JIBUN': '지번_주소',
        '원본_대지면적': '총대지면적',
        '토지이음_건폐율_MAX': '건폐율(최대기준)',
        '토지이음_용적율_표시': '용적률(토지이음)',
        '상세내역_임시': '용도지역_상세'
    }, inplace=True)

    result_df = result_df.round({'총대지면적': 2, '가중평균_건폐율': 2, '가중평균_용적율': 2, '분석_커버리지': 1})

    print(f"   ✅ 최종 산출 완료: {len(result_df):,}개")
    
    # 검증: 601-1번지
    target = result_df[result_df['PNU'].astype(str).str.contains('6010001')]
    if not target.empty:
        print("\n[최종 검증] 601-1번지 결과:")
        print(target[['지번_주소', '용도지역_상세', '건폐율(최대기준)', '용적률(토지이음)', '산정_층수']].to_string())

    result_df.to_csv("seoul_vworld_standard_final.csv", index=False, encoding='utf-8-sig')
    print("🎉 파일 저장 완료")

if __name__ == "__main__":
    run_vworld_standard_analysis()