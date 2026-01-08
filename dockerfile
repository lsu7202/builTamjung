FROM python:3.11

# 1. 시스템 의존성 설치 (PostgreSQL 클라이언트 및 PostGIS 관련 라이브러리)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    postgis \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. 의존성 설치 (requirements.txt에 flask-migrate, geoalchemy2 필수 포함!)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 소스 코드 복사
COPY . .

# 4. 실행 권한 부여 (entrypoint 스크립트 사용 시 필요)
# 아래 'entrypoint.sh'를 만드는 대신 CMD에서 바로 처리하는 방법으로 가겠습니다.

EXPOSE 7070

# 5. 실행 명령어 수정 (DB 업데이트 후 Gunicorn 실행)
# 💡 핵심: flask db upgrade를 먼저 실행해서 모델 변경사항을 DB에 반영함
CMD sh -c "flask db upgrade && gunicorn --worker-class gevent --workers 4 --bind 0.0.0.0:7070 --timeout 120 app:app"