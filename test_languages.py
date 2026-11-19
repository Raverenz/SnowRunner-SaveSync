import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from i18n import LANGUAGES,Translator,read_language,write_language
from translations import ENGLISH,TRANSLATIONS
from savesync import App,load

class LanguageTests(unittest.TestCase):
    def test_default_and_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config'/'settings.json'
            self.assertEqual(read_language(path),'en')
            for language in LANGUAGES:
                write_language(path,language);self.assertEqual(read_language(path),language)
            path.write_text('{broken');self.assertEqual(read_language(path),'en')
            path.write_text('{"language":"unsupported"}');self.assertEqual(read_language(path),'en')
            path.write_text('[]');self.assertEqual(read_language(path),'en')
            path.write_text('{"other":123}');write_language(path,'pl')
            self.assertEqual(json.loads(path.read_text())['other'],123)
    def test_complete_catalogs(self):
        for language in ('de','fr','es','pt'):
            self.assertEqual(set(ENGLISH.values())-set(TRANSLATIONS[language]),set(),language)
            self.assertTrue(all(TRANSLATIONS[language].values()))
    def test_templates_and_identifiers(self):
        source='Gracz: 6900 XP | poziom 7'
        self.assertEqual(Translator('en').text(source),'Player: 6900 XP | level 7')
        self.assertEqual(Translator('de').text(source),'Spieler: 6900 XP | Level 7')
        path=r'C:\Gracz\Pojazdy\Mój save.cfg'
        self.assertEqual(Translator('es').text(path+' | Pojazdy: 4'),path+' | Vehículos: 4')
        self.assertEqual(Translator('fr').text('engine_chevrolet_01'),'engine_chevrolet_01')
        for language in LANGUAGES:
            self.assertNotIn('Nieobsługiwany',Translator(language).text('Nieobsługiwany format. Wybierz CompleteSave*.cfg lub .dat w formacie JSON.')) if language!='pl' else None
    def test_maps_and_upgrades(self):
        for language in LANGUAGES:
            translated=Translator(language).text('Michigan — Czarna Rzeka — Podwyższone zawieszenie — Chevrolet CK1500')
            self.assertIn('Chevrolet CK1500',translated)
            if language!='pl':self.assertNotIn('Czarna Rzeka',translated);self.assertNotIn('Podwyższone',translated)
    def test_live_switch_preserves_pending_data_and_saves_canonical_values(self):
        guest={'persistentProfileData':{'money':100,'experience':1700,'rank':3,'unlockedItemNames':{}},'upgradesGiverData':{},'missions':{'untouched':1}}
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);settings=folder/'settings.json';save=folder/'CompleteSave.cfg'
            raw=json.dumps({'CompleteSave':{'SslValue':guest}}).encode()+b'\x00';save.write_bytes(raw)
            root=tk.Tk();root.withdraw()
            try:
                app=App(root,settings_path=settings)
                self.assertEqual(app.ui.translator.language,'en')
                app.guest.set(str(save));app.read_saves();app.mode.set('Dodaj kwotę');app.amount.set('50')
                app.xp_mode.set('Ustaw poziom');app.xp_amount.set('7');app.preview();self.assertIsNotNone(app.pending)
                pending=copy.deepcopy(app.pending);loaded=copy.deepcopy(app.loaded_guest)
                app.manual['test_component']=False
                row=app.table.get_children()[0];app.table.selection_set(row)
                app.notebook.select(app.vehicle_tab)
                for code,native in LANGUAGES.items():
                    app.language.set(native);app.change_language()
                    self.assertEqual(app.notebook.tab(app.vehicle_tab,'text'),app.ui.text('Pojazdy'))
                    self.assertEqual(app.pending,pending);self.assertEqual(app.loaded_guest,loaded)
                    self.assertEqual(app.manual,{'test_component':False})
                    self.assertEqual(app.table.selection(),(row,))
                    self.assertEqual(str(app.notebook.select()),str(app.vehicle_tab))
                    self.assertEqual(app.mode.get(),'Dodaj kwotę');self.assertEqual(app.xp_mode.get(),'Ustaw poziom')
                    self.assertEqual(save.read_bytes(),raw);self.assertEqual(read_language(settings),code)
                    self.assertIn('6900',app.report.get('1.0','end'))
                app.manual.clear();app.language.set('Deutsch');app.change_language()
                # Exercise the visible combobox, not just the canonical variable.
                xp_combo=next(w for w in app.xp_box.winfo_children() if w.winfo_class()=='TCombobox')
                self.assertEqual(xp_combo.get(),'Level festlegen')
                xp_combo.current(3);xp_combo.event_generate('<<ComboboxSelected>>');root.update()
                self.assertEqual(app.xp_mode.get(),'Ustaw XP');app.xp_amount.set('6900');app.preview()
                with patch('savesync.messagebox.showinfo'),patch('savesync.messagebox.showerror') as error:
                    app.save();error.assert_not_called()
                out=load(save)[1]
                self.assertEqual(out['persistentProfileData']['money'],150)
                self.assertEqual((out['persistentProfileData']['experience'],out['persistentProfileData']['rank']),(6900,7))
                self.assertEqual(out['missions'],guest['missions'])
                self.assertEqual(next(folder.glob('*.bak')).read_bytes(),raw)
                app.xp_mode.set('Ustaw poziom');app.xp_amount.set('99')
                with patch('savesync.messagebox.showerror') as error:
                    app.preview();self.assertIn('Level muss',error.call_args.args[1])
            finally:root.destroy()
            root=tk.Tk();root.withdraw()
            try:self.assertEqual(App(root,settings_path=settings).ui.translator.language,'de')
            finally:root.destroy()

if __name__=='__main__':unittest.main()

