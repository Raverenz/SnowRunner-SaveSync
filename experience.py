"""SnowRunner cumulative XP thresholds (MapRunner rank-xp chart)."""
from bisect import bisect_right
import copy

THRESHOLDS = (0,700,1700,2900,4100,5400,6900,8500,10100,11800,13700,15700,17800,20100,22500,25000,27500,30100,32700,35500,38300,41300,44300,47500,50700,54100,57500,61100,64900,69000)
MODES = ('Bez zmian','Synchronizuj z hostem','Dodaj XP','Ustaw XP','Ustaw poziom')
MAX_XP = 2147483647

def valid_xp(value):
    return type(value) is int and 0 <= value <= MAX_XP

def rank_for_xp(xp):
    if not valid_xp(xp): raise ValueError('XP musi być liczbą całkowitą od 0 do 2147483647.')
    return bisect_right(THRESHOLDS,xp)

def project_experience(host,guest,mode='Bez zmian',value=0):
    if mode not in MODES: raise ValueError('Nieznany tryb zmiany XP.')
    xp=guest.get('experience');rank=guest.get('rank')
    if mode=='Bez zmian':return xp,rank
    if not valid_xp(xp):raise ValueError('Zapis gracza nie zawiera obsługiwanej wartości XP.')
    if mode=='Synchronizuj z hostem':
        if host is None or not valid_xp(host.get('experience')):raise ValueError('Wczytaj zapis hosta z prawidłową wartością XP.')
        xp=max(xp,host['experience'])
    else:
        if type(value) is not int:raise ValueError('Wpisz całkowitą liczbę XP lub poziom.')
        if mode=='Ustaw poziom':
            if not 1<=value<=30:raise ValueError('Poziom musi mieścić się w zakresie 1–30.')
            xp=THRESHOLDS[value-1]
        elif mode=='Dodaj XP':
            if value<0:raise ValueError('Dodawane XP nie może być ujemne.')
            xp+=value
        else:xp=value
    return xp,rank_for_xp(xp)

def apply_experience(host,guest,mode='Bez zmian',value=0):
    out=copy.deepcopy(guest);profile=out['persistentProfileData']
    xp,rank=project_experience(host['persistentProfileData'] if host else None,profile,mode,value)
    changes=[]
    if mode!='Bez zmian':
        if (profile.get('experience'),profile.get('rank'))!=(xp,rank):
            changes.append(f"Doświadczenie: {profile.get('experience')} → {xp} XP; poziom: {profile.get('rank')} → {rank}.")
            profile.update(experience=xp,rank=rank)
    return out,changes
