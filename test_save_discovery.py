import json,os,queue,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from save_discovery import Candidate,SearchRoot,discover_saves,windows_search_roots,modified_ago
from savesync import App


def create(path,balance=100):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'CompleteSave':{'SslValue':{'persistentProfileData':{'money':balance,'experience':1234}}}}),encoding='utf-8')
    return path


class DiscoveryTests(unittest.TestCase):
    def test_roots_accounts_slots_order_validation_dedupe(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);steam=root/'userdata';storage=root/'storage'
            one=create(steam/'123'/'1465360'/'remote'/'CompleteSave.cfg')
            two=create(steam/'456'/'1465360'/'remote'/'CompleteSave2.cfg',500)
            epic=create(storage/'epic-profile'/'CompleteSave1.dat',700)
            create(steam/'123'/'999'/'remote'/'CompleteSave.cfg')
            create(steam/'nonnumeric'/'1465360'/'remote'/'CompleteSave.cfg')
            create(storage/'epic-profile'/'CompleteSave1.cfg.bak')
            create(storage/'epic-profile'/'CompleteSave9.cfg')
            broken=storage/'epic-profile'/'CompleteSave3.dat';broken.write_text('invalid JSON')
            os.utime(one,(1000,1000));os.utime(two,(2000,2000));os.utime(epic,(3000,3000))
            roots=[SearchRoot(steam,'Steam','steam'),SearchRoot(steam,'Steam duplicate','steam'),SearchRoot(storage,'Epic','storage'),SearchRoot(root/'missing','Steam','steam')]
            result=discover_saves(roots)
            self.assertEqual([c.path for c in result],[epic.resolve(),two.resolve(),one.resolve()])
            self.assertEqual([c.slot for c in result],[2,3,1])
            self.assertEqual([c.account for c in result],['epic-profile','456','123'])
            self.assertEqual([c.money for c in result],[700,500,100])
    def test_documents_onedrive_and_registry_custom_steam(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);home=root/'user';steam=root/'CustomSteam';docs=root/'RedirectedDocuments'
            def registry(hive,path,name,view=0):
                if name=='SteamPath':return str(steam)
                if name=='Personal':return str(docs)
                return None
            with patch('save_discovery._registry_value',side_effect=registry):
                roots=windows_search_roots({'OneDrive':str(root/'Cloud'),'ProgramFiles(x86)':str(root/'Programs')},home)
            paths={str(r.path) for r in roots}
            self.assertIn(str(steam/'userdata'),paths)
            self.assertIn(str(docs/'My Games'/'SnowRunner'/'base'/'storage'),paths)
            self.assertIn(str(root/'Cloud'/'Documents'/'My Games'/'SnowRunner'/'base'/'storage'),paths)
            self.assertEqual(len(roots),len(paths))
    def test_cancellation_and_relative_time(self):
        event=threading.Event();event.set()
        self.assertEqual(discover_saves([],cancel=event),[])
        self.assertEqual(modified_ago(100,130),'przed chwilą')
        self.assertEqual(modified_ago(0,120),'2 min temu')
    def test_ui_single_multiple_and_manual_choice_wins(self):
        root=tk.Tk();root.withdraw()
        try:
            app=App(root)
            one=Candidate(Path('first.cfg'),'Steam','123',1,100,500,1000)
            two=Candidate(Path('second.cfg'),'Steam','123',2,200,600,2000)
            def apply(candidates,old='',automatic=True):
                q=queue.Queue();q.put((candidates,None))
                app._save_search={'queue':q,'cancel':threading.Event(),'guest':old,'automatic':automatic}
                app.poll_save_search()
            apply([one])
            self.assertEqual(app.guest.get(),str(one.path))
            self.assertIsNone(app.loaded_guest)
            self.assertFalse(app.money_box.winfo_manager())
            app.guest.set('')
            with patch.object(app,'show_detected_saves') as show:
                apply([one,two]);show.assert_called_once_with([one,two])
                self.assertEqual(app.guest.get(),'')
            app.guest.set('manual.cfg');apply([one],old='')
            self.assertEqual(app.guest.get(),'manual.cfg')
            app.host.set('host.cfg');app.guest.set('');app.loaded_host=('loaded',)
            apply([one]);self.assertEqual(app.guest.get(),'')
            self.assertEqual(app.host.get(),'host.cfg')
            app.loaded_host=None
            app.show_detected_saves([one,two]);root.update_idletasks()
            self.assertTrue(app._save_search_window.winfo_exists())
            app._save_search_window.destroy()
        finally:root.destroy()
    def test_background_worker_is_nonblocking(self):
        root=tk.Tk();root.withdraw();started=threading.Event();release=threading.Event()
        try:
            app=App(root)
            def discover(**kwargs):started.set();release.wait(2);return []
            with patch('savesync.discover_saves',side_effect=discover):
                app.detect_player_save(automatic=True)
                self.assertTrue(started.wait(1))
                self.assertIsNotNone(app._save_search)
                release.set()
                deadline=time.monotonic()+2
                while app._save_search is not None and time.monotonic()<deadline:
                    root.update();time.sleep(.01)
                self.assertIsNone(app._save_search)
                self.assertIn('Nie znaleziono',app.status.get())
        finally:release.set();root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=__import__('unittest.mock',fromlist=['patch']).patch('savesync.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__=='__main__':unittest.main()


# Keep legacy UI assertions independent of the machine's saved language.