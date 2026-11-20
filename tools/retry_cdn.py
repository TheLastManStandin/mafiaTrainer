"""Retry originals on VK's alternate public CDN; do not synthesize gesture images."""
import concurrent.futures,json,urllib.request,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'tools/gesture_manifest.json').read_text())
folder=ROOT/'mafia_trainer/assets/media'
def attempt(e):
 if (folder/(e['id']+'.gif')).exists() or e['kind']!='video':return
 for base in ['psv4.userapi.com','psv4.vkuseraudio.net','psv4.vkuserphoto.ru']:
  url=e['url'].replace('psv4.vkuserphoto.ru',base)+'?download=1'
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://vk.ru/'}),timeout=12) as r:raw=r.read()
   f=Path('/tmp')/(e['id']+'-retry.mp4');f.write_bytes(raw)
   subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(f),'-filter_complex','fps=10,scale=520:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer','-loop','0',str(folder/(e['id']+'.gif'))],check=True)
   return e['id']+' animation recovered'
  except Exception:pass
 return e['id']+' original unavailable'
if __name__=='__main__':
 selected={int(x.name[1:3]) for x in folder.iterdir()}
 selected|={15,18,30,31,46,48,49,71}
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
  for result in pool.map(attempt,[e for e in manifest if int(e['id'][1:]) in selected]):
   if result:print(result,flush=True)
