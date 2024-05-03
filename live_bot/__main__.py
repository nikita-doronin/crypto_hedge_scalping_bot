import os,asyncio,requests,json,re,csv,logging,sql_queries
import pandas as pd
import mysql.connector as sql_connect
import keyring as kr
from sys import exit
from time import sleep
from math import floor
from pandas_ta import ema
from datetime import timedelta
from binance import Client,AsyncClient,BinanceSocketManager
from logging.handlers import RotatingFileHandler
from logging import Formatter

def get_saved_creds():
    # get credentials that where generated at 'set_creds.ipynb':
    global api_key,api_secret,telegram_chat_id,telegram_token_id,sql_host,sql_user,sql_password,sql_database_name
    try:
        api_key = kr.get_password("exchange_creds",'api_key')
        api_secret = kr.get_password("exchange_creds",'api_secret')
        telegram_chat_id = kr.get_password("telegram_creds",'telegram_chat_id')
        telegram_token_id = kr.get_password("telegram_creds",'telegram_token_id')
        sql_host = kr.get_password("sql_creds",'sql_host')
        sql_user = kr.get_password("sql_creds",'sql_user')
        sql_password =  kr.get_password("sql_creds",'sql_password')
        sql_database_name = kr.get_password("sql_creds",'sql_database_name')
        return api_key,api_secret,telegram_chat_id,telegram_token_id,sql_host,sql_user,sql_password,sql_database_name
    except:
        exit()

get_saved_creds()

def send_telegram(text):
    global telegram_chat_id,telegram_token_id
    try: # send to telegram
        params = {'chat_id':telegram_chat_id, 'text': text, 'parse_mode': 'HTML'}
        resp = requests.post('https://api.telegram.org/bot{}/sendMessage'.format(telegram_token_id), params)
        resp.raise_for_status()
        pass
    except:
        pass

def get_script_directory():
    # Get the path of the directory containing the currently running script:
    global script_directory
    try:
        script_directory = os.path.dirname(os.path.realpath(__file__))
        return script_directory
    except Exception as e:
        send_telegram('Failed to get current directory. Script will be exited.')
        exit()

get_script_directory()

def find_strategy_settings():
    global settings_path
    def find_json_file(file_name):
        # Find the bot_settings.json file in current folder:
        for root, dirs, files in os.walk(script_directory):
            if file_name in files:
                return os.path.join(root, file_name)
        return None

    # Name of json file that need to be found:
    try:
        settings_path = find_json_file(file_name='bot_settings.json')
        del find_json_file
    except Exception as e:
        send_telegram(f'Failed to get settings path.\nScript will be exited.\nReason: {e}')
        exit()

    if not settings_path:
        send_telegram(f'bot_settings.json not found in the current directory.\nScript will be exited.')
        exit()

    return settings_path

find_strategy_settings()

# Write existing settings to JSON:
def write_new_json(a_list): # Convert and save CURRENT Python list to JSON
    global initial_list
    try:
        with open(settings_path, 'w') as fp:
            json.dump(a_list, fp, indent=4)
        fp.close()
        del fp, a_list
    except Exception as e:
        pass

def read_initial_list():
    global initial_list,bsm_dict,logs_path,trade_results_path,script_directory
    try:
        # Read settings from JSON
        initial_list_json=open(settings_path, 'rb') # read initial settings of strategy
        initial_list = json.load(initial_list_json)
        initial_list_json.close()
        del initial_list_json
        bsm_dict={} # dictionary for binance socket manager

        # Getting the folder path and other paths to save logs:
        logs_path = script_directory+'/'+initial_list['inp_account']+'_'+initial_list['inp_bot_name']+'_'+initial_list['inp_crypto']+'.log'
        trade_results_path = script_directory +'/'+initial_list['inp_account']+'_'+initial_list['inp_bot_name']+'_'+initial_list['inp_crypto']+'_results'+'.csv'
        del script_directory
        return initial_list,bsm_dict,logs_path,trade_results_path
    except Exception as e:
        send_telegram(f'Failed to read from JSON or get settings path.\nScript will be exited.\nReason: {e}')
        exit()

read_initial_list()

# Save Logs from API:
logger_api = logging.getLogger() # get named logger
handler = RotatingFileHandler(filename=logs_path, mode='a', maxBytes=20*1024*1024,backupCount=2, encoding='utf-8', delay=False) # save logs and when it will be more than 20 Mb, create a copy and continue, maximum 2 copies are allowed + active file
formatter = Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')  # create formatter and add to handler
handler.setFormatter(formatter) # create formatter and add to handler
logger_api.addHandler(handler) # add the handler to named logger
logger_api.setLevel(logging.INFO) # set the logging level

def error_logger(error_no,error_msg): # Error logging
	
    send_telegram(initial_list['inp_account']+', '+initial_list['inp_bot_name']+', '+initial_list['inp_crypto']+f', Error - {error_no}\n{error_msg}')

    try:
        logger_api.error('error_no: '+str(error_no)+' ,error_msg: '+str(error_msg)) # to log the message
        pass
    except:
        pass

def change_position_mode():
    global logger_api
    while True:
        try:
            position_mode=client.futures_change_position_mode(dualSidePosition=True) # Change position mode to Hedge-mode: (dualSidePosition=True)
            try:
                logger_api.info('RECEIVED futures_change_position_mode: '+str(position_mode)) # to log the message
            except:
                pass
            del position_mode
            break
        except Exception as e:
            if str(e) == 'APIError(code=-4059): No need to change position side.': # break the loop if position side is already setted
                break
            else:
                error_logger(error_no=2,error_msg=e)
            sleep(0.5)
            del e
            pass

def change_margin_settings():
    global initial_list, logger_api
    while True:
        try: # Change leverage
            change_leverage=client.futures_change_leverage(symbol=initial_list['inp_crypto'],leverage=initial_list['inp_leverage'])
            try:
                logger_api.info('RECEIVED futures_change_leverage: '+str(change_leverage)) # to log the message
            except:
                pass
            del change_leverage
            break
        except Exception as e: # no need to break the loop in this case, becouse binance not returning error
            error_logger(error_no=3,error_msg=e)
            sleep(0.5)
            del e
            pass

    while True:
        try: # Change margin type to isolated or CROSSED
            change_margin_type=client.futures_change_margin_type(symbol=initial_list['inp_crypto'],marginType='CROSSED')
            try:
                logger_api.info('RECEIVED futures_change_leverage: '+str(change_margin_type)) # to log the message
            except:
                pass
            del change_margin_type
            break
        except Exception as e:
            if str(e) == 'APIError(code=-4046): No need to change margin type.': # break the loop if margin is already setted
                break
            else:
                error_logger(error_no=4,error_msg=e)
            sleep(0.5)
            del e
            pass

def check_precision():
    global initial_list, logger_api

    while True: # Check precision of qty and price
        try:
            info = client.futures_exchange_info()
            # try:
            #     logger_api.info('RECEIVED futures_exchange_info: '+str(info)) # to log the message
            # except:
            #     pass
            for i in range(0,len(info['symbols'])): # Get the decimal rounding of both price and qty
                if info['symbols'][i]['symbol'] == initial_list['inp_crypto']:
                    pri = info['symbols'][i]['filters'][0]['tickSize']
                    qty = info['symbols'][i]['filters'][1]['minQty']
                    break

            counter = 0
            for i in range(0,len(pri)): # type: ignore
                    counter += 1
                    if pri[i] == '1': # type: ignore
                        break 
            initial_list['precision_pri'] = counter - 2

            counter = 0
            for i in range(0,len(qty)): # type: ignore
                counter += 1
                if qty[i] == '1': # type: ignore
                    break 
            initial_list['precision_qty'] = counter - 2

            del info, i, counter, pri, qty #type:ignore
            break
        except Exception as e:
            error_logger(error_no=5,error_msg=e)
            sleep(0.5)
            del e
            pass
    write_new_json(initial_list) # save sttings to JSON

