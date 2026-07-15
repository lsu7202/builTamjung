"""seoul_land_info 통합주소 복원 (외부 데이터 조인 전용 파생 컬럼)

- 검색이 PNU 기반으로 전환되며 삭제됐던 컬럼이나, 네이버 크롤링(임대/매매) 주소 조인과
  기존 API(/api/floors, 실거래가/AI추정가 업로드, 주소목록 조회)가 이 컬럼을 참조하므로 복원한다.
- 값은 시도+시군구+주소 조합으로 백필. 이미 컬럼/값이 있는 환경(로컬)에서도 안전하도록
  전부 IF NOT EXISTS / IS NULL 조건의 멱등 SQL로 작성.

Revision ID: c4e8f2a91b37
Revises: b3d9a1c47e02
Create Date: 2026-07-15

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c4e8f2a91b37'
down_revision = 'b3d9a1c47e02'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE seoul_land_info ADD COLUMN IF NOT EXISTS "통합주소" text')
    op.execute('''
        UPDATE seoul_land_info
           SET "통합주소" = TRIM(
                   COALESCE("시도", '') || ' ' ||
                   COALESCE("시군구", '') || ' ' ||
                   COALESCE("주소", '')
               )
         WHERE "통합주소" IS NULL
    ''')
    op.execute('CREATE INDEX IF NOT EXISTS idx_sli_full_addr ON seoul_land_info ("통합주소")')


def downgrade():
    op.execute('DROP INDEX IF EXISTS idx_sli_full_addr')
    op.execute('ALTER TABLE seoul_land_info DROP COLUMN IF EXISTS "통합주소"')
