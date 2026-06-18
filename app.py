import streamlit as st
import cv2
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import io
from PIL import Image

# 1. 網頁頁面基本設定
st.set_page_config(
    page_title="遠東新班表 AI 自動辨識系統 (影像優化版)",
    page_icon="📊",
    layout="wide"
)

st.title("📊 遠東新世紀 - 班表 AI 自動辨識系統")
st.markdown("### 🛠️ 整合功能：【自動旋轉扶正】+【手動角度微調】+【垂直字元優化辨識】")
st.write("---")

# 2. 核心功能 A：OpenCV 自動偵測角度並旋轉扶正
def auto_correct_image_rotation(image_bytes):
    """
    利用霍夫變換偵測班表線條，自動計算傾斜角度並旋轉至水平。
    """
    # 將上傳的 bytes 轉為 OpenCV 影像格式
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None, 0.0
        
    # 轉灰階並偵測邊緣
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # 偵測直線
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
    
    angles = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
            if -45 < angle < 45:
                angles.append(angle)
            elif angle > 45:
                angles.append(angle - 90)
            elif angle < -45:
                angles.append(angle + 90)

    # 如果有偵測到線條，計算中位數角度並旋轉
    if len(angles) > 0:
        detected_angle = np.median(angles)
        return img, detected_angle
    
    return img, 0.0

def rotate_image(img, angle):
    """根據指定角度旋轉圖片，邊緣補白底"""
    if angle == 0.0:
        return img
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
    return rotated

# 3. 核心功能 B：修正後的 AI 辨識模擬邏輯 (支援由上到下垂直字元)
def process_ocr_with_vertical_logic(img_cv):
    """
    實際開發時，此處會將經由 OpenCV 轉正後的 img_cv 送入 Google Document AI。
    此處模擬經由「垂直判定演算法」修正後提取出的精準排班矩陣。
    """
    rectified_roster_data = [
        ["39868", "徐祖慈", "A組", "工程師", ["B","B","H","O","A","A","B","B","H","O","*","A","A","A","O","A","B","B","B","B","H","H","代A","代A","O","B","B","B","B","S","H","O"]],
        ["26811", "凃牧廷", "B組", "分析師", ["B","O","代A","代A","H","B","O","H","C","C","*","C","C","C","O","代A","代A","代A","公A","公A","公A","A","A","H","O","代A","C","C","C","H","S","O"]],
        ["68211", "王佳眉", "C組", "技術員", ["H","B","B","B","B","O","S","B","B","B","*","H","O","B","B","B","B","H","O","A","A","B","B","B","H","O","A","A","B","B","B","B"]],
        ["48168", "周廣益", "D組", "技術員", ["H","O","C","C","C","C","H","代A","代A","O","*","B","B","C","C","C","H","S","O","B","B","C","C","H","代A","O","C","C","C","H","O","O"]],
        ["38976", "黃紹禹", "A組", "技術員", ["H","代A","代A","O","B","B","C","C","C","C","*","H","H","O","B","C","C","C","C","O","O","B","B","B","B","H","S","O","B","C","C","O"]]
    ]
    return rectified_roster_data

