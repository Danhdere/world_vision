import pandas as pd
import os
from openai import OpenAI
import time
import re 
from dotenv import load_dotenv
load_dotenv()

class FacilitySuitabilityClassifier:
    """Classifies Medical Inventory based on suitability for rural clinicls or district hospitals"""

    def __init__(self, client = None):

        self.client = client or globals().get('client')
        if not self.client:
            raise ValueError("OpenAI client is not initialized. Please provide a valid client.")

        self.facility_types = [
            "Rural Clinics",
            "District Hospitals",
            "Both", 
            "Needs Review"
            ]
        
        #equipment suitable for rural clinics (based on research)
        self.rural_clinic_equipment = [
            "blood pressure monitor", "thermometer", "stethoscope", "weight scale",
            "glucometer", "hemoglobinometer", "nebulizer", "oxygen concentrator",
            "fetoscope", "delivery kit", "wound care", "dressing", "bandage", 
            "sterilization", "autoclave", "pressure cooker", "rapid test",
            "hiv test", "malaria test", "pregnancy test", "urinalysis", "dipstick",
            "first aid", "oral medication", "injection", "immunization", "vaccine",
            "iv fluid", "cannula", "catheter", "splint", "crutch"
        ]
        
        # Equipment typically found in district hospitals only
        self.district_hospital_equipment = [
            "ventilator", "ecg", "electrocardiograph", "chemistry analyzer", 
            "hematology analyzer", "operating table", "surgical", "anesthesia",
            "electrosurgical", "ceiling light", "operating light", "slit lamp",
            "ophthalmology", "x-ray", "radiography", "ultrasound", "imaging",
            "incubator", "blood bank", "refrigerator", "cpap", "icu", "intensive care",
            "cesarean", "theatre", "surgery", "fracture", "biopsy", "endoscopy",
            "laparoscopy", "microscope", "centrifuge", "culture", "microbiology",
            "monitor", "patient monitor", "fetal monitor", "cross matching", "transfusion"
        ]
        
                # Items that might be problematic or need review
        self.needs_review_keywords = [
            "expired", "damaged", "recalled", "obsolete", "discontinued", 
            "complex", "specialized", "calibration required", "maintenance intensive",
            "proprietary", "requires training", "missing components", "advanced",
            "high power", "continuous electricity", "climate controlled", "mri", "ct scan",
            "radiation", "radioactive", "nuclear", "restricted", "controlled substance"
        ]

    def determine_facility_suitability(self, description, category = None, vendor_name = None):
        """
        Determine the suitability of a medical item based on its description and category.
        First tries keyword matching, then falls back to OpenAI API
        """

        if pd.isna(description) or description == "":
            return "Needs Review"
        
        desc_lower = description.lower()

        #check for items that need review first 
        for keyword in self.needs_review_keywords:
            if keyword in desc_lower:
                return "Needs Review"
        
        # Check if suitable for rural clinics
        rural_match = False
        for keyword in self.rural_clinic_equipment:
            if keyword in desc_lower:
                rural_match = True
                break
        
        # Check if suitable for district hospitals
        district_match = False
        for keyword in self.district_hospital_equipment:
            if keyword in desc_lower:
                district_match = True
                break

        if rural_match and district_match:
            return "Both"
        elif rural_match:
            return "Rural Clinics"
        elif district_match:
            return "District Hospitals"
        
        #If no clear match through keywords, use OpenAI to classify
        try:
            # Combine description, category, and vendor
            context = f"Description: {description}"
            if category and not pd.isna(category):
                context += f", Category: {category}"
            if vendor_name and not pd.isna(vendor_name):
                context += f", Vendor: {vendor_name}"

            # Create prompt 
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages = [
                    {"role": "system", "content": """You are a healthcare facility equipment specialist
                        Rural clinics typically have:
                        - Basic equipment limited to essential primary care
                        - Basic wound care supplies and dressing materials
                        - IV cannulation capabilities for fluid administration
                        - Equipment for uncomplicated deliveries
                        - Simple diagnostic tools (glucometers, thermometers, blood pressure monitors)
                        - Limited electricity and often unreliable power
                        - Basic sterilization (pressure cookers, table-top autoclaves)
                        - Very limited laboratory capabilities (rapid tests only)
                        - No advanced imaging

                        District hospitals have more advanced capabilities including:
                        - Surgery facilities and operating rooms
                        - ECG machines and patient monitors
                        - Imaging equipment (X-ray, ultrasound)
                        - Laboratory with chemistry analyzers and hematology analyzers
                        - Blood banking capabilities
                        - Anesthesia equipment
                        - More reliable electricity (often with backup generators)
                        - Oxygen supply systems
                        - Capacity for more complex procedures

                        Based ONLY on this information, classify the medical item into ONE of these categories:
                        1. Rural Clinic - Suitable for use in basic rural clinics
                        2. District Hospital - Requires district hospital capabilities
                        3. Both Settings - Can be effectively used in either setting
                        4. Needs Review - May not be usable or requires additional assessment            

                        Respond with ONLY the category name."""         
                     },
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens = 30 
                )
            facility_type = response.choices[0].message.content.strip()

            #Clean up response
            if ":" in facility_type:
                facility_type = facility_type.split(":")[1].strip()
            if facility_type not in self.facility_types:
                #find closest match
                for valid_type in self.facility_types:
                    if valid_type.lower() in facility_type.lower():
                        return valid_type 
                
                #if still not match, return "needs review"
                return "Needs Review"
            
            return facility_type 

        except Exception as e:
            print(f"Error classifying item: {e}")
            return "Needs Review"
        
    def process_csv(self, input_file, output_file = None, category_col="Product Category"):
        """
        Process the CSV file to determine facility suitability for each item.
        """

        try:
            if not output_file:
                base_name = os.path.splitext(input_file)[0]
                output_file = f"{base_name}_facilitized.csv"
            
            #read csv file
            print(f"Reading file: {input_file}")
            df = pd.read_csv(input_file)
            
            # Add facility suitability column
            df["Facility Suitability"] =""

            # Process items
            batch_size = 50 
            for i in range(0, len(df)):
                
                #get item description and other relevent fields
                description = df.loc[i, "DESCRIPTION"] if "DESCRIPTION" in df.columns else ""
                category = df.iloc[i][category_col] if category_col in df.columns else None
                vendor_name = df.loc[i, "VENDOR_NAME"] if "VENDOR_NAME" in df.columns else None

                #determine facility suitability
                facility_type = self.determine_facility_suitability(description, category, vendor_name)
                df.loc[i, "Facility Suitability"] = facility_type

                #progress reporting
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1} items/{len(df)} items")

                if (i + 1) % batch_size == 0 and (i + 1) < len(df):
                    print(f"Pausing to avoid API rate limits...")
                    time.sleep(5) 

            #save processed data
            print(f"Saving results to {output_file}")
            df.to_csv(output_file, index = False)

            #Print facility suitability distribution
            facility_counts = df["Facility Suitability"].value_counts()
            print("\nFacility Suitability Distribution:")
            for facility, count in facility_counts.items():
                print(f"{facility}: {count}") 

            return df 
            
        except Exception as e:
            print(f"Error processing CSV: {e}")
            raise
def main():
    input_file = "inventory/Quarterly DC cleanout Dec 3 2024.xlsx - Sheet1.csv"
    output_file = "inventory/Quarterly DC cleanout Dec 3 2024_facilitized.csv"

    #check api key is set 
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please add your OpenAI API key to the .env file.")
        return
    
    try:
        # Initialize the classifier
        client = OpenAI(api_key=api_key)
        classifier = FacilitySuitabilityClassifier(client)
        
        # Process the CSV file
        classifier.process_csv(
            input_file=input_file,
            output_file=output_file
        )
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()