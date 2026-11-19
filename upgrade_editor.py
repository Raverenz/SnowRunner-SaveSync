"""Manual component unlocks. Does not modify installed parts or inventory."""
import copy
from catalog import UPGRADES
from unlock_ids import UNLOCK_IDS


def normal(level):
    return level.lower().removesuffix('_new')


COMPONENT_POINTS = {}
for (level,key),item in UPGRADES.items():
    component = UNLOCK_IDS.get(key)
    if component:
        COMPONENT_POINTS.setdefault(component,[]).append((level,key))


def is_unlocked(save,component):
    profile = (save or {}).get('persistentProfileData',{})
    items = profile.get('unlockedItemNames',{})
    return isinstance(items,dict) and component in items


def apply_manual(save,overrides):
    out = copy.deepcopy(save)
    if not overrides: return out,[]
    items = out['persistentProfileData'].get('unlockedItemNames')
    maps = out.get('upgradesGiverData')
    if not isinstance(items,dict) or not isinstance(maps,dict):
        raise ValueError('Nieobsługiwane dane odblokowań gracza.')
    changes=[]
    touched=set()
    for component,enabled in sorted(overrides.items()):
        if component not in COMPONENT_POINTS or type(enabled) is not bool:
            raise ValueError('Nieobsługiwane ręczne odblokowanie: '+str(component))
        changed = False
        if enabled:
            if component not in items:
                items[component]=False
                changed=True
        elif component in items:
            del items[component]
            changed=True
        for canonical,key in COMPONENT_POINTS[component]:
            levels=[level for level in maps if normal(level)==normal(canonical)]
            if not levels and enabled:
                levels=[canonical]
                maps[canonical]={}
            for level in levels:
                points=maps[level]
                if not isinstance(points,dict): raise ValueError('Nieobsługiwany format punktów ulepszeń.')
                keys=[k for k in points if k.upper()==key.upper()]
                if not keys and enabled: keys=[key]
                for actual in keys:
                    old=points.get(actual,0)
                    if type(old) is not int or old not in (0,1,2): raise ValueError('Nieobsługiwany status ulepszenia.')
                    new=2 if enabled else 0
                    if old!=new:
                        points[actual]=new; touched.add(level); changed=True
        if changed:
            level,key=COMPONENT_POINTS[component][0]
            item=UPGRADES[(level,key)]
            action='Odblokuj' if enabled else 'Usuń odblokowanie'
            changes.append(f'{action}: {item["name"]} — {", ".join(item["trucks"])} [{component}]')
    for owner in [out,out['persistentProfileData']]:
        counters=owner.get('discoveredUpgrades')
        if counters is None: continue
        if not isinstance(counters,dict): raise ValueError('Nieobsługiwany licznik ulepszeń.')
        for level in touched:
            for counter_level,counter in counters.items():
                if normal(counter_level)!=normal(level): continue
                if not isinstance(counter,dict): raise ValueError('Nieobsługiwany licznik mapy.')
                counter['current']=sum(type(v) is int and v==2 for v in maps[level].values())
    return out,changes
