from sqlmodel import Field, SQLModel


class NewsProvider(SQLModel, table=True):
    __tablename__ = "news_providers"

    id: int | None = Field(primary_key=True)
    title: str = Field(unique=True, max_length=255)
    description: str | None
    priority: int | None
