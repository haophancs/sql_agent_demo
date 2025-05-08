-- Here are some sample queries for the inventory management system

-- <query description>
-- Top 10 best-selling products by quantity for the past month
-- </query description>
-- <query>
SELECT 
    dp.product_name,
    dp.category,
    SUM(fs.quantity_sold) AS total_quantity_sold,
    SUM(fs.net_price) AS total_revenue
FROM 
    FACT_SALES fs
JOIN 
    DIM_PRODUCT dp ON fs.product_id = dp.product_id
JOIN 
    DIM_DATE dd ON fs.date_id = dd.date_id
WHERE 
    dd.full_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 
    dp.product_id, dp.product_name, dp.category
ORDER BY 
    total_quantity_sold DESC
LIMIT 10;
-- </query>

-- <query description>
-- Store performance comparison: monthly sales, YTD, and year-over-year growth
-- </query description>
-- <query>
WITH monthly_sales AS (
    SELECT 
        ds.store_id,
        ds.store_name,
        dd.year,
        dd.month,
        SUM(fs.net_price) AS monthly_revenue
    FROM 
        FACT_SALES fs
    JOIN 
        DIM_STORE ds ON fs.store_id = ds.store_id
    JOIN 
        DIM_DATE dd ON fs.date_id = dd.date_id
    GROUP BY 
        ds.store_id, ds.store_name, dd.year, dd.month
),
ytd_sales AS (
    SELECT 
        store_id,
        store_name,
        year,
        SUM(monthly_revenue) AS ytd_revenue
    FROM 
        monthly_sales
    WHERE 
        (year = EXTRACT(YEAR FROM CURRENT_DATE) AND month <= EXTRACT(MONTH FROM CURRENT_DATE))
    GROUP BY 
        store_id, store_name, year
),
prev_year_sales AS (
    SELECT 
        store_id,
        store_name,
        year + 1 AS year,
        SUM(monthly_revenue) AS prev_year_revenue
    FROM 
        monthly_sales
    WHERE 
        year = EXTRACT(YEAR FROM CURRENT_DATE) - 1
    GROUP BY 
        store_id, store_name, year
)

SELECT 
    y.store_id,
    y.store_name,
    y.year,
    y.ytd_revenue,
    p.prev_year_revenue,
    (y.ytd_revenue - p.prev_year_revenue) / p.prev_year_revenue * 100 AS yoy_growth_percent
FROM 
    ytd_sales y
LEFT JOIN 
    prev_year_sales p ON y.store_id = p.store_id AND y.year = p.year
ORDER BY 
    yoy_growth_percent DESC;
-- </query>

-- <query description>
-- Inventory stockout analysis: Products with the most frequent stockouts in the last quarter
-- </query description>
-- <query>
SELECT 
    dp.product_id,
    dp.product_name,
    dp.category,
    COUNT(fi.inventory_id) AS stockout_count,
    AVG(fi.days_of_supply) AS avg_days_of_supply
FROM 
    FACT_INVENTORY fi
JOIN 
    DIM_PRODUCT dp ON fi.product_id = dp.product_id
JOIN 
    DIM_DATE dd ON fi.date_id = dd.date_id
WHERE 
    fi.is_stockout = TRUE
    AND dd.quarter = (
        SELECT quarter 
        FROM DIM_DATE 
        WHERE full_date = (CURRENT_DATE - INTERVAL '1 day')
    )
GROUP BY 
    dp.product_id, dp.product_name, dp.category
ORDER BY 
    stockout_count DESC
LIMIT 20;
-- </query>

-- <query description>
-- Employee sales performance ranking by store and department
-- </query description>
-- <query>
SELECT 
    ds.store_name,
    de.department,
    de.employee_name,
    SUM(fs.net_price) AS total_sales,
    SUM(fs.profit_margin) AS total_profit,
    COUNT(DISTINCT fs.customer_id) AS customers_served,
    RANK() OVER (
        PARTITION BY ds.store_id, de.department 
        ORDER BY SUM(fs.net_price) DESC
    ) AS department_rank
