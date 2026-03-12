from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import os
import hashlib
import json
from datetime import datetime
from werkzeug.utils import secure_filename

try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    RAZORPAY_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'farmkart_secret_key_2024'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

RAZORPAY_KEY_ID = 'rzp_test_SPZ8xj6PqHyZ89'
RAZORPAY_KEY_SECRET = '9mLMC4y2FP6Jhyt4V2nGLTf0'

DB_PATH = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image TEXT DEFAULT 'default.jpg',
            category TEXT DEFAULT 'vegetables',
            unit TEXT DEFAULT 'kg',
            stock INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            total_amount REAL NOT NULL,
            payment_id TEXT,
            razorpay_order_id TEXT,
            status TEXT DEFAULT 'pending',
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    ''')

    admin_pwd = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
              ('admin', 'admin@farmkart.com', admin_pwd, 'admin'))

    products = [
        ('Fresh Tomatoes', 40, 'Organically grown red tomatoes, freshly harvested from the farm.', 'tomatoes.jpg', 'vegetables', 'kg'),
        ('Green Spinach', 25, 'Tender baby spinach leaves, rich in iron and vitamins.', 'spinach.jpg', 'vegetables', 'bunch'),
        ('Organic Carrots', 55, 'Sweet crunchy carrots grown without pesticides.', 'carrots.jpg', 'vegetables', 'kg'),
        ('Farm Eggs', 90, 'Free-range chicken eggs, pack of 12.', 'eggs.jpg', 'dairy', 'dozen'),
        ('Fresh Milk', 60, 'Pure cow milk delivered fresh daily from our dairy farm.', 'milk.jpg', 'dairy', 'liter'),
        ('Basmati Rice', 120, 'Premium quality long-grain basmati rice.', 'rice.jpg', 'grains', 'kg'),
        ('Wheat Flour', 45, 'Stone-ground whole wheat flour, freshly milled.', 'wheat.jpg', 'grains', 'kg'),
        ('Alphonso Mangoes', 350, 'King of mangoes – sweet, juicy Alphonso from Ratnagiri.', 'mango.jpg', 'fruits', 'dozen'),
        ('Organic Honey', 280, 'Raw, unprocessed wildflower honey from hill forests.', 'honey.jpg', 'others', '500g'),
        ('Green Chillies', 20, 'Fresh spicy green chillies, perfect for cooking.', 'chilli.jpg', 'vegetables', '250g'),
        ('Onions', 35, 'Fresh onions – a kitchen staple grown on our fields.', 'onion.jpg', 'vegetables', 'kg'),
        ('Potatoes', 30, 'Farm fresh potatoes, versatile and nutritious.', 'potato.jpg', 'vegetables', 'kg'),
    ]
    c.executemany("INSERT OR IGNORE INTO products (name, price, description, image, category, unit) VALUES (?,?,?,?,?,?)", products)

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC LIMIT 8').fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM products').fetchall()
    conn.close()
    return render_template('index.html', products=products, categories=categories)

@app.route('/products')
def products():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    conn = get_db()
    if category:
        prods = conn.execute('SELECT * FROM products WHERE category = ?', (category,)).fetchall()
    elif search:
        prods = conn.execute("SELECT * FROM products WHERE name LIKE ? OR description LIKE ?",
                             (f'%{search}%', f'%{search}%')).fetchall()
    else:
        prods = conn.execute('SELECT * FROM products').fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM products').fetchall()
    conn.close()
    return render_template('products.html', products=prods, categories=categories, selected=category, search=search)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = hash_password(request.form['password'])
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── USER ROUTES ───────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def user_dashboard():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    cart_count = conn.execute('SELECT SUM(quantity) FROM cart WHERE user_id = ?', (session['user_id'],)).fetchone()[0] or 0
    recent_orders = conn.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC LIMIT 3', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user/dashboard.html', products=products, cart_count=cart_count, recent_orders=recent_orders)

@app.route('/cart')
@login_required
def cart():
    conn = get_db()
    items = conn.execute('''
        SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image, p.unit
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    total = sum(i['price'] * i['quantity'] for i in items)
    conn.close()
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    conn = get_db()
    existing = conn.execute('SELECT * FROM cart WHERE user_id = ? AND product_id = ?',
                            (session['user_id'], product_id)).fetchone()
    if existing:
        conn.execute('UPDATE cart SET quantity = quantity + ? WHERE id = ?', (quantity, existing['id']))
    else:
        conn.execute('INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)',
                     (session['user_id'], product_id, quantity))
    conn.commit()
    conn.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('Added to cart!', 'success')
    return redirect(request.referrer or url_for('cart'))

