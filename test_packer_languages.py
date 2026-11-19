import ast,json,tempfile,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from host_packer import build_plan
from host_packer_app import PackerApp
from i18n import LANGUAGES,Translator,read_language

class PackerLanguageTests(unittest.TestCase):
    def test_all_packer_messages_have_translations(self):
        for source in ('host_packer.py','host_packer_app.py'):
            tree=ast.parse(Path(source).read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    translated=Translator('en').text(node.value)
                    self.assertFalse(any(c in translated for c in 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ'),repr(node.value))
    def test_switch_during_pack_preserves_files_progress_and_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder).resolve();settings=folder/'settings.json';source=folder/'CompleteSave.cfg'
            data=json.dumps({'CompleteSave':{'SslValue':{'persistentProfileData':{'money':1234,'experience':6900,'rank':7}}}}).encode()+b'\x00'
            source.write_bytes(data);sts=folder/'sts_level_us_01_01.cfg';sts.write_bytes(b'STS bytes unchanged')
            plan=build_plan(source);destination=folder/'host.zip'
            root=tk.Tk();root.withdraw()
            try:
                app=PackerApp(root,settings_path=settings);self.assertEqual(app.ui.translator.language,'en')
                self.assertEqual(root.title(),'SnowRunner — Host Packer');app.show_plan(plan)
                node=app.files.get_children()[1];app.files.selection_set(node);app.describe_file()
                self.assertIn('Black River',root.getvar(app.details._name))
                with patch('host_packer_app.filedialog.asksaveasfilename',return_value=str(destination)):
                    app.pack()
                job=app.job;self.assertIsNotNone(job)
                for code,name in LANGUAGES.items():
                    app.language.set(name);app.change_language()
                    self.assertIs(app.job,job);self.assertIs(app.plan,plan)
                    self.assertEqual(app.files.selection(),(node,));self.assertEqual(source.read_bytes(),data)
                    self.assertEqual(read_language(settings),code)
                app.language.set('Deutsch');app.change_language()
                deadline=time.monotonic()+5
                while app.job is not None and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertIsNone(app.job);self.assertEqual(app.last_export,destination.resolve())
                self.assertEqual(app.files.item(node,'values')[3],'Gepackt')
                app.language.set('Español');app.change_language()
                self.assertEqual(app.files.item(node,'values')[3],'Empaquetado')
                with patch.object(root,'clipboard_clear'),patch.object(root,'clipboard_append') as copy:
                    app.copy_report();report=copy.call_args.args[0]
                    self.assertIn('Archivos empaquetados',report);self.assertNotIn('Czarna Rzeka',report)
                    self.assertIn('CompleteSave.cfg',report);self.assertIn(str(destination),report)
                with zipfile.ZipFile(destination) as archive:
                    self.assertEqual(set(archive.namelist()),{source.name,sts.name})
                    self.assertEqual(archive.read(source.name),data)
                    self.assertEqual(archive.read(sts.name),sts.read_bytes())
            finally:app.close()
            root=tk.Tk();root.withdraw()
            try:self.assertEqual(PackerApp(root,settings_path=settings).ui.translator.language,'es')
            finally:root.destroy()
    def test_dialog_labels_and_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root=tk.Tk();root.withdraw()
            try:
                app=PackerApp(root,settings_path=Path(folder)/'settings.json');app.language.set('Français');app.change_language()
                with patch('host_packer_app.filedialog.askopenfilename',return_value='') as choose:
                    app.browse();self.assertEqual(choose.call_args.kwargs['title'],'Choisir le fichier principal CompleteSave')
                # Worker errors are translated on the main UI thread.
                app.start_job('plan',lambda cancel,events:(_ for _ in ()).throw(ValueError('Nieprawidłowe saldo w zapisie.')))
                deadline=time.monotonic()+5
                with patch('host_packer_app.messagebox.showerror') as error:
                    while app.job is not None and time.monotonic()<deadline:root.update();time.sleep(.01)
                    self.assertEqual(error.call_args.args[1],'Solde incorrect dans la sauvegarde.')
            finally:app.close()

if __name__=='__main__':unittest.main()
