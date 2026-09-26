"""Build a private HWPML application from the official exported template.

Requires bundled lxml, tmp/official_form.hml (native Hancom export),
private/team.json. This script does not publish, submit, or replace the original.
"""
from pathlib import Path
from copy import deepcopy
import json
import re
import base64
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'private/제출준비'
OUT.mkdir(parents=True, exist_ok=True)
tree = E.parse(str(ROOT / 'tmp/official_form.hml'))
root = tree.getroot()
team = json.loads((ROOT / 'private/team.json').read_text(encoding='utf-8'))
md = (ROOT / '기획/제출제안서_원고.md').read_text(encoding='utf-8')
title = md.splitlines()[0].removeprefix('# ')
section = root.find('.//BODY/SECTION')
tables = root.findall('.//BODY/SECTION/P/TEXT/TABLE')
mapping = root.find('HEAD/MAPPINGTABLE')

def add_shape(tag, base, attrs, **margin):
    parent = mapping.find(tag+'LIST')
    x = deepcopy(parent.findall(tag)[base])
    idx = max(int(n.get('Id')) for n in parent) + 1
    x.set('Id', str(idx))
    for k,v in attrs.items(): x.set(k,str(v))
    if margin:
        for k,v in margin.items(): x.find('PARAMARGIN').set(k,str(v))
    parent.append(x)
    parent.set('Count', str(len(parent)))
    return str(idx),x

body_c,body_cs = add_shape('CHARSHAPE', 0, {'Height':1100,'TextColor':0})
small_c,small_cs = add_shape('CHARSHAPE',0,{'Height':1000,'TextColor':0})
bold_c,bold_cs = add_shape('CHARSHAPE',0,{'Height':1100,'TextColor':0})
E.SubElement(bold_cs,'BOLD')
sig_c,sig_cs = add_shape('CHARSHAPE',0,{'Height':1500,'TextColor':0})
for face in mapping.findall('FACENAMELIST/FONTFACE'):
    entries=face.findall('FONT')
    regular=next((x.get('Id') for x in entries if x.get('Name')=='맑은 고딕'),None)
    if regular is None:
        regular=str(max(int(x.get('Id')) for x in entries)+1)
        E.SubElement(face,'FONT',Id=regular,Name='맑은 고딕',Type='ttf')
    signature=str(max(int(x.get('Id')) for x in face.findall('FONT'))+1)
    E.SubElement(face,'FONT',Id=signature,Name='휴먼편지체',Type='ttf')
    face.set('Count',str(len(face)))
    lang=face.get('Lang')
    for cs in (body_cs,small_cs,bold_cs): cs.find('FONTID').set(lang,regular)
    sig_cs.find('FONTID').set(lang,signature)

body_p,_=add_shape('PARASHAPE',0,{'Align':'Justify','SnapToGrid':'false','WidowOrphan':'true'},LineSpacing=140,Prev=0,Next=400)
subhead_p,_=add_shape('PARASHAPE',0,{'Align':'Left','KeepWithNext':'true','SnapToGrid':'false'},LineSpacing=145,Prev=450,Next=350)
center_p,_=add_shape('PARASHAPE',0,{'Align':'Center','SnapToGrid':'false'},LineSpacing=130,Prev=0,Next=0)
reference_p,_=add_shape('PARASHAPE',0,{'Align':'Left','SnapToGrid':'false'},LineSpacing=140,Prev=0,Next=400)
page_p,_=add_shape('PARASHAPE',19,{'PageBreakBefore':'true'})

def para(text, char=body_c, shape=body_p):
    p=E.Element('P',ParaShape=shape,Style='0')
    t=E.SubElement(p,'TEXT',CharShape=char)
    E.SubElement(t,'CHAR').text=text
    return p

def fill(cell, text, char=body_c, shape=center_p):
    ps=cell.find('PARALIST')
    for p in list(ps): ps.remove(p)
    ps.append(para(text,char,shape))

rows=tables[0].findall('ROW')
cell=lambda row,col: rows[row].findall('CELL')[col]
fill(cell(1,1),team['team_name'])
for button in tables[0].findall('.//BUTTONSET'):
    button.set('Value','1' if button.get('Caption')=='A' else '0')
