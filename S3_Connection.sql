CREATE OR REPLACE DATABASE MealMindData;



CREATE OR REPLACE STORAGE INTEGRATION s3_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::219494607505:role/mysnowflakerole'
  STORAGE_ALLOWED_LOCATIONS = ('s3://snowflake-mealmind/');

DESC INTEGRATION s3_int;

CREATE OR REPLACE FILE FORMAT my_csv_format
  TYPE = 'CSV'
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  NULL_IF = ('NULL', 'null', '')
  EMPTY_FIELD_AS_NULL = TRUE
  FIELD_OPTIONALLY_ENCLOSED_BY = '"';

CREATE OR REPLACE STAGE raw_data_stage
  STORAGE_INTEGRATION = s3_int
  URL = 's3://snowflake-mealmind/'
  FILE_FORMAT = my_csv_format;

LIST @raw_data_stage;



SELECT 
    CURRENT_USER() as username,
    CURRENT_ROLE() as role,
    CURRENT_WAREHOUSE() as warehouse,
    CURRENT_DATABASE() as database,
    CURRENT_SCHEMA() as schema,
    CURRENT_REGION() as region,
    CURRENT_ACCOUNT() as account;