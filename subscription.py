from telegram.error import TelegramError
from database import get_subscriptions


async def check_subscription(uid: int, context) -> list:
    channels = get_subscriptions()
    not_subbed = []

    for ch in channels:
        try:
            member = await context.bot.get_chat_member(
                chat_id=ch["channel_id"],
                user_id=uid
            )
            if member.status not in ("member", "administrator", "creator"):
                not_subbed.append(dict(ch))
        except TelegramError:
            # Bot kanalga kira olmasa — obuna kerak deb hisoblaymiz
            not_subbed.append(dict(ch))

    return not_subbed