FROM 
    FACT_SALES fs
JOIN 
    DIM_EMPLOYEE de ON fs.employee_id = de.employee_id
JOIN 
    DIM_STORE ds ON fs.store_id = ds.store_id
JOIN 
    DIM_DATE dd ON fs.date_id = dd.date_id
WHERE 
    dd.year = EXTRACT(YEAR FROM CURRENT_DATE)
    AND dd.month = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY 
    ds.store_id, ds.store_name, de.department, de.employee_name
ORDER BY 
    ds.store_name, de.department, department_rank;
-- </query>

-- <query description>
-- Supplier reliability analysis: Average lead time and late deliveries by supplier
-- </query description>
-- <query>
SELECT 
    ds.supplier_name,
    COUNT(fpo.po_id) AS total_orders,
    AVG(fpo.lead_time_days) AS avg_lead_time,
    SUM(CASE 
            WHEN fpo.actual_delivery_date > fpo.expected_delivery_date 
            THEN 1 ELSE 0 
        END) AS late_deliveries,
    ROUND(
        SUM(CASE 
                WHEN fpo.actual_delivery_date > fpo.expected_delivery_date 
                THEN 1 ELSE 0 
            END)::FLOAT / COUNT(fpo.po_id) * 100, 
        2
    ) AS late_delivery_percentage,
    AVG(
        CASE 
            WHEN fpo.actual_delivery_date > fpo.expected_delivery_date 
            THEN (fpo.actual_delivery_date - fpo.expected_delivery_date) 
            ELSE 0 
        END
    ) AS avg_days_late
FROM 
    FACT_PURCHASE_ORDERS fpo
JOIN 
    DIM_SUPPLIER ds ON fpo.supplier_id = ds.supplier_id
WHERE 
    fpo.actual_delivery_date IS NOT NULL
    AND fpo.po_status = 'Delivered'
GROUP BY 
    ds.supplier_name
ORDER BY 
    late_delivery_percentage DESC;
-- </query>

-- <query description>
-- Top 10 most profitable product categories by season
-- </query description>
-- <query>
SELECT 
    dd.season,
    dp.category,
    SUM(fs.quantity_sold) AS total_units_sold,
    SUM(fs.net_price) AS total_revenue,
    SUM(fs.profit_margin) AS total_profit,
    ROUND(SUM(fs.profit_margin) / SUM(fs.net_price) * 100, 2) AS profit_margin_percentage
FROM 
    FACT_SALES fs
JOIN 
    DIM_PRODUCT dp ON fs.product_id = dp.product_id
JOIN 
    DIM_DATE dd ON fs.date_id = dd.date_id
WHERE 
    dd.year = EXTRACT(YEAR FROM CURRENT_DATE)
GROUP BY 
    dd.season, dp.category
ORDER BY 
    dd.season, total_profit DESC;
-- </query>

-- <query description>
-- Customer purchase frequency and average basket analysis
-- </query description>
-- <query>
WITH customer_purchases AS (
    SELECT 
        dc.customer_id,
        dc.customer_name,
        dc.loyalty_segment,
        COUNT(DISTINCT fs.transaction_id) AS purchase_count,
        COUNT(fs.sale_id) AS total_items_purchased,
        SUM(fs.net_price) AS total_spent,
        MIN(dd.full_date) AS first_purchase,
        MAX(dd.full_date) AS last_purchase
    FROM 
        FACT_SALES fs
    JOIN 
        DIM_CUSTOMER dc ON fs.customer_id = dc.customer_id
    JOIN 
        DIM_DATE dd ON fs.date_id = dd.date_id
    WHERE 
        dd.full_date >= CURRENT_DATE - INTERVAL '365 days'
    GROUP BY 
        dc.customer_id, dc.customer_name, dc.loyalty_segment
)

