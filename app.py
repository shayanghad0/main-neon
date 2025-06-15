import os
import json
import datetime
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from models import User, get_all_users, get_user_by_username, create_user, update_user, get_user_positions
from forms import LoginForm, RegisterForm, DepositForm, WithdrawalForm, TradeForm, PriceForm
from utils import (load_data, save_data, initialize_data_files, calculate_liquidation_price, 
                  load_prices, save_prices, update_price, get_deposits, get_withdrawals, 
                  process_deposit, process_withdrawal, create_position, close_position, 
                  get_user_balance, adjust_balance, add_bonus_to_new_user, authenticate_admin,
                  get_leaderboard, get_positions_analysis)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# CSRF exempt routes
@csrf.exempt
def csrf_exempt(route_function):
    return route_function

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure data directory exists
if not os.path.exists('data'):
    os.makedirs('data')

# Initialize data files if they don't exist
initialize_data_files()

# Load supported cryptocurrencies
SUPPORTED_COINS = ["BTC", "ETH", "ETC", "LTC", "BNB", "TRX", "PEPE", "AAVE", "DOGE", 
                   "SOL", "ADA", "AVAX", "SHIB", "TON", "POL", "FIL", "ATOM"]

@login_manager.user_loader
def load_user(user_id):
    users = load_data('users.json')
    for user in users:
        if str(user['id']) == user_id:
            return User(user)
    return None

# Public Routes
@app.route('/')
def index():
    prices = load_prices()
    return render_template('public/index.html', prices=prices, SUPPORTED_COINS=SUPPORTED_COINS)

@app.route('/bonus-guide')
def bonus_guide():
    return render_template('public/bonus_guide.html')

@app.route('/leaderboard')
def leaderboard():
    # Get top 10 traders
    top_traders = get_leaderboard(limit=10)
    return render_template('public/leaderboard.html', top_traders=top_traders)

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # First try admin authentication
        if authenticate_admin(username, password):
            session['admin'] = True
            session['username'] = username
            flash('ورود مدیر با موفقیت انجام شد', 'success')
            return redirect(url_for('admin_dashboard'))

        # If not admin, try regular user authentication
        user = get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('ورود با موفقیت انجام شد', 'success')
            return redirect(url_for('user_dashboard'))

        # If neither admin nor user authentication worked
        flash('نام کاربری یا رمز عبور اشتباه است', 'danger')

    return render_template('auth/login.html', form=form)

@app.route('/logout')
def logout():
    if 'admin' in session:
        session.pop('admin')
        session.pop('username')
    else:
        logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
