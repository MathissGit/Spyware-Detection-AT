"""Tests unitaires scripts/build_iocs.py : types STIX2 complets, branches non couvertes."""
import json
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
try:
    import build_iocs as bi
finally:
    sys.path.pop(0)


class TestLoadJson:
    def test_valid_json(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        assert bi.load_json(str(p)) == {"key": "value"}

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            bi.load_json(str(p))


class TestSourceContent:
    def test_file_local(self, tmp_path):
        p = tmp_path / "ioc.yaml"
        p.write_text("- name: test\n", encoding="utf-8")
        source = {"name": "test", "type": "yaml", "file": str(p)}
        assert bi.source_content(source) == "- name: test\n"

    def test_file_relative(self, monkeypatch, tmp_path):
        (tmp_path / "local.yaml").write_text("- name: x\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(bi, "SCRIPT_DIR", str(tmp_path))
        source = {"name": "x", "type": "yaml", "file": "local.yaml"}
        content = bi.source_content(source)
        assert content == "- name: x\n"

    def test_file_not_found(self):
        source = {"name": "x", "type": "yaml", "file": "/nonexistent.yaml"}
        assert bi.source_content(source) is None

    def test_github_source_no_requests(self, monkeypatch):
        monkeypatch.setattr(bi, "requests", None)
        source = {"name": "x", "github": {"owner": "o", "repo": "r",
                                            "branch": "main", "path": "f.yaml"}}
        assert bi.source_content(source) is None

    def test_url_no_requests(self, monkeypatch):
        monkeypatch.setattr(bi, "requests", None)
        source = {"name": "x", "url": "https://example.com/ioc.yaml"}
        assert bi.source_content(source) is None

    def test_empty_source(self):
        source = {"name": "empty"}
        assert bi.source_content(source) is None

    def test_github_url_construction(self, monkeypatch):
        called_url = {}
        class FakeRequests:
            @staticmethod
            def get(url, **kw):
                called_url["url"] = url
                class R:
                    status_code = 200
                    text = "- name: ok\n"
                return R()
        monkeypatch.setattr(bi, "requests", FakeRequests)
        source = {"name": "test", "github": {"owner": "myorg",
                                              "repo": "myrepo",
                                              "branch": "main",
                                              "path": "indicators.yaml"}}
        content = bi.source_content(source)
        assert called_url["url"].startswith("https://raw.githubusercontent.com/")
        assert "myorg" in called_url["url"]
        assert content == "- name: ok\n"

    def test_github_404(self, monkeypatch):
        class FakeRequests:
            @staticmethod
            def get(url, **kw):
                class R:
                    status_code = 404
                    text = ""
                return R()
        monkeypatch.setattr(bi, "requests", FakeRequests)
        source = {"name": "x", "github": {"owner": "o", "repo": "r",
                                            "branch": "main", "path": "f"}}
        assert bi.source_content(source) is None


class TestIndicatorsFromYaml:
    def test_valid_list(self):
        yaml_str = "- name: A\n  packages: [com.a]\n- name: B\n"
        entries = bi.indicators_from_yaml(yaml_str)
        assert len(entries) == 2

    def test_invalid_yaml(self):
        entries = bi.indicators_from_yaml("{{bad yaml")
        assert entries == []

    def test_not_a_list(self):
        entries = bi.indicators_from_yaml("key: value")
        assert entries == []

    def test_filters_non_dicts(self):
        yaml_str = "- name: A\n- not a dict\n- name: B\n  packages: [x]\n"
        entries = bi.indicators_from_yaml(yaml_str)
        assert len(entries) == 2


class TestBuildStix2FullPatterns:
    def test_all_indicator_types(self):
        indicators = [{
            "name": "TestMalware",
            "type": "stalkerware",
            "packages": ["com.test.pkg"],
            "certificates": ["ABCDEF1234567890"],
            "websites": ["evil.com", "https://evil2.com/path"],
            "distribution": ["malware.com/dist"],
            "c2": {"domains": ["c2.evil.com"], "ips": ["1.2.3.4"]},
            "domains": ["extra.evil.com"],
            "ips": ["5.6.7.8"],
            "emails": ["bad@evil.com"],
            "processes": ["malicious_process"],
            "hashes": ["sha256hash123"],
        }]
        bundle = bi.build_stix2(indicators, "test")
        assert bundle is not None
        assert bundle["type"] == "bundle"
        objects = bundle["objects"]
        indicators_out = [o for o in objects if o["type"] == "indicator"]
        malware_out = [o for o in objects if o["type"] == "malware"]
        rels = [o for o in objects if o["type"] == "relationship"]
        assert len(malware_out) == 1
        assert malware_out[0]["name"] == "TestMalware"
        assert len(indicators_out) >= 10
        assert len(rels) == len(indicators_out)

    def test_c2_as_list(self):
        indicators = [{"name": "X", "c2": ["domain1.com", "domain2.com"]}]
        bundle = bi.build_stix2(indicators, "test")
        assert bundle is not None
        inds = [o for o in bundle["objects"] if o["type"] == "indicator"]
        patterns = [o["pattern"] for o in inds]
        assert any("domain1.com" in p for p in patterns)

    def test_empty_indicators(self):
        bundle = bi.build_stix2([], "test")
        assert bundle is None

    def test_deduplication(self):
        seen = set()
        entries = [{"name": "A", "packages": ["com.dup"]}]
        b1 = bi.build_stix2(entries, "s1", seen_patterns=seen)
        b2 = bi.build_stix2(entries, "s2", seen_patterns=seen)
        n1 = sum(1 for o in b1["objects"] if o["type"] == "indicator")
        n2 = sum(1 for o in b2["objects"] if o["type"] == "indicator")
        assert n1 == 1
        assert n2 == 0

    def test_no_seen_patterns(self):
        entries = [{"name": "A", "packages": ["com.x"]}]
        b = bi.build_stix2(entries, "test")
        assert b is not None
        assert len(b["objects"]) > 0

    def test_ip_and_ip_key(self):
        indicators = [{"name": "X", "ip": ["1.1.1.1"], "ips": ["2.2.2.2"]}]
        bundle = bi.build_stix2(indicators, "test")
        assert bundle is not None
        patterns = [o["pattern"] for o in bundle["objects"] if o["type"] == "indicator"]
        assert any("1.1.1.1" in p for p in patterns)
        assert any("2.2.2.2" in p for p in patterns)


class TestSitePattern:
    def test_domain(self):
        assert "domain-name:value" in bi._site_pattern("evil.com")

    def test_url_with_protocol(self):
        p = bi._site_pattern("https://evil.com/path")
        assert "url:value" in p

    def test_url_without_protocol(self):
        p = bi._site_pattern("evil.com/path")
        assert "url:value" in p

    def test_www_prefix_is_domain(self):
        p = bi._site_pattern("www.evil.com")
        assert "domain-name:value" in p


class TestSlugify:
    def test_normal(self):
        assert bi.slugify("AssoEchap Stalkerware") == "assoechap_stalkerware"

    def test_special_chars(self):
        result = bi.slugify("IOC/Test@#$")
        assert result.islower()
        assert all(c.isalnum() or c in "._-" for c in result)

    def test_empty(self):
        assert bi.slugify("") == "ioc"

    def test_only_special(self):
        result = bi.slugify("@#$%")
        assert result == "ioc"


class TestDetectType:
    def test_yaml_file(self):
        source = {"file": "test.yaml"}
        assert bi.detect_type(source, "") == "yaml"

    def test_yml_file(self):
        source = {"file": "test.yml"}
        assert bi.detect_type(source, "") == "yaml"

    def test_stix2_json(self):
        content = json.dumps({"type": "bundle", "objects": []})
        source = {"file": "test.stix2"}
        assert bi.detect_type(source, content) == "stix2"

    def test_stix2_dict(self):
        source = {"file": "test.json"}
        content = json.dumps({"type": "bundle", "objects": []})
        assert bi.detect_type(source, content) == "stix2"

    def test_yaml_content_list(self):
        source = {}
        content = yaml.dump([{"name": "test"}])
        assert bi.detect_type(source, content) == "yaml"

    def test_github_yaml(self):
        source = {"github": {"path": "iocs.yaml"}}
        assert bi.detect_type(source, "") == "yaml"

    def test_invalid_json_file(self):
        source = {"file": "test.json"}
        assert bi.detect_type(source, "not json") == "json"


class TestWriteStix2:
    def test_writes_file(self, tmp_path):
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
            {"type": "malware", "name": "m"},
        ]}
        path = str(tmp_path / "test.stix2")
        count = bi.write_stix2(path, bundle)
        assert count == 1
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["objects"]) == 2


