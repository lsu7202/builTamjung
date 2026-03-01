let PNU;

// 매물 정보 조회
/**
 * API를 이용해 매물 정보를 검색하고 결과값을 가져오는 함수
 * (각 인풋 항목 매칭 로직은 제외됨)
 */
async function searchPropertyData() {
    const address = `${document.getElementById('reg-sigungu').value} ${document.getElementById('reg-dong').value} ${document.getElementById('reg-address-input').value}`
    
    if (!address) {
        alert("주소를 입력해주세요.");
        return;
    }

    console.log(address)

    // 1. 주소를 PNU(고유번호)로 변환
    // bjdcode.js에서 제공하는 변환 함수 사용
    const pnuList = window.convertAddressToPNU(address);
    if (pnuList.length === 0) {
        alert("주소 형식이 올바르지 않거나 PNU 변환에 실패했습니다.");
        return;
    }

    try {
        // 2. 메인 매물 정보(seoul_land_info) 검색
        // /api/get_data는 필터 조건에 '고유번호' 리스트를 받음
        const resMain = await fetch('/api/get_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                "고유번호": pnuList,
                "limit": 1
            })
        });
        const mainResult = await resMain.json();
        const mainInfo = (mainResult.data && mainResult.data.length > 0) ? mainResult.data[0] : null;

        // 3. 건물층 상세 정보(prop_details) 검색
        // /api/get_propDetail은 단일 '고유번호'를 파라미터로 받음
        const resDetail = await fetch('/api/get_propDetail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                "고유번호": pnuList[0] 
            })
        });
        const detailResult = await resDetail.json();
        const detailInfo = detailResult.success ? detailResult.data : [];
        
        const resProp = await fetch(`/api/get_prop_main?고유번호=${pnuList[0]}`)
        const propData = await resProp.json();
        const propInfo = await propData.data || null;

        // 결과값 로그 출력 (사용자 확인용)
        console.log("--- 매물 검색 결과 ---");
        console.log("1. 메인 정보 (seoul_land_info):", mainInfo);
        console.log("2. 층별 상세 (prop_details):", detailInfo);
        console.log("3. 매물정보", propInfo);

        if (!mainInfo) {
            alert("DB에서 해당 매물 정보를 찾을 수 없습니다.");
        }

        // 결과 객체 반환 (추후 매칭 작업 시 사용 가능)
        return {
            main: mainInfo,
            details: detailInfo,
            prop: propInfo
        };

    } catch (e) {
        console.error("API 호출 중 오류 발생:", e);
        alert("서버 통신 중 오류가 발생했습니다.");
    }
}

