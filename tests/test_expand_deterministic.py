import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

# Ensure local src/ is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from aialib.generation.expand import build_arg_parser  # type: ignore


class TestDeterministicExpansion(unittest.TestCase):
    def run_expand(self, work: Path) -> tuple[str, str]:
        spec = Path("data/prompts_v2.yaml").resolve()
        out1 = work / "prompts_expanded.jsonl"
        manifest1 = work / "manifest.json"
        argv = [
            "--spec",
            str(spec),
            "--out",
            str(out1),
            "--manifest",
            str(manifest1),
            "--seed",
            str(1337),
            "--stratify",
            "family",
        ]
        parser = build_arg_parser()
        args = parser.parse_args(argv)
        # Call module entry
        from aialib.generation.expand import load_spec, prepare_templates, iterate_instances, write_manifest
        spec_data = load_spec(args.spec)
        spec_data["__path__"] = str(args.spec)
        import random

        rng = random.Random(1337)
        templates = prepare_templates(spec_data.get("templates", []))
        instances = []
        for t in templates:
            instances.extend(list(iterate_instances(t, rng)))
        # Sort by prompt id for determinism
        instances.sort(key=lambda x: x["prompt_id"])
        # Write once, read back
        out1.parent.mkdir(parents=True, exist_ok=True)
        with out1.open("w", encoding="utf-8") as h:
            for rec in instances:
                h.write(json.dumps(rec, sort_keys=True) + "\n")
        write_manifest(manifest1, spec_data, instances)
        return out1.read_text(encoding="utf-8"), manifest1.read_text(encoding="utf-8")

    def test_byte_identical_outputs(self):
        work1 = Path(tempfile.mkdtemp(prefix="aialib_test1_"))
        work2 = Path(tempfile.mkdtemp(prefix="aialib_test2_"))
        try:
            a, a_m = self.run_expand(work1)
            b, b_m = self.run_expand(work2)
            self.assertEqual(a, b, "Expanded prompts must be byte-identical across runs with same seed")
            # Check stable ids
            first_line = a.splitlines()[0]
            obj = json.loads(first_line)
            self.assertIn("prompt_id", obj)
            self.assertIn("prompt_hash", obj)
            self.assertTrue(obj["prompt_id"])
            self.assertTrue(obj["prompt_hash"])
            # Manifest must include seed and spec hash
            m = json.loads(a_m)
            self.assertEqual(m.get("seed"), 1337)
            self.assertIn("spec_hash", m)
        finally:
            shutil.rmtree(work1, ignore_errors=True)
            shutil.rmtree(work2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
