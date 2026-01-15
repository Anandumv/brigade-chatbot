import pixeltable as pxt
import time

try:
    pxt.drop_table('brigade.projects', ignore_errors=True)
    print("Drop issued.")
    time.sleep(5)
    print("Waited 5 seconds.")
    # Check if exists
    try:
        t = pxt.get_table('brigade.projects')
        print("Table STILL exists!")
    except:
        print("Table gone.")
except Exception as e:
    print(e)
