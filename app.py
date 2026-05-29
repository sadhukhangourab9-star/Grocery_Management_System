from flask import Flask, request, jsonify, render_template
import json, os, gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- CONFIG ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
# For Render, paste JSON content into GOOGLE_CREDENTIALS_JSON env var
CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")

def get_sh():
    if not CREDS_JSON or not SHEET_ID:
        raise RuntimeError("Environment variables not set")
    info = json.loads(CREDS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

# --- DB HELPERS ---
def get_inv_title():
    return f"Inventory_{datetime.now().strftime('%b_%Y')}"

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sync', methods=['POST'])
def sync_db():
    sh = get_sh()
    existing = {ws.title for ws in sh.worksheets()}
    
    # 1. Product Master
    if "Product_Master" not in existing:
        ws = sh.add_worksheet("Product_Master", 100, 2)
        ws.update('A1', [['Product Name']])
    
    # 2. Slot Master
    if "Slot_Master" not in existing:
        ws = sh.add_worksheet("Slot_Master", 20, 2)
        ws.update('A1', [['Slots'], ['10 PM'], ['12 PM'], ['8 AM']])
        
    # 3. Inventory Sheet
    products = sh.worksheet("Product_Master").col_values(1)[1:]
    headers = ["Date", "Slot", "Account", "Order Name", "Status"] + products
    title = get_inv_title()
    
    if title not in existing:
        ws = sh.add_worksheet(title, 1000, len(headers) + 2)
        ws.update('A1', [headers])
        ws.append_row(["-", "-", "Old Stock", "-", "Delivered"] + [0]*len(products))
    else:
        ws = sh.worksheet(title)
        ws.update('A1', [headers]) # Update headers if products added
        
    return jsonify({"success": True})

@app.route('/api/meta', methods=['GET'])
def get_meta():
    sh = get_sh()
    products = sh.worksheet("Product_Master").col_values(1)[1:]
    slots = sh.worksheet("Slot_Master").col_values(1)[1:]
    return jsonify({"products": products, "slots": slots})

@app.route('/api/order', methods=['POST'])
def add_order():
    data = request.json
    sh = get_sh()
    ws = sh.worksheet(get_inv_title())
    products = sh.worksheet("Product_Master").col_values(1)[1:]
    
    row = [data['date'], data['slot'], data['account'], data['order_name'], "Pending"]
    for p in products:
        row.append(data['quantities'].get(p, 0))
    
    ws.append_row(row)
    return jsonify({"success": True})

@app.route('/api/receiver', methods=['GET'])
def receiver_data():
    sh = get_sh()
    ws = sh.worksheet(get_inv_title())
    data = ws.get_all_records()
    pending = [r for r in data if r.get('Status') == 'Pending']
    # Get products (everything after 'Status')
    products = sh.worksheet("Product_Master").col_values(1)[1:]
    return jsonify({"pending": pending, "products": products})

@app.route('/api/verify', methods=['POST'])
def verify():
    row_idx = request.json['row_index'] # 0-based from JS
    sh = get_sh()
    ws = sh.worksheet(get_inv_title())
    ws.update_cell(row_idx + 2, 5, "Delivered") # Column 5 is Status
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
