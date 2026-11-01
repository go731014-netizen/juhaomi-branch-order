import pandas as pd
import streamlit as st
from common import config, get_rows, insert_row, load_stores, load_products, shipped_totals, derived_status, UNITS

st.set_page_config(page_title="揪好覓｜門市叫貨", page_icon="🛒", layout="wide")
st.title("🛒 揪好覓｜門市叫貨")
st.caption("門市叫貨、查詢自己的叫貨與出貨進度；不顯示任何庫存數量。")
url, key = config(admin=False)

try:
    stores = load_stores(url, key)
    products = load_products(url, key, active_only=True)
except Exception as e:
    st.error("讀取資料失敗，請確認 Supabase 連線及資料表讀取權限。")
    st.code(str(e))
    st.stop()

if not stores:
    st.warning("stores 資料表目前沒有門市資料。")
    st.stop()

store_map = {s["store_name"]: s["id"] for s in stores}
branch = st.selectbox("選擇叫貨門市", list(store_map.keys()))
store_id = store_map[branch]

tab_order, tab_add, tab_history = st.tabs(["🧾 我要叫貨", "➕ 新增商品", "📋 叫貨／出貨紀錄"])

with tab_order:
    keyword = st.text_input("搜尋商品", placeholder="輸入商品名稱、商品編號或條碼")
    filtered = products
    if keyword:
        k = keyword.strip().lower()
        filtered = [p for p in products if k in str(p.get("product_name", "")).lower()
                    or k in str(p.get("product_code", "")).lower()
                    or k in str(p.get("barcode", "")).lower()]
    if not filtered:
        st.info("找不到符合的啟用商品，可以到「新增商品」登記。")
    else:
        cart = []
        with st.form("order_form"):
            st.write(f"**{branch}｜可叫商品**")
            for p in filtered:
                c1, c2, c3 = st.columns([4, 1.2, 1.5])
                c1.write(f"**{p['product_name']}**")
                c1.caption(f"編號：{p.get('product_code') or '—'}")
                c2.write(p.get("unit") or "個")
                qty = c3.number_input("叫貨數量", min_value=0, step=1, value=0,
                                      key=f"qty_{p['id']}", label_visibility="collapsed")
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
                        "min_stock": 0, "is_active": True
                    })
                    st.success("商品新增成功，已立即開放五間門市叫貨！")
                    st.rerun()
            except Exception as e:
                st.error("新增商品失敗，請確認 products 欄位及新增權限。")
                st.code(str(e))

with tab_history:
    try:
        records = get_rows(url, key, "restock_requests", {
            "select": "id,product_id,requested_quantity,status,note,created_at",
            "store_id": f"eq.{store_id}", "order": "id.desc", "limit": "200"
        })
        shipments = get_rows(url, key, "shipment_records", {
            "select": "id,restock_request_id,quantity,note,shipped_by,shipped_at",
            "order": "shipped_at.desc", "limit": "1000"
        })
        if records:
            pmap = {p["id"]: p["product_name"] for p in load_products(url, key, active_only=False)}
            totals = shipped_totals(shipments)
            display = []
            for r in records:
                requested = float(r.get("requested_quantity") or 0)
                shipped = totals.get(r["id"], 0.0)
                display.append({
                    "叫貨單號": r.get("id"),
                    "商品": pmap.get(r.get("product_id"), f"商品 #{r.get('product_id')}"),
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
        st.error("讀取叫貨／出貨紀錄失敗。請先確認已建立 shipment_records 資料表，且門市端具有讀取權限。")
        st.code(str(e))
