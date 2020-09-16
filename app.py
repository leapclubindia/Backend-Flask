from flask import Flask, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
import pprint, json, datetime
import pandas as pd
from config import DevelopmentConfig
from datetime import timezone
from sshtunnel import SSHTunnelForwarder

app = Flask(__name__, instance_relative_config=True)

app.config.from_object(DevelopmentConfig)
app.config.from_pyfile('config.py')

if app.config['SQLALCHEMY_DATABASE_URI'] == '':
    server = SSHTunnelForwarder(
              (app.config['HOST'], 22),
              ssh_username=app.config['SSH_USERNAME'],
              ssh_private_key= app.config['SSH_PRIVATE_KEY'],
              remote_bind_address=('127.0.0.1', app.config['PORT']))

    server.start()

    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{}:{}@localhost:{}/{}'.format(app.config['USER'],
                                                                           app.config['PASSWORD'],
                                                                           server.local_bind_port,
                                                                           app.config['DATABASE'])
db = SQLAlchemy(app)

# payments table schem
class Payments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    created_at = db.Column(db.String)
    currency = db.Column(db.String)
    email = db.Column(db.String)
    fee = db.Column(db.Integer)
    invoice_id = db.Column(db.String)
    phone = db.Column(db.String)
    status = db.Column(db.String)
    tax = db.Column(db.Integer)

class Orders(db.Model):
    order_id = db.Column(db.Integer, primary_key=True)
    payment_status = db.Column(db.String)
    payment_type = db.Column(db.String)
    amount_paid = db.Column(db.Float)
    total_amount = db.Column(db.Float)
    razorpay_payment_id = db.Column(db.String)
    razorpay_order_id = db.Column(db.String)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.utcnow())

@app.route("/", methods=["GET", "POST"])
def webhooks():
    if request.method == "GET":
        page = request.args.get("page", 1, type=int)
        payments = Payments.query.paginate(page = page, per_page=50)
        return render_template("payments.html", payments = payments)
    else:
        data = request.get_json()
        if data:
            main_obj = data["payload"]["payment"]["entity"]
            if (data["event"] == "invoice.paid") & ('receipt' in  data['payload']['order']['entity'].keys()):
                try:
                    receipt = int(data['payload']['order']['entity']['receipt'])
                    if (Orders.query.filter_by(order_id=receipt).count()>1):
                        return "Error"
                    order = Orders.query.filter_by(order_id=receipt).first()
                    if order != None and order.payment_status != "Paid":
                        order.payment_status = "Paid"
                        order.payment_type = "Online on Delivery"
                        order.amount_paid = (main_obj["amount"]/100)
                        order.razorpay_payment_id = main_obj["id"]
                        order.razorpay_order_id = main_obj["order_id"]
                        order.updated_at = datetime.datetime.utcnow()
                        db.session.commit()
                    payment = Payments(
                    invoice_id = receipt,
                    email = main_obj["email"],
                    phone = main_obj["contact"],
                    currency = main_obj["currency"],
                    amount = main_obj["amount"],
                    fee = main_obj["fee"],
                    tax = main_obj["tax"],
                    created_at = main_obj["created_at"],
                    status = main_obj["status"]
                )
                    db.session.add(payment)
                    db.session.commit()
                except:
                    return "Error"
            return main_obj
        else:
            return {"Please Send some data."}

@app.route("/orders")
def orders():
    page = request.args.get("page", 1, type=int)
    orders =Orders.query.order_by(Orders.order_id.desc()).paginate(page = page, per_page=50)
    return render_template("orders.html", orders = orders)

if __name__ == "__main__":
    db.create_all()
    app.run()
