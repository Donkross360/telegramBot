import logging
import requests
import asyncio
import nest_asyncio
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, ApplicationBuilder

# Apply nest_asyncio to handle event loop conflicts in environments like Jupyter or some IDEs
nest_asyncio.apply()

# Constants


# Configure logging
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

# Fetch exchange rates
def fetch_exchange_rates():
    url = f"https://openexchangerates.org/api/latest.json?app_id={EXCHANGE_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        return {
            "USD/NGN": rates.get("NGN", "N/A"),
            "GBP/NGN": rates.get("NGN", "N/A") / rates.get("GBP", 1),
            "EUR/NGN": rates.get("NGN", "N/A") / rates.get("EUR", 1),
        }
    except requests.RequestException as e:
        logging.error(f"Error fetching exchange rates: {e}")
        return None

# Start command with buttons
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Get Today's Rates", callback_data="get_rates")],
        [InlineKeyboardButton("Set Alert", callback_data="set_alert")],
        [InlineKeyboardButton("Start Alert Monitoring", callback_data="schedule_alert")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Exchange Rate Bot! Please choose an option below:",
        reply_markup=reply_markup,
    )

# Handle button clicks
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query_data = query.data
    await query.answer()  # Acknowledge the button press

    if query_data == "get_rates":
        rates = fetch_exchange_rates()
        if rates:
            message = (
                f"Today's Exchange Rates:\n"
                f"- USD/NGN: {rates['USD/NGN']:.2f}\n"
                f"- GBP/NGN: {rates['GBP/NGN']:.2f}\n"
                f"- EUR/NGN: {rates['EUR/NGN']:.2f}"
            )
        else:
            message = "Failed to fetch exchange rates. Please try again later."
        await query.edit_message_text(message)

    elif query_data == "set_alert":
        await query.edit_message_text(
            "Please use the format: /alert [CURRENCY_PAIR] [THRESHOLD_RATE]\n"
            "Example: /alert USD/NGN 850"
        )

    elif query_data == "schedule_alert":
        if "alerts" in context.user_data:
            if context.job_queue:
                context.job_queue.run_repeating(
                    check_alerts,
                    interval=3600,  # Check every hour
                    first=10,  # Start 10 seconds after scheduling
                    data={
                        "user_id": query.message.chat_id,
                        "alert": context.user_data["alerts"],
                    },
                )
                await query.edit_message_text("Alert monitoring started.")
            else:
                await query.edit_message_text("Job queue is not available. Please restart the bot.")
        else:
            await query.edit_message_text("No alert set. Use /alert first.")

# Get rates using /rate command
async def rate(update: Update, context: CallbackContext) -> None:
    rates = fetch_exchange_rates()
    if rates:
        message = (
            f"Today's Exchange Rates:\n"
            f"- USD/NGN: {rates['USD/NGN']:.2f}\n"
            f"- GBP/NGN: {rates['GBP/NGN']:.2f}\n"
            f"- EUR/NGN: {rates['EUR/NGN']:.2f}"
        )
    else:
        message = "Failed to fetch exchange rates. Please try again later."
    await update.message.reply_text(message)

# Set alerts using the /alert command
async def alert(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text.split()
    try:
        currency_pair = user_message[1].upper()
        threshold_rate = float(user_message[2])
        context.user_data["alerts"] = (currency_pair, threshold_rate)
        await update.message.reply_text(
            f"Alert set for {currency_pair} when it crosses {threshold_rate:.2f}."
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Usage: /alert [CURRENCY_PAIR] [THRESHOLD_RATE]\nExample: /alert USD/NGN 850"
        )

# Check alerts
async def check_alerts(context: CallbackContext) -> None:
    job = context.job
    user_id = job.data["user_id"]
    currency_pair, threshold_rate = job.data["alert"]
    rates = fetch_exchange_rates()
    if rates:
        current_rate = rates.get(currency_pair, None)
        if current_rate and current_rate >= threshold_rate:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Alert! {currency_pair} has hit {current_rate:.2f}, crossing your threshold of {threshold_rate:.2f}.",
            )
            job.schedule_removal()

# Set bot commands for the menu button
async def set_bot_commands(application):
    commands = [
        BotCommand(command="start", description="Start interacting with the bot"),
        BotCommand(command="rate", description="Get today's exchange rates"),
        BotCommand(command="alert", description="Set an alert for currency rates"),
    ]
    await application.bot.set_my_commands(commands)

# Main function
async def main():
    # Build the application with explicitly enabled JobQueue
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    

    # Start the JobQueue explicitly
    job_queue = application.job_queue

    # Set up command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("rate", rate))
    application.add_handler(CommandHandler("alert", alert))

    # Set bot commands
    await set_bot_commands(application)

    # Start the bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())  # Use asyncio.run to run the async function