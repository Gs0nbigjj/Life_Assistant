# cogs\LifeTracker\ui\Select\RangeSelect.py
import discord
from discord import ui
from cogs.BasicDiscordObject import LockableView
from cogs.LifeTracker.utils import LifeTracker_Manager

class RangeSelect(ui.Select):
    def __init__(self, bot, category_id, current_days, options_list, row=None, mode="switch"):
        self.bot = bot
        self.category_id = category_id
        self.mode = mode
        
        # 衛述句優化：防呆並決定實際使用的選項列表
        actual_options = options_list if isinstance(options_list, list) else [7, 30, 365]
        
        # Dict Mapping 消除原本的單行 if-else 分支
        mode_configs = {
            "delete": {
                "prefix": "🗑️ 刪除 ", 
                "emoji": "🗑️", 
                "placeholder": "🗑️ 選擇要刪除的區間..."
            },
            "switch": {
                "prefix": "", 
                "emoji": "⌛", 
                "placeholder": "⌛ 切換統計區間..."
            }
        }
        config = mode_configs.get(mode, mode_configs["switch"])
        # 跑迴圈呼叫獨立格式化方法，組裝 SelectOption
        select_options = []
        for d in actual_options:
            days_int = int(d)
            label = self._format_days_label(days_int)
            
            # 判斷是否為預設選項
            is_default = (days_int == int(current_days)) if mode == "switch" else False
            
            select_options.append(discord.SelectOption(
                label=f"{config['prefix']}{label}", 
                value=str(d), 
                emoji=config['emoji'],
                default=is_default
            ))

        super().__init__(placeholder=config['placeholder'], options=select_options, row=row)

        @staticmethod
        def _format_days_label(days: int) -> str:
            """天數換算為複合時間文字（年/月/週/天），拉平主函式複雜度 🟢"""
            remaining_days = days
            parts = []
            
            # 計算年 (365天)
            years = remaining_days // 365
            if years > 0:
                parts.append(f"{years} 年 ")
                remaining_days %= 365
            
            # 計算月 (30天)
            months = remaining_days // 30
            if months > 0:
                parts.append(f"{months} 個月 ")
                remaining_days %= 30
                
            # 計算週 (7天)
            weeks = remaining_days // 7
            if weeks > 0:
                parts.append(f"{weeks} 週 ")
                remaining_days %= 7
                
            # 計算剩餘天數
            if remaining_days > 0 or not parts:
                parts.append(f"{remaining_days} 天 ")
            
            return "".join(parts)

    async def callback(self, interaction: discord.Interaction):
        # 優先處理 switch 模式（衛述句：符合就執行並早退）
        if self.mode == "switch":
            await interaction.response.defer()
            await self._handle_switch_mode(interaction)
            return

        # 處理非 switch 模式 (例如 delete) 的鎖定與核心邏輯
        if isinstance(self.view, LockableView):
            await self.view.lock_all(interaction)

        try:
            days = int(self.values[0])
            if self.mode == "delete":
                await self._handle_delete_mode(interaction, days)
        except Exception as e:
            print(f"❌ RangeSelect [{self.mode}] 出錯: {e}")
            import traceback
            traceback.get_exc()
            if isinstance(self.view, LockableView):
                await self.view.unlock_all()


    async def _handle_switch_mode(self, interaction: discord.Interaction):
        """理切換統計區間的邏輯"""
        days = int(self.values[0])
        LifeTracker_Manager.update_current_range(self.category_id, days)
        
        from cogs.LifeTracker.ui.View.CategoryDetailView import CategoryDetailView
        embed, view, chart_file = await CategoryDetailView.create_ui(
            bot=self.bot, category_id=self.category_id, range_days=days
        )
        
        attachments = [chart_file] if chart_file else []
        await interaction.edit_original_response(embed=embed, view=view, attachments=attachments)

    async def _handle_delete_mode(self, interaction: discord.Interaction, days: int):
        """處理刪除區間選項的邏輯"""
        success = LifeTracker_Manager.delete_range_option(self.category_id, days)
        
        from cogs.LifeTracker.ui.View.RangeEditView import RangeEditView
        embed, view = await RangeEditView.create_ui(self.bot, self.category_id)
        
        if not success:
            embed.title = "❌ 刪除失敗"
            embed.description = "無法刪除該選項，**系統必須保留至少一個時間區間**！\n\n" + embed.description
            embed.color = discord.Color.red()
        
        if view:
            await view.unlock_all() 

        await interaction.edit_original_response(embed=embed, view=view, attachments=[])