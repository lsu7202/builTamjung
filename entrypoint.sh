#!/bin/sh

# 1. DB가 준비될 때까지 잠시 대기 (선택사항)
sleep 3

# 2. 마이그레이션 폴더가 없으면 초기화 (처음 한 번만 실행됨)
if [ ! -d "migrations" ]; then
    flask db init
fi

# 3. 모델 변경사항을 감지해서 마이그레이션 파일 생성
# (실제 운영 환경에서는 migrate는 로컬에서 하고 upgrade만 자동화하는 게 안전하긴 함)
flask db migrate -m "auto migration" || echo "No changes to migrate"

# 4. DB를 최신 모델 상태로 업그레이드 (데이터 유지하며 컬럼 추가)
flask db upgrade

# 5. 원래 실행하려던 Flask 앱(Gunicorn) 실행
exec "$@"