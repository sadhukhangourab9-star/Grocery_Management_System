import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os
from datetime import datetime

# --- 1. SETTINGS ---
SHEET_NAME = "Grocery_Management_System"  # MUST match your Google Sheet name exactly
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 2. CREDENTIAL LOADING ---
def load_creds():
    # Try Render Environment Variable first
    if "gcp_service_account" in os.environ:
        try:
            creds_json = os.environ.get("gcp_service_account")
            if creds_json.startswith("'") and creds_json.endswith("'"):
                creds_json = creds_json[1:-1]
            info = json.loads(creds_json)
            return Credentials.from_service_account_info(info, scopes=SCOPE)
        except Exception as e:
            st.error(f"Error parsing Environment Variable: {e}")

    # Try Local File
    if os.path.exists("google_creds.json"):
        return Credentials.from_service_account_file("google_creds.json", scopes=SCOPE)

    st.error("No credentials found! Set 'gcp_service_account' in Render or add 'google_creds.json' locally.")
    st.stop()

# --- 3. INITIALIZE CONNECTION ---
# We define these at the top level so all functions can see them
try:
    creds = load_creds()
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME) # This defines 'sh' globally
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# --- 4. HELPER FUNCTIONS ---
def get_inventory_sheet():
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    try:
        return sh.worksheet(month_title)
    except:
        # Fallback to the first inventory sheet found if current month doesn't exist yet
        worksheets = [ws.title for ws in sh.worksheets() if "Inventory_" in ws.title]
        return sh.worksheet(worksheets[0])

def get_products():
    return sh.worksheet("Product_Master").col_values(1)[1:]

# --- 5. MAIN APP UI ---
st.set_page_config(page_title="Grocery Inventory", layout="wide")
st.sidebar.title("🛒 Grocery Admin")
menu = st.sidebar.radio("Navigation", ["Amazon Entry", "Receiver View", "Daily Sales", "Inventory Report"])

# Load dynamic data
products = get_products()
inv_ws = get_inventory_sheet()

# --- PAGE: AMAZON ENTRY ---
if menu == "Amazon Entry":
    st.header("📦 Amazon Order Input")
    with st.form("entry_form"):
        col1, col2, col3 = st.columns(3)
        date = col1.date_input("Order Date")
        slot = col2.selectbox("Slot", ["10 PM", "12 PM", "8 AM", "2 PM"])
        acc = col3.text_input("Account (e.g. Amazon 16/10)")
        
        st.write("---")
        st.write("Enter Quantities:")
        cols = st.columns(3)
        input_data = []
        for i, p in enumerate(products):
            with cols[i % 3]:
                qty = st.number_input(f"{p}", min_value=0, step=1, key=f"in_{p}")
                input_data.append(qty)
        
        if st.form_submit_button("Log Order"):
            row = [str(date), slot, acc, "Pending"] + input_data
            inv_ws.append_row(row)
            st.success("Order Logged in Google Sheets!")

# --- PAGE: RECEIVER VIEW ---
elif menu == "Receiver View":
    st.header("🚚 Incoming Deliveries")
    data = inv_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        if 'Status' in df.columns:
            pending = df[df['Status'] == 'Pending']
            
            if pending.empty:
                st.success("No pending items to receive!")
            else:
                for index, row in pending.iterrows():
                    sheet_row_index = index + 2 
                    with st.expander(f"Order: {row['Account']} | Slot: {row['Slot']}"):
                        for p in products:
                            if row.get(p, 0) > 0:
                                st.write(f"- {p}: **{row[p]}**")
                        
                        if st.button("Mark as Delivered", key=f"recv_{index}"):
                            # Status is in Column D (4)
                            inv_ws.update_cell(sheet_row_index, 4, "Delivered")
                            st.rerun()
        else:
            st.error("Column 'Status' not found in sheet.")

# --- PAGE: DAILY SALES ---
elif menu == "Daily Sales":
    st.header("💰 Record Sales")
    with st.form("sales_form"):
        buyer = st.selectbox("Buyer", ["Rajkumar da", "Souvik da", "Gourab", "Walk-in"])
        prod = st.selectbox("Product", products)
        sqty = st.number_input("Quantity Sold", min_value=1)
        
        if st.form_submit_button("Submit Sale"):
            sh.worksheet("Sales_Log").append_row([str(datetime.now().date()), buyer, prod, sqty])
            st.success("Sale Logged!")

# --- PAGE: INVENTORY REPORT ---
elif menu == "Inventory Report":
    st.header("📊 Current Stock Status")
    inv_data = pd.DataFrame(inv_ws.get_all_records())
    sales_data = pd.DataFrame(sh.worksheet("Sales_Log").get_all_records())
    
    report = []
    for p in products:
        received = 0
        if not inv_data.empty and p in inv_data.columns:
            received = inv_data[inv_data['Status'] == 'Delivered'][p].sum()
        
        sold = 0
        if not sales_data.empty and 'Product Name' in sales_data.columns:
            sold = sales_data[sales_data['Product Name'] == p]['Quantity Sold'].sum()
        
        report.append({
            "Product": p,
            "Received": received,
            "Sold": sold,
            "Current Stock": received - sold
        })
    
    st.table(pd.DataFrame(report))
