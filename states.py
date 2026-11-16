from aiogram.fsm.state import State, StatesGroup

class AppealStates(StatesGroup):
    ban_reason = State()
    explanation = State()
    agreement = State()

class ModeratorRequestStates(StatesGroup):
    reason = State()

class MoreInfoStates(StatesGroup):
    response = State()

class BroadcastStates(StatesGroup):
    message = State()
