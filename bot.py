import logging
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                       LabeledPrice, ChatJoinRequest, ReplyKeyboardMarkup, KeyboardButton)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, PreCheckoutQueryHandler,
                           ChatJoinRequestHandler, InlineQueryHandler,
                           filters, ContextTypes)
from config import BOT_TOKEN, ADMIN_IDS, VIP_STARS
from database import *
from languages import t
from subscription import check_subscription

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ═══════════════════════════════════════════════════════
# HOLATLAR (STATE)
# ═══════════════════════════════════════════════════════

user_states  = {}   # { uid: "searching" | "contact_admin" | "admin_reply_12345" }
admin_states = {}   # { uid: {"step": "...", ...} }

CATEGORIES = {
    "movie":   "🎬 Kinolar",
    "serial":  "📺 Seriallar",
    "anime":   "🎌 Anime",
    "cartoon": "🎠 Multfilmlar",
    "drama":   "🎭 Dramalar",
}

# ═══════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════

def bottom_kb():
    """Har doim pastda ko'rinadigan tugma"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Bosh menyu")]],
        resize_keyboard=True,
        persistent=True
    )


def main_menu_kb(lang, adm=False):
    kb = [
        [InlineKeyboardButton(t(lang, "movies"),   callback_data="cat_movie"),
         InlineKeyboardButton(t(lang, "serials"),  callback_data="cat_serial")],
        [InlineKeyboardButton(t(lang, "contact_admin"), callback_data="contact_admin"),
         InlineKeyboardButton(t(lang, "lang_btn"),      callback_data="lang")],
    ]
    if adm:
        kb.append([InlineKeyboardButton("👑 Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="set_lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
    ]])


def back_menu_kb(lang):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "menu"), callback_data="menu")
    ]])


def movies_list_kb(movies, category, lang, page=0, per_page=12):
    kb = []
    row = []
    for m in movies:
        vip = "💎 " if m["is_vip"] else ""
        btn = InlineKeyboardButton(f"{vip}{m['title']}", callback_data=f"movie_{m['id']}")
        row.append(btn)
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{category}_{page - 1}"))
    total = count_movies_by_category(category)
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{category}_{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(t(lang, "menu"), callback_data="menu")])
    return InlineKeyboardMarkup(kb)


def movie_kb(movie, lang):
    kb = [
        [InlineKeyboardButton(t(lang, "watch"), callback_data=f"watch_{movie['id']}")],
        [InlineKeyboardButton(t(lang, "rate"),  callback_data=f"rate_{movie['id']}")],
        [InlineKeyboardButton(t(lang, "back"),  callback_data=f"cat_{movie['category']}")],
    ]
    return InlineKeyboardMarkup(kb)


def movie_text(movie, lang):
    return t(lang, "movie_info",
             title=movie["title"],
             year=movie["year"] or "—",
             rating=movie["rating"] or "—",
             country=movie["country"] or "—",
             genre=movie["genre"] or "—",
             description=movie["description"] or "—")


# ═══════════════════════════════════════════════════════
# OBUNA TEKSHIRISH — YORDAMCHI
# ═══════════════════════════════════════════════════════

async def show_sub_required(target, context, channels, lang):
    kb = [[InlineKeyboardButton(f"📢 {ch['channel_name']}", url=ch["channel_url"])]
          for ch in channels]
    kb.append([InlineKeyboardButton(t(lang, "sub_check"), callback_data="check_sub")])
    text = t(lang, "sub_required")
    if hasattr(target, "message"):
        await target.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        try:
            await target.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        except:
            await target.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


# ═══════════════════════════════════════════════════════
# /START
# ═══════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.full_name, user.username)

    if user.id in ADMIN_IDS:
        add_admin(user.id, user.id)

    db_user = get_user(user.id)
    lang = get_user_lang(user.id)

    # Birinchi marta — til tanlash
    if not db_user["lang"]:
        await update.message.reply_text(
            "🌐 Tilni tanlang / Выберите язык:",
            reply_markup=lang_kb()
        )
        return

    # Obuna tekshirish
    not_subbed = await check_subscription(user.id, context)
    if not_subbed:
        await show_sub_required(update, context, not_subbed, lang)
        return

    # Pastki tugmani ko'rsat
    await update.message.reply_text("👇", reply_markup=bottom_kb())

    await update.message.reply_text(
        t(lang, "start_msg"),
        reply_markup=main_menu_kb(lang, is_admin(user.id)),
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════
# CALLBACK HANDLER — ASOSIY
# ═══════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    d    = query.data
    lang = get_user_lang(uid)

    # ── TIL TANLASH ───────────────────────────────────
    if d.startswith("set_lang_"):
        new_lang = d.replace("set_lang_", "")
        set_user_lang(uid, new_lang)
        lang = new_lang
        not_subbed = await check_subscription(uid, context)
        if not_subbed:
            await show_sub_required(query, context, not_subbed, lang)
            return
        await query.edit_message_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    if d == "lang":
        await query.edit_message_text(
            "🌐 Tilni tanlang / Выберите язык:",
            reply_markup=lang_kb()
        )
        return

    # ── BOSH MENYU ────────────────────────────────────
    if d == "menu":
        not_subbed = await check_subscription(uid, context)
        if not_subbed:
            await show_sub_required(query, context, not_subbed, lang)
            return
        await query.edit_message_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    # ── OBUNA TEKSHIRISH ──────────────────────────────
    if d == "check_sub":
        not_subbed = await check_subscription(uid, context)
        if not_subbed:
            await query.answer(t(lang, "sub_fail"), show_alert=True)
            await show_sub_required(query, context, not_subbed, lang)
        else:
            await query.answer(t(lang, "sub_ok"), show_alert=True)
            await query.edit_message_text(
                t(lang, "start_msg"),
                reply_markup=main_menu_kb(lang, is_admin(uid)),
                parse_mode="Markdown"
            )
        return

    # ── ADMIN CALLBACKLAR ─────────────────────────────
    if is_admin(uid) and (
        d == "admin_panel" or d.startswith("adm_") or
        d.startswith("sub_type_") or d.startswith("del_sub_") or
        d.startswith("cat_sel_") or d.startswith("adm_ep_") or
        d.startswith("adm_new_season_") or d.startswith("adm_add_ep_") or
        d.startswith("vip_give_") or d.startswith("reply_to_") or
        d in ("movie_vip_yes", "movie_vip_no", "movie_skip_poster")
    ):
        await admin_callback(query, context, uid, d, lang)
        return

    # ── USER CALLBACKLAR ──────────────────────────────
    await user_callback(query, context, uid, d, lang)


# ═══════════════════════════════════════════════════════
# USER CALLBACK
# ═══════════════════════════════════════════════════════

async def user_callback(query, context, uid, d, lang):

    # ── KATEGORIYA ────────────────────────────────────
    if d.startswith("cat_"):
        category = d.replace("cat_", "")
        movies = get_movies_by_category(category)
        cat_name = CATEGORIES.get(category, category)
        if not movies:
            await query.edit_message_text(
                f"{cat_name}\n\n{t(lang, 'no_movies')}",
                reply_markup=back_menu_kb(lang)
            )
            return
        await query.edit_message_text(
            f"{cat_name} — *{count_movies_by_category(category)} ta*",
            reply_markup=movies_list_kb(movies, category, lang),
            parse_mode="Markdown"
        )

    # ── SAHIFALASH ────────────────────────────────────
    elif d.startswith("page_"):
        parts = d.split("_")
        category = parts[1]
        page = int(parts[2])
        movies = get_movies_by_category(category, offset=page * 12)
        await query.edit_message_text(
            f"{CATEGORIES.get(category, category)}",
            reply_markup=movies_list_kb(movies, category, lang, page),
            parse_mode="Markdown"
        )

    # ── KINO KARTOCHKA ────────────────────────────────
    elif d.startswith("movie_"):
        movie_id = int(d.replace("movie_", ""))
        movie = get_movie(movie_id)
        if not movie:
            await query.answer("❌ Topilmadi!", show_alert=True)
            return

        if movie["is_vip"] and not is_vip(uid):
            await query.edit_message_text(
                t(lang, "vip_only"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "vip_buy"), callback_data="vip")],
                    [InlineKeyboardButton(t(lang, "back"),    callback_data=f"cat_{movie['category']}")],
                ])
            )
            return

        add_view(uid, movie_id)
        text = movie_text(movie, lang)

        if movie["poster_id"]:
            try:
                await query.message.reply_photo(
                    photo=movie["poster_id"],
                    caption=text,
                    reply_markup=movie_kb(movie, lang),
                    parse_mode="Markdown"
                )
                await query.message.delete()
                return
            except:
                pass

        await query.edit_message_text(
            text,
            reply_markup=movie_kb(movie, lang),
            parse_mode="Markdown"
        )

    # ── KO'RISH ───────────────────────────────────────
    elif d.startswith("watch_"):
        movie_id = int(d.replace("watch_", ""))
        movie = get_movie(movie_id)
        if not movie:
            await query.answer("❌ Topilmadi!", show_alert=True)
            return

        protect = get_setting("forward_enabled") == "0"

        if movie["category"] in ("serial", "anime", "drama"):
            seasons = get_seasons(movie_id)
            if seasons:
                kb = [[InlineKeyboardButton(
                    f"📂 {s['season_num']}-Fasl",
                    callback_data=f"season_{movie_id}_{s['id']}"
                )] for s in seasons]
                kb.append([InlineKeyboardButton(t(lang, "back"), callback_data=f"movie_{movie_id}")])
                await query.edit_message_text(
                    f"📂 *{movie['title']}*\n\nFaslni tanlang:",
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="Markdown"
                )
            else:
                eps = get_episodes(movie_id)
                await show_episodes(query, eps, movie, lang)
        else:
            eps = get_episodes(movie_id)
            if eps:
                try:
                    await context.bot.send_video(
                        chat_id=uid,
                        video=eps[0]["file_id"],
                        caption=f"🎬 *{movie['title']}*",
                        protect_content=protect,
                        parse_mode="Markdown"
                    )
                    await query.answer("✅ Yuborildi!")
                except:
                    await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
            else:
                await query.answer("❌ Fayl topilmadi!", show_alert=True)

    # ── FASL ──────────────────────────────────────────
    elif d.startswith("season_"):
        parts = d.split("_")
        movie_id  = int(parts[1])
        season_id = int(parts[2])
        movie = get_movie(movie_id)
        eps = get_episodes(movie_id, season_id)
        await show_episodes(query, eps, movie, lang, season_id)

    # ── ALOHIDA QISM ──────────────────────────────────
    elif d.startswith("ep_"):
        ep_id = int(d.replace("ep_", ""))
        conn = get_conn()
        ep = conn.execute("SELECT * FROM episodes WHERE id=?", (ep_id,)).fetchone()
        conn.close()
        if ep:
            protect = get_setting("forward_enabled") == "0"
            try:
                await context.bot.send_video(
                    chat_id=uid,
                    video=ep["file_id"],
                    caption=f"📺 {ep['episode_num']}-qism",
                    protect_content=protect
                )
                await query.answer("✅ Yuborildi!")
            except:
                await query.answer("❌ Xatolik!", show_alert=True)
        else:
            await query.answer("❌ Topilmadi!", show_alert=True)

    # ── BARCHA QISMLAR ────────────────────────────────
    elif d.startswith("all_eps_"):
        parts = d.split("_")
        movie_id  = int(parts[2])
        season_id = int(parts[3]) if parts[3] != "0" else None
        eps = get_episodes(movie_id, season_id)
        movie = get_movie(movie_id)
        protect = get_setting("forward_enabled") == "0"
        await query.answer(f"⬇️ {len(eps)} ta qism yuborilmoqda...")
        for ep in eps:
            try:
                await context.bot.send_video(
                    chat_id=uid,
                    video=ep["file_id"],
                    caption=f"📺 {ep['episode_num']}-qism | {movie['title']}",
                    protect_content=protect
                )
            except:
                pass

    # ── BAHO BERISH ───────────────────────────────────
    elif d.startswith("rate_"):
        movie_id = int(d.replace("rate_", ""))
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"⭐{i}", callback_data=f"setrate_{movie_id}_{i}")
            for i in range(1, 6)
        ], [InlineKeyboardButton(t(lang, "back"), callback_data=f"movie_{movie_id}")]])
        await query.edit_message_text("⭐ Baho bering (1 dan 5 gacha):", reply_markup=kb)

    elif d.startswith("setrate_"):
        parts = d.split("_")
        movie_id = int(parts[1])
        rating   = int(parts[2])
        set_rating(uid, movie_id, rating)
        await query.answer(t(lang, "rated"), show_alert=True)
        movie = get_movie(movie_id)
        await query.edit_message_text(
            movie_text(movie, lang),
            reply_markup=movie_kb(movie, lang),
            parse_mode="Markdown"
        )

    # ── TASODIFIY ─────────────────────────────────────
    elif d == "random":
        movie = get_random_movie()
        if not movie:
            await query.answer("❌ Hech qanday kino yo'q!", show_alert=True)
            return
        if movie["is_vip"] and not is_vip(uid):
            movie = get_random_movie()
        if movie:
            add_view(uid, movie["id"])
            await query.edit_message_text(
                movie_text(movie, lang),
                reply_markup=movie_kb(movie, lang),
                parse_mode="Markdown"
            )

    # ── QIDIRUV ───────────────────────────────────────
    elif d == "search":
        user_states[uid] = "searching"
        await query.edit_message_text(
            t(lang, "search_prompt"),
            reply_markup=back_menu_kb(lang)
        )

    # ── VIP ───────────────────────────────────────────
    elif d == "vip":
        if is_vip(uid):
            row = get_user(uid)
            await query.edit_message_text(
                t(lang, "vip_active", date=row["vip_until"]),
                reply_markup=back_menu_kb(lang)
            )
        else:
            await query.edit_message_text(
                f"💎 *VIP obuna*\n\n"
                f"✅ Barcha VIP kinolarga kirish\n"
                f"✅ Reklamasiz\n\n"
                f"⭐ 1 oy — {VIP_STARS['1_oy']['stars']} Stars\n"
                f"⭐ 3 oy — {VIP_STARS['3_oy']['stars']} Stars\n"
                f"⭐ 12 oy — {VIP_STARS['12_oy']['stars']} Stars",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"⭐ 1 oy — {VIP_STARS['1_oy']['stars']} Stars",  callback_data="stars_1_oy")],
                    [InlineKeyboardButton(f"⭐ 3 oy — {VIP_STARS['3_oy']['stars']} Stars",  callback_data="stars_3_oy")],
                    [InlineKeyboardButton(f"⭐ 12 oy — {VIP_STARS['12_oy']['stars']} Stars", callback_data="stars_12_oy")],
                    [InlineKeyboardButton(t(lang, "back"), callback_data="menu")],
                ]),
                parse_mode="Markdown"
            )

    # ── STARS TO'LOV ──────────────────────────────────
    elif d.startswith("stars_"):
        plan_key = d.replace("stars_", "")
        plan = VIP_STARS.get(plan_key)
        if plan:
            await context.bot.send_invoice(
                chat_id=uid,
                title=f"💎 VIP — {plan['label']}",
                description=f"MediaBot VIP {plan['label']}ga. Barcha VIP kinolarga kirish!",
                payload=f"vip_{plan_key}",
                currency="XTR",
                prices=[LabeledPrice(label=f"VIP {plan['label']}", amount=plan["stars"])],
            )

    # ── ADMIN BILAN BOG'LANISH ────────────────────────
    elif d == "contact_admin":
        user_states[uid] = "contact_admin"
        await query.edit_message_text(
            t(lang, "contact_prompt"),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "cancel"), callback_data="menu")
            ]])
        )

    # ── ADMIN JAVOB (foydalanuvchi tomonidan) ─────────
    elif d.startswith("reply_to_") and not is_admin(uid):
        pass  # faqat admin uchun


async def show_episodes(query, eps, movie, lang, season_id=None):
    if not eps:
        await query.answer("❌ Qismlar topilmadi!", show_alert=True)
        return
    kb = []
    row = []
    for ep in eps:
        btn = InlineKeyboardButton(f"📺 {ep['episode_num']}", callback_data=f"ep_{ep['id']}")
        row.append(btn)
        if len(row) == 4:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    sid_str = str(season_id) if season_id else "0"
    kb.append([InlineKeyboardButton("⬇️ Barcha qismlar", callback_data=f"all_eps_{movie['id']}_{sid_str}")])
    kb.append([InlineKeyboardButton(t("uz", "back"), callback_data=f"watch_{movie['id']}")])

    await query.edit_message_text(
        f"📺 *{movie['title']}*\n\nQismni tanlang ({len(eps)} ta):",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════
# ADMIN CALLBACK
# ═══════════════════════════════════════════════════════

async def admin_callback(query, context, uid, d, lang):
    if not is_admin(uid):
        await query.answer("🚫 Ruxsat yo'q!", show_alert=True)
        return

    # ── ADMIN PANEL ───────────────────────────────────
    if d == "admin_panel":
        await query.edit_message_text(
            "👑 *Admin panel*",
            reply_markup=admin_menu_kb(),
            parse_mode="Markdown"
        )

    # ── STATISTIKA ────────────────────────────────────
    elif d == "adm_stats":
        s = get_stats()
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n"
            f"👥 Foydalanuvchilar: *{s['users']}*\n"
            f"🎬 Kinolar: *{s['movies']}*\n"
            f"👁 Bugungi ko'rishlar: *{s['today_views']}*\n"
            f"📈 Jami ko'rishlar: *{s['total_views']}*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )

    # ── KINO QO'SHISH ─────────────────────────────────
    elif d == "adm_add_movie":
        await query.edit_message_text(
            "🎬 *Kategoriyani tanlang:*",
            reply_markup=category_kb(),
            parse_mode="Markdown"
        )

    elif d.startswith("cat_sel_"):
        category = d.replace("cat_sel_", "")
        cat_names = {"movie": "🎬 Kino", "serial": "📺 Serial",
                     "anime": "🎌 Anime", "cartoon": "🎠 Multfilm", "drama": "🎭 Drama"}
        admin_states[uid] = {"step": "movie_title", "category": category, "data": {}}
        await query.edit_message_text(
            f"*{cat_names[category]}* tanlandi.\n\n📝 Kino nomini yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )

    elif d == "movie_vip_yes":
        state = admin_states.get(uid, {})
        state["data"]["is_vip"] = 1
        state["step"] = "movie_poster"
        admin_states[uid] = state
        await query.edit_message_text(
            "🖼 Poster rasmini yuboring:\n_(o'tkazib yuborish uchun tugmani bosing)_",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazish", callback_data="movie_skip_poster")]]),
            parse_mode="Markdown"
        )

    elif d == "movie_vip_no":
        state = admin_states.get(uid, {})
        state["data"]["is_vip"] = 0
        state["step"] = "movie_poster"
        admin_states[uid] = state
        await query.edit_message_text(
            "🖼 Poster rasmini yuboring:\n_(o'tkazib yuborish uchun tugmani bosing)_",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazish", callback_data="movie_skip_poster")]]),
            parse_mode="Markdown"
        )

    elif d == "movie_skip_poster":
        state = admin_states.get(uid, {})
        state["data"]["poster_id"] = None
        state["data"]["added_by"]  = uid
        state["data"]["category"]  = state.get("category", "movie")
        category = state.get("category")
        if category in ("serial", "anime", "drama"):
            movie_id = add_movie(state["data"])
            admin_states.pop(uid, None)
            await query.edit_message_text(
                f"✅ *{state['data']['title']}* qo'shildi! (ID: `{movie_id}`)\n\nEndi qismlarni qo'shishingiz mumkin:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Qism qo'shish", callback_data=f"adm_add_ep_{movie_id}")],
                    [InlineKeyboardButton("🔙 Admin panel",   callback_data="admin_panel")],
                ]),
                parse_mode="Markdown"
            )
        else:
            state["step"] = "add_ep_file"
            state["movie_id"] = None
            state["season_id"] = None
            state["ep_num"] = 1
            admin_states[uid] = state
            await query.edit_message_text("🎬 Video faylni yuboring:")

    # ── KINO O'CHIRISH ────────────────────────────────
    elif d == "adm_del_movie":
        admin_states[uid] = {"step": "del_movie_id"}
        await query.edit_message_text(
            "🗑 O'chirmoqchi bo'lgan kino ID sini yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
        )

    # ── QISM QO'SHISH ─────────────────────────────────
    elif d.startswith("adm_add_ep_"):
        movie_id = int(d.replace("adm_add_ep_", ""))
        movie = get_movie(movie_id)
        if not movie:
            await query.answer("Kino topilmadi!", show_alert=True)
            return
        if movie["category"] in ("serial", "anime", "drama"):
            seasons = get_seasons(movie_id)
            kb = [[InlineKeyboardButton(f"📂 {s['season_num']}-Fasl",
                                        callback_data=f"adm_ep_season_{movie_id}_{s['id']}")] for s in seasons]
            kb.append([InlineKeyboardButton("➕ Yangi fasl", callback_data=f"adm_new_season_{movie_id}")])
            kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
            await query.edit_message_text(
                f"📂 *{movie['title']}*\n\nFaslni tanlang:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
        else:
            admin_states[uid] = {"step": "add_ep_file", "movie_id": movie_id, "season_id": None, "ep_num": 1}
            await query.edit_message_text(
                f"🎬 *{movie['title']}*\n\nVideo faylni yuboring:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]]),
                parse_mode="Markdown"
            )

    elif d.startswith("adm_new_season_"):
        movie_id = int(d.replace("adm_new_season_", ""))
        admin_states[uid] = {"step": "new_season_num", "movie_id": movie_id}
        await query.edit_message_text(
            "📂 Yangi fasl raqamini yozing (1, 2, 3...):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
        )

    elif d.startswith("adm_ep_season_"):
        parts = d.split("_")
        movie_id  = int(parts[3])
        season_id = int(parts[4])
        eps = get_episodes(movie_id, season_id)
        next_ep = len(eps) + 1
        admin_states[uid] = {"step": "add_ep_file", "movie_id": movie_id,
                              "season_id": season_id, "ep_num": next_ep}
        movie = get_movie(movie_id)
        await query.edit_message_text(
            f"📺 *{movie['title']}*\n\n{next_ep}-qismni yuboring (video):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )

    # ── OBUNA BOSHQARISH ──────────────────────────────
    elif d == "adm_subs":
        await query.edit_message_text(
            "📢 *Majburiy obuna:*",
            reply_markup=sub_menu_kb(),
            parse_mode="Markdown"
        )

    elif d == "adm_sub_list":
        subs = get_subscriptions()
        if not subs:
            text = "📋 Hozircha kanal yo'q."
        else:
            text = "📋 *Kanallar:*\n\n"
            for i, s in enumerate(subs, 1):
                text += f"{i}. {s['channel_name']} | `{s['channel_id']}`\n"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="adm_subs")]]),
            parse_mode="Markdown"
        )

    elif d == "adm_sub_add":
        await query.edit_message_text(
            "📢 *Kanal turini tanlang:*",
            reply_markup=sub_type_kb(),
            parse_mode="Markdown"
        )

    elif d.startswith("sub_type_"):
        sub_type = d.replace("sub_type_", "")
        type_names = {"public": "📢 Ommaviy", "private": "🔒 Maxfiy"}
        admin_states[uid] = {"step": "sub_channel_id", "sub_type": sub_type}
        await query.edit_message_text(
            f"*{type_names.get(sub_type, sub_type)}* tanlandi.\n\n"
            f"📝 Kanal ID yoki @username yuboring:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="adm_subs")]]),
            parse_mode="Markdown"
        )

    elif d == "adm_sub_del":
        subs = get_subscriptions()
        if not subs:
            await query.answer("Kanal yo'q!", show_alert=True)
            return
        kb = [[InlineKeyboardButton(f"🗑 {s['channel_name']}", callback_data=f"del_sub_{s['id']}")] for s in subs]
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_subs")])
        await query.edit_message_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("del_sub_"):
        sub_id = int(d.replace("del_sub_", ""))
        remove_subscription(sub_id)
        await query.answer("✅ O'chirildi!", show_alert=True)
        await query.edit_message_text(
            "📢 *Majburiy obuna:*",
            reply_markup=sub_menu_kb(),
            parse_mode="Markdown"
        )

    # ── XABAR YUBORISH ────────────────────────────────
    elif d == "adm_broadcast":
        admin_states[uid] = {"step": "broadcast_text"}
        await query.edit_message_text(
            "📣 Yubormoqchi bo'lgan xabarni yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
        )

    # ── ADMIN QO'SHISH ────────────────────────────────
    elif d == "adm_add_admin":
        admin_states[uid] = {"step": "add_admin_id"}
        await query.edit_message_text(
            "👤 Yangi admin Telegram ID sini yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
        )

    # ── VIP BERISH ────────────────────────────────────
    elif d == "adm_vip":
        admin_states[uid] = {"step": "vip_user_id"}
        await query.edit_message_text(
            "💎 VIP bermoqchi bo'lgan foydalanuvchi ID sini yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])
        )

    elif d.startswith("vip_give_"):
        parts = d.split("_")
        target_id = int(parts[2])
        days = int(parts[3])
        until = set_vip(target_id, days)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Sizga {days} kunlik VIP berildi!\n📅 Muddat: *{until}*",
                parse_mode="Markdown"
            )
        except:
            pass
        await query.edit_message_text(
            f"✅ {target_id} ga {days} kunlik VIP berildi!\nMuddati: {until}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
        )
        admin_states.pop(uid, None)

    # ── SOZLAMALAR ────────────────────────────────────
    elif d == "adm_settings":
        fwd = get_setting("forward_enabled")
        fwd_text = "✅ Forward: Yoqilgan" if fwd == "1" else "🚫 Forward: O'chirilgan"
        await query.edit_message_text(
            "⚙️ *Sozlamalar:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(fwd_text, callback_data="adm_toggle_forward")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")],
            ]),
            parse_mode="Markdown"
        )

    elif d == "adm_toggle_forward":
        current = get_setting("forward_enabled")
        new_val = "0" if current == "1" else "1"
        set_setting("forward_enabled", new_val)
        msg = "✅ Forward yoqildi!" if new_val == "1" else "🚫 Forward o'chirildi!"
        await query.answer(msg, show_alert=True)
        fwd_text = "✅ Forward: Yoqilgan" if new_val == "1" else "🚫 Forward: O'chirilgan"
        await query.edit_message_text(
            "⚙️ *Sozlamalar:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(fwd_text, callback_data="adm_toggle_forward")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")],
            ]),
            parse_mode="Markdown"
        )

    # ── INBOX ─────────────────────────────────────────
    elif d == "adm_inbox":
        msgs = get_messages()
        if not msgs:
            await query.edit_message_text(
                "📩 *Xabarlar*\n\n_Hozircha xabar yo'q._",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]),
                parse_mode="Markdown"
            )
            return
        text = "📩 *Oxirgi xabarlar:*\n\n"
        kb = []
        for m in msgs[:10]:
            short = m["message"][:60] + ("..." if len(m["message"]) > 60 else "")
            text += f"👤 `{m['user_id']}` — {m['full_name']}\n💬 {short}\n🕐 {m['created_at'][:16]}\n\n"
            kb.append([InlineKeyboardButton(
                f"↩️ {m['full_name']} ga javob",
                callback_data=f"reply_to_{m['user_id']}"
            )])
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )

    # ── FOYDALANUVCHIGA JAVOB ─────────────────────────
    elif d.startswith("reply_to_"):
        target_id = int(d.replace("reply_to_", ""))
        admin_states[uid] = {"step": "admin_reply", "target_id": target_id}
        await query.message.reply_text(
            f"✏️ `{target_id}` foydalanuvchiga javob yozing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")
            ]]),
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════
# ADMIN MENYULARI
# ═══════════════════════════════════════════════════════

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo'shish",    callback_data="adm_add_movie"),
         InlineKeyboardButton("🗑 Kino o'chirish",   callback_data="adm_del_movie")],
        [InlineKeyboardButton("📢 Obuna",            callback_data="adm_subs"),
         InlineKeyboardButton("📊 Statistika",       callback_data="adm_stats")],
        [InlineKeyboardButton("📣 Xabar yuborish",   callback_data="adm_broadcast"),
         InlineKeyboardButton("👤 Admin qo'shish",   callback_data="adm_add_admin")],
        [InlineKeyboardButton("💎 VIP berish",       callback_data="adm_vip"),
         InlineKeyboardButton("⚙️ Sozlamalar",       callback_data="adm_settings")],
        [InlineKeyboardButton("📩 Xabarlar",         callback_data="adm_inbox")],
        [InlineKeyboardButton("🔙 Orqaga",           callback_data="menu")],
    ])


def category_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",    callback_data="cat_sel_movie"),
         InlineKeyboardButton("📺 Serial",  callback_data="cat_sel_serial")],
        [InlineKeyboardButton("🎌 Anime",   callback_data="cat_sel_anime"),
         InlineKeyboardButton("🎠 Multfilm",callback_data="cat_sel_cartoon")],
        [InlineKeyboardButton("🎭 Drama",   callback_data="cat_sel_drama")],
        [InlineKeyboardButton("❌ Bekor",   callback_data="admin_panel")],
    ])


def sub_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo'shish",    callback_data="adm_sub_add"),
         InlineKeyboardButton("🗑 Kanal o'chirish",   callback_data="adm_sub_del")],
        [InlineKeyboardButton("📋 Ro'yxat",           callback_data="adm_sub_list")],
        [InlineKeyboardButton("🔙 Orqaga",            callback_data="admin_panel")],
    ])


def sub_type_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Ommaviy kanal", callback_data="sub_type_public")],
        [InlineKeyboardButton("🔒 Maxfiy kanal",  callback_data="sub_type_private")],
        [InlineKeyboardButton("🔙 Bekor",         callback_data="adm_subs")],
    ])


# ═══════════════════════════════════════════════════════
# XABAR HANDLER (MATN)
# ═══════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_lang(uid)

    # ── KOD ORQALI QIDIRISH (#10 yoki /10) ──────────────
    if text.startswith("#") or (text.startswith("/") and text[1:].isdigit()):
        code = text.replace("#", "").replace("/", "").strip()
        if code.isdigit():
            movie = get_movie(int(code))
            if movie:
                protect = get_setting("forward_enabled") == "0"
                add_view(uid, movie["id"])

                # Serial/anime/drama — qismlar ro'yxati
                if movie["category"] in ("serial", "anime", "drama"):
                    seasons = get_seasons(movie["id"])
                    if seasons:
                        kb = [[InlineKeyboardButton(
                            f"📂 {s['season_num']}-Fasl",
                            callback_data=f"season_{movie['id']}_{s['id']}"
                        )] for s in seasons]
                        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu")])
                        await update.message.reply_text(
                            f"📂 *{movie['title']}*\n\nFaslni tanlang:",
                            reply_markup=InlineKeyboardMarkup(kb),
                            parse_mode="Markdown"
                        )
                    else:
                        eps = get_episodes(movie["id"])
                        if eps:
                            kb = []
                            row = []
                            for ep in eps:
                                row.append(InlineKeyboardButton(
                                    f"📺 {ep['episode_num']}",
                                    callback_data=f"ep_{ep['id']}"
                                ))
                                if len(row) == 4:
                                    kb.append(row)
                                    row = []
                            if row:
                                kb.append(row)
                            kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu")])
                            await update.message.reply_text(
                                f"📺 *{movie['title']}*\n\nQismni tanlang ({len(eps)} ta):",
                                reply_markup=InlineKeyboardMarkup(kb),
                                parse_mode="Markdown"
                            )
                        else:
                            await update.message.reply_text("❌ Qismlar topilmadi!")

                # Kino — to'g'ridan video yuborish
                else:
                    eps = get_episodes(movie["id"])
                    if eps:
                        try:
                            await context.bot.send_video(
                                chat_id=uid,
                                video=eps[0]["file_id"],
                                caption=f"🎬 *{movie['title']}*📅 {movie['year'] or ''} | ⭐ {movie['rating'] or ''}",
                                protect_content=protect,
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            await update.message.reply_text(f"❌ Xatolik: {e}")
                    else:
                        await update.message.reply_text("❌ Video topilmadi!")
            else:
                await update.message.reply_text(
                    f"❌ #{code} kodli kino topilmadi!",
                    reply_markup=back_menu_kb(lang)
                )
        return

    # ── PASTKI TUGMA ──────────────────────────────────
    if text == "🏠 Bosh menyu":
        user_states.pop(uid, None)
        not_subbed = await check_subscription(uid, context)
        if not_subbed:
            await update.message.reply_text(
                t(lang, "sub_required"),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(f"📢 {ch['channel_name']}", url=ch["channel_url"])]
                     for ch in not_subbed] +
                    [[InlineKeyboardButton(t(lang, "sub_check"), callback_data="check_sub")]]
                )
            )
            return
        await update.message.reply_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    # ── ADMIN HOLATLARI ───────────────────────────────
    if is_admin(uid) and uid in admin_states:
        await handle_admin_text(update, context, uid, text, lang)
        return

    # ── USER HOLATLARI ────────────────────────────────
    state = user_states.get(uid, "")

    if state == "contact_admin":
        user_states.pop(uid, None)
        row = get_user(uid)
        name = row["full_name"] or "Noma'lum"
        save_message(uid, name, text)
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 *Yangi xabar!*\n\n"
                         f"👤 [{name}](tg://user?id={uid}) — `{uid}`\n\n"
                         f"💬 {text}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Javob berish", callback_data=f"reply_to_{uid}")
                    ]]),
                    parse_mode="Markdown"
                )
            except:
                pass
        await update.message.reply_text(
            t(lang, "contact_sent"),
            reply_markup=back_menu_kb(lang)
        )
        return

    if state == "searching":
        user_states.pop(uid, None)
        results = search_movies(text)
        if not results:
            await update.message.reply_text(
                t(lang, "no_results"),
                reply_markup=back_menu_kb(lang)
            )
            return
        await update.message.reply_text(
            f"🔍 *{len(results)} ta natija:*",
            reply_markup=movies_list_kb(results, "search", lang),
            parse_mode="Markdown"
        )
        return

    # Boshqa xabarlar
    await update.message.reply_text(
        "Menyu uchun /start bosing 😊",
        reply_markup=back_menu_kb(lang)
    )


async def handle_admin_text(update, context, uid, text, lang):
    state = admin_states.get(uid, {})
    step  = state.get("step", "")

    # ── KINO QO'SHISH QADAMLARI ───────────────────────
    if step == "movie_title":
        state["data"]["title"] = text
        state["step"] = "movie_year"
        admin_states[uid] = state
        await update.message.reply_text("📅 Yilni yozing (masalan: 2024) yoki — :")

    elif step == "movie_year":
        state["data"]["year"] = int(text) if text.isdigit() else None
        state["step"] = "movie_country"
        admin_states[uid] = state
        await update.message.reply_text("🌍 Mamlakatni yozing yoki — :")

    elif step == "movie_country":
        state["data"]["country"] = None if text == "—" else text
        state["step"] = "movie_genre"
        admin_states[uid] = state
        await update.message.reply_text("🎭 Janrni yozing yoki — :")

    elif step == "movie_genre":
        state["data"]["genre"] = None if text == "—" else text
        state["data"]["description"] = None
        state["data"]["is_vip"] = 0
        state["step"] = "movie_code"
        admin_states[uid] = state
        await update.message.reply_text(
            "🔑 Kino kodi kiriting (masalan: 1, 2, 100):\n_(Foydalanuvchilar shu kod bilan topadi)_",
            parse_mode="Markdown"
        )

    elif step == "movie_code":
        if text.isdigit():
            state["data"]["custom_id"] = int(text)
            state["step"] = "movie_poster"
            admin_states[uid] = state
            await update.message.reply_text(
                f"✅ Kod: *#{text}*\n\n🖼 Poster rasmini yuboring yoki o'tkazib yuboring:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazish", callback_data="movie_skip_poster")]]),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Faqat raqam kiriting! (masalan: 1, 2, 100)")

    elif step == "movie_desc":
        state["data"]["description"] = None
        state["data"]["is_vip"] = 0
        state["step"] = "movie_poster"
        admin_states[uid] = state
        await update.message.reply_text(
            "🖼 Poster rasmini yuboring yoki o'tkazib yuboring:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazish", callback_data="movie_skip_poster")]])
        )

    elif step == "movie_poster":
        # Faqat rasm yuborilsa
        if update.message.photo:
            state["data"]["poster_id"] = update.message.photo[-1].file_id
        state["data"]["added_by"] = uid
        category = state.get("category")
        if category in ("serial", "anime", "drama"):
            movie_id = add_movie(state["data"])
            admin_states.pop(uid, None)
            await update.message.reply_text(
                f"✅ *{state['data']['title']}* qo'shildi! (ID: {movie_id})",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Qism qo'shish", callback_data=f"adm_add_ep_{movie_id}")],
                    [InlineKeyboardButton("🔙 Admin panel",   callback_data="admin_panel")],
                ]),
                parse_mode="Markdown"
            )
        else:
            state["step"] = "add_ep_file"
            state["movie_id"] = None
            state["season_id"] = None
            state["ep_num"] = 1
            admin_states[uid] = state
            await update.message.reply_text("🎬 Video faylni yuboring:")

    # ── KINO O'CHIRISH ────────────────────────────────
    elif step == "del_movie_id":
        if text.isdigit():
            movie = get_movie(int(text))
            if movie:
                delete_movie(int(text))
                await update.message.reply_text(
                    f"✅ *{movie['title']}* o'chirildi!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]]),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Kino topilmadi!")
        else:
            await update.message.reply_text("❌ Noto'g'ri ID!")
        admin_states.pop(uid, None)

    # ── YANGI FASL RAQAMI ─────────────────────────────
    elif step == "new_season_num":
        if text.isdigit():
            movie_id  = state["movie_id"]
            season_id = add_season(movie_id, int(text))
            admin_states[uid] = {"step": "add_ep_file", "movie_id": movie_id,
                                  "season_id": season_id, "ep_num": 1}
            await update.message.reply_text(f"✅ {text}-fasl yaratildi!\n\n1-qismni yuboring (video):")
        else:
            await update.message.reply_text("❌ Raqam kiriting!")

    # ── KANAL QO'SHISH ────────────────────────────────
    elif step == "sub_channel_id":
        state["channel_id"] = text
        state["step"] = "sub_channel_name"
        admin_states[uid] = state
        await update.message.reply_text("📝 Kanal nomini yozing:")

    elif step == "sub_channel_name":
        state["channel_name"] = text
        state["step"] = "sub_channel_url"
        admin_states[uid] = state
        await update.message.reply_text("🔗 Kanal linkini yozing (@username yoki https://t.me/...):")

    elif step == "sub_channel_url":
        add_subscription(state["channel_id"], state["channel_name"], text, state["sub_type"])
        admin_states.pop(uid, None)
        await update.message.reply_text(
            f"✅ *{state['channel_name']}* qo'shildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Obuna menyu", callback_data="adm_subs")]]),
            parse_mode="Markdown"
        )

    # ── XABAR YUBORISH ────────────────────────────────
    elif step == "broadcast_text":
        users = get_all_user_ids()
        sent = 0
        for user_id in users:
            try:
                await context.bot.send_message(chat_id=user_id, text=text)
                sent += 1
            except:
                pass
        admin_states.pop(uid, None)
        await update.message.reply_text(
            f"✅ {sent} ta foydalanuvchiga yuborildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
        )

    # ── ADMIN QO'SHISH ────────────────────────────────
    elif step == "add_admin_id":
        if text.isdigit():
            add_admin(int(text), uid)
            await update.message.reply_text(
                f"✅ {text} admin qilindi!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
            )
        else:
            await update.message.reply_text("❌ Noto'g'ri ID!")
        admin_states.pop(uid, None)

    # ── VIP BERISH ────────────────────────────────────
    elif step == "vip_user_id":
        if text.isdigit():
            target_id = int(text)
            state["target_id"] = target_id
            state["step"] = "vip_days"
            admin_states[uid] = state
            await update.message.reply_text(
                f"💎 {target_id} ga necha kunlik VIP?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("30 kun",  callback_data=f"vip_give_{target_id}_30"),
                     InlineKeyboardButton("90 kun",  callback_data=f"vip_give_{target_id}_90")],
                    [InlineKeyboardButton("365 kun", callback_data=f"vip_give_{target_id}_365")],
                ])
            )
        else:
            await update.message.reply_text("❌ Noto'g'ri ID!")
            admin_states.pop(uid, None)

    # ── ADMIN JAVOB BERISH ────────────────────────────
    elif step == "admin_reply":
        target_id = state["target_id"]
        admin_states.pop(uid, None)
        target_lang = get_user_lang(target_id)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📬 *Admin javob berdi:*\n\n{text}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(target_lang, "contact_admin"), callback_data="contact_admin")
                ]]),
                parse_mode="Markdown"
            )
            await update.message.reply_text(
                t(lang, "admin_reply_sent"),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
            )
        except:
            await update.message.reply_text(t(lang, "admin_reply_fail"))


# ═══════════════════════════════════════════════════════
# XABAR HANDLER (VIDEO / RASM / FAYL)
# ═══════════════════════════════════════════════════════

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    state = admin_states.get(uid, {})
    step  = state.get("step", "")

    if step == "movie_poster" and update.message.photo:
        state["data"]["poster_id"] = update.message.photo[-1].file_id
        state["data"]["added_by"]  = uid
        state["data"]["category"]  = state.get("category", "movie")
        category = state.get("category")
        if category in ("serial", "anime", "drama"):
            movie_id = add_movie(state["data"])
            admin_states.pop(uid, None)
            await update.message.reply_text(
                f"✅ *{state['data']['title']}* qo'shildi! (ID: {movie_id})",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Qism qo'shish", callback_data=f"adm_add_ep_{movie_id}")],
                    [InlineKeyboardButton("🔙 Admin panel",   callback_data="admin_panel")],
                ]),
                parse_mode="Markdown"
            )
        else:
            state["step"] = "add_ep_file"
            state["movie_id"] = None
            state["season_id"] = None
            state["ep_num"] = 1
            admin_states[uid] = state
            await update.message.reply_text("🎬 Video faylni yuboring:")
        return

    if step == "add_ep_file" and (update.message.video or update.message.document):
        file_id = (update.message.video or update.message.document).file_id

        # Agar kino hali DB ga qo'shilmagan bo'lsa
        if state.get("data") and not state.get("movie_id"):
            state["data"]["added_by"] = uid
            state["data"]["category"] = state.get("category", "movie")
            state["movie_id"] = add_movie(state["data"])

        movie_id  = state["movie_id"]
        season_id = state.get("season_id")
        ep_num    = state.get("ep_num", 1)

        add_episode(movie_id, file_id, season_id, ep_num)
        movie = get_movie(movie_id)
        state["ep_num"] = ep_num + 1
        admin_states[uid] = state

        await update.message.reply_text(
            f"✅ {ep_num}-qism qo'shildi! (*{movie['title']}*)\n"
            f"🔑 Kino kodi: `#{movie_id}`\n\n"
            f"Foydalanuvchilar #{movie_id} yozib topadi!\n\nYana qism qo'shish yoki tugallash:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yana qism",   callback_data=f"adm_ep_season_{movie_id}_{season_id or 0}")
                 if season_id else
                 InlineKeyboardButton("➕ Yana qism",   callback_data=f"adm_add_ep_{movie_id}")],
                [InlineKeyboardButton("✅ Tugallash",   callback_data="admin_panel")],
            ]),
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════
# STARS TO'LOV
# ═══════════════════════════════════════════════════════

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    lang    = get_user_lang(uid)
    payload = update.message.successful_payment.invoice_payload
    plan_key = payload.replace("vip_", "")
    plan = VIP_STARS.get(plan_key)
    if plan:
        until = set_vip(uid, plan["days"])
        await update.message.reply_text(
            f"🎉 *To'lov qabul qilindi!*\n\n"
            f"💎 VIP faollashdi — {plan['label']}\n"
            f"📅 Tugash: *{until}*",
            reply_markup=back_menu_kb(lang),
            parse_mode="Markdown"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💎 Yangi VIP!\n👤 {uid}\n📦 {plan['label']}\n⭐ {plan['stars']} Stars"
                )
            except:
                pass


# ═══════════════════════════════════════════════════════
# JOIN REQUEST
# ═══════════════════════════════════════════════════════

async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request: ChatJoinRequest = update.chat_join_request
    try:
        await context.bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=request.from_user.id
        )
    except:
        pass


# ═══════════════════════════════════════════════════════
# INLINE QIDIRUV
# ═══════════════════════════════════════════════════════

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.inline_query.query.strip()
    if not query_text:
        return
    from telegram import InlineQueryResultArticle, InputTextMessageContent
    import uuid
    results_db = search_movies(query_text)
    results = []
    for m in results_db[:10]:
        vip = "💎 " if m["is_vip"] else ""
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"{vip}{m['title']}",
            description=f"📅 {m['year'] or '—'} | ⭐ {m['rating']}",
            input_message_content=InputTextMessageContent(f"/movie_{m['id']}")
        ))
    await update.inline_query.answer(results, cache_time=10)


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    print("🤖 MediaBot ishga tushmoqda...")
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
        media_handler
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_handler
    ))

    print("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
