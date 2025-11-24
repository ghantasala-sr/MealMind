-- Staging: Clean serving size data

SELECT 
    id AS portion_id,
    fdc_id,
    portion_description,
    gram_weight,
    measure_unit_id,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw_data', 'raw_food_portion') }}
WHERE fdc_id IS NOT NULL
  AND gram_weight IS NOT NULL
  AND gram_weight > 0