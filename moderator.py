from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from database import is_moderator, list_appeals, get_appeal, transition_appeal, activity_log
from keyboards import moderator_gate, mod_dashboard, appeal_actions
from states import MoreInfoStates

router = Router()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

async def authorized(event):
    uid = event.from_user.id
    return await is_moderator(uid)

@router.message(Command("mod"))
async def mod_entry(message: Message):
    if not await is_moderator(message.from_user.id):
        await message.answer(
            "MODERATOR ACCESS\n\nYou are not currently authorized to access the "
            "GTS NETWORK moderation panel.\n\nIf you are an authorized team member, "
            "submit a moderator access request.",
            reply_markup=moderator_gate()
        )
        return
    await message.answer("GTS NETWORK MODERATION PANEL\n\nSelect an option:", reply_markup=mod_dashboard())

@router.callback_query(F.data.startswith("mod:"))
async def mod_callbacks(call: CallbackQuery, state: FSMContext):
    if not await is_moderator(call.from_user.id):
        await call.answer("Access denied. Moderator approval is required.", show_alert=True)
        return
    parts = call.data.split(":")
    action = parts[1]
    if action == "logout":
        await call.message.edit_text("You have left the moderation panel.")
    elif action == "profile":
        await call.message.edit_text(
            f"MODERATOR PROFILE\n\nTelegram ID: {call.from_user.id}\n"
            f"Username: @{call.from_user.username or 'not set'}\n"
            f"Name: {call.from_user.full_name}",
            reply_markup=mod_dashboard()
        )
    elif action == "list":
        status = parts[2]
        rows = await list_appeals(status, 15)
        if not rows:
            await call.message.edit_text(f"No {status.replace('_',' ')} appeals.", reply_markup=mod_dashboard())
        else:
            await call.message.edit_text(f"{status.replace('_',' ').upper()} APPEALS\n\nSelect an appeal below.")
            for r in rows:
                text = (f"Appeal #{r['id']}\nUser ID: {r['user_id']}\nUsername: @{r['username'] or 'not set'}\n"
                        f"Group: {r['group_name']}\nReason for ban: {r['ban_reason']}\n"
                        f"Explanation: {r['explanation']}\nAgrees to rules: {'Yes' if r['agreement'] else 'No'}\n"
                        f"Submitted: {r['created_at']}\nStatus: {r['status']}")
                await call.message.answer(text, reply_markup=appeal_actions(r["id"]) if status in ("pending","under_review","more_info_required") else None)
    elif action in ("approve", "reject", "more", "user"):
        if len(parts) < 3 or not parts[2].isdigit():
            await call.answer("Invalid appeal.", show_alert=True); return
        appeal_id = int(parts[2])
        appeal = await get_appeal(appeal_id)
        if not appeal:
            await call.answer("Appeal not found.", show_alert=True); return
        if action == "user":
            await call.message.answer(
                f"APPLICANT PROFILE\nUser ID: {appeal['user_id']}\n"
                f"Username: @{appeal['username'] or 'not set'}\n"
                f"First name: {appeal['first_name']}"
            )
        elif action == "more":
            await state.update_data(appeal_id=appeal_id)
            await state.set_state(MoreInfoStates.response)
            await call.message.answer(f"Send the message to applicant for appeal #{appeal_id}.")
        else:
            new_status = "approved" if action == "approve" else "rejected"
            result = await transition_appeal(
                appeal_id, new_status, call.from_user.id, "", now(),
                ("pending","under_review","more_info_required")
            )
            if not result:
                await call.answer("This appeal has already been handled or is being processed.", show_alert=True)
                return
            try:
                await call.bot.send_message(
                    result["user_id"],
                    f"UPDATE ON APPEAL #{appeal_id}\n\n"
                    f"Your appeal has been {new_status}.\n"
                    f"Group: {result['group_name']}\n"
                    + ("The decision has been recorded by the moderation team." if new_status == "approved"
                       else "You may contact support if you need clarification.")
                )
            except (TelegramForbiddenError, TelegramBadRequest):
                pass
            await call.message.answer(f"Appeal #{appeal_id} has been {new_status}.")
    await call.answer()

@router.message(MoreInfoStates.response)
async def more_info_response(message: Message, state: FSMContext):
    if not await is_moderator(message.from_user.id):
        await state.clear()
        await message.answer("Access denied.")
        return
    data = await state.get_data()
    appeal_id = data.get("appeal_id")
    response = (message.text or "").strip()
    if not response or len(response) > 2000:
        await message.answer("Please send a message of up to 2000 characters.")
        return
    result = await transition_appeal(
        appeal_id, "more_info_required", message.from_user.id, response, now(),
        ("pending","under_review","more_info_required")
    )
    await state.clear()
    if not result:
        await message.answer("This appeal has already been handled.")
        return
    try:
        await message.bot.send_message(
            result["user_id"],
            f"MORE INFORMATION REQUIRED\n\n"
            f"The moderation team needs additional information for appeal #{appeal_id}.\n\n"
            f"Moderator message:\n{response}\n\n"
            "Please submit your response by contacting support through the bot."
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
    await message.answer(f"Your message for appeal #{appeal_id} has been sent.")
