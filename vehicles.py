"""Read-only fleet and map-record browser. Never infers ownership from map presence."""
from pathlib import Path
import re,struct,uuid,zlib
from catalog import LEVELS
from prices import PRICES
from sts_equipment import decode_equipment, DecodeError


def normalize_level(level):
    return str(level).lower().removesuffix('_new').removesuffix('_crop')


MAPS={normalize_level(key):value for key,value in LEVELS.items()}


def location(level,kind):
    info=MAPS.get(normalize_level(level))
    return f'{info["region"]} — {info["map"]} — {kind}' if info else f'{level or "Nieznana mapa"} — {kind}'


def companion_files(save_path):
    if not save_path:return []
    path=Path(save_path)
    match=re.fullmatch(r'CompleteSave([0-3]?)\.(cfg|dat)',path.name,re.I)
    if not match:return []
    prefix=(match[1]+'_') if match[1] else ''
    pattern=re.compile(re.escape(prefix)+r'sts_level_[\w-]+\.(cfg|dat)',re.I)
    return sorted(p for p in path.parent.iterdir() if p.is_file() and pattern.fullmatch(p.name))


def read_sts(path,prices=PRICES):
    """Read GUID records and strictly validate their equipment segments."""
    path=Path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Plik STS przekracza limit 32 MB.')
    raw=path.read_bytes()
    if len(raw)<6:raise ValueError('Niepełny plik STS.')
    expected=struct.unpack_from('<I',raw)[0]
    if expected>64*1024*1024:raise ValueError('Rozpakowany STS przekracza limit 64 MB.')
    decoder=zlib.decompressobj()
    payload=decoder.decompress(raw[4:],64*1024*1024+1)
    if not decoder.eof or len(payload)!=expected:raise ValueError('Nieobsługiwany lub uszkodzony STS.')
    match=re.fullmatch(r'(?:[0-3]_)?sts_(level_[\w-]+)\.(?:cfg|dat)',path.name,re.I)
    if not match:raise ValueError('Nie rozpoznano mapy w nazwie STS.')
    level=match[1]
    headers=[]
    # A type string, empty object name, and an RFC4122-shaped GUID; all length-prefixed.
    regex=rb'([a-z][a-z0-9_]{2,120})\x00\x01\x00\x00\x27\x00(\{[a-fA-F0-9-]{36}\})\x00'
    for hit in re.finditer(regex,payload,re.I):
        start=hit.start()
        if start<2 or struct.unpack_from('<H',payload,start-2)[0]!=len(hit[1])+1:continue
        try:identity=uuid.UUID(hit[2].decode('ascii').strip('{}'))
        except ValueError:continue
        if identity.int==0:continue
        headers.append((start,hit.end(),hit[1].decode('ascii').lower(),str(identity)))
    result=[];seen=set()
    for index,(start,end,kind,gid) in enumerate(headers):
        if gid in seen:continue
        seen.add(gid)
        model=prices['trucks'].get(kind)
        if model and model.get('is_trailer'):continue
        if model is None and any(s in kind for s in ('trailer','cargo','addon')):continue
        stop=headers[index+1][0]-2 if index+1<len(headers) else min(len(payload),end+128000)
        found=[];seen_parts=set()
        for hit in re.finditer(rb'([a-z][a-z0-9_]{2,150})\x00',payload[end:stop],re.I):
            offset=end+hit.start();key=hit[1].decode('ascii').lower()
            if offset<2 or struct.unpack_from('<H',payload,offset-2)[0]!=len(hit[1])+1:continue
            part=prices['parts'].get(key)
            if part and key not in seen_parts:
                found.append({'kind':part.get('kind','Dodatek'),'name':part.get('name',key),'id':key,'source':'Wykryty identyfikator w STS (lista niepełna)'})
                seen_parts.add(key)
        descriptor=None;decode_error=''
        try:
            descriptor=decode_equipment(payload,end,stop)
            descriptor.update(type=kind,globalId='{'+gid+'}')
            found=installed_parts(descriptor,prices)
            for part in found:part['source']='Zdekodowane wyposażenie STS'
        except (DecodeError,struct.error) as error:decode_error=str(error)
        result.append({'type':kind,'name':(model or {}).get('name',kind),'guid':gid,'level':level,
                       'location':location(level,'Na mapie'),'parts':found,'file':str(path),
                       'descriptor':descriptor,'decode_error':decode_error})
    return result


