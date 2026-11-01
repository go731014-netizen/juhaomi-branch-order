-- 揪好覓叫貨系統 V1.2：新增分批出貨明細表
-- 只新增 shipment_records，不修改既有 stores / products / inventory / restock_requests。

create table if not exists public.shipment_records (
    id bigserial primary key,
    restock_request_id bigint not null references public.restock_requests(id) on delete restrict,
    quantity numeric(12, 2) not null check (quantity > 0),
    note text,
    shipped_by text,
    shipped_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index if not exists idx_shipment_records_request_id
    on public.shipment_records (restock_request_id);

create index if not exists idx_shipment_records_shipped_at
    on public.shipment_records (shipped_at desc);

alter table public.shipment_records enable row level security;

-- 門市端目前採「免登入、由使用者自行選擇分店」的設計，
-- 因此此政策允許公開讀取出貨明細，門市 App 再依所選分店顯示資料。
-- 注意：沒有員工登入驗證，就無法在資料庫層真正隔離各分店資料。
drop policy if exists "public can read shipment records" on public.shipment_records;
create policy "public can read shipment records"
    on public.shipment_records for select
    to anon, authenticated
    using (true);

-- 只有管理端使用 service_role key 寫入；service_role 會略過 RLS。
grant select on public.shipment_records to anon, authenticated;
grant all on public.shipment_records to service_role;
grant usage, select on sequence public.shipment_records_id_seq to service_role;
