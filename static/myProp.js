/**
 * 빌탐정 (BuilTamjung) - 매물 관리 통합 스크립트
 * 모든 수치는 '원/㎡' 단위로 내부 관리하며, 화면 출력 시에만 단위 변환을 수행합니다.
 */

let PNU; // 전역 PNU 고유번호

// =========================================================
// 1. 중앙 단위 및 가치 매니저 (Val Manager)
// =========================================================
const Val = {
    units: { eok: 100000000, man: 10000, won: 1, area: 1, rate: 1, percent: 1 },

    get: function (id) {
        const el = document.getElementById(id);
        if (!el) return 0;
        return parseFloat(el.dataset.raw) || 0;
    },

    set: function (id, rawValue) {
        const el = document.getElementById(id);
        if (!el) return;

        el.dataset.raw = rawValue;
        const unit = el.dataset.unit || 'won';
        let displayValue = "";

        if (unit === 'area') {
            const num = parseFloat(rawValue);
            // 면적: 평/㎡ 모드 대응 및 소수점 처리
            if (isPyungMode) {
                displayValue = (num * 0.3025).toFixed(2) + " 평";
            } else {
                displayValue = ((num % 1 === 0) ? num.toLocaleString() : num.toFixed(2)) + " ㎡";
            }
        } else if (unit === 'rate') {
            // 수익률: formatRate 내부에서 %를 붙이므로 중복 방지
            displayValue = this.formatRate(el, rawValue);
        } else if (unit === 'percent') {
            displayValue = this.formatPerc(el, rawValue);
        } else if (unit === 'eok') {
            // 억 단위: 소수점 2자리 + ' 억'
            const unitVal = rawValue / this.units.eok;
            displayValue = unitVal.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }) + " 억";
        } else if (unit === 'man') {
            // 만 단위: 소수점 없이 반올림 + ' 만원'
            const unitVal = Math.round(rawValue / this.units.man);
            displayValue = unitVal.toLocaleString() + " 만원";
        } else if (unit === 'won') {
            // 원 단위: 소수점 없이 반올림 + ' 원'
            const unitVal = Math.round(rawValue);
            displayValue = unitVal.toLocaleString() + " 원";
        } else {
            displayValue = rawValue;
        }

        if (el.tagName === 'INPUT') el.value = displayValue;
        else el.innerText = displayValue;
    },

    sync: function (el) {
        const unit = el.dataset.unit || 'won';
        // 입력 시 숫자, 소수점, 마이너스 기호만 남김
        let val = el.value.replace(/[^0-9.-]/g, '');
        if (val === "" || isNaN(val)) { el.dataset.raw = 0; return; }

        if (unit === 'area' || unit === 'rate') {
            if (isPyungMode) {
                el.dataset.raw = (parseFloat(val) / 0.3025);
            } else {
                el.dataset.raw = parseFloat(val);
            }
        } else {
            // 저장 시에는 원단위로 환산하여 정수로 보관
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
        if (isNaN(num)) return "- %";
        // 수익률 색상 및 소수점 2자리 고정
        return num.toFixed(2) + "%";
    }
};
// =========================================================
// 2. 데이터 검색 및 조회 (API)
// =========================================================
async function searchPropertyData() {
    const sigungu = document.getElementById('reg-sigungu').value;
    const dong = document.getElementById('reg-dong').value;
    const addr = document.getElementById('reg-address-input').value;
    const address = `${sigungu} ${dong} ${addr}`.trim();

    if (!addr) {
        alert("주소를 입력해주세요.");
        return;
    }

    const pnuList = window.convertAddressToPNU(address);
    if (pnuList.length === 0) {
        alert("PNU 변환에 실패했습니다.");
        return;
    }

    try {
        const [resMain, resDetail, resProp] = await Promise.all([
            fetch('/api/get_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ "고유번호": pnuList, "limit": 1 })
            }),
            fetch('/api/get_propDetail', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ "고유번호": pnuList[0] })
            }),
            fetch(`/api/get_prop_main?고유번호=${pnuList[0]}`)
        ]);

        const mainResult = await resMain.json();
        const detailResult = await resDetail.json();
        const propData = await resProp.json();

        return {
            main: (mainResult.data && mainResult.data.length > 0) ? mainResult.data[0] : {},
            details: detailResult.success ? detailResult.data : [],
            prop: propData.data || {}
        };
    } catch (e) {
        console.error("API 호출 중 오류:", e);
        alert("서버 통신 오류");
    }
}

