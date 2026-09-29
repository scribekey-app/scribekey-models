import glob, json, time

import jiwer
import numpy as np
import sherpa_onnx
import soundfile as sf
from whisper_normalizer.english import EnglishTextNormalizer
from whisper_normalizer.basic import BasicTextNormalizer
en,basic=EnglishTextNormalizer(),BasicTextNormalizer()
def mk(d):
    return sherpa_onnx.OfflineRecognizer.from_transducer(encoder=f"{d}/encoder.int8.onnx",decoder=f"{d}/decoder.int8.onnx",joiner=f"{d}/joiner.int8.onnx",tokens=f"{d}/tokens.txt",model_type="nemo_transducer",num_threads=2)
rs={"v3":mk("v3"),"ultra":mk("ultra")}
rng=np.random.default_rng(1)
def load(p):
    x,sr=sf.read(p,dtype="float32"); assert sr==16000,sr; return x
out={}
for js in sorted(glob.glob("clips/*.json")):
    name=js.split("/")[-1][:-5]; rows=json.load(open(js)); norm=en if name.startswith(("libri","fl_en")) else basic
    pool=[load(r["wav"]) for r in rows]
    refs=[norm(r["ref"]) for r in rows]
    for cond in ("clean","babble5dB"):
        hyps={k:[] for k in rs}; dur=0; tm={k:0. for k in rs}
        for i,r in enumerate(rows):
            x=pool[i]
            if cond!="clean":
                b=np.zeros_like(x)
                for j in rng.choice(len(pool),3,replace=False):
                    y=pool[j]; y=np.resize(y,len(x)); b+=y
                g=np.sqrt(np.mean(x**2)/(np.mean(b**2)+1e-9)/10**(5/10)); x=x+g*b
            dur+=len(x)/16000
            for k,rc in rs.items():
                s=rc.create_stream(); s.accept_waveform(16000,x); t=time.time(); rc.decode_stream(s); tm[k]+=time.time()-t
                hyps[k].append(norm(s.result.text))
        keep=[i for i,r in enumerate(refs) if r.strip()]
        res={k:jiwer.wer([refs[i] for i in keep],[hyps[k][i] for i in keep]) for k in rs}
        # per-clip paired win/loss
        pc={k:[jiwer.wer(refs[i],hyps[k][i]) if hyps[k][i] else 1.0 for i in keep] for k in rs}
        d=np.array(pc["ultra"])-np.array(pc["v3"])
        out[f"{name}/{cond}"]={"n":len(keep),"audio_s":round(dur),"wer":{k:round(v*100,2) for k,v in res.items()},"ultra_better":int((d<0).sum()),"ultra_worse":int((d>0).sum()),"rtfx":{k:round(dur/tm[k],1) for k in rs}}
        print(name,cond,out[f"{name}/{cond}"],flush=True)
json.dump(out,open("bench_out.json","w"),indent=1)
