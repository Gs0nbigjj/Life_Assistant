import discord
import asyncio
import traceback
from datetime import datetime
from cogs.BasicDiscordObject import LockableView
from cogs.Stock.utils import StockManager, get_stock_quote, fugle_api_lock
from cogs.Stock.stock_config import FUGLE_TOKEN, TW_TZ

class StockListView(LockableView):
    def __init__(self, bot, user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        
        from cogs.Stock.ui.Button.StockRefreshBtn import StockRefreshBtn
        from cogs.Stock.ui.Button.StockBackToDashboardBtn import StockBackToDashboardBtn
        
        self.add_item(StockRefreshBtn(self.bot, row=0))
        self.add_item(StockBackToDashboardBtn(self.bot, row=0))

    @staticmethod
    async def create_ui(bot, user_id: int, user_name: str):
        """
        建立投資清單看板。優化後資料讀取與組裝解耦。
        """
        try:
            stocks = StockManager.get_user_stocks(user_id)

            # 衛述句早退：若沒有持股則直接回傳主儀表板
            if not stocks:
                from cogs.Stock.ui.View.StockDashboardView import StockDashboardView
                return StockDashboardView.create_dashboard(bot, user_id)

            embed = discord.Embed(
                title=f"📊 {user_name} 的投資清單", 
                color=discord.Color.blue(),
                timestamp=datetime.now(TW_TZ)
            )

            # 迴圈內部拉平，交由獨立方法處理個股數據
            for s in stocks:
                await StockListView._append_stock_field(embed, s)
                await asyncio.sleep(1.1)

            view = StockListView(bot, user_id)
            return embed, view

        except Exception as e:
            print(f"❌ StockListView.create_ui 發生錯誤: {e}")
            traceback.print_exc()
            return None, None

    @staticmethod
    async def _append_stock_field(embed: discord.Embed, stock_obj) -> None:
        """[輔助方法] 負責單一檔股票的富果 API 撈取、未實現損益計算與 Embed 欄位渲染"""
        # 1. 透過 fugle_api_lock 確保執行緒安全並發送 API 請求
        async with fugle_api_lock:
            info = get_stock_quote(stock_obj.stock_symbol, FUGLE_TOKEN)
        
        # 2. 防呆：若讀取失敗則直接新增失敗欄位並中斷
        if not info or not info.get('lastPrice'):
            embed.add_field(
                name=f"⚠️ 讀取失敗 ({stock_obj.stock_symbol})", 
                value="無法取得最新股價 (可能為 API 限流、網路異常或下市)", 
                inline=False
            )
            return

        # 3. 讀取成功，解析現價與漲跌幅
        price = info['lastPrice']
        pct = info['changePercent']
        if pct > 0:
            emoji = "🔴"
        elif pct < 0:
            emoji = "🟢"
        else:
            emoji = "⚪"
        
        # 4. 計算投資報酬率（ROI）與盈虧文字組裝（使用衛述句拉平 nested if）
        profit_data = StockManager.calculate_profit(price, stock_obj.shares, stock_obj.total_cost)
        
        if not profit_data:
            roi_str = f"\n成本: `{stock_obj.buy_price or 'N/A'}`"
        else:
            roi_str = (
                f"\n均價: `{profit_data['avg_price']:.2f}` | 持股: `{stock_obj.shares}`"
                f"\n預估盈虧: `NT$ {profit_data['net_profit']:,}`"
                f"\n實質投報: `{profit_data['roi']:.2f}%`"
            )

        embed.add_field(
            name=f"{info['name']} ({stock_obj.stock_symbol})", 
            value=f"現價: `{price}` ({emoji}{pct:.2f}%){roi_str}", 
            inline=False
        )
        
    @classmethod
    async def load_and_render_ui(cls, interaction: discord.Interaction, bot):
        """共用的 UI 渲染與異常處理解決方案 (徹底消滅按鈕間的重複代碼)"""
        loading_embed = discord.Embed(
            title=f"📊 {interaction.user.name} 的投資清單", 
            description="⏳ 正在向 Fugle API 獲取最新行情，請稍候...\n(受限於免費版 API，每檔股票需等待 1.1 秒)",
            color=discord.Color.blue()
        )
        
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=loading_embed, view=None)
        else:
            await interaction.edit_original_response(embed=loading_embed, view=None)
        try:
            embed, view = await cls.create_ui(
                bot=bot, 
                user_id=interaction.user.id, 
                user_name=interaction.user.name
            )

            if embed and view:
                await interaction.edit_original_response(content=None, embed=embed, view=view)
            else:
                err_embed = discord.Embed(title="❌ 獲取資料失敗", description="請稍後再試。", color=discord.Color.red())
                await interaction.edit_original_response(embed=err_embed, view=None)
                
        except Exception as e:
            import logging
            logging.getLogger("discord").exception("❌ 股票看板渲染執行崩潰")
            
            err_embed = discord.Embed(title="❌ 系統異常", description=f"發生錯誤：{e}", color=discord.Color.red())
            await interaction.edit_original_response(embed=err_embed, view=None)