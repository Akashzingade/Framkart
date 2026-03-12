# 🌾 FarmKart – Online Farmer Marketplace

A full-stack e-commerce platform connecting farmers to customers, built with Flask + SQLite.

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install flask werkzeug
```

### 2. Run the app
```bash
cd farmkart
python app.py
```

### 3. Open in browser
```
http://localhost:5000
```

---

## 🔑 Default Credentials

| Role  | Email                | Password |
|-------|----------------------|----------|
| Admin | admin@farmkart.com   | admin123 |
| User  | Register a new account |        |

---

## 💳 Razorpay Setup (Production)

1. Sign up at https://razorpay.com
2. Get your API keys from Dashboard → Settings → API Keys
3. In `app.py`, replace:
   ```python
   RAZORPAY_KEY_ID = 'rzp_test_YourKeyHere'
   RAZORPAY_KEY_SECRET = 'YourSecretHere'
   ```
4. For server-side order creation, install razorpay SDK:
   ```bash
   pip install razorpay
   ```
   Then use in `create_order` route:
   ```python
   import razorpay
   client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
   order = client.order.create({'amount': int(total*100), 'currency': 'INR'})
   ```

**Without real Razorpay keys:** The app works in demo mode. When the Razorpay modal would appear, it falls back to a test order flow automatically.

---

## 📁 Project Structure

```
farmkart/
├── app.py                    # Flask backend (all routes)
├── database.db               # SQLite database (auto-created)
├── requirements.txt
├── static/
│   ├── css/style.css         # All styles
│   ├── js/main.js            # Cart, payment, toast logic
│   └── images/               # Product images (upload here)
└── templates/
    ├── base.html             # Shared navbar/footer
    ├── index.html            # Homepage
    ├── products.html         # Product listing
    ├── login.html            # Login page
    ├── register.html         # Registration
    ├── cart.html             # Shopping cart
    ├── checkout.html         # Checkout + Razorpay
    ├── order_success.html    # Order confirmation
    ├── admin/
    │   ├── base_admin.html   # Admin layout with sidebar
    │   ├── dashboard.html    # Admin overview
    │   ├── manage_products.html
    │   ├── add_product.html
    │   ├── edit_product.html
    │   ├── orders.html
    │   └── users.html
    └── user/
        ├── dashboard.html
        ├── orders.html
        └── profile.html
```

---

## ✨ Features

### User
- Register / Login / Logout
- Browse products by category or search
- Add to cart, update quantities, remove items
- Checkout with delivery address
- Razorpay payment (UPI, Card, NetBanking)
- View order history and confirmation

### Admin
- Dashboard with stats (products, orders, users, revenue)
- Add / Edit / Delete products with image upload
- View and update order status
- Manage users

---

## 🛠️ Tech Stack
- **Backend:** Python Flask
- **Database:** SQLite (via sqlite3)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Fonts:** Playfair Display + DM Sans (Google Fonts)
- **Payment:** Razorpay
- **Sessions:** Flask built-in sessions
