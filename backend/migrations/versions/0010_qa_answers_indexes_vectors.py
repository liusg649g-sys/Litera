"""Single-document QA: persisted answers, versioned indexes and chunk vectors."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMBLOB, MEDIUMTEXT

revision = '0010_qa_answers_indexes_vectors'
down_revision = '0009_extraction'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('qa_answers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_sha256', sa.String(64), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('mode', sa.String(16), nullable=False),
        sa.Column('intent', sa.String(24), nullable=False),
        sa.Column('question', sa.Text().with_variant(MEDIUMTEXT(), 'mysql'), nullable=False),
        sa.Column('answer', sa.Text().with_variant(MEDIUMTEXT(), 'mysql'), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=False),
        sa.Column('model', sa.String(200), nullable=False),
        sa.Column('context_revision', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        mysql_engine='InnoDB')
    op.create_index('ix_qa_answers_owner_doc_created', 'qa_answers', ['owner_id', 'document_id', 'created_at'])
    op.create_index('ix_qa_answers_doc_version', 'qa_answers', ['document_id', 'extraction_version'])

    op.create_table('qa_indexes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('embedding_model', sa.String(200), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),  # building | ready | failed
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('built_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('document_id', 'extraction_version', name='uq_qa_indexes_doc_version'),
        mysql_engine='InnoDB')
    op.create_index('ix_qa_indexes_owner_document', 'qa_indexes', ['owner_id', 'document_id', 'status'])

    op.create_table('qa_chunk_vectors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extraction_version', sa.String(36), nullable=False),
        sa.Column('chunk_id', sa.String(36), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('vector', sa.LargeBinary().with_variant(MEDIUMBLOB(), 'mysql'), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('chunk_id', name='uq_qa_chunk_vectors_chunk'),
        mysql_engine='InnoDB')
    op.create_index('ix_qa_chunk_vectors_doc_version', 'qa_chunk_vectors', ['document_id', 'extraction_version'])


def downgrade():
    # Published answers are user-visible history; vectors are rebuildable but the
    # answers are not. Roll back the application, never the saved evidence.
    raise RuntimeError('Retain QA answers and vectors; roll back application only')
