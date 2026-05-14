import logging
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                       LabeledPrice, ReplyKeyboardMarkup, KeyboardButton)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, PreCheckoutQueryHandler,
                           ChatJoinRequestHandler, filters, ContextTypes)
from config import BOT_TOKEN, ADMIN_IDS, VIP_STARS
from database import *
from languages import t
from subscription import check_subscription

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

user_states  = {}
admin_states = {}

# ═══════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════

def bottom_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("🏠 Bosh menyu")]], resize_keyboard=True, persistent=True)

def main_menu_kb(lang, adm=False):
    kb = [
        [InlineKeyboardButton("🎬 Kinolar", callback_data="cat_movie")],
        [InlineKeyboardButton(t(lang, "contact_admin"), callback_data="contact_admin"),
         InlineKeyboardButton(t(lang, "lang_btn"), callback_data="lang")],
    ]
    if adm:
        kb.append([InlineKeyboardButton("👑 Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)

def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="set_lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
    ]])

def back_kb(lang):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "menu"), callback_data="menu")]])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")]])

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo'shish",  callback_data="adm_add_movie"),
         InlineKeyboardButton("🗑 Kino o'chirish", callback_data="adm_del_movie")],
        [InlineKeyboardButton("📢 Obuna",          callback_data="adm_subs"),
         InlineKeyboardButton("📊 Statistika",     callback_data="adm_stats")],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data="adm_broadcast"),
         InlineKeyboardButton("👤 Admin qo'shish", callback_data="adm_add_admin")],
        [InlineKeyboardButton("📩 Xabarlar",       callback_data="adm_inbox"),
         InlineKeyboardButton("⚙️ Sozlamalar",     callback_data="adm_settings")],
        [InlineKeyboardButton("🔙 Orqaga",         callback_data="menu")],
    ])

def sub_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo'shish",  callback_data="adm_sub_add"),
         InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="adm_sub_del")],
        [InlineKeyboardButton("📋 Ro'yxat",         callback_data="adm_sub_list")],
        [InlineKeyboardButton("🔙 Orqaga",          callback_data="admin_panel")],
    ])

# ═══════════════════════════════════════════════════════
# /START
# ═══════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.full_name, user.username)
    if user.id in ADMIN_IDS:
        add_admin(user.id, user.id)

    db_user = get_user(user.id)
    lang    = get_user_lang(user.id)

    # Birinchi marta — til tanlash
    if not db_user["lang"]:
        await update.message.reply_text("🌐 Tilni tanlang / Выберите язык:", reply_markup=lang_kb())
        return

    # Obuna tekshirish — faqat startda
    not_subbed = await check_subscription(user.id, context)
    if not_subbed:
        kb = [[InlineKeyboardButton(f"📢 {ch['channel_name']}", url=ch["channel_url"])] for ch in not_subbed]
        kb.append([InlineKeyboardButton(t(lang, "sub_check"), callback_data="check_sub")])
        await update.message.reply_text(t(lang, "sub_required"), reply_markup=InlineKeyboardMarkup(kb))
        return

    await update.message.reply_text("👇", reply_markup=bottom_kb())
    await update.message.reply_text(
        t(lang, "start_msg"),
        reply_markup=main_menu_kb(lang, is_admin(user.id)),
        parse_mode="Markdown"
    )

