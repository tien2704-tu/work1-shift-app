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
st.write("透過上傳大班表照片，系統將嘗試抓取您的班別；若因【人名在最左邊】導致部分日期漏讀，您可在步驟二輕鬆補正。")

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

# 2. 側邊欄：設定班別與時間對照 + 強制月份選擇
st.sidebar.header("⚙️ 班別與週期配置")
time_A = st.sidebar.text_input("早班 (A)", "08:00 - 16:00")
time_B = st.sidebar.text_input("中班 / 小夜班 (B)", "16:00 - 24:00")
time_C = st.sidebar.text_input("夜班 / 大夜班 (C)", "00:00 - 08:00")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 排班週期起點月份")
target_base_month = st.sidebar.slider("請手動指定上個月是幾月：", min_value=1, max_value=12, value=4, step=1)
next_m = target_base_month + 1 if target_base_month < 12 else 1

current_year = 2026
last_month_total_days = calendar.monthrange(current_year, target_base_month)[1]
st.sidebar.caption(f"🎯 當前鎖定區間：\n{target_base_month}月21日至月底 加上 {next_m}月1日至20日")

# 3. 📸 照片上傳功能區
st.subheader("📸 步驟一：導入班表圖檔")
uploaded_file = st.file_uploader("請選擇班表照片 (PNG, JPG, JPEG)...", type=["png", "jpg", "jpeg"])

