"""Reproducible explanatory figures: idea, operation, and concrete use."""
from pathlib import Path
import math, os, subprocess
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'기획/시각자료'
TMP=ROOT/'tmp/proposal_visuals'
OUT.mkdir(parents=True,exist_ok=True)
TMP.mkdir(parents=True,exist_ok=True)
FONT=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
pdfmetrics.registerFont(TTFont('Korean',str(FONT/'malgun.ttf')))
pdfmetrics.registerFont(TTFont('KoreanBold',str(FONT/'malgunbd.ttf')))
POPPLER=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe'
INK,MUTED,ACCENT='#202124','#595D63','#991B42'
LINE,PALE,WASH='#CBCED2','#F1F2F3','#F7EDF0'

def text(c,x,y,s,size=10,bold=False,color=INK):
 c.setFillColor(HexColor(color));c.setFont('KoreanBold' if bold else 'Korean',size);c.drawString(x,y,s)
def lines(c,x,y,items,size=10,leading=15,**kwargs):
 for i,s in enumerate(items):text(c,x,y-i*leading,s,size,**kwargs)
def line(c,x1,y1,x2,y2,color=LINE,width=.7):
 c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x1,y1,x2,y2)
def rect(c,x,y,w,h,fill=None,stroke=LINE,width=.7):
 c.setLineWidth(width);c.setStrokeColor(HexColor(stroke))
 if fill:c.setFillColor(HexColor(fill))
 c.rect(x,y,w,h,fill=bool(fill),stroke=True)
def arrow(c,x1,y1,x2,y2,color=MUTED):
 line(c,x1,y1,x2,y2,color,.9);a=math.atan2(y2-y1,x2-x1)
 for d in (-.5,.5):line(c,x2,y2,x2-4.5*math.cos(a+d),y2-4.5*math.sin(a+d),color,.9)
def title(c,y,number,label):
 text(c,2,y,'그림 '+number,9,True,ACCENT);text(c,43,y-1,label,13,True);line(c,2,y-14,438,y-14,INK,.9)
def page_icon(c,x,y,w=25,h=31,color=MUTED):
 rect(c,x,y,w,h,'#FFFFFF',color)
 for i,f in enumerate((.65,.65,.45)):line(c,x+5,y+h-9-i*6,x+w*f,y+h-9-i*6,color)

def overview(c):
 title(c,222,'1','고객의 불편을 새로운 기획안으로')
 text(c,2,186,'01  기획자가 넣는 자료',10,True)
 text(c,155,186,'02  상품기획 Agent',10,True,ACCENT)
 text(c,316,186,'03  기획자가 받는 결과',10,True)
 page_icon(c,4,131)
 text(c,39,151,'고객 리뷰',10.5,True);text(c,39,136,'어떤 상황이 불편한가',9.5,color=MUTED)
 page_icon(c,4,81)
 text(c,39,101,'제품 설명서·명세',10.5,True);text(c,39,86,'지금 어떤 기능이 있는가',9.2,color=MUTED)
 arrow(c,135,119,152,119)
 rect(c,157,76,130,90,PALE,PALE);line(c,157,166,287,166,ACCENT,2)
 lines(c,170,144,['불편과 기존 기능을 대조','남아 있는 문제를 찾고','해결할 콘셉트를 제안'],10.4,23)
 arrow(c,291,119,309,119)
 rect(c,316,70,122,97,'#FFFFFF','#878B91')
 text(c,328,146,'콘셉트 최대 3개',10.5,True);line(c,328,135,426,135)
 lines(c,328,119,['해결할 고객 불편','기능·제품·서비스 방향','근거와 설계 요구사항'],9.4,17)
 line(c,2,51,438,51)
 text(c,2,28,'누가 사용하나',9.4,True,ACCENT)
 text(c,82,28,'키친 상품기획자',10.5,True)
 text(c,188,28,'제품군·목표 고객·개선 과제를 정해 요청',9.6,color=MUTED)

