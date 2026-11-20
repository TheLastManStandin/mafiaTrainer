"""Extract media metadata from the user's MSU Mafia reference (saved HTML)."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import json,re,sys
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data): self.parts.append(data)
def plain(s):
    p=Text();p.feed(s);return ' '.join(''.join(p.parts).split())
s=Path(sys.argv[1]).read_text()
section=''; title='';entries=[]
for match in re.finditer(r'<(h3|p|figure)\b[^>]*>.*?</\1>',s,re.S):
    block=match.group();tag=match.group(1); txt=plain(block)
    if tag=='h3': section=txt
    if tag=='p' and re.match(r'^\d+\)',txt): title=re.sub(r'^\d+\)\s*','',txt)
    if tag!='figure': continue
    video=re.search(r'<source[^>]+src="([^"]+)"',block)
    photo=re.search(r'data-sizes="([^"]+)"',block)
    url='';kind=''
    if video: url=unescape(video[1]);kind='video'
    elif photo:
        sizes=json.loads(unescape(photo[1]))[0];url=sizes.get('x',sizes['m'])[0];kind='image'
    if not url: continue
    entries.append(dict(id=f'g{len(entries)+1:02}',title=title,section=section,url=url,kind=kind,caption=txt,poster=unescape(re.search(r'poster="([^"]+)"',block)[1]) if 'poster=' in block else ''))
Path('tools/gesture_manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2))
for e in entries: print(e['id'],e['kind'],e['section'],':',e['title'],e['caption'])
