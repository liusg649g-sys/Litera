"""B1 additive annotation storage. Original files and business rows are untouched."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT

revision = "0005_annotations"
down_revision = "0004_reader_progress"
branch_labels = depends_on = None
timestamp = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
annotation_text = sa.Text().with_variant(MEDIUMTEXT(), "mysql")


def upgrade():
    op.create_table("annotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.JSON()), sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("style", sa.JSON(), nullable=False), sa.Column("selected_text", annotation_text),
        sa.Column("content", annotation_text), sa.Column("color", sa.String(7), nullable=False),
        sa.Column("asset_id", sa.String(36)), sa.Column("z_index", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False), sa.Column("updated_at", timestamp, nullable=False),
        sa.Column("deleted_at", timestamp))
    op.create_index("ix_annotations_owner_document_page", "annotations", ["owner_id", "document_id", "page_number"])
    op.create_index("ix_annotations_document_updated", "annotations", ["document_id", "updated_at"])
    op.create_table("document_reader_state",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("annotation_revision", sa.Integer(), nullable=False))
    op.create_index("ix_document_reader_state_owner_id", "document_reader_state", ["owner_id"])
    op.create_table("annotation_command_receipts",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("command_id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False), sa.Column("expires_at", timestamp, nullable=False))
    op.create_index("ix_annotation_command_receipts_owner_id", "annotation_command_receipts", ["owner_id"])
    op.create_index("ix_annotation_receipts_expiry", "annotation_command_receipts", ["expires_at"])


def downgrade():
    raise RuntimeError("Annotation data must be retained; roll back the application, not user annotations")
