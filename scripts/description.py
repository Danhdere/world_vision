import pandas as pd
import os
import time
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class GPTDescriptionGenerator:
    """
    Generates simple, layperson-friendly descriptions for medical inventory items
    using OpenAI's GPT-3.5 model
    """
    
    def __init__(self):
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"  # Using GPT-3.5 for cost efficiency
        
        # Rate limiting parameters
        self.requests_per_minute = 50  # Adjust based on your API tier
        self.request_interval = 60 / self.requests_per_minute
        self.last_request_time = 0
        
        # Track API usage for cost estimation
        self.total_tokens = 0
        self.total_requests = 0
        
    def _wait_for_rate_limit(self):
        """Implements rate limiting to avoid API errors"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.request_interval:
            sleep_time = self.request_interval - time_since_last_request
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
    
    def _create_prompt(self, item_data):
        """Create a prompt for GPT to generate a simple description"""
        description = item_data.get('DESCRIPTION', '')
        vendor = item_data.get('VENDOR_NAME', '')
        category = item_data.get('CATEGORY', '')
        subcategory = item_data.get('SUBCATEGORY', '')
        
        prompt = f"""Create a clear, one-line description of this medical item that would be understandable to someone without medical training. 
Use common abbreviations where appropriate, but ensure the meaning remains clear to a general audience.

Item: {description}"""
        
        # Add vendor information if available
        if vendor and not pd.isna(vendor):
            prompt += f"\nVendor: {vendor}"
            
        # Add category information if available
        if category and not pd.isna(category):
            prompt += f"\nCategory: {category}"
            
        # Add subcategory information if available
        if subcategory and not pd.isna(subcategory):
            prompt += f"\nSubcategory: {subcategory}"
            
        prompt += """

The description should be concise (under 15 words if possible) and focus on what the item is and its basic purpose.
Use common abbreviations (like 'pkg' for package, 'qty' for quantity, etc.) to keep it short.
If measurements are present, include them using standard abbreviations (cm, ml, etc.)
Do NOT include any brand names unless they are necessary for identification.
Make sure your response is ONLY the one-line description and nothing else."""
        
        return prompt
    
    def generate_description(self, item_data):
        """
        Generate a simple description for a medical item using GPT-3.5
        
        Args:
            item_data: Dict containing item information
            
        Returns:
            str: Simple, layperson-friendly description
        """
        if not item_data or not isinstance(item_data, dict):
            return "Invalid item data"
            
        description = item_data.get('DESCRIPTION', '')
        if pd.isna(description) or description == "":
            return "No description available"
            
        # Create the prompt
        prompt = self._create_prompt(item_data)
        
        # Implement rate limiting
        self._wait_for_rate_limit()
        
        # Make the API request with error handling and retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates simple, clear descriptions of medical items that non-medical people can understand."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,  # Lower temperature for more consistent responses
                    max_tokens=60     # Limit response length
                )
                
                # Update usage statistics
                self.total_tokens += response.usage.total_tokens
                self.total_requests += 1
                
                # Extract and clean the description
                description = response.choices[0].message.content.strip()
                
                # Remove any quotation marks that GPT might add
                description = description.strip('"\'')
                
                return description
                    
            except Exception as e:
                print(f"API error: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    return f"Error generating description: {str(e)}"
                    
        return "Failed to generate description after multiple attempts"
    
    def process_inventory_file(self, input_file, output_file=None, batch_size=None):
        """
        Process a CSV inventory file to add simple GPT-generated descriptions
        
        Args:
            input_file: Path to input CSV file
            output_file: Path to output CSV file (if None, will add suffix '_with_gpt_desc')
            batch_size: Number of items to process (for testing with subset)
            
        Returns:
            DataFrame with added GPT descriptions
        """
        try:
            # Create default output file name if not provided
            if not output_file:
                base_name = input_file.rsplit('.', 1)[0]
                output_file = f"{base_name}_with_gpt_desc.csv"
                
            # Read the inventory file
            print(f"Reading inventory file: {input_file}")
            df = pd.read_csv(input_file)
            
            # Limit to batch_size if specified
            if batch_size and batch_size < len(df):
                print(f"Processing subset of {batch_size} items for testing")
                df_to_process = df.iloc[:batch_size].copy()
            else:
                df_to_process = df.copy()
                
            # Add a new column for the GPT descriptions
            df_to_process['SIMPLE_DESCRIPTION'] = ""
            
            # Process each row with progress bar
            print(f"Generating descriptions for {len(df_to_process)} items...")
            for idx, row in tqdm(df_to_process.iterrows(), total=len(df_to_process)):
                item_data = row.to_dict()
                gpt_desc = self.generate_description(item_data)
                df_to_process.loc[idx, 'SIMPLE_DESCRIPTION'] = gpt_desc
                
                # Save intermediate results every 50 items
                if (idx + 1) % 50 == 0:
                    intermediate_file = f"{output_file}.temp"
                    df_to_process.to_csv(intermediate_file, index=False)
                    print(f"Saved intermediate results after {idx + 1} items")
                    
                    # Display cost estimation
                    cost_estimate = (self.total_tokens / 1000) * 0.002  # $0.002 per 1K tokens for GPT-3.5
                    print(f"Tokens used so far: {self.total_tokens} (est. cost: ${cost_estimate:.2f})")
            
            # If we processed a subset, merge it back with the original dataframe
            if batch_size and batch_size < len(df):
                df.loc[:batch_size-1, 'SIMPLE_DESCRIPTION'] = df_to_process['SIMPLE_DESCRIPTION']
                final_df = df
            else:
                final_df = df_to_process
                
            # Save the results
            print(f"Saving results to {output_file}")
            final_df.to_csv(output_file, index=False)
            
            # Print final statistics
            cost_estimate = (self.total_tokens / 1000) * 0.002
            print("\nProcessing complete!")
            print(f"Total API requests: {self.total_requests}")
            print(f"Total tokens used: {self.total_tokens}")
            print(f"Estimated API cost: ${cost_estimate:.2f}")
            
            # Print some examples
            print("\nExample simple descriptions:")
            sample_size = min(5, len(df_to_process))
            for i in range(sample_size):
                original = df_to_process.iloc[i]['DESCRIPTION']
                simple = df_to_process.iloc[i]['SIMPLE_DESCRIPTION']
                print(f"Original: {original}")
                print(f"Simple: {simple}")
                print("-" * 50)
                
            return final_df
            
        except Exception as e:
            print(f"Error processing inventory file: {e}")
            raise

# Example usage
if __name__ == "__main__":
    generator = GPTDescriptionGenerator()
    
    # Use specified file paths
    input_file = "../inventory/Quarterly DC cleanout Dec 3 2024_facilitized_3.csv"
    output_file = "../inventory/Quarterly DC cleanout Dec 3 2024_descriptive_4.csv"    
    
    # Ask if they want to test with a smaller batch first
    test_batch = input("Do you want to test with a smaller batch first? (y/n): ")
    batch_size = None
    if test_batch.lower().startswith('y'):
        batch_size = int(input("Enter number of items to process for testing: "))
    
    # Process the inventory file with specific output file
    generator.process_inventory_file(input_file, output_file=output_file, batch_size=batch_size)