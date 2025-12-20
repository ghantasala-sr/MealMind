import streamlit as st
import snowflake.connector
import json
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import tempfile

# Load environment variables
load_dotenv()

# Snowflake connection configuration
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "MEAL_MIND_COMBINED"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "RAW_SCHEMA"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
}

st.set_page_config(page_title="Inventory Image Upload", layout="wide")
st.title("📦 Inventory Management - Snowflake Cortex Multimodal")

def standardize_unit(quantity, unit, item_name=""):
    """Convert quantity to standardized metric units (gm, kg, ml, l)"""
    unit_lower = unit.lower().strip()
    item_lower = item_name.lower()
    
    # Weight conversions to grams
    weight_conversions = {
        'g': (1, 'gm'),
        'gm': (1, 'gm'),
        'gram': (1, 'gm'),
        'grams': (1, 'gm'),
        'kg': (1000, 'gm'),
        'kilogram': (1000, 'gm'),
        'kilograms': (1000, 'gm'),
        'oz': (28.35, 'gm'),
        'ounce': (28.35, 'gm'),
        'ounces': (28.35, 'gm'),
        'lb': (453.592, 'gm'),
        'lbs': (453.592, 'gm'),
        'pound': (453.592, 'gm'),
        'pounds': (453.592, 'gm'),
    }
    
    # Volume conversions to ml
    volume_conversions = {
        'ml': (1, 'ml'),
        'milliliter': (1, 'ml'),
        'milliliters': (1, 'ml'),
        'l': (1000, 'ml'),
        'liter': (1000, 'ml'),
        'liters': (1000, 'ml'),
        'litre': (1000, 'ml'),
        'litres': (1000, 'ml'),
        'fl oz': (29.5735, 'ml'),
        'fluid ounce': (29.5735, 'ml'),
        'cup': (236.588, 'ml'),
        'cups': (236.588, 'ml'),
        'pint': (473.176, 'ml'),
        'pints': (473.176, 'ml'),
        'gallon': (3785.41, 'ml'),
        'gallons': (3785.41, 'ml'),
        'tbsp': (14.787, 'ml'),
        'tablespoon': (14.787, 'ml'),
        'tablespoons': (14.787, 'ml'),
        'tsp': (4.929, 'ml'),
        'teaspoon': (4.929, 'ml'),
        'teaspoons': (4.929, 'ml'),
    }
    
    # Container types that typically hold liquids (convert to ml)
    liquid_containers = ['carton', 'bottle', 'can', 'glass', 'cup', 'jug', 'pitcher']
    
    # Item keywords that indicate liquid/weight-based products
    liquid_keywords = ['milk', 'juice', 'kombucha', 'water', 'beverage', 'drink', 'oil', 'sauce', 'syrup', 'yogurt', 'cream', 'almond']
    weight_keywords = ['supplement', 'vitamin', 'powder', 'flour', 'sugar', 'salt', 'coffee', 'tea']
    
    # Check if it's a liquid/volume item based on item name
    is_liquid_item = any(keyword in item_lower for keyword in liquid_keywords)
    is_weight_item = any(keyword in item_lower for keyword in weight_keywords)
    is_liquid_container = any(container in unit_lower for container in liquid_containers)
    
    # If it's a liquid container (carton, bottle, can) but not a count unit, convert to ml
    if is_liquid_container and not any(c in unit_lower for c in ['pieces', 'items', 'box', 'bunch']):
        # Assume standard volumes for common containers
        container_defaults = {
            'carton': 946,  # 1 quart in ml (typical milk carton)
            'bottle': 500,  # 500ml (typical bottle)
            'can': 355,     # 355ml (typical can)
            'glass': 240,   # 240ml (typical glass)
        }
        
        for container, default_ml in container_defaults.items():
            if container in unit_lower:
                return round(quantity * default_ml, 2), 'ml'
    
    # If it's explicitly a liquid item, prefer ml
    if is_liquid_item and is_liquid_container:
        return round(quantity * 500, 2), 'ml'  # Default to 500ml per container
    
    # Try to find conversion in standard tables
    if unit_lower in weight_conversions:
        multiplier, std_unit = weight_conversions[unit_lower]
        return round(quantity * multiplier, 2), std_unit
    elif unit_lower in volume_conversions:
        multiplier, std_unit = volume_conversions[unit_lower]
        return round(quantity * multiplier, 2), std_unit
    else:
        # Default: treat as pieces (count-based)
        return quantity, 'pieces'

