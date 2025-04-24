import argparse
import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# Import custom modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.read_csv import read_inventory_csv
from scripts.categorize import MedicalInventoryCategorizer
from scripts.facilitize import FacilitySuitabilityClassifier
from scripts.description import GPTDescriptionGenerator

# Load environment variables
load_dotenv()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Medical Inventory Processing System")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--output", help="Path to output CSV file (default: <input_basename>_processed.csv)")
    parser.add_argument("--skip-facility", action="store_true", help="Skip facility suitability classification")
    parser.add_argument("--skip-descriptions", action="store_true", help="Skip generation of simple descriptions")
    parser.add_argument("--preserve-existing", action="store_true", default=True, 
                        help="Preserve existing category assignments (default: True)")
    parser.add_argument("--batch-size", type=int, default=50, 
                        help="Batch size for API calls to avoid rate limiting (default: 50)")
    parser.add_argument("--description-batch", type=int, 
                        help="Number of items to process for descriptions (for testing, default: all items)")
    
    return parser.parse_args()

def generate_summary_report(df, output_path, processing_time, skip_facility=False, skip_descriptions=False):
    """Generate a summary report of the processing results"""
    # Create a summary report
    report_path = os.path.splitext(output_path)[0] + "_summary.txt"
    
    with open(report_path, "w") as f:
        f.write("Medical Inventory Processing Summary\n")
        f.write("==================================\n\n")
        
        f.write(f"Input file: {args.input}\n")
        f.write(f"Output file: {output_path}\n")
        f.write(f"Processing time: {processing_time:.2f} seconds\n\n")
        
        f.write(f"Total items processed: {len(df)}\n\n")
        
        # Product Category distribution
        f.write("Product Category Distribution:\n")
        f.write("----------------------------\n")
        category_counts = df["Product Category"].value_counts()
        total_items = len(df)
        
        for category, count in category_counts.items():
            percentage = (count / total_items) * 100
            f.write(f"{category}: {count} ({percentage:.1f}%)\n")
        
        # Facility Suitability distribution (if available)
        if not skip_facility and "Facility Suitability" in df.columns:
            f.write("\nFacility Suitability Distribution:\n")
            f.write("--------------------------------\n")
            facility_counts = df["Facility Suitability"].value_counts()
            
            for facility, count in facility_counts.items():
                percentage = (count / total_items) * 100
                f.write(f"{facility}: {count} ({percentage:.1f}%)\n")
        
        # Cross-tabulation of Category and Facility Suitability
        if not skip_facility and "Facility Suitability" in df.columns:
            f.write("\nCategory by Facility Cross-tabulation:\n")
            f.write("---------------------------------\n")
            cross_tab = pd.crosstab(df["Product Category"], df["Facility Suitability"])
            f.write(cross_tab.to_string())
            
        # Sample of Simple Descriptions (if available)
        if not skip_descriptions and "SIMPLE_DESCRIPTION" in df.columns:
            f.write("\nSample of Simple Descriptions:\n")
            f.write("----------------------------\n")
            # Get 10 random samples of item descriptions
            samples = df.sample(min(10, len(df)))
            for _, row in samples.iterrows():
                original = row["DESCRIPTION"]
                simple = row["SIMPLE_DESCRIPTION"]
                f.write(f"Original: {original}\n")
                f.write(f"Simple  : {simple}\n\n")
            
    print(f"Summary report written to: {report_path}")
    return report_path