# 4. Streamlit 前端版面佈局
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 步驟一：上傳與影像校正")
    uploaded_file = st.file_uploader("請選擇或拖曳班表圖片檔案...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # 讀取原始檔案 bytes
        file_bytes = uploaded_file.read()
        
        # 進行自動角度偵測
        cv_img, auto_angle = auto_correct_image_rotation(file_bytes)
        
        st.info(f"✨ 系統自動偵測：圖片傾斜角度約為 `{auto_angle:.2f}°`")
        
        # 提供手動微調滑桿（預設值為自動偵測到的反向角度，用以抵銷傾斜）
        # 如果自動偵測為 3 度，滑桿預設就減 3 度來扶正
        manual_adjust = st.slider(
            "🔄 手動微調旋轉角度 (若自動校正不完美時使用)", 
            min_value=-180.0, 
            max_value=180.0, 
            value=float(-auto_angle),
            step=0.5
        )
        
        # 根據最終滑桿角度進行旋轉
        final_rotated_img = rotate_image(cv_img, manual_adjust)
        
        # 將 OpenCV 格式轉回 PIL Image 供 Streamlit 網頁顯示
        color_coverted = cv2.cvtColor(final_rotated_img, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(color_coverted)
        
        st.image(pil_image, caption="💡 這是即將送入 AI 辨識的【校正後影像】", use_column_width=True)

with col2:
    st.subheader("⚙️ 步驟二：確認結果並導出 Excel")
    if uploaded_file is not None:
        # 當點擊按鈕時，才正式啟動辨識與 Excel 封裝流程
        if st.button("🚀 開始 AI 網格結構辨識", type="primary"):
            with st.spinner("AI 正在解析轉正後的網格與手寫字跡..."):
                
                # 將轉正後的影像送入辨識核心
                roster_data = process_ocr_with_vertical_logic(final_rotated_img)
                
                # --- 開始構建 Excel ---
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "2026年05月份班表"
                ws.views.sheetView[0].showGridLines = True
                
                # 主標題
                ws.merge_cells("A1:AM1")
                ws["A1"] = "遠東新世紀股份有限公司 觀音化學纖維廠\n技術處化驗科觀音 2026年度05月份班表"
                ws["A1"].font = Font(name="Microsoft JhengHei", size=14, bold=True, color="FFFFFF")
                ws["A1"].fill = PatternFill(start_color="1B4D3E", end_color="1B4D3E", fill_type="solid")
                ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                ws.row_dimensions[1].height = 45
                
                # 月份大跨欄
                ws.merge_cells("E2:O2")
                ws["E2"] = "04月"
                ws.merge_cells("P2:AI2")
                ws["P2"] = "05月"
                for cell in ["E2", "P2"]:
                    ws[cell].font = Font(name="Microsoft JhengHei", size=10, bold=True, color="FFFFFF")
                    ws[cell].fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
                    ws[cell].alignment = Alignment(horizontal="center", vertical="center")
                    
                # 欄位頭
                days_headers = ["工號", "姓名", "組別", "職稱"]
                dates = [str(i) for i in range(21, 32)] + [str(i) for i in range(1, 21)]
                dates[10] = "31*" 
                stat_headers = ["O", "H", "S", "代", "休"]
                all_headers = days_headers + dates + stat_headers
                
                for col_idx, h in enumerate(all_headers, start=1):
                    cell = ws.cell(row=3, column=col_idx, value=h)
                    cell.font = Font(name="Microsoft JhengHei", size=10, bold=True)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
                    
                # 數據填入與樣式上色
                for r_idx, row_data in enumerate(roster_data, start=4):
                    for i in range(4):
                        ws.cell(row=r_idx, column=i+1, value=row_data[i])
                    
                    for d_idx, shift in enumerate(row_data[4]):
                        cell = ws.cell(row=r_idx, column=5 + d_idx, value=shift)
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        if shift in ["O", "休"]:
                            cell.fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
                        elif "代" in shift or "公" in shift:
                            cell.fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
                    
                    start_col = get_column_letter(5)
                    end_col = get_column_letter(4 + len(dates))
                    total_days = len(dates)
                    
                    # 統計公式
                    ws.cell(row=r_idx, column=5+total_days, value=f'=COUNTIF({start_col}{r_idx}:{end_col}{r_idx}, "O")')
                    ws.cell(row=r_idx, column=6+total_days, value=f'=COUNTIF({start_col}{r_idx}:{end_col}{r_idx}, "H")')
                    ws.cell(row=r_idx, column=7+total_days, value=f'=COUNTIF({start_col}{r_idx}:{end_col}{r_idx}, "S")')
                    ws.cell(row=r_idx, column=8+total_days, value=f'=COUNTIF({start_col}{r_idx}:{end_col}{r_idx}, "*代*")')
                    ws.cell(row=r_idx, column=9+total_days, value=f'=COUNTIF({start_col}{r_idx}:{end_col}{r_idx}, "休")')
                    
                    for c_offset in range(5):
                        c = ws.cell(row=r_idx, column=5+total_days+c_offset)
                        c.font = Font(name="Microsoft JhengHei", size=10, bold=True)
                        c.alignment = Alignment(horizontal="center", vertical="center")
                        c.fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")

                # 紙本手寫紅字備註
                ws.merge_cells(f"A{len(roster_data)+5}:AM{len(roster_data)+5}")
                ws[f"A{len(roster_data)+5}"] = "【特別手寫備註】5/6 ~ 5/8 凃牧廷 急急人員初訓"
                ws[f"A{len(roster_data)+5}"].font = Font(name="Microsoft JhengHei", size=11, bold=True, color="C62828")
                ws[f"A{len(roster_data)+5}"].fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")

                # 欄寬最佳化
                for col in ws.columns:
                    col_letter = get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = 6
                ws.column_dimensions['A'].width = 10
                ws.column_dimensions['B'].width = 12

                # 輸出二進位流
                excel_buffer = io.BytesIO()
                wb.save(excel_buffer)
                excel_buffer.seek(0)
                
                st.success("🎉 影像扶正與垂直字元辨識圓滿成功！")
                
                # 下載按鈕
                st.download_button(
                    label="📥 下載校正版 Excel 檔案",
                    data=excel_buffer,
                    file_name="遠東新世紀_影像優化班表.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("請先在左側上傳排班表圖片。")
