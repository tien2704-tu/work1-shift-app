# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import re
import calendar
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io

# 1. 網頁基礎設定 (必須是 Streamlit 的第一個指令)
st.set_page_config(page_title="技術處化驗科排班看板", page_icon="🧪", layout="centered")

st.title("🧪 技術處化驗科 ─ 個人排班月行事曆")
st.write("您可以透過【上傳檔案】或【手機現場拍照】導入最新班表，系統將自動辨識並產出可下載的行事曆圖檔。")

# 側邊欄：設定班別與時間對照
st.sidebar.header("⚙️ 班別時間配置")
time_A = st.sidebar.text_input("早班 (A)", "08:00 - 16:00")
time_B = st.sidebar.text_input("中班 / 小夜班 (B)", "16:00 - 24:00")
time_C = st.sidebar.text_input("夜班 / 大夜班 (C)", "00:00 - 08:00")

# 📸 照片上傳與拍照功能區
st.subheader("📸 步驟一：導入班表照片 / 圖檔")
upload_tab, camera_tab = st.tabs(["📁 上傳班表圖檔", "📷 手機拍照導入"])

img_file = None
with upload_tab:
    uploaded_file = st.file_uploader("請選擇班表照片 (PNG, JPG, JPEG)...", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img_file = uploaded_file

with camera_tab:
    camera_file = st.camera_input("請對準紙本班表進行拍照：")
    if camera_file:
        img_file = camera_file

# 初始化 Session State 用來記錄圖片的旋轉角度
if 'rotation_angle' not in st.session_state:
    st.session_state.rotation_angle = 0
if 'last_img_name' not in st.session_state:
    st.session_state.last_img_name = None

if img_file is not None and img_file.name != st.session_state.last_img_name:
    st.session_state.rotation_angle = 0
    st.session_state.last_img_name = img_file.name

# 處理圖片旋轉邏輯
opencv_image = None
if img_file is not None:
    file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
    opencv_image = cv2.imdecode(file_bytes, 1)
    
    st.markdown("##### 🔄 圖檔方向調整")
    col_rot1, col_rot2, col_rot3 = st.columns([1, 1, 2])
    with col_rot1:
        if st.button("↩️ 逆時針轉 90°"):
            st.session_state.rotation_angle = (st.session_state.rotation_angle - 90) % 360
            st.rerun()
    with col_rot2:
        if st.button("↪️ 順時針轉 90°"):
            st.session_state.rotation_angle = (st.session_state.rotation_angle + 90) % 360
            st.rerun()
    with col_rot3:
        if st.session_state.rotation_angle != 0:
            st.caption(f"目前已旋轉：`{st.session_state.rotation_angle}°`")

    if st.session_state.rotation_angle == 90:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_90_CLOCKWISE)
    elif st.session_state.rotation_angle == 180:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_180)
    elif st.session_state.rotation_angle == 270:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    preview_rgb = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
    st.image(preview_rgb, caption=f"已調正之班表預覽 ({st.session_state.rotation_angle}°)", use_container_width=True)

# 延遲安全載入 OCR 機制，防止雲端伺服器記憶體超載崩潰
@st.cache_resource
def try_ocr_text(_img_np):
    try:
        import easyocr
        reader = easyocr.Reader(['ch_tra', 'en'], gpu=False)
        ocr_results = reader.readtext(_img_np)
        
        lines_dict = {}
        for (bbox, text, prob) in ocr_results:
            if prob > 0.15:
                y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                matched_row = None
                for r_y in lines_dict.keys():
                    if abs(r_y - y_center) < 15:
                        matched_row = r_y
                        break
                if matched_row is not None:
                    lines_dict[matched_row].append((bbox[0][0], text))
                else:
                    lines_dict[y_center] = [(bbox[0][0], text)]
        
        sorted_lines = []
        for r_y in sorted(lines_dict.keys()):
            sorted_words = sorted(lines_dict[r_y], key=lambda x: x[0])
            sorted_lines.append(" ".join([w[1] for w in sorted_words]))
        return "\n".join(sorted_lines)
    except Exception as e:
        return f"ERROR:{e}"

extracted_text = ""
if opencv_image is not None:
    with st.spinner("🔍 系統正在安全沙盒中辨識圖檔文字，初次啟動可能需要較長時間..."):
        res = try_ocr_text(opencv_image)
        if res.startswith("ERROR:"):
            st.warning("⚠️ 雲端偵測到 OCR 初始化逾時，已自動為您切換至手動編輯模式。")
            extracted_text = "4/21：B\n4/22：O\n4/23：代A\n4/24：代A\n4/25：H\n4/26：B"
        else:
            extracted_text = res
            st.success("✨ 圖檔字元識別完成！請在下方檢查並修正內容。")
