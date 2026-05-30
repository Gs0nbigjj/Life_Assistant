import discord
from discord import ui

class AddSubCategoryBtn(ui.Button):
    def __init__(self, bot, label="新增標籤", emoji="🏷️", row=1, *, category_name: str=None, category_id: int=None):
        super().__init__(label=label, style=discord.ButtonStyle.success, emoji=emoji, row=row)
        self.bot = bot
        self.category_name = category_name
        self.category_id = category_id

    async def callback(self, interaction: discord.Interaction):
        from cogs.LifeTracker.ui.Modal import AddSubCategoryModal
        if self.category_id:
            await interaction.response.send_modal(AddSubCategoryModal(self.bot, category_id=self.category_id))
        else:
            await interaction.response.send_modal(AddSubCategoryModal(self.bot, category_name=self.category_name))