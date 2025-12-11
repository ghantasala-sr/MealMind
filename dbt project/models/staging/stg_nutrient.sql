-- Staging: Clean nutrient definitions

SELECT 
    id AS nutrient_id,
    TRIM(name) AS nutrient_name,
    unit_name,
    nutrient_nbr,
    rank_order
FROM {{ source('raw_data', 'raw_nutrient') }}
WHERE name IS NOT NULL