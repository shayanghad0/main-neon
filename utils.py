import os
import json
import uuid
import datetime
import threading
import time
import logging
import requests
import random
from werkzeug.security import check_password_hash

# Constants
ADMIN_USERNAME = "shayanghad0"
ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$0eKali86gKTFdEqE$5c6f4bfb913ffe475f9cda04906969d13c81b535ce070fa7cf84fae5227828e212daf52ab03ad5bf3b2158d2b9472c1a971bb069cefc9a4c750e3f646444a0d5"  # hashed version of shGh1389@
DEFAULT_PRICES = {
    "BTC/USDT": 62000,
    "ETH/USDT": 3000,
    "ETC/USDT": 25,
    "LTC/USDT": 85,
    "BNB/USDT": 550,
    "TRX/USDT": 0.12,
    "PEPE/USDT": 0.00001,
    "AAVE/USDT": 90,
    "DOGE/USDT": 0.12,
    "SOL/USDT": 145,
    "ADA/USDT": 0.45,
    "AVAX/USDT": 35,
    "SHIB/USDT": 0.00002,
    "TON/USDT": 5.5,
    "POL/USDT": 9,
    "FIL/USDT": 6,
    "ATOM/USDT": 11
}

# Ensure data directory exists
if not os.path.exists('data'):
    os.makedirs('data')

def load_data(filename):
    """Load data from a JSON file in the data directory"""
    file_path = os.path.join('data', filename)
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                logging.error(f"Error decoding JSON from {file_path}")
                return []
    else:
        return []

def save_data(filename, data):
    """Save data to a JSON file in the data directory"""
    file_path = os.path.join('data', filename)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def initialize_data_files():
    """Initialize all required data files if they don't exist"""
    data_files = ['users.json', 'trades.json', 'deposits.json', 'withdrawals.json', 'prices.json']
    
    for filename in data_files:
        file_path = os.path.join('data', filename)
        
        if not os.path.exists(file_path):
            if filename == 'prices.json':
                # Initialize with default prices
                save_data(filename, DEFAULT_PRICES)
            else:
                save_data(filename, [])

def fetch_crypto_prices():
    """Fetch cryptocurrency prices from public API or generate realistic ones"""
    SUPPORTED_COINS = ["BTC", "ETH", "ETC", "LTC", "BNB", "TRX", "PEPE", "AAVE", "DOGE", 
                      "SOL", "ADA", "AVAX", "SHIB", "TON", "POL", "FIL", "ATOM"]
    prices = {}
    
    try:
        # Try to fetch from CoinGecko API (as alternate to Binance which returns 451)
        api_ids = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'LTC': 'litecoin', 
            'BNB': 'binancecoin', 'SOL': 'solana', 'ADA': 'cardano', 
            'AVAX': 'avalanche-2', 'DOGE': 'dogecoin'
        }
        
        # We'll try the main coins and fallback for the rest
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,litecoin,binancecoin,solana,cardano,avalanche-2,dogecoin&vs_currencies=usd', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Process the fetched data
            for coin in SUPPORTED_COINS:
                pair = f"{coin}/USDT"
                if coin in api_ids and api_ids[coin] in data:
                    # Get price from API
                    price = data[api_ids[coin]]['usd']
                    prices[pair] = price
                    logging.info(f"Got price for {coin}: ${price}")
                else:
                    # For coins not in API response, use default with variation
                    default_price = DEFAULT_PRICES.get(pair, 1.0)
                    variation = random.uniform(-0.05, 0.05)  # +/- 5% variation
                    prices[pair] = default_price * (1 + variation)
            
            logging.info("Successfully fetched some prices from CoinGecko API")
        else:
            # If API call fails, use defaults with variations
            logging.warning(f"Failed to fetch prices, status code: {response.status_code}")
            raise Exception("API failed")
            
    except Exception as e:
        logging.error(f"Error fetching crypto prices: {str(e)}")
        
        # Try to load existing prices first
        existing_prices = load_data('prices.json')
        if existing_prices and isinstance(existing_prices, dict) and len(existing_prices) > 0:
            prices = existing_prices
            
            # Add some variation to existing prices to make them look fresh
            for pair in prices:
                variation = random.uniform(-0.02, 0.02)  # +/- 2% variation
                prices[pair] = prices[pair] * (1 + variation)
            
            logging.info("Using existing prices with variations")
        else:
            # If no existing prices, use defaults with variations
            prices = DEFAULT_PRICES.copy()
            for pair in prices:
                variation = random.uniform(-0.05, 0.05)  # +/- 5% variation
                prices[pair] = prices[pair] * (1 + variation)
            
            logging.info("Using default prices with variations")
    
    # Make sure we have all the required pairs
    for coin in SUPPORTED_COINS:
        pair = f"{coin}/USDT"
        if pair not in prices:
            prices[pair] = DEFAULT_PRICES.get(pair, 1.0)
    
    # Save the fetched/generated prices
    save_data('prices.json', prices)
    
    return prices

