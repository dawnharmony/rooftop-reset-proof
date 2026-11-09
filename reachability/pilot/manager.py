"""Bounded, checkpointed pilot runner. Pause exits the entire process tree."""
import argparse,os,sys,time,json,sqlite3,subprocess,threading,queue,base64,csv,msvcrt
from pathlib import Path
from resources import Job,memory,available,identity,same_process
HERE=Path(__file__).resolve().parent
def atomic(path,data):
 if isinstance(data,dict) and 'pid' in data and (path.name=='status.json' or path.parent==HERE/'active'):
  data=dict(data);data['process_created']=identity(data['pid'])
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8')
 for _ in range(10):
  try:tmp.replace(path);return
  except PermissionError:time.sleep(.02)
 raise RuntimeError('Cannot publish status file')
def request_pause(folder,source='user'):
 folder.mkdir(parents=True,exist_ok=True);atomic(folder/'pause.request',{'requested':time.time(),'source':source});print('Pause requested. The current small task will finish; workers and coordinator then exit and release RAM.')
def pause_all(source='user'):
 atomic(HERE/'global-pause.request',{'requested':time.time(),'source':source})
 print('Pausing all pilot managers and workers...',flush=True)
 end=time.time()+8
 while time.time()<end:
  active=[]
  for p in (HERE/'active').glob('*.json'):
   try:
    q=json.loads(p.read_text());
    if same_process(q['pid'],q.get('process_created')):active.append(q['pid'])
   except (OSError,json.JSONDecodeError):pass
  if not active:print('Pilot processes have exited; their RAM is released.');return
  time.sleep(.1)
 print('Pause is still requested. Check status before resuming.')
