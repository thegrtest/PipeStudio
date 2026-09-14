"""Mode-aware presentation of shared Blender controls."""
def install(studio):
    def branch(cls,draw_flashlight):
        original=cls.draw
        def draw(self,context):
            if context.scene.pipe_studio.product_mode=='FLASHLIGHT':
                draw_flashlight(self,context)
            else:
                original(self,context)
        cls.draw=draw
    original_main=studio.PIPE_PT_main.draw
    def main(self,context):
        l=self.layout; p=context.scene.pipe_studio
        l.prop(p,'product_mode',expand=True)
        if p.product_mode=='PIPE':
            original_main(self,context)
            return
        l.label(text='Touching row · alternating brass/plastic ends' if p.environment=='BUTTON_TRACK' else 'Touching row · alternating bulb ends')
        row=l.row(align=True)
        row.operator('pipe.environment',text='Overhead track').preset='TRACK'
        row.operator('pipe.environment',text='Grazing track').preset='TRACK_GRAZING'
        l.operator('pipe.environment',text='Brass button track · 3 cameras').preset='BUTTON_TRACK'
        l.label(text='Scene: '+p.environment)
        row=l.row(align=True)
        row.operator('pipe.view',text='Camera view').preset='CURRENT'
        row.operator('render.render',text='Render preview')
        l.prop(p,'mask_view')
        l.operator('pipe.export',text='Export 3-camera set + labels' if p.environment=='BUTTON_TRACK' and p.flashlight_capture=='ALL' else 'Export current image + masks').randomize=False
        if context.scene.get('pipe_error'):
            l.label(text=context.scene['pipe_error'],icon='ERROR')
        if p.last_export:
            status=studio.read_status(p.last_export)
            l.label(text=f"{status.get('state','Ready')} · {status.get('completed',0)} / {status.get('total','?')}")
            if status.get('state') in ('starting','rendering'):
                l.operator('pipe.cancel',text='Stop after current camera set' if p.environment=='BUTTON_TRACK' else 'Stop after current image')
            l.operator('pipe.open',text='Open exports')
            l.operator('pipe.open',text='Latest image').image=True
    studio.PIPE_PT_main.draw=main
    studio.PIPE_PT_main.bl_label='Inspection Studio'
    def shape(self,context):
        for key in ('flashlight_count','flashlight_roll') if context.scene.pipe_studio.environment=='BUTTON_TRACK' else ('flashlight_count','flashlight_roll','battery_probability'):
            self.layout.prop(context.scene.pipe_studio,key)
        self.layout.label(text='Exterior only · seam at brass/plastic joint' if context.scene.pipe_studio.environment=='BUTTON_TRACK' else 'Battery absence is metadata, not a label.')
        if context.scene.pipe_studio.environment=='BUTTON_TRACK':
            self.layout.prop(context.scene.pipe_studio,'flashlight_length_scale')
            self.layout.label(text=f'Illustrative length: {2.792*context.scene.pipe_studio.flashlight_length_scale:.2f} × diameter')
            self.layout.prop(context.scene.pipe_studio,'crimp_tightness')
            self.layout.prop(context.scene.pipe_studio,'crimp_twist')
            self.layout.prop(context.scene.pipe_studio,'crimp_fold_depth')
    branch(studio.PIPE_PT_shape,shape)
    studio.PIPE_PT_shape.bl_label='Product geometry'
    def defect(self,context):
        l=self.layout; p=context.scene.pipe_studio
        flashlight=p.product_mode=='FLASHLIGHT'
        kinds=[('NONE','Clean'),('DENT','Dent'),('SCRATCH','Scratch')] if flashlight else [('NONE','Clean'),('DENT','Dent'),('FOLD','Fold')]
        row=l.row(align=True)
        for kind,label in kinds:
            row.operator('pipe.condition',text=label,depress=p.defect==kind).kind=kind
        if flashlight and p.environment=='BUTTON_TRACK':
            row=l.row(align=True)
            row.operator('pipe.condition',text='Shallow dent').kind='SHALLOW_DENT'
            row.operator('pipe.condition',text='Body twist',depress=p.defect=='TWIST').kind='TWIST'
            row=l.row(align=True)
            for kind,label in [('OPEN_CENTER','Open center'),('PROTRUDING_CRIMP','Protruding crimp')]:
                row.operator('pipe.condition',text=label,depress=p.defect==kind).kind=kind
        if flashlight:
            l.prop(p,'flashlight_layout')
            if p.flashlight_layout=='SINGLE':
                l.prop(p,'flashlight_index')
                if p.environment=='BUTTON_TRACK':
                    l.prop(p,'flashlight_region')
                elif p.defect!='SCRATCH':
                    l.prop(p,'flashlight_surface',expand=True)
            else:
                l.label(text='Most shells defective; one changes per click.' if p.environment=='BUTTON_TRACK' else 'Mixed row contains all 3 defect classes.')
                if p.environment=='BUTTON_TRACK':
                    l.label(text=f'Defective shells: {context.scene.get("button_row_defective_count",0)} / {p.flashlight_count}')
                    l.label(text=f'Next update: shell {context.scene.get("button_row_next_index",0)+1}')
        col=l.column(); col.enabled=p.defect!='NONE'
        if flashlight and p.environment=='BUTTON_TRACK':
            if p.defect=='TWIST':
                col.prop(p,'body_twist');col.prop(p,'body_twist_span')
            if p.defect=='OPEN_CENTER' or p.flashlight_layout=='MIXED':col.prop(p,'crimp_opening')
            if p.defect=='PROTRUDING_CRIMP' or p.flashlight_layout=='MIXED':
                col.prop(p,'crimp_lift');col.prop(p,'crimp_spread')
        if flashlight and p.defect=='TWIST':
            col.prop(p,'position',text='Twist center along body')
            row=l.row(align=True);row.prop(p,'seed');row.operator('pipe.randomize',text='Update one shell')
            return
        if p.defect in ('OPEN_CENTER','PROTRUDING_CRIMP'):
            col.prop(p,'irregularity');col.prop(p,'angle',text='Asymmetry direction')
            row=l.row(align=True);row.prop(p,'seed');row.operator('pipe.randomize',text='Update one shell' if p.environment=='BUTTON_TRACK' else 'New specimen')
            return
        if not flashlight:
            for key in ('defect_style','secondary_strength'):
                col.prop(p,key,slider=True)
        elif p.environment=='BUTTON_TRACK' and p.flashlight_layout=='SINGLE':
            col.prop(p,'defect_style',text='Dent shape')
        for key,label in [('position','Position along housing' if flashlight else 'Position along pipe'),
                          ('depth','Depth / local radius'),('width','Length / selected housing' if flashlight else 'Length / pipe length'),
                          ('arc','Width around surface'),('angle','Rotate defect (degrees)'),
                          ('irregularity','Irregularity'),('defect_rotation','Defect tilt')]:
            col.prop(p,key,text=label,slider=True)
        col.operator('pipe.front')
        row=l.row(align=True); row.prop(p,'seed'); row.operator('pipe.randomize',text='Update one shell' if flashlight and p.environment=='BUTTON_TRACK' else 'New defect')
    studio.PIPE_PT_defect.draw=defect
    def surface(self,context):
        p=context.scene.pipe_studio;l=self.layout
        if p.environment=='BUTTON_TRACK':
            row=l.row(align=True)
            row.operator('pipe.shell_appearance',text='Reference finish').preset='REFERENCE'
            row.operator('pipe.shell_appearance',text='Clean finish').preset='CLEAN'
            l.operator('pipe.shell_appearance',text='Previous satin finish').preset='SATIN'
            l.label(text='Appearance presets retain all defects.')
            box=l.box();box.label(text='Plastic and printing')
            for key in ('plastic_roughness','plastic_specular','plastic_coat','plastic_finish_variation','groove_polish','groove_residue','crimp_roughness','plastic_ink_wear'):
                box.prop(p,key,slider=True)
            box=l.box();box.label(text='Brass')
            for key,label in [('roughness','Brass roughness'),('oxide_amount','Mottled oxide finish'),('polish_amount','Burnished drawing streaks'),('brass_green','Olive brass tint')]:
                box.prop(p,key,text=label,slider=True)
            l.label(text='Normal surface details · no defect labels')
            l.prop(p,'inspection_track_finish')
        keys=('texture_strength','wear','dust_amount','finish_marks') if p.environment=='BUTTON_TRACK' else ('roughness','texture_strength')
        for key in keys:
            self.layout.prop(context.scene.pipe_studio,key,slider=True)
    branch(studio.PIPE_PT_light,surface)
    studio.PIPE_PT_light.bl_label='Surface finish'
    def lights(self,context):
        if context.scene.pipe_studio.environment=='BUTTON_TRACK':
            row=self.layout.row(align=True)
            row.operator('pipe.shell_lighting',text='Photo lighting').preset='PHOTO'
            row.operator('pipe.shell_lighting',text='Earlier lighting').preset='EARLIER'
            for key in ('inspection_light_rig','inspection_light_distance'):
                self.layout.prop(context.scene.pipe_studio,key)
        for key in ('key_power','key_angle','key_span','light_softness','fill_power','rim_power','ambient_strength','exposure','tone_mapping','color_cast','sensor_noise'):
            self.layout.prop(context.scene.pipe_studio,key,slider=True)
        if context.scene.pipe_studio.environment=='BUTTON_TRACK':
            for key in ('inspection_softness','inspection_scatter'):
                self.layout.prop(context.scene.pipe_studio,key,slider=True)
    branch(studio.PIPE_PT_illumination,lights)
    def camera(self,context):
        if context.scene.pipe_studio.environment=='BUTTON_TRACK':
            self.layout.prop(context.scene.pipe_studio,'flashlight_camera')
            self.layout.prop(context.scene.pipe_studio,'flashlight_projection')
            if context.scene.pipe_studio.flashlight_camera=='REFERENCE':
                self.layout.prop(context.scene.pipe_studio,'flashlight_reference_elevation')
            self.layout.prop(context.scene.pipe_studio,'flashlight_capture')
        for key in ('camera_zoom','camera_shift_x','camera_shift_y','frame_aspect'):
            self.layout.prop(context.scene.pipe_studio,key,slider=True)
        self.layout.label(text='Opposing 45° cameras + overhead' if context.scene.pipe_studio.environment=='BUTTON_TRACK' else 'Camera points straight down at the track.')
    branch(studio.PIPE_PT_camera,camera)
    original_batch=studio.PIPE_PT_batch.draw
    def batch(self,context):
        p=context.scene.pipe_studio
        if p.product_mode!='FLASHLIGHT' or p.environment!='BUTTON_TRACK':
            original_batch(self,context);return
        l=self.layout
        for key in ('resolution','samples','output_dir','flashlight_capture','flashlight_variation','flashlight_crops'):
            l.prop(p,key)
        l.prop(p,'batch_count',text='Specimen rows')
        l.label(text=f"{p.batch_count*(3 if p.flashlight_capture=='ALL' else 1)} images")
        l.prop(p,'clean_fraction',text='Clean row probability');l.prop(p,'front_only')
        l.operator('pipe.export',text='Auto-generate inspection images').randomize=True
        l.label(text='Regions and defects have separate labels.')
        l.operator('pipe.save');l.operator('pipe.reset')
    studio.PIPE_PT_batch.draw=batch
    studio.PIPE_PT_test.poll=classmethod(lambda cls,context:context.scene.pipe_studio.product_mode=='PIPE')
    def reset(self,context):
        from app_model import DEFAULTS
        from product_modes import initial_settings
        studio.apply_settings(context.scene,initial_settings(context.scene.pipe_studio.product_mode,DEFAULTS))
        context.scene.pipe_studio.mask_view=False
        return {'FINISHED'}
    studio.PIPE_OT_reset.execute=reset
    for cls in studio.CLASSES:
        if hasattr(cls,'bl_category'):
            cls.bl_category='Inspection Studio'
