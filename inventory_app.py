
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
    st.subheader("🏬 美術館店（總倉）庫存")

    if stock_df.empty:
        st.info("目前尚無庫存資料。")
    elif product_df.empty:
        st.info("目前尚無商品資料。")
    else:
        warehouse_id = 3

        warehouse_stock = stock_df[
            stock_df["store_id"] == warehouse_id
        ].merge(
            product_df[["id", "product_name", "unit"]],
            left_on="product_id",
            right_on="id",
            how="left"
        )

        warehouse_stock = warehouse_stock[
            ["product_name", "quantity", "unit"]
        ]
        warehouse_stock.columns = ["商品", "總倉庫存數量", "單位"]

        st.dataframe(
            warehouse_stock,
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

            # 取得美術館店（總倉）的庫存
            warehouse_id = 3
            warehouse_qty = stock_df[
                stock_df["store_id"] == warehouse_id
            ][["product_id", "quantity"]].rename(
                columns={"quantity": "總倉庫存"}
            )

            order_df = order_df.merge(
                warehouse_qty,
                on="product_id",
                how="left"
            )

            order_df["current_quantity"] = (
                order_df["總倉庫存"].fillna(0)
            )
            order_df = order_df.drop(columns=["總倉庫存"])


})



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

# ===== 商品管理 =====
st.divider()
st.header("🛠️ 商品管理")
st.subheader("➕ 新增商品")

with st.form("add_product_form", clear_on_submit=True):
    product_code = st.text_input("商品編號（必填）")
    product_name = st.text_input("商品名稱（必填）")
    barcode = st.text_input("商品條碼（沒有可留空）")
    unit = st.selectbox(
        "計量單位",
        ["個", "包", "盒", "袋", "瓶", "罐", "斤", "公斤", "箱"]
    )
    min_stock = st.number_input(
        "最低庫存提醒數量",
        min_value=0,
        value=0,
        step=1
    )

    submitted = st.form_submit_button("💾 新增商品")

    if submitted:
        if not product_code.strip() or not product_name.strip():
            st.warning("請填寫商品編號和商品名稱。")
        else:
            try:
                new_product = {
                    "product_code": product_code.strip(),
                    "product_name": product_name.strip(),
                    "barcode": barcode.strip() or None,
                    "unit": unit,
                    "min_stock": int(min_stock),
                    "is_active": True
                }
                add_data("products", new_product)
                st.success("商品新增成功！")
                st.rerun()
            except Exception as e:
                st.error("新增失敗，請確認商品編號是否重複。")
                st.code(str(e))
st.divider()
st.subheader("📋 商品清單")

try:
    product_list = get_data(
        "products",
        {
            "select": "id,product_code,product_name,barcode,unit,min_stock,is_active",
            "order": "id.desc"
        }
    )

    if product_list:
        product_df = pd.DataFrame(product_list)
        product_df = product_df.rename(columns={
            "id": "編號",
            "product_code": "商品編號",
            "product_name": "商品名稱",
            "barcode": "商品條碼",
            "unit": "單位",
            "min_stock": "最低庫存提醒",
            "is_active": "啟用中"
        })
        st.dataframe(
            product_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("目前還沒有商品資料。")

except Exception as e:
    st.error("讀取商品清單失敗，請確認資料庫設定。")
    st.code(str(e))
# ===== 商品啟用狀態管理 =====
st.divider()
st.subheader("🔧 商品啟用／停用管理")

try:
    all_products = get_data(
        "products",
        {
            "select": "id,product_code,product_name,is_active",
            "order": "id.desc"
        }
    )

    if all_products:
        product_options = {
            f'{p["product_code"]}｜{p["product_name"]}｜'
            f'{"啟用中" if p["is_active"] else "已停用"}': p
            for p in all_products
        }

        selected_label = st.selectbox(
            "選擇要管理的商品",
            list(product_options.keys())
        )
        selected_item = product_options[selected_label]

        st.write(
            "目前狀態：",
            "啟用中" if selected_item["is_active"] else "已停用"
        )

        if selected_item["is_active"]:
            if st.button("⏸️ 停用此商品", use_container_width=True):
                response = requests.patch(
                    f'{SUPABASE_URL}/rest/v1/products?id=eq.{selected_item["id"]}',
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    json={"is_active": False},
                    timeout=20
                )
                response.raise_for_status()
                st.success("商品已停用！")
                st.rerun()
        else:
            if st.button("▶️ 重新啟用此商品", use_container_width=True):
                response = requests.patch(
                    f'{SUPABASE_URL}/rest/v1/products?id=eq.{selected_item["id"]}',
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    json={"is_active": True},
                    timeout=20
                )
                response.raise_for_status()
                st.success("商品已重新啟用！")
                st.rerun()
    else:
        st.info("目前沒有商品資料。")

except Exception as e:
    st.error("商品狀態更新失敗，請確認資料庫連線。")
    st.code(str(e))
# ===== 商品資料修改 =====
st.divider()
st.subheader("✏️ 修改商品資料")

try:
    edit_products = get_data(
        "products",
        {
            "select": "id,product_code,product_name,barcode,unit,min_stock,is_active",
            "order": "id.desc"
        }
    )

    if edit_products:
        edit_options = {
            f'{p["product_code"]} | {p["product_name"]}': p
            for p in edit_products
        }

        edit_label = st.selectbox(
            "選擇要修改的商品",
            list(edit_options.keys()),
            key="edit_product_select"
        )
        edit_product = edit_options[edit_label]

        with st.form("edit_product_form"):
            edit_name = st.text_input(
                "商品名稱",
                value=edit_product["product_name"] or ""
            )
            edit_barcode = st.text_input(
                "商品條碼",
                value=edit_product["barcode"] or ""
            )
            edit_unit = st.selectbox(
                "計量單位",
                ["個", "包", "盒", "袋", "瓶", "罐", "斤", "公斤", "箱"],
                index=(
                    ["個", "包", "盒", "袋", "瓶", "罐", "斤", "公斤", "箱"].index(
                        edit_product["unit"]
                    )
                    if edit_product["unit"] in
                    ["個", "包", "盒", "袋", "瓶", "罐", "斤", "公斤", "箱"]
                    else 0
                )
            )
            edit_min_stock = st.number_input(
                "最低庫存提醒數量",
                min_value=0,
                value=int(edit_product["min_stock"] or 0),
                step=1
            )

            save_edit = st.form_submit_button("💾 儲存修改")

            if save_edit:
                if not edit_name.strip():
                    st.warning("商品名稱不可空白。")
                else:
                    response = requests.patch(
                        f'{SUPABASE_URL}/rest/v1/products?id=eq.{edit_product["id"]}',
                        headers={**HEADERS, "Prefer": "return=minimal"},
                        json={
                            "product_name": edit_name.strip(),
                            "barcode": edit_barcode.strip() or None,
                            "unit": edit_unit,
                            "min_stock": int(edit_min_stock)
                        },
                        timeout=20
                    )
                    response.raise_for_status()
                    st.success("商品資料修改成功！")
                    st.rerun()
    else:
        st.info("目前沒有商品資料。")

except Exception as e:
    st.error("修改商品資料失敗，請確認資料庫連線。")
    st.code(str(e))
