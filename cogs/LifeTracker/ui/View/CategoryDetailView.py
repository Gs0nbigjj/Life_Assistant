import discord
import traceback
from cogs.LifeTracker.utils.LifeTracker_Manager import LifeTracker_Manager
from cogs.LifeTracker.ui.Button import (
    BackToLifeDashboardBtn, LogRecordBtn, PageBtn, 
    ManageSubcatBtn, ToggleChartBtn, ToggleListModeBtn, ToggleRangeEditBtn
)
from cogs.LifeTracker.ui.Button.EInvoicePlatformBtn import EInvoicePlatformBtn
from cogs.LifeTracker.src import generate_donut_chart
from cogs.LifeTracker.ui.Select.RangeSelect import RangeSelect
from cogs.BasicDiscordObject import LockableView

class CategoryDetailView(LockableView):
    def __init__(self, bot, category_id: int, page: int = 0, field_index: int = 0, 
                 fields_count: int = 1, show_list: bool = False, range_days: int = 7, 
                 options_list: list = None, total_pages: int = 0, cat_name: str = ""):
        super().__init__(timeout=None)
        self.bot = bot
        self.category_id = category_id
        self.page = page
        self.field_index = field_index
        self.show_list = show_list
        self.range_days = range_days
        self.total_pages = total_pages
        self.cat_name = cat_name
        
        self.add_item(LogRecordBtn(bot, category_id, row=0))
        self.add_item(ManageSubcatBtn(bot, category_id, row=0))
        self.add_item(ToggleListModeBtn(bot, category_id, page, field_index, show_list, row=0))
    
        self.add_item(RangeSelect(bot, category_id, range_days, options_list or [7, 30, 180, 365], row=1))
        
        if not show_list:
            if fields_count > 1:
                self.add_item(ToggleChartBtn(bot, category_id, field_index, fields_count, row=2))
            self.add_item(ToggleRangeEditBtn(bot, category_id, row=2))
            if self.cat_name == "消費":
                self.add_item(EInvoicePlatformBtn(bot, category_id, row=2))
        else:
            if page > 0:
                self.add_item(PageBtn(bot, category_id, page - 1, field_index, show_list, emoji="◀️", row=2))
            
            if page + 1 < total_pages:
                self.add_item(PageBtn(bot, category_id, page + 1, field_index, show_list, emoji="▶️", row=2))

        self.add_item(BackToLifeDashboardBtn(bot, row=2))


    @staticmethod
    async def create_ui(bot, category_id: int, page: int = 0, field_index: int = 0, 
                        show_list: bool = False, range_days: int = None):
        try:
            cat_info, _ = LifeTracker_Manager.get_category_details(category_id)
            cat_name = cat_info['name']
        
            # 參數與變數初估
            current_days = range_days if range_days is not None else (cat_info.get('current_range') or 7)
            options_list = cat_info.get('range_options') or [7, 30, 180, 365]

            fields = cat_info['fields']
            fields_count = len(fields)
            target_field = fields[field_index] if fields_count > 0 else None

            # 基礎 Embed 組裝
            embed = discord.Embed(
                title=f"📊 分類看板：{cat_name}",
                description=f"紀錄數值分類：`{', '.join(fields)}`\n目前檢視：**{target_field}**\n⌛ **目顯示區間：過去 {current_days} 天的紀錄**",
                color=discord.Color.gold()
            )

            chart_file = None
            total_pages = 0

            # 根據模式分流行為（核心降分點：將龐大的區塊搬移至輔助方法）
            if not show_list:
                chart_file = await CategoryDetailView._build_dashboard_mode(
                    embed, cat_info, category_id, target_field, current_days
                )
            else:
                total_pages = await CategoryDetailView._build_list_mode(
                    embed, category_id, page, current_days
                )
            
            # 生成最終 View
            view = CategoryDetailView(
                bot, category_id, page, field_index, fields_count, 
                show_list, current_days, options_list, total_pages, cat_name
            )
            return embed, view, chart_file

        except Exception as e:
            print("[create_ui 崩潰]")
            traceback.print_exc()
            error_embed = discord.Embed(title="❌ 介面生成失敗", description=f"錯誤原因：`{e}`", color=discord.Color.red())
            return error_embed, None, None

    @staticmethod
    async def _build_dashboard_mode(embed: discord.Embed, cat_info: dict, category_id: int, target_field: str, current_days: int):
        """處理主看板模式下的 AI 建議加載與圖表繪製邏輯"""
        ai_suggestion = cat_info.get('last_ai_analysis')
        update_time = cat_info.get('analysis_updated_at')

        # 加載 AI 建議
        if ai_suggestion:
            time_str = update_time.strftime("%m/%d") if update_time else "本週"
            embed.add_field(name=f"🪄 AI 本週總結建議 ({time_str})", value=ai_suggestion, inline=False)
        else:
            embed.add_field(name="🪄 AI 分析服務", value="目前尚無分析紀錄，將在下週一自動產生。", inline=False)

        # 撈取數據與繪圖
        stats_data = LifeTracker_Manager.get_subcat_stats(category_id, target_field, range_days=current_days)
        if not stats_data:
            embed.add_field(name="目前暫無數據", value=f"在過去 {current_days} 天內沒有紀錄。", inline=False)
            return None

        chart_file = generate_donut_chart(cat_info['name'], stats_data, target_field)
        if chart_file:
            embed.set_image(url=f"attachment://{chart_file.filename}")
        return chart_file

    @staticmethod
    async def _build_list_mode(embed: discord.Embed, category_id: int, page: int, current_days: int) -> int:
        """[輔助方法] 專門處理歷史清單模式下的分頁撈取與 Embed 欄位渲染"""
        records, total_pages = LifeTracker_Manager.get_recent_records(
            category_id, page=page, limit=10, range_days=current_days
        )
        
        if not records:
            embed.add_field(name="近期紀錄", value="目前還沒有任何紀錄喔！", inline=False)
        else:
            # 跑迴圈組裝欄位
            for r in records:
                val_str = " | ".join([f"{k}: {v}" for k, v in r['values'].items()])
                embed.add_field(
                    name=f"🏷️ [{r['sub_name']}] - {r['created_at']}",
                    value=f"**{val_str} - {r['note']}**",
                    inline=False
                )

        return total_pages