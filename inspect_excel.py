import pandas as pd
import os

file_path = "Test - Projects.xlsx"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

try:
    df = pd.read_excel(file_path)
    print("Columns:", list(df.columns))
    print("\nFirst 3 rows:")
    print(df.head(3).to_string())
    
    # Check data types
    print("\nData Types:")
    print(df.dtypes)
except Exception as e:
    print(f"Error reading excel: {e}")
