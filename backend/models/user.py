from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped
from sqlalchemy.testing.schema import mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):


    __tablename__ = "users"

    id:Mapped[int] = mapped_column(primary_key = True,autoincrement = True,)
    username: Mapped[str] = mapped_column(String(50),nullable=False,)
    email:Mapped[str] = mapped_column(String(100),unique = True,nullable = False)
    password: Mapped[str] = mapped_column(String(255), nullable=False, )
