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

# ==================== 1. 定義資料結構 ====================
class DailySchedule(BaseModel):
    date: str = Field(description="日期，格式必須為 'MM/DD'，例如 '04/21' 或 '05/10'")
    shift: str = Field(description="班別代號，例如 B, C, O, 代A, H")

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
    """
    根據指定的年份、月份與該員工的班表字典，畫出月曆並轉成 PNG 圖片位元組
    """
    # 設定 matplotlib 支援中文（Streamlit 雲端預設字型可能無中文，改用簡單粗體線條或防呆處理）
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial'] 
    plt.rcParams['axes.unicode_minus'] = False

    # 取得該月的天數與第一天是星期幾
    cal = calendar.monthcalendar(year, month)
    
    # 建立畫布
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    ax.axis('off')
    ax.set_title(f"{year}年 {month}月 - {target_name} 個任班表", fontsize=18, weight='bold', pad=20)

    # 畫星期欄位標頭
    weeks = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for i, w in enumerate(weeks):
        ax.text(i + 0.5, len(cal) + 0.5, w, ha='center', va='center', fontsize=12, weight='bold', bbox=dict(boxstyle='square', facecolor='#e0e0e0', edgecolor='none'))

    # 填入日期與班表
    for r, week in enumerate(cal):
        for c, day in enumerate(week):
            # 計算網格 Y 軸位置（由上往下）
            y_pos = len(cal) - r - 0.5
            x_pos = c + 0.5
            
            # 畫格子外框
            rect = plt.Rectangle((c, len(cal) - r - 1), 1, 1, fill=False, edgecolor='#cccccc', linewidth=1)
            ax.add_patch(rect)
            
            if day != 0:
                # 顯示日期數字（右上角）
                ax.text(c + 0.85, y_pos + 0.35, str(day), ha='center', va='center', fontsize=10, color='#666666')
                
                # 比對班表字典裡有沒有這天的班
                date_str = f"{str(month).zfill(2)}/{str(day).zfill(2)}"
                if date_str in schedule_dict:
                    shift_text = schedule_dict[date_str]
                    
                    # 根據班別給予不同顏色外觀
                    color_map = {
                        'H': '#ffcccc', 'O': '#f0f0f0', 'B': '#ccffcc', 
                        'C': '#ffe5cc', '代A': '#cce5ff', '公A': '#e5ccff'
                    }
                    face_color = color_map.get(shift_text, '#ffffff')
                    
                    # 在格子內畫出班別底色區塊與文字
                    box = plt.Rectangle((c+0.05, len(cal) - r - 0.9), 0.9, 0.6, fill=True, facecolor=face_color, edgecolor='none', alpha=0.7)
                    ax.add_patch(box)
                    ax.text(x_pos, y_pos - 0.1, shift_text, ha='center', va='center', fontsize=14, weight='bold')

    ax.set_xlim(0, 7)
    ax.set_ylim(0, len(cal) + 1)
    
    # 將圖片存入記憶體快取，不佔用實體硬碟空間
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    img_buf.seek(0)
    plt.close()
    return img_buf


# ==================== 3. Streamlit 網頁介面 ====================
st.set_page_config(page_title="AI 班表行事曆生成器", layout="wide")

st.title("📊 智慧班表照片 ➡️ 月行事曆照片生成系統")
st.subheader("功能：1. 智慧照片辨識 | 2. 彙整成月曆照片並提供下載")

# 側邊欄設定
st.sidebar.header("🔑 系統設定")
api_key = st.sidebar.text_input("請輸入您的 Gemini API Key", type="password")
st.sidebar.markdown("[👉 點此免費獲取 API Key](https://aistudio.google.com/)")

# 功能一：上傳照片辨識
st.markdown("### 📥 功能一：上傳班表照片")
uploaded_file = st.file_uploader("請上傳您的班表照片 (JPG 或 PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file and api_key:
    image = Image.open(uploaded_file)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(image, caption="您上傳的班表原圖", use_container_width=True)
        
    with col2:
        st.write("⏳ AI 正在深度解讀班表格子與手寫字，請稍候...")
        
        try:
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
            
            # --- 轉成 DataFrame 網頁檢視 ---
            employee_names = [emp['name'] for emp in result_json['extracted_data']]
            
            # 功能二：選擇員工並彙整成月行事曆照片
            st.markdown("---")
            st.markdown("### 📅 功能二：彙整個人月行事曆照片")
            
            selected_emp = st.selectbox("請選擇您的名字以生成專屬月曆：", employee_names)
            
            # 找到該員工的班表數據
            emp_data = next(emp for emp in result_json['extracted_data'] if emp['name'] == selected_emp)
            
            # 建立日曆比對字典 {"05/06": "公A", "05/07": "公A"}
            schedule_dict = {day['date']: day['shift'] for day in emp_data['schedules']}
            
            # 目前這張班表涵蓋 2026 年的 4 月與 5 月，讓使用者選擇要下載哪個月的行事曆照片
            target_month = st.radio("請選擇欲生成的月份行事曆照片：", [4, 5], horizontal=True)
            
            # 繪製並生成圖片快取
            with st.spinner("正在為您繪製月曆照片..."):
                calendar_img_buf = generate_calendar_image(2026, target_month, selected_emp, schedule_dict)
                
            # 在網頁上預覽產出的月曆照片
            st.image(calendar_img_buf, caption=f"{selected_emp} - 2026年{target_month}月 行事曆預覽", use_container_width=True)
            
            # 提供照片格式 (PNG) 下載按鈕
            st.download_button(
                label=f"🖼️ 下載 {selected_emp} 的 {target_month}月份行事曆照片 (PNG)",
                data=calendar_img_buf,
                file_name=f"{selected_emp}_2026_{target_month}月行事曆.png",
                mime="image/png"
            )
            
        except Exception as e:
            st.error(f"系統發生異常：{str(e)}")

elif not api_key:
    st.warning("👈 請先在左側邊欄輸入您的 Gemini API Key 才能開啟服務喔！")
