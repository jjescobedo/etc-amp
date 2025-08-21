# ETC-AMP Trading Bot

This is a simple trading bot for the ETC-AMP exchange challenge. It uses a weighted average of recent trade prices (weighted by trade size) to make buy and sell decisions. The bot does not use historical backtesting, but is designed to work in live or simulated environments.

## How it works
- The bot connects to the exchange and listens for market data.
- For each symbol, it calculates a weighted average price from the most recent trades.
- It places buy or sell orders when the current market prices deviate from the weighted average by a configurable threshold.
- Order and position management is handled automatically.

## Usage
1. Configure your team name in `bot.py`.
2. Make the script executable: `chmod +x bot.py`
3. Run in a loop (example for prod-like test):
   ```sh
   while true; do ./bot.py --test prod-like; sleep 1; done
   ```

## Notes
- No backtesting data is provided; the bot is designed for live trading.
- The code is clean and should work as described.
- For more details, see comments in `bot.py`.

## License
MIT
