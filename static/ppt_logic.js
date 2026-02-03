


// --- 기존 변수 유지 ---
let sourceImg = null;
let imgX = 0; let imgY = 0; let imgScale = 1;
let isDragging = false; let startX, startY;

// --- 전역 관리 객체 (위치도 & 매물사진) ---
let mapCanvasHandlers = [];
let roomCanvasHandlers = []; // 03 매물사진용 추가

// [상단 선언부 추가]
let buildInfoHandler = null;
let landPlanHandler = null;

let map1Handler = null;
let map2Handler = null;

const btn = document.getElementById('generatePpt')

// ppt_logic.js 파일 내 LAYOUT_CONFIG 수정
const LAYOUT_CONFIG = {
    1: [
        { x: 0.8, y: 0.22, w: 9.14, h: 6.34 }
    ],
    2: [
        { x: 0.8, y: 0.22, w: 4.53, h: 6.34 },
        { x: 5.39, y: 0.22, w: 4.53, h: 6.34 }
    ],
    3: [
        { x: 0.8, y: 0.22, w: 4.53, h: 6.34 },      // 좌측 큰 이미지
        { x: 5.39, y: 0.22, w: 4.53, h: 3.15 },   // 우측 상단
        { x: 5.39, y: 3.4, w: 4.53, h: 3.15 }   // 우측 하단
    ],
    4: [
        { x: 0.8, y: 0.22, w: 4.53, h: 3.15 },     // 좌측 상단
        { x: 0.8, y: 3.4, w: 4.53, h: 3.15 },    // 좌측 하단
        { x: 5.39, y: 0.22, w: 4.53, h: 3.15 },   // 우측 상단
        { x: 5.39, y: 3.4, w: 4.53, h: 3.15 }   // 우측 하단
    ],
    locationMap: [
        { x: 0.2, y: 0.76, w: 4.76, h: 5.91 }, // 좌측 이미지 (제목 하단)
        { x: 5.01, y: 0.76, w: 4.76, h: 5.91 }  // 우측 이미지 (제목 하단)
    ],
    splitFull: [
        { x: 0.8, y: 0.14, w: 4.2, h: 6.49 }, // 05 건축물정보 이미지 위치
        { x: 5.68, y: 0.14, w: 4.2, h: 6.49 }  // 06 토지이용계획 이미지 위치
    ]
};

const canvas = document.getElementById('buildingCanvas');
const ctx = canvas.getContext('2d');


// --- 화질 개선을 위한 고해상도 설정 추가 ---
canvas.width = 300 * 3;  // 900
canvas.height = 473.6 * 3; // 1420.8 (기존 1278에서 변경)
canvas.style.width = "300px";
canvas.style.height = "473.6px";

// 보간 품질 설정
ctx.imageSmoothingEnabled = true;
ctx.imageSmoothingQuality = 'high';
const zoomRange = document.getElementById('zoomRange');

// --- 01 건물개요: 단일 이미지 핸들러 (유지 및 버튼 의존성 제거) ---
function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        sourceImg = new Image();
        sourceImg.onload = function () {
            const ratio = Math.max(canvas.width / sourceImg.width, canvas.height / sourceImg.height);
            imgScale = ratio; zoomRange.value = ratio;
            imgX = (canvas.width - sourceImg.width * imgScale) / 2;
            imgY = (canvas.height - sourceImg.height * imgScale) / 2;
            drawCanvas();
        };
        sourceImg.src = e.target.result;
    };
    reader.readAsDataURL(file);


}

function drawCanvas() {
    if (!sourceImg) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(sourceImg, imgX, imgY, sourceImg.width * imgScale, sourceImg.height * imgScale);
}

