let map = null;
let markers = [], markerMap = {}, infoWindows = {};
let globalData = {}; // 전체 데이터 저장용

// 현재 선택된 임시 마커 (검색/클릭 시 생성됨)
let currentMarker = null;

window.onload = function() {
    initMap();
    loadWishlist(); // 초기 로딩
};

function initMap() {
    map = new naver.maps.Map('map', {
        center: new naver.maps.LatLng(37.5665, 126.9780),
        zoom: 15
    });
    // 지도 클릭 시 좌표로 주소 검색
    naver.maps.Event.addListener(map, 'click', function(e) {
        searchCoordinateToAddress(e.coord);
    });
}

// --- 데이터 로드 및 리스트 렌더링 ---
async function loadWishlist() {
    const container = document.getElementById('wishlistContainer');
    const datalist = document.getElementById('existingGroups');
    const countBadge = document.getElementById('countBadge');
    
    try {
        const res = await fetch('/api/wishlist');
        globalData = await res.json();
        
        // 초기화
        markers.forEach(m => m.setMap(null));
        markers = []; markerMap = {}; infoWindows = {};
        container.innerHTML = '';
        datalist.innerHTML = '';

        countBadge.innerText = Object.keys(globalData).length;

        const groupedData = {};
        const groupSet = new Set();

        // 데이터 분류 및 마커 생성
        for (const [addr, info] of Object.entries(globalData)) {
            addMarkerToMap(addr, info); // 지도에 마커 추가

            const gName = info.group_name || '기본';
            if (!groupedData[gName]) groupedData[gName] = [];
            groupedData[gName].push({ address: addr, ...info });
            groupSet.add(gName);
        }

        // 그룹명 자동완성 채우기
        groupSet.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g;
            datalist.appendChild(opt);
        });

        // 리스트 렌더링
        if (Object.keys(groupedData).length === 0) {
            container.innerHTML = '<div class="text-center text-gray-400 mt-10">저장된 데이터가 없습니다.</div>';
            return;
        }

        Object.keys(groupedData).sort().forEach(groupName => {
            const items = groupedData[groupName];
            
            const details = document.createElement('details');
            details.open = true; 
            details.className = "group bg-white border rounded-lg overflow-hidden mb-2 shadow-sm";

            const summary = document.createElement('summary');
            summary.className = "flex justify-between items-center p-3 bg-slate-50 hover:bg-slate-100 text-sm font-bold text-slate-700 select-none";
            summary.innerHTML = `
                <div class="flex items-center gap-2">
                    <i class="fa-solid fa-folder text-yellow-500"></i> ${groupName}
                </div>
                <span class="text-xs bg-white border px-1.5 rounded text-gray-500">${items.length}</span>
            `;

            const listDiv = document.createElement('div');
            items.forEach(item => {
                listDiv.appendChild(createListItem(item));
            });

            details.appendChild(summary);
            details.appendChild(listDiv);
            container.appendChild(details);
        });

    } catch (e) { console.error(e); }
}

