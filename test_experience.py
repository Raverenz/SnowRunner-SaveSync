import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from experience import *
from savesync import App,load

class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.guest={'persistentProfileData':{'experience':1700,'rank':3,'money':100,'unlockedItemNames':{'own':False}},'upgradesGiverData':{'map':{'part':1}},'trucks':[{'parts':['engine']}]}
        self.host=copy.deepcopy(self.guest);self.host['persistentProfileData'].update(experience=7000,rank=7)
    def test_all_threshold_boundaries(self):
        for rank,xp in enumerate(THRESHOLDS,1):
            self.assertEqual(rank_for_xp(xp),rank)
            if xp:self.assertEqual(rank_for_xp(xp-1),rank-1)
        self.assertEqual(rank_for_xp(MAX_XP),30)
    def test_sync_and_no_downgrade(self):
        out,changes=apply_experience(self.host,self.guest,MODES[1])
        self.assertEqual((out['persistentProfileData']['experience'],out['persistentProfileData']['rank']),(7000,7))
        self.assertTrue(changes)
        self.assertEqual(apply_experience(self.guest,self.host,MODES[1])[0],self.host)
        self.assertEqual(self.guest['persistentProfileData']['experience'],1700)
        self.assertEqual(out['trucks'],self.guest['trucks'])
        self.assertEqual(out['upgradesGiverData'],self.guest['upgradesGiverData'])
        self.assertEqual(out['persistentProfileData']['unlockedItemNames'],self.guest['persistentProfileData']['unlockedItemNames'])
    def test_manual_and_rank_repair(self):
        self.assertEqual(project_experience(None,self.guest['persistentProfileData'],'Ustaw poziom',7),(6900,7))
        self.assertEqual(project_experience(None,self.guest['persistentProfileData'],'Dodaj XP',5200),(6900,7))
        self.assertEqual(project_experience(None,self.host['persistentProfileData'],'Ustaw XP',0),(0,1))
        self.guest['persistentProfileData']['rank']=30
        self.assertEqual(project_experience(None,self.guest['persistentProfileData'],'Ustaw XP',1700),(1700,3))
        self.assertEqual(apply_experience(None,self.guest)[0],self.guest)
    def test_validation(self):
        for value in (-1,MAX_XP+1,True,1.2):
            with self.assertRaises(ValueError):rank_for_xp(value)
        for mode,value in [('Ustaw poziom',0),('Ustaw poziom',31),('Dodaj XP',-1),('Ustaw XP',MAX_XP+1),('unknown',0)]:
            with self.assertRaises(ValueError):project_experience(None,self.guest['persistentProfileData'],mode,value)
        with self.assertRaises(ValueError):project_experience(None,self.guest['persistentProfileData'],MODES[1])
    def test_gui_preview_save_backup_and_reset(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'CompleteSave.cfg';host=Path(d)/'CompleteSave1.cfg'
            raw=json.dumps({'CompleteSave':{'SslValue':self.guest}}).encode()+b'\x00';path.write_bytes(raw)
            host.write_text(json.dumps({'CompleteSave1':{'SslValue':self.host}}))
            root=tk.Tk();root.withdraw()
            try:
                app=App(root);app.host.set(str(host));app.guest.set(str(path));app.read_saves()
                self.assertEqual(app.xp_mode.get(),MODES[1]);app.sync.set(False)
                with patch('savesync.messagebox.showerror') as errors,patch('savesync.messagebox.showinfo'):
                    app.preview();self.assertIsNotNone(app.pending);app.save();errors.assert_not_called()
                    self.assertEqual(load(path)[1]['persistentProfileData']['rank'],7)
                    self.assertEqual(next(Path(d).glob('*.bak')).read_bytes(),raw)
                    app.xp_mode.set('Ustaw poziom');app.xp_amount.set('10');app.preview()
                    self.assertEqual(app.pending[1]['CompleteSave']['SslValue']['persistentProfileData']['experience'],11800)
                    app.xp_amount.set('31');self.assertIsNone(app.pending);app.preview();errors.assert_called_once()
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