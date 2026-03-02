/**
 * 빌탐정 (BuilTamjung) - 매물 관리 통합 스크립트
 * 모든 수치는 '원/㎡' 단위로 내부 관리하며, 화면 출력 시에만 단위 변환을 수행합니다.
 */

let PNU; // 전역 PNU 고유번호

// =========================================================
// 1. 중앙 단위 및 가치 매니저 (Val Manager)
// =========================================================
const Val = {
    // 모든 데이터 유닛 정의
    units: { eok: 100000000, man: 10000, won: 1, area: 1, rate: 1, percent: 1, text: 1, gongsi: 1 },

    // 원본 데이터 가져오기 (항상 Won/㎡ 기준)
    get: function (id) {
        const el = document.getElementById(id);
        if (!el) return "";
        const unit = el.dataset.unit || 'won';
        // text 단위는 문자열 그대로, 나머지는 숫자 반환
        if (unit === 'text') return el.dataset.raw || el.value || "";
        return parseFloat(el.dataset.raw) || 0;
    },

    // 화면에 값 세팅 및 단위 표시
    set: function (id, rawValue) {
        const el = document.getElementById(id);
        if (!el) return;

        el.dataset.raw = rawValue;
        const unit = el.dataset.unit || 'won';
        let displayValue = "";

        if (unit === 'text') {
            displayValue = rawValue;
        } else if (unit === 'area') {
            const num = parseFloat(rawValue);
            // 면적: 평/㎡ 모드 대응
            if (!isPyungMode) {
                displayValue = (num * 0.3025).toFixed(2) + " 평";
            } else {
                displayValue = ((num % 1 === 0) ? num.toLocaleString() : num.toFixed(2)) + " ㎡";
            }
        } else if (unit === 'gongsi') {
            // 공시지가 단가: 평 모드일 때 평당가로 변환하여 출력
            let unitVal = !isPyungMode ? (rawValue / 0.3025) : rawValue;
            displayValue = Math.round(unitVal).toLocaleString() + " 원";
        } else if (unit === 'rate') {
            displayValue = this.formatRate(el, rawValue);
        } else if (unit === 'percent') {
            displayValue = this.formatPerc(el, rawValue);
        } else if (unit === 'eok') {
            // 억 단위: 소수점 2자리 고정
            const unitVal = rawValue / this.units.eok;
            displayValue = unitVal.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }) + " 억";
        } else if (unit === 'man') {
            // 만 단위: 반올림
            const unitVal = Math.round(rawValue / this.units.man);
            displayValue = unitVal.toLocaleString() + " 만원";
        } else if (unit === 'won') {
            // 원 단위: 반올림
            const unitVal = Math.round(rawValue);
            displayValue = unitVal.toLocaleString() + " 원";
        } else {
            displayValue = rawValue;
        }

        if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
            el.value = displayValue;
        } else {
            el.innerText = displayValue;
        }
    },

    // 화면 입력값을 원본 데이터로 동기화
    sync: function (el) {
        const unit = el.dataset.unit || 'won';
        if (unit === 'text') {
            el.dataset.raw = el.value;
            return;
        }
        // 숫자, 소수점, 마이너스 제외하고 제거
        let val = el.value.replace(/[^0-9.-]/g, '');
        if (val === "" || isNaN(val)) { el.dataset.raw = 0; return; }

        if (unit === 'area' || unit === 'gongsi') {
            // 평 모드에서 입력 시 m2 기준으로 역산하여 저장
            if (!isPyungMode) {
                if (unit === 'area') el.dataset.raw = (parseFloat(val) / 0.3025);
                else el.dataset.raw = (parseFloat(val) * 0.3025); // 평당가 -> m2당가
            } else {
                el.dataset.raw = parseFloat(val);
            }
        } else if (unit === 'rate' || unit === 'percent') {
            el.dataset.raw = parseFloat(val);
        } else {
            el.dataset.raw = Math.round(parseFloat(val) * this.units[unit]);
        }
        this.set(el.id, el.dataset.raw);
    },

    formatRate: function (el, val) {
        const num = parseFloat(val);
        if (isNaN(num)) return "- %";
        // 수익률 색상 및 소수점 2자리 고정
        el.style.color = num > 0 ? "#3b82f6" : (num < 0 ? "#ef4444" : "");
        el.style.backgroundColor = num > 0 ? "#e3f2fd" : (num < 0 ? "#ffe7d9" : "");
        return num.toFixed(2) + "%";
    },

    formatPerc: function (el, val) {
        const num = parseFloat(val);
        return isNaN(num) ? "- %" : num.toFixed(2) + "%";
    }
};

