"""Read-only analysis of the supplied pre-change evaluation; no inference."""
import csv,json,re,math,hashlib
from collections import Counter,defaultdict
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

SOURCE=Path('C:/Users/daugh/EvalReports/eval_20260923_232143')
OUT=Path(__file__).resolve().parent/'eval_gap_20260923_232143'
OUT.mkdir(exist_ok=True)
MODELS=['best_ap50_95_ckpt','best_ap50_ckpt','latest_ckpt']

def main():
    rows=list(csv.DictReader((SOURCE/'per_image.csv').open(newline='',encoding='utf-8-sig')))
    by=defaultdict(dict)
    for row in rows:
        for key in ('gt_count','pred_count','tp','fp','fn','should_kick','did_kick'):row[key]=int(row[key])
        by[row['image']][row['model']]=row
    attrs={}
    for name,records in by.items():
        r=records['latest_ckpt'];p=Path(r['image_path'])
        with Image.open(p) as im:w,h=im.size
        lp=Path(str(p).replace('val\\images\\','val\\labels\\')).with_suffix('.txt')
        boxes=[]
        for line in lp.read_text(encoding='utf-8-sig').splitlines():
            v=list(map(float,line.split()))
            if len(v)==5:
                c,x,y,bw,bh=v;boxes.append(dict(cls=int(c),x=x,y=y,w=bw,h=bh,
                    model_w=bw*w*640/max(w,h),model_h=bh*h*640/max(w,h)))
            elif len(v)>=7:
                xs=v[1::2];ys=v[2::2];bw=max(xs)-min(xs);bh=max(ys)-min(ys)
                boxes.append(dict(cls=int(v[0]),x=(max(xs)+min(xs))/2,y=(max(ys)+min(ys))/2,w=bw,h=bh,
                    model_w=bw*w*640/max(w,h),model_h=bh*h*640/max(w,h)))
        assert len(boxes)==r['gt_count'],name
        camera=re.search(r'cam(\d+)',name)
        attrs[name]=dict(camera=camera.group(1) if camera else 'other',width=w,height=h,boxes=boxes,
            date=name[:8],all_fn=all(v['fn']>0 for v in records.values()),
            all_escape=all(v['should_kick'] and not v['did_kick'] for v in records.values()))
    def aggregate(m,group):
        acc=defaultdict(Counter)
        for name,records in by.items():
            a=attrs[name];r=records[m];key=group(a,r)
            if key is None:continue
            v=acc[key];v.update(images=1,positive=int(r['gt_count']>0),negative=int(r['gt_count']==0),
                gt=r['gt_count'],tp=r['tp'],fn=r['fn'],fp=r['fp'],
                escapes=int(r['should_kick'] and not r['did_kick']),
                false_alarm=int(not r['should_kick'] and r['did_kick']),
                partial=int(r['tp']>0 and r['fn']>0),any_fn=int(r['fn']>0))
        return {k:{**v,'recall':round(v['tp']/v['gt'],4) if v['gt'] else None,
            'precision':round(v['tp']/(v['tp']+v['fp']),4) if v['tp']+v['fp'] else None} for k,v in acc.items()}
    def size(a,r):
        if len(a['boxes'])!=1:return None
        b=a['boxes'][0];s=math.sqrt(b['model_w']*b['model_h'])
        return '<16' if s<16 else '16-31' if s<32 else '32-63' if s<64 else '64+'
    out=dict(source=str(SOURCE),source_sha256={n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ('run.json','summary.csv','per_class.csv','per_image.csv')},
        cameras={m:aggregate(m,lambda a,r:a['camera']) for m in MODELS},
        single_gt_size={m:aggregate(m,size) for m in MODELS},
        multiplicity=aggregate('latest_ckpt',lambda a,r:str(r['gt_count'])),
        common_fn_images=sum(a['all_fn'] for a in attrs.values()),
        common_escape_images=sum(a['all_escape'] for a in attrs.values()),
        common_fn_cameras=dict(Counter(a['camera'] for a in attrs.values() if a['all_fn'])),
        common_escape_cameras=dict(Counter(a['camera'] for a in attrs.values() if a['all_escape'])),
        attributes=attrs)
    (OUT/'analysis.json').write_text(json.dumps(out,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k not in ('attributes','source_sha256')},indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    picks={}
    for cam in sorted(set(a['camera'] for a in attrs.values())):
        candidates=[n for n in by if attrs[n]['camera']==cam and by[n]['latest_ckpt']['fn']>0]
        candidates.sort(key=lambda n:(not attrs[n]['all_escape'],not attrs[n]['all_fn'], -by[n]['latest_ckpt']['fn'],n))
        # Spread over time instead of taking nine adjacent frames of one part.
        selected=[];events=set()
        for n in candidates:
            event=n[:13]
            if event in events:continue
            selected.append(n);events.add(event)
            if len(selected)==9:break
        if selected:picks['miss_cam'+cam]=selected
    negatives=[n for n in by if by[n]['latest_ckpt']['gt_count']==0 and by[n]['latest_ckpt']['fp']>0]
    negatives.sort(key=lambda n:(attrs[n]['camera'],-by[n]['latest_ckpt']['fp'],n))
    picks['false_alarms']=negatives[::max(1,len(negatives)//15)][:15]
    partials=[n for n in by if by[n]['latest_ckpt']['tp']>0 and by[n]['latest_ckpt']['fn']>0]
    partials.sort(key=lambda n:(attrs[n]['camera'],n))
    picks['partial_misses']=partials[::max(1,len(partials)//12)][:12]
    for key,names in picks.items():
        sheet=Image.new('RGB',(1152,426*math.ceil(len(names)/3)),'#101b26')
        for i,n in enumerate(names):
            r=by[n]['latest_ckpt'];im=Image.open(SOURCE/'annotated/latest_ckpt'/n).convert('RGB');im.thumbnail((384,384))
            x=(i%3)*384;y=(i//3)*426;sheet.paste(im,(x+(384-im.width)//2,y+42))
            d=ImageDraw.Draw(sheet);d.text((x+5,y+2),n,font=font,fill='white')
            d.text((x+5,y+21),f"GT {r['gt_count']} TP {r['tp']} FP {r['fp']} FN {r['fn']} | all miss {attrs[n]['all_fn']}",font=font,fill='#ffce77')
        sheet.save(OUT/(key+'.jpg'),quality=94)
    (OUT/'selections.json').write_text(json.dumps(picks,indent=2))

if __name__=='__main__':main()
