"""Standalone Pipe Studio UI. Blender runs as a hidden, persistent render worker."""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import uuid

from PIL import Image, ImageTk, ImageDraw
from app_model import DEFAULTS, LIMITS, PRESETS, validate_settings, front_angle
from geometry import PipeSpec, random_spec


def project_root():
    start=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    for candidate in (start,*start.parents):
        if (candidate/'pipe_studio.py').is_file():
            return candidate
    raise RuntimeError('Pipe Studio renderer files are missing. Keep the application inside its project folder.')


ROOT=project_root()
BG='#11171e'; PANEL='#1b242e'; FIELD='#26333f'; TEXT='#edf2f6'; MUTED='#a6b6c5'; ACCENT='#edb86a'
BLENDER=Path(r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe')


def atomic_json(path,data):
    path=Path(path); temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8'); temporary.replace(path)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}


class ScrollPage(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.canvas=tk.Canvas(self,bg=PANEL,highlightthickness=0,width=350)
        bar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side='left',fill='both',expand=True); bar.pack(side='right',fill='y')
        self.content=ttk.Frame(self.canvas,padding=(17,15,15,20))
        self.item=self.canvas.create_window((0,0),window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.item,width=e.width))
        self.bind_all('<MouseWheel>',self.wheel,add='+')
    def wheel(self,event):
        if self.winfo_ismapped() and self.winfo_rootx()<=event.x_root<self.winfo_rootx()+self.winfo_width() and self.winfo_rooty()<=event.y_root<self.winfo_rooty()+self.winfo_height():
            self.canvas.yview_scroll(int(-event.delta/120)*3,'units')


