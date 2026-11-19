"""Strict read-only decoding of the equipment segment in GUID-style STS records."""
import math,re,struct


class DecodeError(ValueError):pass


class Reader:
    def __init__(self,data,position=0,end=None):
        self.data=data;self.pos=position;self.end=len(data) if end is None else end
    def take(self,size):
        if size<0 or self.pos+size>self.end:raise DecodeError('Niepełny segment wyposażenia STS.')
        out=self.data[self.pos:self.pos+size];self.pos+=size;return out
    def integer(self):return struct.unpack('<I',self.take(4))[0]
    def floating(self):
        value=struct.unpack('<f',self.take(4))[0]
        if not math.isfinite(value):raise DecodeError('Nieprawidłowa liczba w wyposażeniu STS.')
        return value
    def boolean(self):
        value=self.take(1)[0]
        if value not in (0,1):raise DecodeError('Nieprawidłowy znacznik STS.')
        return bool(value)
    def string(self):
        size=struct.unpack('<H',self.take(2))[0]
        if not 1<=size<=256:raise DecodeError('Nieobsługiwany ciąg znaków STS.')
        raw=self.take(size)
        if raw[-1]!=0 or any(c<32 or c>126 for c in raw[:-1]):raise DecodeError('Nieobsługiwany ciąg znaków STS.')
        return raw[:-1].decode('ascii')


def _core(data,offset,end):
    r=Reader(data,offset,end)
    engine,gearbox,winch,wheels,rims,tires=[r.string() for _ in range(6)]
    scale=r.floating();suspension=r.string()
    # Match serialized slot roles, not arbitrary catalog matches elsewhere in the record.
    if not re.fullmatch(r'[\w]+engine[\w]*',engine,re.I):raise DecodeError('Brak silnika.')
    if not re.fullmatch(r'g_[\w]+',gearbox,re.I):raise DecodeError('Brak skrzyni.')
    if not re.fullmatch(r'w_[\w]+',winch,re.I):raise DecodeError('Brak wyciągarki.')
    if not wheels.lower().startswith('wheels_') or not rims or not tires or not .05<=scale<=3:
        raise DecodeError('Nieprawidłowy komplet kół.')
    if not re.fullmatch(r'[\w]+suspension[\w]*',suspension,re.I):raise DecodeError('Brak zawieszenia.')
    tail=r.pos
    alternatives=[]
    # Existing map objects and newer player records differ by an optional water float.
    for has_water in (False,True):
        t=Reader(data,tail,end)
        try:
            fuel=t.floating()
            if fuel<0:continue
            if has_water and t.floating()<0:continue
            damages=[t.integer() for _ in range(5)]
            if any(value>2147483647 for value in damages):continue
            wheel_count=t.integer()
            if wheel_count not in (0,2,3,4,6,8,10,12,14,16):continue
            wheel_damage=[t.integer() for _ in range(wheel_count)]
            if any(value>2147483647 for value in wheel_damage):continue
            unlocked=t.boolean();frozen=t.boolean();trailer=t.string()
            if trailer and not re.fullmatch(r'\{[0-9a-f-]{36}\}',trailer,re.I):continue
            repairs=t.integer();wheel_repairs=t.integer();height_count=t.integer()
            if height_count!=wheel_count or repairs>2147483647 or wheel_repairs>2147483647:continue
            heights=[t.floating() for _ in range(height_count)]
            if any(abs(value)>5 for value in heights):continue
            alternatives.append((unlocked,t.pos))
        except (DecodeError,struct.error):continue
    if len(alternatives)!=1:raise DecodeError('Nie rozpoznano jednoznacznie znaczników i kół STS.')
    return {'engine':{'name':engine},'gearbox':{'name':gearbox},'winchUpgrade':{'name':winch},
            'wheelsType':wheels,'rims':rims,'tires':tires,'wheelsScale':scale,'suspension':suspension,
            'isUnlocked':alternatives[0][0],'needToInstallDefaultAddons':False},alternatives[0][1]


def decode_equipment(data,after_guid,end):
    header=Reader(data,after_guid,end)
    header.integer() # truckCRC
    count=header.integer()
    if count>256:raise DecodeError('Nieobsługiwana liczba dodatków STS.')
    addon_start=header.pos
    # The fixed role sequence identifies the end of the variable-size addon/physics segment.
    cores=[]
    for hit in re.finditer(rb'[a-z][a-z0-9_]*engine[a-z0-9_]*\x00',data[addon_start:min(end,addon_start+128000)],re.I):
        offset=addon_start+hit.start()-2
        if offset<addon_start:continue
        try:desc,stop=_core(data,offset,end)
        except (DecodeError,struct.error):continue
        cores.append((offset,desc,stop))
    if len(cores)!=1:raise DecodeError('Brak jednoznacznego segmentu wyposażenia STS.')
    core_start,desc,stop=cores[0]
    addons=[]
    for hit in re.finditer(rb'([a-z][a-z0-9_]{1,150})\x00',data[addon_start:core_start],re.I):
        offset=addon_start+hit.start()-2
        if offset<addon_start:continue
        try:
            r=Reader(data,offset,core_start)
            key=r.string();parent=r.string()
            if key.lower().startswith('bone') or not parent.lower().startswith('bone'):continue
            r.boolean()
        except (DecodeError,struct.error):continue
        addons.append((offset,key))
    if len(addons)!=count or (count and addons[0][0]!=addon_start):
        raise DecodeError(f'Niepełna lista dodatków STS ({len(addons)}/{count}).')
    desc['addons']=[{'name':key} for _,key in addons]
    return desc
