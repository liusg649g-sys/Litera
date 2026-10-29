"""Extraction jobs, results, pages and chunks. Additive; no changes to existing tables."""
from alembic import op
import sqlalchemy as sa
revision = '0009_extraction'
down_revision = '0008_user_model_profiles'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('extraction_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),  # queued | processing | completed | failed
        sa.Column('attempts', sa.Integer, nullable=False, default=0),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('version_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        mysql_engine='InnoDB')
    op.create_table('extraction_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('field_sources', sa.JSON(), nullable=False),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('document_id', 'extraction_version', name='uq_extraction_results_doc_version'),
        mysql_engine='InnoDB')
    op.create_table('document_pages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('page_number', sa.Integer, nullable=False),
        sa.Column('text', sa.Text().with_variant(sa.dialects.mysql.MEDIUMTEXT(), 'mysql'), nullable=False),
        sa.UniqueConstraint('document_id', 'extraction_version', 'page_number', name='uq_document_pages_doc_ver_page'),
        mysql_engine='InnoDB')
    op.create_table('document_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('page_number', sa.Integer, nullable=False),
        sa.Column('start_offset', sa.Integer, nullable=False),
        sa.Column('end_offset', sa.Integer, nullable=False),
        sa.Column('text', sa.Text().with_variant(sa.dialects.mysql.MEDIUMTEXT(), 'mysql'), nullable=False),
        mysql_engine='InnoDB')

def downgrade():
    op.drop_table('document_chunks')
    op.drop_table('document_pages')
    op.drop_table('extraction_results')
    op.drop_table('extraction_jobs')