class PipeApp(tk.Tk):
    def __init__(self,auto_start=True):
        super().__init__()
        self.title('Pipe Studio | Tapered metal pipes')
        if (ROOT/'assets'/'pipe.ico').exists():
            self.iconbitmap(str(ROOT/'assets'/'pipe.ico'))
        self.configure(bg=BG)
        self.geometry('1480x940'); self.minsize(1120,760)
        self.loading=True; self.vars={}; self.entries={}; self.entry_formats={}
        self.pending_preview=False; self.pending_export=None; self.active=None; self.handled=None
        self.proc=None; self.session=None; self.preview_image=None; self.preview_mask=None; self.preview_info=None
        self.reference_image=None; self.reference_path=None; self.render_photo=None; self.debounce=None
        self.last_export=None; self.worker_error=None; self.closed=False; self.preview_counter=0
        self._style()
        saved=read_json(ROOT/'desktop_settings.json')
        try:
            values=validate_settings(saved)
        except ValueError:
            values=dict(DEFAULTS)
        for key,value in values.items():
            var=tk.StringVar(value=value) if isinstance(value,str) else tk.DoubleVar(value=value)
            self.vars[key]=var
            var.trace_add('write',lambda *_,k=key:self.changed(k))
        self.auto_preview=tk.BooleanVar(value=True)
        self.mask_display=tk.BooleanVar(value=False); self.box_display=tk.BooleanVar(value=False)
        self.reference_display=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value='Starting renderer…')
        self.preview_status=tk.StringVar(value='Ray-traced preview')
        self.export_count=tk.IntVar(value=12); self.clean_chance=tk.DoubleVar(value=.2)
        self.output_dir=tk.StringVar(value=str(ROOT/'exports'))
        self.front_only=tk.BooleanVar(value=True)
        self._build()
        self.loading=False; self.update_buttons()
        sample=ROOT/'examples'/'images'/'dent.png'
        if sample.exists():
            self.preview_image=Image.open(sample).convert('RGB')
            self.preview_status.set('Example render • updating to your controls')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(150,self.draw_preview)
        self.bind('<Control-Return>',lambda e:self.request_preview())
        self.bind('<Control-s>',lambda e:self.save_preset())
        self.bind('<F5>',lambda e:self.request_preview())
        if auto_start:
            self.after(200,self.start_worker)
        self.after(200,self.poll)
        self.after(350,self.show_window)

    def report_callback_exception(self,exc,value,tb):
        logging.error('UI callback failed: %s',''.join(traceback.format_exception(exc,value,tb)))
        if hasattr(self,'status'):
            self.status.set('An action failed. Details were saved to application.log.')

    def _style(self):
        self.option_add('*Font',('Segoe UI',10))
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('.',background=PANEL,foreground=TEXT,fieldbackground=FIELD,borderwidth=0)
        style.configure('TFrame',background=PANEL)
        style.configure('TLabel',background=PANEL,foreground=TEXT)
        style.configure('Muted.TLabel',foreground=MUTED,font=('Segoe UI',9))
        style.configure('Section.TLabel',font=('Segoe UI Semibold',11))
        style.configure('TNotebook',background=PANEL,tabmargins=(0,0,0,0))
        style.configure('TNotebook.Tab',padding=(11,12),background=PANEL,foreground=MUTED)
        style.map('TNotebook.Tab',background=[('selected',FIELD)],foreground=[('selected',ACCENT)])
        style.configure('TButton',padding=(11,9),background=FIELD,foreground=TEXT)
        style.map('TButton',background=[('active','#364858'),('disabled',PANEL)],foreground=[('disabled','#667585')])
        style.configure('Accent.TButton',background=ACCENT,foreground='#171d25',font=('Segoe UI Semibold',10))
        style.map('Accent.TButton',background=[('active','#f5cd94')])
        style.configure('TEntry',padding=5,fieldbackground=FIELD,foreground=TEXT,insertcolor=TEXT)
        style.configure('TCombobox',padding=5,fieldbackground=FIELD,foreground=TEXT,arrowcolor=TEXT)
        style.map('TCombobox',fieldbackground=[('readonly',FIELD)],foreground=[('readonly',TEXT)])
        style.configure('TCheckbutton',background=PANEL,foreground=TEXT,indicatorbackground=FIELD)
        style.map('TCheckbutton',background=[('active',PANEL)])
        style.configure('Horizontal.TScale',background=PANEL,troughcolor=FIELD,sliderlength=18)
        style.configure('TProgressbar',troughcolor=FIELD,background=ACCENT)
        style.configure('Vertical.TScrollbar',background=FIELD,troughcolor=PANEL,arrowcolor=MUTED)

    def _build(self):
        header=tk.Frame(self,bg=BG); header.pack(fill='x',padx=25,pady=(20,17))
        brand=tk.Frame(header,bg=BG); brand.pack(side='left')
        tk.Label(brand,text='PIPE STUDIO',bg=BG,fg=TEXT,font=('Segoe UI Semibold',23)).pack(anchor='w')
        tk.Label(brand,text='Tapered metal pipes · shape, defects, and light',bg=BG,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w')
        ttk.Button(header,text='Open exports',command=self.open_exports).pack(side='right',padx=(8,0))
        ttk.Button(header,text='Load setup',command=self.load_preset).pack(side='right',padx=(8,0))
        ttk.Button(header,text='Save setup',command=self.save_preset).pack(side='right',padx=(8,0))
        body=tk.Frame(self,bg=BG); body.pack(fill='both',expand=True,padx=22,pady=(0,12))
        controls=tk.Frame(body,bg=PANEL,width=386); controls.pack(side='left',fill='y',padx=(0,15)); controls.pack_propagate(False)
        top=ttk.Frame(controls,padding=(18,15)); top.pack(fill='x')
        ttk.Label(top,text='LOOK PRESET',style='Muted.TLabel').pack(anchor='w',pady=(0,6))
        self.preset_name=tk.StringVar(value='Soft studio')
        preset=ttk.Combobox(top,textvariable=self.preset_name,values=list(PRESETS),state='readonly')
        preset.pack(fill='x'); preset.bind('<<ComboboxSelected>>',lambda e:self.apply_values(PRESETS[self.preset_name.get()]))
        notebook=ttk.Notebook(controls); notebook.pack(fill='both',expand=True)
        pages={name:ScrollPage(notebook) for name in ('Defect','Light','Pipe','Export')}
        for name,page in pages.items():
            notebook.add(page,text=name)
        self.notebook=notebook
        defect=pages['Defect'].content
        ttk.Label(defect,text='Choose a surface condition',style='Section.TLabel').pack(anchor='w',pady=(0,12))
        row=ttk.Frame(defect); row.pack(fill='x',pady=(0,15)); self.defect_buttons={}
        for kind,label in [('NONE','Clean'),('DENT','Dent'),('FOLD','Fold')]:
            button=ttk.Button(row,text=label,command=lambda k=kind:self.vars['defect'].set(k))
            button.pack(side='left',fill='x',expand=True,padx=2); self.defect_buttons[kind]=button
        self.slider(defect,'position','Position along pipe',100,'%')
        self.slider(defect,'depth','Depth / local radius',100,'%')
        self.slider(defect,'width','Length / pipe length',100,'%')
        self.slider(defect,'arc','Width around pipe',1,'°')
        self.slider(defect,'angle','Rotate defect around pipe',1,'°')
        self.slider(defect,'irregularity','Irregularity',100,'%')
        ttk.Button(defect,text='Bring defect to camera',command=self.bring_front).pack(fill='x',pady=(3,7))
        ttk.Button(defect,text='Generate another defect',command=self.randomize).pack(fill='x')
        seedrow=ttk.Frame(defect); seedrow.pack(fill='x',pady=12)
        ttk.Label(seedrow,text='Repeatable seed',style='Muted.TLabel').pack(side='left')
        ttk.Entry(seedrow,textvariable=self.vars['seed'],width=12).pack(side='right')
        light=pages['Light'].content
        ttk.Label(light,text='Metal and reflections',style='Section.TLabel').pack(anchor='w',pady=(0,12))
        for key,label,factor,suffix in [('roughness','Surface roughness',100,'%'),('texture_strength','Brushed grain',100,'%'),
                ('wear','Surface variation',100,'%'),('key_angle','Light direction',1,'°'),
                ('light_softness','Reflection softness',1,''),('key_power','Key light',1,'W'),
                ('fill_power','Fill light',1,'W'),('exposure','Exposure',1,'EV'),('color_cast','Light tint',1,''),
                ('sensor_noise','Camera noise',100,'%')]:
            self.slider(light,key,label,factor,suffix)
        ttk.Label(light,text='Backdrop',style='Muted.TLabel').pack(anchor='w',pady=(5,5))
        ttk.Combobox(light,textvariable=self.vars['background'],values=['GREY','DARK','GREEN'],state='readonly').pack(fill='x')
        pipe=pages['Pipe'].content
        ttk.Label(pipe,text='Hollow pipe shape',style='Section.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Label(pipe,text='Relative scene units · both ends are open',style='Muted.TLabel').pack(anchor='w',pady=(0,14))
        for key,label,factor,suffix in [('length','Length',1,''),('radius','Inlet radius',1,''),
                ('end_ratio','Outlet / inlet radius',100,'%'),('wall_ratio','Wall / inlet radius',100,'%'),
                ('taper_start','Taper starts',100,'%'),('taper_end','Taper ends',100,'%')]:
            self.slider(pipe,key,label,factor,suffix)
        ttk.Label(pipe,text='Camera',style='Section.TLabel').pack(anchor='w',pady=(12,12))
        row=ttk.Frame(pipe); row.pack(fill='x',pady=(0,10))
        for label,values in [('Side',{'camera_yaw':0,'camera_elevation':5}),('Oblique',{'camera_yaw':22,'camera_elevation':16}),('Reverse',{'camera_yaw':158,'camera_elevation':16})]:
            ttk.Button(row,text=label,command=lambda v=values:self.apply_values(v)).pack(side='left',expand=True,fill='x',padx=2)
        self.slider(pipe,'camera_yaw','Orbit',1,'°'); self.slider(pipe,'camera_elevation','Elevation',1,'°')
        self.slider(pipe,'focus_blur','Focus blur',100,'%')
        export=pages['Export'].content
        ttk.Label(export,text='Image quality',style='Section.TLabel').pack(anchor='w',pady=(0,12))
        for key,label,items in [('resolution','Width (pixels)',[1280,1920,2560]),('samples','Render samples',[32,96,192])]:
            ttk.Label(export,text=label,style='Muted.TLabel').pack(anchor='w',pady=(7,5))
            ttk.Combobox(export,textvariable=self.vars[key],values=items,state='readonly').pack(fill='x')
        ttk.Button(export,text='Export current image',style='Accent.TButton',command=lambda:self.export(False)).pack(fill='x',pady=(18,22))
        ttk.Label(export,text='Randomized batch',style='Section.TLabel').pack(anchor='w',pady=(0,12))
        row=ttk.Frame(export); row.pack(fill='x',pady=5)
        ttk.Label(row,text='Image count').pack(side='left')
        ttk.Spinbox(row,from_=1,to=1000,textvariable=self.export_count,width=8).pack(side='right')
        ttk.Label(export,text='Clean image probability',style='Muted.TLabel').pack(anchor='w',pady=(12,4))
        ttk.Scale(export,from_=0,to=1,variable=self.clean_chance).pack(fill='x')
        ttk.Checkbutton(export,text='Keep defects near camera',variable=self.front_only).pack(anchor='w',pady=12)
        ttk.Button(export,text='Generate batch',command=lambda:self.export(True)).pack(fill='x',pady=(0,16))
        ttk.Label(export,text='Export folder',style='Muted.TLabel').pack(anchor='w',pady=(10,5))
        ttk.Entry(export,textvariable=self.output_dir).pack(fill='x')
        ttk.Button(export,text='Choose folder…',command=self.choose_output).pack(fill='x',pady=(7,13))
        ttk.Label(export,text='Images + masks + YOLO labels\nSettings and seeds saved with every image.',style='Muted.TLabel',wraplength=300).pack(anchor='w')
        bottom=ttk.Frame(controls,padding=(17,12)); bottom.pack(fill='x')
        ttk.Checkbutton(bottom,text='Update preview automatically',variable=self.auto_preview,command=self.auto_changed).pack(anchor='w',pady=(0,10))
        ttk.Button(bottom,text='Update preview   F5',style='Accent.TButton',command=self.request_preview).pack(fill='x')
        viewer=tk.Frame(body,bg=PANEL); viewer.pack(side='left',fill='both',expand=True)
        toolbar=ttk.Frame(viewer,padding=(18,12)); toolbar.pack(fill='x')
        ttk.Label(toolbar,textvariable=self.preview_status,style='Section.TLabel').pack(side='left')
        ttk.Button(toolbar,text='Reference photo…',command=self.load_reference).pack(side='right')
        toggles=ttk.Frame(viewer,padding=(18,0,18,9)); toggles.pack(fill='x')
        for text,var in [('Defect mask',self.mask_display),('Bounding box',self.box_display),('Compare reference',self.reference_display)]:
            ttk.Checkbutton(toggles,text=text,variable=var,command=self.draw_preview).pack(side='left',padx=(0,20))
        self.canvas=tk.Canvas(viewer,bg='#141c24',highlightthickness=0,cursor='fleur')
        self.canvas.pack(fill='both',expand=True,padx=12,pady=(0,5))
        self.canvas.bind('<Configure>',lambda e:self.draw_preview())
        self.canvas.bind('<ButtonPress-1>',self.drag_start); self.canvas.bind('<B1-Motion>',self.drag_move)
        self.canvas.bind('<ButtonRelease-1>',self.drag_end)
        footer=ttk.Frame(viewer,padding=(18,12)); footer.pack(fill='x')
        ttk.Label(footer,text='Drag to rotate · release to render   |   Lighting presets are adjustable approximations.',style='Muted.TLabel').pack(side='left')
        statusbar=tk.Frame(self,bg=BG); statusbar.pack(fill='x',padx=24,pady=(0,17))
        tk.Label(statusbar,textvariable=self.status,bg=BG,fg=MUTED,anchor='w').pack(side='left',fill='x',expand=True)
        self.stop_button=ttk.Button(statusbar,text='Stop after current image',command=self.cancel_export)
        self.stop_button.pack(side='right'); self.stop_button.configure(state='disabled')
        ttk.Button(statusbar,text='Export image',style='Accent.TButton',command=lambda:self.export(False)).pack(side='right',padx=10)

    def slider(self,parent,key,label,factor=1,suffix=''):
        frame=ttk.Frame(parent); frame.pack(fill='x',pady=(0,12))
        line=ttk.Frame(frame); line.pack(fill='x')
        ttk.Label(line,text=label).pack(side='left')
        display=tk.StringVar(); self.entries[key]=display; self.entry_formats[key]=(factor,suffix)
        entry=ttk.Entry(line,textvariable=display,width=8,justify='right'); entry.pack(side='right')
        entry.bind('<Return>',lambda e,k=key:self.commit_entry(k)); entry.bind('<FocusOut>',lambda e,k=key:self.commit_entry(k))
        low,high=LIMITS[key]
        ttk.Scale(frame,from_=low,to=high,variable=self.vars[key]).pack(fill='x',pady=(5,0))
        self.format_entry(key)

    def format_entry(self,key):
        if key in self.entries:
            factor,suffix=self.entry_formats[key]
            try:
                self.entries[key].set(f'{self.vars[key].get()*factor:.2f}'.rstrip('0').rstrip('.')+suffix)
            except tk.TclError:
                pass

    def commit_entry(self,key):
        factor,suffix=self.entry_formats[key]
        try:
            text=self.entries[key].get().strip().replace(suffix,'') if suffix else self.entries[key].get().strip()
            value=float(text)/factor; low,high=LIMITS[key]
            self.vars[key].set(max(low,min(high,value)))
        except (ValueError,tk.TclError):
            self.format_entry(key)

    def changed(self,key):
        self.format_entry(key)
        if self.loading:
            return
        self.update_buttons()
        if self.debounce:
            self.after_cancel(self.debounce)
        self.debounce=self.after(800,self.auto_changed)

    def auto_changed(self):
        self.debounce=None
        if self.auto_preview.get():
            self.request_preview()
        else:
            self.status.set('Controls changed. Click Update preview.')

    def settings(self):
        return validate_settings({key:var.get() for key,var in self.vars.items()})

    def apply_values(self,values):
        self.loading=True
        try:
            for key,value in values.items():
                if key in self.vars:
                    self.vars[key].set(value)
        finally:
            self.loading=False
        self.update_buttons(); self.auto_changed()

    def update_buttons(self):
        for kind,button in getattr(self,'defect_buttons',{}).items():
            button.configure(style='Accent.TButton' if self.vars['defect'].get()==kind else 'TButton')

    def bring_front(self):
        try:
            self.vars['angle'].set(front_angle(self.settings()))
        except (ValueError,tk.TclError) as exc:
            self.status.set(str(exc))

    def randomize(self):
        try:
            values=self.settings(); spec=PipeSpec(**{k:values[k] for k in PipeSpec.__dataclass_fields__})
            self.apply_values(asdict(random_spec(spec,values['seed']+1,front_angle(values))))
        except (ValueError,tk.TclError) as exc:
            self.status.set(str(exc))

    def drag_start(self,event):
        self.drag_origin=(event.x,event.y,self.vars['camera_yaw'].get(),self.vars['camera_elevation'].get())

    def drag_move(self,event):
        if not hasattr(self,'drag_origin'):
            return
        x,y,yaw,elevation=self.drag_origin
        self.loading=True
        self.vars['camera_yaw'].set(max(-175,min(175,yaw+(event.x-x)*.18)))
        self.vars['camera_elevation'].set(max(0,min(70,elevation-(event.y-y)*.12)))
        self.loading=False
        self.status.set('Release to render this camera angle.')

    def drag_end(self,event):
        if hasattr(self,'drag_origin'):
            del self.drag_origin
            self.request_preview()

    def show_window(self):
        self.deiconify(); self.lift(); self.attributes('-topmost',True)
        self.after(650,lambda:self.attributes('-topmost',False))

    def start_worker(self):
        if self.proc and self.proc.poll() is None:
            return
        blender=BLENDER
        config=read_json(ROOT/'desktop_config.json')
        if config.get('blender'):
            blender=Path(config['blender'])
        if not blender.is_file():
            location=filedialog.askopenfilename(title='Locate Blender executable',filetypes=[('Blender','blender.exe')])
            if not location:
                self.status.set('Blender was not selected. The preview renderer is unavailable.'); return
            blender=Path(location); atomic_json(ROOT/'desktop_config.json',{'blender':str(blender)})
        self.session=ROOT/'.cache'/'desktop-sessions'/uuid.uuid4().hex[:12]
        self.session.mkdir(parents=True,exist_ok=True)
        atomic_json(ROOT/'desktop_runtime.json',{'pid':os.getpid(),'session':str(self.session),'executable':sys.executable})
        try:
            with (self.session/'worker.log').open('w',encoding='utf-8') as log:
                self.proc=subprocess.Popen([str(blender),'--background','--factory-startup','--python-exit-code','1',
                    '--python',str(ROOT/'desktop_worker.py'),'--',str(self.session)],cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.worker_error=None; self.pending_preview=True
            self.status.set('Starting the background renderer…')
        except OSError as exc:
            self.worker_error=str(exc); self.status.set('Renderer could not start: '+str(exc))

    def request_preview(self):
        try:
            self.settings()
        except (ValueError,tk.TclError) as exc:
            self.status.set(str(exc)); return
        if not self.proc or self.proc.poll() is not None:
            self.start_worker()
        self.pending_preview=True
        self.status.set('Preview queued…' if self.active else 'Updating preview…')

    def dispatch(self,request):
        request['id']=uuid.uuid4().hex[:10]
        self.active=request; self.handled=None
        atomic_json(self.session/'request.json',request)
        self.status.set('Rendering preview…' if request['mode']=='preview' else 'Rendering export…')

    def poll(self):
        if self.closed:
            return
        try:
            if self.proc:
                state=read_json(self.session/'status.json')
                if self.proc.poll() is not None and not self.worker_error:
                    self.worker_error='Renderer stopped. Click Update preview to restart it.'
                    self.status.set(self.worker_error); self.active=None
                if state.get('state') in ('done','error') and self.active and state.get('id')==self.active['id']:
                    finished=self.active; self.active=None
                    if state['state']=='error':
                        self.worker_error=state.get('error','Render failed')
                        logging.error(self.worker_error)
                        self.status.set('Render failed. See application.log or restart the preview.')
                    elif finished['mode']=='preview':
                        self.worker_error=None
                        self.preview_image=Image.open(state['image']).convert('RGB')
                        self.preview_mask=Image.open(state['mask']).convert('L')
                        self.preview_info=state['metadata']; self.preview_counter+=1
                        self.preview_status.set(f"{self.preview_info['defect_type'].title()} · seed {self.preview_info['parameters']['seed']} · preview")
                        self.draw_preview()
                        self.status.set('Ready · '+state.get('device','renderer'))
                    else:
                        self.worker_error=None
                        result=state.get('result',{})
                        self.status.set(f"Export {result.get('state','finished')} · {result.get('completed',0)} image(s) saved")
                        self.stop_button.configure(state='disabled')
                if self.active and self.active['mode']=='export':
                    progress=read_json(Path(self.active['folder'])/'status.json')
                    self.status.set(f"Export: {progress.get('completed',0)} / {progress.get('total','?')} images · {progress.get('state','starting')}")
                if not self.active and self.proc.poll() is None and state.get('state') in ('ready','done','error'):
                    if self.pending_export:
                        request=self.pending_export; self.pending_export=None; self.dispatch(request)
                    elif self.pending_preview:
                        self.pending_preview=False
                        try:
                            self.dispatch({'mode':'preview','settings':self.settings()})
                        except (ValueError,tk.TclError) as exc:
                            self.status.set(str(exc))
        except Exception:
            logging.exception('Desktop poll error'); self.status.set('A preview error occurred. Details are in application.log.')
        self.after(200,self.poll)

    def export(self,batch):
        if self.pending_export or (self.active and self.active['mode']=='export'):
            self.status.set('An export is already running. Wait or stop it first.'); return
        try:
            values=self.settings(); count=int(self.export_count.get()) if batch else 1
            chance=float(self.clean_chance.get())
            if not 1<=count<=1000 or not 0<=chance<=1:
                raise ValueError('Choose 1–1000 images and a clean probability from 0 to 1.')
            folder=Path(self.output_dir.get()).expanduser()/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
            folder.mkdir(parents=True,exist_ok=False)
            atomic_json(folder/'job.json',{'settings':values,'count':count,'randomize':bool(batch),
                        'clean_fraction':chance,'front_only':self.front_only.get()})
            atomic_json(folder/'status.json',{'state':'queued','completed':0,'total':count})
            self.pending_export={'mode':'export','settings':values,'folder':str(folder)}
            self.last_export=folder; self.stop_button.configure(state='normal')
            self.status.set('Export queued. Your current controls were saved with it.')
            if not self.proc or self.proc.poll() is not None:
                self.start_worker()
        except (ValueError,OSError,tk.TclError) as exc:
            messagebox.showerror('Cannot export',str(exc))

    def cancel_export(self):
        if self.pending_export:
            folder=Path(self.pending_export['folder']); self.pending_export=None
            atomic_json(folder/'status.json',{'state':'cancelled','completed':0,'total':0})
            self.stop_button.configure(state='disabled'); self.status.set('Queued export cancelled.')
        elif self.active and self.active['mode']=='export':
            (Path(self.active['folder'])/'cancel.flag').touch()
            self.status.set('Stopping after the current image and mask finish…')

    def draw_preview(self):
        if not hasattr(self,'canvas'):
            return
        width,height=self.canvas.winfo_width(),self.canvas.winfo_height()
        if width<10 or height<10:
            return
        self.canvas.delete('all')
        if self.preview_image is None:
            self.canvas.create_text(width/2,height/2,text='Preparing your first preview…',fill=MUTED,font=('Segoe UI',14)); return
        rendered=self.preview_image.copy()
        if self.preview_mask and self.mask_display.get():
            overlay=Image.new('RGB',rendered.size,'#f1a64b')
            mask=self.preview_mask.point(lambda value:int(value*.45))
            rendered=Image.composite(overlay,rendered,mask)
        if self.preview_info and self.box_display.get() and self.preview_info.get('bbox_xywh'):
            x,y,w,h=self.preview_info['bbox_xywh']
            ImageDraw.Draw(rendered).rectangle((x,y,x+w,y+h),outline='#f5b95d',width=3)
        compare=self.reference_display.get() and self.reference_image is not None
        panel_width=(width-32)//2 if compare else width-24
        images=[('SYNTHETIC',rendered)]
        if compare:
            images.append(('REFERENCE',self.reference_image))
        self.render_photos=[]
        for index,(label,pil) in enumerate(images):
            available_h=height-48
            ratio=min(panel_width/pil.width,available_h/pil.height)
            resized=pil.resize((max(1,int(pil.width*ratio)),max(1,int(pil.height*ratio))),Image.Resampling.LANCZOS)
            photo=ImageTk.PhotoImage(resized); self.render_photos.append(photo)
            center=(12+panel_width/2)+(panel_width+8)*index if compare else width/2
            self.canvas.create_image(center,height/2+10,image=photo)
            if compare:
                self.canvas.create_text(center,18,text=label,fill=MUTED,font=('Segoe UI Semibold',10))

    def load_reference(self):
        path=filedialog.askopenfilename(title='Choose a reference photo',initialdir=str(ROOT.parent/'TestDataset'),
                                       filetypes=[('Images','*.jpg *.jpeg *.png *.bmp *.tif *.tiff')])
        if path:
            try:
                with Image.open(path) as source:
                    self.reference_image=source.convert('RGB')
                self.reference_path=path; self.reference_display.set(True); self.draw_preview()
            except OSError as exc:
                messagebox.showerror('Cannot open photo',str(exc))

    def choose_output(self):
        path=filedialog.askdirectory(title='Choose export folder',initialdir=self.output_dir.get())
        if path:
            self.output_dir.set(path)

    def open_exports(self):
        path=self.last_export or Path(self.output_dir.get())
        path.mkdir(parents=True,exist_ok=True); os.startfile(str(path))

    def save_preset(self):
        try:
            values=self.settings()
        except (ValueError,tk.TclError) as exc:
            messagebox.showerror('Cannot save setup',str(exc)); return
        directory=ROOT/'presets'; directory.mkdir(exist_ok=True)
        path=filedialog.asksaveasfilename(title='Save Pipe Studio setup',initialdir=str(directory),
                                         defaultextension='.json',filetypes=[('Pipe setup','*.json')])
        if path:
            atomic_json(path,values); self.status.set('Setup saved.')

    def load_preset(self):
        path=filedialog.askopenfilename(title='Load Pipe Studio setup',initialdir=str(ROOT/'presets'),filetypes=[('Pipe setup','*.json')])
        if path:
            try:
                values=validate_settings(json.loads(Path(path).read_text(encoding='utf-8')))
                self.apply_values(values)
            except (OSError,ValueError,TypeError) as exc:
                messagebox.showerror('Cannot load setup',str(exc))

    def close(self):
        if self.closed:
            return
        self.closed=True
        try:
            atomic_json(ROOT/'desktop_settings.json',self.settings())
        except Exception:
            logging.exception('Settings could not be saved')
        if self.active and self.active['mode']=='export':
            (Path(self.active['folder'])/'cancel.flag').touch()
        if self.pending_export:
            atomic_json(Path(self.pending_export['folder'])/'status.json',{'state':'cancelled','completed':0})
        if self.session:
            (self.session/'stop.flag').touch()
        self.destroy()


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--ui-test',action='store_true')
    args=parser.parse_args()
    instance_mutex=None
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        if not args.ui_test:
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
            kernel.CreateMutexW.restype=wintypes.HANDLE
            instance_mutex=kernel.CreateMutexW(None,False,'Local\\TaperedPipeStudioDesktopV2')
            if ctypes.get_last_error()==183:
                user=ctypes.windll.user32
                user.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]
                user.FindWindowW.restype=wintypes.HWND
                window=user.FindWindowW(None,'Pipe Studio | Tapered metal pipes')
                if window:
                    user.ShowWindow(window,9); user.SetForegroundWindow(window)
                return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    logging.basicConfig(filename=str(ROOT/'application.log'),level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        app=PipeApp()
        if args.ui_test:
            from PIL import ImageGrab
            started=time.time()
            phase=[0]
            def check():
                folder=ROOT/'verification'; folder.mkdir(exist_ok=True)
                try:
                    if phase[0]==0 and app.preview_counter>=1:
                        app.update()
                        x,y=app.winfo_rootx(),app.winfo_rooty()
                        ImageGrab.grab(bbox=(x,y,x+app.winfo_width(),y+app.winfo_height())).save(folder/'desktop-ui.png')
                        app.apply_values({**PRESETS['Inspection light'],'defect':'FOLD'})
                        phase[0]=1
                    elif phase[0]==1 and app.preview_counter>=2:
                        assert app.preview_info['defect_type']=='FOLD'
                        assert app.preview_info['parameters']['sensor_noise']>0
                        assert app.preview_info['visible_mask_pixels']>10
                        app.mask_display.set(True); app.box_display.set(True); app.draw_preview()
                        app.update()
                        x,y=app.winfo_rootx(),app.winfo_rooty()
                        ImageGrab.grab(bbox=(x,y,x+app.winfo_width(),y+app.winfo_height())).save(folder/'desktop-ui-mask.png')
                        app.export_count.set(2); app.loading=True
                        app.vars['resolution'].set(640); app.vars['samples'].set(16)
                        app.loading=False; app.output_dir.set(str(folder/'desktop-export'))
                        app.export(True); phase[0]=2
                    elif phase[0]==2 and app.last_export and read_json(app.last_export/'status.json').get('state')=='complete':
                        manifest=read_json(app.last_export/'manifest.json')
                        assert len(manifest['samples'])==2
                        atomic_json(folder/'desktop-ui-result.json',{'passed':True,'title':app.title(),
                               'visible':bool(app.winfo_viewable()),'preview':app.preview_info,'session':str(app.session),
                               'export':str(app.last_export),'export_count':len(manifest['samples'])})
                        app.loading=True
                        for key,value in DEFAULTS.items():
                            app.vars[key].set(value)
                        app.loading=False; app.close(); return
                    if time.time()-started>120:
                        raise TimeoutError(app.status.get())
                    app.after(250,check)
                except Exception:
                    atomic_json(folder/'desktop-ui-result.json',{'passed':False,'error':traceback.format_exc(),'status':app.status.get()})
                    app.close()
            app.after(500,check)
        app.mainloop()
    except Exception:
        logging.exception('Application startup failed')
        raise


if __name__=='__main__':
    main()
