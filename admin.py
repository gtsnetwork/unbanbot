from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from config import OWNER_ID
from database import (
    review_mod_request, pending_mod_requests, moderators_list, list_appeals,
    stats, remove_moderator, activity_log
)
from keyboards import owner_request_buttons, mod_dashboard
from states import BroadcastStates

router = Router()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def owner_only(uid):
    return uid == OWNER_ID

@router.message(Command("admin"))
async def admin_dashboard(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied.")
        return
    s = await stats()
    await message.answer(
        "GTS NETWORK SUPER ADMIN\n\n"
        f"Users: {s['users']}\nAppeals: {s['appeals']}\nPending: {s['pending']}\n"
        f"Approved: {s['approved']}\nRejected: {s['rejected']}\nModerators: {s['mods']}\n\n"
        "Commands: /mods /requests /appeals /stats /removemod /broadcast /activity"
    )

@router.message(Command("stats"))
async def stats_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    s = await stats()
    await message.answer("\n".join(f"{k.title()}: {v}" for k,v in s.items()))

@router.message(Command("mods"))
async def mods_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    rows = await moderators_list()
    text = "APPROVED MODERATORS\n\n" + ("\n".join(
        f"User ID: {r['user_id']} | Approved: {r['approved_at']}" for r in rows
    ) or "No approved moderators.")
    await message.answer(text)

@router.message(Command("requests"))
async def requests_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    rows = await pending_mod_requests()
    if not rows:
        await message.answer("There are no pending moderator requests."); return
    for r in rows:
        await message.answer(
            f"MODERATOR REQUEST #{r['id']}\nUser ID: {r['user_id']}\n"
            f"Username: @{r['username'] or 'not set'}\nName: {r['full_name']}\n"
            f"Reason: {r['reason']}\nSubmitted: {r['created_at']}",
            reply_markup=owner_request_buttons(r["id"])
        )

@router.message(Command("appeals"))
async def appeals_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    rows = await list_appeals(None, 30)
    if not rows:
        await message.answer("No appeals have been submitted."); return
    for r in rows:
        await message.answer(
            f"Appeal #{r['id']} | {r['status']}\nUser ID: {r['user_id']}\n"
            f"Group: {r['group_name']}\nSubmitted: {r['created_at']}"
        )

@router.message(Command("activity"))
async def activity_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    rows = await activity_log()
    await message.answer("MODERATOR ACTIVITY\n\n" + ("\n".join(
        f"{r['created_at']} | {r['moderator_id']} | {r['action']} | {r['target']}"
        for r in rows
    ) or "No activity recorded."))

@router.message(Command("removemod"))
async def remove_mod_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    args = (message.text or "").split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("Usage: /removemod <telegram_user_id>"); return
    uid = int(args[1])
    if uid == OWNER_ID:
        await message.answer("The owner cannot be removed."); return
    changed = await remove_moderator(uid, now())
    await message.answer("Moderator access revoked." if changed else "No active moderator found for that ID.")
    try:
        await message.bot.send_message(uid, "Your GTS NETWORK moderator access has been revoked.")
    except (TelegramForbiddenError, TelegramBadRequest):
        pass

@router.message(Command("addmod"))
async def addmod_command(message: Message):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    await message.answer(
        "To approve a moderator, ask them to open the bot and use /mod, then submit "
        "a moderator access request. Review requests with /requests."
    )

@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if not owner_only(message.from_user.id):
        await message.answer("Access denied."); return
    await state.set_state(BroadcastStates.message)
    await message.answer("Send the announcement text. Send /cancel to cancel.")

@router.message(BroadcastStates.message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Broadcast cancelled.")

@router.message(BroadcastStates.message)
async def broadcast_send(message: Message, state: FSMContext):
    if not owner_only(message.from_user.id):
        await state.clear(); await message.answer("Access denied."); return
    text = (message.text or "").strip()
    if not text or len(text) > 3500:
        await message.answer("Send text up to 3500 characters."); return
    from database import connect
    async with await connect() as db:
        cur = await db.execute("SELECT user_id FROM bot_users")
        users = await cur.fetchall()
    sent = failed = 0
    for row in users:
        try:
            await message.bot.send_message(row["user_id"], text)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
    await state.clear()
    await message.answer(f"Broadcast finished.\nSent: {sent}\nFailed: {failed}")

@router.callback_query(F.data.startswith("admin:mod:"))
async def review_request_callback(call: CallbackQuery):
    if not owner_only(call.from_user.id):
        await call.answer("Owner authorization required.", show_alert=True); return
    parts = call.data.split(":")
    if len(parts) != 4 or not parts[3].isdigit():
        await call.answer("Invalid request.", show_alert=True); return
    action, request_id = parts[2], int(parts[3])
    if action not in ("approve","reject"):
        await call.answer("Invalid action.", show_alert=True); return
    result = await review_mod_request(request_id, action == "approve", now())
    if not result:
        await call.answer("This request has already been reviewed.", show_alert=True); return
    await call.message.edit_text(f"Moderator request #{request_id} {result['status']}.")
    try:
        await call.bot.send_message(
            result["user_id"],
            "Your moderator access request has been approved."
            if action == "approve"
            else "Your moderator access request has been rejected."
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
    await call.answer("Decision recorded.")
