from invest.routes import headlines_page
from TESTING.stock_headlines import headlines_page as hp
import json
from datetime import datetime

from invest import create_app

app = create_app()

with app.test_request_context("/headlines"):
    data = headlines_page("TCS")
    data2=hp("TCS")
# print(data)

# print(data2)

data = data.get_json()
data2=data2.get_json()

def compare(a, b, path="root"):
    if type(a) != type(b):
        print(f"{path}: TYPE MISMATCH")
        print(f"  Route: {type(a).__name__}")
        print(f"  Test : {type(b).__name__}")
        return

    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())

        for key in sorted(all_keys):
            if key not in a:
                print(f"{path}.{key}: Missing in Route")
            elif key not in b:
                print(f"{path}.{key}: Missing in Test")
            else:
                compare(a[key], b[key], f"{path}.{key}")

    elif isinstance(a, list):
        if len(a) != len(b):
            print(f"{path}: List length differs")
            print(f"  Route: {len(a)}")
            print(f"  Test : {len(b)}")

        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f"{path}[{i}]")

    elif isinstance(a, tuple):
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f"{path}[{i}]")

    else:
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) > 0.02:          # ignore tiny fp jitter from live API calls
                print(f"{path}: DIFFERENT")
                print(f"  Route: {a}")
                print(f"  Test : {b}")
        elif a != b:
            print(f"{path}: DIFFERENT")
            print(f"  Route: {a}")
            print(f"  Test : {b}")

if data==data2:
    print("MATCH")
else:
    compare(data, data2)