def calculate_returns():
    global initial_list, logger_api

    try: # calculate returns of trade and save it
        new_data_long=[]
        new_data_short=[]
        sql_val=()
        sql_val_long=()
        sql_val_short=()
        if initial_list['long_trade']:
            # Long calculations:
            pnl_long = initial_list['end_value_long'] - initial_list['initial_value_long']

            total_commission_long = initial_list['entry_commission_amount_long'] + initial_list['exit_commission_amount_long']
            net_pnl_long = pnl_long - total_commission_long
            net_pnl_long = round(net_pnl_long,5)

            roi_trade_long = (net_pnl_long/initial_list['initial_value_long']) * 100 # returns on trade (money really used)
            roi_trade_long = round(roi_trade_long,5)

            roe_trade_long = (net_pnl_long/initial_list['usdt_cross_wallet_balance']) * 100 # returns on total deposit account
            roe_trade_long = round(roe_trade_long,5)

            ro_capital_trade_long = (net_pnl_long/initial_list['inp_capital']) * 100 # returns on capital dedicated to this strategy
            ro_capital_trade_long = round(ro_capital_trade_long,5)

            total_commission_long = round(total_commission_long,5)

            initial_list['initial_value_long'] = round(initial_list['initial_value_long'],5)
            SecToConvert_long = pd.to_datetime(initial_list['end_time_trade_long']) - pd.to_datetime(initial_list['start_time_trade_long']) #return time from string back to pandas datetime
            SecToConvert_long = SecToConvert_long.total_seconds()
            duration_long = str(timedelta(seconds = SecToConvert_long))

            avg_entry_price_long=round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long'], initial_list['precision_pri'])

            if initial_list['lowest_price'] < float(avg_entry_price_long): # long drawdown calculation
                account_drawdown_long = initial_list['usdt_cross_wallet_balance'] - (initial_list['initial_value_long'] - ((initial_list['initial_value_long']/avg_entry_price_long)*initial_list['lowest_price'])) # drawdown to all account deposit
                account_drawdown_long_per = -abs(round(((1-(account_drawdown_long/initial_list['usdt_cross_wallet_balance']))*100),5))

                capital_drawdown_long = initial_list['inp_capital'] - (initial_list['initial_value_long'] - ((initial_list['initial_value_long']/avg_entry_price_long)*initial_list['lowest_price'])) # drawdown to capital dedicated to this strategy
                capital_drawdown_long_per = -abs(round(((1-(capital_drawdown_long/initial_list['inp_capital']))*100),5))
                del account_drawdown_long, capital_drawdown_long
            else:
                account_drawdown_long_per = 0
                capital_drawdown_long_per = 0

            new_data_long = [initial_list['inp_account'],initial_list['inp_crypto'],initial_list['inp_bot_name'],'binance','main','futures',initial_list['inp_leverage'],initial_list['inp_timeframe'],pd.to_datetime(initial_list['start_time_trade_long']),pd.to_datetime(initial_list['end_time_trade_long']),'long',initial_list['inp_capital'],net_pnl_long,initial_list['initial_value_long'],initial_list['end_value_long'],total_commission_long,roi_trade_long,roe_trade_long,ro_capital_trade_long,initial_list['avg_entry_price_grid_1_long'],avg_entry_price_long,initial_list['avg_exit_price_grid_long'],initial_list['entry_commission_amount_long'],initial_list['entry_commission_asset_long'],initial_list['exit_commission_amount_long'],initial_list['exit_commission_asset_long'],initial_list['usdt_wallet_balance'],initial_list['usdt_cross_wallet_balance'],account_drawdown_long_per,capital_drawdown_long_per]
            sql_val_long = (initial_list['inp_sql_table'],initial_list['inp_account'],initial_list['inp_crypto'],initial_list['inp_bot_name'],'binance','main','futures',initial_list['inp_leverage'],initial_list['inp_timeframe'],str(pd.to_datetime(initial_list['start_time_trade_long'])),str(pd.to_datetime(initial_list['end_time_trade_long'])),'long',initial_list['inp_capital'],net_pnl_long,initial_list['initial_value_long'],initial_list['end_value_long'],total_commission_long,roi_trade_long,roe_trade_long,ro_capital_trade_long,initial_list['avg_entry_price_grid_1_long'],avg_entry_price_long,initial_list['avg_exit_price_grid_long'],initial_list['entry_commission_amount_long'],initial_list['entry_commission_asset_long'],initial_list['exit_commission_amount_long'],initial_list['exit_commission_asset_long'],initial_list['usdt_wallet_balance'],initial_list['usdt_cross_wallet_balance'],account_drawdown_long_per,capital_drawdown_long_per)

            send_telegram('Account: '+initial_list['inp_account']+'\nBot: '+initial_list['inp_bot_name']+'\nAsset: '+initial_list['inp_crypto']+'\nTF: '+initial_list['inp_timeframe']+'\nNet Long Returns: '+str(net_pnl_long)+' $'+'\nLong ROI: '+str(roi_trade_long)+' %'+'\nLong ROE: '+str(roe_trade_long)+' %'+'\nStrategy Capital: '+str(initial_list['inp_capital'])+' $'+'\nLong Trade Duration: '+str(duration_long)+'\nLong Account Drawdown: '+str(account_drawdown_long_per)+' %'+'\nLong Capital Drawdown: '+str(capital_drawdown_long_per)+' %')

            del pnl_long, total_commission_long, net_pnl_long, roi_trade_long, roe_trade_long, ro_capital_trade_long, SecToConvert_long, duration_long, avg_entry_price_long, account_drawdown_long_per, capital_drawdown_long_per

        if initial_list['short_trade']:
            # Short calculations:
            pnl_short = initial_list['initial_value_short'] - initial_list['end_value_short']

            total_commission_short = initial_list['entry_commission_amount_short'] + initial_list['exit_commission_amount_short']
            net_pnl_short = pnl_short - total_commission_short
            net_pnl_short = round(net_pnl_short,5)

            roi_trade_short = (net_pnl_short/initial_list['initial_value_long']) * 100 # returns on trade (money really used)
            roi_trade_short = round(roi_trade_short,5)

            roe_trade_short = (net_pnl_short/initial_list['usdt_cross_wallet_balance']) * 100 # returns on total deposit account
            roe_trade_short = round(roe_trade_short,5)

            ro_capital_trade_short = (net_pnl_short/initial_list['inp_capital']) * 100 # returns on capital dedicated to this strategy
            ro_capital_trade_short = round(ro_capital_trade_short,5)

            total_commission_short = round(total_commission_short,5)

            initial_list['initial_value_short'] = round(initial_list['initial_value_short'],5)
            SecToConvert_short = pd.to_datetime(initial_list['end_time_trade_short']) - pd.to_datetime(initial_list['start_time_trade_short']) #return time from string back to pandas datetime
            SecToConvert_short = SecToConvert_short.total_seconds()
            duration_short = str(timedelta(seconds = SecToConvert_short))

            avg_entry_price_short=round(initial_list['avg_entry_price_grid_5_short'], initial_list['precision_pri'])

            if initial_list['highest_price'] > float(avg_entry_price_short): # short drawdown calculation
                account_drawdown_short = initial_list['usdt_cross_wallet_balance'] - (initial_list['initial_value_short'] - ((initial_list['initial_value_short']/avg_entry_price_short)*initial_list['highest_price'])) # drawdown to all account deposit
                account_drawdown_short_per = -abs(round(((1-(account_drawdown_short/initial_list['usdt_cross_wallet_balance']))*100),5))

                capital_drawdown_short = initial_list['inp_capital'] - (initial_list['initial_value_short'] - ((initial_list['initial_value_short']/avg_entry_price_short)*initial_list['highest_price'])) # drawdown to capital dedicated to this strategy
                capital_drawdown_short_per = -abs(round(((1-(capital_drawdown_short/initial_list['inp_capital']))*100),5))
                del account_drawdown_short, capital_drawdown_short
            else:
                account_drawdown_short_per = 0
                capital_drawdown_short_per = 0

            new_data_short = [initial_list['inp_account'],initial_list['inp_crypto'],initial_list['inp_bot_name'],'binance','main','futures',initial_list['inp_leverage'],initial_list['inp_timeframe'],pd.to_datetime(initial_list['start_time_trade_short']),pd.to_datetime(initial_list['end_time_trade_short']),'short',initial_list['inp_capital'],net_pnl_short,initial_list['initial_value_short'],initial_list['end_value_short'],total_commission_short,roi_trade_short,roe_trade_short,ro_capital_trade_short,initial_list['avg_entry_price_grid_5_short'],avg_entry_price_short,initial_list['avg_exit_price_grid_short'],initial_list['entry_commission_amount_short'],initial_list['entry_commission_asset_short'],initial_list['exit_commission_amount_short'],initial_list['exit_commission_asset_short'],initial_list['usdt_wallet_balance'],initial_list['usdt_cross_wallet_balance'],account_drawdown_short_per,capital_drawdown_short_per]
            sql_val_short = (initial_list['inp_sql_table'],initial_list['inp_account'],initial_list['inp_crypto'],initial_list['inp_bot_name'],'binance','main','futures',initial_list['inp_leverage'],initial_list['inp_timeframe'],str(pd.to_datetime(initial_list['start_time_trade_short'])),str(pd.to_datetime(initial_list['end_time_trade_short'])),'short',initial_list['inp_capital'],net_pnl_short,initial_list['initial_value_short'],initial_list['end_value_short'],total_commission_short,roi_trade_short,roe_trade_short,ro_capital_trade_short,initial_list['avg_entry_price_grid_5_short'],avg_entry_price_short,initial_list['avg_exit_price_grid_short'],initial_list['entry_commission_amount_short'],initial_list['entry_commission_asset_short'],initial_list['exit_commission_amount_short'],initial_list['exit_commission_asset_short'],initial_list['usdt_wallet_balance'],initial_list['usdt_cross_wallet_balance'],account_drawdown_short_per,capital_drawdown_short_per)

            send_telegram('Account: '+initial_list['inp_account']+'\nBot: '+initial_list['inp_bot_name']+'\nAsset: '+initial_list['inp_crypto']+'\nTF: '+initial_list['inp_timeframe']+'\nNet Short Returns: '+str(net_pnl_short)+' $'+'\nShort ROI: '+str(roi_trade_short)+' %'+'\nShort ROE: '+str(roe_trade_short)+' %'+'\nStrategy Capital: '+str(initial_list['inp_capital'])+' $'+'\nShort Trade Duration: '+str(duration_short)+'\nShort Account Drawdown: '+str(account_drawdown_short_per)+' %'+'\nShort Capital Drawdown: '+str(capital_drawdown_short_per)+' %')

            del pnl_short, total_commission_short, net_pnl_short, roi_trade_short, roe_trade_short, ro_capital_trade_short, SecToConvert_short, duration_short, avg_entry_price_short, account_drawdown_short_per, capital_drawdown_short_per

        # Write the result:
        csv_header=['account','asset','bot_name','exchange','sub_account','spot_futures','leverage','time_frame','start_time','end_time','side','capital','net_pnl','initial_value','end_value','total_commission','trade_roi','deposit_roe','capital_returns','1st_entry_price','avg_entry_price','avg_exit_price','entry_commission_amount','entry_commission_asset','exit_commission_amount','exit_commission_asset','usdt_wallet_balance','usdt_cross_wallet_balance','account_drawdown_per','capital_drawdown_per']

        def create_csv_file(file_path, header): # Create a CSV file if not already created
            if not os.path.isfile(file_path):
                with open(file_path, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(header)
                    del writer

        def read_csv_file(file_path): # Read data from a CSV file
            data = []
            with open(file_path, 'r') as file:
                reader = csv.reader(file)
                header = next(reader)  # Skip the header
                for row in reader:
                    data.append(row)
            return header, data

        def add_data_to_csv(file_path, new_data): # Add new data to a CSV file and close it
            with open(file_path, 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(new_data)
                del writer

        try:
            header, existing_data = read_csv_file(trade_results_path) # try to read and write data
            if initial_list['long_trade']:
                add_data_to_csv(trade_results_path, new_data_long)
            if initial_list['short_trade']:
                add_data_to_csv(trade_results_path, new_data_short)
        except FileNotFoundError: # in case file was not found, we create a new one and after write the data
            create_csv_file(trade_results_path, csv_header) 
            if initial_list['long_trade']:
                add_data_to_csv(trade_results_path, new_data_long)
            if initial_list['short_trade']:
                add_data_to_csv(trade_results_path, new_data_short)
        
        del new_data_long, new_data_short, csv_header

        try: # write to MySQL
            mydb = sql_connect.connect(host=sql_host,user=sql_user,password=sql_password,database=sql_database_name)
            mycursor = mydb.cursor()
            
            if initial_list['inp_create_table_in_db']:
                # Try to create a table if table doesn't exist to store the future results
                try:
                    mycursor.execute(sql_queries.create_table(table=initial_list['inp_sql_table']))
                except:
                    pass

            if initial_list['long_trade']:
                mycursor.execute(sql_queries.insert_new_data(sql_val_long))
                mydb.commit() # Important!: Notice the statement: mydb.commit(). It is required to make the changes, otherwise no changes are made to the table.
            if initial_list['short_trade']:
                mycursor.execute(sql_queries.insert_new_data(sql_val_short))
                mydb.commit() # Important!: Notice the statement: mydb.commit(). It is required to make the changes, otherwise no changes are made to the table.

            mycursor.close
            mydb.close
            del mydb, mycursor, sql_val, sql_val_long, sql_val_short
        except:
            pass

    except Exception as e:
        error_logger(error_no=6,error_msg=e)
        del e
        pass

    # Reset counters below after TP:
    initial_list['ema'] = 0
    initial_list['price_grid_1_long'] = 0
    initial_list['price_grid_2_long'] = 0
    initial_list['price_grid_3_long'] = 0
    initial_list['price_grid_4_long'] = 0
    initial_list['price_grid_5_short'] = 0
    initial_list['qty_grid_1_long'] = 0
    initial_list['qty_grid_2_long'] = 0
    initial_list['qty_grid_3_long'] = 0
    initial_list['qty_grid_4_long'] = 0
    initial_list['qty_grid_5_short'] = 0
    initial_list['tp_target_long'] = 0
    initial_list['tp_target_short'] = 0
    initial_list['limit_long_order_grid_1'] = 0
    initial_list['limit_long_order_grid_2'] = 0
    initial_list['limit_long_order_grid_3'] = 0
    initial_list['limit_long_order_grid_4'] = 0
    initial_list['market_short_order_grid_5'] = 0
    initial_list['tp_market_long_order'] = 0
    initial_list['tp_market_short_order'] = 0
    initial_list['grid_1_long_taken'] = False
    initial_list['grid_2_long_taken'] = False
    initial_list['grid_3_long_taken'] = False
    initial_list['grid_4_long_taken'] = False
    initial_list['grid_5_short_taken'] = False
    initial_list['inside_short_order_grid_5'] = False
    initial_list['inside_long_tp'] = False
    initial_list['long_tp_taken'] = False
    initial_list['inside_short_tp'] = False
    initial_list['short_tp_taken'] = False
    initial_list['start_time_trade_long'] = None
    initial_list['end_time_trade_long'] = None
    initial_list['start_time_trade_short'] = None
    initial_list['end_time_trade_short'] = None
    initial_list['avg_entry_price_grid_1_long'] = 0
    initial_list['avg_entry_price_grid_2_long'] = 0
    initial_list['avg_entry_price_grid_3_long'] = 0
    initial_list['avg_entry_price_grid_4_long'] = 0
    initial_list['avg_entry_price_grid_5_short'] = 0
    initial_list['value_long_1'] = 0
    initial_list['value_long_2'] = 0
    initial_list['value_long_3'] = 0
    initial_list['value_long_4'] = 0
    initial_list['value_short_5'] = 0
    initial_list['initial_value_long'] = 0
    initial_list['initial_value_short'] = 0
    initial_list['avg_exit_price_grid_long'] = 0
    initial_list['avg_exit_price_grid_short'] = 0
    initial_list['long_close_open_orders_checked'] = False
    initial_list['short_close_open_orders_checked'] = False
    initial_list['end_value_long'] = 0
    initial_list['cumulative_qty_long'] = 0
    initial_list['cumulative_qty_short'] = 0
    initial_list['entry_commission_amount_long'] = 0
    initial_list['entry_commission_asset_long'] = None
    initial_list['exit_commission_amount_long'] = 0
    initial_list['exit_commission_asset_long'] = None
    initial_list['entry_commission_amount_short'] = 0
    initial_list['entry_commission_asset_short'] = None
    initial_list['exit_commission_amount_short'] = 0
    initial_list['exit_commission_asset_short'] = None
    initial_list['usdt_wallet_balance'] = 0
    initial_list['usdt_cross_wallet_balance'] = 0
    initial_list['lowest_price'] = 0
    initial_list['highest_price'] = 0
    initial_list['it_was_a_trade_last_df'] = True
    initial_list['trade'] = False
    initial_list['long_trade'] = False
    initial_list['short_trade'] = False
    write_new_json(initial_list) # save sttings to JSON

def cancel_limit_orders():
    global initial_list, logger_api

    while True:
        try:
            cancel_all_orders=client.futures_cancel_all_open_orders(symbol=initial_list['inp_crypto'])
            try:
                logger_api.info('RECEIVED futures_cancel_all_open_orders: '+str(cancel_all_orders)) # to log the message
            except:
                pass

            initial_list['limit_long_order_grid_1'] = 0
            initial_list['limit_long_order_grid_2'] = 0
            initial_list['limit_long_order_grid_3'] = 0
            initial_list['limit_long_order_grid_4'] = 0
            if cancel_all_orders['msg']=='The operation of cancel all open order is done.':
                del cancel_all_orders
                break
        except Exception as e: # no need to break the error, becouse binance is providing the callback every time.
            if str(e) != "APIError(code=-1021): Timestamp for this request is outside of the recvWindow.":
                error_logger(error_no=7,error_msg=e)
            sleep(0.5)
            del e
            pass
    write_new_json(initial_list) # save sttings to JSON

async def close_connection():
    global bsm_dict
    bsm_dict['update_task'].cancel() #cancel parallell task
    await bsm_dict['async_client'].close_connection()
    bsm_dict['async_client'] = None
    bsm_dict['bsm'] = None
    bsm_dict['spot_user_socket'] = None
    bsm_dict['spot_kline_socket'] = None
    bsm_dict['update_task'] = None

async def stop_bot():
    global bsm_dict

    cancel_limit_orders()

    bsm_dict['update_task'].cancel() #cancel parallell task
    await bsm_dict['async_client'].close_connection()
    bsm_dict['async_client'] = None
    bsm_dict['bsm'] = None
    bsm_dict['spot_user_socket'] = None
    bsm_dict['spot_kline_socket'] = None
    bsm_dict['update_task'] = None

async def update_settings():
    global initial_list, bsm_dict, check_list

    cancel_limit_orders()

    # Recalculate new strategy settings:
    initial_list['inp_capital'] = check_list['inp_capital']
    initial_list['inp_ema_length'] = check_list['inp_ema_length']
    initial_list['inp_timeframe'] = check_list['inp_timeframe']
    initial_list['inp_lookback_1st_run'] = check_list['inp_lookback_1st_run']
    initial_list['inp_grid_1_long_per_dca'] = check_list['inp_grid_1_long_per_dca']
    initial_list['inp_grid_2_long_per_dca'] = check_list['inp_grid_2_long_per_dca']
    initial_list['inp_grid_3_long_per_dca'] = check_list['inp_grid_3_long_per_dca']
    initial_list['inp_grid_4_long_per_dca'] = check_list['inp_grid_4_long_per_dca']
    initial_list['inp_grid_5_short_per_dca'] = check_list['inp_grid_5_short_per_dca']
    initial_list['inp_1_grid_long_per_deposit'] = check_list['inp_1_grid_long_per_deposit']
    initial_list['inp_2_grid_long_per_deposit'] = check_list['inp_2_grid_long_per_deposit']
    initial_list['inp_3_grid_long_per_deposit'] = check_list['inp_3_grid_long_per_deposit']
    initial_list['inp_4_grid_long_per_deposit'] = check_list['inp_4_grid_long_per_deposit']
    initial_list['inp_5_grid_short_per_deposit'] = check_list['inp_5_grid_short_per_deposit']
    initial_list['inp_tp_long_per'] = check_list['inp_tp_long_per']
    initial_list['inp_tp_short_per'] = check_list['inp_tp_short_per']
    initial_list['inp_stop_bot'] = 'no'
    initial_list['inp_update_settings'] = 'no'

    # Recalculate TP:
    if initial_list['tp_target_short'] != 0:
        initial_list['tp_target_short'] = round(initial_list['avg_entry_price_grid_5_short']*(1-(initial_list['inp_tp_short_per']/100)),initial_list['precision_pri'])

    if initial_list['tp_target_long'] != 0:
        initial_list['tp_target_long'] = round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long']*(1+(initial_list['inp_tp_long_per']/100)),initial_list['precision_pri'])

    # Close current connection:
    bsm_dict['update_task'].cancel() #cancel parallell task
    await bsm_dict['async_client'].close_connection()
    bsm_dict['async_client'] = None
    bsm_dict['bsm'] = None
    bsm_dict['futures_user_socket'] = None
    bsm_dict['futures_kline_socket'] = None
    bsm_dict['update_task'] = None

def get_data(crypto,interval,lookback):
    while True: # Getting historical prices from futures
        try:
            df = pd.DataFrame(client.futures_historical_klines(crypto,interval,lookback))
            df = df.iloc[:,:7]
            df.columns = ['time','open','high','low','close','volume','close_time']
            df = df.loc[:,['time','close']]
            df = df.astype(float)
            df['time'] = pd.to_datetime(df['time'],unit='ms')
            df.dropna(inplace=True)
            last_row = len(df) # getting the len of df to delete the last row of df
            df = df.drop(df.index[last_row-1])  # Deleting the last row of df
            return df # "return" will break the "wile true" loop
        except Exception as e:
            if str(e) != "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))":
                error_logger(error_no=8,error_msg=e)
            sleep(0.5)
            del e
            pass

def put_long_limit_orders(quantity_1,quantity_2,quantity_3,quantity_4,price_1,price_2,price_3,price_4):
    global initial_list, logger_api
    while True:
        try: # put the limit orders on binance
            initial_list['limit_long_order_grid_1'] = client.futures_create_order(symbol=initial_list['inp_crypto'],side='BUY',positionSide='LONG',type='LIMIT',quantity=quantity_1,price=price_1,timeInForce='GTC')
            initial_list['limit_long_order_grid_2'] = client.futures_create_order(symbol=initial_list['inp_crypto'],side='BUY',positionSide='LONG',type='LIMIT',quantity=quantity_2,price=price_2,timeInForce='GTC')
            initial_list['limit_long_order_grid_3'] = client.futures_create_order(symbol=initial_list['inp_crypto'],side='BUY',positionSide='LONG',type='LIMIT',quantity=quantity_3,price=price_3,timeInForce='GTC')
            initial_list['limit_long_order_grid_4'] = client.futures_create_order(symbol=initial_list['inp_crypto'],side='BUY',positionSide='LONG',type='LIMIT',quantity=quantity_4,price=price_4,timeInForce='GTC')

            try:
                logger_api.info('RECEIVED limit_long_order_grid_1: '+str(initial_list['limit_long_order_grid_1'])) # to log the message
                logger_api.info('RECEIVED limit_long_order_grid_2: '+str(initial_list['limit_long_order_grid_2'])) # to log the message
                logger_api.info('RECEIVED limit_long_order_grid_3: '+str(initial_list['limit_long_order_grid_3'])) # to log the message
                logger_api.info('RECEIVED limit_long_order_grid_4: '+str(initial_list['limit_long_order_grid_4'])) # to log the message
            except:
                pass
            break
        except Exception as e:
            error_logger(error_no=9,error_msg=e)
            if str(e) == "APIError(code=-2019): Margin is insufficient." or str(e) == "APIError(code=-4164): Order's notional must be no smaller than 5 (unless you choose reduce only).": #type:ignore
                send_telegram(initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nNot enough money to put limit orders - bot will be stopped')
                initial_list['inp_stop_bot'] = 'yes'
                asyncio.run(stop_bot())  # stop the bot in case we have not enough money to open a trade
                break
            else:
                cancel_limit_orders()
            sleep(0.5)
            del e
            pass
    write_new_json(initial_list) # save sttings to JSON

def put_market_order(qty,side,positionside):
    global logger_api
    # Hedge mode binance: side (BUY or SELL), positionSide (LONT or SHORT):
    # BUY LONG = open long
    # SELL SHORT = open short
    # SELL LONG = close long
    # BUY SHORT = close short
    while True:
        try: # put the limit orders on binance
            order = client.futures_create_order(symbol=initial_list['inp_crypto'],side=side,positionSide=positionside,type='MARKET',quantity=qty)
            try:
                logger_api.info('RECEIVED market_order: '+str(order)) # to log the message
            except:
                pass
            return order
        except Exception as e:
            error_logger(error_no=10,error_msg=e)
            if (side=='SELL' and positionside=='LONG') or (side=='BUY' and positionside=='SHORT'):
                break # in case we are closing the position, we want to break the loop and exicate the close_open_positions() later.
            sleep(0.5)
            del e
            pass

def close_open_positions():
    global initial_list, logger_api
    while True: # close all long and short open trades after TP in case there are any left
        try:
            positions=pd.DataFrame(client.futures_position_information(symbol=initial_list['inp_crypto'], recvWindow=59999), columns=['symbol','positionAmt', 'entryPrice','positionSide'])

            try:
                logger_api.info('RECEIVED futures_position_information: '+str(positions)) # to log the message
            except:
                pass

            long_positions = positions[positions['positionSide']=='LONG']
            long_positions = long_positions[long_positions['entryPrice']!="0.0"] # define data frame without 0

            short_positions = positions[positions['positionSide']=='SHORT']
            short_positions = short_positions[short_positions['entryPrice']!="0.0"] # define data frame without 0

            if long_positions.empty and short_positions.empty:  # in case there are no open long trades we break the loop
                initial_list['long_close_open_orders_checked'] = True
                initial_list['short_close_open_orders_checked'] = True
                break

            if not initial_list['long_close_open_orders_checked']: #check long orders
                if not long_positions.empty: # in case there are active open long trades
                    qty_long=long_positions['positionAmt'].iloc[0]
                    qty_long=float(qty_long) # convert to float so binance could understand it
                    initial_list['inside_long_tp'] = True
                    initial_list['tp_market_long_order']=put_market_order(qty=qty_long,side='SELL',positionside='LONG')
                    del qty_long
                    initial_list['long_close_open_orders_checked'] = False

            if not initial_list['short_close_open_orders_checked']: #check long orders
                if not short_positions.empty: # in case there are active open long trades
                    qty_short=short_positions['positionAmt'].iloc[0]
                    qty_short=float(qty_short) # convert to float so binance could understand it
                    qty_short=abs(qty_short) # abs deletes minus from positionAmt
                    qty_short=float(qty_short)
                    initial_list['inside_short_tp'] = True
                    initial_list['tp_market_short_order']=put_market_order(qty=qty_short,side='BUY',positionside='SHORT')
                    del qty_short
                    initial_list['long_close_open_orders_checked'] = False
            
            del positions, long_positions, short_positions

        except Exception as e:
            error_logger(error_no=11,error_msg=e)
            sleep(0.5)
            del e
            pass

    initial_list['long_close_open_orders_checked'] = False
    initial_list['short_close_open_orders_checked'] = False

async def position_update():
    global initial_list, bsm_dict, logger_api

    while True: # Checking for position update in another parallell task
        try:
            update = await bsm_dict['futures_user_socket'].recv()

            try:
                logger_api.info('RECEIVED position_update: '+str(update)) # to log the message
            except Exception:
                pass

            if str(update['e']) == 'ORDER_TRADE_UPDATE': # position/order update # https://binance-docs.github.io/apidocs/spot/en/#public-api-definitions
                if str(update['o']['s']) == initial_list['inp_crypto']: # filter the asset we trade
                    if str(update['o']['X']) == 'FILLED' or str(update['o']['X']) == 'PARTIALLY_FILLED': # when order was fully or partially filled

                        if not initial_list['grid_1_long_taken']: # needs to correctly filter the "initial_list['limit_long_order_grid_1']['orderId']"
                            if str(initial_list['limit_long_order_grid_1']) != '0': # needs to correctly filter the "initial_list['limit_long_order_grid_1']['orderId']"
                                if str(update['o']['i']) == str(initial_list['limit_long_order_grid_1']['orderId']):
                                    initial_list['start_time_trade_long'] = str(pd.to_datetime((int(update['o']['T']) / 1000), unit='s')) # convert time to string so it could be saved to JSON # T =Order Trade Time
                                    initial_list['avg_entry_price_grid_1_long'] = float(update['o']['ap']) # ap = Average Price
                                    initial_list['entry_commission_amount_long'] = float(initial_list['entry_commission_amount_long'])+float(update['o']['n']) # n =Commission, will not push if no commission
                                    initial_list['entry_commission_asset_long'] = str(update['o']['N']) # N =Commission Asset (ex. USDT), will not push if no commission
                                    initial_list['cumulative_qty_long'] = float(initial_list['cumulative_qty_long'])+float(update['o']['z']) # z = Order Filled Accumulated Quantity
                                    initial_list['value_long_1'] = round(float(update['o']['z'])*float(initial_list['avg_entry_price_grid_1_long']),2) # Calculation to get in USDT
                                    initial_list['tp_target_long'] = round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long']*(1+(initial_list['inp_tp_long_per']/100)),initial_list['precision_pri']) #recalculate avg entry price and new take profit
                                    initial_list['initial_value_long'] = initial_list['value_long_1'] + initial_list['value_long_2'] + initial_list['value_long_3'] + initial_list['value_long_4']
                                    initial_list['long_trade'] = True
                                    initial_list['trade'] = True
                                    if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                        initial_list['grid_1_long_taken'] = True
                                        write_new_json(initial_list) # save sttings to JSON
                                        send_telegram('Open Grid 1 Long:\n'+initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nPrice: '+str(initial_list['avg_entry_price_grid_1_long'])+'\nValue $: '+str(initial_list['value_long_1'])+'\nTP Value $: '+str(initial_list['initial_value_long'])+'\nTP QTY: '+str(initial_list['cumulative_qty_long']))

                        if not initial_list['grid_2_long_taken']:
                            if str(initial_list['limit_long_order_grid_2']) != '0':
                                if str(update['o']['i']) == str(initial_list['limit_long_order_grid_2']['orderId']):
                                    initial_list['avg_entry_price_grid_2_long'] = float(update['o']['ap'])
                                    initial_list['entry_commission_amount_long'] = float(initial_list['entry_commission_amount_long'])+float(update['o']['n'])
                                    initial_list['entry_commission_asset_long'] = str(update['o']['N'])
                                    initial_list['cumulative_qty_long'] = float(initial_list['cumulative_qty_long'])+float(update['o']['z'])
                                    initial_list['value_long_2'] = round(float(update['o']['z'])*float(initial_list['avg_entry_price_grid_2_long']),2)
                                    initial_list['tp_target_long'] = round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long']*(1+(initial_list['inp_tp_long_per']/100)),initial_list['precision_pri'])
                                    initial_list['initial_value_long'] = initial_list['value_long_1'] + initial_list['value_long_2'] + initial_list['value_long_3'] + initial_list['value_long_4']
                                    initial_list['long_trade'] = True
                                    initial_list['trade'] = True
                                    if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                        initial_list['grid_2_long_taken'] = True
                                        write_new_json(initial_list) # save sttings to JSON
                                        send_telegram('Open Grid 2 Long:\n'+initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nPrice: '+str(initial_list['avg_entry_price_grid_2_long'])+'\nValue $: '+str(initial_list['value_long_2'])+'\nTP Value $: '+str(initial_list['initial_value_long'])+'\nTP QTY: '+str(initial_list['cumulative_qty_long']))

                        if not initial_list['grid_3_long_taken']:
                            if str(initial_list['limit_long_order_grid_3']) != '0':
                                if str(update['o']['i']) == str(initial_list['limit_long_order_grid_3']['orderId']):
                                    initial_list['avg_entry_price_grid_3_long'] = float(update['o']['ap'])
                                    initial_list['entry_commission_amount_long'] = float(initial_list['entry_commission_amount_long'])+float(update['o']['n'])
                                    initial_list['entry_commission_asset_long'] = str(update['o']['N'])
                                    initial_list['cumulative_qty_long'] = float(initial_list['cumulative_qty_long'])+float(update['o']['z'])
                                    initial_list['value_long_3'] = round(float(update['o']['z'])*float(initial_list['avg_entry_price_grid_3_long']),2)
                                    initial_list['tp_target_long'] = round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long']*(1+(initial_list['inp_tp_long_per']/100)),initial_list['precision_pri'])
                                    initial_list['initial_value_long'] = initial_list['value_long_1'] + initial_list['value_long_2'] + initial_list['value_long_3'] + initial_list['value_long_4']
                                    initial_list['long_trade'] = True
                                    initial_list['trade'] = True
                                    if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                        initial_list['grid_3_long_taken'] = True
                                        write_new_json(initial_list) # save sttings to JSON
                                        send_telegram('Open Grid 3 Long:\n'+initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nPrice: '+str(initial_list['avg_entry_price_grid_3_long'])+'\nValue $: '+str(initial_list['value_long_3'])+'\nTP Value $: '+str(initial_list['initial_value_long'])+'\nTP QTY: '+str(initial_list['cumulative_qty_long']))

                        if not initial_list['grid_4_long_taken']:
                            if str(initial_list['limit_long_order_grid_4']) != '0':
                                if str(update['o']['i']) == str(initial_list['limit_long_order_grid_4']['orderId']):
                                    initial_list['avg_entry_price_grid_4_long'] = float(update['o']['ap'])
                                    initial_list['entry_commission_amount_long'] = float(initial_list['entry_commission_amount_long'])+float(update['o']['n'])
                                    initial_list['entry_commission_asset_long'] = str(update['o']['N'])
                                    initial_list['cumulative_qty_long'] = float(initial_list['cumulative_qty_long'])+float(update['o']['z'])
                                    initial_list['value_long_4'] = round(float(update['o']['z'])*float(initial_list['avg_entry_price_grid_4_long']),2)
                                    initial_list['tp_target_long'] = round(((initial_list['avg_entry_price_grid_1_long']*initial_list['qty_grid_1_long'])+(initial_list['avg_entry_price_grid_2_long']*initial_list['qty_grid_2_long'])+(initial_list['avg_entry_price_grid_3_long']*initial_list['qty_grid_3_long'])+(initial_list['avg_entry_price_grid_4_long']*initial_list['qty_grid_4_long']))/initial_list['cumulative_qty_long']*(1+(initial_list['inp_tp_long_per']/100)),initial_list['precision_pri'])
                                    initial_list['initial_value_long'] = initial_list['value_long_1'] + initial_list['value_long_2'] + initial_list['value_long_3'] + initial_list['value_long_4']
                                    initial_list['long_trade'] = True
                                    initial_list['trade'] = True
                                    if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                        initial_list['grid_4_long_taken'] = True
                                        write_new_json(initial_list) # save sttings to JSON
                                        send_telegram('Open Grid 4 Long:\n'+initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nPrice: '+str(initial_list['avg_entry_price_grid_4_long'])+'\nValue $: '+str(initial_list['value_long_4'])+'\nTP Value $: '+str(initial_list['initial_value_long'])+'\nTP QTY: '+str(initial_list['cumulative_qty_long']))

                        if not initial_list['grid_5_short_taken']:
                            if str(initial_list['market_short_order_grid_5']) != '0':
                                if str(update['o']['i']) == str(initial_list['market_short_order_grid_5']['orderId']):
                                    initial_list['start_time_trade_short'] = str(pd.to_datetime((int(update['o']['T']) / 1000), unit='s'))
                                    initial_list['avg_entry_price_grid_5_short'] = float(update['o']['ap'])
                                    initial_list['entry_commission_amount_short'] = float(initial_list['entry_commission_amount_short'])+float(update['o']['n'])
                                    initial_list['entry_commission_asset_short'] = str(update['o']['N'])
                                    initial_list['cumulative_qty_short'] = float(initial_list['cumulative_qty_short'])+float(update['o']['z'])
                                    initial_list['value_short_5'] = round(float(update['o']['z'])*float(initial_list['avg_entry_price_grid_5_short']),2)
                                    initial_list['tp_target_short'] = round(initial_list['avg_entry_price_grid_5_short']*(1-(initial_list['inp_tp_short_per']/100)),initial_list['precision_pri'])
                                    initial_list['initial_value_short'] = initial_list['value_short_5']
                                    initial_list['short_trade'] = True
                                    initial_list['trade'] = True
                                    if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                        initial_list['grid_5_short_taken'] = True
                                        write_new_json(initial_list) # save sttings to JSON
                                        send_telegram('Open Grid 5 Short:\n'+initial_list['inp_account']+' - '+initial_list['inp_bot_name']+' - '+initial_list['inp_crypto']+' - '+initial_list['inp_timeframe']+'\nPrice: '+str(initial_list['avg_entry_price_grid_5_short'])+'\nValue $: '+str(initial_list['value_short_5'])+'\nTP Value $: '+str(initial_list['initial_value_short'])+'\nTP QTY: '+str(initial_list['cumulative_qty_short']))

                        if initial_list['inside_long_tp']:
                            if not initial_list['long_tp_taken']:
                                if str(initial_list['tp_market_long_order']) != '0':
                                    if str(update['o']['i']) == str(initial_list['tp_market_long_order']['orderId']): # Long Take Profit calculation
                                        initial_list['end_time_trade_long'] = str(pd.to_datetime((int(update['o']['T']) / 1000), unit='s'))
                                        initial_list['avg_exit_price_grid_long'] = float(update['o']['ap'])
                                        initial_list['exit_commission_amount_long'] = (initial_list['exit_commission_amount_long'] + float(update['o']['n']))
                                        initial_list['exit_commission_asset_long'] = str(update['o']['N'])
                                        initial_list['end_value_long'] = round(float(update['o']['z'])*float(initial_list['avg_exit_price_grid_long']),2)
                                        if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                            initial_list['long_tp_taken'] = True
                                            if initial_list['long_trade'] and not initial_list['short_trade']: # in case we he only long trade open, we don't need to wait for the short tp
                                                calculate_returns()
                                            if initial_list['long_trade'] and initial_list['short_trade'] and initial_list['long_tp_taken'] and initial_list['short_tp_taken']: # in case we have both long and short trades, we wait to hit both TPs
                                                calculate_returns()

                        if initial_list['inside_short_tp']:
                            if not initial_list['short_tp_taken']:
                                if str(initial_list['tp_market_short_order']) != '0':
                                    if str(update['o']['i']) == str(initial_list['tp_market_short_order']['orderId']): # Short Take Profit calculation
                                        initial_list['end_time_trade_short'] = str(pd.to_datetime((int(update['o']['T']) / 1000), unit='s'))
                                        initial_list['avg_exit_price_grid_short'] = float(update['o']['ap'])
                                        initial_list['exit_commission_amount_short'] = (initial_list['exit_commission_amount_short'] + float(update['o']['n']))
                                        initial_list['exit_commission_asset_short'] = str(update['o']['N'])
                                        initial_list['end_value_short']=round(float(update['o']['z'])*float(initial_list['avg_exit_price_grid_short']),2)
                                        if str(update['o']['X']) == 'FILLED': # in case order was fully filled
                                            initial_list['short_tp_taken'] = True
                                            if initial_list['long_trade'] and initial_list['short_trade'] and initial_list['long_tp_taken'] and initial_list['short_tp_taken']: # in case we have both long and short trades, we wait to hit both TPs
                                                calculate_returns()
                                            if initial_list['short_trade'] and not initial_list['long_trade']: # in case we he only short trade open, we don't need to wait for the long tp
                                                calculate_returns()
            
            if str(update['e']) == 'ACCOUNT_UPDATE':
                try:
                    if initial_list['inside_long_tp'] or initial_list['inside_short_tp']:
                        if str(update['a']['P'][0]['s']) == initial_list['inp_crypto']:
                            initial_list['usdt_wallet_balance'] = floor(float(update['a']['B'][0]['wb']) * 10**2) / 10**2
                            initial_list['usdt_cross_wallet_balance'] = floor(float(update['a']['B'][0]['cw']) * 10**2) / 10**2
                            pass
                except:
                    pass

            del update
        except Exception as e:
            error_logger(error_no=12,error_msg=e)
            del e
            pass

async def start_bot():
    global initial_list, bsm_dict, api_key, api_secret, logger_api

    bsm_dict['async_client'] = await AsyncClient.create(api_key,api_secret)
    bsm_dict['bsm'] = BinanceSocketManager(bsm_dict['async_client']) # Instantiating Websocket Manager

    bsm_dict['futures_user_socket'] = bsm_dict['bsm'].futures_user_socket()
    await bsm_dict['futures_user_socket'].__aenter__()
   
    bsm_dict['futures_kline_socket'] = bsm_dict['bsm'].kline_futures_socket(initial_list['inp_crypto'],initial_list['inp_timeframe'])
    await bsm_dict['futures_kline_socket'].__aenter__()

    bsm_dict['update_task'] = asyncio.create_task(position_update()) # Creating a parallel task
    await asyncio.sleep(0.0001)

    send_telegram('Account: '+initial_list['inp_account']+' - Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+f' - Started at {pd.Timestamp.now()}')

    if not initial_list['trade']: # in case there is no open trade
        cancel_limit_orders()

    df_1 = get_data(initial_list['inp_crypto'],initial_list['inp_timeframe'],initial_list['inp_lookback_1st_run']) # get data first time
    initial_list['it_was_a_trade_last_df'] = False

    while True: # this part is needed to calculate ema first time
        try:
            df_1['ema'] = round((ema(close=df_1['close'], length=initial_list['inp_ema_length'])),initial_list['precision_pri']) #type:ignore
            initial_list['ema'] = df_1['ema'].iloc[-1]

            initial_list['price_grid_1_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_1_long_per_dca']/100)),initial_list['precision_pri'])
            initial_list['price_grid_2_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_2_long_per_dca']/100)),initial_list['precision_pri'])
            initial_list['price_grid_3_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_3_long_per_dca']/100)),initial_list['precision_pri'])
            initial_list['price_grid_4_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_4_long_per_dca']/100)),initial_list['precision_pri'])
            initial_list['price_grid_5_short'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_5_short_per_dca']/100)),initial_list['precision_pri'])

            initial_list['qty_grid_1_long'] = round((initial_list['inp_capital']*(initial_list['inp_1_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_1_long']),initial_list['precision_qty'])
            initial_list['qty_grid_2_long'] = round((initial_list['inp_capital']*(initial_list['inp_2_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_2_long']),initial_list['precision_qty'])
            initial_list['qty_grid_3_long'] = round((initial_list['inp_capital']*(initial_list['inp_3_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_3_long']),initial_list['precision_qty'])
            initial_list['qty_grid_4_long'] = round((initial_list['inp_capital']*(initial_list['inp_4_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_4_long']),initial_list['precision_qty'])
            initial_list['qty_grid_5_short'] = round((initial_list['inp_capital']*(initial_list['inp_5_grid_short_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_5_short']),initial_list['precision_qty'])

            initial_list['lowest_price'] = initial_list['price_grid_1_long'] # needs to define what is lowest price for drawdown
            initial_list['highest_price'] = initial_list['price_grid_1_long'] # needs to define what is lowest price for drawdown
            break
        except Exception as e:
            error_logger(error_no=13,error_msg=e)
            del e
            await asyncio.sleep(0.5)
            pass

    if not initial_list['trade']:
        put_long_limit_orders(quantity_1=initial_list['qty_grid_1_long'],quantity_2=initial_list['qty_grid_2_long'],quantity_3=initial_list['qty_grid_3_long'],quantity_4=initial_list['qty_grid_4_long'],price_1=initial_list['price_grid_1_long'],price_2=initial_list['price_grid_2_long'],price_3=initial_list['price_grid_3_long'],price_4=initial_list['price_grid_4_long'])

    while True:
        candle = await bsm_dict['futures_kline_socket'].recv()
        
        if candle['k']['x']: # wait for a new candle
            if not initial_list['trade']: # in case there is no open trade                         
                while True:
                    try:
                        if initial_list['it_was_a_trade_last_df']: # get data first time again after the trade, because during the trade we don't need to update the df, counter will be reset after puttting new limit orders
                            df_1 = get_data(initial_list['inp_crypto'],initial_list['inp_timeframe'],initial_list['inp_lookback_1st_run'])
                        
                        # Extraxt the time and the close prise from tick candle to build future df:
                        candle_time = pd.to_datetime(candle['k']['t']/1000, unit='s')
                        candle_close=float(candle['k']['c'])
                        df_2 = pd.DataFrame({'time': [candle_time], 'close': [candle_close]})

                        # Extraxt the lenght of lookback from initial_list['inp_lookback_1st_run']:
                        numeric_part = re.search(r'\d+', initial_list['inp_lookback_1st_run']) # Using regular expression to extract the numeric part
                        lookback_tail = int(numeric_part.group()) if numeric_part else None # Converting the extracted numeric part to an integer

                        # Taking original df_1 and concat it with new df_2 to get df_final to save some time on downloading data from binance:
                        df_1 = df_1[['time','close']] # taking the data we need from df_1
                        df_final = pd.concat([df_1,df_2],ignore_index=True) # contact with final cleand data #type: ignore
                        df_final.drop_duplicates(ignore_index=True,inplace=True,keep="first") # delete duplicates in case we downloaded more data than we needed
                        df_final=df_final.tail(lookback_tail) # filter the last "lookback_tail" rows of data #type: ignore
                        df_1 = df_final # replacing df_final
                        del df_final, df_2, numeric_part, lookback_tail #type: ignore
                        df_1=df_1.reset_index(drop='True') # drop the index #type: ignore
                        df_1['ema'] = round((ema(close=df_1['close'], length=initial_list['inp_ema_length'])),initial_list['precision_pri']) #type:ignore

                        if (df_1['ema'].iloc[-1] != df_1['ema'].iloc[-2]) or initial_list['it_was_a_trade_last_df']: # in case ema is the same like previous, we don't need to recalculate the grids again and just wait for new ema or in case we had a trade last candle, so we need to put new limit orders
                            cancel_limit_orders()

                            # """Calculate new grids:"""
                            initial_list['ema'] = df_1['ema'].iloc[-1]

                            initial_list['price_grid_1_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_1_long_per_dca']/100)),initial_list['precision_pri'])
                            initial_list['price_grid_2_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_2_long_per_dca']/100)),initial_list['precision_pri'])
                            initial_list['price_grid_3_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_3_long_per_dca']/100)),initial_list['precision_pri'])
                            initial_list['price_grid_4_long'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_4_long_per_dca']/100)),initial_list['precision_pri'])
                            initial_list['price_grid_5_short'] = round((initial_list['ema'] - (initial_list['ema']*initial_list['inp_grid_5_short_per_dca']/100)),initial_list['precision_pri'])

                            initial_list['qty_grid_1_long'] = round((initial_list['inp_capital']*(initial_list['inp_1_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_1_long']),initial_list['precision_qty'])
                            initial_list['qty_grid_2_long'] = round((initial_list['inp_capital']*(initial_list['inp_2_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_2_long']),initial_list['precision_qty'])
                            initial_list['qty_grid_3_long'] = round((initial_list['inp_capital']*(initial_list['inp_3_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_3_long']),initial_list['precision_qty'])
                            initial_list['qty_grid_4_long'] = round((initial_list['inp_capital']*(initial_list['inp_4_grid_long_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_4_long']),initial_list['precision_qty'])
                            initial_list['qty_grid_5_short'] = round((initial_list['inp_capital']*(initial_list['inp_5_grid_short_per_deposit']/100*initial_list['inp_leverage']))/float(initial_list['price_grid_5_short']),initial_list['precision_qty'])

                            initial_list['lowest_price'] = initial_list['price_grid_1_long'] # needs to define what is lowest price for drawdown
                            initial_list['highest_price'] = initial_list['price_grid_1_long'] # needs to define what is lowest price for drawdown

                            put_long_limit_orders(quantity_1=initial_list['qty_grid_1_long'],quantity_2=initial_list['qty_grid_2_long'],quantity_3=initial_list['qty_grid_3_long'],quantity_4=initial_list['qty_grid_4_long'],price_1=initial_list['price_grid_1_long'],price_2=initial_list['price_grid_2_long'],price_3=initial_list['price_grid_3_long'],price_4=initial_list['price_grid_4_long'])
                            initial_list['it_was_a_trade_last_df'] = False # reset the counter after we put a new limit order after last candle was a trade
                        break
                    except Exception as e:
                        error_logger(error_no=14,error_msg=e)
                        del e
                        await asyncio.sleep(0.5)
                        pass

        if initial_list['trade']:

            if initial_list['long_trade']: # in case we have active long trade
                if not initial_list['long_tp_taken'] and not initial_list['inside_long_tp']: # tp long
                    if float(candle['k']['c']) >= initial_list['tp_target_long']:
                        initial_list['inside_long_tp'] = True
                        initial_list['cumulative_qty_long']=round(initial_list['cumulative_qty_long'],initial_list['precision_qty'])
                        initial_list['tp_market_long_order'] = put_market_order(qty=initial_list['cumulative_qty_long'],side='SELL',positionside='LONG')
                        if initial_list['short_trade']: # in case we hit long tp, but we also have open short trade
                            initial_list['inside_short_tp'] = True
                            initial_list['tp_market_short_order'] = put_market_order(qty=initial_list['cumulative_qty_short'],side='BUY',positionside='SHORT')
                        cancel_limit_orders()
                        close_open_positions()
                        try:
                            logger_api.info('RECEIVED price from Binance at Long TP: '+str(candle)) # to log the message
                        except:
                            pass

                if initial_list['short_trade']: # in case we have active short trade
                    if not initial_list['short_tp_taken'] and not initial_list['inside_short_tp'] and initial_list['grid_5_short_taken']: # tp short
                        if float(candle['k']['c']) <= initial_list['tp_target_short']:
                            initial_list['inside_short_tp'] = True
                            initial_list['inside_long_tp'] = True
                            initial_list['cumulative_qty_long']=round(initial_list['cumulative_qty_long'],initial_list['precision_qty'])
                            initial_list['cumulative_qty_short']=round(initial_list['cumulative_qty_short'],initial_list['precision_qty'])
                            initial_list['tp_market_short_order'] = put_market_order(qty=initial_list['cumulative_qty_short'],side='BUY',positionside='SHORT')
                            initial_list['tp_market_long_order'] = put_market_order(qty=initial_list['cumulative_qty_long'],side='SELL',positionside='LONG')
                            cancel_limit_orders()
                            close_open_positions()
                            try:
                                logger_api.info('RECEIVED price from Binance at Short TP: '+str(candle)) # to log the message
                            except:
                                pass

                    if float(candle['k']['c']) > initial_list['highest_price']:
                        initial_list['highest_price'] = float(candle['k']['c']) # needs to calculate drawdown

                if not initial_list['short_trade']: # short hedge trade - 5 grid
                    if not initial_list['inside_short_order_grid_5'] and not initial_list['grid_5_short_taken']:
                        if float(candle['k']['c']) < initial_list['price_grid_5_short']:
                            initial_list['inside_short_order_grid_5'] = True
                            initial_list['market_short_order_grid_5'] = put_market_order(qty=initial_list['qty_grid_5_short'],side='SELL',positionside='SHORT')
                            try:
                                logger_api.info('RECEIVED price from Binance at 5 grid Short: '+str(candle)) # to log the message
                            except:
                                pass

                if float(candle['k']['c']) < initial_list['lowest_price']:
                    initial_list['lowest_price'] = float(candle['k']['c']) # needs to calculate drawdown

if __name__ == "__main__":

    client = Client(api_key,api_secret) # initialize binance API client

    change_position_mode()
    change_margin_settings()
    check_precision()
    del change_position_mode, change_margin_settings, check_precision

    print('\nAccount: '+initial_list['inp_account']+' - Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+f' - Started at {pd.Timestamp.now()}'+'\n') 

    while True:
        try:
            asyncio.run(start_bot())
        except:
                # Needs only to check if we want to stop the bot or change settings:
                check_list_json=open(settings_path, 'rb')
                check_list = json.load(check_list_json)
                check_list_json.close()

                if check_list['inp_stop_bot'] == 'no' and check_list['inp_update_settings'] == 'yes': # update bot settings
                    asyncio.run(update_settings())
                    write_new_json(initial_list) # save settings to a new JSON
                    error_logger(error_no=1001,error_msg='Account: '+initial_list['inp_account']+' -  Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+' - strategy settings where manually updated'+f' at {pd.Timestamp.now()}')

                if check_list['inp_stop_bot'] == 'no' and check_list['inp_update_settings'] == 'no': # restart the bot
                    asyncio.run(close_connection())
                    write_new_json(initial_list) # save settings to a new JSON
                    error_logger(error_no=1002,error_msg='Account: '+initial_list['inp_account']+' -  Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+' - connection was restarted' +f' at {pd.Timestamp.now()}')

                if check_list['inp_stop_bot'] == 'yes': # stop the bot
                    os.system('clear')
                    asyncio.run(stop_bot())
                    write_new_json(initial_list) # save sttings to a new JSON

                    if initial_list['trade']: # if there is an open position
                        error_logger(error_no=1003,error_msg='Account: '+initial_list['inp_account']+' -  Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+ ' - was Manually Stopped (Position still open, limit orders canceled)!')
                        
                    if not initial_list['trade']: # if there is no open position
                        error_logger(error_no=1004,error_msg='Account: '+initial_list['inp_account']+' -  Bot: '+initial_list['inp_bot_name']+' - Asset: '+initial_list['inp_crypto']+' - Time Frame: '+initial_list['inp_timeframe']+ ' - was Manually Stopped (No open position, limit orders canceled)')
                    os.system('clear')
                    break
        finally:
            pass