from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from .database import Base


class User(Base):
    """Someone who has signed in. Created on demand from the email Cloudflare
    Access vouches for - there is no password or sign-up form (app/auth.py).

    Anything a person creates should carry their id so they only ever see
    their own: give the table a non-null `owner_id = Column(Integer,
    ForeignKey("users.id"), nullable=False)` and filter EVERY query on it
    (see the README's "Accounts" section). Emails are stored lowercased."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Define your SQLAlchemy models here, e.g.:
#
# from sqlalchemy import ForeignKey
#
# class Thing(Base):
#     __tablename__ = "things"
#
#     id = Column(Integer, primary_key=True)
#     owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     name = Column(String, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow)
