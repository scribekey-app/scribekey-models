# Fresh process: load one model, decode one clip, report peak host RSS.
import sys, os, json, resource
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soundfile as sf
from common import mk, decode
name,models_root,wav=sys.argv[1:4]
r0=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
rc=mk(name,models_root); r1=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
x,sr=sf.read(wav,dtype="float32"); txt,dt=decode(rc,x)
r2=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps({"model":name,"rss_before_load_mb":round(r0/1024,1),"rss_after_load_mb":round(r1/1024,1),"peak_rss_after_decode_mb":round(r2/1024,1),"clip_s":round(len(x)/sr,2),"decode_s":round(dt,2),"text":txt}))
