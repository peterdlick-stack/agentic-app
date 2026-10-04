import os,sys
from pathlib import Path
ROOT=Path(os.environ['ISOLATION_ROOT']).resolve();sys.dont_write_bytecode=True
ROOTS=(ROOT,Path(os.environ['ISOLATION_EVIDENCE_ROOT']).resolve())

def guarded_path(p,fd=None,follow=True):
    if isinstance(p,int):return
    q=Path(os.fsdecode(p))
    if not q.is_absolute() and isinstance(fd,int) and fd>=0:q=Path(os.readlink('/proc/self/fd/'+str(fd)))/q
    q=q.resolve() if follow else q.parent.resolve()/q.name
    if not any(q.is_relative_to(root) for root in ROOTS):raise PermissionError('WRITE_OUTSIDE_R:'+str(q))
def guard(event,args):
    if event=='open':
        p,mode,flags=args
        if isinstance(p,(str,bytes,os.PathLike)) and ((isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))):guarded_path(p)
    elif event=='sqlite3.connect':
        p=args[0]
        if p != ':memory:':
            # sqlite URI paths are interpreted by native SQLite, not pathlib.
            if isinstance(p,str) and p.startswith('file:'):
                raise PermissionError('SQLITE_URI_NOT_ALLOWED')
            guarded_path(p)
    elif event in ('os.remove','os.rmdir'):guarded_path(args[0],args[1],False)
    elif event in ('os.mkdir','os.chmod'):guarded_path(args[0],args[2])
    elif event=='os.utime':guarded_path(args[0],args[3])
    elif event=='os.truncate':guarded_path(args[0])
    elif event in ('os.rename','os.link'):
        guarded_path(args[0],args[2],False);guarded_path(args[1],args[3],False)
    elif event=='os.symlink':guarded_path(args[1],args[2],False)
sys.addaudithook(guard)

# -m prepends cwd after sitecustomize; a finder pins the entire package even
# when cwd contains a fixture copy. Log actual spec origins used by each PID.
import importlib.abc, importlib.machinery, hashlib, json, time
IMPORT_ROOT=Path(os.environ['CANDIDATE_IMPORT_ROOT']).resolve()
class CandidateFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname=='context_player':
            spec=importlib.machinery.PathFinder.find_spec(fullname,[str(IMPORT_ROOT)])
        elif fullname.startswith('context_player.'):
            spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        else:return None
        if spec and spec.origin and spec.origin!='namespace':
            origin=Path(spec.origin).resolve()
            if not origin.is_relative_to(IMPORT_ROOT/'context_player'):
                raise ImportError('NON_CANDIDATE_IMPORT:'+str(origin))
            if fullname in ('context_player.backend','context_player.feedback'):
                row={'pid':os.getpid(),'ppid':os.getppid(),'module':fullname,'path':str(origin),'sha256':hashlib.sha256(origin.read_bytes()).hexdigest(),'time_ns':time.time_ns(),'cwd':os.getcwd()}
                with open(os.environ['IMPORT_AUDIT_PATH'],'a') as stream:stream.write(json.dumps(row)+'\n')
        return spec
sys.meta_path.insert(0,CandidateFinder())
