import json,os,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from host_packer import build_plan,create_package,package_report,suggested_filename,PackError,PackCancelled
from host_packer_app import PackerApp
from host_archive import inspect_archive,prepare_bundle
from savesync import load_bytes
from save_discovery import Candidate


def make_save(path,money=100):
    path.parent.mkdir(parents=True,exist_ok=True)
    doc={'CompleteSave':{'SslValue':{'persistentProfileData':{'money':money,'experience':1234,'rank':2,'ownedTrucks':{}},'upgradesGiverData':{}}}}
    raw=b'\xef\xbb\xbf'+json.dumps(doc).encode()+b'\x00'
    path.write_bytes(raw);return path


class HostPackerTests(unittest.TestCase):
    def test_slot_selection_descriptions_and_manager_compatibility(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'userdata'/'123'/'1465360'/'remote'/'CompleteSave1.cfg')
            one=source.parent/'1_sts_level_us_01_01.cfg';one.write_bytes(b'first map binary')
            two=source.parent/'1_sts_level_us_01_04_new.dat';two.write_bytes(b'second map binary')
            (source.parent/'sts_level_us_01_02.cfg').write_bytes(b'other slot')
            (source.parent/'2_sts_level_us_01_02.cfg').write_bytes(b'other slot')
            (source.parent/'1_fog_level_us_01_01.cfg').write_bytes(b'fog')
            (source.parent/'CommonSslSave.cfg').write_bytes(b'common')
            originals={p.resolve():p.read_bytes() for p in source.parent.iterdir()}
            plan=build_plan(source)
            self.assertEqual(plan.slot,2);self.assertEqual(plan.account,'123')
            self.assertEqual({f.name for f in plan.files},{source.name,one.name,two.name})
            self.assertIn('Czarna Rzeka',plan.files[1].description)
            self.assertIn('Michigan',plan.files[1].description)
            self.assertIn('Wyspa Drummond',plan.files[2].description)
            destination=folder/'host.zip';create_package(plan,destination)
            with zipfile.ZipFile(destination) as archive:
                self.assertTrue(all('/' not in name and '\\' not in name for name in archive.namelist()))
                for file in plan.files:self.assertEqual(archive.read(file.name),originals[file.path])
            inspection=inspect_archive(destination,load_bytes)
            self.assertEqual(inspection.saves[0].slot,2)
            bundle=prepare_bundle(inspection,inspection.saves[0])
            try:self.assertEqual(bundle.save_path.read_bytes(),originals[source.resolve()])
            finally:bundle.close()
            self.assertEqual(originals,{p:p.read_bytes() for p in originals})
            report=package_report(plan,destination)
            self.assertIn('Spakowane pliki',report)
            for file in plan.files:self.assertIn(file.name,report)
    def test_changed_source_does_not_publish_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave.cfg');plan=build_plan(source)
            make_save(source,999)
            with self.assertRaises(PackError):create_package(plan,folder/'host.zip')
            self.assertFalse((folder/'host.zip').exists())
            self.assertFalse(list(folder.glob('.snowrunner-pack-*.tmp')))
    def test_new_map_file_requires_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave.cfg');plan=build_plan(source)
            (folder/'sts_level_us_01_01.cfg').write_bytes(b'new map')
            with self.assertRaises(PackError):create_package(plan,folder/'host.zip')
            self.assertFalse((folder/'host.zip').exists())
    def test_cancel_preserves_existing_zip_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave.cfg')
            (folder/'sts_level_us_01_01.cfg').write_bytes(b'map')
            plan=build_plan(source);destination=folder/'host.zip';destination.write_bytes(b'original')
            event=threading.Event()
            with self.assertRaises(PackCancelled):create_package(plan,destination,True,event,lambda *args:event.set())
            self.assertEqual(destination.read_bytes(),b'original')
            self.assertFalse(list(folder.glob('.snowrunner-pack-*.tmp')))
    def test_no_overwrite_and_unique_suggestion(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave.cfg');plan=build_plan(source)
            first=folder/suggested_filename(plan,folder);create_package(plan,first)
            self.assertNotEqual(suggested_filename(plan,folder),first.name)
            with self.assertRaises(FileExistsError):create_package(plan,first)
            make_save(source,200);new=build_plan(source);create_package(new,first,overwrite=True)
            self.assertEqual(inspect_archive(first,load_bytes).saves[0].money,200)
    def test_unknown_map_and_invalid_main(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave3.dat')
            (folder/'3_sts_level_mod_custom.dat').write_bytes(b'map')
            plan=build_plan(source)
            self.assertIn('level_mod_custom',plan.files[1].description)
            self.assertIn('poza katalogiem',plan.files[1].description)
            invalid=folder/'not_a_save.cfg';invalid.write_bytes(source.read_bytes())
            with self.assertRaises(PackError):build_plan(invalid)
    def test_ui_discovery_selection_export_and_report(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=make_save(folder/'CompleteSave.cfg')
            (folder/'sts_level_us_01_01.cfg').write_bytes(b'map state')
            candidate=Candidate(source,'Steam','123',1,time.time(),100,1234)
            root=tk.Tk();root.withdraw()
            def finish(app):
                deadline=time.monotonic()+3
                root.update()
                while app.job is not None and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertIsNone(app.job)
            try:
                app=PackerApp(root)
                with patch('host_packer_app.discover_saves',return_value=[candidate]):app.search();finish(app)
                # Selection events can start the manifest worker in the next event cycle.
                finish(app)
                self.assertIsNotNone(app.plan)
                self.assertEqual(len(app.files.get_children()),2)
                destination=folder/'host.zip'
                with patch('host_packer_app.filedialog.asksaveasfilename',return_value=str(destination)),patch('host_packer_app.messagebox.showerror') as error:
                    app.pack();finish(app);error.assert_not_called()
                self.assertEqual(app.last_export,destination.resolve())
                self.assertTrue(all(app.files.set(node,'state')=='Spakowano' for node in app.files.get_children()))
                self.assertIn('gotowy do wysłania',app.status.get())
                self.assertIn('Czarna Rzeka',package_report(app.plan,app.last_export))
            finally:root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=patch('host_packer_app.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__=='__main__':unittest.main()
