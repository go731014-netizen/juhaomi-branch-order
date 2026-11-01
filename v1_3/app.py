import pandas as pd
import streamlit as st
from common import (
    config, get_rows, insert_row, load_stores, load_products,
    shipped_totals, derived_status, UNITS, TEMPERATURES, temperature_of
)

st.set_page_config(page_title="揪好覓｜門市叫貨", page_icon="🛒", layout="wide")
st.title("🛒 揪好覓｜門市叫貨")
st.caption("五間門市共用商品清單・依溫層叫貨・查詢叫貨與出貨進度；不顯示庫存數量。")
url, key = config(admin=False)

try:
    stores = load_stores(url, key)
    products = load_products(url, key, active_only=True)
except Exception as e:
    st.error("讀取資料失敗，請確認 Supabase 連線、資料表欄位及讀取權限。")
    st.code(str(e))
    st.stop()

if not stores:
    st.warning("目前讀不到門市資料。請管理者檢查 stores 資料表的 anon SELECT 權限及 RLS 政策；資料表本身可能仍有資料。")
    st.stop()

store_map = {s["store_name"]: s["id"] for s in stores}
branch = st.selectbox("選擇叫貨門市", list(store_map.keys()))
store_id = store_map[branch]

tab_order, tab_add, tab_history = st.tabs(["🧾 我要叫貨", "➕ 新增商品", "📋 叫貨／出貨紀錄"])

with tab_order:
    temp_filter = st.radio("商品溫層", ["全部", *TEMPERATURES], horizontal=True, key="branch_temp_filter")
    keyword = st.text_input("搜尋商品", placeholder="輸入商品名稱、商品編號或條碼")
    filtered = products
    if temp_filter != "全部":
        filtered = [p for p in filtered if temperature_of(p) == temp_filter]
    if keyword:
        k = keyword.strip().lower()
        filtered = [
            p for p in filtered
            if k in str(p.get("product_name", "")).lower()
            or k in str(p.get("product_code", "")).lower()
            or k in str(p.get("barcode", "")).lower()
        ]
    if not filtered:
        st.info("找不到符合條件的啟用商品，可以到「新增商品」登記。")
    else:
        cart = []
        with st.form("order_form"):
            st.write(f"**{branch}｜可叫商品**")
            for p in filtered:
                c1, c2, c3 = st.columns([4, 1.2, 1.5])
                c1.write(f"**{p['product_name']}**")
                c1.caption(f"{temperature_of(p)}｜編號：{p.get('product_code') or '—'}")
                c2.write(p.get("unit") or "個")
                qty = c3.number_input(
                    "叫貨數量", min_value=0, step=1, value=0,
                    key=f"qty_{p['id']}", label_visibility="collapsed"
                )
                if qty > 0:
                    cart.append({"product_id": p["id"], "quantity": int(qty)})
            note = st.text_input("整張叫貨單備註（選填）")
            submitted = st.form_submit_button("送出叫貨單", type="primary", use_container_width=True)
        if submitted:
            if not cart:
                st.warning("請至少輸入一項商品數量。")
            else:
        try:
            for item in cart:
                st.write("測試資料：", item)
                st.write("門市 ID：", store_id)
                insert_row(url, key, "restock_requests", {
                    "store_id": store_id,
                    "product_id": item["product_id"],
                    "current_quantity": 0,
                    "requested_quantity": item["quantity"],
                    "note": note.strip() or None,
                    "status": "pending"
                })
            st.success(f"{branch} 已送出 {len(cart)} 項叫貨申請！")
            st.rerun()
        except Exception as e:
            st.error("送出失敗，請確認 restock_requests 欄位及新增權限。")
            st.code(str(e))
   

with tab_add:
    st.write("新增後立即開放五間門市搜尋及叫貨。新增前請先搜尋，避免重複商品。")
    with st.form("add_product_form", clear_on_submit=True):
        code = st.text_input("商品編號（必填）")
        name = st.text_input("商品名稱（必填）")
        barcode = st.text_input("商品條碼（選填）")
        unit = st.selectbox("計量單位", UNITS)
        temperature = st.selectbox("商品溫層（必選）", TEMPERATURES)
        add = st.form_submit_button("新增並立即開放叫貨", type="primary")
    if add:
        if not code.strip() or not name.strip():
            st.warning("請填寫商品編號及商品名稱。")
        else:
            try:
                exists = get_rows(url, key, "products", {
                    "select": "id", "product_code": f"eq.{code.strip()}", "limit": "1"
                })
                if exists:
                    st.warning("這個商品編號已存在，請勿重複新增。")
                else:
                    insert_row(url, key, "products", {
                        "product_code": code.strip(), "product_name": name.strip(),
                        "barcode": barcode.strip() or None, "unit": unit,
                        "temperature": temperature, "min_stock": 0, "is_active": True
                    })
                    st.success("商品新增成功，已立即開放五間門市叫貨！")
                    st.rerun()
            except Exception as e:
                st.error("新增商品失敗。請確認 products.temperature 欄位及新增權限。")
                st.code(str(e))

with tab_history:
    try:
        records = get_rows(url, key, "restock_requests", {
            "select": "id,product_id,requested_quantity,status,note,created_at",
            "store_id": f"eq.{store_id}", "order": "id.desc", "limit": "200"
        })
        shipments = get_rows(url, key, "shipment_records", {
            "select": "id,restock_request_id,quantity,note,shipped_by,shipped_at",
            "order": "shipped_at.desc", "limit": "3000"
        })
        if records:
            all_products = load_products(url, key, active_only=False)
            pmap = {p["id"]: p for p in all_products}
            totals = shipped_totals(shipments)
            display = []
            for r in records:
                requested = float(r.get("requested_quantity") or 0)
                shipped = totals.get(r["id"], 0.0)
                p = pmap.get(r.get("product_id"), {})
                display.append({
                    "叫貨單號": r.get("id"),
                    "商品": p.get("product_name", f"商品 #{r.get('product_id')}"),
                    "溫層": temperature_of(p),
                    "叫貨數量": requested,
                    "累計出貨": shipped,
                    "剩餘未出貨": max(0, requested - shipped),
                    "出貨狀態": derived_status(requested, shipped),
                    "叫貨備註": r.get("note"),
                    "申請時間": r.get("created_at")
                })
            st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
            st.subheader("每次出貨明細")
            request_ids = {r["id"] for r in records}
            own_shipments = [s for s in shipments if s.get("restock_request_id") in request_ids]
            if own_shipments:
                st.dataframe(pd.DataFrame([{
                    "出貨紀錄編號": s.get("id"), "叫貨單號": s.get("restock_request_id"),
                    "本次出貨數量": s.get("quantity"), "出貨時間": s.get("shipped_at"),
                    "出貨人員": s.get("shipped_by"), "出貨備註": s.get("note")
                } for s in own_shipments]), use_container_width=True, hide_index=True)
            else:
                st.info("目前還沒有出貨紀錄。")
        else:
            st.info("這間門市目前沒有叫貨紀錄。")
    except Exception as e:
        st.error("讀取叫貨／出貨紀錄失敗。請確認 shipment_records 及門市端讀取權限。")
        st.code(str(e))
