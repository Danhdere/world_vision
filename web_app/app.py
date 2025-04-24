from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import pandas as pd
import uuid
import time
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI

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

def allowed_files(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

if __name__ == '__main__':
    app.run(debug=True)
