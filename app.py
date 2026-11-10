import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'ecom.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '')  # Use a default empty string if SECRET_KEY is not set
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')  # Use a default empty string if ADMIN_PASSWORD is not set
app.jinja_env.globals['_'] = lambda s: s  # Support gettext translation tags if used in templates


def get_db():
    if"db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    fast_run = not DB_PATH.exists()
    db = get_db()
    db.executescript(""" 
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        old_price REAL NOT NULL DEFAULT 0,
        description TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        image TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        total_price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        customer_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products (id)
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL,
        phone TEXT NOT NULL,
        password TEXT
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    );
    """)

    # Ensure old_price column exists in products table
    cursor = db.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cursor.fetchall()]
    if "old_price" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN old_price REAL NOT NULL DEFAULT 0")
        db.commit()

    # Ensure quantity column exists in products table
    if "quantity" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0")
        db.commit()

    # Ensure password column exists in customers table
    cursor = db.execute("PRAGMA table_info(customers)")
    customer_cols = [row[1] for row in cursor.fetchall()]
    if "password" not in customer_cols:
        db.execute("ALTER TABLE customers ADD COLUMN password TEXT")
        db.commit()

    # Ensure customer_id column exists in orders table
    cursor = db.execute("PRAGMA table_info(orders)")
    order_cols = [row[1] for row in cursor.fetchall()]
    if "customer_id" not in order_cols:
        db.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
        db.commit()

    # Insert sample products if table is empty
    count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        sample_products = [
            ("Product 1", 19.99, 29.99, 0, "Description for Product 1", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80"),
            ("Product 2", 29.99, 39.99, 0, "Description for Product 2", "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80"),
            ("Product 3", 39.99, 49.99, 0, "Description for Product 3", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop&q=80"),
        ]
        db.executemany(
            "INSERT INTO products (name, price, old_price, quantity, description, image) VALUES (?, ?, ?, ?, ?, ?)",
            sample_products
        )
        db.commit()

if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY is not set in the environment variables.")

if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD is not set in the environment variables.")

@app.route('/')
def index():
    products = get_db().execute("SELECT * FROM products").fetchall()
    return render_template('index.html', products=products)

@app.route('/products')
def products():
    products = get_db().execute("SELECT * FROM products").fetchall()
    return render_template('products.html', products=products)

@app.route('/product-detail/<product_id>')
def product_detail(product_id):
    product = get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        return "Product not found", 404
    return render_template('product-detail.html', product=product)

def get_cart_items():
    items = []
    for product_id, quantity in session.get('cart', {}).items():
        product = get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product and quantity > 0:
            item = dict(product)
            item['quantity'] = min(quantity, 99)
            item["subtotal"] = item['quantity'] * item['price']
            items.append(item)
    return items

@app.route('/cart')
def cart():
    items = get_cart_items()
    subtotal = sum(item['subtotal'] for item in items)
    shipping = 10.0 if items else 0.0
    grand_total = subtotal + shipping
    return render_template('cart.html', cart_items=items, subtotal=subtotal, shipping=shipping, grand_total=grand_total)

@app.route('/cart/update/<product_id>', methods=['POST'])
def update_cart(product_id):
    try:
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1

    cart = session.get('cart', {})
    key = str(product_id)
    if quantity > 0:
        cart[key] = min(quantity, 99)
    else:
        cart.pop(key, None)
    session['cart'] = cart
    session.modified = True
    flash("Cart updated successfully.", "info")
    return redirect(url_for('cart'))

@app.route('/cart/remove/<product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    key = str(product_id)
    cart.pop(key, None)
    if key.isdigit():
        cart.pop(int(key), None)
    session['cart'] = cart
    session.modified = True
    flash("Item removed from cart.", "info")
    return redirect(url_for('cart'))

@app.route('/cart/clear', methods=['POST'])
def clear_cart():
    session['cart'] = {}
    session.modified = True
    flash("Cart cleared.", "info")
    return redirect(url_for('cart'))

@app.context_processor
def shared_template_values():
    def csrf_token():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(16)
        return session['_csrf_token']
    
    current_customer = None
    customer_id = session.get('customer_id') or session.get('user_id')
    if customer_id:
        current_customer = get_db().execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    cart_count = sum(session.get('cart', {}).values())
    return {
        'csrf_token': csrf_token,
        'cart_count': cart_count,
        'cart_items': get_cart_items,
        'current_customer': current_customer
    }

@app.before_request
def csrf_protect():
    if request.method == "POST":
        expected = session.get('_csrf_token', None)
        supplied = request.form.get('csrf_token', None)
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(403, description="CSRF token missing or incorrect.")

@app.route('/add-to-cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        return "Product not found", 404

    try:
        qty = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        qty = 1

    cart = session.get('cart', {})
    key = str(product_id)
    current_quantity = cart.get(key, 0)
    new_quantity = min(current_quantity + max(1, qty), 99)
    cart[key] = new_quantity
    session['cart'] = cart
    session.modified = True
    flash(f"Added {product['name']} to cart.", "success")
    return redirect(request.referrer or url_for('index'))

# ==========================================
# CUSTOMER AUTHENTICATION ROUTES
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if session.get('customer_id'):
        flash("You are already logged in.", "info")
        return redirect(url_for('index'))

    next_url = request.args.get('next') or request.form.get('next')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('customer/login.html', next_url=next_url)

        db = get_db()
        customer = db.execute("SELECT * FROM customers WHERE LOWER(email) = ?", (email,)).fetchone()

        if customer and customer['password'] and check_password_hash(customer['password'], password):
            session['customer_id'] = customer['id']
            session['customer_name'] = customer['name']
            session.modified = True
            flash(f"Welcome back, {customer['name']}!", "success")
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('checkout') if session.get('cart') else url_for('index'))
        else:
            flash("Invalid email or password. Please try again or create an account.", "danger")

    return render_template('customer/login.html', next_url=next_url)

@app.route('/register', methods=['GET', 'POST'])
@app.route('/customer/register', methods=['GET', 'POST'])
def customer_register():
    if session.get('customer_id'):
        flash("You are already logged in.", "info")
        return redirect(url_for('index'))

    next_url = request.args.get('next') or request.form.get('next')
    form_data = {}

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        form_data = {'name': name, 'email': email, 'phone': phone, 'address': address}

        if not all([name, email, phone, address, password, confirm_password]):
            flash("Please fill in all required fields.", "danger")
            return render_template('customer/register.html', next_url=next_url, form_data=form_data)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('customer/register.html', next_url=next_url, form_data=form_data)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('customer/register.html', next_url=next_url, form_data=form_data)

        if not (1 <= len(phone) <= 15 and phone.isdigit() and "@" in email):
            flash("Please enter a valid email and phone number.", "danger")
            return render_template('customer/register.html', next_url=next_url, form_data=form_data)

        db = get_db()
        existing = db.execute("SELECT id FROM customers WHERE LOWER(email) = ?", (email,)).fetchone()
        if existing:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('customer_login', next=next_url))

        hashed_pw = generate_password_hash(password)
        cursor = db.execute(
            "INSERT INTO customers (name, email, phone, address, password) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, address, hashed_pw)
        )
        db.commit()

        customer_id = cursor.lastrowid
        session['customer_id'] = customer_id
        session['customer_name'] = name
        session.modified = True

        flash("Account created successfully! Welcome to SwiftCart.", "success")
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('checkout') if session.get('cart') else url_for('index'))

    return render_template('customer/register.html', next_url=next_url, form_data=form_data)

@app.route('/logout')
@app.route('/customer/logout')
def customer_logout():
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    session.pop('customer', None)
    session.modified = True
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('index'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty. Please add items to your cart before checking out.", "warning")
        return redirect(url_for('cart'))
    subtotal = sum(item['subtotal'] for item in items)
    shipping = 10.0 if items else 0.0
    grand_total = subtotal + shipping

    db = get_db()
    customer = None
    customer_id = session.get('customer_id') or session.get('user_id')
    if customer_id:
        customer = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        name = request.form.get('full_name', '').strip() or request.form.get('name', '').strip() or f"{first_name} {last_name}".strip()
        email = request.form.get('email', '').strip().lower()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if city and city not in address:
            shipping_address = f"{address}, {city}"
        else:
            shipping_address = address

        if not all([name, email, shipping_address, phone]):
            flash("Please fill in all required shipping and contact fields.", "danger")
            return redirect(url_for('checkout'))

        if not (1 <= len(phone) <= 15 and phone.isdigit() and len(email) <= 255 and "@" in email):
            flash("Please enter a valid email address and phone number.", "danger")
            return redirect(url_for('checkout'))

        # Customer Registration / Authentication Handling:
        if customer:
            customer_id = customer['id']
            db.execute(
                "UPDATE customers SET name = ?, address = ?, phone = ? WHERE id = ?",
                (name, shipping_address, phone, customer_id)
            )
        else:
            existing = db.execute("SELECT * FROM customers WHERE LOWER(email) = ?", (email,)).fetchone()
            if existing:
                if existing['password']:
                    if not password or not check_password_hash(existing['password'], password):
                        flash("This email is already registered. Please provide your correct password or log in first.", "danger")
                        return redirect(url_for('checkout'))
                customer_id = existing['id']
                session['customer_id'] = customer_id
                session['customer_name'] = existing['name']
                session.modified = True
                db.execute(
                    "UPDATE customers SET name = ?, address = ?, phone = ? WHERE id = ?",
                    (name, shipping_address, phone, customer_id)
                )
            else:
                # Register new customer directly on checkout page
                if not password or len(password) < 6:
                    flash("Please provide a password of at least 6 characters to create your account during checkout.", "danger")
                    return redirect(url_for('checkout'))

                hashed_pw = generate_password_hash(password)
                cursor = db.execute(
                    "INSERT INTO customers (name, email, address, phone, password) VALUES (?, ?, ?, ?, ?)",
                    (name, email, shipping_address, phone, hashed_pw)
                )
                customer_id = cursor.lastrowid
                session['customer_id'] = customer_id
                session['customer_name'] = name
                session.modified = True

        # Save order items linked to customer_id
        for item in items:
            db.execute(
                "INSERT INTO orders (product_id, quantity, total_price, status, customer_id) VALUES (?, ?, ?, ?, ?)",
                (item['id'], item['quantity'], item['subtotal'], 'Pending', customer_id)
            )

        db.commit()

        order_id = secrets.randbelow(900000) + 100000
        session['cart'] = {}
        flash("Order placed successfully!", "success")
        return redirect(url_for('order_success', order_id=order_id))

    return render_template(
        'checkout.html',
        items=items,
        subtotal=subtotal,
        shipping=shipping,
        grand_total=grand_total,
        customer=customer
    )

@app.route('/order-success')
@app.route('/order-success/<order_id>')
def order_success(order_id=None):
    order_id = order_id or request.args.get('order_id', '894102')
    return render_template('order-success.html', order_id=order_id)

# ==========================================
# ADMIN AUTH & MANAGEMENT ROUTES
# ==========================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Please log in to access the admin area.", "warning")
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    next_url = request.args.get('next') or request.form.get('next')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        is_authenticated = False
        if ADMIN_PASSWORD and secrets.compare_digest(password, ADMIN_PASSWORD):
            is_authenticated = True
        else:
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password)
            ).fetchone()
            if user:
                is_authenticated = True

        if is_authenticated:
            session['is_admin'] = True
            session.modified = True
            flash("Welcome to the Admin Dashboard!", "success")
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('admin/login.html', next_url=next_url)

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.modified = True
    flash("You have been logged out of the admin panel.", "info")
    return redirect(url_for('admin_login'))

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    total_revenue_row = db.execute("SELECT COALESCE(SUM(total_price), 0) FROM orders").fetchone()
    total_revenue = total_revenue_row[0] if total_revenue_row else 0.0

    total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_customers = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    recent_orders = db.execute("""
        SELECT o.id, o.product_id, o.quantity, o.total_price, o.status,
               p.name AS product_name, p.image AS product_image
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        ORDER BY o.id DESC
        LIMIT 6
    """).fetchall()

    return render_template(
        'admin/dashboard.html',
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_products=total_products,
        total_customers=total_customers,
        recent_orders=recent_orders
    )

