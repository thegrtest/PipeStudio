import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import unittest

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from fleet_common import digest_file, digest_json, read_json
from release_store import install, stage
from test_domain_runtime import fixture


def release_request(contents):
    files={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    return dict(release=digest_json(files),files=files)


def transfer(root, contents, request, offer):
    archive=root/'incoming'/(request['release']+'.tgz'); archive.parent.mkdir(exist_ok=True)
    with tarfile.open(archive,'w:gz') as package:
        for name in offer['missing']:
            data=contents[name]; member=tarfile.TarInfo(name); member.size=len(data)
            package.addfile(member,io.BytesIO(data))
    return {**request,'archive':archive.name,'sha256':digest_file(archive),'base_release':offer['base_release']}


class FleetUpdateTests(unittest.TestCase):
    def test_live_staging_does_not_activate_or_modify_the_old_release(self):
        with fixture() as root:
            old={'renderer.py':b'old'}; req=release_request(old)
            install(root,transfer(root,old,req,stage(root,req)))
            new={'renderer.py':b'new'}; req2=release_request(new)
            patch=transfer(root,new,req2,stage(root,{**req2,'activate':False}))
            install(root,{**patch,'activate':False})
            self.assertEqual(read_json(root/'current_release.json')['release'],req['release'])
            self.assertTrue(stage(root,{**req2,'activate':False})['installed'])
            self.assertEqual(read_json(root/'current_release.json')['release'],req['release'])
            stage(root,req2)
            self.assertEqual(read_json(root/'current_release.json')['release'],req2['release'])

    def test_incremental_update_reuses_files_without_altering_previous_release(self):
        with fixture() as root:
            first={'renderer.py':b'version one','assets/texture.png':b'large unchanged asset'}
            request=release_request(first); offer=stage(root,request)
            self.assertEqual(set(offer['missing']),set(first))
            install(root,transfer(root,first,request,offer))
            second={**first,'renderer.py':b'version two','calibration.json':b'{}'}
            new=release_request(second); offer=stage(root,new)
            self.assertEqual(set(offer['missing']),{'renderer.py','calibration.json'})
            result=install(root,transfer(root,second,new,offer))
            self.assertEqual((result['changed'],result['reused']),(2,1))
            self.assertEqual((root/'releases'/request['release']/'renderer.py').read_bytes(),b'version one')
            repeat=stage(root,new)
            self.assertTrue(repeat['installed'])
            self.assertEqual(repeat['missing'],[])

    def test_corrupt_base_file_is_transferred_again_and_new_release_is_isolated(self):
        with fixture() as root:
            old={'renderer.py':b'v1','asset.json':b'original'}
            req=release_request(old); offer=stage(root,req); install(root,transfer(root,old,req,offer))
            (root/'releases'/req['release']/'asset.json').write_bytes(b'corrupt')
            new={**old,'renderer.py':b'v2'}; req2=release_request(new); offer=stage(root,req2)
            self.assertIn('asset.json',offer['missing'])
            install(root,transfer(root,new,req2,offer))
            (root/'releases'/req['release']/'asset.json').write_bytes(b'manual edit')
            self.assertEqual((root/'releases'/req2['release']/'asset.json').read_bytes(),b'original')

    def test_bad_patch_never_replaces_installed_release(self):
        with fixture() as root:
            data={'renderer.py':b'first'}; req=release_request(data)
            install(root,transfer(root,data,req,stage(root,req)))
            update={'renderer.py':b'second'}; req2=release_request(update)
            patch=transfer(root,update,req2,stage(root,req2)); patch['sha256']='0'*64
            with self.assertRaises(ValueError): install(root,patch)
            self.assertEqual(read_json(root/'current_release.json')['release'],req['release'])
            self.assertFalse((root/'releases'/req2['release']).exists())

    def test_release_manifest_cannot_name_paths_outside_snapshot(self):
        with fixture() as root:
            with self.assertRaises(ValueError): stage(root,release_request({'../outside':b'bad'}))


if __name__=='__main__': unittest.main()
