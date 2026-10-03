"""Build a private HWPML application from the official exported template.

Requires bundled lxml, tmp/official_form.hml (native Hancom export),
private/team.json. This script does not publish, submit, or replace the original.
"""
from pathlib import Path
from copy import deepcopy
import json
import re
import base64
from PIL import Image
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
image_p,_=add_shape('PARASHAPE',0,{'Align':'Center','SnapToGrid':'false'},LineSpacing=100,Prev=300,Next=600)
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

def embed_image(path):
    binaries=mapping.find('BINDATALIST')
    if binaries is None:
        binaries=E.Element('BINDATALIST',Count='0')
        mapping.insert(0,binaries)
    storage=root.find('TAIL/BINDATASTORAGE')
    if storage is None:
        storage=E.Element('BINDATASTORAGE')
        root.find('TAIL').insert(0,storage)
    idx=str(max([int(n.get('BinData')) for n in binaries]+[0])+1)
    data=path.read_bytes()
    E.SubElement(binaries,'BINITEM',Type='Embedding',BinData=idx,Format='png')
    binaries.set('Count',str(len(binaries)))
    E.SubElement(storage,'BINDATA',Id=idx,Size=str(len(data)),Encoding='Base64',Compress='false').text=base64.b64encode(data).decode('ascii')
    with Image.open(path) as im: w,h=im.size
    return {'bin_id':idx,'width':w,'height':h}

def signature_overlay(cell,item,serial,table_index,member_index):
    """Put transparent ink in front of the unchanged original signature label."""
    width=item.get('width_hwp',4800)
    height=round(width*item['height']/item['width'])
    if table_index==2 and height>1400:
        width=round(width*1400/height)
        height=1400
    centers={0:(464.91,[547.24,569.92,592.60,615.28,637.96]),2:(482.31,[637.10,651.98,666.74,681.62,696.38]),3:(473.91,[581.66,602.18,622.70,643.22,663.74])}
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
        if not m.get('signature_insertion_authorized',True):
            continue
        if signatures:
            item=next(x for x in signatures['members'] if x['name']==m['name'])
            signature_overlay(target,item,ti*5+mi,ti,mi)
        else:
            fill(target,m['name'],sig_c)
    for char in tables[ti].findall('.//CHAR'):
        if re.fullmatch(r'2026년\s*월\s*일',char.text or ''):
            char.text=team['date']

# Keep the consent footer clear after the additional member row is populated.
consent_paragraphs=tables[2].findall('ROW/CELL/PARALIST/P')
for index,p in enumerate(consent_paragraphs):
    if ''.join(p.itertext()).strip()=='국립창원대학교 인공지능원장 귀하' and index:
        previous=consent_paragraphs[index-1]
        if not ''.join(previous.itertext()).strip() and previous.find('.//TABLE') is None:
            previous.getparent().remove(previous)

def inline_image(path,serial):
    item=embed_image(path)
    width=42600
    height=round(width*item['height']/item['width'])
    # Reuse the proven native picture structure, with inline flow positioning.
    dummy=E.Element('CELL')
    E.SubElement(dummy,'PARALIST').append(para(''))
    signature_overlay(dummy,item,serial,0,0)
    pic=dummy.find('.//PICTURE')
    shape=pic.find('SHAPEOBJECT')
    shape.set('TextWrap','TopAndBottom')
    size=shape.find('SIZE')
    size.set('Width',str(width));size.set('Height',str(height))
    pos=shape.find('POSITION')
    for k,v in {'TreatAsChar':'true','AffectLSpacing':'true','VertRelTo':'Para','HorzRelTo':'Para','VertOffset':'0','HorzOffset':'0','AllowOverlap':'false'}.items():pos.set(k,v)
    comp=pic.find('SHAPECOMPONENT')
    for k,v in {'OriWidth':width,'CurWidth':width,'OriHeight':height,'CurHeight':height}.items():comp.set(k,str(v))
    rot=comp.find('ROTATIONINFO')
    rot.set('CenterX',str(width//2));rot.set('CenterY',str(height//2))
    rect=pic.find('IMAGERECT')
    for k,v in {'X0':0,'Y0':0,'X1':width,'Y1':0,'X2':width,'Y2':height,'X3':0,'Y3':height}.items():rect.set(k,str(v))
    p=para('',shape=image_p)
    p.find('TEXT').append(pic)
    return p

# Mark only choices explicitly confirmed by the user for every current member.
for nested in tables[2].findall('.//TABLE'):
    for row in nested.findall('ROW'):
        cells=row.findall('CELL')
        if len(cells)==5 and ''.join(cells[1].itertext()).strip()=='동의함':
            label=''.join(cells[0].itertext()).strip()
            key='personal_information' if label.startswith('개인정보') else 'portrait_use'
            choice=team.get('consent_choices',{}).get(key)
            if choice is not None:
                cells[2].find('.//CHAR').text='( ○ )' if choice else '(    )'
                cells[4].find('.//CHAR').text='(    )' if choice else '( ○ )'

sections=re.split(r'(?m)^## \d+\. ',md)[1:]
prop=tables[1]
prows=prop.findall('ROW')
fill(prows[2].findall('CELL')[1],title,small_c)
section_chunks={}
image_serial=100
for i,content in enumerate(sections):
    heading,body=content.split('\n',1)
    c=prows[4+i*2].find('CELL')
    ps=c.find('PARALIST')
    ps.set('VertAlign','Top')
    for p in list(ps):ps.remove(p)
    chunks=[[]]
    for block in body.strip().split('\n\n'):
        for line in block.splitlines():
            if line=='<!-- pagebreak -->':
                chunks.append([])
            elif line.startswith('!['):
                match=re.fullmatch(r'!\[([^]]+)\]\(([^)]+)\)',line)
                if not match:raise ValueError('Invalid diagram reference')
                chunks[-1].append(inline_image(ROOT/'기획'/match.group(2),image_serial))
                image_serial+=1
            elif line.startswith('### '):chunks[-1].append(para(line[4:],bold_c,subhead_p))
            elif line:chunks[-1].append(para(line,small_c,reference_p) if line.startswith('[') else para(line))
    section_chunks[i]=chunks
    for p in chunks[0]:ps.append(deepcopy(p))
    c.set('Height','1000')
    c.set('HasMargin','true')
    c.find('CELLMARGIN').set('Top','600')
    c.find('CELLMARGIN').set('Bottom','500')

# Keep official sections; each example gets a deliberately paginated continuation.
anchor=prop.getparent().getparent()
insert_at=list(section).index(anchor)
pages=[(i,ci) for i in range(len(sections)) for ci in range(len(section_chunks[i]))]
for page_index,(i,chunk_index) in enumerate(pages):
    page=deepcopy(anchor)
    page.set('ParaShape',page_p)
    table=page.find('TEXT/TABLE')
    existing=table.findall('ROW')
    keep=([0,1,2] if page_index==0 else [])+[3+2*i,4+2*i]
    for ri,row in enumerate(existing):
        if ri not in keep:table.remove(row)
    content_cell=existing[4+2*i].find('CELL/PARALIST')
    for p in list(content_cell):content_cell.remove(p)
    for p in section_chunks[i][chunk_index]:content_cell.append(deepcopy(p))
    if chunk_index:
        heading_char=existing[3+2*i].find('.//CHAR')
        heading_char.text=(heading_char.text or '')+' (계속)'
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
