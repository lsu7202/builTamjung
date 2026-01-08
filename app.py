import os, re
import logging
import json
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from flask_compress import Compress  # 추가: Gzip 압축
from flask.json.provider import JSONProvider
import orjson
from flask_migrate import Migrate
from models import db
from dotenv import load_dotenv

load_dotenv()

# --- 1. 네이버 API 및 DB 설정 ---
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET')

# 도커 내부 통신용 DB 설정
DB_USER = os.getenv('DB_USER', 'iseung-ug')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST', "localhost") 
DB_PORT = os.getenv('DB_PORT', "5432")
DB_NAME = os.getenv('DB_NAME', "postgres")
TABLE_NAME = os.getenv('TABLE_NAME', "seoul_land_info")

# SQLAlchemy 연결 URL
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
Compress(app)
db.init_app(app)  # Flask 앱과 SQLAlchemy 연결
migrate = Migrate(app, db)  # Flask-Migrate와 앱, DB 연결

class OrjsonProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        # orjson.dumps는 bytes를 반환하므로 decode가 필요할 수 있음
        return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY).decode('utf-8')

    def loads(self, s, **kwargs):
        return orjson.loads(s)

    # 이 메서드가 없어서 에러가 발생한 것입니다!
    def response(self, *args, **kwargs):
        """jsonify()가 호출될 때 실제 HTTP 응답 객체를 만드는 부분입니다."""
        # 중요: 아래 줄에서 *와 **를 모두 제거해야 합니다.
        obj = self._prepare_response_obj(args, kwargs) 
        
        # 성능을 위해 bytes 상태 그대로 응답 객체에 전달합니다.
        dumped_bytes = orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY)
        
        return self._app.response_class(
            dumped_bytes, 
            mimetype="application/json"
        )

app.json = OrjsonProvider(app)
app.config['JSON_AS_ASCII'] = False
app.debug = True
logging.basicConfig(level=logging.INFO)

# DB 엔진 생성
engine = create_engine(
    DB_URL,
    pool_size=20,            # 기본 유지 연결 수 (기본값 5에서 확장)
    max_overflow=40,         # 필요 시 추가로 생성할 최대 연결 수
    pool_timeout=30,         # 연결을 기다리는 최대 시간
    pool_recycle=1800,       # 30분마다 연결 재설정 (DB 연결 끊김 방지)
    pool_pre_ping=True       # 연결 유효성 자동 체크
)

# --- 필터 매핑 상수 ---
FILTER_MAPPING = {
    '매매가': '매매가억',
    '공시지가': '공시지가',
    '입지': '입지',
    '긴급도': '긴급도',
    '대지면적': '대지면적',
    '연면적': '연면적',
    '건축면적': '건축면적',
    '용적률산정용연면적': '용적률산정용연면적',
    '엘리베이터': '엘리베이터',
    '주차장': '주차장',
    '규모지상': '규모지상',
    '규모지하': '규모지하',
    '대수선 및 리모델링': '대수선및리모델링', 
    '사용승인일': '사용승인일',
    '지목명': '지목',
    '도로접면': '도로',
    '주용도코드명': '주용도',
    '형상': '형상',
    '용도지역': '용도지역'
}

# --- [추가] 날짜 입력 정규화 헬퍼 함수 ---
def normalize_date(val):
    if not val: return None
    # 숫자만 추출
    s = re.sub(r'[^0-9]', '', str(val))
    if len(s) == 4: return s + "0101"  # 2023 -> 20230101
    if len(s) == 6: return s + "01"    # 202305 -> 20230501
    return s

