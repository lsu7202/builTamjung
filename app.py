import os
import logging
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text

# --- 1. 기본 설정 ---

# (중요) DB 연결 설정
DB_USER = "iseung-ug"  # Homebrew 설치 시 macOS 사용자명
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "addresses"  # ★★★ 사용자님 DB 이름
TABLE_NAME = "seoul_land_info"  # ★★★ 사용자님 테이블 이름

DB_URL = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print(f"✅ 데이터베이스 '{DB_NAME}' 연결 성공")
except Exception as e:
    print(f"❌ 데이터베이스 연결 실패: {e}")
    print("DB_URL, 사용자명, DB이름이 올바른지 확인하세요.")
    exit()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False 
app.debug = True 
logging.basicConfig(level=logging.INFO)

# --- 2. 기본 라우트 (HTML 페이지) ---

@app.route('/')
def index():
    return render_template('index.html')

# --- 3. API 라우트 (데이터 조회) ---

# ★★★ (수정됨) /api/get_data 엔드포인트 ★★★
@app.route('/api/get_data')
def get_data():
    """
    '법정동명'과 '토지이용상황'을 기준으로 데이터를 조회하는 API
    URL 예시: /api/get_data?bjd_name=강남구&land_use=주거용
    """
    # 1. 두 개의 파라미터를 받음 (값이 없으면 빈 문자열, 양쪽 공백 제거)
    bjd_name = request.args.get('bjd_name', '').strip()
    land_use = request.args.get('land_use', '').strip()
    
    if not bjd_name and not land_use:
        return jsonify({"error": "검색 파라미터가 하나 이상 필요합니다."}), 400

    app.logger.info(f"조회 시도: 법정동명='{bjd_name}', 토지이용상황='{land_use}'")

    try:
        with engine.connect() as conn:
            
            # 2. 쿼리 동적 생성
            base_query = f"SELECT *, ctid FROM {TABLE_NAME}"
            where_clauses = [] # WHERE 조건을 저장할 리스트
            params = {}        # SQL 파라미터를 저장할 딕셔너리

            # 법정동명 조건 추가
            if bjd_name:
                where_clauses.append('TRIM("통합주소") LIKE :bjd_name')
                params["bjd_name"] = f"%{bjd_name}%"
            
            # 토지이용상황 조건 추가
            if land_use:
                # [주의] DB에 저장된 실제 컬럼명으로 변경해야 할 수 있습니다. (예: "토지이용")
                where_clauses.append('TRIM("토지이용상황") LIKE :land_use')
                params["land_use"] = f"%{land_use}%"

            # 3. WHERE 절 조립
            query_sql = base_query
            if where_clauses:
                # where_clauses 리스트를 ' AND '로 연결
                query_sql += " WHERE " + " AND ".join(where_clauses)
            
            query_sql += " LIMIT 50000" # LIMIT은 유지
            
            query = text(query_sql)
            
            app.logger.info(f"실행 쿼리: {query} | 파라미터: {params}")
            
            # 4. 쿼리 실행
            result = conn.execute(query, params)
            
            rows = result.mappings().all()
            app.logger.info(f"조회 결과: {len(rows)} 건")
            
            data_to_send = [dict(row) for row in rows]
            
            return jsonify(data_to_send)
            
    except Exception as e:
        app.logger.error(f"데이터 조회 중 오류 발생: {e}", exc_info=True)
        # 컬럼명이 잘못된 경우 (예: "토지이용상황" 컬럼이 없음) 여기서 오류가 발생할 수 있습니다.
        return jsonify({"error": f"데이터 조회 중 오류 발생: {e}"}), 500

# --- 4. API 라우트 (데이터 수정) ---
# (수정 사항 없음)
@app.route('/api/update_data', methods=['POST'])
def update_data():
    """
    Handsontable에서 수정된 데이터를 받아 DB에 업데이트하는 API
    ctid를 기준으로 행을 찾아 업데이트합니다.
    """
    data_list = request.json
    if not data_list:
        return jsonify({"error": "업데이트할 데이터가 없습니다."}), 400

    updated_count = 0
    
    try:
        with engine.begin() as conn: # 트랜잭션 시작
            for row in data_list:
                ctid = row.pop('ctid', None)
                if not ctid:
                    continue 

                set_clauses = [f'"{key}" = :{key}' for key in row.keys()]
                set_sql = ", ".join(set_clauses)
                
                query = text(f"""
                    UPDATE {TABLE_NAME}
                    SET {set_sql}
                    WHERE ctid = :ctid
                """)
                
                row['ctid'] = ctid 
                
                result = conn.execute(query, row)
                if result.rowcount > 0:
                    updated_count += 1
        
        app.logger.info(f"업데이트 완료: {updated_count} 건")
        return jsonify({
            "status": "success", 
            "message": f"총 {updated_count}개의 행이 성공적으로 업데이트되었습니다."
        })

    except Exception as e:
        app.logger.error(f"데이터 업데이트 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error": f"데이터 업데이트 중 오류 발생: {e}"}), 500

# --- 5. Flask 앱 실행 ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=3000)