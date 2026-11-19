"""Standalone host-only package builder for SnowRunner SaveSync."""
from pathlib import Path
from i18n import UI,LANGUAGES,settings_file,read_language,write_language
import os,queue,threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from save_discovery import discover_saves,modified_ago
from host_archive import application_folder
from host_packer import build_plan,create_package,profile_for_discovery,suggested_filename,package_report,PackCancelled


def amount(value):return f'{value:,}'.replace(',',' ')


def size_label(value):
    return f'{value/1024/1024:.1f} MB' if value>=1024*1024 else f'{value/1024:.1f} KB'


class PackerApp:
    def __init__(self,root,settings_path=None):
        self.root=root
        self.settings_path=Path(settings_path) if settings_path is not None else settings_file()
        self.ui=UI(root,read_language(self.settings_path))
        root.title(self.ui.text('SnowRunner — Paker hosta'));root.geometry('1160x800');root.minsize(880,650)
        self.plan=None;self.last_export=None;self.current_path=None;self.job=None;self.poll_job=None;self.closing=False
        root.protocol('WM_DELETE_WINDOW',self.close)
        box=ttk.Frame(root,padding=16);box.pack(fill='both',expand=True)
        header=ttk.Frame(box);header.pack(fill='x')
        languages=ttk.Frame(header);languages.pack(side='right')
        self.ui.Label(languages,text='Język').pack(side='left')
        self.language=tk.StringVar(value=LANGUAGES[self.ui.translator.language])
        self.language_selector=ttk.Combobox(languages,textvariable=self.language,values=list(LANGUAGES.values()),state='readonly',width=18)
        self.language_selector.pack(side='left',padx=8)
        self.language_selector.bind('<<ComboboxSelected>>',self.change_language)
        self.ui.Label(header,text='SnowRunner • Paker hosta',font=('Segoe UI',20,'bold')).pack(anchor='w')
        self.ui.Label(box,text='Wybierz profil i slot. Program dobierze zapis główny i pliki map do paczki dla graczy. Zamknij grę przed pakowaniem.',wraplength=1100).pack(anchor='w',pady=7)
        buttons=ttk.Frame(box);buttons.pack(fill='x',pady=5)
        self.search_button=self.ui.Button(buttons,text='Wyszukaj zapisy',command=self.search);self.search_button.pack(side='left')
        self.browse_button=self.ui.Button(buttons,text='Wybierz save ręcznie…',command=self.browse);self.browse_button.pack(side='left',padx=8)
        self.ui.Label(box,text='Profile i sloty zapisów',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(8,4))
        profile_box=ttk.Frame(box);profile_box.pack(fill='x')
        self.profiles=self.ui.Treeview(profile_box,columns=('platform','account','slot','changed','money','xp'),show='headings',height=4,selectmode='browse')
        for col,title,width in [('platform','Platforma',170),('account','Konto / profil',240),('slot','Slot',65),('changed','Zmieniono',140),('money','Gotówka',150),('xp','XP',130)]:
            self.profiles.heading(col,text=title);self.profiles.column(col,width=width,minwidth=50,stretch=True)
        scroll=ttk.Scrollbar(profile_box,orient='vertical',command=self.profiles.yview);self.profiles.configure(yscrollcommand=scroll.set)
        self.profiles.pack(side='left',fill='x',expand=True);scroll.pack(side='right',fill='y')
        self.candidates={};self.profiles.bind('<<TreeviewSelect>>',self.select_profile)
        self.profiles.bind('<Button-1>',lambda event:'break' if self.is_packing() else None)
        self.profiles.bind('<Key>',lambda event:'break' if self.is_packing() else None)
        self.source=tk.StringVar();ttk.Entry(box,textvariable=self.source,state='readonly').pack(fill='x',pady=(8,3))
        self.summary=self.ui.StringVar(value='Wyszukuję lokalne zapisy…')
        self.ui.Label(box,textvariable=self.summary,wraplength=1100).pack(anchor='w',pady=5)
        list_header=ttk.Frame(box);list_header.pack(fill='x',pady=4)
        self.file_count=self.ui.StringVar(value='Pliki do paczki')
        self.ui.Label(list_header,textvariable=self.file_count,font=('Segoe UI',11,'bold')).pack(side='left')
        self.refresh_button=self.ui.Button(list_header,text='Odśwież pliki',command=self.refresh,state='disabled');self.refresh_button.pack(side='right')
        footer=ttk.Frame(box);footer.pack(side='bottom',fill='x')
        self.details=self.ui.StringVar(value='W ZIP-ie będą wyłącznie pliki wybranego slotu, bez podfolderów.')
        self.ui.Label(footer,textvariable=self.details,wraplength=1100).pack(anchor='w',pady=6)
        self.status=self.ui.StringVar(value='Gotowy do wyszukiwania.')
        self.ui.Label(footer,textvariable=self.status,wraplength=1100).pack(anchor='w',pady=4)
        self.progress=ttk.Progressbar(footer,mode='determinate');self.progress.pack(fill='x',pady=4)
        actions=ttk.Frame(footer);actions.pack(fill='x',pady=5)
        self.pack_button=self.ui.Button(actions,text='Utwórz paczkę ZIP…',command=self.pack,state='disabled');self.pack_button.pack(side='left')
        self.copy_button=self.ui.Button(actions,text='Kopiuj listę plików',command=self.copy_report,state='disabled');self.copy_button.pack(side='left',padx=8)
        self.folder_button=self.ui.Button(actions,text='Pokaż folder paczki',command=self.open_folder,state='disabled');self.folder_button.pack(side='left')
        self.output=tk.StringVar();ttk.Entry(footer,textvariable=self.output,state='readonly').pack(fill='x',pady=4)
        grid=ttk.Frame(box);grid.pack(fill='both',expand=True)
        self.files=self.ui.Treeview(grid,columns=('file','size','description','state'),show='headings',height=10)
        for col,title,width in [('file','Plik',260),('size','Rozmiar',85),('description','Za co odpowiada',630),('state','Status',120)]:
            self.files.heading(col,text=title);self.files.column(col,width=width,minwidth=70,stretch=False)
        v=ttk.Scrollbar(grid,orient='vertical',command=self.files.yview);h=ttk.Scrollbar(grid,orient='horizontal',command=self.files.xview)
        self.files.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        self.files.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew')
        grid.rowconfigure(0,weight=1);grid.columnconfigure(0,weight=1)
        self.files.bind('<<TreeviewSelect>>',self.describe_file)
        self.file_nodes={}

    def change_language(self,event=None):
        code=next((key for key,value in LANGUAGES.items() if value==self.language.get()),'en')
        self.ui.change_language(code)
        self.root.title(self.ui.text('SnowRunner — Paker hosta'))
        try:write_language(self.settings_path,code)
        except OSError:
            self.ui.dialog(messagebox.showerror,'Ustawienia języka','Nie można zapisać ustawienia języka. W tej sesji wybrany język pozostaje aktywny.',parent=self.root)

    def is_packing(self):return self.job is not None and self.job['kind']=='pack'

    def controls(self):
        packing=self.is_packing()
        for button in (self.search_button,self.browse_button):button.configure(state='disabled' if packing else 'normal')
        self.refresh_button.configure(state='normal' if self.current_path and not packing else 'disabled')
        self.pack_button.configure(state='normal' if self.plan is not None and self.job is None else 'disabled')
        self.copy_button.configure(state='normal' if self.plan is not None and not packing else 'disabled')
        self.folder_button.configure(state='normal' if self.last_export and not packing else 'disabled')

    def start_job(self,kind,task):
        if self.is_packing():return
        if self.job is not None:self.job['cancel'].set()
        if self.poll_job is not None:self.root.after_cancel(self.poll_job);self.poll_job=None
        events=queue.Queue();cancel=threading.Event();self.job={'kind':kind,'events':events,'cancel':cancel}
        def worker():
            try:events.put(('done',task(cancel,events)))
            except PackCancelled:events.put(('cancelled',None))
            except Exception as error:events.put(('error',str(error)))
        threading.Thread(target=worker,name='SnowRunner-host-packer',daemon=True).start()
        self.controls();self.poll_job=self.root.after(60,self.poll)

    def poll(self):
        self.poll_job=None;job=self.job
        if job is None:return
        while True:
            try:kind,value=job['events'].get_nowait()
            except queue.Empty:
                self.poll_job=self.root.after(60,self.poll);return
            if kind=='progress':
                index,total,name=value;self.progress.configure(maximum=max(total,1),value=index)
                self.status.set(f'Pakowanie {index}/{total}: {name}')
                continue
            self.job=None
            if self.closing:self.root.destroy();return
            self.controls()
            if kind=='error':
                self.status.set('Nie udało się wykonać operacji: '+value)
                self.file_states('Do spakowania')
                self.ui.dialog(messagebox.showerror,'Paker hosta',value,parent=self.root);return
            if kind=='cancelled':self.status.set('Anulowano operację.');return
            if job['kind']=='search':self.show_candidates(value)
            elif job['kind']=='plan':self.show_plan(value)
            elif job['kind']=='pack':self.show_completed(value)
            return

    def search(self):
        if self.is_packing():return
        self.status.set('Szukam zapisów Steam, Dokumentów i OneDrive…')
        self.start_job('search',lambda cancel,events:discover_saves(validator=profile_for_discovery,cancel=cancel))

    def show_candidates(self,candidates):
        self.profiles.delete(*self.profiles.get_children());self.candidates.clear()
        for candidate in candidates:
            node=self.profiles.insert('','end',values=(candidate.platform,candidate.account,candidate.slot,modified_ago(candidate.modified),amount(candidate.money)+' $',amount(candidate.experience) if candidate.experience is not None else '—'))
            self.candidates[node]=candidate
        if len(candidates)==1:
            node=next(iter(self.candidates));self.profiles.selection_set(node);self.profiles.focus(node)
        self.status.set(f'Znaleziono {len(candidates)} zapisów. Wybierz profil i slot.' if candidates else 'Nie znaleziono zapisów. Użyj „Wybierz save ręcznie…”.')

    def select_profile(self,*_):
        if self.is_packing():return
        selected=self.profiles.selection()
        if selected and selected[0] in self.candidates:self.load_path(self.candidates[selected[0]].path)

    def browse(self):
        if self.is_packing():return
        path=self.ui.dialog(filedialog.askopenfilename,title='Wybierz główny plik CompleteSave',filetypes=[('SnowRunner — zapis główny','CompleteSave*.cfg CompleteSave*.dat'),('Wszystkie pliki','*.*')])
        if path:self.load_path(path)

    def load_path(self,path):
        if self.is_packing():return
        self.current_path=Path(path);self.plan=None;self.last_export=None;self.output.set('');self.source.set(str(path))
        self.files.delete(*self.files.get_children());self.file_nodes.clear()
        self.summary.set('Odczytuję profil i dobieram pliki właściwego slotu…');self.status.set('Sprawdzam pliki zapisu.');self.progress.configure(value=0)
        self.start_job('plan',lambda cancel,events:build_plan(path,cancel))

    def refresh(self):
        if self.current_path:self.load_path(self.current_path)

    def show_plan(self,plan):
        self.plan=plan;self.source.set(str(plan.source))
        xp=amount(plan.experience) if plan.experience is not None else 'brak danych'
        rank=plan.rank if plan.rank is not None else 'brak danych'
        self.summary.set(f'Profil: {plan.account} • Slot {plan.slot} • Saldo: {amount(plan.money)} $ • XP: {xp} • Ranga: {rank}')
        self.file_count.set(f'Pliki do paczki: {len(plan.files)} • {size_label(plan.total_size)}')
        self.files.delete(*self.files.get_children());self.file_nodes.clear()
        for file in plan.files:
            node=self.files.insert('','end',values=(file.name,size_label(file.size),file.description,'Do spakowania'));self.file_nodes[file.name]=node
        self.status.set('Gotowe. Utwórz ZIP — wszystkie potrzebne pliki wybrano automatycznie.' if len(plan.files)>1 else 'Znaleziono tylko zapis główny. Brak STS tego slotu; paczka nie dostarczy danych o pojazdach na mapach.')
        self.details.set('Zaznacz wiersz, aby przeczytać pełny opis pliku. Inne sloty i pliki fog nie są dodawane.')
        self.controls()

    def file_states(self,state):
        for node in self.file_nodes.values():
            if self.files.exists(node):
                values=self.files.raw_item(node,'values');self.files.item(node,values=(*values[:3],state))

    def describe_file(self,*_):
        selected=self.files.selection()
        if selected:
            values=self.files.raw_item(selected[0],'values');self.details.set(str(values[0])+' — '+str(values[2]))

    def pack(self):
        if self.plan is None or self.job is not None:return
        folder=application_folder()
        path=self.ui.dialog(filedialog.asksaveasfilename,title='Zapisz paczkę hosta',initialdir=str(folder),initialfile=suggested_filename(self.plan,folder),defaultextension='.zip',filetypes=[('Paczka ZIP','*.zip')],confirmoverwrite=True)
        if not path:return
        plan=self.plan;destination=Path(path);overwrite=destination.exists()
        self.last_export=None;self.output.set('');self.file_states('Pakowanie…');self.progress.configure(value=0,maximum=len(plan.files))
        self.status.set('Tworzę i sprawdzam paczkę ZIP…')
        def work(cancel,events):
            return create_package(plan,destination,overwrite,cancel,lambda i,total,name:events.put(('progress',(i,total,name))))
        self.start_job('pack',work)

    def show_completed(self,path):
        self.last_export=Path(path);self.output.set(str(path));self.file_states('Spakowano')
        self.progress.configure(value=len(self.plan.files),maximum=len(self.plan.files))
        self.status.set(f'Gotowe — {len(self.plan.files)} plików. ZIP jest gotowy do wysłania graczom.')
        self.details.set('Lista plików potwierdza zawartość gotowej paczki. Przyciskiem „Kopiuj listę plików” skopiujesz opisy.')
        self.controls()

    def copy_report(self):
        if self.plan is None:return
        self.root.clipboard_clear();self.root.clipboard_append(self.ui.text(package_report(self.plan,self.last_export)))
        self.status.set('Skopiowano listę plików i ich opisów do schowka.')

    def open_folder(self):
        if self.last_export:
            try:os.startfile(self.last_export.parent)
            except OSError as error:self.ui.dialog(messagebox.showerror,'Nie można otworzyć folderu',str(error),parent=self.root)

    def close(self):
        if self.job is not None:
            self.job['cancel'].set()
            if self.is_packing():
                self.closing=True;self.status.set('Przerywam pakowanie i usuwam plik tymczasowy…');return
        if self.poll_job is not None:self.root.after_cancel(self.poll_job);self.poll_job=None
        self.root.destroy()


if __name__=='__main__':
    root=tk.Tk();ttk.Style().theme_use('clam');app=PackerApp(root)
    root.after(200,app.search);root.mainloop()
