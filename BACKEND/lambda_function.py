# lambda_function.py — new file, sits next to run.py
from mangum import Mangum
from invest import create_app

app = create_app()
handler = Mangum(app)