class TestWritePassthroughSource:
    def test_valid_stix2(self, tmp_path):
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
        ]}
        path = str(tmp_path / "out.stix2")
        count = bi.write_passthrough_source(path, json.dumps(bundle))
        assert count == 1

    def test_invalid_json(self, tmp_path):
        path = str(tmp_path / "bad.stix2")
        count = bi.write_passthrough_source(path, "not json")
        assert count == 0


class TestProcessSource:
    def test_yaml_source(self, tmp_path):
        yaml_content = yaml.dump([
            {"name": "TestPkg", "type": "stalkerware",
             "packages": ["com.test.pkg"]}
        ])
        source = {"name": "TestSource", "type": "yaml"}
        count = bi.process_source(source, yaml_content, str(tmp_path))
        assert count >= 1

    def test_stix2_passthrough(self, tmp_path):
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
        ]}
        source = {"name": "TestStix2", "type": "stix2"}
        count = bi.process_source(source, json.dumps(bundle), str(tmp_path))
        assert count == 1

    def test_empty_yaml_source(self, tmp_path):
        source = {"name": "Empty", "type": "yaml"}
        count = bi.process_source(source, "[]", str(tmp_path))
        assert count == 0


class TestCmdUpdate:
    def test_dry_run_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bi, "PERSONAL_FILE",
                            str(tmp_path / "iop.json"))
        (tmp_path / "iop.json").write_text(
            json.dumps({"indicators": [
                {"name": "Test", "type": "stalkerware",
                 "packages": ["com.test"]}
            ]}), encoding="utf-8")
        monkeypatch.setattr(bi, "SOURCES_FILE",
                            str(tmp_path / "ios.json"))
        (tmp_path / "ios.json").write_text(
            json.dumps({"sources": []}), encoding="utf-8")
        ret = bi.cmd_update(str(tmp_path / "out"), dry_run=True)
        assert ret == 0

    def test_no_personal(self, monkeypatch, tmp_path):
        personal = tmp_path / "personal.json"
        personal.write_text(json.dumps({"indicators": []}), encoding="utf-8")
        monkeypatch.setattr(bi, "PERSONAL_FILE", str(personal))
        monkeypatch.setattr(bi, "SOURCES_FILE",
                            str(tmp_path / "ios.json"))
        (tmp_path / "ios.json").write_text(
            json.dumps({"sources": []}), encoding="utf-8")
        ret = bi.cmd_update(str(tmp_path / "out"), dry_run=True)
        assert ret == 0


