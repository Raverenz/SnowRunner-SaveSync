import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from company import assess
from savesync import App,load

class CompanyTests(unittest.TestCase):
    def setUp(self):
        self.prices={
            'trucks':{'truck':{'name':'Truck','price':1000,'defaults':{'engine':'e','gearbox':'g','suspension':'s','winchUpgrade':'w'},'default_addons':['bumper'],'wheels':{'type':'wheels_test','tire':'tire'}},
                      'trailer':{'name':'Trailer','price':500,'is_trailer':True}},
            'parts':{key:{'price':price,'name':key} for key,price in [('e',100),('g',50),('s',70),('w',20),('bumper',10),('upgraded',300)]},
            'tires':{'wheels_test|tire':{'price':80,'name':'Tires'}}}
        self.truck={'type':'truck','globalId':'one','engine':{'name':'e'},'gearbox':{'name':'g'},'suspension':'s','winchUpgrade':{'name':'w'},'wheelsType':'wheels_test','tires':'tire','addons':[{'name':'bumper'}]}
        self.save={'persistentProfileData':{'money':200,'experience':12345,'rank':9,'ownedTrucks':{'truck':1},'trucksInWarehouse':[self.truck],'addons':{'upgraded':2,'e':0,'trailer':1},'unlockedItemNames':{'not_owned':False}},'garagesData':{}}
    def test_exact_total_does_not_count_unlocks(self):
        original=copy.deepcopy(self.save)
        result=assess(self.save,self.prices)
        self.assertEqual(result['total'],200+1000+100+50+70+20+80+10+600+500)
        self.assertTrue(result['complete'])
        self.assertEqual((result['experience'],result['rank']),(12345,9))
        self.assertEqual(self.save,original)
    def test_duplicate_descriptor_not_counted_twice(self):
        self.save['garagesData']={'map':{'slotsDatas':{'slot':{'truckDesc':copy.deepcopy(self.truck)}}}}
        self.assertEqual(assess(self.save,self.prices)['total'],assess({**self.save,'garagesData':{}},self.prices)['total'])
    def test_multiple_owned_trucks_same_model(self):
        self.save['persistentProfileData']['ownedTrucks']['truck']=2
        clone=copy.deepcopy(self.truck);clone['globalId']='two'
        self.save['persistentProfileData']['trucksInWarehouse'].append(clone)
        result=assess(self.save,self.prices)
        self.assertEqual(result['chassis'],2000)
        self.assertEqual(result['installed'],660)
        self.assertTrue(result['complete'])
    def test_outside_map_and_unknown_price_are_explicit(self):
        self.save['persistentProfileData']['ownedTrucks']['truck']=2
        self.save['persistentProfileData']['addons']['mod_part']=1
        result=assess(self.save,self.prices)
        self.assertFalse(result['complete'])
        self.assertEqual(result['chassis'],2000)
        self.assertEqual(result['installed'],330)
        self.assertTrue(any('wyposażenie na mapie pominięte' in note for note in result['warnings']))
        self.assertTrue(any('mod_part' in note for note in result['warnings']))
    def test_stock_defaults_and_composite_tire_inventory(self):
        self.save['persistentProfileData']['trucksInWarehouse']=[{'type':'truck','needToInstallDefaultAddons':True,'addons':[]}]
        self.save['persistentProfileData']['addons']['wheels_test_tire_0.45']=2
        result=assess(self.save,self.prices)
        self.assertEqual(result['installed'],330)
        self.assertEqual(result['spares'],1260)
        self.assertTrue(result['complete'])
    def test_host_only_and_details_and_refresh_after_write(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'CompleteSave.cfg'
            path.write_text(json.dumps({'CompleteSave':{'SslValue':self.save}}),encoding='utf-8')
            root=tk.Tk();root.withdraw()
            try:
                app=App(root);app.host.set(str(path));app.read_saves()
                self.assertIsNotNone(app.loaded_host);self.assertIsNone(app.loaded_guest)
                self.assertEqual(app.valuations['host']['experience'],12345)
                self.assertIn('12 345 XP',app.asset_labels['host'].get())
                self.assertFalse(app.money_box.winfo_manager())
                app.show_assets('host');root.update_idletasks()
                app.host.set('');app.guest.set(str(path));app.read_saves()
                before=app.valuations['guest']['total']
                app.mode.set('Dodaj kwotę');app.amount.set('50');app.preview()
                with patch('savesync.messagebox.showinfo'): app.save()
                self.assertEqual(app.valuations['guest']['total'],before+50)
                self.assertEqual(load(path)[1]['persistentProfileData']['experience'],12345)
                app.guest.set('other');self.assertFalse(app.assets_box.winfo_manager())
            finally: root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=__import__('unittest.mock',fromlist=['patch']).patch('savesync.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__=='__main__':unittest.main()


# Keep legacy UI assertions independent of the machine's saved language.