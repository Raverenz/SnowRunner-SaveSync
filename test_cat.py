import unittest
from collections import Counter
from unittest.mock import Mock,patch
import tkinter as tk
from cat_effects import RARITIES,roll_rarity
from savesync import App

class CatTests(unittest.TestCase):
    def test_exact_roll_weights(self):
        counts=Counter(roll_rarity(Mock(randrange=Mock(return_value=i)))['name'] for i in range(100))
        self.assertEqual(counts,{r['name']:r['weight'] for r in RARITIES})
    def test_quality_background_effects_replacement_and_close(self):
        root=tk.Tk();root.withdraw()
        errors=[];root.report_callback_exception=lambda *args: errors.append(args)
        try:
            app=App(root);previous=None
            for rarity in RARITIES:
                with patch('savesync.roll_rarity',return_value=rarity):app.show_cat()
                self.assertNotEqual(app.cat_breed,previous);previous=app.cat_breed
                self.assertEqual(app.cat_canvas.cget('background'),rarity['background'])
                effect=getattr(app,'cat_effect',None)
                if rarity['name'] in ('Epic','Legendary'):
                    self.assertIsNotNone(effect)
                    self.assertTrue(app.cat_canvas.find_withtag('fireworks'))
                    order=list(app.cat_canvas.find_all())
                    sparks=app.cat_canvas.find_withtag('fireworks')
                    self.assertLess(max(order.index(i) for i in sparks),min(order.index(i) for i in order if i not in sparks))
                else:self.assertIsNone(effect)
                window=app.cat_window
                with patch('savesync.roll_rarity',return_value=RARITIES[0]):app.show_cat()
                self.assertNotEqual(app.cat_breed,previous);previous=app.cat_breed
                self.assertIs(app.cat_window,window)
                self.assertFalse(app.cat_canvas.find_withtag('fireworks'))
                if effect:self.assertTrue(effect.stopped)
            with patch('savesync.roll_rarity',return_value=RARITIES[4]):app.show_cat()
            effect=app.cat_effect;app.close_cat();root.update()
            self.assertTrue(effect.stopped);self.assertIsNone(effect.job)
            self.assertFalse(errors)
            app.show_cat();app.close_cat()
        finally:root.destroy()


# Keep legacy UI assertions independent of the saved language.
def setUpModule():
    global _language_patch
    _language_patch=__import__('unittest.mock',fromlist=['patch']).patch('savesync.read_language',return_value='pl')
    _language_patch.start()

def tearDownModule():
    _language_patch.stop()

if __name__=='__main__':unittest.main()


# Keep legacy UI assertions independent of the machine's saved language.