import ctypes,os
from ctypes import wintypes as W
K=ctypes.WinDLL('kernel32',use_last_error=True);P=ctypes.WinDLL('psapi',use_last_error=True)
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)]
K.GetProcessTimes.argtypes=[W.HANDLE,ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME)]
def identity(pid):
 h=K.OpenProcess(0x1000,False,pid)
 if not h:return None
 try:
  c,e,k,u=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
  if not K.GetProcessTimes(h,ctypes.byref(c),ctypes.byref(e),ctypes.byref(k),ctypes.byref(u)):return None
  return (c.dwHighDateTime<<32)|c.dwLowDateTime
 finally:K.CloseHandle(h)
def process_state(pid,created):
 if created is None:return 'unverified identity'
 h=K.OpenProcess(0x1000,False,pid)
 if not h:
  # A separate sandbox token may be unable to query a live worker. Do not
  # report that its RAM was released merely because access was denied.
  return 'unknown (access denied)' if ctypes.get_last_error()==5 else 'exited'
 try:
  c,e,k,u=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
  if not K.GetProcessTimes(h,ctypes.byref(c),ctypes.byref(e),ctypes.byref(k),ctypes.byref(u)):return 'unknown (access denied)'
  if ((c.dwHighDateTime<<32)|c.dwLowDateTime)!=created:return 'different process'
  code=W.DWORD()
  if not K.GetExitCodeProcess(h,ctypes.byref(code)):return 'unknown (access denied)'
  return 'running' if code.value==259 else 'exited'
 finally:K.CloseHandle(h)

def same_process(pid,created):return process_state(pid,created) in ['running','unknown (access denied)']
K.CloseHandle.argtypes=[W.HANDLE];K.GetCurrentProcess.restype=W.HANDLE
class COUNTERS(ctypes.Structure):
 _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ['peak','rss','poolPeak','pool','nonPoolPeak','nonPool','page','pagePeak','private']]
P.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.POINTER(COUNTERS),W.DWORD]
def memory(pid):
 h=K.OpenProcess(0x1000|0x10,False,pid)
 if not h:return {'rss':0,'private':0}
 c=COUNTERS();c.cb=ctypes.sizeof(c)
 try:
  exitcode=W.DWORD()
  if K.GetExitCodeProcess(h,ctypes.byref(exitcode)) and exitcode.value!=259:return {'rss':0,'private':0}
  if not P.GetProcessMemoryInfo(h,ctypes.byref(c),c.cb):return {'rss':0,'private':0}
  return {'rss':c.rss,'private':c.private}
 finally:K.CloseHandle(h)
class MEMORY(ctypes.Structure):
 _fields_=[('length',W.DWORD),('load',W.DWORD)]+[(n,ctypes.c_ulonglong) for n in ['total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extended']]
def available():
 m=MEMORY();m.length=ctypes.sizeof(m);K.GlobalMemoryStatusEx(ctypes.byref(m));return m.available
class BASIC(ctypes.Structure):
 _fields_=[('processTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',W.DWORD),('minWorking',ctypes.c_size_t),('maxWorking',ctypes.c_size_t),('active',W.DWORD),('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ['ro','wo','oo','rb','wb','ob']]
class EXTENDED(ctypes.Structure):_fields_=[('basic',BASIC),('io',IO),('processMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProcess',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
K.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
K.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p]
class Job:
 def __init__(self,mib):
  self.handle=K.CreateJobObjectW(None,None);self.info=EXTENDED();self.info.basic.flags=0x2000|0x200 # kill on last handle close + aggregate commit limit
  self.info.jobMemory=mib*1024**2
  if not self.handle or not K.SetInformationJobObject(self.handle,9,ctypes.byref(self.info),ctypes.sizeof(self.info)) or not K.AssignProcessToJobObject(self.handle,K.GetCurrentProcess()):
   raise OSError(ctypes.get_last_error(),'Cannot enforce Windows Job memory limit; refusing to run')
 def peak(self):
  q=EXTENDED()
  if K.QueryInformationJobObject(self.handle,9,ctypes.byref(q),ctypes.sizeof(q),None):return q.peakJob
  return 0
 def configured_limit(self):
  q=EXTENDED()
  if not K.QueryInformationJobObject(self.handle,9,ctypes.byref(q),ctypes.sizeof(q),None):raise OSError(ctypes.get_last_error())
  return {'flags':q.basic.flags,'commitLimitBytes':q.jobMemory}
 # Keep this handle alive until process exit: it kills any orphan child workers.