// 필드 50개 이상 전체 매핑 (생략 없음)
async function fillPropertyDataHandler() {
    const rs = await searchPropertyData();
    if (!rs) return;
    const { main, details, prop } = rs;
    PNU = main.고유번호;

    const session = await loadSessionInfo(); // script.js 전역 함수

    // [1] 세부 정보 및 담당자
    document.getElementById('reg-manager').value = prop.담당자 || session.user_name || "";
    document.getElementById('reg-owner-type').value = prop.소유자타입 || "개인";
    document.getElementById('reg-owner-name').value = prop.소유자명 || "";
    document.getElementById('reg-contact').value = prop.전화번호 || "";
    document.getElementById('reg-relationship').value = prop.관계 || "건물주/법인대표";
    document.getElementById('reg-inclination').value = prop.성향 || "";
    document.getElementById('reg-proped-date').value = prop.접수일 || new Intl.DateTimeFormat('fr-CA').format(new Date());
    document.getElementById('reg-intent-to-buy').value = prop.매수의향서 || "";
    document.getElementById('reg-video-timestamp').value = prop.영상번호분초 || "";
    document.getElementById('reg-owner-details').value = prop.소유자현재 || "";

    // [2] 메인 가치 정보 (Val 매니저)
    Val.set('reg-sale-price', prop.매매가억 || 0);
    Val.set('reg-total-security', prop.총보증금 || 0);
    Val.set('reg-total-rent', prop.총월세부가세별도 || 0);
    Val.set('reg-total-manage', prop.총관리비 || 0);
    document.getElementById('reg-prop-id').value = prop.매물번호 || "";

    // [3] 진행 및 등급
    if (document.getElementById('reg-status')) document.getElementById('reg-status').value = prop.진행상태 || "준비";
    document.getElementById('reg-urgency').value = prop.긴급도 || "없음";
    document.getElementById('reg-location').value = prop.입지 || "";
    document.getElementById('reg-grade').value = prop.등급 || "";
    document.getElementById('reg-b-usage').value = prop.건물용도 || "";
    document.getElementById('reg-has-photo').value = prop.사진 || "무";
    document.getElementById('reg-has-brief').value = prop.브리핑 || "무";
    document.getElementById('reg-eviction').value = prop.명도 || "확인중";
    document.getElementById('reg-usage-change').value = prop.용도변경 || "확인중";
    document.getElementById('reg-demolition').value = prop.멸실 || "확인중";

    // [4] 건물 정보
    document.getElementById('reg-floor-above').value = main.규모지상 || "";
    document.getElementById('reg-floor-below').value = main.규모지하 || "";
    Val.set('reg-land-area', main.대지면적 || 0);
    Val.set('reg-build-area', main.건축면적 || 0);
    Val.set('reg-total-area-val', main.연면적 || 0);
    Val.set('reg-far-area', main.용적률산정연면적 || 0);
    document.getElementById('reg-elevator').value = main.엘리베이터 || 0;
    document.getElementById('reg-parking').value = main.주차장 || 0;
    document.getElementById('reg-approval-date').value = main.사용승인일 || "";
    document.getElementById('reg-remodel-date').value = main.대수선및리모델링 || "";
    Val.set('reg-bc-ratio', main.건폐율 || "");
    Val.set('reg-far-ratio', main.용적률 || "");
    Val.set('reg-legal-bc', main.법정건폐율 || "");
    Val.set('reg-legal-far', main.법정용적률 || "");

    // [5] 토지 정보
    Val.set('reg-total-land-area', main.대지면적 || 0);
    document.getElementById('reg-jimok').value = main.지목 || "";
    document.getElementById('reg-zoning').value = main.용도지역 || "";
    document.getElementById('reg-land-status').value = main.토지이용상황 || "";
    document.getElementById('reg-main-code').value = main.주용도 || "";
    document.getElementById('reg-shape').value = main.형상 || "";
    document.getElementById('reg-road').value = main.도로 || "";
    document.getElementById('reg-other-usage').value = main.기타용도 || "";
    Val.set('reg-gongsi-cur', main.공시지가 || 0);
    Val.set('reg-gongsi-5y', main.공시지가5년전 || 0);
    Val.set('reg-gongsi-10y', main.공시지가10년전 || 0);

    // [6] 매각 및 광고
    document.getElementById('reg-sale-date1').value = main.매각일1 || "";
    Val.set('reg-sale-amt1', main.매각액1 || 0);
    document.getElementById('reg-sale-date2').value = main.매각일2 || "";
    Val.set('reg-sale-amt2', main.매각액2 || 0);
    document.getElementById('reg-sale-date3').value = main.매각일3 || "";
    Val.set('reg-sale-amt3', main.매각액3 || 0);
    Val.set('reg-naver-cur', main.네이버광고 || 0);
    Val.set('reg-naver-past', main.네이버광고과거 || 0);
    document.getElementById('reg-builtamjung-ad').value = main.빌탐정광고등록유무 || "무";

    // 층별 상세 데이터 동적 로드
    const container = document.getElementById('floor-rows-container');
    container.innerHTML = "";
    if (details && details.length > 0) {
        details.forEach(d => addFloorRow(d));
    }

    calculatePropertyStats(); // 로딩 후 즉시 계산
    loadMemos(PNU); // 메모 로드
}