# ═══════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    d    = query.data
    lang = get_user_lang(uid)

    # TIL
    if d.startswith("set_lang_"):
        new_lang = d.replace("set_lang_", "")
        set_user_lang(uid, new_lang)
        lang = new_lang
        await query.message.reply_text("👇", reply_markup=bottom_kb())
        await query.edit_message_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    if d == "lang":
        await query.edit_message_text("🌐 Tilni tanlang / Выберите язык:", reply_markup=lang_kb())
        return

    # OBUNA TEKSHIRISH
    if d == "check_sub":
        not_subbed = await check_subscription(uid, context)
        if not_subbed:
            await query.answer(t(lang, "sub_fail"), show_alert=True)
        else:
            await query.answer(t(lang, "sub_ok"), show_alert=True)
            await query.edit_message_text(
                t(lang, "start_msg"),
                reply_markup=main_menu_kb(lang, is_admin(uid)),
                parse_mode="Markdown"
            )
        return

    # BOSH MENYU — subscription tekshirilmaydi (tez ishlaydi)
    if d == "menu":
        user_states.pop(uid, None)
        admin_states.pop(uid, None)
        await query.edit_message_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    # ADMIN CALLBACKLAR
    if is_admin(uid) and (
        d == "admin_panel" or d.startswith("adm_") or
        d.startswith("sub_type_") or d.startswith("del_sub_") or
        d.startswith("cat_sel_") or d.startswith("adm_ep_") or
        d.startswith("adm_add_ep_") or d.startswith("vip_give_") or
        d.startswith("reply_to_") or d == "movie_skip_poster"
    ):
        await admin_cb(query, context, uid, d, lang)
        return

    # KINOLAR — kod so'rash
    if d == "cat_movie":
        user_states[uid] = "waiting_code"
        await query.edit_message_text(
            "🔑 Kino kodini kiriting:\n_(Masalan: 1, 2, 5)_",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        return

    # QISM
    if d.startswith("ep_"):
        ep_id = int(d.replace("ep_", ""))
        conn  = get_conn()
        ep    = conn.execute("SELECT * FROM episodes WHERE id=?", (ep_id,)).fetchone()
        conn.close()
        if ep:
            protect = get_setting("forward_enabled") == "0"
            try:
                await context.bot.send_video(chat_id=uid, video=ep["file_id"], protect_content=protect)
                await query.answer("✅ Yuborildi!")
            except Exception as e:
                logging.error(f"Video yuborishda xato: {e}")
                await query.answer("❌ Xatolik!", show_alert=True)
        return

    # MUROJAAT
    if d == "contact_admin":
        user_states[uid] = "contact_admin"
        await query.edit_message_text(
            t(lang, "contact_prompt"),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t(lang, "cancel"), callback_data="menu")
            ]])
        )
        return

# ═══════════════════════════════════════════════════════
# ADMIN CALLBACK
# ═══════════════════════════════════════════════════════

