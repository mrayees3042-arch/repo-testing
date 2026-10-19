import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.database as database
from backend.app_service import AppService

class GroupsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.path = str(Path(self.tmp.name) / 'test.db')
        self.patch = patch.object(database, 'DB_PATH', self.path); self.patch.start()
        with patch('backend.plc_manager.threading.Thread.start'):
            self.app = AppService()
        self.tm = self.app.manager.tag_manager; self.db = self.tm.db
        a = self.db.create_table('First'); b = self.db.create_table('Second')
        self.tables = [a,b]
        self.ids = [self.db.create_tag(t, 'Tag '+str(t), 'M', 0, '0.0', 'BOOL', 'Read Only') for t in self.tables]
    def tearDown(self):
        self.db.conn.close(); self.patch.stop(); self.tmp.cleanup()
    def test_persist_edit_and_delete(self):
        r=self.app.save_group(None,'Motors', self.ids); self.assertTrue(r['success']); gid=r['id']
        second=database.Database(); self.assertEqual(len(second.get_group_tags(gid)),2); second.conn.close()
        self.assertTrue(self.app.save_group(gid,'Pumps',[self.ids[1]])['success'])
        self.assertEqual(self.app.get_groups()[0]['name'],'Pumps')
        self.assertEqual(len(self.app.get_group_tags(gid)),1)
        self.app.delete_group(gid); self.assertEqual(self.app.get_groups(),[])
        self.assertIsNotNone(self.db.get_tag(self.ids[1]))
    def test_invalid_atomic_and_cascade(self):
        gid=self.app.save_group(None,'A',self.ids)['id']
        self.assertFalse(self.app.save_group(gid,'Changed',[99999])['success'])
        self.assertEqual(self.app.get_groups()[0]['name'],'A')
        self.assertEqual(len(self.app.get_group_tags(gid)),2)
        self.db.delete_table(self.tables[0]); self.assertEqual(len(self.app.get_group_tags(gid)),1)
        self.db.delete_tag(self.ids[1]); self.assertEqual(self.app.get_group_tags(gid),[])
        self.assertFalse(self.app.save_group(None,'  ',[])['success'])
    def test_group_reads_and_stale(self):
        gid=self.app.save_group(None,'Both',self.ids)['id']
        plc=self.app.manager.get_plc('default'); client=MagicMock(); client.connected=True; client.is_connected.return_value=True; client.read_tag.return_value=(True,False)
        plc.update(state='CONNECTED',client=client)
        self.app.monitor_group(gid); self.tm.poll_tags()
        self.assertEqual(client.read_tag.call_count,2)
        snap=self.app.get_group_snapshot(gid)
        self.assertTrue(all(r['live']['quality']=='GOOD' and r['live']['value'] is False for r in snap['tags']))
        self.tm.set_active_table(self.tables[0])
        self.assertTrue(all(r['live']['quality']=='GOOD' for r in self.app.get_group_snapshot(gid)['tags']))
        self.tm.set_polling(True, self.tables[0]); client.read_tag.reset_mock(); self.tm.poll_tags()
        self.assertEqual(client.read_tag.call_count,2, 'Overlapping table/group tags should be read once')
        self.app.monitor_group(None)
        self.assertTrue(all(r['live']['quality']=='STALE' for r in self.app.get_group_snapshot(gid)['tags']))
        self.app.monitor_group(gid); plc['state']='DISCONNECTED'
        self.assertFalse(self.app.get_group_snapshot(gid)['connected'])
        self.assertTrue(all(r['live']['quality']=='STALE' for r in self.app.get_group_snapshot(gid)['tags']))
    def test_theme_persistence(self):
        self.assertTrue(self.app.set_theme('light'))
        self.assertEqual(self.app.get_theme(),'light')
        self.assertFalse(self.app.set_theme('other'))
        self.assertEqual(self.app.get_theme(),'light')

if __name__=='__main__': unittest.main()
