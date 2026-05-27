import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os
from datetime import datetime

# --- CONFIG ---
SHEET_NAME = "Grocery_Management_System"
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def load_creds():
    if "gcp_service_account" in os.environ:
        try:
            creds_json = os.environ.get("gcp_service_account")
            if creds_json.startswith("'") and creds_json.endswith("'"):
                creds_json = creds_json[1:-1]
            return Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPE)
        except: pass
    if os.path.exists("google_creds.json"):
        return Credentials.from_service_account_file("google_creds.json", scopes=SCOPE)
    st.error("Credentials not found.")
    st.stop()

# --- INIT ---
creds = load_creds()
client = gspread.authorize(creds)
sh = client.open(SHEET_NAME)

# --- DATABASE SYNC LOGIC (The "Setup" Button) ---
def sync_database_structure():
    with st.spinner("Syncing Database..."):
        # 1. Ensure Slot Master exists
        try:
            ws_slots = sh.worksheet("Slot_Master")
        except:
            ws_slots = sh.add_worksheet(title="Slot_Master", rows="100", cols="2")
            ws_slots.update('A1', [['Slots']])
            ws_slots.update('A2:A4', [['10 PM'], ['12 PM'], ['8 AM']])

        # 2. Get the master product list
        products = sh.worksheet("Product_Master").col_values(1)[1:]
        
        # 3. Handle Current Month Sheet
        month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
        headers = ["Date", "Slot", "Account", "Order Name", "Status"] + products
        
        try:
            ws_inv = sh.worksheet(month_title)
            # Update headers in case products were added
            ws_inv.update('A1', [headers])
        except:
            ws_inv = sh.add_worksheet(title=month_title, rows="1000", cols=str(len(headers) + 5))
            ws_inv.update('A1', [headers])
            # Add Initial Old Stock row
            old_stock = ["-", "-", "Old Stock", "-", "Delivered"] + [0] * len(products)
            ws_inv.append_row(old_stock)
        
        # 4. Ensure Sales Log exists
        try:
            sh.worksheet("Sales_Log")
        except:
            ws_sales = sh.add_worksheet(title="Sales_Log", rows="1000", cols="5")
            ws_sales.update('A1', [['Date', 'Buyer Name', 'Product Name', 'Quantity Sold']])
            
    st.sidebar.success("Database Synced Successfully!")

# --- UI SETUP ---
st.set_page_config(page_title="Grocery Dashboard", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("🛠 Admin Tools")
if st.sidebar.button("🔄 Sync/Setup Database"):
    sync_database_structure()

st.sidebar.write("---")
menu = st.sidebar.radio("Navigation", ["Amazon Entry", "Receiver View", "Daily Sales", "Inventory & Summary"])

# --- LOAD DATA ---
def get_products():
    return sh.worksheet("Product_Master").col_values(1)[1:]

def get_slots():
    return sh.worksheet("Slot_Master").col_values(1)[1:]

def get_inventory_sheet():
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    try:
        return sh.worksheet(month_title)
    except:
        st.warning("Current month sheet not found. Please click 'Sync Database' in the sidebar.")
        st.stop()

products = get_products()
slots = get_slots()
inv_ws = get_inventory_sheet()

# --- 1. AMAZON ENTRY ---
if menu == "Amazon Entry":
    st.header("📦 Amazon Order Input")
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        date = col1.date_input("Order Date")
        slot = col2.selectbox("Slot", slots)
        
        col3, col4 = st.columns(2)
        acc = col3.text_input("Account Name")
        order_name = col4.text_input("Order Name")
        
        st.write("---")
        input_data = []
        cols = st.columns(3)
        for i, p in enumerate(products):
            with cols[i % 3]:
                input_data.append(st.number_input(f"{p}", min_value=0, step=1, key=f"in_{p}"))
        
        if st.form_submit_button("Log Order"):
            row = [str(date), slot, acc, order_name, "Pending"] + input_data
            inv_ws.append_row(row)
            st.success(f"Order '{order_name}' logged!")

# --- 2. RECEIVER VIEW ---
elif menu == "Receiver View":
    st.header("🚚 Receiver's Verification")
    data = inv_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        if 'Status' in df.columns:
            pending = df[df['Status'] == 'Pending']
            if pending.empty:
                st.info("No pending orders.")
            else:
                for index, row in pending.iterrows():
                    with st.expander(f"📦 {row.get('Order Name', 'Unknown')} (Slot: {row['Slot']})"):
                        st.write(f"**Account:** {row['Account']}")
                        for p in products:
                            if row.get(p, 0) > 0:
                                st.write(f"- {p}: {row[p]}")
                        
                        if st.button("Mark Delivered", key=f"btn_{index}"):
                            # Status is Column E (5)
                            inv_ws.update_cell(index + 2, 5, "Delivered")
                            st.rerun()

# --- 3. DAILY SALES ---
elif menu == "Daily Sales":
    st.header("💰 Sales Log")
    with st.form("sales"):
        buyer = st.selectbox("Buyer", ["Rajkumar da", "Souvik da", "Gourab", "Other"])
        prod = st.selectbox("Product", products)
        qty = st.number_input("Qty", min_value=1)
        if st.form_submit_button("Log Sale"):
            sh.worksheet("Sales_Log").append_row([str(datetime.now().date()), buyer, prod, qty])
            st.success("Sale Recorded")

# --- 4. INVENTORY & SUMMARY ---
elif menu == "Inventory & Summary":
    st.header("📊 Stock & Order Summary")
    inv_data = pd.DataFrame(inv_ws.get_all_records())
    
    if not inv_data.empty:
        st.subheader("📋 Order Statistics")
        total_orders = len(inv_data) - 1
        delivered = len(inv_data[inv_data['Status'] == 'Delivered'])
        pending = len(inv_data[inv_data['Status'] == 'Pending'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Orders", total_orders)
        col2.metric("Delivered", delivered)
        col3.metric("Pending", pending)

    st.subheader("📦 Current Stock Status")
    try:
        sales_data = pd.DataFrame(sh.worksheet("Sales_Log").get_all_records())
    except:
        sales_data = pd.DataFrame()

    report = []
    for p in products:
        received = inv_data[inv_data['Status'] == 'Delivered'][p].sum() if not inv_data.empty and p in inv_data.columns else 0
        sold = sales_data[sales_data['Product Name'] == p]['Quantity Sold'].sum() if not sales_data.empty and 'Product Name' in sales_data.columns else 0
        report.append({"Product": p, "Received": received, "Sold": sold, "Stock": received - sold})
    
    st.dataframe(pd.DataFrame(report), use_container_width=True)