def get_existing_users():
    """Fetch list of existing users from Snowflake"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT USER_ID FROM MEAL_MIND_COMBINED.RAW_SCHEMA.USERS ORDER BY USER_ID")
        users = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return users
    except Exception as e:
        st.warning(f"Could not fetch users: {e}")
        return []

def get_snowflake_connection():
    """Establish Snowflake connection"""
    try:
        conn = snowflake.connector.connect(
            account=SNOWFLAKE_CONFIG["account"],
            warehouse=SNOWFLAKE_CONFIG["warehouse"],
            database=SNOWFLAKE_CONFIG["database"],
            schema=SNOWFLAKE_CONFIG["schema"],
            user=SNOWFLAKE_CONFIG["user"],
            password=SNOWFLAKE_CONFIG["password"],
        )
        return conn
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def setup_image_stage(conn):
    """Create or verify image stage exists"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE OR REPLACE STAGE inventory_images
            DIRECTORY = ( ENABLE = true )
            ENCRYPTION = ( TYPE = 'SNOWFLAKE_SSE' )
        """)
        cursor.close()
        return True
    except Exception as e:
        st.error(f"Error setting up stage: {e}")
        return False

def extract_inventory_multimodal(image_data: bytes, user_id: str):
    """Extract inventory using Snowflake Cortex AI_COMPLETE multimodal"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    # Setup stage
    if not setup_image_stage(conn):
        return None
    
    cursor = conn.cursor()
    
    # Save image temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name
    
    try:
        # Generate unique filename
        filename = f"inventory_{int(datetime.utcnow().timestamp())}.jpg"
        
        # Upload image to stage using PUT command
        put_cmd = f"PUT 'file://{tmp_path}' @inventory_images AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        st.write(f"Executing: {put_cmd}")
        cursor.execute(put_cmd)
        
        # Verify file was uploaded by listing stage
        cursor.execute("LIST @inventory_images")
        files = cursor.fetchall()
        st.write(f"Files in stage: {files}")
        
        if not files:
            st.error("Upload failed - no files in stage")
            cursor.close()
            conn.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return None
        
        st.success(f"✅ Uploaded image: {filename}")
        
        # Define the prompt
        prompt = "Analyze this refrigerator/inventory image and extract all items visible. For each item, provide: item_name, quantity (as number), unit (pieces/boxes/kg/liters/etc), and category. Return ONLY a valid JSON array with no markdown. Example: [{\"item_name\": \"Lettuce\", \"quantity\": 1, \"unit\": \"pieces\", \"category\": \"Produce\"}]"
        
        # Use AI_COMPLETE with TO_FILE - this is the correct syntax
        st.info("🔄 Processing image with Snowflake Cortex Claude 3.5 Sonnet...")
        
        # Get the actual filename from the uploaded file
        actual_filename = files[0][0].split('/')[-1]
        st.write(f"Using file: {actual_filename}")
        
        query = f"""SELECT AI_COMPLETE('claude-3-5-sonnet', 
            '{prompt}',
            TO_FILE('@inventory_images', '{actual_filename}')
        ) as extraction_result"""
        
        cursor.execute(query)
        result = cursor.fetchone()
        
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        
        if result:
            response_text = result[0]
            st.write("**Raw Response:**")
            st.code(response_text, language="json")
            
            try:
                # The response might be a JSON string wrapped in another string
                # First, unescape it if needed
                cleaned = response_text.strip()
                
                # If it's a string that starts with quotes, it's double-encoded
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    cleaned = cleaned[1:-1]  # Remove outer quotes
                    cleaned = cleaned.replace('\\n', '\n')  # Unescape newlines
                    cleaned = cleaned.replace('\\\"', '"')  # Unescape quotes
                
                # Remove markdown code blocks if present
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                
                cleaned = cleaned.strip()
                
                # Parse JSON
                items = json.loads(cleaned)
                
                # Ensure items is a list
                if isinstance(items, dict):
                    items = [items]
                elif not isinstance(items, list):
                    st.error(f"Unexpected response format: {type(items)}")
                    st.write(f"Content: {items}")
                    return None
                
                cursor.close()
                conn.close()
                return items
                
            except json.JSONDecodeError as je:
                st.error(f"Failed to parse JSON: {je}")
                return None
        
        cursor.close()
        conn.close()
        return None
        
    except Exception as e:
        st.error(f"Error during extraction: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        cursor.close()
        conn.close()
        return None

def add_inventory_to_snowflake(user_id, items):
    """Add extracted items to Snowflake inventory table with standardized units"""
    conn = get_snowflake_connection()
    if not conn:
        return 0
    
    try:
        cursor = conn.cursor()
        inserted_count = 0
        
        for item in items:
            inventory_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            # Standardize the unit and quantity
            quantity = item.get("quantity", 0)
            unit = item.get("unit", "pieces")
            item_name = item.get("item_name", "")
            std_quantity, std_unit = standardize_unit(quantity, unit, item_name)
            
            insert_query = """
            INSERT INTO INVENTORY (INVENTORY_ID, USER_ID, ITEM_NAME, QUANTITY, UNIT, CATEGORY, CREATED_AT, UPDATED_AT)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(
                insert_query,
                (
                    inventory_id,
                    user_id,
                    item.get("item_name", "Unknown"),
                    std_quantity,
                    std_unit,
                    item.get("category", "Uncategorized"),
                    now,
                    now,
                ),
            )
            inserted_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        return inserted_count
    except Exception as e:
        st.error(f"Error updating Snowflake: {e}")
        return 0

def get_existing_users():
    """Fetch list of existing users from Snowflake"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT USER_ID FROM MEAL_MIND_COMBINED.RAW_SCHEMA.USERS ORDER BY USER_ID")
        users = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return users
    except Exception as e:
        st.warning(f"Could not fetch users: {e}")
        return []

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    st.subheader("Snowflake Settings")
    
    account = st.text_input("Account ID", value=SNOWFLAKE_CONFIG["account"] or "", key="account_input")
    warehouse = st.text_input("Warehouse", value=SNOWFLAKE_CONFIG["warehouse"] or "", key="warehouse_input")
    username = st.text_input("Username", value=SNOWFLAKE_CONFIG["user"] or "", key="user_input")
    password = st.text_input("Password", type="password", value=SNOWFLAKE_CONFIG["password"] or "", key="pass_input")
    
    if st.button("Test Connection"):
        conn = get_snowflake_connection()
        if conn:
            st.success("✅ Connection successful!")
            conn.close()
        else:
            st.error("❌ Connection failed!")

