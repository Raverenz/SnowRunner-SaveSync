import json,os,stat,struct,tempfile,unittest,zipfile,zlib
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from host_archive import application_folder,newest_zip,inspect_archive,prepare_bundle,ArchiveError
from savesync import App,load_bytes,load
from save_discovery import Candidate
from test_sts_valuation import record,G1


def save_data(balance=500,unlock='host_part'):
    return {'CompleteSave':{'SslValue':{'persistentProfileData':{'money':balance,'experience':1234,'rank':2,'ownedTrucks':{},'trucksInWarehouse':[],'addons':{},'unlockedItemNames':{unlock:False}},'garagesData':{},'upgradesGiverData':{}}}}


def pack(path,entries):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in entries.items():archive.writestr(name,json.dumps(data) if isinstance(data,dict) else data)
    return path


class HostArchiveTests(unittest.TestCase):
    def test_newest_is_filesystem_date_and_executable_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            old=pack(folder/'z-name.zip',{'CompleteSave.cfg':save_data()})
            new=pack(folder/'a-name.ZIP',{'CompleteSave.cfg':save_data()})
            os.utime(old,(100,100));os.utime(new,(200,200))
            (folder/'nested').mkdir();pack(folder/'nested'/'later.zip',{'CompleteSave.cfg':save_data()})
            self.assertEqual(newest_zip(folder),new)
            with patch('host_archive.sys.frozen',True,create=True),patch('host_archive.sys.executable',str(folder/'manager.exe')):
                self.assertEqual(application_folder(),folder.resolve())
    def test_metadata_slot_and_only_matching_sts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pack(Path(folder)/'host.zip',{'CompleteSave.cfg':save_data(100),'CompleteSave1.dat':save_data(900),'sts_level_us_01_01.cfg':b'first','1_sts_level_us_01_01.dat':b'second','fog_level_us_01_01.cfg':b'ignored','notes.txt':'ignored'})
            original=path.read_bytes();info=inspect_archive(path,load_bytes)
            self.assertEqual([(m.slot,m.money,m.experience,m.rank) for m in info.saves],[(1,100,1234,2),(2,900,1234,2)])
            bundle=prepare_bundle(info,info.saves[1]);cache=bundle.save_path.parent
            try:self.assertEqual({p.name for p in cache.iterdir()},{'CompleteSave1.dat','1_sts_level_us_01_01.dat'})
            finally:bundle.close()
            self.assertFalse(cache.exists());self.assertEqual(path.read_bytes(),original)
    def test_reject_nested_duplicate_symlink_and_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            for badname in ['../CompleteSave.cfg','folder/CompleteSave.cfg',r'folder\CompleteSave.cfg']:
                path=pack(folder/'bad.zip',{badname:save_data()})
                with self.assertRaises(ArchiveError):inspect_archive(path,load_bytes)
            path=pack(folder/'duplicate.zip',{'CompleteSave.cfg':save_data(),'COMPLETESAVE.CFG':save_data()})
            with self.assertRaises(ArchiveError):inspect_archive(path,load_bytes)
            path=folder/'link.zip'
            with zipfile.ZipFile(path,'w') as z:
                info=zipfile.ZipInfo('CompleteSave.cfg');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'target')
            with self.assertRaises(ArchiveError):inspect_archive(path,load_bytes)
            path=pack(folder/'limit.zip',{'CompleteSave.cfg':save_data()})
            with patch('host_archive.MAX_TOTAL',10):
                with self.assertRaises(ArchiveError):inspect_archive(path,load_bytes)
    def test_changed_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pack(Path(folder)/'host.zip',{'CompleteSave.cfg':save_data()})
            info=inspect_archive(path,load_bytes)
            pack(path,{'CompleteSave.cfg':save_data(999)})
            with self.assertRaises(ArchiveError):prepare_bundle(info,info.saves[0])
    def test_ui_yes_no_and_invalid_newest_not_old_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);path=pack(folder/'host.zip',{'CompleteSave.cfg':save_data()})
            root=tk.Tk();root.withdraw()
            try:
                app=App(root)
                with patch('savesync.application_folder',return_value=folder),patch('savesync.messagebox.askyesno',return_value=False) as ask,patch.object(app,'detect_player_save') as discover:
                    app.startup();ask.assert_called_once();discover.assert_called_once_with(automatic=True,allow_loaded_host=True)
                self.assertEqual(app.host.get(),'');self.assertIsNone(app._host_bundle)
                with patch('savesync.messagebox.askyesno',return_value=True) as ask:
                    self.assertTrue(app.open_host_zip(path))
                    self.assertIn('1 234 XP',ask.call_args.args[1]);self.assertIn('500 $',ask.call_args.args[1])
                self.assertIsNotNone(app.loaded_host)
                cache=app._host_bundle.save_path.parent
                app.host.set('');self.assertFalse(cache.exists())
                bad=folder/'latest.zip';bad.write_bytes(b'broken zip')
                os.utime(path,(100,100));os.utime(bad,(200,200))
                with patch('savesync.application_folder',return_value=folder),patch('savesync.messagebox.showerror') as error,patch.object(app,'detect_player_save'):
                    app.startup();error.assert_called_once()
                self.assertEqual(app.host.get(),'')
            finally:root.destroy()
    def test_ui_bundle_sts_sync_preview_and_read_only_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);host=save_data();profile=host['CompleteSave']['SslValue']['persistentProfileData'];profile['ownedTrucks']={'chevrolet_ck1500':1}
            payload=record(G1)[0];sts=struct.pack('<I',len(payload))+zlib.compress(payload)
            path=pack(folder/'host.zip',{'CompleteSave1.cfg':host,'1_sts_level_us_01_01.cfg':sts})
            original=path.read_bytes();guest=folder/'guest.cfg';guest.write_text(json.dumps(save_data(100,'guest_part')),encoding='utf-8')
            root=tk.Tk();root.withdraw()
            try:
                app=App(root)
                with patch('savesync.messagebox.askyesno',return_value=True):self.assertTrue(app.open_host_zip(path))
                self.assertEqual(app.valuations['host']['map_count'],1)
                app.use_detected_save(Candidate(guest,'Steam','test',1,0,100,1234));app.preview()
                self.assertIsNotNone(app.pending)
                with patch('savesync.messagebox.showinfo'):app.save()
                self.assertIn('host_part',load(guest)[1]['persistentProfileData']['unlockedItemNames'])
                self.assertEqual(path.read_bytes(),original)
                self.assertEqual(app.valuations['host']['map_count'],1)
                cache=app._host_bundle.save_path.parent
                pack(path,{'CompleteSave1.cfg':save_data(999)})
                with patch('savesync.messagebox.showerror') as error:app.preview();error.assert_called_once()
                self.assertIsNone(app.pending)
                app.read_saves();self.assertEqual(app.loaded_host[1]['persistentProfileData']['money'],999)
                self.assertFalse(cache.exists())
            finally:root.destroy()
    def test_multiple_slots_require_member_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pack(Path(folder)/'host.zip',{'CompleteSave.cfg':save_data(100),'CompleteSave2.cfg':save_data(800)})
            root=tk.Tk();root.withdraw()
            try:
                app=App(root)
                with patch.object(app,'choose_host_zip_member',side_effect=lambda info:info.saves[1]) as choose,patch('savesync.messagebox.askyesno',return_value=True):
                    app.open_host_zip(path);choose.assert_called_once()
                self.assertEqual(app.loaded_host[1]['persistentProfileData']['money'],800)
                self.assertEqual(app._host_bundle.member.slot,3)
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