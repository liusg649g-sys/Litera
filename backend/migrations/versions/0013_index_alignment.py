"""Align extraction/document-chunk indexes with the ORM declarations.

0009 created single-column indexes on extraction_jobs.owner_id/document_id and
document_chunks.owner_id, while the models declare composite lead indexes used by
the worker and QA lookup paths. Add the declared composites; keep existing
single-column indexes for backward compatibility.
"""
from alembic import op

revision = '0013_index_alignment'
down_revision = '0012_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_extraction_jobs_owner_document', 'extraction_jobs',
                    ['owner_id', 'document_id'])
    op.create_index('ix_document_chunks_owner_doc_ver', 'document_chunks',
                    ['owner_id', 'document_id', 'extraction_version'])


def downgrade():
    op.drop_index('ix_document_chunks_owner_doc_ver', table_name='document_chunks')
    op.drop_index('ix_extraction_jobs_owner_document', table_name='extraction_jobs')
