import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import traceback
from datetime import datetime

# 導入配置與自定義工具
from cogs.Stock.stock_config import MARKET_OPEN, MARKET_CLOSE, REPORT_TIME, FUGLE_TOKEN, TW_TZ
from cogs.Stock.utils import StockManager, get_stock_quote,fugle_api_lock

class Stock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 啟動背景任務
        self.stock_monitor.start()

    def cog_unload(self):
        self.stock_monitor.cancel()

    # 指令入口 (UI)
    @app_commands.command(name="stock", description="開啟股票監控儀表板")
    async def stock_dashboard(self, interaction: discord.Interaction):
        """進入股票模組的主入口"""
        try:
            from .ui.View.StockDashboardView import StockDashboardView
            # 產生 Embed 與 View
            embed, view = StockDashboardView.create_dashboard(self.bot, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"❌ 開啟儀表板失敗: {e}")
            traceback.print_exc()

    # 背景任務 (Tasks)
    @tasks.loop(minutes=1)
    async def stock_monitor(self):
        """每分鐘檢查一次股價 (免費版序列檢查模式)。"""
        now = datetime.now(TW_TZ)
        if now.weekday() >= 5: 
            return 
            
        current_time_val = now.hour * 100 + now.minute
        if not (MARKET_OPEN <= current_time_val <= MARKET_CLOSE): 
            return

        today_date_str = now.strftime('%Y-%m-%d')

        try:
            watches = StockManager.get_alert_watches()

            for watch in watches:
                # 將每一筆訂閱交給獨立的處理器，完全拉平巢狀
                await self._check_single_watch(watch, today_date_str)
                await asyncio.sleep(1.1) 
                
        except Exception as e:
            print(f"⚠️ 監控循環錯誤: {e}")

    # ==================== 抽離出的單一股票檢查處理器 ====================

    async def _check_single_watch(self, watch: dict, today_date_str: str):
        """[輔助方法] 負責單一股票的 API 請求、條件比對與通知分發。使用衛述句全面平坦化"""
        user_id = watch['user_id']
        symbol = watch['stock_symbol']

        # 1. 取得即時報價 (透過 fugle_api_lock 確保執行緒安全)
        async with fugle_api_lock:
            info = get_stock_quote(symbol, FUGLE_TOKEN)
            
        # 衛述句防呆：若拿不到報價或價格不合法，立刻早退
        curr_price = info.get('lastPrice') or info.get('current')

        if not info or not curr_price:
            return

        # curr_price = info['lastPrice']
        change_pct = info['changePercent'] / 100

        # 2. 決定預警類型與訊息 (消滅深層的 if 嵌套)
        alert_info = self._evaluate_alert_condition(watch, info, curr_price, change_pct, today_date_str)
        if not alert_info:
            return  # 未達觸發門檻，早退

        alert_msg, alert_type = alert_info

        # 3. 檢查最後通知價格，確認無誤後發送並寫入資料庫
        if watch['last_notified_price'] != curr_price:
            await self.send_dm(user_id, alert_msg)
            StockManager.update_notified_price_and_date(
                user_id=user_id, 
                symbol=symbol, 
                price=curr_price, 
                alert_type=alert_type, 
                date_str=today_date_str
            )

    @staticmethod
    def _evaluate_alert_condition(watch: dict, info: dict, curr_price: float, change_pct: float, today_date_str: str) -> tuple[str, str] | None:
        """[微小輔助方法] 專門抽離複雜的漲跌幅與日期比對邏輯"""
        symbol = watch['stock_symbol']
        last_up_date = watch.get('last_up_notified_date').strftime('%Y-%m-%d') if hasattr(watch.get('last_up_notified_date'), 'strftime') else watch.get('last_up_notified_date')
        last_down_date = watch.get('last_down_notified_date').strftime('%Y-%m-%d') if hasattr(watch.get('last_down_notified_date'), 'strftime') else watch.get('last_down_notified_date')

        # 漲幅預警判定
        if watch['target_up'] and change_pct >= watch['target_up']:
            if last_up_date != today_date_str:
                return f"🔴 **{info['name']} ({symbol})** 噴發！\n現價：`{curr_price}` (漲幅：`{change_pct*100:.2f}%`)", "up"

        # 跌幅預警判定
        if watch['target_down'] and change_pct <= watch['target_down']:
            if last_down_date != today_date_str:
                return f"🟢 **{info['name']} ({symbol})** 下跌！\n現價：`{curr_price}` (跌幅：`{change_pct*100:.2f}%`)", "down"

        return None

    @tasks.loop(time=REPORT_TIME)

    async def send_dm(self, user_id, content):
        """發送私訊輔助函數"""
        try:
            user = await self.bot.fetch_user(user_id)
            if user: await user.send(content)
        except Exception as e:
            print(f"❌ 無法發送私訊給 {user_id}: {e}")
