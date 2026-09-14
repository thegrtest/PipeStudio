"""Relative visual recipes estimated from user-supplied inspection photographs."""
from app_model import DEFAULTS

SCENE_PRESETS={
 'MACHINE': {**DEFAULTS,'environment':'MACHINE','length':8.0,'radius':.90,
     'end_ratio':.70,'wall_ratio':.045,'body_taper':.025,'taper_start':.78,'taper_end':.88,
     'shoulder_roundness':.18,'defect':'DENT','position':.803,'angle':180,'depth':.08,
     'width':.013,'arc':9,'irregularity':.12,'roughness':.40,'texture_strength':.38,
     'oxide_amount':.34,'polish_amount':.27,'finish_marks':.28,
     'wear':.24,'brass_green':.62,'key_power':1850,'key_angle':55,'fill_power':24,
     'rim_power':100,'light_softness':.45,'ambient_strength':.04,'exposure':0,'tone_mapping':'STANDARD',
     'color_cast':.20,'sensor_noise':.018,'camera_yaw':0,'camera_elevation':4,
     'camera_zoom':1.45,'camera_shift_x':-.125,'camera_shift_y':.025,'frame_aspect':1.28,
     'focus_blur':.75,'resolution':1600,'samples':192},
 'GODSLIGHT': {**DEFAULTS,'environment':'GODSLIGHT','length':8.0,'radius':.90,
     'end_ratio':.68,'wall_ratio':.045,'body_taper':.045,'taper_start':.80,'taper_end':.88,
     'shoulder_roundness':.18,'defect':'NONE','position':.825,'angle':160,'depth':.06,
     'width':.025,'arc':15,'irregularity':.16,'roughness':.51,'texture_strength':.65,
     'oxide_amount':.52,'polish_amount':.19,'finish_marks':.42,
     'wear':.40,'brass_green':.95,'key_power':125,'key_angle':80,'fill_power':50,
     'rim_power':85,'light_softness':1.7,'key_span':.6,'ambient_strength':.13,'exposure':0,
     'color_cast':.38,'sensor_noise':.012,'camera_yaw':0,'camera_elevation':1,'tone_mapping':'STANDARD',
     'camera_zoom':.90,'camera_shift_x':.035,'camera_shift_y':.035,'frame_aspect':1936/1216,
     'focus_blur':.65,'resolution':1936,'samples':192},
 'STUDIO': {**DEFAULTS,'environment':'STUDIO'}
}

REFERENCE_PATHS={
 'MACHINE': 'references/upright-inspection.png',
 'GODSLIGHT': 'references/godslight-horizontal.jpg',
}