// --- 리스트 아이템 생성 ---
function createListItem(item) {
    const el = document.createElement('div');
    const safeId = `item-${btoa(unescape(encodeURIComponent(item.address))).replace(/=/g,'')}`;
    
    el.id = safeId;
    el.className = "p-3 border-b last:border-0 hover:bg-blue-50 transition relative group/item";

    el.innerHTML = `
        <div class="flex justify-between items-start cursor-pointer" onclick="moveToLocation('${item.address}')">
            <div class="flex gap-2 items-start overflow-hidden w-full">
                <div class="w-3 h-3 rounded-full mt-1 flex-shrink-0" style="background-color: ${item.color};"></div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-bold text-gray-800 leading-tight break-keep">${item.address}</p>
                    ${item.note ? `<p class="text-xs text-gray-500 mt-1 bg-gray-100 p-1 rounded inline-block"><i class="fa-regular fa-note-sticky"></i> ${item.note}</p>` : ''}
                </div>
            </div>
        </div>
        
        <div class="flex gap-2 absolute top-2 right-2 opacity-0 group-hover/item:opacity-100 transition-opacity bg-white/90 px-1 rounded shadow-sm">
            <button onclick="enableEdit('${item.address}', '${safeId}')" class="text-blue-500 hover:text-blue-700 text-xs p-1" title="수정">
                <i class="fa-solid fa-pen"></i>
            </button>
            <button onclick="deleteItem(event, '${item.address}')" class="text-red-400 hover:text-red-600 text-xs p-1" title="삭제">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    return el;
}

// --- 수정 모드 UI ---
window.enableEdit = (address, elementId) => {
    const info = globalData[address];
    const el = document.getElementById(elementId);
    if (!el) return;

    el.innerHTML = `
        <div class="bg-blue-50 p-2 -m-2 rounded ring-2 ring-blue-100">
            <p class="text-xs font-bold text-gray-500 mb-2">${address}</p>
            
            <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-bold w-8 text-gray-600">그룹</span>
                <input type="text" id="edit-group-${elementId}" list="existingGroups" value="${info.group_name}" 
                       class="flex-1 text-xs border rounded px-2 py-1 focus:border-blue-500 outline-none">
            </div>

            <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-bold w-8 text-gray-600">색상</span>
                <input type="color" id="edit-color-${elementId}" value="${info.color}" class="h-6 w-6 border-none bg-transparent p-0 cursor-pointer">
            </div>

            <textarea id="edit-note-${elementId}" class="w-full text-xs border rounded px-2 py-1 mb-2 resize-none focus:border-blue-500 outline-none" 
                      rows="2" placeholder="메모">${info.note}</textarea>

            <div class="flex gap-2 justify-end">
                <button onclick="loadWishlist()" class="px-3 py-1 text-xs bg-gray-300 hover:bg-gray-400 rounded text-white">취소</button>
                <button onclick="saveEdit('${address}', '${elementId}')" class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded text-white font-bold shadow-sm">저장</button>
            </div>
        </div>
    `;
};

// --- 수정 저장 ---
window.saveEdit = async (address, elementId) => {
    const newGroup = document.getElementById(`edit-group-${elementId}`).value;
    const newColor = document.getElementById(`edit-color-${elementId}`).value;
    const newNote = document.getElementById(`edit-note-${elementId}`).value;

    try {
        await fetch('/api/wishlist', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                address: address, 
                color: newColor, 
                group_name: newGroup, 
                note: newNote 
            })
        });
        loadWishlist(); 
    } catch(e) { alert("저장 실패"); }
};

// --- 신규 저장 (좌측 패널) ---
async function saveCurrentLocation() {
    const address = document.getElementById('currentAddress').innerText;
    if (!address) return;

    const group = document.getElementById('markGroupName').value;
    const color = document.getElementById('markColorPicker').value;
    const note = document.getElementById('markNote').value;

    try {
        await fetch('/api/wishlist', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ address, group_name: group, color, note })
        });
        
        alert("저장되었습니다.");
        document.getElementById('selectedInfo').classList.add('hidden');
        if(currentMarker) currentMarker.setMap(null); // 임시 마커 제거
        loadWishlist(); // 리스트 갱신
    } catch (e) { alert("저장 실패"); }
}

// --- 삭제 기능 ---
window.deleteItem = async (e, address) => {
    e.stopPropagation();
    if (!confirm("정말 삭제하시겠습니까?")) return;
    
    try {
        await fetch('/api/wishlist', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ address })
        });
        loadWishlist();
    } catch(e) { alert("삭제 오류"); }
};

// --- [핵심] 지도 마커 생성 함수 (정보창에 로드뷰 버튼 포함) ---
function addMarkerToMap(address, info) {
    naver.maps.Service.geocode({ query: address }, function(status, response) {
        if (status === naver.maps.Service.Status.OK && response.v2.addresses.length > 0) {
            const item = response.v2.addresses[0];
            const latlng = new naver.maps.LatLng(item.y, item.x);

            const marker = new naver.maps.Marker({
                position: latlng, map: map,
                icon: {
                    content: `<div style="background:${info.color}; width:20px; height:20px; border-radius:50%; border:2px solid white; box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>`
                }
            });

            // 정보창 컨텐츠 (로드뷰 버튼 포함)
            const infoWindow = new naver.maps.InfoWindow({
                content: `
                    <div style="padding:10px; min-width:180px;">
                        <div style="font-size:11px; color:#888;">${info.group_name}</div>
                        <div style="font-weight:bold; font-size:13px; margin-bottom:5px;">${address}</div>
                        ${info.note ? `<div style="background:#f3f4f6; padding:4px; border-radius:4px; font-size:11px; margin-bottom:5px;">${info.note}</div>` : ''}
                        
                        <button onclick="openRoadView(${item.y}, ${item.x}, '${address}')" 
                                class="w-full bg-blue-500 hover:bg-blue-600 text-white text-xs py-1.5 rounded font-bold transition flex items-center justify-center gap-1">
                            <i class="fa-solid fa-street-view"></i> 로드뷰 보기
                        </button>
                    </div>`,
                backgroundColor: "white",
                borderColor: "#ccc",
                borderWidth: 1,
                anchorSize: new naver.maps.Size(10, 10)
            });

            naver.maps.Event.addListener(marker, 'click', () => {
                if (infoWindow.getMap()) infoWindow.close();
                else infoWindow.open(map, marker);
            });

            markers.push(marker);
            markerMap[address] = marker;
            infoWindows[address] = infoWindow;
        }
    });
}

