"""Build reviewable Windows release bundles from explicit source and binary inputs."""
import argparse,hashlib,importlib.metadata,json,os,re,subprocess,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MODULES=('savesync.py','host_packer_app.py','host_packer.py','host_archive.py','save_discovery.py',
 'catalog.py','catalog_languages.py','prices.py','unlock_ids.py','upgrade_editor.py','experience.py',
 'company.py','vehicles.py','sts_equipment.py','cat_effects.py','i18n.py','translations.py',
 'build_prices.py','build_catalog_languages.py')
TESTS=('test_savesync.py','test_host_packer.py','test_host_archive.py','test_save_discovery.py',
 'test_company.py','test_experience.py','test_vehicles.py','test_sts_valuation.py','test_cat.py',
 'test_languages.py','test_packer_languages.py','test_release.py')
DOCS=('README.md','README.pl.md','HOST-PACKER-README.md','LICENSE','THIRD_PARTY_NOTICES.md',
 'SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','VERSION','requirements-build.txt',
 '.gitignore','.gitattributes','Uruchom.cmd','Uruchom-Paker.cmd','docs/BUILD.md',
 'docs/FIRST_RELEASE.pl.md','docs/RELEASE_NOTES.md','docs/licenses/Tcl.txt','.github/workflows/ci.yml',
 '.github/workflows/release.yml','.github/dependabot.yml','.github/ISSUE_TEMPLATE/bug_report.yml',
 '.github/ISSUE_TEMPLATE/config.yml','tools/build_release.py')
SOURCES=MODULES+TESTS+DOCS

def version():
    value=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',value):raise ValueError('Invalid VERSION')
    return value

def source_files(root=ROOT):
    result=[]
    for name in SOURCES:
        path=root/name
        if not path.is_file() or path.is_symlink():raise ValueError('Missing or linked source: '+name)
        if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Source escapes project: '+name)
        result.append(path)
    return result

def zip_files(destination,files):
    # Inputs are explicit (archive name, bytes). Never include arbitrary dist/release files.
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files):
            if name.startswith(('/','\\')) or '..' in Path(name).parts:raise ValueError('Unsafe archive name')
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;archive.writestr(info,data)

def source_archive(destination,root=ROOT):
    zip_files(destination,[(path.relative_to(root).as_posix(),path.read_bytes()) for path in source_files(root)])

def third_party_licenses():
    sections=[]
    for label,path in [('Python',Path(sys.base_prefix)/'LICENSE.txt'),
                       ('Tcl',ROOT/'docs/licenses/Tcl.txt'),
                       ('Tk',Path(sys.base_prefix)/'tcl/tk8.6/license.terms')]:
        if not path.is_file():raise ValueError('Required runtime license not found: '+str(path))
        sections.append(label+'\n'+'='*60+'\n'+path.read_text(encoding='utf-8',errors='replace'))
    dist=importlib.metadata.distribution('pyinstaller');found=False
    for file in dist.files or ():
        if file.name.upper().startswith(('COPYING','LICENSE')):
            path=dist.locate_file(file)
            if path.is_file():
                sections.append('PyInstaller / '+file.name+'\n'+'='*60+'\n'+path.read_text(encoding='utf-8',errors='replace'));found=True
    if not found:raise ValueError('PyInstaller license not found')
    return '\n\n'.join(sections).encode('utf-8')

def build_binaries(value):
    if sys.platform!='win32':raise RuntimeError('Windows x64 is required for the executable release build')
    if sys.maxsize<=2**32:raise RuntimeError('Use 64-bit Python')
    components=tuple(int(n) for n in value.split('.'))
    numeric=components+(0,)*(4-len(components))
    work=ROOT/'build/release';work.mkdir(parents=True,exist_ok=True)
    info=work/'version_info.txt'
    info.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers="+repr(numeric)+", prodvers="+repr(numeric)+", mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('ProductName','SnowRunner SaveSync'), StringStruct('ProductVersion',"+repr(value)+"), StringStruct('FileVersion',"+repr(value)+")])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])",encoding='utf-8')
    result={}
    for name,module in [('SnowRunner-SaveSync','savesync.py'),('SnowRunner-HostPacker','host_packer_app.py')]:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--noupx','--onefile','--windowed',
          '--name',name,'--distpath',str(work/'bin'),'--workpath',str(work/'work'),
          '--specpath',str(work/'spec'),'--version-file',str(info),str(ROOT/module)],cwd=ROOT,check=True)
        result[name]=work/'bin'/(name+'.exe')
    return result

def commit_id():
    result=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True)
    return result.stdout.strip() if result.returncode==0 else 'uncommitted'

def make_release(source_only=False,expected_tag=None):
    value=version()
    if expected_tag is not None and expected_tag!='v'+value:raise ValueError('Tag must match VERSION: v'+value)
    source_files()  # Validate the complete allowlist before starting expensive builds.
    output=ROOT/'release';output.mkdir(exist_ok=True)
    source=output/f'SnowRunner-SaveSync-{value}-source.zip';source_archive(source)
    artifacts=[source]
    if not source_only:
        licenses=third_party_licenses()
        binaries=build_binaries(value)
        for name,binary in binaries.items():
            target=output/f'{name}-{value}-windows-x64.zip'
            files=[(binary.name,binary.read_bytes()),('THIRD_PARTY_LICENSES.txt',licenses)]
            files += [(name,(ROOT/name).read_bytes()) for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','docs/BUILD.md','docs/RELEASE_NOTES.md','HOST-PACKER-README.md')]
            zip_files(target,files);artifacts.append(target)
    metadata={'version':value,'source_commit':commit_id(),'python':sys.version,'platform':sys.platform,
      'local_preview':not bool(os.environ.get('GITHUB_ACTIONS')),'source_only':source_only,
      'catalog_distribution':'included by maintainer decision; no third-party permission asserted; see THIRD_PARTY_NOTICES.md',
      'build_packages':{name:importlib.metadata.version(name) for name in ('pyinstaller','pyinstaller-hooks-contrib')} if not source_only else {},
      'artifacts':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}}
    info=output/'build-info.json';info.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8');artifacts.append(info)
    checksums=output/'SHA256SUMS.txt';checksums.write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n' for path in sorted(artifacts)),encoding='utf-8')
    print('Release preview:',output)
    return artifacts+[checksums]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-only',action='store_true');parser.add_argument('--tag')
    args=parser.parse_args();make_release(args.source_only,args.tag)
