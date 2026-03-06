from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geometry
from sqlalchemy import Index, text
from decimal import Decimal

db = SQLAlchemy()

# --------------------------------------------------------------------------
# 1. Models (테이블 정의)
# --------------------------------------------------------------------------

class Team(db.Model):
    __tablename__ = "teams"
    master_id = db.Column(db.Text, primary_key=True) 
    members = db.relationship('Users', backref='my_team', foreign_keys='Users.belong_to_team')

class Users(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Text, primary_key=True)
    user_pw = db.Column(db.Text)
    user_name = db.Column(db.Text)
    belong_to_team = db.Column(db.Text, db.ForeignKey('teams.master_id'))
    role = db.Column(db.Text, default="SLAVE")

    settings = db.relationship('UserSetting', backref='owner', cascade="all, delete-orphan")

class UserSetting(db.Model):
    __tablename__ = 'user_settings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # [핵심] 유저 테이블의 user_id를 참조함
    user_id = db.Column(db.Text, db.ForeignKey('users.user_id'), nullable=False)
    setting_key = db.Column(db.Text, nullable=False) # 예: 'column_order_v1'
    setting_value = db.Column(db.Text) # JSON 데이터가 문자열로 저장됨
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    # 유저 한 명당 특정 키는 하나만 존재하도록 제약 조건 설정
    __table_args__ = (db.UniqueConstraint('user_id', 'setting_key', name='_user_setting_uc'),)

class PropMain(db.Model):
    __tablename__ = 'prop_main'
    id = db.Column(db.Integer, name="매물번호", primary_key=True, autoincrement=True)
    pnu = db.Column(db.Text, name="고유번호", unique=True)
    manager_Id = db.Column(db.Text, name="담당자")
    progress = db.Column(db.Text, name="진행상태")
    sale_price_billon = db.Column(db.Numeric, name="매매가")
    sale_price_by_land_area = db.Column(db.Numeric, name="대지면적평단가")
    sale_price_by_floor_area = db.Column(db.Numeric, name="연면적평단가")
    total_security = db.Column(db.Numeric, name="총보증금")
    total_monthly_rent = db.Column(db.Numeric, name="총월세부가세별도")
    total_management_fee = db.Column(db.Numeric, name="총관리비")
    yield_rate = db.Column(db.Float, name="수익률")
    except_empty_yield = db.Column(db.Float, name="공실제외수익률")
    self_yield = db.Column(db.Float, name="자기자본수익률")
    invest_cash = db.Column(db.Numeric, name="자기자본")
    loan_rate = db.Column(db.Float, name="이자율")
    urgency = db.Column(db.Text, name="긴급도")
    grade = db.Column(db.Text, name="등급")
    location_quality = db.Column(db.Text, name="입지")
    building_usage = db.Column(db.Text, name="건물용도")
    photo = db.Column(db.Text, name="사진")
    briefing = db.Column(db.Text, name="브리핑")
    eviction = db.Column(db.Text, name="명도")
    demolition = db.Column(db.Text, name="멸실")
    usage_change = db.Column(db.Text, name="용도변경")
    ownertype = db.Column(db.Text, name="소유자타입")
    owner_name = db.Column(db.Text, name="소유자명")
    contact = db.Column(db.Text, name="전화번호")
    inclination = db.Column(db.Text, name="성향")
    relationship = db.Column(db.Text, name="관계")
    proped_date = db.Column(db.Date, name="접수일")
    video_timestamp = db.Column(db.Text, name="영상번호분초")
    intent_to_buy = db.Column(db.Text, name="매수의향서")
    toad_ad = db.Column(db.Text, name="빌탐정광고등록유무")

class PropMemo(db.Model):
    __tablename__ = 'prop_memos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pnu = db.Column(db.Text, db.ForeignKey('seoul_land_info.고유번호'), nullable=False)
    writer_id = db.Column(db.Text, db.ForeignKey('users.user_id'))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    importance = db.Column(db.Text)
    writer = db.relationship('Users', backref='written_memos')

