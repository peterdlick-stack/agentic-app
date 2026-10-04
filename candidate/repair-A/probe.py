import hashlib,json,os,sqlite3,subprocess,sys,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R));from launcher import run

def check():
    temp=Path(tempfile.gettempdir()).resolve();assert temp.is_relative_to(R)
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);p=d/'value';p.write_text('probe');link=d/'link';link.symlink_to(p);assert link.read_text()=='probe'
        db=sqlite3.connect(d/'test.sqlite3');db.execute('create table probe(v)');db.close()
    assert not d.exists()
    from context_player import backend,feedback
    return {'temp':str(temp),'home':os.environ.get('HOME'),'symlink':True,'sqlite_cleanup':True,'backend':backend.__file__,'feedback':feedback.__file__,'no_pycache':sys.dont_write_bytecode}
if __name__=='__main__':
    if '--child' in sys.argv:print(json.dumps(check()));sys.exit(0)
    outcomes={}
    for name,cwd in [('main',R/'integration'),('fixture_child',R/'integration/test-fixtures')]:
        p=run(['python3','-B',str(Path(__file__)),'--child'],cwd);outcomes[name]={'exit':p.returncode,'output':p.stdout};assert p.returncode==0,p.stdout
    for name,code in {
      'outside_open':"open('/tmp/context-recommend-repair-forbidden','w')",
      'outside_sqlite':"import sqlite3;sqlite3.connect('/tmp/context-recommend-repair-forbidden.sqlite3')",
      'symlink_escape':"from pathlib import Path; import tempfile; d=Path(tempfile.mkdtemp()); (d/'escape').symlink_to('/tmp'); (d/'escape/context-recommend-repair-forbidden').write_text('bad')"
    }.items():
        p=run(['python3','-B','-c',code]);outcomes[name]={'exit':p.returncode,'output':p.stdout};assert p.returncode!=0 and 'WRITE_OUTSIDE_R' in p.stdout
    outcomes['parent_HOME']=os.environ.get('HOME')
    (R/'repair-A/probe.json').write_text(json.dumps(outcomes,indent=2));print(json.dumps(outcomes,indent=2))
