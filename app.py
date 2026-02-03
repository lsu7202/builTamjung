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
from sqlalchemy import inspect

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

import decimal  # 1. 파일 상단에 decimal 임포트 추가

class OrjsonProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        def default(item):
            # Decimal 객체를 발견하면 float으로 변환
            if isinstance(item, decimal.Decimal):
                return float(item)
            raise TypeError(f"Type {type(item)} not serializable")

        return orjson.dumps(
            obj, 
            default=default, # 이 부분이 핵심입니다.
            option=orjson.OPT_SERIALIZE_NUMPY
        ).decode('utf-8')

    def response(self, *args, **kwargs):
        obj = self._prepare_response_obj(args, kwargs) 
        
        def default(item):
            if isinstance(item, decimal.Decimal):
                return float(item)
            raise TypeError(f"Type {type(item)} not serializable")
            
        dumped_bytes = orjson.dumps(
            obj, 
            default=default, 
            option=orjson.OPT_SERIALIZE_NUMPY
        )
        
        return self._app.response_class(
            dumped_bytes, 
            mimetype="application/json"
        )

    def loads(self, s, **kwargs):
        return orjson.loads(s)

    

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
    
    # 1. 고유번호 (PNU) 처리 - 리스트 형태 대응 및 LIKE 절 적용
    pnu_input = filters.get('고유번호', [])
    
    # 입력값이 단일 값(문자열/딕셔너리)일 경우를 대비해 리스트로 변환
    if isinstance(pnu_input, (str, dict)):
        pnu_input = [pnu_input]
    
    pnu_conds = []
    if pnu_input:
        for idx, p in enumerate(pnu_input):
            # 딕셔너리 {'value': '...'} 또는 문자열에서 값 추출
            val = p.get('value', '') if isinstance(p, dict) else p
            if val and str(val).strip():
                p_key = f"pnu_idx_{idx}"
                # PNU 앞부분만으로도 검색 가능하도록 LIKE 사용 (전방 일치)
                pnu_conds.append(f'"고유번호" LIKE :{p_key}')
                params[p_key] = f"{str(val).strip()}%"
                
    # 여러 PNU 조건이 들어오면 OR로 묶음 (예: 역삼동 PNU OR 서초동 PNU)
    if pnu_conds:
        where_clauses.append(f"({' OR '.join(pnu_conds)})")

    # 2. 상세 조건 (multi_filters)
    multi_filters = filters.get('multi_filters', {})
    for key, values in multi_filters.items():
        if values:
            db_col = FILTER_MAPPING.get(key, key)
            clean_values = [v.strip() for v in values if v.strip()]
            if clean_values:
                or_conds = [f'"{db_col}" LIKE :multi_{key}_{idx}' for idx, val in enumerate(clean_values)]
                where_clauses.append(f"({' OR '.join(or_conds)})")
                for idx, val in enumerate(clean_values):
                    params[f'multi_{key}_{idx}'] = f"%{val}%"

    # 3. 범위 검색 (ranges)
    ranges = filters.get('ranges', {})
    sales_min = None
    sales_max = None
    for col_key, val_dict in ranges.items():
        if col_key == '매각일':
            sales_min = normalize_date(val_dict.get('min'))
            sales_max = normalize_date(val_dict.get('max'))
            continue

        db_col = FILTER_MAPPING.get(col_key, col_key)
        is_date_col = col_key in ['사용승인일', '대수선 및 리모델링']
        
        # MIN/MAX 처리 (기존 로직 유지)
        for bound in ['min', 'max']:
            if bound in val_dict and str(val_dict[bound]).strip():
                p_key = f"{bound}_{col_key.replace(' ', '_')}"
                raw_val = val_dict[bound]
                operator = ">=" if bound == 'min' else "<="
                
                if is_date_col:
                    where_clauses.append(f'"{db_col}" {operator} :{p_key}')
                    params[p_key] = normalize_date(raw_val)
                else:
                    try:
                        # 1. 일단 파이썬에서 숫자로 바꿉니다 (필터값 검증)
                        val_float = float(raw_val)
                        params[p_key] = val_float
                        
                        # 2. 성능 최적화 비교 로직
                        if bound == 'min' and val_float == 0:
                            # CAST 안 쓰고 컬럼 그대로 사용 (인덱스 활용)
                            # min이 0일 때만 NULL인 데이터를 포함시킴
                            where_clauses.append(f'("{db_col}" >= :{p_key} OR "{db_col}" IS NULL)')
                        else:
                            # 일반적인 경우에는 그냥 비교 (이것도 인덱스 탐)
                            where_clauses.append(f'"{db_col}" {operator} :{p_key}')
                            
                    except (ValueError, TypeError):
                        # 숫자가 아니면 어쩔 수 없이 원래 문자열대로 처리
                        where_clauses.append(f'"{db_col}" {operator} :{p_key}')
                        params[p_key] = raw_val

    # app.py 내 build_where_clause 함수의 매각 관련 로직 수정 (약 183행 부근)

    # 4. 매각일 및 매각 회수 복합 로직
    sales_count = filters.get('sales_count', 'all')
    if sales_min or sales_max or sales_count != 'all':
        sales_conds = []
        
        # [수정] 빈 문자열('') 대신 IS NOT NULL / IS NULL 사용
        if sales_count in ['1', '2', '3']:
            if sales_count == '3':
                # 3회 매각: 1, 2, 3 모두 존재
                sales_conds.append("(\"매각일1\" IS NOT NULL AND \"매각일2\" IS NOT NULL AND \"매각일3\" IS NOT NULL)")
            elif sales_count == '2':
                # 2회 매각: 1, 2는 있고 3은 없음
                sales_conds.append("(\"매각일1\" IS NOT NULL AND \"매각일2\" IS NOT NULL AND \"매각일3\" IS NULL)")
            elif sales_count == '1':
                # 1회 매각: 1만 있고 2, 3은 없음
                sales_conds.append("(\"매각일1\" IS NOT NULL AND \"매각일2\" IS NULL AND \"매각일3\" IS NULL)")
        
        if sales_min or sales_max:
            range_parts = []
            for col in ["매각일1", "매각일2", "매각일3"]:
                p_parts = []
                # [수정] DB 컬럼이 Integer이므로 비교 값을 int()로 변환하여 전달
                if sales_min:
                    p_parts.append(f'"{col}" >= :s_min')
                    params['s_min'] = int(sales_min) 
                if sales_max:
                    p_parts.append(f'"{col}" <= :s_max')
                    params['s_max'] = int(sales_max)
                range_parts.append(f"({' AND '.join(p_parts)})")
            sales_conds.append(f"({' OR '.join(range_parts)})")
        
        if sales_conds:
            where_clauses.append(f"({' AND '.join(sales_conds)})")

    # --- 핵심 변경 사항: 조건이 없으면 무조건 0건 반환 ---
    if where_clauses:
        return " WHERE " + " AND ".join(where_clauses)
    else:
        # PNU 포함 어떤 조건도 없을 경우 쿼리가 데이터를 찾지 못하도록 강제
        return " WHERE 1=0"



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

