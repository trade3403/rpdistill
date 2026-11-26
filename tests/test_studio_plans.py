import tempfile
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone,timedelta
import unittest
from rpdistill.pipeline import CorpusPipeline
from rpdistill.papers import PaperQuery
from rpdistill.inference import TranslationOptions
from rpdistill.teachers import TeacherRegistry,Teacher
from rpdistill.studio_plans import create,tick,recover,cancel,connect
from rpdistill.studio import snapshot

class StudioPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"db.sqlite3"
        self.engine=CorpusPipeline(self.db)
        self.model="fixture/model"
        self.rev="a"*40
        TeacherRegistry(self.db).put(Teacher(self.model,self.rev,"mit",False,False,None),self.root,[])
        self.template=self.engine.create(PaperQuery(("test",),"2024-01-01","2024-12-31",limit=3),self.model,self.rev,
            TranslationOptions(),root=self.root/"papers",max_bytes=1024,paper_limit=2,segment_limit=3)["id"]
        self.clock=datetime.now(timezone.utc)+timedelta(seconds=10)
    def make(self,cycles=2):
        return create(self.db,self.template,"mit",5,cycles,1024*cycles,approved=True)
    def finish(self,child,*,plan_id,state="candidate_complete"):
        # A scheduled child must not be executable independently.
        with self.assertRaisesRegex(ValueError,"belongs to its plan"):
            self.engine.run(child)
        with self.assertRaisesRegex(ValueError,"plan not ready"):
            tick(self.db,plan_id,approved=True,clock=lambda:self.clock)
        with closing(connect(self.db)) as c,c:
            c.execute("UPDATE corpus_runs SET state=?,stage=5 WHERE id=?",(state,child))
        return self.engine.get(child)
    def test_bounded_cycle_and_due(self):
        for approved,budget in ((False,2048),(True,1024)):
            with self.assertRaises(ValueError):
                create(self.db,self.template,"mit",5,2,budget,approved=approved)
        p=self.make()
        self.assertEqual(snapshot(self.db)["counts"]["plan_cycles"],0)
        with self.assertRaises(ValueError):
            tick(self.db,p["id"])
        r=tick(self.db,p["id"],approved=True,run=self.finish,clock=lambda:self.clock)
        self.assertEqual((r["claimed"],r["state"]),(1,"ready"))
        r=tick(self.db,p["id"],approved=True,run=lambda *a,**kw:self.fail("not due"),clock=lambda:self.clock)
        self.assertEqual(r["state"],"waiting")
        self.clock+=timedelta(minutes=5)
        r=tick(self.db,p["id"],approved=True,run=self.finish,clock=lambda:self.clock)
        self.assertEqual((r["claimed"],r["state"]),(2,"complete"))
        with self.assertRaises(ValueError):
            tick(self.db,p["id"],approved=True)
        s=snapshot(self.db)
        self.assertEqual(s["counts"]["plan_cycles"],2)
        self.assertEqual(s["counts"]["plan_active"],0)
        self.assertEqual(self.engine.get(self.template)["state"],"queued")
    def test_interruption_consumes_budget_and_no_replay(self):
        p=self.make()
        def crash(*args,**kwargs):
            raise RuntimeError("fixture crash before execution")
        with self.assertRaises(RuntimeError):
            tick(self.db,p["id"],approved=True,run=crash,clock=lambda:self.clock)
        s=snapshot(self.db);child=s["rows"]["plans"][0]["active_run"]
        self.assertEqual(s["rows"]["plans"][0]["claimed"],1)
        self.assertEqual(s["counts"]["plan_active"],1)
        with self.assertRaises(ValueError):
            recover(self.db,p["id"])
        with self.assertRaises(ValueError):
            tick(self.db,p["id"],approved=True)
        r=recover(self.db,p["id"],worker_stopped=True)
        self.assertEqual((r["claimed"],r["state"]),(1,"stopped"))
        self.assertEqual(self.engine.get(child)["state"],"interrupted")
        with self.assertRaises(ValueError):
            self.engine.resume(child,worker_stopped=True)
        with self.assertRaises(ValueError):
            tick(self.db,p["id"],approved=True)
    def test_insufficient_and_license_changed(self):
        p=self.make()
        r=tick(self.db,p["id"],approved=True,run=lambda child,plan_id:self.finish(child,plan_id=plan_id,state="insufficient_candidates"),clock=lambda:self.clock)
        self.assertEqual((r["claimed"],r["state"]),(1,"stopped"))
        p=self.make()
        TeacherRegistry(self.db).put(Teacher(self.model,self.rev,"apache-2.0",False,False,None),self.root,[])
        with self.assertRaisesRegex(ValueError,"license changed"):
            tick(self.db,p["id"],approved=True,clock=lambda:self.clock)
        self.assertEqual(cancel(self.db,p["id"],approved=True)["state"],"cancelled")
