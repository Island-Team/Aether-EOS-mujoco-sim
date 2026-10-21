#!/usr/bin/env python3
"""Compose pinned Menagerie UR5e and 2F-85 models into a mobile benchmark scene."""
from pathlib import Path
import xml.etree.ElementTree as ET
from copy import deepcopy

root = Path(__file__).resolve().parent
ur = ET.parse(root/'menagerie/universal_robots_ur5e/ur5e.xml').getroot()
gr = ET.parse(root/'menagerie/robotiq_2f85/2f85.xml').getroot()
for node in gr.iter():
    if node.tag=='mesh' and 'name' not in node.attrib and 'file' in node.attrib: node.set('name',Path(node.get('file')).stem)
    if 'name' in node.attrib: node.set('name', 'gr_'+node.get('name'))
    for k in ('class','childclass','mesh','material','joint','joint1','joint2','tendon','body1','body2'):
        if k in node.attrib: node.set(k, 'gr_'+node.get(k))
scene = ET.Element('mujoco', {'model':'eos_benchmark_v1'})
ET.SubElement(scene,'compiler',{'angle':'radian','autolimits':'true'})
ET.SubElement(scene,'option',{'timestep':'0.002','integrator':'implicitfast','gravity':'0 0 -9.81','cone':'elliptic','impratio':'10'})
ET.SubElement(ET.SubElement(scene,'visual'),'global',{'offwidth':'640','offheight':'480'})
ET.SubElement(scene,'statistic',{'center':'0 0 0.6','extent':'3'})
for source in (ur,gr):
    default=source.find('default')
    scene.append(deepcopy(default))
asset=ET.SubElement(scene,'asset')
for source,prefix in ((ur,'universal_robots_ur5e'),(gr,'robotiq_2f85')):
    for el in source.find('asset'):
        copied=deepcopy(el)
        if 'file' in copied.attrib: copied.set('file',f'menagerie/{prefix}/assets/'+copied.get('file'))
        asset.append(copied)
world=ET.SubElement(scene,'worldbody')
ET.SubElement(world,'light',{'pos':'0 0 4','dir':'0 0 -1','diffuse':'0.8 0.8 0.8'})
ET.SubElement(world,'geom',{'name':'floor','type':'plane','size':'5 5 0.1','rgba':'0.82 0.84 0.87 1','friction':'0.9 0.01 0.001'})
mobile=ET.SubElement(world,'body',{'name':'mobile_base','pos':'-1.2 0 0.42'})
for name,axis,jtype in [('base_x','1 0 0','slide'),('base_y','0 1 0','slide'),('base_yaw','0 0 1','hinge')]:
    ET.SubElement(mobile,'joint',{'name':name,'type':jtype,'axis':axis,'damping':'30' if jtype=='slide' else '15'})
ET.SubElement(mobile,'geom',{'name':'base_chassis','type':'box','size':'0.30 0.27 0.16','pos':'0 0 -0.24','mass':'40','rgba':'0.13 0.20 0.3 1'})
ET.SubElement(mobile,'camera',{'name':'robot_camera','pos':'0.18 0 0.78','xyaxes':'0 -1 0 0.3 0 1','fovy':'65'})
robot=deepcopy(ur.find('worldbody/body'))
robot.set('pos','0 0 -0.08')
mobile.append(robot)
wrist=next(x for x in robot.iter('body') if x.get('name')=='wrist_3_link')
gribody=deepcopy(gr.find('worldbody/body'))
gribody.set('pos','0 0.1 0')
gribody.set('quat','0.70710678 -0.70710678 0 0')
wrist.append(gribody)
# The attachment site is the Cartesian target; the gripper pinch site is used for grasp status.
ET.SubElement(world,'geom',{'name':'table','type':'box','pos':'0.35 0 0.35','size':'0.45 0.6 0.35','rgba':'0.55 0.43 0.33 1'})
obj=ET.SubElement(world,'body',{'name':'benchmark_object','pos':'0.00 -0.18 0.75'})
ET.SubElement(obj,'freejoint',{'name':'object_free'})
ET.SubElement(obj,'geom',{'name':'object_geom','type':'box','size':'0.035 0.035 0.05','mass':'0.18','rgba':'0.92 0.36 0.12 1','friction':'1.2 0.005 0.0001'})
ET.SubElement(world,'geom',{'name':'bin_floor','type':'box','pos':'-0.06 0.24 0.71','size':'0.14 0.14 0.01','rgba':'0.1 0.65 0.3 1'})
for x,y,z,sx,sy,sz in [(-0.06,0.095,0.755,0.15,0.01,0.055),(-0.06,0.385,0.755,0.15,0.01,0.055),(-0.205,0.24,0.755,0.01,0.15,0.055),(0.085,0.24,0.755,0.01,0.15,0.055)]:
    ET.SubElement(world,'geom',{'type':'box','pos':f'{x} {y} {z}','size':f'{sx} {sy} {sz}','rgba':'0.1 0.65 0.3 1','contype':'0','conaffinity':'0'})
for i,(x,y) in enumerate([(-0.55,-0.65),(-0.45,0.8)]):
    ET.SubElement(world,'geom',{'name':f'obstacle_{i}','type':'box','pos':f'{x} {y} 0.3','size':'0.18 0.18 0.3','rgba':'0.65 0.1 0.12 1'})
for source in (ur,gr):
    for section in ('contact','tendon','equality','actuator'):
        element=source.find(section)
        if element is None: continue
        dest=scene.find(section)
        if dest is None: dest=ET.SubElement(scene,section)
        dest.extend(deepcopy(list(element)))
act=scene.find('actuator')
for joint in ('base_x','base_y','base_yaw'):
    ET.SubElement(act,'velocity',{'name':joint+'_motor','joint':joint,'kv':'1000','ctrlrange':'-1.5 1.5','ctrllimited':'true'})
ET.indent(scene)
ET.ElementTree(scene).write(root/'scene.xml',encoding='unicode',xml_declaration=True)
