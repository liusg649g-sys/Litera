"""Extraction retry queue: next_retry_at + 0-second default for queued rows.

Separates retry scheduling from status; the independent extraction-worker
process reads `status='queued' AND (next_retry_at IS NULL OR next_retry_at <= NOW())`
under SKIP LOCKED and consumes jobs. api lifespan scan of orphan queued rows
is removed (worker restart is safe).
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_extraction_retry_queue'
down_revision = '0010_qa_answers_indexes_vectors'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('extraction_jobs',
        sa.Column('next_retry_at', sa.DateTime(timezone=False), nullable=True))
    # Backfill existing queued/processing rows with NOW() so the new worker picks
    # them up immediately; completed/failed rows get NULL (never re-queue from scan).
    op.execute("UPDATE extraction_jobs SET next_retry_at = NOW() "
               "WHERE status IN ('queued', 'processing')")
    op.execute("UPDATE extraction_jobs SET next_retry_at = NULL "
               "WHERE status IN ('completed', 'failed')")
    op.create_index('ix_extraction_jobs_status_retry',
                    'extraction_jobs', ['status', 'next_retry_at'])


def downgrade():
    op.drop_index('ix_extraction_jobs_status_retry', table_name='extraction_jobs')
    op.drop_column('extraction_jobs', 'next_retry_at')