@app.route('/image')
def image_view():
    return render_template('image.html')

# --- API 1: 데이터 조회 (테이블 표시용) ---
@app.route('/api/get_data', methods=['POST'])
def get_data():
    req = request.json
    page = req.get('page', 1)
    limit = req.get('limit', 100)
    offset = (page - 1) * limit

    # 정렬 파라미터 추출 (기본값 '주소')
    sort_col = req.get('sort_column', '주소')
    sort_order = req.get('sort_order', 'ASC')
    
    params = {}
    where_sql = build_where_clause(req, params)

    # 정렬 SQL 생성
    if sort_col == '주소':
        # "고유번호"(PNU)는 본번과 부번이 0019, 0001 처럼 4자리 숫자로 채워져 있어
        # 사전식 정렬을 하더라도 결과적으로 숫자의 크기순(자연어 정렬)으로 정렬됩니다.
        # 시군구 및 법정동 코드도 포함되어 있어 지역별 그룹화 정렬도 동시에 해결됩니다.
        order_by_sql = 'ORDER BY "고유번호" ASC NULLS LAST'
    elif sort_col == '규모':
        order_by_sql = 'ORDER BY (COALESCE("규모지상", 0) + COALESCE("규모지하", 0)) DESC'
    else:
        db_col = FILTER_MAPPING.get(sort_col, sort_col)
        order_by_sql = f'ORDER BY "{db_col}" {sort_order} NULLS LAST'
    
    try:
        with engine.connect() as conn:
            # 전체 개수 확인
            count_sql = f"SELECT COUNT(*) FROM {TABLE_NAME}" + where_sql
            total_count = conn.execute(text(count_sql), params).scalar()

            # 정렬 및 페이징이 포함된 데이터 조회
            data_sql = f"""
                SELECT *, ctid 
                FROM {TABLE_NAME} 
                {where_sql} 
                {order_by_sql} 
                LIMIT :limit OFFSET :offset
            """
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

    # 필터 WHERE 절 생성 (조건 없으면 WHERE 1=0 반환됨)
    where_sql = build_where_clause(req, params)

    # 공간 검색 조건 결합
    spatial_cond = "geom && ST_MakeEnvelope(:minX, :minY, :maxX, :maxY, 4326)"
    
    # [수정] WHERE 절이 이미 존재하므로 AND로 결합
    final_sql = f"{where_sql} AND {spatial_cond}"

    sql_query = f"SELECT x, y, \"주소\" FROM {TABLE_NAME} {final_sql} LIMIT 3000"
    
    # --- [디버깅 로그] 터미널에서 확인 가능 ---
    app.logger.info("=== [MAP DATA QUERY] ===")
    app.logger.info(f"Generated SQL: {sql_query}")
    app.logger.info(f"Parameters: {params}")
    # ---------------------------------------

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query), params)
            points = [{"x": row[0], "y": row[1], "addr": row[2]} for row in result.fetchall()]
            return jsonify(points)
    except Exception as e:
        app.logger.error(f"Map Data SQL Error: {e}")
        return jsonify([]), 500

