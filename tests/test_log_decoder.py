import base64
import importlib.util
import json
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('study_logs',Path(__file__).resolve().parents[1]/'tools/study_logs.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

class LogDecoderTest(unittest.TestCase):
    def chunks(self,key,record):
        data=base64.b64encode(json.dumps(record,ensure_ascii=False).encode()).decode()
        chunks=[data[i:i+80] for i in range(0,len(data),80)]
        return ['D/HintBackStudy: '+json.dumps({'record_id':key,'part':i,'parts':len(chunks),'data':chunk}) for i,chunk in enumerate(chunks)]
    def test_unicode_multiline_interleaved_records(self):
        record={'event':'request','prompt':"First line\n'नाम' "*2000}
        decoder=module.Decoder(); chunks=self.chunks('a',record)
        self.assertIsNone(decoder.feed(chunks[0]))
        self.assertEqual(decoder.feed(self.chunks('b',{'event':'focus'})[0]),{'event':'focus'})
        for chunk in reversed(chunks[1:]): result=decoder.feed(chunk)
        self.assertEqual(result,record); self.assertFalse(decoder.pending)
    def test_missing_chunk_stays_incomplete(self):
        decoder=module.Decoder()
        for chunk in self.chunks('a',{'prompt':'x'*100})[:-1]: self.assertIsNone(decoder.feed(chunk))
        self.assertTrue(decoder.pending)

if __name__=='__main__': unittest.main()
