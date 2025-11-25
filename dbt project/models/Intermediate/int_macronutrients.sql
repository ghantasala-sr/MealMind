-- Intermediate: Pivot key nutrients for meal planning

{{ config(
    materialized='view'
) }}

SELECT 
    f.fdc_id,
    f.food_name,
    f.category,
    f.data_type,
    MAX(CASE WHEN n.nutrient_name LIKE '%Energy%' THEN fn.nutrient_amount END) AS calories,
    MAX(CASE WHEN n.nutrient_name LIKE '%Protein%' THEN fn.nutrient_amount END) AS protein,
    MAX(CASE WHEN n.nutrient_name LIKE '%Total lipid%' THEN fn.nutrient_amount END) AS total_fat,
    MAX(CASE WHEN n.nutrient_name LIKE '%Carbohydrate%' THEN fn.nutrient_amount END) AS carbohydrate,
    MAX(CASE WHEN n.nutrient_name LIKE '%Fiber%' THEN fn.nutrient_amount END) AS fiber,
    MAX(CASE WHEN n.nutrient_name LIKE '%Sodium%' THEN fn.nutrient_amount END) AS sodium
FROM {{ ref('stg_food') }} f
LEFT JOIN {{ ref('STG_FOOD_NUTRIENTS') }} fn 
    ON f.fdc_id = fn.fdc_id
LEFT JOIN {{ ref('stg_nutrient') }} n 
    ON fn.nutrient_id = n.nutrient_id
WHERE fn.nutrient_amount > 0
GROUP BY f.fdc_id, f.food_name, f.category, f.data_type