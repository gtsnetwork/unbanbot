from datetime import datetime, timezone
import time
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from config import OWNER_ID, GUIDELINES_TEXT, SUPPORT_TEXT, RATE_LIMIT_SECONDS
from database import upsert_user, create_appeal, user_appeals, rate_allowed, list_appeals
from keyboards import main_menu, group_menu, agreement_menu, preview_menu, edit_menu, GROUPS
from states import AppealStates, ModeratorRequestStates
from database import add_mod_request
from keyboards import moderator_gate

router = Router()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def user_label(row):
    return f"@{row['username']}" if row["username"] else "Not set"

def preview(data, user):
    return (
        "GTS NETWORK | APPEAL PREVIEW\n\n"
        f"Appeal group: {data['group']}\n"
        f"Telegram User ID: {user.id}\n"
        f"Username: @{user.username}" if user.username else
        f"Appeal group: {data['group']}\nTelegram User ID: {user.id}\nUsername: Not set"
    ) + (
        f"\nFirst name: {user.first_name}\n\n"
        f"1. Why were you banned?\n{data['ban_reason']}\n\n"
        f"2. Why should the ban be removed?\n{data['explanation']}\n\n"
        f"3. Agree to follow group rules: {'Yes' if data['agreement'] else 'No'}"
    )

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await upsert_user(message.from_user.id, message.from_user.username,
                      message.from_user.first_name, now())
    await message.answer(
        "GTS NETWORK | APPEAL CENTER\n\n"
        "Welcome to the official GTS NETWORK Appeal Center.\n\n"
        "If you believe your account was banned unfairly or would like to request "
        "another opportunity to join our network, you can submit an official unban appeal here.\n\n"
        "Our moderation team will review your request.\n\n"
        "Select an option below to continue.",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "user:home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("GTS NETWORK | APPEAL CENTER\n\nSelect an option below to continue.", reply_markup=main_menu())
    await call.answer()

@router.callback_query(F.data == "user:appeal")
async def start_appeal(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(user_id=call.from_user.id, username=call.from_user.username,
                            first_name=call.from_user.first_name)
    await call.message.edit_text("Select the GTS NETWORK group you were banned from:", reply_markup=group_menu())
    await call.answer()

@router.callback_query(F.data.startswith("appeal:group:"))
async def choose_group(call: CallbackQuery, state: FSMContext):
    group = call.data.split(":", 2)[2]
    if group not in GROUPS:
        await call.answer("Invalid group.", show_alert=True); return
    await state.update_data(group=group)
    await state.set_state(AppealStates.ban_reason)
    await call.message.edit_text("Question 1 of 3\n\nWhy were you banned from this group?")
    await call.answer()

@router.message(AppealStates.ban_reason)
async def ban_reason(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 5 or len(value) > 2000:
        await message.answer("Please provide between 5 and 2000 characters.")
        return
    await state.update_data(ban_reason=value)
    await state.set_state(AppealStates.explanation)
    await message.answer("Question 2 of 3\n\nWhy do you believe your ban should be removed?")

@router.message(AppealStates.explanation)
async def explanation(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 5 or len(value) > 2000:
        await message.answer("Please provide between 5 and 2000 characters.")
        return
    await state.update_data(explanation=value)
    await state.set_state(AppealStates.agreement)
    await message.answer("Question 3 of 3\n\nDo you understand and agree to follow the group rules if unbanned?",
                         reply_markup=agreement_menu())

@router.callback_query(AppealStates.agreement, F.data.startswith("appeal:agreement:"))
async def agreement(call: CallbackQuery, state: FSMContext):
    agreed = call.data.endswith(":yes")
    await state.update_data(agreement=agreed)
    if not agreed:
        await call.message.edit_text(
            "You must agree to follow the group rules to submit an appeal.",
            reply_markup=main_menu()
        )
        await state.clear()
    else:
        data = await state.get_data()
        await call.message.edit_text(preview(data, call.from_user), reply_markup=preview_menu())
    await call.answer()

@router.callback_query(F.data == "appeal:edit")
async def edit_answers(call: CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=edit_menu())
    await call.answer()

@router.callback_query(F.data.startswith("appeal:edit:"))
async def edit_field(call: CallbackQuery, state: FSMContext):
    field = call.data.rsplit(":", 1)[1]
    if field == "ban":
        await state.set_state(AppealStates.ban_reason)
        prompt = "Enter the updated answer: Why were you banned?"
    elif field == "explanation":
        await state.set_state(AppealStates.explanation)
        prompt = "Enter the updated explanation for why your ban should be removed."
    elif field == "agreement":
        await state.set_state(AppealStates.agreement)
        await call.message.edit_text("Do you agree to follow the group rules?", reply_markup=agreement_menu())
        await call.answer(); return
    else:
        await call.answer("Invalid selection.", show_alert=True); return
    await call.message.edit_text(prompt)
    await call.answer()

@router.callback_query(F.data == "appeal:preview")
async def back_preview(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not all(k in data for k in ("group","ban_reason","explanation","agreement")):
        await call.answer("The appeal is incomplete.", show_alert=True); return
    await call.message.edit_text(preview(data, call.from_user), reply_markup=preview_menu())
    await call.answer()

@router.callback_query(F.data == "appeal:submit")
async def submit(call: CallbackQuery, state: FSMContext):
    if not await rate_allowed(call.from_user.id, time.time(), RATE_LIMIT_SECONDS):
        await call.answer("Please wait before trying again.", show_alert=True); return
    data = await state.get_data()
    required = ("group","ban_reason","explanation","agreement")
    if not all(k in data for k in required):
        await call.answer("Your appeal is incomplete. Start again.", show_alert=True); return
    appeal_id = await create_appeal(data, now())
    await state.clear()
    if appeal_id is None:
        await call.message.edit_text("You already have an active appeal for this group.")
        await call.answer(); return
    await call.message.edit_text(
        f"Your appeal has been submitted successfully.\n\nAppeal ID: #{appeal_id}\n"
        "Status: Pending\n\nYou will receive a notification when its status changes.",
        reply_markup=main_menu()
    )
    rows = await list_appeals("pending", 100)
    appeal = next((r for r in rows if r["id"] == appeal_id), None)
    if appeal:
        from database import moderators_list
        mods = await moderators_list()
        targets = {OWNER_ID} | {m["user_id"] for m in mods}
        text = (
            f"NEW APPEAL #{appeal_id}\n\nUser ID: {appeal['user_id']}\n"
            f"Username: {user_label(appeal)}\nFirst name: {appeal['first_name']}\n"
            f"Group: {appeal['group_name']}\n\nReason for ban:\n{appeal['ban_reason']}\n\n"
            f"Explanation:\n{appeal['explanation']}\n\n"
            f"Agrees to rules: {'Yes' if appeal['agreement'] else 'No'}\n"
            f"Submitted: {appeal['created_at']}"
        )
        from keyboards import appeal_actions
        for target in targets:
            try:
                await call.bot.send_message(target, text, reply_markup=appeal_actions(appeal_id))
            except (TelegramForbiddenError, TelegramBadRequest):
                pass
    await call.answer()

@router.callback_query(F.data == "user:status")
async def status(call: CallbackQuery):
    rows = await user_appeals(call.from_user.id)
    if not rows:
        text = "You have not submitted any appeals."
    else:
        text = "YOUR APPEAL STATUS\n\n"
        for r in rows:
            text += (f"Appeal ID: #{r['id']}\nGroup: {r['group_name']}\n"
                     f"Submitted: {r['created_at']}\nStatus: {r['status'].replace('_',' ').title()}\n"
                     f"Moderator response: {r['moderator_response'] or 'No response'}\n\n")
    await call.message.edit_text(text, reply_markup=main_menu())
    await call.answer()

@router.callback_query(F.data == "user:guidelines")
async def guidelines(call: CallbackQuery):
    await call.message.edit_text("APPEAL GUIDELINES\n\n" + GUIDELINES_TEXT, reply_markup=main_menu())
    await call.answer()

@router.callback_query(F.data == "user:support")
async def support(call: CallbackQuery):
    await call.message.edit_text("CONTACT SUPPORT\n\n" + SUPPORT_TEXT, reply_markup=main_menu())
    await call.answer()

@router.callback_query(F.data == "mod:request")
async def request_mod_start(call: CallbackQuery, state: FSMContext):
    from database import is_moderator
    if await is_moderator(call.from_user.id):
        await call.answer("You are already an approved moderator.", show_alert=True); return
    await state.set_state(ModeratorRequestStates.reason)
    await call.message.answer("Please explain why you are requesting moderator access.")
    await call.answer()

@router.message(ModeratorRequestStates.reason)
async def request_mod_submit(message: Message, state: FSMContext):
    from database import is_moderator
    if await is_moderator(message.from_user.id):
        await state.clear()
        await message.answer("You already have moderator access.")
        return
    reason = (message.text or "").strip()
    if len(reason) < 10 or len(reason) > 1500:
        await message.answer("Please provide between 10 and 1500 characters.")
        return
    request_id = await add_mod_request(message.from_user.id, message.from_user.username,
                                       message.from_user.full_name, reason, now())
    await state.clear()
    await message.answer("Your moderator access request has been sent to the network owner.")
    from keyboards import owner_request_buttons
    try:
        await message.bot.send_message(
            OWNER_ID,
            f"MODERATOR ACCESS REQUEST #{request_id}\n\nUser ID: {message.from_user.id}\n"
            f"Username: @{message.from_user.username or 'not set'}\n"
            f"Full name: {message.from_user.full_name}\nReason:\n{reason}",
            reply_markup=owner_request_buttons(request_id)
        )
    except TelegramForbiddenError:
        await message.answer("The request was saved, but the owner must start the bot before receiving notifications.")
