import streamlit as st
import os
from PIL import Image
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
import pandas as pd
import json

# 引入繪圖與時間處理套件
import matplotlib.pyplot as plt
import calendar
from datetime import datetime
from io import BytesIO

# ==================== 1. 定義資料結構 (JSON Schema) ====================
class DailySchedule(BaseModel):
    date: str = Field(description="日期，格式必須為 'MM/DD'，例如 '04/21' 或 '05/10'")
    shift: str = Field(description="班別代號，例如 B, C, O, 代A, H, 公A")

class EmployeeSchedule(BaseModel):
    name: str = Field(description="員工姓名")
    emp_id: str = Field(description="工號")
    group: str = Field(description="組別")
    schedules: List[DailySchedule] = Field(description="每日班表清單")

class RosterExtraction(BaseModel):
    company: str = Field(description="公司與廠區名稱")
    month: str = Field(description="班表月份主要月份，例如 '2026年度05月份'")
    extracted_data: List[EmployeeSchedule] = Field(description="所有員工班表資料")


# ==================== 2. 核心功能：繪製月行事曆照片 ====================
def generate_calendar_image(year, month, target_name, schedule_dict):
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif'] 
    plt.rcParams['axes.unicode_minus'] = False

    cal = calendar.monthcalendar(year, month)
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    ax.axis('off')
    
    # 標題
    ax.set_title(f"{year} / {str(month).zfill(2)} - {target_name}'s Schedule", fontsize=18, weight='bold', pad=20)

    # 畫星期欄位標頭
    weeks = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for i, w in enumerate(weeks):
        ax.text(i + 0.5, len(cal) + 0.5, w, ha='center', va='center', fontsize=12, weight='bold', 
                bbox=dict(boxstyle='square', facecolor='#e0e0e0', edgecolor='none'))

    # 填入日期與班表
    for r, week in enumerate(cal):
        for c, day in enumerate(week):
            y_pos = len(cal) - r - 0.5
            x_pos = c + 0.5
            
            rect = plt.Rectangle((c, len(cal) - r - 1), 1, 1, fill=False, edgecolor='#cccccc', linewidth=1)
            ax.add_patch(rect)
            
            if day != 0:
                ax.text(c + 0.85, y_pos + 0.35, str(day), ha='center', va='center', fontsize=10, color='#666666')
                
                date_str = f"{str(month).zfill(2)}/{str(day).zfill(2)}"
                if date_str in schedule_dict:
                    shift_text = schedule_dict[date_str]
                    
                    color_map = {
                        'H': '#ffcccc', 'O': '#f0f0f0', 'B': '#ccffcc', 
                        'C': '#ffe5cc', '代A': '#cce5ff', '公A': '#e5ccff', 'A': '#ffffcc'
                    }
                    face_color = color_map.get(shift_text, '#ffffff')
                    
                    box = plt.Rectangle((c+0.05, len(cal) - r - 0.9), 0.9, 0.6, fill=True, facecolor=face_color, edgecolor='none', alpha=0.7)
                    ax.add_patch(box)
                    ax.text(x_pos, y_pos - 0.1, shift_text, ha='center', va='center', fontsize=14, weight='bold')

    ax.set_xlim(0, 7)
    ax.set_ylim(0, len(cal) + 1)
    
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    img_buf.seek(0)
    plt.close()
    return img_buf


# ==================== 3. Streamlit 網頁介面 ====================
st.set_page_config(page_title="AI 班表行事曆生成器", layout="wide")

st.title("📊 智慧班表照片 ➡️ 月行事曆照片生成系統")
st.subheader("功能：1. 智慧照片辨識 | 2. 彙整成月曆照片並提供下載")

# 後台自動獲取 Key（優先從 Secrets 抓，找不到再抓系統環境變數）
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

# 功能一：上傳照片辨識
st.markdown("### 📥 功能一：上傳班表照片")
uploaded_file = st.file_uploader("請上傳您的班表照片 (JPG 或 PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file:
    if not api_key:
        st.error("❌ 系統未偵測到 API Key。請至 Streamlit Secrets 後台設定 `GEMINI_API_KEY`。")
    else:
        image = Image.open(uploaded_file)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(image, caption="您上傳的班表原圖", use_container_width=True)
            
        with col2:
            st.write("⏳ AI 正在深度解讀班表格子與手寫字，請稍候...")
            
            try:
                # 這裡直接調用後台設定好的 Key
                client = genai.Client(api_key=api_key)
                
                prompt = """
                你是一個專業的工廠班表數據提取專家。請仔細分析這張班表圖片：
                1. 識別月份與公司標頭（例如 2026年度05月份）。
                2. 對齊橫軸日期（4/21~4/30 欄位與 5/1~5/20 欄位）與縱軸員工。
                3. 日期格式請務必統一整理轉換為 'MM/DD'（例如 4月21日請寫 '04/21'，5月5日請寫 '05/05'）。
                4. 優先識別藍色原子筆手寫的假別異動（例如 公A、代A）。
                5. 完全依照 JSON Schema 格式輸出。
                """
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RosterExtraction,
                        temperature=0.1,
                    ),
                )
                
                result_json = json.loads(response.text)
                st.success(f"✅ 辨識成功！廠區：{result_json['company']} ({result_json['month']})")
                
                employee_names = [emp['name'] for emp in result_json['extracted_data']]
                
                # 功能二：選擇員工並彙整成月行事曆照片
                st.markdown("---")
                st.markdown("### 📅 功能二：彙整個人月行事曆照片")
                
                selected_emp = st.selectbox("請選擇您的名字以生成專屬月曆：", employee_names)
                
                emp_data = next(emp for emp in result_json['extracted_data'] if emp['name'] == selected_emp)
                schedule_dict = {day['date']: day['shift'] for day in emp_data['schedules']}
                
                target_month = st.radio("請選擇欲生成的月份行事曆照片：", [4, 5], horizontal=True)
                
                with st.spinner("正在為您繪製月曆照片..."):
                    calendar_img_buf = generate_calendar_image(2026, target_month, selected_emp, schedule_dict)
                    
                st.image(calendar_img_buf, caption=f"{selected_emp} - 2026年{target_month}月 行事曆預覽", use_container_width=True)
                
                st.download_button(
                    label=f"🖼️ 下載 {selected_emp} 的 {target_month}月份行事曆照片 (PNG)",
                    data=calendar_img_buf,
                    file_name=f"{selected_emp}_2026_{target_month}M_Schedule.png",
                    mime="image/png"
                )
                
            except Exception as e:
                st.error(f"系統發生異常：{str(e)}")
