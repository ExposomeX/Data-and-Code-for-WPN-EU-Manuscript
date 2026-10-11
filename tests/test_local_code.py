"""CPU package input and output contract checks; no model inference."""
import csv
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'local_code'))
from wpn_core import CSV_COLUMNS, evaluate_input, positive, read_input, save_results
spec = importlib.util.spec_from_file_location('build_code_package', ROOT / 'tools/build_code_package.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)

class InputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / 'local_code/data/chemicals.json').read_text(encoding='utf-8'))

    def test_all_catalog_identities(self):
        for field in ['id','cas','name']:
            checks, valid = evaluate_input([{'identifier':x[field], 'ww':'1','row':i} for i,x in enumerate(self.catalog)],self.catalog)
            self.assertEqual(len(valid),52)
            self.assertTrue(all(x['valid'] for x in checks))

    def test_subset_unknown_and_invalid(self):
        other = next(x for x in self.catalog if x['id'] != 'DMSMPAJRVJJAGA-UHFFFAOYSA-N')
        checks, valid = evaluate_input([{'identifier':'BIT','ww':'.5e+1','row':1},{'identifier':'unknown','ww':'10','row':2},{'identifier':other['name'],'ww':'0','row':3}],self.catalog)
        self.assertEqual(len(valid),1)
        self.assertEqual(valid[0]['value'],5.)
        self.assertEqual([x['valid'] for x in checks],[True,False,False])

    def test_duplicate_alias_all_excluded(self):
        checks, valid = evaluate_input([{'identifier':'BIT','ww':'1','row':1},{'identifier':'2634-33-5','ww':'2','row':2}],self.catalog)
        self.assertFalse(valid)
        self.assertTrue(all('Duplicate' in x['reason'] for x in checks))

    def test_ww_strict(self):
        for value in ['',None,0,-1,'NaN','inf','0x10','1,000','1 mg/L','1e999',True]:
            self.assertIsNone(positive(value),value)
        for value in ['1','+1','.2','1.','1e-10']:
            self.assertIsNotNone(positive(value),value)

    def test_examples(self):
        for suffix in ['csv','xlsx']:
            records = read_input(ROOT / f'local_code/examples/example_52.{suffix}')
            self.assertEqual(len(evaluate_input(records,self.catalog)[1]),52)

    def test_wrong_unit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.csv'
            path.write_text('Chemical,WW (nM),Unit\nBIT,1,mg/L\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'nM'):
                read_input(path)
            path.write_text('Chemical,WW (nM),Unit\nBIT,1,nM\n',encoding='utf-8')
            self.assertEqual(len(read_input(path)),1)

    def test_wrong_concentration_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.csv'
            path.write_text('Chemical,WW (uM)\nBIT,1\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'nM'):
                read_input(path)

    def test_xlsx_inaccurate_dimension(self):
        from openpyxl import Workbook
        book=Workbook()
        book.active.append(['Chemical','WW (nM)'])
        book.active.append(['BIT',1.])
        binary=BytesIO()
        book.save(binary)
        with tempfile.TemporaryDirectory() as folder:
            for dimension in ['<dimension ref="A1:A1"/>','']:
                path=Path(folder)/'input.xlsx'
                with zipfile.ZipFile(BytesIO(binary.getvalue())) as original, zipfile.ZipFile(path,'w') as target:
                    for item in original.infolist():
                        data=original.read(item.filename)
                        if item.filename=='xl/worksheets/sheet1.xml':
                            data=data.replace(b'<dimension ref="A1:B2"/>',dimension.encode())
                        target.writestr(item,data)
                self.assertEqual(read_input(path)[0]['identifier'],'BIT')

    def test_only_five_output_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'result.csv'
            save_results(path,[{'rank':1,'name':'BIT','ww':1.,'beq':2.,'contribution':100.,'de':'not exported'}])
            with path.open(encoding='utf-8-sig') as stream:
                rows=list(csv.reader(stream))
            self.assertEqual(rows[0],CSV_COLUMNS)
            self.assertEqual(len(rows[1]),5)

class PackagingContract(unittest.TestCase):
    """Use tiny model fixtures so these checks do not run or copy real models."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.package = self.folder / 'portable project' / 'local_code'
        self.output = self.folder / 'downloads'
        for relative in (*packaging.ROOT_FILES, *packaging.SUPPORT_FILES):
            target = self.package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'local_code' / relative, target)
        models = self.package / 'models'
        models.mkdir()
        for name in packaging.MODEL_FILES:
            (models / name).write_bytes(f'test fixture for {name}'.encode())
        self.manifest = {
            'version': 'fixture-model-version',
            'sha256': {name: packaging.sha256(models / name) for name in packaging.MODEL_FILES},
        }
        self.write_model_manifest()
        for relative, content in {
            'inputs/concentrations.csv': b'Chemical,WW (nM)\nBIT,12\n',
            'inputs/concentrations.xlsx': b'User workbook must remain untouched',
            'results/20261010_120000/WPN_results.csv': b'Previous user results',
            'results/20261010_120000/README.txt': b'Not the result root README',
            'VALIDATION.md': b'Intermediate validation report',
            '__pycache__/wpn_core.pyc': b'cache',
            '.venv/installed-package.py': b'installed dependency',
            'data/cache/report.json': b'cache report',
        }.items():
            target = self.package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    def write_model_manifest(self):
        (self.package / 'models/manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def snapshot(self, folder):
        return {path.relative_to(folder).as_posix(): packaging.sha256(path)
                for path in folder.rglob('*') if path.is_file()}

    def test_portable_package_has_blank_inputs_and_preserves_source_files(self):
        before = self.snapshot(self.package)
        info = packaging.build_package(self.package, self.output)
        self.assertEqual(before, self.snapshot(self.package))
        self.assertEqual(info['modelVersion'], 'fixture-model-version')
        archive_path = self.output / packaging.ARCHIVE_NAME
        self.assertEqual(info['sha256'], packaging.sha256(archive_path))
        self.assertEqual(info['bytes'], archive_path.stat().st_size)
        self.assertEqual(info, json.loads((self.output / packaging.MANIFEST_NAME).read_text()))
        self.assertEqual(len(list(self.output.iterdir())), 2)
        with zipfile.ZipFile(archive_path) as archive:
            expected = set(packaging.ROOT_FILES) | set(packaging.SUPPORT_FILES) | {
                'models/manifest.json', 'inputs/concentrations.csv', 'inputs/concentrations.xlsx',
                *(f'models/{name}' for name in packaging.MODEL_FILES),
            }
            self.assertEqual(set(archive.namelist()), {f'WPN-local-code/{name}' for name in expected})
            catalog = json.loads((self.package / 'data/chemicals.json').read_text(encoding='utf-8'))
            for suffix in ['csv', 'xlsx']:
                blank = self.folder / f'blank.{suffix}'
                blank.write_bytes(archive.read(f'WPN-local-code/inputs/concentrations.{suffix}'))
                records = read_input(blank)
                self.assertEqual(len(records), 52)
                self.assertFalse(evaluate_input(records, catalog)[1])
                self.assertEqual(
                    archive.read(f'WPN-local-code/examples/example_52.{suffix}'),
                    (self.package / f'examples/example_52.{suffix}').read_bytes(),
                )
            for name in packaging.MODEL_FILES:
                self.assertEqual(archive.read(f'WPN-local-code/models/{name}'),
                                 (self.package / 'models' / name).read_bytes())

    def test_invalid_artifact_keeps_existing_downloads(self):
        packaging.build_package(self.package, self.output)
        before = self.snapshot(self.output)
        (self.package / 'models/model.joblib').write_bytes(b'changed model')
        with self.assertRaisesRegex(ValueError, 'hash does not match'):
            packaging.build_package(self.package, self.output)
        self.assertEqual(before, self.snapshot(self.output))

    def test_publication_failure_restores_previous_pair(self):
        packaging.build_package(self.package, self.output)
        before = self.snapshot(self.output)
        (self.package / 'README.md').write_text('New package documentation', encoding='utf-8')
        replace = packaging.os.replace

        def fail_manifest(source, target):
            if Path(source).name == packaging.MANIFEST_NAME:
                raise PermissionError('Simulated manifest file lock')
            return replace(source, target)

        with patch.object(packaging.os, 'replace', side_effect=fail_manifest):
            with self.assertRaisesRegex(PermissionError, 'Simulated'):
                packaging.build_package(self.package, self.output)
        self.assertEqual(before, self.snapshot(self.output))

    def test_rejects_unsafe_paths_and_output_inside_user_files(self):
        self.manifest['sha256']['../outside.joblib'] = 'unsafe'
        self.write_model_manifest()
        with self.assertRaisesRegex(ValueError, 'Unsafe model artifact name'):
            packaging.build_package(self.package, self.output)
        self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, 'outside local_code'):
            packaging.build_package(self.package, self.package / 'inputs')


if __name__=='__main__':
    unittest.main()
