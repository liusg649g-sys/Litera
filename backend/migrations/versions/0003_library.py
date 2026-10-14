"""Personal classification, reading history and durable PDF cleanup; preserves existing IDs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME
library_time = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")

revision = "0003_library"
down_revision = "0002_documents"
branch_labels = depends_on = None

def upgrade():
    for name in ("folders", "tags"):
        columns = [sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("normalized_name", sa.String(300), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("owner_id", "normalized_name", name=f"uq_{name}_owner_name")]
        if name == "tags":
            columns.append(sa.Column("color", sa.String(7)))
        op.create_table(name, *columns)
    # Add the nullable FK separately: SQLite supports REFERENCES ADD COLUMN;
    # MySQL uses ALTER ADD CONSTRAINT, without rebuilding documents.
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE documents ADD COLUMN folder_id VARCHAR(36) REFERENCES folders(id) ON DELETE SET NULL")
    else:
        op.add_column("documents", sa.Column("folder_id", sa.String(36)))
        op.create_foreign_key("fk_documents_folder", "documents", "folders", ["folder_id"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("last_read_at", library_time))
    op.add_column("documents", sa.Column("purge_job_id", sa.String(36)))
    op.create_index("ix_documents_folder", "documents", ["owner_id", "folder_id"])
    op.create_index("ix_documents_recent", "documents", ["owner_id", "deleted_at", "last_read_at"])
    op.create_table("document_tags",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False))
    op.create_index("ix_document_tags_owner_tag", "document_tags", ["owner_id", "tag_id"])
    op.create_table("reading_progress",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("page_number", sa.Integer()), sa.Column("zoom", sa.String(20)),
        sa.Column("last_read_at", library_time, nullable=False), sa.Column("version", sa.Integer(), nullable=False))
    op.create_index("ix_reading_progress_owner_id", "reading_progress", ["owner_id"])
    op.create_table("cleanup_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False, unique=True),
        sa.Column("storage_key", sa.String(80)), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("error_code", sa.String(64)),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_cleanup_jobs_owner_id", "cleanup_jobs", ["owner_id"])

def downgrade():
    for name in ("cleanup_jobs", "reading_progress", "document_tags"):
        op.drop_table(name)
    op.drop_index("ix_documents_recent", table_name="documents")
    op.drop_index("ix_documents_folder", table_name="documents")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_documents_folder", "documents", type_="foreignkey")
    for name in ("purge_job_id", "last_read_at", "folder_id"):
        op.drop_column("documents", name)
    op.drop_table("tags")
    op.drop_table("folders")
