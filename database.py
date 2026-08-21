from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = f"sqlite:///{Path(__file__).with_name('stockbuddy.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
