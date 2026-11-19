import copy,json,struct,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from vehicles import fleet,read_sts,companion_files
from savesync import App


def encoded(text):
    raw=text.encode('ascii')+b'\0'
    return struct.pack('<H',len(raw))+raw


def sts(path,kind='chevrolet_ck1500',guid='{12345678-1234-1234-1234-123456789abc}'):
    payload=encoded(kind)+encoded('')+encoded(guid)+b'\0'*20+encoded('chevrolet_ck1500_suspension_high')
    raw=struct.pack('<I',len(payload))+zlib.compress(payload)
    path.write_bytes(raw)
    return raw


class VehicleTests(unittest.TestCase):
    def setUp(self):
        self.truck={'type':'chevrolet_ck1500','globalId':'truck1','engine':{'name':'us_scout_old_engine_1'},'gearbox':{'name':'g_scout_offroad'},'suspension':'chevrolet_ck1500_suspension_high','addons':[{'name':'chevrolet_ck1500_diff_lock'}]}
        self.save={'persistentProfileData':{'money':100,'experience':1000,'rank':2,'ownedTrucks':{'chevrolet_ck1500':1},'trucksInWarehouse':[],'addons':{},'unlockedItemNames':{}},'garagesData':{'level_us_01_01':{'slotsDatas':{'slot':{'truckDesc':self.truck}}}},'upgradesGiverData':{}}
    def test_garage_parts_location_and_read_only(self):
        before=copy.deepcopy(self.save)
        data=fleet(self.save,sts_paths=[])
        self.assertEqual(len(data['trucks']),1)
        truck=data['trucks'][0]
        self.assertEqual(truck['location'],'Michigan — Czarna Rzeka — Garaż')
        self.assertIn('chevrolet_ck1500_suspension_high',[p['id'] for p in truck['parts']])
        self.assertTrue(any(p['kind']=='Silnik' and p['id']=='us_scout_old_engine_1' for p in truck['parts']))
        self.assertEqual(self.save,before)
    def test_global_warehouse_not_retained_map(self):
        self.save['garagesData']={}
        truck=copy.deepcopy(self.truck);truck['retainedMapId']='level_us_01_02'
        self.save['persistentProfileData']['trucksInWarehouse']=[truck,copy.deepcopy(truck)]
        data=fleet(self.save,sts_paths=[])
        self.assertEqual(len(data['trucks']),1)
        self.assertIn('globalny',data['trucks'][0]['location'])
        self.assertNotIn('Smithville',data['trucks'][0]['location'])
    def test_each_physical_truck_and_unknown_map(self):
        self.save['persistentProfileData']['ownedTrucks']['chevrolet_ck1500']=3
        clone=copy.deepcopy(self.truck);clone['globalId']='truck2'
        self.save['persistentProfileData']['trucksInWarehouse']=[clone]
        data=fleet(self.save,sts_paths=[])
        self.assertEqual(sum(t['qty'] for t in data['trucks']),3)
        self.assertEqual(sum(not bool(t['parts']) for t in data['trucks']),1)
    def test_sts_slot_selection_and_unconfirmed_records(self):
        self.save['garagesData']={}
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);main=folder/'CompleteSave1.cfg';main.write_text('{}')
            correct=folder/'1_sts_level_us_01_02.cfg';raw=sts(correct)
            sts(folder/'sts_level_us_01_01.cfg')
            sts(folder/'2_sts_level_us_01_02.cfg')
            self.assertEqual(companion_files(main),[correct])
            record=read_sts(correct)[0]
            self.assertEqual(record['location'],'Michigan — Zapora Smithville — Na mapie')
            self.assertEqual(record['parts'][0]['id'],'chevrolet_ck1500_suspension_high')
            result=fleet(self.save,main)
            self.assertEqual(result['files'],1)
            self.assertEqual(len(result['trucks'][0]['candidates']),1)
            self.assertFalse(result['trucks'][0]['parts'])
            self.assertTrue(result['trucks'][0]['location'].startswith('Możliwe:'))
            self.assertIn('własność niepotwierdzona',result['trucks'][0]['state'])
            self.assertEqual(correct.read_bytes(),raw)
    def test_corrupt_sts_and_unknown_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            bad=Path(folder)/'sts_level_us_01_01.cfg';bad.write_bytes(b'broken')
            data=fleet(self.save,sts_paths=[bad])
            self.assertEqual(len(data['trucks']),1)
            self.assertTrue(any(bad.name in n for n in data['notes']))
        malformed={'persistentProfileData':{'trucksInWarehouse':1},'garagesData':[]}
        self.assertTrue(fleet(malformed,sts_paths=[])['notes'])
    def test_ui_tree_expand_search_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);main=folder/'CompleteSave.cfg'
            main.write_text(json.dumps({'CompleteSave':{'SslValue':self.save}}),encoding='utf-8')
            root=tk.Tk();root.withdraw()
            try:
                app=App(root)
                self.assertEqual(app.notebook.tab(app.vehicle_tab,'text'),app.ui.text('Pojazdy'))
                app.guest.set(str(main));app.read_saves();app.notebook.select(app.vehicle_tab)
                roots=app.vehicle_tree.get_children()
                self.assertEqual(len(roots),1)
                self.assertTrue(app.vehicle_tree.get_children(roots[0]))
                app.expand_vehicles(True);self.assertTrue(app.vehicle_tree.item(roots[0],'open'))
                app.expand_vehicles(False);self.assertFalse(app.vehicle_tree.item(roots[0],'open'))
                app.vehicle_search.set('CK1500');self.assertEqual(len(app.vehicle_tree.get_children()),1)
                app.vehicle_search.set('nonexistent');self.assertFalse(app.vehicle_tree.get_children())
                app.vehicle_search.set('');app.guest.set('changed')
                self.assertFalse(app.vehicle_tree.get_children())
                app.guest.set(str(main));app.read_saves()
                wrong=folder/'1_sts_level_us_01_01.cfg';sts(wrong)
                with patch('savesync.filedialog.askopenfilenames',return_value=[str(wrong)]),patch('savesync.messagebox.showerror') as error:
                    app.choose_vehicle_sts();error.assert_called_once()
            finally:root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=__import__('unittest.mock',fromlist=['patch']).patch('savesync.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__=='__main__':unittest.main()


# Keep legacy UI assertions independent of the machine's saved language.