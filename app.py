# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import re
import calendar
from PIL import Image, ImageDraw, ImageFont
import io
import urllib.request

# 1. 網頁基礎設定
st.set_page_config(page_title="技術處化驗科排班看板", page_icon="🧪", layout="centered")

st.title("🧪 技術處化驗科 ─ 個人排班月行事曆")
st.write("因為大班表結構（人名在最左邊）不適合 OCR 橫向掃描，本版本已全面升級為【100% 精準的鋼體輸入模式】，保證絕不漏天、絕不重複！")

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

# 2. 側邊欄：時間配置與週期起點
st.sidebar.header("⚙️ 班別與週期配置")
time_A = st.sidebar.text_input("早班 (A)", "08:00 - 16:00")
time_B = st.sidebar.text_input("中班 / 小夜班 (B)", "16:00 - 24:00")
time_C = st.sidebar.text_input("夜班 / 大夜班 (C)", "00:00 - 08:00")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 排班週期起點月份")
target_base_month = st.sidebar.slider("請手動指定上個月是幾月：", min_value=1, max_value=12, value=4, step=1)
next_m = target_base_month + 1 if target_base_month < 12 else 1

# 計算上個月月底有幾天
current_year = 2026
last_month_total_days = calendar.monthrange(current_year, target_base_month)[1]

st.sidebar.caption(f"🎯 當前鎖定區間：\n{target_base_month}月21日至{target_base_month}月{last_month_total_days}日\n{next_m}月1日至{next_m}月20日")


# 3. 📝 步驟一：一鍵產生並核對排班
st.subheader("📝 步驟一：填入您的班表代碼")
st.markdown("下方已為您自動配對好 **21日至月底** 以及 **下月1日至20日** 的所有日期。您只需要直接修改對應日期的代碼即可：")

# 建立所有合法的最新班別代碼清單供使用者參考
st.info("💡 可用班表代碼：A (早班) | B (中/小夜) | C (夜/大夜) | H/O/S/代A/代B/代C (休假) | AH/AO/AS/BH/BO/BS/CH/CO/CS (加班)")

# 自動生成預設文字流
lines_demo = []
# 21日到月底
for d in range(21, last_month_total_days + 1):
    lines_demo.append(f"{target_base_month}/{d}：O")
# 1日到20日
for d in range(1, 21):
    lines_demo.append(f"{next_m}/{d:02d}：O")
default_text = "\n".join(lines_demo)

# 文字輸入框，使用者可以直接在這邊快速修改代碼（不需管圖片辨識錯誤）
user_input = st.text_area("✍️ 請在此修改或貼上您的排班內容 (格式：月/日：代碼)", value=default_text, height=350)

# 確認按鈕
col_btn1, col_btn2 = st.columns([2, 1])
with col_btn1:
    if st.button("👉 確認班表內容無誤，生成視覺行事曆看板", type="primary"):
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


# 4. 🎨 核心：高質感跨月型行事曆畫布繪製器
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
    
    # 看板色彩圖例說明區
    draw.rectangle([(35, 90), (585, 155)], fill="#F5F5F7")
    draw.text((45, 96), "☀️ A/早班加班: 黃/橘 | ⛅ B/中班加班: 藍/靛 | 🌙 C/夜班加班: 綠/深綠", fill="#1D1D1F", font=font_text)
    draw.text((45, 115), "🏖️ H、O、S、代A、代B、代C : 皆歸屬 [休假/放假] (灰色)", fill="#1D1D1F", font=font_text)
    draw.text((45, 134), f"時間配置: 早班:{time_A} | 中班:{time_B} | 夜班:{time_C}", fill="#424245", font=font_text)

    y_offset = 175
    
    # 按照設定的月份先後順序繪製
    for month in sorted(schedule_data.keys()):
        draw.rectangle([(35, y_offset), (585, y_offset + 25)], fill="#E8E8ED")
        
        # 區分上半部與下半部區間的標題
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
            
            # 嚴格控制只渲染指定的跨月精準日期
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
                    
                    # 化驗科專用精準色彩分配邏輯
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
                    elif s_upper in ["H", "O", "S", "代A", "代B", "代C"]: # 全系列休假（灰色）
                        bg_color = "#E0E0E0"
                    else:
                        bg_color = "#ECEFF1"
                        
                    draw.rectangle([(box_x1 + 4, box_y1 + 20), (box_x2 - 4, box_y2 - 4)], fill=bg_color)
                    draw.text((box_x1 + 6, box_y1 + 26), shift, fill="#1D1D1F", font=font_shift)
            current_cell += 1
            
        rows_count = (current_cell - 1) // 7 + 1
        y_offset += rows_count * 60 + 12
    return img


# 5. 🔓 步驟二：行事曆看板生成與圖檔下載
if st.session_state.step2_confirmed:
    if user_input.strip():
        try:
            parsed_data, year_val = parse_schedule(user_input)
            if parsed_data:
                st.markdown("---")
                st.subheader("🖼️ 步驟二：行事曆生成與圖檔下載")
                
                generated_img = draw_calendar_image(parsed_data, year_val)
                img_buffer = io.BytesIO()
                generated_img.save(img_buffer, format="PNG")
                img_bytes = img_buffer.getvalue()
                
                st.image(img_bytes, caption=f"已成功建立 {target_base_month}月21日至下月20日 的鋼體排班畫布", use_container_width=True)
                st.download_button(
                    label="📥 點此下載排班月行事曆 PNG 圖檔",
                    data=img_bytes,
                    file_name=f"技術處化驗科排班行事曆_{target_base_month}月21日至下月20日.png",
                    mime="image/png"
                )
            else:
                st.error("輸入內容解析失敗，請確認格式。")
        except Exception as e:
            st.error(f"畫布繪製失敗: {e}")
    else:
        st.warning("請先填入您的排班資料。")
