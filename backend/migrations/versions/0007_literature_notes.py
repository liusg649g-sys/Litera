"""P3-A additive personal notes and document many-to-many links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT

revision = "0007_literature_notes"
down_revision = "0006_reader_assets"
branch_labels = depends_on = None


def upgrade():
    timestamp = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table("notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("content_format", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_schema_version", sa.Integer(), nullable=False),
        # Explicit application values avoid MySQL JSON DEFAULT compatibility traps.
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        mysql_engine="InnoDB")
    op.create_index("ix_notes_owner_updated", "notes", ["owner_id", "updated_at", "id"])
    op.create_table("note_documents",
        sa.Column("note_id", sa.String(36), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        mysql_engine="InnoDB")
    op.create_index("ix_note_documents_owner_document", "note_documents", ["owner_id", "document_id", "note_id"])


def downgrade():
    raise RuntimeError("Retain personal notes and links; roll back application only")