def installed_parts(truck,prices=PRICES):
    model=prices['trucks'].get(str(truck.get('type','')).lower(),{})
    defaults=model.get('defaults',{})
    result=[]
    for field,title in [('engine','Silnik'),('gearbox','Skrzynia biegów'),('suspension','Zawieszenie'),('winchUpgrade','Wyciągarka')]:
        key=truck.get(field)
        if isinstance(key,dict):key=key.get('name')
        inferred=not bool(key)
        key=key or defaults.get(field)
        if key:
            item=prices['parts'].get(str(key).lower(),{})
            result.append({'kind':title,'name':item.get('name',key),'id':key,'source':'Domyślne wg katalogu' if inferred else 'Zapis pojazdu'})
        else:result.append({'kind':title,'name':'Brak danych','id':'','source':'Nie zapisano części i brak wartości domyślnej'})
    group=truck.get('wheelsType') or model.get('wheels',{}).get('type')
    tire=truck.get('tires') or model.get('wheels',{}).get('tire')
    if group and tire:
        key=group+'|'+tire;item=prices['tires'].get(key.lower(),{})
        result.append({'kind':'Komplet opon','name':item.get('name',tire),'id':key,'source':'Zapis pojazdu' if truck.get('tires') else 'Domyślne wg katalogu'})
    addons=truck.get('addons',[])
    keys=[a.get('name') for a in addons if isinstance(a,dict) and a.get('name')] if isinstance(addons,list) else []
    actual=set(keys)
    if truck.get('needToInstallDefaultAddons'):keys.extend(k for k in model.get('default_addons',[]) if k not in keys)
    for key in keys:
        item=prices['parts'].get(key.lower(),{})
        result.append({'kind':item.get('kind','Dodatek'),'name':item.get('name',key),'id':key,'source':'Zapis pojazdu' if key in actual else 'Domyślne wg katalogu'})
    return result


