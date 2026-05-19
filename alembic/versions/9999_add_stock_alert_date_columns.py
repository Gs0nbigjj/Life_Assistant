"""add stock alert date columns

Revision ID: 9999_add_stock_alert_date_columns
Revises: fe3f26b43b98
Create Date: 2026-05-19 17:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# 🌟 注意：down_revision 指向你圖片中最後一隻檔案的 Hash 碼，確保歷史紀錄成功對接！
revision: str = '9999_add_stock_alert_date_columns'
down_revision: Union[str, None] = None  # 👈 改成 None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 🚀 在本地與雲端執行 upgrade 時，自動在 user_stock_watch 資料表補上這兩個欄位
    op.add_column('user_stock_watch', sa.Column('last_up_date', sa.String(), nullable=True))
    op.add_column('user_stock_watch', sa.Column('last_down_date', sa.String(), nullable=True))


def downgrade() -> None:
    # 復原指令（若需要降級時執行）
    op.drop_column('user_stock_watch', 'last_up_date')
    op.drop_column('user_stock_watch', 'last_down_date')