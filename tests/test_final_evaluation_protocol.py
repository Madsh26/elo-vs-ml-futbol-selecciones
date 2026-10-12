"""Protocol and integrity checks without loading post-2022 outcomes."""
from pathlib import Path
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_final_evaluation import frozen_checks,protocol_checks


class EvaluationProtocolTests(unittest.TestCase):
    def test_frozen_integrity_and_reference_commit(self):
        check=frozen_checks()
        self.assertTrue(check['models_selected_commit'].startswith('3297696'))
        self.assertEqual(check['protected_code_files_checked'],5)

    def test_protocol_seal_gate_and_predefined_populations(self):
        protocol_checks()
        protocol=json.loads((ROOT/'reports/final_evaluation/protocol.json').read_text(encoding='utf-8'))
        self.assertTrue(protocol['approval_required_before_any_post2022_metric'])
        self.assertEqual(protocol['evaluation_population']['evidence_status'],'semiconfirmatory, not untouched')
        self.assertEqual(protocol['uncertainty']['bootstrap_replicates'],2000)
        self.assertEqual(len(protocol['subperiods']),4)
        self.assertEqual(len(set(protocol['worldcup_48'])),48)
        self.assertEqual(protocol['strata']['strong_teams']['home_elo_strictly_greater_than'],1700)
        self.assertNotIn('DataCamp',protocol['comparators'])
        self.assertEqual(protocol['product_separation']['reconciliation'],'none')

    def test_probability_discrepancy_is_selection_evidence_only(self):
        difference=json.loads((ROOT/'reports/final_evaluation/pre2023_product_discrepancy.json').read_text(encoding='utf-8'))
        self.assertFalse(difference['post2022_metrics_computed'])
        self.assertEqual(difference['matches'],6376)
        self.assertGreaterEqual(difference['mean_absolute_probability_difference'],0)
        self.assertLessEqual(difference['mean_absolute_probability_difference'],1)


if __name__=='__main__':unittest.main()