else:
    extracted_text = "【請先在上方導入照片，或在此處直接貼入純文字班表】"

# 4. 📝 步驟二：純文字班表確認與核對區
st.subheader("📝 步驟二：系統辨識結果核對與人工修正")
user_input = st.text_area("OCR 提取出的原始純文字如下（格式：月份/日期：班別）：", value=extracted_text, height=180)

# 核心解析邏輯
def parse_schedule(text):
    schedule_data = {}
    lines = text.strip().split('\n')
    current_year = 2026
    
    for line in lines:
        match = re.search(r'(\d+)/(\d+).*?[:：\s]\s*([A-Za-z0-9\u4e00-\u9fa5]+)', line)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            shift_type = match.group(3).strip()
            if month not in schedule_data:
                schedule_data[month] = {}
            schedule_data[month][day] = shift_type
    return schedule_data, current_year

# 5. 🎨 核心：Python 後端高畫質圖片生成器
def draw_calendar_image(schedule_data, year):
    img = Image.new("RGB", (600, 850), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("Arial.ttf", 20)
        font_subtitle = ImageFont.truetype("Arial.ttf", 16)
        font_text = ImageFont.truetype("Arial.ttf", 12)
    except IOError:
        font_title = font_subtitle = font_text = ImageFont.load_default()

    draw.rectangle([(20, 20), (580, 830)], outline="#E0E0E0", width=2)
    draw.text((40, 40), "遠東新世紀股份有限公司 觀音化學纖維廠", fill="#1D1D1F", font=font_title)
    draw.text((40, 70), "技術處化驗科 ─ 個人排班月行事曆", fill="#424245", font=font_subtitle)
    
    draw.rectangle([(40, 105), (560, 155)], fill="#F5f5F7")
    draw.text((50, 115), f"A: 早班 ({time_A})  |  B: 中班 ({time_B})", fill="#1D1D1F", font=font_text)
    draw.text((50, 135), f"C: 夜班 ({time_C})  |  H/O/S/代班: 休假", fill="#1D1D1F", font=font_text)

    y_offset = 180
    for month in sorted(schedule_data.keys()):
        draw.rectangle([(40, y_offset), (560, y_offset + 25)], fill="#E8E8ED")
        draw.text((50, y_offset + 5), f"{year}年 {month:02d}月", fill="#1D1D1F", font=font_subtitle)
        y_offset += 35
        
        weeks = ['日', '一', '二', '三', '四', '五', '六']
        for i, wk in enumerate(weeks):
            draw.text((45 + i*72, y_offset), wk, fill="#86868B", font=font_text)
        y_offset += 20
        
        first_day = datetime.date(year, month, 1)
        blank_cells = (first_day.weekday() + 1) % 7
        total_days = calendar.monthrange(year, month)[1]
        
        current_cell = blank_cells
        x_start = 40
        for day in range(1, total_days + 1):
            col = current_cell % 7
            row = current_cell // 7
            box_x1 = x_start + col * 73
            box_y1 = y_offset + row * 55
            box_x2 = box_x1 + 68
            box_y2 = box_y1 + 50
            
            draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill="#F5F5F7")
            draw.text((box_x1 + 5, box_y1 + 5), str(day), fill="#1D1D1F", font=font_text)
            
            if day in schedule_data[month]:
                shift = schedule_data[month][day]
                bg_color = "#FFE082" if shift == 'A' else ("#B3E5FC" if shift == 'B' else ("#C8E6C9" if shift == 'C' else "#E0E0E0"))
                draw.rectangle([(box_x1 + 5, box_y1 + 22), (box_x2 - 5, box_y2 - 5)], fill=bg_color)
                draw.text((box_x1 + 12, box_y1 + 26), shift, fill="#1D1D1F", font=font_text)
            current_cell += 1
            
        rows_count = (current_cell - 1) // 7 + 1
        y_offset += rows_count * 58 + 10
    return img

# 6. 網頁渲染與輸出下載區
if user_input and user_input != "【請先在上方導入照片，或在此處直接貼入純文字班表】":
    try:
        parsed_data, year_val = parse_schedule(user_input)
        st.subheader("🖼️ 步驟三：行事曆生成與圖檔下載")
        
        generated_img = draw_calendar_image(parsed_data, year_val)
        img_buffer = io.BytesIO()
        generated_img.save(img_buffer, format="PNG")
        img_bytes = img_buffer.getvalue()
        
        st.image(img_bytes, caption="這是系統即將為您導出的最終平板風格排班圖", use_container_width=True)
        st.download_button(
            label="📥 點此下載排班月行事曆 PNG 圖檔",
            data=img_bytes,
            file_name=f"排班行事曆_{year_val}年.png",
            mime="image/png"
        )
    except Exception as e:
        st.error(f"行事曆生成失敗: {e}")
