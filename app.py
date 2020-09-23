from flask import Flask, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
import pprint, json, datetime, razorpay, uuid
import pandas as pd
from config import DevelopmentConfig
from datetime import timezone
from sshtunnel import SSHTunnelForwarder
from sqlalchemy.dialects.postgresql import UUID
from custom import list_order_items, get_order_refunds, list_order_refunds, get_int

app = Flask(__name__, instance_relative_config=True)

app.config.from_object(DevelopmentConfig)
app.config.from_pyfile("config.py")

if app.config["SQLALCHEMY_DATABASE_URI"] == "":
    server = SSHTunnelForwarder(
        (app.config["HOST"], 22),
        ssh_username=app.config["SSH_USERNAME"],
        ssh_private_key=app.config["SSH_PRIVATE_KEY"],
        remote_bind_address=("127.0.0.1", app.config["PORT"]),
    )

    server.start()

    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://{}:{}@localhost:{}/{}".format(
        app.config["USER"],
        app.config["PASSWORD"],
        server.local_bind_port,
        app.config["DATABASE"],
    )
db = SQLAlchemy(app)
razorpay_client = razorpay.Client(
    auth=("rzp_test_NbcxeXyisd2EhB", "wKClBRsKbNXl8RIJQQ4CFLkB")
)


