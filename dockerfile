FROM python:3.11
# 시스템 의존성 설치: PostgreSQL 클라이언트 라이브러리 (psycopg2-binary가 요구함)
RUN apt-get update && apt-get install -y libpq-dev gcc
# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 파일을 복사하고 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 나머지 애플리케이션 파일 복사 (app.py, templates 폴더 등)
# .dockerignore 파일을 사용하면 좋습니다.
COPY . .

# Flask 애플리케이션이 5000번 포트를 사용하므로 노출
EXPOSE 7070

# 컨테이너 시작 시 실행할 명령어 (Flask 서버 실행)
# Gunicorn 사용을 위해 CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]로 변경 권장
# 현재 app.py의 app.run 설정을 따르기 위해 아래 CMD 유지
CMD ["gunicorn", "--bind", "0.0.0.0:7070", "app:app"]