// ============================================================================
// 주변 임대시세 분석 (임대시세 탭)
// 백엔드: /api/rent/batches, /api/rent/analyze, /api/rent/analyze/excel
// ============================================================================
const RentAnalysis = (() => {
    let initialized = false;
    let lastPayload = null; // 엑셀 다운로드 시 동일 조건 재사용

    const $ = (id) => document.getElementById(id);

    const fmtComma = (v) => (v === null || v === undefined || isNaN(v)) ? '-' : Number(v).toLocaleString('ko-KR');
    const fmtEok = (v) => {
        const n = Number(v);
        if (!n) return '0';
        if (Math.abs(n) >= 100000000) return (n / 100000000).toFixed(2).replace(/\.?0+$/, '') + '억';
        if (Math.abs(n) >= 10000) return fmtComma(Math.round(n / 10000)) + '만';
        return fmtComma(n);
    };

    // ------------------------------------------------------------------
    // 초기화: 배치 목록 로드 + 기본 주소행 1개
    // ------------------------------------------------------------------
    async function init() {
        if (initialized) return;
        initialized = true;
        addRow();
        await loadBatches();
    }

    async function loadBatches() {
        const sel = $('rent-batch-select');
        try {
            const res = await fetch('/api/rent/batches');
            const batches = await res.json();
            if (!Array.isArray(batches) || batches.length === 0) {
                sel.innerHTML = '<option value="">데이터 없음 (크롤링 업로드 필요)</option>';
                setStatus('아직 업로드된 임대 크롤링 데이터가 없습니다. 데스크탑 앱에서 "주변임대 업데이트"를 먼저 실행하세요.');
                return;
            }
            sel.innerHTML = batches.map((b, i) =>
                `<option value="${b.batch_id}">${b.completed_at} (${fmtComma(b.record_count)}건)${i === 0 ? ' - 최신' : ''}</option>`
            ).join('');
        } catch (e) {
            sel.innerHTML = '<option value="">목록 로드 실패</option>';
            setStatus('배치 목록을 불러오지 못했습니다: ' + e.message);
        }
    }

    function setStatus(msg, isError = false) {
        const el = $('rent-status');
        el.textContent = msg || '';
        el.className = 'text-xs mt-3 ' + (isError ? 'text-red-500 font-bold' : 'text-gray-500');
    }

    // ------------------------------------------------------------------
    // 대상 주소 행 관리
    // ------------------------------------------------------------------
    function addRow() {
        const container = $('rent-target-rows');
        const row = document.createElement('div');
        row.className = 'rent-target-row flex flex-wrap items-center gap-2';
        row.innerHTML = `
            <input type="text" placeholder="주소 (예: 서울특별시 강서구 방화동 563)"
                class="rent-addr border border-gray-300 rounded px-2 py-1.5 text-xs flex-1 min-w-[280px]">
            <button class="px-2 py-1.5 border border-gray-300 rounded text-[11px] font-bold text-gray-600 bg-white hover:bg-gray-50"
                onclick="RentAnalysis.fetchFloors(this)" title="DB에서 규모지하/지상 자동 조회">층수 조회</button>
            <label class="text-[11px] font-bold text-gray-500">지하</label>
            <input type="number" min="0" value="0" class="rent-under border border-gray-300 rounded px-1 py-1.5 text-xs w-14 text-center">
            <label class="text-[11px] font-bold text-gray-500">지상</label>
            <input type="number" min="0" value="0" class="rent-above border border-gray-300 rounded px-1 py-1.5 text-xs w-14 text-center">
            <button class="px-2 py-1.5 text-red-500 font-bold text-xs hover:bg-red-50 rounded"
                onclick="this.closest('.rent-target-row').remove()" title="행 삭제">✕</button>
        `;
        container.appendChild(row);
    }

    async function fetchFloors(btn) {
        const row = btn.closest('.rent-target-row');
        const address = row.querySelector('.rent-addr').value.trim();
        if (!address) { setStatus('주소를 먼저 입력하세요.', true); return; }
        try {
            const res = await fetch('/api/floors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ address })
            });
            const data = await res.json();
            if (!res.ok) { setStatus(`층수 조회 실패: ${data.error || res.status}`, true); return; }
            row.querySelector('.rent-under').value = data.underground_floors ?? 0;
            row.querySelector('.rent-above').value = data.aboveground_floors ?? 0;
            setStatus(`${address} → 지하 ${data.underground_floors ?? 0} / 지상 ${data.aboveground_floors ?? 0}`);
        } catch (e) {
            setStatus('층수 조회 중 오류: ' + e.message, true);
        }
    }

    function collectPayload() {
        const targets = [];
        document.querySelectorAll('#rent-target-rows .rent-target-row').forEach(row => {
            const address = row.querySelector('.rent-addr').value.trim();
            if (!address) return;
            targets.push({
                address,
                under: parseInt(row.querySelector('.rent-under').value || '0', 10),
                above: parseInt(row.querySelector('.rent-above').value || '0', 10),
            });
        });
        return {
            targets,
            radius_km: parseFloat($('rent-radius').value || '0.5'),
            batch_id: $('rent-batch-select').value ? parseInt($('rent-batch-select').value, 10) : null,
        };
    }

    // ------------------------------------------------------------------
    // 분석 실행 + 렌더링
    // ------------------------------------------------------------------
    async function run() {
        const payload = collectPayload();
        if (payload.targets.length === 0) { setStatus('분석할 주소를 1개 이상 입력하세요.', true); return; }

        const btn = $('btn-rent-analyze');
        btn.disabled = true;
        setStatus('분석 중...');
        $('rent-results').innerHTML = '';
        $('btn-rent-excel').disabled = true;

        try {
            const res = await fetch('/api/rent/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) { setStatus(`분석 실패: ${data.error || res.status}`, true); return; }

            lastPayload = payload;
            renderResults(data);

            const parts = [`기준시점 ${data.batch.completed_at} 기준 분석 완료.`];
            if (data.unmatched && data.unmatched.length > 0) {
                parts.push(`⚠️ DB에서 찾지 못한 주소: ${data.unmatched.join(', ')} (통합주소와 정확히 일치해야 합니다)`);
            }
            setStatus(parts.join(' '), data.unmatched && data.unmatched.length > 0);
            $('btn-rent-excel').disabled = data.results.length === 0;
        } catch (e) {
            setStatus('분석 중 오류: ' + e.message, true);
        } finally {
            btn.disabled = false;
        }
    }

    function renderResults(data) {
        const container = $('rent-results');
        container.innerHTML = '';

        data.results.forEach(result => {
            const section = document.createElement('section');
            section.className = 'bg-white border border-gray-200 rounded-xl shadow-sm p-5';

            const summaryRows = result.floor_summary.map(fs => `
                <tr class="border-b border-gray-100">
                    <td class="px-3 py-1.5 text-center font-bold">${fs.층}</td>
                    <td class="px-3 py-1.5 text-center">${fs.건수}</td>
                    <td class="px-3 py-1.5 text-right">${fmtComma(fs.평균계약평당보증금)}</td>
                    <td class="px-3 py-1.5 text-right">${fmtComma(fs.평균계약평당임대료)}</td>
                </tr>`).join('');

            const itemRows = result.items.map((it, idx) => `
                <tr class="border-b border-gray-100 hover:bg-gray-50">
                    <td class="px-2 py-1 text-center text-gray-400">${idx + 1}</td>
                    <td class="px-2 py-1 text-center font-bold">${it.층}</td>
                    <td class="px-2 py-1 text-right">${it.계약평 || '-'}</td>
                    <td class="px-2 py-1 text-right">${it.전용평 || '-'}</td>
                    <td class="px-2 py-1 text-right">${fmtEok(it.보증금)}</td>
                    <td class="px-2 py-1 text-right">${fmtEok(it.임대료)}</td>
                    <td class="px-2 py-1 text-right">${fmtComma(it.계약평당보증금)}</td>
                    <td class="px-2 py-1 text-right">${fmtComma(it.계약평당임대료)}</td>
                    <td class="px-2 py-1 text-center">${it.사용승인일 || '-'}</td>
                    <td class="px-2 py-1 text-left">${it.주소}</td>
                </tr>`).join('');

            section.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <h4 class="text-sm font-black text-gray-800">
                        <i class="fa-solid fa-location-dot text-emerald-600 mr-1"></i>
                        ${result.target_address}
                        <span class="text-xs font-bold text-gray-400 ml-2">
                            ${result.target_floor_range} · 반경 ${result.radius_km}km · ${fmtComma(result.item_count)}건
                        </span>
                    </h4>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div class="lg:col-span-1">
                        <p class="text-[11px] font-bold text-gray-500 mb-1">층별 요약 (평균 계약 평당가, 원)</p>
                        <table class="w-full text-xs border border-gray-200 rounded">
                            <thead class="bg-emerald-50 text-emerald-800">
                                <tr>
                                    <th class="px-3 py-1.5">층</th>
                                    <th class="px-3 py-1.5">건수</th>
                                    <th class="px-3 py-1.5">평당 보증금</th>
                                    <th class="px-3 py-1.5">평당 임대료</th>
                                </tr>
                            </thead>
                            <tbody>${summaryRows || '<tr><td colspan="4" class="px-3 py-3 text-center text-gray-400">데이터 없음</td></tr>'}</tbody>
                        </table>
                    </div>
                    <div class="lg:col-span-2 overflow-x-auto">
                        <p class="text-[11px] font-bold text-gray-500 mb-1">매물 목록</p>
                        <table class="w-full text-xs border border-gray-200 rounded whitespace-nowrap">
                            <thead class="bg-gray-50 text-gray-600">
                                <tr>
                                    <th class="px-2 py-1.5">#</th>
                                    <th class="px-2 py-1.5">층</th>
                                    <th class="px-2 py-1.5">계약(평)</th>
                                    <th class="px-2 py-1.5">전용(평)</th>
                                    <th class="px-2 py-1.5">보증금</th>
                                    <th class="px-2 py-1.5">임대료</th>
                                    <th class="px-2 py-1.5">평당 보증금</th>
                                    <th class="px-2 py-1.5">평당 임대료</th>
                                    <th class="px-2 py-1.5">사용승인일</th>
                                    <th class="px-2 py-1.5">주소</th>
                                </tr>
                            </thead>
                            <tbody>${itemRows || '<tr><td colspan="10" class="px-3 py-3 text-center text-gray-400">반경 내 조건에 맞는 매물이 없습니다</td></tr>'}</tbody>
                        </table>
                    </div>
                </div>`;
            container.appendChild(section);
        });
    }

    // ------------------------------------------------------------------
    // 엑셀 다운로드 (마지막 분석과 동일 조건)
    // ------------------------------------------------------------------
    async function downloadExcel() {
        if (!lastPayload) { setStatus('먼저 분석을 실행하세요.', true); return; }
        const btn = $('btn-rent-excel');
        btn.disabled = true;
        setStatus('엑셀 생성 중...');
        try {
            const res = await fetch('/api/rent/analyze/excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lastPayload)
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                setStatus(`엑셀 생성 실패: ${data.error || res.status}`, true);
                return;
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const cd = res.headers.get('Content-Disposition') || '';
            const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)/);
            a.download = m ? decodeURIComponent(m[1]) : '주변임대시세.xlsx';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            setStatus('엑셀 다운로드 완료.');
        } catch (e) {
            setStatus('엑셀 다운로드 오류: ' + e.message, true);
        } finally {
            btn.disabled = false;
        }
    }

    return { init, addRow, fetchFloors, run, downloadExcel };
})();
