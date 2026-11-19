"""Display-only localization; canonical save data and option values stay untouched."""
from pathlib import Path
import json,os,re,tempfile,weakref
import tkinter as tk
from tkinter import ttk
from translations import ENGLISH, TRANSLATIONS

LANGUAGES={'en':'English','pl':'Polski','de':'Deutsch','fr':'Français','es':'Español','pt':'Português'}

def settings_file():
    return Path(os.environ.get('APPDATA',Path.home()/'.config'))/'SnowRunnerSaveSync'/'settings.json'

def read_language(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8')).get('language','en')
        return value if value in LANGUAGES else 'en'
    except (OSError,ValueError,TypeError,AttributeError):return 'en'

def write_language(path,language):
    if language not in LANGUAGES:raise ValueError('Unknown language')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):data={}
    if not isinstance(data,dict):data={}
    data['language']=language
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
            tmp=Path(stream.name);json.dump(data,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if tmp and tmp.exists():tmp.unlink()

class Translator:
    def __init__(self,language='en'):
        self.language=language if language in LANGUAGES else 'en'
        self._patterns={};self._mappings={}
    def text(self,value):
        if not isinstance(value,str) or self.language=='pl':return value
        mapping=self._mappings.get(self.language)
        if mapping is None:
            mapping={source:TRANSLATIONS.get(self.language,{}).get(english,english) for source,english in ENGLISH.items()}
            self._mappings[self.language]=mapping
        if value in mapping:return mapping[value]
        # One substitution pass: a translated phrase is never translated again.
        pattern=self._patterns.get(self.language)
        if pattern is None:
            pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True))+r')(?!\w)')
            self._patterns[self.language]=pattern
        # Preserve user paths and technical identifiers verbatim in diagnostic text.
        protected=re.compile(r'[A-Za-z]:[\\/][^\n|]*|\b[\w-]+_[\w.-]+\b|\b[^\s|]+\.(?:cfg|dat|zip|bak)(?:\.[\w.-]+)?\b',re.I)
        parts=protected.split(value);matches=list(protected.finditer(value));out=[]
        for index,part in enumerate(parts):
            out.append(pattern.sub(lambda m:mapping[m.group()],part))
            if index<len(matches):out.append(matches[index].group())
        return ''.join(out)

class UI:
    def __init__(self,root,language='en'):
        self.root=root;self.translator=Translator(language);self._objects=[]
    def text(self,value):return self.translator.text(value)
    def register(self,obj):self._objects.append(weakref.ref(obj))
    def change_language(self,language):
        if language not in LANGUAGES:raise ValueError('Unknown language')
        self.translator.language=language
        live=[]
        for ref in self._objects:
            obj=ref()
            if obj is not None:
                try:obj.retranslate();live.append(ref)
                except tk.TclError:pass
        self._objects=live
    def StringVar(self,*args,**kwargs):return DisplayVar(self,*args,**kwargs)
    def Label(self,*args,**kwargs):return LocalLabel(self,*args,**kwargs)
    def Button(self,*args,**kwargs):return LocalButton(self,*args,**kwargs)
    def Checkbutton(self,*args,**kwargs):return LocalCheckbutton(self,*args,**kwargs)
    def LabelFrame(self,*args,**kwargs):return LocalLabelFrame(self,*args,**kwargs)
    def Notebook(self,*args,**kwargs):return LocalNotebook(self,*args,**kwargs)
    def Treeview(self,*args,**kwargs):return LocalTree(self,*args,**kwargs)
    def Combobox(self,*args,**kwargs):return LocalCombo(self,*args,**kwargs)
    def Text(self,*args,**kwargs):return LocalText(self,*args,**kwargs)
    def Toplevel(self,*args,**kwargs):return LocalWindow(self,*args,**kwargs)
    def Canvas(self,*args,**kwargs):return LocalCanvas(self,*args,**kwargs)
    def dialog(self,method,*args,**kwargs):
        args=tuple(self.text(arg) for arg in args)
        if 'title' in kwargs:kwargs['title']=self.text(kwargs['title'])
        if 'filetypes' in kwargs:kwargs['filetypes']=[(self.text(label),pattern) for label,pattern in kwargs['filetypes']]
        return method(*args,**kwargs)

class DisplayVar(tk.StringVar):
    def __init__(self,ui,*args,**kwargs):
        self.ui=ui;self.raw=kwargs.get('value','');kwargs.setdefault('master',ui.root)
        super().__init__(*args,**kwargs);ui.register(self);self.retranslate()
    def set(self,value):self.raw=value;super().set(self.ui.text(value))
    def get(self):return self.raw
    def retranslate(self):super().set(self.ui.text(self.raw))

class TextOption:
    def __init__(self,ui,*args,**kwargs):
        self.ui=ui;self.raw_text=kwargs.get('text','')
        if 'text' in kwargs:kwargs['text']=ui.text(kwargs['text'])
        super().__init__(*args,**kwargs);ui.register(self)
    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs};cnf=None
        if 'text' in kwargs:self.raw_text=kwargs['text'];kwargs['text']=self.ui.text(self.raw_text)
        return super().configure(cnf,**kwargs)
    config=configure
    def retranslate(self):super().configure(text=self.ui.text(self.raw_text))
class LocalLabel(TextOption,ttk.Label):pass
class LocalButton(TextOption,ttk.Button):pass
class LocalCheckbutton(TextOption,ttk.Checkbutton):pass
class LocalLabelFrame(TextOption,ttk.LabelFrame):pass

