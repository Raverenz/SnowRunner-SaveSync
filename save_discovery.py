"""Locate local PC saves in known Steam/Documents roots without scanning whole disks."""
from dataclasses import dataclass
from pathlib import Path
import json,os,re,time

SAVE_NAME=re.compile(r'CompleteSave([1-3]?)\.(cfg|dat)',re.I)


@dataclass(frozen=True)
class SearchRoot:
    path: Path
    platform: str
    layout: str


@dataclass(frozen=True)
class Candidate:
    path: Path
    platform: str
    account: str
    slot: int
    modified: float
    money: int
    experience: object=None


def _registry_value(hive,path,name,view=0):
    try:
        import winreg
        with winreg.OpenKey(hive,path,0,winreg.KEY_READ|view) as key:
            return winreg.QueryValueEx(key,name)[0]
    except (ImportError,OSError):return None


def windows_search_roots(environ=None,home=None):
    env=os.environ if environ is None else environ
    home=Path.home() if home is None else Path(home)
    steam=[];documents=[]
    try:
        import winreg
        steam.append(_registry_value(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'))
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            steam.append(_registry_value(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Valve\Steam','InstallPath',view))
        for key in ('User Shell Folders','Shell Folders'):
            documents.append(_registry_value(winreg.HKEY_CURRENT_USER,'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\'+key,'Personal'))
    except ImportError:pass
    for key in ('ProgramFiles(x86)','ProgramFiles'):
        if env.get(key):steam.append(str(Path(env[key])/'Steam'))
    if os.name=='nt':steam.extend([r'C:\Program Files (x86)\Steam',r'C:\Program Files\Steam'])
    documents.append(str(home/'Documents'))
    for key in ('OneDrive','OneDriveConsumer','OneDriveCommercial'):
        if env.get(key):documents.append(str(Path(env[key])/'Documents'))
    documents.extend([str(home/'OneDrive'/'Documents'),str(home/'OneDrive'/'Dokumenty')])
    results=[];seen=set()
    for paths,platform,layout,suffix in [(steam,'Steam','steam',('userdata',)),(documents,'Dokumenty / Epic','storage',('My Games','SnowRunner','base','storage'))]:
        for raw in paths:
            if not isinstance(raw,str) or not raw.strip():continue
            path=Path(os.path.expandvars(raw)).joinpath(*suffix)
            identity=os.path.normcase(os.path.abspath(path))
            if identity not in seen:
                seen.add(identity);results.append(SearchRoot(path,platform,layout))
    return results


def _children(path):
    try:return sorted(path.iterdir(),key=lambda child:child.name.casefold())
    except OSError:return []


def _profile(path):
    doc=json.loads(path.read_bytes().decode('utf-8-sig').rstrip('\x00\r\n '))
    if not isinstance(doc,dict):raise ValueError('Nieprawidłowy zapis.')
    blocks=[value['SslValue'] for key,value in doc.items() if key.startswith('CompleteSave') and isinstance(value,dict) and isinstance(value.get('SslValue'),dict)]
    if len(blocks)!=1:raise ValueError('Nieobsługiwany zapis.')
    return blocks[0].get('persistentProfileData',{})


def discover_saves(search_roots=None,validator=None,cancel=None):
    results=[];seen=set()
    roots=windows_search_roots() if search_roots is None else search_roots
    for root in roots:
        if cancel is not None and cancel.is_set():break
        folders=[]
        for account in _children(Path(root.path)):
            try:
                if not account.is_dir():continue
            except OSError:continue
            if root.layout=='steam':
                if not account.name.isdigit():continue
                folders.append((account/'1465360'/'remote',account.name))
            else:folders.append((account,account.name))
        if root.layout=='storage':folders.append((Path(root.path),Path(root.path).name))
        for folder,account in folders:
            for path in _children(folder):
                if cancel is not None and cancel.is_set():return sorted(results,key=lambda item:(-item.modified,str(item.path)))
                match=SAVE_NAME.fullmatch(path.name)
                if not match:continue
                try:
                    stat=path.stat()
                    if not path.is_file() or not 0<stat.st_size<=32*1024*1024:continue
                    identity=os.path.normcase(str(path.resolve()))
                    if identity in seen:continue
                    profile=validator(path) if validator else _profile(path)
                    if not isinstance(profile,dict):continue
                    balance=profile.get('money')
                    if type(balance) is not int or balance<0:continue
                    xp=profile.get('experience')
                    if type(xp) is not int or xp<0:xp=None
                    seen.add(identity)
                    results.append(Candidate(path.resolve(),root.platform,account,int(match[1] or '0')+1,stat.st_mtime,balance,xp))
                except (OSError,ValueError,UnicodeError,TypeError,RecursionError):continue
    return sorted(results,key=lambda item:(-item.modified,str(item.path)))


def modified_ago(timestamp,now=None):
    seconds=max(0,int((time.time() if now is None else now)-timestamp))
    if seconds<60:return 'przed chwilą'
    if seconds<3600:return f'{seconds//60} min temu'
    if seconds<86400:return f'{seconds//3600} godz. temu'
    return f'{seconds//86400} dni temu'
