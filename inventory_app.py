
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="揪好覓庫存叫貨系統",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 揪好覓｜庫存叫貨系統")
st.caption("總倉・五間門市｜手機簡易操作")

# 從 Streamlit Secrets 讀取設定
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("尚未設定 Supabase 連線資料，請至 Streamlit Secrets 設定。")
    st.stop()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def get_data(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    response = requests.get(
        url,
        headers=HEADERS,
        params=params or {},
        timeout=20
    )
    response.raise_for_status()
    return response.json()

def add_data(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    response = requests.post(
        url,
        headers=HEADERS,
        json=data,
        timeout=20
    )
    response.raise_for_status()
    return response.json()

try:
    stores = get_data(
        "stores",
        {"select": "id,store_name", "order": "id"}
    )
    products = get_data(
        "products",
        {
            "select": "id,product_code,product_name,unit,min_stock,is_active",
            "is_active": "eq.true",
            "order": "product_name"
        }
    )
    stocks = get_data(
        "inventory",
        {"select": "store_id,product_id,quantity"}
    )
    orders = get_data(
        "restock_requests",
        {"select": "*", "order": "id.desc", "limit": "100"}
    )
except Exception as e:
    st.error("讀取資料失敗，請確認 Supabase 資料表與連線設定。")
    st.code(str(e))
    st.stop()

if not stores:
    st.warning("目前 stores 資料表沒有門市資料。")
    st.stop()

store_df = pd.DataFrame(stores)
product_df = pd.DataFrame(products)
stock_df = pd.DataFrame(stocks)

tab1, tab2, tab3 = st.tabs(
    ["📦 門市叫貨", "📊 庫存查詢", "🧾 叫貨紀錄"]
)

with tab1:
    st.subheader("門市補貨申請")

    store_options = {
        row["store_name"]: row["id"]
        for row in stores
    }
    selected_store = st.selectbox(
        "選擇門市",
        list(store_options.keys())
    )
    store_id = store_options[selected_store]

    if product_df.empty:
        st.warning("尚未建立啟用中的商品。")
    else:
        product_options = {
            f'{p["product_name"]}（{p.get("unit") or "個"}）':
            p["id"]
            for p in products
        }

        selected_product = st.selectbox(
            "選擇商品",
            list(product_options.keys())
        )
        product_id = product_options[selected_product]

        match = [
            x for x in stocks
            if x["store_id"] == store_id
            and x["product_id"] == product_id
        ]
        current_qty = float(match[0]["quantity"]) if match else 0

        st.metric("目前庫存", f"{current_qty:g}")

        with st.form("restock_form"):
            request_qty = st.number_input(
                "申請補貨數量",
                min_value=1,
                step=1,
                value=1
            )
            note = st.text_input("備註（可不填）")
            submitted = st.form_submit_button(
                "📨 送出叫貨申請",
                use_container_width=True
            )

        if submitted:
            try:
                add_data(
                    "restock_requests",
                    {
                        "store_id": store_id,
                        "product_id": product_id,
                        "current_quantity": current_qty,
                        "requested_quantity": request_qty,
                        "note": note,
                        "status": "pending"
                    }
                )
                st.success("叫貨申請已送出！")
                st.rerun()
            except Exception as e:
                st.error("送出失敗，請確認資料表設定。")
                st.code(str(e))

with tab2:
    st.subheader("📊 各門市庫存")

    if stock_df.empty:
        st.info("目前尚無庫存資料。")
    elif not product_df.empty:
        stock_view = stock_df.merge(
            store_df[["id", "store_name"]],
            left_on="store_id",
            right_on="id",
            how="left"
        ).merge(
            product_df[["id", "product_name", "unit"]],
            left_on="product_id",
            right_on="id",
            how="left"
        )

        stock_view = stock_view[
            ["store_name", "product_name", "quantity", "unit"]
        ]
        stock_view.columns = ["門市", "商品", "庫存數量", "單位"]
        st.dataframe(
            stock_view,
            use_container_width=True,
            hide_index=True
        )

with tab3:
    st.subheader("🧾 最近叫貨紀錄")

    if orders:
        order_df = pd.DataFrame(orders)
        order_df = order_df.merge(
            store_df[["id", "store_name"]],
            left_on="store_id",
            right_on="id",
            how="left"
        )
        order_df = order_df.merge(
            product_df[["id", "product_name"]],
            left_on="product_id",
            right_on="id",
            how="left"
        )

        cols = [
            c for c in [
                "id", "store_name", "product_name",
                "current_quantity", "requested_quantity",
                "status", "note", "created_at"
            ]
            if c in order_df.columns
        ]
        order_df = order_df[cols]
        order_df = order_df.rename(columns={
            "id": "單號",
            "store_name": "門市",
            "product_name": "商品",
            "current_quantity": "目前庫存",
            "requested_quantity": "申請數量",
            "status": "狀態",
            "note": "備註",
            "created_at": "申請時間"
        })
        st.dataframe(
            order_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("目前還沒有叫貨紀錄。")

st.caption("揪好覓庫存叫貨系統｜測試版本")
