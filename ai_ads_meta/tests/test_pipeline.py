"""Offline tests: API responses are canned, no network access."""

import csv
import json
import os
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from ai_ads_meta import analyze, audit, sources
from ai_ads_meta.cli import main
from ai_ads_meta.model import Record, dedupe, load_jsonl
from ai_ads_meta.taxonomy import classify, feature_names

OPENALEX = {
    "meta": {"next_cursor": None},
    "results": [{
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1000/ABC",
        "title": "Sponsored answers in <i>LLM</i> chatbots erode user trust",
        "publication_year": 2025,
        "publication_date": "2025-03-01",
        "type": "article",
        "language": "en",
        "cited_by_count": 12,
        "primary_location": {"source": {"display_name": "Journal of Advertising"}},
        "authorships": [{"author": {"display_name": "A. Author"}, "countries": ["UA", "US"]}],
        "open_access": {"is_oa": True},
        "keywords": [{"display_name": "Advertising"}],
        "abstract_inverted_index": {
            "We": [0], "run": [1], "an": [2], "experiment": [3], "showing": [4], "that": [5],
            "undisclosed": [6], "advertising": [7], "in": [8], "chatbots": [9], "reduces": [10],
            "trust": [11], "and": [12], "raises": [13], "manipulation": [14], "concerns.": [15],
        },
    }],
}
CROSSREF = {"message": {"next-cursor": None, "items": [
    {   # same paper as the OpenAlex one -> must merge
        "DOI": "10.1000/abc", "title": ["Sponsored answers in LLM chatbots erode user trust"],
        "container-title": ["Journal of Advertising"], "type": "journal-article",
        "author": [{"given": "A.", "family": "Author"}, {"given": "B.", "family": "Second"}],
        "issued": {"date-parts": [[2025, 3]]}, "is-referenced-by-count": 15,
    },
    {   # irrelevant: advertising but no AI
        "DOI": "10.1000/xyz", "title": ["Billboard advertising in rural areas"],
        "issued": {"date-parts": [[2020]]}, "abstract": "<jats:p>A survey of outdoor ads.</jats:p>",
    },
]}}
ARXIV = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <published>2025-01-02T00:00:00Z</published>
    <title>Personalized advertising with
      large language models: privacy risks</title>
    <summary>We benchmark generative AI ad targeting and its privacy harms.</summary>
    <author><name>C. Third</name></author>
    <category term="cs.CY"/>
  </entry>
