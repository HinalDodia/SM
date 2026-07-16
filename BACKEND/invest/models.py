from invest import db
from datetime import datetime 


class Users(db.Model):
    __tablename__='users'
    userid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # username/display name
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))  # nullable for SSO users
    otp_code = db.Column(db.String(10))
    otp_ts = db.Column(db.DateTime)
    money=db.Column(db.Numeric(12,2), default=10000)
    profitorloss=db.Column(db.Numeric(12,2), default=0)
    profitpercent=db.Column(db.Float,default=0.0)
    losspercent=db.Column(db.Float,default=0.0)
    last_login=db.Column(db.DateTime)
    progress = db.Column(db.Integer, default=0)
    level = db.Column(db.String(20), default='Beginner')

    watchlist = db.relationship('Watchlist', backref='users', lazy=True)
    portfolio =db.relationship('Portfolio', backref='users',cascade="all, delete")


class Stock(db.Model):
    __tablename__ = 'stock'
    stock_id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(10), unique=True, nullable=False)
    stock_name = db.Column(db.String(100))

    watchlisted_by = db.relationship('Watchlist', backref='stock', lazy=True)
    portfolio_entries = db.relationship('Portfolio', backref='stock', lazy=True)


class Watchlist(db.Model): 
    __tablename__ = 'watchlist'
    watchlist_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.stock_id'), nullable=False)


class Portfolio(db.Model):
    __tablename__='portfolio'
    portfolioid=db.Column(db.Integer,primary_key=True,autoincrement=True)
    userid=db.Column(db.Integer,db.ForeignKey('users.userid'))
    stockname=db.Column(db.String(100))
    companyname=db.Column(db.String(100))
    totalquantity = db.Column(db.Integer, default=0)  
    averagebuyprice = db.Column(db.Numeric(12, 2), default=0.00)  
    totalinvested = db.Column(db.Numeric(12, 2), default=0.00)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.stock_id')) 
    sector = db.Column(db.String(100), nullable=True)
  


class Transactionhistory(db.Model):
    __tablename__='transactionhistory'
    transactionid=db.Column(db.Integer,primary_key=True,autoincrement=True)
    userid=db.Column(db.Integer,db.ForeignKey('users.userid'),nullable=False)
    portfolioid=db.Column(db.Integer,db.ForeignKey('portfolio.portfolioid'),nullable=False)
    companyname=db.Column(db.String(100),nullable=False)
    stockname=db.Column(db.String(100),nullable=False)
    quantity=db.Column(db.Integer,nullable=False)
    price=db.Column(db.Numeric(12,2),nullable=False)
    transactiontype=db.Column(db.String(10),nullable=False)
    timestamp=db.Column(db.DateTime,default=datetime)


class FIFOLot(db.Model):
    __tablename__ = 'fifolot'
    lotid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userid = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)
    portfolioid = db.Column(db.Integer, db.ForeignKey('portfolio.portfolioid'), nullable=False)
    companyname = db.Column(db.String(100), nullable=False)
    quantityremaining = db.Column(db.Integer, nullable=False)  
    pricepershare = db.Column(db.Numeric(12, 2), nullable=False) 
    buydate = db.Column(db.DateTime, default=datetime)


class Stockhistory(db.Model):   # ✅ renamed to proper CamelCase
    __tablename__ = "stockhistory"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userid = db.Column(db.Integer, db.ForeignKey("users.userid"))
    stock_name = db.Column(db.String(50), nullable=False)
    dates = db.Column(db.Date, nullable=False)
    close_price = db.Column(db.Float, nullable=False)


class Useractivity(db.Model):
    __tablename__ = "useractivity"
    activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userid = db.Column(db.Integer, db.ForeignKey("users.userid"))
    activity_type = db.Column(db.String(50), nullable=False)
    activity_value = db.Column(db.Float, default=0)
    activity_date = db.Column(db.DateTime, server_default=db.func.now())


class Stockdata(db.Model):
    __tablename__ = "stockdata"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    symbol = db.Column(db.String(30))
    date = db.Column(db.Date)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    adj_close = db.Column(db.Float)
    volume = db.Column(db.BigInteger)

class Milestones(db.Model):
    __tablename__ = "milestones"
    milestone_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50))
    description = db.Column(db.String(255))
    type = db.Column(db.String(20))   # "portfolio", "profit", "consistency"
    threshold_value = db.Column(db.Float)


class UserMilestones(db.Model):
    __tablename__ = "usermilestones"   # match your table name exactly
    usermilestone_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ✅ correct column name
    userid = db.Column(db.Integer, db.ForeignKey("users.userid"))
    milestone_id = db.Column(db.Integer, db.ForeignKey("milestones.milestone_id"))
    achieved_on = db.Column(db.DateTime, default=datetime.utcnow)