class PropDetails(db.Model):
    __tablename__ = 'prop_details'
    __table_args__ = (db.UniqueConstraint('고유번호', '층', name='uix_prop_addr_floor'),)
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pnu = db.Column(db.Text, name="고유번호")
    floor = db.Column(db.Text, name="층")
    form = db.Column(db.Text, name="형태")
    size = db.Column(db.Float, name="평수")
    security = db.Column(db.Integer, name="보증금")
    rent = db.Column(db.Integer, name="임대료")
    management = db.Column(db.Integer, name="월관리비")
    lease_range = db.Column(db.Text, name="임대차기간")
    isEmpty = db.Column(db.Boolean, name="공실유무")
    created_at = db.Column(db.DateTime, name="생성일", default=db.func.now())

class SeoulLandInfo(db.Model):
    __tablename__ = 'seoul_land_info'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pnu = db.Column(db.Text, name="고유번호", unique=True)
    sido = db.Column(db.Text, name="시도")
    sigungu = db.Column(db.Text, name="시군구")
    address = db.Column(db.Text, name="주소")
    jimok = db.Column(db.Text, name="지목")
    land_usage_status = db.Column(db.Text, name="토지이용상황")
    shape = db.Column(db.Text, name="형상")
    road = db.Column(db.Text, name="도로")
    land_area = db.Column(db.Float, name="토지면적")
    build_land_area = db.Column(db.Float, name="대지면적")
    total_floor_area = db.Column(db.Float, name="연면적")
    building_area = db.Column(db.Float, name="건축면적")
    
    # [필수 추가] 테이블 연동 및 계산용 필드
    far_area = db.Column(db.Float, name="용적률산정연면적")
    floor_above = db.Column(db.Integer, name="규모지상")
    floor_below = db.Column(db.Integer, name="규모지하")
    elevator = db.Column(db.Integer, name="엘리베이터")
    parking = db.Column(db.Integer, name="주차장")
    approval_date = db.Column(db.Text, name="사용승인일")
    remodel_date = db.Column(db.Text, name="대수선및리모델링")
    
    zoning = db.Column(db.Text, name="용도지역")
    main_usage = db.Column(db.Text, name="주용도")
    ect_usage = db.Column(db.Text, name="기타용도")
    bc_ratio = db.Column(db.Float, name="건폐율")
    legal_bc_ratio = db.Column(db.Float, name="법정건폐율")
    far_ratio = db.Column(db.Float, name="용적률")
    legal_far_ratio = db.Column(db.Float, name="법정용적률")
    official_price = db.Column(db.Numeric, name="공시지가")
    official_price_5y = db.Column(db.Numeric, name="공시지가5년전")
    official_price_10y = db.Column(db.Numeric, name="공시지가10년전")
    
    official_price_growth_5y = db.Column(db.Float, name="공시지가상승률5년전")
    official_price_growth_10y = db.Column(db.Float, name="공시지가상승률10년전")
    bc_diff = db.Column(db.Float, name="건폐율법정건폐율")
    far_diff = db.Column(db.Float, name="용적률법정용적률")
    official_price_total = db.Column(db.Numeric, name="공시지가합계")
    official_price_base = db.Column(db.Numeric, name="공시지가기준")
    saleprice_officailprice_scale = db.Column(db.Float, name="총공시지가와매매가비율")
    
    # [필수 추가] AI추정가 및 매각 정보
    ai_price = db.Column(db.Text, name="AI추정가")
    ai_ratio = db.Column(db.Float, name="AI추정가매매가비율")
    naver_ad = db.Column(db.Numeric, name="네이버광고")
    naver_ad_past = db.Column(db.Numeric, name="네이버광고과거") 
    naver_ad_rate = db.Column(db.Float, name="네이버광고상승률")
    sale_date1 = db.Column(db.Text, name="매각일1")
    sale_date2 = db.Column(db.Text, name="매각일2")
    sale_date3 = db.Column(db.Text, name="매각일3")
    sale_amount_1 = db.Column(db.Numeric, name="매각액1")
    sale_amount_2 = db.Column(db.Numeric, name="매각액2")
    sale_amount_3 = db.Column(db.Numeric, name="매각액3")
    sale_rate = db.Column(db.Float, name="매각손익률")
    owner_current = db.Column(db.Text, name="소유자현재")
    owner_old = db.Column(db.Text, name="소유자과거")

    x = db.Column(db.Float(53))
    y = db.Column(db.Float(53))
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=False), name="geom")

    __table_args__ = (
        Index('idx_seoul_land_info_pnu', '고유번호'),
        Index('idx_seoul_land_info_geom', 'geom', postgresql_using='gist'),
    )

