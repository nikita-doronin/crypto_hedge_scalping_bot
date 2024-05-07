# README

## Disclaimer

This software for crypto algorithmic trading is provided as-is, without any warranties or guarantees of its performance. The author is not responsible for any losses incurred through the use of this software. Users are advised to conduct their own research and exercise caution when using this strategy. The trading strategy implemented in this software is not financial advice, and users should seek professional financial advice before making any investment decisions.

## Legal statement

The source code is protected by **Attribution-NonCommercial (CC BY-NC)** license.
The **`LICENCE`** itself could be found in repository root directory.

This license allows others to distribute, remix, adapt, and build upon my work non-commercially, as long as they give me credit for the original creation and indicate if changes were made. This license prohibits the use of my work for commercial purposes without my explicit permission.

Using third-party Python libraries in my project does not necessarily mean my entire project adopts the same license as those libraries. When I use a library in my project, I am typically using it as a dependency. The license I choose for my project affects only my code and original trading idea, not the libraries I use.

## Trading Strategy

Detailed strategy visualisation with examples could be found in repository root directory:

`strategy_visualisation.pdf`

Description:
- Strategy calculates new EMA every new candle.
- There are 5 grids are calculated based on EMA output: (4 Long Limit Orders and 1 Short Market Order).
- The aim of the strategy is to catch the rapid price movement and take a profit from a price pullback.
- In case new price continue falling there is no Stop Loss for a Long position. The risk is hedged by Short Position so the trade is closed at break-even without actual loss.
- There is only one situation that could really close the trade in loss: when strategy collected all the grids and price rapidly returned back to initial level. In this case Long Position will be closed in profit, however the Short Position will be closed in loss and actual result is Loss.
- Strategy is using hedge mode for trading that allows to open Long and Short orders at the same time.
- The timeframe is defined by user. The EMA length is defined by user. Grids and volumes are defined by user.

## Live Trading Bot

Live Trading Bot was created for the Binance Futures Exchange. The bot itself could be found in `live_bot` folder of root directory:

`__main.py__`

The script logic could be found here:
`live_bot/script_logic/script_logic.drawio`.

You may be using [drawio](https://www.drawio.com/) to open the file. Otherwise you could open the **.png** file:
`live_bot/script_logic/script_logic.drawio.png`


### To run the Trading Bot follow the next steps:

1. Create a virtual involvement or use Docker instead.

2. Install dependencies `requirements.in`.

3. Set up the credentials `live_bot/set_creds/set_creds.ipynb` for:

    - **Exchange API Keys:**
        - api_key
        - api_secret

    - **Your telegram bot:**
        - telegram_token_id
        - telegram_chat_id

    - **Your SQL Database:**
        - sql_host
        - sql_user
        - sql_password
        - sql_database_name

4. Input strategy settings into `live_bot/bot_settings.json`, note that you should update only the inputs with the prefix **"inp_..."**:

    - **"inp_account"**: Put your account name here just to define telegram message and save the trade results
    - **"inp_bot_name"**: Put your bot name here just to define telegram message and save the trade results
    - **"inp_create_table_in_db"**: **true** or **false**, will create the table in case the table doesn't exist, **false** by default
    - **"inp_sql_table"**: Put your custom database name, **"results_crypto_futures"** by default
    - **"inp_stop_bot"**: Input to stop the bot, **yes** or **no**, **"no"** by default
    - **"inp_update_settings"**: Input to update the settings in case bos is running, **yes** or **no**, **"no"** by default
    - **"inp_crypto"**: Put the asset you want to trade (e.g. **"BTCUSDT"**, **"ETHUSDT"**)
    - **"inp_capital"**: Put the deposit you want to trade WITHOUT leverage (in **USDT**)
    - **"inp_leverage"**: Put the leverage you want to trade **1** by default. In case you want to trade with leverage, put the amount to capital without the leverage (e.g. you want to trade 500 USDT with leverage 2, so put 500 to **"inp_capital"** and 2 to **"inp_leverage"** and you will trade 1000 USDT)
    - **"inp_ema_length"**: Put the length of EMA, **2** by default
    - **"inp_timeframe"**: Put the timeframe of EMA, **"5m"** (m - minutes) by default
    - **"inp_lookback_1st_run"**: Put the lookback period to get the historical candles and calculate EMA correctly, **"240m"** (m - minutes) by default, recommended 48 candles back (e.g. 5m * 48 = 240m)
    - **"inp_grid_1_long_per_dca"**: Put the % shift down of 1st long grid
    - **"inp_grid_2_long_per_dca"**: Put the % shift down of 2nd long grid
    - **"inp_grid_3_long_per_dca"**: Put the % shift down of 3rd long grid
    - **"inp_grid_4_long_per_dca"**: Put the % shift down of 4th long grid
    - **"inp_grid_5_short_per_dca"**: Put the % shift down of 5th short grid
    - **"inp_1_grid_long_per_deposit"**: Put the % of total deposit to for 1st long grid
    - **"inp_2_grid_long_per_deposit"**: Put the % of total deposit to for 2nd long grid
    - **"inp_3_grid_long_per_deposit"**: Put the % of total deposit to for 3rd long grid
    - **"inp_4_grid_long_per_deposit"**: Put the % of total deposit to for 4th long grid
    - **"inp_5_grid_short_per_deposit"**: Put the % of total deposit to for 5th short grid
    - **"inp_tp_long_per"**: Put the Take Profit in % for long position
    - **"inp_tp_short_per"**: Put the Take Profit in % for short position

5. Run the `crypto_hedge_scalping_bot/live_bot/__main__.py`.

### To stop the Trading Bot follow the next steps:

1. Input **yes** to **"inp_stop_bot"** inside `live_bot/bot_settings.json`, save it.
2. Use **KeyboardInterrupt** (usually Control+C or Delete) inside your Terminal.

## Strategy Backtest
### Python backtest

The Strategy Backtest script could be found in `backtest` folder of root directory:

`backtest.ipynb`

1. Get the tick data. It could be found on official [Binance website](https://data.binance.vision/?prefix=data/futures/um/monthly/trades/).

2. Save the tick data at `crypto_hedge_scalping_bot/backtest/raw_data`.

3. Run the script that will clean and concat the data for future backtest `crypto_hedge_scalping_bot/backtest/prepare_data.ipynb`.

4. The output will be saved under `crypto_hedge_scalping_bot/backtest/cleaned_data`.

5. Run the `crypto_hedge_scalping_bot/backtest/prepare_data.ipynb` to evaluate the historical strategy performance.

### Pine Script (TradingView) backtest

For quick strategy performance check via TradingView find the Pine Script source at `crypto_hedge_scalping_bot/backtest/pinescript`.

Script is also available on [TradingView](https://tradingview.com/script/KnHofBm1-hedge-scalp/)