async function fillPropertyDataHandler() {
    const rs = await searchPropertyData()
    const main = rs.main;
    PNU = main.고유번호;
    const details = rs.details;
    const prop = rs.prop;

    const session_rs = await loadSessionInfo()

    // --- 기존 변수 ---
    manager = document.getElementById('reg-manager')
    owner_type = document.getElementById('reg-owner-type')
    owner_name = document.getElementById('reg-owner-name')
    contact = document.getElementById('reg-contact')
    relationship = document.getElementById('reg-relationship')
    inclination = document.getElementById('reg-inclination')
    proped_date = document.getElementById('reg-proped-date')
    intent_to_buy = document.getElementById('reg-intent-to-buy')
    video_timestamp = document.getElementById('reg-video-timestamp')
    owner_details = document.getElementById('reg-owner-details')
    memo = document.getElementById('reg-memo')

    // --- 주소 및 검색 관련 ---
    sigungu = document.getElementById('reg-sigungu')
    dong = document.getElementById('reg-dong')
    address_input = document.getElementById('reg-address-input')

    // --- 메인 정보 (수익률/가격 등) ---
    sale_price = document.getElementById('reg-sale-price')
    yield_val = document.getElementById('reg-yield')
    total_security = document.getElementById('reg-total-security')
    total_rent = document.getElementById('reg-total-rent')
    total_manage = document.getElementById('reg-total-manage')
    price_land = document.getElementById('reg-price-land')
    price_total = document.getElementById('reg-price-total')
    gongsi_ratio = document.getElementById('reg-gongsi-ratio')
    prop_id = document.getElementById('reg-prop-id')
    invest_cash = document.getElementById('reg-invest-cash')
    loan_rate = document.getElementById('reg-loan-rate')

    // --- 진행 및 등급 정보 ---
    status = document.getElementById('reg-status')
    urgency = document.getElementById('reg-urgency')
    location_grade = document.getElementById('reg-location')
    grade = document.getElementById('reg-grade')
    b_usage = document.getElementById('reg-b-usage')
    has_photo = document.getElementById('reg-has-photo')
    has_brief = document.getElementById('reg-has-brief')
    eviction = document.getElementById('reg-eviction')
    usage_change = document.getElementById('reg-usage-change')
    demolition = document.getElementById('reg-demolition')

    // --- 건물 상세 정보 ---
    floor_above = document.getElementById('reg-floor-above')
    floor_below = document.getElementById('reg-floor-below')
    land_area = document.getElementById('reg-land-area')
    build_area = document.getElementById('reg-build-area')
    total_area_val = document.getElementById('reg-total-area-val')
    far_area = document.getElementById('reg-far-area')
    elevator = document.getElementById('reg-elevator')
    parking = document.getElementById('reg-parking')
    approval_date = document.getElementById('reg-approval-date')
    remodel_date = document.getElementById('reg-remodel-date')
    bc_ratio = document.getElementById('reg-bc-ratio')
    legal_bc = document.getElementById('reg-legal-bc')
    bc_diff = document.getElementById('reg-bc-diff')
    far_ratio = document.getElementById('reg-far-ratio')
    legal_far = document.getElementById('reg-legal-far')
    far_diff = document.getElementById('reg-far-diff')

    // --- 토지 정보 ---
    total_land_area = document.getElementById('reg-total-land-area')
    jimok = document.getElementById('reg-jimok')
    zoning = document.getElementById('reg-zoning')
    land_status = document.getElementById('reg-land-status')
    main_code = document.getElementById('reg-main-code')
    shape = document.getElementById('reg-shape')
    road = document.getElementById('reg-road')
    other_usage = document.getElementById('reg-other-usage')
    gongsi_cur = document.getElementById('reg-gongsi-cur')
    gongsi_total = document.getElementById('reg-gongsi-total')
    gongsi_5y = document.getElementById('reg-gongsi-5y')
    gongsi_10y = document.getElementById('reg-gongsi-10y')

    // --- 매각 정보 ---
    sale_date1 = document.getElementById('reg-sale-date1')
    sale_amt1 = document.getElementById('reg-sale-amt1')
    sale_date2 = document.getElementById('reg-sale-date2')
    sale_amt2 = document.getElementById('reg-sale-amt2')
    sale_date3 = document.getElementById('reg-sale-date3')
    sale_amt3 = document.getElementById('reg-sale-amt3')
    sale_profit = document.getElementById('reg-sale-profit')

    // --- 네이버 광고 및 기타 ---
    naver_cur = document.getElementById('reg-naver-cur')
    naver_past = document.getElementById('reg-naver-past')
    naver_rate = document.getElementById('reg-naver-rate')
    builtamjung_ad = document.getElementById('reg-builtamjung-ad')


    // [세부 정보 및 담당자]
    // 담당자가 없으면 현재 로그인한 세션 유저 ID로 세팅
    manager.value = prop.담당자 || session_rs.user_name || "";
    owner_type.value = prop.소유자타입 || "개인"; // 기본값 설정
    owner_name.value = prop.소유자명 || "";
    contact.value = prop.전화번호 || "";
    relationship.value = prop.관계 || "건물주/법인대표";
    inclination.value = prop.성향 || "";
    proped_date.value = prop.접수일 || new Intl.DateTimeFormat('fr-CA').format(new Date());
    intent_to_buy.value = prop.매수의향서 || "";
    video_timestamp.value = prop.영상번호분초 || "";
    owner_details.value = prop.소유자현재 || ""; // DB 필드명 '소유자현재' 매핑

    // [메인 정보 - 수익률/가격]
    sale_price.value = prop.매매가억 || "";
    yield_val.value = prop.수익률 || "";
    total_security.value = prop.총보증금 || "";
    total_rent.value = prop.총월세부가세별도 || "";
    total_manage.value = prop.총관리비 || "";
    price_land.value = prop.대지면적평단가 || "";
    price_total.value = prop.연면적평단가 || "";
    gongsi_ratio.value = prop.총공시지가와매매가비율 || "";
    prop_id.value = prop.매물번호 || "";
    // invest_cash, loan_rate는 보통 계산용이므로 초기값 0 또는 빈값
    invest_cash.value = "";
    loan_rate.value = "";

    // [진행 및 등급]
    // 중복 ID 주의: HTML에서 urgency와 status 구분 필요
    if(status) status.value = prop.진행상태 || "준비"; 
    urgency.value = prop.긴급도 || "없음";
    location_grade.value = prop.입지 || "";
    grade.value = prop.등급 || "";
    b_usage.value = prop.건물용도 || "";
    has_photo.value = prop.사진 || "무";
    has_brief.value = prop.브리핑 || "무";
    eviction.value = prop.명도 || "확인중";
    usage_change.value = prop.용도변경 || "확인중";
    demolition.value = prop.멸실 || "확인중";

    // [건물 정보]
    floor_above.value = main.규모지상 || "";
    floor_below.value = main.규모지하 || "";
    land_area.value = main.대지면적 || "";
    build_area.value = main.건축면적 || "";
    total_area_val.value = main.연면적 || "";
    far_area.value = main.용적률산정연면적 || "";
    elevator.value = main.엘리베이터 || 0;
    parking.value = main.주차장 || 0;
    approval_date.value = main.사용승인일 || "";
    remodel_date.value = main.대수선및리모델링 || "";
    
    // 비율 데이터 (Readonly 필드들)
    bc_ratio.value = main.건폐율 || "";
    legal_bc.value = main.법정건폐율 || "";
    far_ratio.value = main.용적률 || "";
    legal_far.value = main.법정용적률 || "";

    // [토지 정보]
    total_land_area.value = main.대지면적 || ""; // 혹은 main.토지면적
    jimok.value = main.지목 || "";
    zoning.value = main.용도지역 || "";
    land_status.value = main.토지이용상황 || "";
    main_code.value = main.주용도 || "";
    shape.value = main.형상 || "";
    road.value = main.도로 || "";
    other_usage.value = main.기타용도 || "";
    gongsi_cur.value = main.공시지가 || "";
    gongsi_5y.value = main.공시지가5년전 || "";
    gongsi_10y.value = main.공시지가10년전 || "";

    // [매각 및 네이버 정보]
    sale_date1.value = main.매각일1 || "";
    sale_amt1.value = main.매각액1 || "";
    sale_profit.value = main.매각손익률 || "";
    naver_cur.value = main.네이버광고 || "";
    naver_past.value = main.네이버광고과거 || "";
    naver_rate.value = main.네이버광고상승률 || "";
    builtamjung_ad.value = main.빌탐정광고등록유무 || "무";

    console.log("모든 데이터 매칭 완료");
    
    // 데이터 로드 후 자동으로 계산 함수 실행 (필요 시)
    if (typeof calculatePropertyStats === "function") {
        calculatePropertyStats();
    }
    


}


