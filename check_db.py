import pixeltable as pt
import sys

def check_counts():
    try:
        pt.init()
        t = pt.get_table("projects")
        df = t.collect()
        print(f"Total projects in table: {len(df)}")
        
        whitefield_2bhk = []
        for p in df:
            loc = str(p['location']).lower()
            conf = str(p['configuration']).lower().replace(" ", "")
            if "whitefield" in loc and "2bhk" in conf:
                whitefield_2bhk.append(p['name'])
        
        print(f"Projects with 2BHK in Whitefield: {len(whitefield_2bhk)}")
        for name in whitefield_2bhk:
            print(f"- {name}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_counts()
