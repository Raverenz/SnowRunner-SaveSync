"""Read-only nominal valuation of owned assets in CompleteSave and verified STS equipment."""
from collections import Counter
import re
from prices import PRICES


def money(value):
    return f'{value:,}'.replace(',',' ')+' $'


def assess(save,prices=None,map_trucks=None):
    prices=PRICES if prices is None else prices
    profile=save.get('persistentProfileData',{})
    rows=[]; warnings=[]
    def warn(text):
        if text not in warnings: warnings.append(text)
    def valid_count(value,where):
        if type(value) is not int or value<0:
            warn('Nieprawidłowa liczba sztuk: '+where);return 0
        return value
    def item(key,category='parts'):
        result=prices.get(category,{}).get(key.lower())
        if result is None and category=='parts':
            trailer=prices.get('trucks',{}).get(key.lower())
            if trailer and trailer.get('is_trailer'): result=trailer
        if result is None and category=='parts' and key.lower().startswith('wheels_'):
            for composite,entry in prices.get('tires',{}).items():
                prefix=composite.replace('|','_')+'_'
                if key.lower().startswith(prefix) and re.fullmatch(r'\d+(?:\.\d+)?',key[len(prefix):]): return entry
        return result
    def add(kind,key,qty,source,category='parts'):
        if not qty or not key: return 0
        entry=item(key,category)
        if entry is None:
            warn(f'Brak ceny: {key} ({source}, {qty} szt.)')
            rows.append((kind,key,qty,None,None,source));return 0
        total=entry['price']*qty
        rows.append((kind,entry.get('name',key)+' ['+key+']',qty,entry['price'],total,source))
        return total
    cash=profile.get('money')
    if type(cash) is not int or cash<0:
        warn('Brak poprawnego salda.');cash=0
    xp=profile.get('experience');rank=profile.get('rank')
    if type(xp) is not int or xp<0: xp=None
    if type(rank) is not int or rank<1: rank=None
    descriptors=[];seen=set()
    def collect(truck,where):
        if not isinstance(truck,dict) or not truck.get('type'): return
        gid=str(truck.get('globalId') or '').strip('{}').lower()
        if gid:
            if gid in seen: return
            seen.add(gid)
        descriptors.append((truck,where))
    warehouse=profile.get('trucksInWarehouse',[])
    if isinstance(warehouse,list):
        for truck in warehouse: collect(truck,'Magazyn ciężarówek')
    else: warn('Nieobsługiwany magazyn ciężarówek.')
    garages=save.get('garagesData',{})
    if isinstance(garages,dict):
        for level,garage in garages.items():
            if not isinstance(garage,dict): warn('Nieobsługiwany garaż: '+level);continue
            slots=garage.get('slotsDatas',{})
            if not isinstance(slots,dict): warn('Nieobsługiwane miejsca w garażu: '+level);continue
            for slot in slots.values():
                if isinstance(slot,dict): collect(slot.get('truckDesc'),'Garaż: '+level)
    else: warn('Nieobsługiwany format garaży.')
    for truck,where in map_trucks or []:
        collect(truck,where+' (STS)')
    by_type={}
    for truck,where in descriptors: by_type.setdefault(truck['type'].lower(),[]).append((truck,where))
    owned=profile.get('ownedTrucks')
    if not isinstance(owned,dict):
        owned={key:len(items) for key,items in by_type.items()}
        warn('Brak licznika ownedTrucks — liczba pojazdów oparta tylko na magazynie i garażach.')
    counts={key.lower():valid_count(qty,key) for key,qty in owned.items()}
    chassis=installed=spares=0;total_trucks=0;described=0
    for kind,qty in counts.items():
        if not qty: continue
        total_trucks+=qty
        chassis+=add('Podwozie',kind,qty,'Wszystkie posiadane ciężarówki','trucks')
        known=by_type.get(kind,[])
        if len(known)>qty: warn(f'Niezgodna liczba opisów i ownedTrucks: {kind}.')
        for truck,where in known[:qty]:
            described+=1
            model=item(kind,'trucks') or {}
            defaults=model.get('defaults',{})
            source=where+' / '+model.get('name',kind)
            for field in ('engine','gearbox','suspension','winchUpgrade'):
                value=truck.get(field)
                if isinstance(value,dict): value=value.get('name','')
                value=value or defaults.get(field)
                if value: installed+=add('Zamontowana część',value,1,source)
                elif field in defaults: warn(f'Brak opisu części {field}: {kind}.')
            group=truck.get('wheelsType') or model.get('wheels',{}).get('type')
            tire=truck.get('tires') or model.get('wheels',{}).get('tire')
            if group and tire: installed+=add('Zamontowane opony',group+'|'+tire,1,source,'tires')
            addons=truck.get('addons',[])
            if not isinstance(addons,list): warn('Nieobsługiwane wyposażenie: '+kind);addons=[]
            addon_ids=[a.get('name') for a in addons if isinstance(a,dict) and a.get('name')]
            if truck.get('needToInstallDefaultAddons'):
                addon_ids.extend(k for k in model.get('default_addons',[]) if k not in addon_ids)
            for key in addon_ids: installed+=add('Zamontowany dodatek',key,1,source)
        missing=qty-min(len(known),qty)
        if missing:
            warn(f'{kind}: {missing} pojazd(y) bez jednoznacznego opisu w magazynie, garażu lub STS. Podwozia wliczone; wyposażenie na mapie pominięte. Wczytaj właściwe STS i sprawdź potwierdzenia pojazdów albo przenieś je do garażu lub magazynu.')
    for kind in by_type:
        if not counts.get(kind): warn('Opis pojazdu bez potwierdzonej własności (pominięty): '+kind)
    inventory=profile.get('addons',{})
    if isinstance(inventory,dict):
        for key,qty in inventory.items(): spares+=add('Część / dodatek w zapasie',key,valid_count(qty,key),'Magazyn części i dodatków')
    else: warn('Nieobsługiwany magazyn części.')
    if profile.get('damagableAddons'):
        warn('Oddzielne uszkadzalne dodatki nie są wycenione (damagableAddons).')
    for field in ('refundGarageTruckDescs','refundTruckDescs'):
        if profile.get(field): warn('Zapis zawiera oczekujące zwroty pojazdów ('+field+'); nie są doliczane bez potwierdzenia własności.')
    return {'map_count':sum(1 for _,where in descriptors if where.endswith('(STS)')),'cash':cash,'chassis':chassis,'installed':installed,'spares':spares,
            'total':cash+chassis+installed+spares,'experience':xp,'rank':rank,
            'truck_count':total_trucks,'described_count':described,'rows':rows,'warnings':warnings,'complete':not warnings}


def summary(result):
    prefix='' if result['complete'] else 'co najmniej '
    xp=f'{result["experience"]:,}'.replace(',',' ') if result['experience'] is not None else 'brak danych'
    rank=str(result['rank']) if result['rank'] is not None else 'brak danych'
    return f'Wartość firmy: {prefix}{money(result["total"])}\nDoświadczenie: {xp} XP  •  Ranga: {rank}'
