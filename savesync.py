from i18n import UI, LANGUAGES, settings_file, read_language, write_language
from experience import MODES, valid_xp, project_experience, apply_experience
import copy, json, os, tempfile, random, queue, threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def pairs(items):
    out = {}
    for k, v in items:
        if k in out: raise ValueError('Powtórzony klucz JSON: ' + k)
        out[k] = v
    return out


def load(path):
    return load_bytes(Path(path).read_bytes())


def load_bytes(raw):
    text = raw.decode('utf-8-sig')
    clean = text.rstrip('\x00\r\n ')
    doc = json.loads(clean, object_pairs_hook=pairs)
    blocks = [v['SslValue'] for k,v in doc.items() if k.startswith('CompleteSave') and isinstance(v,dict) and isinstance(v.get('SslValue'),dict)]
    if len(blocks) != 1 or not isinstance(blocks[0].get('persistentProfileData'),dict):
        raise ValueError('Nieobsługiwany format. Wybierz CompleteSave*.cfg lub .dat w formacie JSON.')
    return doc, blocks[0], raw, raw.startswith(b'\xef\xbb\xbf'), text[len(clean):]


def merge(host, guest, sync=True, mode='Bez zmian', amount=0):
    out = copy.deepcopy(guest)
    profile = out['persistentProfileData']
    changes = []
    if sync:
        source = host['persistentProfileData'].get('unlockedItemNames')
        target = profile.get('unlockedItemNames')
        if not isinstance(source,dict) or not isinstance(target,dict):
            raise ValueError('Brak obsługiwanej listy unlockedItemNames.')
        for key,value in source.items():
            if key not in target:
                target[key] = copy.deepcopy(value)
                changes.append('Odblokowanie: ' + key)
        maps = host.get('upgradesGiverData')
        dest = out.get('upgradesGiverData')
        if not isinstance(maps,dict) or not isinstance(dest,dict):
            raise ValueError('Brak sekcji upgradesGiverData.')
        for level, upgrades in maps.items():
            if not isinstance(upgrades,dict): raise ValueError('Nieobsługiwany format ulepszeń.')
            for key,status in upgrades.items():
                if type(status) is not int or status not in (0,1,2): raise ValueError('Nieobsługiwany status ulepszenia.')
                if status != 2: continue
                target_level = dest.setdefault(level,{})
                if not isinstance(target_level,dict): raise ValueError('Nieobsługiwany format ulepszeń gracza.')
                old = target_level.get(key,0)
                if type(old) is not int or old not in (0,1,2): raise ValueError('Nieobsługiwany status gracza.')
                if old < 2:
                    target_level[key] = 2
                    changes.append('Zebrane ulepszenie: '+' — '.join(x for x in upgrade_info(level,key) if x))
    if mode != 'Bez zmian':
        old = profile.get('money')
        if type(old) is not int or type(amount) is not int or amount < 0: raise ValueError('Kwota musi być nieujemną liczbą całkowitą.')
        new = old + amount if mode == 'Dodaj kwotę' else amount
        if not 0 <= new <= 2147483647: raise ValueError('Saldo poza zakresem 0–2 147 483 647.')
        profile['money'] = new
        if old != new: changes.append(f'Pieniądze: {old} → {new}')
    return out, changes


