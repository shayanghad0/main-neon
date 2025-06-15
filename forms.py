from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, IntegerField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional
from werkzeug.security import generate_password_hash

class LoginForm(FlaskForm):
    username = StringField('نام کاربری', validators=[DataRequired()])
    password = PasswordField('رمز عبور', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('نام کاربری', validators=[DataRequired(), Length(min=4, max=20)])
    name = StringField('نام', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('ایمیل', validators=[DataRequired(), Email()])
    password = PasswordField('رمز عبور', validators=[
        DataRequired(),
        Length(min=8, message='رمز عبور باید حداقل 8 کاراکتر باشد')
    ])
    confirm_password = PasswordField('تکرار رمز عبور', validators=[
        DataRequired(),
        EqualTo('password', message='رمز عبور باید تطابق داشته باشد')
    ])

class DepositForm(FlaskForm):
    amount = FloatField('مقدار (دلار)', validators=[
        DataRequired(),
        NumberRange(min=100, message='حداقل مقدار 100 دلار است')
    ])
    tx_hash = StringField('تراکنش هش', validators=[DataRequired()])

class WithdrawalForm(FlaskForm):
    amount = FloatField('مقدار (دلار)', validators=[
        DataRequired(),
        NumberRange(min=150, message='حداقل مقدار 150 دلار است')
    ])
    wallet_address = StringField('آدرس کیف پول', validators=[DataRequired()])

class TradeForm(FlaskForm):
    amount = FloatField('مقدار (دلار)', validators=[DataRequired()])
    leverage = IntegerField('اهرم', validators=[
        DataRequired(),
        NumberRange(min=1, max=10000, message='اهرم باید بین 1x تا 10000x باشد')
    ])
    position_type = SelectField('نوع موقعیت', choices=[('long', 'خرید (Long)'), ('short', 'فروش (Short)')], validators=[DataRequired()])
    take_profit = FloatField('حد سود (Take Profit)', validators=[Optional()])
    stop_loss = FloatField('حد ضرر (Stop Loss)', validators=[Optional()])

class PriceForm(FlaskForm):
    coin = SelectField('ارز دیجیتال', choices=[
        ('BTC', 'BTC'),
        ('ETH', 'ETH'),
        ('ETC', 'ETC'),
        ('LTC', 'LTC'),
        ('BNB', 'BNB'),
        ('TRX', 'TRX'),
        ('PEPE', 'PEPE'),
        ('AAVE', 'AAVE'),
        ('DOGE', 'DOGE'),
        ('SOL', 'SOL'),
        ('ADA', 'ADA'),
        ('AVAX', 'AVAX'),
        ('SHIB', 'SHIB'),
        ('TON', 'TON'),
        ('POL', 'POL'),
        ('FIL', 'FIL'),
        ('ATOM', 'ATOM')
    ], validators=[DataRequired()])
    price = FloatField('قیمت جدید', validators=[DataRequired()])
    duration = IntegerField('مدت زمان (دقیقه)', validators=[
        DataRequired(),
        NumberRange(min=1, max=60, message='مدت زمان باید بین 1 تا 60 دقیقه باشد')
    ])
