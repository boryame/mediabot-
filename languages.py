LANGS = {
    "uz": {
        "start_msg":     "👋 Xush kelibsiz!\n\n🎬 Kino, serial, anime va boshqalar shu yerda!\n\nQuyidagi bo'limlardan birini tanlang:",
        "movies":        "🎬 Kinolar",
        "serials":       "📺 Seriallar",
        "anime":         "🎌 Anime",
        "cartoons":      "🎠 Multfilmlar",
        "drama":         "🎭 Dramalar",
        "random":        "🎲 Tasodifiy",
        "search":        "🔍 Qidirish",
        "vip":           "💎 VIP",
        "lang_btn":      "🌐 Til",
        "contact_admin": "📩 Murojaat",
        "back":          "🔙 Orqaga",
        "menu":          "🏠 Bosh menyu",
        "cancel":        "❌ Bekor",

        "search_prompt": "🔍 Kino nomini yozing:",
        "no_results":    "❌ Hech narsa topilmadi",
        "no_movies":     "❌ Hozircha kino yo'q",

        "sub_required":  "⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:",
        "sub_check":     "✅ Obunani tekshirish",
        "sub_ok":        "✅ Obuna tasdiqlandi!",
        "sub_fail":      "❌ Hali barcha kanallarga obuna bo'lmadingiz!",

        "vip_only":      "💎 Bu kontent faqat VIP uchun!\n\nVIP bo'lish uchun quyidagi tugmani bosing:",
        "vip_active":    "💎 VIP faol! Muddati: {date}",
        "vip_buy":       "💳 VIP sotib olish",

        "movie_info":    "🎬 *{title}*\n\n📅 Yil: {year}\n⭐ Reyting: {rating}\n🌍 Mamlakat: {country}\n📝 Janr: {genre}\n\n📖 {description}",
        "watch":         "▶️ Ko'rish",
        "rate":          "⭐ Baho berish",
        "rated":         "✅ Bahoyingiz qabul qilindi!",

        "contact_prompt": "📩 Xabaringizni yozing, admin ko'rib chiqadi:",
        "contact_sent":   "✅ Xabar adminga yuborildi! Tez orada javob berishadi.",

        "admin_reply_sent": "✅ Javob yuborildi!",
        "admin_reply_fail": "❌ Xabar yuborib bo'lmadi!",
    },
    "ru": {
        "start_msg":     "👋 Добро пожаловать!\n\n🎬 Фильмы, сериалы, аниме и многое другое!\n\nВыберите раздел:",
        "movies":        "🎬 Фильмы",
        "serials":       "📺 Сериалы",
        "anime":         "🎌 Аниме",
        "cartoons":      "🎠 Мультфильмы",
        "drama":         "🎭 Дорамы",
        "random":        "🎲 Случайное",
        "search":        "🔍 Поиск",
        "vip":           "💎 VIP",
        "lang_btn":      "🌐 Язык",
        "contact_admin": "📩 Связь",
        "back":          "🔙 Назад",
        "menu":          "🏠 Главное меню",
        "cancel":        "❌ Отмена",

        "search_prompt": "🔍 Введите название фильма:",
        "no_results":    "❌ Ничего не найдено",
        "no_movies":     "❌ Фильмов пока нет",

        "sub_required":  "⚠️ Для использования бота подпишитесь на каналы:",
        "sub_check":     "✅ Проверить подписку",
        "sub_ok":        "✅ Подписка подтверждена!",
        "sub_fail":      "❌ Вы не подписаны на все каналы!",

        "vip_only":      "💎 Этот контент только для VIP!\n\nНажмите кнопку для оформления:",
        "vip_active":    "💎 VIP активен! Дата окончания: {date}",
        "vip_buy":       "💳 Купить VIP",

        "movie_info":    "🎬 *{title}*\n\n📅 Год: {year}\n⭐ Рейтинг: {rating}\n🌍 Страна: {country}\n📝 Жанр: {genre}\n\n📖 {description}",
        "watch":         "▶️ Смотреть",
        "rate":          "⭐ Оценить",
        "rated":         "✅ Ваша оценка принята!",

        "contact_prompt": "📩 Напишите сообщение, админ рассмотрит его:",
        "contact_sent":   "✅ Сообщение отправлено админу! Скоро ответят.",

        "admin_reply_sent": "✅ Ответ отправлен!",
        "admin_reply_fail": "❌ Не удалось отправить сообщение!",
    }
}


def t(lang, key, **kwargs):
    text = LANGS.get(lang, LANGS["uz"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text
