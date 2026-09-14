"""Kinematic six-flap closure. Model units use a nominal body diameter of one.

This approximates the outside shape of a twisted, pressed tube. It is not an
impact/thermoplastic solver and does not infer why a closure failed.
"""
import math

RADIUS=.482
RIM=1.35
THICKNESS=.014

def point(r,s,sector,item,d=None):
    r=max(0,min(RADIUS,r))
    tightness=item.get('crimp_tightness',.85)
    twist=math.radians(item.get('crimp_twist',18))
    phase=item.get('crimp_phase',0)
    theta=(sector+s)*math.tau/6+phase+twist*(1-.45*tightness)*max(0,1-r/RADIUS)**1.5
    fold_depth=item.get('crimp_fold_depth',.085)
    support=max(0,1-(r/RADIUS)**12)
    crest=math.sin(math.pi*s)**1.7
    rounded=math.exp(-((r-.255)/.175)**2)*(1-math.exp(-(r/.035)**2))
    y=RIM-fold_depth*support+fold_depth*.90*crest*rounded*support
    y+=.008*math.exp(-((s-.10)/.055)**2)*rounded*support
    # Compact the rolled shoulders into a smaller star. Steep, narrowly rounded
    # seam sides replace the old broad dome, while keeping the tips pressed in.
    active_radius=.405
    t=min(1,r/active_radius)
    envelope=max(0,math.sin(math.pi*t**.8))**.65
    wave=max(0,math.sin(math.pi*s))
    ridge=((wave*wave+.0025)**.36-.0025**.36)/((1.0025)**.36-.0025**.36)
    tight_y=RIM-fold_depth*(.62+.38*envelope)+fold_depth*.80*ridge*envelope
    tight_y+=.006*math.exp(-((s-.075)/.035)**2)*envelope
    if r>active_radius:
        u=(r-active_radius)/(RADIUS-active_radius)
        tight_y=RIM-.62*fold_depth*(1-u*u*(3-2*u))
    y=y*(1-tightness)+tight_y*tightness
    y=min(RIM,y)
    delta=0
    if d and d['kind']=='protruding_crimp':
        spread=d['spread']
        influence=max(0,1-(r/spread)**2)**2
        skew=1+.2*d['irregularity']*math.sin(theta-d['angle'])*min(1,r/.06)
        center_drop=fold_depth*(1-.38*tightness)
        delta=(center_drop+d['lift'])*influence*skew
        y+=delta
    return (r*math.cos(theta),y,r*math.sin(theta)),delta

def opening_radius(s,sector,d):
    if not d or d['kind']!='open_center':return 0
    # Withdraw the folded tips unevenly; the aperture has six soft scallops.
    return d['opening']*(1+.13*math.cos(math.tau*s)+d['irregularity']*.2*math.sin(sector*1.7))

def build(item,defect=None):
    """Return a single region mesh containing six thick, individually folded flaps."""
    verts=[];faces=[];marks=[];aperture=[]
    nr,ns=96,64
    opened=bool(defect and defect['kind']=='open_center')
    for sector in range(6):
        grid=[];displacements=[]
        for k in range(nr+1):
            row=[];ds=[]
            for j in range(ns+1):
                s=j/ns;inner=opening_radius(s,sector,defect)
                r=inner+(RADIUS-inner)*k/nr
                co,delta=point(r,s,sector,item,defect)
                row.append(len(verts));verts.append(co);ds.append(delta)
                if k==0 and j<ns:aperture.append(co)
            grid.append(row);displacements.append(ds)
        for k in range(nr):
            for j in range(ns):
                f=(grid[k][j],grid[k][j+1],grid[k+1][j+1],grid[k+1][j])
                if k==0 and not opened:f=(grid[k][j],grid[k+1][j+1],grid[k+1][j])
                faces.append(f)
                if opened:
                    marked=k<3  # Deformed tip/lip support; aperture receives its own diagnostic surface.
                else:
                    marked=bool(defect and max(displacements[k][j],displacements[k+1][j+1])>defect.get('lift',1)*.08)
                marks.append(marked)
        # Thin underside and edge walls, visible through a real opening.
        offset=len(verts)
        flat=[index for row in grid for index in row]
        mapping={index:offset+i for i,index in enumerate(flat)}
        verts.extend((verts[index][0],verts[index][1]-THICKNESS,verts[index][2]) for index in flat)
        for k in range(nr):
            for j in range(ns):
                f=(grid[k][j],grid[k][j+1],grid[k+1][j+1],grid[k+1][j])
                if k==0 and not opened:f=(grid[k][j],grid[k+1][j+1],grid[k+1][j])
                faces.append(tuple(mapping[v] for v in reversed(f)));marks.append(False)
        boundary=grid[0]+[row[-1] for row in grid[1:]]+list(reversed(grid[-1][:-1]))+[row[0] for row in reversed(grid[1:-1])]
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):
            faces.append((a,mapping[a],mapping[b],b));marks.append(opened and a in grid[0] and b in grid[0])
    return verts,faces,marks,aperture if opened else []
