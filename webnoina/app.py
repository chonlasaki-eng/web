from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask import flash
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

import qrcode, base64

# 🔥 QR
import qrcode
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super-secret-key"

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# 👇 วาง admin_required ตรงนี้เลย
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            return "Access Denied", 403
        return f(*args, **kwargs)
    return wrapper    

# ================= IMAGE FOLDER =================
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= PRODUCTS =================




# ================= AUTH =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            return "กรอกข้อมูลไม่ครบ"
        hash_pw = generate_password_hash(password)
        db = get_db()
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_pw)
        )
        db.commit()
        db.close()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            # 🔥 ถ้าเป็น admin ให้เข้า dashboard เลย
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("index"))

        # ❌ ถ้า login ไม่สำเร็จ
        flash("Username หรือ Password ไม่ถูกต้อง")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")




@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route("/admin/products")
@admin_required
def admin_products():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin/products.html", products=products)



@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        category = request.form["category"]
        description = request.form["description"]
        image_url = request.form["image_url"]

        db = get_db()
        db.execute(
            "INSERT INTO products (name, price, category, description, image_url) VALUES (?, ?, ?, ?, ?)",
            (name, price, category, description, image_url)
        )
        db.commit()

        return redirect(url_for("admin_products"))

    return render_template("admin/add_product.html")


@app.route("/admin/products/delete/<int:id>")
@admin_required
def delete_product(id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (id,))
    db.commit()

    return redirect(url_for("admin_products"))


@app.route("/admin/products/edit/<int:id>", methods=["GET","POST"])
@admin_required
def edit_product(id):
    db = get_db()

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        category = request.form["category"]
        description = request.form["description"]
        image_url = request.form["image_url"]

        db.execute("""
            UPDATE products
            SET name=?, price=?, category=?, description=?, image_url=?
            WHERE id=?
        """,(name,price,category,description,image_url,id))

        db.commit()

        return redirect(url_for("admin_products"))

    product = db.execute(
        "SELECT * FROM products WHERE id=?",
        (id,)
    ).fetchone()

    return render_template("admin/edit_product.html", product=product)







# ================= STORE =================
@app.route('/')
def index():
    category = request.args.get('category', 'ทั้งหมด')
    db = get_db()

    if category == 'ทั้งหมด':
        products = db.execute("SELECT * FROM products").fetchall()
    else:
        products = db.execute(
            "SELECT * FROM products WHERE category = ?",
            (category,)
        ).fetchall()

    # 🔥 ดึงหมวดหมู่จาก DB แทน
    category_rows = db.execute(
        "SELECT DISTINCT category FROM products"
    ).fetchall()

    db.close()

    categories = ['ทั้งหมด'] + [row['category'] for row in category_rows]

    return render_template(
        'index.html',
        products=products,
        categories=categories,
        current_category=category,
        cart_count=len(session.get('cart', []))
    )


@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    data = request.get_json()
    product_id = int(data.get('product_id'))

    cart = session.get('cart', [])
    cart = [item for item in cart if item['product_id'] != product_id]

    session['cart'] = cart
    return jsonify(success=True)



@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = int(data.get('product_id'))

    cart = session.get('cart', [])

    found = False
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += 1
            found = True
            break

    if not found:
        cart.append({
            'product_id': product_id,
            'quantity': 1
        })

    session['cart'] = cart
    session.modified = True

    # ✅ คำนวณจำนวนรวม
    cart_count = sum(item['quantity'] for item in cart)

    return jsonify(success=True, cart_count=cart_count)


@app.route('/api/cart/increase', methods=['POST'])
def increase_quantity():
    data = request.get_json()
    product_id = data.get('product_id')

    cart = session.get('cart', [])

    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += 1
            break

    session['cart'] = cart
    return jsonify({'message': 'Increased'})

@app.route('/api/cart/decrease', methods=['POST'])
def decrease_quantity():
    data = request.get_json()
    product_id = data.get('product_id')

    cart = session.get('cart', [])

    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] -= 1
            if item['quantity'] <= 0:
                cart.remove(item)
            break

    session['cart'] = cart
    return jsonify({'message': 'Decreased'})    


