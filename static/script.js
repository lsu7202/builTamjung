let map = null;
let searchMarkers = [];
let loadedPointIds = new Set(); // 이미 로드된 포인트의 ID(주소) 저장소
let lastFilters = "";
let povMarker = null; // 파노라마 시야 표시용 마커
let isRulerMode = false;
let pano = null;
let drawingManager = null;
let resultOverlays = [];
let markerClustering = null; // 클러스터러 변수 추가
let isAroundViewVisible = true;




const ZOOM_THRESHOLD = 12;
const syncChannel = new BroadcastChannel('pano_sync'); // 파노라마 탭과 통신

function initMap(x = 37.5665, y = 126.9780) {
    const mapContainer = document.getElementById('map');
    if (!mapContainer) return;

    map = new naver.maps.Map(mapContainer, {
        center: new naver.maps.LatLng(x, y),
        zoom: 15
    });

    // 지도가 움직임이 멈췄을 때 데이터 로드
    naver.maps.Event.addListener(map, 'idle', refreshMapData);

    markerClustering = new MarkerClustering({
        minClusterSize: 2,
        maxZoom: 19, // 이 줌 레벨보다 커지면 클러스터링 해제
        map: map,
        markers: searchMarkers,
        disableClickZoom: false,
        gridSize: 120,
        icons: [
            // 클러스터 아이콘 (필요시 스타일 수정 가능)
            { content: '<div style="cursor:pointer;width:40px;height:40px;line-height:42px;font-size:12px;color:white;text-align:center;font-weight:bold;background:url(https://navermaps.github.io/maps.js.ncp/docs/img/cluster-marker-1.png);background-size:contain;"></div>', size: new naver.maps.Size(40, 40), anchor: new naver.maps.Point(20, 20) }
        ],
        stylingFunction: function (clusterMarker, count) {
            clusterMarker.getElement().querySelector('div:first-child').innerText = count;
        }
    });

    naver.maps.Event.addListener(map, 'click', function (e) {
        movePovMarker(e.coord);
    });

    if (naver.maps.drawing) {
        setupDrawing();
    } else {
        naver.maps.onJSContentLoaded = function () {
            setupDrawing();
        };
    }

}

// 1. 지도 타입 변경 함수 (일반/위성 혼합형)
function setMapType(type) {
    const btnNormal = document.getElementById('btn-normal-map');
    const btnSatellite = document.getElementById('btn-satellite-map');

    if (type === 'satellite') {
        // [수정] SATELLITE 대신 HYBRID를 사용해야 라벨(도로명, 랜드마크 등)이 보입니다.
        map.setMapTypeId(naver.maps.MapTypeId.HYBRID);
        btnSatellite.classList.add('active');
        btnNormal.classList.remove('active');
    } else {
        map.setMapTypeId(naver.maps.MapTypeId.NORMAL);
        btnNormal.classList.add('active');
        btnSatellite.classList.remove('active');
    }
}

function setupDrawing() {
    drawingManager = new naver.maps.drawing.DrawingManager({
        map: map,
        drawingControl: [],
        polylineOptions: {
            strokeColor: '#ff4d4d',
            strokeWeight: 4
        }
    });

    // 1. 선이 추가될 때 (더블클릭/우클릭 종료)
    drawingManager.addListener('polylineAdded', function (overlay) {
        const path = overlay.getPath();
        const infoWindow = calculateAndShowDistance(path);

        // ★ 중요: 선 객체에 생성된 정보창을 몰래 숨겨둡니다 (나중에 찾아서 지우려고)
        overlay.myInfoWindow = infoWindow;

        resultOverlays.push(overlay);
        stopRuler();
    });

    // 2. ★ 우클릭 메뉴로 선을 삭제할 때 발생하는 이벤트
    drawingManager.addListener('polylineRemoved', function (overlay) {
        console.log("우클릭으로 선 삭제됨");

        // 아까 숨겨뒀던 정보창을 찾아서 지도에서 지웁니다.
        if (overlay.myInfoWindow) {
            overlay.myInfoWindow.setMap(null);
        }

        // 관리 배열에서도 해당 선을 제거합니다.
        resultOverlays = resultOverlays.filter(item => item !== overlay);
    });
}

/**
 * 3. 거리 계산 및 결과 표시 (InfoWindow)
 */
