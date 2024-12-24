import asyncio
import logging
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from config import BOT_TOKEN
import random
from db import Session, create_user, get_user_by_telegram_username, get_user_by_telegram_id, create_group, get_group_by_telegram_id, add_user_to_group, get_group_participants, set_group_inactive, set_user_has_private_chat

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    if message.chat.type == 'private':
        session = Session()
        set_user_has_private_chat(session, message.from_user.id)
        session.close()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Join Secret Santa!", callback_data="join")
    await message.answer(f"Hello, {message.from_user.first_name}! \n\nPlease make sure to start a private chat with me first (by sending me /start), then click the button below to join the Secret Santa game.\n",
                         reply_markup=keyboard.as_markup())

@dp.message(lambda message: message.chat.type == 'private')
async def private_message_handler(message: types.Message):
    session = Session()
    set_user_has_private_chat(session, message.from_user.id)
    session.close()
    await message.answer("Thanks for starting a private chat with me.")

@dp.callback_query(lambda c: c.data == 'join')
async def join_callback_handler(query: types.CallbackQuery):
    session = Session()
    user_telegram_username = query.from_user.username
    user_telegram_id = query.from_user.id
    group_telegram_id = query.message.chat.id
    user = get_user_by_telegram_id(session, user_telegram_id)
    if not user:
      user = create_user(session, user_telegram_id, user_telegram_username)
    group = get_group_by_telegram_id(session, group_telegram_id)
    if not group:
        group = create_group(session, group_telegram_id)
    if user and group:
        if add_user_to_group(session, user, group):
            await query.answer("You have joined the Secret Santa game!", show_alert=True)
        else:
             await query.answer("You are already in this Secret Santa game!", show_alert=True)
    else:
        await query.answer("Error joining the Secret Santa game. Please try again later.", show_alert=True)
    session.close()


@dp.message(Command('end'))
async def end_command_handler(message: types.Message):
    session = Session()
    group_telegram_id = message.chat.id
    group = get_group_by_telegram_id(session, group_telegram_id)

    if not group or group.is_active == 0:
        await message.answer("This group is not currently active in Secret Santa.")
        session.close()
        return

    participants = get_group_participants(session, group.id)

    if not participants or len(participants) < 2:
        await message.answer("Not enough participants to start Secret Santa.")
        session.close()
        return


    non_interacted_users = [p.telegram_username for p in participants if not p.has_private_chat]

    if non_interacted_users:
        users_str = ", ".join([f"@{user}" for user in non_interacted_users])
        await message.answer(f"The following users need to start a private chat with the bot before Secret Santa can start: {users_str}")
        session.close()
        return


    random.shuffle(participants)
    givers = participants[:]
    receivers = participants[1:] + [participants[0]]
    for giver, receiver in zip(givers, receivers):
        if giver and receiver:
            logging.info(f"Sending to user ID: {giver.telegram_id}, username: {giver.telegram_username}")
            try:
                await bot.send_message(giver.telegram_id,
                                       f"Secret Santa: You're giving a gift to @{receiver.telegram_username}!",
                                        parse_mode=ParseMode.HTML)
            except Exception as e:
               logging.error(f"Error sending to {giver.telegram_username} : {e}")
               if "chat not found" in str(e).lower():
                   logging.warning(f"User {giver.telegram_username} has not started private chat with the bot.")


    set_group_inactive(session, group_telegram_id)
    await message.answer("Secret Santa distribution completed! Check your private messages.")
    session.close()


async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())