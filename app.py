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

# --- DATABASE SYNC LOGIC ---
def sync_database_structure():
    with st.spinner("Syncing Database..."):
        # 1. Ensure Product Master exists (Essential for app)
        try:
            ws_prod = sh.worksheet("Product_Master")
        except:
            ws_prod = sh.add_worksheet(title="Product_Master", rows="100", cols="2")
            ws_prod.update('A1', [['Product Name']])
            st.warning("Product_Master created. Please add products there and sync again.")

        # 2. Ensure Slot Master exists
        try:
            sh.worksheet("Slot_Master")
        except:
            ws_slots = sh.add_worksheet(title="Slot_Master", rows="100", cols="2")
            ws_slots.update('A1', [['Slots']])
            ws_slots.update('A2:A4', [['10 PM'], ['12 PM'], ['8 AM']])

        # 3. Get products
        products = sh.worksheet("Product_Master").col_values(1)[1:]
        
        # 4. Handle Current Month Sheet
        month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
        headers = ["Date", "Slot", "Account", "Order Name", "Status"] + products
        
        try:
            ws_inv = sh.worksheet(month_title)
            ws_inv.update('A1', [headers])
        except:
            ws_inv = sh.add_worksheet(title=month_title, rows="1000", cols=str(len(headers) + 5))
            ws_inv.update('A1', [headers])
            old_stock = ["-", "-", "Old Stock", "-", "Delivered"] + [0] * len(products)
            ws_inv.append_row(old_stock)
        
        # 5. Ensure Sales Log exists
        try:
            sh.worksheet("Sales_Log")
        except:
            ws_sales = sh.add_worksheet(title="Sales_Log", rows="1000", cols="5")
            ws_sales.update('A1', [['Date', 'Buyer Name', 'Product Name', 'Quantity Sold']])
            
    st.sidebar.success("Database Synced!")
    st.rerun()

# --- DATA FETCHING (WITH ERROR HANDLING) ---
def get_products():
    try:
        return sh.worksheet("Product_Master").col_values(1)[1:]
    except:
        return []

def get_slots():
    try:
        return sh.worksheet("Slot_Master").col_values(1)[1:]
    except:
        return ["Default Slot"]

def get_inventory_sheet():
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    try:
        return sh.worksheet(month_title)
    except:
        return None

# --- UI SETUP ---
st.set_page_config(page_title="Grocery Dashboard", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("🛠 Admin Tools")
if st.sidebar.button("🔄 Sync/Setup Database"):
    sync_database_structure()

st.sidebar.write("---")
menu = st.sidebar.radio("Navigation", ["Amazon Entry", "Receiver View", "Daily Sales", "Inventory & Summary"])

# Load variables
products = get_products()
slots = get_slots()
inv_ws = get_inventory_sheet()

# Check if DB is ready
if not products or inv_ws is None:
    st.error("⚠️ Database Not Ready")
    st.info("Please click the 'Sync/Setup Database' button in the sidebar to initialize your sheets.")
    st.stop()

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
# --- 2. RECEIVER VIEW (UPDATED) ---
elif menu == "Receiver View":
    st.header("🚚 Receiver's Verification")
    
    data_records = inv_ws.get_all_records()
    if data_records:
        df = pd.DataFrame(data_records)
        
        if 'Status' in df.columns:
            pending = df[df['Status'] == 'Pending']
            
            if pending.empty:
                st.success("🎉 No pending items to receive!")
            else:
                # --- NEW: SLOT SUMMARY TABLE ---
                st.subheader("📊 Total Expected Items (By Slot)")
                selected_summary_slot = st.selectbox("Filter Summary by Slot:", ["All"] + list(pending['Slot'].unique()))
                
                # Filter data for the summary table
                summary_df = pending.copy()
                if selected_summary_slot != "All":
                    summary_df = summary_df[summary_df['Slot'] == selected_summary_slot]
                
                # Calculate totals for products
                totals = summary_df[products].sum().reset_index()
                totals.columns = ['Product Name', 'Total Quantity']
                # Show only products that have a quantity > 0
                totals = totals[totals['Total Quantity'] > 0]
                
                if not totals.empty:
                    st.table(totals)
                else:
                    st.info("No items found for this slot.")

                st.write("---")
                st.subheader("📦 Individual Order Breakdown")
                
                # Display individual expanders (Your existing view)
                for index, row in pending.iterrows():
                    # We use the row index + 2 for Google Sheets (1-based + header)
                    sheet_row_index = index + 2 
                    
                    with st.expander(f"📦 {row.get('Order Name', 'No Name')} (Slot: {row['Slot']})"):
                        st.write(f"**Account:** {row['Account']}")
                        item_found = False
                        for p in products:
                            if row.get(p, 0) > 0:
                                st.write(f"- {p}: **{row[p]}**")
                                item_found = True
                        
                        if not item_found:
                            st.write("No items in this order.")

                        if st.button("Mark Delivered", key=f"recv_{index}"):
                            # Update Status in Column E (5)
                            inv_ws.update_cell(sheet_row_index, 5, "Delivered")
                            st.toast(f"Order {row.get('Order Name')} marked as delivered!")
                            st.rerun()
    else:
        st.info("The inventory sheet is empty.")

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
    data_records = inv_ws.get_all_records()
    inv_data = pd.DataFrame(data_records) if data_records else pd.DataFrame()
    
    if not inv_data.empty:
        st.subheader("📋 Order Statistics")
        total_orders = len(inv_data) - 1
        delivered = len(inv_data[inv_data['Status'] == 'Delivered']) if 'Status' in inv_data.columns else 0
        pending = len(inv_data[inv_data['Status'] == 'Pending']) if 'Status' in inv_data.columns else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Orders", total_orders)
        col2.metric("Delivered", delivered)
        col3.metric("Pending", pending)

    st.subheader("📦 Current Stock Status")
    try:
        sales_records = sh.worksheet("Sales_Log").get_all_records()
        sales_data = pd.DataFrame(sales_records)
    except:
        sales_data = pd.DataFrame()

    report = []
    for p in products:
        received = inv_data[inv_data['Status'] == 'Delivered'][p].sum() if not inv_data.empty and p in inv_data.columns else 0
        sold = sales_data[sales_data['Product Name'] == p]['Quantity Sold'].sum() if not sales_data.empty and 'Product Name' in sales_data.columns else 0
        report.append({"Product": p, "Received": received, "Sold": sold, "Stock": received - sold})
    st.dataframe(pd.DataFrame(report), use_container_width=True)
