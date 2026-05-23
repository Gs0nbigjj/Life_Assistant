# cogs\LifeTracker\src\invoice_processor.py
import os
import pandas as pd
import asyncio
from datetime import datetime
from cogs.LifeTracker.utils import LifeTracker_Manager, AiAnalyzer
from database import SessionLocal
from database.models import TrackerCategory, TrackerSubCategory
import time

class InvoiceProcessor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.download_path = os.path.join("cogs", "LifeTracker", "src", "downloads")
        self.target_category_id = LifeTracker_Manager.get_consumption_category_id(user_id)

    def get_latest_csv(self):
        files = [f for f in os.listdir(self.download_path) if f.endswith('.csv')]
        if not files: return None
        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.download_path, x)), reverse=True)
        return os.path.join(self.download_path, files[0])

    async def process(self):
        if not self.target_category_id:
            print(f"❌ 找不到 User({self.user_id}) 的「消費」分類，停止匯入。")
            return

        csv_path = self.get_latest_csv()
        if not csv_path:
            print("📅 找不到任何 CSV 檔案。")
            return

        print(f"🚀 開始處理發票檔案: {csv_path} (對應分類 ID: {self.target_category_id})")
        
        try:
            df = pd.read_csv(csv_path, skipfooter=2, engine='python', encoding='utf-8')
        except Exception as e:
            print(f"❌ CSV 讀取失敗: {e}")
            return

        with SessionLocal() as db:
            subcats = db.query(TrackerSubCategory).filter_by(category_id=self.target_category_id).all()
            subcat_map = {s.name: s.id for s in subcats} 
            subcat_names = list(subcat_map.keys())

        df = df[df['消費明細_金額'] > 0]
        
        unique_items = df['消費明細_品名'].dropna().unique().tolist()
        
        if not unique_items:
            print("⚠️ 沒有需要處理的有效發票品項。")
            return
            
        print(f"📦 整理出 {len(unique_items)} 個獨立品項，準備交由 AI 批次分類...")
        
        ai_mapping = await AiAnalyzer.classify_consumption_batch(unique_items, subcat_names)
        print("🤖 AI 批次分類完成！開始寫入資料庫...")

        for index, row in df.iterrows():
            item_name = row['消費明細_品名']
            amount = row['消費明細_金額']
            date_raw = str(row['發票日期']) 
            
            record_date = f"{date_raw[:4]}/{date_raw[4:6]}/{date_raw[6:8]}"
            
            # 從剛剛 AI 給的對照表拿出分類，找不到就預設為「其他」
            ai_tag = ai_mapping.get(item_name, "其他")
            target_subcat_id = subcat_map.get(ai_tag)

            values_dict = {"金額": amount}
            
            success, err = LifeTracker_Manager.add_life_record(
                user_id=self.user_id,
                category_id=self.target_category_id,
                subcat_id=target_subcat_id,
                values_dict=values_dict,
                note=item_name,
                record_time_str=record_date
            )

            if success:
                print(f"✅ [{ai_tag}] {item_name} (${amount})")
            else:
                print(f"❌ 記錄失敗: {err}")
                
        print("🏁 所有發票資料處理完畢！")

        try:
            os.remove(csv_path)
            print(f"🗑️ 已成功刪除暫存檔案: {os.path.basename(csv_path)}")
        except Exception as e:
            print(f"⚠️ 無法刪除檔案 {csv_path}: {e}")