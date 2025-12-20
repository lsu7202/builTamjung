import os
import logging
import json
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text

# --- 1. 네이버 API 설정 ---
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET')

# --- 2. DB 연결 설정 ---
DB_USER = os.getenv('DB_USER', 'iseung-ug')
DB_HOST = os.getenv('DB_HOST', "localhost")
DB_PORT = os.getenv('DB_PORT', "5432")
DB_NAME = os.getenv('DB_NAME', "postgres")
DB_PASS = os.getenv('DB_PASS')
TABLE_NAME = os.getenv('TABLE_NAME', "seoul_land_info")
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.debug = True
logging.basicConfig(level=logging.INFO)

engine = create_engine(DB_URL)

# --- 3. [핵심] HTML 키 -> DB 컬럼명 통합 매핑 ---
# index.html의 data-col 값(좌측)을 실제 DB 컬럼명(우측)으로 연결
FILTER_MAPPING = {
    # [범위 검색용 매핑]
    '매매가': '매매가억',
    '공시지가': '공시지가',
    '입지': '입지',
    '긴급도': '긴급도',
    '대지면적': '대지면적',
    '연면적': '연면적',
    '건축면적': '건축면적',
    '용적률산정용연면적': '용적률산정용연면적', # DB컬럼명 확인 필요(같다면 생략 가능하나 명시 권장)
    '엘리베이터': '엘리베이터',
    '주차장': '주차장',
    '규모지상': '규모지상',
    '규모지하': '규모지하',
    '대수선 및 리모델링': '대수선및리모델링', 
    '사용승인일': '사용승인일',
    
    # [멀티 필터용 매핑]
    '지목명': '지목',
    '도로접면': '도로',
    '주용도코드명': '주용도',
    '형상': '형상',
    '용도지역': '용도지역'
}

# --- 4. 페이지 라우트 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_view():
    return render_template('map.html', client_id=NAVER_CLIENT_ID)

@app.route('/panorama')
def panorama_view():
    return render_template('panorama.html', client_id=NAVER_CLIENT_ID)