# --------------------------------------------------------------------------
# 2. Database Trigger Setup (자동화의 핵심)
# --------------------------------------------------------------------------

def setup_db_triggers(engine):
    """
    DB 트리거를 생성합니다. 
    마이그레이션 전/후 언제 호출되어도 에러가 나지 않도록 테이블 존재 여부를 체크합니다.
    """
    trigger_sql = """
    DO $$ 
    BEGIN
        -- seoul_land_info 테이블이 실제 존재할 때만 실행
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'seoul_land_info') THEN
            
            -- 1. 계산 함수 정의
            CREATE OR REPLACE FUNCTION fn_calculate_land_data()
            RETURNS TRIGGER AS $trg$
            DECLARE
                v_sale_price NUMERIC;
            BEGIN
                -- 공시지가 합계 & 기준 계산
                IF NEW.공시지가 IS NOT NULL AND NEW.토지면적 IS NOT NULL THEN
                    NEW.공시지가합계 := NEW.공시지가 * NEW.토지면적;
                    NEW.공시지가기준 := NEW.공시지가 * NEW.토지면적 * 1.9;
                END IF;

                -- 공시지가 상승률 계산
                IF NEW.공시지가5년전 IS NOT NULL AND NEW.공시지가5년전 > 0 THEN
                    NEW.공시지가상승률5년전 := ((NEW.공시지가 - NEW.공시지가5년전) / NEW.공시지가5년전) * 100;
                END IF;
                IF NEW.공시지가10년전 IS NOT NULL AND NEW.공시지가10년전 > 0 THEN
                    NEW.공시지가상승률10년전 := ((NEW.공시지가 - NEW.공시지가10년전) / NEW.공시지가10년전) * 100;
                END IF;

                -- 건폐율/용적률 차이 계산
                IF NEW.건폐율 IS NOT NULL AND NEW.법정건폐율 IS NOT NULL THEN
                    NEW.건폐율법정건폐율 := NEW.건폐율 - NEW.법정건폐율;
                END IF;
                IF NEW.용적률 IS NOT NULL AND NEW.법정용적률 IS NOT NULL THEN
                    NEW.용적률법정용적률 := NEW.용적률 - NEW.법정용적률;
                END IF;

                -- 네이버광고/매각손익 상승률 계산
                IF NEW.네이버광고 IS NOT NULL AND NEW.네이버광고과거 IS NOT NULL AND NEW.네이버광고과거 > 0 THEN
                    NEW.네이버광고상승률 := ((NEW.네이버광고 - NEW.네이버광고과거) / NEW.네이버광고과거) * 100;
                END IF;
                IF NEW.매각액1 IS NOT NULL AND NEW.매각액2 IS NOT NULL AND NEW.매각액2 > 0 THEN
                    NEW.매각손익률 := ((NEW.매각액1 - NEW.매각액2) / NEW.매각액2) * 100;
                END IF;

                -- 총공시지가와매매가비율 (매매가 억 단위를 원 단위로 변환 보정)
                SELECT 매매가 INTO v_sale_price FROM prop_main WHERE 고유번호 = NEW.고유번호 LIMIT 1;
                IF v_sale_price IS NOT NULL AND NEW.공시지가기준 IS NOT NULL AND NEW.공시지가기준 > 0 THEN
                    NEW.총공시지가와매매가비율 := (v_sale_price * 100000000) / NEW.공시지가기준;
                END IF;

                RETURN NEW;
            END;
            $trg$ LANGUAGE plpgsql;

            -- 2. 트리거 재생성 (기존 것 삭제 후 생성)
            DROP TRIGGER IF EXISTS trg_auto_calc_land ON seoul_land_info;
            CREATE TRIGGER trg_auto_calc_land
            BEFORE INSERT OR UPDATE ON seoul_land_info
            FOR EACH ROW EXECUTE FUNCTION fn_calculate_land_data();
            
        END IF;
    END $$;
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(trigger_sql))
            conn.commit()
    except Exception as e:
        # 이 시점에 에러가 나더라도 앱 기동이 멈추지 않도록 로그만 출력
        print(f"Trigger Setup Notice: {e}")