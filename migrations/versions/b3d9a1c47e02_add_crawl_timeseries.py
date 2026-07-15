"""add crawl timeseries tables (crawl_batches, naver_ad_history, naver_rent_articles)

Revision ID: b3d9a1c47e02
Revises: f7f36f1f8d55
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision = 'b3d9a1c47e02'
down_revision = 'f7f36f1f8d55'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crawl_batches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='uploading'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_crawl_batches_kind_status', 'crawl_batches', ['kind', 'status', 'completed_at'])

    op.create_table(
        'naver_ad_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(), nullable=True),
        sa.Column('lat', sa.Float(precision=53), nullable=True),
        sa.Column('lon', sa.Float(precision=53), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['crawl_batches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_nah_batch_addr', 'naver_ad_history', ['batch_id', 'address'])

    op.create_table(
        'naver_rent_articles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('article_no', sa.Text(), nullable=False),
        sa.Column('deposit', sa.Numeric(), nullable=True),
        sa.Column('rent', sa.Numeric(), nullable=True),
        sa.Column('floor_info', sa.Text(), nullable=True),
        sa.Column('floor_num', sa.SmallInteger(), nullable=True),
        sa.Column('area_contract', sa.Float(), nullable=True),
        sa.Column('area_exclusive', sa.Float(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('lat', sa.Float(precision=53), nullable=True),
        sa.Column('lon', sa.Float(precision=53), nullable=True),
        sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['crawl_batches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id', 'article_no', name='uq_nra_batch_article'),
    )
    op.create_index('idx_nra_batch', 'naver_rent_articles', ['batch_id'])
    op.create_index('idx_nra_geom', 'naver_rent_articles', ['geom'], postgresql_using='gist')


def downgrade():
    op.drop_index('idx_nra_geom', table_name='naver_rent_articles')
    op.drop_index('idx_nra_batch', table_name='naver_rent_articles')
    op.drop_table('naver_rent_articles')
    op.drop_index('idx_nah_batch_addr', table_name='naver_ad_history')
    op.drop_table('naver_ad_history')
    op.drop_index('idx_crawl_batches_kind_status', table_name='crawl_batches')
    op.drop_table('crawl_batches')
