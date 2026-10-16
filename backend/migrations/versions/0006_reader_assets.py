"""B2 additive private raster assets; retain all existing business rows."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME
revision = "0006_reader_assets"
down_revision = "0005_annotations"
branch_labels = depends_on = None

def upgrade():
    timestamp = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table("reader_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(80), unique=True, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False), sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)), sa.Column("created_at", timestamp, nullable=False),
        sa.Column("expires_at", timestamp))
    op.create_index("ix_reader_assets_document_status", "reader_assets", ["owner_id", "document_id", "status"])

def downgrade():
    raise RuntimeError("Retain reader assets; roll back application only")