class LocalNotebook(ttk.Notebook):
    def __init__(self,ui,*args,**kwargs):self.ui=ui;self.labels={};super().__init__(*args,**kwargs);ui.register(self)
    def add(self,child,**kwargs):
        self.labels[str(child)]=kwargs.get('text','');kwargs['text']=self.ui.text(self.labels[str(child)]);super().add(child,**kwargs)
    def retranslate(self):
        for tab,label in self.labels.items():self.tab(tab,text=self.ui.text(label))

class LocalTree(ttk.Treeview):
    def __init__(self,ui,*args,**kwargs):self.ui=ui;self.labels={};self.rows={};super().__init__(*args,**kwargs);ui.register(self)
    def heading(self,column,option=None,**kwargs):
        if 'text' in kwargs:self.labels[column]=kwargs['text'];kwargs['text']=self.ui.text(kwargs['text'])
        return super().heading(column,option,**kwargs)
    def insert(self,parent,index,iid=None,**kwargs):
        raw={k:v for k,v in kwargs.items() if k in ('text','values')}
        for k,v in raw.items():kwargs[k]=tuple(self.ui.text(x) for x in v) if k=='values' else self.ui.text(v)
        iid=super().insert(parent,index,iid,**kwargs);self.rows[iid]=raw;return iid
    def item(self,item,option=None,**kwargs):
        for key in ('text','values'):
            if key in kwargs:
                self.rows.setdefault(item,{})[key]=kwargs[key]
                kwargs[key]=tuple(self.ui.text(v) for v in kwargs[key]) if key=='values' else self.ui.text(kwargs[key])
        return super().item(item,option,**kwargs)
    def raw_item(self,item,option=None):
        result=super().item(item);result.update(self.rows.get(item,{}))
        return result.get(option) if option else result
    def delete(self,*items):
        def forget(item):
            for child in self.get_children(item):forget(child)
            self.rows.pop(item,None)
        for item in items:forget(item)
        return super().delete(*items)
    def retranslate(self):
        for col,text in self.labels.items():super().heading(col,text=self.ui.text(text))
        for iid,raw in self.rows.items():
            super().item(iid,**{k:tuple(self.ui.text(x) for x in v) if k=='values' else self.ui.text(v) for k,v in raw.items()})

class LocalCombo(ttk.Combobox):
    """Translated choices backed by the original, language-independent option variable."""
    def __init__(self,ui,*args,**kwargs):
        self.ui=ui;self.canonical=kwargs.pop('textvariable');self.choices=tuple(kwargs.pop('values'))
        self.display=tk.StringVar(master=ui.root);kwargs['textvariable']=self.display
        super().__init__(*args,**kwargs);ui.register(self)
        super().bind('<<ComboboxSelected>>',self.select)
        self.trace=self.canonical.trace_add('write',lambda *_:self.retranslate())
        self.bind('<Destroy>',self.cleanup,add='+');self.retranslate()
    def bind(self,sequence=None,func=None,add=None):
        if sequence=='<<ComboboxSelected>>' and func:add='+'
        return super().bind(sequence,func,add)
    def select(self,event=None):
        index=self.current()
        if index>=0:self.canonical.set(self.choices[index])
    def retranslate(self):
        super().configure(values=[self.ui.text(v) for v in self.choices])
        value=self.canonical.get()
        if value in self.choices:self.current(self.choices.index(value))
        else:self.display.set(self.ui.text(value))
    def cleanup(self,event):
        if event.widget is self:self.canonical.trace_remove('write',self.trace)

class LocalText(tk.Text):
    def __init__(self,ui,*args,**kwargs):self.ui=ui;self.raw='';super().__init__(*args,**kwargs);ui.register(self)
    def insert(self,index,chars,*args):
        if index in ('end','1.0'):self.raw=(self.raw+chars) if index=='end' else (chars+self.raw)
        return super().insert(index,self.ui.text(chars),*args)
    def delete(self,index1,index2=None):
        if index1=='1.0' and index2=='end':self.raw=''
        return super().delete(index1,index2)
    def retranslate(self):
        state=self.cget('state');view=self.yview();super().configure(state='normal')
        super().delete('1.0','end');super().insert('1.0',self.ui.text(self.raw));self.yview_moveto(view[0]);super().configure(state=state)

class LocalWindow(tk.Toplevel):
    def __init__(self,ui,*args,**kwargs):self.ui=ui;self.raw_title='';super().__init__(*args,**kwargs);ui.register(self)
    def title(self,string=None):
        if string is None:return super().title()
        self.raw_title=string;return super().title(self.ui.text(string))
    def retranslate(self):super().title(self.ui.text(self.raw_title))

class LocalCanvas(tk.Canvas):
    def __init__(self,ui,*args,**kwargs):self.ui=ui;self.labels={};super().__init__(*args,**kwargs);ui.register(self)
    def create_text(self,*args,**kwargs):
        raw=kwargs.get('text','');kwargs['text']=self.ui.text(raw)
        item=super().create_text(*args,**kwargs);self.labels[item]=raw;return item
    def delete(self,*args):
        if 'all' in args:self.labels.clear()
        return super().delete(*args)
    def retranslate(self):
        for item,raw in self.labels.items():self.itemconfigure(item,text=self.ui.text(raw))
