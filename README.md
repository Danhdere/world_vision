# world_vision
The objective of this project is to identify and test AI tools that can streamline the categorization of corporate product donations and automate dependency analysis. Our goal is to develop a classification system that assigns products to relevant categories, determines the ideal end-user, and flags items requiring additional components for functionality. By leveraging AI-powered tools, we will evaluate different models for their ability to process medical supply data, refine categorization accuracy, and optimize decision-making. Based on our findings, we will recommend the most effective AI solution for improving efficiency and consistency in corporate donation assessments.

# World Vision Product Categorization Tool

## What is this program?
This is a computer program that helps organize and categorize donated products. It can:
- Put products into the right categories
- Figure out who would use each product
- Tell you if a product needs other parts to work

## What you need before starting:
1. A computer that can connect to the internet
2. A program called "Python" (we'll help you install this)
3. A special code called an "OpenAI API key" (we'll help you get this)

## Step 1: Installing Python
1. Open your internet browser (like Chrome, Safari, or Firefox)
2. Go to this website: https://www.python.org/downloads/
3. Click the big yellow button that says "Download Python"
4. Find the downloaded file (usually in your "Downloads" folder)
5. Double-click the downloaded file to start installing
6. **VERY IMPORTANT**: On the first screen of the installer, check the box that says "Add Python to PATH"
7. Click "Install Now"
8. Wait for the installation to finish
9. Click "Close" when it's done

## Step 2: Getting your OpenAI API Key
1. Open your internet browser
2. Go to this website: https://platform.openai.com/
3. Click "Sign up" to create an account (or "Log in" if you already have one)
4. Once you're logged in, look for your picture or initials in the top right corner
5. Click on your picture/initials
6. Click on "View API keys"
7. Click "Create new secret key"
8. **VERY IMPORTANT**: Copy the key that appears and save it somewhere safe (like in a text file on your computer)
   - You won't be able to see this key again after you close the window
   - Make sure to copy the entire key

Downloading the Program from GitHub

Open your web browser (Chrome, Firefox, Safari, Edge, etc.).
Go to https://github.com/Danhdere/world_vision
Go to the GitHub page where the program lives. You’ll see something like this at the top right:
 Code ▼
Click “Code” to open a menu.
Choose “Download ZIP”.
This saves a file called something like world_vision.zip to your computer’s Downloads folder.
Find the ZIP file in your Downloads folder.
Unzip (extract) it:

Windows: Right-click the .zip file ➔ “Extract All…” ➔ click “Extract.”

Mac: Double-click the .zip file.

A new folder with the program’s files will appear. It should be named world_vision

## Step 3: Creating an OpenAI API Account to pay for API calls
1. Add Payment & Fund Your OpenAI API Account
   Even though OpenAI gives you a free trial credit when you first sign up, you’ll need to add a payment method if you want to keep using       the API after that. Here’s how:

2. Log in to the OpenAI Dashboard
• Open your web browser and go to https://platform.openai.com/
• Click Log in, enter your OpenAI account email and password.

3. Go to the Billing Page
• In the left-hand menu, click Billing (it may look like a little credit-card icon).
• This shows you your current balance and usage history.

4. Add a Payment Method
• Under “Payment methods,” click Add a payment method.
• Enter your credit/debit card details (card number, expiration date, CVC) or choose another supported method.
• Click Save.

5. Review Pricing & Usage
• On that same page you’ll see “API pricing” links (for models like GPT-4, GPT-3.5). Click one to see per-token rates.
• You can set a monthly spending limit or usage alerts if you want to cap how much you spend.

6. Check Your Balance Anytime
• Your current credit (trial or paid) shows at the top of the Billing page.
• As you make API calls in your code, the cost is deducted here in real time.

7. Understanding Charges
• Each API call is billed by “tokens” (roughly words or word-pieces).
• For example, asking for 100–200 words from GPT-3.5 might cost only a few cents.
• Always refer back to the pricing page so there are no surprises at the end of the month.

Best Practices:
Monitor regularly: Check the “Usage” tab once a week.
Set alerts: Configure email or Slack alerts for when you hit, say, 75% of your budget.
Optimize your code: Batch requests or shorten prompts to save tokens.

## Step 4: Setting up the Program
1. Find the folder called "world_vision-main" on your computer. Should be in the downloads folder on your computer.
2. Inside the "world_vision-main" folder, find the "web_app" folder
3. Go to the main.py file. Open it. And insert the api key where the api_key = ... line is.
   (Replace "your_api_key_here" with the API key you saved earlier)
   
## Step 5: Installing Required Programs
1. Open the Terminal (Mac) or Command Prompt (Windows):
   - On Mac: Click the magnifying glass in the top right, type "Terminal", and press Enter
   - On Windows: Click the Start button, type "cmd", and press Enter
2. Type these commands one at a time (press Enter after each one):
   ```
   cd Desktop/Downloads/world_vision/web_app
   pip install flask pandas openai python-dotenv Werkzeug
   "probably optional"
   ```
3. Wait for the installation to finish (you'll see your cursor again when it's done)

## Step 6: Running the Program
1. Make sure you're still in the Terminal/Command Prompt
2. Type this command and press Enter:
   ```
   python app.py
   ```
5. Press Enter

## How to Use the Program
1. On the website that opens:
   - Click the "Choose File" button
   - Find and select your file (it should be a CSV or Excel file)
   - Click "Upload"
2. Wait for the program to process your file
3. When it's done, you'll see the results on the screen
4. You can download the results by clicking the "Download" button

## What kind of files can I use?
- The program works with two types of files:
  - CSV files (they usually end in .csv)
  - Excel files (they usually end in .xlsx)
- Your file should be smaller than 16MB
- Your file should have information about products, like:
  - Product names
  - Descriptions
  - Categories

## Need Help?
1. Look at the error messages in the Terminal/Command Prompt
2. Contact the person who gave you this program
3. Make sure you followed all the steps correctly

## Important Things to Remember
1. You must have an OpenAI API key for the program to work
2. The API key must be in the ".env" file
3. You need to be connected to the internet
4. The program will create two new folders:
   - "uploads" (where your files are stored)
   - "results" (where the processed files are saved)

