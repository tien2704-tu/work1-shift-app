# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import re
import calendar
import cv2
import numpy as np
from PIL import Image

# 延遲載入 easyocr 以優化網頁載入速度
@st.cache_resource
def load_ocr_reader():
    import easyocr
    # 設定支援繁體中文 (ch_tra) 與英文 (en)
    return easyocr.Reader(['ch_tra', 'en'], gpu=False)

# 1. 網頁基礎設定
st.set_page_config(page_title="技術處化驗科排班看板", page_icon="🧪", layout="centered")

st.title("🧪 技術處化驗科 ─ 個人排班月行事曆")
st.write("您可以透過【上傳檔案】或【手機現場拍照】導入最新班表，系統將自動進行光學辨識 (OCR)。")

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
        st.image(uploaded_file, caption="已成功上傳的班表照片", use_container_width=True)

with camera_tab:
    camera_file = st.camera_input("請對準紙本班表進行拍照：")
    if camera_file:
        img_file = camera_file

# 初始化辨識出來的文字
extracted_text = ""

# 當有圖片輸入時，啟動真實 OCR 辨識
if img_file is not None:
    with st.spinner("🔍 系統正在極速辨識圖檔中的排班文字，請稍候..."):
        try:
            # 將上傳的檔案轉換為 OpenCV 影像格式
            file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
            opencv_image = cv2.imdecode(file_bytes, 1)
            
            # 讀取 OCR 模型
            reader = load_ocr_reader()
            
            # 進行文字識別
            ocr_results = reader.readtext(opencv_image)
            
            # 整理辨識出來的每行文字
            lines_dict = {}
            for (bbox, text, prob) in ocr_results:
                if prob > 0.2:  # 過濾掉信心度過低的雜訊
                    # 使用 y 座標進行基礎的分行排序
                    y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                    # 容許上下 15 像素內的文字視為同一行
                    matched_row = None
                    for r_y in lines_dict.keys():
                        if abs(r_y - y_center) < 15:
                            matched_row = r_y
                            break
                    if matched_row is not None:
                        lines_dict[matched_row].append((bbox[0][0], text))
                    else:
                        lines_dict[y_center] = [(bbox[0][0], text)]
            
            # 根據座標從上到下、從左到右重組文字
            sorted_lines = []
            for r_y in sorted(lines_dict.keys()):
                # 同一行內依照 x 座標從左到右排序
                sorted_words = sorted(lines_dict[r_y], key=lambda x: x[0])
                line_text = " ".join([w[1] for w in sorted_words])
                sorted_lines.append(line_text)
            
            extracted_text = "\n".join(sorted_lines)
            st.success("✨ 圖檔字元識別完成！請在下方檢查並修正內容。")
            
        except Exception as ocr_err:
            st.error(f"OCR 辨識模組初始化失敗，已自動切換回預設範本。錯誤訊息: {ocr_err}")
            # 防呆機制：若環境缺少套件，自動代入歷史預設範本
            extracted_text = """4/21：B\n4/22：O\n4/23：代A\n4/24：代A\n4/25：H\n4/26：B\n4/27：O\n4/28：H\n4/29：C\n4/30：C\n5/01：C\n5/02：C\n5/03：C\n5/04：O\n5/05：代A\n5/06：代公A\n5/07：代公A\n5/08：代公A\n5/09：A\n5/10：A\n5/11：H\n5/12：O\n5/13：代A\n5/14：C\n5/15：C\n5/16：C\n5/17：C\n5/18：S\n5/19：O\n5/20：O"""
else:
    extracted_text = "【請先在上方導入照片，或在此處直接貼入純文字班表】"

# 4. 📝 步驟二：純文字班表確認與核對區
st.subheader("📝 步驟二：系統辨識結果核對與人工修正")
st.info("💡 貼心提示：OCR 辨識率受照片清晰度影響。若格式有歪斜，請手動調整為「月份/日期：班別代號」（例如：`4/21：B`），下方的行事曆就會同步更新！")
user_input = st.text_area("OCR 提取出的原始純文字如下：", value=extracted_text, height=280)

# 5. 核心解析邏輯 (一格內上到下)
def parse_schedule(text):
    schedule_data = {}
    lines = text.strip().split('\n')
    current_year = 2026  # 年度設定
    
    for line in lines:
        # 相容多種格式：支援 4/21:B、4/21(二):B、4/21 B
        match = re.search(r'(\d+)/(\d+).*?[:：\s]\s*([A-Za-z0-9\u4e00-\u9fa5]+)', line)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            shift_type = match.group(3).strip()
            
            if month not in schedule_data:
                schedule_data[month] = {}
            schedule_data[month][day] = shift_type
            
    return schedule_data, current_year