# --- 헬퍼 함수: 필터 조건을 SQL WHERE절로 변환 ---
def build_where_clause(filters, params):
    where_clauses = []
    
    keyword = filters.get('keyword', '').strip()
    sigungu_list = filters.get('sigungu', [])
    bjd_list = filters.get('bjd', [])
    bunji = filters.get('bunji', '').strip()
    multi_filters = filters.get('multi_filters', {})
    ranges = filters.get('ranges', {})
    # sales_count 수집
    sales_count = filters.get('sales_count', 'all')
    sales_min = None
    sales_max = None

    if keyword:
        address_chunks = re.findall(r'[가-힣0-9A-Za-z]+\s+\d+(?:-\d+)?', keyword)

        if address_chunks:
            addr_conds = []
            for i, addr in enumerate(address_chunks):
                p_name = f"multi_addr_{i}"
                
                escaped_addr = re.escape(addr.strip())
                flexible_addr = escaped_addr.replace(r'\ ', r'\s+')
                
                addr_conds.append(f'"통합주소" ~ :{p_name}')

                params[p_name] = f"(^|[^0-9]){flexible_addr}([^0-9-]|\Z)"
            
            where_clauses.append(f"({' OR '.join(addr_conds)})")

    # 2. 지역
    if sigungu_list:
        or_conds = [f'"통합주소" LIKE :si_{i}' for i, v in enumerate(sigungu_list)]
        where_clauses.append(f"({' OR '.join(or_conds)})")
        for i, v in enumerate(sigungu_list): params[f'si_{i}'] = f"%{v}%"

    if bjd_list:
        or_conds = [f'"통합주소" LIKE :bjd_{i}' for i, v in enumerate(bjd_list)]
        where_clauses.append(f"({' OR '.join(or_conds)})")
        for i, v in enumerate(bjd_list): params[f'bjd_{i}'] = f"%{v}%"

    # 3. 번지
    if bunji:
        where_clauses.append('"통합주소" ~ :bunji_exact')
        params['bunji_exact'] = f" {bunji}$"

    # 4. 상세 조건
    for key, values in multi_filters.items():
        if values:
            db_col = FILTER_MAPPING.get(key, key)
            clean_values = [v.strip() for v in values if v.strip()]
            if clean_values:
                or_conds = [f'"{db_col}" LIKE :multi_{key}_{idx}' for idx, val in enumerate(clean_values)]
                where_clauses.append(f"({' OR '.join(or_conds)})")
                for idx, val in enumerate(clean_values):
                    params[f'multi_{key}_{idx}'] = f"%{val}%"

    # 5. 범위 검색 (날짜 자동 보정 및 매각일 특수 처리 포함)
    for col_key, val_dict in ranges.items():
        if col_key == '매각일':
            sales_min = normalize_date(val_dict.get('min'))
            sales_max = normalize_date(val_dict.get('max'))
            continue

        db_col = FILTER_MAPPING.get(col_key, col_key)
        is_date_col = col_key in ['사용승인일', '대수선 및 리모델링']
        
        # MIN (이상)
        if 'min' in val_dict and str(val_dict['min']).strip():
            p_min = f"min_{col_key.replace(' ', '_')}"
            raw_val = val_dict['min']
            if is_date_col:
                where_clauses.append(f'"{db_col}" >= :{p_min}')
                params[p_min] = normalize_date(raw_val)
            else:
                try:
                    where_clauses.append(f'CAST(NULLIF("{db_col}", \'\') AS FLOAT) >= :{p_min}')
                    params[p_min] = float(raw_val)
                except:
                    where_clauses.append(f'"{db_col}" >= :{p_min}')
                    params[p_min] = raw_val
        
        # MAX (이하)
        if 'max' in val_dict and str(val_dict['max']).strip():
            p_max = f"max_{col_key.replace(' ', '_')}"
            raw_val = val_dict['max']
            if is_date_col:
                where_clauses.append(f'"{db_col}" <= :{p_max}')
                params[p_max] = normalize_date(raw_val)
            else:
                try:
                    where_clauses.append(f'CAST(NULLIF("{db_col}", \'\') AS FLOAT) <= :{p_max}')
                    params[p_max] = float(raw_val)
                except:
                    where_clauses.append(f'"{db_col}" <= :{p_max}')
                    params[p_max] = raw_val

    # 6. 매각일 및 매각 회수 복합 로직
    if sales_min or sales_max or sales_count != 'all':
        sales_conds = []
        # 회수 필터링 (1, 2, 3회)
        if sales_count == '3':
            sales_conds.append("(\"매각일1\" != '' AND \"매각일2\" != '' AND \"매각일3\" != '')")
        elif sales_count == '2':
            sales_conds.append("(\"매각일1\" != '' AND \"매각일2\" != '' AND (\"매각일3\" = '' OR \"매각일3\" IS NULL))")
        elif sales_count == '1':
            sales_conds.append("(\"매각일1\" != '' AND (\"매각일2\" = '' OR \"매각일2\" IS NULL) AND (\"매각일3\" = '' OR \"매각일3\" IS NULL))")
        
        # 매각일 범위 (OR 조건: 1, 2, 3 중 하나라도 걸리면 조회)
        if sales_min or sales_max:
            range_parts = []
            for col in ["매각일1", "매각일2", "매각일3"]:
                p_parts = []
                if sales_min:
                    p_parts.append(f'"{col}" >= :s_min'); params['s_min'] = sales_min
                if sales_max:
                    p_parts.append(f'"{col}" <= :s_max'); params['s_max'] = sales_max
                range_parts.append(f"({' AND '.join(p_parts)})")
            sales_conds.append(f"({' OR '.join(range_parts)})")
        
        if sales_conds:
            where_clauses.append(f"({' AND '.join(sales_conds)})")

    return " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

