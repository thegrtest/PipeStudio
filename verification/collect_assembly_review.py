"""Collect completed assembly runs with local YAMLs and a reference review page."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from assembly_generate import complete,copy_or_link,finalize,write_schema
from assembly_plan import DEFECT_CLASSES,PART_CLASSES
from verify_assembly_track import verify


def collect(sources,output,reference=None):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Use a new collection directory: '+str(output))
    loaded=[];ids=set()
    # Check all inputs before creating the destination.
    for source in sources:
        source=Path(source).resolve();plan=json.loads((source/'plan.json').read_text(encoding='utf-8'))
        verify(source)
        for row in plan['rows']:
            if row['sample_id'] in ids:raise ValueError('Duplicate sample ID: '+row['sample_id'])
            ids.add(row['sample_id'])
        loaded.append((source,plan))
    output.mkdir(parents=True)
    rows=[];receipts=[]
    for source,plan in loaded:
        accepted=[r for r in plan['rows'] if complete(source,r)]
        rows.extend(accepted)
        receipts.append(dict(source=str(source),frames=len(accepted),rejected=len(plan['rows'])-len(accepted),
                             plan_sha256=hashlib.sha256((source/'plan.json').read_bytes()).hexdigest(),settings=plan['settings']))
        for row in accepted:
            info=json.loads((source/'metadata'/(row['sample_id']+'.json')).read_text(encoding='utf-8'))
            files=set(info['sha256'])|{a['mask'] for a in info['parts']+info['annotations']}
            # Retain also fully hidden diagnostic masks, for reproducible review.
            files.update(p.relative_to(source).as_posix() for p in (source/'masks').glob(row['sample_id']+'_*.png'))
            files.add('metadata/'+row['sample_id']+'.json')
            for name in files:copy_or_link(source/name,output/name)
    plan=dict(settings={'kind':'verified_collection','count':len(rows)},rows=rows)
    (output/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    for root,names in ((output,DEFECT_CLASSES),(output/'tracking',PART_CLASSES)):
        write_schema(root,names);shutil.copyfile(root/'dataset.yaml',root/'data.yaml')
    finalize(output,plan)
    result=verify(output)
    (output/'collection.json').write_text(json.dumps(dict(sources=receipts,validation=result),indent=2),encoding='utf-8')
    # Preserve the earlier conveyor training choice as an optional one-class
    # export, with exact same image and box coordinates. Original labels remain.
    single=output/'defect_only';write_schema(single,('Defect',))
    shutil.copyfile(single/'dataset.yaml',single/'data.yaml')
    for row in rows:
        stem=row['sample_id'];copy_or_link(output/'all/images'/(stem+'.png'),single/'all/images'/(stem+'.png'))
        label=single/'all/labels'/(stem+'.txt');label.parent.mkdir(parents=True,exist_ok=True)
        original=(output/'all/labels'/(stem+'.txt')).read_text(encoding='utf-8').splitlines()
        label.write_text(''.join('0 '+' '.join(line.split()[1:])+'\n' for line in original),encoding='utf-8')
    for split in ('train','val'):shutil.copyfile(output/(split+'.txt'),single/(split+'.txt'))
    (single/'mapping.json').write_text(json.dumps({'source_classes':list(DEFECT_CLASSES),'destination':{'0':'Defect'},'frames':len(rows)},indent=2),encoding='utf-8')
    if reference:
        target=output/'reference.jpg';shutil.copy2(reference,target)
        page=output/'index.html';text=page.read_text(encoding='utf-8')
        text=text.replace('<title>Assembly track · Pipe Studio</title>','<title>Warm LED track · Pipe Studio</title>')
        text=text.replace('<h1>Inert assembly · Four-bar inspection track</h1>', '<h1>Warm LED track · 1920 × 1200</h1>')
        text=text.replace('svg{position:absolute;','.frame svg{position:absolute;')
        text=text.replace('.hide svg{display:none}', '.hide .frame svg{display:none}')
        start=text.index('<p>Native 1920')
        end=text.index('</p>',start)+4
        text=text[:start]+('<p>Rendered brass/copper assemblies on an AI-cleaned photographic background. '
            'Warm broad, balanced and four-line illumination. Blue boxes: shell/ferrule; coral: geometric defect support. '
            'Clean controls have empty defect labels. This visual review does not establish detector accuracy.</p>'
            '<details open><summary>Real reference</summary><img style="max-width:960px" src="reference.jpg">'
            '<svg style="display:block;width:100%;max-width:960px" viewBox="240 675 640 140">'
            '<image href="reference.jpg" width="1920" height="1200"/></svg></details>'
            '<p><a href="defect_only/data.yaml">One-class Defect dataset</a> · '
            '<a href="data.yaml">Four defect classes</a> · <a href="tracking/data.yaml">Shell/ferrule tracking</a></p>')+text[end:]
        for row in rows:
            info=json.loads((output/'metadata'/(row['sample_id']+'.json')).read_text(encoding='utf-8'))
            text=text.replace(html.escape(row['sample_id'])+' ·',html.escape(row['sample_id'])+' · '+info['recipe']['lighting']+' ·')
            boxes=[p['bbox_xywh'] for p in info['parts']]
            x=max(0,min(b[0] for b in boxes)-25);y=max(0,min(b[1] for b in boxes)-25)
            right=min(info['width'],max(b[0]+b[2] for b in boxes)+25)
            bottom=min(info['height'],max(b[1]+b[3] for b in boxes)+25)
            crop=(f'<svg style="display:block;width:100%;margin-top:12px" viewBox="{x} {y} {right-x} {bottom-y}">'
                  f'<image href="{info["image"]}" width="{info["width"]}" height="{info["height"]}"/></svg>')
            needle='<p>'+html.escape(row['sample_id'])+' ·'
            text=text.replace(needle,crop+needle)
        page.write_text(text,encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    args=parser.parse_args()
    print(json.dumps(collect(args.source,args.output,args.reference),indent=2))
