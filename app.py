from flask import Flask, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
import pprint, json, datetime
import pandas as pd
from config import DevelopmentConfig

app = Flask(__name__)
db = SQLAlchemy(app)

app.config.from_object(DevelopmentConfig)

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

# orderpayment table schema
class OrderPayments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number= db.Column(db.Integer)
    customer_name= db.Column(db.String)
    customer_email= db.Column(db.String)
    customer_contact= db.Column(db.String)
    amount= db.Column(db.Integer)
    description= db.Column(db.String)
    expire_by= db.Column(db.String)
    partial_payment= db.Column(db.Integer)
    status= db.Column(db.String)
    payment_link_id= db.Column(db.String)
    payment_link_short_URL= db.Column(db.String)
    error_description= db.Column(db.String)
    payment_status= db.Column(db.String)
    payment_date= db.Column(db.String)

class Orders(db.Model):
    order_id = db.Column(db.String, primary_key=True)
    payment_status = db.Column(db.String)
    amount_paid = db.Column(db.String)
    razorpay_payment_id = db.Column(db.String)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now())


# main route for home page
@app.route("/", methods=["GET", "POST"])
def webhooks():
    if request.method == "GET":
        payments = Payments.query.all()
        return render_template("payments.html", payments = payments)
    else:
        data = request.get_json()
        if data:
            main_obj = data["payload"]["payment"]["entity"]
            if main_obj["status"] == "captured":
                payment_db = OrderPayments.query.filter_by(payment_link_id=main_obj["invoice_id"]).first()
                if payment_db != None:
                    payment_db.payment_status = "Paid"
                    payment_db.payment_date = data["created_at"]
                    order = Orders.query.filter_by(order_id=payment_db.invoice_number).first()
                    if order != None:
                        order.payment_status = "Paid"
                        order.amount_paid = main_obj["amount"]
                        order.razorpay_payment_id = main_obj["invoice_id"]
                        order.updated_at = datetime.datetime.now()
                    db.session.commit()
            payment = Payments(
                invoice_id = main_obj["invoice_id"],
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
            return main_obj
        else:
            return {error: "Please Send some data."}

# imported data get in this route
@app.route("/imported_data")
def imported_data():
        order_payments = OrderPayments.query.all()
        return render_template("order_payments.html", payments = order_payments)


@app.route("/upload_csv", methods=["GET", "POST"])
def upload_csv():
    if request.method == "GET":
        return render_template("upload_form.html")
    file = request.files["csv_file"]
    excel_data_df = pd.read_excel(file)
    json_str = excel_data_df.to_json(orient='records')
    data = json.loads(json_str)
    for p in data:
        print(p)
        new_payment = OrderPayments(
            invoice_number=p["Invoice Number"],
            customer_name=p["Customer Name"],
            customer_email=p["Customer Email"],
            customer_contact=p["Customer Contact"],
            amount=p["Amount (In Paise)"],
            description=p["Description"],
            expire_by=p["Expire By"],
            partial_payment=p["Partial Payment"],
            status=p["Status"],
            payment_link_id=p["Payment Link Id"],
            payment_link_short_URL=p["Payment Link Short URL"],
            error_description=p["Error description"],
        )
        db.session.add(new_payment)
        db.session.commit()
    return redirect(url_for("imported_data"))