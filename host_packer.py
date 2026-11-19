"""Prepare flat, verified host packages without modifying source saves."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,os,re,tempfile,zipfile
from catalog import LEVELS
from host_archive import MAIN,STS,MAX_FILE,MAX_TOTAL


class PackError(ValueError):pass
class PackCancelled(Exception):pass


@dataclass(frozen=True)
class PackedFile:
    path: Path
    name: str
    description: str
    size: int
    modified_ns: int
    digest: str


@dataclass(frozen=True)
class PackagePlan:
    source: Path
    slot: int
    account: str
    money: int
    experience: object
    rank: object
    files: tuple

    @property
    def total_size(self):return sum(file.size for file in self.files)


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():raise PackCancelled('Anulowano pakowanie.')


def parse_main(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise PackError('Zapis zawiera powtórzone klucze JSON.')
            result[key]=value
        return result
    try:doc=json.loads(raw.decode('utf-8-sig').rstrip('\x00\r\n '),object_pairs_hook=pairs)
    except (UnicodeError,ValueError,RecursionError) as error:raise PackError('Nie można odczytać głównego zapisu: '+str(error)) from error
    if not isinstance(doc,dict):raise PackError('Nieprawidłowy format głównego zapisu.')
    blocks=[v['SslValue'] for k,v in doc.items() if k.startswith('CompleteSave') and isinstance(v,dict) and isinstance(v.get('SslValue'),dict)]
    if len(blocks)!=1 or not isinstance(blocks[0].get('persistentProfileData'),dict):raise PackError('To nie jest obsługiwany plik CompleteSave.')
    profile=blocks[0]['persistentProfileData']
    if type(profile.get('money')) is not int or profile['money']<0:raise PackError('Nieprawidłowe saldo w zapisie.')
    return profile


def read_stable(path,cancel=None):
    check_cancel(cancel);path=Path(path);before=path.stat()
    if not path.is_file() or not 0<before.st_size<=MAX_FILE:raise PackError('Pusty lub zbyt duży plik (limit 32 MB): '+path.name)
    chunks=[];size=0
    with path.open('rb') as stream:
        while True:
            check_cancel(cancel);chunk=stream.read(1024*1024)
            if not chunk:break
            size+=len(chunk)
            if size>MAX_FILE:raise PackError('Plik przekracza limit 32 MB: '+path.name)
            chunks.append(chunk)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or size!=before.st_size:
        raise PackError('Plik zmienił się podczas odczytu: '+path.name+'. Zamknij grę i odśwież listę plików.')
    return b''.join(chunks),after


def profile_for_discovery(path):return parse_main(read_stable(path)[0])


def matching_sts(source):
    source=Path(source);match=MAIN.fullmatch(source.name)
    if not match:raise PackError('Wybierz oryginalny plik CompleteSave.cfg/.dat lub CompleteSave1–3.cfg/.dat.')
    prefix=match[1]
    return sorted((p for p in source.parent.iterdir() if p.is_file() and (m:=STS.fullmatch(p.name)) and (m[1] or '')==prefix),key=lambda p:p.name.casefold())


def file_description(name,slot):
    if MAIN.fullmatch(name):return f'Zapis główny, slot {slot}: profil, gotówka, XP, odblokowania, magazyn i garaże.'
    match=re.fullmatch(r'(?:[1-3]_)?sts_(level_[\w-]+)\.(?:cfg|dat)',name,re.I)
    if not match:return 'Plik stanu mapy.'
    key=match[1].lower().removesuffix('_new').removesuffix('_crop')
    maps={k.lower().removesuffix('_new').removesuffix('_crop'):v for k,v in LEVELS.items()}
    info=maps.get(key)
    if info:return f'Stan mapy i pojazdy: {info["map"]} — {info["region"]}.'
    return f'Stan mapy i pojazdy: {match[1]} (nazwa mapy poza katalogiem).'


def build_plan(source,cancel=None):
    source=Path(source).resolve(strict=True);match=MAIN.fullmatch(source.name)
    if not match:raise PackError('Wybierz oryginalny plik CompleteSave.cfg/.dat lub CompleteSave1–3.cfg/.dat.')
    slot=int(match[1] or '0')+1
    raw,metadata=read_stable(source,cancel);profile=parse_main(raw)
    paths=[source]+matching_sts(source);files=[];seen=set();total=0
    if len(paths)>4096:raise PackError('Znaleziono zbyt wiele plików.')
    for path in paths:
        check_cancel(cancel)
        data,meta=(raw,metadata) if path==source else read_stable(path,cancel)
        if path.name.casefold() in seen:raise PackError('Powtórzona nazwa pliku: '+path.name)
        seen.add(path.name.casefold());total+=len(data)
        if total>MAX_TOTAL:raise PackError('Wybrane pliki przekraczają limit paczki 256 MB.')
        files.append(PackedFile(path,path.name,file_description(path.name,slot),len(data),meta.st_mtime_ns,hashlib.sha256(data).hexdigest()))
    account=source.parent.parent.parent.name if source.parent.name.lower()=='remote' and source.parent.parent.name=='1465360' else source.parent.name
    xp=profile.get('experience');rank=profile.get('rank')
    return PackagePlan(source,slot,account,profile['money'],xp if type(xp) is int and xp>=0 else None,rank if type(rank) is int and rank>0 else None,tuple(files))


def suggested_filename(plan,folder):
    base=f'SnowRunner_host_slot-{plan.slot}'
    for number in range(1,10000):
        name=base+('' if number==1 else f'_{number}')+'.zip'
        if not (Path(folder)/name).exists():return name
    raise PackError('Za dużo paczek o tej samej nazwie. Wybierz inną nazwę ZIP.')


def verify_file(file,cancel=None):
    data,meta=read_stable(file.path,cancel)
    if meta.st_mtime_ns!=file.modified_ns or len(data)!=file.size or hashlib.sha256(data).hexdigest()!=file.digest:
        raise PackError('Plik zmienił się od podglądu: '+file.name+'. Zamknij grę i kliknij „Odśwież pliki”.')
    return data


def create_package(plan,destination,overwrite=False,cancel=None,progress=None):
    destination=Path(destination).resolve()
    if destination.suffix.lower()!='.zip':raise PackError('Paczka musi mieć rozszerzenie .zip.')
    if destination.exists() and not overwrite:raise FileExistsError('Plik ZIP już istnieje. Wybierz inną nazwę.')
    for file in plan.files:
        if destination==file.path.resolve() or (destination.exists() and os.path.samefile(destination,file.path)):
            raise PackError('Nie można zastąpić pliku źródłowego paczką ZIP.')
    expected={file.name for file in plan.files}
    def verify_set():
        current={plan.source.name}|{p.name for p in matching_sts(plan.source)}
        if current!=expected:raise PackError('Zmieniła się lista plików STS. Zamknij grę i kliknij „Odśwież pliki”.')
    verify_set();check_cancel(cancel)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.snowrunner-pack-',suffix='.tmp',dir=destination.parent,delete=False) as stream:temporary=Path(stream.name)
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for index,file in enumerate(plan.files,1):
                check_cancel(cancel);data=verify_file(file,cancel)
                archive.writestr(file.name,data)
                check_cancel(cancel)
                if progress:progress(index,len(plan.files),file.name)
        verify_set()
        for file in plan.files:verify_file(file,cancel)
        with zipfile.ZipFile(temporary) as archive:
            if set(archive.namelist())!=expected or archive.testzip() is not None:raise PackError('Nie udało się zweryfikować gotowej paczki ZIP.')
        check_cancel(cancel)
        if overwrite:os.replace(temporary,destination)
        elif os.name=='nt':os.rename(temporary,destination)
        else:os.link(temporary,destination);temporary.unlink()
        temporary=None
        return destination
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def package_report(plan,destination=None):
    title='Spakowane pliki' if destination else 'Pliki do spakowania'
    lines=[title+f' — profil {plan.account}, slot {plan.slot}']
    if destination:lines.append('ZIP: '+str(destination))
    lines.append('')
    lines.extend(file.name+' — '+file.description for file in plan.files)
    return '\n'.join(lines)
