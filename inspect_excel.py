import pandas as pd

file_path = "/Users/anandumv/Downloads/chatbot/GPT Projects (1).xlsx"
try:
    df = pd.read_excel(file_path)
    print("Columns:", list(df.columns))
    print("First row:", df.iloc[0].to_dict())
    print("Total rows:", len(df))
except Exception as e:
    print(f"Error reading excel: {e}")
