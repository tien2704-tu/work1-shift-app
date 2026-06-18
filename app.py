import streamlit as st
import numpy as np
import pandas as pd
import re
import calendar
from datetime import datetime
import easyocr
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io

# 1. 設定 Streamlit 頁面網頁標題與佈局
st.set_page_config(
    page_title="Excel 班表轉月行事曆工具", 
    page_icon="📅",
    layout="centered"
)

# 2. 設定繪圖字體（解決雲端 Linux 伺服器中文變豆腐方塊的問題）
import matplotlib as mpl
# 優先載入中文字體，若伺服器無此字體，會自動映射至標準無襯線字體
mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS', 'Microsoft JhengHei', 'SimHei'] 
mpl.rcParams['axes.unicode_minus'] = False

# -------------------------------------------------------------------------
# 核心快取：避免網頁每次操作都重新載入 OCR 模型（可大幅提升運行速度）
# -------------------------------------------------------------------------
@st.cache_resource
def load_ocr_reader():
    # 支援繁體中文 (ch_tra) 與英文 (en)
    return easyocr.Reader(['ch_tra', 'en'])

reader = load_ocr_reader()

# -------------------------------------------------------------------------
# 邏輯一：圖片文字辨識與班表結構化
# -------------------------------------------------------------------------
def parse_schedule_image(image_bytes):
    # 將上傳的檔案流轉為圖像矩陣
    image = Image.open(io.BytesIO(image_bytes))
    img_array = np.array(image)
    
    # 執行辨識
    result = reader.readtext(img_array)
    detected_texts = [res[1] for res in result]
    all_text = " ".join(detected_texts)
    
    # 預設目前的年份與月份
    year = datetime.now().year
    month = datetime.now().month
    
    # 嘗試用正規表示法自動抓取圖片中的「年/月」
    month_match = re.search(r'(\d{4})[年/-](\d{1,2})', all_text)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
    else:
        single_month = re.search(r'(\d{1,2})\s*月', all_text)
        if single_month:
            month = int(single_month.group(1))
            
    schedule_dict = {}
    # 設定常見的排班關鍵字
    shift_keywords = ['常日', '常', '小夜', '夜', '大夜', '休', 'W', 'N', 'D', 'O']
    current_date = None
    
    # 簡單線性配對邏輯：抓到日期(1~31)後，若下一個字串包含關鍵字，則進行綁定
    for text in detected_texts:
        text = text.strip()
        if text.isdigit() and 1 <= int(text) <= 31:
            current_date = int(text)
        elif current_date and any(kw in text for kw in shift_keywords):
            schedule_dict[current_date] = text
            current_date = None  # 配對成功，重置等待下一個日期
            
    # 保底機制：若 OCR 因截圖模糊未抓到任何資料，生成一組標準展示資料，避免畫面空白
    is_mock = False
    if not schedule_dict:
        is_mock = True
        for d in range(1, 32):
            if d % 7 in [6, 0]: schedule_dict[d] = "休"
            elif d % 3 == 0: schedule_dict[d] = "小夜"
            else: schedule_dict[d] = "常日"
            
    return year, month, schedule_dict, is_mock

