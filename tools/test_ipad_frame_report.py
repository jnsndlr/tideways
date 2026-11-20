import unittest
import xml.etree.ElementTree as ET

from ipad_frame_report import FRAME_TABLE, THERMAL_TABLE, summarize


def table(name, columns, rows):
    root = ET.Element("trace-query-result")
    node = ET.SubElement(root, "node")
    schema = ET.SubElement(node, "schema", name=name)
    for col in columns:
        ET.SubElement(ET.SubElement(schema, "col"), "mnemonic").text = col
    ids = {}
    for values in rows:
        row = ET.SubElement(node, "row")
        for column, value in zip(columns, values):
            value = str(value)
            key = (column, value)
            if key in ids:
                ET.SubElement(row, "value", ref=ids[key])
            else:
                ids[key] = str(len(ids) + 1)
                ET.SubElement(row, "value", id=ids[key], fmt=value).text = value
    return root


def metric(start, count, ms, process="Tideways", variant=0, layer=1, name="Frame Interval"):
    return (start * 10**9, 10**9, ms, count, variant, name, process, f"{process} (42)", layer)


def report(metrics, states=((0, 60, "Nominal"),)):
    frames = table(FRAME_TABLE, ["start", "duration", "value-in-ms", "number-of-frames",
                                 "metric-variant", "name", "process-name", "process", "layer-id"], metrics)
    thermal = table(THERMAL_TABLE, ["start", "end", "thermal-state", "track-label"],
                    [(int(low * 1e9), int(high * 1e9), label, "Current") for low, high, label in states])
    return summarize(frames, thermal, "Tideways", 2)


class FrameReportTest(unittest.TestCase):
    def test_weights_frames_and_excludes_other_processes_variants_and_warmup(self):
        rows = report([metric(0, 100, 100), metric(2, 1, 10), metric(3, 3, 30),
                       metric(2, 4, 12, name="GPU Active Time"), metric(2, 50, 80, variant=1),
                       metric(2, 20, 70, process="Other")])
        self.assertEqual(rows, [("Tideways (42)", "1", "Nominal", 4, 25, 40, 4, 12)])

    def test_keeps_layers_thermal_transitions_and_uncovered_windows_separate(self):
        rows = report([metric(2, 2, 20), metric(3, 2, 25), metric(4, 2, 40),
                       metric(5, 2, 50), metric(2, 1, 15, layer=2)],
                      [(0, 3.5, "Nominal"), (3.5, 5, "Serious")])
        self.assertEqual({(r[1], r[2]): r[4] for r in rows},
                         {("1", "Nominal"): 20, ("1", "Partial or changing"): 25,
                          ("1", "Serious"): 40, ("1", "Unknown"): 50, ("2", "Nominal"): 15})
        self.assertTrue(all(r[6:] == (0, None) for r in rows))

    def test_missing_or_invalid_game_frames_fail(self):
        for metrics in [[metric(2, 1, 22, process="Other")], [metric(2, 0, 20)],
                        [metric(2, 1, float("nan"))]]:
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                report(metrics)


if __name__ == "__main__":
    unittest.main()