// =========================================================
// 3. 실시간 수식 계산기 (Calculations)
// =========================================================
function calculatePropertyStats() {
    const salePrice = Val.get('reg-sale-price');
    const landArea = Val.get('reg-land-area');
    const totalArea = Val.get('reg-total-area-val');
    const buildArea = Val.get('reg-build-area');
    const farArea = Val.get('reg-far-area');
    const gongsi = Val.get('reg-gongsi-cur');
    const bcRatio = Val.get('reg-bc-ratio');
    const farRatio = Val.get('reg-far-ratio');
    const bcLegal = Val.get('reg-legal-bc');
    const farLegal = Val.get('reg-legal-far');

    console.log(totalArea)

    // [A] 층별 임대 내역 합산 (만 단위 필드)
    let fullSum = { sec: 0, rent: 0, man: 0 };
    let currentSum = { sec: 0, rent: 0, man: 0 };

    document.querySelectorAll('.property-row').forEach(row => {
        const s = (parseFloat(row.querySelector('.floor-sec')?.value.replace(/,/g, '')) || 0) * 10000;
        const r = (parseFloat(row.querySelector('.floor-rent')?.value.replace(/,/g, '')) || 0) * 10000;
        const m = (parseFloat(row.querySelector('.floor-man')?.value.replace(/,/g, '')) || 0) * 10000;
        const isEmpty = row.querySelector('.floor-empty')?.value === "유";

        fullSum.sec += s; fullSum.rent += r; fullSum.man += m;
        if (!isEmpty) { currentSum.sec += s; currentSum.rent += r; currentSum.man += m; }
    });

    // 합계 필드 업데이트
    Val.set('reg-total-security', fullSum.sec);
    Val.set('reg-total-rent', fullSum.rent);
    Val.set('reg-total-manage', fullSum.man);

    // [B] 수익률 계산
    const calcYield = (s, r) => {
        const netPrice = salePrice - s;
        return netPrice > 0 ? ((r * 12) / netPrice * 100) : 0;
    };

    Val.set('reg-yield', calcYield(fullSum.sec, fullSum.rent));
    document.getElementById('sum-yield-current').innerText = calcYield(currentSum.sec, currentSum.rent).toFixed(2) + "%";
    document.getElementById('sum-yield-full').innerText = calcYield(fullSum.sec, fullSum.rent).toFixed(2) + "%";

    // [C] 평단가 및 기타 비율
    if (landArea > 0) {
        const py = landArea * 0.3025;
        Val.set('reg-price-land', Math.round((salePrice) / py));
    }

    if (totalArea > 0) {
        const py = totalArea * 0.3025;
        Val.set('reg-price-total', Math.round((salePrice) / py));
    }

    if (salePrice > 0) {
        Val.set('reg-gongsi-ratio', gongsi / salePrice);
    }

    const investCash = Val.get('reg-invest-cash');
    const loanRate = Val.get('reg-loan-rate'); // 이제 NaN이 아닌 4.5 같은 숫자가 잘 들어옴

    if (investCash > 0) {
        // 매매가보다 보증금+현금이 많을 경우 대출은 0으로 처리
        const loanAmount = Math.max(0, salePrice - fullSum.sec - investCash);
        document.getElementById('loan-amount-display').innerText = `대출 ${(loanAmount / 100000000).toFixed(2)}억`;

        const annualInt = loanAmount * (loanRate / 100); // 연 이자 비용
        const selfYield = ((fullSum.rent * 12) - annualInt) / investCash * 100;
        Val.set('reg-self-yield-display', selfYield);
    }

    Val.set('reg-bc-diff', bcRatio - bcLegal);
    Val.set('reg-far-diff', farRatio - farLegal);
}