def start(folder,args):
 folder.mkdir(parents=True,exist_ok=True)
 lock=(folder/'manager.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
 try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 except OSError:print('A pilot manager already owns this run.');return 2
 if args.command=='resume':
  (folder/'pause.request').unlink(missing_ok=True)
  if folder==(HERE/'run').resolve():(HERE/'global-pause.request').unlink(missing_ok=True)
 if (folder/'pause.request').exists() or (HERE/'global-pause.request').exists():print('Paused. Use RESUME PILOT.cmd to continue.');return 0
 # Assignment to an OS Job is mandatory; children automatically inherit it.
 guard=Job(args.memory_mib)
 registry=HERE/'active';registry.mkdir(exist_ok=True);entry=registry/(str(os.getpid())+'.json');atomic(entry,{'pid':os.getpid(),'folder':str(folder)})
 if not (folder/'pilot.sqlite').exists():
  subprocess.run([sys.executable,str(HERE/'build.py'),str(folder)],check=True,creationflags=0x08000000)
 conn=sqlite3.connect(folder/'pilot.sqlite');conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA wal_autocheckpoint=256');conn.execute('UPDATE jobs SET status="pending" WHERE status="running"');conn.commit()
 total=conn.execute('SELECT count(*) FROM jobs').fetchone()[0];initial_done=conn.execute('SELECT count(*) FROM jobs WHERE status="done"').fetchone()[0]
 started=time.time();workers={};events=queue.Queue(maxsize=max(8,args.workers*2));stop=None;completed=0;kernel_seconds=0;peak_rss=0;peak_private=0;last_status=0;failed=False
 metrics=(folder/'metrics.csv').open('a',newline='');writer=csv.writer(metrics)
 if metrics.tell()==0:writer.writerow(['time','done','active_workers','rss_bytes','private_bytes','available_bytes','queue_length'])
 def reader(proc):
  try:
   for line in proc.stdout:
    try:events.put(('result',proc.pid,json.loads(line)))
    except json.JSONDecodeError:events.put(('bad',proc.pid,line[:1000]))
  finally:events.put(('eof',proc.pid,None))
 def spawn():
  ids=[r[0] for r in conn.execute('SELECT id FROM jobs WHERE status="pending" ORDER BY id LIMIT ?',(args.batch,))]
  if not ids:return False
  conn.executemany('UPDATE jobs SET status="running" WHERE id=?',[(i,) for i in ids]);conn.commit()
  err=(folder/'worker-errors.log').open('ab')
  p=subprocess.Popen([sys.executable,str(HERE/'worker.py'),str(folder),','.join(map(str,ids))],stdout=subprocess.PIPE,stderr=err,text=True,creationflags=0x08000000|0x4000)
  t=threading.Thread(target=reader,args=(p,),daemon=True);workers[p.pid]={'p':p,'thread':t,'ids':ids,'err':err};t.start();return True
 def status(state,reason=None):
  done=conn.execute('SELECT count(*) FROM jobs WHERE status="done"').fetchone()[0]
  d={'state':state,'reason':reason,'pid':os.getpid(),'updated':time.time(),'done':done,'total':total,'remaining':total-done,'workers':len(workers),'memory_limit_mib':args.memory_mib,'peak_rss_mib':peak_rss/2**20,'peak_private_mib':peak_private/2**20,'peak_job_commit_mib':guard.peak()/2**20,'session_seconds':time.time()-started,'session_jobs':completed,'kernel_seconds':kernel_seconds,'jobs_per_second':completed/max(.001,time.time()-started),'checkpoint':'pilot.sqlite: each completed task committed'}
  d['worker_pids']=list(workers)
  atomic(folder/'status.json',d);return d
 try:
  status('running')
  while True:
   now=time.time()
   if ((folder/'pause.request').exists() or (HERE/'global-pause.request').exists()) and not stop:stop='pause requested';pause_time=now
   if now-last_status>=.5:
    samples=[memory(os.getpid())]+[memory(pid) for pid in workers]
    rss=sum(q['rss'] for q in samples);private=sum(q['private'] for q in samples);free=available();peak_rss=max(peak_rss,rss);peak_private=max(peak_private,private)
    done=initial_done+completed;writer.writerow([now,done,len(workers),rss,private,free,events.qsize()]);metrics.flush()
    size=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    reason='system RAM reserve' if free<args.reserve_mib*2**20 else 'soft memory guard' if private>args.memory_mib*2**20*.8 else 'disk budget' if size>args.disk_mib*2**20 else None
    if reason and not stop:stop=reason;pause_time=now;request_pause(folder,'resource guard')
    status('pausing' if stop else 'running',stop);last_status=now
   if not stop:
    while len(workers)<args.workers and spawn():pass
   if stop and workers and now-pause_time>5:
    for w in workers.values():w['p'].terminate()
   try:kind,pid,payload=events.get(timeout=.05)
   except queue.Empty:kind=None
   if kind=='result':
    blob=base64.b64decode(payload.pop('frontier'));elapsed=payload['seconds'];payload['blob_bytes']=len(blob)
    conn.execute('UPDATE jobs SET status="done",result=?,frontier=? WHERE id=?',(json.dumps(payload),blob,payload['id']));conn.commit();completed+=1;kernel_seconds+=elapsed
   elif kind=='bad':
    failed=True
    if not stop:stop='worker protocol error';pause_time=now;request_pause(folder,'worker error')
   elif kind=='eof':
    w=workers.pop(pid);code=w['p'].wait();w['thread'].join();w['p'].stdout.close();w['err'].close()
    conn.executemany('UPDATE jobs SET status="pending" WHERE id=? AND status="running"',[(i,) for i in w['ids']]);conn.commit()
    if code and not stop:failed=True;stop='worker exited '+str(code);pause_time=now;request_pause(folder,'worker error')
   if not workers and events.empty():
    pending=conn.execute('SELECT count(*) FROM jobs WHERE status!="done"').fetchone()[0]
    if stop or pending==0:break
  conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
  final=status('error' if failed else 'paused' if stop else 'complete',stop)
  with (folder/'sessions.jsonl').open('a',encoding='utf-8') as sessionlog:sessionlog.write(json.dumps(final)+'\n')
  print(json.dumps(final),flush=True)
  return 1 if failed else 0
 finally:
  for w in workers.values():
   if w['p'].poll() is None:w['p'].terminate()
   w['p'].wait();w['thread'].join(timeout=2);w['err'].close()
  metrics.close();conn.close();lock.close();entry.unlink(missing_ok=True)
  # Deliberately retain the Job handle: OS process exit closes it and kills
  # any remaining descendants, including after an unexpected Python failure.
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['run','resume','pause','status']);p.add_argument('--folder',type=Path,default=HERE/'run');p.add_argument('--workers',type=int,default=8);p.add_argument('--batch',type=int,default=32);p.add_argument('--memory-mib',type=int,default=512);p.add_argument('--reserve-mib',type=int,default=8192);p.add_argument('--disk-mib',type=int,default=512);a=p.parse_args();a.folder=a.folder.resolve()
 if not 1<=a.workers<=16 or not 1<=a.batch<=256:raise ValueError('Workers1..16; batch1..256')
 if a.command=='pause':
  pause_all();return 0
 if a.command=='status':
  q=a.folder/'status.json'
  if not q.exists():print('No run started.');return 0
  s=json.loads(q.read_text(encoding='utf-8'));s['global_pause_requested']=(HERE/'global-pause.request').exists();s['manager_is_running']=same_process(s['pid'],s.get('process_created'))
  if s['state'] in ['running','pausing'] and not s['manager_is_running']:s['state']='stopped unexpectedly; checkpoint can be resumed'
  print(json.dumps(s,indent=2));return 0
 return start(a.folder,a)
if __name__=='__main__':sys.exit(main())
