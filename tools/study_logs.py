#!/usr/bin/env python3
"""Decode chunked HintBackStudy logcat records, or capture one explicitly reset trial.
No third-party dependencies. Start capture BEFORE opening the test form.
"""
import argparse
import base64
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

RECEIVER = 'com.android.talkback/com.google.android.accessibility.talkback.hintgen.HintGenSelfTestReceiver'

class Decoder:
    def __init__(self): self.pending = {}
    def feed(self, line):
        marker = line.find('{')
        if marker < 0: return None
        chunk = json.loads(line[marker:])
        if 'record_id' not in chunk: return None
        total, part = chunk['parts'], chunk['part']
        if not isinstance(total,int) or not 0 <= part < total <= 10000:
            raise ValueError('Invalid log chunk index/count')
        entry = self.pending.setdefault(chunk['record_id'], {'total':total,'chunks':{}})
        if total != entry['total']: raise ValueError('Conflicting chunk counts')
        entry['chunks'][part] = chunk['data']
        if len(entry['chunks']) != total: return None
        del self.pending[chunk['record_id']]
        return json.loads(base64.b64decode(''.join(entry['chunks'][i] for i in range(total)),validate=True))

def write_record(output, record):
    output.write(json.dumps(record,ensure_ascii=False)+'\n'); output.flush()

def decode(args):
    decoder=Decoder()
    with Path(args.input).open() as source, Path(args.output).open('x') as output:
        for line in source:
            record=decoder.feed(line)
            if record is not None: write_record(output,record)
    if decoder.pending: raise RuntimeError(f'{len(decoder.pending)} incomplete records; output is partial.')

def capture(args):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.trial): raise ValueError('Trial ID must contain 1–64 letters, digits, underscores or hyphens.')
    adb=['adb'] + (['-s',args.serial] if args.serial else [])
    subprocess.run(adb+['get-state'],check=True,capture_output=True,text=True)
    decoder=Decoder(); lines=queue.Queue(); session=None; ended=False
    def broadcast(action, extras=()):
        result=subprocess.run(adb+['shell','am','broadcast','-a','com.android.talkback.'+action,'-n',RECEIVER]+list(extras),check=True,capture_output=True,text=True,timeout=15)
        if 'Error' in result.stdout or 'Exception' in result.stdout: raise RuntimeError(result.stdout)
    with Path(args.output).open('x') as output:
        proc=subprocess.Popen(adb+['logcat','-v','raw','-T','1','-s','HintBackStudy:D','*:S'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        def pump():
            for line in proc.stdout: lines.put(line)
            lines.put(None)
        threading.Thread(target=pump,daemon=True).start()
        try:
            broadcast('HINTGEN_START_TRIAL',['--es','trial_id',args.trial,'--ez','generation_enabled',str(args.reader=='hintback').lower()])
            deadline=time.monotonic()+15
            while True:
                try: line=lines.get(timeout=0.2)
                except queue.Empty:
                    if session is None and time.monotonic()>deadline:
                        raise RuntimeError('No trial_start acknowledgement. Install the updated debug APK and enable its accessibility service.')
                    continue
                if line is None: raise RuntimeError('adb logcat ended: '+proc.stderr.read())
                record=decoder.feed(line)
                if record is None or record.get('trial_id')!=args.trial: continue
                if record['event']=='trial_start':
                    if session is not None and session != record['session_id']:
                        raise RuntimeError('Another capture reset this trial while it was running.')
                    session=record['session_id']
                    print(f'Ready: {args.trial}, generation {"on" if args.reader=="hintback" else "off"}. Open the form now. Ctrl-C after exporting the web log.',flush=True)
                if record['session_id']==session: write_record(output,record)
        except KeyboardInterrupt:
            broadcast('HINTGEN_END_TRIAL'); ended=True
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try: line=lines.get(timeout=0.2)
                except queue.Empty: continue
                if line is None: break
                record=decoder.feed(line)
                if record is not None and record.get('session_id')==session:
                    write_record(output,record)
                    if record['event']=='trial_end': break
        finally:
            if not ended:
                try: broadcast('HINTGEN_END_TRIAL')
                except Exception as error: print(f'Could not end diagnostic trial: {error}',file=sys.stderr)
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            proc.stdout.close(); proc.stderr.close()
    if decoder.pending: print('Warning: incomplete diagnostic records at capture boundary.',file=sys.stderr)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('decode'); p.add_argument('input'); p.add_argument('output'); p.set_defaults(run=decode)
    p=sub.add_parser('capture'); p.add_argument('--trial',required=True); p.add_argument('--reader',choices=['talkback','hintback'],required=True); p.add_argument('--serial'); p.add_argument('--output',required=True); p.set_defaults(run=capture)
    args=parser.parse_args()
    try: args.run(args)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        parser.exit(1,f'{error}\n')

if __name__=='__main__': main()
