import pandas as pd
import sys

file_path = "GPT Projects (1).xlsx"
try:
    df = pd.read_excel(file_path)
    print("Columns in", file_path, ":")
    print(df.columns.tolist())
    print("\nFirst row sample:")
    print(df.iloc[0].to_dict())
except Exception as e:
    print(f"Error: {e}")
