import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
# Ensure your google_creds.json is in the same folder
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("google_creds.json", scopes=scope)
client = gspread.authorize(creds)

# 1. Provide the EXACT name of your Google Sheet
SHEET_NAME = "Grocery_Management_System"

# 2. The list of products from your text file
PRODUCT_LIST = [
    "Fortune Mustard pouch", "Fortune Mustard Bottle", "Fortune Soya pouch", 
    "Fortune Ricebran", "Fortune Sunflower", "Fortune mustard 5L jar", 
    "Fortune Soya 5L jar", "Emami bottle", "Emami mustard pouch", 
    "Emami Ricebran", "Emami Soyabean", "Engine", "Saffola gold", 
    "Amulia 200 gm", "Amulia 500 gm", "Amulia 1kg", "Sunlight 1kg", 
    "Sunlight 500", "Surf excel 1kg", "Surf excel 500", "Vim 750", 
    "Lyzol", "Harpic 1L", "Harpic 500", "Tide 500", "Godrej fab 4L", 
    "Godrej fab 1L", "Tata Tea 100gm", "Dalda", "Ashirbad atta 5kg"
]

def setup_database():
    try:
        # Open the spreadsheet
        try:
            sh = client.open(SHEET_NAME)
            print(f"Connected to existing sheet: {SHEET_NAME}")
        except gspread.SpreadsheetNotFound:
            sh = client.create(SHEET_NAME)
            print(f"Created new spreadsheet: {SHEET_NAME}")
            print(f"IMPORTANT: Share the sheet with your service account email!")

        # --- TAB 1: PRODUCT MASTER ---
        print("Setting up Product_Master...")
        try:
            ws_master = sh.add_worksheet(title="Product_Master", rows="100", cols="5")
        except:
            ws_master = sh.worksheet("Product_Master")
        
        ws_master.clear()
        ws_master.update('A1', [['Product Name']])
        # Update product list (convert list to list of lists for gspread)
        product_rows = [[p] for p in PRODUCT_LIST]
        ws_master.update(f'A2:A{len(PRODUCT_LIST)+1}', product_rows)

        # --- TAB 2: SALES LOG ---
        print("Setting up Sales_Log...")
        try:
            ws_sales = sh.add_worksheet(title="Sales_Log", rows="1000", cols="10")
        except:
            ws_sales = sh.worksheet("Sales_Log")
        ws_sales.clear()
        ws_sales.update('A1', [['Date', 'Buyer Name', 'Product Name', 'Quantity Sold']])

        # --- TAB 3: CURRENT MONTH INVENTORY ---
        month_year = datetime.now().strftime("%b_%Y")
        inventory_title = f"Inventory_{month_year}"
        print(f"Setting up {inventory_title}...")
        
        try:
            ws_inv = sh.add_worksheet(title=inventory_title, rows="500", cols="100")
        except:
            ws_inv = sh.worksheet(inventory_title)
        
        ws_inv.clear()
        # Create headers: Date, Slot, Account, Status + All Products
        headers = ["Date", "Slot", "Account", "Status"] + PRODUCT_LIST
        ws_inv.update('A1', [headers])
        
        # Add a placeholder 'Old Stock' row as requested
        old_stock_row = ["-", "-", "Old Stock", "Delivered"] + [0] * len(PRODUCT_LIST)
        ws_inv.append_row(old_stock_row)

        # Cleanup: Remove the default "Sheet1" if it exists
        try:
            sheet1 = sh.worksheet("Sheet1")
            sh.del_worksheet(sheet1)
        except:
            pass

        print("\n✅ DATABASE SETUP COMPLETE!")
        print(f"Spreadsheet URL: https://docs.google.com/spreadsheets/d/{sh.id}")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    setup_database()