// 메모 저장 및 수정 통합 함수
async function saveMemo() {
    const pnu = PNU;
    const content = document.getElementById('reg-memo').value;
    const importance = document.getElementById('reg-importance').value;
    const memoId = document.getElementById('edit-memo-id').value;

    if (!pnu) return alert("매물 정보(PNU)가 없습니다.");
    if (!content) return alert("내용을 입력해주세요.");

    // ID가 있으면 수정(update), 없으면 신규(add)
    const url = memoId ? '/api/update_memo' : '/api/add_memo';
    const payload = memoId ? { id: memoId, content, importance } : { pnu, content, importance };

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (response.ok) {
        document.getElementById('reg-memo').value = "";
        document.getElementById('edit-memo-id').value = "";
        document.getElementById('btn-save-memo').innerText = "입력 (Ctrl+Enter)";
        loadMemos(pnu); // 목록 새로고침
    } else {
        alert("저장에 실패했습니다.");
    }
}

// 메모 불러오기 및 화면 그리기
async function loadMemos(pnu) {
    const container = document.getElementById('memo-list-container');
    if (!pnu) return;

    const response = await fetch(`/api/load_memos?pnu=${pnu}`);
    const data = await response.json();
    
    container.innerHTML = ""; // 기존 목록 비우기

    if (data.memos.length === 0) {
        container.innerHTML = `<p class="text-center text-gray-400 text-xs mt-10">등록된 메모가 없습니다.</p>`;
        return;
    }

    data.memos.forEach(memo => {
        // 중요도별 색상 지정
        let bgColor = "bg-gray-100 border-gray-200"; // 일반
        if (memo.importance === "중요") bgColor = "bg-yellow-50 border-yellow-200 text-yellow-900";
        if (memo.importance === "매우중요") bgColor = "bg-purple-50 border-purple-200 text-purple-900";

        const memoBox = document.createElement('div');
        memoBox.className = `${bgColor} p-3 rounded-lg border shadow-sm cursor-pointer hover:brightness-95 transition-all`;
        memoBox.onclick = () => prepareUpdate(memo); // 클릭 시 수정 모드
        
        memoBox.innerHTML = `
            <div class="flex justify-between items-start mb-1">
                <span class="text-[10px] font-bold opacity-70">${memo.writer_name}</span>
                <span class="text-[9px] opacity-50">${memo.created_at}</span>
            </div>
            <p class="text-xs whitespace-pre-wrap">${memo.content}</p>
        `;
        container.appendChild(memoBox);
    });
}

