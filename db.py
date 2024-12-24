from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import select
from config import DATABASE_URL
from typing import List, Optional


engine = create_engine(DATABASE_URL)
Base = declarative_base()

association_table = Table(
    'group_participants',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id'))
)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(String, nullable=False)
    has_private_chat = Column(Boolean, default=False)

    groups = relationship(
        "Group",
        secondary=association_table,
        back_populates="participants"
    )

    def __repr__(self):
      return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.telegram_username}, has_private_chat={self.has_private_chat})>"


class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    is_active = Column(Integer, default=1)

    participants = relationship(
        "User",
        secondary=association_table,
        back_populates="groups"
    )

    def __repr__(self):
        return f"<Group(id={self.id}, telegram_id={self.telegram_id}, participants={[p.telegram_username for p in self.participants]})>"


Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def create_user(session, telegram_id, telegram_username):
    new_user = User(telegram_id=telegram_id, telegram_username=telegram_username)
    session.add(new_user)
    try:
        session.commit()
        return new_user
    except IntegrityError:
        session.rollback()
        return None

def get_user_by_telegram_username(session, telegram_username) -> Optional[User]:
    return session.query(User).filter(User.telegram_username == telegram_username).first()

def get_user_by_telegram_id(session, telegram_id) -> Optional[User]:
    return session.query(User).filter(User.telegram_id == telegram_id).first()

def set_user_has_private_chat(session, telegram_id):
    user = session.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.has_private_chat = True
        session.commit()
        return True
    return False

def create_group(session, telegram_id):
    new_group = Group(telegram_id=telegram_id)
    session.add(new_group)
    try:
        session.commit()
        return new_group
    except IntegrityError:
        session.rollback()
        return None

def get_group_by_telegram_id(session, telegram_id) -> Optional[Group]:
    return session.query(Group).filter(Group.telegram_id == telegram_id).first()


def add_user_to_group(session, user:User, group: Group):
     if user in group.participants:
         return False
     group.participants.append(user)
     session.commit()
     return True


def get_group_participants(session, group_id) -> Optional[List[User]]:
  group = session.query(Group).filter(Group.id == group_id).first()
  if group:
      return group.participants
  return None

def set_group_inactive(session, telegram_id):
    group = session.query(Group).filter(Group.telegram_id == telegram_id).first()
    if group:
      group.is_active = 0
      session.commit()
      return True
    return False