# 6. HTML 繪圖與下載生成器
def generate_html_with_download(schedule_data, year):
    html_content = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    
    <div style="text-align: center; margin-bottom: 15px;">
        <button id="download-btn" style="background-color: #0071e3; color: white; border: none; padding: 10px 20px; font-size: 14px; font-weight: 600; border-radius: 8px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-family: sans-serif;">
            📥 點此匯出如同實體平板樣式的 PNG 圖檔
        </button>
    </div>

    <div id="calendar-card" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #ffffff; padding: 20px; border-radius: 16px; max-width: 480px; margin: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.05); box-sizing: border-box;">
        <div style="text-align: center; margin-bottom: 12px;">
            <h1 style="font-size: 16px; color: #1d1d1f; margin: 0; font-weight: 700;">遠東新世紀股份有限公司 觀音化學纖維廠</h1>
            <h2 style="font-size: 14px; color: #424245; margin: 4px 0 0 0; font-weight: 600;">遠東新世紀化驗科 ─ 個人排班月行事曆</h2>
        </div>
        
        <div style="background: #f5f5f7; border-radius: 8px; padding: 8px; font-size: 10px; color: #1d1d1f; display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px; margin-bottom: 12px; line-height: 1.4;">
            <div><span style="background:#ffe082; color:#7f6000; padding:1px 4px; border-radius:3px; font-weight:bold;">A</span> 早班 ({time_A})</div>
            <div><span style="background:#b3e5fc; color:#0277bd; padding:1px 4px; border-radius:3px; font-weight:bold;">B</span> 中班/小夜 ({time_B})</div>
            <div><span style="background:#c8e6c9; color:#2e7d32; padding:1px 4px; border-radius:3px; font-weight:bold;">C</span> 夜班/大夜 ({time_C})</div>
            <div><span style="background:#ffcc80; color:#b78103; padding:1px 4px; border-radius:3px; font-weight:bold;">加</span> 加班組合班別</div>
            <div style="grid-column: span 2;"><span style="background:#e0e0e0; color:#616161; padding:1px 4px; border-radius:3px; font-weight:bold;">休</span> H / O / S / 代A、B、C (均為休假)</div>
        </div>
    """
    
    for month in sorted(schedule_data.keys()):
        html_content += f"<div style='font-size: 12px; font-weight: bold; background: #e8e8ed; padding: 4px 8px; border-radius: 4px; margin: 12px 0 4px 0; color:#1d1d1f;'>{year}年 {month:02d}月</div>"
        html_content += "<div style='display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; text-align: center;'>"
        
        for wk in ['日', '一', '二', '三', '四', '五', '六']:
            html_content += f"<div style='font-size: 11px; font-weight: 600; color: #86868b; padding-bottom: 2px;'>{wk}</div>"
            
        days_in_month = sorted(schedule_data[month].keys())
        if not days_in_month:
            continue
            
        first_day_date = datetime.date(year, month, 1)
        python_wk = first_day_date.weekday()
        blank_cells = (python_wk + 1) % 7
        
        for _ in range(blank_cells):
            html_content += "<div style='background: transparent;'></div>"
            
        total_days = calendar.monthrange(year, month)[1]
        for day in range(1, total_days + 1):
            if day in schedule_data[month]:
                shift = schedule_data[month][day]
                
                # 色彩與規則識別邏輯
                if shift == 'A':
                    bg_color, text_color, label, subtitle = "#ffe082", "#7f6000", "A", "早班"
                elif shift in ['AH', 'AO', 'AS']:
                    bg_color, text_color, label, subtitle = "#fff59d", "#b78103", shift, "早加班"
                elif shift == 'B':
                    bg_color, text_color, label, subtitle = "#b3e5fc", "#0277bd", "B", "中班"
                elif shift in ['BH', 'BO', 'BS']:
                    bg_color, text_color, label, subtitle = "#81d4fa", "#01579b", shift, "中加班"
                elif shift == 'C':
                    bg_color, text_color, label, subtitle = "#c8e6c9", "#2e7d32", "C", "夜班"
                elif shift in ['CH', 'CO', 'CS']:
                    bg_color, text_color, label, subtitle = "#a5d6a7", "#1b5e20", shift, "夜加班"
                elif '公' in shift:
                    bg_color, text_color, label, subtitle = "#ffe082", "#7f6000", shift, "急救初訓"
                elif shift in ['H', 'O', 'S'] or shift in ['代A', '代B', '代C']:
                    bg_color, text_color, label, subtitle = "#e0e0e0", "#616161", shift, "休假"
                else:
                    bg_color, text_color, label, subtitle = "#eeeeee", "#9e9e9e", shift, "外班"
                    
                html_content += f"""
                <div style="background: #f5f5f7; border-radius: 6px; padding: 4px 2px; min-height: 44px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
                    <div style="font-size: 10px; font-weight: 600; color: #1d1d1f; text-align: left; padding-left: 3px;">{day}</div>
                    <div style="background: {bg_color}; color: {text_color}; font-size: 9px; font-weight: bold; padding: 1px 0; border-radius: 4px; margin: 1px 2px;">
                        {label}
                        <span style="font-size: 7px; color: rgba(0,0,0,0.5); display: block; font-weight: normal;">{subtitle}</span>
                    </div>
                </div>
                """
            else:
                html_content += f"""
                <div style="background: #fafafa; border-radius: 6px; padding: 4px 2px; min-height: 44px; display: flex; flex-direction: column; justify-content: flex-start; box-sizing: border-box; opacity: 0.4;">
                    <div style="font-size: 10px; font-weight: 500; color: #86868b; text-align: left; padding-left: 3px;">{day}</div>
                </div>
                """
        html_content += "</div>"
    html_content += "</div>"
    
    html_content += """
    <script>
    document.getElementById('download-btn').addEventListener('click', function() {
        const element = document.getElementById('calendar-card');
        html2canvas(element, {
            scale: 2,
            backgroundColor: "#ffffff",
            useCORS: true
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = '2026個人排班行事曆.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    });
    </script>
    """
    return html_content

# 7. 📸 步驟三：即時網格生成與確認
if user_input and user_input != "【請先在上方導入照片，或在此處直接貼入純文字班表】":
    try:
        parsed_data, year_val = parse_schedule(user_input)
        final_html = generate_html_with_download(parsed_data, year_val)
        
        st.subheader("🖼️ 步驟三：美化行事曆預覽與下載")
        st.components.v1.html(final_html, height=720, scrolling=False)
        
    except Exception as e:
        st.error(f"解析發生錯誤: {e}")
