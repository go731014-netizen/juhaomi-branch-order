
import hmac
import pandas as pd
import streamlit as st

from common import (
    config, get_rows, insert_row, patch_row,
    load_stores, load_products,
    shipped_totals, derived_status,
    UNITS, TEMPERATURES, temperature_of
)

st.set_page_config(
    page_title="揪好覓｜門市叫貨與總倉管理",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 揪好覓｜雲端叫貨管理")
st.caption("五間門市共用商品清單・總倉統一管理・分批出貨紀錄")

# ==================================================
# 主要分頁
# ==================================================

tab_branch, tab_admin = st.tabs(["🏪 門市叫貨", "👑 總倉管理"])

# ==================================================
# 門市叫貨
# ==================================================

with tab_branch:
    st.subheader("🏪 門市叫貨")

    try:
        url, key = config(admin=False)
        stores = load_stores(url, key)
        products = load_products(url, key, active_only=True)
    except Exception:
        st.error("讀取門市資料失敗，請確認 Supabase 連線及讀取權限。")
        stores, products = [], []

    if stores:
        store_map = {s["store_name"]: s["id"] for s in stores}
        branch = st.selectbox("選擇叫貨門市", list(store_map.keys()))
        store_id = store_map[branch]

        tab_order, tab_add, tab_history = st.tabs(
            ["🧾 我要叫貨", "➕ 新增商品", "📋 叫貨／出貨紀錄"]
        )

        # ------------------------------
        # 我要叫貨
        # ------------------------------

        with tab_order:
            temp_filter = st.radio(
                "商品溫層",
                ["全部", *TEMPERATURES],
                horizontal=True,
                key="branch_temp_filter"
            )

            keyword = st.text_input(
                "搜尋商品",
                placeholder="輸入商品名稱、商品編號或條碼",
                key="branch_search"
            )

            filtered = products

            if temp_filter != "全部":
                filtered = [
                    p for p in filtered
                    if temperature_of(p) == temp_filter
                ]

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
                        c1.caption(
                            f"{temperature_of(p)}｜編號：{p.get('product_code') or '—'}"
                        )
                        c2.write(p.get("unit") or "個")

                        qty = c3.number_input(
                            "叫貨數量",
                            min_value=0,
                            step=1,
                            value=0,
                            key=f"qty_{p['id']}",
                            label_visibility="collapsed"
                        )

                        if qty > 0:
                            cart.append({
                                "product_id": p["id"],
                                "quantity": int(qty)
                            })

                    note = st.text_input("整張叫貨單備註（選填）")

                    submitted = st.form_submit_button(
                        "送出叫貨單",
                        type="primary",
                        use_container_width=True
                    )

                if submitted:
                    if not cart:
                        st.warning("請至少輸入一項商品數量。")
                    else:
                        try:
                            for item in cart:
                                insert_row(
                                    url, key, "restock_requests",
                                    {
                                        "store_id": store_id,
                                        "product_id": item["product_id"],
                                        "current_quantity": 0,
                                        "requested_quantity": item["quantity"],
                                        "note": note.strip() or None,
                                        "status": "pending"
                                    }
                                )

                            st.success(
                                f"{branch} 已送出 {len(cart)} 項叫貨申請！"
                            )
                        except Exception as e:
                            st.error("送出失敗，請確認資料表欄位及新增權限。")
                            st.code(str(e))

        # ------------------------------
        # 新增商品
        # ------------------------------

        with tab_add:
            st.write(
                "新增後立即開放五間門市搜尋及叫貨。"
                "新增前請先搜尋，避免重複商品。"
            )

            with st.form("add_product_form", clear_on_submit=True):
                code = st.text_input("商品編號（必填）")
                name = st.text_input("商品名稱（必填）")
                barcode = st.text_input("商品條碼（選填）")
                unit = st.selectbox("計量單位", UNITS)
                temperature = st.selectbox("商品溫層（必選）", TEMPERATURES)

                add = st.form_submit_button(
                    "新增並立即開放叫貨",
                    type="primary"
                )

            if add:
                if not code.strip() or not name.strip():
                    st.warning("請填寫商品編號及商品名稱。")
                else:
                    try:
                        exists = get_rows(
                            url, key, "products",
                            {
                                "select": "id",
                                "product_code": f"eq.{code.strip()}",
                                "limit": "1"
                            }
                        )

                        if exists:
                            st.warning("這個商品編號已存在，請勿重複新增。")
                        else:
                            insert_row(
                                url, key, "products",
                                {
                                    "product_code": code.strip(),
                                    "product_name": name.strip(),
                                    "barcode": barcode.strip() or None,
                                    "unit": unit,
                                    "temperature": temperature,
                                    "min_stock": 0,
                                    "is_active": True
                                }
                            )
                            st.success("商品新增成功，已立即開放五間門市叫貨！")
                            st.rerun()

                    except Exception as e:
                        st.error("新增商品失敗，請確認 products 資料表欄位及權限。")
                        st.code(str(e))

        # ------------------------------
        # 叫貨／出貨紀錄
        # ------------------------------

        with tab_history:
            try:
                records = get_rows(
                    url, key, "restock_requests",
                    {
                        "select": "id,product_id,requested_quantity,status,note,created_at",
                        "store_id": f"eq.{store_id}",
                        "order": "id.desc",
                        "limit": "200"
                    }
                )

                if records:
                    all_products = load_products(
                        url, key, active_only=False
                    )
                    pmap = {p["id"]: p for p in all_products}

                    request_ids = {r["id"] for r in records}

                    shipments = get_rows(
                        url, key, "shipment_records",
                        {
                            "select": "id,restock_request_id,quantity,note,shipped_by,shipped_at",
                            "restock_request_id": "in.(" + ",".join(
                                str(i) for i in request_ids
                            ) + ")",
                            "order": "shipped_at.desc",
                            "limit": "3000"
                        }
                    )

                    totals = shipped_totals(shipments)
                    display = []

                    for r in records:
                        requested = float(r.get("requested_quantity") or 0)
                        shipped = totals.get(r["id"], 0.0)
                        p = pmap.get(r.get("product_id"), {})

                        display.append({
                            "叫貨單號": r.get("id"),
                            "商品": p.get("product_name", "未知商品"),
                            "溫層": temperature_of(p),
                            "叫貨數量": requested,
                            "累計出貨": shipped,
                            "剩餘未出貨": max(0, requested - shipped),
                            "出貨狀態": derived_status(requested, shipped),
                            "叫貨備註": r.get("note"),
                            "申請時間": r.get("created_at")
                        })

                    st.dataframe(
                        pd.DataFrame(display),
                        use_container_width=True,
                        hide_index=True
                    )

                    st.subheader("每次出貨明細")

                    if shipments:
                        st.dataframe(
                            pd.DataFrame([
                                {
                                    "出貨紀錄編號": s.get("id"),
                                    "叫貨單號": s.get("restock_request_id"),
                                    "本次出貨數量": s.get("quantity"),
                                    "出貨時間": s.get("shipped_at"),
                                    "出貨人員": s.get("shipped_by"),
                                    "出貨備註": s.get("note")
                                }
                                for s in shipments
                            ]),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("目前還沒有出貨紀錄。")
                else:
                    st.info("這間門市目前沒有叫貨紀錄。")

            except Exception as e:
                st.error("讀取叫貨／出貨紀錄失敗，請確認相關資料表及讀取權限。")
                st.code(str(e))
    else:
        st.warning("目前讀不到門市資料，請管理者檢查 stores 資料表。")

# ==================================================
# 總倉管理
# ==================================================

with tab_admin:
    st.subheader("👑 總倉管理")

    admin_password = st.secrets.get("ADMIN_PASSWORD", "")

    if not admin_password:
        st.error("尚未設定 ADMIN_PASSWORD，請至 Streamlit Secrets 設定。")

    elif not st.session_state.get("admin_ok", False):
        st.write("此區僅供闆娘及授權管理人員使用。")

        with st.form("admin_login_form"):
            entered_password = st.text_input(
                "管理者密碼",
                type="password"
            )
            login = st.form_submit_button(
                "登入總倉管理",
                type="primary"
            )

        if login:
            if hmac.compare_digest(entered_password, admin_password):
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("管理密碼不正確，請再試一次。")

    else:
        if st.button("🔒 登出總倉管理"):
            st.session_state["admin_ok"] = False
            st.rerun()

        # 只有通過密碼驗證後，才讀取管理端金鑰
        try:
            admin_url, admin_key = config(admin=True)

            admin_stores = load_stores(admin_url, admin_key)
            admin_products = load_products(
                admin_url, admin_key, active_only=False
            )

            orders = get_rows(
                admin_url, admin_key, "restock_requests",
                {
                    "select": "*",
                    "order": "id.desc",
                    "limit": "1000"
                }
            )

            shipments = get_rows(
                admin_url, admin_key, "shipment_records",
                {
                    "select": "id,restock_request_id,quantity,note,shipped_by,shipped_at",
                    "order": "shipped_at.desc",
                    "limit": "3000"
                }
            )

        except Exception as e:
            st.error(
                "管理資料讀取失敗。請確認管理金鑰、資料表及欄位設定。"
            )
            st.code(str(e))
            orders, shipments = [], []
            admin_stores, admin_products = [], []

        if admin_stores:
            store_map = {
                s["id"]: s["store_name"] for s in admin_stores
            }
            product_map = {
                p["id"]: p["product_name"] for p in admin_products
            }
            totals = shipped_totals(shipments)

            admin_tab_orders, admin_tab_ship, admin_tab_history, admin_tab_products = st.tabs(
                [
                    "📋 全部叫貨紀錄",
                    "🚚 登記出貨",
                    "🧾 出貨歷史",
                    "🛠️ 商品管理"
                ]
            )

            # ------------------------------
            # 全部叫貨紀錄
            # ------------------------------

            with admin_tab_orders:
                rows = []

                for o in orders:
                    requested = float(o.get("requested_quantity") or 0)
                    shipped = totals.get(o["id"], 0.0)

                    rows.append({
                        "叫貨單號": o.get("id"),
                        "門市": store_map.get(o.get("store_id"), "未知門市"),
                        "商品": product_map.get(
                            o.get("product_id"),
                            f"商品 #{o.get('product_id')}"
                        ),
                        "叫貨數量": requested,
                        "累計出貨": shipped,
                        "剩餘未出貨": max(0, requested - shipped),
                        "出貨狀態": derived_status(requested, shipped),
                        "叫貨備註": o.get("note"),
                        "申請時間": o.get("created_at")
                    })

                if rows:
                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("目前沒有叫貨紀錄。")

            # ------------------------------
            # 登記出貨
            # ------------------------------

            with admin_tab_ship:
                pending = []

                for o in orders:
                    requested = float(o.get("requested_quantity") or 0)
                    shipped = totals.get(o["id"], 0.0)
                    remaining = max(0.0, requested - shipped)

                    if remaining > 1e-9:
                        label = (
                            f"#{o['id']}｜"
                            f"{store_map.get(o.get('store_id'), '未知門市')}｜"
                            f"{product_map.get(o.get('product_id'), '未知商品')}｜"
                            f"剩餘 {remaining:g}"
                        )
                        pending.append((label, o, remaining))

                if not pending:
                    st.success("目前沒有待出貨或部分出貨的叫貨項目。")
                else:
                    labels = [x[0] for x in pending]
                    selected_label = st.selectbox(
                        "選擇要出貨的叫貨項目",
                        labels
                    )

                    _, order, remaining = next(
                        x for x in pending if x[0] == selected_label
                    )

                    requested = float(order.get("requested_quantity") or 0)
                    already = totals.get(order["id"], 0.0)

                    st.write(
                        f"**門市：** {store_map.get(order.get('store_id'), '未知門市')}"
                    )
                    st.write(
                        f"**商品：** {product_map.get(order.get('product_id'), '未知商品')}"
                    )
                    st.write(
                        f"**原叫貨數量：** {requested:g}　"
                        f"｜ **累計已出：** {already:g}　"
                        f"｜ **剩餘：** {remaining:g}"
                    )

                    with st.form("shipment_form", clear_on_submit=True):
                        qty = st.number_input(
                            "本次實際出貨數量",
                            min_value=0.01,
                            max_value=float(remaining),
                            value=float(remaining),
                            step=1.0
                        )
                        shipped_by = st.text_input("出貨人員（選填）")
                        note = st.text_area("本次出貨備註（選填）")

                        submit_ship = st.form_submit_button(
                            "確認登記本次出貨",
                            type="primary"
                        )

                    if submit_ship:
                        if qty <= 0 or qty > remaining + 1e-9:
                            st.error(
                                f"出貨數量不可超過剩餘數量 {remaining:g}。"
                            )
                        else:
                            try:
                                insert_row(
                                    admin_url, admin_key,
                                    "shipment_records",
                                    {
                                        "restock_request_id": order["id"],
                                        "quantity": float(qty),
                                        "note": note.strip() or None,
                                        "shipped_by": shipped_by.strip() or None
                                    }
                                )
                                st.success("本次出貨已登記，歷史紀錄已保留。")
                                st.rerun()
                            except Exception as e:
                                st.error("出貨登記失敗，請確認出貨資料表。")
                                st.code(str(e))

            # ------------------------------
            # 出貨歷史
            # ------------------------------

            with admin_tab_history:
                if shipments:
                    order_map = {o["id"]: o for o in orders}
                    rows = []

                    for s in shipments:
                        o = order_map.get(
                            s.get("restock_request_id"), {}
                        )

                        rows.append({
                            "出貨紀錄編號": s.get("id"),
                            "叫貨單號": s.get("restock_request_id"),
                            "門市": store_map.get(
                                o.get("store_id"), "未知門市"
                            ),
                            "商品": product_map.get(
                                o.get("product_id"), "未知商品"
                            ),
                            "本次出貨數量": s.get("quantity"),
                            "出貨時間": s.get("shipped_at"),
                            "出貨人員": s.get("shipped_by"),
                            "出貨備註": s.get("note")
                        })

                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("目前還沒有出貨紀錄。")

            # ------------------------------
 
            with admin_tab_products:
                st.subheader("商品清單")

                if admin_products:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "商品編號": p.get("product_code"),
                                "商品名稱": p.get("product_name"),
                                "條碼": p.get("barcode"),
                                "單位": p.get("unit"),
                                "溫層": temperature_of(p),
                                "啟用中": p.get("is_active")
                            }
                            for p in admin_products
                        ]),
                        use_container_width=True,
                        hide_index=True
                    )

                    opts = {
                        f"{p.get('product_code')}｜{p.get('product_name')}｜ID {p['id']}": p
                        for p in admin_products
                    }

                    selected_label = st.selectbox(
                        "選擇商品修改",
                        list(opts.keys()),
                        key="admin_product_select"
                    )

                    item = opts[selected_label]

                    with st.form(
                        "edit_product_form",
                        clear_on_submit=False
                    ):
                        name = st.text_input(
                            "商品名稱",
                            value=item.get("product_name") or "",
                            key=f"edit_name_{item['id']}"
                        )

                        barcode = st.text_input(
                            "商品條碼",
                            value=item.get("barcode") or "",
                            key=f"edit_barcode_{item['id']}"
                        )

                        unit = st.selectbox(
                            "計量單位",
                            UNITS,
                            index=(
                                UNITS.index(item.get("unit"))
                                if item.get("unit") in UNITS else 0
                            ),
                            key=f"edit_unit_{item['id']}"
                        )

                        temperature = st.selectbox(
                            "商品溫層",
                            TEMPERATURES,
                            index=(
                                TEMPERATURES.index(item.get("temperature"))
                                if item.get("temperature") in TEMPERATURES else 2
                            ),
                            key=f"edit_temperature_{item['id']}"
                        )

                        min_stock = st.number_input(
                            "最低庫存欄位",
                            min_value=0,
                            value=int(item.get("min_stock") or 0),
                            key=f"edit_min_stock_{item['id']}"
                        )

                        active = st.checkbox(
                            "啟用商品（啟用後門市可叫貨）",
                            value=bool(item.get("is_active")),
                            key=f"edit_active_{item['id']}"
                        )

                        save = st.form_submit_button(
                            "儲存商品修改"
                        )

                    if save:
                        try:
                            patch_row(
                                admin_url,
                                admin_key,
                                "products",
                                {"id": f"eq.{item['id']}"},
                                {
                                    "product_name": name.strip(),
                                    "barcode": barcode.strip() or None,
                                    "unit": unit,
                                    "temperature": temperature,
                                    "min_stock": int(min_stock),
                                    "is_active": active
                                }
                            )

                            st.success("商品資料已更新。")
                            st.rerun()

                        except Exception as e:
                            st.error("商品修改失敗。")
                            st.code(str(e))

                else:
                    st.info("目前沒有商品。")
          