img_file = uploaded_file

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
            st.caption(f"目前已旋轉：{st.session_state.rotation_angle}°")

    if st.session_state.rotation_angle == 90:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_90_CLOCKWISE)
    elif st.session_state.rotation_angle == 180:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_180)
    elif st.session_state.rotation_angle == 270:
        opencv_image = cv2.rotate(opencv_image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    preview_rgb = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
    st.image(preview_rgb, caption=f"已調正之班表預覽 ({st.session_state.rotation_angle}°)", use_container_width=True)


# 🎯 核心辨識邏輯：專攻橫向人名結構去重演算法
def robust_extract_schedule(_img_np, base_m):
    try:
        import pytesseract
        
        # 影像去噪與二值化，降低大表格線條的干擾
        gray = cv2.cvtColor(_img_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 7)
        
        pil_img = Image.fromarray(thresh)
        raw_text = pytesseract.image_to_string(pil_img, lang='chi_tra+eng', config=r'--psm 6')
        
        valid_shifts = [
            "AH", "AO", "AS", "BH", "BO", "BS", "CH", "CO", "CS",
            "代A", "代B", "代C", "A", "B", "C", "H", "O", "S"
        ]

        tokens = raw_text.split()
        extracted_dict = {} # 利用字典特性：相同的 (月份, 日期) 只會保留一個，完美做到「去重」
        pending_day = None
        
        next_m_val = base_m + 1 if base_m < 12 else 1
        
        for t in tokens:
            t = t.strip().upper()
            
            # 日期特徵提取
            md_match = re.search(r'([0-9]{1,2})[/\-_]([0-9]{1,2})', t)
            if md_match:
                d_val = int(md_match.group(2))
                if 1 <= d_val <= 31:
                    pending_day = d_val
                continue
            
            if t.isdigit():
                val = int(t)
                if 1 <= val <= 31 and val not in [2026, 8, 16, 24]:
                    pending_day = val
                continue
            
            # 班別特徵提取
            matched_shift = None
            for vs in valid_shifts:
                if vs == t or vs in t:
                    matched_shift = vs
                    break
            
            if pending_day and matched_shift:
                if pending_day >= 21:
                    extracted_dict[(base_m, pending_day)] = matched_shift
                elif pending_day <= 20:
                    extracted_dict[(next_m_val, pending_day)] = matched_shift
                pending_day = None 
                
        return extracted_dict
    except Exception:
        return {}

# 執行辨識並取得資料字典
ocr_data_dict = {}
if opencv_image is not None:
    with st.spinner(f"🎯 正在對大班表進行橫向數據流清洗與防重複解析..."):
        ocr_data_dict = robust_extract_schedule(opencv_image, target_base_month)
        if ocr_data_dict:
            st.success("✨ 照片基本代碼抓取完畢！已為您自動匯入下方核對欄。")
        else:
            st.info("💡 已就緒，系統已自動為您鋪設完整的日期空白範本。")

# 4. 📝 步驟二：純文字班表確認與核對區 (自動補齊遺漏天數)
st.markdown("---")
st.subheader("📝 步驟二：辨識結果核對與人工修正")
st.markdown(f"**💡 提示：下方已為您自動按順序對齊 {target_base_month}/21 到 {next_m}/20 的所有天數。若照片有漏讀，您只需把 `O` 改成您的班別代碼即可，不需重新打字！**")

# 自動合併：不論 OCR 有沒有抓完整，都自動輸出一個「不漏天、不重複」的完整列表
merged_lines = []

# 上個月 21 日至月底
for d in range(21, last_month_total_days + 1):
    shift_val = ocr_data_dict.get((target_base_month, d), "O") # 沒抓到就預設為 O 方便您改
    merged_lines.append(f"{target_base_month}/{d:02d}：{shift_val}")

# 下個月 1 日至 20 日
for d in range(1, 21):
    shift_val = ocr_data_dict.get((next_m, d), "O")
    merged_lines.append(f"{next_m}/{d:02d}：{shift_val}")

final_placeholder_text = "\n".join(merged_lines)

user_input = st.text_area("排班原始文字核對欄 (格式：月/日：代碼)：", value=final_placeholder_text, height=350)

# 確認按鈕
col_btn1, col_btn2 = st.columns([2, 1])
with col_btn1:
    if st.button("👉 確認上方班表內容無誤，生成視覺行事曆看板", type="primary"):
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

# 5. 🎨 核心：高質感跨月型行事曆畫布繪製器
def draw_calendar_image(schedule_data, year):
    img = Image.new("RGB", (620, 960), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    if font_ttf_path:
        font_title = ImageFont.truetype(font_ttf_path, 18)
        font_subtitle = ImageFont.truetype(font_ttf_path, 14)
        font_text = ImageFont.truetype(font_ttf_path, 11)
        font_shift = ImageFont.truetype(font_ttf_path, 11)
    else:
        font_title = font_subtitle = font_text = font_shift = ImageFont.load_default()

    # 外框
    draw.rectangle([(15, 15), (605, 945)], outline="#E0E0E0", width=2)
    draw.text((35, 35), "遠東新世紀股份有限公司 觀音化學纖維廠", fill="#1D1D1F", font=font_title)
    draw.text((35, 60), "技術處化驗科 ─ 個人排班月行事曆 (21日 至 20日)", fill="#424245", font=font_subtitle)
    
    # 看板色彩圖例
    draw.rectangle([(35, 90), (585, 155)], fill="#F5F5F7")
    draw.text((45, 96), "☀️ A/早班加班: 黃/橘 | ⛅ B/中班加班: 藍/靛 | 🌙 C/夜班加班: 綠/深綠", fill="#1D1D1F", font=font_text)
    draw.text((45, 115), "🏖️ H、O、S、代A、代B、代C : 皆歸屬 [休假/放假] (灰色)", fill="#1D1D1F", font=font_text)
    draw.text((45, 134), f"時間配置: 早班:{time_A} | 中班:{time_B} | 夜班:{time_C}", fill="#424245", font=font_text)

    y_offset = 175
    
    for month in sorted(schedule_data.keys()):
        draw.rectangle([(35, y_offset), (585, y_offset + 25)], fill="#E8E8ED")
        
        has_late_days = any(d >= 21 for d in schedule_data[month].keys())
        range_str = " (21日 至 月底)" if has_late_days else " (01日 至 20日)"
            
        draw.text((45, y_offset + 4), f"{year}年 {month:02d}月{range_str}", fill="#1D1D1F", font=font_subtitle)
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
            
            should_draw = False
            if has_late_days and day >= 21:
                should_draw = True
            elif not has_late_days and day <= 20:
                should_draw = True
                
            if should_draw:
                draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill="#F5F5F7")
                draw.text((box_x1 + 5, box_y1 + 4), str(day), fill="#1D1D1F", font=font_text)
                
                if day in schedule_data[month]:
                    shift = schedule_data[month][day].strip()
                    s_upper = shift.upper()
                    
                    if s_upper in ["AH", "AO", "AS"]:    # 早班加班
                        bg_color = "#FFB74D" 
                    elif s_upper in ["BH", "BO", "BS"]:  # 中班加班
                        bg_color = "#4FC3F7"
                    elif s_upper in ["CH", "CO", "CS"]:  # 夜班加班
                        bg_color = "#81C784"
                    elif s_upper == 'A':                 # 標準早班
                        bg_color = "#FFF176"
                    elif s_upper == 'B':                 # 標準中班
                        bg_color = "#E1F5FE"
                    elif s_upper == 'C':                 # 標準夜班
                        bg_color = "#E8F5E9"
                    elif s_upper in ["H", "O", "S", "代A", "代B", "代C"]: # 休假
                        bg_color = "#E0E0E0"
                    else:
                        bg_color = "#ECEFF1"
                        
                    draw.rectangle([(box_x1 + 4, box_y1 + 20), (box_x2 - 4, box_y2 - 4)], fill=bg_color)
                    draw.text((box_x1 + 6, box_y1 + 26), shift, fill="#1D1D1F", font=font_shift)
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
                
                st.image(img_bytes, caption=f"已成功建立 {target_base_month}月21日至下月20日 的排班看板", use_container_width=True)
                st.download_button(
                    label="📥 點此下載排班月行事曆 PNG 圖檔",
                    data=img_bytes,
                    file_name=f"技術處化驗科排班行事曆_{target_base_month}月21日至下月20日.png",
                    mime="image/png"
                )
            else:
                st.error("輸入內容解析失敗。")
        except Exception as e:
            st.error(f"行事曆生成失敗: {e}")
