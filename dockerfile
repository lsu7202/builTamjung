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

# 4. ENTRYPOINT 설정
#    /app 밖(/entrypoint.sh)에 두는 이유: docker-compose가 개발 편의로 .:/app을 마운트하는데,
#    /app 안에 두면 호스트 폴더가 이미지 파일을 가려서 (특히 Windows에서) 실행이 깨진다.
#    sed로 CRLF 제거: Windows에서 빌드해도 shebang이 깨지지 않도록 방어.
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 7070

# 5. 실행 명령어 (entrypoint.sh의 "$@"로 전달됨)
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "4", "--bind", "0.0.0.0:7070", "--timeout", "120", "app:app"]