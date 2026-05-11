from telegram.error import TelegramError
from database import get_subscriptions


async def check_subscription(uid: int, context) -> list:
    """
    Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi.
    Bo'sh ro'yxat = hammasi OK.
    """
    channels = get_subscriptions()
    not_subbed = []

    for ch in channels:
        try:
            member = await context.bot.get_chat_member(
                chat_id=ch["channel_id"],
                user_id=uid
            )
            if member.status in ("member", "administrator", "creator"):
                continue
            else:
                not_subbed.append(dict(ch))
        except TelegramError:
            # Bot kanalga kira olmasa — o'tkazib yuboramiz
            pass

    return not_subbed