def workflow(c):
 title(c,205,'2','자료를 읽고, 대조하고, 검사하며 제안한다')
 stages=[('1','불편 정리',['리뷰에서 사용 상황과','구체적인 불편 추출']),('2','기존 기능 대조',['같은 제품의 기능과','남아 있는 불편 구분']),('3','콘셉트 작성',['해결할 기능·제품과','요구사항 작성']),('4','중복·근거 검사',['이미 있는 기능인지','원문 근거와 연결 확인'])]
 for i,(number,label,detail) in enumerate(stages):
  x=2+i*114
  text(c,x,167,number,16,True,ACCENT);text(c,x,145,label,10.8,True)
  lines(c,x,122,detail,9.4,15,color=MUTED);line(c,x,96,x+94,96)
  if i<3:arrow(c,x+96,145,x+108,145)
 line(c,390,92,390,75,ACCENT);line(c,390,75,278,75,ACCENT);arrow(c,278,75,278,92,ACCENT)
 text(c,285,59,'중복·누락이 있으면 수정',9.4,color=ACCENT)
 rect(c,2,14,236,53,PALE,PALE);text(c,14,45,'기획자 검토',10.4,True);text(c,14,27,'콘셉트 + 근거 + 확인할 요구사항',10)
 line(c,430,92,430,40);arrow(c,430,40,244,40);text(c,312,23,'검사를 거친 제안 전달',9.2,color=MUTED)

def fridge(c,x,y):
 # Open refrigerator: insulated cabinet, shelves, crisper, and door bins.
 rect(c,x,y,60,87,'#FFFFFF','#646970',1);rect(c,x+5,y+5,50,75,'#FFFFFF',LINE)
 rect(c,x+8,y+8,44,17,PALE,'#7A7E84');line(c,x+24,y+21,x+36,y+21,'#7A7E84',1.5)
 line(c,x+9,y+83,x+51,y+83,'#7A7E84',1.2)
 for bx in (13,34):
  rect(c,x+bx,y+59,7,18,'#FFFFFF','#7A7E84');rect(c,x+bx+2,y+77,3,3,PALE,'#7A7E84')
 polygon(c,[(x+60,y),(x+81,y+8),(x+81,y+87),(x+60,y+87)],'#F7F8F9','#646970')
 for by in (18,51,72):
  polygon(c,[(x+64,y+by),(x+77,y+by+4),(x+77,y+by+12),(x+64,y+by+8)],'#E4E7EA','#8B9096')
 line(c,x+79,y+36,x+79,y+59,'#646970',1.7)
 line(c,x+5,y+29,x+55,y+29,'#7A7E84');line(c,x+5,y+57,x+55,y+57,'#7A7E84')
 rect(c,x+10,y+32,16,15,PALE,'#7A7E84');c.setDash(2,2);rect(c,x+31,y+32,18,15,None,ACCENT);c.setDash()
 arrow(c,x+50,y+39,x+85,y+39,ACCENT)
 p=c.beginPath()
 for i,pt in enumerate([(x+77,y+26),(x+102,y+26),(x+112,y+35),(x+112,y+51),(x+87,y+51),(x+77,y+42)]):
  (p.moveTo if i==0 else p.lineTo)(*pt)
 p.close();c.setFillColor(HexColor(WASH));c.setStrokeColor(HexColor(ACCENT));c.drawPath(p,fill=1,stroke=1)
 q=c.beginPath()
 for i,pt in enumerate([(x+81,y+43),(x+89,y+49),(x+108,y+49),(x+100,y+43)]):
  (q.moveTo if i==0 else q.lineTo)(*pt)
 q.close();c.setFillColor(HexColor('#FFFFFF'));c.drawPath(q,fill=1,stroke=1)
 line(c,x+77,y+42,x+102,y+42,ACCENT);line(c,x+102,y+42,x+112,y+51,ACCENT);line(c,x+102,y+26,x+102,y+42,ACCENT)
 text(c,x+7,y-15,'냉장고 내부',8.7,color=MUTED);text(c,x+84,y+8,'탈착 트레이',7.8,True,ACCENT)

def polygon(c,points,fill,stroke=LINE):
 p=c.beginPath();p.moveTo(*points[0])
 for pt in points[1:]:p.lineTo(*pt)
 p.close();c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(.8);c.drawPath(p,fill=1,stroke=1)