# payments table schem
class Payments(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    amount = db.Column(db.Integer)
    created_at = db.Column(db.String)
    currency = db.Column(db.String)
    email = db.Column(db.String)
    fee = db.Column(db.Integer)
    invoice_id = db.Column(db.Integer, db.ForeignKey("payment_links.receipt"))
    phone = db.Column(db.String)
    status = db.Column(db.String)
    tax = db.Column(db.Integer)


class Orders(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("order_items.order_id"),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    order_id = db.Column(db.Integer, unique=True, nullable=False)
    payment_status = db.Column(db.String)
    payment_type = db.Column(db.String)
    amount_paid = db.Column(db.Float)
    total_amount = db.Column(db.Float)
    razorpay_payment_id = db.Column(db.String)
    razorpay_order_id = db.Column(db.String)
    mobile_number = db.Column(db.String)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.utcnow())
    customer_entity_id = db.Column(UUID(as_uuid=True))
    order_items = db.relationship(
        "OrderItems", foreign_keys="OrderItems.order_id", uselist=True
    )
    customer_entity = db.relationship("Entities", uselist=False)
    payment_link = db.relationship(
        "PaymentLinks", foreign_keys="PaymentLinks.receipt", uselist=False
    )


class RefundOrder(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    quantity = db.Column(db.Float)
    order_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("order_items.id"))


class OrderItems(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    price = db.Column(db.Float)
    amount = db.Column(db.Float)
    quantity = db.Column(db.Float)
    order_refund = db.relationship(
        "RefundOrder", foreign_keys="RefundOrder.order_item_id", uselist=False
    )
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("orders.id"))
    product_variant_id = db.Column(UUID(as_uuid=True))
    order = db.relationship("Orders", foreign_keys="Orders.id", uselist=False)
    product_variant = db.relationship(
        "ProductVariants", foreign_keys="ProductVariants.id", uselist=False
    )


class Entities(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("orders.customer_entity_id"),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    entity_name = db.Column(db.String)
    email = db.Column(db.String)


class PaymentLinks(db.Model):
    id = db.Column(db.String, unique=True, nullable=True)
    contact = db.Column(db.String)
    name = db.Column(db.String)
    short_url = db.Column(db.String)
    amount = db.Column(db.Float)
    receipt = db.Column(
        db.Integer, db.ForeignKey("orders.order_id"), unique=True, primary_key=True
    )
    issued_at = db.Column(db.String)
    status = db.Column(db.String)
    payment = db.relationship("Payments", uselist=False)


class ProductVariants(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("order_items.product_variant_id"),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    name = db.Column(db.String)
    price = db.Column(db.Float)
    product_id = db.Column(UUID(as_uuid=True))
    product = db.relationship("Products", uselist=False)


class Products(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("product_variants.product_id"),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    name = db.Column(db.String)


@app.route("/", methods=["GET", "POST"])
def webhooks():
    if request.method == "GET":
        page = request.args.get("page", 1, type=int)
        payments = Payments.query.paginate(page=page, per_page=50)
        return render_template("payments.html", payments=payments)
    else:
        data = request.get_json()
        if data:
            main_obj = data["payload"]["payment"]["entity"]
            if (data["event"] == "invoice.paid") & (
                "receipt" in data["payload"]["order"]["entity"].keys()
            ):
                try:
                    receipt = int(data["payload"]["order"]["entity"]["receipt"])
                    if Orders.query.filter_by(order_id=receipt).count() > 1:
                        return "Error"
                    order = Orders.query.filter_by(order_id=receipt).first()
                    if order != None and order.payment_status != "Paid":
                        order.payment_status = "Paid"
                        order.payment_type = "Online on Delivery"
                        order.amount_paid = main_obj["amount"] / 100
                        order.razorpay_payment_id = main_obj["id"]
                        order.razorpay_order_id = main_obj["order_id"]
                        order.updated_at = datetime.datetime.utcnow()
                        db.session.commit()
                    payment = Payments(
                        invoice_id=receipt,
                        email=main_obj["email"],
                        phone=main_obj["contact"],
                        currency=main_obj["currency"],
                        amount=main_obj["amount"],
                        fee=main_obj["fee"],
                        tax=main_obj["tax"],
                        created_at=main_obj["created_at"],
                        status=main_obj["status"],
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
    orders = Orders.query.order_by(Orders.order_id.desc()).paginate(
        page=page, per_page=50
    )
    payment_links = PaymentLinks.query.all()
    refund_dict = {}
    for o in orders.items:
        total_refunds = 0
        for item in o.order_items:
            if item.order_refund:
                total_refunds = total_refunds + item.price * item.order_refund.quantity
        refund_dict[o.order_id] = total_refunds

    def get_ids(p):
        if p.short_url != None:
            return int(p.receipt)

    payment_links = list(map(get_ids, payment_links))
    return render_template(
        "orders.html", orders=orders, links=payment_links, refund_dict=refund_dict
    )


def gen_payment_link(order_id):
    order = Orders.query.filter_by(order_id=order_id).first()
    customer = Entities.query.filter_by(id=order.customer_entity_id).first()
    total_refunds = 0
    for item in order.order_items:
        if item.order_refund:
            total_refunds = total_refunds + item.price * item.order_refund.quantity
    data = {
        "customer": {
            "name": customer.entity_name,
            "email": customer.email,
            "contact": order.mobile_number,
        },
        "options": {"checkout": {"name": "Leap Club"}},
        "type": "link",
        "receipt": str(order_id),
        "amount": (order.total_amount - total_refunds) * 100,
        "currency": "INR",
        "description": "Thanks for shoppping ",
    }
    try:
        razorpay_payment_link = razorpay_client.invoice.create(data=data)
        payment_link = PaymentLinks(
            id=razorpay_payment_link["id"],
            contact=razorpay_payment_link["customer_details"]["contact"],
            name=razorpay_payment_link["customer_details"]["name"],
            short_url=razorpay_payment_link["short_url"],
            amount=razorpay_payment_link["amount"],
            receipt=razorpay_payment_link["receipt"],
            issued_at=razorpay_payment_link["issued_at"],
            status="Success",
        )
    except:
        payment_link = PaymentLinks(
            id=None,
            contact=order.mobile_number,
            name=customer.entity_name,
            short_url=None,
            amount=(order.total_amount - total_refunds),
            receipt=order_id,
            issued_at=None,
            status="Failled",
        )
    db.session.add(payment_link)
    db.session.commit()
    return True


@app.route("/payment_link", methods=["GET", "POST"])
def payment_link():
    if request.method == "GET":
        page = request.args.get("page", 1, type=int)
        payment_links = PaymentLinks.query.paginate(page=page, per_page=50)
        return render_template("payment_links.html", payment_links=payment_links)
    orders = request.form.to_dict(flat=False)
    total_links = {}
    if orders:
        for o in orders["orders"]:
            gen_payment_link(o)
        return redirect(url_for("payment_link"))
    else:
        return redirect(url_for("orders"))


@app.route("/whatsapp/<int:order_id>")
def whatsapp(order_id):
    order = Orders.query.filter_by(order_id=order_id).first()
    text = "Hi - Your order is on the way.\n\nPlease check whether you are satisfied with the quality of items when you receive them. Feel free to Whatsapp me here if you have any queries.\n\nI hope you will like them. Looking forward to your feedback. :)\n\n\nHere are the order details:\n\n"
    text = text + list_order_items(order.order_items)
    text = (
        text
        + "*Total Amount: "
        + get_int(order.total_amount - get_order_refunds(order.order_items))+"*"
    )
    order_refunds = list_order_refunds(order.order_items)
    if order_refunds:
        text = text + "\n\nWe are not able to send:\n\n" + order_refunds
    return "<textarea style='width: 900px; height: 500px'>" + text + "</textarea>"


if __name__ == "__main__":
    db.create_all()
    app.run()
