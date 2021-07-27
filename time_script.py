import schedule
import time
import requests

def whatever():
    # requests.get()
    return
schedule.every(1).minute.do(whatever)

while True:
    schedule.run_pending()
    time.sleep(1)