// =========================================================
// 4. 층별 관리 및 메모 기능 (Full)
// =========================================================
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
        <div class="col-span-1"><select class="floor-empty w-full border rounded p-1" onchange="calculatePropertyStats()"><option value="무" ${data?.공실유무 === '무' ? 'selected' : ''}>무</option><option value="유" ${data?.공실유무 === '유' ? 'selected' : ''}>유</option></select></div>
        <div class="col-span-1 text-center"><button onclick="this.parentElement.parentElement.remove(); calculatePropertyStats();" class="text-red-400"><i class="fa-solid fa-trash-can"></i></button></div>
    `;
    container.appendChild(row);
}

function autoComma(el) {
    let val = el.value.replace(/[^0-9.]/g, '');
    if (val) el.value = parseFloat(val).toLocaleString();
}

async function saveMemo() {
    const pnu = PNU;
    const content = document.getElementById('reg-memo').value;
    const importance = document.getElementById('reg-importance').value;
    const memoId = document.getElementById('edit-memo-id').value;

    if (!pnu) return alert("매물 정보가 없습니다.");
    if (!content) return alert("내용을 입력해주세요.");

    const url = memoId ? '/api/update_memo' : '/api/add_memo';
    const payload = memoId ? { id: memoId, content, importance } : { pnu, content, importance };

    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (res.ok) {
        document.getElementById('reg-memo').value = "";
        document.getElementById('edit-memo-id').value = "";
        document.getElementById('btn-save-memo').innerText = "입력 (Ctrl+Enter)";
        loadMemos(pnu);
    }
}

async function loadMemos(pnu) {
    const container = document.getElementById('memo-list-container');
    if (!pnu) return;
    const res = await fetch(`/api/load_memos?pnu=${pnu}`);
    const data = await res.json();
    container.innerHTML = "";
    if (data.memos.length === 0) {
        container.innerHTML = `<p class="text-center text-gray-400 text-xs mt-10">등록된 메모가 없습니다.</p>`;
        return;
    }
    data.memos.forEach(memo => {
        let bgColor = "bg-gray-100 border-gray-200";
        if (memo.importance === "중요") bgColor = "bg-yellow-50 border-yellow-200 text-yellow-900";
        if (memo.importance === "매우중요") bgColor = "bg-purple-50 border-purple-200 text-purple-900";
        const box = document.createElement('div');
        box.className = `${bgColor} p-3 rounded-lg border shadow-sm cursor-pointer hover:brightness-95 transition-all mb-2`;
        box.onclick = () => prepareUpdate(memo);
        box.innerHTML = `<div class="flex justify-between items-start mb-1"><span class="text-[10px] font-bold opacity-70">${memo.writer_name}</span><span class="text-[9px] opacity-50">${memo.created_at}</span></div><p class="text-xs whitespace-pre-wrap">${memo.content}</p>`;
        container.appendChild(box);
    });
}

function prepareUpdate(memo) {
    document.getElementById('reg-memo').value = memo.content;
    document.getElementById('reg-importance').value = memo.importance || "일반";
    document.getElementById('edit-memo-id').value = memo.id;
    document.getElementById('btn-save-memo').innerText = "수정 완료";
    document.getElementById('reg-memo').focus();
}

function initRegRegionSelectors() {
    const siSelect = document.getElementById('reg-sigungu');
    const dongSelect = document.getElementById('reg-dong');
    if (!siSelect) return;
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

// =========================================================
// 5. 초기화 및 이벤트 바인딩
// =========================================================
window.addEventListener('DOMContentLoaded', () => {
    initRegRegionSelectors();
    document.getElementById('btnToggleUnit').addEventListener('click', () => {
        // 면적 단위 변경 시 모든 관련 필드 강제 업데이트
        const areaIds = ['reg-land-area', 'reg-build-area', 'reg-total-area-val', 'reg-far-area', 'reg-total-land-area'];
        areaIds.forEach(id => Val.set(id, Val.get(id)));
        calculatePropertyStats();
    });
});

function eokToFullValue(eokStr) { return Math.round(parseFloat(eokStr) * 100000000); }
function resetRegistration() {
    document.getElementById('reg-address-input').value = '';
    document.getElementById('floor-rows-container').innerHTML = '';
}