// 01 건물개요 이벤트 리스너들
// 01 건물개요 이벤트 리스너 수정
canvas.addEventListener('mousedown', (e) => {
    if (sourceImg) {
        isDragging = true;
        // 3배 보정 적용
        startX = (e.offsetX * 3) - imgX;
        startY = (e.offsetY * 3) - imgY;
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (isDragging && sourceImg) {
        // 3배 보정 적용
        imgX = (e.offsetX * 3) - startX;
        imgY = (e.offsetY * 3) - startY;
        drawCanvas();
    }
});
window.addEventListener('mouseup', () => { isDragging = false; });

canvas.addEventListener('wheel', (e) => {
    if (!sourceImg) return; e.preventDefault();
    imgScale = Math.min(Math.max(0.1, imgScale + (e.deltaY > 0 ? -0.05 : 0.05)), 5);
    zoomRange.value = imgScale; drawCanvas();
});
zoomRange.addEventListener('input', (e) => { if (sourceImg) { imgScale = parseFloat(e.target.value); drawCanvas(); } });

class ImageEditor {
    constructor(slideContainer, file, config) {
        this.config = config;
        const scaleFactor = 3; // 해상도 3배 뻥튀기 (고화질 유지 핵심)

        // [수정] 퍼센트와 숫자를 모두 처리하는 변환 함수
        const toPx = (val, base) => {
            if (typeof val === 'string' && val.includes('%')) {
                return (parseFloat(val) / 100) * base;
            }
            return parseFloat(val) * 80; // 기존 인치 방식 유지 (80px/inch)
        };

        const baseW = 800; // 슬라이드 가로 전체 800px
        const baseH = 554; // 슬라이드 세로 전체 554px

        this.wrapper = document.createElement('div');
        this.wrapper.className = "editor-item-wrapper";
        this.wrapper.style.position = "absolute";

        const pixelX = toPx(config.x, baseW);
        const pixelY = toPx(config.y, baseH);
        const pixelW = toPx(config.w, baseW);
        const pixelH = toPx(config.h, baseH);

        this.wrapper.style.left = pixelX + "px";
        this.wrapper.style.top = pixelY + "px";
        this.wrapper.style.width = pixelW + "px";

        this.canvas = document.createElement('canvas');
        // 1. 캔버스 내부 해상도는 3배로 크게 설정
        this.canvas.width = pixelW * scaleFactor;
        this.canvas.height = pixelH * scaleFactor;

        // 2. 화면에 보이는 크기(CSS)는 기존 레이아웃 유지
        this.canvas.style.width = pixelW + "px";
        this.canvas.style.height = pixelH + "px";
        this.canvas.className = "map-edit-canvas";

        this.ctx = this.canvas.getContext('2d');
        // 3. 이미지 보간 품질 최대로 설정
        this.ctx.imageSmoothingEnabled = true;
        this.ctx.imageSmoothingQuality = 'high';

        this.slider = document.createElement('input');
        this.slider.type = "range";
        // 슬라이더 조절 범위를 해상도 증가에 맞춰 넉넉히 설정
        this.slider.min = "0.01"; this.slider.max = "5"; this.slider.step = "0.01";
        this.slider.style.width = "100%";

        this.img = new Image();
        this.scale = 1; this.x = 0; this.y = 0;
        this.isDragging = false;

        this.init(file);
        this.wrapper.appendChild(this.canvas);
        this.wrapper.appendChild(this.slider);
        slideContainer.appendChild(this.wrapper);
    }

    init(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.img.onload = () => {
                // 캔버스의 내부 해상도(this.canvas.width) 기준으로 초기 비율 계산
                const ratio = Math.max(this.canvas.width / this.img.width, this.canvas.height / this.img.height);
                this.scale = ratio; this.slider.value = ratio;
                this.x = (this.canvas.width - this.img.width * this.scale) / 2;
                this.y = (this.canvas.height - this.img.height * this.scale) / 2;
                this.draw();
            };
            this.img.src = e.target.result;
        };
        reader.readAsDataURL(file);
        this.addEvents();
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        // 고해상도 캔버스 위에 이미지를 그림
        this.ctx.drawImage(this.img, this.x, this.y, this.img.width * this.scale, this.img.height * this.scale);
    }

    addEvents() {
        // 드래그 좌표 계산 시 CSS 크기와 실제 픽셀 크기 차이 보정 (scaleFactor 3배)
        this.canvas.onmousedown = (e) => {
            this.isDragging = true;
            this.sx = (e.offsetX * 3) - this.x;
            this.sy = (e.offsetY * 3) - this.y;
        };
        window.addEventListener('mouseup', () => this.isDragging = false);
        this.canvas.onmousemove = (e) => {
            if (this.isDragging) {
                this.x = (e.offsetX * 3) - this.sx;
                this.y = (e.offsetY * 3) - this.sy;
                this.draw();
            }
        };
        this.canvas.onwheel = (e) => {
            e.preventDefault();
            this.scale = Math.min(Math.max(0.01, this.scale + (e.deltaY > 0 ? -0.01 : 0.01)), 5);
            this.slider.value = this.scale; this.draw();
        };
        this.slider.oninput = (e) => { this.scale = parseFloat(e.target.value); this.draw(); };
    }
    getData() { return this.canvas.toDataURL('image/png'); }
}

// --- 다중 업로드 통합 처리 (type에 따라 분기) ---
function handleMultiUpload(e, type) {
    const file = e.target.files[0];
    if (!file) return;

    // 05, 06번은 공통 미리보기 박스 사용
    const preview = document.getElementById('splitPreview');
    const placeholder = document.getElementById('splitPlaceholder');
    if (placeholder) placeholder.style.display = 'none';

    if (type === 'buildInfo') {
        // 기존 왼쪽 이미지가 있다면 삭제 후 새로 생성
        if (buildInfoHandler) preview.removeChild(buildInfoHandler.wrapper);
        buildInfoHandler = new ImageEditor(preview, file, LAYOUT_CONFIG.splitFull[0]);
    } else if (type === 'landPlan') {
        // 기존 오른쪽 이미지가 있다면 삭제 후 새로 생성
        if (landPlanHandler) preview.removeChild(landPlanHandler.wrapper);
        landPlanHandler = new ImageEditor(preview, file, LAYOUT_CONFIG.splitFull[1]);
    } else if (type === 'map1' || type === 'map2') {
        const preview = document.getElementById('mapPreview');
        const placeholder = document.getElementById('mapPlaceholder');
        if (placeholder) placeholder.style.display = 'none';

        if (type === 'map1') {
            if (map1Handler) preview.removeChild(map1Handler.wrapper);
            map1Handler = new ImageEditor(preview, file, LAYOUT_CONFIG.locationMap[0]);
        } else {
            if (map2Handler) preview.removeChild(map2Handler.wrapper);
            map2Handler = new ImageEditor(preview, file, LAYOUT_CONFIG.locationMap[1]);
        }
    } else {
        // 기존 map, room 다중 업로드 로직 (기존 파일 업로드된 ppt_logic.js 내용 유지)
        const files = Array.from(e.target.files);
        const previewId = type === 'map' ? 'mapPreview' : 'roomPreview';
        const targetPreview = document.getElementById(previewId);
        targetPreview.innerHTML = "";

        if (type === 'map') mapCanvasHandlers = [];
        else roomCanvasHandlers = [];

        for (let i = 0; i < files.length; i += 4) {
            const chunk = files.slice(i, i + 4);
            const slideBox = document.createElement('div');
            slideBox.className = "slide-preview-box";
            targetPreview.appendChild(slideBox);
            chunk.forEach((f, idx) => {
                const h = new ImageEditor(slideBox, f, LAYOUT_CONFIG[chunk.length][idx]);
                if (type === 'map') mapCanvasHandlers.push(h);
                else roomCanvasHandlers.push(h);
            });
        }

    }

}

