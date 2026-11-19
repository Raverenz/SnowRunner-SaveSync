"""Build factual offline price catalog from the user's installed initial.pak."""
import copy,json,re,sys,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit('Usage: python build_prices.py <path-to-initial.pak>')
pak=Path(sys.argv[1])
z=zipfile.ZipFile(pak)
strings=dict(re.findall(r'^([^\s]+)\s+"(.*)"\s*$',z.read('[strings]/strings_polish.str').decode('utf-16'),re.M))
docs={}; index={}
for path in z.namelist():
 if '/classes/' not in path or not path.endswith('.xml'): continue
 category=path.split('/classes/')[1].split('/')[0]
 if category not in ('trucks','engines','gearboxes','suspensions','winches','wheels'): continue
 text=z.read(path).decode('utf-8-sig')
 text=re.sub(r'([\s<])([A-Za-z_][\w]*):([\w]+)',r'\1\2_\3',text)
 try: root=ET.fromstring('<root>'+text+'</root>')
 except ET.ParseError: continue
 docs[path]=root
 index.setdefault((category,Path(path).stem),[]).append(path)

def parent_path(path,stem):
 category=path.split('/classes/')[1].split('/')[0]
 choices=index.get((category,stem),[])
 local=str(Path(path).parent).replace('\\','/')+'/'+stem+'.xml'
 if local in choices: return local
 return min(choices,key=lambda p: ('/_dlc/' in p,len(p))) if choices else None

def overlay(base,child):
 if child.get('_noinherit')=='true': return copy.deepcopy(child)
 result=copy.deepcopy(base);result.attrib.update(child.attrib)
 for node in child:
  if node.tag in ('_parent','_templates'): continue
  identity=node.get('Name')
  targets=[e for e in result if e.tag==node.tag and (not identity or e.get('Name')==identity)]
  if len(targets)==1:
   old=targets[0]; pos=list(result).index(old); result.remove(old); result.insert(pos,overlay(old,node))
  else: result.append(copy.deepcopy(node))
 return result
cache={}
def resolve(path,seen=()):
 if path in cache: return cache[path]
 if path in seen: return docs[path]
 root=docs[path]; parent=root.find('_parent')
 if parent is not None:
  target=parent_path(path,parent.get('File',''))
  if target: root=overlay(resolve(target,seen+(path,)),root)
 cache[path]=root
 return root

def price(gd):
 if gd is None: return None
 try: value=int(gd.get('Price'))
 except (ValueError,TypeError): return None
 return value if value>=0 else None

def label(ui,fallback):
 name=ui.get('UiName') if ui is not None else None
 text=strings.get(name,fallback).replace('\\"','"')
 return text if len(text)<=120 else fallback

parts={};trucks={};tires={};conflicts=set()
def add_part(key,entry):
 if key in parts and parts[key]['price']!=entry['price']:
  conflicts.add(key)
 else: parts[key]=entry

for path in docs:
 root=resolve(path); category=path.split('/classes/')[1].split('/')[0];file=Path(path).stem
 truck=root.find('Truck')
 if truck is not None:
  gd=truck.find('GameData');p=price(gd)
  if p is None: continue
  td=truck.find('TruckData'); defaults={}
  for tag,field in [('EngineSocket','engine'),('GearboxSocket','gearbox'),('SuspensionSocket','suspension'),('WinchUpgradeSocket','winchUpgrade')]:
   socket=truck.find('TruckData/'+tag)
   if socket is not None: defaults[field]=socket.get('Default','')
  wheels=truck.find('TruckData/Wheels')
  default_addons=[e.get('Addon') for e in truck.findall('GameData/AddonSockets/Socket') if e.get('Addon')]
  # Default addons are declared explicitly in GameData/AddonSockets/Socket/DefaultAddon or DefaultAddon tags.
  default_addons += [e.get('Type') for e in truck.iter('DefaultAddon') if e.get('Type')]
  default_addons += [e.get('DefaultAddon') for e in truck.iter('AddonSockets') if e.get('DefaultAddon')]
  trucks[file]={'name':label(truck.find('GameData/UiDesc'),file),'price':p,'defaults':defaults,
                'is_trailer':'/trailers/' in path,'default_addons':default_addons,'wheels':{'type':wheels.get('DefaultWheelType',''),'tire':wheels.get('DefaultTire','')} if wheels is not None else {}}
 addon=root.find('TruckAddon')
 if addon is not None:
  p=price(addon.find('GameData'))
  if p is not None:
   add_part(file,{'name':label(addon.find('GameData/UiDesc'),file),'price':p,'kind':'Dodatek'})
 for container,tag,kind in [('EngineVariants','Engine','Silnik'),('GearboxVariants','Gearbox','Skrzynia biegów'),('SuspensionSetVariants','SuspensionSet','Zawieszenie'),('WinchVariants','Winch','Wyciągarka')]:
  for e in root.findall(container+'/'+tag):
   p=price(e.find('GameData'));key=e.get('Name')
   if p is not None and key: add_part(key,{'name':label(e.find('GameData/UiDesc'),key),'price':p,'kind':kind})
 for e in root.findall('TruckWheels/TruckTires/TruckTire'):
  p=price(e.find('GameData'));key=e.get('Name')
  if p is not None and key: tires[file+'|'+key]={'name':label(e.find('GameData/UiDesc'),key),'price':p,'kind':'Komplet opon'}
for key in conflicts: parts.pop(key,None)
# Case-insensitive game IDs; never choose between conflicting prices.
def lower_keys(entries):
 result={};bad=set()
 for key,value in entries.items():
  k=key.lower()
  if k in result and result[k]['price']!=value['price']: bad.add(k)
  else: result[k]=value
 for k in bad: result.pop(k,None)
 return result
catalog={'trucks':lower_keys(trucks),'parts':lower_keys(parts),'tires':lower_keys(tires)}
Path('prices.py').write_text('# Nominal catalog prices from local SnowRunner initial.pak, 2026-11-11.\n# Chassis prices exclude equipment. No game XML or media included.\nPRICES = '+repr(catalog)+'\n',encoding='utf-8')
print({k:len(v) for k,v in catalog.items()},'conflicting parts',len(conflicts))
print('CK1500',catalog['trucks'].get('chevrolet_ck1500'))
