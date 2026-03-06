import os, re, datetime
import logging
import json
# app.py 상단 임포트 부분
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from sqlalchemy import create_engine, text
from flask_compress import Compress  # 추가: Gzip 압축
from flask.json.provider import JSONProvider
import orjson
from flask_migrate import Migrate
from models import db, Users, Team, PropMemo, PropMain, SeoulLandInfo, UserSetting, setup_db_triggers
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
app.secret_key = 'builtamjung_secret_key_1234'

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

with app.app_context():
    try:
        setup_db_triggers(engine)
        logging.info("DB 트리거가 성공적으로 설정되었습니다.")
    except Exception as e:
        logging.error(f"DB 트리거 설정 중 오류 발생: {e}")

# --- 필터 매핑 상수 ---
FILTER_MAPPING = {
    '매매가': '매매가',
    '공시지가': '공시지가',
    '입지': '입지',
    '긴급도': '긴급도',
    '대지면적': '대지면적',
    '연면적': '연면적',
    '건축면적': '건축면적',
    '용적률산정용연면적': '용적률산정연면적',
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
    
    # 1. 고유번호 (PNU) 처리 - 조인 시 모호성 방지를 위해 L. 붙임
    pnu_input = filters.get('고유번호', [])
    if isinstance(pnu_input, (str, dict)):
        pnu_input = [pnu_input]
    
    pnu_conds = []
    if pnu_input:
        for idx, p in enumerate(pnu_input):
            val = p.get('value', '') if isinstance(p, dict) else p
            if val and str(val).strip():
                p_key = f"pnu_idx_{idx}"
                pnu_conds.append(f'L."고유번호" LIKE :{p_key}') # 테이블 별칭 L 적용
                params[p_key] = f"{str(val).strip()}%"
                
    if pnu_conds:
        where_clauses.append(f"({' OR '.join(pnu_conds)})")

    # 2. 상세 조건 (multi_filters)
    multi_filters = filters.get('multi_filters', {})
    for key, values in multi_filters.items():
        if values:
            db_col = FILTER_MAPPING.get(key, key)
            clean_values = [v.strip() for v in values if v.strip()]
            if clean_values:
                or_conds = [f'L."{db_col}" LIKE :multi_{key}_{idx}' for idx, val in enumerate(clean_values)]
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
        
        for bound in ['min', 'max']:
            if bound in val_dict and str(val_dict[bound]).strip():
                p_key = f"{bound}_{col_key.replace(' ', '_')}"
                raw_val = val_dict[bound]
                operator = ">=" if bound == 'min' else "<="
                
                if is_date_col:
                    where_clauses.append(f'L."{db_col}" {operator} :{p_key}')
                    params[p_key] = normalize_date(raw_val)
                else:
                    try:
                        val_float = float(raw_val)
                        params[p_key] = val_float
                        if bound == 'min' and val_float == 0:
                            where_clauses.append(f'(L."{db_col}" >= :{p_key} OR L."{db_col}" IS NULL)')
                        else:
                            where_clauses.append(f'L."{db_col}" {operator} :{p_key}')
                    except (ValueError, TypeError):
                        where_clauses.append(f'L."{db_col}" {operator} :{p_key}')
                        params[p_key] = raw_val

    # 4. 매각일 및 매각 회수 복합 로직
    sales_count = filters.get('sales_count', 'all')
    if sales_min or sales_max or sales_count != 'all':
        sales_conds = []
        if sales_count in ['1', '2', '3']:
            if sales_count == '3':
                sales_conds.append("(L.\"매각일1\" IS NOT NULL AND L.\"매각일2\" IS NOT NULL AND L.\"매각일3\" IS NOT NULL)")
            elif sales_count == '2':
                sales_conds.append("(L.\"매각일1\" IS NOT NULL AND L.\"매각일2\" IS NOT NULL AND L.\"매각일3\" IS NULL)")
            elif sales_count == '1':
                sales_conds.append("(L.\"매각일1\" IS NOT NULL AND L.\"매각일2\" IS NULL AND L.\"매각일3\" IS NULL)")
        
        if sales_min or sales_max:
            range_parts = []
            for col in ["매각일1", "매각일2", "매각일3"]:
                p_parts = []
                if sales_min:
                    p_parts.append(f'L."{col}" >= :s_min')
                    params['s_min'] = int(sales_min) 
                if sales_max:
                    p_parts.append(f'L."{col}" <= :s_max')
                    params['s_max'] = int(sales_max)
                range_parts.append(f"({' AND '.join(p_parts)})")
            sales_conds.append(f"({' OR '.join(range_parts)})")
        
        if sales_conds:
            where_clauses.append(f"({' AND '.join(sales_conds)})")

    if where_clauses: return " WHERE " + " AND ".join(where_clauses)
    else: return " WHERE 1=0"



# --- 라우트 정의 ---

@app.route('/')
def index():
    return render_template('index.html', client_id=NAVER_CLIENT_ID)

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/image')
def image_view():
    return render_template('image.html')

# --- API 1: 데이터 조회 (테이블 표시용) ---
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
    # build_where_clause 내부에서 이미 L."고유번호"와 같이 L 별칭을 사용함
    where_sql = build_where_clause(req, params)

    # [수정] 정렬 SQL에서 모든 컬럼에 테이블 접두사 명시 (AmbiguousColumn 오류 해결)
    if sort_col == '주소':
        order_by_sql = 'ORDER BY L."고유번호" ASC NULLS LAST'
    elif sort_col == '규모':
        # 기존 규모 정렬 로직 유지하되 접두사 L 추가
        order_by_sql = 'ORDER BY (COALESCE(L."규모지상", 0) + COALESCE(L."규모지하", 0)) DESC'
    else:
        db_col = FILTER_MAPPING.get(sort_col, sort_col)
        # PropMain 소속인지 확인하여 정렬 기준 설정
        prop_cols = {c.name for c in PropMain.__table__.columns}
        prefix = "P" if db_col in prop_cols else "L"
        order_by_sql = f'ORDER BY {prefix}."{db_col}" {sort_order} NULLS LAST'
    
    try:
        with engine.connect() as conn:
            # 전체 개수 확인 (JOIN 불필요하므로 기존 로직 유지하되 L 별칭 추가)
            count_sql = f"SELECT COUNT(*) FROM {TABLE_NAME} L" + where_sql
            total_count = conn.execute(text(count_sql), params).scalar()

            # [핵심] LEFT JOIN 쿼리 (FROM seoul_land_info L 로 별칭 부여)
            data_sql = f"""
                SELECT L.*, P.*, L."고유번호" as "pnu_key"
                FROM {TABLE_NAME} L
                LEFT JOIN prop_main P ON L."고유번호" = P."고유번호"
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

    # 필터 WHERE 절 생성 (L. 별칭 사용됨)
    where_sql = build_where_clause(req, params)

    # [수정] 공간 검색 조건에도 L. 접두사 적용하여 모호성 제거
    spatial_cond = "L.geom && ST_MakeEnvelope(:minX, :minY, :maxX, :maxY, 4326)"
    
    final_sql = f"{where_sql} AND {spatial_cond}"

    # [수정] FROM {TABLE_NAME} 뒤에 L 별칭 추가 (UndefinedTable 오류 해결)
    sql_query = f"SELECT L.x, L.y, L.\"주소\" FROM {TABLE_NAME} L {final_sql} LIMIT 3000"
    
    app.logger.info("=== [MAP DATA QUERY] ===")
    app.logger.info(f"Generated SQL: {sql_query}")
    app.logger.info(f"Parameters: {params}")

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query), params)
            points = [{"x": row[0], "y": row[1], "addr": row[2]} for row in result.fetchall()]
            return jsonify(points)
    except Exception as e:
        app.logger.error(f"Map Data SQL Error: {e}")
        return jsonify([]), 500

from sqlalchemy import func

@app.route('/api/get_prop_main', methods=['GET'])
def get_prop_main():
    pnu = request.args.get('고유번호')
    if not pnu:
        return jsonify({"message": "PNU가 필요합니다."}), 400

    prop = PropMain.query.filter_by(pnu=pnu).first()
    
    # 일치하는 데이터가 없는 경우
    if not prop:
        # DB에서 현재 가장 큰 ID 값을 가져옴 (없으면 0)
        max_id = db.session.query(func.max(PropMain.id)).scalar() or 0
        next_id = max_id + 1
        
        return jsonify({
            "success": True, 
            "data": {
                "매물번호": next_id, # 새로 추가될 때 부여될 번호
                "고유번호": pnu,
                "신규등록": True # 프론트엔드에서 신규 여부를 판단하기 위한 플래그
            },
            "message": "등록된 정보가 없어 신규 번호를 할당했습니다."
        }), 200

    # 기존 데이터가 있는 경우 (모델 필드명을 한글 키값으로 매핑)
    result = {
        "매물번호": prop.id,
        "고유번호": prop.pnu,
        "담당자": prop.manager_Id,
        "진행상태": prop.progress,
        "매매가": float(prop.sale_price_billon) if prop.sale_price_billon else None,
        "대지면적평단가": float(prop.sale_price_by_land_area) if prop.sale_price_by_land_area else None,
        "연면적평단가": float(prop.sale_price_by_floor_area) if prop.sale_price_by_floor_area else None,
        "총보증금": float(prop.total_security) if prop.total_security else None,
        "총월세부가세별도": float(prop.total_monthly_rent) if prop.total_monthly_rent else None,
        "총관리비": float(prop.total_management_fee) if prop.total_management_fee else None,
        "수익률": prop.yield_rate,
        "공실제외수익률": prop.except_empty_yield,
        "자기자본수익률": prop.self_yield,
        "자기자본": prop.invest_cash,
        "이자율": prop.loan_rate,
        "긴급도": prop.urgency,
        "등급": prop.grade,
        "입지": prop.location_quality,
        "건물용도": prop.building_usage,
        "사진": prop.photo,
        "브리핑": prop.briefing,
        "명도": prop.eviction,
        "멸실": prop.demolition,
        "용도변경": prop.usage_change,
        "소유자타입": prop.ownertype,
        "소유자명": prop.owner_name,
        "전화번호": prop.contact,
        "성향": prop.inclination,
        "관계": prop.relationship,
        "접수일": prop.proped_date.isoformat() if prop.proped_date else None,
        "영상번호분초": prop.video_timestamp,
        "매수의향서": prop.intent_to_buy,
        "빌탐정광고등록유무": prop.toad_ad
    }
    return jsonify({"success": True, "data": result}), 200

@app.route('/api/save_prop_main', methods=['POST'])
def save_prop_main():
    data = request.get_json()
    pnu = data.get('고유번호')
    if not pnu:
        return jsonify({"message": "PNU는 필수입니다."}), 400

    # 기존 데이터가 있는지 확인 (있으면 수정, 없으면 생성)
    prop = PropMain.query.filter_by(pnu=pnu).first()
    if not prop:
        prop = PropMain(pnu=pnu)
        db.session.add(prop)

    try:
        # 데이터 업데이트 (JS에서 보낸 한글 키를 모델 필드에 매칭)
        prop.manager_Id = data.get('담당자')
        prop.progress = data.get('진행상태')
        prop.sale_price_billon = data.get('매매가')
        prop.sale_price_by_land_area = data.get('대지면적평단가')
        prop.sale_price_by_floor_area = data.get('연면적평단가')
        prop.total_security = data.get('총보증금')
        prop.total_monthly_rent = data.get('총월세부가세별도')
        prop.total_management_fee = data.get('총관리비')
        prop.yield_rate = data.get('수익률')
        prop.except_empty_yield = data.get('공실제외수익률')
        prop.self_yield = data.get('자기자본수익률')
        prop.urgency = data.get('긴급도')
        prop.grade = data.get('등급')
        prop.location_quality = data.get('입지')
        prop.building_usage = data.get('건물용도')
        prop.photo = data.get('사진')
        prop.briefing = data.get('브리핑')
        prop.eviction = data.get('명도')
        prop.demolition = data.get('멸실')
        prop.usage_change = data.get('용도변경')
        prop.ownertype = data.get('소유자타입')
        prop.owner_name = data.get('소유자명')
        prop.contact = data.get('전화번호')
        prop.inclination = data.get('성향')
        prop.relationship = data.get('관계')
        prop.video_timestamp = data.get('영상번호분초')
        prop.intent_to_buy = data.get('매수의향서')
        prop.memo = data.get('memo')
        prop.toad_ad = data.get('빌탐정광고등록유무')
        
        # 날짜 처리
        if data.get('접수일'):
            prop.proped_date = datetime.strptime(data.get('접수일'), '%Y-%m-%d').date()

        db.session.commit()
        return jsonify({"success": True, "message": "저장 완료"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_propDetail', methods=['POST'])   
def get_propDetail_data():
    req = request.json
    pnu_val = req.get('고유번호')

    if not pnu_val:
        return jsonify({"success": False, "message": "고유번호가 제공되지 않았습니다."}), 400

    # 1. LIMIT 1을 추가하여 단 한 개의 행만 가져옵니다.
    # 2. ORDER BY를 통해 '가장 정확한(대표적인)' 데이터가 위로 오게 정렬합니다.
    sql = text("""
        SELECT *
        FROM prop_details
        WHERE "고유번호" = :pnu
        ORDER BY "층" ASC, "id" ASC
        LIMIT 1
    """)

    try:
        with engine.connect() as conn:
            # 변수명을 :pnu와 일치시킵니다. (기존 addr -> pnu_val)
            result = conn.execute(sql, {"pnu": pnu_val})
            row = result.fetchone() # 하나만 가져올 때는 fetchone()이 효율적입니다.
            
            if row:
                # 단일 행을 딕셔너리로 변환
                data = dict(row._mapping)
                return jsonify({
                    "success": True, 
                    "data": data
                })
            else:
                return jsonify({"success": False, "message": "해당 고유번호의 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        print(f"Error fetching property details: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/register_property_final', methods=['POST'])
def register_property_final():
    data = request.json
    pnu = data.get('pnu')
    if not pnu:
        return jsonify({"success": False, "message": "PNU 누락"}), 400

    try:
        with engine.begin() as conn: # 트랜잭션 시작
            # 1. PropMain (매물 정보) 업데이트
            m = data.get('main')
            upsert_prop = text("""
                INSERT INTO prop_main ("고유번호", "담당자", "진행상태", "매매가", "총보증금", "총월세부가세별도", "총관리비", 
                "긴급도", "등급", "입지", "건물용도", "사진", "브리핑", "명도", "멸실", "용도변경", "소유자타입", "소유자명", 
                "전화번호", "성향", "관계", "접수일", "영상번호분초", "매수의향서", "빌탐정광고등록유무", "대지면적평단가", "연면적평단가", "수익률", "공실제외수익률","자기자본수익률", "자기자본","이자율")
                VALUES (:pnu, :manager, :status, :price, :sec, :rent, :mgmt, :urgency, :grade, :loc, :usage, :photo, 
                :brief, :evict, :demo, :u_change, :o_type, :o_name, :contact, :inclined, :rel, :p_date, :video, :intent, :toad, :price_land, :price_total, :yield, :yield_current, :yield_self, :invest_cash, :loan_rate)
                ON CONFLICT ("고유번호") DO UPDATE SET
                "담당자" = EXCLUDED."담당자", "진행상태" = EXCLUDED."진행상태", "매매가" = EXCLUDED."매매가", 
                "총보증금" = EXCLUDED."총보증금", "총월세부가세별도" = EXCLUDED."총월세부가세별도", "총관리비" = EXCLUDED."총관리비",
                "긴급도" = EXCLUDED."긴급도", "등급" = EXCLUDED."등급", "입지" = EXCLUDED."입지", "건물용도" = EXCLUDED."건물용도",
                "사진" = EXCLUDED."사진", "브리핑" = EXCLUDED."브리핑", "명도" = EXCLUDED."명도", "멸실" = EXCLUDED."멸실",
                "용도변경" = EXCLUDED."용도변경", "소유자타입" = EXCLUDED."소유자타입", "소유자명" = EXCLUDED."소유자명",
                "전화번호" = EXCLUDED."전화번호", "성향" = EXCLUDED."성향", "관계" = EXCLUDED."관계", "접수일" = EXCLUDED."접수일",
                "영상번호분초" = EXCLUDED."영상번호분초", "매수의향서" = EXCLUDED."매수의향서", "빌탐정광고등록유무" = EXCLUDED."빌탐정광고등록유무", "대지면적평단가" = EXCLUDED."대지면적평단가", "연면적평단가" = EXCLUDED."연면적평단가", "수익률" = EXCLUDED."수익률", "공실제외수익률" = EXCLUDED."공실제외수익률", "자기자본수익률" = EXCLUDED."자기자본수익률", "자기자본" = EXCLUDED."자기자본", "이자율" = EXCLUDED."이자율"
            """)
            conn.execute(upsert_prop, {**m, "pnu": pnu})

            # 2. SeoulLandInfo (건물/토지 물리 정보) 업데이트
            l = data.get('land')
            update_land = text("""
                UPDATE seoul_land_info SET
                "규모지상" = :f_above, "규모지하" = :f_below, "대지면적" = :b_area, "건축면적" = :a_area, "연면적" = :t_area,
                "용적률산정연면적" = :far_area, "엘리베이터" = :elev, "주차장" = :park, "사용승인일" = :a_date, "대수선및리모델링" = :r_date,
                "법정건폐율" = :l_bc, "법정용적률" = :l_far, "토지면적" = :land_area, "지목" = :jimok, "용도지역" = :zoning,
                "토지이용상황" = :status, "주용도" = :main_usage, "형상" = :shape, "도로" = :road, "기타용도" = :other,
                "공시지가" = :g_cur, "공시지가5년전" = :g_5y, "공시지가10년전" = :g_10y,
                "매각일1" = :s_d1, "매각액1" = :s_a1, "매각일2" = :s_d2, "매각액2" = :s_a2, "매각일3" = :s_d3, "매각액3" = :s_a3,
                "네이버광고" = :n_cur, "네이버광고과거" = :n_past, "소유자현재" = :o_current
                WHERE "고유번호" = :pnu
            """)
            conn.execute(update_land, {**l, "pnu": pnu})

            # 3. PropDetails (층별 상세) 갱신
            conn.execute(text("DELETE FROM prop_details WHERE \"고유번호\" = :pnu"), {"pnu": pnu})
            for f in data.get('floors', []):
                conn.execute(text("""
                    INSERT INTO prop_details ("고유번호", "층", "형태", "평수", "보증금", "임대료", "월관리비", "임대차기간", "공실유무")
                    VALUES (:pnu, :floor, :form, :size, :sec, :rent, :mgmt, :period, :isEmpty)
                """), {**f, "pnu": pnu})

        return jsonify({"success": True, "message": "모든 데이터가 한 개도 빠짐없이 저장되었습니다."})
    except Exception as e:
        app.logger.error(f"Final Save Error: {e}")
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
# --- API 2: 대기열용 전체 주소 조회 (중복 제거) ---
@app.route('/api/get_all_addresses', methods=['POST'])
def get_all_addresses():
    req = request.json
    params = {}
    where_sql = build_where_clause(req, params)
    
    try:
        with engine.connect() as conn:
            # [수정] FROM seoul_land_info L 로 별칭 추가
            sql = f"SELECT DISTINCT L.\"통합주소\" FROM {TABLE_NAME} L" + where_sql
            result = conn.execute(text(sql), params)
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
                    WHEN "매매가" IS NOT NULL AND "매매가" != ''
                         AND CAST(NULLIF(REGEXP_REPLACE("매매가", '[^0-9.]', '', 'g'), '') AS NUMERIC) > 0 
                    THEN ROUND(
                        -- (원 단위 정수 / 100,000,000) 하여 '억' 단위로 맞춘 후 비율 계산
                        (CAST(:AI추정가 AS NUMERIC) / 100000000) / 
                        CAST(NULLIF(REGEXP_REPLACE("매매가", '[^0-9.]', '', 'g'), '') AS NUMERIC) * 100
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
    """
    Handsontable의 변경 사항을 DB에 실시간 저장.
    수정된 필드명에 따라 SeoulLandInfo 또는 PropMain 테이블로 자동 분기.
    """
    data_list = request.json
    if not data_list: return jsonify({"error": "No data"}), 400
    
    # 1. 모델에서 유효한 컬럼 리스트 추출 (고유번호 자체는 업데이트 대상에서 제외)
    PROP_COLS = {c.name for c in PropMain.__table__.columns if not c.primary_key and c.name != "고유번호"}
    LAND_COLS = {c.name for c in SeoulLandInfo.__table__.columns if not c.primary_key and c.name != "고유번호"}

    try:
        with engine.begin() as conn:
            for row in data_list:
                pnu = row.get('고유번호')
                if not pnu: continue
                
                # 2. PropMain(매물정보) 업데이트 (Upsert)
                # '매매가', '진행상태' 등 사용자가 수정한 값
                prop_update = {k: v for k, v in row.items() if k in PROP_COLS}
                if prop_update:
                    cols = ", ".join([f'"{k}"' for k in prop_update.keys()])
                    vals = ", ".join([f':{k}' for k in prop_update.keys()])
                    upds = ", ".join([f'"{k}" = EXCLUDED."{k}"' for k in prop_update.keys()])
                    
                    query = text(f"""
                        INSERT INTO prop_main ("고유번호", {cols})
                        VALUES (:pnu, {vals})
                        ON CONFLICT ("고유번호") DO UPDATE SET {upds}
                    """)
                    conn.execute(query, {**prop_update, "pnu": pnu})

                # 3. SeoulLandInfo(토지정보) 업데이트
                # '대지면적', '공시지가', '규모지상' 등 공공데이터 정보
                land_update = {k: v for k, v in row.items() if k in LAND_COLS}
                if land_update:
                    set_sql = ", ".join([f'"{k}" = :{k}' for k in land_update.keys()])
                    query = text(f'UPDATE seoul_land_info SET {set_sql} WHERE "고유번호" = :pnu')
                    conn.execute(query, {**land_update, "pnu": pnu})
                
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"Update Data API Error: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/settings/columns', methods=['GET', 'POST'])
def column_settings():
    """
    로그인한 유저별로 독립된 컬럼 설정(순서)을 저장하거나 불러옵니다.
    """
    # 1. 세션에서 현재 로그인된 유저 식별
    u_id = session.get('user_id')
    if not u_id:
        return jsonify({"error": "로그인이 필요합니다."}), 401
    
    key = "column_order_v1"
    
    try:
        if request.method == 'POST':
            columns = request.json.get('columns')
            # 2. 기존 설정이 있는지 확인 (Upsert 로직)
            setting = UserSetting.query.filter_by(user_id=u_id, setting_key=key).first()
            if not setting:
                setting = UserSetting(user_id=u_id, setting_key=key)
                db.session.add(setting)
            
            # JSON 배열을 문자열로 변환하여 저장
            setting.setting_value = json.dumps(columns)
            db.session.commit()
            return jsonify({"status": "success"})
            
        elif request.method == 'GET':
            # 3. 로그인한 유저의 설정값만 반환
            setting = UserSetting.query.filter_by(user_id=u_id, setting_key=key).first()
            if setting and setting.setting_value:
                return jsonify(json.loads(setting.setting_value))
            return jsonify([]) # 설정이 없으면 빈 배열 반환
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"컬럼 설정 오류: {e}")
        return jsonify({"error": str(e)}), 500
    
# app.py 내 해당 API를 아래 내용으로 교체하세요.

@app.route('/api/get_building_history', methods=['POST'])
def get_building_history():
    """
    PNU(고유번호) 리스트를 받아 사용승인일과 대수선 정보를 반환.
    get_data의 PNU 처리 로직(LIKE 및 OR 검색)을 차용함.
    """
    req = request.json
    pnu_input = req.get('pnus', []) # 기존 'addresses' 대신 'pnus' 사용
    
    if not pnu_input:
        return jsonify({})

    # 입력값이 단일 값일 경우 리스트로 변환 (get_data 로직 참고)
    if isinstance(pnu_input, (str, dict)):
        pnu_input = [pnu_input]

    params = {}
    pnu_conds = []
    
    # 1. PNU 조건 빌드 (LIKE 연산 적용으로 10자리/19자리 모두 대응 가능)
    for idx, p in enumerate(pnu_input):
        val = p.get('value', '') if isinstance(p, dict) else p
        if val and str(val).strip():
            p_key = f"p_idx_{idx}"
            pnu_conds.append(f'"고유번호" LIKE :{p_key}')
            params[p_key] = f"{str(val).strip()}%"

    if not pnu_conds:
        return jsonify({})

    # 2. 쿼리 구성
    where_sql = f"WHERE ({' OR '.join(pnu_conds)})"
    
    try:
        with engine.connect() as conn:
            # 고유번호를 키로 사용하도록 변경
            query = text(f"""
                SELECT "고유번호", "사용승인일", "대수선및리모델링" 
                FROM {TABLE_NAME} 
                {where_sql}
            """)
            result = conn.execute(query, params)
            
            # 응답 구조: { "PNU": {"사용승인일": "...", "대수선": "..."}, ... }
            history_map = {
                row[0]: {
                    "사용승인일": row[1], 
                    "대수선및리모델링": row[2]
                } for row in result.fetchall()
            }
            return jsonify(history_map)
            
    except Exception as e:
        app.logger.error(f"PNU-based History Fetch Error: {e}")
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
    

# Auth ---------------------------------

# app.py에 추가

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    u_id = data.get('user_id')
    u_role = data.get('role')

    if Users.query.get(u_id):
        return jsonify({"message": "이미 존재하는 아이디입니다."}), 400

    new_user = Users(
        user_id=u_id,
        user_pw=data.get('user_pw'),
        user_name=data.get('user_name'),
        role=u_role
    )

    if u_role == 'MASTER':
        # 마스터는 본인 아이디로 팀 생성
        new_team = Team(master_id=u_id)
        new_user.belong_to_team = u_id
        db.session.add(new_team)
    else:
        # 슬레이브는 입력받은 팀장 아이디 확인
        m_id = data.get('master_id')
        if not Team.query.get(m_id):
            return jsonify({"message": "존재하지 않는 팀장(마스터) 아이디입니다."}), 400
        new_user.belong_to_team = m_id

    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "회원가입 완료"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = Users.query.filter_by(
        user_id=data.get('user_id'), 
        user_pw=data.get('user_pw'),
    ).first()

    if not user:
        return jsonify({"message": "아이디 또는 비밀번호가 틀렸습니다."}), 401

    # 세션 정의
    session['user_id'] = user.user_id
    session['user_name'] = user.user_name
    session['role'] = user.role
    session['team_id'] = user.belong_to_team # 마스터 아이디가 담김
    
    return jsonify({"message": "로그인 성공"}), 200

# app.py 내 Auth 라우트 위나 적당한 위치에 추가

@app.before_request
def login_required():
    # 1. 세션에 user_id가 있는지 확인
    user_id = session.get('user_id')
    
    # 2. 예외 처리해야 할 경로 정의 (로그인 안 해도 접근 가능해야 하는 곳)
    # 'auth' (HTML 페이지), 'login' (인증 API), 'signup' (회원가입 API), 'static' (이미지/CSS 등)
    allowed_endpoints = ['auth', 'login', 'signup', 'static']
    
    # 3. 세션이 없고, 현재 요청한 곳이 허용된 경로가 아니면 /auth로 강제 이동
    if not user_id and request.endpoint not in allowed_endpoints:
        return redirect(url_for('auth'))
    
@app.route('/api/get_session', methods=['GET'])
def get_session():
    # 세션에 정보가 있는지 확인
    if 'user_id' in session:
        return jsonify({
            "logged_in": True,
            "user_id": session.get('user_id'),
            "user_name": session.get('user_name'),
            "role": session.get('role'),
            "team_id": session.get('team_id')
        }), 200
    else:
        return jsonify({"logged_in": False}), 401
    
#----메모 Memo ------------------------------

from flask import request, jsonify, session

# 1. 메모 조회 엔드포인트
@app.route('/api/load_memos', methods=['GET'])
def load_memos():
    pnu = request.args.get('pnu')
    if not pnu:
        return jsonify({"message": "PNU가 필요합니다."}), 400

    # PNU에 해당하는 메모들을 최신순으로 조회
    memos = PropMemo.query.filter_by(pnu=pnu).order_by(PropMemo.created_at.desc()).all()
    
    memo_list = []
    for m in memos:
        memo_list.append({
            "id": m.id,
            "content": m.content,
            "writer_name": m.writer.user_name if m.writer else "알 수 없음", # 관계 설정을 통해 이름 가져옴
            "created_at": m.created_at.strftime('%Y-%m-%d %H:%M'),
            "importance": m.importance
        })
    
    return jsonify({"memos": memo_list}), 200

# 2. 메모 추가 엔드포인트
@app.route('/api/add_memo', methods=['POST'])
def add_memo():
    data = request.get_json()
    pnu = data.get('pnu')
    content = data.get('content')
    importance = data.get('importance', '보통') # 기본값 '보통'
    
    # 세션에서 현재 로그인한 사용자 ID 가져오기
    writer_id = session.get('user_id')

    if not pnu or not content:
        return jsonify({"message": "필수 입력 정보가 누락되었습니다."}), 400
    
    if not writer_id:
        return jsonify({"message": "로그인이 필요합니다."}), 401

    try:
        new_memo = PropMemo(
            pnu=pnu,
            writer_id=writer_id,
            content=content,
            importance=importance
        )
        db.session.add(new_memo)
        db.session.commit()
        
        return jsonify({"message": "메모가 성공적으로 등록되었습니다."}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"오류 발생: {str(e)}"}), 500
    
# 메모 수정 엔드포인트
@app.route('/api/update_memo', methods=['POST'])
def update_memo():
    data = request.get_json()
    memo_id = data.get('id')
    content = data.get('content')
    importance = data.get('importance')
    
    if not memo_id or not content:
        return jsonify({"message": "수정할 내용이 없습니다."}), 400
        
    memo = PropMemo.query.get(memo_id)
    if not memo:
        return jsonify({"message": "메모를 찾을 수 없습니다."}), 404
    
    # 본인 확인 로직 (필요시)
    if memo.writer_id != session.get('user_id'):
        return jsonify({"message": "수정 권한이 없습니다."}), 403

    try:
        memo.content = content
        memo.importance = importance
        memo.created_at = db.func.now() # 수정 시간 업데이트
        db.session.commit()
        return jsonify({"message": "수정 완료"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)