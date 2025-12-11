-- Mart: Complete meal planning view with dietary filters and unique food names

{{ config(
    materialized='table',
    unique_key='food_name',
    on_schema_change='sync_all_columns'
) }}

WITH base_nutrients AS (
    SELECT 
        fdc_id,
        LOWER(TRIM(food_name)) AS food_name,  -- Convert to lowercase and trim spaces
        -- Check if category is numeric and replace with 'Uncategorized'
        CASE 
            WHEN REGEXP_LIKE(category, '^[0-9]+$') THEN 'Uncategorized'
            WHEN category IS NULL THEN 'Uncategorized'
            WHEN category = '' THEN 'Uncategorized'
            ELSE category
        END AS category,
        data_type,
        calories,
        protein,
        total_fat,
        carbohydrate,
        fiber,
        sodium
    FROM {{ ref('int_macronutrients') }}
    WHERE fdc_id IS NOT NULL  -- Filter out null FDC_IDs
      AND calories IS NOT NULL
      AND protein IS NOT NULL
      AND food_name IS NOT NULL
),

-- Remove duplicates by keeping the record with the highest FDC_ID for each unique food name
deduplicated AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY food_name  -- Group by lowercase food_name
            ORDER BY 
                -- Prioritize records with more complete data
                CASE 
                    WHEN fiber IS NOT NULL AND sodium IS NOT NULL THEN 1
                    WHEN fiber IS NOT NULL OR sodium IS NOT NULL THEN 2
                    ELSE 3
                END,
                fdc_id DESC  -- Then by highest FDC_ID (typically newer/more recent)
        ) AS rn
    FROM base_nutrients
)

SELECT 
    fdc_id,
    food_name,
    category,
    data_type,
    calories,
    protein,
    total_fat,
    carbohydrate,
    fiber,
    sodium,
    -- Dietary restriction flags
    CASE 
        WHEN COALESCE(category, '') NOT ILIKE '%beef%' 
        AND COALESCE(category, '') NOT ILIKE '%pork%' 
        AND COALESCE(category, '') NOT ILIKE '%poultry%'
        AND COALESCE(category, '') NOT ILIKE '%fish%' 
        AND COALESCE(category, '') NOT ILIKE '%meat%'
        AND COALESCE(category, '') NOT ILIKE '%chicken%'
        AND COALESCE(category, '') NOT ILIKE '%turkey%'
        AND COALESCE(category, '') NOT ILIKE '%lamb%'
        AND COALESCE(category, '') NOT ILIKE '%seafood%'
        AND category NOT IN ('Poultry Products', 'Pork Products', 'Beef Products', 
                             'Finfish and Shellfish Products', 'Lamb, Veal, and Game Products',
                             'Sausages and Luncheon Meats')
        THEN TRUE 
        ELSE FALSE 
    END AS vegetarian_friendly,
    CASE 
        WHEN sodium < 140 THEN TRUE 
        ELSE FALSE 
    END AS low_sodium,
    CASE 
        WHEN protein >= 15 THEN TRUE 
        ELSE FALSE 
    END AS high_protein,
    CASE 
        WHEN carbohydrate <= 25 THEN TRUE 
        ELSE FALSE 
    END AS low_carb,
    CASE 
        WHEN total_fat < 5 THEN TRUE 
        ELSE FALSE 
    END AS low_fat,
    -- Calorie density classification
    CASE 
        WHEN calories < 100 THEN 'Very Low' 
        WHEN calories BETWEEN 100 AND 200 THEN 'Low'
        WHEN calories BETWEEN 200 AND 400 THEN 'Moderate'
        WHEN calories > 400 THEN 'High'
    END AS calorie_density
FROM deduplicated
WHERE rn = 1  -- Keep only one record per unique food name