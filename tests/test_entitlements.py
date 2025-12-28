import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, GroupEntitlement
from app.services import entitlements


def create_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_free_plan_defaults():
    session = create_session()
    result = entitlements.for_group(session, group_id=1)
    assert result.plan == "free"
    assert result.max_participants == 20
    assert not result.features


def test_pro_plan_features():
    session = create_session()
    session.add(GroupEntitlement(group_id=1, plan="pro", valid_until=None))
    session.commit()

    result = entitlements.for_group(session, group_id=1)
    assert result.plan == "pro"
    assert entitlements.FEATURE_WISHLIST in result.features


def test_expired_plan_falls_back_to_free():
    session = create_session()
    expired = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    session.add(GroupEntitlement(group_id=1, plan="pro", valid_until=expired))
    session.commit()

    result = entitlements.for_group(session, group_id=1)
    assert result.plan == "free"
    assert result.max_participants == 20
