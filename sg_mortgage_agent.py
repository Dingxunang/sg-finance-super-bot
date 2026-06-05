import requests
from openai import OpenAI

def get_latest_sora_rates():
    """Fetches the latest daily and compounded SORA rates from the official MAS API."""
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

        # Ensure values are parsed cleanly as floats to prevent runtime mathematical type errors
        return {
            "date": latest.get("end_of_day", "Unknown Date"),
            "sora_daily": float(latest.get("sora", 0.0)),
            "sora_3m": float(latest.get("sora_comp_3m", 0.0))
        }
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch live MAS SORA rates ({e}). Using conservative 2026 baseline fallbacks.")
        # Fallback values adjusted closer to realistic 2026 parameters
        return {"date": "Fallback Baseline (Recent)", "sora_daily": 3.45, "sora_3m": 3.55}

def run_mortgage_agent():
    # 1. Fetch real-time benchmark parameters
    sora_data = get_latest_sora_rates()

    print("\n" + "="*60)
    print("🇸🇬 ENTER YOUR MORTGAGE DETAILS")
    print("="*60)

    # Gather dynamic inputs from the user in the terminal
    try:
        loan_str = input("Outstanding Loan Amount (SGD) [default 800000]: ").replace(',', '').strip()
        loan_amount = float(loan_str) if loan_str else 800000.0

        fixed_str = input("Offered Fixed Rate (%) [default 2.85]: ").strip()
        fixed_rate = float(fixed_str) if fixed_str else 2.85

        spread_str = input("Floating Loan Spread (%) [default 0.65]: ").strip()
        current_spread = float(spread_str) if spread_str else 0.65
    except ValueError:
        print("\n⚠️ Invalid input detected. Reverting to default values.")
        loan_amount, fixed_rate, current_spread = 800000.0, 2.85, 0.65

    # Calculate current effective floating loan rate for comparison
    effective_floating_rate = round(sora_data['sora_3m'] + current_spread, 3)

    # 2. Point to the local Ollama orchestration instance
    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    # Enhanced prompt with structured markdown guidance and analytical expectations
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
    3. Conclude with a definitive, highly professional risk-versus-reward recommendation (e.g., assessing the likelihood of interest rate adjustments over a 2-year horizon).
    4. Keep your output direct, eliminating generic conversational fluff.
    """

    print("\n" + "="*60)
    print(f"🇸🇬 SG Free Local Refinance Agent: ACTIVE")
    print(f"Loaded Context Date: {sora_data['date']}")
    print(f"Loaded 3M SORA:      {sora_data['sora_3m']}%")
    print(f"Effective Floating:  {effective_floating_rate}%")
    print("="*60 + "\n")

    # Dynamically inject the user's inputted numbers into the query
    user_query = f"I have a loan amount of SGD {loan_amount:,.2f}. A bank offered me a fixed rate at {fixed_rate}%. My alternative is a floating rate at 3M SORA + {current_spread}%. Which one should I choose based on the live SORA rate today?"
    print(f"User: {user_query}\n")

    try:
        # 3. Request inference execution across local hardware
        completion = client.chat.completions.create(
            model="gemma2",  # Ensure this matches your local 'ollama list' identifier exactly
            messages=[  # type: ignore
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1  # Highly deterministic to focus entirely on financial math accuracy
        )

        print(f"Agent Response:\n\n{completion.choices[0].message.content}")
        print("\n" + "="*60)

    except Exception as infer_err:
        print(f"Execution Error: Local inference model call failed. Ensure Ollama is running (`ollama serve` or `ollama run gemma2`). Details: {infer_err}")

if __name__ == "__main__":
    run_mortgage_agent()