# --- 5. 데이터 조회 API (대대적 리팩토링) ---
@app.route('/api/get_data', methods=['POST'])
def get_data():
    req = request.json
    
    page = req.get('page', 1)
    limit = req.get('limit', 100)
    offset = (page - 1) * limit

    keyword = req.get('keyword', '').strip()
    
    # 리스트형 데이터 수신
    sigungu_list = req.get('sigungu', []) 
    bjd_list = req.get('bjd', [])
    bunji = (req.get('bunji') or '').strip()
    
    multi_filters = req.get('multi_filters', {}) 
    ranges = req.get('ranges', {})          # 숫자 + 리모델링일 등
    date_range = req.get('date_range', {})  # 사용승인일

    try:
        with engine.connect() as conn:
            where_clauses = []
            params = {}

            if keyword:
                # 검색어가 숫자로 끝나는 경우 (예: "601-1") -> 뒤에 숫자가 더 붙지 않는지 확인
                if keyword[-1].isdigit():
                    # PostgreSQL 정규식 연산자 '~' 사용
                    # ([^0-9]|$) 의미: 뒤에 '숫자가 아닌 문자'가 오거나 '문장의 끝'이어야 함
                    where_clauses.append('"통합주소" ~ :keyword_regex')
                    params['keyword_regex'] = f"{keyword}([^0-9]|$)"
                else:
                    # 숫자로 끝나지 않는 경우(예: "역삼동") -> 기존처럼 포함 검색
                    where_clauses.append('"통합주소" LIKE :keyword')
                    params['keyword'] = f"%{keyword}%"

            # 2. 시군구 (OR 조건)
            if sigungu_list:
                or_conds = []
                for idx, val in enumerate(sigungu_list):
                    key = f"sigungu_{idx}"
                    or_conds.append(f'"통합주소" LIKE :{key}')
                    params[key] = f"%{val}%"
                if or_conds:
                    where_clauses.append(f"({' OR '.join(or_conds)})")
            
            # 3. 법정동 (OR 조건)
            if bjd_list:
                or_conds = []
                for idx, val in enumerate(bjd_list):
                    key = f"bjd_{idx}"
                    or_conds.append(f'"통합주소" LIKE :{key}')
                    params[key] = f"%{val}%"
                if or_conds:
                    where_clauses.append(f"({' OR '.join(or_conds)})")

            # 4. 상세지번
            if bunji:
                # 주소가 해당 번지로 정확히 '끝나는지' 확인 (정규식 사용)
                # 예: " ... 역삼동 601-1" (O), " ... 역삼동 601-12" (X)
                where_clauses.append('"통합주소" ~ :bunji_exact')
                # (space) + 번지 + (문장끝) 조합
                params['bunji_exact'] = f" {bunji}$"

            # 5. 다중 필터 (지목, 용도지역 등)
            for key, values in multi_filters.items():
                if values:
                    # 매핑된 DB 컬럼명 사용 (없으면 키 그대로)
                    db_col = FILTER_MAPPING.get(key, key)
                    clean_values = [v.strip() for v in values if v.strip()]
                    
                    if clean_values:
                        or_conds = []
                        for idx, val in enumerate(clean_values):
                            p_key = f"multi_{key}_{idx}" # 파라미터 키 중복 방지
                            or_conds.append(f'"{db_col}" LIKE :{p_key}')
                            params[p_key] = f"%{val}%"
                        if or_conds:
                            where_clauses.append(f"({' OR '.join(or_conds)})")

            # 6. [핵심] 범위 검색 (숫자 & 날짜 혼합 처리)
            # ranges = {'매매가': {'min': 10}, '리모델링일': {'max': '2023-01-01'}, '입지': {'min': 3}}
            for col_key, val_dict in ranges.items():
                db_col = FILTER_MAPPING.get(col_key, col_key) # DB 컬럼명 변환
                
                # 최소값 (min) -> SQL: >= (이상)
                if 'min' in val_dict and val_dict['min'] is not None:
                    raw_val = val_dict['min']
                    p_min = f"min_{col_key}"
                    
                    # 날짜 문자열(하이픈 포함)인 경우 -> 문자열 비교
                    if isinstance(raw_val, str) and '-' in raw_val:
                        where_clauses.append(f'"{db_col}" >= :{p_min}')
                        params[p_min] = raw_val
                    else:
                        # 숫자형인 경우 -> CAST 후 비교 (안전장치 포함)
                        try:
                            where_clauses.append(f'CAST("{db_col}" AS FLOAT) >= :{p_min}')
                            params[p_min] = float(raw_val)
                        except:
                            # 변환 실패 시 문자열로 처리 (fallback)
                            where_clauses.append(f'"{db_col}" >= :{p_min}')
                            params[p_min] = raw_val

                # 최대값 (max) -> SQL: <= (이하)
                if 'max' in val_dict and val_dict['max'] is not None:
                    raw_val = val_dict['max']
                    p_max = f"max_{col_key}"
                    
                    if isinstance(raw_val, str) and '-' in raw_val:
                        where_clauses.append(f'"{db_col}" <= :{p_max}')
                        params[p_max] = raw_val
                    else:
                        try:
                            where_clauses.append(f'CAST("{db_col}" AS FLOAT) <= :{p_max}')
                            params[p_max] = float(raw_val)
                        except:
                            where_clauses.append(f'"{db_col}" <= :{p_max}')
                            params[p_max] = raw_val

            # 7. 사용승인일 검색 (HTML JS에서 별도 date_range로 보냄)
            if date_range:
                db_col = FILTER_MAPPING.get('사용승인일', '사용승인일')
                
                # HTML은 'YYYY-MM-DD'를 보냄. 
                # DB가 VARCHAR(8) 'YYYYMMDD'라면 하이픈 제거 필요.
                # DB가 DATE 타입이거나 'YYYY-MM-DD' 형식이면 그대로 사용.
                # (여기서는 안전하게 하이픈 제거 로직을 유지하되 옵션으로 둠)
                
                if date_range.get('start'):
                    # start_str = date_range['start'].replace('-', '') # DB 포맷에 맞춰 주석 해제/설정
                    start_str = date_range['start'] 
                    where_clauses.append(f'"{db_col}" >= :start_date')
                    params['start_date'] = start_str
                    
                if date_range.get('end'):
                    # end_str = date_range['end'].replace('-', '')
                    end_str = date_range['end']
                    where_clauses.append(f'"{db_col}" <= :end_date')
                    params['end_date'] = end_str

            # 쿼리 조합
            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)
            
            # 카운트 쿼리
            count_sql = f"SELECT COUNT(*) FROM {TABLE_NAME}" + where_sql
            total_count = conn.execute(text(count_sql), params).scalar()

            # 데이터 조회 (ctid 포함)
            data_sql = f"SELECT *, ctid FROM {TABLE_NAME}" + where_sql + " LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset

            result = conn.execute(text(data_sql), params)
            rows = result.mappings().all()

            return jsonify({
                "data": [dict(row) for row in rows],
                "total": total_count,
                "page": page,
                "limit": limit
            })

    except Exception as e:
        app.logger.error(f"SQL Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- 6. 데이터 업데이트 API (기존 로직 유지 + 보완) ---
@app.route('/api/update_data', methods=['POST'])
def update_data():
    data_list = request.json
    if not data_list: return jsonify({"error": "No data"}), 400
    try:
        with engine.begin() as conn:
            for row in data_list:
                ctid = row.pop('ctid', None)
                if not ctid: continue
                
                row.pop('통합주소', None) 
                
                # 매매가 수정 시 비율 자동 계산
                if '매매가억' in row:
                    try:
                        price_val = row.get('매매가억')
                        if isinstance(price_val, str):
                            price_val = price_val.replace(',', '').strip()
                        price = float(price_val) if price_val else 0.0

                        base_val = row.get('공시지가기준') # DB 컬럼명 확인
                        if isinstance(base_val, str):
                            base_val = base_val.replace(',', '').strip()
                        base_price = float(base_val) if base_val else 0.0
                        
                        if base_price > 0:
                            row['총공시지가와매매가비율'] = round((price / base_price) * 100, 2)
                        
                        row['매매가억'] = price
                    except:
                        pass # 계산 실패 시 기존 값 유지 혹은 0

                set_clauses = [f'"{k}" = :{k}' for k in row.keys()]
                if not set_clauses: continue

                query = text(f"UPDATE {TABLE_NAME} SET {', '.join(set_clauses)} WHERE ctid = :ctid")
                row['ctid'] = ctid
                conn.execute(query, row)
                
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"Update Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- 7. 위시리스트 관리 API ---
@app.route('/api/wishlist', methods=['GET', 'POST', 'DELETE'])
def manage_wishlist():
    try:
        if request.method == 'GET':
            with engine.connect() as conn:
                # 테이블 존재 여부 체크 생략 (에러 시 500 반환)
                result = conn.execute(text("SELECT * FROM wishlist ORDER BY created_at DESC"))
                rows = result.mappings().all()
                return jsonify({
                    row['address']: {
                        'color': row['color'], 
                        'group_name': row.get('group_name', '기본'),
                        'note': row.get('note', '') 
                    } for row in rows
                })
        elif request.method == 'POST':
            data = request.json
            with engine.begin() as conn:
                # 테이블 생성 (없을 경우)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS wishlist (
                        address VARCHAR(255) PRIMARY KEY,
                        color VARCHAR(50),
                        group_name VARCHAR(100),
                        note TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("""
                    INSERT INTO wishlist (address, color, group_name, note) 
                    VALUES (:addr, :col, :grp, :note)
                    ON CONFLICT (address) DO UPDATE 
                    SET color = :col, group_name = :grp, note = :note
                """), {
                    'addr': data.get('address'), 
                    'col': data.get('color', '#ffff00'), 
                    'grp': data.get('group_name', '기본'),
                    'note': data.get('note', '')
                })
            return jsonify({"status": "success"})
        elif request.method == 'DELETE':
            data = request.json
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM wishlist WHERE address = :addr"), {'addr': data.get('address')})
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 8. 컬럼 설정 저장 API ---
@app.route('/api/settings/columns', methods=['GET', 'POST'])
def column_settings():
    key = "column_order_v1"
    try:
        if request.method == 'POST':
            columns = request.json.get('columns')
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        setting_key VARCHAR(100) PRIMARY KEY,
                        setting_value TEXT
                    )
                """))
                conn.execute(text("""
                    INSERT INTO user_settings (setting_key, setting_value) VALUES (:key, :val)
                    ON CONFLICT (setting_key) DO UPDATE SET setting_value = :val
                """), {'key': key, 'val': json.dumps(columns)})
            return jsonify({"status": "success"})
        elif request.method == 'GET':
            with engine.connect() as conn:
                try:
                    result = conn.execute(text("SELECT setting_value FROM user_settings WHERE setting_key = :key"), {'key': key})
                    row = result.fetchone()
                    return jsonify(json.loads(row[0]) if row else [])
                except:
                    return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)