class TestCmdCheck:
    def test_empty_returns_1(self, tmp_path):
        out_dir = str(tmp_path / "empty")
        ret = bi.cmd_check(out_dir)
        assert ret == 1

    def test_fresh_returns_0(self, tmp_path):
        out_dir = str(tmp_path / "mvt_iocs")
        os.makedirs(out_dir, exist_ok=True)
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
        ]}
        with open(os.path.join(out_dir, "test.stix2"), "w",
                  encoding="utf-8") as f:
            json.dump(bundle, f)
        ret = bi.cmd_check(out_dir)
        assert ret == 0


class TestIocFilesStats:
    def test_empty_dir(self, tmp_path):
        stats = bi._ioc_files_stats(str(tmp_path / "empty"))
        assert stats == []

    def test_valid_file(self, tmp_path):
        d = tmp_path / "mvt_iocs"
        d.mkdir()
        bundle = {"type": "bundle", "objects": [
            {"type": "indicator", "pattern": "[x='y']"},
        ]}
        with open(d / "test.stix2", "w", encoding="utf-8") as f:
            json.dump(bundle, f)
        stats = bi._ioc_files_stats(str(d))
        assert len(stats) == 1
        assert stats[0]["count"] == 1

    def test_corrupt_file(self, tmp_path):
        d = tmp_path / "mvt_iocs"
        d.mkdir()
        (d / "bad.stix2").write_text("not json", encoding="utf-8")
        stats = bi._ioc_files_stats(str(d))
        assert len(stats) == 1
        assert stats[0]["count"] == -1
