#!/usr/bin/env python3
"""Tests for repo_pack.py, including the project-store snapshot guards:
dirty tree, credential URL, absolute --repo and slice handling; the selected-path
guard (inside the repository, no symbolic link, normal form, a regular file of
the commit's tree, bytes read from the commit and never the working tree); and
clone's --force-refresh against a local bare repository, which refuses rather
than overwrites an ignored local file."""
import argparse, contextlib, io, os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RP = os.path.join(HERE, "repo_pack.py")
import importlib.util
spec = importlib.util.spec_from_file_location("repo_pack", RP)
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)

def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

class Fixture(unittest.TestCase):
    def setUp(self):
        # 2026-08-30 rule: remove-and-recreate, never rm -rf "$d"/*
        self.root = tempfile.mkdtemp(prefix="rp-fix-")
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(self.repo)
        sh(["git", "init", "-q"], cwd=self.repo)
        sh(["git", "config", "user.email", "t@t"], cwd=self.repo)
        sh(["git", "config", "user.name", "t"], cwd=self.repo)
        open(os.path.join(self.repo, "plain.md"), "w").write("# planted-doc-e7q1\nhello\n")
        open(os.path.join(self.repo, "nested.md"), "w").write("outer\n```\ninner fence body\n```\ntail " + "[" * 2 + "link" + "]" * 2 + " [x](bareword)\n## in-body heading that must not count as a section\n")
        open(os.path.join(self.repo, "big.md"), "w").write("A" * (70 * 1024))  # C1: 70 KiB
        open(os.path.join(self.repo, "ptr.bin"), "wb").write(b"version https://git-lfs.github.com/spec/v1\noid sha256:aa\n")
        open(os.path.join(self.repo, "ctrl.md"), "wb").write(b"line\x0cfeed\n")
        sh(["git", "add", "-A"], cwd=self.repo); sh(["git", "commit", "-qm", "fix"], cwd=self.repo)
        self.sha = sh(["git", "rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        self.url = "https://github.com/fixture/repo"
        sh(["git", "remote", "add", "origin", self.url], cwd=self.repo)

    def tearDown(self):
        shutil.rmtree(self.root)

    def build(self, rels, **kw):
        return rp.build_pack(self.repo, rels, self.url, self.sha, kw.get("slice"), 2, "test")

    def pack(self, *extra):
        """Run the real verb with --no-write against the fixture by ABSOLUTE path (the project-store shape)."""
        return sh([sys.executable, RP, "pack-and-write", "--repo", self.repo, "--ledger-id", "t", "--no-write", *extra])

    def test_planted_file_appears_and_sha_pinned(self):
        body, n = self.build(["plain.md"])
        self.assertIn("planted-doc-e7q1", body)
        self.assertIn(f"- sha: {self.sha}", body)          # pin proof vs git rev-parse
        self.assertEqual(n, 1)
        self.assertIsNone(rp.self_check(body))

    def test_nested_fence_escalates_and_roundtrips_capture_write(self):
        body, _ = self.build(["nested.md"])
        m = re.search(r"^(`{4,})\n", body, re.M)
        self.assertIsNotNone(m, "fence must escalate past interior ```")
        # round-trip through the real sanitiser: fenced bodies byte-exact (no control bytes here)
        sys.path.insert(0, HERE)
        import capture_write as cw
        sanitised = cw.sanitise(body) if hasattr(cw, "sanitise") else None
        if sanitised is not None:
            self.assertIn("inner fence body", sanitised)
            self.assertIn("[" * 2 + "link" + "]" * 2, sanitised)           # inside fence → NOT defanged
            self.assertIn("[x](bareword)", sanitised)

    def test_C1_whole_file(self):
        body, _ = self.build(["big.md"])
        self.assertIn("A" * (70 * 1024), body)
        self.assertNotIn("[TRUNCATED at", body)

    def test_lfs_pointer_skipped_and_empty_selection_refused(self):
        body, n = self.build(["ptr.bin", "plain.md"])
        self.assertIn("git-LFS pointer", body); self.assertEqual(n, 1)
        with self.assertRaises(SystemExit):                # only skippables → §11 refusal
            self.build(["ptr.bin"])

    def test_control_bytes_noted(self):
        body, _ = self.build(["ctrl.md", "plain.md"])
        self.assertIn("control bytes present", body)

    def test_killed_emission_fails_self_check(self):
        body, _ = self.build(["plain.md"])
        cut = body[: len(body) // 2]                       # simulate death mid-emission
        err = rp.self_check(cut)
        self.assertIsNotNone(err, "truncated pack must fail the footer/count checker")
        self.assertIn("footer", err)

    def test_count_invariant_fires(self):
        body, _ = self.build(["plain.md", "nested.md"])
        bad = body.replace("- files: 2", "- files: 3")
        self.assertIsNotNone(rp.self_check(bad))

    def test_clean_refuses_outside_store(self):            # negative control
        r = sh([sys.executable, RP, "clean", "--repo", "../../etc"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refusing", r.stderr)

    # ---- project-store snapshot guards (2026-09-07) -------------------------------------------------

    def test_clean_refuses_project_store_root(self):       # the decisive negative control (design rollout step 4)
        target = os.path.expanduser("~/.llm-wiki/projects/fixture-never-created")
        r = sh([sys.executable, RP, "clean", "--repo", target])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refusing", r.stderr)

    def test_pack_accepts_absolute_repo_outside_store(self):   # positive control
        r = self.pack("--paths", "plain.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pack ok: 1 files", r.stdout)

    def test_credential_remote_refused_and_bare_user_stripped(self):
        sh(["git", "remote", "set-url", "origin", "https://git:tok-e7q1@host.example/x"], cwd=self.repo)
        r = self.pack("--paths", "plain.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("credential part", r.stderr)
        self.assertNotIn("pack ok", r.stdout)               # refused before any emission
        self.assertNotIn("tok-e7q1", r.stdout + r.stderr)   # the secret never echoed
        sh(["git", "remote", "set-url", "origin", "https://git@git.overleaf.example/abc"], cwd=self.repo)
        body, _ = rp.build_pack(self.repo, ["plain.md"], "https://git@git.overleaf.example/abc", self.sha, None, 2, "t")
        self.assertIn("- repo: https://git.overleaf.example/abc\n", body)   # bare user part dropped from the header

    def test_dirty_tracked_file_refused(self):              # the guard fires
        open(os.path.join(self.repo, "plain.md"), "a").write("edit after commit\n")
        r = self.pack("--paths", "nested.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dirty tree", r.stderr)
        self.assertIn("plain.md (modified", r.stderr)

    def test_unselected_untracked_never_blocks_but_selected_does(self):   # the guard does not fire, then does
        open(os.path.join(self.repo, ".DS_Store"), "wb").write(b"\x00\x00")
        open(os.path.join(self.repo, "notes-untracked.md"), "w").write("draft\n")
        r = self.pack("--paths", "plain.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        r2 = self.pack("--paths", "plain.md,notes-untracked.md")
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("notes-untracked.md (untracked, selected)", r2.stderr)

    def test_C6_allow_large_records_only(self):
        plain = self.pack("--paths", "big.md")
        flagged = self.pack("--paths", "big.md", "--allow-large", "why")
        bodies = []
        for result in (plain, flagged):
            self.assertEqual(result.returncode, 0, result.stderr)
            path = re.search(r" · tmp (.+)", result.stdout).group(1)
            with open(path) as stream:
                bodies.append(stream.read())
            os.remove(path)
        for body in bodies:
            self.assertIn("A" * (70 * 1024), body)
            self.assertNotIn("[TRUNCATED at", body)
        self.assertNotIn("allow-large:", bodies[0])
        self.assertEqual(bodies[1].replace(" · allow-large: why", ""), bodies[0])

    def test_provenance_distinct_per_slice_and_defaults_to_sha12(self):
        u = "https://git.overleaf.example/abc"
        p1 = rp.provenance(u, self.sha, "aaaa1111")
        p2 = rp.provenance(u, self.sha, "bbbb2222")
        self.assertNotEqual(p1, p2)
        self.assertEqual(rp.provenance(u, self.sha, "aaaa1111"), p1)     # a repeated slice repeats the provenance
        self.assertEqual(rp.provenance(u, self.sha, None), f"{u}#{self.sha[:12]}")   # non-GitHub default: the short sha
        self.assertEqual(rp.provenance("https://github.com/o/r", self.sha, None), f"https://github.com/o/r/tree/{self.sha}")

    # ---- selected paths stay inside the repository, so the header sha describes every byte packed --------------

    def outside(self):
        path = os.path.join(self.root, "outside.md")       # beside the repository, never in it
        with open(path, "w") as fh: fh.write("# bytes-from-outside-e7q1\n")
        return path

    def assert_refused(self, r, why):
        m = re.search(r" · tmp (.+)", r.stdout)
        if m: os.remove(m.group(1))                        # an unguarded copy emits a pack: leave no temp file
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(f"selected path refused ({why})", r.stderr)
        self.assertNotIn("pack ok", r.stdout)
        self.assertNotIn("bytes-from-outside-e7q1", r.stdout + r.stderr)

    def test_absolute_and_escaping_selection_refused(self):
        out = self.outside()
        self.assert_refused(self.pack("--paths", out), "absolute")
        self.assert_refused(self.pack("--paths", "../outside.md"), "outside the repository")
        with self.assertRaises(SystemExit) as cm:          # build_pack refuses for any caller, before reading a file
            self.build(["plain.md", "../outside.md"])
        self.assertEqual(cm.exception.code, 2)

    def test_tracked_symlink_refused(self):
        out = self.outside()
        os.symlink(out, os.path.join(self.repo, "link-out.md"))
        os.symlink("plain.md", os.path.join(self.repo, "link-in.md"))
        sh(["git", "add", "-A"], cwd=self.repo); sh(["git", "commit", "-qm", "links"], cwd=self.repo)   # tracked: a clean tree
        self.assert_refused(self.pack("--paths", "link-out.md"), "a symbolic link")
        self.assert_refused(self.pack("--paths", "link-in.md"), "a symbolic link")   # the commit holds a link, not plain.md's bytes

    def test_selection_inside_repository_still_packs(self):   # control: the guard never fires on the repository's own files
        os.makedirs(os.path.join(self.repo, "sub"))
        with open(os.path.join(self.repo, "sub", "doc.md"), "w") as fh: fh.write("# nested-doc-e7q1\n")
        sh(["git", "add", "-A"], cwd=self.repo); sh(["git", "commit", "-qm", "sub"], cwd=self.repo)
        for extra in (("--paths", "sub/doc.md,plain.md"), ("--globs", "*.md")):
            r = self.pack(*extra)
            m = re.search(r" · tmp (.+)", r.stdout)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(m.group(1)) as fh: body = fh.read()
            os.remove(m.group(1))
            self.assertIn("planted-doc-e7q1", body)

    # ---- every byte packed is the commit's: a regular file of its tree, read from the object store ------------

    def commit(self, msg):
        sh(["git", "add", "-A"], cwd=self.repo); sh(["git", "commit", "-qm", msg], cwd=self.repo)
        self.sha = sh(["git", "rev-parse", "HEAD"], cwd=self.repo).stdout.strip()

    def assert_clean(self):                                # premise: guard (a) sees nothing to refuse
        self.assertEqual(sh(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.repo).stdout, "")

    def test_unnormalised_spelling_refused(self):
        with open(os.path.join(self.repo, "notes.md"), "w") as fh: fh.write("# bytes-from-outside-e7q1 untracked\n")
        self.assertIn("?? notes.md", sh(["git", "status", "--porcelain"], cwd=self.repo).stdout)   # premise: untracked
        self.assert_refused(self.pack("--paths", "./notes.md"), "not in normal form")   # matches no status line
        self.assert_refused(self.pack("--paths", "./plain.md"), "not in normal form")   # a tracked file too: the spelling decides

    def test_ignored_file_refused(self):
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh: fh.write("notes-ignored.md\n")
        self.commit("ignore rule")
        with open(os.path.join(self.repo, "notes-ignored.md"), "w") as fh: fh.write("# bytes-from-outside-e7q1 ignored\n")
        self.assert_clean()
        self.assertIn("!! notes-ignored.md", sh(["git", "status", "--porcelain", "--ignored"], cwd=self.repo).stdout)
        why = f"not a file of commit {self.sha[:12]}"
        self.assert_refused(self.pack("--paths", "notes-ignored.md"), why)
        self.assert_refused(self.pack("--globs", "*.md"), why)                 # a glob reaches it the same way

    def test_path_through_an_internal_symlinked_directory_refused(self):
        os.makedirs(os.path.join(self.repo, "realdir"))
        with open(os.path.join(self.repo, "realdir", "doc.md"), "w") as fh: fh.write("# real-doc-e7q1\n")
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh: fh.write("scratchdir/\n")
        os.symlink("realdir", os.path.join(self.repo, "linkdir"))      # tracked links to directories inside the repository
        os.symlink("scratchdir", os.path.join(self.repo, "linkign"))
        self.commit("links to directories")
        os.makedirs(os.path.join(self.repo, "scratchdir"))
        with open(os.path.join(self.repo, "scratchdir", "doc.md"), "w") as fh: fh.write("# bytes-from-outside-e7q1 ignored\n")
        self.assert_clean()
        for rel in ("linkdir/doc.md", "linkign/doc.md"):              # the commit holds no file at either path
            self.assert_refused(self.pack("--paths", rel), f"not a file of commit {self.sha[:12]}")
        r = self.pack("--paths", "realdir/doc.md")                     # control: the real path packs
        m = re.search(r" · tmp (.+)", r.stdout)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(m.group(1)) as fh: body = fh.read()
        os.remove(m.group(1))
        self.assertIn("## realdir/doc.md\n\n```\n# real-doc-e7q1\n\n```\n", body)

    def test_submodule_entry_and_its_contents_refused(self):
        sh(["git", "update-index", "--add", "--cacheinfo", f"160000,{self.sha},mod"], cwd=self.repo)   # a gitlink entry
        sh(["git", "commit", "-qm", "gitlink"], cwd=self.repo)
        self.sha = sh(["git", "rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        os.makedirs(os.path.join(self.repo, "mod"))
        with open(os.path.join(self.repo, "mod", "file.md"), "w") as fh: fh.write("# bytes-from-outside-e7q1 submodule\n")
        self.assert_clean()
        self.assert_refused(self.pack("--paths", "mod"), "a submodule")
        self.assert_refused(self.pack("--paths", "mod/file.md"), f"not a file of commit {self.sha[:12]}")

    def test_working_tree_edit_never_reaches_the_pack(self):
        with open(os.path.join(self.repo, "plain.md"), "a") as fh: fh.write("working-tree-edit-e7q1\n")
        committed = "## plain.md\n\n```\n# planted-doc-e7q1\nhello\n\n```\n"
        for staged in (False, True):                                   # unstaged, then staged: neither is the commit
            if staged:
                sh(["git", "add", "plain.md"], cwd=self.repo)
            body, n = self.build(["plain.md"])
            self.assertIn(committed, body)
            self.assertNotIn("working-tree-edit-e7q1", body)
        self.assertIn("plain.md (modified", self.pack("--paths", "plain.md").stderr)   # the verb still refuses the dirty tree

    def test_normal_case_unchanged(self):                             # control: a clean commit packs the bytes it holds
        os.makedirs(os.path.join(self.repo, "sub"))
        for rel, data in (("sub/doc.md", b"# nested-doc-e7q1\n"), ("run me.sh", b"#!/bin/sh\necho hi\n"),
                          ("data.bin", b"\x00\x01binary\n")):
            with open(os.path.join(self.repo, rel), "wb") as fh: fh.write(data)
        os.chmod(os.path.join(self.repo, "run me.sh"), 0o755)
        self.commit("more kinds")
        self.assert_clean()
        rels = ["big.md", "ctrl.md", "data.bin", "nested.md", "plain.md", "ptr.bin", "run me.sh", "sub/doc.md"]
        body, n = self.build(rels)
        packed = [rel for rel in rels if rel not in ("data.bin", "ptr.bin")]
        self.assertEqual(n, len(packed))
        for rel in packed:                                             # on a clean tree the working copy holds the same bytes
            with open(os.path.join(self.repo, rel), "rb") as fh: text = fh.read().decode("utf-8", errors="replace")
            f = rp.fence_for(text)
            self.assertIn(f"## {rel}\n\n{f}\n{text}\n{f}\n", body)
        self.assertIn("- skipped: data.bin (binary); ptr.bin (git-LFS pointer)\n", body)
        self.assertIn("- noted: ctrl.md (control bytes present — sanitiser strip applies)\n", body)
        self.assertIsNone(rp.self_check(body))

class Clone(unittest.TestCase):
    """clone against a local bare repository (no network); the store is redirected into the fixture."""
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rp-clone-")
        work = os.path.join(self.root, "work"); os.makedirs(work)
        for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"], ["git", "config", "user.name", "t"]):
            sh(cmd, cwd=work)
        self.shas = []
        for text in ("one\n", "two\n"):
            with open(os.path.join(work, "a.md"), "w") as fh: fh.write(text)
            sh(["git", "add", "-A"], cwd=work); sh(["git", "commit", "-qm", text.strip()], cwd=work)
            self.shas.append(sh(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip())
        bare = os.path.join(self.root, "fixture-owner", "fixture-repo.git")
        sh(["git", "clone", "-q", "--bare", work, bare])
        self.url = "file://" + bare                        # file://, so --depth is honoured as for a remote
        self.keep, rp.STORE = rp.STORE, os.path.join(self.root, "store")
        self.dest = os.path.join(rp.STORE, "fixture-owner-fixture-repo")

    def tearDown(self):
        rp.STORE = self.keep
        shutil.rmtree(self.root)

    def clone(self, sha, force=False):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rp.cmd_clone(argparse.Namespace(url=self.url, sha=sha, sparse=None, force_refresh=force))
        return out.getvalue()

    def head(self):
        return sh(["git", "rev-parse", "HEAD"], cwd=self.dest).stdout.strip()

    def test_same_sha_reuses_and_a_different_sha_needs_the_flag(self):   # controls
        a, b = self.shas
        self.assertIn("cloned", self.clone(a)); self.assertEqual(self.head(), a)
        self.assertIn("reuse", self.clone(a))
        with self.assertRaises(SystemExit): self.clone(b)
        self.assertEqual(self.head(), a)

    def test_force_refresh_reaches_the_requested_sha(self):
        a, b = self.shas
        self.clone(a)
        out = self.clone(b, force=True)
        self.assertEqual(self.head(), b, out)
        self.assertIn(f"refreshed {self.dest} @ {b}", out)
        with open(os.path.join(self.dest, "a.md")) as fh: self.assertEqual(fh.read(), "two\n")

    def test_force_refresh_refuses_local_changes(self):
        a, b = self.shas
        self.clone(a)
        with open(os.path.join(self.dest, "a.md"), "w") as fh: fh.write("local edit\n")
        with self.assertRaises(SystemExit) as cm: self.clone(b, force=True)
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(self.head(), a)
        with open(os.path.join(self.dest, "a.md")) as fh: self.assertEqual(fh.read(), "local edit\n")   # never discarded

    def test_force_refresh_refuses_to_overwrite_an_ignored_file(self):
        # Commit A ignores b.md; commit B tracks it. An ignored local b.md at A is refused, never overwritten.
        work = os.path.join(self.root, "work-collide"); os.makedirs(work)
        for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"], ["git", "config", "user.name", "t"]):
            sh(cmd, cwd=work)
        shas = []
        for files, add in (({".gitignore": "b.md\n", "keep.md": "A\n"}, ["git", "add", "-A"]),
                           ({"keep.md": "B\n", "b.md": "tracked at B\n"}, ["git", "add", "-f", "keep.md", "b.md"])):
            for name, text in files.items():
                with open(os.path.join(work, name), "w") as fh: fh.write(text)
            sh(add, cwd=work); sh(["git", "commit", "-qm", "step"], cwd=work)
            shas.append(sh(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip())
        bare = os.path.join(self.root, "fixture-owner", "collide-repo.git")
        sh(["git", "clone", "-q", "--bare", work, bare])
        self.url, self.dest = "file://" + bare, os.path.join(rp.STORE, "fixture-owner-collide-repo")
        a, b = shas
        self.clone(a)
        local = os.path.join(self.dest, "b.md")
        with open(local, "w") as fh: fh.write("local ignored bytes\n")
        self.assertIn("!! b.md", sh(["git", "status", "--porcelain", "--ignored"], cwd=self.dest).stdout)   # premise: ignored
        with self.assertRaises(SystemExit) as cm: self.clone(b, force=True)
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(self.head(), a)
        with open(local) as fh: self.assertEqual(fh.read(), "local ignored bytes\n")   # never overwritten
        with open(os.path.join(self.dest, "keep.md")) as fh: self.assertEqual(fh.read(), "A\n")   # nothing half-applied

if __name__ == "__main__":
    unittest.main(verbosity=1)