async def admin_cb(query, context, uid, d, lang):
    if d == "admin_panel":
        await query.edit_message_text("👑 *Admin panel*", reply_markup=admin_menu_kb(), parse_mode="Markdown")

    elif d == "adm_stats":
        s = get_stats()
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n"
            f"👥 Foydalanuvchilar: *{s['users']}*\n"
            f"🎬 Kinolar: *{s['movies']}*\n"
            f"👁 Bugun: *{s['today_views']}*\n"
            f"📈 Jami: *{s['total_views']}*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )

    elif d == "adm_add_movie":
        await query.edit_message_text(
            "🎬 Kategoriyani tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Kino", callback_data="cat_sel_movie")],
                [InlineKeyboardButton("❌ Bekor", callback_data="admin_panel")],
            ])
        )

    elif d.startswith("cat_sel_"):
        category = d.replace("cat_sel_", "")
        admin_states[uid] = {"step": "movie_title", "category": category, "data": {}}
        await query.edit_message_text("📝 Kino nomini yozing:", reply_markup=cancel_kb())

    elif d == "movie_skip_poster":
        state = admin_states.get(uid, {})
        if not state:
            await query.answer("Xatolik! Qaytadan boshlang.", show_alert=True)
            return
        state["data"]["poster_id"] = None
        state["data"]["added_by"]  = uid
        state["data"]["category"]  = state.get("category", "movie")
        state["step"]     = "add_ep_file"
        state["movie_id"] = None
        state["season_id"]= None
        state["ep_num"]   = 1
        admin_states[uid] = state
        await query.edit_message_text("🎬 Video faylni yuboring (yoki kanaldan forward qiling):")

    elif d == "adm_del_movie":
        admin_states[uid] = {"step": "del_movie_id"}
        await query.edit_message_text("🗑 O'chirmoqchi bo'lgan kino kodini yozing:", reply_markup=cancel_kb())

    elif d.startswith("adm_add_ep_"):
        movie_id = int(d.replace("adm_add_ep_", ""))
        movie = get_movie(movie_id)
        if not movie:
            await query.answer("Kino topilmadi!", show_alert=True)
            return
        admin_states[uid] = {
            "step": "add_ep_file", "movie_id": movie_id,
            "season_id": None, "ep_num": len(get_episodes(movie_id)) + 1,
            "category": movie["category"]
        }
        await query.edit_message_text(
            f"📺 *{movie['title']}*\n\nVideo yuboring:",
            reply_markup=cancel_kb(), parse_mode="Markdown"
        )

    elif d == "adm_subs":
        await query.edit_message_text("📢 *Majburiy obuna:*", reply_markup=sub_menu_kb(), parse_mode="Markdown")

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
            "📢 Kanal turini tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Ommaviy", callback_data="sub_type_public")],
                [InlineKeyboardButton("🔒 Maxfiy",  callback_data="sub_type_private")],
                [InlineKeyboardButton("🔙 Bekor",   callback_data="adm_subs")],
            ])
        )

    elif d.startswith("sub_type_"):
        sub_type = d.replace("sub_type_", "")
        admin_states[uid] = {"step": "sub_channel_id", "sub_type": sub_type}
        await query.edit_message_text(
            "📝 Kanal ID yoki @username yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor", callback_data="adm_subs")]])
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
        remove_subscription(int(d.replace("del_sub_", "")))
        await query.answer("✅ O'chirildi!", show_alert=True)
        await query.edit_message_text("📢 *Majburiy obuna:*", reply_markup=sub_menu_kb(), parse_mode="Markdown")

    elif d == "adm_broadcast":
        admin_states[uid] = {"step": "broadcast_text"}
        await query.edit_message_text("📣 Xabarni yozing:", reply_markup=cancel_kb())

    elif d == "adm_add_admin":
        admin_states[uid] = {"step": "add_admin_id"}
        await query.edit_message_text("👤 Yangi admin ID sini yozing:", reply_markup=cancel_kb())

    elif d == "adm_vip":
        admin_states[uid] = {"step": "vip_user_id"}
        await query.edit_message_text("💎 Foydalanuvchi ID sini yozing:", reply_markup=cancel_kb())

    elif d.startswith("vip_give_"):
        parts     = d.split("_")
        target_id = int(parts[2])
        days      = int(parts[3])
        until     = set_vip(target_id, days)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Sizga {days} kunlik VIP berildi!\n📅 Muddat: *{until}*",
                parse_mode="Markdown"
            )
        except:
            pass
        await query.edit_message_text(
            f"✅ {target_id} ga {days} kunlik VIP.\nMuddati: {until}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
        )
        admin_states.pop(uid, None)

    elif d == "adm_settings":
        fwd      = get_setting("forward_enabled")
        fwd_text = "✅ Forward: Yoq" if fwd == "1" else "🚫 Forward: O'ch"
        await query.edit_message_text(
            "⚙️ *Sozlamalar:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(fwd_text, callback_data="adm_toggle_forward")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")],
            ]),
            parse_mode="Markdown"
        )

    elif d == "adm_toggle_forward":
        new_val  = "0" if get_setting("forward_enabled") == "1" else "1"
        set_setting("forward_enabled", new_val)
        fwd_text = "✅ Forward: Yoq" if new_val == "1" else "🚫 Forward: O'ch"
        await query.answer("✅ O'zgartirildi!")
        await query.edit_message_text(
            "⚙️ *Sozlamalar:*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(fwd_text, callback_data="adm_toggle_forward")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")],
            ]),
            parse_mode="Markdown"
        )

    elif d == "adm_inbox":
        msgs = get_messages()
        if not msgs:
            await query.edit_message_text(
                "📩 Hozircha xabar yo'q.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]])
            )
            return
        text = "📩 *Xabarlar:*\n\n"
        kb   = []
        for m in msgs[:10]:
            text += f"👤 `{m['user_id']}` — {m['full_name']}\n💬 {m['message'][:50]}\n\n"
            kb.append([InlineKeyboardButton(f"↩️ {m['full_name']}", callback_data=f"reply_to_{m['user_id']}")])
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif d.startswith("reply_to_"):
        target_id = int(d.replace("reply_to_", ""))
        admin_states[uid] = {"step": "admin_reply", "target_id": target_id}
        await query.message.reply_text(
            f"✏️ `{target_id}` ga javob yozing:",
            reply_markup=cancel_kb(),
            parse_mode="Markdown"
        )

