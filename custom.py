def get_int(f):
    if f == int(f):
        return str(int(f))
    else:
        return str(f)

def list_order_items(order_items):
    msg = ""
    for order_item in order_items:
        c_quantity = order_item.quantity
        if order_item.order_refund != None:
            c_quantity = order_item.quantity - order_item.order_refund.quantity
        if c_quantity != 0.0:
            msg = (
                msg
                + order_item.product_variant.product.name
                + " ("
                + order_item.product_variant.name
                + ") x "
                + get_int(c_quantity)
                + "\n"
                + "₹"
                + get_int(order_item.price)
                + " x "
                + get_int(c_quantity)
                + " = "
                + get_int(order_item.price * c_quantity)
                + "\n\n"
            )
    return msg

def get_order_refunds(order_items):
    total_refunds = 0
    for item in order_items:
        if item.order_refund:
            total_refunds = total_refunds + item.price * item.order_refund.quantity
    return total_refunds

def list_order_refunds(order_items):
    msg = ""
    for order_item in order_items:
        if order_item.order_refund != None:
            msg = (
                msg
                + order_item.product_variant.product.name
                + " ("
                + order_item.product_variant.name
                + ") x "
                + get_int(order_item.order_refund.quantity)
                + "\n"
                + "₹"
                + get_int(order_item.price)
                + " x "
                + get_int(order_item.order_refund.quantity)
                + " = "
                + get_int(order_item.price * order_item.order_refund.quantity)
                + "\n\n"
            )
    return msg