let TitleAddr = "브리핑자료"

// [전역 변수 선언] - 다른 함수(PPT 생성 등)에서도 접근 가능합니다.
let fullAddr = "", area = "", area_p = "", areaUsing = "", offLandPrice = "", offLandPrice_m = "";
let floorArea = "", floorArea_p = "", buildArea = "", buildArea_p = "", buildingLandRatio = "", floorAreaRatio = "";
let under = "", above = "", parking = "", buildDate = "", lift = "";
let price = "", returnrate = "", pricebyarea = "", pricebyfloor = "", alldeposit = "", allrent = "" ;

// --- [추가] DB 컬럼 식별자 전역 변수 ---
const DB_COL_FLOOR = "층";
const DB_COL_TYPE = "형태";
const DB_COL_DEPOSIT = "보증금";
const DB_COL_RENT = "임대료";
const DB_COL_MANAGEMENT = "월관리비";
const DB_COL_AREA = "평수";
const DB_COL_PERIOD = "임대차기간";

// 실제 PPT 생성에 사용될 데이터 배열
let leaseData = [];

async function fetchLeaseData(fullAddress) {
    const addressParts = fullAddress.split(' ');
    const filteredParts = addressParts.slice(2);
    TitleAddr = filteredParts.join(' ');


    try {
        const res = await fetch('/api/get_propDetail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "통합주소": fullAddress })
        });

        const result = await res.json();

        if (result.success && result.data) {
            // DB 데이터를 PPT 로직에서 사용하는 형식으로 매핑
            leaseData = result.data.map(item => ({
                floor: item[DB_COL_FLOOR] || "-",
                type: item[DB_COL_TYPE] || "-",
                // [수정] 금액을 만원 단위로 변환 (/ 10000) 후 콤마 포맷팅
                deposit: Math.floor(Number(item[DB_COL_DEPOSIT] || 0) / 10000).toLocaleString(),
                rent: Math.floor(Number(item[DB_COL_RENT] || 0) / 10000).toLocaleString(),

                management: Math.floor(Number(item[DB_COL_MANAGEMENT] || 0) / 10000).toLocaleString(),
                // [수정] 평수를 숫자로 변환 후 소수점 2자리까지 반올림하여 표시
                area: Number(item[DB_COL_AREA] || 0).toFixed(2),
                period: item[DB_COL_PERIOD] || "-"
            }));
            console.log("임대현황 로드 완료:", leaseData.length, "건");
        } else {
            leaseData = [];
            console.warn("임대현황 데이터가 없습니다.");
        }
    } catch (e) {
        console.error("임대현황 조회 중 오류:", e);
        leaseData = [];
    }
}

