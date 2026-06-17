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
st.write("您可以透過【上傳檔案】導入最新班表，系統將自動依據「一格內上到下」邏輯定位辨識跨月班表，並產出可下載的行事曆圖檔。")

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
# 讓使用者主動手動鎖定月份，徹底解決 OCR 亂跳月份的問題
target_base_month = st.sidebar.slider("請手動指定上個月是幾月：", min_value=1, max_value=12, value=4, step=1)
st.sidebar.caption(f"🎯 系統目前已鎖定週期：\n{target_base_month}月21日至月底 加上 {target_base_month+1 if target_base_month<12 else 1}月1日至20日")

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


# 🎯 核心辨識邏輯：導入手動控制起點與一格內縱向解算
def robust_extract_schedule(_img_np, base_m):
    try:
        import pytesseract
        
        # 1. 影像極致預處理
        gray = cv2.cvtColor(_img_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)
        gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 5)
        
        # 2. 多重 OCR 引擎融合 (PSM 11 專攻結構散落字元)
        pil_img = Image.fromarray(thresh)
        raw_text_6 = pytesseract.image_to_string(pil_img, lang='chi_tra+eng', config=r'--psm 6')
        raw_text_11 = pytesseract.image_to_string(pil_img, lang='chi_tra+eng', config=r'--psm 11')
        
        full_blob = raw_text_6 + "\n" + raw_text_11
        full_blob = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', full_blob)
        
        # 所有合法班別代碼
        valid_shifts = [
            "AH", "AO", "AS", "BH", "BO", "BS", "CH", "CO", "CS",
            "代A", "代B", "代C", "A", "B", "C", "H", "O", "S"
        ]

        # 3. 縱向 Tokens 網格清洗與「鐵律分水嶺」演算法
        tokens = full_blob.split()
        extracted_data = []
        pending_day = None
        
        next_m = base_m + 1 if base_m < 12 else 1
        
        for t in tokens:
            t = t.strip().upper()
            
            # 若包含斜線格式，取出日期數字
            md_match = re.search(r'([0-9]{1,2})[/\-_]([0-9]{1,2})', t)
            if md_match:
                d_val = int(md_match.group(2))
                if 1 <= d_val <= 31:
                    pending_day = d_val
                continue
            
            # 純數字判定
            if t.isdigit():
                val = int(t)
                if 1 <= val <= 31 and val not in [2026, 8, 16, 24]:
                    pending_day = val
                continue
            
            # 格內由上到下匹配代碼
            matched_shift = None
            for vs in valid_shifts:
                if vs == t or vs in t:
                    matched_shift = vs
                    break
            
            # 💡 鐵律分配邏輯：依據 21 號完美歸入跨月區間
            if pending_day and matched_shift:
                if pending_day >= 21:
                    # 21至月底：強制歸屬在手選的 base_m (上個月)
                    extracted_data.append((base_m, pending_day, matched_shift))
                elif pending_day <= 20:
                    # 1至20號：強制歸屬在 next_m (下個月)
                    extracted_data.append((next_m, pending_day, matched_shift))
                pending_day = None # 釋放狀態
                
        # 移除重複並按日期順序嚴格排序
        unique_data = list(set(extracted_data))
        unique_data.sort(key=lambda x: (x[0], x[1]))
        
        matched_lines = []
        for m, d, s in unique_data:
            matched_lines.append(f"{m}/{d:02d}：{s}")
            
        if matched_lines:
            return "\n".join(matched_lines)
        return ""
    except Exception as e:
        err_msg = str(e)
        if "tesseract is not installed" in err_msg.lower() or "path" in err_msg.lower():
            return "ERR_TESSERACT_NOT_FOUND"
        return f"辨識核心異常: {err_msg}"

extracted_text = ""
if opencv_image is not None:
    with st.spinner(f"🎯 正在依據強制週期（{target_base_month}月21日至下月20日）進行格內縱向深度解算..."):
        ocr_extracted = robust_extract_schedule(opencv_image, target_base_month)
        if ocr_extracted == "ERR_TESSERACT_NOT_FOUND":
            st.error("❌ 系統偵測到伺服器尚未安裝 Tesseract OCR 主程式。請確認專案根目錄中已建立包含 'tesseract-ocr' 的 packages.txt 檔案並推送到 GitHub 重新部署。")
        elif ocr_extracted:
            extracted_text = ocr_extracted
            st.success("✨ 班表跨月內容處理完成！已精準定位指定之跨月區間。")
        else:
            extracted_text = ""
            st.warning("⚠️ 自動辨識未能完美捕捉所有格子。已為您清空核對欄，請直接參考下方格式手動修正或貼上。")
else:
    extracted_text = ""

# 4. 📝 步驟二：純文字班表確認與核對區
st.markdown("---")
st.subheader("📝 步驟二：系統辨識結果核對與人工修正")
st.caption(f"請檢查或手動補正排班文字。目前系統將精準繪製 {target_base_month}月21日至月底 與 下月1日至20日。")
user_input = st.text_area("排班原始文字核對欄：", value=extracted_text, height=280, placeholder="範例格式：\n4/21：B\n4/30：CH\n5/01：A\n5/14：代A\n5/20：O")

# 確認按鈕
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
            
            # 嚴格且完美地只繪製指定循環區間內的格子
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
                    
                    # 精準色彩代碼比對
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
                    elif s_upper in ["H", "O", "S", "代A", "代B", "代C"]: # 全系列休假
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
                
                st.image(img_bytes, caption=f"已成功產出指定的跨月（{target_base_month}月21日至下月20日）排班圖檔", use_container_width=True)
                st.download_button(
                    label="📥 點此下載排班月行事曆 PNG 圖檔",
                    data=img_bytes,
                    file_name=f"排班行事曆_{target_base_month}月21日至下月20日.png",
                    mime="image/png"
                )
            else:
                st.error("輸入內容無法解析，請確認是否有包含格式如 '4/21：B' 的字樣。")
        except Exception as e:
            st.error(f"行事曆生成失敗: {e}")
    else:
        st.warning("請先在步驟二的核對欄內確認或手動輸入您的排班資料。")
