"""Compare saved detector predictions against a fully covered image list.

Fixed-threshold precision/recall only, not COCO AP. Export native-image pixel
boxes AFTER reversing YOLOX letterbox scaling and AFTER NMS. Every evaluated
image needs an explicit entry, including images with no detections.
"""
import argparse
import hashlib
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import numpy as np
from PIL import Image
from yolox_readiness import parse_labels,camera_name,IMAGE_EXTS


def iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0]))
    y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=x*y
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union>0 else 0


def match(ground_truth,predictions,threshold=.25,iou_threshold=.5,known_classes=(0,1)):
    truth=[x for x in ground_truth if x['class_id'] in known_classes]
    preds=sorted((x for x in predictions if x['score']>=threshold and x['class_id'] in known_classes),key=lambda x:-x['score'])
    used=set();counts=defaultdict(Counter);failures=[];confusion=Counter()
    for pred in preds:
        candidates=[(iou(pred['bbox_xyxy'],gt['bbox_xyxy']),index) for index,gt in enumerate(truth)
                    if index not in used and gt['class_id']==pred['class_id']]
        overlap,index=max(candidates,default=(0,-1))
        cid=str(pred['class_id'])
        if overlap>=iou_threshold:
            used.add(index);counts[cid]['tp']+=1
        else:
            counts[cid]['fp']+=1;failures.append(dict(type='false_positive',prediction=pred))
            wrong=[gt for gt in truth if gt['class_id']!=pred['class_id'] and iou(gt['bbox_xyxy'],pred['bbox_xyxy'])>=iou_threshold]
            if wrong:confusion[f'{wrong[0]["class_id"]}->{pred["class_id"]}']+=1
    for index,gt in enumerate(truth):
        cid=str(gt['class_id']);counts[cid]['ground_truth']+=1
        if index not in used:
            counts[cid]['fn']+=1;failures.append(dict(type='false_negative',ground_truth=gt))
    return counts,failures,confusion


def score(root,document,threshold=.25,iou_threshold=.5,known_classes=(0,1)):
    root=Path(root).resolve()
    if (root/'all/images').is_dir():root=root/'all'
    metadata=document.get('metadata',{})
    if not re.fullmatch('[0-9a-fA-F]{64}',str(metadata.get('checkpoint_sha256',''))):
        raise ValueError('Record the actual checkpoint SHA256 before comparing evaluations')
    if metadata.get('box_space')!='native_xyxy' or not metadata.get('input_size') or 'nms_threshold' not in metadata:
        raise ValueError('Record native_xyxy box space, model input_size and nms_threshold')
    shape=metadata['input_size']
    if len(shape)!=2 or any(not isinstance(v,int) or isinstance(v,bool) or v<=0 for v in shape):
        raise ValueError('input_size must contain two positive pixel dimensions')
    floor=metadata.get('export_confidence_floor')
    if floor is None or not 0<=floor<=threshold or not 0<=metadata['nms_threshold']<=1:
        raise ValueError('Record an export_confidence_floor no higher than the scoring threshold and a valid NMS threshold')
    entries=document['images'];predicted={r['file_name']:r['detections'] for r in entries}
    if len(predicted)!=len(entries):raise ValueError('Duplicate prediction image entries')
    images={p.name:p for p in (root/'images').iterdir() if p.suffix.lower() in IMAGE_EXTS}
    if set(predicted)!=set(images):raise ValueError('Predictions must explicitly cover every image in this evaluation folder, including empty detections')
    total=defaultdict(Counter);groups=defaultdict(Counter);failure_queue=[];confusion=Counter()
    sizes=defaultdict(Counter);label_hash=hashlib.sha256()
    for name,path in sorted(images.items()):
        with Image.open(path) as im:width,height=im.size
        content=(root/'labels'/(path.stem+'.txt')).read_text(encoding='utf-8-sig')
        rows=parse_labels(content)
        label_hash.update(json.dumps([name,width,height,content]).encode())
        ground=[]
        for cid,x,y,w,h in rows:
            ground.append(dict(class_id=cid,bbox_xyxy=[(x-w/2)*width,(y-h/2)*height,(x+w/2)*width,(y+h/2)*height]))
        for p in predicted[name]:
            box=p['bbox_xyxy']
            if (p['class_id'] not in (0,1,2,3) or len(box)!=4 or not np.isfinite([p['score'],*box]).all()
                or not 0<=p['score']<=1 or box[2]<=box[0] or box[3]<=box[1]
                or min(box)<0 or box[2]>width or box[3]>height):raise ValueError('Invalid native prediction: '+name)
        counts,failures,wrong=match(ground,predicted[name],threshold,iou_threshold,known_classes)
        confusion.update(wrong)
        for cid,c in counts.items():total[cid].update(c);groups[f'{camera_name(path.stem)}/{cid}'].update(c)
        for gt in ground:
            if gt['class_id'] not in known_classes:continue
            b=gt['bbox_xyxy'];short=min(b[2]-b[0],b[3]-b[1])*640/max(width,height)
            band='<8' if short<8 else '8-16' if short<16 else '16-32' if short<32 else '>=32'
            key=f'{gt["class_id"]}/{band}px_at_640';sizes[key]['ground_truth']+=1
            missed=any(f.get('ground_truth')==gt for f in failures)
            sizes[key]['fn' if missed else 'tp']+=1
        failure_queue.extend(dict(image=str(path),camera=camera_name(path.stem),**f) for f in failures)
    def metrics(c):
        tp,fp,fn=c['tp'],c['fp'],c['fn']
        return dict(c,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)
    return dict(metadata=metadata,images=len(images),dataset_root=str(root),
                ground_truth_labels_sha256=label_hash.hexdigest(),confidence_threshold=threshold,iou_threshold=iou_threshold,
                evaluated_classes=list(known_classes),ignored_prediction_classes=[k for k in range(4) if k not in known_classes],
                definition='Fixed-threshold box metrics; not AP. Unknown stain annotations are excluded, not treated as verified negatives.',
                by_class={k:metrics(c) for k,c in total.items()},by_camera_class={k:metrics(c) for k,c in groups.items()},
                recall_by_thickness={k:metrics(c) for k,c in sizes.items()},
                wrong_class_overlap_counts=dict(confusion),failure_queue=failure_queue)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real',type=Path,required=True);parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--confidence',type=float,default=.25)
    parser.add_argument('--iou',type=float,default=.5);parser.add_argument('--classes',default='0,1')
    args=parser.parse_args()
    if not 0<=args.confidence<=1 or not 0<args.iou<=1:parser.error('Thresholds must be in [0,1], with IoU > 0')
    result=score(args.real,json.loads(args.predictions.read_text()),args.confidence,args.iou,tuple(int(v) for v in args.classes.split(',')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='failure_queue'},indent=2))
