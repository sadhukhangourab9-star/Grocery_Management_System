import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIG ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("google_creds.json", scopes=scope)
client = gspread.authorize(creds)
SHEET_NAME = "Grocery_Management_System"

def setup_database_v2():
    sh = client.open(SHEET_NAME)

    # 1. Create Slot Master Tab
    try:
        ws_slots = sh.add_worksheet(title="Slot_Master", rows="100", cols="2")
        ws_slots.update('A1', [['Slots']])
        ws_slots.update('A2:A6', [['10 PM'], ['12 PM'], ['8 AM'], ['2 PM'], ['4 PM']])
        print("✅ Slot_Master created.")
    except:
        print("ℹ️ Slot_Master already exists.")

    # 2. Update/Create Current Month Sheet with "Order Name"
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    products = sh.worksheet("Product_Master").col_values(1)[1:]
    
    # New Headers: Date, Slot, Account, Order Name, Status + Products
    headers = ["Date", "Slot", "Account", "Order Name", "Status"] + products
    
    try:
        ws_inv = sh.add_worksheet(title=month_title, rows="500", cols="100")
    except:
        ws_inv = sh.worksheet(month_title)
    
    ws_inv.update('A1', [headers])
    print(f"✅ {month_title} headers updated.")

if __name__ == "__main__":
    setup_database_v2()
