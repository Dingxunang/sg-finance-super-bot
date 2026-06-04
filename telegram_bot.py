import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# --- 1. DATA FETCHING (MAS API) ---
def get_latest_sora_rates():
    url = "https://eservices.mas.gov.sg/api/action/datastore/search.json"
    params = {
        "resource_id": "5f2b18a5-1174-48e2-a3c1-0c3fbcd299e5",
        "sort": "end_of_day desc",
        "limit": 1
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        records = data.get("result", {}).get("records", [])
        if not records:
            raise ValueError("No records returned from MAS Datastore.")
        latest = records[0]
        return {
            "date": latest.get("end_of_day", "Unknown Date"),
            "sora_daily": float(latest.get("sora", 0.0)),
            "sora_3m": float(latest.get("sora_comp_3m", 0.0))
        }
    except Exception:
        # 2026 Baseline Fallback Parameters
        return {"date": "Fallback Baseline (Recent)", "sora_daily": 3.45, "sora_3m": 3.55}

# --- 2. TELEGRAM CORE COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🇸🇬 *Welcome to the SG Mortgage Refinance Agent!*\n\n"
        "To evaluate a loan option against the live MAS 3M SORA rate, please send your details in this format:\n\n"
        "`Loan: 800000\n"
        "Fixed: 2.85\n"
        "Spread: 0.65`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("🔄 Fetching live MAS SORA data and calculating... Please hold.")

    # Simple text parsing parameters
    loan_amount = 800000.0
    fixed_rate = 2.85
    current_spread = 0.65

    try:
        for line in text.split('\n'):
            if 'loan:' in line.lower():
                loan_amount = float(line.lower().replace('loan:', '').replace(',', '').strip())
            if 'fixed:' in line.lower():
                fixed_rate = float(line.lower().replace('fixed:', '').replace('%', '').strip())
            if 'spread:' in line.lower():
                current_spread = float(line.lower().replace('spread:', '').replace('%', '').strip())
    except Exception:
        await update.message.reply_text("⚠️ Could not parse your text perfectly. Using default configuration baseline.")

    sora_data = get_latest_sora_rates()
    effective_floating_rate = round(sora_data['sora_3m'] + current_spread, 3)

    # --- 3. GOOGLE GEMINI AI INFERENCE ---
    gemini_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_key)

    system_prompt = f"""
    You are an expert Singapore Mortgage Advisory Agent specializing in residential private property refinancing.
    
    CRITICAL LIVE BENCHMARK CONTEXT:
    - Current Data Target Date: {sora_data['date']}
    - Live Daily SORA: {sora_data['sora_daily']}%
    - Live 3-Month Compounded SORA (3M SORA): {sora_data['sora_3m']}%
    - Customer's Effective Floating Rate (3M SORA + {current_spread}%): {effective_floating_rate}%
    - Customer's Loan Amount: SGD {loan_amount:,.2f}

    ROLE ACTIONS:
    1. Systematically compare the user's options using the exact live mathematical figures provided.
    2. Output your financial comparison breakdown cleanly using a Markdown Table format. Ensure all monetary values are explicitly formatted in SGD (e.g., S$ or SGD).
    3. Conclude with a definitive, highly professional risk-versus-reward recommendation over a 2-year horizon.
    4. Keep your output direct, eliminating generic conversational fluff.
    """

    user_query = f"I have a loan amount of SGD {loan_amount:,.2f}. A bank offered me a fixed rate at {fixed_rate}%. My alternative is a floating rate at 3M SORA + {current_spread}%. Which one should I choose based on the live SORA rate today?"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_query,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1
            )
        )
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error during AI calculation execution: {e}")

# --- 4. WEBHOOK ENTRYPOINT FOR DEPLOYMENT ---
if __name__ == "__main__":
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    # Render automatically generates this environment variable variable
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"Starting webhook on port {PORT} via endpoint {RENDER_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}"
    )