def fleet(save,save_path=None,sts_paths=None,prices=PRICES,confirmed_guids=None):
    profile=save.get('persistentProfileData',{})
    trucks=[];notes=[];seen=set();described={};map_descriptors=[]
    confirmed_guids=set(confirmed_guids or [])
    def add(desc,where):
        if not isinstance(desc,dict) or not isinstance(desc.get('type'),str):return
        kind=desc['type'].lower();gid=str(desc.get('globalId') or '').lower()
        if gid and gid in seen:return
        if gid:seen.add(gid)
        model=prices['trucks'].get(kind,{})
        if model.get('is_trailer'):return
        described[kind]=described.get(kind,0)+1
        trucks.append({'type':kind,'name':model.get('name',desc['type']),'guid':gid,'location':where,'qty':1,
                       'parts':installed_parts(desc,prices),'candidates':[],'state':'Potwierdzony opis pojazdu'})
    warehouse=profile.get('trucksInWarehouse',[])
    if not isinstance(warehouse,list):
        warehouse=[];notes.append('Nieobsługiwany magazyn ciężarówek.')
    for truck in warehouse:
        add(truck,'Magazyn ciężarówek (globalny, bez przypisania do mapy)')
    garages=save.get('garagesData',{})
    if not isinstance(garages,dict):
        garages={};notes.append('Nieobsługiwany format garaży.')
    for level,garage in garages.items():
        if not isinstance(garage,dict):continue
        slots=garage.get('slotsDatas',{})
        if not isinstance(slots,dict):continue
        for slot in slots.values():
            if isinstance(slot,dict):add(slot.get('truckDesc'),location(level,'Garaż'))
    candidates=[];records_by_guid={}
    files=companion_files(save_path) if sts_paths is None else list(sts_paths)
    if len(files)>150:files=files[:150];notes.append('Ograniczono odczyt do 150 plików STS.')
    for path in files:
        try:
            for record in read_sts(path,prices):
                if '{'+record['guid']+'}' in seen or record['guid'] in seen:continue
                records_by_guid.setdefault(record['guid'],[]).append(record)
        except (OSError,ValueError,zlib.error,struct.error) as exc:notes.append(Path(path).name+': '+str(exc))
    for gid,records in records_by_guid.items():
        active=[record for record in records if record['descriptor'] is not None and record['descriptor']['isUnlocked']]
        record=(active or records)[0]
        if len(active)>1 and any((r['level'],r['descriptor'])!=(record['level'],record['descriptor']) for r in active[1:]):
            record=dict(record);record['descriptor']=None
            record['decode_error']='Sprzeczne aktywne rekordy tego samego GUID w kilku plikach STS.'
            notes.append('Nie wyceniono sprzecznych kopii pojazdu '+gid+': '+', '.join(r['file'] for r in active))
        candidates.append(record)
    owned=profile.get('ownedTrucks')
    if isinstance(owned,dict):
        for raw_kind,count in owned.items():
            if type(count) is not int or count<0:notes.append('Nieprawidłowy licznik pojazdów: '+raw_kind);continue
            kind=raw_kind.lower();missing=count-described.get(kind,0)
            if missing<0:notes.append('Więcej opisów niż w liczniku ownedTrucks: '+kind)
            if missing<=0:continue
            matches=[r for r in candidates if r['type']==kind]
            eligible=[r for r in matches if r['descriptor'] is not None and r['descriptor']['isUnlocked']]
            undecoded=any(r['descriptor'] is None for r in matches)
            if len(eligible)==missing and not undecoded:
                selected=eligible;match_reason='STS: odblokowany, liczba zgodna z ownedTrucks'
            else:
                selected=[r for r in eligible if r['guid'] in confirmed_guids]
                match_reason='STS: własność potwierdzona ręcznie'
                if len(selected)>missing:
                    selected=[];notes.append('Potwierdzono zbyt wiele pojazdów STS tego samego modelu: '+kind)
            for record in selected:
                add(record['descriptor'],record['location'])
                trucks[-1]['state']=match_reason
                map_descriptors.append((record['descriptor'],record['location']))
            missing-=len(selected)
            if not missing:continue
            matches=[r for r in matches if r not in selected]
            places=list(dict.fromkeys(record['location'] for record in matches))
            place='Możliwe: '+' / '.join(places) if places else 'Brak opisu w CompleteSave — lokalizacja niepotwierdzona'
            trucks.append({'type':kind,'name':prices['trucks'].get(kind,{}).get('name',raw_kind),'guid':'','qty':missing,
                'location':place,
                'parts':[],'candidates':matches,'state':f'{len(matches)} pasujących rekordów STS; własność niepotwierdzona' if matches else 'Brak pasujących rekordów STS'})
    else:notes.append('Brak ownedTrucks — lista opiera się na opisach w magazynie i garażach.')
    notes.append('Magazyn ciężarówek jest globalny; retainedMapId nie jest jego obecną lokalizacją.')
    if map_descriptors:
        notes.append(f'Wyposażenie {len(map_descriptors)} pojazdów mapowych zdekodowano i włączono do wyceny. Podwozia nie są liczone ponownie.')
    if any(t['candidates'] for t in trucks):
        notes.append('STS zawiera też pojazdy misji i gości. Automatyczne dopasowanie wymaga odblokowania pojazdu, pełnego segmentu wyposażenia i zgodnej liczby egzemplarzy w ownedTrucks. Przy niejednoznaczności wybierz właściwy rekord i potwierdź jego własność do wyceny.')
    if any(not t['parts'] for t in trucks):
        notes.append('Brakujące lub nieobsługiwane dane pozostają oznaczone. Identyfikatory znalezione w niepełnym rekordzie STS nie są doliczane do wyceny.')
    return {'trucks':sorted(trucks,key=lambda t:(t['name'].casefold(),t['location'])),'notes':notes,'files':len(files),
            'map_descriptors':map_descriptors,'file_paths':files}
