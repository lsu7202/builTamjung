FROM python:3.11

# 1. 시스템 의존성 설치 (pg_isready 사용을 위해 postgresql-client 필수)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    postgis \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 소스 코드 복사
COPY . .

# 4. 실행 권한 부여 및 ENTRYPOINT 설정
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]

EXPOSE 7070

# 5. 실행 명령어 (entrypoint.sh의 "$@"로 전달됨)
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "4", "--bind", "0.0.0.0:7070", "--timeout", "120", "app:app"]