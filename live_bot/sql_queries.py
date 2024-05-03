def create_table(table):
    # Create a table if table doesn't exist to store the future results

    query=f"""
        CREATE TABLE IF NOT EXISTS {table}
            (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account VARCHAR(255),
                asset VARCHAR(255),
                bot_name VARCHAR(255),
                exchange VARCHAR(255),
                sub_account VARCHAR(255),
                spot_futures VARCHAR(255),
                leverage VARCHAR(255),
                time_frame VARCHAR(255),
                start_time VARCHAR(255),
                end_time VARCHAR(255),
                side VARCHAR(255),
                capital FLOAT(24),
                net_pnl FLOAT(24),
                initial_value FLOAT(24),
                end_value FLOAT(24),
                total_commission FLOAT(24),
                trade_roi FLOAT(24),
                deposit_roe FLOAT(24),
                capital_returns FLOAT(24),
                1st_entry_price FLOAT(24),
                avg_entry_price FLOAT(24),
                avg_exit_price FLOAT(24),
                entry_commission_amount FLOAT(24),
                entry_commission_asset VARCHAR(255),
                exit_commission_amount FLOAT(24),
                exit_commission_asset VARCHAR(255),
                usdt_wallet_balance FLOAT(24),
                usdt_cross_wallet_balance FLOAT(24),
                account_drawdown_per FLOAT(24),
                capital_drawdown_per FLOAT(24)
            )
    """
    return query

def insert_new_data(sql_val_long):
    query = "INSERT INTO %s (account,asset,bot_name,exchange,sub_account,spot_futures,leverage,time_frame,start_time,end_time,side,capital,net_pnl,initial_value,end_value,total_commission,trade_roi,deposit_roe,capital_returns,1st_entry_price,avg_entry_price,avg_exit_price,entry_commission_amount,entry_commission_asset,exit_commission_amount,exit_commission_asset,usdt_wallet_balance,usdt_cross_wallet_balance,account_drawdown_per,capital_drawdown_per)VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" % sql_val_long
    return query