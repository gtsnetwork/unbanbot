from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

GROUPS = ("@chatyear", "@whiteages", "@fragte", "@chatteing")

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_menu():
    return kb([
        [InlineKeyboardButton(text="Submit an Appeal", callback_data="user:appeal")],
        [InlineKeyboardButton(text="Check Appeal Status", callback_data="user:status")],
        [InlineKeyboardButton(text="Appeal Guidelines", callback_data="user:guidelines")],
        [InlineKeyboardButton(text="Contact Support", callback_data="user:support")],
    ])

def group_menu():
    return kb([[InlineKeyboardButton(text=g, callback_data=f"appeal:group:{g}")] for g in GROUPS] +
              [[InlineKeyboardButton(text="Cancel", callback_data="user:home")]])

def agreement_menu():
    return kb([
        [InlineKeyboardButton(text="I Agree", callback_data="appeal:agreement:yes")],
        [InlineKeyboardButton(text="I Do Not Agree", callback_data="appeal:agreement:no")],
        [InlineKeyboardButton(text="Cancel", callback_data="user:home")],
    ])

def preview_menu():
    return kb([
        [InlineKeyboardButton(text="Submit Appeal", callback_data="appeal:submit")],
        [InlineKeyboardButton(text="Edit Answers", callback_data="appeal:edit")],
        [InlineKeyboardButton(text="Cancel", callback_data="user:home")],
    ])

def edit_menu():
    return kb([
        [InlineKeyboardButton(text="Edit Ban Reason", callback_data="appeal:edit:ban")],
        [InlineKeyboardButton(text="Edit Explanation", callback_data="appeal:edit:explanation")],
        [InlineKeyboardButton(text="Edit Rules Agreement", callback_data="appeal:edit:agreement")],
        [InlineKeyboardButton(text="Back to Preview", callback_data="appeal:preview")],
    ])

def moderator_gate():
    return kb([[InlineKeyboardButton(text="Request Moderator Access", callback_data="mod:request")]])

def owner_request_buttons(request_id):
    return kb([[
        InlineKeyboardButton(text="Approve Moderator", callback_data=f"admin:mod:approve:{request_id}"),
        InlineKeyboardButton(text="Reject Request", callback_data=f"admin:mod:reject:{request_id}")
    ]])

def mod_dashboard():
    return kb([
        [InlineKeyboardButton(text="Pending Appeals", callback_data="mod:list:pending")],
        [InlineKeyboardButton(text="Approved Appeals", callback_data="mod:list:approved")],
        [InlineKeyboardButton(text="Rejected Appeals", callback_data="mod:list:rejected")],
        [InlineKeyboardButton(text="Moderator Profile", callback_data="mod:profile")],
        [InlineKeyboardButton(text="Logout", callback_data="mod:logout")],
    ])

def appeal_actions(appeal_id):
    return kb([
        [InlineKeyboardButton(text="Approve", callback_data=f"mod:approve:{appeal_id}"),
         InlineKeyboardButton(text="Reject", callback_data=f"mod:reject:{appeal_id}")],
        [InlineKeyboardButton(text="Request More Information", callback_data=f"mod:more:{appeal_id}")],
        [InlineKeyboardButton(text="View User Profile", callback_data=f"mod:user:{appeal_id}")],
    ])