// =========================================================
// 2. 데이터 검색 및 조회 (API)
// =========================================================
async function searchPropertyData() {
    const address = `${document.getElementById('reg-sigungu').value} ${document.getElementById('reg-dong').value} ${document.getElementById('reg-address-input').value}`.trim();
    if (!address) return alert("주소를 입력해주세요.");
    const pnuList = window.convertAddressToPNU(address);
    if (pnuList.length === 0) return alert("PNU 변환 실패");

    try {
        const [resMain, resDetail, resProp] = await Promise.all([
            fetch('/api/get_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ "고유번호": pnuList, "limit": 1 }) }),
            fetch('/api/get_propDetail', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ "고유번호": pnuList[0] }) }),
            fetch(`/api/get_prop_main?고유번호=${pnuList[0]}`)
        ]);
        const mainResult = await resMain.json(), detailResult = await resDetail.json(), propData = await resProp.json();
        return { 
            main: (mainResult.data && mainResult.data.length > 0) ? mainResult.data[0] : {}, 
            details: detailResult.success ? detailResult.data : [], 
            prop: propData.data || {} 
        };
    } catch (e) { alert("서버 통신 에러"); }
}

async function fillPropertyDataHandler() {
    const rs = await searchPropertyData();
    if (!rs) return;
    const { main, details, prop } = rs;
    PNU = main.고유번호;
    const session = await loadSessionInfo();

    // [1] 세부 정보 및 담당자 (Val.set 통일)
    Val.set('reg-manager', prop.담당자 || session.user_name || "");
    Val.set('reg-owner-type', prop.소유자타입 || "개인");
    Val.set('reg-owner-name', prop.소유자명 || "");
    Val.set('reg-contact', prop.전화번호 || "");
    Val.set('reg-relationship', prop.관계 || "건물주/법인대표");
    Val.set('reg-inclination', prop.성향 || "");
    Val.set('reg-proped-date', prop.접수일 || new Intl.DateTimeFormat('fr-CA').format(new Date()));
    Val.set('reg-intent-to-buy', prop.매수의향서 || "");
    Val.set('reg-video-timestamp', prop.영상번호분초 || "");
    Val.set('reg-owner-details', prop.소유자현재 || "");

    // [2] 메인 정보
    Val.set('reg-sale-price', prop.매매가억 || 0);
    Val.set('reg-total-security', prop.총보증금 || 0);
    Val.set('reg-total-rent', prop.총월세부가세별도 || 0);
    Val.set('reg-total-manage', prop.총관리비 || 0);
    Val.set('reg-prop-id', prop.매물번호 || "");

    // [3] 진행 및 등급
    Val.set('reg-status', prop.진행상태 || "준비");
    Val.set('reg-urgency', prop.긴급도 || "없음");
    Val.set('reg-location', prop.입지 || "");
    Val.set('reg-grade', prop.등급 || "");
    Val.set('reg-b-usage', prop.건물용도 || "");
    Val.set('reg-has-photo', prop.사진 || "무");
    Val.set('reg-has-brief', prop.브리핑 || "무");
    Val.set('reg-eviction', prop.명도 || "확인중");
    Val.set('reg-usage-change', prop.용도변경 || "확인중");
    Val.set('reg-demolition', prop.멸실 || "확인중");

    // [4] 건물 정보
    Val.set('reg-floor-above', main.규모지상 || "");
    Val.set('reg-floor-below', main.규모지하 || "");
    Val.set('reg-land-area', main.대지면적 || 0);
    Val.set('reg-build-area', main.건축면적 || 0);
    Val.set('reg-total-area-val', main.연면적 || 0);
    Val.set('reg-far-area', main.용적률산정연면적 || 0);
    Val.set('reg-elevator', main.엘리베이터 || 0);
    Val.set('reg-parking', main.주차장 || 0);
    Val.set('reg-approval-date', main.사용승인일 || "");
    Val.set('reg-remodel-date', main.대수선및리모델링 || "");
    Val.set('reg-legal-bc', main.법정건폐율 || 0);
    Val.set('reg-legal-far', main.법정용적률 || 0);

    // [5] 토지 정보
    Val.set('reg-total-land-area', main.토지면적 || 0);
    Val.set('reg-jimok', main.지목 || "");
    Val.set('reg-zoning', main.용도지역 || "");
    Val.set('reg-land-status', main.토지이용상황 || "");
    Val.set('reg-main-code', main.주용도 || "");
    Val.set('reg-shape', main.형상 || "");
    Val.set('reg-road', main.도로 || "");
    Val.set('reg-other-usage', main.기타용도 || "");
    Val.set('reg-gongsi-cur', main.공시지가 || 0);
    Val.set('reg-gongsi-5y', main.공시지가5년전 || 0);
    Val.set('reg-gongsi-10y', main.공시지가10년전 || 0);

    // [6] 매각 및 광고
    Val.set('reg-sale-date1', main.매각일1 || ""); Val.set('reg-sale-amt1', main.매각액1 || 0);
    Val.set('reg-sale-date2', main.매각일2 || ""); Val.set('reg-sale-amt2', main.매각액2 || 0);
    Val.set('reg-sale-date3', main.매각일3 || ""); Val.set('reg-sale-amt3', main.매각액3 || 0);
    Val.set('reg-naver-cur', main.네이버광고 || 0); Val.set('reg-naver-past', main.네이버광고과거 || 0);
    Val.set('reg-builtamjung-ad', main.빌탐정광고등록유무 || "무");

    const container = document.getElementById('floor-rows-container');
    container.innerHTML = "";
    if (details.length > 0) details.forEach(d => addFloorRow(d));

    calculatePropertyStats();
    loadMemos(PNU);
}