def dishwasher(c):
 # Front-open appliance, control strip, two wire racks, plates and a pot.
 rect(c,24,95,105,69,'#FFFFFF','#646970',1)
 rect(c,29,100,95,50,'#E9ECEF','#8B9096')
 rect(c,29,153,95,7,PALE,LINE)
 for x in (34,40,46):c.setStrokeColor(HexColor(MUTED));c.circle(x,156.5,1,stroke=1,fill=0)
 rect(c,105,155,13,3,'#646970','#646970')
 for yy in (126,105):
  rect(c,34,yy,85,19,'#FFFFFF','#8B9096')
  for xx in range(39,119,8):line(c,xx,yy,xx,yy+18,LINE,.5)
  line(c,34,yy+6,119,yy+6,LINE,.5)
 for xx in (43,54,65):
  c.setStrokeColor(HexColor(ACCENT));c.setLineWidth(1);c.ellipse(xx,108,xx+7,122,stroke=1,fill=0)
 rect(c,84,111,21,10,PALE,ACCENT);line(c,80,118,84,118,ACCENT);line(c,105,118,109,118,ACCENT)
 for xx in (43,65,87):rect(c,xx,131,12,10,PALE,'#7A7E84')
 polygon(c,[(24,95),(129,95),(144,78),(9,78)],'#ECEFF1','#646970')
 rect(c,58,82,30,5,'#FFFFFF','#8B9096')
 text(c,26,65,'식기세척기 · 열린 문과 바구니',8.1,color=MUTED)

def microwave(c):
 # Familiar countertop silhouette, door handle, keypad and glass turntable.
 rect(c,12,105,138,55,'#FFFFFF','#646970',1.1)
 rect(c,17,111,96,43,'#DEE3E7','#646970')
 rect(c,23,116,78,32,'#F5F7F8','#A3A8AD')
 c.setStrokeColor(HexColor('#8B9096'));c.ellipse(30,119,94,128,stroke=1,fill=0)
 c.ellipse(42,123,83,136,stroke=1,fill=0);line(c,43,128,48,122,'#8B9096');line(c,82,128,77,122,'#8B9096')
 line(c,107,121,107,145,'#646970',2.5)
 rect(c,119,142,24,11,'#303940','#303940');text(c,122,145,'1:30',6.5,color='#FFFFFF')
 for yy in (136,130,124):
  for xx in (122,130,138):rect(c,xx,yy,4,3,PALE,'#8B9096',.5)
 rect(c,120,115,22,5,WASH,ACCENT)
 rect(c,23,102,14,3,'#646970','#646970');rect(c,125,102,14,3,'#646970','#646970')
 text(c,20,89,'전자레인지 · 저장/호출 조작부',8.2,color=MUTED)
 rect(c,18,67,129,15,'#FFFFFF',ACCENT)
 text(c,26,71,'설정 저장 후보 → 중복 제외',8.3,True,ACCENT)

def example(c):
 example_header(c,'3','사용 예시 1: 냉장고 청소를 더 간편하게',
  '“냉장고를 청소할 때 느끼는 불편을 줄일 기능을 찾아줘.”',
  ['“음료를 쏟으면 선반 위 식품을','모두 꺼내고 청소해야 해요.”'],
  ['선반을 분리해서','세척할 수 있는 기능 제공'],
  '분리 기능이 있어도 식품을 모두 옮기는 부담은 남는다.')
 fridge(c,16,80)
 text(c,165,152,'02  Agent가 콘셉트·요구사항 작성',9.4,True,ACCENT)
 text(c,165,130,'구획별 탈착 트레이',14,True)
 lines(c,165,109,['오염된 구획만 꺼내 세척하는 구조를 제안','전체 식품을 옮기는 부담을 줄이는 방향'],9.8,16)
 text(c,165,72,'검토할 요구사항  용량 · 탈착 편의 · 세척성',9.1,color=MUTED)
 example_footer(c,'새 자료와 겹치면 후보를 제외하고 다시 제안',
  '근거·설계 조건을 확인하고 콘셉트 채택·보완')

