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
    st.stop()

# --- INIT ---
creds = load_creds()
client = gspread.authorize(creds)
sh = client.open(SHEET_NAME)

def get_products():
    return sh.worksheet("Product_Master").col_values(1)[1:]

def get_slots():
    return sh.worksheet("Slot_Master").col_values(1)[1:]

def get_inventory_sheet():
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    return sh.worksheet(month_title)

# --- UI ---
st.set_page_config(page_title="Grocery Dashboard", layout="wide")
menu = st.sidebar.radio("Menu", ["Amazon Entry", "Receiver View", "Daily Sales", "Inventory & Summary"])

products = get_products()
slots = get_slots()
inv_ws = get_inventory_sheet()

# 1. AMAZON ENTRY
if menu == "Amazon Entry":
    st.header("📦 Amazon Order Input")
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        date = col1.date_input("Order Date")
        slot = col2.selectbox("Slot", slots)
        
        col3, col4 = st.columns(2)
        acc = col3.text_input("Account Name")
        order_name = col4.text_input("Order Name (e.g. Order #123)")
        
        st.write("---")
        input_data = []
        cols = st.columns(3)
        for i, p in enumerate(products):
            with cols[i % 3]:
                input_data.append(st.number_input(f"{p}", min_value=0, step=1, key=f"in_{p}"))
        
        if st.form_submit_button("Log Order"):
            # Format: Date, Slot, Account, Order Name, Status, Products...
            row = [str(date), slot, acc, order_name, "Pending"] + input_data
            inv_ws.append_row(row)
            st.success("Order Logged!")

# 2. RECEIVER VIEW
elif menu == "Receiver View":
    st.header("🚚 Receiver's Verification")
    data = inv_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        pending = df[df['Status'] == 'Pending']
        
        if pending.empty:
            st.info("No pending orders.")
        else:
            for index, row in pending.iterrows():
                # Title uses Order Name now
                with st.expander(f"📦 {row['Order Name']} (Slot: {row['Slot']})"):
                    st.write(f"**Account:** {row['Account']}")
                    for p in products:
                        if row.get(p, 0) > 0:
                            st.write(f"- {p}: {row[p]}")
                    
                    if st.button("Mark Delivered", key=f"btn_{index}"):
                        # Status is now Column E (5)
                        inv_ws.update_cell(index + 2, 5, "Delivered")
                        st.rerun()

# 3. DAILY SALES
elif menu == "Daily Sales":
    st.header("💰 Sales Log")
    with st.form("sales"):
        buyer = st.selectbox("Buyer", ["Rajkumar da", "Souvik da", "Gourab", "Other"])
        prod = st.selectbox("Product", products)
        qty = st.number_input("Qty", min_value=1)
        if st.form_submit_button("Log Sale"):
            sh.worksheet("Sales_Log").append_row([str(datetime.now().date()), buyer, prod, qty])
            st.success("Sale Recorded")

# 4. INVENTORY & SUMMARY
elif menu == "Inventory & Summary":
    st.header("📊 Stock & Order Summary")
    inv_data = pd.DataFrame(inv_ws.get_all_records())
    
    # --- Part A: Order Summary Table ---
    st.subheader("📋 Order Statistics")
    if not inv_data.empty:
        total_orders = len(inv_data) - 1 # excluding old stock row
        delivered_orders = len(inv_data[inv_data['Status'] == 'Delivered'])
        pending_orders = len(inv_data[inv_data['Status'] == 'Pending'])
        
        summary_df = pd.DataFrame({
            "Metric": ["Total Orders Placed", "Delivered", "Pending Verification"],
            "Count": [total_orders, delivered_orders, pending_orders]
        })
        st.table(summary_df)
        
        # Orders per slot
        st.write("**Orders per Slot:**")
        slot_counts = inv_data['Slot'].value_counts()
        st.bar_chart(slot_counts)

    # --- Part B: Product Stock ---
    st.subheader("📦 Product Stock Status")
    sales_data = pd.DataFrame(sh.worksheet("Sales_Log").get_all_records())
    report = []
    for p in products:
        received = inv_data[inv_data['Status'] == 'Delivered'][p].sum() if not inv_data.empty else 0
        sold = sales_data[sales_data['Product Name'] == p]['Quantity Sold'].sum() if not sales_data.empty else 0
        report.append({"Product": p, "Received": received, "Sold": sold, "Stock": received - sold})
    st.dataframe(pd.DataFrame(report), use_container_width=True)