// =========================================================
// 3. 실시간 수식 계산기 (Calculations)
// =========================================================
function calculatePropertyStats() {
    const salePrice = Val.get('reg-sale-price'), landArea = Val.get('reg-land-area'), totalArea = Val.get('reg-total-area-val');
    const buildArea = Val.get('reg-build-area'), farArea = Val.get('reg-far-area'), gongsi = Val.get('reg-gongsi-cur');
    const bcLegal = Val.get('reg-legal-bc'), farLegal = Val.get('reg-legal-far');

    let fullSum = { sec: 0, rent: 0, man: 0 }, currentSum = { sec: 0, rent: 0, man: 0 };
    document.querySelectorAll('.property-row').forEach(row => {
        const s = (parseFloat(row.querySelector('.floor-sec')?.value.replace(/,/g, '')) || 0) * 10000;
        const r = (parseFloat(row.querySelector('.floor-rent')?.value.replace(/,/g, '')) || 0) * 10000;
        const m = (parseFloat(row.querySelector('.floor-man')?.value.replace(/,/g, '')) || 0) * 10000;
        const isEmpty = row.querySelector('.floor-empty')?.value === "유";
        fullSum.sec += s; fullSum.rent += r; fullSum.man += m;
        if (!isEmpty) { currentSum.sec += s; currentSum.rent += r; currentSum.man += m; }
    });

    Val.set('reg-total-security', fullSum.sec); Val.set('reg-total-rent', fullSum.rent); Val.set('reg-total-manage', fullSum.man);
    Val.set('sum-sec-current', currentSum.sec); Val.set('sum-rent-current', currentSum.rent); Val.set('sum-man-current', currentSum.man);
    Val.set('sum-sec-full', fullSum.sec); Val.set('sum-rent-full', fullSum.rent); Val.set('sum-man-full', fullSum.man);

    const calcYield = (s, r) => { const net = salePrice - s; return net > 0 ? ((r * 12) / net * 100) : 0; };
    Val.set('reg-yield', calcYield(fullSum.sec, fullSum.rent));
    Val.set('sum-yield-current', calcYield(currentSum.sec, currentSum.rent));
    Val.set('sum-yield-full', calcYield(fullSum.sec, fullSum.rent));

    if (landArea > 0) {
        Val.set('reg-price-land', Math.round(salePrice / (landArea * 0.3025)));
        Val.set('reg-bc-ratio', (buildArea / landArea) * 100);
        Val.set('reg-far-ratio', (farArea / landArea) * 100);
        const baseWon = landArea * gongsi * 1.9;
        Val.set('reg-gongsi-total', baseWon); Val.set('reg-gongsi-ratio', (baseWon / salePrice) * 100);
    }
    if (totalArea > 0) Val.set('reg-price-total', Math.round(salePrice / (totalArea * 0.3025)));

    const investCash = Val.get('reg-invest-cash'), loanRate = Val.get('reg-loan-rate');
    if (investCash > 0) {
        const loan = Math.max(0, salePrice - fullSum.sec - investCash);
        document.getElementById('loan-amount-display').innerText = `${(investCash/100000000).toFixed(2)}억 / ${loanRate.toFixed(2)}%`;
        Val.set('reg-self-yield-display', ((fullSum.rent * 12) - (loan * (loanRate / 100))) / investCash * 100);
    }

    Val.set('reg-bc-diff', Val.get('reg-bc-ratio') - bcLegal);
    Val.set('reg-far-diff', Val.get('reg-far-ratio') - farLegal);
}