# ═══════════════════════════════════════════════════════
# MATN HANDLER
# ═══════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_lang(uid)

    # Pastki tugma
    if text == "🏠 Bosh menyu":
        user_states.pop(uid, None)
        admin_states.pop(uid, None)
        await update.message.reply_text(
            t(lang, "start_msg"),
            reply_markup=main_menu_kb(lang, is_admin(uid)),
            parse_mode="Markdown"
        )
        return

    # Admin holatlari
    if is_admin(uid) and uid in admin_states:
        await admin_text(update, context, uid, text, lang)
        return

    state = user_states.get(uid, "")

    # Kod kutish holati
    if state == "waiting_code":
        code = text.replace("#", "").strip()
        if code.isdigit():
            movie = get_movie(int(code))
            if movie:
                protect = get_setting("forward_enabled") == "0"
                add_view(uid, movie["id"])
                eps = get_episodes(movie["id"])
                if eps:
                    try:
                        user_states.pop(uid, None)
                        await context.bot.send_video(
                            chat_id=uid,
                            video=eps[0]["file_id"],
                            caption=f"🎬 *{movie['title']}*",
                            protect_content=protect,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logging.error(f"Video xato: {e}")
                        await update.message.reply_text("❌ Video yuborishda xatolik!", reply_markup=back_kb(lang))
                else:
                    await update.message.reply_text("❌ Video topilmadi!", reply_markup=back_kb(lang))
            else:
                await update.message.reply_text("❌ Bu kodda kino topilmadi!\nQaytadan kiriting:")
        else:
            await update.message.reply_text("❌ Faqat raqam kiriting! (masalan: 1, 2, 5)")
        return

    # Murojaat holati
    if state == "contact_admin":
        user_states.pop(uid, None)
        row  = get_user(uid)
        name = (row["full_name"] or "Noma'lum") if row else "Noma'lum"
        save_message(uid, name, text)
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 *Yangi xabar!*\n\n👤 [{name}](tg://user?id={uid}) — `{uid}`\n\n💬 {text}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Javob berish", callback_data=f"reply_to_{uid}")
                    ]]),
                    parse_mode="Markdown"
                )
            except:
                pass
        await update.message.reply_text(t(lang, "contact_sent"), reply_markup=back_kb(lang))
        return

    # # yoki raqam bilan qidiruv
    code = text.replace("#", "").strip()
    if code.isdigit():
        movie = get_movie(int(code))
        if movie:
            protect = get_setting("forward_enabled") == "0"
            add_view(uid, movie["id"])
            eps = get_episodes(movie["id"])
            if eps:
                try:
                    await context.bot.send_video(
                        chat_id=uid,
                        video=eps[0]["file_id"],
                        caption=f"🎬 *{movie['title']}*",
                        protect_content=protect,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Video xato: {e}")
                    await update.message.reply_text("❌ Xatolik!", reply_markup=back_kb(lang))
            else:
                await update.message.reply_text("❌ Video topilmadi!", reply_markup=back_kb(lang))
        else:
            await update.message.reply_text("❌ Kino topilmadi!", reply_markup=back_kb(lang))
        return

    await update.message.reply_text("Menyu uchun /start bosing 😊", reply_markup=back_kb(lang))

# ═══════════════════════════════════════════════════════
# ADMIN MATN HANDLER
# ═══════════════════════════════════════════════════════

async def admin_text(update, context, uid, text, lang):
    state = admin_states.get(uid, {})
    step  = state.get("step", "")

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
        state["data"]["genre"]       = None if text == "—" else text
        state["data"]["description"] = None
        state["data"]["is_vip"]      = 0
        state["step"] = "movie_code"
        admin_states[uid] = state
        await update.message.reply_text("🔑 Kino kodini kiriting (masalan: 1, 2, 100):")

    elif step == "movie_code":
        if text.isdigit():
            state["data"]["custom_id"] = int(text)
            state["step"] = "movie_poster"
            admin_states[uid] = state
            await update.message.reply_text(
                f"✅ Kod: #{text}\n\n🖼 Poster rasmini yuboring yoki o'tkazib yuboring:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏭ O'tkazish", callback_data="movie_skip_poster")
                ]])
            )
        else:
            await update.message.reply_text("❌ Faqat raqam kiriting! (masalan: 1, 2, 100)")

    elif step == "del_movie_id":
        if text.isdigit():
            movie = get_movie(int(text))
            if movie:
                delete_movie(int(text))
                await update.message.reply_text(
                    f"✅ {movie['title']} o'chirildi!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
                )
            else:
                await update.message.reply_text("❌ Kino topilmadi!")
        else:
            await update.message.reply_text("❌ Noto'g'ri kod!")
        admin_states.pop(uid, None)

    elif step == "sub_channel_id":
        state["channel_id"] = text
        state["step"] = "sub_channel_name"
        admin_states[uid] = state
        await update.message.reply_text("📝 Kanal nomini yozing:")

    elif step == "sub_channel_name":
        state["channel_name"] = text
        state["step"] = "sub_channel_url"
        admin_states[uid] = state
        await update.message.reply_text("🔗 Kanal linkini yozing (https://t.me/...):")

    elif step == "sub_channel_url":
        add_subscription(state["channel_id"], state["channel_name"], text, state["sub_type"])
        admin_states.pop(uid, None)
        await update.message.reply_text(
            f"✅ {state['channel_name']} qo'shildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Obuna", callback_data="adm_subs")]])
        )

    elif step == "broadcast_text":
        count = 0
        for uid2 in get_all_user_ids():
            try:
                await context.bot.send_message(chat_id=uid2, text=text)
                count += 1
            except:
                pass
        admin_states.pop(uid, None)
        await update.message.reply_text(
            f"✅ {count} ta foydalanuvchiga yuborildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
        )

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

    elif step == "vip_user_id":
        if text.isdigit():
            target_id = int(text)
            state["target_id"] = target_id
            state["step"] = "vip_days"
            admin_states[uid] = state
            await update.message.reply_text(
                f"💎 {target_id} ga necha kun VIP?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("30 kun",  callback_data=f"vip_give_{target_id}_30"),
                     InlineKeyboardButton("90 kun",  callback_data=f"vip_give_{target_id}_90")],
                    [InlineKeyboardButton("365 kun", callback_data=f"vip_give_{target_id}_365")],
                ])
            )
        else:
            await update.message.reply_text("❌ Noto'g'ri ID!")
            admin_states.pop(uid, None)

    elif step == "admin_reply":
        target_id = state["target_id"]
        admin_states.pop(uid, None)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📬 *Admin javob berdi:*\n\n{text}",
                parse_mode="Markdown"
            )
            await update.message.reply_text(
                "✅ Javob yuborildi!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
            )
        except:
            await update.message.reply_text("❌ Xabar yuborib bo'lmadi!")

