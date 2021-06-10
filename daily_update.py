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

r.put(f"http://www.open-projections.com/projections/{y}-{m}-{d}")
