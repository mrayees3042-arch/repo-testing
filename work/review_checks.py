import sys, unittest, threading
from unittest.mock import MagicMock, patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.database as database
database.DB_PATH = ':memory:'
import test_verification
result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(test_verification))
assert result.wasSuccessful()
print('EXISTING_SUITE',result.testsRun,len(result.failures),len(result.errors))
from backend.tag_manager import TagManager
from backend.plc_manager import PLCManager
from backend.app_service import AppService
with patch('backend.plc_manager.threading.Thread.start'):
    service=AppService()
manager=service.manager
plc=manager.get_plc('default')
client=MagicMock();client.connected=True;client.is_connected.return_value=True
client.write_tag.return_value=(True,'Success')
plc.update(state='CONNECTED',client=client)
tm=manager.tag_manager
tag={'id':1,'name':'REAL test','area':'M','db_number':0,'address':'4','data_type':'REAL','access_mode':'Read/Write'}
tm.db.get_tag=MagicMock(return_value=tag)
for requested,readback in [(1000000,1000090),(0.0005,0)]:
    client.read_tag.return_value=(True,readback)
    print('REAL_MISMATCH',requested,readback,tm.write_tag(1,requested))
    assert not tm.write_tag(1,requested)[0]
import struct
client.read_tag.return_value=(True,struct.unpack('>f',struct.pack('>f',123.456))[0])
assert tm.write_tag(1,123.456)[0]
tm._update_live_tag(1,12,'GOOD',None,0)
tm.set_polling(False)
manager.disconnect('default')
print('OFFLINE_WRITE_DETAILS',service.get_tag_details_for_write(1))
assert service.get_tag_details_for_write(1)['quality']=='STALE'
# Reconnect probe blocks while manual Disconnect completes.
plc['state']='CONNECTION LOST';plc['last_reconnect_attempt']=0
entered=threading.Event();resume=threading.Event()
def probe(*a,**k):entered.set();resume.wait(3);return True,'open'
client.test_tcp_connection.side_effect=probe
client.connect.return_value=(True,'connected',1)
client.get_cpu_state.return_value=(True,'RUN','ok')
manager._running=True
t=threading.Thread(target=manager._health_monitor_loop);t.start()
assert entered.wait(3)
manager.disconnect('default')
print('STATE_AFTER_MANUAL_DISCONNECT',plc['state'])
manager._running=False;resume.set();t.join(4)
print('STATE_AFTER_PENDING_RETRY',plc['state'],'CONNECT_CALLS',client.connect.call_count)
assert plc['state']=='DISCONNECTED'
assert client.connect.call_count==0
