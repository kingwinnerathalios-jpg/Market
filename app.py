import os
from decimal import Decimal
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///market.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE_URL = (
    "https://api-m.sandbox.paypal.com"
    if os.getenv("PAYPAL_MODE", "sandbox").lower() == "sandbox"
    else "https://api-m.paypal.com"
)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Handmade")
    stock = db.Column(db.Integer, nullable=False, default=10)

    @property
    def price(self):
        return Decimal(self.price_cents) / Decimal(100)

def money(cents):
    return f"{Decimal(cents) / Decimal(100):.2f}"

app.jinja_env.filters["money"] = money

def cart_items():
    cart = session.get("cart", {})
    result = []
    total = 0
    for product_id, quantity in cart.items():
        product = db.session.get(Product, int(product_id))
        if not product or quantity < 1:
            continue
        quantity = min(int(quantity), product.stock)
        line_total = product.price_cents * quantity
        total += line_total
        result.append({"product": product, "quantity": quantity, "line_total": line_total})
    return result, total

@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    return {"cart_count": sum(int(q) for q in cart.values())}

@app.route("/")
def index():
    products = Product.query.order_by(Product.id).all()
    return render_template("index.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template("product.html", product=product)

@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = db.get_or_404(Product, product_id)
    if product.stock <= 0:
        flash("Dieses Produkt ist leider ausverkauft.", "error")
        return redirect(request.referrer or url_for("index"))
    cart = session.get("cart", {})
    key = str(product_id)
    current = int(cart.get(key, 0))
    if current >= product.stock:
        flash("Du hast bereits den gesamten verfügbaren Bestand im Warenkorb.", "error")
    else:
        cart[key] = current + 1
        session["cart"] = cart
        flash(f"{product.name} wurde zum Warenkorb hinzugefügt.", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart")
def view_cart():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/update")
def update_cart():
    cart = session.get("cart", {})
    for product_id, value in request.form.items():
        try:
            quantity = int(value)
            product = db.session.get(Product, int(product_id))
        except (ValueError, TypeError):
            continue
        if not product:
            cart.pop(product_id, None)
        elif quantity <= 0:
            cart.pop(product_id, None)
        else:
            cart[product_id] = min(quantity, product.stock)
    session["cart"] = cart
    flash("Warenkorb aktualisiert.", "success")
    return redirect(url_for("view_cart"))

def paypal_access_token():
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError("PayPal ist noch nicht konfiguriert. Trage Sandbox-Zugangsdaten in .env ein.")
    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json"},
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]

@app.get("/api/paypal/config")
def paypal_config():
    if not PAYPAL_CLIENT_ID:
        return jsonify({"configured": False}), 503
    return jsonify({"configured": True, "clientId": PAYPAL_CLIENT_ID})

@app.post("/api/paypal/create-order")
def paypal_create_order():
    items, total_cents = cart_items()
    if not items or total_cents <= 0:
        return jsonify({"error": "Dein Warenkorb ist leer."}), 400

    # Re-check stock and calculate the total on the server. Never trust browser prices.
    for item in items:
        if item["quantity"] > item["product"].stock:
            return jsonify({"error": "Ein Produkt ist nicht mehr in ausreichender Menge verfügbar."}), 409

    try:
        token = paypal_access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "EUR",
                    "value": money(total_cents),
                },
                "description": "Handgemachte Produkte",
            }],
            "application_context": {
                "brand_name": "Kleine Manufaktur",
                "shipping_preference": "GET_FROM_FILE",
                "user_action": "PAY_NOW",
            },
        }
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        return jsonify(response.json())
    except (requests.RequestException, RuntimeError) as exc:
        app.logger.exception("PayPal order creation failed")
        return jsonify({"error": "PayPal konnte die Bestellung gerade nicht erstellen."}), 502

@app.post("/api/paypal/capture-order")
def paypal_capture_order():
    data = request.get_json(silent=True) or {}
    order_id = data.get("orderID", "")
    if not order_id or len(order_id) > 100:
        return jsonify({"error": "Ungültige Bestellnummer."}), 400

    try:
        token = paypal_access_token()
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()

        # Only clear the cart and reduce stock after PayPal confirms COMPLETED.
        if result.get("status") == "COMPLETED":
            items, _ = cart_items()
            for item in items:
                product = db.session.get(Product, item["product"].id)
                if product:
                    product.stock = max(0, product.stock - item["quantity"])
            db.session.commit()
            session["cart"] = {}
            session["last_order"] = order_id
            return jsonify({"status": "COMPLETED", "orderID": order_id})
        return jsonify({"status": result.get("status", "UNKNOWN"), "error": "Zahlung wurde noch nicht abgeschlossen."}), 400
    except (requests.RequestException, RuntimeError):
        app.logger.exception("PayPal capture failed")
        return jsonify({"error": "Die Zahlung konnte nicht bestätigt werden. Bitte prüfe dein PayPal-Konto."}), 502

@app.route("/success")
def success():
    order_id = session.pop("last_order", None)
    if not order_id:
        return redirect(url_for("index"))
    return render_template("success.html", order_id=order_id)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

def seed_products():
    if Product.query.count():
        return
    examples = [
        ("Keramikbecher", "Handgefertigter Becher aus Keramik. Jedes Stück ist ein Unikat.", 2490,
         "https://images.unsplash.com/photo-1577937927133-66ef06acdf18?w=900", "Keramik", 8),
        ("Makramee-Wanddeko", "Dekorative Wanddeko, sorgfältig von Hand geknüpft.", 3290,
         "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=900", "Deko", 5),
        ("Ledernotizbuch", "Kleines Notizbuch mit handgefertigtem Einband.", 1890,
         "https://images.unsplash.com/photo-1517842645767-c639042777db?w=900", "Papier", 12),
        ("Duftkerze", "Pflanzenwachskerze im wiederverwendbaren Glas.", 1590,
         "https://images.unsplash.com/photo-1603006905003-be475563bc59?w=900", "Kerzen", 10),
    ]
    for name, description, price, image, category, stock in examples:
        db.session.add(Product(name=name, description=description, price_cents=price,
                               image_url=image, category=category, stock=stock))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_products()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
