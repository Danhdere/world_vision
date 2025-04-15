import pandas as pd
import os 
from openai import OpenAI
import time
from dotenv import load_dotenv

#load env variables 
load_dotenv() 

#get openai api key from env variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class MedicalInventoryCategorizer:
    def __init__(self, client = None): 
        """Intialize the categorizer with OpenAI client"""
        self.client = client or globals().gt('client')
        if not self.client:
            raise ValueError("OpenAI client is not initialized. Please provide a valid client.")
        
        #define medical product categories
        self.categories = [
            "Medical Equipment & Furniture",  # Durable items such as exam tables, surgical lights, and patient chairs
            "Medical & Surgical Supplies",    # Consumables including gloves, bandages, tubing, and instruments
            "PPE & Infection Control",        # Personal protective equipment like masks, gowns, and sanitizing products
            "Cleaning & Facility Maintenance", # Disinfectants, wipes, and related sanitation materials
            "Diagnostics & Lab Use"           # Items used for monitoring, testing, or sample handling
        ]

        #Category mappin gfor common medical items (can be edited or expaneded) 
        self.category_mapping = {
            # Medical Equipment & Furniture
            "table": "Medical Equipment & Furniture",
            "chair": "Medical Equipment & Furniture",
            "bed": "Medical Equipment & Furniture",
            "cart": "Medical Equipment & Furniture",
            "light": "Medical Equipment & Furniture",
            "stool": "Medical Equipment & Furniture",
            "cabinet": "Medical Equipment & Furniture",
            "monitor": "Medical Equipment & Furniture",
            "scale": "Medical Equipment & Furniture",
            
            # Medical & Surgical Supplies
            "syringe": "Medical & Surgical Supplies",
            "needle": "Medical & Surgical Supplies",
            "bandage": "Medical & Surgical Supplies",
            "gauze": "Medical & Surgical Supplies",
            "tape": "Medical & Surgical Supplies",
            "glove": "Medical & Surgical Supplies",
            "tubing": "Medical & Surgical Supplies",
            "catheter": "Medical & Surgical Supplies",
            "dressing": "Medical & Surgical Supplies",
            "suture": "Medical & Surgical Supplies",
            "scalpel": "Medical & Surgical Supplies",
            "blade": "Medical & Surgical Supplies",
            
            # PPE & Infection Control
            "mask": "PPE & Infection Control",
            "gown": "PPE & Infection Control",
            "shield": "PPE & Infection Control",
            "goggle": "PPE & Infection Control",
            "sanitizer": "PPE & Infection Control",
            "ppe": "PPE & Infection Control",
            "protection": "PPE & Infection Control",
            "face": "PPE & Infection Control",
            
            # Cleaning & Facility Maintenance
            "disinfectant": "Cleaning & Facility Maintenance",
            "wipe": "Cleaning & Facility Maintenance",
            "cleaner": "Cleaning & Facility Maintenance",
            "detergent": "Cleaning & Facility Maintenance",
            "soap": "Cleaning & Facility Maintenance",
            "sanitizing": "Cleaning & Facility Maintenance",
            "bleach": "Cleaning & Facility Maintenance",
            "mop": "Cleaning & Facility Maintenance",
            
            # Diagnostics & Lab Use
            "test": "Diagnostics & Lab Use",
            "lab": "Diagnostics & Lab Use",
            "specimen": "Diagnostics & Lab Use",
            "culture": "Diagnostics & Lab Use",
            "slide": "Diagnostics & Lab Use",
            "microscope": "Diagnostics & Lab Use",
            "analyzer": "Diagnostics & Lab Use",
            "reagent": "Diagnostics & Lab Use",
            "diagnostic": "Diagnostics & Lab Use"
        }
    def categorize_item(self, description, vendor_name = None, subcategory = None):
        """
        Determine category based on item description and other metadata 
        First tries direct keyword matching, then falls back to OpenAI API
        """

        if pd.isna(description) or description == "":
            return "Uncategorized" 
        
        # convert to lowercase
        desc_lower = description.lower() 

        # Check for direct keyword mapping
        for keyword, category in self.category_mapping.items():
            if keyword in desc_lower:
                return category 
        
        #if subcategory is provided, use it as a hint
        if subcategory and not pd.isna(subcategory):
            sub_lower = subcategory.lower()
            for keyword, category in self.category_mapping.items():
                if keyword in sub_lower:
                    return category
        
        # if not match found, use OpenAI to categorize 
        try:
            #combine description and vendor info 
            context = f"Description: {description}"
            if vendor_name and not pd.isna(vendor_name):
                context += f", Vendor: {vendor_name}"
            if subcategory and not pd.isna(subcategory):
                context += f", Subcategory: {subcategory}"

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages = [
                    {"role": "system", "content": f"""You are a helpful assistant that categorizes medical inventory items. 
                     Respond with a single category name that best fits the item.
                     Choose ONLY from these categories:
                     1. Medical Equipment & Furniture – Durable items such as exam tables, surgical lights, and patient chairs.
                     2. Medical & Surgical Supplies – Consumables including gloves, bandages, tubing, and instruments.
                     3. PPE & Infection Control – Personal protective equipment like masks, gowns, and sanitizing products.
                     4. Cleaning & Facility Maintenance – Disinfectants, wipes, and related sanitation materials.
                     5. Diagnostics & Lab Use – Items used for monitoring, testing, or sample handling.
                     
                     Respond ONLY with the category name, nothing else."""},
                     {"role": "user", "content": context}
                ],
                max_tokens = 30, 
                temperature = 0.0,                 
                     
            )
            category = response.choices[0].message.content.strip()

            #clean up response 
            if ":" in category:
                category = category.split(":")[1].strip()

            # validate response is one of our categories
            if category not in self.categories:
                #find closest match
                for valid_category in self.categories:
                    if valid_category.lower() in category.lower():
                        return valid_category
                #if still no match, return "needs review"
                return "Needs Review"

            return category
        
        except Exception as e:
            print(f"Error categorizing item: {e}")
            return "Needs Review"
    
    def process_csv(self, input_file, output_file = None, batch_size = 50, preserve_existing = True):
        """
        Process the CSV file, categorize items, and save results
        """

        try:
            if not output_file:
                base_name = os.path.splittext(input_file)[0]
                output_file = f"{base_name}_categorized.csv"
            
            #read csv file
            print(f"Reading file: {input_file}")
            df = pd.read_csv(input_file)
            print(f"DataFrame shape: {df.shape}")

            #check if product category exists
            category_col = "Product Category"
            has_category = category_col in df.columns

            if not has_category:
                df[category_col] = ""
            elif preserve_existing:
                #fill only empty categories if preserve_existing is True
                print(f"Preserving {df[category_col].notna().sum()} existing categories")
            else:
                #clear all categories if preserve_existing is False
                df[category_col] = ""
            
            #count items that need categorization
            items_to_categorize = df[df[category_col].isna() | (df[category_col] == "")].shape[0]
            print(f"Items to categorize: {items_to_categorize}")

            #process data in batches to avoid rate limiting
            count = 0 
            for i in range(0, len(df)):
                #skip if category exists and we're preserving existing values
                if preserve_existing and df.loc[i, category_col] and not pd.isna(df.loc[i, category_col]):
                    continue

                # get item description and other relevent fields
                description = df.loc[i, "DESCRIPTION"] if "DESCRIPTION" in df.columns else ""
                vendor_name = df.loc[i, "VENDOR_NAME"] if "VENDOR_NAME" in df.columns else None
                subcategory = df.loc[i, "SUBCATEGORY"] if "SUBCATEGORY" in df.columns else None

                #categorize the item
                category = self.categorize_item(description, vendor_name, subcategory)
                df.loc[i, category_col] = category

                count += 1 
                if count % 10 == 0:
                    print(f"Processed {count}/{items_to_categorize} items")

                if count % batch_size == 0 and count < items_to_categorize:
                    print(f"Pausing for 10 seconds to avoid rate limiting...")
                    time.sleep(10)

            #save results
            print(f"Saving results to {output_file}")
            df.to_csv(output_file, index = False)
            print(f"CSV processing completed successfully.")

            #print category distribution
            category_counts = df[category_col].value_counts()
            print("\nProduct Category Distribution:")
            for category, count in category_counts.items():
                print(f"{category}: {count}")
            
            return df
        
        except Exception as e:
            print(f"Error processing CSV: {e}")
            raise 

def main():
    """Main Function Running Script"""
    input_file = "inventory/Quarterly DC cleanout Dec 3 2024.xlsx - Sheet1.csv"
    output_file = "inventory/Quarterly DC cleanout Dec 3 2024_categorized.csv"

    #check api key is set 
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Please set it in the .env file.")
        return

    try:
        # Intialize categorizer
        categorizer = MedicalInventoryCategorizer(client)

        #process csv
        categorizer.process_csv(
            input_file=input_file,
            output_file=output_file,
            batch_size=50,
            preserve_existing=True
        )

    except Exception as e:
        print(f"Error processing CSV: {e}")
        raise

if __name__ == "__main__":
    main()