# -------------------------------------------------------------------------
# 邏輯二：利用 Matplotlib 繪製精美月曆圖
# -------------------------------------------------------------------------
def generate_calendar_image(year, month, schedule_dict):
    # 計算該月第一天是星期幾(0=星期一)，以及該月總天數
    first_weekday, num_days = calendar.monthrange(year, month)
    first_weekday = (first_weekday + 1) % 7 # 修正為 0=星期日
    
    total_slots = first_weekday + num_days
    num_weeks = (total_slots + 6) // 7
    
    # 動態調整畫布高度，確保比例完美
    fig, ax = plt.subplots(figsize=(10, 2 + num_weeks * 1.5), dpi=150)
    ax.set_xlim(0, 7)
    ax.set_ylim(0, num_weeks + 1)
    ax.axis('off')
    
    # 視覺風格色彩定義
    bg_color = "#FAFAFA"
    header_color = "#3A4750"
    grid_border_color = "#E0E0E0"
    
    color_map = {
        "休": {"bg": "#EAEAEA", "text": "#888888"},
        "常日": {"bg": "#E8F4F8", "text": "#1E6B7B"},
        "小夜": {"bg": "#FFF4E0", "text": "#B27000"},
        "大夜": {"bg": "#F5EFFF", "text": "#623697"}
    }
    
    fig.patch.set_facecolor(bg_color)
    
    # 1. 繪製主標題
    ax.text(3.5, num_weeks + 0.6, f"{year} 年 {month} 月 行事曆班表", 
            fontsize=18, fontweight='bold', ha='center', va='center', color=header_color)
    
    # 2. 繪製星期欄位 (日 到 六)
    weekdays = ['日', '一', '二', '三', '四', '五', '六']
    for i, day in enumerate(weekdays):
        txt_color = "#D32F2F" if i in [0, 6] else "#333333"
        ax.text(i + 0.5, num_weeks + 0.1, day, fontsize=12, fontweight='bold', ha='center', va='center', color=txt_color)
        ax.plot([i, i+1], [num_weeks, num_weeks], color=header_color, linewidth=1.5)

    # 3. 依序填入日期格與班表內容
    day_counter = 1
    for week in range(num_weeks):
        row_idx = num_weeks - 1 - week  # 座標由下而上繪製
        for idx in range(7):
            # 判斷是否為邊界外的空白格子
            if (week == 0 and idx < first_weekday) or day_counter > num_days:
                rect = patches.Rectangle((idx, row_idx), 1, 1, linewidth=0.5, edgecolor=grid_border_color, facecolor='none')
                ax.add_patch(rect)
                continue
            
            shift = schedule_dict.get(day_counter, "")
            face_color = "#FFFFFF"
            text_color = "#222222"
            
            # 對應排班色彩
            for key, style in color_map.items():
                if key in shift:
                    face_color = style["bg"]
                    text_color = style["text"]
                    break
            
            # 週末加強著色 (若為休假或空值)
            if idx in [0, 6] and (shift == "" or "休" in shift):
                face_color = "#FFF0F0"
                if shift == "": shift = "休"
                text_color = "#C62828"

            # 畫方塊
            rect = patches.Rectangle((idx, row_idx), 1, 1, linewidth=0.8, edgecolor=grid_border_color, facecolor=face_color)
            ax.add_patch(rect)
            
            # 填入左上角日期
            ax.text(idx + 0.1, row_idx + 0.75, str(day_counter), fontsize=11, fontweight='bold', ha='left', va='center', color="#555555")
            
            # 填入中央班表代碼
            if shift:
                ax.text(idx + 0.5, row_idx + 0.35, shift, fontsize=13, fontweight='bold', ha='center', va='center', color=text_color)
            
            day_counter += 1

    plt.tight_layout()
    
    # 將圖片轉換為記憶體流 (BytesIO)，以便 Streamlit 直接讀取下載，不需儲存在伺服器硬碟
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    img_buf.seek(0)
    plt.close()
    return img_buf

# -------------------------------------------------------------------------
# 介面渲染 (Streamlit 網頁前端)
# -------------------------------------------------------------------------
st.title("📅 Excel 班表截圖轉月行事曆")
st.markdown("不用安裝任何程式！直接上傳您的 Excel 班表截圖，系統將自動分析文字並繪製成色彩清晰、方便閱讀的月曆圖檔。")

# 建立檔案上傳區塊
uploaded_file = st.file_uploader("請上傳班表圖片檔 (支援 PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # 呈現使用者上傳的原始圖片
    st.image(uploaded_file, caption="📸 您上傳的班表截圖", use_container_width=True)
    
    # 觸發辨識與生成的按鈕
    if st.button("🚀 開始自動辨識與轉換"):
        with st.spinner("雲端 AI 正在分析圖片並繪製月曆中，請稍候..."):
            file_bytes = uploaded_file.read()
            
            # 1. 執行 OCR 解析
            year, month, schedule, is_mock = parse_schedule_image(file_bytes)
            
            if is_mock:
                st.warning("⚠️ 系統未能完美辨識出班表排列，以下為您產出標準示範排班圖。您可以確認截圖是否清晰或欄位是否包含『常日、小夜、大夜、休』等關鍵字。")
            
            # 2. 產出月曆圖片流
            output_img_buf = generate_calendar_image(year, month, schedule)
            
            # 3. 網頁上渲染產出的月曆結果
            st.markdown("---")
            st.subheader("🎉 轉換成功！您的專屬月行事曆：")
            st.image(output_img_buf, caption=f"{year}年{month}月 個人作息圖", use_container_width=True)
            
            # 4. 提供一鍵下載按鈕
            st.download_button(
                label="💾 下載這張月曆圖片 (PNG)",
                data=output_img_buf,
                file_name=f"{year}年{month}月_個人行事曆.png",
                mime="image/png"
            )
