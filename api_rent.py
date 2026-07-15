"""주변임대시세 분석 API (네이버임대광고 시계열 기반)

- GET  /api/rent/batches        : 완료된 임대 크롤링 배치 목록 (기준시점 선택용)
- POST /api/rent/analyze        : 대상 주소들 반경 내 임대매물 분석 (층 필터 + 평당가 + 층별 요약)
- POST /api/rent/analyze/excel  : 동일 분석 결과를 기존 getGeo.py 양식 엑셀로 다운로드

인증: 웹 세션 (app.py의 전역 login_required가 적용됨)
"""
import io
import re
import datetime

from flask import Blueprint, request, jsonify, send_file
from sqlalchemy import text

PYEONG_FACTOR = 0.3025


def format_date(date_str):
    """20231231 → 2023.12.31 (기존 getGeo.format_date 포팅)"""
    if not date_str:
        return ''
    nums = re.sub(r'[^0-9]', '', str(date_str))
    if len(nums) == 8:
        return f"{nums[:4]}.{nums[4:6]}.{nums[6:]}"
    return str(date_str)


def floor_label_of(floor_num):
    if floor_num is None:
        return ''
    return f"B{abs(floor_num)}" if floor_num < 0 else f"{floor_num}F"


def create_rent_blueprint(engine):
    bp = Blueprint('rent', __name__)

    # ------------------------------------------------------------------
    # 배치 목록 (기준시점 드롭다운)
    # ------------------------------------------------------------------
    @bp.route('/api/rent/batches', methods=['GET'])
    def list_batches():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, completed_at, record_count, note
                  FROM crawl_batches
                 WHERE kind = 'naver_rent' AND status = 'completed'
                 ORDER BY completed_at DESC
            """)).mappings().all()
        return jsonify([{
            "batch_id": r['id'],
            "completed_at": r['completed_at'].strftime('%Y-%m-%d %H:%M') if r['completed_at'] else None,
            "record_count": r['record_count'],
            "note": r['note'],
        } for r in rows])

    # ------------------------------------------------------------------
    # 분석 코어 (analyze / excel 공용)
    # ------------------------------------------------------------------
    def run_analysis(payload):
        targets = payload.get('targets') or []
        radius_km = float(payload.get('radius_km') or 0.5)
        batch_id = payload.get('batch_id')

        if not targets:
            return None, ({"error": "targets가 비어 있습니다."}, 400)

        with engine.connect() as conn:
            # 1. 배치 결정 (미지정 시 최신 완료 배치)
            if batch_id:
                batch = conn.execute(text("""
                    SELECT id, completed_at FROM crawl_batches
                     WHERE id = :id AND kind = 'naver_rent' AND status = 'completed'
                """), {"id": batch_id}).mappings().first()
            else:
                batch = conn.execute(text("""
                    SELECT id, completed_at FROM crawl_batches
                     WHERE kind = 'naver_rent' AND status = 'completed'
                     ORDER BY completed_at DESC LIMIT 1
                """)).mappings().first()
            if not batch:
                return None, ({"error": "완료된 임대 크롤링 배치가 없습니다."}, 404)

            results, unmatched = [], []
            for t in targets:
                address = (t.get('address') or '').strip()
                under = abs(int(t.get('under') or 0))
                above = int(t.get('above') or 0)
                if not address:
                    continue

                # 2. 주소 → 좌표 (seoul_land_info 통합주소 조회, 지오코딩 불필요)
                loc = conn.execute(text("""
                    SELECT x, y FROM seoul_land_info
                     WHERE "통합주소" = :addr AND geom IS NOT NULL
                     LIMIT 1
                """), {"addr": address}).first()
                if not loc:
                    unmatched.append(address)
                    continue
                lon, lat = float(loc[0]), float(loc[1])

                # 3. 반경 + 층 필터 검색, 사용승인일/대수선 조인
                rows = conn.execute(text("""
                    SELECT r.article_no, r.floor_info, r.floor_num,
                           r.deposit, r.rent, r.area_contract, r.area_exclusive,
                           r.address, s."사용승인일" AS approval_date,
                           s."대수선및리모델링" AS remodel_date
                      FROM naver_rent_articles r
                      LEFT JOIN seoul_land_info s ON s."통합주소" = r.address
                     WHERE r.batch_id = :batch_id
                       AND ST_DWithin(r.geom::geography,
                                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                                      :radius_m)
                       AND r.floor_num IS NOT NULL
                       AND r.floor_num BETWEEN :u_limit AND :a_limit
                     ORDER BY r.floor_num DESC
                """), {
                    "batch_id": batch['id'], "lon": lon, "lat": lat,
                    "radius_m": radius_km * 1000.0,
                    "u_limit": -under, "a_limit": above,
                }).mappings().all()

                # 4. 평당가 계산 (기존 getGeo.calc 로직 포팅)
                items = []
                for r in rows:
                    deposit = float(r['deposit'] or 0)
                    rent = float(r['rent'] or 0)
                    c_pyeong = round(float(r['area_contract'] or 0) * PYEONG_FACTOR, 2)
                    e_pyeong = round(float(r['area_exclusive'] or 0) * PYEONG_FACTOR, 2)
                    items.append({
                        "매물번호": r['article_no'],
                        "층": floor_label_of(r['floor_num']),
                        "num_floor": r['floor_num'],
                        "계약평": c_pyeong,
                        "전용평": e_pyeong,
                        "보증금": int(deposit),
                        "임대료": int(rent),
                        "계약평당보증금": round(deposit / c_pyeong) if c_pyeong > 0 else 0,
                        "계약평당임대료": round(rent / c_pyeong) if c_pyeong > 0 else 0,
                        "전용평당보증금": round(deposit / e_pyeong) if e_pyeong > 0 else 0,
                        "전용평당임대료": round(rent / e_pyeong) if e_pyeong > 0 else 0,
                        "사용승인일": format_date(r['approval_date']),
                        "대수선": format_date(r['remodel_date']),
                        "주소": r['address'] or '',
                    })

                # 5. 층별 요약 (계약면적 있는 매물 기준 평균)
                floor_summary = []
                for fnum in sorted({i['num_floor'] for i in items}, reverse=True):
                    f_items = [i for i in items if i['num_floor'] == fnum]
                    valid = [i for i in f_items if i['계약평당보증금'] > 0 or i['계약평당임대료'] > 0]
                    n = len(valid)
                    floor_summary.append({
                        "층": floor_label_of(fnum),
                        "건수": len(f_items),
                        "평균계약평당보증금": round(sum(i['계약평당보증금'] for i in valid) / n) if n else 0,
                        "평균계약평당임대료": round(sum(i['계약평당임대료'] for i in valid) / n) if n else 0,
                    })

                results.append({
                    "target_address": address,
                    "target_floor_range": f"B{under}~{above}F",
                    "radius_km": radius_km,
                    "item_count": len(items),
                    "items": items,
                    "floor_summary": floor_summary,
                })

        analysis = {
            "batch": {
                "batch_id": batch['id'],
                "completed_at": batch['completed_at'].strftime('%Y-%m-%d %H:%M') if batch['completed_at'] else None,
            },
            "results": results,
            "unmatched": unmatched,
        }
        return analysis, None

    # ------------------------------------------------------------------
    # 네이버광고(매매) 시계열 이력 조회 — 내매물 모달의 이력 UI용
    # ------------------------------------------------------------------
    @bp.route('/api/naver_ad/history', methods=['POST'])
    def naver_ad_history():
        req = request.json or {}
        pnu = (req.get('pnu') or '').strip()
        if not pnu:
            return jsonify({"error": "pnu가 필요합니다."}), 400
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT b.completed_at, MIN(h.price) AS price
                  FROM naver_ad_history h
                  JOIN crawl_batches b ON b.id = h.batch_id AND b.status = 'completed'
                  JOIN seoul_land_info s ON s."통합주소" = h.address
                 WHERE s."고유번호" = :pnu
                 GROUP BY b.id, b.completed_at
                 ORDER BY b.completed_at DESC
            """), {"pnu": pnu}).all()
        return jsonify([{
            "date": r[0].strftime('%Y-%m-%d') if r[0] else None,
            "price": float(r[1]) if r[1] is not None else None,
        } for r in rows])

    @bp.route('/api/rent/analyze', methods=['POST'])
    def analyze():
        analysis, err = run_analysis(request.json or {})
        if err:
            body, code = err
            return jsonify(body), code
        return jsonify(analysis)

    # ------------------------------------------------------------------
    # 엑셀 다운로드 (기존 getGeo.save_to_excel 양식, target당 시트 1장)
    # ------------------------------------------------------------------
    @bp.route('/api/rent/analyze/excel', methods=['POST'])
    def analyze_excel():
        import xlsxwriter

        analysis, err = run_analysis(request.json or {})
        if err:
            body, code = err
            return jsonify(body), code

        buf = io.BytesIO()
        workbook = xlsxwriter.Workbook(buf, {'in_memory': True})
        comma_format = workbook.add_format({'num_format': '#,##0', 'align': 'center'})
        decimal_format = workbook.add_format({'num_format': '#,##0.00', 'align': 'center'})

        TABLE1_HEADERS = ["매물순서", "층", "계약면적(평)", "전용면적(평)", "보증금", "임대료",
                          "계약 평당 보증금", "계약 평당 임대료", "관리비", "사용승인일", "대수선", "주소"]
        TABLE2_HEADERS = ["순번", "층", "본매물 면적(평)", "평균 계약 평당 보증금",
                          "평균 계약 평당 임대료", "추정 보증금(계약)", "추정 임대료(계약)"]

        used_names = set()
        for data in analysis['results']:
            # 시트명: 31자 제한 + 특수문자 제거 + 중복 방지
            base = ''.join(c for c in data['target_address'] if c.isalnum() or c in (' ', '.', '-'))[:28] or 'Sheet'
            name, seq = base, 1
            while name in used_names:
                seq += 1
                name = f"{base}_{seq}"
            used_names.add(name)
            worksheet = workbook.add_worksheet(name)

            items = data['items']  # 이미 층 내림차순 정렬됨

            # --- 표 1 (A~L열) ---
            for c, h in enumerate(TABLE1_HEADERS):
                worksheet.write(0, c, h)
            for r, item in enumerate(items, start=1):
                worksheet.write(r, 0, r)
                worksheet.write(r, 1, item['층'])
                worksheet.write(r, 2, item['계약평'])
                worksheet.write(r, 3, item['전용평'])
                worksheet.write(r, 4, item['보증금'])
                worksheet.write(r, 5, item['임대료'])
                worksheet.write(r, 6, item['계약평당보증금'])
                worksheet.write(r, 7, item['계약평당임대료'])
                worksheet.write(r, 8, 0)  # 관리비 미수집
                worksheet.write(r, 9, item['사용승인일'])
                worksheet.write(r, 10, item['대수선'])
                worksheet.write(r, 11, item['주소'])

            # --- 표 2 (N~T열, index 13~19) ---
            for c, h in enumerate(TABLE2_HEADERS):
                worksheet.write(0, 13 + c, h)
            unique_floors = [fs['층'] for fs in data['floor_summary']]
            last_row_t1 = len(items) + 1
            t1_floor_col = f"$B$2:$B${last_row_t1}"
            for i, floor_lbl in enumerate(unique_floors):
                row_idx = i + 2  # 엑셀 1-based, 헤더 다음 행
                worksheet.write(row_idx - 1, 13, i + 1)
                worksheet.write(row_idx - 1, 14, floor_lbl)
                worksheet.write_number(row_idx - 1, 15, 0.00, decimal_format)  # 본매물 면적(입력용)
                worksheet.write_formula(
                    f'Q{row_idx}',
                    f'=IFERROR(AVERAGEIFS($G$2:$G${last_row_t1}, {t1_floor_col}, O{row_idx}), 0)',
                    comma_format)
                worksheet.write_formula(
                    f'R{row_idx}',
                    f'=IFERROR(AVERAGEIFS($H$2:$H${last_row_t1}, {t1_floor_col}, O{row_idx}), 0)',
                    comma_format)
                worksheet.write_formula(f'S{row_idx}', f'=Q{row_idx}*P{row_idx}', comma_format)
                worksheet.write_formula(f'T{row_idx}', f'=R{row_idx}*P{row_idx}', comma_format)

            # --- 열 서식 (기존 getGeo 양식 동일) ---
            worksheet.set_column('A:B', 10, comma_format)
            worksheet.set_column('C:D', 12, decimal_format)
            worksheet.set_column('E:I', 15, comma_format)
            worksheet.set_column('J:K', 15, comma_format)
            worksheet.set_column('L:L', 40)
            worksheet.set_column('M:M', 5)
            worksheet.set_column('N:O', 10, comma_format)
            worksheet.set_column('P:P', 15, decimal_format)
            worksheet.set_column('Q:T', 18, comma_format)

        if not analysis['results']:
            workbook.add_worksheet('결과없음')
        workbook.close()
        buf.seek(0)

        stamp = datetime.datetime.now().strftime('%Y%m%d')
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"주변임대시세_{stamp}.xlsx",
        )

    return bp
