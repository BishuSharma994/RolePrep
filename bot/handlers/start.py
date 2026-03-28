from backend.handlers.payment_handler import POLICY_URL


async def start(update, context):
    context.user_data.clear()
    context.user_data["state"] = "ASK_ROLE"
    context.user_data["policy_accepted"] = False

    await update.message.reply_text(
        "Welcome to RolePrep.\n\n"
        "Policy: No refunds for this digital service.\n"
        f"Read full policy: {POLICY_URL}\n\n"
        "Step 1: Enter the role you are applying for."
    )


async def policy_command(update, context):
    await update.message.reply_text(
        f"Read full policy:\n{POLICY_URL}"
    )
