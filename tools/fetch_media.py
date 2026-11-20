"""Download referenced educational media; preserve attribution in gesture_manifest.json."""
import concurrent.futures,json,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EASY=[1,2,3,4,5,6,7,8,9,11,14,15,16,17,18,66,67,68,56,59]
MEDIUM=[19,20,21,22,23,24,25,26,29,30,32,34,35,42,44,54,58,60,61,62]
HARD=[27,28,31,33,36,37,38,39,40,41,43,45,46,48,49,50,51,70,71,75]
def fetch(e):
    folder=ROOT/'mafia_trainer/assets/media';folder.mkdir(exist_ok=True,parents=True)
    target=folder/(e['id']+('.gif' if e['kind']=='video' else '.jpg'))
    if target.exists(): return e['id']+' cached'
    raw=Path('/tmp')/(e['id']+('.mp4' if e['kind']=='video' else '.jpg'))
    for attempt in range(3):
        try:
            req=urllib.request.Request(e['url'],headers={'User-Agent':'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req,timeout=40) as resp: raw.write_bytes(resp.read())
            except urllib.error.HTTPError:
                alternate=e['url'].replace('.vkuserphoto.ru/', '.userapi.com/')
                with urllib.request.urlopen(urllib.request.Request(alternate,headers={'User-Agent':'Mozilla/5.0','Referer':'https://vk.ru/'}),timeout=40) as resp: raw.write_bytes(resp.read())
            if e['kind']=='video':
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-filter_complex','fps=10,scale=520:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer','-loop','0',str(target)],check=True)
            else: target.write_bytes(raw.read_bytes())
            return e['id']+' OK'
        except Exception as ex:
            if attempt==2:
                if e.get('poster'):
                    try:
                        with urllib.request.urlopen(e['poster'],timeout=30) as r: (folder/(e['id']+'.jpg')).write_bytes(r.read())
                        return e['id']+' POSTER (video unavailable)'
                    except Exception: pass
                return e['id']+' FAILED '+str(ex)
            time.sleep(1)
if __name__=='__main__':
    manifest=json.loads((ROOT/'tools/gesture_manifest.json').read_text())
    selected=set(EASY+MEDIUM+HARD)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch,[e for e in manifest if int(e['id'][1:]) in selected]): print(result,flush=True)
