-- Staging: Clean and standardize food-nutrient relationship data

WITH source AS (
    SELECT * FROM {{ source('raw_data', 'raw_food_nutrient') }}
),

cleaned AS (
    SELECT
        -- IDs
        id AS food_nutrient_id,
        fdc_id,
        nutrient_id,
        
        -- Measurements
        COALESCE(amount, 0) AS nutrient_amount,
        data_points,
        
        -- Statistical values
        min_value,
        max_value,
        median_value,
        
        -- Daily value percentage
        percent_daily_value,
        
        -- Metadata
        CURRENT_TIMESTAMP() AS _loaded_at
        
    FROM source
    WHERE fdc_id IS NOT NULL
      AND nutrient_id IS NOT NULL
      AND amount >= 0  -- Filter out negative values
)

SELECT * FROM cleaned