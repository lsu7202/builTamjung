# DB 자동 초기화 폴더

이 폴더는 postgres 컨테이너의 `/docker-entrypoint-initdb.d/`로 마운트되며,
**DB 볼륨이 최초 생성될 때 한 번만** 파일명 순서대로 자동 실행된다.

- `10_extensions.sql` — postgis / pg_trgm 확장 생성 (git 포함)
- `20_restore.sql` — **데이터 백업 복원용 (git 미포함, 직접 복사)**

## 새 PC에서 데이터까지 자동 세팅하는 법

1. 백업 파일(예: `backup_0609.sql`)을 이 폴더에 `20_restore.sql` 이름으로 복사
2. `docker compose up -d --build`
   - 볼륨이 이미 생성된 상태라면 먼저 `docker compose down -v` 로 볼륨 삭제 후 실행
3. 복원(수 분 소요)이 끝나면 flask 컨테이너가 자동으로 마이그레이션을 이어서 적용한다
   (백업 이후 추가된 시계열 테이블·통합주소 컬럼 등)

주의: `down -v`는 기존 볼륨의 데이터를 삭제한다. 이미 쓰고 있는 DB에는 절대 실행하지 말 것.