function calculateAndShowDistance(path) {
    if (!path || path.getLength() < 2) return null;

    let totalDistance = 0;
    for (let i = 0; i < path.getLength() - 1; i++) {
        totalDistance += map.getProjection().getDistance(path.getAt(i), path.getAt(i + 1));
    }

    const distanceStr = totalDistance >= 1000
        ? (totalDistance / 1000).toFixed(2) + " km"
        : Math.round(totalDistance) + " m";

    // 결과창(InfoWindow) 생성
    const infoWindow = new naver.maps.InfoWindow({
        content: `<div style="padding:5px 10px; background:#ff4d4d; color:white; border-radius:20px; font-size:12px; font-weight:bold; border:2px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.2);">총 거리: ${distanceStr}</div>`,
        borderWidth: 0,
        disableAnchor: true,
        backgroundColor: 'transparent',
        pixelOffset: new naver.maps.Point(0, -15)
    });

    const lastCoord = path.getAt(path.getLength() - 1);
    infoWindow.open(map, lastCoord);

    return infoWindow; // 생성된 객체 반환
}

/**
 * 4. 제어 및 삭제 함수
 */
function toggleRuler() {
    if (!drawingManager) return;
    isRulerMode = !isRulerMode;
    const btn = document.getElementById('ruler-btn');

    if (isRulerMode) {
        if (povMarker) povMarker.setMap(null);

        drawingManager.set('drawingMode', naver.maps.drawing.DrawingMode.POLYLINE);
        if (btn) btn.classList.add('bg-red-100', 'text-red-600');
        map.setCursor('crosshair');
    } else {
        stopRuler();
    }
}

function stopRuler() {
    isRulerMode = false;
    if (drawingManager) drawingManager.set('drawingMode', naver.maps.drawing.DrawingMode.HAND);

    if (povMarker) povMarker.setMap(map);
    const btn = document.getElementById('ruler-btn');
    if (btn) btn.classList.remove('bg-red-100', 'text-red-600');
    map.setCursor('grab');


}

// ★ 전체 삭제 기능: 이 함수를 호출하면 선과 거리 정보창이 모두 사라집니다.
function clearRuler() {
    if (resultOverlays.length === 0) return;

    resultOverlays.forEach(item => {
        // A. DrawingManager에서 관리하는 도형인 경우 (id나 name 속성이 있음)
        if (drawingManager && (item.id || item.name)) {
            drawingManager.removeDrawing(item);
        }

        // B. 지도에서 직접 제거 (InfoWindow 및 Polyline 공통)
        if (item.setMap) {
            item.setMap(null);
        }
    });

    // 바구니 비우기
    resultOverlays = [];
    console.log("모든 측정 데이터가 삭제되었습니다.");
}

/**
 * 2. 마커 가시성 제어 함수
 * @param {boolean} visible - 표시 여부
 */
function updateMarkersVisibility(visible) {
    const targetMap = visible ? map : null;
    searchMarkers.forEach(marker => {
        // 현재 상태와 다를 때만 맵 연결 상태 변경 (성능 최적화)
        if (marker.getMap() !== targetMap) {
            marker.setMap(targetMap);
        }
    });
}

/**
 * 3. 마커 렌더링 함수 (누적 방식)
 */
function renderMarkers(points) {
    points.forEach(pt => {
        // ID 캐시에 추가하여 중복 방지
        loadedPointIds.add(pt.addr);

        const marker = new naver.maps.Marker({
            position: new naver.maps.LatLng(pt.y, pt.x),

            icon: {
                content: `<div style="background:#3b82f6; opacity: 0.82; width:24px; height:24px; border-radius:50%; border:0.2px solid white; box-shadow:0px 3px 1px rgba(0,0,0,0.2);"></div>`,
                anchor: new naver.maps.Point(12, 12)
            }
        });

        const infoWindow = new naver.maps.InfoWindow({
            content: `<div style="padding:10px; min-width:140px;">
                <p style="font-weight:bold; font-size:12px; margin-bottom:5px;">
                    <a href="https://map.naver.com/p/search/${pt.addr}" target="_blank" style="text-decoration:none; color:#2563eb;">
                        ${pt.addr} <i class="fa-solid fa-up-right-from-square" style="font-size:10px;"></i>
                    </a>
                </p>
            </div>`
        });

        naver.maps.Event.addListener(marker, 'click', () => { infoWindow.open(map, marker); });

        // 전체 마커 관리 배열에 추가
        searchMarkers.push(marker);
    });

    // [중요] 마커 배열이 업데이트되었음을 클러스터러에 통보
    if (markerClustering) {
        markerClustering.setMarkers(searchMarkers);
    }
}

