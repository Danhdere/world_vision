import pandas as pd
import os 

def read_inventory_csv(file_path):

    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Read CSV file
        print(f"Reading file: {file_path}")
        df = pd.read_csv(file_path)

        # Basic validation
        expected_columns = [
            "DIST_NO", "DC_NAME", "ITEM_NO", "VEND_CAT_NUM", 
            "AVAILABILITY_QTY", "SELL_UOM", "ABC_CODE", 
            "VENDOR_ABBR", "VENDOR_NAME", "DESCRIPTION", 
            "COST", "EXT_COST", "GROSS_CUBIC", "CUBIC_FEET", 
            "EXT_GROSS_CUBIC", "EST_PALLETS", "CATEGORY", 
            "SUBCATEGORY", "DATING", "AGE_DESC", 
            "REGULATION", "LEGEND_DESCRIPTION"
        ]

        # check for required columns
        required_columns = ["ITEM_NO", "DESCRIPTION", "VENDOR_NAME"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        #print basic statistics
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")

        return df

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        raise

def main():
    file_path = "inventory/Quarterly DC cleanout Dec 3 2024.xlsx - Sheet1.csv"
    df = read_inventory_csv(file_path)
    print(df.head()) 
    print("\nCSV processing completed successfully.")

if __name__ == "__main__":
    main() 