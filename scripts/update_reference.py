"""Rebuild source-linked route inventories without importing the app or reading secrets."""
import ast
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def link(path, label=None):
    return f"[{label or path.name}](../{path.relative_to(ROOT).as_posix()})"

def generate():
    lines = ['# Generated route reference', '', 'Generated from source with `python scripts/update_reference.py`. This inventory records declared routes; it does not prove authorization or deployed availability. See CODE_MAP.md for services and tests.', '', '## Browser routes', '', '| Browser URL | Component | Source |', '| --- | --- | --- |']
    app = ROOT / 'frontend/src/App.jsx'
    text = app.read_text(encoding='utf-8')
    imports = dict(re.findall(r"const (\w+) = lazy\(\(\) => import\([\"']([^\"']+)", text))
    workspace = ''
    for match in re.finditer(r'<Route\b(.*?)(?:/>|>)',text,re.S):
        tag = match.group(1)
        path = re.search(r"path=[\"']([^\"']+)",tag)
        if not path: continue
        # Opening tag may stop at the first JSX >; capture element separately nearby.
        chunk = text[match.start():match.start()+600]
        element = re.search(r'element=\{\s*<(\w+)',chunk)
        component = element.group(1) if element else 'Container / see App.jsx'
        if component == 'ProtectedRoute':
            child = re.search(r'<ProtectedRoute[^>]*>\s*<(\w+)',chunk)
            if child: component = child.group(1)
        target = imports.get(component)
        source = app.parent / target if target else app
        if not source.exists() and source.with_suffix('.jsx').exists(): source = source.with_suffix('.jsx')
        if not source.exists(): source = app
        declared = path.group(1)
        if declared.startswith('/'):
            workspace = declared if declared in {'/institution','/teacher','/student','/platform'} else ''
            full = declared
        else:
            full = declared if declared == '*' else workspace + '/' + declared
        lines.append(f'| `{full}` | {component} | {link(source)} |')
    lines += ['', '## API endpoints', '', 'Includes literal APIRouter prefixes. Function links identify the handler; dependency checks determine permissions. Dynamic/nonliteral declarations, if any, require manual review.', '', '| Method | Endpoint | Handler | Source |', '| --- | --- | --- | --- |']
    for file in sorted((ROOT/'backend/app/api/routes').glob('*.py')):
        tree=ast.parse(file.read_text(encoding='utf-8'));prefix=''
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='APIRouter':
                for kw in node.keywords:
                    if kw.arg=='prefix' and isinstance(kw.value,ast.Constant):prefix=kw.value.value
        for node in tree.body:
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            for deco in node.decorator_list:
                if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr in {'get','post','put','patch','delete','head','options'} and deco.args and isinstance(deco.args[0],ast.Constant):
                    lines.append(f'| {deco.func.attr.upper()} | `{prefix}{deco.args[0].value}` | `{node.name}` | {link(file)} |')
    lines += ['', '## Test modules', '', 'Run from backend: `python -m pytest tests/<module>.py -q`. See the maintenance handbook for isolated database constraints.', '']
    lines += ['- '+link(f) for f in sorted((ROOT/'backend/tests').glob('test_*.py'))]
    lines += ['', '## Database model map', '', 'Columns below are declared on each class; inherited tenant IDs, UUIDs and timestamps are defined in backend/app/db/base.py. Read each model for constraints, indexes and types. Changes also need an Alembic migration.', '', '| Table | Model | Declared fields | Source |', '| --- | --- | --- | --- |']
    for file in sorted((ROOT/'backend/app/models').glob('*.py')):
        tree=ast.parse(file.read_text(encoding='utf-8'))
        for node in tree.body:
            if not isinstance(node,ast.ClassDef): continue
            table=None;fields=[]
            for field in node.body:
                if isinstance(field,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__tablename__' for t in field.targets) and isinstance(field.value,ast.Constant):table=field.value.value
                if isinstance(field,ast.AnnAssign) and isinstance(field.target,ast.Name):fields.append(field.target.id)
            if table:lines.append(f'| `{table}` | `{node.name}` | '+', '.join('`'+f+'`' for f in fields)+f' | {link(file)} |')
    lines += ['', '## Migration source inventory', '', 'Inspect revision/down_revision inside each file and use Alembic history for execution order. Filename order alone does not establish ancestry. Downgrades may deliberately refuse to discard populated history.', '']
    lines += ['- '+link(f) for f in sorted((ROOT/'backend/alembic/versions').glob('*.py'))]
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    target=ROOT/'docs/ROUTE_REFERENCE.md';target.write_text(generate(),encoding='utf-8');print('Updated docs/ROUTE_REFERENCE.md')