fill(cell(2,1),title,small_c)
lead=team['members'][0]
fill(cell(3,2),lead['department'])
fill(cell(3,4),lead['name'])
fill(cell(4,1),lead['phone'],small_c)
fill(cell(4,3),team['email'],small_c)
for i,m in enumerate(team['members']):
    for c,key in enumerate(('name','department','year','student_id','phone','role')):
        fill(cell(6+i,c),m[key],small_c)

# Embed separately prepared handwriting assets when the private manifest exists.
signature_manifest=ROOT/'private/서명/manifest.json'
signatures=json.loads(signature_manifest.read_text(encoding='utf-8')) if signature_manifest.exists() else None
if signatures:
    binaries=E.Element('BINDATALIST',Count=str(len(signatures['members'])))
    mapping.insert(0,binaries)
    storage=E.Element('BINDATASTORAGE')
    root.find('TAIL').insert(0,storage)
    for i,item in enumerate(signatures['members'],1):
        item['bin_id']=str(i)
        data=(ROOT/item['path']).read_bytes()
        E.SubElement(binaries,'BINITEM',Type='Embedding',BinData=str(i),Format='png')
        E.SubElement(storage,'BINDATA',Id=str(i),Size=str(len(data)),Encoding='Base64',Compress='false').text=base64.b64encode(data).decode('ascii')