@app.route('/admin/products')
@admin_required
def admin_products():
    products = get_db().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        old_price = request.form.get('old_price', '').strip()
        quantity = request.form.get('quantity', '').strip()
        image = request.form.get('image', '').strip()
        description = request.form.get('description', '').strip()

        if not name or not price or not description or not image:
            flash("Please fill in all required fields.", "danger")
            return render_template('admin/product_form.html', product=None)

        try:
            price_val = float(price)
            old_price_val = float(old_price) if old_price else 0.0
            qty_val = int(quantity) if quantity else 0
        except ValueError:
            flash("Price and stock quantity must be valid numbers.", "danger")
            return render_template('admin/product_form.html', product=None)

        db = get_db()
        db.execute(
            "INSERT INTO products (name, price, old_price, quantity, description, image) VALUES (?, ?, ?, ?, ?, ?)",
            (name, price_val, old_price_val, qty_val, description, image)
        )
        db.commit()
        flash(f"Product '{name}' was created successfully!", "success")
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', product=None)

@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        abort(404, description="Product not found")

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        old_price = request.form.get('old_price', '').strip()
        quantity = request.form.get('quantity', '').strip()
        image = request.form.get('image', '').strip()
        description = request.form.get('description', '').strip()

        if not name or not price or not description or not image:
            flash("Please fill in all required fields.", "danger")
            return render_template('admin/product_form.html', product=product)

        try:
            price_val = float(price)
            old_price_val = float(old_price) if old_price else 0.0
            qty_val = int(quantity) if quantity else 0
        except ValueError:
            flash("Price and stock quantity must be valid numbers.", "danger")
            return render_template('admin/product_form.html', product=product)

        db.execute(
            "UPDATE products SET name = ?, price = ?, old_price = ?, quantity = ?, description = ?, image = ? WHERE id = ?",
            (name, price_val, old_price_val, qty_val, description, image, product_id)
        )
        db.commit()
        flash(f"Product '{name}' updated successfully!", "success")
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', product=product)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    db = get_db()
    product = db.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
    if product:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()
        flash(f"Product '{product['name']}' was deleted.", "info")
    else:
        flash("Product not found.", "warning")
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = get_db().execute("""
        SELECT o.id, o.product_id, o.quantity, o.total_price, o.status, o.customer_id,
               p.name AS product_name, p.image AS product_image, p.price AS product_price,
               c.name AS customer_name, c.email AS customer_email, c.phone AS customer_phone
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        LEFT JOIN customers c ON o.customer_id = c.id
        ORDER BY o.id DESC
    """).fetchall()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/orders/update-status/<int:order_id>', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get('status', '').strip()
    valid_statuses = ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
    if new_status in valid_statuses:
        db = get_db()
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        db.commit()
        flash(f"Order #ORD-{order_id} status updated to {new_status}.", "success")
    else:
        flash("Invalid order status.", "danger")
    return redirect(url_for('admin_orders'))

@app.route('/admin/customers')
@admin_required
def admin_customers():
    customers = get_db().execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return render_template('admin/customers.html', customers=customers)

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)