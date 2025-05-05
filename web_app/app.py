from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash, jsonify
import os
import pandas as pd
import uuid
import time
import threading
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
import sys 

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # This should be the world_vision/ directory
sys.path.append(parent_dir)

from scripts.read_csv import read_inventory_csv
from scripts.categorize import MedicalInventoryCategorizer
from scripts.facilitize import FacilitySuitabilityClassifier
from scripts.description import GPTDescriptionGenerator

app = Flask(__name__) 
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Dictionary to store processing progress
processing_tasks = {}

def allowed_files(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_background_task(processing_id, file_path, unique_id, original_filename, options):
    """Background task to process data with progress tracking"""
    progress_data = processing_tasks[processing_id]
    
    try:
        # Extract options
        preserve_existing = options.get('preserve_existing', True)
        batch_size = options.get('batch_size', 50)
        skip_facility = options.get('skip_facility', True)
        skip_descriptions = options.get('skip_descriptions', True)
        
        # Define file paths
        base_name = os.path.splitext(original_filename)[0]
        final_filename = f"{base_name}_processed.csv"
        final_path = os.path.join(app.config['RESULTS_FOLDER'], f"{unique_id}_{final_filename}")
        
        # Define intermediate file paths if needed
        categorized_output = final_path
        facility_output = final_path
        
        if not skip_facility or not skip_descriptions:
            categorized_filename = f"{base_name}_categorized.csv"
            categorized_output = os.path.join(app.config['RESULTS_FOLDER'], f"{unique_id}_{categorized_filename}")
        
        if not skip_facility and not skip_descriptions:
            facilitized_filename = f"{base_name}_facilitized.csv"
            facility_output = os.path.join(app.config['RESULTS_FOLDER'], f"{unique_id}_{facilitized_filename}")
        elif not skip_facility:
            facility_output = final_path
            
        # Track timing and process data
        processing_times = {}
        df = None
        
        # 1. Read and validate the CSV file
        progress_data['status'] = 'Reading and validating CSV file'
        progress_data['current_step'] = 'Data validation'
        
        start_time = time.time()
        df = read_inventory_csv(file_path)
        progress_data['total_items'] = len(df)
        progress_data['completed_items'] = len(df)  # Mark this step as complete
        processing_times['reading'] = time.time() - start_time
        
        # 2. Categorize items
        progress_data['status'] = 'Categorizing medical inventory items'
        progress_data['current_step'] = 'Category assignment'
        progress_data['completed_items'] = 0  # Reset for new step
        
        start_time = time.time()
        
        # Custom categorizer implementation to track progress
        categorizer = MedicalInventoryCategorizer(client)
        
        # If Product Category column doesn't exist, add it
        if "Product Category" not in df.columns:
            df["Product Category"] = ""
        
        # Count items that need categorization
        if preserve_existing:
            items_to_categorize = df[df["Product Category"].isna() | (df["Product Category"] == "")].shape[0]
        else:
            items_to_categorize = len(df)
            df["Product Category"] = ""
        
        # Process items with progress tracking
        count = 0
        for i in range(len(df)):
            # Skip if category exists and we're preserving existing values
            if preserve_existing and df.loc[i, "Product Category"] and not pd.isna(df.loc[i, "Product Category"]):
                continue
            
            # Get item description and other relevant fields
            description = df.loc[i, "DESCRIPTION"] if "DESCRIPTION" in df.columns else ""
            vendor_name = df.loc[i, "VENDOR_NAME"] if "VENDOR_NAME" in df.columns else None
            subcategory = df.loc[i, "SUBCATEGORY"] if "SUBCATEGORY" in df.columns else None
            
            # Categorize the item
            category = categorizer.categorize_item(description, vendor_name, subcategory)
            df.loc[i, "Product Category"] = category
            
            count += 1
            # Update progress
            progress_data['completed_items'] = count
            progress_data['current_step'] = f'Category assignment ({count}/{items_to_categorize})'
            
            if count % batch_size == 0 and count < items_to_categorize:
                time.sleep(0.1)  # Small delay to avoid rate limiting
        
        # Save results
        df.to_csv(categorized_output, index=False)
        
        processing_times['categorization'] = time.time() - start_time
        
        # Get category distribution for results page
        category_counts = df["Product Category"].value_counts().to_dict()
        progress_data['category_counts'] = category_counts
        
        # 3. Classify facility suitability (if not skipped)
        facility_counts = {}
        
        if not skip_facility:
            progress_data['status'] = 'Classifying facility suitability'
            progress_data['current_step'] = 'Facility classification'
            progress_data['completed_items'] = 0  # Reset for new step
            
            start_time = time.time()
            
            # Custom facility classification with progress tracking
            classifier = FacilitySuitabilityClassifier(client)
            
            # Process with our own progress tracking instead of using the class method
            df = pd.read_csv(categorized_output)
            
            # Add facility suitability column
            df["Facility Suitability"] = ""
            
            for i in range(len(df)):
                # Get description and category
                description = df.loc[i, "DESCRIPTION"] if "DESCRIPTION" in df.columns else ""
                category = df.iloc[i]["Product Category"] if "Product Category" in df.columns else None
                vendor_name = df.loc[i, "VENDOR_NAME"] if "VENDOR_NAME" in df.columns else None
                
                # Determine facility suitability
                facility_type = classifier.determine_facility_suitability(description, category, vendor_name)
                df.loc[i, "Facility Suitability"] = facility_type
                
                # Update progress
                progress_data['completed_items'] = i + 1
                progress_data['current_step'] = f'Facility classification ({i+1}/{len(df)})'
                
                if (i + 1) % 10 == 0:
                    time.sleep(0.05)  # Small delay
            
            # Save processed data
            df.to_csv(facility_output, index=False)
            
            processing_times['facility'] = time.time() - start_time
            
            # Get facility distribution
            facility_counts = df["Facility Suitability"].value_counts().to_dict()
            progress_data['facility_counts'] = facility_counts
        
        # 4. Generate simple descriptions (if not skipped)
        if not skip_descriptions:
            progress_data['status'] = 'Generating simple descriptions'
            progress_data['current_step'] = 'Description generation'
            progress_data['completed_items'] = 0  # Reset for new step
            
            start_time = time.time()
            
            description_generator = GPTDescriptionGenerator()
            
            # Get the input file based on previous steps
            input_for_desc = facility_output if not skip_facility else categorized_output
            
            # Load data from the appropriate input file
            df = pd.read_csv(input_for_desc)
            
            # Add simple description column
            df['SIMPLE_DESCRIPTION'] = ""
            
            # Process each row with progress updates
            for idx, row in enumerate(df.iterrows()):
                index, item_data = row
                gpt_desc = description_generator.generate_description(item_data.to_dict())
                df.loc[index, 'SIMPLE_DESCRIPTION'] = gpt_desc
                
                # Update progress
                progress_data['completed_items'] = idx + 1
                progress_data['current_step'] = f'Description generation ({idx+1}/{len(df)})'
                
                if (idx + 1) % 10 == 0:
                    time.sleep(0.05)  # Small delay
            
            # Save results
            df.to_csv(final_path, index=False)
            
            processing_times['descriptions'] = time.time() - start_time
        
        # Make sure the final file exists
        if skip_descriptions and skip_facility:
            # If we only did categorization, rename the output file to the final path
            if os.path.exists(categorized_output) and categorized_output != final_path:
                os.rename(categorized_output, final_path)
                df = pd.read_csv(final_path)
        elif skip_descriptions and not skip_facility:
            # If we did categorization and facility but no descriptions
            if os.path.exists(facility_output) and facility_output != final_path:
                os.rename(facility_output, final_path)
                df = pd.read_csv(final_path)
        
        # Calculate total processing time
        total_time = sum(processing_times.values())
        
        # 5. Generate summary report
        progress_data['status'] = 'Generating summary report'
        progress_data['current_step'] = 'Creating summary'
        
        summary_filename = f"{base_name}_summary.txt"
        summary_path = os.path.join(app.config['RESULTS_FOLDER'], f"{unique_id}_{summary_filename}")
        
        # Create the summary report
        with open(summary_path, 'w') as f:
            f.write("Medical Inventory Processing Summary\n")
            f.write("==================================\n\n")
            
            f.write(f"Input file: {original_filename}\n")
            f.write(f"Output file: {final_filename}\n")
            f.write(f"Processing time: {total_time:.2f} seconds\n\n")
            
            f.write(f"Total items processed: {len(df)}\n\n")
            
            # Product Category distribution
            f.write("Product Category Distribution:\n")
            f.write("----------------------------\n")
            for category, count in category_counts.items():
                percentage = (count / len(df)) * 100
                f.write(f"{category}: {count} ({percentage:.1f}%)\n")
            
            # Facility Suitability distribution (if available)
            if not skip_facility and "Facility Suitability" in df.columns:
                f.write("\nFacility Suitability Distribution:\n")
                f.write("--------------------------------\n")
                for facility, count in facility_counts.items():
                    percentage = (count / len(df)) * 100
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
        
        # Clean up intermediate files
        intermediate_files = []
        if categorized_output != final_path and os.path.exists(categorized_output):
            intermediate_files.append(categorized_output)
        if facility_output != final_path and facility_output != categorized_output and os.path.exists(facility_output):
            intermediate_files.append(facility_output)
        
        for file_path in intermediate_files:
            try:
                os.remove(file_path)
                print(f"Removed intermediate file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {str(e)}")
        
        # Store results data for the results page
        progress_data['results'] = {
            'output_path': final_path,
            'output_filename': final_filename,
            'summary_path': summary_path,
            'summary_filename': summary_filename,
            'total_processed': len(df),
            'category_counts': category_counts,
            'facility_counts': facility_counts,
            'processing_time': total_time
        }
        
        # Mark processing as complete
        progress_data['status'] = 'Processing complete'
        progress_data['completed'] = True
        progress_data['completed_items'] = progress_data['total_items']
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        progress_data['error'] = str(e)
        progress_data['status'] = f'Error: {str(e)}'
        progress_data['completed'] = True

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page with file upload form"""
    if request.method == 'POST':
        #check if the post request as file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        #if user does not select file, browser also submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_files(file.filename):
            # generate unique file name to avoid collisions
            unique_id = str(uuid.uuid4())
            original_filename = secure_filename(file.filename)
            filename = f"{unique_id}_{original_filename}"

            # save uploaded file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # store info in session to access in next step
            session['file_path'] = file_path
            session['original_filename'] = original_filename
            session['unique_id'] = unique_id

            return redirect(url_for('configure'))
        
        else:
            flash('Invalid file type. Only CSV and Excel files are allowed.')
            return redirect(request.url)
            
    return render_template('index.html')

@app.route('/configure', methods=['GET', 'POST'])
def configure():
    """Configure processing options"""
    if 'file_path' not in session:
        flash('No file uploaded. Please upload a file first.')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Collect configuration options
        preserve_existing = 'preserve_existing' in request.form
        batch_size = int(request.form.get('batch_size', 50))
        skip_facility = 'classify_facility' not in request.form
        skip_descriptions = 'generate_descriptions' not in request.form
        
        # Store config in session
        session['preserve_existing'] = preserve_existing
        session['batch_size'] = batch_size
        session['skip_facility'] = skip_facility
        session['skip_descriptions'] = skip_descriptions
        
        # Generate a processing ID for tracking
        processing_id = str(uuid.uuid4())
        session['processing_id'] = processing_id
        
        # Get file info from session
        file_path = session['file_path']
        unique_id = session['unique_id']
        original_filename = session['original_filename']
        
        # Initialize progress tracking
        try:
            df = pd.read_csv(file_path)
            total_items = len(df)
        except:
            total_items = 100  # Default if we can't read the file
            
        # Set up progress tracking
        processing_tasks[processing_id] = {
            'total_items': total_items,
            'completed_items': 0,
            'status': 'Initializing',
            'current_step': 'Starting processing',
            'completed': False,
            'error': None,
            'results': None
        }
        
        # Setup options for the background task
        options = {
            'preserve_existing': preserve_existing,
            'batch_size': batch_size,
            'skip_facility': skip_facility,
            'skip_descriptions': skip_descriptions
        }
        
        # Start background processing
        thread = threading.Thread(
            target=process_background_task,
            args=(processing_id, file_path, unique_id, original_filename, options)
        )
        thread.daemon = True
        thread.start()
        
        # Redirect to the processing page
        return redirect(url_for('processing'))
    
    # Preview the CSV for configuration
    try:
        df = pd.read_csv(session['file_path'])
        # Check if category column exists
        has_category = 'Product Category' in df.columns
        has_facility = 'Facility Suitability' in df.columns
        has_descriptions = 'SIMPLE_DESCRIPTION' in df.columns
        
        # Get column names and sample rows for preview
        columns = df.columns.tolist()
        sample = df.head(5).to_dict('records')
        
        return render_template('configure.html', 
                               columns=columns, 
                               sample=sample, 
                               has_category=has_category,
                               has_facility=has_facility,
                               has_descriptions=has_descriptions,
                               filename=session['original_filename'])
    except Exception as e:
        flash(f'Error reading CSV file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/processing')
def processing():
    """Show processing progress with a progress bar"""
    if 'processing_id' not in session:
        flash('No processing task initiated')
        return redirect(url_for('index'))
    
    processing_id = session['processing_id']
    
    # Check if this processing ID exists
    if processing_id not in processing_tasks:
        flash('Processing task not found')
        return redirect(url_for('index'))
    
    progress_data = processing_tasks[processing_id]
    
    # If processing is already complete, redirect to results
    if progress_data.get('completed', False) and not progress_data.get('error'):
        return redirect(url_for('results'))
    
    # Show processing page with progress bar
    return render_template('processing.html',
                         filename=session['original_filename'],
                         processing_id=processing_id,
                         total_items=progress_data['total_items'])

@app.route('/progress/<processing_id>')
def progress(processing_id):
    """Return current processing progress as JSON"""
    if processing_id not in processing_tasks:
        return jsonify({
            'error': 'Processing task not found',
            'completed': False,
            'status': 'Error: Task not found'
        })
    
    progress_data = processing_tasks[processing_id]
    
    # If processing is complete and successful, store results in session
    if progress_data.get('completed', False) and not progress_data.get('error') and progress_data.get('results'):
        results = progress_data['results']
        
        # Store output paths in session for download
        session['output_path'] = results['output_path']
        session['output_filename'] = results['output_filename']
        session['summary_path'] = results['summary_path']
        session['summary_filename'] = results['summary_filename']
        
        # Store other results for display
        session['category_counts'] = results['category_counts']
        session['facility_counts'] = results.get('facility_counts', {})
        session['total_processed'] = results['total_processed']
        session['processing_time'] = results['processing_time']
    
    # Return current progress as JSON
    return jsonify({
        'completed_items': progress_data.get('completed_items', 0),
        'total_items': progress_data.get('total_items', 100),
        'status': progress_data.get('status', 'Processing'),
        'current_step': progress_data.get('current_step', ''),
        'completed': progress_data.get('completed', False),
        'error': progress_data.get('error')
    })

@app.route('/process')
def process():
    """Legacy process endpoint - now redirects to processing page if task exists"""
    if 'processing_id' in session:
        return redirect(url_for('processing'))
        
    # If no processing ID, process normally (for backward compatibility)
    if 'file_path' not in session:
        flash('No file uploaded. Please upload a file first.')
        return redirect(url_for('index'))
        
    # Redirect to configure page as we need to start a processing task
    flash('Please configure processing options first')
    return redirect(url_for('configure'))

@app.route('/results')
def results():
    """Display processing results"""
    # Check if we have a completed processing task
    if 'processing_id' in session and session['processing_id'] in processing_tasks:
        processing_id = session['processing_id']
        progress_data = processing_tasks[processing_id]
        
        if progress_data.get('completed', False) and progress_data.get('results'):
            results = progress_data['results']
            
            return render_template('results.html',
                                original_filename=session['original_filename'],
                                output_filename=results['output_filename'],
                                total_processed=results['total_processed'],
                                category_counts=results['category_counts'],
                                facility_counts=results.get('facility_counts', {}),
                                classify_facility=len(results.get('facility_counts', {})) > 0,
                                generate_descriptions='SIMPLE_DESCRIPTION' in pd.read_csv(results['output_path']).columns,
                                processing_time=results['processing_time'],
                                summary_filename=results['summary_filename'])
    
    # If we don't have a processing task but have session data (for backward compatibility)
    if 'output_path' in session and os.path.exists(session['output_path']):
        try:
            df = pd.read_csv(session['output_path'])
            classify_facility = 'Facility Suitability' in df.columns
            generate_descriptions = 'SIMPLE_DESCRIPTION' in df.columns
            
            # Use stored category_counts if available, otherwise calculate from file
            if 'category_counts' in session:
                category_counts = session['category_counts']
            else:
                category_counts = df["Product Category"].value_counts().to_dict()
            
            # Use stored facility_counts if available, otherwise calculate from file
            if 'facility_counts' in session:
                facility_counts = session['facility_counts']
            elif classify_facility:
                facility_counts = df["Facility Suitability"].value_counts().to_dict()
            else:
                facility_counts = {}
                
            return render_template('results.html',
                                original_filename=session.get('original_filename', 'Unknown file'),
                                output_filename=session.get('output_filename', os.path.basename(session['output_path'])),
                                total_processed=len(df),
                                category_counts=category_counts,
                                facility_counts=facility_counts,
                                classify_facility=classify_facility,
                                generate_descriptions=generate_descriptions,
                                processing_time=session.get('processing_time', 0),
                                summary_filename=session.get('summary_filename', 'summary.txt'))
        except Exception as e:
            flash(f'Error loading results: {str(e)}')
            return redirect(url_for('index'))
    
    # No results available
    flash('No processing results available')
    return redirect(url_for('index'))

@app.route('/download/<file_type>')
def download(file_type):
    """Download the processed file or summary report"""
    if file_type == 'data':
        if 'output_path' not in session:
            flash('No processed file available for download')
            return redirect(url_for('index'))
        
        output_path = session['output_path']
        output_filename = session['output_filename']
        
        return send_file(output_path, as_attachment=True, download_name=output_filename)
    
    elif file_type == 'summary':
        if 'summary_path' not in session:
            flash('No summary report available for download')
            return redirect(url_for('index'))
        
        summary_path = session['summary_path']
        summary_filename = session['summary_filename']
        
        return send_file(summary_path, as_attachment=True, download_name=summary_filename)
    
    else:
        flash('Invalid download type')
        return redirect(url_for('index'))

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up session and files after completing or canceling"""
    # Clean up uploaded file
    if 'file_path' in session and os.path.exists(session['file_path']):
        try:
            os.remove(session['file_path'])
        except:
            pass
    
    # Clean up output file
    if 'output_path' in session and os.path.exists(session['output_path']):
        try:
            os.remove(session['output_path'])
        except:
            pass
    
    # Clean up summary file
    if 'summary_path' in session and os.path.exists(session['summary_path']):
        try:
            os.remove(session['summary_path'])
        except:
            pass
    
    # Remove processing task if it exists
    if 'processing_id' in session and session['processing_id'] in processing_tasks:
        del processing_tasks[session['processing_id']]
    
    # Clear session data
    session.clear()
    
    flash('Files cleaned up successfully')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)