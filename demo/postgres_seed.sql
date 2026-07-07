DROP TABLE IF EXISTS orders_scale;
DROP TABLE IF EXISTS customers_scale;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id integer PRIMARY KEY,
    customer_code text,
    name text,
    state text,
    status text,
    updated_at timestamptz
);

CREATE TABLE orders (
    order_id integer PRIMARY KEY,
    customer_id integer,
    customer_code text,
    status text,
    updated_at timestamptz
);

INSERT INTO customers (id, customer_code, name, state, status, updated_at) VALUES
    (1, ' CUST-001 ', 'Ada Lovelace', 'California', 'ACTIVE', now() - interval '2 hours'),
    (2, 'CUST-002', 'Grace Hopper', 'CA', 'Active', now() - interval '5 hours'),
    (3, 'CUST-003', 'Katherine Johnson', 'Calif.', 'active', now() - interval '30 hours'),
    (4, 'LEGACY', 'Mary Jackson', 'New York', 'PENDING', now() - interval '4 days');

INSERT INTO orders (order_id, customer_id, customer_code, status, updated_at) VALUES
    (1001, 1, 'cust001', 'ACTIVE', now() - interval '1 hour'),
    (1002, 1, 'CUST.001', 'Active', now() - interval '2 hours'),
    (1003, 2, ' cust002 ', 'active', now() - interval '3 hours'),
    (1004, 999, 'UNKNOWN', 'PENDING', now() - interval '2 days');

CREATE TABLE customers_scale AS
SELECT
    gs AS id,
    CASE
        WHEN gs % 10 = 0 THEN ' CUST-' || lpad(gs::text, 6, '0') || ' '
        ELSE 'CUST-' || lpad(gs::text, 6, '0')
    END AS customer_code,
    'Customer ' || gs AS name,
    CASE WHEN gs % 3 = 0 THEN 'California' WHEN gs % 3 = 1 THEN 'CA' ELSE 'Calif.' END AS state,
    CASE WHEN gs % 3 = 0 THEN 'ACTIVE' WHEN gs % 3 = 1 THEN 'Active' ELSE 'active' END AS status,
    now() - ((gs % 96) || ' hours')::interval AS updated_at
FROM generate_series(1, 100000) AS gs;

ALTER TABLE customers_scale ADD PRIMARY KEY (id);

CREATE TABLE orders_scale AS
SELECT
    gs AS order_id,
    CASE WHEN gs % 25000 = 0 THEN 999999 ELSE ((gs % 100000) + 1) END AS customer_id,
    CASE
        WHEN gs % 4 = 0 THEN 'cust' || lpad(((gs % 100000) + 1)::text, 6, '0')
        WHEN gs % 4 = 1 THEN 'CUST.' || lpad(((gs % 100000) + 1)::text, 6, '0')
        ELSE 'CUST-' || lpad(((gs % 100000) + 1)::text, 6, '0')
    END AS customer_code,
    CASE WHEN gs % 3 = 0 THEN 'ACTIVE' WHEN gs % 3 = 1 THEN 'Active' ELSE 'active' END AS status,
    now() - ((gs % 48) || ' hours')::interval AS updated_at
FROM generate_series(1, 250000) AS gs;

ALTER TABLE orders_scale ADD PRIMARY KEY (order_id);