@app.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    cart_id = request.form.get('cart_id')
    quantity = int(request.form.get('quantity', 1))
    conn = get_db()
    if quantity <= 0:
        conn.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, session['user_id']))
    else:
        conn.execute('UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?',
                     (quantity, cart_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    conn = get_db()
    conn.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_db()
    items = conn.execute('''
        SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image, p.unit
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))
    total = sum(i['price'] * i['quantity'] for i in items)
    return render_template('checkout.html', items=items, total=total, razorpay_key=RAZORPAY_KEY_ID)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.json
    address = data.get('address')
    conn = get_db()
    items = conn.execute('''
        SELECT c.quantity, p.id as product_id, p.price
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    total = sum(i['price'] * i['quantity'] for i in items)
    conn.close()

    razorpay_order_id = None
    if RAZORPAY_AVAILABLE and not RAZORPAY_KEY_ID.endswith('YourKeyHere'):
        try:
            rz_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            rz_order = rz_client.order.create({
                'amount': int(total * 100),
                'currency': 'INR',
                'payment_capture': 1
            })
            razorpay_order_id = rz_order['id']
        except Exception as e:
            print(f"Razorpay order creation failed: {e}")
            razorpay_order_id = f"order_fallback_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    else:
        razorpay_order_id = f"order_mock_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    session['pending_order'] = {
        'address': address,
        'total': total,
        'razorpay_order_id': razorpay_order_id
    }

    return jsonify({
        'order_id': razorpay_order_id,
        'amount': int(total * 100),
        'currency': 'INR',
        'key': RAZORPAY_KEY_ID
    })

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    data = request.json
    payment_id = data.get('payment_id', 'demo_payment_' + datetime.now().strftime('%Y%m%d%H%M%S'))
    pending = session.get('pending_order', {})
    address = pending.get('address', data.get('address', ''))
    conn = get_db()
    items = conn.execute('''
        SELECT c.quantity, p.id as product_id, p.price
        FROM cart c JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    total = sum(i['price'] * i['quantity'] for i in items)

    is_cod = payment_id.startswith('cod_') or data.get('is_cod', False)
    order_status = 'pending' if is_cod else 'paid'

    cursor = conn.execute('''
        INSERT INTO orders (user_id, address, total_amount, payment_id, razorpay_order_id, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], address, total, payment_id, pending.get('razorpay_order_id', ''), order_status))
    order_id = cursor.lastrowid

    for item in items:
        conn.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                     (order_id, item['product_id'], item['quantity'], item['price']))

    conn.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    session.pop('pending_order', None)
    return jsonify({'success': True, 'order_id': order_id})

@app.route('/order-success/<int:order_id>')
@login_required
def order_success(order_id):
    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?',
                         (order_id, session['user_id'])).fetchone()
    items = conn.execute('''
        SELECT oi.quantity, oi.price, p.name, p.image
        FROM order_items oi JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    conn.close()
    return render_template('order_success.html', order=order, items=items)

@app.route('/my-orders')
@login_required
def my_orders():
    conn = get_db()
    orders = conn.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC',
                          (session['user_id'],)).fetchall()
    orders_with_items = []
    for o in orders:
        items = conn.execute('''
            SELECT oi.quantity, oi.price, p.name, p.image
            FROM order_items oi JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (o['id'],)).fetchall()
        orders_with_items.append({'order': o, 'items': items})
    conn.close()
    return render_template('user/orders.html', orders_with_items=orders_with_items)