@csrf.exempt
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Create new user
        user_data = {
            'username': form.username.data,
            'email': form.email.data,
            'name': form.name.data,
            'password_hash': form.password.data,  # Will be hashed in create_user
            'registered_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance': 0,
            'is_active': True
        }

        user = create_user(user_data)
        if user:
            # Add bonus to new user
            add_bonus_to_new_user(user.id)

            # Login the user
            login_user(user)
            flash('Registration successful! 50$ bonus added to your account (valid for 12 hours)', 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash('Username or email already exists', 'danger')

    return render_template('auth/register.html', form=form)

# User Routes
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    balance = get_user_balance(current_user.id)
    positions = get_user_positions(current_user.id)

    return render_template('user/dashboard.html', 
                          user=current_user, 
                          balance=balance, 
                          positions=positions,
                          SUPPORTED_COINS=SUPPORTED_COINS)

@app.route('/user/deposit', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def user_deposit():
    form = DepositForm()
    if form.validate_on_submit():
        amount = form.amount.data
        tx_hash = form.tx_hash.data

        if amount < 100:
            flash('Minimum deposit amount is 100$', 'danger')
        else:
            deposit_id = process_deposit(current_user.id, amount, tx_hash)
            if deposit_id:
                flash('Deposit request submitted successfully. Waiting for admin approval.', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Failed to process deposit', 'danger')

    # Get user's deposit history
    deposits = get_deposits(current_user.id)
    return render_template('user/deposit.html', form=form, deposits=deposits)

@app.route('/user/withdrawals', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def user_withdrawals():
    form = WithdrawalForm()
    balance = get_user_balance(current_user.id)

    if form.validate_on_submit():
        amount = form.amount.data
        wallet_address = form.wallet_address.data

        # Check if user has bonus money that can't be withdrawn
        users = load_data('users.json')
        user = next((u for u in users if u.get('id') == current_user.id), None)
        has_bonus = user.get('has_bonus', False) if user else False

        if amount < 150:
            flash('Minimum withdrawal amount is 150$', 'danger')
        elif amount > balance:
            flash('Insufficient balance', 'danger')
        elif has_bonus and balance <= 50:
            flash('You need to make profits from trading before withdrawing.', 'danger')
        elif has_bonus and amount > balance - 50:
            # Allow withdrawal of any amount above the bonus
            remaining = balance - 50
            flash(f'You can only withdraw up to ${remaining:.2f} while keeping the $50 bonus for trading.', 'danger')
        else:
            withdrawal_id = process_withdrawal(current_user.id, amount, wallet_address)
            if withdrawal_id:
                flash('Withdrawal request submitted successfully. Waiting for admin approval.', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Failed to process withdrawal', 'danger')

    # Get user's withdrawal history
    withdrawals = get_withdrawals(current_user.id)
    return render_template('user/withdrawals.html', form=form, withdrawals=withdrawals, balance=balance)

@app.route('/user/trade/<coin>')
@login_required
def user_trade(coin):
    if coin not in SUPPORTED_COINS:
        flash('Invalid cryptocurrency', 'danger')
        return redirect(url_for('user_dashboard'))

    balance = get_user_balance(current_user.id)
    form = TradeForm()
    prices = load_prices()

    return render_template('user/trade.html', 
                          user=current_user,
                          balance=balance,
                          coin=coin,
                          prices=prices,
                          form=form,
                          SUPPORTED_COINS=SUPPORTED_COINS)

@app.route('/api/open-position', methods=['POST'])
@login_required
@csrf.exempt
def open_position():
    data = request.json

    coin = data.get('coin')
    amount = float(data.get('amount'))
    leverage = int(data.get('leverage'))
    position_type = data.get('type')  # 'long' or 'short'
    take_profit = data.get('take_profit')  # Optional
    stop_loss = data.get('stop_loss')  # Optional

    if coin not in SUPPORTED_COINS:
        return jsonify({'success': False, 'message': 'Invalid cryptocurrency'})

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Amount must be greater than 0'})

    # Check leverage limits based on coin
    if coin == 'BTC':
        max_leverage = 500  # Bitcoin can go up to 500x
    else:
        max_leverage = 250  # Other coins limited to 250x

    # Cap leverage if it exceeds the limit
    if leverage > max_leverage:
        leverage = max_leverage

    if leverage < 1:
        return jsonify({'success': False, 'message': 'Leverage must be at least 1x'})

    balance = get_user_balance(current_user.id)
    if amount > balance:
        return jsonify({'success': False, 'message': 'Insufficient balance'})

    prices = load_prices()
    entry_price = prices.get(f"{coin}/USDT", 0)

    if entry_price <= 0:
        return jsonify({'success': False, 'message': 'Invalid price data'})

    # Calculate liquidation price
    liquidation_price = calculate_liquidation_price(entry_price, leverage, position_type)

    # Create position
    position_id = create_position(current_user.id, coin, amount, leverage, entry_price, liquidation_price, position_type, take_profit, stop_loss)

    if position_id:
        # Deduct amount from balance
        adjust_balance(current_user.id, -amount)
        return jsonify({
            'success': True, 
            'message': 'Position opened successfully',
            'position_id': position_id,
            'entry_price': entry_price,
            'liquidation_price': liquidation_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to open position'})

@app.route('/api/close-position/<position_id>', methods=['POST'])
@login_required
@csrf.exempt
def close_position_route(position_id):
    positions = get_user_positions(current_user.id)
    position = None

    for pos in positions:
        if pos.get('id') == position_id:
            position = pos
            break

    if not position:
        return jsonify({'success': False, 'message': 'Position not found'})

    prices = load_prices()
    close_price = prices.get(f"{position['coin']}/USDT", 0)

    if close_price <= 0:
        return jsonify({'success': False, 'message': 'Invalid price data'})

    result = close_position(position_id, close_price)

    if result:
        # Add profit/loss to balance
        profit_loss = result.get('profit_loss', 0)
        adjust_balance(current_user.id, profit_loss)

        return jsonify({
            'success': True, 
            'message': 'Position closed successfully',
            'profit_loss': profit_loss
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to close position'})

# Admin Routes
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    users = get_all_users()
    total_users = len(users)

    # Calculate total balance
    total_balance = sum(get_user_balance(user.id) for user in users)

    # Get recent deposit and withdrawal requests
    deposits = load_data('deposits.json')
    withdrawals = load_data('withdrawals.json')

    recent_deposits = sorted(deposits, key=lambda x: x.get('date'), reverse=True)[:5]
    recent_withdrawals = sorted(withdrawals, key=lambda x: x.get('date'), reverse=True)[:5]

    # Get active positions
    trades = load_data('trades.json')
    active_positions = [trade for trade in trades if trade.get('status') == 'open']

    return render_template('admin/dashboard.html', 
                          total_users=total_users,
                          total_balance=total_balance,
                          recent_deposits=recent_deposits,
                          recent_withdrawals=recent_withdrawals,
                          active_positions=active_positions)

@app.route('/admin/user-management')
def admin_user_management():
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    users = get_all_users()
    user_data = []

    for user in users:
        positions = get_user_positions(user.id)
        balance = get_user_balance(user.id)

        user_data.append({
            'user': user,
            'balance': balance,
            'positions': positions
        })

    return render_template('admin/user_management.html', users=user_data)

@app.route('/admin/user/<user_id>', methods=['GET', 'POST'])
@csrf.exempt
def admin_user_detail(user_id):
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    users = load_data('users.json')
    user_data = None

    for user in users:
        if str(user.get('id')) == user_id:
            user_data = user
            break

    if not user_data:
        flash('User not found', 'danger')
        return redirect(url_for('admin_user_management'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update':
            # Update user data
            user_data['name'] = request.form.get('name')
            user_data['email'] = request.form.get('email')
            user_data['balance'] = float(request.form.get('balance'))

            save_data('users.json', users)
            flash('User updated successfully', 'success')
        elif action == 'ban':
            # Ban user
            reason = request.form.get('ban_reason')
            user_data['is_active'] = False
            user_data['ban_reason'] = reason

            save_data('users.json', users)
            flash('User banned successfully', 'success')
        elif action == 'unban':
            # Unban user
            user_data['is_active'] = True
            if 'ban_reason' in user_data:
                del user_data['ban_reason']

            save_data('users.json', users)
            flash('User unbanned successfully', 'success')

    positions = get_user_positions(int(user_id))

    # Get user's recent activity
    deposits = [d for d in load_data('deposits.json') if d.get('user_id') == int(user_id)]
    withdrawals = [w for w in load_data('withdrawals.json') if w.get('user_id') == int(user_id)]
    trades = [t for t in load_data('trades.json') if t.get('user_id') == int(user_id)]

    recent_activity = []
    for deposit in deposits:
        recent_activity.append({
            'type': 'deposit',
            'date': deposit.get('date'),
            'amount': deposit.get('amount'),
            'status': deposit.get('status')
        })

    for withdrawal in withdrawals:
        recent_activity.append({
            'type': 'withdrawal',
            'date': withdrawal.get('date'),
            'amount': withdrawal.get('amount'),
            'status': withdrawal.get('status')
        })

    for trade in trades:
        recent_activity.append({
            'type': 'trade',
            'date': trade.get('open_date'),
            'coin': trade.get('coin'),
            'amount': trade.get('amount'),
            'leverage': trade.get('leverage'),
            'status': trade.get('status')
        })

    recent_activity = sorted(recent_activity, key=lambda x: x.get('date'), reverse=True)[:10]

    return render_template('admin/user_detail.html', 
                          user=user_data,
                          positions=positions,
                          recent_activity=recent_activity)

@app.route('/admin/requests')
def admin_requests():
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    deposits = load_data('deposits.json')
    withdrawals = load_data('withdrawals.json')

    pending_deposits = [d for d in deposits if d.get('status') == 'pending']
    pending_withdrawals = [w for w in withdrawals if w.get('status') == 'pending']

    return render_template('admin/requests.html', 
                          pending_deposits=pending_deposits,
                          pending_withdrawals=pending_withdrawals)

@app.route('/admin/request/deposit/<request_id>', methods=['POST'])
@csrf.exempt
def admin_deposit_action(request_id):
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    action = request.form.get('action')
    deposits = load_data('deposits.json')

    for deposit in deposits:
        if str(deposit.get('id')) == request_id:
            if action == 'approve':
                deposit['status'] = 'approved'
                deposit['approved_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Add amount to user's balance
                adjust_balance(deposit.get('user_id'), deposit.get('amount'))

                flash('Deposit approved successfully', 'success')
            elif action == 'reject':
                reason = request.form.get('reject_reason')
                deposit['status'] = 'rejected'
                deposit['rejected_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                deposit['reject_reason'] = reason

                flash('Deposit rejected successfully', 'success')

            save_data('deposits.json', deposits)
            break

    return redirect(url_for('admin_requests'))

@app.route('/admin/request/withdrawal/<request_id>', methods=['POST'])
@csrf.exempt
def admin_withdrawal_action(request_id):
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    action = request.form.get('action')
    withdrawals = load_data('withdrawals.json')

    for withdrawal in withdrawals:
        if str(withdrawal.get('id')) == request_id:
            if action == 'approve':
                withdrawal['status'] = 'approved'
                withdrawal['approved_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                flash('Withdrawal approved successfully', 'success')
            elif action == 'reject':
                reason = request.form.get('reject_reason')
                withdrawal['status'] = 'rejected'
                withdrawal['rejected_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                withdrawal['reject_reason'] = reason

                # Refund amount to user's balance
                adjust_balance(withdrawal.get('user_id'), withdrawal.get('amount'))

                flash('Withdrawal rejected successfully', 'success')

            save_data('withdrawals.json', withdrawals)
            break

    return redirect(url_for('admin_requests'))

@app.route('/admin/price', methods=['GET', 'POST'])
@csrf.exempt
def admin_price():
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    form = PriceForm()
    prices = load_prices()

    if form.validate_on_submit():
        coin = form.coin.data
        new_price = form.price.data
        duration = form.duration.data

        if coin not in SUPPORTED_COINS:
            flash('Invalid cryptocurrency', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid cryptocurrency'})
        else:
            # Call the update_price function
            result = update_price(coin, new_price, duration)
            if result and result.get('success'):
                flash(f'Price updated successfully for {duration} minutes', 'success')

                # Reload the prices to make sure we have the latest
                updated_prices = load_prices()
                current_price = updated_prices.get(f"{coin}/USDT")

                # Log success with details
                app.logger.info(f"Admin price change: {coin} to {current_price}$ for {duration} minutes")

                # Handle AJAX requests differently
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True, 
                        'message': f'Price updated successfully for {duration} minutes',
                        'coin': coin,
                        'price': current_price,  # Use the actual price from updated_prices
                        'duration': duration
                    })
            else:
                flash('Error updating price', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False, 
                        'message': 'Error updating price'
                    })
            return redirect(url_for('admin_price'))

    return render_template('admin/price.html', form=form, prices=prices, SUPPORTED_COINS=SUPPORTED_COINS)

@app.route('/admin/positions')
def admin_positions():
    if 'admin' not in session:
        flash('Admin login required', 'danger')
        return redirect(url_for('login', type='admin'))

    # Get position statistics
    position_analysis = get_positions_analysis()

    # Get all positions
    trades = load_data('trades.json')

    # Get user information for positions
    users = {user.id: user for user in get_all_users()}

    for trade in trades:
        user_id = trade.get('user_id')
        if user_id in users:
            trade['username'] = users[user_id].username
        else:
            trade['username'] = "Unknown"

    return render_template('admin/positions.html', 
                          position_analysis=position_analysis,
                          trades=trades,
                          SUPPORTED_COINS=SUPPORTED_COINS)

# API routes
@app.route('/api/prices')
@csrf.exempt
def api_prices():
    prices = load_prices()
    return jsonify(prices)

@app.route('/api/positions')
@login_required
@csrf.exempt
def api_positions():
    positions = get_user_positions(current_user.id)
    prices = load_prices()

    # Include current price for each position
    for position in positions:
        coin = position.get('coin')
        position['current_price'] = prices.get(f"{coin}/USDT", 0)

        # Calculate profit/loss in real-time
        if position.get('status') == 'open':
            entry_price = float(position.get('entry_price', 0))
            amount = float(position.get('amount', 0))
            leverage = float(position.get('leverage', 1))
            position_type = position.get('type')
            current_price = position['current_price']

            if position_type == 'long':
                price_difference = current_price - entry_price
            else:  # short
                price_difference = entry_price - current_price

            if entry_price > 0:
                price_change_percentage = price_difference / entry_price
                profit_loss = amount + (amount * leverage * price_change_percentage)
                position['current_profit_loss'] = round(profit_loss, 2)
                position['price_change_percentage'] = round(price_change_percentage * 100, 2)

                # Check if take profit or stop loss has been hit
                take_profit = position.get('take_profit')
                stop_loss = position.get('stop_loss')

                if position_type == 'long':
                    # For long positions
                    if take_profit is not None and current_price >= float(take_profit):
                        # Take profit hit for long position
                        result = close_position(position['id'], current_price)
                        if result:
                            adjust_balance(current_user.id, result.get('profit_loss', 0))
                            position['status'] = 'closed'
                            position['close_price'] = current_price
                            position['profit_loss'] = result.get('profit_loss', 0)
                            position['close_reason'] = 'take_profit'
                    elif stop_loss is not None and current_price <= float(stop_loss):
                        # Stop loss hit for long position
                        result = close_position(position['id'], current_price)
                        if result:
                            adjust_balance(current_user.id, result.get('profit_loss', 0))
                            position['status'] = 'closed'
                            position['close_price'] = current_price
                            position['profit_loss'] = result.get('profit_loss', 0)
                            position['close_reason'] = 'stop_loss'
                else:  # short position
                    # For short positions
                    if take_profit is not None and current_price <= float(take_profit):
                        # Take profit hit for short position
                        result = close_position(position['id'], current_price)
                        if result:
                            adjust_balance(current_user.id, result.get('profit_loss', 0))
                            position['status'] = 'closed'
                            position['close_price'] = current_price
                            position['profit_loss'] = result.get('profit_loss', 0)
                            position['close_reason'] = 'take_profit'
                    elif stop_loss is not None and current_price >= float(stop_loss):
                        # Stop loss hit for short position
                        result = close_position(position['id'], current_price)
                        if result:
                            adjust_balance(current_user.id, result.get('profit_loss', 0))
                            position['status'] = 'closed'
                            position['close_price'] = current_price
                            position['profit_loss'] = result.get('profit_loss', 0)
                            position['close_reason'] = 'stop_loss'

    return jsonify(positions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
