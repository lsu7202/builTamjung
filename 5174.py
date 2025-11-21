import geopandas as gpd
import pandas as pd
import re 
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# [0] 설정
FILE_LAND_SHP = "연속지적도_서울_5174/LSMD_CONT_LDREG_5174_11_202511.shp" 
FILE_ZONE_SHP = "용도지역_서울_5174/LSMD_CONT_UQ111_5174_11_202511.shp" 
CRS_SEOUL_5174 = "+proj=tmerc +lat_0=38 +lon_0=127.0028902777778 +k=1 +x_0=200000 +y_0=500000 +ellps=bessel +units=m +no_defs +towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43"

# [1] 매핑
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
    'UQA500': '도시지역미지정', 'UQA999': '도시지역기타',
    'UQA01X': '미상(도시지역)'
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

def run_luris_exact_logic():
    print("🚀 [토지이음 정밀 동기화] 5174 원본 + 절사(Floor) 로직 적용...")

    try:
        print("1. 파일 로드 중...")
        gdf_land = gpd.read_file(FILE_LAND_SHP, encoding='cp949') 
        gdf_zone = gpd.read_file(FILE_ZONE_SHP, encoding='cp949')
        
        gdf_land = gdf_land[['PNU', 'JIBUN', 'geometry']]
        if 'MNUM' in gdf_zone.columns: gdf_zone = gdf_zone[['MNUM', 'geometry']]
        
        gdf_land.set_crs(CRS_SEOUL_5174, allow_override=True, inplace=True)
        gdf_zone.set_crs(CRS_SEOUL_5174, allow_override=True, inplace=True)
        
        gdf_land['geometry'] = gdf_land['geometry'].buffer(0)
        gdf_zone['geometry'] = gdf_zone['geometry'].buffer(0)
        
        # [중요] 여기서 만든 컬럼은 Overlay하면 자동으로 따라감
        gdf_land['원본_대지면적'] = gdf_land.geometry.area 
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return

    # 2. 매핑
    def parse_zone_info(mnum):
        if not isinstance(mnum, str): return "미상", 0, 0
        match = re.search(r'(UQA[0-9A-Z]{3})', mnum)
        if match:
            name = CODE_TO_NAME.get(match.group(1), "미상")
            limits = LEGAL_LIMITS.get(name, (0, 0))
            return name, limits[0], limits[1]
        return "미상", 0, 0

    zone_data = gdf_zone['MNUM'].apply(parse_zone_info)
    gdf_zone['용도지역명'] = [x[0] for x in zone_data]
    gdf_zone['법정건폐율'] = [x[1] for x in zone_data]
    gdf_zone['법정용적율'] = [x[2] for x in zone_data]

    # 3. 오버레이
    print("2. 공간 분석 수행...")
    valid_zone = gdf_zone[gdf_zone['용도지역명'] != "미상"]
    
    # Overlay 결과에 '원본_대지면적'이 자동으로 포함됨
    gdf_overlay = gpd.overlay(gdf_land, valid_zone, how='intersection', keep_geom_type=True)
    gdf_overlay['조각면적_RAW'] = gdf_overlay.geometry.area

    # 4. 면적 보정
    pnu_sum = gdf_overlay.groupby('PNU')['조각면적_RAW'].sum().rename('조각합계')
    gdf_overlay = gdf_overlay.merge(pnu_sum, on='PNU', how='left')
    
    # [삭제함] 여기서 또 merge하면 컬럼 이름이 깨짐 (KeyError 원인 제거)
    # gdf_overlay = gdf_overlay.merge(gdf_land[['PNU', '원본_대지면적']], ...) -> 삭제
    
    gdf_overlay['구성비율'] = gdf_overlay['조각면적_RAW'] / gdf_overlay['조각합계']
    
    # 이제 에러 안 남 (이미 컬럼이 있으니까)
    gdf_overlay['보정_조각면적'] = gdf_overlay['원본_대지면적'] * gdf_overlay['구성비율']
    
    gdf_overlay['상세내역'] = gdf_overlay.apply(
        lambda r: f"{r['용도지역명']}({r['보정_조각면적']:.1f}㎡)", axis=1
    )

    # =================================================================
    # 5. 토지이음 계산식 (용적률 절사합산 / 건폐율 반올림)
    # =================================================================
    print("3. 토지이음 계산식 적용...")

    def calculate_luris_exact(group):
        areas = group['보정_조각면적'].values
        names = group['용도지역명'].values
        
        # 가중평균 여부 판단
        threshold = 330.0
        if any("상업" in name for name in names): threshold = 660.0 
        has_green = any("녹지" in name for name in names)
        has_small_fragment = np.any(areas <= threshold)
        
        apply_weighted_avg = False
        if has_green:
            green_indices = [i for i, name in enumerate(names) if "녹지" in name]
            if np.all(areas[green_indices] <= threshold): apply_weighted_avg = True
        else:
            if has_small_fragment: apply_weighted_avg = True

        # ----------- 계산 로직 -----------
        if apply_weighted_avg:
            # 1. 건폐율: 전체 가중평균 후 반올림
            weighted_bcr_sum = np.sum(group['법정건폐율'] * group['보정_조각면적'])
            total_area = group['원본_대지면적'].values[0]
            final_bcr = round(weighted_bcr_sum / total_area)
            display_bcr = f"{int(final_bcr)}%"

            # 2. 용적률: 각 기여분 절사(Floor) 후 합산 (695, 778 맞추는 핵심)
            contributions = (group['보정_조각면적'] / total_area) * group['법정용적율']
            floored_contributions = np.floor(contributions) 
            final_far = np.sum(floored_contributions)
            display_far = f"{int(final_far)}%"

            # 3. 층수
            max_bcr_limit = np.max(group['법정건폐율'])
            calc_floors = int(final_far / max_bcr_limit) if max_bcr_limit > 0 else 0
            method = "가중평균"
            
        else:
            unique_bcr = sorted(list(set(group['법정건폐율'].astype(int))))
            unique_far = sorted(list(set(group['법정용적율'].astype(int))))
            display_bcr = ", ".join([f"{x}%" for x in unique_bcr])
            display_far = ", ".join([f"{x}%" for x in unique_far])
            
            main_idx = np.argmax(areas)
            calc_floors = int(group['법정용적율'].values[main_idx] / group['법정건폐율'].values[main_idx]) \
                          if group['법정건폐율'].values[main_idx] > 0 else 0
            method = "각각적용"

        return pd.Series({
            '건폐율(토지이음)': display_bcr,
            '용적률(토지이음)': display_far,
            '산정_층수': calc_floors,
            '상세내역': ", ".join(group['상세내역']),
            '적용방식': method
        })

    # 6. 결과 산출
    result_df = gdf_overlay.groupby('PNU').apply(calculate_luris_exact).reset_index()
    
    # 원본 정보 병합 (여기서는 결과 테이블 만드는 거라 merge 필요)
    land_info = gdf_land[['PNU', 'JIBUN', '원본_대지면적']].drop_duplicates('PNU')
    result_df = result_df.merge(land_info, on='PNU', how='left')
    
    final_cols = ['PNU', 'JIBUN', '원본_대지면적', '건폐율(토지이음)', '용적률(토지이음)', '산정_층수', '적용방식', '상세내역']
    final_df = result_df[final_cols].round({'원본_대지면적': 2})

    print(f"   ✅ 최종 산출 완료: {len(final_df):,}개")

    # [검증]
    t1 = final_df[final_df['PNU'].astype(str).str.contains('6010001')] 
    t2 = final_df[final_df['PNU'].astype(str).str.contains('6010015')] 
    
    if not t1.empty:
        print("\n[검증 1] 601-1번지 (목표: 778%)")
        print(t1[['JIBUN', '건폐율(토지이음)', '용적률(토지이음)', '산정_층수']].to_string(index=False))
    
    if not t2.empty:
        print("\n[검증 2] 601-15번지 (목표: 695%, 58%)")
        print(t2[['JIBUN', '건폐율(토지이음)', '용적률(토지이음)', '산정_층수']].to_string(index=False))

    final_df.to_csv("seoul_exact_luris_final.csv", index=False, encoding='utf-8-sig')
    print("\n🎉 파일 저장 완료")

if __name__ == "__main__":
    run_luris_exact_logic()