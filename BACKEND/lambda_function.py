from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi
from invest import create_app

app = create_app()
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app, lifespan="off")