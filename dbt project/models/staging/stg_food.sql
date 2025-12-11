SELECT 
    fdc_id,
    data_type,
    LOWER(TRIM(description)) AS food_name,  -- Convert to lowercase
    food_category AS category
FROM {{ source('raw_data', 'raw_food') }}
WHERE description IS NOT NULL
  AND description != ''
  AND fdc_id IS NOT NULL