"""P2-A private documents and immutable PDF attachments."""
from alembic import op
import sqlalchemy as sa

revision = "0002_documents"
down_revision = "0001_auth"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("abstract", sa.Text()),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("year", sa.Integer()),
        sa.Column("journal", sa.String(500)),
        sa.Column("doi", sa.String(255)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parse_status", sa.String(24), nullable=False),
        sa.Column("extraction_version", sa.String(36)),
        sa.Column("page_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()))
    op.create_index("ix_documents_owner_active_created", "documents", ["owner_id", "deleted_at", "created_at"])
    op.create_table("document_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_document_files_document"),
        sa.UniqueConstraint("storage_key", name="uq_document_files_storage"),
        sa.UniqueConstraint("owner_id", "sha256", name="uq_document_files_owner_hash"))

def downgrade():
    op.drop_table("document_files")
    op.drop_index("ix_documents_owner_active_created", table_name="documents")
    op.drop_table("documents")