@app.route('/cart')
def cart():
    cart = session.get('cart', [])
    cart_items = []
    db = get_db()

    for item in cart:
        product = db.execute(
            "SELECT * FROM products WHERE id = ?",
            (item['product_id'],)
        ).fetchone()

        if product:
            quantity = item['quantity']
            total_price = product['price'] * quantity

            cart_items.append({
                **dict(product),
                'quantity': quantity,
                'total': total_price
            })

    db.close()

    subtotal = sum(i['total'] for i in cart_items)
    shipping = 50 if subtotal > 0 else 0
    total = subtotal + shipping

    return render_template(
        'cart.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total
    )




@app.route('/checkout')
@login_required
def checkout():
    cart = session.get('cart', [])
    cart_items = []
    db = get_db()

    for item in cart:
        product = db.execute(
            "SELECT * FROM products WHERE id = ?",
            (item['product_id'],)
        ).fetchone()

        if product:
            quantity = item['quantity']
            total_price = product['price'] * quantity

            cart_items.append({
                **dict(product),
                'quantity': quantity,
                'total': total_price
            })

    db.close()

    subtotal = sum(i['total'] for i in cart_items)
    shipping = 50 if subtotal > 0 else 0
    total = subtotal + shipping

    return render_template(
        'checkout.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total
    )

@app.route('/api/order/place', methods=['POST'])
@login_required
def place_order():

    data = request.get_json()

    if not data:
        return jsonify(success=False, message="No data")

    payment_method = data.get("payment_method", "cod")
    name = data.get("name")
    phone = data.get("phone")
    address = data.get("address")

    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    cart = session.get("cart", [])
    db = get_db()

    if not cart:
        return jsonify(success=False, message="Cart empty")

    total = 0

    # 🔹 คำนวณราคา
    for item in cart:
        product = db.execute(
            "SELECT * FROM products WHERE id=?",
            (item["product_id"],)
        ).fetchone()

        if product:
            total += product["price"] * item["quantity"]

    shipping = 50 if total > 0 else 0
    total = total + shipping

    # 🔹 บันทึก ORDER
    db.execute(
        """
        INSERT INTO orders
        (order_id, user_id, name, phone, address, total, payment_method, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            session["user_id"],
            name,
            phone,
            address,
            total,
            payment_method,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    # 🔹 บันทึกสินค้าใน ORDER
    for item in cart:

        product = db.execute(
            "SELECT * FROM products WHERE id=?",
            (item["product_id"],)
        ).fetchone()

        if not product:
            continue

        db.execute(
            """
            INSERT INTO order_items
            (order_id, product_id, name, price, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order_id,
                product["id"],
                product["name"],
                product["price"],
                item["quantity"]
            )
        )

    db.commit()

    # ================= PROMPTPAY =================
    if payment_method == "bank":

        promptpay_number = "0999999999"

        payload = f"PROMPTPAY:{promptpay_number}|ORDER:{order_id}"

        qr = qrcode.make(payload)

        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        session["cart"] = []
        session.modified = True

        return jsonify(
            success=True,
            payment_method="bank",
            order_id=order_id,
            qr_data=qr_base64
        )

    # ================= COD =================

    session["cart"] = []
    session.modified = True

    return jsonify(
        success=True,
        payment_method="cod",
        redirect_url=f"/success/{order_id}"
    )


@app.route("/order/delete/<order_id>")
@login_required
def delete_order(order_id):

    db = get_db()

    # ลบสินค้าใน order ก่อน
    db.execute(
        "DELETE FROM order_items WHERE order_id=?",
        (order_id,)
    )

    # ลบ order
    db.execute(
        "DELETE FROM orders WHERE order_id=? AND user_id=?",
        (order_id, session["user_id"])
    )

    db.commit()

    return redirect(url_for("orders"))



#order history
@app.route("/orders")
@login_required
def orders():

    db = get_db()

    orders = db.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    order_list = []

    for order in orders:

        items = db.execute("""
            SELECT oi.*, p.image_url
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """,(order["order_id"],)).fetchall()

        order_list.append({
            "order": order,
            "items": items
        })

    return render_template("orders.html", orders=order_list)


@app.route('/success/<order_id>')
@login_required
def order_success(order_id):
    return render_template("success.html", order_id=order_id)

# ================= RUN =================
if __name__ == '__main__':
    
    app.run(debug=True, host='localhost', port=5000)