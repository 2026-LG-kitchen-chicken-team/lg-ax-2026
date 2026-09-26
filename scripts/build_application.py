"""Build a private HWPML application from the official exported template.

Requires bundled lxml, tmp/official_form.hml (native Hancom export),
private/team.json. This script does not publish, submit, or replace the original.
"""
from pathlib import Path
from copy import deepcopy
import json
import re
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

# Add generic handwriting name text to the original signature cells.
for ti in (0,2,3):
    sig=tables[ti].findall('.//TABLE')[-1]
    for row,m in zip(sig.findall('ROW'),team['members']):
        cells=row.findall('CELL')
        if ti==0:
            fill(cells[0],m['role'],small_c)
            fill(cells[1],m['name'],sig_c)
        else:
            fill(cells[1],m['name'],body_c)
            fill(cells[2],m['name'],sig_c)
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
