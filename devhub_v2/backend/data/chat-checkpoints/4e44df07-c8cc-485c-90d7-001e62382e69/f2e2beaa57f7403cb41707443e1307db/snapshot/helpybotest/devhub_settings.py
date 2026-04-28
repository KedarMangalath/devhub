from helpybotest.settings import *
# DevHub: strip X-Frame-Options so the in-IDE preview iframe can load the app
MIDDLEWARE = [m for m in MIDDLEWARE if 'XFrameOptionsMiddleware' not in m]
