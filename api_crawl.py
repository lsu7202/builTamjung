"""데스크탑 크롤링 데이터 업로드 API (시계열 배치 방식)

데스크탑 앱이 크롤링 결과를 배치 단위로 업로드한다:
  1) POST /api/crawl/batches            → 배치 생성 (status=uploading)
  2) POST /api/crawl/batches/<id>/chunks → 레코드 청크 반복 업로드 (청크별 독립 트랜잭션)
  3) POST /api/crawl/batches/<id>/complete → 배치 확정. naver_sale이면 seoul_land_info의
     네이버광고(최신)/네이버광고과거(직전) 파생 컬럼 갱신 (상승률은 기존 DB 트리거가 계산)
  실패 시) POST /api/crawl/batches/<id>/abort → 배치 및 하위 레코드 삭제 (CASCADE)

인증: X-API-KEY 헤더 == .env의 UPLOAD_API_KEY
"""
import os
import re
import hmac
from functools import wraps

from flask import Blueprint, request, jsonify
from sqlalchemy import text

VALID_KINDS = {'naver_sale', 'naver_rent'}


def parse_floor_num(floor_info):
    """floorInfo 원문("4/5", "B1/5")에서 해당 층 정수를 추출. 지하는 음수, 실패 시 None."""
    if floor_info is None:
        return None
    raw = str(floor_info).split('/')[0].strip()
    digits = re.sub(r'[^0-9]', '', raw)
    if not digits:
        return None
    num = int(digits)
    if 'B' in raw.upper():
        num = -num
    return num