const MARKER_SIZE = 33;
const MARKER_ICON_CLASS = 'text-4xl'; // 2xl -> 4xl로 키움

/**
 * 4. 마커 전체 삭제 (필터 변경 시에만 호출)
 */
function clearMarkers() {
    searchMarkers.forEach(m => m.setMap(null));
    searchMarkers = [];
    loadedPointIds.clear(); // 로드된 ID 기록도 모두 삭제

    // [중요] 클러스터러에서도 마커 제거
    if (markerClustering) {
        markerClustering.setMarkers([]);
    }
}


function movePovMarker(pos) {
    if (!povMarker) {
        povMarker = new naver.maps.Marker({
            position: pos,
            map: map,
            draggable: true, // ★ 꾹 눌러서 이동 가능하도록 설정
            icon: {
                content: `<div id="pov-arrow" style="transition: transform 0.1s;"><i class="fa-solid fa-location-arrow text-red-500 ${MARKER_ICON_CLASS}"></i></div>`,
                // 크기의 절반을 계산해서 자동으로 중앙 배치
                anchor: new naver.maps.Point(MARKER_SIZE / 2, MARKER_SIZE / 2)
            },
            zIndex: 100
        });

        // 드래그가 끝났을 때 파노라마 위치 업데이트
        naver.maps.Event.addListener(povMarker, 'dragend', function (e) {
            if (pano && document.getElementById('pano-wrapper').style.display === 'block') {
                pano.setPosition(e.coord);
            }
        });
    } else {
        povMarker.setPosition(pos);
    }
}

// 3. 우측 패널 버튼 클릭 시 실행될 함수
function triggerPanoAtMarker() {
    if (!povMarker) {
        alert("지도 위를 클릭하여 로드뷰를 볼 위치를 선택해주세요.");
        return;
    }
    const currentPos = povMarker.getPosition();
    openPano(currentPos.lat(), currentPos.lng());
}

// script.js 하단 또는 적절한 위치
syncChannel.onmessage = function (event) {
    const { type, lat, lng } = event.data;

    if (type === 'MOVE_TO_FIRST_RESULT') {
        // 1. 좌표 생성
        const moveLatLn = new naver.maps.LatLng(lat, lng);

        // 2. 지도 중심 이동
        map.setCenter(moveLatLn);

        // 3. 줌 레벨을 상세 수준으로 변경
        map.setZoom(17);

        // 4. (옵션) 해당 위치에 파노라마(로드뷰) 마커 배치 준비
        if (typeof movePovMarker === 'function') {
            movePovMarker(moveLatLn);
        }
    }
};

