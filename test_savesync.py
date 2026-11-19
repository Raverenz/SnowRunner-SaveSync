import copy, json, tempfile, unittest
from pathlib import Path
from savesync import load, merge, write_save, App, upgrade_info, upgrade_rows
from unittest.mock import patch
import tkinter as tk
from upgrade_editor import apply_manual
from unlock_ids import UNLOCK_IDS

class Tests(unittest.TestCase):
    def setUp(self):
        self.host = {'persistentProfileData':{'money':900,'unlockedItemNames':{'engine_a':False,'engine_b':False}},'upgradesGiverData':{'map':{'a':2,'b':1,'c':0}}}
        self.guest = {'persistentProfileData':{'money':100,'unlockedItemNames':{'own':False}},'upgradesGiverData':{'map':{'a':1,'own':2}},'trucks':[{'fuel':10}],'missions':{'x':1}}
    def test_union_and_no_unrelated_changes(self):
        original = copy.deepcopy(self.guest)
        out,changes = merge(self.host,self.guest)
        self.assertEqual(self.guest,original)
        self.assertEqual(out['trucks'],original['trucks'])
        self.assertEqual(out['missions'],original['missions'])
        self.assertEqual(out['persistentProfileData']['money'],100)
        self.assertEqual(set(out['persistentProfileData']['unlockedItemNames']),{'own','engine_a','engine_b'})
        self.assertEqual(out['upgradesGiverData']['map'],{'a':2,'own':2})
        self.assertEqual(merge(self.host,out)[1],[])
    def test_money(self):
        self.assertEqual(merge(None,self.guest,False,'Dodaj kwotę',50)[0]['persistentProfileData']['money'],150)
        self.assertEqual(merge(None,self.guest,False,'Ustaw saldo',0)[0]['persistentProfileData']['money'],0)
        for value in [-1,2147483647]:
            with self.assertRaises(ValueError): merge(None,self.guest,False,'Dodaj kwotę',value)
    def test_backup_and_format(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'CompleteSave1.cfg'
            raw = b'\xef\xbb\xbf'+json.dumps({'CompleteSave1':{'SslValue':self.guest}}).encode()+b'\x00'
            path.write_bytes(raw)
            doc,block,original,bom,suffix = load(path)
            block['persistentProfileData']['money'] = 500
            backup = write_save(path,doc,original,bom,suffix)
            self.assertEqual(backup.read_bytes(),raw)
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertTrue(path.read_bytes().endswith(b'\x00'))
            self.assertEqual(load(path)[1]['persistentProfileData']['money'],500)
            with self.assertRaises(ValueError): write_save(path,doc,original,bom,suffix)
    def test_reject_unknown_structure(self):
        self.host['upgradesGiverData']['map']['a'] = 3
        with self.assertRaises(ValueError): merge(self.host,self.guest)
    def test_ui(self):
        root = tk.Tk(); root.withdraw()
        app = App(root); root.update_idletasks()
        self.assertFalse(app.money_box.winfo_manager())
        self.assertIsNone(app.loaded_guest)
        root.destroy()

    def test_catalog(self):
        region,location,name,trucks = upgrade_info('level_us_01_01','US_01_01_UPGRADE_CK_SUSPENSION')
        self.assertEqual((region,location,name,trucks),('Michigan','Czarna Rzeka','Podwyższone zawieszenie','Chevrolet CK1500'))
        self.assertEqual(upgrade_info('level_us_01_04','US_01_04_UPG_1'),upgrade_info('level_us_01_04_new','US_01_04_UPG_1'))
        self.assertIn('Nieznane ulepszenie',upgrade_info('mod_map','UNKNOWN')[2])
        rows = upgrade_rows(self.host,self.guest)
        self.assertTrue(any(r[7] == 'A' and r[6] == 'Do synchronizacji' for r in rows))
    def test_ui_load_money_and_write(self):
        with tempfile.TemporaryDirectory() as d:
            hp,gp = Path(d)/'host.cfg',Path(d)/'guest.cfg'
            for p,save in [(hp,self.host),(gp,self.guest)]:
                p.write_text(json.dumps({'CompleteSave':{'SslValue':save}}),encoding='utf-8')
            root = tk.Tk(); root.withdraw()
            try:
                app = App(root)
                app.host.set(str(hp)); app.guest.set(str(gp))
                app.read_saves(); root.update_idletasks()
                self.assertEqual(app.money_box.winfo_manager(),'pack')
                self.assertIn('100',app.balance.get())
                app.mode.set('Dodaj kwotę'); app.amount.set('50'); app.preview()
                self.assertIsNotNone(app.pending)
                with patch('savesync.messagebox.showinfo'): app.save()
                self.assertEqual(load(gp)[1]['persistentProfileData']['money'],150)
                self.assertEqual(app.mode.get(),'Bez zmian')
                self.assertIn('150',app.balance.get())
                app.preview(); self.assertIsNone(app.pending)
                app.guest.set(str(gp)+'other')
                self.assertFalse(app.money_box.winfo_manager())
                self.assertIsNone(app.loaded_guest)
            finally: root.destroy()

    def test_manual_add_remove_and_inventory(self):
        component=UNLOCK_IDS['US_01_01_UPGRADE_CK_SUSPENSION']
        guest=copy.deepcopy(self.guest)
        guest['persistentProfileData']['discoveredUpgrades']={'level_us_01_01':{'current':0,'all':7}}
        guest['trucks']=[{'suspension':component,'fuel':12}]
        original=copy.deepcopy(guest)
        unlocked,changes=apply_manual(guest,{component:True})
        self.assertEqual(guest,original)
        self.assertIn(component,unlocked['persistentProfileData']['unlockedItemNames'])
        self.assertIs(unlocked['persistentProfileData']['unlockedItemNames'][component],False)
        self.assertEqual(unlocked['upgradesGiverData']['level_us_01_01']['US_01_01_UPGRADE_CK_SUSPENSION'],2)
        self.assertEqual(unlocked['persistentProfileData']['discoveredUpgrades']['level_us_01_01']['current'],1)
        self.assertEqual(apply_manual(unlocked,{component:True})[1],[])
        locked,changes=apply_manual(unlocked,{component:False})
        self.assertNotIn(component,locked['persistentProfileData']['unlockedItemNames'])
        self.assertEqual(locked['upgradesGiverData']['level_us_01_01']['US_01_01_UPGRADE_CK_SUSPENSION'],0)
        self.assertEqual(locked['persistentProfileData']['discoveredUpgrades']['level_us_01_01']['current'],0)
        self.assertEqual(locked['trucks'],original['trucks'])
        self.assertEqual(locked['missions'],original['missions'])
        self.assertEqual(locked['persistentProfileData']['money'],100)
    def test_manual_overrides_host_and_aliases(self):
        component=UNLOCK_IDS['US_02_02_UPG_01']
        key='US_02_02_UPG_01'
        guest=copy.deepcopy(self.guest)
        guest['upgradesGiverData']['level_us_02_02']={key:0}
        out,changes=apply_manual(guest,{component:True})
        self.assertEqual(out['upgradesGiverData']['level_us_02_02'][key],2)
        self.assertNotIn('level_us_02_02_new',out['upgradesGiverData'])
        host=copy.deepcopy(out)
        merged,_=merge(host,guest)
        locked,_=apply_manual(merged,{component:False})
        self.assertNotIn(component,locked['persistentProfileData']['unlockedItemNames'])
        self.assertEqual(locked['upgradesGiverData']['level_us_02_02'][key],0)
    def test_manual_shared_component_and_reject_unknown(self):
        component=UNLOCK_IDS['US_01_04_UPG_1']
        out,_=apply_manual(self.guest,{component:True})
        from upgrade_editor import COMPONENT_POINTS
        for level,key in COMPONENT_POINTS[component]:
            self.assertEqual(out['upgradesGiverData'][level][key],2)
        with self.assertRaises(ValueError): apply_manual(self.guest,{'unknown_item':True})
        self.assertEqual(len(UNLOCK_IDS),165)
    def test_ui_manual_checkbox_and_save(self):
        key='US_01_01_UPGRADE_CK_SUSPENSION'; component=UNLOCK_IDS[key]
        with tempfile.TemporaryDirectory() as d:
            gp=Path(d)/'guest.cfg'
            gp.write_text(json.dumps({'CompleteSave':{'SslValue':self.guest}}),encoding='utf-8')
            root=tk.Tk(); root.withdraw()
            try:
                app=App(root); app.guest.set(str(gp)); app.read_saves()
                self.assertFalse(app.sync.get())
                iid=next(i for i in app.row_keys if app.row_keys[i]==component)
                app.table.selection_set(iid); app.table.focus(iid)
                app.space_checkbox()
                self.assertIs(app.manual[component],True)
                app.search.set('Chevrolet CK1500')
                self.assertIs(app.manual[component],True)
                app.preview(); self.assertIsNotNone(app.pending)
                with patch('savesync.messagebox.showinfo'): app.save()
                self.assertIn(component,load(gp)[1]['persistentProfileData']['unlockedItemNames'])
                self.assertEqual(app.manual,{})
                iid=next(i for i in app.row_keys if app.row_keys[i]==component)
                app.table.selection_set(iid); app.space_checkbox(); app.preview()
                with patch('savesync.messagebox.showinfo'): app.save()
                self.assertNotIn(component,load(gp)[1]['persistentProfileData']['unlockedItemNames'])
            finally: root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=__import__('unittest.mock',fromlist=['patch']).patch('savesync.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__ == '__main__': unittest.main()


# Keep legacy UI assertions independent of the machine's saved language.