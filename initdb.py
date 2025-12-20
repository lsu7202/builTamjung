import psycopg2

# --- DB 설정 (upload_csv.py와 동일하게 맞춰주세요) ---
DB_HOST = "localhost"
DB_PORT = "5433"      # 주의: 아까 5433으로 바꾸셨다면 5433, 아니면 5432
DB_USER = "iseung-ug" # .env 파일 내용
DB_PASS = "1234"   # .env 파일 내용
DB_NAME = "postgres" # .env 파일 내용

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