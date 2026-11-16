# GTS NETWORK | APPEAL CENTER

A Telegram unban appeal and moderation bot built with Python 3.11+, Aiogram 3.x and SQLite.

## Features

- Appeal flow for `@chatyear`, `@whiteages`, `@fragte`, and `@chatteing`.
- Three-question appeal form with preview and edit controls.
- Duplicate active appeal prevention per user and group.
- User-owned appeal status view.
- Telegram ID-based moderator authorization.
- Owner approval of moderator requests; owner ID defaults to `8480522053`.
- Moderator appeal review, rejection, and request-more-information actions.
- Appeal history and moderator activity records.
- Owner statistics, moderator list, request list, appeal list, activity log and broadcast.
- SQLite persistence, WAL mode, logging and basic submission rate limiting.

## Setup

1. Create a bot with BotFather and copy its token.
2. Copy `.env.example` to `.env`.
3. Put the bot token in `BOT_TOKEN`. Do not commit `.env`.
4. Install Python 3.11 or later.
5. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Start the bot:

   ```bash
   python main.py
   ```

The SQLite database is created automatically at `data/appeals.sqlite3`.

## Commands

### Users
- `/start` - Open the appeal center.
- `/mod` - Open moderator panel or request access.
- `/status` - The status view is also available from the menu.

### Moderators
- `/mod` - Open moderator dashboard.
- `/pending` is not required; use the dashboard buttons.

### Owner
- `/admin` - Super admin overview.
- `/mods` - Approved moderators.
- `/requests` - Pending moderator requests.
- `/appeals` - Recent appeals.
- `/stats` - Bot statistics.
- `/addmod` - Instructions for the owner approval workflow.
- `/removemod <telegram_user_id>` - Revoke moderator access.
- `/broadcast` - Send an announcement to users.
- `/activity` - Recent moderator activity.

## Deployment

For Railway, create a worker service from this repository, set `BOT_TOKEN`, `OWNER_ID`, and `DATABASE_PATH`, and use the Procfile command `python main.py`.

For SQLite persistence, attach a persistent volume and set `DATABASE_PATH` to a location on that volume. Do not use ephemeral deployment storage if the database must survive redeployments. Run one bot worker against this SQLite database.

For Fly.io, create a persistent volume and mount it, then set `DATABASE_PATH` to a file on the mounted volume.

## Important operational notes

- The owner must start the bot at least once before the bot can send private notifications to the owner.
- A moderator must start the bot before receiving private messages from it.
- The bot must be added to the groups and granted appropriate administrator permissions before it can perform any actual unban action.
- This project records appeal decisions and notifies applicants. It does not automatically unban users. Automatic unbanning requires storing each group's numeric chat ID and implementing a separately permission-checked `unbanChatMember` operation.
- `Request More Information` sends a custom message and changes the status to `more_info_required`. The applicant's response collection workflow can be added as a follow-on feature; the initial version directs the applicant to contact support.
- Telegram bot API delivery cannot be guaranteed if a user blocks the bot or has not started it.
- SQLite is appropriate for a single worker. For multiple concurrent replicas, migrate to PostgreSQL and use a distributed transaction/locking strategy.

## Security

Never commit `.env` or share your bot token. Rotate the token with BotFather immediately if it is exposed. Owner and moderator permissions are checked on privileged commands and callback actions.
