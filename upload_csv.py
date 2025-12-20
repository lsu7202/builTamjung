import pandas as pd
from sqlalchemy import create_engine
import os
import psycopg2

# --- 설정 (도커 .env에 설정한 값과 일치해야 함) ---
DB_USER = "iseung-ug"     # .env의 DB_USER
DB_PASS = "1234"  # .env의 DB_PASS (꼭 수정하세요!)
DB_HOST = "136.113.21.134"     # 로컬에서 실행하므로 localhost
DB_PORT = "5050"          # docker-compose에서 열어둔 포트
DB_NAME = "postgres"     # .env의 DB_NAME
TABLE_NAME = "seoul_land_info" # app.py에서 사용하는 테이블명

# --- CSV 파일 설정 ---
CSV_FILE_PATH = "data.csv" # 가지고 계신 csv 파일 경로/이름

# 1. DB 연결 엔진 생성
db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(db_url)

def create_tables():
    try:
        # DB 연결
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME
        )
        cur = conn.cursor()

        print("🔨 테이블 생성을 시작합니다...")

        # 1. 위시리스트(wishlist) 테이블 생성
        # app.py 로직에 맞춰 address를 PK로 잡고, created_at 컬럼을 추가했습니다.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                address TEXT PRIMARY KEY,
                color TEXT DEFAULT '#ffff00',
                group_name TEXT DEFAULT '기본',
                note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ 'wishlist' 테이블 생성 완료")

        # 2. 사용자 설정(user_settings) 테이블 생성
        # 컬럼 순서 저장 기능 등에 사용됩니다.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            );
        """)
        print("✅ 'user_settings' 테이블 생성 완료")

        conn.commit()
        cur.close()
        conn.close()
        print("🎉 모든 테이블 준비 끝! 이제 웹사이트를 새로고침 해보세요.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("팁: 비밀번호나 포트 번호(5432 vs 5433)를 확인해주세요.")

if __name__ == "__main__":
    create_tables()

    print("💾 CSV 파일 읽는 중...")
    # CSV 파일 읽기 (한글 깨짐 방지를 위해 encoding 확인 필요, 보통 utf-8 또는 cp949)
    try:
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8', dtype="str")
    except UnicodeDecodeError:
        df = pd.read_csv(CSV_FILE_PATH, encoding='cp949', dtype="str")

    print(f"🚀 {len(df)}개 데이터 업로드 시작... (시간이 좀 걸릴 수 있습니다)")

    # 2. DB에 데이터 넣기
    # if_exists='replace': 기존 테이블이 있으면 지우고 새로 만듭니다 (초기화용)
    # if_exists='append': 기존 데이터 뒤에 추가합니다
    df.to_sql(name=TABLE_NAME, con=engine, if_exists='replace', index=False)

    print("✅ 데이터 업로드 완료! 이제 웹사이트를 새로고침 해보세요.")