def load_prices():
    """Load current prices, fetching from API if possible"""
    return fetch_crypto_prices()

def save_prices(prices):
    """Save updated prices"""
    save_data('prices.json', prices)

def update_price(coin, new_price, duration):
    """Update the price of a coin for a specific duration"""
    prices = load_prices()
    pair = f"{coin}/USDT"
    
    # Store the original price
    original_price = prices.get(pair, 0)
    
    # Make sure the price is a float
    new_price = float(new_price)
    
    # Update the price
    logging.info(f"Changing price for {pair} from {original_price} to {new_price} for {duration} minutes")
    prices[pair] = new_price
    save_prices(prices)
    
    # Force reload of prices to make sure they are fresh for any API calls
    updated_prices = load_prices()
    if updated_prices.get(pair) == new_price:
        logging.info(f"Price for {pair} successfully updated to {new_price}")
    else:
        logging.error(f"Price update failed. Expected {new_price} but got {updated_prices.get(pair)}")
    
    # Schedule a task to revert the price after the duration
    def revert_price():
        time.sleep(duration * 60)  # Convert minutes to seconds
        current_prices = load_prices()
        
        # Only revert if the price hasn't been changed again by another admin action
        if abs(current_prices.get(pair, 0) - new_price) < 0.01:  # Allow for tiny float differences
            current_prices[pair] = original_price
            save_prices(current_prices)
            logging.info(f"Price for {pair} reverted to {original_price} after {duration} minutes")
        else:
            logging.info(f"Price for {pair} not reverted as it was modified during the duration period")
    
    # Start a thread to revert the price
    revert_thread = threading.Thread(target=revert_price, daemon=True)
    revert_thread.start()
    
    logging.info(f"Price for {pair} updated to {new_price} for {duration} minutes")
    
    return {"success": True, "pair": pair, "price": new_price, "duration": duration}

def calculate_liquidation_price(entry_price, leverage, position_type):
    """Calculate liquidation price based on entry price, leverage, and position type"""
    if position_type == 'long':
        liquidation_price = entry_price * (1 - (1 / leverage))
    else:  # short
        liquidation_price = entry_price * (1 + (1 / leverage))
    
    return round(liquidation_price, 8)

def get_user_balance(user_id):
    """Get the balance of a user"""
    users = load_data('users.json')
    
    for user in users:
        if user.get('id') == user_id:
            return user.get('balance', 0)
    
    return 0

def adjust_balance(user_id, amount):
    """Adjust the balance of a user"""
    users = load_data('users.json')
    
    for user in users:
        if user.get('id') == user_id:
            current_balance = user.get('balance', 0)
            
            if amount < 0 and abs(amount) >= current_balance:
                # Liquidation case - set balance to zero instead of negative
                user['balance'] = 0
                logging.info(f"User {user_id} was liquidated. Balance set to 0 (was: {current_balance}, loss: {amount})")
            else:
                # Normal case - add amount to balance
                user['balance'] = current_balance + amount
                
            save_data('users.json', users)
            return True
    
    return False

def add_bonus_to_new_user(user_id):
    """Add $50 bonus to a new user, valid for 12 hours. 
    The bonus can only be used for trading with max 10x leverage."""
    # Add bonus amount to user's balance
    adjust_balance(user_id, 50)
    
    # Mark user as having a bonus so we can apply restrictions
    users = load_data('users.json')
    for user in users:
        if user.get('id') == user_id:
            user['has_bonus'] = True
            save_data('users.json', users)
            break
    
    # Schedule a task to remove the bonus after 12 hours if not used
    def remove_bonus():
        time.sleep(12 * 60 * 60)  # 12 hours in seconds
        
        # Check if the bonus is still there
        balance = get_user_balance(user_id)
        if balance >= 50:
            adjust_balance(user_id, -50)
            logging.info(f"Removed unused bonus from user {user_id}")
            
            # Remove the bonus flag
            users = load_data('users.json')
            for user in users:
                if user.get('id') == user_id:
                    user['has_bonus'] = False
                    save_data('users.json', users)
                    break
    
    # Start a thread to remove the bonus
    threading.Thread(target=remove_bonus, daemon=True).start()

def get_deposits(user_id=None):
    """Get deposits for a user or all deposits if user_id is None"""
    deposits = load_data('deposits.json')
    
    if user_id is None:
        return deposits
    else:
        return [deposit for deposit in deposits if deposit.get('user_id') == user_id]

