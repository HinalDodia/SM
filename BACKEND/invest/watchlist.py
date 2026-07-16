# watchlist.py
from flask import request, jsonify
from invest import db
from invest.models import Users, Stock, Watchlist, Portfolio, FIFOLot, Transactionhistory
from datetime import datetime
from decimal import Decimal
import yfinance as yf

def add_to_watchlist():
    data = request.get_json()
    user_id = data.get('userid')
    stock_id = data.get('stock_id')

    if not user_id or not stock_id:
        return jsonify({'error': 'Missing userid or stock_id'}), 400

    existing = Watchlist.query.filter_by(user_id=user_id, stock_id=stock_id).first()
    if existing:
        return jsonify({'message': 'Stock already in watchlist'}), 200

    new_entry = Watchlist(user_id=user_id, stock_id=stock_id)
    db.session.add(new_entry)
    db.session.commit()
    return jsonify({'message': 'Stock added to watchlist'}), 201

#---------------------------------------------------------------------------------

def get_watchlist(userid):
    try:
        watchlist_entries = Watchlist.query.filter_by(user_id=userid).all()
        stock_data = []

        for entry in watchlist_entries:
            stock = entry.stock
            if not stock:
                continue

            symbol_plain = stock.stock_symbol
            symbol = symbol_plain

            # default logo (always present)
            logo_url = "https://assets-netstorage.groww.in/stock-assets/logos/Groww-Generic-Stock.png"

            try:
                ticker =yf.Ticker(symbol.upper()+ ".NS")
                info = ticker.info or {}

                price = info.get("regularMarketPrice") or info.get("previousClose")
                previous_close = info.get("previousClose")

                change = None
                change_percent = None

                if price is not None and previous_close:
                    change = round(price - previous_close, 2)
                    change_percent = round((change / previous_close) * 100, 2)

                stock_data.append({
                    "stock_id": stock.stock_id,
                    "symbol": symbol_plain,
                    "name": stock.stock_name,
                    "price": float(price) if price is not None else None,
                    "change": float(change) if change is not None else None,
                    "change_percent": float(change_percent) if change_percent is not None else None,
                    "logo_url": logo_url
                })

            except Exception as e:
                stock_data.append({
                    "stock_id": stock.stock_id,
                    "symbol": symbol_plain,
                    "name": stock.stock_name,
                    "logo_url": logo_url,
                    "error": str(e)
                })

        return jsonify(stock_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def remove_from_watchlist(userid, stock_id):
    try:
        if not userid or not stock_id:
            return jsonify({'error': 'userid and stock_id are required'}), 400

        entry = Watchlist.query.filter_by(user_id=userid, stock_id=stock_id).first()
        if not entry:
            return jsonify({'message': 'Entry not found in watchlist'}), 404

        db.session.delete(entry)
        db.session.commit()
        # This returns a Response object
        return jsonify({'message': 'Stock removed from watchlist successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove stock: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'error': f'Failed to remove stock: {str(e)}'}), 500

def buy_from_watchlist():
    data = request.get_json()
    user_id = data.get('userid')
    symbol = data.get('symbol')
    quantity = data.get('quantity')

    if not all([user_id, symbol, quantity]):
        return jsonify({'error': 'Missing data'}), 400

    try:
        user = Users.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        clean_symbol = str(symbol).strip().upper()

        stock = Stock.query.filter(Stock.stock_symbol.ilike(clean_symbol)).first()

        if not stock:
            return jsonify({'error': f'Stock symbol {clean_symbol} not found in database'}), 404

        # NASDAQ ticker
        ticker = yf.Ticker(clean_symbol.upper()+ ".NS")

        info = ticker.info or {}
        live_price = info.get("regularMarketPrice") or info.get("previousClose")

        if live_price is None:
            return jsonify({'error': 'Could not fetch live price'}), 500

        live_price = Decimal(str(live_price))
        quantity = int(quantity)
        total_cost = live_price * quantity

        if user.money < total_cost:
            return jsonify({'error': 'Insufficient funds'}), 400

        portfolio_entry = Portfolio.query.filter_by(userid=user_id, stock_id=stock.stock_id).first()

        if portfolio_entry:
            prev_total_qty = portfolio_entry.totalquantity or 0
            prev_total_inv = portfolio_entry.totalinvested or Decimal("0")

            new_total_qty = prev_total_qty + quantity
            new_total_inv = prev_total_inv + total_cost

            portfolio_entry.totalquantity = new_total_qty
            portfolio_entry.totalinvested = new_total_inv
            portfolio_entry.averagebuyprice = new_total_inv / new_total_qty

        else:
            portfolio_entry = Portfolio(
                userid=user_id,
                stock_id=stock.stock_id,
                stockname=clean_symbol,
                companyname=stock.stock_name,
                totalquantity=quantity,
                totalinvested=total_cost,
                averagebuyprice=live_price
            )

            db.session.add(portfolio_entry)
            db.session.flush()

        user.money = user.money - total_cost

        fifo = FIFOLot(
            userid=user_id,
            portfolioid=portfolio_entry.portfolioid,
            companyname=stock.stock_name,
            quantityremaining=quantity,
            pricepershare=live_price,
            buydate=datetime.utcnow()
        )

        db.session.add(fifo)

        txn = Transactionhistory(
            userid=user_id,
            portfolioid=portfolio_entry.portfolioid,
            companyname=stock.stock_name,
            stockname=clean_symbol,
            quantity=quantity,
            price=live_price,
            transactiontype="BUY",
            timestamp=datetime.utcnow()
        )

        db.session.add(txn)

        watch = Watchlist.query.filter_by(user_id=user_id, stock_id=stock.stock_id).first()
        if watch:
            db.session.delete(watch)

        db.session.commit()

        return jsonify({
            'message': f'{quantity} shares of {clean_symbol} bought!',
            'symbol': clean_symbol,
            'quantity': quantity,
            'price_per_share': str(live_price),
            'total_invested': str(total_cost),
            'new_wallet': float(user.money)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to buy stock: {str(e)}'}), 500