def write_save(path, doc, raw, bom, suffix):
    path = Path(path)
    if path.read_bytes() != raw: raise ValueError('Plik zmienił się od podglądu. Wczytaj ponownie.')
    data = (('\ufeff' if bom else '') + json.dumps(doc,ensure_ascii=False,separators=(',',':'),allow_nan=False) + suffix).encode('utf-8')
    backup = path.with_name(path.name + '.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
    with backup.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
            tmp = Path(f.name)
            f.write(data); f.flush(); os.fsync(f.fileno())
        if path.read_bytes() != raw: raise ValueError('Plik zmienił się podczas zapisu.')
        os.replace(tmp,path)
    finally:
        if tmp and tmp.exists(): tmp.unlink()
    return backup


from catalog import LEVELS, UPGRADES
from unlock_ids import UNLOCK_IDS
from upgrade_editor import apply_manual, is_unlocked
from company import assess, summary, money
from cat_effects import roll_rarity, Fireworks
from vehicles import fleet
from save_discovery import discover_saves, modified_ago
from host_archive import application_folder, newest_zip, inspect_archive, prepare_bundle, ArchiveError, HostLoadCancelled


def normal_level(level):
    return level.lower().removesuffix('_new')


MAP_NAMES = {normal_level(k): v for k, v in LEVELS.items()}
UPGRADE_NAMES = {(normal_level(level), key.upper()): v for (level,key), v in UPGRADES.items()}


def upgrade_info(level, key):
    place = MAP_NAMES.get(normal_level(level), {'region':'Nieznany region', 'map':level})
    item = UPGRADE_NAMES.get((normal_level(level), key.upper()))
    if not item:
        return place['region'], place['map'], 'Nieznane ulepszenie: '+key, ''
    if item['type'] == 'Zawieszenie' and item['name'] == 'Podwyższone':
        name = 'Podwyższone zawieszenie'
    else:
        name = item['type']+' — '+item['name']
    return place['region'], place['map'], name, ', '.join(item['trucks'])


def upgrade_rows(host, guest):
    def states(save):
        result = {}
        for level, upgrades in (save or {}).get('upgradesGiverData',{}).items():
            if isinstance(upgrades,dict):
                for key,status in upgrades.items():
                    result[(normal_level(level),key.upper())] = status
        return result
    hs,gs = states(host),states(guest)
    labels = {0:'Nieodkryte',1:'Odkryte',2:'Zebrane'}
    rows = []
    for level,key in UPGRADE_NAMES.keys() | hs.keys() | gs.keys():
        region,map_name,name,trucks = upgrade_info(level,key)
        h,g = hs.get((level,key)),gs.get((level,key))
        rows.append((region,map_name,name,trucks,labels.get(h,'Brak danych'),labels.get(g,'Brak danych'),
                     'Do synchronizacji' if h == 2 and g != 2 else '', key))
    return sorted(rows,key=lambda row: (row[0],row[1],row[2],row[7]))


class App:
    def __init__(self,root,settings_path=None):
        self.root = root
        self.settings_path=Path(settings_path) if settings_path is not None else settings_file()
        self.ui=UI(root,read_language(self.settings_path))
        root.title('SnowRunner SaveSync')
        root.geometry('1220x860'); root.minsize(960,700)
        self.pending = None; self.loaded_host = self.loaded_guest = None
        self.manual = {}; self.row_keys = {}; self.valuations = {}
        self.fleets = {}
        self._host_bundle=None
        self._save_search=None;self._save_search_job=None;self._save_search_window=None
        self.root.bind("<Destroy>",self.cancel_save_search,add="+")
        self.vehicle_confirmed={"host":set(),"guest":set()};self.vehicle_candidates={}
        box = ttk.Frame(root,padding=16); box.pack(fill='both',expand=True)
        header=ttk.Frame(box);header.pack(fill='x')
        language_bar=ttk.Frame(header);language_bar.pack(side='right',padx=(10,0))
        self.ui.Label(language_bar,text='Język').pack(side='left')
        self.language=tk.StringVar(value=LANGUAGES[self.ui.translator.language])
        self.language_selector=ttk.Combobox(language_bar,textvariable=self.language,values=list(LANGUAGES.values()),state='readonly',width=18)
        self.language_selector.pack(side='left',padx=8)
        self.language_selector.bind('<<ComboboxSelected>>',self.change_language)
        self.ui.Label(header,text='SnowRunner • synchronizacja co-op',font=('Segoe UI',20,'bold')).pack(side='left')
        self.ui.Button(header,text='Pokaż kotka 🐱',command=self.show_cat).pack(side='right')
        self.ui.Label(box,text='Wybierz zapis hosta i swój zapis. Przed zapisem zamknij grę. Kopia .bak powstanie automatycznie.').pack(anchor='w',pady=6)
        self.host,self.guest = tk.StringVar(),tk.StringVar()
        self.file_row(box,'Zapis hosta',self.host)
        self.file_row(box,'Twój zapis',self.guest,detect=True)
        self.ui.Label(box,text=r'Domyślne miejsce plików zapisu to: C:\Program Files (x86)\Steam\userdata\[id-konta]\1465360\remote',wraplength=900).pack(anchor='w',pady=(6,2))
        self.ui.Button(box,text='Wczytaj zapisy',command=self.read_saves).pack(anchor='w',pady=5)
        self.status = self.ui.StringVar(value='Wczytaj swój zapis, aby zobaczyć saldo i stan ulepszeń.')
        self.ui.Label(box,textvariable=self.status,wraplength=1100).pack(anchor='w')
        self.notebook=self.ui.Notebook(box);self.notebook.pack(fill='both',expand=True,pady=(8,0))
        self.sync_tab=ttk.Frame(self.notebook,padding=6)
        self.vehicle_tab=ttk.Frame(self.notebook,padding=10)
        self.notebook.add(self.sync_tab,text='Synchronizacja i ulepszenia')
        self.notebook.add(self.vehicle_tab,text='Pojazdy')
        self.asset_tab=ttk.Frame(self.notebook,padding=10)
        self.notebook.add(self.asset_tab,text='Majątek i XP')
        self.ui.Label(self.asset_tab,text='Wczytaj zapis hosta lub gracza, aby porównać majątek i doświadczenie.').pack(anchor='w',pady=8)
        body=self.sync_tab
        self.assets_box=self.ui.LabelFrame(self.asset_tab,text='Majątek i doświadczenie — wczytane zapisy',padding=8)
        self.asset_labels={};self.asset_details={}
        for column,(key,title) in enumerate([('host','Host'),('guest','Gracz')]):
            card=ttk.Frame(self.assets_box);card.grid(row=0,column=column,sticky='nsew',padx=8)
            self.assets_box.columnconfigure(column,weight=1)
            self.ui.Label(card,text=title,font=('Segoe UI',11,'bold')).pack(anchor='w')
            var=self.ui.StringVar(value='Nie wczytano zapisu');self.asset_labels[key]=var
            self.ui.Label(card,textvariable=var,font=('Segoe UI',10),wraplength=520).pack(anchor='w')
            button=self.ui.Button(card,text='Szczegóły wyceny',command=lambda key=key:self.show_assets(key),state='disabled')
            button.pack(anchor='w',pady=2);self.asset_details[key]=button
        self.ui.Label(self.assets_box,text='Wartość firmy = gotówka + podwozia + zamontowane wyposażenie + części i dodatki w zapasie. Ceny katalogowe.',wraplength=1100).grid(row=1,column=0,columnspan=2,sticky='w')
        self.money_box = self.ui.LabelFrame(body,text='Pieniądze gracza',padding=10)
        self.balance = self.ui.StringVar(); self.mode = tk.StringVar(value='Bez zmian'); self.amount = tk.StringVar(value='0')
        self.ui.Label(self.money_box,textvariable=self.balance,font=('Segoe UI',11,'bold')).pack(side='left',padx=8)
        self.ui.Combobox(self.money_box,textvariable=self.mode,state='readonly',values=['Bez zmian','Dodaj kwotę','Ustaw saldo'],width=17).pack(side='left',padx=8)
        self.amount_entry = ttk.Entry(self.money_box,textvariable=self.amount,width=16,state='disabled'); self.amount_entry.pack(side='left')
        self.result_balance = self.ui.StringVar()
        self.ui.Label(self.money_box,textvariable=self.result_balance).pack(side='left',padx=12)
        self.xp_box = self.ui.LabelFrame(body,text='Doświadczenie i poziom gracza',padding=6)
        self.xp_mode=tk.StringVar(value='Bez zmian');self.xp_amount=tk.StringVar(value='0')
        self.xp_current=self.ui.StringVar();self.xp_result=self.ui.StringVar()
        self.ui.Label(self.xp_box,textvariable=self.xp_current).grid(row=0,column=0,columnspan=4,sticky='w')
        self.ui.Combobox(self.xp_box,textvariable=self.xp_mode,state='readonly',values=MODES,width=23).grid(row=1,column=0,padx=(0,8))
        self.xp_entry=ttk.Entry(self.xp_box,textvariable=self.xp_amount,width=14,state='disabled');self.xp_entry.grid(row=1,column=1)
        self.ui.Label(self.xp_box,textvariable=self.xp_result).grid(row=1,column=2,padx=10,sticky='w')
        self.ui.Label(self.xp_box,text='Synchronizacja wyrównuje XP w górę. Poziom 1–30 ustawia minimalne XP; odkrycia na mapie są synchronizowane osobno.').grid(row=2,column=0,columnspan=4,sticky='w')
        self.sync = tk.BooleanVar(value=True)
        self.options = ttk.Frame(body); self.options.pack(fill='x',pady=8)
        self.ui.Checkbutton(self.options,text='Synchronizuj ulepszenia i listę odblokowań hosta (może zawierać pojazdy)',variable=self.sync).pack(anchor='w')
        filters = ttk.Frame(body); filters.pack(fill='x',pady=5)
        self.ui.Label(filters,text='Szukaj mapy, części lub pojazdu:').pack(side='left')
        self.search = tk.StringVar(); ttk.Entry(filters,textvariable=self.search,width=32).pack(side='left',padx=8)
        self.only_missing = tk.BooleanVar()
        self.ui.Checkbutton(filters,text='Tylko brakujące u gracza',variable=self.only_missing,command=self.refresh_list).pack(side='left')
        footer=ttk.Frame(body);footer.pack(side='bottom',fill='x')
        table_box = ttk.Frame(body); table_box.pack(fill='both',expand=True)
        columns = ('region','map','part','trucks','host','guest','action','id')
        self.table = self.ui.Treeview(table_box,columns=columns,show='tree headings',height=12)
        self.table.heading('#0',text='Po zapisie')
        self.table.column('#0',width=85,minwidth=85,stretch=False)
        for col,title,width in zip(columns,['Region','Mapa','Ulepszenie','Pojazdy','Host','Gracz','Zmiana','Identyfikator'],[120,155,210,300,90,90,130,240]):
            self.table.heading(col,text=title); self.table.column(col,width=width,minwidth=70,stretch=False)
        vertical = ttk.Scrollbar(table_box,orient='vertical',command=self.table.yview)
        horizontal = ttk.Scrollbar(table_box,orient='horizontal',command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.table.grid(row=0,column=0,sticky='nsew'); vertical.grid(row=0,column=1,sticky='ns'); horizontal.grid(row=1,column=0,sticky='ew')
        table_box.rowconfigure(0,weight=1); table_box.columnconfigure(0,weight=1)
        self.table.tag_configure('missing',background='#fff0cf')
        self.detail = self.ui.StringVar(value='Zaznacz ulepszenie, aby zobaczyć pełny opis i listę pojazdów.')
        self.ui.Label(footer,textvariable=self.detail,wraplength=1100).pack(anchor='w',pady=5)
        self.table.bind('<<TreeviewSelect>>',self.select_row)
        self.table.bind('<Button-1>',self.click_checkbox)
        self.table.bind('<space>',self.space_checkbox)
        edit_row=ttk.Frame(footer); edit_row.pack(fill='x',pady=3)
        self.checked=tk.BooleanVar()
        self.edit_check=self.ui.Checkbutton(edit_row,text='Odblokowane po zapisie (zaznacz / odznacz wybrane ulepszenie)',variable=self.checked,command=self.edit_selected,state='disabled')
        self.edit_check.pack(side='left')
        self.ui.Button(edit_row,text='Cofnij ręczne zmiany',command=self.reset_manual).pack(side='right')
        self.ui.Label(footer,text='Checkbox zmienia odblokowanie w garażu i punkt na mapie. Ręczne zmiany mają pierwszeństwo przed hostem.').pack(anchor='w')
        row = ttk.Frame(footer); row.pack(fill='x',pady=5)
        self.preview_btn = self.ui.Button(row,text='1. Podgląd zmian',command=self.preview,state='disabled'); self.preview_btn.pack(side='left')
        self.save_btn = self.ui.Button(row,text='2. Zapisz z kopią zapasową',command=self.save,state='disabled'); self.save_btn.pack(side='left',padx=10)
        self.report = self.ui.Text(footer,height=4,wrap='word',state='disabled'); self.report.pack(fill='x',pady=5)
        for var in (self.host,self.guest): var.trace_add('write',self.path_changed)
        for var in (self.mode,self.amount,self.sync,self.xp_mode,self.xp_amount): var.trace_add('write',self.options_changed)
        self.search.trace_add('write',lambda *_: self.refresh_list())
        self.refresh_list()
        self.build_vehicle_tab()

    def change_language(self,event=None):
        code=next((key for key,value in LANGUAGES.items() if value==self.language.get()),'en')
        self.ui.change_language(code)
        try:write_language(self.settings_path,code)
        except OSError:
            self.ui.dialog(messagebox.showerror,'Ustawienia języka','Nie można zapisać ustawienia języka. W tej sesji wybrany język pozostaje aktywny.',parent=self.root)

    def build_vehicle_tab(self):
        tools=ttk.Frame(self.vehicle_tab);tools.pack(fill='x',pady=(0,8))
        self.ui.Label(tools,text='Zapis:').pack(side='left')
        self.vehicle_source=tk.StringVar(value='Gracz')
        selector=self.ui.Combobox(tools,textvariable=self.vehicle_source,state='readonly',values=['Gracz','Host'],width=12)
        selector.pack(side='left',padx=6);selector.bind('<<ComboboxSelected>>',lambda *_:self.refresh_vehicles())
        self.ui.Button(tools,text='Wczytaj pliki STS…',command=self.choose_vehicle_sts).pack(side='left',padx=5)
        self.confirm_sts_button=self.ui.Button(tools,text='To mój pojazd — dolicz',command=self.confirm_vehicle_sts,state='disabled');self.confirm_sts_button.pack(side='left',padx=5)
        self.ui.Button(tools,text='Cofnij potwierdzenia',command=self.reset_vehicle_sts).pack(side='left',padx=5)
        self.ui.Button(tools,text='Rozwiń wszystko',command=lambda:self.expand_vehicles(True)).pack(side='right')
        self.ui.Button(tools,text='Zwiń wszystko',command=lambda:self.expand_vehicles(False)).pack(side='right',padx=5)
        searchrow=ttk.Frame(self.vehicle_tab);searchrow.pack(fill='x',pady=(0,7))
        self.ui.Label(searchrow,text='Szukaj pojazdu, mapy lub części:').pack(side='left')
        self.vehicle_search=tk.StringVar()
        ttk.Entry(searchrow,textvariable=self.vehicle_search,width=45).pack(side='left',padx=8)
        self.vehicle_status=self.ui.StringVar(value='Wczytaj zapis hosta lub gracza.')
        self.ui.Label(self.vehicle_tab,textvariable=self.vehicle_status,wraplength=1100).pack(anchor='w',pady=4)
        # Reserve the explanatory footer before allocating space to the expanding tree.
        footer=ttk.Frame(self.vehicle_tab);footer.pack(side='bottom',fill='x')
        self.vehicle_details=self.ui.StringVar(value='Rozwiń pojazd, aby zobaczyć jego wyposażenie.')
        self.ui.Label(footer,textvariable=self.vehicle_details,wraplength=1100).pack(anchor='w',pady=6)
        self.vehicle_notes=self.ui.Text(footer,height=5,wrap='word',state='disabled')
        self.vehicle_notes.pack(fill='x')
        frame=ttk.Frame(self.vehicle_tab);frame.pack(fill='both',expand=True)
        self.vehicle_tree=self.ui.Treeview(frame,columns=('location','source','id'),show='tree headings',height=14,selectmode='browse')
        for col,title,width in [('#0','Pojazd / zamontowana część',370),('location','Miejsce / rodzaj części',385),('source','Źródło / pewność danych',260),('id','Identyfikator',290)]:
            self.vehicle_tree.heading(col,text=title);self.vehicle_tree.column(col,width=width,minwidth=90,stretch=False)
        v=ttk.Scrollbar(frame,orient='vertical',command=self.vehicle_tree.yview)
        h=ttk.Scrollbar(frame,orient='horizontal',command=self.vehicle_tree.xview)
        self.vehicle_tree.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        self.vehicle_tree.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        self.vehicle_tree.tag_configure('uncertain',foreground='#9a6500')
        self.vehicle_tree.bind('<<TreeviewSelect>>',self.select_vehicle)
        self.vehicle_search.trace_add('write',lambda *_:self.refresh_vehicles())

    def selected_vehicle_key(self):
        return 'host' if self.vehicle_source.get()=='Host' else 'guest'

    def refresh_vehicles(self):
        if not hasattr(self,'vehicle_tree'):return
        self.vehicle_tree.delete(*self.vehicle_tree.get_children());self.vehicle_candidates.clear()
        self.confirm_sts_button.configure(state='disabled')
        key=self.selected_vehicle_key();data=self.fleets.get(key)
        self.vehicle_details.set('Rozwiń pojazd, aby zobaczyć wyposażenie. Zaznaczenie wiersza pokazuje jego pełny opis.')
        if not data:
            self.vehicle_status.set('Nie wczytano tego zapisu. Wybierz plik i kliknij „Wczytaj zapisy”.')
            notes='Przy wczytaniu CompleteSave program automatycznie szuka plików STS tego samego slotu w jego folderze. Możesz też wskazać je ręcznie.'
        else:
            query=self.vehicle_search.get().casefold();shown=0
            def add_parts(parent,parts):
                for part in parts:
                    self.vehicle_tree.insert(parent,'end',text=part['name'],values=(part['kind'],part['source'],part['id']))
            for truck in data['trucks']:
                terms=[truck['name'],truck['type'],truck['location']]
                terms.extend(' '.join(str(v) for v in p.values()) for p in truck['parts'])
                terms.extend(c['location']+' '+c['guid']+' '+' '.join(p['name'] for p in c['parts']) for c in truck['candidates'])
                if query not in (' '.join(terms)+' '+self.ui.text(' '.join(terms))).casefold():continue
                shown+=truck['qty'];title=truck['name']+(f' × {truck["qty"]}' if truck['qty']>1 else '')
                node=self.vehicle_tree.insert('','end',text=title,values=(truck['location'],truck['state'],truck['guid'] or truck['type']),tags=('uncertain',) if not truck['parts'] else (),open=bool(query))
                add_parts(node,truck['parts'])
                if not truck['parts']:
                    self.vehicle_tree.insert(node,'end',text='Brak potwierdzonego wyposażenia w CompleteSave',values=('','Przenieś pojazd do garażu lub magazynu i zapisz grę',''))
                for candidate in truck['candidates']:
                    descriptor=candidate.get('descriptor')
                    status='STS — własność niepotwierdzona' if descriptor is None or descriptor['isUnlocked'] else 'STS — nieodblokowany, poza wyceną'
                    possible=self.vehicle_tree.insert(node,'end',text='Możliwy rekord: '+candidate['name'],values=(candidate['location'],status,candidate['guid']),tags=('uncertain',),open=bool(query))
                    self.vehicle_candidates[possible]=candidate
                    add_parts(possible,candidate['parts'])
                    explanation='Pełny segment wyposażenia STS' if descriptor is not None else 'Niepełny odczyt: '+candidate.get('decode_error','')
                    self.vehicle_tree.insert(possible,'end',text=explanation,values=('',candidate['file'],''))
            total=sum(t['qty'] for t in data['trucks'])
            path=self.host.get() if key=='host' else self.guest.get()
            self.vehicle_status.set(f'{path} | Pojazdy: {shown} / {total} | Odczytane pliki STS: {data["files"]}')
            notes='\n'.join(data['notes'])
        self.vehicle_notes.configure(state='normal');self.vehicle_notes.delete('1.0','end');self.vehicle_notes.insert('end',notes);self.vehicle_notes.configure(state='disabled')

    def select_vehicle(self,*_):
        selected=self.vehicle_tree.selection()
        if selected:
            item=self.vehicle_tree.raw_item(selected[0]);values=item['values']
            self.vehicle_details.set(item['text']+'\n'+' | '.join(str(v) for v in values if v))
            candidate=self.vehicle_candidates.get(selected[0]);descriptor=candidate.get('descriptor') if candidate else None
            self.confirm_sts_button.configure(state='normal' if descriptor and descriptor['isUnlocked'] else 'disabled')

    def expand_vehicles(self,expanded):
        def visit(parent):
            for node in self.vehicle_tree.get_children(parent):
                if self.vehicle_tree.get_children(node):
                    self.vehicle_tree.item(node,open=expanded);visit(node)
        visit('')

    def choose_vehicle_sts(self):
        key=self.selected_vehicle_key()
        data=self.loaded_host if key=='host' else self.loaded_guest
        if data is None:
            self.ui.dialog(messagebox.showinfo,'Najpierw wczytaj zapis','Wczytaj zapis wybranego gracza lub hosta.');return
        paths=self.ui.dialog(filedialog.askopenfilenames,title='Pliki STS dla wybranego zapisu (ten sam slot)',filetypes=[('Stan map SnowRunner','*sts_level_*.cfg *sts_level_*.dat')])
        if not paths:return
        save_path=str(self.host_save_path()) if key=='host' else self.guest.get()
        import re
        slot=re.fullmatch(r'CompleteSave([0-3]?)\.(?:cfg|dat)',Path(save_path).name,re.I)
        prefixes={re.match(r'(?:(\d)_)?sts_',Path(p).name,re.I).group(1) or '' for p in paths if re.match(r'(?:(\d)_)?sts_',Path(p).name,re.I)}
        if len(prefixes)!=1 or (slot and prefixes!={slot[1]}):
            self.ui.dialog(messagebox.showerror,'Niepasujący slot','Wybierz wyłącznie pliki STS z tego samego slotu co CompleteSave.');return
        try:
            result=fleet(data[1],save_path,sts_paths=paths)
            self.vehicle_confirmed[key].clear();self.fleets[key]=result
            self.invalidate();self.refresh_vehicles();self.refresh_valuations()
        except (OSError,ValueError,TypeError) as exc:self.ui.dialog(messagebox.showerror,'Nie można odczytać STS',str(exc))

    def confirm_vehicle_sts(self):
        selected=self.vehicle_tree.selection()
        candidate=self.vehicle_candidates.get(selected[0]) if selected else None
        if candidate is None or candidate.get('descriptor') is None or not candidate['descriptor']['isUnlocked']:return
        key=self.selected_vehicle_key();self.vehicle_confirmed[key].add(candidate['guid'])
        self.rebuild_vehicle_valuation(key)

    def reset_vehicle_sts(self):
        key=self.selected_vehicle_key();self.vehicle_confirmed[key].clear();self.rebuild_vehicle_valuation(key)

    def rebuild_vehicle_valuation(self,key):
        loaded=self.loaded_host if key=='host' else self.loaded_guest
        if loaded is None:return
        files=self.fleets.get(key,{}).get('file_paths',[])
        path=str(self.host_save_path()) if key=='host' else self.guest.get()
        self.fleets[key]=fleet(loaded[1],path,sts_paths=files,confirmed_guids=self.vehicle_confirmed[key])
        self.invalidate();self.refresh_vehicles();self.refresh_valuations()

    def refresh_valuations(self):
        self.valuations={key:assess(data[1],map_trucks=self.fleets.get(key,{}).get('map_descriptors',[])) for key,data in [('host',self.loaded_host),('guest',self.loaded_guest)] if data}
        for key in self.asset_labels:
            value=self.valuations.get(key)
            text=summary(value) if value else 'Nie wczytano zapisu'
            if value:
                text+=f'\nCiężarówki: {value["truck_count"]}  •  Wyposażenie znane dla: {value["described_count"]} (STS: {value["map_count"]})'
                if not value['complete']:text+='\nNiepełna wycena — sprawdź szczegóły.'
            self.asset_labels[key].set(text)
            self.asset_details[key].configure(state='normal' if value else 'disabled')

    def show_cat(self):
        self.stop_cat_effects()
        existing=getattr(self,'cat_window',None)
        if existing is not None and existing.winfo_exists():
            existing.lift();existing.focus_set()
        else:
            self.cat_window=self.ui.Toplevel(self.root)
            self.cat_window.resizable(False,False)
            self.cat_canvas=self.ui.Canvas(self.cat_window,width=440,height=430,bg='#fff4df',highlightthickness=0)
            self.cat_canvas.pack()
            self.cat_window.protocol('WM_DELETE_WINDOW',self.close_cat)
            self.cat_window.bind('<Destroy>',lambda event:self.stop_cat_effects() if event.widget is self.cat_window else None)
        breeds=[
            ('Brytyjski krótkowłosy','#929da9','#d6dde3','#d8ab48','round'),
            ('Syjamski','#eee0c6','#655347','#6fbae0','point'),
            ('Maine coon','#b8885a','#f4dec1','#95b563','fluffy'),
            ('Bengalski','#dca458','#f7ddb3','#a2bf6c','spots'),
            ('Rosyjski niebieski','#8494a4','#bfcbd4','#8abe69','plain'),
            ('Szkocki zwisłouchy','#c4b4a6','#f1e6d8','#cda651','fold'),
        ]
        choices=[b for b in breeds if b[0]!=getattr(self,'cat_breed',None)]
        breed,coat,light,eyes,pattern=random.choice(choices)
        self.cat_breed=breed
        rarity=roll_rarity();self.cat_rarity=rarity['name']
        self.cat_window.title('Kotek — '+rarity['name']+' — '+breed)
        canvas=self.cat_canvas;canvas.delete('all')
        canvas.configure(background=rarity['background'])
        canvas.create_rectangle(5,5,435,425,outline=rarity['accent'],width=5)
        canvas.create_text(220,25,text=f'{rarity["name"]} • {rarity["weight"]}%',font=('Segoe UI',15,'bold'),fill=rarity['text'])
        # A local vector illustration; works offline and needs no extra files.
        canvas.create_oval(80,348,365,386,fill='#ead9bd',outline='')
        canvas.create_line(305,337,367,319,380,278,356,257,fill=coat,width=26,smooth=True,capstyle='round')
        canvas.create_oval(132,204,310,374,fill=coat,outline='#75432a',width=3)
        canvas.create_oval(175,258,267,369,fill=light,outline='')
        canvas.create_polygon(125,145,122,60,192,105,fill=coat,outline='#75432a',width=3)
        canvas.create_polygon(249,104,316,60,316,151,fill=coat,outline='#75432a',width=3)
        canvas.create_polygon(138,118,136,83,170,108,fill='#eaa3a1',outline='')
        canvas.create_polygon(270,108,302,83,301,122,fill='#eaa3a1',outline='')
        canvas.create_oval(110,94,330,267,fill=coat,outline='#75432a',width=3)
        if pattern=='point':
            canvas.create_oval(135,130,305,245,fill=light,outline='')
        elif pattern=='spots':
            for x,y in [(145,136),(180,119),(248,119),(292,137),(145,246),(290,243),(151,285),(285,290)]:
                canvas.create_oval(x-7,y-5,x+7,y+5,fill='#795333',outline='')
        elif pattern=='fluffy':
            for points in [(118,165,85,203,120,206,100,232,147,246),(322,165,355,203,320,206,340,232,293,246)]:
                canvas.create_polygon(*points,fill=coat,outline='#75432a',width=2)
            canvas.create_line(122,85,116,48,137,79,fill=coat,width=5)
            canvas.create_line(301,80,321,48,315,87,fill=coat,width=5)
        elif pattern=='fold':
            canvas.create_polygon(122,61,192,105,137,125,fill=coat,outline=coat)
            canvas.create_polygon(249,104,316,61,303,126,fill=coat,outline=coat)
            canvas.create_polygon(122,97,171,106,143,136,fill=coat,outline='#75432a',width=3)
            canvas.create_polygon(318,97,269,106,297,136,fill=coat,outline='#75432a',width=3)
        elif pattern=='round':
            canvas.create_oval(114,177,162,224,fill=coat,outline='')
            canvas.create_oval(278,177,326,224,fill=coat,outline='')
        for x in (168,268):
            canvas.create_oval(x-15,153,x+15,188,fill=eyes,outline='#453629',width=2)
            canvas.create_oval(x-4,154,x+4,187,fill='#302b25',outline='')
            canvas.create_oval(x-7,157,x-1,164,fill='white',outline='')
        canvas.create_oval(164,195,221,238,fill=light,outline='')
        canvas.create_oval(219,195,276,238,fill=light,outline='')
        canvas.create_polygon(207,200,233,200,220,213,fill='#cd858a',outline='#75432a',width=2)
        canvas.create_line(220,213,220,223,207,230,fill='#75432a',width=2,smooth=True)
        canvas.create_line(220,223,233,230,fill='#75432a',width=2,smooth=True)
        for y,dy in ((205,-12),(218,0),(230,12)):
            canvas.create_line(173,y,91,y+dy,fill='#75432a',width=2)
            canvas.create_line(267,y,349,y+dy,fill='#75432a',width=2)
        for x in (161,266):
            canvas.create_oval(x-27,340,x+27,375,fill=light,outline='#75432a',width=2)
        canvas.create_text(220,402,text=breed,font=('Segoe UI',16,'bold'),fill=rarity['text'])
        if self.cat_rarity in ('Epic','Legendary'):
            self.cat_effect=Fireworks(canvas)

    def stop_cat_effects(self):
        effect=getattr(self,'cat_effect',None)
        if effect is not None:
            effect.stop();self.cat_effect=None

    def close_cat(self):
        self.stop_cat_effects()
        window=getattr(self,'cat_window',None)
        if window is not None and window.winfo_exists():window.destroy()

    def file_row(self,parent,label,var,detect=False):
        row = ttk.Frame(parent); row.pack(fill='x',pady=3)
        self.ui.Label(row,text=label,width=13).pack(side='left')
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True,padx=5)
        def choose():
            path = self.ui.dialog(filedialog.askopenfilename,title=label,filetypes=[('SnowRunner','*.cfg *.dat *.zip' if var is self.host else '*.cfg *.dat'),('Wszystkie','*.*')])
            if path:
                if var is self.host and Path(path).suffix.lower()=='.zip':self.open_host_zip(path,prompt=False)
                else:var.set(path)
        self.ui.Button(row,text='Wybierz…',command=choose).pack(side='left')
        if detect:
            self.detect_save_button=self.ui.Button(row,text='Znajdź mój save',command=self.detect_player_save)
            self.detect_save_button.pack(side='left',padx=(6,0))

    def release_host_bundle(self):
        bundle=self._host_bundle;self._host_bundle=None
        if bundle is not None:bundle.close()

    def host_save_path(self):
        if self._host_bundle is not None and Path(self.host.get()).resolve()==self._host_bundle.inspection.path:
            return self._host_bundle.save_path
        return Path(self.host.get())

    def host_unchanged(self):
        if self._host_bundle is not None:self._host_bundle.check_unchanged()
        return self.host_save_path().read_bytes()==self.loaded_host[2]

    def load_host(self):
        path=Path(self.host.get())
        if path.suffix.lower()=='.zip':
            bundle=self._host_bundle
            current=False
            if bundle is not None and path.resolve()==bundle.inspection.path:
                try:bundle.check_unchanged();current=True
                except (OSError,ValueError):pass
            if not current:
                prepared=self.prepare_host_zip(path,prompt=False)
                if prepared is None:raise HostLoadCancelled()
                self.release_host_bundle();self._host_bundle=prepared
        return load(self.host_save_path())

    def prepare_host_zip(self,path,prompt=True):
        inspection=inspect_archive(path,load_bytes)
        member=inspection.saves[0] if len(inspection.saves)==1 else self.choose_host_zip_member(inspection)
        if member is None:return None
        if prompt:
            xp=f'{member.experience:,}'.replace(',',' ') if member.experience is not None else 'brak danych'
            rank=member.rank if member.rank is not None else 'brak danych'
            trucks=member.trucks if member.trucks is not None else 'brak danych'
            question=f'Znaleziono plik zapisu hosta — {inspection.path.name}\n\n{member.name} • slot {member.slot}\nSaldo: {money(member.money)}\nDoświadczenie: {xp} XP • ranga: {rank}\nPosiadane ciężarówki: {trucks}\n\nCzy chcesz go wczytać?'
            if not self.ui.dialog(messagebox.askyesno,'Znaleziono zapis hosta',question,parent=self.root):return None
        return prepare_bundle(inspection,member)

    def open_host_zip(self,path,prompt=True):
        try:
            prepared=self.prepare_host_zip(path,prompt)
            if prepared is None:return False
            self.host.set(str(prepared.inspection.path))
            self.release_host_bundle();self._host_bundle=prepared
            self.read_saves()
            return self.loaded_host is not None
        except (OSError,ValueError,RuntimeError) as error:
            self.ui.dialog(messagebox.showerror,'Nie można wczytać ZIP hosta',str(error),parent=self.root)
            return False

    def choose_host_zip_member(self,inspection):
        window=self.ui.Toplevel(self.root);window.title('Wybierz slot hosta z ZIP');window.geometry('800x360')
        window.transient(self.root);selected=[None]
        box=ttk.Frame(window,padding=12);box.pack(fill='both',expand=True)
        self.ui.Label(box,text='ZIP zawiera kilka zapisów. Wybierz właściwy slot hosta.',wraplength=750).pack(anchor='w',pady=8)
        row=ttk.Frame(box);row.pack(side='bottom',fill='x',pady=8)
        table=self.ui.Treeview(box,columns=('slot','money','xp','rank'),show='tree headings',selectmode='browse')
        table.heading('#0',text='Plik');table.column('#0',width=240)
        for col,title in [('slot','Slot'),('money','Saldo'),('xp','XP'),('rank','Ranga')]:
            table.heading(col,text=title);table.column(col,width=100)
        indexed={}
        for member in inspection.saves:
            node=table.insert('','end',text=member.name,values=(member.slot,money(member.money),member.experience if member.experience is not None else '—',member.rank if member.rank is not None else '—'))
            indexed[node]=member
        table.pack(fill='both',expand=True)
        def choose(*_):
            nodes=table.selection()
            if nodes:selected[0]=indexed[nodes[0]];window.destroy()
        self.ui.Button(row,text='Wybierz zapis hosta',command=choose).pack(side='right')
        self.ui.Button(row,text='Anuluj',command=window.destroy).pack(side='right',padx=8)
        table.bind('<Double-1>',choose);table.bind('<Return>',choose)
        first=next(iter(indexed));table.selection_set(first);table.focus(first);table.focus_set()
        window.grab_set();self.root.wait_window(window)
        return selected[0]

    def startup(self):
        if not self.host.get().strip():
            archive=newest_zip(application_folder())
            if archive is not None:self.open_host_zip(archive,prompt=True)
        self.detect_player_save(automatic=True,allow_loaded_host=True)

    def cancel_save_search(self,event=None):
        if event is not None and event.widget is not self.root:return
        self.release_host_bundle()
        if self._save_search is not None:self._save_search['cancel'].set()
        self._save_search=None
        if self._save_search_job is not None:
            try:self.root.after_cancel(self._save_search_job)
            except tk.TclError:pass
            self._save_search_job=None

    def detect_player_save(self,automatic=False,allow_loaded_host=False):
        if automatic and self.guest.get().strip():return
        if self._save_search is not None:return
        window=self._save_search_window
        if window is not None and window.winfo_exists():
            window.lift();return
        result_queue=queue.Queue();cancel=threading.Event()
        request={'queue':result_queue,'cancel':cancel,'guest':self.guest.get(),'automatic':automatic,'allow_host':allow_loaded_host}
        self._save_search=request;self.detect_save_button.configure(state='disabled')
        self.status.set('Szukam lokalnych zapisów gracza w folderach Steam i Dokumenty…')
        def worker():
            try:
                def validate(path):return load(path)[1]['persistentProfileData']
                result_queue.put((discover_saves(validator=validate,cancel=cancel),None))
            except Exception as error:result_queue.put(([],str(error)))
        threading.Thread(target=worker,name='SnowRunner-save-discovery',daemon=True).start()
        self._save_search_job=self.root.after(75,self.poll_save_search)

    def poll_save_search(self):
        self._save_search_job=None;request=self._save_search
        if request is None:return
        try:candidates,error=request['queue'].get_nowait()
        except queue.Empty:
            self._save_search_job=self.root.after(75,self.poll_save_search);return
        self._save_search=None;self.detect_save_button.configure(state='normal')
        # A user's newer choice wins over a background search result.
        if request['cancel'].is_set() or self.guest.get()!=request['guest']:return
        if request['automatic'] and (self.loaded_guest is not None or (self.loaded_host is not None and not request.get('allow_host',False))):return
        if error:
            self.status.set('Nie udało się wyszukać zapisów. Wybierz swój plik ręcznie.');return
        host=self.host.get().strip()
        def different_from_host(candidate):
            if not host:return True
            try:return not os.path.samefile(candidate.path,host)
            except OSError:return os.path.normcase(str(candidate.path))!=os.path.normcase(os.path.abspath(host))
        candidates=[candidate for candidate in candidates if different_from_host(candidate)]
        if not candidates:
            self.status.set('Nie znaleziono lokalnego zapisu gracza. Użyj „Wybierz…” lub spróbuj ponownie po zapisaniu gry.');return
        if len(candidates)==1 and not request['guest'].strip():
            self.use_detected_save(candidates[0]);return
        self.show_detected_saves(candidates)

    def use_detected_save(self,candidate):
        self.guest.set(str(candidate.path))
        self.status.set(f'Znaleziono zapis gracza: {candidate.platform}, konto/profil {candidate.account}, slot {candidate.slot}. Kliknij „Wczytaj zapisy”.')
        if self._host_bundle is not None:self.read_saves()

    def show_detected_saves(self,candidates):
        window=self.ui.Toplevel(self.root);self._save_search_window=window
        window.title('Wybierz lokalny zapis gracza');window.geometry('1080x430');window.minsize(800,340)
        box=ttk.Frame(window,padding=12);box.pack(fill='both',expand=True)
        self.ui.Label(box,text='Znaleziono kilka zapisów lub wskazano już plik. Wybierz konto i slot; najnowsze zapisy są na górze.',wraplength=1000).pack(anchor='w',pady=(0,8))
        footer=ttk.Frame(box);footer.pack(side='bottom',fill='x',pady=(8,0))
        details=self.ui.StringVar();self.ui.Label(footer,textvariable=details,wraplength=1000).pack(anchor='w',pady=4)
        grid=ttk.Frame(box);grid.pack(fill='both',expand=True)
        columns=('platform','account','slot','modified','money','xp','path')
        table=self.ui.Treeview(grid,columns=columns,show='headings',selectmode='browse')
        for col,title,width in zip(columns,['Platforma','Konto / profil','Slot','Zmieniono','Gotówka','XP','Plik'],[140,130,50,100,110,90,600]):
            table.heading(col,text=title);table.column(col,width=width,minwidth=40,stretch=False)
        v=ttk.Scrollbar(grid,orient='vertical',command=table.yview);h=ttk.Scrollbar(grid,orient='horizontal',command=table.xview)
        table.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        table.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew')
        grid.rowconfigure(0,weight=1);grid.columnconfigure(0,weight=1)
        indexed={}
        for candidate in candidates:
            node=table.insert('','end',values=(candidate.platform,candidate.account,candidate.slot,modified_ago(candidate.modified),money(candidate.money),candidate.experience if candidate.experience is not None else '—',str(candidate.path)))
            indexed[node]=candidate
        def selected():
            selection=table.selection();return indexed.get(selection[0]) if selection else None
        def describe(*_):
            candidate=selected();details.set(str(candidate.path) if candidate else '')
        def choose(*_):
            candidate=selected()
            if candidate:
                self.use_detected_save(candidate);window.destroy()
        table.bind('<<TreeviewSelect>>',describe);table.bind('<Double-1>',choose);table.bind('<Return>',choose)
        def dismiss(*_):
            window.destroy();self.status.set('Listę zapisów zamknięto. Możesz użyć „Znajdź mój save” ponownie lub wybrać plik ręcznie.')
        window.protocol('WM_DELETE_WINDOW',dismiss);window.bind('<Escape>',dismiss)
        self.ui.Button(footer,text='Użyj wybranego zapisu',command=choose).pack(side='right')
        self.ui.Button(footer,text='Anuluj',command=dismiss).pack(side='right',padx=8)
        if indexed:
            first=next(iter(indexed));table.selection_set(first);table.focus(first);table.focus_set();describe()
        self.status.set(f'Znaleziono {len(candidates)} lokalnych zapisów. Wybierz konto i slot w otwartym oknie.')

    def invalidate(self):
        self.pending = None; self.save_btn.configure(state='disabled')

    def path_changed(self,*_):
        if self._host_bundle is not None:
            try:keep=Path(self.host.get()).resolve()==self._host_bundle.inspection.path
            except OSError:keep=False
            if not keep:self.release_host_bundle()
        self.invalidate(); self.manual.clear(); self.loaded_host = self.loaded_guest = None
        self.money_box.pack_forget(); self.xp_box.pack_forget(); self.assets_box.pack_forget(); self.valuations.clear(); self.preview_btn.configure(state='disabled')
        self.status.set('Ścieżki zmienione. Kliknij „Wczytaj zapisy”.')
        self.show(''); self.refresh_list()
        self.fleets.clear();self.vehicle_confirmed={"host":set(),"guest":set()};self.refresh_vehicles()

    def options_changed(self,*_):
        self.invalidate()
        self.amount_entry.configure(state='disabled' if self.mode.get() == 'Bez zmian' else 'normal')
        if self.loaded_guest:
            old = self.loaded_guest[1]['persistentProfileData']['money']
            try:
                amount = int(self.amount.get())
                new = old if self.mode.get() == 'Bez zmian' else (old+amount if self.mode.get() == 'Dodaj kwotę' else amount)
                if self.mode.get() != 'Bez zmian' and (amount < 0 or not 0 <= new <= 2147483647): raise ValueError()
                self.result_balance.set(f'Po zapisie: {new:,} $'.replace(',',' '))
            except ValueError: self.result_balance.set('Nieprawidłowa kwota')
        self.xp_entry.configure(state='normal' if self.xp_mode.get() in ('Dodaj XP','Ustaw XP','Ustaw poziom') else 'disabled')
        if self.loaded_guest:
            profile=self.loaded_guest[1]['persistentProfileData']
            host=self.loaded_host[1]['persistentProfileData'] if self.loaded_host else None
            self.xp_current.set(f"Gracz: {profile.get('experience','brak danych')} XP | poziom {profile.get('rank','?')}"+(f"     Host: {host.get('experience','brak danych')} XP | poziom {host.get('rank','?')}" if host else ''))
            try:
                value=int(self.xp_amount.get()) if self.xp_mode.get() in ('Dodaj XP','Ustaw XP','Ustaw poziom') else 0
                xp,rank=project_experience(host,profile,self.xp_mode.get(),value)
                self.xp_result.set(f'Po zapisie: {xp} XP | poziom {rank}')
            except ValueError as error:self.xp_result.set(str(error))
        self.refresh_list()

    def read_saves(self):
        self.invalidate(); self.manual.clear(); self.loaded_host = self.loaded_guest = None
        self.money_box.pack_forget(); self.xp_box.pack_forget(); self.assets_box.pack_forget(); self.valuations.clear()
        self.preview_btn.configure(state='disabled'); self.refresh_list()
        self.fleets.clear();self.vehicle_confirmed={"host":set(),"guest":set()};self.refresh_vehicles()
        try:
            guest=load(self.guest.get()) if self.guest.get().strip() else None
            host=self.load_host() if self.host.get().strip() else None
            if not guest and not host: raise ValueError('Wybierz przynajmniej jeden zapis.')
            if guest:
                balance=guest[1]['persistentProfileData'].get('money')
                if type(balance) is not int or balance<0: raise ValueError('Nieobsługiwane saldo gracza.')
            if host and guest and os.path.samefile(self.host_save_path(),self.guest.get()): raise ValueError('Host i gracz muszą wskazywać różne pliki.')
            self.loaded_guest,self.loaded_host=guest,host
            self.mode.set('Bez zmian');self.amount.set('0');self.sync.set(host is not None)
            self.xp_amount.set('0');self.xp_mode.set('Synchronizuj z hostem' if host and guest and valid_xp(host[1]['persistentProfileData'].get('experience')) and valid_xp(guest[1]['persistentProfileData'].get('experience')) else 'Bez zmian')
            self.assets_box.pack(fill='x',pady=5)
            if guest:
                self.balance.set(f'Obecne saldo: {money(balance)}')
                self.money_box.pack(fill='x',pady=5,before=self.options)
                self.xp_box.pack(fill='x',pady=3,before=self.options)
                self.preview_btn.configure(state='normal')
            self.options_changed()
            self.status.set('Wczytano '+('zapis hosta i gracza.' if host and guest else ('zapis gracza.' if guest else 'zapis hosta — podgląd majątku i XP.')))
            self.show('');self.refresh_list()
            for key,data,path in [('host',host,str(self.host_save_path())),('guest',guest,self.guest.get())]:
                if data:
                    try:self.fleets[key]=fleet(data[1],path)
                    except (OSError,ValueError,TypeError) as error:
                        self.fleets[key]=fleet(data[1],sts_paths=[])
                        self.fleets[key]['notes'].insert(0,'Nie udało się odczytać plików map: '+str(error))
            self.vehicle_source.set('Gracz' if guest else 'Host')
            self.refresh_vehicles();self.refresh_valuations()
        except HostLoadCancelled:
            self.status.set('Anulowano wybór zapisu hosta.')
        except Exception as e:
            self.status.set('Nie udało się wczytać zapisów.')
            self.ui.dialog(messagebox.showerror,'Błąd wczytywania',str(e))

    def show_assets(self,key):
        result=self.valuations.get(key)
        if not result:return
        window=self.ui.Toplevel(self.root);window.title('Wartość firmy — '+('host' if key=='host' else 'gracz'))
        window.geometry('1100x700')
        box=ttk.Frame(window,padding=12);box.pack(fill='both',expand=True)
        self.ui.Label(box,text=summary(result),font=('Segoe UI',13,'bold')).pack(anchor='w')
        breakdown='Gotówka: '+money(result['cash'])+' | Podwozia: '+money(result['chassis'])+' | Zamontowane części: '+money(result['installed'])+' | Zapas: '+money(result['spares'])
        self.ui.Label(box,text=breakdown,wraplength=1060).pack(anchor='w',pady=8)
        grid=ttk.Frame(box);grid.pack(fill='both',expand=True)
        columns=('kind','name','qty','price','total','source')
        table=self.ui.Treeview(grid,columns=columns,show='headings')
        for col,title,width in zip(columns,['Rodzaj','Element','Szt.','Cena/szt.','Wartość','Miejsce'],[160,350,45,100,110,300]):
            table.heading(col,text=title);table.column(col,width=width,minwidth=40,stretch=False)
        v=ttk.Scrollbar(grid,orient='vertical',command=table.yview);h=ttk.Scrollbar(grid,orient='horizontal',command=table.xview)
        table.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        table.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew')
        grid.rowconfigure(0,weight=1);grid.columnconfigure(0,weight=1)
        for kind,name,qty,unit,total,source in result['rows']:
            table.insert('','end',values=(kind,name,qty,money(unit) if unit is not None else 'Brak ceny',money(total) if total is not None else 'Pominięto',source))
        text=self.ui.Text(box,height=7,wrap='word');text.pack(fill='x',pady=8)
        notes=['Wycena nominalna według katalogu gry z 11.11.2026. Nie jest to cena sprzedaży ani suma historycznych wydatków; mnożniki NG+ nie są stosowane. Same odblokowania nie zwiększają majątku.']
        notes+=result['warnings'] or ['Wszystkie posiadane elementy obecne w obsługiwanych sekcjach zapisu zostały wycenione.']
        text.insert('end','\n\n'.join(notes));text.configure(state='disabled')

    def desired(self,component):
        if component in self.manual: return self.manual[component]
        if self.loaded_guest and is_unlocked(self.loaded_guest[1],component): return True
        return bool(self.sync.get() and self.loaded_host and is_unlocked(self.loaded_host[1],component))

    def refresh_list(self):
        self.table.delete(*self.table.get_children()); self.row_keys.clear()
        host = self.loaded_host[1] if self.loaded_host else None
        guest = self.loaded_guest[1] if self.loaded_guest else None
        query = self.search.get().casefold()
        for row in upgrade_rows(host,guest):
            if query not in (' '.join(row)+' '+self.ui.text(' '.join(row))).casefold(): continue
            if self.only_missing.get() and not row[6]: continue
            component=UNLOCK_IDS.get(row[7])
            values=list(row)
            if component in self.manual:
                values[6]='Ręcznie: odblokuj' if self.manual[component] else 'Ręcznie: usuń'
            label=('☑' if self.desired(component) else '☐') if component and self.loaded_guest else '—'
            if not component: values[6]='Brak mapowania części'
            iid=self.table.insert('', 'end',text=label,values=values,tags=('missing',) if values[6] else ())
            self.row_keys[iid]=component
        self.edit_check.configure(state='disabled') if hasattr(self,'edit_check') else None
        self.detail.set('Kliknij checkbox lub zaznacz ulepszenie i naciśnij spację. Zmiany zostaną zapisane dopiero przyciskiem „Zapisz”.')

    def select_row(self,*_):
        selected = self.table.selection()
        if selected:
            row = self.table.raw_item(selected[0],'values')
            component=self.row_keys.get(selected[0])
            self.checked.set(self.desired(component) if component else False)
            self.edit_check.configure(state='normal' if component and self.loaded_guest else 'disabled')
            self.detail.set(f'{row[0]} — {row[1]} — {row[2]}\nPojazdy: {row[3] or "brak w katalogu"} | Część: {component or "brak pewnego mapowania — edycja niedostępna"}')
        elif hasattr(self,'edit_check'): self.edit_check.configure(state='disabled')

    def edit_selected(self):
        selected=self.table.selection()
        if not selected or not self.loaded_guest: return
        component=self.row_keys.get(selected[0])
        if not component: return
        value=self.checked.get()
        baseline=is_unlocked(self.loaded_guest[1],component) or bool(self.sync.get() and self.loaded_host and is_unlocked(self.loaded_host[1],component))
        if value==baseline: self.manual.pop(component,None)
        else: self.manual[component]=value
        self.invalidate(); self.refresh_list()
        for iid,key in self.row_keys.items():
            if key==component:
                self.table.selection_set(iid); self.table.focus(iid); self.select_row(); break

    def click_checkbox(self,event):
        if self.table.identify_column(event.x)!='#0': return
        iid=self.table.identify_row(event.y)
        if not iid or not self.loaded_guest or not self.row_keys.get(iid): return
        self.table.selection_set(iid); self.table.focus(iid)
        self.checked.set(not self.desired(self.row_keys[iid])); self.edit_selected()
        return 'break'

    def space_checkbox(self,event=None):
        selected=self.table.selection()
        if selected and self.loaded_guest:
            component=self.row_keys.get(selected[0])
            if component:
                self.checked.set(not self.desired(component)); self.edit_selected()
        return 'break'

    def reset_manual(self):
        self.manual.clear(); self.invalidate(); self.refresh_list()

    def show(self,text):
        self.report.configure(state='normal'); self.report.delete('1.0','end'); self.report.insert('end',text); self.report.configure(state='disabled')

    def preview(self):
        self.invalidate()
        try:
            if not self.loaded_guest: raise ValueError('Najpierw wczytaj zapis gracza.')
            if self.sync.get() and not self.loaded_host: raise ValueError('Wczytaj hosta lub wyłącz synchronizację do samej edycji pieniędzy.')
            path = Path(self.guest.get()).resolve(strict=True)
            doc,guest,raw,bom,suffix = self.loaded_guest
            if path.read_bytes() != raw: raise ValueError('Zapis gracza zmienił się. Wczytaj ponownie.')
            if (self.sync.get() or self.xp_mode.get()=='Synchronizuj z hostem') and not self.host_unchanged(): raise ValueError('Zapis hosta zmienił się. Wczytaj ponownie.')
            amount = int(self.amount.get()) if self.mode.get() != 'Bez zmian' else 0
            result,changes = merge(self.loaded_host[1] if self.loaded_host else None,guest,self.sync.get(),self.mode.get(),amount)
            xp_value=int(self.xp_amount.get()) if self.xp_mode.get() in ('Dodaj XP','Ustaw XP','Ustaw poziom') else 0
            result,xp_changes=apply_experience(self.loaded_host[1] if self.loaded_host else None,result,self.xp_mode.get(),xp_value)
            changes.extend(xp_changes)
            result,manual_changes = apply_manual(result,self.manual)
            changes.extend(manual_changes)
            output = copy.deepcopy(doc)
            block = next(v['SslValue'] for k,v in output.items() if k.startswith('CompleteSave') and isinstance(v,dict) and isinstance(v.get('SslValue'),dict))
            block.clear(); block.update(result)
            valuation=assess(result,map_trucks=self.fleets.get('guest',{}).get('map_descriptors',[]))
            wealth_note=summary(valuation)
            self.show(('\n'.join(changes) if changes else 'Brak zmian.')+'\n\nPo zapisie gracza:\n'+wealth_note)
            if changes:
                self.pending = (path,output,raw,bom,suffix)
                self.save_btn.configure(state='normal')
        except Exception as e: self.ui.dialog(messagebox.showerror,'Nie można przygotować zmian',str(e))

    def save(self):
        if not self.pending: return
        try:
            if (self.sync.get() or self.xp_mode.get()=='Synchronizuj z hostem') and self.loaded_host and not self.host_unchanged():raise ValueError('Zapis hosta zmienił się. Wczytaj ponownie.')
            backup = write_save(*self.pending)
            snapshots={key:(list(data.get('file_paths',[])),set(self.vehicle_confirmed[key])) for key,data in self.fleets.items()}
            self.read_saves()
            for key,(files,confirmed) in snapshots.items():
                loaded=self.loaded_host if key=='host' else self.loaded_guest
                if loaded is not None:
                    path=str(self.host_save_path()) if key=='host' else self.guest.get()
                    self.vehicle_confirmed[key]=confirmed
                    self.fleets[key]=fleet(loaded[1],path,sts_paths=files,confirmed_guids=confirmed)
            self.refresh_vehicles();self.refresh_valuations()
            self.show('Zapisano zmiany.\nKopia zapasowa: '+str(backup))
            self.ui.dialog(messagebox.showinfo,'Gotowe','Zapisano zmiany i kopię zapasową.')
        except Exception as e: self.ui.dialog(messagebox.showerror,'Zapis przerwany',str(e))
        finally: self.invalidate()

if __name__ == '__main__':
    root = tk.Tk(); ttk.Style().theme_use('clam'); app=App(root)
    root.after(200,app.startup)
    root.mainloop()