# --- 라우트 정의 ---

@app.route('/')
def index():
    return render_template('index.html', client_id=NAVER_CLIENT_ID)

@app.route('/map')
def map_view():
    return render_template('map.html', client_id=NAVER_CLIENT_ID)

@app.route('/panorama')
def panorama_view():
    return render_template('panorama.html', client_id=NAVER_CLIENT_ID)

# --- API 1: 데이터 조회 (테이블 표시용) ---
@app.route('/api/get_data', methods=['POST'])
def get_data():
    req = request.json
    page = req.get('page', 1)
    limit = req.get('limit', 100)
    offset = (page - 1) * limit
    
    params = {}
    where_sql = build_where_clause(req, params)
    
    try:
        with engine.connect() as conn:
            # 총 개수
            count_sql = f"SELECT COUNT(*) FROM {TABLE_NAME}" + where_sql
            total_count = conn.execute(text(count_sql), params).scalar()

            # 데이터 조회
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
    
# app.py 내 get_map_data API 부분 수정
@app.route('/api/get_map_data', methods=['POST'])
def get_map_data():
    req = request.json
    bounds = req.get('bounds')
    if not bounds: return jsonify([])

    params = {
        "minX": bounds['minX'], "maxX": bounds['maxX'],
        "minY": bounds['minY'], "maxY": bounds['maxY']
    }

    # 1. 기존 필터(매매가, 면적 등) WHERE 절 생성
    # build_where_clause 함수는 이미 app.py 상단에 정의되어 있음
    where_sql = build_where_clause(req, params)

    # 2. 공간 검색 조건(Bounds) 추가
    spatial_cond = "geom && ST_MakeEnvelope(:minX, :minY, :maxX, :maxY, 4326)"
    
    if where_sql:
        # 이미 WHERE가 있으면 AND로 결합
        final_sql = f"{where_sql} AND {spatial_cond}"
    else:
        # 필터가 없으면 WHERE 공간조건만
        final_sql = f" WHERE {spatial_cond}"

    # 3. 쿼리 실행 (성능을 위해 필요한 컬럼만 추출, LIMIT 상향)
    sql = text(f"""
        SELECT "x", "y", "통합주소" 
        FROM {TABLE_NAME} 
        {final_sql}
        LIMIT 3000 
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(sql, params)
            points = [{"x": row[0], "y": row[1], "addr": row[2]} for row in result.fetchall()]
            return jsonify(points)
    except Exception as e:
        app.logger.error(f"Map Filter API Error: {e}")
        return jsonify([]), 500
    
# app.py 의 해당 API 부분 수정
@app.route('/api/bulk_update_sales_by_address', methods=['POST'])
def bulk_update_sales_by_address():
    data_list = request.json
    if not data_list:
        return jsonify({"error": "데이터가 없습니다."}), 400

    CHUNK_SIZE = 500 
    total_updated = 0
    missing_addresses = [] # 누락된 주소를 담을 리스트

    try:
        for i in range(0, len(data_list), CHUNK_SIZE):
            chunk = data_list[i : i + CHUNK_SIZE]
            chunk_addrs = [item.get('통합주소') for item in chunk if item.get('통합주소')]

            # 1. 현재 청크의 주소들 중 DB에 존재하는 주소 확인
            with engine.connect() as conn:
                check_query = text(f'SELECT DISTINCT "통합주소" FROM {TABLE_NAME} WHERE "통합주소" IN :addr_list')
                result = conn.execute(check_query, {"addr_list": tuple(chunk_addrs)})
                existing_addrs = {row[0] for row in result.fetchall()}

            # 2. DB에 없는 주소들 추출
            for addr in chunk_addrs:
                if addr not in existing_addrs:
                    missing_addresses.append(addr)

            # 3. 존재하는 데이터에 대해서만 업데이트 실행 (기존 로직)
            # (중략: 기존 UPDATE 쿼리 로직 동일하게 유지)
            query = text(f"""
                UPDATE {TABLE_NAME} AS t
                SET "매각일1" = v.m_date1, "매각액1" = v.m_price1,
                    "매각일2" = v.m_date2, "매각액2" = v.m_price2,
                    "매각일3" = v.m_date3, "매각액3" = v.m_price3
                FROM (VALUES 
                    {", ".join([f"(:addr_{j}, :d1_{j}, :p1_{j}, :d2_{j}, :p2_{j}, :d3_{j}, :p3_{j})" for j in range(len(chunk))])}
                ) AS v(address, m_date1, m_price1, m_date2, m_price2, m_date3, m_price3)
                WHERE t."통합주소" = v.address;
            """)

            params = {}
            for j, item in enumerate(chunk):
                params[f'addr_{j}'] = item.get('통합주소')
                params[f'd1_{j}'] = item.get('매각일1', '')
                params[f'p1_{j}'] = item.get('매각액1', '')
                params[f'd2_{j}'] = item.get('매각일2', '')
                params[f'p2_{j}'] = item.get('매각액2', '')
                params[f'd3_{j}'] = item.get('매각일3', '')
                params[f'p3_{j}'] = item.get('매각액3', '')

            with engine.begin() as conn:
                result = conn.execute(query, params)
                total_updated += result.rowcount

        return jsonify({
            "status": "success",
            "message": f"총 {len(data_list)}개 요청 중 {total_updated}개 행 업데이트 완료",
            "missing_count": len(missing_addresses),
            "missing_addresses": missing_addresses # 누락된 리스트 반환
        })

    except Exception as e:
        app.logger.error(f"Bulk Update Error: {e}")
        return jsonify({"error": str(e)}), 500
# --- API 2: 대기열용 전체 주소 조회 (중복 제거) ---
@app.route('/api/get_all_addresses', methods=['POST'])
def get_all_addresses():
    req = request.json
    params = {}
    where_sql = build_where_clause(req, params)
    
    try:
        with engine.connect() as conn:
            # 통합주소만 중복 없이 조회
            sql = f"SELECT DISTINCT \"통합주소\" FROM {TABLE_NAME}" + where_sql
            result = conn.execute(text(sql), params)
            # 리스트 형태로 반환
            addresses = [row[0] for row in result.fetchall()]
            return jsonify(addresses)
    except Exception as e:
        app.logger.error(f"Fetch All Address Error: {e}")
        return jsonify({"error": str(e)}), 500

# [추가] 한글 금액 문자열("2억 9,122만")을 숫자(2.9122)로 변환하는 함수
def parse_korean_money_to_float(price_str):
    if not price_str or price_str in ["null", "Error", "SearchFail"]:
        return 0.0
    
    try:
        # 1. 공백 및 콤마 제거
        clean_str = price_str.replace(',', '').replace(' ', '')
        
        # 2. '억'과 '만' 단위 처리
        eok_val = 0
        man_val = 0
        
        if '억' in clean_str:
            parts = clean_str.split('억')
            eok_part = parts[0]
            if eok_part:
                eok_val = float(eok_part)
            
            if len(parts) > 1 and parts[1]:
                man_part = parts[1].replace('만', '')
                if man_part:
                    man_val = float(man_part)
        else:
            if '만' in clean_str:
                man_part = clean_str.replace('만', '')
                if man_part:
                    man_val = float(man_part)
            else:
                return float(clean_str)

        # 3. 합산 (만 단위는 0.0001억)
        result = eok_val + (man_val * 0.0001)
        return round(result, 4) 

    except Exception as e:
        print(f"Money Parse Error: {price_str} -> {e}")
        return 0.0


# --- API 3: [수정됨] 주소 기준 AI추정가 일괄 업데이트 ---
@app.route('/api/update_price_by_address', methods=['POST'])
def update_price_by_address():
    data_list = request.json  # 예: [{"통합주소": "...", "AI추정가": 7606720000}, ...]
    if not data_list: return jsonify({"error": "No data"}), 400
    
    try:
        query = text(f"""
            UPDATE {TABLE_NAME} 
            SET "AI추정가" = CAST(:AI추정가 AS TEXT),
                "AI추정가매매가비율" = CASE 
                    WHEN "매매가억" IS NOT NULL AND "매매가억" != ''
                         AND CAST(NULLIF(REGEXP_REPLACE("매매가억", '[^0-9.]', '', 'g'), '') AS NUMERIC) > 0 
                    THEN ROUND(
                        -- (원 단위 정수 / 100,000,000) 하여 '억' 단위로 맞춘 후 비율 계산
                        (CAST(:AI추정가 AS NUMERIC) / 100000000) / 
                        CAST(NULLIF(REGEXP_REPLACE("매매가억", '[^0-9.]', '', 'g'), '') AS NUMERIC) * 100
                    , 2)
                    ELSE "AI추정가매매가비율"
                END
            WHERE "통합주소" = :통합주소
        """)

        with engine.begin() as conn:
            result = conn.execute(query, data_list)
            updated_count = result.rowcount
                
        return jsonify({"status": "success", "updated_rows": updated_count})
    except Exception as e:
        app.logger.error(f"Bulk Update Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- API 4: 기존 데이터 업데이트 (그리드 수정용) ---
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
                
                if '매매가억' in row:
                    try:
                        price_val = str(row.get('매매가억')).replace(',', '').strip()
                        price = float(price_val) if price_val else 0.0
                        base_val = str(row.get('공시지가기준') or '').replace(',', '').strip()
                        base_price = float(base_val) if base_val else 0.0
                        if base_price > 0:
                            row['총공시지가와매매가비율'] = round((price / base_price) * 100, 2)
                        row['매매가억'] = price
                    except: pass

                set_clauses = [f'"{k}" = :{k}' for k in row.keys()]
                if not set_clauses: continue
                query = text(f"UPDATE {TABLE_NAME} SET {', '.join(set_clauses)} WHERE ctid = :ctid")
                row['ctid'] = ctid
                conn.execute(query, row)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API 5: 위시리스트 관리 ---
@app.route('/api/wishlist', methods=['GET', 'POST', 'DELETE'])
def manage_wishlist():
    try:
        if request.method == 'GET':
            with engine.connect() as conn:
                result = conn.execute(text("SELECT * FROM wishlist ORDER BY created_at DESC"))
                rows = result.mappings().all()
                return jsonify({row['address']: {'color': row['color'], 'group_name': row.get('group_name', '기본'), 'note': row.get('note', '')} for row in rows})
        elif request.method == 'POST':
            data = request.json
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS wishlist (address VARCHAR(255) PRIMARY KEY, color VARCHAR(50), group_name VARCHAR(100), note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                conn.execute(text("INSERT INTO wishlist (address, color, group_name, note) VALUES (:addr, :col, :grp, :note) ON CONFLICT (address) DO UPDATE SET color = :col, group_name = :grp, note = :note"), 
                             {'addr': data.get('address'), 'col': data.get('color', '#ffff00'), 'grp': data.get('group_name', '기본'), 'note': data.get('note', '')})
            return jsonify({"status": "success"})
        elif request.method == 'DELETE':
            data = request.json
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM wishlist WHERE address = :addr"), {'addr': data.get('address')})
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API 6: 컬럼 설정 ---
@app.route('/api/settings/columns', methods=['GET', 'POST'])
def column_settings():
    key = "column_order_v1"
    try:
        if request.method == 'POST':
            columns = request.json.get('columns')
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS user_settings (setting_key VARCHAR(100) PRIMARY KEY, setting_value TEXT)"))
                conn.execute(text("INSERT INTO user_settings (setting_key, setting_value) VALUES (:key, :val) ON CONFLICT (setting_key) DO UPDATE SET setting_value = :val"), {'key': key, 'val': json.dumps(columns)})
            return jsonify({"status": "success"})
        elif request.method == 'GET':
            with engine.connect() as conn:
                result = conn.execute(text("SELECT setting_value FROM user_settings WHERE setting_key = :key"), {'key': key})
                row = result.fetchone()
                return jsonify(json.loads(row[0]) if row else [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/get_building_history', methods=['POST'])
def get_building_history():
    """주소 리스트를 받아 사용승인일과 대수선 정보를 반환"""
    req = request.json
    addresses = req.get('addresses', [])
    
    if not addresses:
        return jsonify({})

    try:
        with engine.connect() as conn:
            # 주소 리스트를 SQL IN 절에 넣기 위해 튜플화
            query = text(f"""
                SELECT "통합주소", "사용승인일", "대수선및리모델링" 
                FROM {TABLE_NAME} 
                WHERE "통합주소" IN :addr_list
            """)
            result = conn.execute(query, {"addr_list": tuple(addresses)})
            
            # { "주소": {"사용승인일": "...", "대수선": "..."}, ... } 형식으로 변환
            history_map = {
                row[0]: {
                    "사용승인일": row[1], 
                    "대수선및리모델링": row[2]
                } for row in result.fetchall()
            }
            return jsonify(history_map)
    except Exception as e:
        app.logger.error(f"Remote DB Fetch Error: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/floors', methods=['POST'])
def get_floors():
    """주소를 받아 규모지하와 규모지상을 반환"""
    req = request.json
    address = req.get('address')
    
    if not address:
        return jsonify({"error": "주소가 제공되지 않았습니다."}), 400

    try:
        with engine.connect() as conn:
            # 1. SQL 쿼리 작성 (규모지하, 규모지상 컬럼 조회)
            query = text(f"""
                SELECT "규모지하", "규모지상" 
                FROM {TABLE_NAME} 
                WHERE "통합주소" = :address 
                LIMIT 1
            """)
            
            result = conn.execute(query, {"address": address}).fetchone()
            
            if result:
                # result[0]은 규모지하, result[1]은 규모지상 (SELECT 절 순서)
                return jsonify({
                    "status": "success",
                    "address": address,
                    "underground_floors": result[0],
                    "aboveground_floors": result[1]
                })
            else:
                return jsonify({"error": "해당 주소의 정보를 찾을 수 없습니다."}), 404
                
    except Exception as e:
        app.logger.error(f"Fetch Floor Info Error: {e}")
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)