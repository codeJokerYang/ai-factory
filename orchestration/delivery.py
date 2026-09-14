"""Verified local handoff bundles; this module never publishes to a server."""
import hashlib
import io
import json
import zipfile
import re
from pathlib import Path

from .util import resolve_within


def capture_artifacts(target):
    from .schemas import GeneratedFile
    from .security import validate_feature_files
    from .scaffold import scaffold_files
    target = Path(target)
    manifest = json.loads((target / '.factory-generated.json').read_text(encoding='utf-8'))
    allowed = set(scaffold_files('app')) | {'package-lock.json'}
    paths = set(manifest)
    if (target / 'package-lock.json').exists():
        paths.add('package-lock.json')
    hashes = {}
    total = 0
    for relative in sorted(paths):
        if relative.startswith('.env'):
            continue
        if relative not in allowed:
            validate_feature_files([GeneratedFile(path=relative, content='')])
        path = resolve_within(target, relative)
        if path.is_symlink() or not path.is_file():
            raise ValueError('交付文件缺失或为符号链接：' + relative)
        total += path.stat().st_size
        if total > 64*1024*1024:
            raise ValueError('交付源码超过 64 MiB')
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def make_bundle(record, generated_root):
    from .projects import accepted
    from .business import business_passed
    from .security import scan_files, is_blocking
    from .history import redact
    state = record['state']
    if not accepted(record) or not state.get('delivery_mode') or not business_passed(state):
        raise ValueError('交付包要求交付模式、真实业务测试和全部检查及人工验收通过')
    target = Path(state.get('build_dir') or '').resolve()
    root = Path(generated_root).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError('交付目录不在 generated 内')
    expected = state.get('artifact_hashes')
    if not expected or 'package-lock.json' not in expected:
        raise ValueError('缺少锁定依赖或交付指纹，请重新运行交付检查')
    if capture_artifacts(target) != expected:
        raise ValueError('验收后文件发生变化，禁止打包旧验收结果')
    files = {}
    total = 0
    for relative, checksum in expected.items():
        content = resolve_within(target, relative).read_bytes()
        if hashlib.sha256(content).hexdigest() != checksum:
            raise ValueError('打包过程中源码变化，请重试')
        total += len(content)
        if total > 64 * 1024 * 1024:
            raise ValueError('交付源码过大，超过 64 MiB 上限')
        if is_blocking(scan_files([(relative, content.decode('utf-8', errors='replace'))])):
            raise ValueError('交付源码安全检查未通过：' + relative)
        files[relative] = content
    files['FACTORY-HANDOFF.md'] = ('''# 本地交付包

本包不是已经上线的网站，不含服务商凭据、node_modules 或客户生产数据。

1. 在受控环境安装兼容此项目的 Node.js/npm。
2. 执行 npm ci --ignore-scripts，随后 npm run build。
3. 启动 npm run start，验证本包 business-report.json 中的业务场景。
4. 正式发布前另行配置域名、HTTPS、必要环境变量、生产数据库和访问控制。
5. 保留上一发布包；代码回滚不等于数据库回滚，业务数据需要独立备份。

业务测试仅覆盖配置的场景，不能作为所有功能或生产安全的证明。
''').encode('utf-8')
    business_report = redact(state['business_report'])
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',record['id']):
        raise ValueError('任务编号无效')
    evidence_root = root.parent / '.factory' / 'runs' / record['id'] / 'business'
    for case in business_report['cases']:
        name = case.get('screenshot')
        if name and case.get('screenshot_sha256'):
            if not re.fullmatch(r'case-\d+-(1440|390)\.png',name):
                raise ValueError('业务截图名称无效')
            shot = resolve_within(evidence_root,name)
            if shot.stat().st_size > 8*1024*1024:
                raise ValueError('业务截图过大')
            content=shot.read_bytes()
            if hashlib.sha256(content).hexdigest()!=case['screenshot_sha256']:
                raise ValueError('业务截图在验证后发生变化')
            files['evidence/'+name]=content
            case['screenshot']='evidence/'+name
    files['business-report.json'] = json.dumps(business_report, ensure_ascii=False, indent=2).encode('utf-8')
    files['factory-manifest.json'] = json.dumps(dict(task=record['id'], project=state.get('workspace_id'),
         source_sha256=expected, status='local_handoff_not_deployed'), ensure_ascii=False, indent=2).encode('utf-8')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
