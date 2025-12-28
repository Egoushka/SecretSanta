from aiogram.utils.keyboard import InlineKeyboardBuilder


def join_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Join Secret Santa!", callback_data="join")
    return keyboard.as_markup()


def confirm_end_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Yes, End Secret Santa!", callback_data="confirm_end")
    return keyboard.as_markup()