def get_withdrawals(user_id=None):
    """Get withdrawals for a user or all withdrawals if user_id is None"""
    withdrawals = load_data('withdrawals.json')
    
    if user_id is None:
        return withdrawals
    else:
        return [withdrawal for withdrawal in withdrawals if withdrawal.get('user_id') == user_id]

def process_deposit(user_id, amount, tx_hash):
    """Process a deposit request"""
    deposits = load_data('deposits.json')
    
    # Generate deposit ID
    deposit_id = str(uuid.uuid4())
    
    # Create deposit data
    deposit_data = {
        'id': deposit_id,
        'user_id': user_id,
        'amount': amount,
        'tx_hash': tx_hash,
        'status': 'pending',
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Add deposit to deposits list
    deposits.append(deposit_data)
    
    # Save deposits data
    save_data('deposits.json', deposits)
    
    return deposit_id

def process_withdrawal(user_id, amount, wallet_address):
    """Process a withdrawal request"""
    withdrawals = load_data('withdrawals.json')
    
    # Generate withdrawal ID
    withdrawal_id = str(uuid.uuid4())
    
    # Create withdrawal data
    withdrawal_data = {
        'id': withdrawal_id,
        'user_id': user_id,
        'amount': amount,
        'wallet_address': wallet_address,
        'status': 'pending',
        'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Add withdrawal to withdrawals list
    withdrawals.append(withdrawal_data)
    
    # Save withdrawals data
    save_data('withdrawals.json', withdrawals)
    
    # Deduct amount from user's balance
    adjust_balance(user_id, -amount)
    
    return withdrawal_id

def create_position(user_id, coin, amount, leverage, entry_price, liquidation_price, position_type, take_profit=None, stop_loss=None):
    """Create a new trading position"""
    trades = load_data('trades.json')
    
    # Generate position ID
    position_id = str(uuid.uuid4())
    
    # Ensure all values are proper numeric types
    amount = float(amount)
    leverage = int(leverage)
    entry_price = float(entry_price)
    liquidation_price = float(liquidation_price)
    
    # Process take_profit and stop_loss if provided
    if take_profit is not None:
        take_profit = float(take_profit)
    if stop_loss is not None:
        stop_loss = float(stop_loss)
    
    # Create position data
    position_data = {
        'id': position_id,
        'user_id': user_id,
        'coin': coin,
        'amount': amount,
        'leverage': leverage,
        'entry_price': entry_price,
        'liquidation_price': liquidation_price,
        'take_profit': take_profit,
        'stop_loss': stop_loss,
        'type': position_type,
        'status': 'open',
        'open_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Add position to trades list
    trades.append(position_data)
    
    # Save trades data
    save_data('trades.json', trades)
    
    logging.info(f"New position opened: {coin} {position_type} with amount ${amount} and leverage {leverage}x")
    
    return position_id

def close_position(position_id, close_price):
    """Close a trading position"""
    trades = load_data('trades.json')
    
    for trade in trades:
        if trade.get('id') == position_id and trade.get('status') == 'open':
            # Ensure all values are proper numeric types
            entry_price = float(trade.get('entry_price', 0))
            amount = float(trade.get('amount', 0))
            leverage = float(trade.get('leverage', 1))
            position_type = trade.get('type')
            close_price = float(close_price)
            
            if position_type == 'long':
                price_difference = close_price - entry_price
            else:  # short
                price_difference = entry_price - close_price
            
            # Calculate profit/loss
            price_change_percentage = 0
            if entry_price > 0:
                price_change_percentage = price_difference / entry_price
                profit_loss = amount + (amount * leverage * price_change_percentage)
            else:
                profit_loss = 0
                
            # Round to avoid floating point issues
            profit_loss = round(profit_loss, 2)
            
            # Update trade data
            trade['close_price'] = close_price
            trade['profit_loss'] = profit_loss
            trade['status'] = 'closed'
            trade['close_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            trade['price_change_percentage'] = round(price_change_percentage * 100, 2)
            
            # Save trades data
            save_data('trades.json', trades)
            
            logging.info(f"Position {position_id} closed with profit/loss: ${profit_loss}")
            
            return {
                'position_id': position_id,
                'profit_loss': profit_loss
            }
    
    return None
    
def get_positions_analysis():
    """Get analysis of all positions for admin dashboard
    
    Returns:
        Dictionary with position statistics
    """
    trades = load_data('trades.json')
    
    if not trades:
        return {
            'total_positions': 0,
            'open_count': 0,
            'closed_count': 0,
            'liquidated_count': 0,
            'long_positions': 0,
            'short_positions': 0,
            'long_percentage': 0,
            'short_percentage': 0,
            'total_profit': 0,
            'total_loss': 0,
            'net_profit_loss': 0,
            'coin_distribution': {},
            'avg_leverage': 0,
            'total_volume': 0
        }
    
    # Basic counts
    total_positions = len(trades)
    open_count = sum(1 for t in trades if t.get('status') == 'open')
    closed_count = sum(1 for t in trades if t.get('status') == 'closed')
    liquidated_count = sum(1 for t in trades if t.get('status') == 'liquidated')
    
    # Position types
    long_positions = sum(1 for t in trades if t.get('type') == 'long')
    short_positions = total_positions - long_positions
    
    # Calculate percentages
    long_percentage = round((long_positions / total_positions * 100) if total_positions > 0 else 0, 1)
    short_percentage = round((short_positions / total_positions * 100) if total_positions > 0 else 0, 1)
    
    # Calculate profit/loss
    total_profit = 0
    total_loss = 0
    
    for trade in trades:
        if trade.get('status') in ['closed', 'liquidated'] and 'profit_loss' in trade:
            pl = float(trade.get('profit_loss', 0))
            if pl > 0:
                total_profit += pl
            else:
                total_loss += abs(pl)
    
    net_profit_loss = total_profit - total_loss
    
    # Distribution by coin
    coin_distribution = {}
    for t in trades:
        coin = t.get('coin')
        if coin not in coin_distribution:
            coin_distribution[coin] = 0
        coin_distribution[coin] += 1
    
    # Average leverage
    total_leverage = sum(float(t.get('leverage', 1)) for t in trades)
    avg_leverage = total_leverage / total_positions if total_positions > 0 else 0
    
    # Total volume
    total_volume = sum(float(t.get('amount', 0)) for t in trades)
    
    return {
        'total_positions': total_positions,
        'open_count': open_count,
        'closed_count': closed_count,
        'liquidated_count': liquidated_count,
        'long_positions': long_positions,
        'short_positions': short_positions,
        'long_percentage': long_percentage,
        'short_percentage': short_percentage,
        'total_profit': round(total_profit, 2),
        'total_loss': round(total_loss, 2),
        'net_profit_loss': round(net_profit_loss, 2),
        'coin_distribution': coin_distribution,
        'avg_leverage': round(avg_leverage, 2),
        'total_volume': round(total_volume, 2)
    }

def get_leaderboard(limit=10):
    """Get the top traders leaderboard based on profit percentage
    
    Args:
        limit: Maximum number of users to return
        
    Returns:
        List of top users with their trading stats
    """
    users = load_data('users.json')
    trades = load_data('trades.json')
    
    # Calculate total profit/loss and success rate for each user
    leaderboard_data = {}
    
    for user in users:
        user_id = user.get('id')
        username = user.get('username')
        
        # Skip admin from leaderboard
        if username == ADMIN_USERNAME:
            continue
            
        # Get all closed trades for this user
        user_trades = [t for t in trades if t.get('user_id') == user_id and t.get('status') == 'closed']
        
        if not user_trades:
            continue
            
        # Calculate total profits
        total_profit = sum(float(t.get('profit_loss', 0)) for t in user_trades)
        total_invested = sum(float(t.get('amount', 0)) for t in user_trades)
        
        # Calculate win rate
        profitable_trades = sum(1 for t in user_trades if float(t.get('profit_loss', 0)) > 0)
        win_rate = (profitable_trades / len(user_trades)) * 100 if user_trades else 0
        
        # Calculate average leverage
        total_leverage = sum(float(t.get('leverage', 1)) for t in user_trades)
        avg_leverage = total_leverage / len(user_trades) if user_trades else 0
        
        # Calculate ROI (Return on Investment)
        roi = (total_profit / total_invested) * 100 if total_invested > 0 else 0
        
        # Track largest single profit
        largest_profit = max([float(t.get('profit_loss', 0)) for t in user_trades]) if user_trades else 0
        
        leaderboard_data[user_id] = {
            'user_id': user_id,
            'username': username,
            'name': user.get('name', ''),
            'total_profit': round(total_profit, 2),
            'win_rate': round(win_rate, 2),
            'avg_leverage': round(avg_leverage, 2),
            'roi': round(roi, 2),
            'trade_count': len(user_trades),
            'largest_profit': round(largest_profit, 2)
        }
    
    # Sort users by ROI (Return on Investment)
    sorted_users = sorted(
        leaderboard_data.values(), 
        key=lambda x: x['roi'], 
        reverse=True
    )
    
    # Return top users up to the limit
    return sorted_users[:limit]

def authenticate_admin(username, password):
    """Authenticate admin user"""
    # Direct comparison for admin credentials
    return username == ADMIN_USERNAME and password == "shGh1389@"
