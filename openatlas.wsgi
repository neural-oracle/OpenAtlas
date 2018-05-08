import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append('/var/www/html')
sys.path.append('/var/www/html/myenv/lib/python3.5/site-packages')

from openatlas import app as application