// script.js 내 refreshMapData 함수 교체
async function refreshMapData() {
    console.log("--- [지도 데이터 갱신 시작] ---");

    const filterStr = localStorage.getItem('mapFilters');
    if (!filterStr || filterStr === '{}') {
        console.warn("지도 갱신 중단: 검색 조건이 없습니다.");
        clearMarkers();
        return; 
    }

    const currentFilters = JSON.parse(filterStr);

    // 유의미한 필터가 있는지 체크 (디버깅용 로그 포함)
    const hasFilter = (currentFilters.고유번호 && currentFilters.고유번호.length > 0) || 
                      (currentFilters.keyword && currentFilters.keyword.trim() !== "") || 
                      (currentFilters.multi_filters && Object.keys(currentFilters.multi_filters).length > 0) ||
                      (currentFilters.ranges && Object.keys(currentFilters.ranges).length > 0);

    if (!hasFilter) {
        console.warn("지도 갱신 중단: 유효한 필터 값이 없습니다.", currentFilters);
        clearMarkers();
        return;
    }

    // 필터가 바뀌었는지 확인 (바뀌었으면 캐시 비움)
    if (lastFilters !== filterStr) {
        console.log("필터 변경 감지: 마커 캐시를 초기화합니다.");
        clearMarkers();
        lastFilters = filterStr;
    }

    if (map.getZoom() < ZOOM_THRESHOLD) {
        console.log(`줌 레벨 낮음 (${map.getZoom()}): 데이터 요청을 생략합니다.`);
        return;
    }

    // --- [20% 여유 바운드 계산 및 로그] ---
    const bounds = map.getBounds();
    const sw = bounds.getSW();
    const ne = bounds.getNE();
    const lngDiff = ne.lng() - sw.lng();
    const latDiff = ne.lat() - sw.lat();

    const extendedBounds = {
        minX: sw.lng() - (lngDiff * 0.1),
        maxX: ne.lng() + (lngDiff * 0.1),
        minY: sw.lat() - (latDiff * 0.1),
        maxY: ne.lat() + (latDiff * 0.1)
    };
    
    console.log("요청 바운드(20% 확장):", extendedBounds);

    const requestBody = {
        ...currentFilters,
        bounds: extendedBounds
    };

    try {
        const res = await fetch('/api/get_map_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (!res.ok) throw new Error(`HTTP 에러! 상태코드: ${res.status}`);

        const points = await res.json();
        console.log(`서버 응답: ${points.length}개의 데이터 수신`);

        // 이미 로드된 마커 제외 (pt.addr이 null이 아닌지 확인 필수)
        const newPoints = points.filter(pt => pt.addr && !loadedPointIds.has(pt.addr));
        console.log(`신규 마커 생성 대상: ${newPoints.length}개`);

        if (newPoints.length > 0) {
            renderMarkers(newPoints);
        }
    } catch (e) { 
        console.error("!!! 지도 데이터 로딩 실패 !!!", e); 
    }
}

// 파노라마 시야 아이콘 업데이트
function updatePovIcon(type, lat, lng, pan) {
    if (!povMarker) {
        povMarker = new naver.maps.Marker({
            position: new naver.maps.LatLng(lat, lng),
            map: map,
            icon: {
                content: `<i class="fa-solid fa-location-arrow text-red-500 ${MARKER_ICON_CLASS}" id="pov-icon"></i>`,
                anchor: new naver.maps.Point(MARKER_SIZE / 2, MARKER_SIZE / 2)
            }
        });
    }
    if (type === 'pos') povMarker.setPosition(new naver.maps.LatLng(lat, lng));
    if (type === 'pov') document.getElementById('pov-icon').style.transform = `rotate(${pan - 45}deg)`;
}

function searchAddress() {
    const query = document.getElementById('searchInput').value;
    naver.maps.Service.geocode({ query }, (status, res) => {
        if (status === naver.maps.Service.Status.OK && res.v2.addresses.length > 0) {
            const item = res.v2.addresses[0];
            map.setCenter(new naver.maps.LatLng(item.y, item.x));
            map.setZoom(17);
        }
    });
}


function openPano(lat, lng) {
    const wrapper = document.getElementById('pano-wrapper');
    const panoViewDiv = document.getElementById('pano-view');

    // 1. 컨테이너 표시 (크기 계산을 위해 먼저 수행)
    wrapper.style.display = 'block';
    wrapper.classList.remove('hidden');

    const pos = new naver.maps.LatLng(lat, lng);

    // 2. 기존 인스턴스 정리
    if (pano) {
        pano.setVisible(false);
        pano = null;
        panoViewDiv.innerHTML = '';
    }

    // 3. 파노라마 인스턴스 생성 (주요 옵션 명시)
    // aroundControl: 항공뷰 버튼, flightSpot: 헬리콥터 포인트
    pano = new naver.maps.Panorama(panoViewDiv, {
        position: pos,
        aroundControl: true,
        aroundControlOptions: {
            position: naver.maps.Position.TOP_RIGHT
        },
        flightSpot: true,
        visible: true
    });

    // 4. 리사이즈 및 레이아웃 갱신 강제 수행
    // 레이아웃이 block으로 변한 직후 API가 크기를 0으로 잡는 현상을 방지
    setTimeout(() => {
        if (pano) {
            const newSize = new naver.maps.Size(panoViewDiv.clientWidth, panoViewDiv.clientHeight);
            pano.setSize(newSize);
            window.dispatchEvent(new Event('resize'));
        }
    }, 100);

    // 5. 이벤트 리스너 재등록
    naver.maps.Event.addListener(pano, 'position_changed', () => {
        const newPos = pano.getPosition();
        if (povMarker) povMarker.setPosition(newPos);
    });

    naver.maps.Event.addListener(pano, 'pov_changed', () => {
        const pov = pano.getPov();
        const icon = document.getElementById('pov-arrow');
        if (icon) icon.style.transform = `rotate(${pov.pan}deg)`;
    });

    // 지도 위 마커 업데이트
    updatePovMarker(pos);
}

// 4. 지도 위 시야 아이콘 생성/업데이트
function updatePovMarker(pos) {
    if (!povMarker) {
        povMarker = new naver.maps.Marker({
            position: pos,
            map: map,
            icon: {
                content: `<div id="pov-arrow" style="transition: transform 0.1s;"><i class="fa-solid fa-location-arrow text-red-500 text-2xl"></i></div>`,
                anchor: new naver.maps.Point(12, 12)
            },
            zIndex: 100
        });
    } else {
        povMarker.setMap(map);
        povMarker.setPosition(pos);
    }
}

// 1. 파노라마 확대/축소 토글
function togglePanoSize() {
    const wrapper = document.getElementById('pano-wrapper');
    const mapSection = document.getElementById('map-section');
    const mapDiv = document.getElementById('map');
    const icon = document.getElementById('expand-icon');

    wrapper.classList.toggle('expanded');
    
    if (wrapper.classList.contains('expanded')) {
        // [파노라마가 전체화면일 때]
        mapSection.classList.add('mode-panorama-main'); 
        mapDiv.style.display = 'block'; // 지도가 꺼져있었다면 다시 킴
        icon.className = 'fa-solid fa-compress';
    } else {
        // [다시 원래대로 돌아올 때]
        mapSection.classList.remove('mode-panorama-main');
        mapDiv.style.display = 'block'; // 지도는 항상 보이게 복구
        icon.className = 'fa-solid fa-expand';
    }

    // 중요: 지도의 크기가 변했으므로 Naver Map에 알림
    setTimeout(() => {
        if (map) {
            // 지도의 컨테이너 크기 재계산
            window.dispatchEvent(new Event('resize')); 
        }
        if (pano) {
            const newWidth = wrapper.offsetWidth;
            const newHeight = wrapper.offsetHeight;
            pano.setSize(new naver.maps.Size(newWidth, newHeight));
        }
    }, 300);
}

// 2. 미니맵 모드에서 지도만 숨기기
function hideMiniMap() {
    const mapDiv = document.getElementById('map');
    mapDiv.style.display = 'none';
}

/**
 * 웹 브라우저 전체화면 모드 토글
 */
function toggleWebFullScreen() {
    const body = document.body;
    const icon = document.getElementById('full-screen-icon');
    const isFull = body.classList.toggle('is-fullscreen');

    // 아이콘 변경
    if (isFull) {
        icon.classList.replace('fa-maximize', 'fa-minimize');
    } else {
        icon.classList.replace('fa-minimize', 'fa-maximize');
    }

    // 맵 및 파노라마 리사이즈 강제 실행
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
        
        if (map) {
            map.autoResize(); 
        }
        
        if (pano) {
            const panoViewDiv = document.getElementById('pano-view');
            pano.setSize(new naver.maps.Size(panoViewDiv.clientWidth, panoViewDiv.clientHeight));
        }
    }, 300); // CSS 애니메이션 시간을 고려한 지연 실행
}