// =========================================================
// 4. 이벤트 바인딩 및 초기화
// =========================================================
window.addEventListener('DOMContentLoaded', () => {
    initRegRegionSelectors();
    document.getElementById('btnToggleUnit').addEventListener('click', () => {
        // [수정] 평 버튼 클릭 시 면적 필드와 공시지가 필드들 한꺼번에 리프레시
        const updateIds = [
            'reg-land-area', 'reg-build-area', 'reg-total-area-val', 'reg-far-area', 'reg-total-land-area',
            'reg-gongsi-cur', 'reg-gongsi-5y', 'reg-gongsi-10y'
        ];
        updateIds.forEach(id => Val.set(id, Val.get(id)));
        calculatePropertyStats();
    });
});

// addFloorRow, autoComma, saveMemo, loadMemos 등 유틸 함수 유지
function addFloorRow(data = null) {
    const container = document.getElementById('floor-rows-container');
    const row = document.createElement('div');
    row.className = "grid grid-cols-12 gap-2 p-2 bg-white border rounded-lg items-center shadow-sm property-row";
    row.innerHTML = `
        <div class="col-span-1"><input type="text" class="w-full border rounded p-1 text-center" value="${data?.층 || ''}"></div>
        <div class="col-span-2"><input type="text" class="w-full border rounded p-1" value="${data?.형태 || ''}"></div>
        <div class="col-span-1"><input type="text" class="w-full border rounded p-1 text-right" value="${data?.평수 || ''}"></div>
        <div class="col-span-2"><input type="text" class="floor-sec w-full border rounded p-1 text-right" value="${(data?.보증금 || 0).toLocaleString()}" onblur="autoComma(this); calculatePropertyStats()"></div>
        <div class="col-span-2"><input type="text" class="floor-rent w-full border rounded p-1 text-right" value="${(data?.임대료 || 0).toLocaleString()}" onblur="autoComma(this); calculatePropertyStats()"></div>
        <div class="col-span-1"><input type="text" class="floor-man w-full border rounded p-1 text-right" value="${(data?.월관리비 || 0).toLocaleString()}" onblur="autoComma(this); calculatePropertyStats()"></div>
        <div class="col-span-1"><input type="text" class="w-full border rounded p-1" value="${data?.임대차기간 || ''}"></div>
        <div class="col-span-1"><select class="floor-empty w-full border rounded p-1" onchange="calculatePropertyStats()"><option value="무" ${data?.공실유무==='무'?'selected':''}>무</option><option value="유" ${data?.공실유무==='유'?'selected':''}>유</option></select></div>
        <div class="col-span-1 text-center"><button onclick="this.parentElement.parentElement.remove(); calculatePropertyStats();" class="text-red-400"><i class="fa-solid fa-trash-can"></i></button></div>
    `;
    container.appendChild(row);
}

