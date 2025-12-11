-- Intermediate: Join food with nutrients

{{ config(
    materialized='view'
) }}

SELECT 
    f.fdc_id,
    f.food_name,
    f.category,
    f.data_type,
    fn.nutrient_id,
    n.nutrient_name,
    n.unit_name,
    fn.nutrient_amount AS amount_per_100g,
    fn.data_points,
    fn.min_value,
    fn.max_value
FROM {{ ref('stg_food') }} f
LEFT JOIN {{ ref('STG_FOOD_NUTRIENTS') }} fn ON f.fdc_id = fn.fdc_id
LEFT JOIN {{ ref('stg_nutrient') }} n ON fn.nutrient_id = n.nutrient_id
WHERE fn.nutrient_amount IS NOT NULL