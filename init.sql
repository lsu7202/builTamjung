-- 1. PostGIS 확장 설치
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. 부동산 데이터 테이블 생성
CREATE TABLE IF NOT EXISTS seoul_land_info (
    id SERIAL PRIMARY KEY,
    "통합주소" TEXT UNIQUE,
    "고유번호" TEXT,
    "토지이용상황" TEXT,
    "시도" TEXT,
    "시군구" TEXT,
    "주소" TEXT,
    "지목" TEXT,
    "형상" TEXT,
    "도로" TEXT,
    "대지면적" TEXT,
    "연면적" TEXT,
    "건축면적" TEXT,
    "용도지역" TEXT,
    "주용도" TEXT,
    "기타용도" TEXT,
    "건폐율" TEXT,
    "법정건폐율" TEXT,
    "건폐율법정건폐율" TEXT,
    "용적률" TEXT,
    "법정용적률" TEXT,
    "용적률법정용적률" TEXT,
    "용적률산정용연면적" TEXT,
    "규모지상" TEXT,
    "규모지하" TEXT,
    "엘리베이터" TEXT,
    "주차장" TEXT,
    "사용승인일" TEXT,
    "대수선및리모델링" TEXT,
    "구분상가구분" TEXT,
    "공시지가" TEXT,
    "공시지가5년전" TEXT,
    "공시지가10년전" TEXT,
    "공시지가상승률5년전" TEXT,
    "공시지가상승률10년전" TEXT,
    "공시지가기준" TEXT,
    "매매가억" TEXT,
    "총공시지가와매매가비율" TEXT,
    "상황" TEXT,
    "긴급도" TEXT,
    "등급" TEXT,
    "컨디션" TEXT,
    "입지" TEXT,
    "매수의향서" TEXT,
    "연락처" TEXT,
    "성향" TEXT,
    "관계" TEXT,
    "사진" TEXT,
    "브리핑" TEXT,
    "두꺼비광고등록유무" TEXT,
    "건물용도" TEXT,
    "신축비용" TEXT,
    "리모델링비용" TEXT,
    "지주상황" TEXT,
    "명도" TEXT,
    "용도변경" TEXT,
    "멸실" TEXT,
    "영상번호분초" TEXT,
    "AI추정가" TEXT,
    "AI추정가매매가비율" TEXT,
    "네이버광고" TEXT,
    "네이버광고과거" TEXT,
    "네이버광고상승률" TEXT,
    "매각액1" TEXT,
    "매각일1" TEXT,
    "매각액2" TEXT,
    "매각일2" TEXT,
    "매각액3" TEXT,
    "매각일3" TEXT,
    "x" FLOAT,
    "y" FLOAT,
    "geom" GEOMETRY(Point, 4326)
);

-- 3. 검색 성능 최적화를 위한 인덱스 자동 생성
-- 주소 검색 속도 향상
CREATE INDEX IF NOT EXISTS idx_land_address ON seoul_land_info("통합주소");

-- 지도 범위 검색(공간 쿼리) 속도 향상 (GIST 인덱스)
CREATE INDEX IF NOT EXISTS idx_land_geom ON seoul_land_info USING GIST("geom");

-- 좌표 기준 검색 속도 향상
CREATE INDEX IF NOT EXISTS idx_land_x ON seoul_land_info("x");
CREATE INDEX IF NOT EXISTS idx_land_y ON seoul_land_info("y");


-- -- 1. x, y를 geom으로 변환하는 함수 생성
-- CREATE OR REPLACE FUNCTION update_geom_from_xy()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.x IS NOT NULL AND NEW.y IS NOT NULL THEN
--         NEW.geom := ST_SetSRID(ST_MakePoint(NEW.x, NEW.y), 4326);
--     END IF;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- 2. 데이터가 들어오거나 수정될 때마다 함수 실행하도록 트리거 설정
-- CREATE TRIGGER trg_update_geom
-- BEFORE INSERT OR UPDATE ON seoul_land_info
-- FOR EACH ROW
-- EXECUTE FUNCTION update_geom_from_xy();