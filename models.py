from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geometry

db = SQLAlchemy()

class PropDetails(db.Model):
    __tablename__ = 'prop_details'

    # 복합 유니크 제약조건: 한 건물(통합주소)에 같은 층은 하나만 존재
    __table_args__ = (
        db.UniqueConstraint('통합주소', '층', name='uix_prop_addr_floor'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 서울랜드인포와 매핑할 기준 컬럼
    # 만약 DB 수준에서 강력하게 묶고 싶다면 ForeignKey('seoul_land_info.통합주소')를 쓸 수도 있습니다.
    addr_full = db.Column(db.Text, name="통합주소", index=True)
    
    floor = db.Column(db.Text, name="층")
    floor_sort = db.Column(db.Integer, name="정렬층")
    form = db.Column(db.Text, name="형태")
    size = db.Column(db.Integer, name="평수")
    lease_range = db.Column(db.Text, name="임대차기간") # 'range'는 예약어일 수 있어 컬럼명 조정 권장
    created_at = db.Column(db.DateTime, name="생성일", default=db.func.now())

    def __repr__(self):
        return f'<Detail {self.addr_full} {self.floor}>'


class SeoulLandInfo(db.Model):
    __tablename__ = 'seoul_land_info'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    addr_full = db.Column(db.Text, name="통합주소", index=True) # 중복 허용, 인덱스 유지
    unique_no = db.Column(db.Text, name="고유번호")
    land_usage_status = db.Column(db.Text, name="토지이용상황")
    sido = db.Column(db.Text, name="시도")
    sigungu = db.Column(db.Text, name="시군구")
    address = db.Column(db.Text, name="주소")
    jimok = db.Column(db.Text, name="지목")
    shape = db.Column(db.Text, name="형상")
    road = db.Column(db.Text, name="도로")
    land_area = db.Column(db.Text, name="대지면적")
    total_floor_area = db.Column(db.Text, name="연면적")
    building_area = db.Column(db.Text, name="건축면적")
    zoning = db.Column(db.Text, name="용도지역")
    main_usage = db.Column(db.Text, name="주용도")
    other_usage = db.Column(db.Text, name="기타용도")
    bc_ratio = db.Column(db.Text, name="건폐율")
    legal_bc_ratio = db.Column(db.Text, name="법정건폐율")
    bc_ratio_status = db.Column(db.Text, name="건폐율법정건폐율")
    far_ratio = db.Column(db.Text, name="용적률")
    legal_far_ratio = db.Column(db.Text, name="법정용적률")
    far_ratio_status = db.Column(db.Text, name="용적률법정용적률")
    far_calc_area = db.Column(db.Text, name="용적률산정용연면적")
    scale_above = db.Column(db.Text, name="규모지상")
    scale_below = db.Column(db.Text, name="규모지하")
    elevator = db.Column(db.Text, name="엘리베이터")
    parking = db.Column(db.Text, name="주차장")
    approval_date = db.Column(db.Text, name="사용승인일")
    remodeling = db.Column(db.Text, name="대수선및리모델링")
    shop_division = db.Column(db.Text, name="구분상가구분")
    official_price = db.Column(db.Text, name="공시지가")
    official_price_5y = db.Column(db.Text, name="공시지가5년전")
    official_price_10y = db.Column(db.Text, name="공시지가10년전")
    price_growth_5y = db.Column(db.Text, name="공시지가상승률5년전")
    price_growth_10y = db.Column(db.Text, name="공시지가상승률10년전")
    price_standard = db.Column(db.Text, name="공시지가기준")
    sale_price_billon = db.Column(db.Text, name="매매가억")
    price_ratio = db.Column(db.Text, name="총공시지가와매매가비율")
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
    new_build_cost = db.Column(db.Text, name="신축비용")
    remodel_cost = db.Column(db.Text, name="리모델링비용")
    owner_status = db.Column(db.Text, name="지주상황")
    eviction = db.Column(db.Text, name="명도")
    usage_change = db.Column(db.Text, name="용도변경")
    demolition = db.Column(db.Text, name="멸실")
    video_timestamp = db.Column(db.Text, name="영상번호분초")
    ai_estimated_price = db.Column(db.Text, name="AI추정가")
    ai_price_ratio = db.Column(db.Text, name="AI추정가매매가비율")
    naver_ad = db.Column(db.Text, name="네이버광고")
    naver_ad_past = db.Column(db.Text, name="네이버광고과거")
    naver_ad_growth = db.Column(db.Text, name="네이버광고상승률")
    sale_amount_1 = db.Column(db.Text, name="매각액1")
    sale_date_1 = db.Column(db.Text, name="매각일1")
    sale_amount_2 = db.Column(db.Text, name="매각액2")
    sale_date_2 = db.Column(db.Text, name="매각일2")
    sale_amount_3 = db.Column(db.Text, name="매각액3")
    sale_date_3 = db.Column(db.Text, name="매각일3")
    
    # 숫자 및 공간 데이터 (인덱스 추가)
    x = db.Column(db.Float, index=True)
    y = db.Column(db.Float, index=True)
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326))

    # SeoulLandInfo 클래스 내부에 추가
    details = db.relationship('PropDetails', 
                            primaryjoin="SeoulLandInfo.addr_full == PropDetails.addr_full", 
                            foreign_keys=[PropDetails.addr_full],
                            backref='land_master',
                            lazy=True)
