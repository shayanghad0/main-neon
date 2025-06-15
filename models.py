import os
import json
import datetime
import uuid
from werkzeug.security import generate_password_hash
from flask_login import UserMixin
from utils import load_data, save_data

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.name = user_data.get('name')
        self.password_hash = user_data.get('password_hash')
        self.registered_date = user_data.get('registered_date')
        self._is_active = user_data.get('is_active', True)
        self.ban_reason = user_data.get('ban_reason', '')
        
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
        
    @property
    def is_active(self):
        return self._is_active
        
    @is_active.setter
    def is_active(self, value):
        self._is_active = value

def get_all_users():
    users_data = load_data('users.json')
    return [User(user) for user in users_data]

def get_user_by_username(username):
    users_data = load_data('users.json')
    for user_data in users_data:
        if user_data.get('username') == username:
            return User(user_data)
    return None

def get_user_by_id(user_id):
    users_data = load_data('users.json')
    for user_data in users_data:
        if user_data.get('id') == user_id:
            return User(user_data)
    return None

def create_user(user_data):
    users = load_data('users.json')
    
    # Check if username or email already exists
    for user in users:
        if user.get('username') == user_data.get('username') or user.get('email') == user_data.get('email'):
            return None
    
    # Generate user ID
    user_id = 1
    if users:
        user_id = max(user.get('id', 0) for user in users) + 1
    
    # Hash password
    password = user_data.get('password_hash')
    user_data['password_hash'] = generate_password_hash(password)
    
    # Add ID to user data
    user_data['id'] = user_id
    
    # Add user to users list
    users.append(user_data)
    
    # Save users data
    save_data('users.json', users)
    
    return User(user_data)

def update_user(user_id, update_data):
    users = load_data('users.json')
    
    for user in users:
        if user.get('id') == user_id:
            for key, value in update_data.items():
                if key == 'password':
                    user['password_hash'] = generate_password_hash(value)
                else:
                    user[key] = value
            
            save_data('users.json', users)
            return True
    
    return False

def get_user_positions(user_id):
    trades = load_data('trades.json')
    return [trade for trade in trades if trade.get('user_id') == user_id and trade.get('status') == 'open']
