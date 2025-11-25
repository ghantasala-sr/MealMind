CREATE OR REPLACE SCHEMA RAW_SCHEMA ;

USE SCHEMA RAW_SCHEMA;

CREATE OR REPLACE STAGE raw_data_stage
  STORAGE_INTEGRATION = s3_int
  URL = 's3://snowflake-mealmind/'
  FILE_FORMAT = my_csv_format;

LIST @raw_data_stage;

-- FOOD - START

CREATE OR REPLACE TABLE raw_food (
    fdc_id INTEGER PRIMARY KEY,
    data_type VARCHAR(50),
    description VARCHAR(1000),
    food_category VARCHAR(1000)
);


-- SELECT $1, $2, $3, $4, $5
-- FROM @raw_data_stage/food.csv
-- LIMIT 10;

COPY INTO raw_food (fdc_id, data_type, description, food_category)
FROM (
    SELECT 
        $1::INTEGER,
        $2::VARCHAR(50),
        $3::VARCHAR(1000),
        $4::VARCHAR(1000),
    FROM @raw_data_stage/food.csv
);

Select * from MEALMINDDATA.RAW_SCHEMA.RAW_FOOD;

-- FOOD - END

-- NUTRIENT - START
CREATE OR REPLACE TABLE raw_nutrient (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200),
    unit_name VARCHAR(50),
    nutrient_nbr FLOAT,
    rank_order FLOAT
);

SELECT $1, $2, $3, $4, $5
FROM @raw_data_stage/nutrient.csv
LIMIT 10;

COPY INTO raw_nutrient (id,name,unit_name,nutrient_nbr,rank_order)
FROM (
    SELECT 
        $1::INTEGER,
        $2::VARCHAR(200),
        $3::VARCHAR(50),
        $4::FLOAT,
        $5::FLOAT
    FROM @raw_data_stage/nutrient.csv
);

Select * from MEALMINDDATA.RAW_SCHEMA.RAW_NUTRIENT;


CREATE OR REPLACE TABLE raw_food_category (
    id INTEGER PRIMARY KEY,
    code VARCHAR(10),
    description VARCHAR(200)
);

COPY INTO raw_food_category (id,code,description)
FROM (
    SELECT 
        $1::INTEGER,
        $2::VARCHAR(10),
        $3::VARCHAR(200),
    FROM @raw_data_stage/food_category.csv
);

Select * from MEALMINDDATA.RAW_SCHEMA.RAW_NUTRIENT;

CREATE OR REPLACE TABLE raw_measure_unit (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);

COPY INTO raw_measure_unit (id,name)
FROM (
    SELECT 
        $1::INTEGER,
        $2::VARCHAR(100),
    FROM @raw_data_stage/measure_unit.csv
);

-- DROP TABLE MEALMINDDATA.RAW_SCHEMA.FOOD;

CREATE OR REPLACE TABLE raw_food_nutrient (
    id INTEGER,
    fdc_id INTEGER,
    nutrient_id INTEGER,
    amount FLOAT,
    data_points INTEGER,
    derivation_id INTEGER,
    min_value FLOAT,
    max_value FLOAT,
    median_value FLOAT,
    loq VARCHAR(50),
    footnote VARCHAR(2000),
    min_year_acquired INTEGER,
    percent_daily_value FLOAT
);

COPY INTO raw_food_nutrient (id,fdc_id,nutrient_id,amount,data_points, derivation_id, min_value,max_value,median_value,loq,footnote,min_year_acquired,percent_daily_value)
FROM (
    SELECT 
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13
    FROM @raw_data_stage/food_nutrient.csv
);

select * from MEALMINDDATA.RAW_SCHEMA.RAW_FOOD_NUTRIENT;


CREATE OR REPLACE TABLE raw_food_portion (
    id INTEGER,
    fdc_id INTEGER,
    seq_num INTEGER,
    amount FLOAT,
    measure_unit_id INTEGER,
    portion_description VARCHAR(200),
    modifier VARCHAR(200),
    gram_weight FLOAT,
    data_points INTEGER,
    footnote VARCHAR(500),
    min_year_acquired INTEGER
);

COPY INTO raw_food_portion (id,fdc_id,seq_num,amount,measure_unit_id,portion_description,modifier,gram_weight,data_points,footnote,min_year_acquired)
FROM (
    SELECT 
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
    FROM @raw_data_stage/food_portion.csv
);

select * from MEALMINDDATA.RAW_SCHEMA.RAW_FOOD_PORTION;



CREATE OR REPLACE VIEW v_food_nutrition_complete AS
SELECT 
    f.fdc_id,
    f.data_type,
    f.description AS food_name,
    fn.nutrient_id,
    n.name AS nutrient_name,
    n.unit_name,
    fn.amount AS nutrient_amount_per_100g,
    fn.data_points,
    fn.min_value,
    fn.max_value
FROM raw_food f
LEFT JOIN raw_food_nutrient fn ON f.fdc_id = fn.fdc_id
LEFT JOIN raw_nutrient n ON fn.nutrient_id = n.id
WHERE f.description IS NOT NULL;

SELECT * from MEALMINDDATA.RAW_SCHEMA.v_food_nutrition_complete;

-- Check actual data_type values
SELECT DISTINCT data_type, COUNT(*) as cnt
FROM MEALMINDDATA.RAW_SCHEMA.RAW_FOOD
GROUP BY data_type;

-- Check NULLs in description
SELECT COUNT(*) as total, 
       COUNT(description) as with_description,
       COUNT(*) - COUNT(description) as null_descriptions
FROM MEALMINDDATA.RAW_SCHEMA.RAW_FOOD;