</feed>"""


def fake_fetch(calls):
    def fetch(url):
        calls.append(url)
        host = urlparse(url).netloc
        if "openalex" in host:
            return json.dumps(OPENALEX).encode()
        if "crossref" in host:
            return json.dumps(CROSSREF).encode()
        # arXiv: one page of results, then an empty feed
        if parse_qs(urlparse(url).query)["start"] == ["0"]:
            return ARXIV
        return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
    return fetch


class LiteratureTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._sleep = sources.time.sleep
        sources.time.sleep = lambda s: None
        raw = sources.collect(["advertising large language models"], list(sources.SOURCES),
                              fake_fetch(self.calls), from_year=2018, limit=50,
                              log=open(os.devnull, "w"))
        self.raw = raw
        self.records = [classify(r) for r in dedupe(raw)]

    def tearDown(self):
        sources.time.sleep = self._sleep

    def test_requests(self):
        q = parse_qs(urlparse(self.calls[0]).query)
        self.assertEqual(q["filter"], ["from_publication_date:2018-01-01"])
        arxiv = parse_qs(urlparse(self.calls[-1]).query)["search_query"][0]
        self.assertEqual(arxiv, "all:advertising AND all:large AND all:language AND all:models")

    def test_parse_and_merge(self):
        self.assertEqual(len(self.raw), 4)
        self.assertEqual(len(self.records), 3)
        r = self.records[0]
        self.assertEqual(r.doi, "10.1000/abc")
        self.assertEqual(r.title, "Sponsored answers in LLM chatbots erode user trust")
        self.assertTrue(r.abstract.startswith("We run an experiment"))
        self.assertEqual(r.source, "openalex; crossref")
        self.assertEqual(r.cited_by, 15)
        self.assertEqual(r.authors, ["A. Author", "B. Second"])
        self.assertEqual(r.countries, ["UA", "US"])
        self.assertEqual(self.records[2].title,
                         "Personalized advertising with large language models: privacy risks")

    def test_classification(self):
        trust, billboard, arxiv = self.records
        self.assertTrue(trust.relevant)
        self.assertIn("conversational_ads", trust.ad_format)
        self.assertIn("covert_dark_patterns", trust.ad_format)
        self.assertIn("trust_credibility", trust.user_effect)
        self.assertIn("manipulation_persuasion", trust.user_effect)
        self.assertEqual(trust.method, ["experiment"])
        self.assertEqual(trust.framing, "risk")
        self.assertFalse(billboard.relevant)
        self.assertEqual(billboard.abstract, "A survey of outdoor ads.")
        self.assertTrue(arxiv.relevant)
        self.assertIn("targeting_personalization", arxiv.ad_format)
        self.assertIn("privacy", arxiv.user_effect)
        self.assertIn("system_audit", arxiv.method)

    def test_analyze_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            s = analyze.run(self.records, d)
            self.assertEqual((s["collected"], s["relevant"]), (3, 2))
            self.assertEqual(s["by_year"], {"2025": 2})
            self.assertEqual(s["format_x_effect"]["conversational_ads"]["trust_credibility"], 1)
            self.assertEqual(s["top_cited"][0]["cited_by"], 15)
            with open(os.path.join(d, "features.csv")) as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["year"] + feature_names() + ["framing_risk"])
            self.assertEqual(len(rows), 3)
            self.assertTrue(set(rows[1][1:]) <= {"0", "1"})
            with open(os.path.join(d, "relevant.csv"), encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)
            with open(os.path.join(d, "report.md"), encoding="utf-8") as f:
                self.assertIn("| trust_credibility | 1 | 50.0 |", f.read())

    def test_cli_run(self):
        real = sources.make_fetch
        sources.make_fetch = lambda mailto="": fake_fetch([])
        try:
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(main(["run", "--out", d, "--max-per-query", "10"]), 0)
                self.assertEqual(len(load_jsonl(os.path.join(d, "records.jsonl"))), 3)
                self.assertTrue(os.path.exists(os.path.join(d, "summary.json")))
        finally:
            sources.make_fetch = real

    def test_failed_source_is_not_fatal(self):
        def flaky(url):
            if "crossref" in url:
                raise OSError("boom")
            return fake_fetch([])(url)
        got = sources.collect(["q"], ["openalex", "crossref"], flaky, log=open(os.devnull, "w"))
        self.assertEqual(len(got), 1)


class DedupeTest(unittest.TestCase):
    def test_title_fallback(self):
        a = Record(source="arxiv", title="Ads in LLMs: A Study", queries=["q1"])
        b = Record(source="crossref", title="Ads in LLMs - a study", doi="10.1/x", queries=["q2"])
        c = Record(source="openalex", title="Another title", doi="10.1/x")
        out = dedupe([a, b, c])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].doi, "10.1/x")
        self.assertEqual(out[0].queries, ["q1", "q2"])


class AuditTest(unittest.TestCase):
    def test_example_log(self):
        here = os.path.dirname(os.path.dirname(__file__))
        with tempfile.TemporaryDirectory() as d:
            s = audit.run(os.path.join(here, "examples", "chat_log.jsonl"), d,
                          ["Acme Glide", "Zenbook Lite"])
            with open(os.path.join(d, "audit.csv"), encoding="utf-8-sig") as f:
                rows = {r["id"]: r for r in csv.DictReader(f)}
        self.assertEqual(s["overall"]["responses"], 4)
        self.assertEqual(s["overall"]["share_with_ad_signal"], 0.5)
        self.assertEqual(s["by_model"]["bot-a"]["share_disclosed"], 0.5)
        self.assertEqual(s["by_model"]["bot-b"]["share_undisclosed_promo"], 0.5)
        self.assertEqual(rows["1"]["tracking_params"], "aff; utm_source")
        self.assertEqual(rows["1"]["disclosed"], "True")
        self.assertEqual(rows["3"]["undisclosed_promo"], "True")
        self.assertEqual(rows["3"]["domains"], "store.example.org")
        self.assertEqual(json.loads(rows["3"]["brands"]), {"Zenbook Lite": 1})
        self.assertEqual(rows["2"]["has_ad_signal"], "False")
        self.assertEqual(rows["4"]["has_ad_signal"], "False")


if __name__ == "__main__":
    unittest.main()