function autoComma(el) {
    let val = el.value.replace(/[^0-9.]/g, '');
    if (val) el.value = parseFloat(val).toLocaleString();
}

/**
 * 메모 저장 및 수정 함수
 * Val.get과 Val.set을 사용하여 필드 데이터를 제어합니다.
 */
async function saveMemo() {
    const pnu = PNU; // 전역 PNU 변수 사용
    const content = Val.get('reg-memo');
    const importance = Val.get('reg-importance');
    const memoId = Val.get('edit-memo-id');

    if (!pnu) return alert("매물 정보(PNU)가 없습니다. 정보를 먼저 불러오세요.");
    if (!content) return alert("메모 내용을 입력해주세요.");

    const url = memoId ? '/api/update_memo' : '/api/add_memo';
    const payload = memoId 
        ? { id: memoId, content, importance } 
        : { pnu, content, importance };

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            // 입력창 초기화 (Val.set 사용)
            Val.set('reg-memo', "");
            Val.set('edit-memo-id', "");
            Val.set('reg-importance', "일반");
            
            // 버튼 텍스트 복구
            const btn = document.getElementById('btn-save-memo');
            if (btn) btn.innerText = "입력 (Ctrl+Enter)";
            
            loadMemos(pnu); // 목록 새로고침
        }
    } catch (e) {
        console.error("메모 저장 중 오류:", e);
        alert("메모 저장 실패");
    }
}

/**
 * 메모 목록 로드 및 렌더링 함수
 * 클릭 시 Val.set을 통해 수정 모드로 전환합니다.
 */
async function loadMemos(pnu) {
    const container = document.getElementById('memo-list-container');
    if (!pnu || !container) return;

    try {
        const res = await fetch(`/api/load_memos?pnu=${pnu}`);
        const data = await res.json();
        
        container.innerHTML = "";
        if (!data.memos || data.memos.length === 0) {
            container.innerHTML = `<p class="text-center text-gray-400 text-xs mt-10">등록된 메모가 없습니다.</p>`;
            return;
        }

        data.memos.forEach(memo => {
            // 중요도에 따른 배경색 설정
            let bgColor = "bg-gray-100 border-gray-200";
            if (memo.importance === "중요") bgColor = "bg-yellow-50 border-yellow-200 text-yellow-900";
            if (memo.importance === "매우중요") bgColor = "bg-purple-50 border-purple-200 text-purple-900";

            const box = document.createElement('div');
            box.className = `${bgColor} p-3 rounded-lg border shadow-sm cursor-pointer hover:brightness-95 transition-all mb-2`;
            
            // 클릭 시 수정 모드로 전환 (Val.set 활용)
            box.onclick = () => {
                Val.set('reg-memo', memo.content);
                Val.set('reg-importance', memo.importance || "일반");
                Val.set('edit-memo-id', memo.id);
                
                const btn = document.getElementById('btn-save-memo');
                if (btn) btn.innerText = "수정 완료";
                
                document.getElementById('reg-memo').focus();
            };

            box.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] font-bold opacity-70">${memo.writer_name || '작성자'}</span>
                    <span class="text-[9px] opacity-50">${memo.created_at || ''}</span>
                </div>
                <p class="text-xs whitespace-pre-wrap">${memo.content}</p>
            `;
            container.appendChild(box);
        });
    } catch (e) {
        console.error("메모 로드 중 오류:", e);
    }
}

function initRegRegionSelectors() {
    const siSelect = document.getElementById('reg-sigungu'), dongSelect = document.getElementById('reg-dong');
    if (!siSelect) return;
    siSelect.innerHTML = '<option value="">선택</option>';
    Object.keys(DIVISIONS).forEach(si => { const opt = document.createElement('option'); opt.value = si; opt.innerText = si; siSelect.appendChild(opt); });
    siSelect.onchange = () => {
        dongSelect.innerHTML = '<option value=\"\">선택</option>';
        if (DIVISIONS[siSelect.value]) DIVISIONS[siSelect.value].forEach(dong => { const opt = document.createElement('option'); opt.value = dong; opt.innerText = dong; dongSelect.appendChild(opt); });
    };
}