# Main interface
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 Upload Inventory Image")
    
    existing_users = get_existing_users()
    
    # User ID input
    user_input_type = st.radio("Select USER_ID:", ["Choose from existing", "Enter manually"])
    
    if user_input_type == "Choose from existing":
        if existing_users:
            user_id = st.selectbox("Select User:", existing_users)
        else:
            st.warning("No users found in database. Please enter manually.")
            user_id = st.text_input("Enter USER_ID:")
    else:
        user_id = st.text_input("Enter USER_ID:")
    
    # Image upload
    uploaded_file = st.file_uploader("Upload inventory image", type=["jpg", "jpeg", "png"])
    
    if uploaded_file and user_id:
        image_data = uploaded_file.read()
        
        # Display uploaded image
        st.image(image_data, caption="Uploaded Image", use_container_width=True)
        
        if st.button("🔍 Extract Inventory with Cortex", use_container_width=True):
            with st.spinner("Analyzing with Snowflake Cortex..."):
                items = extract_inventory_multimodal(image_data, user_id)
            
            if items:
                st.session_state.extracted_items = items
                st.session_state.current_user_id = user_id
                st.success(f"✅ Successfully extracted {len(items)} items!")
    elif not user_id:
        st.warning("⚠️ Please enter a USER_ID to proceed")

with col2:
    st.subheader("📋 Extracted Items")
    
    if "extracted_items" in st.session_state and st.session_state.extracted_items:
        items = st.session_state.extracted_items
        
        st.write(f"**Items found: {len(items)}**")
        st.write(f"**Will be saved for USER_ID: `{st.session_state.current_user_id}`**")
        st.divider()
        
        # Display items with standardized units
        for idx, item in enumerate(items):
            quantity = item.get("quantity", 0)
            unit = item.get("unit", "pieces")
            item_name = item.get("item_name", "")
            std_quantity, std_unit = standardize_unit(quantity, unit, item_name)
            
            col1_item, col2_item = st.columns(2)
            with col1_item:
                st.write(f"**{idx + 1}. {item.get('item_name', 'N/A')}**")
                st.write(f"📊 Qty: {quantity} {unit} → **{std_quantity} {std_unit}**")
            with col2_item:
                st.write(f"🏷️ {item.get('category', 'N/A')}")
            st.divider()
        
        # Save to inventory button
        if st.button("✅ Save to Inventory", use_container_width=True):
            with st.spinner("Saving to Snowflake..."):
                inserted = add_inventory_to_snowflake(st.session_state.current_user_id, items)
            
            if inserted > 0:
                st.success(f"✅ Successfully added {inserted} items to inventory!")
                del st.session_state.extracted_items
                st.rerun()
            else:
                st.error("❌ Failed to save items")
    else:
        st.info("📤 Upload an image to extract inventory items")