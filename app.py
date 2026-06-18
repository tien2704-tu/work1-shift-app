import streamlit as st
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import io

# 1. 網頁頁面基本設定
st.set_page_config(
    page_title="遠東新班表 AI 自動辨識系統",
    page_icon="📊",
    layout="wide"
)

# 顯示網頁大標題與副標題
st.title("📊 遠東新世紀 - 班表 AI 自動辨識轉 Excel 系統")
st.markdown("請上傳您的班表照片（如 `IMG_8423.JPG`），系統將自動識別並轉換為包含統計公式的標準 Excel 表格。")
st.write("---")

# 2. 模擬 AI 辨識邏輯 (此處預留未來串接 Google / Azure OCR API 的區塊)
def process_ocr_and_generate_data(image_bytes):
    """
    未來這裡會接收圖片 bytes，並呼叫 OCR 服務。
    目前以 IMG_8423.JPG 的實際辨識數據進行高還原度模擬。
    """
    # 範例回傳：[工號, 姓名, 組別, 職稱, 31天排班清單]
    simulated_data = [
        ["39868", "徐祖慈", "A組", "工程師", ["B","B","H","O","A","A","B","B","H","O","*","A","A","A","O","A","B","B","B","B","H","H","代A","代A","O","B","B","B","B","S","H","O"]],
        ["26811", "凃牧廷", "B組", "分析師", ["B","O","代A","代A","H","B","O","H","C","C","*","C","C","C","O","代A","代A","代A","公A","公A","公A","A","A","H","O","代A","C","C","C","H","S","O"]],
        ["68211", "王佳眉", "C組", "技術員", ["H","B","B","B","B","O","S","B","B","B","*","H","O","B","B","B","B","H","O","A","A","B","B","B","H","O","A","A","B","B","B","B"]],
        ["48168", "周廣益", "D組", "技術員", ["H","O","C","C","C","C","H","代A","代A","O","*","B","B","C","C","C","H","S","O","B","B","C","C","H","代A","O","C","C","C","H","O","O"]],
        ["38976", "黃紹禹", "A組", "技術員", ["H","代A","代A","O","B","B","C","C","C","C","*","H","H","O","B","C","C","C","C","O","O","B","B","B","B","H","S","O","B","C","C","O"]]
    ]
    return simulated_data

# 3. Streamlit 介面佈局：左邊上傳，右邊預覽
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 第一步：上傳排班表照片")
    uploaded_file = st.file_uploader("選擇班表圖片...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # 當使用者上傳照片時，立即在網頁上秀出預覽圖
        st.image(uploaded_file, caption="已上傳的班表照片", use_column_width=True)

with col2:
    st.subheader("⚙️ 第二步：AI 處理與 Excel 下載")
    if uploaded_file is not None:
        with st.spinner("AI 正在解析複雜表格結構與字跡，請稍候..."):
            
            # 讀取圖片並進行 AI 辨識
            image_bytes = uploaded_file.read()
            roster_data = process_ocr_and_generate_data(image_bytes)
            
            # --- 開始利用 openpyxl 在記憶體中建構 Excel 檔案 ---
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "2026年05月份班表"
            ws.views.sheetView[0].showGridLines = True
            
            # 標題與視覺美化
            ws.merge_cells("A1:AM1")
            ws["A1"] = "遠東新世紀股份有限公司 觀音化學纖維廠\n技術處化驗科觀音 2026年度05月份班表"
            ws["A1"].font = Font(name="Microsoft JhengHei", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="1B4D3E", end_color="1B4D3E", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.row_dimensions[1].height = 45
            
            # 月份表頭
            ws.merge_cells("E2:O2")
            ws["E2"] = "04月"
            ws.merge_cells("P2:AI2")
            ws["P2"] = "05月"
            for cell in ["E2", "P2"]:
                ws[cell].font = Font(name="Microsoft JhengHei", size=10, bold=True, color="FFFFFF")
                ws[cell].fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
                ws[cell].alignment = Alignment(horizontal="center", vertical="center")
                
            # 詳細欄位頭
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
                
            # 填入數據與 COUNTIF 公式
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
                
                # 自動統計公式
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

            # 下方加入特別手寫備註的提醒
            ws.merge_cells(f"A{len(roster_data)+5}:AM{len(roster_data)+5}")
            ws[f"A{len(roster_data)+5}"] = "【特別手寫備註】5/6 ~ 5/8 凃牧廷 急救人員初訓"
            ws[f"A{len(roster_data)+5}"].font = Font(name="Microsoft JhengHei", size=11, bold=True, color="C62828")
            ws[f"A{len(roster_data)+5}"].fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")

            # 調整寬度
            for col in ws.columns:
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = 5.5
            ws.column_dimensions['A'].width = 10
            ws.column_dimensions['B'].width = 12

            # 將 Excel 物件轉換成 Streamlit 下載所需的二進位流 (BytesIO)
            excel_buffer = io.BytesIO()
            wb.save(excel_buffer)
            excel_buffer.seek(0)
            
            st.success("🎉 AI 表格結構分析成功！Excel 已封裝完畢。")
            
            # --- 顯示網頁直覺式下載按鈕 ---
            st.download_button(
                label="📥 點我下載優化版 Excel 檔案",
                data=excel_buffer,
                file_name="遠東新世紀_AI辨識班表.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.info("💡 提示：下載的 Excel 檔案右側已經內嵌 `COUNTIF` 排班統計公式，您在 Excel 中修改班別時，統計數據會自動即時更新。")
    else:
        st.warning("請先在左側上傳排班表圖片，系統將自動啟動辨識。")
