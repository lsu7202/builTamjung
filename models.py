from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geometry
from sqlalchemy import Index

db = SQLAlchemy()

class PropDetails(db.Model):
    __tablename__ = 'prop_details'
    __table_args__ = (
        db.UniqueConstraint('통합주소', '층', name='uix_prop_addr_floor'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    addr_full = db.Column(db.Text, name="통합주소", index=True)
    floor = db.Column(db.Text, name="층")
    floor_sort = db.Column(db.Integer, name="정렬층")
    form = db.Column(db.Text, name="형태")
    size = db.Column(db.Float, name="평수")
    security = db.Column(db.Integer, name="보증금")
    rent = db.Column(db.Integer, name="임대료")
    management = db.Column(db.Integer, name="월관리비")
    lease_range = db.Column(db.Text, name="임대차기간")
    created_at = db.Column(db.DateTime, name="생성일", default=db.func.now())

class SeoulLandInfo(db.Model):
    __tablename__ = 'seoul_land_info'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    addr_full = db.Column(db.Text, name="통합주소")
    unique_no = db.Column(db.Text, name="고유번호")
    land_usage_status = db.Column(db.Text, name="토지이용상황")
    sido = db.Column(db.Text, name="시도")
    sigungu = db.Column(db.Text, name="시군구")
    address = db.Column(db.Text, name="주소")
    jimok = db.Column(db.Text, name="지목")
    shape = db.Column(db.Text, name="형상")
    road = db.Column(db.Text, name="도로")
    land_area = db.Column(db.Float, name="대지면적")
    total_floor_area = db.Column(db.Float, name="연면적")
    building_area = db.Column(db.Float, name="건축면적")
    zoning = db.Column(db.Text, name="용도지역")
    main_usage = db.Column(db.Text, name="주용도")
    other_usage = db.Column(db.Text, name="기타용도")
    bc_ratio = db.Column(db.Float, name="건폐율")
    legal_bc_ratio = db.Column(db.Float, name="법정건폐율")
    far_ratio = db.Column(db.Float, name="용적률")
    legal_far_ratio = db.Column(db.Float, name="법정용적률")
    far_calc_area = db.Column(db.Float, name="용적률산정연면적")
    scale_above = db.Column(db.Integer, name="규모지상")
    scale_below = db.Column(db.Integer, name="규모지하")
    elevator = db.Column(db.Integer, name="엘리베이터")
    parking = db.Column(db.Integer, name="주차장")
    approval_date = db.Column(db.Date, name="사용승인일")
    remodeling = db.Column(db.Date, name="대수선및리모델링")
    official_price = db.Column(db.Numeric, name="공시지가")
    official_price_5y = db.Column(db.Numeric, name="공시지가5년전")
    official_price_10y = db.Column(db.Numeric, name="공시지가10년전")
    sale_price_billon = db.Column(db.Numeric, name="매매가억")
    status = db.Column(db.Text, name="상황")
    urgency = db.Column(db.Text, name="긴급도")
    grade = db.Column(db.Text, name="등급")
    condition = db.Column(db.Text, name="컨디션")
    location_quality = db.Column(db.Text, name="입지")
    intent_to_buy = db.Column(db.Text, name="매수의향서")
    contact = db.Column(db.Text, name="연락처")
    inclination = db.Column(db.Text, name="성향")
    relationship = db.Column(db.Text, name="관계")
    photo = db.Column(db.Text, name="사진")
    briefing = db.Column(db.Text, name="브리핑")
    toad_ad = db.Column(db.Text, name="두꺼비광고등록유무")
    building_usage = db.Column(db.Text, name="건물용도")
    new_build_cost = db.Column(db.Numeric, name="신축비용")
    remodel_cost = db.Column(db.Text, name="리모델링비용")
    owner_status = db.Column(db.Text, name="지주상황")
    eviction = db.Column(db.Text, name="명도")
    usage_change = db.Column(db.Text, name="용도변경")
    demolition = db.Column(db.Text, name="멸실")
    video_timestamp = db.Column(db.Text, name="영상번호분초")
    ai_estimated_price = db.Column(db.Numeric, name="AI추정가")
    total_security = db.Column(db.Numeric, name="총보증금")
    total_monthly_rent = db.Column(db.Numeric, name="총월세부가세별도")
    total_management_fee = db.Column(db.Numeric, name="총관리비")
    yield_rate = db.Column(db.Float, name="수익률")
    naver_ad = db.Column(db.Numeric, name="네이버광고")
    naver_ad_past = db.Column(db.Numeric, name="네이버광고과거")
    sale_amount_1 = db.Column(db.Numeric, name="매각액1")
    sale_date_1 = db.Column(db.Integer, name="매각일1")
    sale_amount_2 = db.Column(db.Numeric, name="매각액2")
    sale_date_2 = db.Column(db.Integer, name="매각일2")
    sale_amount_3 = db.Column(db.Numeric, name="매각액3")
    sale_date_3 = db.Column(db.Integer, name="매각일3")
    x = db.Column(db.Float(53))
    y = db.Column(db.Float(53))
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=False), name="geom")

    # ⚠️ 관계 설정 다시 추가 (중요)
    details = db.relationship('PropDetails', 
                            primaryjoin="SeoulLandInfo.addr_full == PropDetails.addr_full", 
                            foreign_keys=[PropDetails.addr_full],
                            backref='land_master',
                            lazy=True)

    __table_args__ = (
        Index('idx_seoul_land_info_pnu', '고유번호'),
        Index('idx_seoul_land_info_geom', 'geom', postgresql_using='gist'),
        Index('ix_seoul_land_info_x', 'x'),
        Index('ix_seoul_land_info_y', 'y'),
    )