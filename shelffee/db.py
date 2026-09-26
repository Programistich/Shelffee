import secrets
from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, Float, ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from shelffee.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Shelf(Base):
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    share_token: Mapped[str] = mapped_column(
        String(32), unique=True, default=lambda: secrets.token_urlsafe(12)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members: Mapped[list["ShelfMember"]] = relationship(
        back_populates="shelf", cascade="all, delete-orphan"
    )
    coffees: Mapped[list["Coffee"]] = relationship(
        back_populates="shelf", cascade="all, delete-orphan"
    )


class ShelfMember(Base):
    __tablename__ = "shelf_members"

    shelf_id: Mapped[int] = mapped_column(
        ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shelf: Mapped[Shelf] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Coffee(Base):
    __tablename__ = "coffees"

    id: Mapped[int] = mapped_column(primary_key=True)
    shelf_id: Mapped[int] = mapped_column(
        ForeignKey("shelves.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    country: Mapped[str] = mapped_column(String(64))
    flavor_notes: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    roast: Mapped[str] = mapped_column(String(16))
    weight_grams: Mapped[int]
    process: Mapped[str] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(128))
    variety: Mapped[str | None] = mapped_column(String(128))
    altitude_masl: Mapped[int | None]
    farm: Mapped[str | None] = mapped_column(String(128))
    sensory_scale: Mapped[int | None]
    acidity: Mapped[int | None]
    sweetness: Mapped[int | None]
    bitterness: Mapped[int | None]
    body: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shelf: Mapped[Shelf] = relationship(back_populates="coffees")
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="coffee", cascade="all, delete-orphan"
    )


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    coffee_id: Mapped[int] = mapped_column(
        ForeignKey("coffees.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(32))
    dose_grams: Mapped[float] = mapped_column(Float)
    grind: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    coffee: Mapped[Coffee] = relationship(back_populates="recipes")


engine = create_async_engine(settings.database_url)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def upsert_user(user_id: int, username: str | None, first_name: str) -> User:
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(id=user_id, username=username, first_name=first_name)
            session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_seen_at = func.now()
        await session.commit()
        await session.refresh(user)
        return user


async def join_shelf_by_token(share_token: str, user_id: int) -> Shelf | None:
    async with SessionFactory() as session:
        shelf = await session.scalar(
            select(Shelf).where(Shelf.share_token == share_token)
        )
        if shelf is None:
            return None
        membership = await session.get(ShelfMember, (shelf.id, user_id))
        if membership is None:
            session.add(ShelfMember(shelf_id=shelf.id, user_id=user_id, role="member"))
            await session.commit()
        return shelf


async def list_shelves(user_id: int) -> list[Shelf]:
    async with SessionFactory() as session:
        result = await session.scalars(
            select(Shelf)
            .join(ShelfMember)
            .where(ShelfMember.user_id == user_id)
            .order_by(Shelf.created_at)
        )
        return list(result)


async def create_shelf(name: str, user_id: int) -> Shelf:
    async with SessionFactory() as session:
        shelf = Shelf(name=name)
        shelf.members.append(ShelfMember(user_id=user_id, role="owner"))
        session.add(shelf)
        await session.commit()
        await session.refresh(shelf)
        return shelf


async def get_shelf_for_user(shelf_id: int, user_id: int) -> Shelf | None:
    async with SessionFactory() as session:
        return await session.scalar(
            select(Shelf)
            .join(ShelfMember)
            .where(Shelf.id == shelf_id, ShelfMember.user_id == user_id)
        )


async def get_shelf_role(shelf_id: int, user_id: int) -> str | None:
    async with SessionFactory() as session:
        membership = await session.get(ShelfMember, (shelf_id, user_id))
        return membership.role if membership else None


async def update_shelf(shelf_id: int, name: str) -> Shelf:
    async with SessionFactory() as session:
        shelf = await session.get(Shelf, shelf_id)
        shelf.name = name
        await session.commit()
        await session.refresh(shelf)
        return shelf


async def delete_shelf(shelf_id: int) -> None:
    async with SessionFactory() as session:
        await session.delete(await session.get(Shelf, shelf_id))
        await session.commit()


async def list_coffees(shelf_id: int) -> list[Coffee]:
    async with SessionFactory() as session:
        result = await session.scalars(
            select(Coffee).where(Coffee.shelf_id == shelf_id).order_by(Coffee.created_at.desc())
        )
        return list(result)


async def create_coffee(shelf_id: int, **fields) -> Coffee:
    async with SessionFactory() as session:
        coffee = Coffee(shelf_id=shelf_id, **fields)
        session.add(coffee)
        await session.commit()
        await session.refresh(coffee)
        return coffee


async def get_coffee_for_user(coffee_id: int, user_id: int) -> Coffee | None:
    async with SessionFactory() as session:
        return await session.scalar(
            select(Coffee)
            .join(Shelf)
            .join(ShelfMember)
            .where(Coffee.id == coffee_id, ShelfMember.user_id == user_id)
        )


async def update_coffee(coffee_id: int, **fields) -> Coffee:
    async with SessionFactory() as session:
        coffee = await session.get(Coffee, coffee_id)
        for key, value in fields.items():
            setattr(coffee, key, value)
        await session.commit()
        await session.refresh(coffee)
        return coffee


async def delete_coffee(coffee_id: int) -> None:
    async with SessionFactory() as session:
        await session.delete(await session.get(Coffee, coffee_id))
        await session.commit()


async def list_recipes(coffee_id: int) -> list[Recipe]:
    async with SessionFactory() as session:
        result = await session.scalars(
            select(Recipe).where(Recipe.coffee_id == coffee_id).order_by(Recipe.created_at.desc())
        )
        return list(result)


async def create_recipe(coffee_id: int, **fields) -> Recipe:
    async with SessionFactory() as session:
        recipe = Recipe(coffee_id=coffee_id, **fields)
        session.add(recipe)
        await session.commit()
        await session.refresh(recipe)
        return recipe
