async def start(update, context):
    context.user_data["state"] = "ASK_ROLE"

    await update.message.reply_text(
        "Welcome to RolePrep.\n\n"
        "Step 1: Enter the role you are applying for."
    )