/**
 * [수정] 파노라마를 닫을 때 전체화면 모드도 함께 해제하도록 보정
 */
function closePano() {
    document.getElementById('pano-wrapper').style.display = 'none';
    
    // 전체화면 모드 해제
    document.body.classList.remove('is-fullscreen');
    const fullIcon = document.getElementById('full-screen-icon');
    if(fullIcon) fullIcon.classList.replace('fa-minimize', 'fa-maximize');

    // PiP 모드 해제 및 지도 복구
    const mapSection = document.getElementById('map-section');
    const mapDiv = document.getElementById('map');
    if(mapSection) mapSection.classList.remove('mode-panorama-main');
    if(mapDiv) mapDiv.style.display = 'block';

    window.dispatchEvent(new Event('resize'));
}

// 거리 계산 함수
function calculateDistance(path) {
    let totalDistance = 0;
    for (let i = 0; i < path.getLength() - 1; i++) {
        const p1 = path.getAt(i);
        const p2 = path.getAt(i + 1);
        totalDistance += map.getProjection().getDistance(p1, p2);
    }
    return totalDistance;
}



/**
 * 지정된 좌표로 지도를 이동시키고 마커를 표시하는 공통 함수
 * @param {number} lat - 위도 (y)
 * @param {number} lng - 경도 (x)
 */
function moveToLocation(lat, lng) {
    // 1. 지도 객체가 있는지 확인 (에러 방지)
    if (!map) {
        console.error("지도 객체(map)가 초기화되지 않았습니다.");
        return;
    }

    const newPos = new naver.maps.LatLng(lat, lng);

    // 2. 중심 이동 및 줌 설정
    map.setCenter(newPos);
    map.setZoom(17);

    // 3. 시야 마커(빨간 화살표) 이동 (함수 존재 여부 체크)
    if (typeof movePovMarker === 'function') {
        movePovMarker(newPos);
    }
}



