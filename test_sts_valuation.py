import copy,json,struct,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from prices import PRICES
from vehicles import fleet,read_sts
from company import assess
from savesync import App
from sts_equipment import decode_equipment,DecodeError


def text(value):
    data=value.encode('ascii')+b'\0';return struct.pack('<H',len(data))+data


def record(guid,unlocked=True,water=True,duplicate_addon=False):
    addons=['chevrolet_ck1500_diff_lock','chevrolet_ck1500_diff_lock' if duplicate_addon else 'chevrolet_ck1500_bumper_rear_default']
    data=text('chevrolet_ck1500')+text('')+text(guid)
    after_guid=len(data)
    data+=struct.pack('<II',0,len(addons))
    for key in addons:data+=text(key)+text('BoneChassis_cdt')+b'\x01'+b'\0'*24
    data+=text('us_scout_old_engine_1')+text('g_scout_offroad')+text('w_scout_default')+text('wheels_scout1')+text('rim_1')+text('highway_1')+struct.pack('<f',.4)+text('chevrolet_ck1500_suspension_high')
    data+=struct.pack('<f',50)
    if water:data+=struct.pack('<f',0)
    data+=struct.pack('<5I',0,0,0,0,0)+struct.pack('<I',4)+struct.pack('<4I',0,0,0,0)
    data+=bytes([int(unlocked),0])+text('')+struct.pack('<3I',0,0,4)+struct.pack('<4f',0,0,0,0)
    return data,after_guid


def write(path,*records):
    payload=b''.join(records);path.write_bytes(struct.pack('<I',len(payload))+zlib.compress(payload))


G1='{12345678-1234-1234-1234-123456789abc}'
G2='{22345678-1234-1234-1234-123456789abc}'


class StsValuationTests(unittest.TestCase):
    def setUp(self):
        self.save={'persistentProfileData':{'money':100,'experience':1234,'rank':2,'ownedTrucks':{'chevrolet_ck1500':1},'trucksInWarehouse':[],'addons':{},'unlockedItemNames':{}},'garagesData':{},'upgradesGiverData':{}}
    def test_both_layouts_and_addon_multiplicity(self):
        for water in (False,True):
            data,start=record(G1,water=water,duplicate_addon=True)
            desc=decode_equipment(data,start,len(data))
            self.assertTrue(desc['isUnlocked'])
            self.assertEqual(desc['addons'],[{'name':'chevrolet_ck1500_diff_lock'}]*2)
            self.assertEqual(desc['wheelsType'],'wheels_scout1')
            self.assertEqual(desc['tires'],'highway_1')
    def test_reject_incomplete_and_wrong_addon_count(self):
        data,start=record(G1)
        with self.assertRaises(DecodeError):decode_equipment(data[:-5],start,len(data)-5)
        corrupt=data[:start+4]+struct.pack('<I',3)+data[start+8:]
        with self.assertRaises(DecodeError):decode_equipment(corrupt,start,len(corrupt))
    def test_exact_value_locked_npc_excluded_and_files_unchanged(self):
        before=copy.deepcopy(self.save)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sts_level_us_01_01.cfg'
            write(path,record(G2,unlocked=False)[0],record(G1,duplicate_addon=True)[0])
            original=path.read_bytes();data=fleet(self.save,sts_paths=[path])
            self.assertEqual(len(data['map_descriptors']),1)
            result=assess(self.save,map_trucks=data['map_descriptors'])
            parts=['us_scout_old_engine_1','g_scout_offroad','w_scout_default','chevrolet_ck1500_suspension_high']+['chevrolet_ck1500_diff_lock']*2
            expected=100+PRICES['trucks']['chevrolet_ck1500']['price']+sum(PRICES['parts'][key]['price'] for key in parts)+PRICES['tires']['wheels_scout1|highway_1']['price']
            self.assertEqual(result['total'],expected)
            self.assertTrue(result['complete']);self.assertEqual(result['map_count'],1)
            self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.save,before)
    def test_ambiguity_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sts_level_us_01_01.cfg';write(path,record(G1)[0],record(G2)[0])
            ambiguous=fleet(self.save,sts_paths=[path])
            self.assertFalse(ambiguous['map_descriptors'])
            resolved=fleet(self.save,sts_paths=[path],confirmed_guids={G2.strip('{}')})
            self.assertEqual(len(resolved['map_descriptors']),1)
            self.assertEqual(resolved['map_descriptors'][0][0]['globalId'],G2)
    def test_duplicate_records_dedupe_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);one=folder/'sts_level_us_01_01.cfg';two=folder/'sts_level_us_01_02.cfg'
            write(one,record(G1)[0]);data=fleet(self.save,sts_paths=[one,one])
            self.assertEqual(len(data['map_descriptors']),1)
            write(two,record(G1)[0]);conflict=fleet(self.save,sts_paths=[one,two])
            self.assertFalse(conflict['map_descriptors'])
            self.assertTrue(any('sprzecznych' in note for note in conflict['notes']))
            write(one,record(G1,unlocked=False)[0]);active=fleet(self.save,sts_paths=[one,two])
            self.assertEqual(len(active['map_descriptors']),1)
            self.assertIn('Smithville',active['map_descriptors'][0][1])
    def test_ui_reprices_manual_load_confirm_and_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);main=folder/'CompleteSave.cfg'
            main.write_text(json.dumps({'CompleteSave':{'SslValue':self.save}}),encoding='utf-8')
            root=tk.Tk();root.withdraw()
            try:
                app=App(root);app.guest.set(str(main));app.read_saves()
                self.assertEqual(app.valuations['guest']['map_count'],0)
                path=folder/'sts_level_us_01_01.cfg';write(path,record(G1)[0],record(G2)[0])
                with patch('savesync.filedialog.askopenfilenames',return_value=[str(path)]):app.choose_vehicle_sts()
                self.assertEqual(app.valuations['guest']['map_count'],0)
                candidate=next(node for node,r in app.vehicle_candidates.items() if r['guid']==G2.strip('{}'))
                app.vehicle_tree.selection_set(candidate);app.confirm_vehicle_sts()
                self.assertEqual(app.valuations['guest']['map_count'],1)
                self.assertTrue(app.valuations['guest']['complete'])
                before=app.valuations['guest']['total'];app.amount.set('50');app.mode.set('Dodaj kwotę');app.preview()
                self.assertIn(f'{before+50:,}'.replace(',',' '),app.report.get('1.0','end'))
                original_sts=path.read_bytes()
                with patch('savesync.messagebox.showinfo'):app.save()
                self.assertEqual(app.valuations['guest']['map_count'],1)
                self.assertEqual(app.valuations['guest']['total'],before+50)
                self.assertEqual(path.read_bytes(),original_sts)
                app.reset_vehicle_sts();self.assertEqual(app.valuations['guest']['map_count'],0)
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