// 수정 모드 전환
function prepareUpdate(memo) {
    document.getElementById('reg-memo').value = memo.content;
    document.getElementById('reg-importance').value = memo.importance || "일반";
    document.getElementById('edit-memo-id').value = memo.id;
    document.getElementById('btn-save-memo').innerText = "수정 완료";
    document.getElementById('reg-memo').focus();
}



// 매물 정보 수정


/**
 * 1. 숫자 서식 변환 헬퍼 (UI '억' <-> DB '실제 숫자')
 * 1.2억 입력 -> 120,000,000 반환
 */
function eokToFullValue(eokStr) {
    if (!eokStr) return 0;
    return Math.round(parseFloat(eokStr) * 100000000);
}

/**
 * 2. 시군구/법정동 동적 초기화
 * DIVISIONS 데이터를 활용해 내 매물 섹션의 셀렉트박스를 채웁니다.
 */
function initRegRegionSelectors() {
    const siSelect = document.getElementById('reg-sigungu');
    const dongSelect = document.getElementById('reg-dong');
    
    siSelect.innerHTML = '<option value="">시군구 선택</option>';
    Object.keys(DIVISIONS).forEach(si => {
        const opt = document.createElement('option');
        opt.value = si; opt.innerText = si;
        siSelect.appendChild(opt);
    });

    siSelect.onchange = () => {
        const si = siSelect.value;
        dongSelect.innerHTML = '<option value="">법정동 선택</option>';
        if (DIVISIONS[si]) {
            DIVISIONS[si].forEach(dong => {
                const opt = document.createElement('option');
                opt.value = dong; opt.innerText = dong;
                dongSelect.appendChild(opt);
            });
        }
    };
}
// myProp.js

/**
 * 1. 전역 단위 토글 연동 (index.html의 btnToggleUnit 클릭 이벤트 확장)
 */
document.getElementById('btnToggleUnit').addEventListener('click', function() {
    // isPyungMode는 이미 index.html에서 토글됨
    const unit = isPyungMode ? "평" : "㎡";
    
    // 라벨 일괄 변경
    document.querySelectorAll('.unit-label').forEach(el => el.innerText = unit);

    // 입력된 면적값들 환산 (area-input 클래스 순회)
    document.querySelectorAll('.area-input').forEach(input => {
        const val = parseFloat(input.value);
        if (!isNaN(val)) {
            if (isPyungMode) {
                input.value = (val * 0.3025).toFixed(2); // m2 -> 평
            } else {
                input.value = (val / 0.3025).toFixed(2); // 평 -> m2
            }
        }
    });

    // 환산 후 수식 재계산
    calculatePropertyStats();
});

