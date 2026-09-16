import unittest
from test_domain_runtime import fixture
from pathlib import Path
from PIL import Image
from yolox_readiness import parse_labels,input_dimensions,camera_name
from score_yolox_predictions import match,score


class ReadinessTests(unittest.TestCase):
    def test_empty_explicit_label_is_valid(self):self.assertEqual(parse_labels('\n'),[])
    def test_invalid_annotation_never_becomes_negative(self):
        for value in ('0 .2 .2 nan .2','7 .5 .5 .1 .1','0 .9 .9 .9 .9','0 .5 .5 0 .1'):
            with self.assertRaises(ValueError):parse_labels(value)
    def test_letterbox_dimensions(self):
        box=parse_labels('0 .5 .5 .1 .1')[0]
        self.assertEqual(input_dimensions(box,2000,1000,640),(64,32))
    def test_camera_label(self):self.assertEqual(camera_name('bundle__domain_001_cam2534'),'CAM2534')
    def test_duplicate_prediction_only_counts_once(self):
        gt=[dict(class_id=0,bbox_xyxy=[10,10,20,20])]
        p=dict(class_id=0,bbox_xyxy=[10,10,20,20],score=.9)
        counts,_,_=match(gt,[p,p]);self.assertEqual(counts['0']['tp'],1);self.assertEqual(counts['0']['fp'],1)
    def test_fold_dent_confusion_and_missing_prediction(self):
        gt=[dict(class_id=0,bbox_xyxy=[10,10,20,20])]
        p=dict(class_id=1,bbox_xyxy=[10,10,20,20],score=.9)
        counts,_,confusion=match(gt,[p]);self.assertEqual(counts['0']['fn'],1)
        self.assertEqual(counts['1']['fp'],1);self.assertEqual(confusion['0->1'],1)
    def test_unknown_stain_coverage_not_scored_as_false_positive(self):
        p=dict(class_id=2,bbox_xyxy=[10,10,20,20],score=.9)
        counts,failures,_=match([],[p]);self.assertFalse(counts);self.assertFalse(failures)

    def test_scoring_requires_complete_coverage_and_low_enough_export_floor(self):
        with fixture() as folder:
            root=Path(folder);(root/'images').mkdir();(root/'labels').mkdir()
            Image.new('RGB',(100,100)).save(root/'images/sample_cam2534.png')
            (root/'labels/sample_cam2534.txt').write_text('0 .5 .5 .2 .2\n')
            meta=dict(checkpoint_sha256='a'*64,input_size=[640,640],nms_threshold=.65,
                      box_space='native_xyxy',export_confidence_floor=.01)
            data=dict(metadata=meta,images=[])
            with self.assertRaisesRegex(ValueError,'every image'):score(root,data)
            data['images']=[dict(file_name='sample_cam2534.png',detections=[])]
            report=score(root,data)
            self.assertEqual(report['by_class']['0']['fn'],1)
            self.assertEqual(report['by_camera_class']['CAM2534/0']['recall'],0)
            self.assertEqual(len(report['ground_truth_labels_sha256']),64)
            meta['export_confidence_floor']=.5
            with self.assertRaisesRegex(ValueError,'export_confidence_floor'):score(root,data)


if __name__=='__main__':unittest.main()