# ═══════════════════════════════════════════════════════
# MEDIA HANDLER
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
        state["step"]      = "add_ep_file"
        state["movie_id"]  = None
        state["season_id"] = None
        state["ep_num"]    = 1
        admin_states[uid]  = state
        await update.message.reply_text("🎬 Video faylni yuboring:")
        return

    if step == "add_ep_file" and (update.message.video or update.message.document):
        file_id = (update.message.video or update.message.document).file_id

        if state.get("data") and not state.get("movie_id"):
            state["data"]["added_by"] = uid
            state["data"]["category"] = state.get("category", "movie")
            state["movie_id"] = add_movie(state["data"])

        movie_id  = state.get("movie_id")
        season_id = state.get("season_id")
        ep_num    = state.get("ep_num", 1)

        if not movie_id:
            await update.message.reply_text(
                "❌ Xatolik! Qaytadan boshlang.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
            )
            admin_states.pop(uid, None)
            return

        add_episode(movie_id, file_id, season_id, ep_num)
        movie = get_movie(movie_id)
        state["ep_num"] = ep_num + 1
        admin_states[uid] = state

        await update.message.reply_text(
            f"✅ Video qo'shildi! ({movie['title']})\n🔑 Kino kodi: #{movie_id}\n\nFoydalanuvchilar #{movie_id} yozib topadi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yana video", callback_data=f"adm_add_ep_{movie_id}")],
                [InlineKeyboardButton("✅ Tugallash",  callback_data="admin_panel")],
            ])
        )

# ═══════════════════════════════════════════════════════
# XATO HANDLER
# ═══════════════════════════════════════════════════════

async def error_handler(update, context):
    logging.error(f"Xato: {context.error}")

# ═══════════════════════════════════════════════════════
# TO'LOV VA JOIN
# ═══════════════════════════════════════════════════════

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    lang    = get_user_lang(uid)
    payload = update.message.successful_payment.invoice_payload
    plan    = VIP_STARS.get(payload.replace("vip_", ""))
    if plan:
        until = set_vip(uid, plan["days"])
        await update.message.reply_text(
            f"🎉 VIP faollashdi!\n📅 Tugash: {until}",
            reply_markup=back_kb(lang)
        )

async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.approve_chat_join_request(
            chat_id=update.chat_join_request.chat.id,
            user_id=update.chat_join_request.from_user.id
        )
    except:
        pass

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    print("🤖 Bot ishga tushmoqda...")
    init_db()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
        media_handler
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    print("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
