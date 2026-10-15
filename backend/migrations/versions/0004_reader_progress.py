"""A2 nullable reader settings; preserve all existing records and PDF files."""
from alembic import op
import sqlalchemy as sa

revision = "0004_reader_progress"
down_revision = "0003_library"
branch_labels = depends_on = None


def upgrade():
    op.add_column("reading_progress", sa.Column("view_mode", sa.String(16), nullable=True))
    op.add_column("reading_progress", sa.Column("zoom_mode", sa.String(16), nullable=True))


def downgrade():
    op.drop_column("reading_progress", "zoom_mode")
    op.drop_column("reading_progress", "view_mode")
