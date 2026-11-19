import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from tools.build_release import ROOT,SOURCES,source_files,source_archive,zip_files,version

class ReleaseTests(unittest.TestCase):
    def test_allowlist_excludes_private_inputs_and_build_outputs(self):
        files=source_files();self.assertEqual(len(files),len(set(files)))
        self.assertEqual(len(SOURCES),len(files))
        for path in files:
            relative=path.relative_to(ROOT)
            self.assertNotIn(relative.parts[0],('dist','build','release','.buildenv','.venv','.git'))
            self.assertNotIn(path.suffix.lower(),('.cfg','.dat','.zip','.bak','.pak','.exe','.key','.pem'))
    def test_source_package_is_exact_and_cannot_pick_up_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);fake_root=directory/'project';fake_root.mkdir()
            for name in SOURCES:
                path=fake_root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'allowed source')
            (fake_root/'dist').mkdir();(fake_root/'dist'/'private-host.zip').write_bytes(b'private save bytes')
            (fake_root/'secret.env').write_bytes(b'private token')
            output=directory/'source.zip';source_archive(output,fake_root)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()),set(SOURCES))
                self.assertTrue(all(archive.read(name)==b'allowed source' for name in SOURCES))
                self.assertIsNone(archive.testzip())
            (fake_root/SOURCES[0]).unlink()
            with self.assertRaises(ValueError):source_files(fake_root)
    def test_zip_manifest_and_version(self):
        self.assertEqual(version(),'1.0')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'package.zip'
            zip_files(output,[('app.exe',b'program'),('LICENSE',b'license')])
            with zipfile.ZipFile(output) as archive:self.assertEqual(archive.namelist(),['LICENSE','app.exe'])
            first=hashlib.sha256(output.read_bytes()).hexdigest()
            zip_files(output,[('LICENSE',b'license'),('app.exe',b'program')])
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),first)
            with self.assertRaises(ValueError):zip_files(output,[('../private.cfg',b'bad')])
    def test_workflows_do_not_publish_automatically(self):
        text=(ROOT/'.github/workflows/release.yml').read_text(encoding='utf-8-sig')
        self.assertIn('--draft',text)
        self.assertNotIn('--prerelease',text)
        self.assertNotIn('pull_request_target',text)
        self.assertIn('persist-credentials: false',text)
        self.assertIn('actions/attest@',text)
        self.assertIn('python -m unittest discover -v',text)

if __name__=='__main__':unittest.main()
