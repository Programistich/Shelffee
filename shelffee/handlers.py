from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from shelffee.config import settings
from shelffee.db import join_shelf_by_token, upsert_user

router = Router()


def webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Відкрити Shelffee",
                    web_app=WebAppInfo(url=settings.webapp_url),
                )
            ]
        ]
    )


@router.message(CommandStart(deep_link=True, magic=F.args.startswith("share_")))
async def start_share(message: Message, command: CommandObject) -> None:
    await upsert_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    shelf = await join_shelf_by_token(command.args.removeprefix("share_"), message.from_user.id)
    if shelf is None:
        await message.answer("Посилання недійсне або полицю видалено.")
        return
    await message.answer(
        f"Тепер у вас є доступ до полиці «{shelf.name}».",
        reply_markup=webapp_keyboard(),
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await upsert_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await message.answer(
        f"Привіт, {message.from_user.first_name}! Це Shelffee.",
        reply_markup=webapp_keyboard(),
    )
