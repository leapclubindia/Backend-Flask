from flask import Flask, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
import pprint, json
import pandas as pd

app = Flask(__name__)
db = SQLAlchemy(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SECRET_KEY"] = "DontTellAnyone"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# orders table schema
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

# importing order payments data from csv file
@app.route("/import")
def data():
    file_name = 'batch-links2.xlsx'
    excel_data_df = pd.read_excel(file_name)
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
    return json_str

# imported data get in this route
@app.route("/imported_data")
def imported_data():
        order_payments = OrderPayments.query.all()
        return render_template("order_payments.html", payments = order_payments)