@app.route('/api/get_propDetail', methods=['POST'])   
def get_propDetail_data():
    req = request.json
    fulladdr = req.get('통합주소')

    if not fulladdr:
        return jsonify({"success": False, "message": "주소가 제공되지 않았습니다."}), 400

    # LIMIT 1을 제거하고 통합주소가 일치하는 모든 행을 가져옵니다.
    # 층별로 정렬(ORDER BY)을 추가하면 데이터 활용이 더 편리합니다.
    sql = text("""
        SELECT *
        FROM prop_details
        WHERE "통합주소" = :addr
        ORDER BY "층" ASC
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(sql, {"addr": fulladdr})
            # 모든 행을 가져옵니다.
            rows = result.fetchall()
            
            if rows:
                # 모든 행을 리스트 형태의 딕셔너리로 변환
                # - 사용자 제공 ppt_logic.js 내의 데이터 구조 참조
                data_list = [dict(row._mapping) for row in rows]
                return jsonify({
                    "success": True, 
                    "count": len(data_list),
                    "data": data_list
                })
            else:
                return jsonify({"success": False, "message": "해당 주소의 상세 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        print(f"Error fetching property details: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
            
    
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
    
    
def get_table_columns():
    """DB에서 실제 테이블의 컬럼 리스트를 가져오는 헬퍼 함수"""
    try:
        inspector = inspect(engine)
        return set(col['name'] for col in inspector.get_columns(TABLE_NAME))
    except Exception as e:
        app.logger.error(f"Error fetching columns: {e}")
        return set()

VALID_DB_COLUMNS = get_table_columns()

@app.route('/api/update_data', methods=['POST'])
def update_data():
    data_list = request.json
    if not data_list: return jsonify({"error": "No data"}), 400
    
    # 만약 서버 실행 중 테이블 구조가 바뀌었을 수 있으므로 
    # VALID_DB_COLUMNS가 비어있다면 다시 가져오게 할 수 있습니다.
    global VALID_DB_COLUMNS
    if not VALID_DB_COLUMNS:
        VALID_DB_COLUMNS = get_table_columns()

    try:
        with engine.begin() as conn:
            for row in data_list:
                ctid = row.pop('ctid', None)
                if not ctid: continue
                row.pop('통합주소', None) 
                
                # --- [추가/수정] 매매가 관련 계산 로직 유지 ---
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

                # --- [핵심 수정] DB에 실제 존재하는 컬럼만 필터링 ---
                # row의 키들 중 VALID_DB_COLUMNS에 있는 것만 추출
                filtered_row = {k: v for k, v in row.items() if k in VALID_DB_COLUMNS}
                
                if not filtered_row: continue

                # SET 구문 생성 (필터링된 결과 사용)
                set_clauses = [f'"{k}" = :{k}' for k in filtered_row.keys()]
                query = text(f"UPDATE {TABLE_NAME} SET {', '.join(set_clauses)} WHERE ctid = :ctid")
                
                # 쿼리 실행용 파라미터 구성
                params = filtered_row.copy()
                params['ctid'] = ctid
                
                conn.execute(query, params)
                
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"Update Data API Error: {e}")
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
    

# app.py 내 save_property API 수정
@app.route('/api/save_property', methods=['POST'])
def save_property():
    data = request.get_json()
    address = data.get('address')
    floors = data.get('floors')

    if not address:
        return jsonify({"error": "주소가 없습니다."}), 400

    try:
        with engine.begin() as conn: # engine.begin()은 자동 커밋을 지원합니다.
            # 1. 기존 이 주소로 등록된 매물 상세 정보를 모두 삭제 (새로 고침 방식)
            # 수동 추가 방식이므로, 기존 데이터를 지우고 현재 화면의 데이터를 넣는 것이 가장 깔끔합니다.
            conn.execute(text("DELETE FROM prop_details WHERE \"통합주소\" = :address"), {"address": address})

            # 2. 새로운 데이터 삽입
            if floors:
                insert_sql = text("""
                    INSERT INTO prop_details 
                    ("통합주소", "층", "형태", "평수", "보증금", "임대료", "월관리비", "임대차기간", "정렬층")
                    VALUES (:address, :floor, :type, :area, :security, :rent, :management, :lease_period, NULL)
                """)
                
                for item in floors:
                    conn.execute(insert_sql, {
                        "address": address,
                        "floor": item['floor'],
                        "type": item['type'],
                        "area": item['area'] or 0,
                        "security": item['security'] or 0,
                        "rent": item['rent'] or 0,
                        "management": item['management'] or 0,
                        "lease_period": item['lease_period'] or ""
                    })

        return jsonify({"status": "success", "message": "성공적으로 저장되었습니다."}), 200

    except Exception as e:
        app.logger.error(f"Save Property Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)