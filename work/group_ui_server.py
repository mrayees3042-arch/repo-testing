"""Isolated UI test server: real service/database, simulated PLC, no network PLC calls."""
import sys, json, tempfile
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.database as database
from backend.app_service import AppService
root=Path(__file__).resolve().parents[1]
tmp=tempfile.TemporaryDirectory(dir=root/'work')
database.DB_PATH=str(Path(tmp.name)/'ui.db')
with patch('backend.plc_manager.threading.Thread.start'):
    app=AppService()
tm=app.manager.tag_manager
for name,tags in [('Cooling',[('Pump running','BOOL','0.0'),('Temperature','REAL','4')]),('Power',[('Motor count','INT','8')])]:
    table=tm.db.create_table(name)
    for title,kind,address in tags: tm.db.create_tag(table,title,'M',0,address,kind,'Read Only')
client=MagicMock(); client.connected='--disconnected' not in sys.argv
client.is_connected.side_effect=lambda: client.connected
counter=0
memory={}
def read(*args):
    global counter
    if not client.connected: return False, 'Disconnected'
    if args in memory: return True, memory[args]
    counter+=1
    return True, (counter%2==0 if args[-1]=='BOOL' else counter)
client.read_tag.side_effect=read
def write(*args):
    memory[args[:-1]]=args[-1]
    return True, 'Written to test memory'
def connect(*args):
    client.connected=True
    return True, 'Connected to test memory', 1
def disconnect(): client.connected=False
client.write_tag.side_effect=write
client.connect.side_effect=connect
client.disconnect.side_effect=disconnect
client.ping.return_value=(True, 'Test ping', 1)
client.get_cpu_state.return_value=(True, 'RUN', '')
# Replace all temporary diagnostic clients too; this server never contacts a PLC.
import backend.plc_manager as plc_module
plc_module.S7Client=lambda: client
plc=app.manager.get_plc('default');plc.update(state='CONNECTED' if client.connected else 'DISCONNECTED',client=client,cpu_state='RUN' if client.connected else 'UNKNOWN')
allowed={'get_status','get_all_tables','get_tags_for_table','set_active_table','set_polling','get_live_tags','get_groups','get_group_tags','save_group','delete_group','monitor_group','get_group_snapshot','get_theme','set_theme','connect','disconnect','reconnect','ping','test_s7_communication','create_table','delete_table','update_table','create_tag','update_tag','delete_tag','get_tag_details_for_write','resolve_tag_address','write_tag'}
bridge='''<script>window.pywebview={api:new Proxy({}, {get:(_,method)=>method==='then'?undefined:(...args)=>fetch('/api/'+String(method),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(args)}).then(async r=>{const data=await r.json();if(!r.ok)throw Error(data.error);return data;})})};</script>'''
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(root/'frontend'),**kw)
    def log_message(self,*a): pass
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            body=(root/'frontend'/'index.html').read_text(encoding='utf-8').replace('<head>', '<head>'+bridge).encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body)
        else: super().do_GET()
    def do_POST(self):
        method=self.path.removeprefix('/api/')
        try:
            args=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if method=='test_connection':
                client.connected=bool(args[0]);plc['state']='CONNECTED' if args[0] else 'DISCONNECTED'; result=True
            elif method in allowed:
                if method in ('get_group_snapshot','get_live_tags'): tm.poll_tags()
                result=getattr(app,method)(*args)
            else: raise ValueError('Test API method not allowed')
            body=json.dumps(result).encode();self.send_response(200)
        except Exception as e:
            body=json.dumps({'error':str(e)}).encode(); self.send_response(500)
        self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
server=HTTPServer(('127.0.0.1',0),Handler)
(root/'work'/'ui_test_port.txt').write_text(str(server.server_port))
print('Isolated UI test server ready',flush=True)
try: server.serve_forever()
finally: tm.db.conn.close();tmp.cleanup()
