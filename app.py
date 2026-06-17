# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import re
import calendar
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import urllib.request

# 1. 網頁基礎設定
st.set_page_config(page_title="技術處化驗科排班看板", page_icon="🧪", layout="centered")

st.title("🧪 技術處化驗科 ─ 個人排班月行事曆")
st.write("您可以透過【上傳檔案】或【手機現場拍照】導入最新班表，系統將自動定位辨識並產出可下載的行事曆圖檔。")

# 安全下載中文字型機制
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

# 2. 側邊欄：設定班別與時間對照
st.sidebar.header("⚙️ 班別時間配置")
time_A = st.sidebar.text_input("早班 (A)", "08:00 - 16:00")
time_B = st.sidebar.text_input("中班 / 小夜班 (B)", "16:00 - 24:00")
time_C = st.sidebar.text_input("夜班 / 大夜班 (C)", "00:00 - 08:00")

# 3. 📸 照片上傳與拍照功能區
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

# 初始化 Session State
if 'rotation_angle' not in st.session_state:
    st.session_state.rotation_angle = 0
if 'last_img_name' not in st.session_state:
    st.session_state.last_img_name = None
if 'step2_confirmed' not in st.session_state:
    st.session_state.step2_confirmed = False

if img_file is not None and img_file.name != st.session_state.last_img_name:
    st.session_state.rotation_angle = 0
    st.session_state.last_img_name = img_file.name
    st.session_state.step2_confirmed = False

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
            st.session_state.step2_confirmed = False
            st.rerun()
    with col_rot2:
        if st.button("↪️ 順時針轉 90°"):
            st.session_state.rotation_angle = (st.session_state.rotation_angle + 90) % 360
            st.session_state.step2_confirmed = False
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


# 🎯 徹底重構的暴力解算 OCR 識別核心
def robust_extract_schedule(_img_np):
    try:
        import pytesseract
        
        # 1. 針對照片進行多重影像預處理 (提升反差，過濾紙張灰底)
        gray = cv2.cvtColor(_img_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)
        # 放大圖片使小字體清晰
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 7)
        
        # 2. 同時提取兩種 PSM 模式下的全圖純文字
        pil_img = Image.fromarray(thresh)
        raw_text_6 = pytesseract.image_to_string(pil_img, lang='chi_tra+eng', config=r'--psm 6')
        raw_text_11 = pytesseract.image_to_string(pil_img, lang='chi_tra+eng', config=r'--psm 11')
        
        full_blob = raw_text_6 + "\n" + raw_text_11
        
        # 移除不可見亂碼，統一轉換為半形
        full_blob = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', full_blob)
        
        # 3. 解析當前年份與月份特徵 (從照片尋找如 2026 或 04、05)
        target_month = 4 # 預設防呆為照片顯示之 4 月
        if "2026" in full_blob:
            month_match = re.search(r'2026[^\d]*0?([45])', full_blob)
            if month_match:
                target_month = int(month_match.group(1))

        # 4. 全局 Token 清洗與配對演算法
        # 我們直接找出圖片中所有「可能是日期」與「可能是班別」的獨立單字
        tokens = full_blob.split()
        
        schedule_map = {}
        pending_day = None
        
        # 定義合法的班別代號集合
        valid_shifts = {"A", "B", "C", "代A", "H", "O", "S", "a", "b", "c"}
        
        for t in tokens:
            t = t.strip()
            # 檢查是否為標準的 M/D 格式 (例如 4/21)
            md_match = re.search(r'([45])[:/.\-_](\d{1,2})', t)
            if md_match:
                m_val = int(md_match.group(1))
                d_val = int(md_match.group(2))
                if 1 <= d_val <= 31:
                    target_month = m_val
                    pending_day = d_val
                continue
                
            # 如果單純是 1~2 位數的純數字，且前面沒有未配對的日期，暫存為可能的「日」
            if t.isdigit():
                val = int(t)
                # 過濾掉時間（如 08, 16, 24, 00）與年份（2026）
                if 1 <= val <= 31 and val not in [2026, 8, 16, 24]:
                    pending_day = val
                continue
            
            # 如果是班別代號，且目前有留存的「日」，立刻進行綁定
            if t in valid_shifts or any(vs in t for vs in valid_shifts):
                # 提取出乾淨的班別名稱
                shift_clean = ""
                if "代A" in t: shift_clean = "代A"
                elif "A" in t or "a" in t: shift_clean = "A"
                elif "B" in t or "b" in t: shift_clean = "B"
                elif "C" in t or "c" in t: shift_clean = "C"
                elif "H" in t: shift_clean = "H"
                elif "O" in t: shift_clean = "O"
                elif "S" in t: shift_clean = "S"
                
                if pending_day and shift_clean:
                    schedule_map[pending_day] = shift_clean
                    pending_day = None # 配對成功，清除狀態
                    
        # 5. 將結果轉回標準的「月份/日期：班別」文字清單
        matched_lines = []
        for d in sorted(schedule_map.keys()):
            matched_lines.append(f"{target_month}/{d:02d}：{schedule_map[d]}")
            
        if matched_lines:
            return "\n".join(matched_lines)
            
        # 終極備援：若無任何配對，但抓得到零星班別字母，直接列出供校對
        fallback_words = re.findall(r'\b[ABC代HOSabc]\b', full_blob)
        if fallback_words:
            st.info("💡 系統已為您捕捉到照片內散落的班別代號，請在下方手動加上日期。")
            return "\n".join([f"{target_month}/{i+1}：{w.upper()}" for i, w in enumerate(fallback_words[:30])])

        return ""
    except Exception as e:
        err_msg = str(e)
        if "tesseract is not installed" in err_msg.lower() or "path" in err_msg.lower():
            return "ERR_TESSERACT_NOT_FOUND"
        return f"辨識核心異常: {err_msg}"