def _to_float(v):
    try:
        if v is None or v == '':
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def create_crawl_blueprint(engine):
    bp = Blueprint('crawl', __name__)

    def require_upload_key(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            server_key = os.getenv('UPLOAD_API_KEY', '')
            if not server_key:
                return jsonify({"error": "server UPLOAD_API_KEY not configured"}), 503
            client_key = request.headers.get('X-API-KEY', '')
            if not hmac.compare_digest(client_key, server_key):
                return jsonify({"error": "unauthorized"}), 401
            return f(*args, **kwargs)
        return wrapper

    def get_batch(conn, batch_id):
        row = conn.execute(
            text("SELECT id, kind, status FROM crawl_batches WHERE id = :id"),
            {"id": batch_id}
        ).mappings().first()
        return row

    # ------------------------------------------------------------------
    # 1. 배치 생성
    # ------------------------------------------------------------------
    @bp.route('/api/crawl/batches', methods=['POST'])
    @require_upload_key
    def create_batch():
        data = request.json or {}
        kind = data.get('kind')
        if kind not in VALID_KINDS:
            return jsonify({"error": f"kind must be one of {sorted(VALID_KINDS)}"}), 400
        with engine.begin() as conn:
            batch_id = conn.execute(
                text("""INSERT INTO crawl_batches (kind, status, note)
                        VALUES (:kind, 'uploading', :note) RETURNING id"""),
                {"kind": kind, "note": data.get('note')}
            ).scalar()
        return jsonify({"batch_id": batch_id})

    # ------------------------------------------------------------------
    # 2. 청크 업로드
    # ------------------------------------------------------------------
    @bp.route('/api/crawl/batches/<int:batch_id>/chunks', methods=['POST'])
    @require_upload_key
    def upload_chunk(batch_id):
        data = request.json or {}
        records = data.get('records')
        if not isinstance(records, list) or not records:
            return jsonify({"error": "records must be a non-empty list"}), 400

        with engine.begin() as conn:
            batch = get_batch(conn, batch_id)
            if not batch:
                return jsonify({"error": "batch not found"}), 404
            if batch['status'] != 'uploading':
                return jsonify({"error": f"batch status is '{batch['status']}', not uploading"}), 409

            if batch['kind'] == 'naver_rent':
                params = []
                for r in records:
                    lat, lon = _to_float(r.get('lat')), _to_float(r.get('lon'))
                    params.append({
                        "batch_id": batch_id,
                        "article_no": str(r.get('article_no') or ''),
                        "deposit": _to_float(r.get('deposit')),
                        "rent": _to_float(r.get('rent')),
                        "floor_info": r.get('floor_info'),
                        "floor_num": parse_floor_num(r.get('floor_info')),
                        "area_contract": _to_float(r.get('area_contract')),
                        "area_exclusive": _to_float(r.get('area_exclusive')),
                        "address": r.get('address'),
                        "lat": lat, "lon": lon,
                    })
                conn.execute(text("""
                    INSERT INTO naver_rent_articles
                        (batch_id, article_no, deposit, rent, floor_info, floor_num,
                         area_contract, area_exclusive, address, lat, lon, geom)
                    VALUES
                        (:batch_id, :article_no, :deposit, :rent, :floor_info, :floor_num,
                         :area_contract, :area_exclusive, :address, :lat, :lon,
                         CASE WHEN CAST(:lat AS float) IS NOT NULL AND CAST(:lon AS float) IS NOT NULL
                              THEN ST_SetSRID(ST_MakePoint(CAST(:lon AS float), CAST(:lat AS float)), 4326)
                         END)
                    ON CONFLICT (batch_id, article_no) DO NOTHING
                """), params)
            else:  # naver_sale
                params = [{
                    "batch_id": batch_id,
                    "address": r.get('address'),
                    "price": _to_float(r.get('price')),
                    "lat": _to_float(r.get('lat')),
                    "lon": _to_float(r.get('lon')),
                } for r in records]
                conn.execute(text("""
                    INSERT INTO naver_ad_history (batch_id, address, price, lat, lon)
                    VALUES (:batch_id, :address, :price, :lat, :lon)
                """), params)

        return jsonify({"success": True, "received": len(records)})

    # ------------------------------------------------------------------
    # 3. 배치 완료 (+ 매매 파생 컬럼 갱신)
    # ------------------------------------------------------------------
    @bp.route('/api/crawl/batches/<int:batch_id>/complete', methods=['POST'])
    @require_upload_key
    def complete_batch(batch_id):
        with engine.begin() as conn:
            batch = get_batch(conn, batch_id)
            if not batch:
                return jsonify({"error": "batch not found"}), 404
            if batch['status'] != 'uploading':
                return jsonify({"error": f"batch status is '{batch['status']}', not uploading"}), 409

            table = 'naver_rent_articles' if batch['kind'] == 'naver_rent' else 'naver_ad_history'
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE batch_id = :id"), {"id": batch_id}
            ).scalar()

            conn.execute(text("""
                UPDATE crawl_batches
                   SET status = 'completed', completed_at = now(), record_count = :cnt
                 WHERE id = :id
            """), {"cnt": count, "id": batch_id})

            derived_updated = None
            if batch['kind'] == 'naver_sale':
                derived_updated = _refresh_sale_derived_columns(conn)

        result = {"success": True, "batch_id": batch_id, "record_count": count}
        if derived_updated is not None:
            result["derived_rows_updated"] = derived_updated
        return jsonify(result)

    def _refresh_sale_derived_columns(conn):
        """최신 완료 배치 → 네이버광고, 직전 완료 배치 → 네이버광고과거.
        상승률은 seoul_land_info의 BEFORE UPDATE 트리거(fn_calculate_land_data)가 계산."""
        # 1. 초기화: 광고가 내려간 물건 반영 + 트리거가 NULL이면 상승률을 안 건드리므로 명시 초기화
        conn.execute(text("""
            UPDATE seoul_land_info
               SET "네이버광고" = NULL, "네이버광고과거" = NULL, "네이버광고상승률" = NULL
             WHERE "네이버광고" IS NOT NULL OR "네이버광고과거" IS NOT NULL
                OR "네이버광고상승률" IS NOT NULL
        """))
        # 2. 최신/직전 배치 조인 갱신 (주소당 다건은 최저가 채택)
        result = conn.execute(text("""
            WITH b AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY completed_at DESC) AS rn
                  FROM crawl_batches
                 WHERE kind = 'naver_sale' AND status = 'completed'
            ),
            cur AS (
                SELECT address, MIN(price) AS price FROM naver_ad_history
                 WHERE batch_id = (SELECT id FROM b WHERE rn = 1) AND address IS NOT NULL
                 GROUP BY address
            ),
            old AS (
                SELECT address, MIN(price) AS price FROM naver_ad_history
                 WHERE batch_id = (SELECT id FROM b WHERE rn = 2) AND address IS NOT NULL
                 GROUP BY address
            )
            UPDATE seoul_land_info t
               SET "네이버광고" = cur.price,
                   "네이버광고과거" = old.price
              FROM cur LEFT JOIN old ON old.address = cur.address
             WHERE t."통합주소" = cur.address
        """))
        return result.rowcount

    # ------------------------------------------------------------------
    # 4. 배치 중단/폐기
    # ------------------------------------------------------------------
    @bp.route('/api/crawl/batches/<int:batch_id>/abort', methods=['POST'])
    @require_upload_key
    def abort_batch(batch_id):
        with engine.begin() as conn:
            batch = get_batch(conn, batch_id)
            if not batch:
                return jsonify({"error": "batch not found"}), 404
            if batch['status'] == 'completed':
                return jsonify({"error": "completed batch cannot be aborted"}), 409
            conn.execute(text("DELETE FROM crawl_batches WHERE id = :id"), {"id": batch_id})
        return jsonify({"success": True, "batch_id": batch_id})

    return bp
