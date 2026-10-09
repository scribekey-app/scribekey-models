# Mirrors /home/user/scribekey-models/bench/asr/extract.py; adds an output-root argument.
import pyarrow.parquet as pq, sys, io, numpy as np, soundfile as sf, json, os
src,name,n,root=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4]
pf=pq.ParquetFile(src); cols=pf.schema.names
tcol="transcription" if "transcription" in cols else "text"
rows=[];seen=0;stride=max(1,pf.metadata.num_rows//n)
os.makedirs(f"{root}/clips/{name}",exist_ok=True)
for b in pf.iter_batches(batch_size=64):
    for r in b.to_pylist():
        if seen%stride==0 and len(rows)<n:
            a=r["audio"] if "audio" in r else {"bytes":r["bytes"]}
            x,sr=sf.read(io.BytesIO(a["bytes"]),dtype="float32")
            p=f"{root}/clips/{name}/{len(rows):03d}.wav"; sf.write(p,x,sr)
            rows.append({"wav":p,"ref":r[tcol]})
        seen+=1
    if len(rows)>=n: break
json.dump(rows,open(f"{root}/clips/{name}.json","w"))
print(name,len(rows),"rows_in_shard",pf.metadata.num_rows,"stride",stride,"tcol",tcol,"audio_s",sum(sf.info(r["wav"]).duration for r in rows))
