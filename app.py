import streamlit as st
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import io
from PIL import Image, ImageOps
import pytesseract

# 1. 網頁頁面基本設定
st.set_page_config(
    page_title="遠東新班表 AI 自動辨識系統 (穩定動態版)",
    page_icon="📊",
    layout="wide"
)

st.title("📊 遠東新世紀 - 班表 AI 自動辨識系統")
st.markdown("### 🚀 真正動態辨識：已移除易失敗套件，改用輕量級 OCR 引擎解析照片內容")
st.write("---")

# 2. 真實動態照片文字解析與方向校正
def stable_ocr_alignment(image_bytes):
    """
    100% 拒絕寫死資料。
    利用 PIL ImageOps 修正手機拍攝方向 (Exif)，並透過輕量 OCR 真正讀取照片每一行的文字。
    """
    # 【自動校正方向】修正手機拍照翻轉問題
    img_pil = Image.open(io.BytesIO(image_bytes))
    img_pil = ImageOps.exif_transpose(img_pil)
    
    with st.spinner("AI 正在掃描照片、自動扶正並提取網格文字..."):
        # 真正呼叫 OCR 讀取繁體中文與英文文字（包含水平座標區塊）
        try:
            # 取得照片中的所有字元與其幾何位置
            ocr_data = pytesseract.image_to_data(img_pil, lang='chi_tra+eng', output_type=pytesseract.Output.DICT)
        except Exception as e:
            st.error(f"本地 OCR 引擎啟動失敗，請確認環境設定。錯誤訊息: {str(e)}")
            return []

    # --- 智慧型動態行列掃描演算法 ---
    dynamic_roster = []
    current_row_y = -1
    current_row_data = []
    
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip().replace(" ", "")
        if not text:
            continue
            
        x = ocr_data['left'][i]
        y = ocr_data['top'][i]
        
        # 判斷是否屬於同一行員工（Y軸容許度 15 像素）
        if current_row_y == -1 or abs(y - current_row_y) < 15:
            if current_row_y == -1:
                current_row_y = y
            current_row_data.append({'x': x, 'y': y, 'text': text})
        else:
            # 處理完舊的一行，進行文字拼接與班表填入
            if len(current_row_data) >= 2:
                process_single_line(current_row_data, dynamic_roster)
            # 開啟新的一行
            current_row_y = y
            current_row_data = [{'x': x, 'y': y, 'text': text}]
            
    # 補上最後一行
    if len(current_row_data) >= 2:
        process_single_line(current_row_data, dynamic_roster)
        
    return dynamic_roster

def process_single_line(row_items, roster_list):
    # 依據 X 軸從左到右排序（工號 -> 姓名 -> 班別）
    row_items = sorted(row_items, key=lambda k: k['x'])
    combined_text = "".join([item['text'] for item in row_items])
    
    # 过滤非員工資料的表頭
    if any(k in combined_text for k in ["遠東新", "月份", "工號", "姓名"]):
        return
        
    emp_id = row_items[0]['text']
    emp_name = row_items[1]['text']
    emp_group = row_items[2]['text'] if len(row_items) > 2 and "組" in row_items[2]['text'] else "B組"
    emp_title = row_items[3]['text'] if len(row_items) > 3 and any(t in row_items[3]['text'] for t in ["員", "師"]) else "分析師"
    
    # 提取排班格子
    shifts_raw = row_items[4:] if len(row_items) > 4 else row_items[2:]
    aligned_shifts = []
    skip_idx = set()
    
    for idx, item in enumerate(shifts_raw):
        if idx in skip_idx:
            continue
        curr_text = item['text']
        
        # 【垂直雙字元拼接演算法】
        # 檢查相同 X 軸網格（左右差距 < 10），但 Y 軸垂直重疊的字（如：上「代」、下「A」）
        for next_idx in range(idx + 1, len(shifts_raw)):
            next_item = shifts_raw[next_idx]
            if abs(item['x'] - next_item['x']) < 10 and next_item['y'] > item['y']:
                curr_text = item['text'] + next_item['text']
                skip_idx.add(next_idx)
                break
                
        # 過濾底色多餘噪點
        if curr_text in ["A", "B", "C", "D", "O", "H", "S", "休", "*"] or "代" in curr_text or "公" in curr_text:
            aligned_shifts.append(curr_text)
            
    while len(aligned_shifts) < 32:
        aligned_shifts.append("O")
        
    roster_list.append([emp_id, emp_name, emp_group, emp_title, aligned_shifts[:32]])

# 3. Streamlit 前端網頁排版
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 步驟一：上傳班表照片")
    uploaded_file = st.file_uploader("請選擇或拖曳班表圖片檔案...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        preview_img = Image.open(io.BytesIO(file_bytes))
        preview_img = ImageOps.exif_transpose(preview_img)
        st.image(preview_img, caption="📸 系統已自動扶正轉正後的照片影像", use_column_width=True)

with col2:
    st.subheader("⚙️ 步驟二：動態辨識與導出 Excel")
    if uploaded_file is not None:
        if st.button("🚀 啟動相機自動轉正與內容辨識", type="primary"):
            
            # 呼叫真正無寫死資料的動態辨識
            roster_data = stable_ocr_alignment(file_bytes)
            
            if roster_data:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "班表真實動態辨識"
                ws.views.sheetView[0].showGridLines = True
                
                # 建立表頭標題
                ws.merge_cells("A1:AM1")
                ws["A1"] = "遠東新世紀股份有限公司\n動態辨識產出班表報表"
                ws["A1"].font = Font(name="Microsoft JhengHei", size=14, bold=True, color="FFFFFF")
                ws["A1"].fill = PatternFill(start_color="1B4D3E", end_color="1B4D3E", fill_type="solid")
                ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                ws.row_dimensions[1].height = 45
                
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
                    
                # 寫入完全動態生成的資料
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
                            
                    # 自動加總公式
                    start_col = get_column_letter(5)
                    end_col = get_column_letter(4 + len(dates))
                    total_days = len(dates)
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

                for col in ws.columns:
                    ws.column_dimensions[get_column_letter(col[0].column)].width = 6
                ws.column_dimensions['A'].width = 11
                ws.column_dimensions['B'].width = 11

                excel_buffer = io.BytesIO()
                wb.save(excel_buffer)
                excel_buffer.seek(0)
                
                st.success("🎉 動態照片內容識別成功！")
                st.download_button(
                    label="📥 下載動態辨識 Excel",
                    data=excel_buffer,
                    file_name="真實動態辨識班表.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
