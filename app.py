"""
Inventory Management API
Flask + MySQL + JWT + Swagger (Flasgger)
Demonstrates all HTTP methods: GET, POST, PUT, PATCH, DELETE
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flasgger import Swagger, swag_from
import mysql.connector
from mysql.connector import Error
import bcrypt
import jwt
import datetime
import os
from functools import wraps

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────
app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config['SECRET_KEY'] = 'inventory_secret_key_2025_enterprise'

# ──────────────────────────────────────────────
# Swagger Configuration
# ──────────────────────────────────────────────
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/swagger/",
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Inventory Management API",
        "description": """
## 🏢 Enterprise Inventory Management API

This API demonstrates **full CRUD operations** with:
- 🔐 **JWT Authentication** (Bearer Token)
- 📦 **Inventory Management** (GET, POST, PUT, PATCH, DELETE)
- 👤 **User Authentication** (Register & Login)
- 🗄️ **MySQL Database** backend

### Authentication Flow
1. **Register** a new user via `POST /api/auth/register`
2. **Login** via `POST /api/auth/login` to receive a JWT token
3. Use the token in the **Authorization** header: `Bearer <your_token>`
4. Perform CRUD operations on `/api/inventory`

### HTTP Methods Demonstrated
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register | Register new user |
| POST | /api/auth/login | Login & get JWT token |
| GET | /api/auth/profile | Get current user profile |
| GET | /api/inventory | Get all inventory items |
| GET | /api/inventory/{id} | Get single item |
| POST | /api/inventory | Create new item |
| PUT | /api/inventory/{id} | Full update of item |
| PATCH | /api/inventory/{id} | Partial update of item |
| DELETE | /api/inventory/{id} | Delete item |
| GET | /api/inventory/stats | Inventory statistics |
        """,
        "version": "1.0.0",
        "contact": {
            "name": "Inventory API Support",
            "email": "support@inventory.com"
        }
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter: **Bearer &lt;JWT token&gt;**\n\nExample: `Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...`"
        }
    },
    "tags": [
        {"name": "Authentication", "description": "User registration, login, and profile"},
        {"name": "Inventory", "description": "Full CRUD operations on inventory items"},
        {"name": "Statistics", "description": "Inventory analytics and stats"},
        {"name": "Health", "description": "API health check"}
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# ──────────────────────────────────────────────
# Database Configuration
# ──────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Anusha@123',          # ← Change to your MySQL password
    'database': 'inventory_db',
    'autocommit': False
}

def get_db_connection():
    """Create and return a MySQL database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"[DB ERROR] {e}")
        return None

def init_database():
    """Create database and tables if they don't exist."""
    try:
        # Connect without specifying a database first
        init_config = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
        conn = mysql.connector.connect(**init_config)
        cursor = conn.cursor()

        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
        cursor.execute(f"USE `{DB_CONFIG['database']}`")
        print(f"[DB] Database '{DB_CONFIG['database']}' ready.")

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(100)        NOT NULL,
                email       VARCHAR(150)        NOT NULL UNIQUE,
                password    VARCHAR(255)        NOT NULL,
                role        ENUM('admin','user') DEFAULT 'user',
                created_at  TIMESTAMP           DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP           DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        print("[DB] Table 'users' ready.")

        # Inventory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                name         VARCHAR(150)       NOT NULL,
                category     VARCHAR(100)       NOT NULL,
                sku          VARCHAR(100)       NOT NULL UNIQUE,
                quantity     INT                NOT NULL DEFAULT 0,
                unit_price   DECIMAL(10, 2)     NOT NULL DEFAULT 0.00,
                supplier     VARCHAR(150)       DEFAULT NULL,
                location     VARCHAR(100)       DEFAULT NULL,
                status       ENUM('active','inactive','discontinued') DEFAULT 'active',
                description  TEXT               DEFAULT NULL,
                created_by   INT,
                created_at   TIMESTAMP          DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP          DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        print("[DB] Table 'inventory' ready.")

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Database initialization complete. ✅")

    except Error as e:
        print(f"[DB INIT ERROR] {e}")