function addFloorRow(data = null) {
    const container = document.getElementById('floor-rows-container');
    const row = document.createElement('div');
    row.className = "grid grid-cols-12 gap-2 p-2 bg-white border border-gray-200 rounded-lg items-center shadow-sm property-row";

    const floor = data ? data.층 : "";
    const type = data ? data.형태 : "";
    const area = data ? data.평수 : "";
    const sec = data ? data.보증금 : "";
    const rent = data ? data.임대료 : "";
    const man = data ? data.월관리비 : "";
    const lease = data ? data.임대차기간 : "";
    const empty = data ? data.공실유무 : "무"; // 기본값 '무'

    row.innerHTML = `
        <div class="col-span-1"><input type="text" class="w-full border rounded px-1 py-1 text-[11px] font-bold text-center" value="${floor}" oninput="calculatePropertyStats()"></div>
        <div class="col-span-2"><input type="text" class="w-full border rounded px-1 py-1 text-[11px]" value="${type}"></div>
        <div class="col-span-1"><input type="number" class="w-full border rounded px-1 py-1 text-[11px] text-right" value="${area}" oninput="calculatePropertyStats()"></div>
        <div class="col-span-2"><input type="number" class="floor-sec w-full border rounded px-1 py-1 text-[11px] text-right" value="${sec}" oninput="calculatePropertyStats()"></div>
        <div class="col-span-2"><input type="number" class="floor-rent w-full border rounded px-1 py-1 text-[11px] text-right" value="${rent}" oninput="calculatePropertyStats()"></div>
        <div class="col-span-1"><input type="number" class="floor-man w-full border rounded px-1 py-1 text-[11px] text-right" value="${man}" oninput="calculatePropertyStats()"></div>
        <div class="col-span-1"><input type="text" class="w-full border rounded px-1 py-1 text-[11px]" value="${lease}"></div>
        <div class="col-span-1">
            <select class="floor-empty w-full border rounded p-1 text-[11px]" onchange="calculatePropertyStats()">
                <option value="무" ${empty === '무' ? 'selected' : ''}>무</option>
                <option value="유" ${empty === '유' ? 'selected' : ''}>유</option>
            </select>
        </div>
        <div class="col-span-1 text-center">
            <button onclick="this.parentElement.parentElement.remove(); calculatePropertyStats();" class="text-red-400 hover:text-red-600"><i class="fa-solid fa-trash-can"></i></button>
        </div>
    `;
    container.appendChild(row);
    calculatePropertyStats();
}
/**
 * 2. 통합 수식 계산기 (단위 보정 포함)
 */
