import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from datetime import datetime

# Telegram Bot API Key
TELEGRAM_API_KEY = '6809725342:AAFrzk0Xm9SQdmuA13q0dMyNEU5QXHITgKI'

# Google Sheets Configuration
GOOGLE_SHEETS_API_KEY = 'AIzaSyAJQG1qtq06pDwI3ZWerBBWGrwytkI8MPI'
SPREADSHEET_ID = '1Qt7k4PdJS4knboB_Vy2m9URi3etYFWZ7lArWXEakU9Q'
CONTACTS_SHEET_NAME = 'Bot_Contacts'
BREAKDOWN_SHEET_NAME = 'BreakdownSheet'
REPAIRED_SHEET_NAME = 'RepairedSheet'

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Define conversation states
MACHINE_NUMBER = range(1)

def fetch_sheet_data(sheet_name):
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}?key={GOOGLE_SHEETS_API_KEY}'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    return response.json().get('values', [])[1:]  # Skip header row

def fetch_contacts():
    return fetch_sheet_data(CONTACTS_SHEET_NAME)

def fetch_breakdown_data():
    return fetch_sheet_data(BREAKDOWN_SHEET_NAME)

def fetch_repaired_data():
    return fetch_sheet_data(REPAIRED_SHEET_NAME)

def parse_date(date_string):
    return datetime.strptime(date_string, "%d/%m/%Y %H:%M:%S")

# Updated function to handle whitespace in machine numbers
def normalize_machine_number(machine_no):
    return ''.join(machine_no.split())

def get_machine_status(machine_no):
    normalized_machine_no = normalize_machine_number(machine_no)
    breakdown_data = fetch_breakdown_data()
    repaired_data = fetch_repaired_data()

    latest_breakdown = None
    latest_repair = None

    # Find the latest breakdown entry
    for row in reversed(breakdown_data):
        if normalize_machine_number(row[1]) == normalized_machine_no:
            latest_breakdown = (parse_date(row[0]), row[2])
            break

    # Find the latest repair entry
    for row in reversed(repaired_data):
        if normalize_machine_number(row[1]) == normalized_machine_no:
            latest_repair = (parse_date(row[0]), row[2])
            break

    if latest_breakdown and latest_repair:
        if latest_repair[0] > latest_breakdown[0]:
            return f"Machine {machine_no} was repaired. Last repaired on {latest_repair[0].strftime('%d/%m/%Y %H:%M:%S')}. Status: {latest_repair[1]}"
        else:
            return f"Machine {machine_no} is currently broken down. Last reported on {latest_breakdown[0].strftime('%d/%m/%Y %H:%M:%S')}. Status: {latest_breakdown[1]}"
    elif latest_breakdown:
        return f"Machine {machine_no} is currently broken down. Last reported on {latest_breakdown[0].strftime('%d/%m/%Y %H:%M:%S')}. Status: {latest_breakdown[1]}"
    elif latest_repair:
        return f"Machine {machine_no} was repaired. Last repaired on {latest_repair[0].strftime('%d/%m/%Y %H:%M:%S')}. Status: {latest_repair[1]}"
    else:
        return f"Machine {machine_no} is currently running."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome to Samudra! I'm a bot, please talk to me!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
    Here are the commands you can use:
    /start - Get a welcome message
    /help - Show this help message
    /contacts - Choose a specific contact
    /contact_all - Show all contacts
    /machine_status - Check the status of a specific machine
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts_data = fetch_contacts()
    if not contacts_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to fetch contacts.")
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"contact_{i}")]
        for i, (name, _) in enumerate(contacts_data)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Which contact do you want?",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    contact_index = int(query.data.split('_')[1])
    contacts_data = fetch_contacts()
    
    if contacts_data and 0 <= contact_index < len(contacts_data):
        name, phone = contacts_data[contact_index]
        await context.bot.send_contact(
            chat_id=update.effective_chat.id,
            phone_number=phone,
            first_name=name
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Contact not found.")

async def contact_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts_data = fetch_contacts()
    if not contacts_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No contacts found.")
        return

    for name, phone in contacts_data:
        await context.bot.send_contact(
            chat_id=update.effective_chat.id,
            phone_number=phone,
            first_name=name
        )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="You can tap on these contacts to call directly.")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_member in update.message.new_chat_members:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome to Samudra, {new_member.first_name}!"
        )

# Updated function to prompt for QR code scanning
async def start_machine_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Note: Telegram doesn't have a built-in QR scanner, so we'll guide the user to use their device's camera
    await update.message.reply_text(
        "Please scan the machine's QR code using your device's camera. "
        "Once scanned, send the machine number here."
    )
    return MACHINE_NUMBER

# Updated function to handle machine status check with normalized machine number
async def check_machine_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    machine_no = update.message.text
    normalized_machine_no = normalize_machine_number(machine_no)
    status = get_machine_status(normalized_machine_no)
    await update.message.reply_text(status)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Machine status check cancelled.")
    return ConversationHandler.END

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_API_KEY).build()
    
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help_command)
    contacts_handler = CommandHandler('contacts', contacts)
    contact_all_handler = CommandHandler('contact_all', contact_all)
    new_member_handler = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    button_handler = CallbackQueryHandler(button)

    # Create conversation handler for machine status
    machine_status_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('machine_status', start_machine_status)],
        states={
            MACHINE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_machine_status)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(contacts_handler)
    application.add_handler(contact_all_handler)
    application.add_handler(new_member_handler)
    application.add_handler(button_handler)
    application.add_handler(machine_status_conv_handler)
    
    application.run_polling()