extracted_text = ""
if opencv_image is not None:
    with st.spinner("🎯 正在啟用全局字元網格檢索，強力清洗照片內表格數據..."):
        ocr_extracted = robust_extract_schedule(opencv_image)
        if ocr_extracted == "ERR_TESSERACT_NOT_FOUND":
            st.error("❌ 系統偵測到伺服器尚未安裝 Tesseract OCR 主程式。請確認專案根目錄中已建立包含 'tesseract-ocr' 的 packages.txt 檔案並推送到 GitHub 重新部署。")
        elif ocr_extracted:
            extracted_text = ocr_extracted
            st.success("✨ 班表內容處理完成！")
        else:
            extracted_text = ""
            st.warning("⚠️ 由於照片格線及文字亂碼塊較明顯，未能全自動精準對齊。已為您將核對欄清空，請直接在下方手動貼上或輸入排班。")
else:
    extracted_text = ""

# 4. 📝 步驟二：純文字班表確認與核對區
st.markdown("---")
st.subheader("📝 步驟二：系統辨識結果核對與人工修正")
st.caption("請檢查下方每一行是否皆符合『月份/日期：班別』格式（例如：`4/21：B`）。")
user_input = st.text_area("排班原始文字核對欄：", value=extracted_text, height=250, placeholder="範例格式：\n4/21：B\n4/22：代A\n5/01：C")

# 在步驟2和步驟3之間的新增確認按鈕
col_btn1, col_btn2 = st.columns([2, 1])
with col_btn1:
    if st.button("👉 確認上方班表內容無誤，進行下一步驟", type="primary"):
        st.session_state.step2_confirmed = True