async function searchAddressForPPT() {
    const addressInput = document.getElementById('address-Input');
    const address = addressInput.value.trim();
    if (!address) return alert("주소를 입력해주세요.");

    try {
        const res = await fetch('/api/get_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keyword: address,
                limit: 1
            })
        });

        const responseData = await res.json();
        const results = responseData.data || [];

        if (results.length === 0) {
            alert("해당 주소로 등록된 매물 정보를 찾을 수 없습니다.");
            return;
        }

        const building = results[0];

        // 1. 계산을 위한 기초 숫자 파싱 (내부 로컬 변수)
        const rawArea = parseFloat(building.대지면적) || 0;
        const rawFloorArea = parseFloat(building.연면적) || 0;
        const rawBuildArea = parseFloat(building.건축면적) || 0;
        const rawOffLandPrice = parseInt(building.공시지가) || 0;
        const rawPrice = parseInt(building.매매가억) || 0;
        const rawDate = String(building.사용승인일) || "";
        

        // 2. 전역 변수에 데이터 가공 및 초기화
        fullAddr = building.통합주소 || "";

        // [면적] 소수점 2자리 반올림 및 평수(_p) 계산
        area = rawArea.toFixed(2);
        area_p = (rawArea * 0.3025).toFixed(2);

        floorArea = rawFloorArea.toFixed(2);
        floorArea_p = (rawFloorArea * 0.3025).toFixed(2);

        buildArea = rawBuildArea.toFixed(2);
        buildArea_p = (rawBuildArea * 0.3025).toFixed(2);

        // [공시지가 및 금액] 콤마 포맷팅 및 단위 계산
        offLandPrice = rawOffLandPrice.toLocaleString();
        offLandPrice_m = (rawArea > 0 ? Math.round(rawOffLandPrice * rawArea) : 0).toLocaleString();
        price = rawPrice.toLocaleString();

        // [비율] % 기호 추가
        buildingLandRatio = (building.건폐율 || 0) + "%";
        floorAreaRatio = (building.용적률 || 0) + "%";

        // [기타 정보]
        areaUsing = (building.용도지역 || "").replace(/\(.*?\)/g, "").trim();
        under = parseInt(building.규모지하) ? "B" + parseInt(building.규모지하) : "B1";
        above = parseInt(building.규모지상) ? parseInt(building.규모지상) + "F" : "1F";
        parking = parseInt(building.주차장 || "0") + "대";
        buildDate = `${rawDate.substring(0, 4)}/${rawDate.substring(4, 6)}/${rawDate.substring(6, 8)}`;
        lift = parseInt(building.엘리베이터 || "0") + "대";

        returnrate = parseFloat(building.수익률 || "0");
        pricebyarea = parseInt(price / area_p).toLocaleString();;
        pricebyfloor = parseInt(price / floorArea_p).toLocaleString();;
        alldeposit = parseInt(building.총보증금 || "0").toLocaleString();;
        allrent = parseInt(building.총월세부가세별도 || "0").toLocaleString();;

        // 입력창 업데이트
        addressInput.value = fullAddr;

        if (fullAddr) {
            await fetchLeaseData(fullAddr);

        }

    } catch (e) {
        console.error("주소 조회 중 오류 발생:", e);
        alert("데이터를 불러오는 중에 문제가 발생했습니다.");
    }
}

document.getElementById('address-btn').addEventListener('click', searchAddressForPPT);



// 이 함수를 ppt_logic.js의 적당한 곳에 선언해둡니다.
function addImageSlide(pres, title, handlers, COL_BLUE, COL_WHITE) {
    if (handlers.length === 0) return;

    for (let i = 0; i < handlers.length; i += 4) {
        const slide = pres.addSlide();
        const chunk = handlers.slice(i, i + 4);
        const layouts = LAYOUT_CONFIG[chunk.length];

        // 1. 좌측 파란색 세로 구분선
        slide.addShape(pres.ShapeType.rect, {
            x: 0.72, y: 0.19, w: 0.02, h: 6.44,
            fill: { color: COL_BLUE }
        });

        // 2. 좌측 세로 타이틀 (공백을 줄바꿈으로 바꿔서 세로로 출력)
        const verticalTitle = title.split(" ").join("\n");
        slide.addText(verticalTitle, {
            x: 0.1, y: 0.22, w: 0.7,
            fontSize: 28, color: "333333",
            fontFace: "맑은고딕", align: "center", valign: "top",
            shadow: {
                type: "outer",    // 바깥쪽 그림자
                color: "000000",  // 그림자 색상 (검정색 기준)
                opacity: 0.5,     // 투명도 50% (1 - 0.5)
                blur: 6,          // 흐리게 6pt
                angle: 45,        // 각도 45도
                offset: 6         // 간격(거리) 6pt
            }
        });

        // 3. 하단 파란색 안내 바
        slide.addShape(pres.ShapeType.rect, {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fill: { color: COL_BLUE }
        });
        slide.addText("본 자료는 제 3자에게 무단복제, 유포, 변경하지 않는 것에 동의하는 전제로 귀사에게 제공합니다. 이를 위반할 경우 법적 책임을 질 수 있습니다.", {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fontSize: 10, color: COL_WHITE, align: "center", valign: "middle", fontFace: "맑은고딕"
        });

        // 4. 이미지 배치
        chunk.forEach((h, idx) => {
            const cfg = layouts[idx];
            slide.addImage({
                data: h.getData(), x: cfg.x, y: cfg.y, w: cfg.w, h: cfg.h
            });
        });
    }
}

function addImageSlide_location(pres, title, handlers, COL_BLUE, COL_WHITE) {
    if (handlers.length === 0) return;

    // handlers는 [map1Handler, map2Handler] 배열입니다.
    const slide = pres.addSlide();
    const config = LAYOUT_CONFIG.locationMap; // 전역 LAYOUT_CONFIG에서 위치 정보 가져옴

    // 1. 상단 파란색 가로 구분선
    slide.addShape(pres.ShapeType.rect, {
        x: 0.2, y: 0.65, w: 9.6, h: 0.03,
        fill: { color: COL_BLUE }
    });

    // 2. 타이틀 (그림자 효과 포함)
    slide.addText(title, {
        x: 0.2, y: 0.35, w: 7.5,
        fontSize: 28, color: "333333",
        fontFace: "맑은고딕", align: "left",
        shadow: {
            type: "outer", color: "000000", opacity: 0.5,
            blur: 6, angle: 45, offset: 6
        }
    });

    // 3. 하단 파란색 안내 바
    slide.addShape(pres.ShapeType.rect, {
        x: 0, y: 6.72, w: "100%", h: 0.20,
        fill: { color: COL_BLUE }
    });
    slide.addText("본 자료는 제 3자에게 무단복제, 유포, 변경하지 않는 것에 동의하는 전제로 귀사에게 제공합니다. 이를 위반할 경우 법적 책임을 질 수 있습니다.", {
        x: 0, y: 6.72, w: "100%", h: 0.20,
        fontSize: 10, color: COL_WHITE, align: "center", valign: "middle", fontFace: "맑은고딕"
    });

    // 4. 이미지 및 테두리(Shape) 배치
    // handlers 배열(이미지 데이터)을 순회하며 배치합니다.
    handlers.forEach((h, idx) => {
        if (h && config[idx]) {
            const loc = config[idx]; // LAYOUT_CONFIG.locationMap의 좌표를 사용

            // A. 이미지 삽입 (fill, line 옵션은 에러 방지를 위해 제거)
            slide.addImage({
                data: h.getData(), 
                x: loc.x, 
                y: loc.y, 
                w: loc.w, 
                h: loc.h
            });

            // B. 이미지 위에 파란색 사각형 테두리(Shape) 추가
            slide.addShape(pres.ShapeType.rect, {
                x: loc.x,
                y: loc.y,
                w: loc.w,
                h: loc.h,
                fill: { type: 'none' },       // 내부 투명 (이미지가 보이게 함)
                line: { 
                    color: COL_BLUE,          // 파란색 (263977)
                    width: 1.5,               // 테두리 두께
                    dashType: 'solid' 
                }
            });
        }
    });
}