def signature_overlay(cell,item,serial,table_index,member_index):
    """Put transparent ink in front of the unchanged original signature label."""
    width=item.get('width_hwp',4800)
    height=round(width*item['height']/item['width'])
    centers={0:(464.91,[547.24,569.92,592.60]),2:(482.31,[628.10,642.86,657.74]),3:(473.91,[581.66,602.18,622.70])}
    cx,ys=centers[table_index]
    left=round(cx*100-width/2)
    top=round(ys[member_index]*100-height/2-220)
    pic=E.Element('PICTURE',Reverse='false')
    shape=E.SubElement(pic,'SHAPEOBJECT',InstId=str(1800000000+serial),Lock='false',NumberingType='Figure',TextWrap='InFrontOfText',ZOrder=str(20+serial))
    E.SubElement(shape,'SIZE',Width=str(width),Height=str(height),WidthRelTo='Absolute',HeightRelTo='Absolute',Protect='false')
    E.SubElement(shape,'POSITION',TreatAsChar='false',AffectLSpacing='false',VertRelTo='Paper',VertAlign='Top',HorzRelTo='Paper',HorzAlign='Left',VertOffset=str(top),HorzOffset=str(left),FlowWithText='false',AllowOverlap='true',HoldAnchorAndSO='false')
    E.SubElement(shape,'OUTSIDEMARGIN',Left='0',Right='0',Top='0',Bottom='0')
    component=E.SubElement(pic,'SHAPECOMPONENT',XPos='0',YPos='0',GroupLevel='0',OriWidth=str(width),OriHeight=str(height),CurWidth=str(width),CurHeight=str(height),HorzFlip='false',VertFlip='false',InstID=str(1810000000+serial))
    E.SubElement(component,'ROTATIONINFO',Angle='0',CenterX=str(width//2),CenterY=str(height//2))
    render=E.SubElement(component,'RENDERINGINFO')
    for tag in ('TRANSMATRIX','SCAMATRIX','ROTMATRIX'):
        E.SubElement(render,tag,E1='1',E2='0',E3='0',E4='0',E5='1',E6='0')
    E.SubElement(pic,'LINESHAPE',Color='0',Width='0',Style='None',EndCap='Round',HeadStyle='Normal',TailStyle='Normal',HeadSize='SmallSmall',TailSize='SmallSmall',OutlineStyle='Normal',Alpha='0')
    E.SubElement(pic,'IMAGERECT',X0='0',Y0='0',X1=str(width),Y1='0',X2=str(width),Y2=str(height),X3='0',Y3=str(height))
    E.SubElement(pic,'IMAGECLIP',Left='0',Top='0',Right=str(item['width']*75),Bottom=str(item['height']*75))
    E.SubElement(pic,'INSIDEMARGIN',Left='0',Right='0',Top='0',Bottom='0')
    E.SubElement(pic,'IMAGE',BinItem=item['bin_id'],Bright='0',Contrast='0',Effect='RealPic',Alpha='0')
    cell.find('PARALIST/P/TEXT').append(pic)

# Keep (서명/인) in place and overlay the corresponding distinct handwriting.
for ti in (0,2,3):
    sig=tables[ti].findall('.//TABLE')[-1]
    for mi,(row,m) in enumerate(zip(sig.findall('ROW'),team['members'])):
        cells=row.findall('CELL')
        if ti==0:
            fill(cells[0],m['role'],small_c)
        else:
            fill(cells[1],m['name'],body_c)
        target=cells[1 if ti==0 else 2]
        if signatures:
            item=next(x for x in signatures['members'] if x['name']==m['name'])
            signature_overlay(target,item,ti*3+mi,ti,mi)
        else:
            fill(target,m['name'],sig_c)
    for char in tables[ti].findall('.//CHAR'):
        if re.fullmatch(r'2026년\s*월\s*일',char.text or ''):
            char.text=team['date']

# Keep original consent choices unchecked pending separate confirmation.
sections=re.split(r'(?m)^## \d+\. ',md)[1:]
prop=tables[1]
prows=prop.findall('ROW')
fill(prows[2].findall('CELL')[1],title,small_c)
for i,content in enumerate(sections):
    heading,body=content.split('\n',1)
    c=prows[4+i*2].find('CELL')
    ps=c.find('PARALIST')
    ps.set('VertAlign','Top')
    for p in list(ps):ps.remove(p)
    for block in body.strip().split('\n\n'):
        for line in block.splitlines():
            if line.startswith('### '):ps.append(para(line[4:],bold_c,subhead_p))
            elif line:ps.append(para(line,small_c,reference_p) if line.startswith('[') else para(line))
    c.set('Height','1000')
    c.set('HasMargin','true')
    c.find('CELLMARGIN').set('Top','600')
    c.find('CELLMARGIN').set('Bottom','500')

# Group the six original sections into five deliberate proposal pages.
anchor=prop.getparent().getparent()
insert_at=list(section).index(anchor)
for page_index,group in enumerate(((0,1),(2,),(3,),(4,),(5,))):
    page=deepcopy(anchor)
    page.set('ParaShape',page_p)
    table=page.find('TEXT/TABLE')
    existing=table.findall('ROW')
    keep=([0,1,2] if page_index==0 else [])+[v for i in group for v in (3+2*i,4+2*i)]
    for ri,row in enumerate(existing):
        if ri not in keep:table.remove(row)
    table.set('RowCount',str(len(table.findall('ROW'))))
    if page_index:
        table.set('ColCount','1')
        for c in table.findall('ROW/CELL'):c.set('ColSpan','1')
    for ri,row in enumerate(table.findall('ROW')):
        for c in row.findall('CELL'):c.set('RowAddr',str(ri))
    table.find('SHAPEOBJECT').set('InstId',str(1700000000+page_index))
    table.find('SHAPEOBJECT/SIZE').set('Height',str(sum(max(int(c.get('Height')) for c in row.findall('CELL')) for row in table.findall('ROW'))))
    section.insert(insert_at+page_index,page)
section.remove(anchor)

# Start administrative attachments on their own page; remove old spacer breaks.
for p in list(section):
    text=''.join(p.itertext())
    if text.startswith('※ 제시한 6개') or text.startswith('※ 제안서는') or text.startswith('※ 최종 제출 시'):
        section.remove(p)
    elif text.startswith('[붙임 2-2]') or text.startswith('[붙임 2-3]'):
        p.set('ParaShape',page_p)
    elif not text.strip() and p.find('.//SECDEF') is None and p.find('.//TABLE') is None:
        section.remove(p)

# Native Hancom recalculates line wrapping when loading HWPML.
target=OUT/'LG_AX_참가신청서_검토본.hml'
tree.write(str(target),encoding='UTF-16',xml_declaration=True)
print('HWPML created; personal fields are confined to private/.')
