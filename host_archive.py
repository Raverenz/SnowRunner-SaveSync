"""Read-only host packages: flat ZIP input, bounded reads, isolated temporary files."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,re,stat,sys,tempfile,zipfile,zlib

MAIN=re.compile(r'CompleteSave([1-3]?)\.(cfg|dat)',re.I)
STS=re.compile(r'(?:(\d)_)?sts_level_[\w-]+\.(cfg|dat)',re.I)
MAX_ARCHIVE=512*1024*1024
MAX_TOTAL=256*1024*1024
MAX_FILE=32*1024*1024


class ArchiveError(ValueError):pass
class HostLoadCancelled(Exception):pass


def application_folder():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent


def newest_zip(folder):
    candidates=[]
    try:children=Path(folder).iterdir()
    except OSError:return None
    try:
        for path in children:
            try:
                if path.is_file() and path.suffix.lower()=='.zip':candidates.append((path.stat().st_mtime_ns,path.name.casefold(),path))
            except OSError:continue
    except OSError:return None
    return max(candidates,key=lambda entry:entry[:2])[2] if candidates else None


def fingerprint(path):
    path=Path(path)
    if path.stat().st_size>MAX_ARCHIVE:raise ArchiveError('Archiwum ZIP przekracza limit 512 MB.')
    digest=hashlib.sha256();count=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            count+=len(block)
            if count>MAX_ARCHIVE:raise ArchiveError('Archiwum ZIP przekracza limit 512 MB.')
            digest.update(block)
    return digest.hexdigest()


def checked_members(archive):
    infos=archive.infolist()
    if len(infos)>4096:raise ArchiveError('Archiwum zawiera zbyt wiele plików.')
    seen=set();total=0
    for info in infos:
        name=info.filename
        if info.is_dir() or '/' in name or '\\' in name or ':' in name or name in ('.','..'):
            raise ArchiveError('ZIP powinien zawierać pliki zapisu bezpośrednio, bez folderów.')
        if name.casefold() in seen:raise ArchiveError('ZIP zawiera powtórzoną nazwę pliku: '+name)
        seen.add(name.casefold())
        mode=info.external_attr>>16
        if stat.S_ISLNK(mode):raise ArchiveError('Archiwum zawiera dowiązanie zamiast zwykłego pliku.')
        if info.flag_bits&1:raise ArchiveError('Archiwa ZIP zabezpieczone hasłem nie są obsługiwane.')
        if info.file_size<0:raise ArchiveError('Nieprawidłowy rozmiar pliku w ZIP.')
        total+=info.file_size
        if total>MAX_TOTAL:raise ArchiveError('Rozpakowana zawartość ZIP przekracza limit 256 MB.')
    return infos


def read_member(archive,info):
    if info.file_size>MAX_FILE:raise ArchiveError('Plik w ZIP przekracza limit 32 MB: '+info.filename)
    with archive.open(info) as stream:
        data=stream.read(MAX_FILE+1)
        if len(data)>MAX_FILE or len(data)!=info.file_size:raise ArchiveError('Nieprawidłowy rozmiar pliku: '+info.filename)
    return data


@dataclass(frozen=True)
class ArchiveSave:
    name: str
    slot: int
    money: int
    experience: object
    rank: object
    trucks: object


@dataclass(frozen=True)
class Inspection:
    path: Path
    fingerprint: str
    saves: tuple


@dataclass
class HostBundle:
    inspection: Inspection
    member: ArchiveSave
    temporary: object
    save_path: Path

    def check_unchanged(self):
        if fingerprint(self.inspection.path)!=self.inspection.fingerprint:
            raise ArchiveError('ZIP hosta zmienił się od wczytania. Kliknij „Wczytaj zapisy” ponownie.')

    def close(self):self.temporary.cleanup()


def inspect_archive(path,parse_save):
    path=Path(path).resolve(strict=True);stamp=fingerprint(path);saves=[]
    try:
        with zipfile.ZipFile(path) as archive:
            infos=checked_members(archive)
            for info in infos:
                match=MAIN.fullmatch(info.filename)
                if not match:continue
                data=parse_save(read_member(archive,info));profile=data[1]['persistentProfileData']
                balance=profile.get('money')
                if type(balance) is not int or balance<0:raise ArchiveError('Nieprawidłowe saldo hosta: '+info.filename)
                xp=profile.get('experience');rank=profile.get('rank');owned=profile.get('ownedTrucks')
                count=sum(v for v in owned.values() if type(v) is int and v>0) if isinstance(owned,dict) else None
                saves.append(ArchiveSave(info.filename,int(match[1] or '0')+1,balance,xp if type(xp) is int and xp>=0 else None,rank if type(rank) is int and rank>0 else None,count))
    except (zipfile.BadZipFile,RuntimeError,NotImplementedError,zlib.error,EOFError) as error:raise ArchiveError('Nie można odczytać ZIP: '+str(error)) from error
    if not saves:raise ArchiveError('W archiwum nie znaleziono pliku CompleteSave*.cfg lub .dat.')
    if fingerprint(path)!=stamp:raise ArchiveError('ZIP zmienił się podczas odczytu. Spróbuj ponownie.')
    return Inspection(path,stamp,tuple(sorted(saves,key=lambda item:(item.slot,item.name.casefold()))))


def prepare_bundle(inspection,member):
    if member not in inspection.saves:raise ArchiveError('Nieprawidłowy wybór zapisu hosta.')
    if fingerprint(inspection.path)!=inspection.fingerprint:raise ArchiveError('ZIP zmienił się od wyświetlenia podsumowania.')
    temporary=tempfile.TemporaryDirectory(prefix='SnowRunner-Host-')
    try:
        with zipfile.ZipFile(inspection.path) as archive:
            for info in checked_members(archive):
                match=STS.fullmatch(info.filename)
                prefix=str(member.slot-1) if member.slot>1 else ''
                if info.filename!=member.name and not (match and (match[1] or '')==prefix):continue
                data=read_member(archive,info)
                with (Path(temporary.name)/info.filename).open('xb') as stream:stream.write(data)
        bundle=HostBundle(inspection,member,temporary,Path(temporary.name)/member.name)
        bundle.check_unchanged()
        return bundle
    except (zipfile.BadZipFile,RuntimeError,NotImplementedError,zlib.error,EOFError) as error:
        temporary.cleanup();raise ArchiveError('Nie można rozpakować ZIP: '+str(error)) from error
    except Exception:
        temporary.cleanup();raise