def example_header(c,number,label,request,review,spec,conclusion):
 title(c,354,number,label)
 rect(c,2,289,436,39,PALE,PALE);text(c,12,312,'기획자 입력  |  요청과 자료 제공',9.3,True)
 text(c,12,296,request,10.5,True)
 text(c,2,270,'고객 리뷰',10,True);lines(c,2,251,review,10,16)
 text(c,246,270,'제품 설명서',10,True);lines(c,246,251,spec,10,16)
 line(c,215,232,215,274)
 line(c,102,232,102,226);line(c,337,232,337,226)
 line(c,102,226,337,226);arrow(c,220,226,220,218,ACCENT)
 rect(c,2,38,436,178,WASH,ACCENT,1)
 rect(c,2,195,436,21,ACCENT,ACCENT)
 text(c,12,201,'AGENT 수행 구간',11,True,'#FFFFFF')
 text(c,151,202,'자료 대조 → 기획안 작성 → 검사·수정',9.6,color='#FFFFFF')
 text(c,12,179,'01  분석·대조',9.3,True,ACCENT)
 text(c,95,179,conclusion,9.5,True)
 line(c,12,171,428,171,'#D9B8C3')

def example_footer(c,revision,review):
 line(c,12,61,428,61,'#D9B8C3')
 text(c,12,46,'03  검사·수정',9.3,True,ACCENT)
 text(c,95,46,revision,9.4)
 arrow(c,220,34,220,23,ACCENT)
 text(c,2,8,'기획자 검토',9.5,True)
 text(c,87,8,review,9.4,color=MUTED)

def loading_guide(c):
 example_header(c,'4','사용 예시 2: 식기 조합에 맞는 적재 안내',
  '“식기세척기에 그릇을 배치할 때의 불편을 줄일 서비스를 찾아줘.”',
  ['“큰 접시와 냄비를 같이 넣을 때','어디에 놓아야 할지 모르겠어요.”'],
  ['기본 적재 그림과','자동 세척 코스 제공'],
  '기본 예시만으로는 내 식기 조합을 배치하기 어렵다.')
 dishwasher(c)
 text(c,170,152,'02  Agent가 서비스·요구사항 작성',9.4,True,ACCENT)
 text(c,170,130,'식기 조합별 배치 가이드',13,True)
 lines(c,170,109,['종류·크기별 적재 순서를 안내하는 서비스','큰 식기·회전 날개 간섭 확인 기능을 제안'],9.4,16)
 text(c,170,72,'검토할 요구사항  조합 입력 · 모델별 배치 규칙',8.9,color=MUTED)
 example_footer(c,'식기·제품 조건이 바뀌면 안내 기능을 재검토',
  '서비스 흐름과 필요한 기능을 확인하고 채택·보완')

def duplicate_filter(c):
 example_header(c,'5','사용 예시 3: 이미 있는 기능은 걸러내기',
  '“전자레인지에서 매일 같은 설정을 반복하는 불편을 줄여줘.”',
  ['“매일 같은 음식을 데우는데','시간과 출력을 다시 입력해요.”'],
  ['내 설정 저장과','원터치 호출 기능 제공'],
  '‘자주 쓰는 설정 저장’은 이미 제공되는 기능이다.')
 microwave(c)
 text(c,170,152,'02  Agent가 중복 제외·확인 질문 작성',9.2,True,ACCENT)
 text(c,170,130,'중복 후보 제외 · 추가 확인',13,True)
 lines(c,170,109,['저장 기능을 알고 사용해 봤는가?', '등록 과정이나 호출 위치가 불편한가?'],9.8,16)
 text(c,170,72,'다음 기획 방향  사용 과정에서 남은 불편 확인',8.9,color=MUTED)
 example_footer(c,'추가 리뷰·조건을 반영해 남은 불편을 다시 분석',
  '추가 확인할 질문을 검토하고 자료·조건 보완')

def save(name,height,draw):
 pdf=TMP/(name+'.pdf');c=canvas.Canvas(str(pdf),pagesize=(440,height));c.setTitle(name);draw(c);c.showPage();c.save()
 subprocess.run([str(POPPLER),'-singlefile','-r','300','-png',str(pdf),str(OUT/name)],check=True)

if __name__=='__main__':
 save('01_아이디어_한눈에',236,overview)
 save('02_Agent_작동방식',220,workflow)
 save('03_냉장고_사용예시',370,example)
 save('04_식기세척기_사용예시',370,loading_guide)
 save('05_전자레인지_사용예시',370,duplicate_filter)
 print('Created idea overview, Agent workflow, and three usage examples.')
