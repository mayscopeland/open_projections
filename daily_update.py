import requests as r
from datetime import date, timedelta

# Build yesterday's game logs
yesterday = date.today() - timedelta(1)

y = yesterday.strftime("%Y")
m = yesterday.strftime("%m")
d = yesterday.strftime("%d")

r.put(f"http://www.open-projections.com/stats/{y}/{m}/{d}")

# Build projections for today
today = date.today()

y = today.strftime("%Y")
m = today.strftime("%m")
d = today.strftime("%d")

r.put(f"http://www.open-projections.com/v3/projections/{y}-{m}-{d}")

# In preseason, build an opening day projection, too
if m in ["1","2","3","10","11","12"]:
    if m in ["10", "11", "12"]:
        y = date.today().year + 1
    r.put(f"http://www.open-projections.com/v3/projections/{y}-04-01")