@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    order_count = conn.execute('SELECT COUNT(*) FROM orders WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    total_spent = conn.execute('SELECT SUM(total_amount) FROM orders WHERE user_id = ?', (session['user_id'],)).fetchone()[0] or 0
    conn.close()
    return render_template('user/profile.html', user=user, order_count=order_count, total_spent=total_spent)

# ─── ADMIN ROUTES ──────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    product_count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    order_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    user_count = conn.execute('SELECT COUNT(*) FROM users WHERE role = "user"').fetchone()[0]
    revenue = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "paid"').fetchone()[0] or 0
    recent_orders = conn.execute('''
        SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id
        ORDER BY o.order_date DESC LIMIT 5
    ''').fetchall()
    conn.close()
    return render_template('admin/dashboard.html', product_count=product_count,
                           order_count=order_count, user_count=user_count,
                           revenue=revenue, recent_orders=recent_orders)

@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/manage_products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form['description']
        category = request.form['category']
        unit = request.form['unit']
        stock = int(request.form.get('stock', 100))
        image = 'default.jpg'

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image = filename

        conn = get_db()
        conn.execute('INSERT INTO products (name, price, description, image, category, unit, stock) VALUES (?,?,?,?,?,?,?)',
                     (name, price, description, image, category, unit, stock))
        conn.commit()
        conn.close()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/add_product.html')

@app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def edit_product(pid):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form['description']
        category = request.form['category']
        unit = request.form['unit']
        stock = int(request.form.get('stock', 100))
        image = product['image']

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image = filename

        conn.execute('UPDATE products SET name=?, price=?, description=?, image=?, category=?, unit=?, stock=? WHERE id=?',
                     (name, price, description, image, category, unit, stock, pid))
        conn.commit()
        conn.close()
        flash('Product updated!', 'success')
        return redirect(url_for('admin_products'))
    conn.close()
    return render_template('admin/edit_product.html', product=product)

@app.route('/admin/products/delete/<int:pid>', methods=['POST'])
@admin_required
def delete_product(pid):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn = get_db()
    orders = conn.execute('''
        SELECT o.*, u.username, u.email FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.order_date DESC
    ''').fetchall()
    orders_with_items = []
    for o in orders:
        items = conn.execute('''
            SELECT oi.quantity, oi.price, p.name
            FROM order_items oi JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (o['id'],)).fetchall()
        orders_with_items.append({'order': o, 'items': items})
    conn.close()
    return render_template('admin/orders.html', orders_with_items=orders_with_items)

@app.route('/admin/orders/update/<int:oid>', methods=['POST'])
@admin_required
def update_order_status(oid):
    status = request.form['status']
    conn = get_db()
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, oid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_orders'))

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute('SELECT u.*, (SELECT COUNT(*) FROM orders WHERE user_id=u.id) as order_count FROM users u').fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/delete/<int:uid>', methods=['POST'])
@admin_required
def delete_user(uid):
    if uid == session['user_id']:
        flash('Cannot delete yourself.', 'error')
        return redirect(url_for('admin_users'))
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (uid,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

# ─── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/cart-items')
@login_required
def cart_items():
    conn = get_db()
    items = conn.execute(
        'SELECT product_id, quantity FROM cart WHERE user_id = ?', (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify({'items': {str(i['product_id']): i['quantity'] for i in items}})

@app.route('/cart/update-qty', methods=['POST'])
@login_required
def update_cart_qty():
    product_id = request.form.get('product_id')
    new_qty = int(request.form.get('new_qty', 1))
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM cart WHERE user_id = ? AND product_id = ?',
        (session['user_id'], product_id)
    ).fetchone()
    if existing:
        conn.execute('UPDATE cart SET quantity = ? WHERE id = ?', (new_qty, existing['id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/cart/remove-by-product/<int:product_id>', methods=['POST'])
@login_required
def remove_by_product(product_id):
    conn = get_db()
    conn.execute('DELETE FROM cart WHERE user_id = ? AND product_id = ?', (session['user_id'], product_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/cart-count')
@login_required
def cart_count():
    conn = get_db()
    count = conn.execute('SELECT SUM(quantity) FROM cart WHERE user_id = ?', (session['user_id'],)).fetchone()[0] or 0
    conn.close()
    return jsonify({'count': count})

@app.route('/admin/fix-images')
@admin_required
def fix_images():
    """Auto-match product names to image files in static/images/"""
    import glob
    image_dir = app.config['UPLOAD_FOLDER']
    all_images = []
    for ext in ['jpg', 'jpeg', 'png', 'webp', 'avif', 'gif']:
        all_images += [os.path.basename(f) for f in glob.glob(os.path.join(image_dir, f'*.{ext}'))]

    conn = get_db()
    products = conn.execute('SELECT * FROM products').fetchall()
    updated = []
    keywords = {
        'tomato': 'tomatoes', 'spinach': 'spinach', 'carrot': 'carrots',
        'egg': 'eggs', 'milk': 'milk', 'rice': 'rice', 'wheat': 'wheat',
        'mango': 'mango', 'honey': 'honey', 'chilli': 'chilli', 'chili': 'chilli',
        'onion': 'onion', 'potato': 'potato', 'potatoes': 'potato'
    }
    for p in products:
        name_lower = p['name'].lower().replace(' ', '')
        matched = None
        for key, base in keywords.items():
            if key in name_lower:
                for img in all_images:
                    if os.path.splitext(img)[0].lower() == base:
                        matched = img
                        break
        if matched and matched != p['image']:
            conn.execute('UPDATE products SET image=? WHERE id=?', (matched, p['id']))
            updated.append(f"{p['name']} → {matched}")

    conn.commit()
    conn.close()

    result = '<h2>Image Fix Results</h2>'
    result += f'<p>Images found: {all_images}</p>'
    result += '<p>Updated:<br>' + '<br>'.join(updated) + '</p>' if updated else '<p>No updates needed or no matching files found.</p>'
    result += '<br><a href="/admin/products">Back to Products</a>'
    return result

if __name__ == '__main__':
    os.makedirs('static/images', exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)