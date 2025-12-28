from aiogram import Router

from app.bot.handlers import group_game, start, upgrade, wishlist

router = Router()
router.include_router(start.router)
router.include_router(group_game.router)
router.include_router(wishlist.router)
router.include_router(upgrade.router)
