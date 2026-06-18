# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import re
import calendar
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import io
import urllib.request
import easyocr  # 引入進階 OCR 辨識引擎

# 設定網頁為寬螢幕置中模式
st.set_page_config(page_title="技術處化驗科雙框OCR排班系統", page_icon="🧪", layout="centered")

st.title("🧪 技術處化驗科 ─ 全網頁自適應雙框 OCR 系統")
st.write("📊 **介面全網頁優化**：所有控制器已全面移至中央主網頁區。操作動線一目了然，您可以直接在下方調整滑桿、縮放紅綠雙框並啟動 AI 辨識！")

# 安全下載中文字型（用於產出美化圖片）
@st.cache_resource
def load_online_font():
    try:
        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        font_path = "NotoSansCJKtc-Regular.otf"
        with urllib.request.urlopen(font_url) as response, open(font_path, 'wb') as out_file:
            out_file.write(response.read())
        return font_path
    except Exception:
        return None

font_ttf_path = load_online_font()

# 初始化 OCR 讀取器 (支援繁體中文與英文數字)
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['ch_tra', 'en'], gpu=False)

reader = load_ocr_reader()

# 狀態管理
if 'rotation_angle' not in st.session_state: st.session_state.rotation_angle = 0
if 'last_img_name' not in st.session_state: st.session_state.last_img_name = None
if 'confirmed_data' not in st.session_state: st.session_state.confirmed_data = None

