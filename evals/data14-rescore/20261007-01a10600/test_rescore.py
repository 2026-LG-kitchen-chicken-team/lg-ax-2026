"""Toy arithmetic/approval-gate regressions; no real gold or model execution."""
from copy import deepcopy
from hashlib import sha256
import unittest
import rescore as code
class RescoreTests(unittest.TestCase):
    def setUp(self):
        self.corpus=[{'id':'UNIT-E'+str(n),'model_id':'UNIT-M','document_version':'UNIT-V','text':'unit '+str(n)} for n in range(1,12)]
        self.queries=[{'id':'UNIT-Q'+str(n),'model_id':'UNIT-M','document_version':'UNIT-V'} for n in range(1,16)]
        self.rows=[{'attempt_id':f'{m}:{n}:{r}','method':m,'query_id':'UNIT-Q'+str(n),'repeat':r,
                    'status':'success','top3':[{'id':'UNIT-E'+str(n)}] if n<=11 else []}
                   for m in ('UNIT-A','UNIT-B','UNIT-C') for n in range(1,16) for r in range(1,6)]
        self.gold={'rows':[{'query_id':'UNIT-Q'+str(n),'approved_evidence':[{
            'id':'UNIT-E'+str(n),'model_id':'UNIT-M','document_version':'UNIT-V',
            'text_utf8_sha256':sha256(('unit '+str(n)).encode()).hexdigest()}]} for n in range(1,12)]}
        self.receipt={'owner':'jeongiryang','status':'verified_PM_gold_approval','scope':'FR01-and-fixed-11-query-rescore',
            'approved_gold_canonical_sha256':code.canonical(self.gold),'source_body_sha256':'a'*64,
            'source_url':'https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#unit-only'}
    def test_no_approval_has_no_primary_score(self):
        out=code.rescore(self.rows,self.corpus,self.queries,self.gold,None)
        self.assertIsNone(out['official_11_question_metrics'])
    def test_non_PM_receipt_not_accepted(self):
        r=deepcopy(self.receipt);r['owner']='unit-not-PM'
        self.assertFalse(code.approval_allows(r,self.gold))
    def test_eleven_queries_not_fiftyfive_repetitions(self):
        rows=deepcopy(self.rows)
        for row in rows:
            if row['method']=='UNIT-A' and row['query_id']=='UNIT-Q11':row['status']='failure';row['top3']=[]
        out=code.rescore(rows,self.corpus,self.queries,self.gold,self.receipt)
        self.assertAlmostEqual(out['official_11_question_metrics']['UNIT-A']['hit_at_1'],10/11)
        self.assertEqual(out['quality_denominator_unique_supported_queries'],11)
    def test_wrong_source_text_hash_rejected(self):
        bad=deepcopy(self.gold);bad['rows'][0]['approved_evidence'][0]['text_utf8_sha256']='0'*64
        r=deepcopy(self.receipt);r['approved_gold_canonical_sha256']=code.canonical(bad)
        with self.assertRaises(AssertionError):code.rescore(self.rows,self.corpus,self.queries,bad,r)
if __name__=='__main__':unittest.main()
