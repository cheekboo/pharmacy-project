from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3

app = Flask(__name__)
app.secret_key = '001Ad002x1ew2341aditya'
DATABASE = 'app.db'

# Database functionality 
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER,
            name TEXT,
            code TEXT,
            quantity INTEGER,
            category TEXT,
            FOREIGN KEY (store_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            store_id INTEGER,
            medicine_code TEXT,
            quantity_requested INTEGER,
            status TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (store_id) REFERENCES users(id)
        );
        ''')
        db.commit()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form['email'].strip()
            password = request.form['password'].strip()
            role = request.form['role'].strip()
            db = get_db()
            db.execute('INSERT INTO users (email, password, role) VALUES (?, ?, ?)', (email, password, role))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "User already exists"
        except Exception as e:
            return f"Error: {e}"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email'].strip()
            password = request.form['password'].strip()
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
            if user:
                session['user_id'] = user['id']
                session['role'] = user['role']
                return redirect(url_for('dashboard_store' if user['role'] == 'store' else 'dashboard_public'))
            else:
                return "Invalid Login credentials."
        except Exception as e:
            return f"Login error: {e}"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard/store')
def dashboard_store():
    if session.get('role') != 'store':
        return redirect(url_for('login'))
    return render_template('dashboard_store.html')

@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():
    if session.get('role') != 'store':
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        code = request.form['code'].strip()
        quantity = int(request.form['quantity'])
        category = request.form['category'].strip()
        store_id = session['user_id']
        db = get_db()

        existing = db.execute(
            'SELECT * FROM medicines WHERE store_id = ? AND name = ? AND code = ?',
            (store_id, name, code)).fetchone()

        if existing:
            new_quantity = existing['quantity'] + quantity
            db.execute('UPDATE medicines SET quantity = ? WHERE id = ?', (new_quantity, existing['id']))
        else:
            db.execute(
                'INSERT INTO medicines (store_id, name, code, quantity, category) VALUES (?, ?, ?, ?, ?)',
                (store_id, name, code, quantity, category))
        db.commit()
        return redirect(url_for('view_medicines'))
    return render_template('add_medicine.html')

@app.route('/view_medicines')
def view_medicines():
    if session.get('role') != 'store':
        return redirect(url_for('login'))
    db = get_db()
    store_id = session['user_id']
    meds = db.execute('SELECT * FROM medicines WHERE store_id = ?', (store_id,)).fetchall()
    return render_template('view_medicines.html', medicines=meds)

@app.route('/view_orders', methods=['GET', 'POST'])
def view_orders():
    if session.get('role') != 'store':
        return redirect(url_for('login'))

    db = get_db()
    store_id = session['user_id']

    if request.method == 'POST':
        order_id = request.form['order_id']
        action = request.form['action']

        order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
        medicine = db.execute(
            'SELECT * FROM medicines WHERE code = ? AND store_id = ?',
            (order['medicine_code'], store_id)).fetchone()

        if action == 'accept':
            if medicine and medicine['quantity'] >= order['quantity_requested']:
                db.execute('UPDATE orders SET status = ? WHERE id = ?', ('Accepted', order_id))
                db.execute('UPDATE medicines SET quantity = quantity - ? WHERE code = ? AND store_id = ?',
                           (order['quantity_requested'], order['medicine_code'], store_id))
            else:
                return "Not enough stock to accept this order."
        elif action == 'reject':
            db.execute('UPDATE orders SET status = ? WHERE id = ?', ('Rejected', order_id))

        db.commit()

    orders = db.execute('''
        SELECT o.*, u.email FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.store_id = ?
    ''', (store_id,)).fetchall()

    return render_template('view_orders.html', orders=orders)

@app.route('/dashboard/public')
def dashboard_public():
    if session.get('role') != 'public':
        return redirect(url_for('login'))
    return render_template('dashboard_public.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    if session.get('role') != 'public':
        return redirect(url_for('login'))
    if request.method == 'POST':
        keyword = request.form['keyword']
        db = get_db()
        results = db.execute('''
            SELECT m.*, u.email as store_email FROM medicines m
            JOIN users u ON m.store_id = u.id
            WHERE m.name LIKE ? OR m.code LIKE ?
        ''', ('%' + keyword + '%', '%' + keyword + '%')).fetchall()
    return render_template('search.html', results=results)

@app.route('/request_order', methods=['POST'])
def request_order():
    if session.get('role') != 'public':
        return redirect(url_for('login'))

    code = request.form['code']
    store_id = int(request.form['store_id'])
    quantity = int(request.form['quantity'])
    user_id = session['user_id']
    db = get_db()

    db.execute(
        'INSERT INTO orders (user_id, store_id, medicine_code, quantity_requested, status) VALUES (?, ?, ?, ?, ?)',
        (user_id, store_id, code, quantity, 'Pending'))
    db.commit()
    return redirect(url_for('dashboard_public'))

@app.route('/my_orders')
def my_orders():
    if session.get('role') != 'public':
        return redirect(url_for('login'))
    db = get_db()
    user_id = session['user_id']
    orders = db.execute('SELECT * FROM orders WHERE user_id = ?', (user_id,)).fetchall()
    return render_template('my_orders.html', orders=orders)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
