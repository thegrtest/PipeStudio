"""Bounded exterior torsion approximation; not a material failure simulation."""
import math

def twist(y,theta,radius,defect):
    t=(y+1.055)/2.405
    span=defect['twist_span'];center=max(span/2,min(1-span/2,defect['position']))
    u=max(0.,min(1.,(t-center)/span+.5))
    turn=u*u*u*(10+u*(-15+6*u))
    offset=math.radians(defect['twist_degrees'])*turn
    envelope=math.sin(math.pi*u)**2
    severity=min(1.,abs(defect['twist_degrees'])/120.)
    # Smooth ovalization and a few helical buckles grow with severity. The
    # radius stays positive and both end boundaries retain their normal size.
    buckle=severity**1.6*envelope
    radius-=.042*buckle*(.55+.45*math.cos(2*theta+offset))
    radius-=.013*severity**2*envelope*(.5+.5*math.cos(3*theta-8*u))**6
    return radius,theta+offset,0.01<u<.99 and abs(defect['twist_degrees'])>1e-6
