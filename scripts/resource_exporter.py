"""Read-only host metrics. CPU/RAM only; Apple GPU metrics intentionally absent."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import time
import psutil
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!='/metrics':self.send_error(404);return
        memory=psutil.virtual_memory()
        text=(f'manufacturing_cpu_percent {psutil.cpu_percent()}\n'
              f'manufacturing_ram_used_bytes {memory.used}\n'
              f'manufacturing_ram_available_bytes {memory.available}\n'
              f'manufacturing_ram_total_bytes {memory.total}\n'
              f'manufacturing_ram_percent {memory.percent}\n')
        self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(text.encode())
    def log_message(self,*args):pass
if __name__=='__main__':
    # Localhost binding is reachable via Docker Desktop's host.docker.internal.
    psutil.cpu_percent();HTTPServer(('127.0.0.1',9108),Handler).serve_forever()