function calculatePropertyStats() {
    const salePriceEok = parseFloat(document.getElementById('reg-sale-price')?.value) || 0;
    const totalSecurityMan = parseFloat(document.getElementById('reg-total-security')?.value) || 0;
    const totalRentMan = parseFloat(document.getElementById('reg-total-rent')?.value) || 0;

    // 면적 데이터들 (현재 화면에 보이는 단위 기준)
    const landAreaIn = parseFloat(document.getElementById('reg-land-area')?.value) || 0;   // 대지면적
    const buildAreaIn = parseFloat(document.getElementById('reg-build-area')?.value) || 0; // 건축면적
    const totalAreaIn = parseFloat(document.getElementById('reg-total-area-val')?.value) || 0; // 연면적
    const farAreaIn = parseFloat(document.getElementById('reg-far-area')?.value) || 0;     // 용적률산정용

    // 계산을 위한 표준화 (평단가는 평으로, 건폐/용적/공시지가는 m2로 환산)
    const landPy = isPyungMode ? landAreaIn : landAreaIn * 0.3025;
    const totalPy = isPyungMode ? totalAreaIn : totalAreaIn * 0.3025;
    const landM2 = isPyungMode ? landAreaIn / 0.3025 : landAreaIn;

    // A. 수익률 = (월세*12) / (매매가-보증금) * 100
    let currentSum = { sec: 0, rent: 0, man: 0 }; 
    let fullSum = { sec: 0, rent: 0, man: 0 };

    // 층별 데이터 순회하며 시나리오별 합산
    document.querySelectorAll('.property-row').forEach(row => {
        const s = parseFloat(row.querySelector('.floor-sec')?.value) || 0;
        const r = parseFloat(row.querySelector('.floor-rent')?.value) || 0;
        const m = parseFloat(row.querySelector('.floor-man')?.value) || 0;
        const isEmpty = row.querySelector('.floor-empty')?.value === "유";

        fullSum.sec += s; fullSum.rent += r; fullSum.man += m;
        if (!isEmpty) { currentSum.sec += s; currentSum.rent += r; currentSum.man += m; }
    });

    document.getElementById('reg-total-security').value = fullSum.sec;
    document.getElementById('reg-total-rent').value = fullSum.rent;
    document.getElementById('reg-total-manage').value = fullSum.man;

    // 수익률 계산 함수 (매매가-보증금 기준)
    const calcYield = (s, r) => {
        const netPrice = (salePriceEok * 10000) - s;
        return netPrice > 0 ? ((r * 12) / netPrice * 100).toFixed(2) + "%" : "-";
    };

    // UI 출력
    document.getElementById('sum-yield-current').innerText = calcYield(currentSum.sec, currentSum.rent);
    document.getElementById('sum-sec-current').innerText = currentSum.sec.toLocaleString() + "만";
    document.getElementById('sum-rent-current').innerText = currentSum.rent.toLocaleString() + "만";
    document.getElementById('sum-man-current').innerText = currentSum.man.toLocaleString() + "만";

    document.getElementById('sum-yield-full').innerText = calcYield(fullSum.sec, fullSum.rent);
    document.getElementById('sum-sec-full').innerText = fullSum.sec.toLocaleString() + "만";
    document.getElementById('sum-rent-full').innerText = fullSum.rent.toLocaleString() + "만";
    document.getElementById('sum-man-full').innerText = fullSum.man.toLocaleString() + "만";
    document.getElementById('reg-yield').value = calcYield(fullSum.sec, fullSum.rent);



    // B. 평단가 (항상 평당 금액으로 노출)
    if (landPy > 0) document.getElementById('reg-price-land').value = (salePriceEok / landPy).toFixed(2) + " 억/평";
    if (totalPy > 0) document.getElementById('reg-price-total').value = (salePriceEok / totalPy).toFixed(2) + " 억/평";

    // C. 건폐율/용적률 (단위가 같으므로 그대로 계산)
    if (landAreaIn > 0) {
        const bc = (buildAreaIn / landAreaIn) * 100;
        const far = (farAreaIn / landAreaIn) * 100;
        document.getElementById('reg-bc-ratio').value = bc.toFixed(2) + "%";
        document.getElementById('reg-far-ratio').value = far.toFixed(2) + "%";
    }

    // D. 공시지가 기준가 비율 (m2당 단가인 공시지가 기준)
    const gongsiCur = parseFloat(document.getElementById('reg-gongsi-cur')?.value) || 0;
    if (landM2 > 0 && gongsiCur > 0 && salePriceEok > 0) {
        const baseEok = (landM2 * gongsiCur * 1.9) / 100000000;
        const ratio = (baseEok / salePriceEok) * 100;
        document.getElementById('reg-gongsi-ratio').value = ratio.toFixed(2) + "%";
    }

    // E. 자기자본 수익률 (제시된 EX 로직)
    const investCashEok = parseFloat(document.getElementById('reg-invest-cash')?.value) || 0;
    const loanRate = parseFloat(document.getElementById('reg-loan-rate')?.value) || 0;

    if (investCashEok > 0) {
        const loanAmountEok = salePriceEok - (totalSecurityMan/10000) - investCashEok;
        document.getElementById('loan-amount-display').innerText = `대출 ${loanAmountEok.toFixed(1)}억`;
        
        const annualIntMan = (loanAmountEok * 10000) * (loanRate / 100);
        const annualRentMan = totalRentMan * 12;
        const selfYield = (annualRentMan - annualIntMan) / (investCashEok * 10000) * 100;
        document.getElementById('reg-self-yield-display').innerText = selfYield.toFixed(2) + "%";
    }

}

/**
 * 4. 최종 저장 전 데이터 정제 (app.py 전송용)
 * 억 단위를 모두 풀어서 DB용 숫자로 만듭니다.
 */
function prepareDataForDB() {
    const rawPrice = document.getElementById('reg-sale-price').value;
    const dbPrice = eokToFullValue(rawPrice); // 1.2 -> 120,000,000
    
    // ... 나머지 필드들도 동일하게 가공하여 fetch() 보낼 객체 생성
}

// 윈도우 로드 시 지역 셀렉터 실행
window.addEventListener('DOMContentLoaded', initRegRegionSelectors);