# --- 1. 導入班表照片與基本參數設定（全網頁中央區） ---
uploaded_file = st.file_uploader("請上傳化驗科大表照片...", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    if uploaded_file.name != st.session_state.last_img_name:
        st.session_state.last_img_name = uploaded_file.name
        st.session_state.rotation_angle = 0
        st.session_state.confirmed_data = None

    # 讀取影像並標準化寬度為 640
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    orig_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # 旋轉按鈕（改為全網頁置中）
    col_rot1, col_rot2 = st.columns(2)
    with col_rot1:
        if st.button("↩️ 逆時針 90°", use_container_width=True): 
            st.session_state.rotation_angle = (st.session_state.rotation_angle - 90) % 360
            st.rerun()
    with col_rot2:
        if st.button("↪️ 順時針 90°", use_container_width=True): 
            st.session_state.rotation_angle = (st.session_state.rotation_angle + 90) % 360
            st.rerun()

    if st.session_state.rotation_angle == 90: orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_CLOCKWISE)
    elif st.session_state.rotation_angle == 180: orig_img = cv2.rotate(orig_img, cv2.ROTATE_180)
    elif st.session_state.rotation_angle == 270: orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    standard_w = 640
    h_orig, w_orig, _ = orig_img.shape
    standard_h = int(h_orig * (standard_w / w_orig))
    cv_img = cv2.resize(orig_img, (standard_w, standard_h))

    # --- 2. 📅 班表主月份設定（從側邊欄移至中央網頁） ---
    st.markdown("### 📅 1. 設定排班主月份")
    target_month = st.number_input("請輸入大表主月份 (例如 5月大表)", min_value=1, max_value=12, value=5, step=1)
    
    prev_month = target_month - 1 if target_month > 1 else 12
    days_in_prev = calendar.monthrange(2026, prev_month)[1]
    
    date_sequence = []
    for d in range(21, days_in_prev + 1): date_sequence.append((prev_month, d))
    for d in range(1, 21): date_sequence.append((target_month, d))
    total_days = len(date_sequence)

    # --- 3. 🎛️ 雙框畫布調整面板（全網頁版本，左右分欄控制） ---
    st.markdown("### 🎛️ 2. 自主拖拉與無段縮放控制面板")
    st.caption("調整下方滑桿時，下方預覽圖的紅框與綠框會即時變動位置與大小，請精準對齊您的格子。")
    
    col_ctrl1, col_ctrl2 = st.columns(2)
    
    with col_ctrl1:
        st.markdown("<div style='background-color:#FFF5F5; padding:15px; border-radius:10px; border-left:5px solid #FF0000;'>", unsafe_allow_html=True)
        st.markdown("#### 🟥 框 1 (個人排班格子)")
        b1_center_x = st.slider("框1 左右水平位置 (X)", 0, standard_w, 335, key="b1_cx")
        b1_center_y = st.slider("框1 上下垂直位置 (Y)", 0, standard_h, 230, key="b1_cy")
        b1_width = st.slider("框1 寬度大小", 50, standard_w, 435, key="b1_w")
        b1_height = st.slider("框1 高度大小", 10, 150, 30, key="b1_h")
        st.markdown("</div>", unsafe_allow_html=True)
        
        b1_x1 = max(0, b1_center_x - b1_width // 2)
        b1_x2 = min(standard_w, b1_center_x + b1_width // 2)
        b1_y1 = max(0, b1_center_y - b1_height // 2)
        b1_y2 = min(standard_h, b1_center_y + b1_height // 2)

    with col_ctrl2:
        st.markdown("<div style='background-color:#F5FBF5; padding:15px; border-radius:10px; border-left:5px solid #00CC00;'>", unsafe_allow_html=True)
        st.markdown("#### 🟩 框 2 (下方手寫備註)")
        b2_center_x = st.slider("框2 左右水平位置 (X)", 0, standard_w, 285, key="b2_cx")
        b2_center_y = st.slider("框2 上下垂直位置 (Y)", 0, standard_h, 705, key="b2_cy")
        b2_width = st.slider("框2 寬度大小", 50, standard_w, 330, key="b2_w")
        b2_height = st.slider("框2 高度大小", 10, 150, 50, key="b2_h")
        st.markdown("</div>", unsafe_allow_html=True)
        
        b2_x1 = max(0, b2_center_x - b2_width // 2)
        b2_x2 = min(standard_w, b2_center_x + b2_width // 2)
        b2_y1 = max(0, b2_center_y - b2_height // 2)
        b2_y2 = min(standard_h, b2_center_y + b2_height // 2)

    # --- 4. 顯示即時雙框網格預覽圖 ---
    st.markdown("### 🖼️ 3. 即時對齊畫面預覽")
    preview_img = cv_img.copy()
    
    # 畫框 1 (排班格) - 紅色
    cv2.rectangle(preview_img, (b1_x1, b1_y1), (b1_x2, b1_y2), (0, 0, 255), 2)
    
    # 畫框 1 內部日曆等分橘線
    step_w = (b1_x2 - b1_x1) / total_days
    for i in range(1, total_days):
        xi = int(b1_x1 + i * step_w)
        cv2.line(preview_img, (xi, b1_y1), (xi, b1_y2), (255, 128, 0), 1)
        
    # 畫框 2 (備註欄) - 綠色
    cv2.rectangle(preview_img, (b2_x1, b2_y1), (b2_x2, b2_y2), (0, 255, 0), 2)

    st.image(cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB), caption="全網頁即時對齊狀態（確認橘色細線有精準切齊每天的格子）", use_container_width=True)

    # --- 5. 🚀 執行 AI 文字識別 ---
    if st.button("🚀 範圍與月份確認無誤，開始啟動 AI 辨識", type="primary", use_container_width=True):
        with st.spinner("AI 正在深度讀取照片內容，請稍候..."):
            
            # 處理【框 1：排班格子 OCR】
            detected_lines = []
            for i, (m, d) in enumerate(date_sequence):
                bx1 = int(b1_x1 + i * step_w)
                bx2 = int(b1_x1 + (i + 1) * step_w)
                
                crop = cv_img[b1_y1:b1_y2, bx1:bx2]
                gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                resized_crop = cv2.resize(gray_crop, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                
                ocr_result = reader.readtext(resized_crop, detail=0)
                
                shift_guess = "O"
                if ocr_result:
                    raw_text = "".join(ocr_result).strip().upper()
                    match = re.search(r'(代A|代公A|公A|A|B|C|H|S|O)', raw_text)
                    if match:
                        shift_guess = match.group(1)
                    else:
                        shift_guess = raw_text[:3] if raw_text else "O"
                
                detected_lines.append(f"{m}/{d:02d}：{shift_guess}")
            
            # 處理【框 2：手寫備註 OCR】
            crop_notes = cv_img[b2_y1:b2_y2, b2_x1:b2_x2]
            gray_notes = cv2.cvtColor(crop_notes, cv2.COLOR_BGR2GRAY)
            enhanced_notes = cv2.equalizeHist(gray_notes)
            
            notes_ocr_result = reader.readtext(enhanced_notes, detail=0)
            detected_notes = " ".join(notes_ocr_result).strip() if notes_ocr_result else "（未辨識到手寫行程）"
            
            st.session_state.confirmed_data = {
                "schedule": "\n".join(detected_lines),
                "notes": detected_notes
            }
        st.success("🎉 AI 影像文字識別完成！請往下拉進行結果核對。")
        st.rerun()

# --- 6. 📝 人工校對與美化圖片導出區 ---
if st.session_state.confirmed_data is not None:
    st.markdown("---")
    st.markdown("### 📝 4. 辨識結果與手機日曆預覽區")
    st.caption("下方為 AI 自動識別出的資料，若照片有反光、陰影造成個別字有錯，您可以直接在此修改，不影響使用。")
    
    col_edit1, col_edit2 = st.columns([3, 2])
    with col_edit1:
        final_schedule = st.text_area("🔧 框1 排班格子識別結果校對：", value=st.session_state.confirmed_data["schedule"], height=250)
    with col_edit2:
        final_notes = st.text_area("📝 框2 手寫行程識別結果校對：", value=st.session_state.confirmed_data["notes"], height=250)

    def parse_text(t):
        data = {}
        for line in t.strip().split('\n'):
            m = re.search(r'(\d+)/(\d+).*?[:：\s]\s*([A-Za-z0-9\u4e00-\u9fa5]+)', line)
            if m:
                m_num, d_num, s_type = int(m.group(1)), int(m.group(2)), m.group(3).strip().upper()
                if m_num not in data: data[m_num] = {}
                data[m_num][d_num] = s_type
        return data

    def draw_beautiful_app_calendar(schedule_data, year, notes_text):
        img = Image.new("RGB", (640, 920), "#FFFFFF")
        draw = ImageDraw.Draw(img)
        
        font_title = ImageFont.truetype(font_ttf_path, 22) if font_ttf_path else ImageFont.load_default()
        font_week = ImageFont.truetype(font_ttf_path, 14) if font_ttf_path else ImageFont.load_default()
        font_day = ImageFont.truetype(font_ttf_path, 12) if font_ttf_path else ImageFont.load_default()
        font_shift = ImageFont.truetype(font_ttf_path, 14) if font_ttf_path else ImageFont.load_default()
        font_note = ImageFont.truetype(font_ttf_path, 13) if font_ttf_path else ImageFont.load_default()

        y_offset = 35
        for month in sorted(schedule_data.keys()):
            has_late_days = any(d >= 21 for d in schedule_data[month].keys())
            draw.text((40, y_offset), f"{year}年 {month:02d}月", fill="#1D1D1F", font=font_title)
            y_offset += 40
            
            weeks = ['日', '一', '二', '三', '四', '五', '六']
            for i, wk in enumerate(weeks):
                draw.text((45 + i*80, y_offset), wk, fill="#8E8E93", font=font_week)
            y_offset += 25
            
            first_day = datetime.date(year, month, 1)
            blank_cells = (first_day.weekday() + 1) % 7
            total_days = calendar.monthrange(year, month)[1]
            current_cell = blank_cells
            
            for day in range(1, total_days + 1):
                col = current_cell % 7
                row = current_cell // 7
                bx1, by1 = 35 + col * 81, y_offset + row * 72
                bx2, by2 = bx1 + 74, by1 + 64
                
                if (has_late_days and day >= 21) or (not has_late_days and day <= 20):
                    shift = schedule_data[month].get(day, "O")
                    
                    if "A" in shift and "代" not in shift and "公" not in shift: bg, tc = "#E3F2FD", "#0D47A1"
                    elif "B" in shift: bg, tc = "#E8F5E9", "#1B5E20"
                    elif "C" in shift: bg, tc = "#FFF9C4", "#F57F17"
                    elif "代" in shift or "公" in shift: bg, tc = "#FFEBEE", "#C62828"
                    else: bg, tc = "#F4F4F6", "#8E8E93"
                    
                    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=8, fill=bg)
                    draw.text((bx1 + 8, by1 + 6), str(day), fill=tc, font=font_day)
                    draw.text((bx1 + 16, by1 + 26), shift, fill=tc, font=font_shift)
                current_cell += 1
            y_offset += ((current_cell - 1) // 7 + 1) * 72 + 25

        if notes_text.strip():
            draw.rounded_rectangle([(35, 770), (605, 880)], radius=12, fill="#FFFDE7")
            draw.text((50, 785), "📋 當月排班特殊行程與公假備註：", fill="#F57F17", font=font_week)
            draw.text((50, 815), f"• {notes_text.strip()}", fill="#424242", font=font_note)
        return img

    # 點擊按鈕直接在下方渲染高質感手機桌布圖檔
    if st.button("🖼️ 產生精美手機 APP 質感美化日曆圖檔", type="secondary", use_container_width=True):
        p_data = parse_text(final_schedule)
        fin_img = draw_beautiful_app_calendar(p_data, 2026, final_notes)
        
        buf = io.BytesIO()
        fin_img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="仿手機 APP 卡片式日曆最終預覽", use_container_width=True)
        st.download_button(label="📥 下載專屬排班圖片至手機照片中", data=buf.getvalue(), file_name="26811_全網頁OCR美化排班表.png", mime="image/png", use_container_width=True)
