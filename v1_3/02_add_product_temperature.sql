-- 揪好覓叫貨系統 V1.3：為 products 新增商品溫層欄位
-- 只新增欄位、限制條件與索引，不刪除既有商品或叫貨資料。
-- 舊商品會自動先歸類為「常溫」，管理者可再到管理端調整。

alter table public.products
    add column if not exists temperature text not null default '常溫';

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'products_temperature_check'
          and conrelid = 'public.products'::regclass
    ) then
        alter table public.products
            add constraint products_temperature_check
            check (temperature in ('冷凍', '冷藏', '常溫'));
    end if;
end
$$;

create index if not exists idx_products_temperature
    on public.products (temperature);