SELECT 
    customer_id,
    customer_name,
    loyalty_segment,
    purchase_count,
    total_items_purchased,
    total_spent,
    ROUND(total_spent / purchase_count, 2) AS avg_basket_value,
    ROUND(total_items_purchased::FLOAT / purchase_count, 2) AS avg_items_per_purchase,
    (CURRENT_DATE - last_purchase) AS days_since_last_purchase,
    ROUND(365::FLOAT / purchase_count, 1) AS avg_days_between_purchases
FROM 
    customer_purchases
ORDER BY 
    total_spent DESC
LIMIT 100;
-- </query>

-- <query description>
-- Promotion effectiveness analysis by product category
-- </query description>
-- <query>
SELECT 
    dp.promotion_name,
    dp.promotion_type,
    dp.discount_percent,
    dpr.category,
    COUNT(fs.sale_id) AS items_sold,
    SUM(fs.quantity_sold) AS total_quantity,
    SUM(fs.net_price) AS revenue_after_discount,
    SUM(fs.discount_amount) AS total_discount_amount,
    ROUND(SUM(fs.discount_amount) / (SUM(fs.net_price) + SUM(fs.discount_amount)) * 100, 2) AS discount_percentage,
    ROUND(SUM(fs.profit_margin) / SUM(fs.net_price) * 100, 2) AS profit_margin_percentage
FROM 
    FACT_SALES fs
JOIN 
    DIM_PROMOTION dp ON fs.promotion_id = dp.promotion_id
JOIN 
    DIM_PRODUCT dpr ON fs.product_id = dpr.product_id
WHERE 
    fs.promotion_id IS NOT NULL
GROUP BY 
    dp.promotion_name, dp.promotion_type, dp.discount_percent, dpr.category
ORDER BY 
    dpr.category, total_discount_amount DESC;
-- </query>

-- <query description>
-- Inventory turnover ratio by product category
-- </query description>
-- <query>
WITH inventory_data AS (
    SELECT 
        dp.category,
        AVG(fi.ending_quantity) AS avg_inventory,
        SUM(fi.sold_quantity) AS total_sold
    FROM 
        FACT_INVENTORY fi
    JOIN 
        DIM_PRODUCT dp ON fi.product_id = dp.product_id
    JOIN 
        DIM_DATE dd ON fi.date_id = dd.date_id
    WHERE 
        dd.full_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY 
        dp.category
)

SELECT 
    category,
    avg_inventory,
    total_sold,
    ROUND(total_sold / NULLIF(avg_inventory, 0), 2) AS inventory_turnover,
    CASE 
        WHEN (total_sold / NULLIF(avg_inventory, 0)) > 0 
        THEN ROUND(90 / (total_sold / NULLIF(avg_inventory, 0)), 1)
        ELSE NULL
    END AS days_of_supply
FROM 
    inventory_data
ORDER BY 
    inventory_turnover DESC;
-- </query>

-- <query description>
-- Employee performance metrics with customer satisfaction correlation
-- </query description>
-- <query>
SELECT 
    de.employee_name,
    de.position,
    ds.store_name,
    ROUND(AVG(fep.sales_amount), 2) AS avg_daily_sales,
    ROUND(AVG(fep.transactions_processed), 2) AS avg_daily_transactions,
    ROUND(AVG(fep.avg_scan_time), 2) AS avg_scan_time_seconds,
    ROUND(AVG(fep.customer_satisfaction_score), 2) AS avg_satisfaction_score,
    ROUND(
        CORR(fep.avg_scan_time, fep.customer_satisfaction_score), 
        3
    ) AS scan_time_satisfaction_correlation
FROM 
    FACT_EMPLOYEE_PERFORMANCE fep
JOIN 
    DIM_EMPLOYEE de ON fep.employee_id = de.employee_id
JOIN 
    DIM_STORE ds ON fep.store_id = ds.store_id
WHERE 
    fep.customer_satisfaction_score IS NOT NULL
GROUP BY 
    de.employee_name, de.position, ds.store_name
HAVING 
    COUNT(fep.performance_id) >= 30  -- Ensure statistical significance
ORDER BY 
    avg_satisfaction_score DESC;
-- </query>