// --- [추가] 새 탭에서 로드뷰 열기 함수 (좌표 기반) ---
window.openRoadView = function(lat, lng, address) {
    // 쿼리 파라미터로 좌표와 주소를 전달하여 새 탭 열기
    const url = `/panorama?lat=${lat}&lng=${lng}&addr=${encodeURIComponent(address)}`;
    window.open(url, '_blank'); 
};

function moveToLocation(address) {
    const marker = markerMap[address];
    if (marker) {
        map.panTo(marker.getPosition());
        map.setZoom(17, true);
        infoWindows[address].open(map, marker);
    } else {
        alert("지도에 표시되지 않는 위치입니다.");
    }
}

function searchAddress() {
    const query = document.getElementById('searchInput').value;
    if (!query) return;
    naver.maps.Service.geocode({ query: query }, function(status, response) {
        if (status !== naver.maps.Service.Status.OK || response.v2.addresses.length === 0) {
            return alert('주소를 찾을 수 없습니다.');
        }
        const item = response.v2.addresses[0];
        const point = new naver.maps.LatLng(item.y, item.x);
        
        map.setCenter(point);
        map.setZoom(17);
        setTempMarker(point, item.roadAddress || item.jibunAddress);
    });
}

function searchCoordinateToAddress(latlng) {
    naver.maps.Service.reverseGeocode({
        coords: latlng,
        orders: [naver.maps.Service.OrderType.ADDR, naver.maps.Service.OrderType.ROAD_ADDR].join(',')
    }, function(status, response) {
        if (status === naver.maps.Service.Status.OK) {
            const items = response.v2.results;
            if (items.length > 0) {
                let address = items[0].region.area1.name + " " + items[0].region.area2.name + " " + items[0].region.area3.name;
                if (items[0].land) address += " " + items[0].land.number1 + (items[0].land.number2 ? "-" + items[0].land.number2 : "");
                setTempMarker(latlng, address);
            }
        }
    });
}

function setTempMarker(latlng, address) {
    if (currentMarker) currentMarker.setMap(null);
    currentMarker = new naver.maps.Marker({
        position: latlng, map: map,
        animation: naver.maps.Animation.BOUNCE
    });
    document.getElementById('currentAddress').innerText = address;
    document.getElementById('selectedInfo').classList.remove('hidden');
    
    // 저장 폼 초기화
    document.getElementById('markNote').value = '';
    document.getElementById('markGroupName').value = '관심물건';
}

function toggleSidebar() {
    const panel = document.getElementById('sidePanel');
    const icon = document.getElementById('toggleIcon');
    if (panel.classList.contains('translate-x-0')) {
        panel.classList.remove('translate-x-0');
        panel.classList.add('translate-x-full');
        icon.className = 'fa-solid fa-chevron-left';
    } else {
        panel.classList.remove('translate-x-full');
        panel.classList.add('translate-x-0');
        icon.className = 'fa-solid fa-chevron-right';
    }
}

// --- [수정] 선택된 위치 패널의 로드뷰 버튼 동작 ---
function openCurrentRoadView() {
    const address = document.getElementById('currentAddress').innerText;
    if (!address) {
        alert("선택된 주소가 없습니다.");
        return;
    }

    // 1. 현재 지도에 찍힌 임시 마커가 있다면 그 좌표 사용 (가장 정확)
    if (currentMarker) {
        const pos = currentMarker.getPosition();
        openRoadView(pos.y, pos.x, address);
    } 
    // 2. 예외 처리: 텍스트는 있는데 마커가 없는 경우 (다시 검색)
    else {
        naver.maps.Service.geocode({ query: address }, function(status, response) {
            if (status === naver.maps.Service.Status.OK && response.v2.addresses.length > 0) {
                const item = response.v2.addresses[0];
                openRoadView(item.y, item.x, address);
            } else {
                alert("위치 좌표를 찾을 수 없습니다.");
            }
        });
    }
}