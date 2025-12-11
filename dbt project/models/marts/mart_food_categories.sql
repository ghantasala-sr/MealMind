-- Mart: Category-level nutrition statistics

{{ config(
    materialized='table'
) }}

SELECT 
    category,
    COUNT(DISTINCT fdc_id) AS total_foods,
    ROUND(AVG(calories), 1) AS avg_calories,
    ROUND(AVG(protein), 1) AS avg_protein,
    ROUND(AVG(total_fat), 1) AS avg_fat,
    ROUND(AVG(carbohydrate), 1) AS avg_carbs,
    ROUND(AVG(fiber), 1) AS avg_fiber,
    COUNT(CASE WHEN protein >= 15 THEN 1 END) AS high_protein_foods,
    COUNT(CASE WHEN sodium < 140 THEN 1 END) AS low_sodium_foods
FROM {{ ref('int_macronutrients') }}
WHERE category IS NOT NULL
GROUP BY category
ORDER BY total_foods DESC