def main():
    # Get command line arguments
    args = parse_arguments()
    
    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}")
        sys.exit(1)
    
    # Determine output path
    if not args.output:
        base_name = os.path.splitext(args.input)[0]
        args.output = f"{base_name}_processed.csv"
    
    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY is not set in the environment or .env file.")
        print("Please set your OpenAI API key before running this script.")
        sys.exit(1)
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # 1. Read and validate the CSV file
        print(f"\n1. Reading and validating CSV file: {args.input}")
        start_time = time.time()
        df = read_inventory_csv(args.input)
        read_time = time.time() - start_time
        print(f"   CSV file read in {read_time:.2f} seconds.")
        
        # 2. Categorize items
        print("\n2. Categorizing medical inventory items...")
        categorizer = MedicalInventoryCategorizer(client)
        
        # Determine if we need to create intermediate files
        categorized_output = args.output
        if not args.skip_facility or not args.skip_descriptions:
            # Create an intermediate file if we're doing more processing steps
            categorized_output = os.path.splitext(args.output)[0] + "_categorized.csv"
        
        start_time = time.time()
        df = categorizer.process_csv(
            input_file=args.input,
            output_file=categorized_output,
            batch_size=args.batch_size,
            preserve_existing=args.preserve_existing
        )
        category_time = time.time() - start_time
        print(f"   Categorization completed in {category_time:.2f} seconds.")
        
        # Print category distribution
        print("\n   Product Category Distribution:")
        category_counts = df["Product Category"].value_counts()
        for category, count in category_counts.items():
            percentage = (count / len(df)) * 100
            print(f"   - {category}: {count} ({percentage:.1f}%)")
        
        # 3. Classify facility suitability (if not skipped)
        facility_time = 0
        facility_output = categorized_output
        
        if not args.skip_facility:
            print("\n3. Classifying facility suitability...")
            classifier = FacilitySuitabilityClassifier(client)
            
            if not args.skip_descriptions:
                # Create intermediate file if we're adding descriptions after
                facility_output = os.path.splitext(args.output)[0] + "_facilitized.csv"
            else:
                facility_output = args.output
            
            start_time = time.time()
            df = classifier.process_csv(
                input_file=categorized_output,
                output_file=facility_output,
                category_col="Product Category"
            )
            facility_time = time.time() - start_time
            print(f"   Facility classification completed in {facility_time:.2f} seconds.")
            
            # Print facility distribution
            print("\n   Facility Suitability Distribution:")
            facility_counts = df["Facility Suitability"].value_counts()
            for facility, count in facility_counts.items():
                percentage = (count / len(df)) * 100
                print(f"   - {facility}: {count} ({percentage:.1f}%)")
        
        # 4. Generate simple descriptions (if not skipped)
        description_time = 0
        if not args.skip_descriptions:
            print("\n4. Generating simple layperson-friendly descriptions...")
            description_generator = GPTDescriptionGenerator()
            
            start_time = time.time()
            input_for_desc = facility_output if not args.skip_facility else categorized_output
            
            # Use the process_inventory_file method directly from the imported module
            final_df = description_generator.process_inventory_file(
                input_file=input_for_desc,
                output_file=args.output,
                batch_size=args.description_batch
            )
            
            # Update our working dataframe
            df = final_df
            
            description_time = time.time() - start_time
            print(f"   Description generation completed in {description_time:.2f} seconds.")
        
        # 5. Generate summary report
        total_time = read_time + category_time + facility_time + description_time
        print(f"\n5. Generating summary report...")
        report_path = generate_summary_report(
            df, 
            args.output, 
            total_time, 
            skip_facility=args.skip_facility,
            skip_descriptions=args.skip_descriptions
        )
        
        # Clean up intermediate files
        intermediate_files = []
        if not args.skip_facility and not args.skip_descriptions:
            if os.path.exists(categorized_output) and categorized_output != args.output:
                intermediate_files.append(categorized_output)
            if os.path.exists(facility_output) and facility_output != args.output:
                intermediate_files.append(facility_output)
        elif not args.skip_facility:
            if os.path.exists(categorized_output) and categorized_output != args.output:
                intermediate_files.append(categorized_output)
        elif not args.skip_descriptions:
            if os.path.exists(categorized_output) and categorized_output != args.output:
                intermediate_files.append(categorized_output)
        
        if intermediate_files:
            print("\nCleaning up intermediate files...")
            for file in intermediate_files:
                os.remove(file)
                print(f"   Removed: {file}")
        
        print(f"\nProcessing completed successfully in {total_time:.2f} seconds.")
        print(f"Results saved to: {args.output}")
        print(f"Summary report: {report_path}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()