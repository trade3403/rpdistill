from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from rpdistill.student import StudentProfile
from rpdistill.training_data import batch_arrays,batches,acquire_assets,ASSET_BYTES

P=StudentProfile(vocab=8,hidden=8,heads=2,ffn=16,encoder_layers=1,
                 decoder_layers=1,positions=8,pad=7)
A={"source_ids":[2,3,0],"target_ids":[4,0]}
B={"source_ids":[2,5,6,0],"target_ids":[4,5,0]}


class TrainingDataTests(unittest.TestCase):
    def test_masks_labels_and_shift(self):
        b=batch_arrays([A,B],P)
        self.assertEqual(b["input_ids"],[[2,3,0,7],[2,5,6,0]])
        self.assertEqual(b["attention_mask"],[[1,1,1,0],[1,1,1,1]])
        self.assertEqual(b["decoder_input_ids"],[[7,4,7],[7,4,5]])
        self.assertEqual(b["decoder_attention_mask"],[[1,1,0],[1,1,1]])
        self.assertEqual(b["labels"],[[4,0,-100],[4,5,0]])

    def test_invalid_sequences(self):
        for ids in ([2,3],[2,7,0],[2,1,0],[2,0,0],[2,9,0],[2,True,0],[2]*9+[0]):
            with self.assertRaises(ValueError):
                batch_arrays([{"source_ids":ids,"target_ids":[4,0]}],P)

    def test_dynamic_budget_splits(self):
        self.assertEqual(len(list(batches([A,B],P,max_padded_tokens=10))),2)
        with self.assertRaises(ValueError):
            list(batches([A],P,max_logits=1))
        self.assertEqual(len(list(batches([A,B],P,batch_size=1))),2)

    def test_asset_budget_and_fixed_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                acquire_assets(tmp,max_bytes=ASSET_BYTES-1)
            transfer=Mock()
            with patch("rpdistill.training_data.checked_assets"):
                result=acquire_assets(tmp,max_bytes=ASSET_BYTES,transfer=transfer)
            self.assertEqual(transfer.call_count,5)
            self.assertFalse(result["weights_downloaded"])
            self.assertTrue(all("pytorch_model" not in x.args[0] for x in transfer.call_args_list))
            self.assertTrue(all(len(x.kwargs["sha256"])==64 for x in transfer.call_args_list))
