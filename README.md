# Life Simulator Telegram Bot

A massive, fully modular 49-system Life Simulator running on Telegram, built with Python and PyTelegramBotAPI.

## Requirements
- Python 3.10+
- `pyTelegramBotAPI`

## How to run (Android Pydroid 3 & Linux/Windows)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Navigate to the game folder:
   ```bash
   cd life_simulator
   ```
3. Run the bot directly:
   ```bash
   python main.py
   ```

## Configuration
- `BOT_TOKEN` and `ADMIN_IDS` can be set as environment variables or directly inside `life_simulator/config.py`.

## Systems Included
- **Core:** Job Promotions, Education degrees, Business Hiring/Firing/Investments.
- **Economy:** Shared Market, Bank Loans, Credit Scores, Atomic Transactions.
- **Social:** Interactive Consent-based Friendships, Marriages, Child Aging via global clock.
- **Anti-Cheat:** Thread-safe memory lock rate limiters.