// --- 3. PPT 생성 (01 이미지 자동 획득 로직 적용) ---
async function generatePPT() {

    btn.disabled = true;
    btn.innerText = "생성 중...";

    // [중요] 브라우저가 UI를 새로고침할 시간을 줍니다 (0.1초)
    // 이 코드가 없으면 브라우저는 '어차피 금방 끝날 거니까' 하고 화면을 안 바꿉니다.
    await new Promise(resolve => setTimeout(resolve, 100));

    try {

        const pres = new PptxGenJS();
        pres.defineLayout({ name: 'LAYOUT_13x9', width: 10.0, height: 6.92 });
        pres.layout = 'LAYOUT_13x9';
        const COL_BLUE = "006ec3"; 
        const COL_WHITE = "FFFFFF";
        const COL_LIGHT_GRAY = "F2F2F2"; // 레이블 배경색

        // Slide 1: 표지 (유지)
        const slide1 = pres.addSlide();
        slide1.addImage({ path: "../static/assets/cover_fixed.png", x: 0, y: 0, w: "100%", h: "100%", sizing: { type: "cover" } });
        slide1.addText("The 두꺼비 부동산", {
            x: 0.5, y: 2.0, w: 10.0, fontSize: 72, color: COL_BLUE, bold: true, fontFace: "맑은고딕",
            outline: { color: COL_WHITE, width: 0.5 }
        });

        const ManagerInfo = "담당자: 이사 김정돈\n연락처 : 010-2639-6946\n팩스 : 0504-425-1151\n이메일 : donjuang100@naver.com\n주소 : 서울시 천호대로 111길 20"
        slide1.addText(ManagerInfo, {
            x: "60%", y: "80%", w: "38%", fontSize: 16, color: COL_WHITE, bold: true, fontFace: "맑은고딕", align: "left"
        })

        // Slide 2: 건물개요 (버튼 클릭 없이 캔버스에서 즉시 추출)
        const slide2 = pres.addSlide();
        slide2.addText("01 건물개요", {
            x: 0.2, y: 0.35, fontSize: 28, color: "333333", bold: false,
            shadow: {
                type: "outer",    // 바깥쪽 그림자
                color: "000000",  // 그림자 색상 (검정색 기준)
                opacity: 0.5,     // 투명도 50% (1 - 0.5)
                blur: 6,          // 흐리게 6pt
                angle: 45,        // 각도 45도
                offset: 6         // 간격(거리) 6pt
            }
        });
        slide2.addShape(pres.ShapeType.rect, { x: 0.2, y: 0.65, w: 9.6, h: 0.03, fill: { color: COL_BLUE } });

        // 버튼 없이 현재 캔버스에 있는 이미지를 그대로 가져옴
        if (sourceImg) {
            const currentBuildingImg = canvas.toDataURL('image/png');
            slide2.addImage({ data: currentBuildingImg, x: 0.2, y: 0.74, w: 3.75, h: 5.92 });
        }

        // 5열 시스템: [카테고리, 항목1, 값1, 항목2, 값2]
        const tableData = [
            // 1. 소재지 섹션 (2행)
            [
                { text: "소재지", options: { rowspan: 2, fill: COL_BLUE, color: COL_WHITE, align: "center", valign: "middle", bold: true } },
                { text: "주소", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: fullAddr, options: { colspan: 3, align: "center" } }
            ],
            [
                { text: "도로상황", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: "", options: { colspan: 3, align: "center" } } // DB에 도로상황 정보가 있다면 여기에 변수 입력
            ],

            // 2. 토지정보 섹션 (3행)
            [
                { text: "토지정보", options: { rowspan: 3, fill: COL_BLUE, color: COL_WHITE, align: "center", valign: "middle", bold: true } },
                { text: "대지면적", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${area}m²`, options: { align: "center" } },
                { text: `${area_p}평`, options: { colspan: 2, align: "center" } } // 이미지처럼 평수를 한 셀로 합침
            ],
            [
                { text: "용도지역", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: areaUsing, options: { colspan: 3, align: "center" } }
            ],
            [
                { text: "공시지가(m²)", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${offLandPrice}원`, options: { align: "center" } },
                { text: "합계", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${offLandPrice_m}원`, options: { align: "center", fontSize: 9 } }
            ],

            // 3. 건물정보 섹션 (5행)
            [
                { text: "건물정보", options: { rowspan: 5, fill: COL_BLUE, color: COL_WHITE, align: "center", valign: "middle", bold: true } },
                { text: "연면적", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${floorArea}m²`, options: { align: "center" } },
                { text: `${floorArea_p}평`, options: { colspan: 2, align: "center" } }
            ],
            [
                { text: "건축면적", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${buildArea}m²`, options: { align: "center" } },
                { text: `${buildArea_p}평`, options: { colspan: 2, align: "center" } }
            ],
            [
                { text: "건폐율", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: buildingLandRatio, options: { align: "center" } },
                { text: "용적률", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: floorAreaRatio, options: { align: "center" } }
            ],
            [
                { text: "규모", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${under} ~ ${above}`, options: { align: "center" } },
                { text: "주차대수", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: parking, options: { align: "center" } }
            ],
            [
                { text: "준공년도", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: buildDate, options: { align: "center" } },
                { text: "승강기", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: lift, options: { align: "center" } }
            ],

            // 4. 금융정보 섹션 (3행) - 이미지에 맞춰 전면 수정
            [
                { text: "금융정보", options: { rowspan: 3, fill: COL_BLUE, color: COL_WHITE, align: "center", valign: "middle", bold: true } },
                { text: "매매가", options: { fill: COL_LIGHT_GRAY, align: "center", color: COL_BLUE, bold: true } },
                { text: `${price}억`, options: { align: "center", color: "FF0000", bold: true, fontSize: 14 } },
                { text: "수익률", options: { fill: COL_LIGHT_GRAY, align: "center", color: COL_BLUE, bold: true } },
                // 수익률 데이터는 DB에 있다면 해당 변수를, 없다면 ""를 입력하세요.
                { text: `${returnrate}%`, options: { align: "center", color: "FF0000", bold: true, fontSize: 14 } } 
            ],
            [
                { text: "평단가", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${pricebyarea}원`, options: { align: "center" } }, // 대지 평단가 계산 로직 필요 시 추가
                { text: "평단가(연면적당)", options: { fill: COL_LIGHT_GRAY, align: "center", fontSize: 8 } },
                { text: `${pricebyfloor}원`, options: { align: "center" } }
            ],
            [
                { text: "보증금", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${alldeposit}원`, options: { align: "center" } }, // 임대현황 합계 데이터 활용 권장
                { text: "임대료", options: { fill: COL_LIGHT_GRAY, align: "center" } },
                { text: `${allrent}원`, options: { align: "center" } }
            ],
            [
                {
                    text: "* 토지이용계획확인원 및 건축물대장 기준 작성",
                    options: {
                        colspan: 5,           // 5개 열을 하나로 합침
                        align: "right",       // 오른쪽 정렬
                        fontSize: 8,          // 글자 크기 조절
                        color: "666666",      // 글자 색상 (회색)
                        valign: "bottom",     // 아래쪽 배치
                        // 핵심: 해당 셀의 테두리를 모두 제거하여 빈 공간처럼 보이게 함
                        border: { type: 'none' },
                        padding: [10, 0, 0, 0] // 위쪽 여백을 주어 데이터와 간격 확보
                    }
                }
            ]
        ];

        // 테이블 생성 실행
        // Slide 2: 건물개요 테이블 (비율 유지 및 열 너비 최적화)
        slide2.addTable(tableData, {
            x: 4.06,
            y: 0.75,
            w: 5.74, // 약 4.8인치
            h: 4.64,
            // colW 총합을 4.8인치에 맞게 재배분 (글자 오버플로 방지)
            // [카테고리(0.5), 항목1(0.9), 값1(1.1), 항목2(0.8), 값2(1.5)]
            colW: [1.148, 1.148, 1.148, 1.148, 1.148],
            border: { pt: 0.5, color: "E1E1E1" },
            fontSize: 10,
            rowH: 0.38,
            valign: "middle",
            fontFace: "맑은고딕"
        });

        // 1. 하단 파란색 안내 바 및 문구
        slide2.addShape(pres.ShapeType.rect, {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fill: { color: COL_BLUE }
        });
        slide2.addText("본 자료는 제 3자에게 무단복제, 유포, 변경하지 않는 것에 동의하는 전제로 귀사에게 제공합니다. 이를 위반할 경우 법적 책임을 질 수 있습니다.", {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fontSize: 10, color: COL_WHITE, align: "center", valign: "middle", fontFace: "맑은고딕"
        });

        // 02 위치도 생성 (단 한 줄로 끝!)
        addImageSlide_location(pres, "02 위치도", [map1Handler, map2Handler], COL_BLUE, COL_WHITE);

        // 03 매물사진 생성 (단 한 줄로 끝!)
        addImageSlide(pres, "03 매물사진", roomCanvasHandlers, COL_BLUE, COL_WHITE);

        const slide4 = pres.addSlide();
        slide4.addText("04 임대 세부 내역", {
            x: 0.2, y: 0.35, fontSize: 28, color: "333333", bold: false,
            shadow: {
                type: "outer",    // 바깥쪽 그림자
                color: "000000",  // 그림자 색상 (검정색 기준)
                opacity: 0.5,     // 투명도 50% (1 - 0.5)
                blur: 6,          // 흐리게 6pt
                angle: 45,        // 각도 45도
                offset: 6         // 간격(거리) 6pt
            }
        });
        slide4.addShape(pres.ShapeType.rect, { x: 0.2, y: 0.65, w: 9.6, h: 0.03, fill: { color: COL_BLUE } });

        // 테이블 헤더 구성
        let leaseTableRows = [
            [
                { text: "층(호)", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "형태", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "평수", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "보증금", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "월임대료", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "월관리비", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } },
                { text: "임대차 기간", options: { fill: COL_BLUE, color: COL_WHITE, align: "center", bold: true } }
            ]
        ];

        // 변수로 관리되는 leaseData를 반복하여 행(Row) 추가
        let totalDeposit = 0;
        let totalRent = 0;
        let totalArea = 0;
        let totalManagement = 0;

        // 전역 변수 leaseData에 담긴 데이터를 테이블 행으로 변환
        leaseData.forEach(item => {
            // [추가] Area 포맷팅 로직: 소수점이 .00이면 정수로, 아니면 소수점 2자리 유지
            const areaVal = parseFloat(item.area) || 0;
            const displayArea = (areaVal % 1 === 0) ? areaVal.toString() : areaVal.toFixed(2);

            // [추가] 금액 포맷팅 (개별 행): 만원 단위 쉼표 적용
            // fetchLeaseData에서 이미 toLocaleString() 처리가 되어 있으므로 그대로 사용하거나, 
            // 안전하게 다시 숫자로 바꿔서 처리할 수 있습니다.
            const displayDeposit = (parseFloat(item.deposit.replace(/,/g, '')) || 0).toLocaleString();
            const displayRent = (parseFloat(item.rent.replace(/,/g, '')) || 0).toLocaleString();
            const displayManagement = (parseFloat(item.management.replace(/,/g, '')) || 0).toLocaleString();

            leaseTableRows.push([
                { text: item.floor, options: { align: "center" } },
                { text: item.type, options: { align: "center" } },
                { text: displayArea, options: { align: "center" } }, 
                { text: displayDeposit + " 만", options: { align: "center" } },
                { text: displayRent + " 만", options: { align: "center" } },
                { text: displayManagement + " 만", options: { align: "center" } },
                { text: item.period, options: { align: "center" } }
            ]);

            // 합계 계산 (계산 시에는 쉼표 제거 후 숫자형으로 변환)
            totalDeposit += parseFloat(item.deposit.replace(/,/g, '')) || 0;
            totalRent += parseFloat(item.rent.replace(/,/g, '')) || 0;
            totalArea += areaVal; 
            totalManagement += parseFloat(item.management.replace(/,/g, '')) || 0;
        });

        // [추가] 합계 행 전용 Area 포맷팅 로직
        const totalDisplayArea = (totalArea % 1 === 0) ? totalArea.toString() : totalArea.toFixed(2);

        // 합계 행 추가 (돈 관련 데이터는 toLocaleString()으로 쉼표 적용)
        leaseTableRows.push([
            { text: "합 계", options: { bold: true, align: "center" } },
            { text: "", options: { fill: COL_WHITE } },
            { text: totalDisplayArea, options: { bold: true, align: "center" } },
            { text: totalDeposit.toLocaleString() + " 만", options: { bold: true, align: "center" } },
            { text: totalRent.toLocaleString() + " 만", options: { bold: true, align: "center" } },
            { text: totalManagement.toLocaleString() + " 만", options: { bold: true, align: "center" } },
            { text: "", options: { fill: COL_WHITE } }
        ]);


        // 테이블 삽입 (13:9 비율 가로 10인치에 맞춤)
        slide4.addTable(leaseTableRows, {
            x: 0.26, y: 0.87, w: 9.47,
            colW: [0.75, 1.042, 1.042, 1.042, 1.042, 3.51], // 컬럼 너비 비율 조정
            border: { pt: 0.5, color: "E1E1E1" },
            fontSize: 11,
            rowH: 0.4,
            valign: "middle"
        });

        // 하단 안내 문구 추가 (이미지 하단 텍스트 반영)
        slide4.addText("* 본 임대 내역은 임대인의 진술에 의해 작성되었으므로 사실과 약간의 차이가 발생할 수 있음",
            { x: 0.5, y: 6.2, w: 9.0, fontSize: 9, color: "888888", align: "right" });
        slide4.addText("* 월임대료 부가세 별도",
            { x: 0.5, y: 6.5, w: 9.0, fontSize: 10, color: "000000", bold: true, align: "right" });

        // 1. 하단 파란색 안내 바 및 문구
        slide4.addShape(pres.ShapeType.rect, {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fill: { color: COL_BLUE }
        });
        slide4.addText("본 자료는 제 3자에게 무단복제, 유포, 변경하지 않는 것에 동의하는 전제로 귀사에게 제공합니다. 이를 위반할 경우 법적 책임을 질 수 있습니다.", {
            x: 0, y: 6.72, w: "100%", h: 0.20,
            fontSize: 10, color: COL_WHITE, align: "center", valign: "middle", fontFace: "맑은고딕"
        });


        if (buildInfoHandler || landPlanHandler) {
            const slide56 = pres.addSlide();

            // 1. 하단 파란색 안내 바 및 문구
            slide56.addShape(pres.ShapeType.rect, {
                x: 0, y: 6.72, w: "100%", h: 0.20,
                fill: { color: COL_BLUE }
            });
            slide56.addText("본 자료는 제 3자에게 무단복제, 유포, 변경하지 않는 것에 동의하는 전제로 귀사에게 제공합니다. 이를 위반할 경우 법적 책임을 질 수 있습니다.", {
                x: 0, y: 6.72, w: "100%", h: 0.20,
                fontSize: 10, color: COL_WHITE, align: "center", valign: "middle", fontFace: "맑은고딕"
            });

            // 2. [05 건축물정보] 영역 디자인
            if (buildInfoHandler) {
                // 좌측 타이틀 (세로)
                slide56.addText("05\n건\n축\n물\n정\n보", {
                    x: 0.1, y: 0.22, w: 0.7, fontSize: 28, color: "333333",
                    fontFace: "맑은고딕", align: "center", valign: "top",
                    shadow: {
                        type: "outer",    // 바깥쪽 그림자
                        color: "000000",  // 그림자 색상 (검정색 기준)
                        opacity: 0.5,     // 투명도 50% (1 - 0.5)
                        blur: 6,          // 흐리게 6pt
                        angle: 45,        // 각도 45도
                        offset: 6         // 간격(거리) 6pt
                    }
                });
                // 이미지 앞 세로 구분선
                slide56.addShape(pres.ShapeType.rect, {
                    x: 0.72, y: 0.19, w: 0.02, h: 6.44, fill: { color: COL_BLUE }
                });
                // 이미지 삽입
                const cfg5 = LAYOUT_CONFIG.splitFull[0];
                slide56.addImage({ data: buildInfoHandler.getData(), x: cfg5.x, y: cfg5.y, w: cfg5.w, h: cfg5.h });
            }

            // 3. 중앙 수직 구분선 (좌우 섹션 분리)
            slide56.addShape(pres.ShapeType.line, {
                x: 5.0, y: 0.2, w: 0, h: 6.1,
                line: { color: "CCCCCC", width: 1.0, dashType: "dash" } // 중앙은 점선으로 처리하여 깔끔하게
            });

            // 4. [06 토지이용계획] 영역 디자인
            if (landPlanHandler) {
                // 우측 타이틀 (세로)
                slide56.addText("06\n토\n지\n이\n용\n계\n획", {
                    x: 5, y: 0.22, w: 0.7, fontSize: 28, color: "333333",
                    fontFace: "맑은고딕", align: "center", valign: "top",
                    shadow: {
                        type: "outer",    // 바깥쪽 그림자
                        color: "000000",  // 그림자 색상 (검정색 기준)
                        opacity: 0.5,     // 투명도 50% (1 - 0.5)
                        blur: 6,          // 흐리게 6pt
                        angle: 45,        // 각도 45도
                        offset: 6         // 간격(거리) 6pt
                    }
                });
                // 이미지 앞 세로 구분선
                slide56.addShape(pres.ShapeType.rect, {
                    x: 5.62, y: 0.19, w: 0.02, h: 6.44, fill: { color: COL_BLUE }
                });
                // 이미지 삽입
                const cfg6 = LAYOUT_CONFIG.splitFull[1];
                slide56.addImage({ data: landPlanHandler.getData(), x: cfg6.x, y: cfg6.y, w: cfg6.w, h: cfg6.h });
            }
        }

        const lastSlide = pres.addSlide();
        lastSlide.addImage({
            path: "../static/assets/cover_fixed_2.png", // 제공된 이미지 경로
            x: 0, y: 0, w: "100%", h: "100%",
            sizing: { type: "cover" } // 슬라이드에 꽉 차게 설정
        });

        // 2. "성공적인 투자" - 상단 배치
        lastSlide.addText("성공적인 투자", {
            x: 0.0, y: 0.7, w: 9.0,
            fontSize: 72, color: COL_BLUE,
            fontFace: "맑은고딕", bold: true,
            outline: { color: COL_WHITE, width: 0.5 }
        });

        // 3. "The 두꺼비가 함께 하겠습니다" - 하단 배치 및 부분 색상(파란색) 적용
        lastSlide.addText(
            [
                { text: "The ", options: { color: COL_BLUE, bold: true } },
                { text: "두꺼비", options: { color: COL_BLUE, bold: true } }, // "두꺼비"만 파란색
                { text: "가 함께 하겠습니다", options: { color: COL_WHITE } }
            ],
            {
                x: 0.0, y: "90%", w: "100%",
                fontSize: 52,
                fontFace: "맑은고딕",
                outline: { color: COL_WHITE, width: 0.5 },
                align: "center",  // 텍스트를 중앙 정렬하여 시각적 균형 확보
                wrap: false,

            }
        );

        pres.writeFile({ fileName: `${TitleAddr}.pptx` });
        await new Promise(resolve => setTimeout(resolve, 500));
    } catch {
        alert("오류 발생");
    } finally {
        btn.disabled = false;
        btn.innerText = "자료생성";
    }
}

btn.addEventListener('click', generatePPT);