# ──────────────────────────────────────────────
# JWT Auth Decorator
# ──────────────────────────────────────────────
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing. Please login.'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token has expired. Please login again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token.'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────
def row_to_dict(cursor, row):
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

def rows_to_list(cursor, rows):
    columns = [col[0] for col in cursor.description]
    result = []
    for row in rows:
        d = dict(zip(columns, row))
        for k, v in d.items():
            if isinstance(v, datetime.datetime):
                d[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(v, datetime.date):
                d[k] = v.strftime('%Y-%m-%d')
        result.append(d)
    return result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC FILE ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.route('/')
@app.route('/login')
def serve_login():
    return send_from_directory('.', 'login.html')

@app.route('/register')
def serve_register():
    return send_from_directory('.', 'register.html')

@app.route('/inventory')
def serve_inventory():
    return send_from_directory('.', 'inventory.html')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HEALTH CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.route('/api/health', methods=['GET'])
def health_check():
    """
    API Health Check
    ---
    tags:
      - Health
    summary: Check if the API is running
    responses:
      200:
        description: API is healthy
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: API is running
            timestamp:
              type: string
              example: "2025-01-01 12:00:00"
            version:
              type: string
              example: "1.0.0"
    """
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    return jsonify({
        'success': True,
        'message': 'Inventory API is running',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': '1.0.0',
        'database': db_status
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUTH ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.route('/api/auth/register', methods=['POST'])
def register():
    """
    Register a new user
    ---
    tags:
      - Authentication
    summary: Create a new user account
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - email
            - password
          properties:
            name:
              type: string
              example: John Doe
              description: Full name
            email:
              type: string
              example: john@example.com
              description: Unique email address
            password:
              type: string
              example: password123
              description: Password (min 6 chars)
            role:
              type: string
              enum: [admin, user]
              example: user
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            user:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                email:
                  type: string
                role:
                  type: string
      400:
        description: Validation error or email already exists
      500:
        description: Server error
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    name     = data.get('name', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role     = data.get('role', 'user')

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'Name, email, and password are required'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                       (name, email, hashed, role))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {'id': user_id, 'name': name, 'email': email, 'role': role}
        }), 201
    except mysql.connector.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already registered'}), 400
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Login and receive JWT token
    ---
    tags:
      - Authentication
    summary: Authenticate user and get access token
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              example: john@example.com
            password:
              type: string
              example: password123
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            token:
              type: string
              description: JWT Bearer token (valid 24 hours)
            user:
              type: object
      401:
        description: Invalid credentials
      500:
        description: Server error
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password, role FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

        user_id, name, user_email, hashed_pw, role = user

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_pw.encode('utf-8')):
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

        token = jwt.encode({
            'user_id': user_id,
            'email': user_email,
            'name': name,
            'role': role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'success': True,
            'message': f'Welcome back, {name}!',
            'token': token,
            'user': {'id': user_id, 'name': name, 'email': user_email, 'role': role}
        })
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/auth/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """
    Get current user profile
    ---
    tags:
      - Authentication
    summary: Retrieve authenticated user's profile
    security:
      - Bearer: []
    responses:
      200:
        description: Profile data
        schema:
          type: object
          properties:
            success:
              type: boolean
            user:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                email:
                  type: string
                role:
                  type: string
                created_at:
                  type: string
      401:
        description: Unauthorized
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE id = %s",
                       (current_user['user_id'],))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        uid, name, email, role, created_at = row
        return jsonify({
            'success': True,
            'user': {
                'id': uid, 'name': name, 'email': email, 'role': role,
                'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else None
            }
        })
    finally:
        conn.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INVENTORY ROUTES — CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route('/api/inventory/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    """
    Get inventory statistics
    ---
    tags:
      - Statistics
    summary: Retrieve aggregated inventory stats
    security:
      - Bearer: []
    responses:
      200:
        description: Statistics data
        schema:
          type: object
          properties:
            success:
              type: boolean
            stats:
              type: object
              properties:
                total_items:
                  type: integer
                total_quantity:
                  type: integer
                total_value:
                  type: number
                low_stock:
                  type: integer
                categories:
                  type: integer
                active_items:
                  type: integer
      401:
        description: Unauthorized
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_items,
                COALESCE(SUM(quantity), 0) AS total_quantity,
                COALESCE(SUM(quantity * unit_price), 0) AS total_value,
                SUM(CASE WHEN quantity <= 10 AND status='active' THEN 1 ELSE 0 END) AS low_stock,
                COUNT(DISTINCT category) AS categories,
                SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active_items
            FROM inventory
        """)
        row = cursor.fetchone()
        cursor.close()
        keys = ['total_items','total_quantity','total_value','low_stock','categories','active_items']
        stats = dict(zip(keys, [float(v) if isinstance(v, (int, float)) else v for v in row]))
        return jsonify({'success': True, 'stats': stats})
    finally:
        conn.close()


@app.route('/api/inventory', methods=['GET'])
@token_required
def get_inventory(current_user):
    """
    Get all inventory items
    ---
    tags:
      - Inventory
    summary: Retrieve all inventory items with optional filters
    security:
      - Bearer: []
    parameters:
      - in: query
        name: category
        type: string
        description: Filter by category
      - in: query
        name: status
        type: string
        enum: [active, inactive, discontinued]
        description: Filter by status
      - in: query
        name: search
        type: string
        description: Search by name or SKU
      - in: query
        name: sort
        type: string
        enum: [name, quantity, unit_price, created_at]
        description: Sort field
      - in: query
        name: order
        type: string
        enum: [asc, desc]
        description: Sort order
      - in: query
        name: page
        type: integer
        description: Page number (default 1)
      - in: query
        name: limit
        type: integer
        description: Items per page (default 20)
    responses:
      200:
        description: List of inventory items
        schema:
          type: object
          properties:
            success:
              type: boolean
            items:
              type: array
              items:
                $ref: '#/definitions/InventoryItem'
            pagination:
              type: object
              properties:
                total:
                  type: integer
                page:
                  type: integer
                limit:
                  type: integer
                pages:
                  type: integer
      401:
        description: Unauthorized
    definitions:
      InventoryItem:
        type: object
        properties:
          id:
            type: integer
          name:
            type: string
          category:
            type: string
          sku:
            type: string
          quantity:
            type: integer
          unit_price:
            type: number
          supplier:
            type: string
          location:
            type: string
          status:
            type: string
          description:
            type: string
          created_at:
            type: string
    """
    category = request.args.get('category', '')
    status   = request.args.get('status', '')
    search   = request.args.get('search', '')
    sort     = request.args.get('sort', 'created_at')
    order    = request.args.get('order', 'desc').upper()
    page     = int(request.args.get('page', 1))
    limit    = int(request.args.get('limit', 20))

    valid_sorts  = ['name','quantity','unit_price','created_at','updated_at']
    valid_orders = ['ASC','DESC']
    if sort not in valid_sorts:  sort = 'created_at'
    if order not in valid_orders: order = 'DESC'

    where_clauses = []
    params = []
    if category:
        where_clauses.append("category = %s")
        params.append(category)
    if status:
        where_clauses.append("status = %s")
        params.append(status)
    if search:
        where_clauses.append("(name LIKE %s OR sku LIKE %s)")
        params.extend([f'%{search}%', f'%{search}%'])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    offset = (page - 1) * limit

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM inventory {where_sql}", params)
        total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT id,name,category,sku,quantity,unit_price,supplier,location,status,description,created_at,updated_at "
            f"FROM inventory {where_sql} ORDER BY {sort} {order} LIMIT %s OFFSET %s",
            params + [limit, offset]
        )
        items = rows_to_list(cursor, cursor.fetchall())
        cursor.close()

        import math
        return jsonify({
            'success': True,
            'items': items,
            'pagination': {
                'total': total,
                'page': page,
                'limit': limit,
                'pages': math.ceil(total / limit) if total else 1
            }
        })
    finally:
        conn.close()


@app.route('/api/inventory/<int:item_id>', methods=['GET'])
@token_required
def get_inventory_item(current_user, item_id):
    """
    Get a single inventory item by ID
    ---
    tags:
      - Inventory
    summary: Retrieve details of a specific inventory item
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
        description: Inventory item ID
    responses:
      200:
        description: Inventory item details
        schema:
          type: object
          properties:
            success:
              type: boolean
            item:
              $ref: '#/definitions/InventoryItem'
      404:
        description: Item not found
      401:
        description: Unauthorized
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id,name,category,sku,quantity,unit_price,supplier,location,status,description,created_by,created_at,updated_at "
            "FROM inventory WHERE id = %s", (item_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return jsonify({'success': False, 'message': 'Item not found'}), 404
        keys = ['id','name','category','sku','quantity','unit_price','supplier','location','status','description','created_by','created_at','updated_at']
        item = {}
        for k, v in zip(keys, row):
            if isinstance(v, datetime.datetime):
                item[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            else:
                item[k] = float(v) if k in ['unit_price'] and v is not None else v
        return jsonify({'success': True, 'item': item})
    finally:
        conn.close()


@app.route('/api/inventory', methods=['POST'])
@token_required
def create_inventory_item(current_user):
    """
    Create a new inventory item
    ---
    tags:
      - Inventory
    summary: Add a new item to the inventory
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - category
            - sku
            - quantity
            - unit_price
          properties:
            name:
              type: string
              example: Laptop Dell XPS 15
            category:
              type: string
              example: Electronics
            sku:
              type: string
              example: DELL-XPS-15-001
            quantity:
              type: integer
              example: 50
            unit_price:
              type: number
              example: 1299.99
            supplier:
              type: string
              example: Dell Inc.
            location:
              type: string
              example: Warehouse A, Row 3
            status:
              type: string
              enum: [active, inactive, discontinued]
              example: active
            description:
              type: string
              example: High-performance laptop with OLED display
    responses:
      201:
        description: Item created successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            item:
              type: object
              properties:
                id:
                  type: integer
      400:
        description: Validation error
      401:
        description: Unauthorized
      409:
        description: SKU already exists
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    required = ['name', 'category', 'sku', 'quantity', 'unit_price']
    for field in required:
        if field not in data or str(data[field]).strip() == '':
            return jsonify({'success': False, 'message': f'Field "{field}" is required'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO inventory (name, category, sku, quantity, unit_price, supplier, location, status, description, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['name'].strip(), data['category'].strip(), data['sku'].strip().upper(),
            int(data['quantity']), float(data['unit_price']),
            data.get('supplier', ''), data.get('location', ''),
            data.get('status', 'active'), data.get('description', ''),
            current_user['user_id']
        ))
        conn.commit()
        item_id = cursor.lastrowid
        cursor.close()
        return jsonify({'success': True, 'message': 'Item created successfully', 'item': {'id': item_id}}), 201
    except mysql.connector.IntegrityError:
        return jsonify({'success': False, 'message': 'SKU already exists'}), 409
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@token_required
def update_inventory_item(current_user, item_id):
    """
    Full update of an inventory item (PUT)
    ---
    tags:
      - Inventory
    summary: Replace all fields of an inventory item
    description: PUT replaces the entire resource. All required fields must be provided.
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - category
            - sku
            - quantity
            - unit_price
          properties:
            name:
              type: string
              example: Laptop Dell XPS 15 Updated
            category:
              type: string
              example: Electronics
            sku:
              type: string
              example: DELL-XPS-15-001
            quantity:
              type: integer
              example: 75
            unit_price:
              type: number
              example: 1199.99
            supplier:
              type: string
              example: Dell Inc.
            location:
              type: string
              example: Warehouse B, Row 1
            status:
              type: string
              enum: [active, inactive, discontinued]
            description:
              type: string
    responses:
      200:
        description: Item updated successfully
      400:
        description: Validation error
      404:
        description: Item not found
      401:
        description: Unauthorized
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    required = ['name', 'category', 'sku', 'quantity', 'unit_price']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'message': f'Field "{field}" is required for PUT'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM inventory WHERE id = %s", (item_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Item not found'}), 404

        cursor.execute("""
            UPDATE inventory SET name=%s, category=%s, sku=%s, quantity=%s, unit_price=%s,
            supplier=%s, location=%s, status=%s, description=%s WHERE id=%s
        """, (
            data['name'].strip(), data['category'].strip(), data['sku'].strip().upper(),
            int(data['quantity']), float(data['unit_price']),
            data.get('supplier', ''), data.get('location', ''),
            data.get('status', 'active'), data.get('description', ''), item_id
        ))
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Item fully updated (PUT)', 'id': item_id})
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/inventory/<int:item_id>', methods=['PATCH'])
@token_required
def patch_inventory_item(current_user, item_id):
    """
    Partial update of an inventory item (PATCH)
    ---
    tags:
      - Inventory
    summary: Update only specified fields of an inventory item
    description: PATCH updates only the fields you provide. Other fields remain unchanged.
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          description: Provide only the fields you want to update
          properties:
            name:
              type: string
            category:
              type: string
            quantity:
              type: integer
              example: 100
            unit_price:
              type: number
            supplier:
              type: string
            location:
              type: string
            status:
              type: string
              enum: [active, inactive, discontinued]
              example: inactive
            description:
              type: string
    responses:
      200:
        description: Item partially updated
      400:
        description: No fields to update
      404:
        description: Item not found
      401:
        description: Unauthorized
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    allowed = ['name','category','sku','quantity','unit_price','supplier','location','status','description']
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({'success': False, 'message': 'No valid fields to update'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM inventory WHERE id = %s", (item_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Item not found'}), 404

        set_clause = ", ".join([f"{k} = %s" for k in fields.keys()])
        values = list(fields.values()) + [item_id]
        cursor.execute(f"UPDATE inventory SET {set_clause} WHERE id = %s", values)
        conn.commit()
        cursor.close()
        return jsonify({
            'success': True,
            'message': f'Item partially updated (PATCH). Fields changed: {list(fields.keys())}',
            'id': item_id,
            'updated_fields': list(fields.keys())
        })
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
@token_required
def delete_inventory_item(current_user, item_id):
    """
    Delete an inventory item
    ---
    tags:
      - Inventory
    summary: Permanently delete an inventory item
    security:
      - Bearer: []
    parameters:
      - in: path
        name: item_id
        type: integer
        required: true
        description: ID of the item to delete
    responses:
      200:
        description: Item deleted successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            deleted_id:
              type: integer
      404:
        description: Item not found
      401:
        description: Unauthorized
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM inventory WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Item not found'}), 404

        item_name = row[1]
        cursor.execute("DELETE FROM inventory WHERE id = %s", (item_id,))
        conn.commit()
        cursor.close()
        return jsonify({
            'success': True,
            'message': f'Item "{item_name}" deleted successfully',
            'deleted_id': item_id
        })
    except Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/inventory/categories', methods=['GET'])
@token_required
def get_categories(current_user):
    """
    Get all inventory categories
    ---
    tags:
      - Inventory
    summary: List all distinct categories in inventory
    security:
      - Bearer: []
    responses:
      200:
        description: List of categories
        schema:
          type: object
          properties:
            success:
              type: boolean
            categories:
              type: array
              items:
                type: string
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM inventory ORDER BY category")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return jsonify({'success': True, 'categories': categories})
    finally:
        conn.close()

# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "═"*60)
    print("  🏢  Inventory Management API  v1.0.0")
    print("═"*60)
    print("  Initializing database...")
    init_database()
    print("\n  📡  Server:    http://localhost:5000")
    print("  📖  Swagger:   http://localhost:5000/swagger/")
    print("  ❤️   Health:    http://localhost:5000/api/health")
    print("═"*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)