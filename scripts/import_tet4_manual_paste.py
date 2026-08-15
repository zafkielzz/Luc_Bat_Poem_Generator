#!/usr/bin/env python3
"""Nhập thơ người dùng dán tay; không sửa file gốc và chỉ tạo artifact dẫn xuất."""
from __future__ import annotations
import hashlib, json, re, sys, unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from engine.evaluator import LucBatEvaluator
from engine.lexical_guard import assess
SOURCE=ROOT/'data/sft/tet4_manual_submission_TEMPLATE.md'
OUT=ROOT/'data/sft/archive/tet4_legacy_staging_v1/tet4_manual_staging_v1.jsonl'
REVIEW=ROOT/'data/sft/tet4_manual_review_v1.jsonl'
AUDIT=ROOT/'data/sft/tet4_manual_audit_v1.json'
SHORT=ROOT/'data/sft/tet4_manual_short_v1.jsonl'
URL_RE=re.compile(r'nguồn\s*:\s*(https?://\S+)',re.I)
BOUNDARY_RE=re.compile(r'^(?:nguồn\s*:|bài\s*\d+\s*:|tác giả\s*:|[-─—]{3,}|khám phá thêm)',re.I)
NOISE_RE=re.compile(r'^(?:thơ mới|nhạc đông nam á|người đông nam á)',re.I)

def clean(line):
    line=unicodedata.normalize('NFC',line).replace('\u200b','').replace('\ufeff','').strip()
    return re.sub(r'^\d+[.)]\s*','',line)

def chunks(path):
    url='manual:unknown'; author=None; group=[]
    for raw in path.read_text(encoding='utf-8').splitlines():
        line=clean(raw)
        m=URL_RE.search(line)
        if m:
            if group: yield url,author,group; group=[]
            url=m.group(1).rstrip('Nguồn').strip(); author=None; continue
        if not line:
            continue
        if line.lower().startswith('tác giả:'):
            if group: yield url,author,group; group=[]
            author=line.split(':',1)[1].strip() or None
            continue
        if BOUNDARY_RE.match(line) or NOISE_RE.match(line):
            if group: yield url,author,group; group=[]
            continue
        group.append(line)
    if group: yield url,author,group

def record(url, author, group, start, text, metrics, lexical):
    digest=hashlib.sha256(unicodedata.normalize('NFC',text).lower().encode()).hexdigest()
    return {'source_id':'tet4_manual_paste_v1','work_id':'manual:'+digest[:20], 'source_work_id':'manual-page:'+hashlib.sha256(url.encode()).hexdigest()[:20], 'source_record_id':f'{hashlib.sha256(url.encode()).hexdigest()[:12]}:{start}', 'url':url, 'domain':re.sub(r'^https?://','',url).split('/')[0], 'title':None, 'author':author, 'published_at':None, 'retrieved_at':datetime.now(timezone.utc).isoformat(), 'text':text, 'text_sha256':digest, 'metrics':{k:metrics[k] for k in ('scr','tcr','rma','combined_rma','structure_ok','is_valid_lucbat')}, 'lexical_issues':lexical['issues'], 'usage':'internal_only_user_pasted'}

def main():
    ev=LucBatEvaluator(); strict=[]; review=[]; short=[]; seen=set(); stats=Counter(); source_groups=0
    for url,author,group in chunks(SOURCE):
        source_groups+=1
        if len(group)==2:
            stats['two_line_units']+=1
            short.append({'source_id':'tet4_manual_paste_v1','source_work_id':'manual-page:'+hashlib.sha256(url.encode()).hexdigest()[:20],'url':url,'author':author,'text':'\n'.join(group),'num_lines':2,'usage':'quarantined_not_for_tet4_sft'})
        if len(group)<4: stats['under_four_lines']+=1; continue
        occupied=set()
        for i in range(len(group)-3):
            stats['windows_scanned']+=1
            text='\n'.join(group[i:i+4]); metrics=ev.evaluate(text,expected_num_lines=4); lexical=assess(text)
            if not metrics['structure_ok']: continue
            stats['structure_ok_windows']+=1
            if lexical['hard_fail']: stats['lexical_rejected']+=1; continue
            if set(range(i,i+4)) & occupied: stats['overlap_rejected']+=1; continue
            item=record(url,author,group,i,text,metrics,lexical)
            if item['text_sha256'] in seen: stats['exact_duplicates']+=1; continue
            seen.add(item['text_sha256']); occupied.update(range(i,i+4))
            if metrics['tcr']>=70 and metrics['rma']>=50: strict.append(item)
            else:
                item['review_reason']='low_rhyme_score' if metrics['rma']<50 else 'low_tone_score'; review.append(item)
    for path,rows in ((OUT,strict),(REVIEW,review),(SHORT,short)):
        path.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')
    audit={'version':'tet4-manual-paste-v1','source':str(SOURCE),'source_groups':source_groups,'strict_records':len(strict),'review_records':len(review),'short_records':len(short),'stats':dict(stats),'selection_rule':'4 lines 6-8-6-8, TCR>=70, RMA>=50, lexical pass, nonoverlap/exact dedup'}
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__': main()