with col_btn2:
    if st.session_state.step2_confirmed:
        st.success("✅ 狀態：已確認")
    else:
        st.info("⏳ 狀態：待確認")

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
    img = Image.new("RGB", (620, 920), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    if font_ttf_path:
        font_title = ImageFont.truetype(font_ttf_path, 20)
        font_subtitle = ImageFont.truetype(font_ttf_path, 15)
        font_text = ImageFont.truetype(font_ttf_path, 12)
        font_shift = ImageFont.truetype(font_ttf_path, 11)
    else:
        font_title = font_subtitle = font_text = font_shift = ImageFont.load_default()

    draw.rectangle([(15, 15), (605, 905)], outline="#E0E0E0", width=2)
    draw.text((35, 35), "遠東新世紀股份有限公司 觀音化學纖維廠", fill="#1D1D1F", font=font_title)
    draw.text((35, 65), "技術處化驗科 ─ 個人排班月行事曆", fill="#424245", font=font_subtitle)
    
    draw.rectangle([(35, 95), (585, 150)], fill="#F5f5F7")
    draw.text((45, 103), f"A: 早班 ({time_A})   B: 中班 ({time_B})", fill="#1D1D1F", font=font_text)
    draw.text((45, 125), f"C: 夜班 ({time_C})   H/O/S/代班: 休假/公假", fill="#1D1D1F", font=font_text)

    y_offset = 175
    for month in sorted(schedule_data.keys()):
        draw.rectangle([(35, y_offset), (585, y_offset + 25)], fill="#E8E8ED")
        draw.text((45, y_offset + 4), f"{year}年 {month:02d}月", fill="#1D1D1F", font=font_subtitle)
        y_offset += 32
        
        weeks = ['日', '一', '二', '三', '四', '五', '六']
        for i, wk in enumerate(weeks):
            draw.text((42 + i*78, y_offset), wk, fill="#86868B", font=font_text)
        y_offset += 22
        
        first_day = datetime.date(year, month, 1)
        blank_cells = (first_day.weekday() + 1) % 7
        total_days = calendar.monthrange(year, month)[1]
        
        current_cell = blank_cells
        x_start = 35
        for day in range(1, total_days + 1):
            col = current_cell % 7
            row = current_cell // 7
            box_x1 = x_start + col * 79
            box_y1 = y_offset + row * 58
            box_x2 = box_x1 + 72
            box_y2 = box_y1 + 52
            
            draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill="#F5F5F7")
            draw.text((box_x1 + 5, box_y1 + 4), str(day), fill="#1D1D1F", font=font_text)
            
            if day in schedule_data[month]:
                shift = schedule_data[month][day]
                # 統一轉成大寫進行比對與渲染
                shift_upper = shift.upper()
                if 'A' in shift_upper and '代' not in shift:
                    bg_color = "#FFE082"
                elif 'B' in shift_upper:
                    bg_color = "#B3E5FC"
                elif 'C' in shift_upper:
                    bg_color = "#C8E6C9"
                else:
                    bg_color = "#E0E0E0"
                    
                draw.rectangle([(box_x1 + 4, box_y1 + 22), (box_x2 - 4, box_y2 - 4)], fill=bg_color)
                draw.text((box_x1 + 8, box_y1 + 27), shift, fill="#1D1D1F", font=font_shift)
            current_cell += 1
            
        rows_count = (current_cell - 1) // 7 + 1
        y_offset += rows_count * 60 + 12
    return img

# 6. 🔓 步驟三：行事曆生成與圖檔下載
if st.session_state.step2_confirmed:
    if user_input.strip():
        try:
            parsed_data, year_val = parse_schedule(user_input)
            if parsed_data:
                st.markdown("---")
                st.subheader("🖼️ 步驟三：行事曆生成與圖檔下載")
                
                generated_img = draw_calendar_image(parsed_data, year_val)
                img_buffer = io.BytesIO()
                generated_img.save(img_buffer, format="PNG")
                img_bytes = img_buffer.getvalue()
                
                st.image(img_bytes, caption="這是依據您確認後的內容所生成的最終平板風格排班圖", use_container_width=True)
                st.download_button(
                    label="📥 點此下載排班月行事曆 PNG 圖檔",
                    data=img_bytes,
                    file_name=f"排班行事曆_{year_val}年.png",
                    mime="image/png"
                )
            else:
                st.error("輸入的內容無法被正確解析為日期格式，請確認是否有包含格式如 '4/21'。")
        except Exception as e:
            st.error(f"行事曆生成失敗: {e}")
    else:
        st.warning("請先在步驟二的核對欄內輸入或貼入您的排班資料。")
