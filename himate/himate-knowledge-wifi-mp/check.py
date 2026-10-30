"""Fixed CI adapter: execute from the protected trusted baseline, never candidate code."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def absolute(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Explicit absolute job paths are required')
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked job roots or inputs are not permitted')
    return path.resolve(strict=True)


def trusted_contracts(root, expected):
    """Compile manifest-verified bytes only; no candidate imports or cached pyc."""
    lock_path = root / 'governance/framework.lock.yaml'
    raw = lock_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Job-pinned trusted rules differ')
    import yaml
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError('Duplicate rule key')
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    lock = yaml.load(raw, Loader=UniqueLoader)
    verified = {}
    for entry in lock['files'].values():
        ref = entry['path']
        if not ref.startswith('governance/') or any(part in {'', '.', '..'} for part in ref.split('/')) or chr(92) in ref or ':' in ref:
            raise ValueError('Unsafe trusted rule path')
        path = absolute(str(root / ref))
        if not path.is_relative_to(root):
            raise ValueError('Trusted rule escaped root')
        data = path.read_bytes()
        if ref in verified or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Trusted rule fingerprint differs')
        verified[ref] = data
    name = '_fixed_ci_' + expected
    class Loader(importlib.abc.Loader):
        def __init__(self, ref): self.ref = ref
        def create_module(self, spec): return None
        def exec_module(self, module):
            module.__file__ = str(root / self.ref)
            if self.ref.endswith('/__init__.py'):
                module.__path__ = []
            exec(compile(verified[self.ref], module.__file__, 'exec'), module.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != name and not fullname.startswith(name + '.'):
                return None
            relative = '__init__' if fullname == name else fullname[len(name) + 1:].replace('.', '/')
            ref = 'governance/contracts/' + relative + '.py'
            if ref not in verified:
                raise ImportError('Unpinned CI contract: ' + fullname)
            return importlib.util.spec_from_loader(fullname, Loader(ref), is_package=fullname == name)
    finder = Finder()
    sys.meta_path.insert(0, finder)
    try:
        importlib.import_module(name)
        parts = sorted(ref[len('governance/contracts/'):-3] for ref in verified
                       if ref.startswith('governance/contracts/') and ref.endswith('.py')
                       and '/' not in ref[len('governance/contracts/'):]
                       and not ref.endswith('/__init__.py'))
        modules = {part: importlib.import_module(name + '.' + part) for part in parts}
        rules = modules['validation'].load_rules(root, expected)
    finally:
        sys.meta_path.remove(finder)
    if lock_path.read_bytes() != raw or any((root / ref).read_bytes() != data for ref, data in verified.items()):
        raise ValueError('Trusted program changed during loading')
    return modules, rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('trusted-root', 'candidate-root', 'rules-digest', 'commit', 'input', 'output'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    try:
        if not all((args.trusted_root, args.candidate_root, args.rules_digest, args.commit, args.output)):
            raise ValueError('Protected job must provide trusted-root, candidate-root, rules-digest, commit and fresh output')
        trusted = absolute(args.trusted_root)
        candidate = absolute(args.candidate_root)
        output = Path(args.output)
        if not output.is_absolute() or output.exists():
            raise ValueError('A fresh absolute job report path is required')
        if output.resolve().is_relative_to(candidate) or output.resolve().is_relative_to(trusted):
            raise ValueError('CI report must be outside input trees')
        modules, rules = trusted_contracts(trusted, args.rules_digest)
        request = strict_json(absolute(args.input).read_bytes()) if args.input else {}
        data, phase = modules['ingest'].check(candidate, {**request, 'formal': True}, rules)
        report = {'report_version': '2.0', 'status': phase, 'phase': phase,
                  'exit_code': 1 if phase == 'failed' else 0, 'complete': True,
                  'rules_digest': args.rules_digest, 'commit': args.commit, **data}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            stream.write(canonical(report))
        print(json.dumps(report, ensure_ascii=True))
        return report['exit_code']
    except Exception as exc:
        print(json.dumps({'report_version': '1.0', 'status': 'incomplete', 'phase': 'incomplete', 'exit_code': 2, 'complete': False, 'checks': [], 'findings': [{'code': 'CI_INPUT_UNAVAILABLE', 'severity': 'error', 'reason': str(exc)}]}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
