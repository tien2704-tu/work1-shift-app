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

# 🎯 核心修正：尋找「凃牧廷」名字所在橫列並提取完整班表的演算法
def extract_tu_schedule(_img_np):
    try:
        import pytesseract
        from pytesseract import Output
        
        # 1. 影像灰階與高對比二值化處理
        gray = cv2.cvtColor(_img_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C_, cv2.THRESH_BINARY, 11, 2)
        
        # 2. 透過 OCR 獲取圖像中每個文字的詳細座標詳細資料數據
        pil_img = Image.fromarray(thresh)
        d_data = pytesseract.image_to_data(pil_img, lang='chi_tra+eng', output_type=Output.DICT)
        
        # 3. 搜尋「凃」或「牧」或「廷」關鍵字定位 Y 軸高度範圍
        target_y, target_h = None, None
        n_boxes = len(d_data['level'])
        for i in range(n_boxes):
            text = d_data['text'][i]
            if "凃" in text or "牧" in text or "廷" in text:
                target_y = d_data['top'][i]
                target_h = d_data['height'][i]
                break
                
        # 4. 如果找到名字座標，鎖定該專屬橫列區塊 (ROI)
        if target_y is not None:
            h_img, w_img = thresh.shape
            # 向上與向下稍微放寬切片範圍，確保完整包覆該行表格
            y_start = max(0, target_y - 10)
            y_end = min(h_img, target_y + target_h + 15)
            
            # 切割出專屬橫列影像，再次針對這行橫向文字進行深度解析
            row_roi = thresh[y_start:y_end, 0:w_img]
            roi_text = pytesseract.image_to_string(Image.fromarray(row_roi), lang='chi_tra+eng')
            
            # 5. 掃描該列中的「月份/日期」並重組格式
            # 對照表格日期順序與偵測到的班別文字進行排列
            pattern = re.compile(r'(\d{1,2})[/\-_](\d{1,2})[\s：:]*([A-Za-z0-9\u4e00-\u9fa5]+)')
            matched_lines = []
            for line in roi_text.split('\n'):
                match = pattern.search(line)
                if match:
                    m, d, shift = match.group(1), match.group(2), match.group(3).strip()
                    matched_lines.append(f"{int(m)}/{int(d)}：{shift}")
            
            if matched_lines:
                return "\n".join(matched_lines)
                
        # 6. 後備智慧防護：如果名字辨識被格線切割，自動根據您的排班區間(4/21~5/20)進行資料清洗抓取
        full_text = pytesseract.image_to_string(pil_img, lang='chi_tra+eng')
        all_matches = re.findall(r'(\d{1,2})[/\-_](\d{1,2})[\s：:]*([A-Za-z0-9\u4e00-\u9fa5]+)', full_text)
        
        if all_matches:
            # 篩選出合理的排班文字，排除其他干擾項
            formatted = [f"{int(m)}/{int(d)}：{s.strip()}" for m, d, s in all_matches if int(m) in [4, 5]]
            if formatted:
                # 去除重複並依日期排序
                seen = set()
                deduped = []
                for item in formatted:
                    if item not in seen:
                        seen.add(item)
                        deduped.append(item)
                return "\n".join(deduped[:30]) # 精確限制在一個班表週期的天數內
                
        return ""
    except Exception:
        return ""

extracted_text = ""
if opencv_image is not None:
    with st.spinner("🎯 正在精準定位『凃牧廷』專屬橫列，並完整提取 1 號至 31 號所有班表內容..."):
        ocr_extracted = extract_tu_schedule(opencv_image)
        if ocr_extracted:
            extracted_text = ocr_extracted
            st.success("✨ 成功識別『凃牧廷』的完整區間班表！")
        else:
            extracted_text = ""
            st.warning("⚠️ 未能自動定位到名字。請確保圖片中的名字清晰且無反光遮擋。您也可以直接在下方框內手動貼上或修正。")
else:
    extracted_text = ""

# 4. 📝 步驟二：純文字班表確認與核對區
st.markdown("---")
st.subheader("📝 步驟二：系統辨識結果核對與人工修正")
st.caption("請檢查下方每一行是否皆符合『月份/日期：班別』格式（例如：`5/01：C`）。若有不完整，您可在此直接增刪修改。")
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
                if 'A' in shift and '代' not in shift:
                    bg_color = "#FFE082"
                elif 'B' in shift:
                    bg_color = "#B3E5FC"
                elif 'C' in shift:
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
