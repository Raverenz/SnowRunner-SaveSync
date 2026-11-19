"""Offline cat rarity rolls and cancellable canvas fireworks."""
import math
import random

RARITIES = (
    {'name':'Common','weight':55,'background':'#eceff1','accent':'#657581','text':'#34414b'},
    {'name':'Uncommon','weight':25,'background':'#dcefe1','accent':'#368557','text':'#245b3b'},
    {'name':'Rare','weight':13,'background':'#dceafa','accent':'#367bc6','text':'#245589'},
    {'name':'Epic','weight':6,'background':'#29183e','accent':'#c17bff','text':'#eddaff'},
    {'name':'Legendary','weight':1,'background':'#332607','accent':'#ffcb45','text':'#ffe6a0'},
)


def roll_rarity(rng=random):
    roll=rng.randrange(sum(r['weight'] for r in RARITIES))
    for rarity in RARITIES:
        if roll<rarity['weight']:return rarity
        roll-=rarity['weight']
    raise AssertionError('Invalid rarity roll')


class Fireworks:
    def __init__(self,canvas,rng=random):
        self.canvas=canvas;self.rng=rng;self.job=None;self.stopped=False
        self.frame=0;self.particles=[]
        self.tick()

    def stop(self):
        self.stopped=True
        if self.job is not None:
            self.canvas.after_cancel(self.job);self.job=None
        if self.canvas.winfo_exists():self.canvas.delete('fireworks')
        self.particles.clear()

    def tick(self):
        self.job=None
        if self.stopped or not self.canvas.winfo_exists():return
        self.canvas.delete('fireworks')
        if self.frame<126 and self.frame%18==0:
            x=self.rng.choice((55,90,350,385));y=self.rng.randint(65,260)
            color=self.rng.choice(('#ffd36a','#ee98ff','#84e8ff','#f9a0a0','#b8ffa3'))
            for i in range(28):
                angle=i*2*math.pi/28+self.rng.uniform(-.08,.08)
                speed=self.rng.uniform(1.5,4.3)
                self.particles.append([x,y,math.cos(angle)*speed,math.sin(angle)*speed,0,color])
        alive=[]
        for p in self.particles:
            p[0]+=p[2];p[1]+=p[3];p[3]+=.055;p[4]+=1
            if p[4]>48:continue
            x,y,vx,vy,age,color=p
            self.canvas.create_line(x-vx*2,y-vy*2,x,y,fill=color,width=2 if age<28 else 1,tags='fireworks')
            alive.append(p)
        self.particles=alive
        self.canvas.tag_lower('fireworks')
        self.frame+=1
        if self.frame<180:self.job=self.canvas.after(33,self.tick)
        else:self.canvas.delete('fireworks');self.particles.clear()
